"""Fake model for ACCESSCAST_WORKER_MODE=fake: deterministic, canned outputs so the whole pipeline runs
without a GPU. Every artefact made this way is stamped `synthetic_test_data` and is never evidence of
model quality.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from accesscast.llm.promptlib import Prompt
from accesscast.verify import nlp


class FakeModel:
    def __init__(self, canned_dir: Path | None) -> None:
        self.canned: dict[str, Any] = {}
        if canned_dir is not None and (canned_dir / "evidence.json").exists():
            self.canned = json.loads((canned_dir / "evidence.json").read_text(encoding="utf-8"))

    # The client calls this with (prompt, request); the request payload is the JSON user message.
    def __call__(self, prompt: Prompt, req: Any) -> dict[str, Any]:
        handler = getattr(self, f"_{prompt.id}", None)
        if handler is None:
            raise NotImplementedError(f"no fake output for prompt {prompt.id}")
        out: dict[str, Any] = handler(req.payload)
        return out

    # ------------------------------------------------------------------ vision
    def _evidence(self, p: dict[str, Any]) -> dict[str, Any]:
        scenes = self.canned.get("scenes", [])
        idx = int(p.get("scene_index", 0))
        if idx < len(scenes):
            return dict(scenes[idx])
        return {
            "setting": "A scene.",
            "characters": [],
            "visible_facts": [
                {"fid": "F001", "frames": [0], "text": "A scene is shown.", "priority": 4, "important": False}
            ],
            "on_screen_text": [],
            "inferences": [],
            "uncertainties": ["fake mode"],
        }

    def _scene_judge(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"same_scene": False, "reason": "fake mode: split"}

    def _naive_caption(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"text": "A scene is shown."}

    # ------------------------------------------------------------------ writing
    def _write_ad(self, p: dict[str, Any]) -> dict[str, Any]:
        drafts = self.canned.get("first_drafts", {})
        items = []
        for g in p["gaps"]:
            text = drafts.get(str(g.get("gap_index", -1)))
            if text is None:
                text = g["facts"][0]["text"] if g["facts"] else "A scene is shown."
            items.append(
                {"gap_id": g["gap_id"], "text": text, "fact_ids": [f["fid"] for f in g["facts"][:2]]}
            )
        return {"items": items}

    def _repair_ad(self, p: dict[str, Any]) -> dict[str, Any]:
        st = p["current_state"]
        facts = sorted(st["allowed_facts"], key=lambda f: (f.get("priority", 4), f["fid"]))
        limit = int(st["words_max"])
        rules = {v["rule"] for v in p["violations"]}
        # Rewrite from facts: describe the person by appearance, then on-screen text if it fits.
        parts: list[str] = []
        fids: list[str] = []
        for f in sorted(facts, key=lambda f: f["fid"]):
            cand = " ".join([*parts, _short(f["text"])])
            if nlp.word_count(cand) <= limit:
                parts.append(_short(f["text"]))
                fids.append(f["fid"])
        text = (
            " ".join(parts) if parts else " ".join(facts[0]["text"].split()[:limit]) if facts else "A scene."
        )
        if "AD009" in rules or "AD010" in rules:
            text = text.replace("Sarah", "A person")
        return {"text": text, "fact_ids": fids or [f["fid"] for f in facts[:1]]}

    def _easy(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"items": [{"id": c["id"], "text": _easy_text(c["text"])} for c in p["cues"]]}

    def _repair_easy(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"items": [{"id": c["id"], "text": c["text"]} for c in p["current_state"]["cues"]]}

    def _tr(self, lang: str, text: str) -> str:
        return str(self.canned.get("translations", {}).get(lang, {}).get(text, text))

    def _translate_subs(self, p: dict[str, Any]) -> dict[str, Any]:
        lang = p["target_lang"]
        return {
            "items": [
                {"id": s["id"], "snippet": s["text"][:10], "translation": self._tr(lang, s["text"])}
                for s in p["segments"]
            ]
        }

    def _repair_subs(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"translation": self._tr(p["target_lang"], p["source"])}

    def _voiceover(self, p: dict[str, Any]) -> dict[str, Any]:
        lang = p["target_lang"]
        return {"items": [{"id": s["id"], "text": self._tr(lang, s["text"])} for s in p["segments"]]}

    def _ad_translate(self, p: dict[str, Any]) -> dict[str, Any]:
        lang = p["target_lang"]
        bt = self.canned.get("back_translations", {})
        out = []
        for line in p["lines"]:
            t = self._tr(lang, line["text"])
            out.append({"id": line["id"], "text": t, "back_translation": bt.get(t, line["text"])})
        return {"items": out}

    # ------------------------------------------------------------------ listening
    def _asr_crosscheck(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"text": p.get("reference_text_fake_only", "")}

    def _sounds(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"labels": ["silence"]}


def _short(fact: str) -> str:
    """Fake-model compression of a fact sentence (drops leading articles of long clauses)."""
    t = fact.rstrip(".")
    t = t.replace("The laptop screen shows ", "On screen: ")
    t = t.replace(" sits at a desk with a laptop", " sits at a laptop")
    t = t.replace("A person with short grey hair and a blue cardigan", "A person in a blue cardigan")
    return t + "."


def _easy_text(text: str) -> str:
    return text.replace("Welcome. ", "Welcome! ").replace("Then press", "Next, press")
