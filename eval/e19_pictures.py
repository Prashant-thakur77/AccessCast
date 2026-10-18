"""E19: describing still pictures on AMD Token Factory (eval/PREREGISTRATION.md), dev split.

One frame per scene of the three dev videos on the site goes through the same path as the live "Describe a picture"
API: Gemma 4 31B lists what is visible, the planner gives one line for an 8-second silent pause, Gemma writes it,
and the description rules check it, with the pipeline's full repair budget. Reports how often the first line broke
a rule (and which), how often repair fixed it, how often a line was left for a person, and seconds per picture.

Usage: python -m eval.e19_pictures [--provider tokenfactory] [--concurrency 3]
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from accesscast import constants as C
from accesscast.config import REPO_ROOT, load_settings
from accesscast.llm.client import LlmClient
from accesscast.project import read_json
from accesscast.proof.api import CASES, picture_context
from accesscast.schemas import ItemStatus, Scene
from accesscast.write.evidence import evidence_from_frames
from accesscast.write.plan_ad import Calibration, plan_description
from accesscast.write.write_ad import WriteOptions, verify_and_repair, write_drafts
from eval.common import Experiment, run_experiment

DEV = (
    "cbf141ec3213",
    "dac08bcd9d7a",
    "8af59806d6b6",
)  # Sintel trailer, NASA talk, NASA eclipse animation (dev)


def _outage(warnings: list[str]) -> bool:
    """The provider, not the model, failed: a timeout, retries used up, or our circuit breaker held the call."""
    text = " ".join(warnings).lower()
    return any(k in text for k in ("marked down", "failed after retries", "timed out", "http 5"))


def pictures() -> list[Path]:
    """One frame per scene: the middle evidence frame the pipeline extracted (dev projects only)."""
    out = []
    for pid in DEV:
        for scene in sorted((REPO_ROOT / "projects" / "_site" / pid / "evidence").glob("SC*")):
            frames = sorted(scene.glob("f*.jpg"))
            if frames:
                out.append(frames[len(frames) // 2])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="tokenfactory")
    ap.add_argument("--concurrency", type=int, default=3)
    args = ap.parse_args()
    settings = load_settings()
    pics = pictures()
    log = REPO_ROOT / "projects" / "_eval" / "e19_pictures" / "llm_calls.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    exp = Experiment(
        "e19_pictures",
        "dev",
        config={
            "question": "How often does Gemma's first description of a still picture break a rule, and does repair fix it?",
            "pictures": [str(p.relative_to(REPO_ROOT)) for p in pics],
            "provider": args.provider,
            "strict_provider": True,
            "pause_ms": C.DESCRIBE_PAUSE_MS,
            "max_repairs": C.REPAIR_MAX_ATTEMPTS,
            "path": "proof.api.picture_context + write.evidence.evidence_from_frames + plan_description + "
            "write_drafts + verify_and_repair (the live API's code, without its time limit)",
        },
    )
    cal = Calibration(**read_json(CASES / "A1_no_pause" / "case.json")["calibration"])

    def one(i_path: tuple[int, Path]) -> dict[str, Any]:
        i, path = i_path
        client = LlmClient(
            settings, provider=args.provider, strict_provider=True, timeout_s=90, max_retries=2, log_path=log
        )
        t0 = time.monotonic()
        scene = Scene(scene_id="SC001", start_ms=0, end_ms=C.DESCRIBE_PAUSE_MS, shots=["SH001"])
        redone = 0
        while True:  # as in E11: a picture hit by a provider outage is redone, never scored as a model result
            ev = evidence_from_frames(client, scene, 0, [path], [C.DESCRIBE_PAUSE_MS // 2])
            if ev.status == "ok" or not _outage(ev.warnings) or redone >= 2:
                break
            redone += 1
            time.sleep(30)
            client = LlmClient(
                settings,
                provider=args.provider,
                strict_provider=True,
                timeout_s=90,
                max_retries=2,
                log_path=log,
            )
        row: dict[str, Any] = {
            "picture": str(path.relative_to(REPO_ROOT)),
            "evidence_ok": ev.status == "ok",
            "redone_after_outage": redone,
        }
        row["facts"] = [f.text for f in ev.visible_facts] if ev.status == "ok" else []
        if ev.status == "ok" and row["facts"]:
            ctx, gap = picture_context(ev)
            ctx.wps_voice = cal.wps_voice
            plans = plan_description([gap], ctx.evidence, [], [], cal)[:1]
            opts = WriteOptions(run_label=f"e19:{i}", project_seed=settings.project_seed)
            items = verify_and_repair(
                client, plans, write_drafts(client, plans, ctx.evidence, ctx, opts), ctx, opts
            )
            for item in items:
                first = item.repair.history[0] if item.repair.history else None
                published = item.status == ItemStatus.PENDING and not item.violations
                row.update(
                    first_line=first.text if first else item.draft,
                    first_rules=list(first.rules) if first else [],
                    published=item.text if published else None,
                    repairs=item.repair.attempts,
                    still_failing=[f.rule for f in item.violations],
                )
        else:
            row["evidence_problem"] = (ev.warnings or ["no answer"])[0][:200]
        row["seconds"] = round(time.monotonic() - t0, 1)
        return row

    def body(e: Experiment) -> None:
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
            rows = list(ex.map(one, enumerate(pics)))
        e.results = rows
        lined = [r for r in rows if "first_line" in r]
        first_failed = [r for r in lined if r["first_rules"]]
        rules = Counter(rule for r in first_failed for rule in r["first_rules"])
        e.summary = {
            "pictures": len(rows),
            "evidence_ok": sum(1 for r in rows if r["evidence_ok"]),
            "lines": len(lined),
            "first_line_broke_a_rule": len(first_failed),
            "first_line_passed": len(lined) - len(first_failed),
            "rules_on_first_lines": dict(rules.most_common()),
            "published_after_repair": sum(1 for r in first_failed if r.get("published")),
            "published_total": sum(1 for r in lined if r.get("published")),
            "left_for_a_person": sum(1 for r in lined if not r.get("published")),
            "seconds_median": round(statistics.median(r["seconds"] for r in rows), 1) if rows else None,
            "seconds_max": max((r["seconds"] for r in rows), default=None),
            "redone_after_outage": sum(r["redone_after_outage"] for r in rows),
        }
        e.checks["every_picture_has_a_row"] = len(rows) == len(pics) and len(pics) > 0
        e.checks["no_endpoint_errors"] = not any(_outage([str(r.get("evidence_problem", ""))]) for r in rows)

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
