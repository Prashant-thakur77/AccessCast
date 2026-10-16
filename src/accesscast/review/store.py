# Store contract (expected_revision → 409, review_history.jsonl, exports_stale) follows PolicyCut's
# policycut/api/events.py and policycut/core/storage.py (https://github.com/xiaodouzi666/Radeon-hackathon-2026-07,
# policycut/ folder), MIT License, Copyright (c) 2026 PolicyCut Team. Rewritten for AccessCast: the revision
# check and the write happen under one lock (PolicyCut's had a check-then-write race), history write
# failures raise instead of being swallowed, and the server returns its own revision to the client.
"""S12 review state: review/state.json + review/review_history.jsonl."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from accesscast.events import now_iso
from accesscast.project import atomic_write_text, read_jsonl, sha256_file, sha256_text, write_jsonl
from accesscast.schemas import Item

ITEM_FILES = ("ad.en", "ad.hi", "ad.it", "sdh.en", "easy.en", "subs.hi", "subs.it", "vo.hi", "vo.it")
_locks: dict[str, threading.Lock] = {}


REVIEWER_STATUSES = frozenset({"approved", "rejected", "needs_revision", "pending"})  # never auto_approved


class RevisionConflict(Exception):
    def __init__(self, current: int) -> None:
        super().__init__(f"changed elsewhere (current revision {current})")
        self.current = current


class ReviewStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.state_p = root / "review" / "state.json"
        self.hist_p = root / "review" / "review_history.jsonl"
        self.lock = _locks.setdefault(str(root.resolve()), threading.Lock())

    # ------------------------------------------------------------ load / save
    def items_path(self, name: str) -> Path:
        return self.root / "items" / f"{name}.jsonl"

    def load_items(self) -> dict[str, Item]:
        out: dict[str, Item] = {}
        for name in ITEM_FILES:
            for row in read_jsonl(self.items_path(name)):
                it = Item.model_validate(row)
                out[it.id] = it
        return out

    def state(self) -> dict[str, Any]:
        if not self.state_p.exists():
            return {"schema_version": "accesscast/review-state/v1", "exports_stale": True, "items": {}}
        data: dict[str, Any] = json.loads(self.state_p.read_text(encoding="utf-8"))
        return data

    def merged(self) -> dict[str, Item]:
        """Items from items/*.jsonl with review state applied on top."""
        items = self.load_items()
        st = self.state()["items"]
        for iid, s in st.items():
            if iid in items:
                upd = {k: v for k, v in s.items() if k in Item.model_fields}
                items[iid] = Item.model_validate({**items[iid].model_dump(mode="json"), **upd})
        return items

    def _save_state(self, st: dict[str, Any]) -> None:
        atomic_write_text(self.state_p, json.dumps(st, indent=1, ensure_ascii=False, sort_keys=True) + "\n")

    def state_sha256(self) -> str:
        return sha256_file(self.state_p) if self.state_p.exists() else ""

    def init_from_items(self) -> None:
        """Seed state.json from items (keeps existing decisions for unchanged ids)."""
        with self.lock:
            st = self.state()
            for iid, it in self.load_items().items():
                cur = st["items"].get(iid)
                if cur is None or cur.get("draft_sha") != _draft_sig(it):
                    st["items"][iid] = {
                        "status": it.status.value,
                        "final": it.final,
                        "revision": 0,
                        "draft_sha": _draft_sig(it),
                        "reviewer": None,
                        "reviewed_at": None,
                        "reviewer_note": "",
                        "override_reason": None,
                        "review_seconds": 0.0,
                    }
            st["exports_stale"] = True
            self._save_state(st)

    # ------------------------------------------------------------ mutation
    def patch(
        self, item_id: str, expected_revision: int, changes: dict[str, Any], who: str, reason: str = ""
    ) -> dict[str, Any]:
        allowed = {"status", "final", "reviewer_note", "override_reason", "review_seconds"}
        bad = set(changes) - allowed
        if bad:
            raise ValueError(f"fields not editable: {sorted(bad)}")
        if "status" in changes and changes["status"] not in REVIEWER_STATUSES:
            raise ValueError(f"a reviewer may set status to {sorted(REVIEWER_STATUSES)}, not {changes['status']!r}")
        with self.lock:
            st = self.state()
            cur = st["items"].get(item_id)
            if cur is None:
                raise KeyError(item_id)
            if int(cur["revision"]) != int(expected_revision):
                raise RevisionConflict(int(cur["revision"]))
            before = {k: cur.get(k) for k in changes}
            if "review_seconds" in changes:
                changes = {
                    **changes,
                    "review_seconds": float(cur.get("review_seconds") or 0)
                    + float(changes["review_seconds"]),
                }
            text_changed = "final" in changes and changes["final"] != cur.get("final")
            cur.update(changes)
            if text_changed and "status" not in changes and cur.get("status") in ("approved", "auto_approved"):
                cur["status"] = "pending"  # an edited line must be checked and approved again
            cur["revision"] = int(cur["revision"]) + 1
            if "status" in changes and changes["status"] in ("approved", "rejected", "needs_revision"):
                cur["reviewer"] = who
                cur["reviewed_at"] = now_iso()
            st["exports_stale"] = True
            rec = {
                "ts": now_iso(),
                "who": who,
                "item": item_id,
                "before": before,
                "after": {k: cur.get(k) for k in changes},
                "reason": reason,
                "revision": cur["revision"],
            }
            self.hist_p.parent.mkdir(parents=True, exist_ok=True)
            with self.hist_p.open("a", encoding="utf-8") as fh:  # history failure raises: never silent
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            self._save_state(st)
            return dict(cur)

    def add_manual(self, item: Item, who: str) -> Item:
        with self.lock:
            name = f"{item.kind.value}.{item.lang}".replace("subtitle", "subs").replace("voiceover", "vo")
            name = name.replace("ad_translation", "ad")
            rows = read_jsonl(self.items_path(name))
            rows.append(item.model_dump(mode="json"))
            write_jsonl(self.items_path(name), rows)
            st = self.state()
            st["items"][item.id] = {
                "status": item.status.value,
                "final": item.final,
                "revision": 0,
                "draft_sha": _draft_sig(item),
                "reviewer": who,
                "reviewed_at": now_iso(),
                "reviewer_note": "manual line",
                "override_reason": None,
                "review_seconds": 0.0,
            }
            st["exports_stale"] = True
            self._save_state(st)
            with self.hist_p.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": now_iso(),
                            "who": who,
                            "item": item.id,
                            "before": None,
                            "after": {"manual": True, "text": item.text},
                            "reason": "manual line",
                        }
                    )
                    + "\n"
                )
            return item

    def auto_approve(self, item_ids: list[str], why: str) -> None:
        with self.lock:
            st = self.state()
            for iid in item_ids:
                cur = st["items"][iid]
                if cur["status"] == "pending":
                    cur["status"] = "auto_approved"
                    cur["revision"] = int(cur["revision"]) + 1
            self._save_state(st)
            with self.hist_p.open("a", encoding="utf-8") as fh:
                for iid in item_ids:
                    fh.write(
                        json.dumps(
                            {
                                "ts": now_iso(),
                                "who": "policy",
                                "item": iid,
                                "after": {"status": "auto_approved"},
                                "reason": why,
                            }
                        )
                        + "\n"
                    )

    def mark_exported(self, state_sha: str) -> None:
        with self.lock:
            if self.state_sha256() != state_sha:
                return  # edits during the render: stay stale (PolicyCut cleared it unconditionally)
            st = self.state()
            st["exports_stale"] = False
            self._save_state(st)


def _draft_sig(it: Item) -> str:
    """Identity of the machine proposal, including its check results: a re-run that changes the text, timing,
    status or violations resets the review for that item (a stricter new result is never hidden)."""
    rules = ",".join(sorted(v.rule for v in it.violations))
    return sha256_text(f"{it.draft}\x00{it.final}\x00{it.anchor_ms}\x00{it.slot.start_ms}-{it.slot.end_ms}"
                       f"\x00{it.status.value}\x00{rules}")
