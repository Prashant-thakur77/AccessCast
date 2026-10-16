"""S15 package: report.json (audit), decisions.json, benchmark.json, cost.json, index.json (PLAN §8.4)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from accesscast import constants as C
from accesscast.events import now_iso
from accesscast.project import read_json, read_jsonl, write_json
from accesscast.review.store import ReviewStore
from accesscast.schemas import ItemKind

if TYPE_CHECKING:
    from accesscast.pipeline import Run


def _p(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    k = max(0, min(len(v) - 1, round(q * (len(v) - 1))))
    return round(v[k], 4)


def benchmark(run: Run) -> dict[str, Any]:
    proj = run.project
    events = proj.events.read()
    stages: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.get("event") == "done" and "wall_s" in e:
            s = stages.setdefault(e["stage"], {"wall_s": 0.0, "runs": 0})
            s["wall_s"] = round(s["wall_s"] + float(e["wall_s"]), 4)
            s["runs"] += 1
    calls = read_jsonl(proj.p("logs", "llm_calls.jsonl"))
    by_prompt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in calls:
        by_prompt[str(c.get("prompt_id", "?")).split("@")[0]].append(c)
    llm = {}
    for pid, cs in sorted(by_prompt.items()):
        lat = [float(c["latency_s"]) for c in cs]
        llm[pid] = {
            "requests": len(cs),
            "ok": sum(1 for c in cs if c.get("status") == "ok"),
            "tokens_in": sum(int(c.get("tokens_in", 0)) for c in cs),
            "tokens_out": sum(int(c.get("tokens_out", 0)) for c in cs),
            "latency_p50_s": _p(lat, 0.5),
            "latency_p95_s": _p(lat, 0.95),
            "providers": sorted({str(c.get("provider")) for c in cs}),
            "served_model_ids": sorted({str(c.get("served_model_id")) for c in cs}),
        }
    return {
        "schema_version": "accesscast/benchmark/v1",
        "generated_at": now_iso(),
        "worker_mode": run.settings.worker_mode,
        "stages": stages,
        "llm": llm,
        "note": "fake mode: timings are not GPU numbers" if run.settings.worker_mode == "fake" else "",
    }


def cost(run: Run, bench: dict[str, Any]) -> dict[str, Any]:
    """GPU cost from measured wall time at the hourly price (PLAN §16.3). Review time added separately."""
    minutes = run.info.duration_ms / 60_000
    wall = sum(float(s["wall_s"]) for s in bench["stages"].values())
    per_min = (wall / 3600 * run.settings.gpu_hourly_cost_usd) / minutes if minutes else None
    return {
        "schema_version": "accesscast/cost/v1",
        "video_minutes": round(minutes, 4),
        "pipeline_wall_s": round(wall, 3),
        "gpu_hourly_cost_usd": run.settings.gpu_hourly_cost_usd,
        "gpu_cost_per_finished_minute_usd": round(per_min, 6) if per_min is not None else None,
        "basis": "single-job wall time on this machine; the E14 batch measurement replaces this",
        "valid_for_publication": run.settings.worker_mode == "real",
        "review": "see review_seconds in report.json; never converted to dollars without a sourced rate",
    }


def decisions(run: Run) -> dict[str, Any]:
    proj = run.project
    store = ReviewStore(proj.root)
    st = store.state()["items"]
    out = []
    for it in sorted(store.merged().values(), key=lambda i: (i.kind.value, i.lang, i.anchor_ms)):
        ev_frames: list[str] = []
        facts: list[dict[str, Any]] = []
        if it.scene_id and proj.p("evidence", it.scene_id, "evidence.json").exists():
            ev = read_json(proj.p("evidence", it.scene_id, "evidence.json"))
            facts = [f for f in ev.get("visible_facts", []) if f["fid"] in it.fact_ids]
            idx = sorted({i for f in facts for i in f.get("frames", [])})
            ev_frames = [
                f"evidence/{it.scene_id}/{ev['frames'][i]}" for i in idx if i < len(ev.get("frames", []))
            ]
        s = st.get(it.id, {})
        out.append(
            {
                "id": it.id,
                "kind": it.kind.value,
                "lang": it.lang,
                "audiences": it.audiences,
                "anchor_ms": it.anchor_ms,
                "slot": it.slot.model_dump(),
                "extended": it.extended,
                "budget": it.budget.model_dump() if it.budget else None,
                "facts": facts,
                "frames": ev_frames,
                "first_draft": it.draft,
                "final_text": it.text,
                "status": it.status.value,
                "rules_fired": sorted({r for h in it.repair.history for r in h.rules}),
                "repairs": [h.model_dump() for h in it.repair.history],
                "stop_reason": it.repair.stop_reason,
                "violations": [v.model_dump() for v in it.violations],
                "warnings": [w.model_dump() for w in it.warnings],
                "confidence": it.confidence,
                "confidence_terms": it.confidence_terms,
                "reviewer": s.get("reviewer"),
                "reviewed_at": s.get("reviewed_at"),
                "changed_by_person": s.get("reviewer") is not None
                and (s.get("final") or it.text)
                != (it.repair.history[-1].text if it.repair.history else it.draft),
                "back_translation": it.back_translation,
                "model": it.model.model_dump() if it.model else None,
                "tts": it.tts.model_dump() if it.tts else None,
                "source_text": it.source_text,
            }
        )
    return {"schema_version": "accesscast/decisions/v1", "generated_at": now_iso(), "items": out}


def build_reports(run: Run) -> dict[str, Any]:
    proj = run.project
    info = run.info
    store = ReviewStore(proj.root)
    items = store.merged()
    st = store.state()["items"]
    render = read_json(proj.p("reports", "render.json")) if proj.p("reports", "render.json").exists() else {}
    bench = benchmark(run)
    counts: dict[str, int] = defaultdict(int)
    approvals = {"person": 0, "auto": 0}
    for it in items.values():
        counts[it.status.value] += 1
        if it.status.value == "approved":
            approvals["person"] += 1
        elif it.status.value == "auto_approved":
            approvals["auto"] += 1
    review_s = [float(v.get("review_seconds") or 0) for v in st.values()]
    overrides = sum(1 for v in st.values() if v.get("override_reason"))
    reviewers = sorted(
        {str(v["reviewer"]) for v in st.values() if v.get("reviewer") and v["reviewer"] != "policy"}
    )
    checks = []
    for it in items.values():
        for f in [*it.violations, *it.warnings]:
            checks.append(
                {
                    "item": it.id,
                    "rule": f.rule,
                    "observed": f.observed,
                    "threshold": f.threshold,
                    "passed": False,
                    "severity": f.severity,
                }
            )
    report = {
        "schema_version": C.SCHEMA_REPORT,
        "generated_at": now_iso(),
        "input": {"sha256": info.sha256, "duration_ms": info.duration_ms, "source_name": info.source_name},
        "synthetic_test_data": info.settings.get("synthetic_test_data", False),
        "outputs": [
            {"version": k, "sha256": v.get("sha256"), "duration_ms": v.get("duration_ms"), "ok": v.get("ok")}
            for k, v in render.get("versions", {}).items()
        ],
        "models": [
            {"name": "google/gemma-4-31B-it", "licence": "Apache-2.0"},
            {"name": "google/gemma-4-E4B-it", "licence": "Apache-2.0"},
            {"name": "hexgrad/Kokoro-82M", "licence": "Apache-2.0"},
        ],
        "environment": {"worker_mode": run.settings.worker_mode},
        "stage_metrics": {k: {"wall_s": v["wall_s"], "fallbacks": []} for k, v in bench["stages"].items()},
        "checks": checks,
        "counts": {"items_by_status": dict(counts), "approvals": approvals},
        "review": {
            "state_sha256": store.state_sha256(),
            "human_reviewed": bool(render.get("human_reviewed")),
            "reviewers": reviewers,
            "review_seconds": round(sum(review_s), 1),
            "overrides": overrides,
        },
        "warnings": ["fake worker mode: canned model outputs"] if run.settings.worker_mode == "fake" else [],
    }
    write_json(proj.p("reports", "report.json"), report)
    write_json(proj.p("reports", "decisions.json"), decisions(run))
    write_json(proj.p("reports", "benchmark.json"), bench)
    write_json(proj.p("reports", "cost.json"), cost(run, bench))
    from accesscast.render_stage import AUDIENCE_VERSIONS, TRACK_LABELS

    index = {
        "schema_version": "accesscast/index/v1",
        "sha12": info.sha12,
        "title": info.source_name,
        "duration_ms": info.duration_ms,
        "human_reviewed": report["review"]["human_reviewed"],
        "synthetic_test_data": report["synthetic_test_data"],
        "reviewed_at": max(
            (str(v.get("reviewed_at")) for v in st.values() if v.get("reviewed_at")), default=None
        ),
        "versions": {
            k: {
                "label": AUDIENCE_VERSIONS[k]["label"],
                "file": v.get("file"),
                "extended": v.get("extended"),
                "tracks": [
                    {
                        "name": t,
                        "kind": TRACK_LABELS[t][0],
                        "srclang": TRACK_LABELS[t][1],
                        "label": TRACK_LABELS[t][2],
                        "file": f"render/tracks/{t}.{k}.vtt"
                        if v.get("extended")
                        else f"render/tracks/{t}.vtt",
                    }
                    for t in v.get("tracks", [])
                ],
                "source_to_output": f"render/source_to_output.{k}.jsonl" if v.get("extended") else None,
            }
            for k, v in render.get("versions", {}).items()
            if v.get("ok")
        },
        "needs_pause_cues": [i.id for i in items.values() if i.kind == ItemKind.EASY and i.needs_pause],
        "tts_engines": sorted({i.tts.engine for i in items.values() if i.tts is not None}),
    }
    write_json(proj.p("reports", "index.json"), index)
    return report


_ = statistics
