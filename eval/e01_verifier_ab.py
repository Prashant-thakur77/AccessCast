"""E1 (headline): do the checks, then Gemma repair, raise the number of description lines that fit the pauses?

Arms (one change per step; PLAN §15.3):
  A  Gemma 4, same plan, no checks — attempt 0 published as written
  B  + checks — failing lines go to a person (counted, not rendered); no repair
  C  + Gemma repair — as B plus up to 3 repairs
All arms share analysis, evidence, plan, budgets, prompts, and the SAME attempt-0 draft per seed. Every arm's
published lines go through the same TTS and the same renderer (RN008 off for every arm), and are measured by
eval/measure_overlap.py, which imports no verifier code.

Usage: python -m eval.e01_verifier_ab --split test|dev [--videos id,id] [--seeds 3] [--provider local]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

import numpy as np

from accesscast import constants as C
from accesscast.config import REPO_ROOT, load_settings
from accesscast.pipeline import (
    ANALYSIS,
    Run,
    open_run,
    stage_evidence,
    stage_ingest,
    verify_context,
)
from accesscast.project import read_jsonl
from accesscast.schemas import Item, ItemStatus
from accesscast.tts.engine import VOICES, load_calibration, synthesize
from accesscast.write.plan_ad import plan_description
from accesscast.write.write_ad import WriteOptions, verify_and_repair, write_drafts
from eval import measure_overlap as M
from eval.common import Experiment, run_experiment

ARMS = ("A", "B", "C")
W3C = REPO_ROOT / "data" / "w3c"


def video_list(split: str, only: list[str]) -> list[dict[str, Any]]:
    if split == "test":
        man = json.loads((REPO_ROOT / "eval" / "datasets" / "manifests" / "w3c_wai.json").read_text())
        vids = sorted({r["video_id"] for r in man["files"] if r["kind"] == "video"})
        out = [
            {
                "id": v,
                "video": W3C / v / f"{v}.mp4",
                "captions": W3C / v / f"{v}.en.vtt",
                "human_desc": W3C / v / f"{v}_desc.en.vtt",
            }
            for v in vids
        ]
    else:
        man = json.loads((REPO_ROOT / "eval" / "datasets" / "manifests" / "dev_clips.json").read_text())
        out = [
            {"id": r["clip"], "video": REPO_ROOT / r["file"], "captions": None, "human_desc": None}
            for r in man["clips"]
            if "sha256" in r
        ]
        out.append(
            {
                "id": "fixture20",
                "video": REPO_ROOT / "tests" / "fixtures" / "fixture20" / "source.mp4",
                "captions": None,
                "human_desc": None,
            }
        )
    return [v for v in out if not only or v["id"] in only]


def arm_outcome(items: list[Item], arm: str) -> list[Item]:
    """Lines an arm publishes. A: every non-empty attempt-0 draft. B/C: lines that passed every error rule."""
    std = [i for i in items if not i.extended]
    if arm == "A":
        return [i for i in std if i.draft.strip()]
    return [i for i in std if i.status == ItemStatus.PENDING and not i.violations]


def render_stem(
    run: Run, published: list[Item], out_dir: Path, name: str
) -> tuple[Path, list[tuple[str, int, int]]]:
    """Same renderer for every arm: TTS + standard mix; returns the separately written description stem."""
    from accesscast.media.mix import Clip, mix_standard

    out_dir.mkdir(parents=True, exist_ok=True)
    voiced = synthesize(published, run.project.p("tts"), run.project.events) if published else []
    clips = [
        Clip(i.id, run.project.p("tts", f"{i.tts.sha256}.wav"), i.anchor_ms + C.AD_PAD_BEFORE_MS)
        for i in voiced
        if i.tts
    ]
    stem = out_dir / f"{name}.stem.wav"
    mix_standard(
        run.project.p("media", "master48k.wav"), clips, out_dir / f"{name}.mix.wav", stem, out_dir / "tmp"
    )
    expected = [
        (i.id, i.anchor_ms + C.AD_PAD_BEFORE_MS, i.anchor_ms + C.AD_PAD_BEFORE_MS + i.tts.duration_ms)
        for i in voiced
        if i.tts
    ]
    return stem, expected


def bootstrap_diff(
    per_video: dict[str, dict[str, tuple[int, int]]], a: str, b: str, n: int = 10_000, seed: int = 20261018
) -> tuple[float, float, float]:
    """Pooled (fit_b − fit_a)/L with a 95% interval, resampling videos (clustered bootstrap)."""
    vids = sorted(per_video)
    rng = np.random.default_rng(seed)
    fa = np.array([per_video[v][a][0] for v in vids], float)
    fb = np.array([per_video[v][b][0] for v in vids], float)
    total = np.array([per_video[v][a][1] for v in vids], float)
    point = float((fb.sum() - fa.sum()) / max(total.sum(), 1))
    stats = []
    for _ in range(n):
        idx = rng.integers(0, len(vids), len(vids))
        stats.append((fb[idx].sum() - fa[idx].sum()) / max(total[idx].sum(), 1))
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return round(point, 4), round(float(lo), 4), round(float(hi), 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--videos", default="")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--provider", default="local")
    ap.add_argument("--experiment-name", default="e01_verifier_ab", help="E3 reuses E1 with another model")
    args = ap.parse_args()
    settings = load_settings()
    exp = Experiment(
        args.experiment_name,
        args.split,
        config={
            "model": settings.local_model,
            "arms": {
                "A": "Gemma 4, same plan, no checks",
                "B": "+ checks, failures go to a person",
                "C": "+ Gemma repair (≤3)",
            },
            "seeds": args.seeds,
            "provider": args.provider,
            "strict_provider": True,
            "worker_mode": settings.worker_mode,
            "overlap_tolerance_ms": M.TOL_MS,
            "coverage_window_ms": 3000,
            "measure": "eval/measure_overlap.py (imports no verifier code)",
        },
    )

    def body(e: Experiment) -> None:
        per_video_seed: dict[str, dict[str, dict[str, tuple[int, int]]]] = {}
        texts: list[
            dict[str, Any]
        ] = []  # line texts are W3C-derived on the test split: never committed (rule 8)
        label_rows: list[dict[str, str]] = []
        vids = video_list(args.split, [x for x in args.videos.split(",") if x])
        e.config["videos_run"] = [v["id"] for v in vids]
        for v in vids:
            proj = stage_ingest(settings, v["video"])
            base = open_run(settings, proj, provider=args.provider, strict=True)
            if not proj.p("analysis", "gaps.json").exists():
                for _n, fn in ANALYSIS:
                    fn(base)
            if not any(proj.p("evidence").glob("*/evidence.json")):
                stage_evidence(base)
            ctx = verify_context(proj, "en")
            cal = load_calibration(VOICES["en"])
            ctx.wps_voice = cal.wps_voice
            plans = [
                p
                for p in plan_description(list(ctx.gaps.values()), ctx.evidence, ctx.words, ctx.vad, cal)
                if not p.extended
            ]
            cues = M.read_vtt_spans(v["captions"]) if v["captions"] and v["captions"].exists() else []
            energy = M.energy_speech_spans(proj.p("media", "master48k.wav"))
            human = (
                [s.start_ms for s in M.read_vtt_spans(v["human_desc"])]
                if v["human_desc"] and v["human_desc"].exists()
                else []
            )
            for s in range(args.seeds):
                label = f"e01:{args.split}:s{s}"
                run = open_run(settings, proj, provider=args.provider, strict=True, run_label=label)
                opts = WriteOptions(run_label=label, project_seed=settings.project_seed)
                drafts = write_drafts(run.client, plans, ctx.evidence, ctx, opts)  # shared by all arms
                arms_items = {
                    "A": verify_and_repair(
                        run.client, plans, drafts, ctx, WriteOptions(**{**opts.__dict__, "checks": False})
                    ),
                    "B": verify_and_repair(
                        run.client, plans, drafts, ctx, WriteOptions(**{**opts.__dict__, "repair": False})
                    ),
                    "C": verify_and_repair(run.client, plans, drafts, ctx, opts),
                }
                L = len(plans)
                for arm in ARMS:
                    pub = arm_outcome(arms_items[arm], arm)
                    stem, expected = render_stem(run, pub, proj.p("eval", "e01", label), arm)
                    measured = M.stem_line_spans(stem, expected)
                    n_fit_cap = n_fit_energy = 0
                    for lid, span in measured.items():
                        ok_cap, worst_cap, _why = M.fits(span, cues) if cues else (None, None, "no captions")
                        ok_en, worst_en, _ = M.fits(span, energy)
                        n_fit_cap += int(bool(ok_cap))
                        n_fit_energy += int(ok_en)
                        it = next(i for i in pub if i.id == lid)
                        texts.append(
                            {
                                "video": v["id"],
                                "seed": s,
                                "arm": arm,
                                "item": lid,
                                "draft": it.draft,
                                "text": it.text,
                            }
                        )
                        e.results.append(
                            {
                                "video": v["id"],
                                "seed": s,
                                "arm": arm,
                                "item": lid,
                                "span_ms": [span.start_ms, span.end_ms],
                                "fits_captions": ok_cap,
                                "overlap_captions_ms": worst_cap,
                                "fits_energy": ok_en,
                                "overlap_energy_ms": worst_en,
                                "repairs": it.repair.attempts,
                                "stop_reason": it.repair.stop_reason,
                            }
                        )
                        label_rows.append(
                            {"video": v["id"], "seed": str(s), "arm": arm, "item": lid, "text": it.text}
                        )
                    hit, nh = M.coverage(list(measured.values()), human) if human else (0, 0)
                    sent = L - len(pub) if arm != "A" else 0
                    first_pass = sum(
                        1 for i in arms_items["B"] if i.status == ItemStatus.PENDING and not i.violations
                    )
                    rec = per_video_seed.setdefault(f"{v['id']}#s{s}", {})
                    rec[arm] = (n_fit_cap if cues else n_fit_energy, L)
                    e.summary.setdefault("per_video", []).append(
                        {
                            "video": v["id"],
                            "seed": s,
                            "arm": arm,
                            "lines_planned": L,
                            "lines_published": len(pub),
                            "lines_fit_captions": n_fit_cap if cues else None,
                            "lines_fit_energy": n_fit_energy,
                            "sent_to_person": sent,
                            "first_pass_ok": first_pass,
                            "coverage_hits": hit,
                            "coverage_of": nh,
                        }
                    )
        # pooled summary per arm
        pooled: dict[str, dict[str, int]] = {}
        for row in e.summary.get("per_video", []):
            p = pooled.setdefault(
                row["arm"],
                {
                    "lines_planned": 0,
                    "lines_published": 0,
                    "lines_fit": 0,
                    "lines_fit_energy": 0,
                    "sent_to_person": 0,
                    "coverage_hits": 0,
                    "coverage_of": 0,
                },
            )
            p["lines_planned"] += row["lines_planned"]
            p["lines_published"] += row["lines_published"]
            p["lines_fit"] += (
                row["lines_fit_captions"]
                if row["lines_fit_captions"] is not None
                else row["lines_fit_energy"]
            )
            p["lines_fit_energy"] += row["lines_fit_energy"]
            p["sent_to_person"] += row["sent_to_person"]
            p["coverage_hits"] += row["coverage_hits"]
            p["coverage_of"] += row["coverage_of"]
        e.summary["pooled"] = pooled
        e.summary["reference"] = (
            "W3C human caption cue times"
            if args.split == "test"
            else "energy detector (dev: no human captions)"
        )
        if pooled.get("A") and pooled.get("C"):
            by_video: dict[str, dict[str, tuple[int, int]]] = {}
            for key, arms in per_video_seed.items():
                vid = key.split("#")[0]
                agg = by_video.setdefault(vid, {a: (0, 0) for a in ARMS})
                for a in ARMS:
                    if a in arms:
                        agg[a] = (agg[a][0] + arms[a][0], agg[a][1] + arms[a][1])
            e.summary["c_minus_a_share"] = dict(
                zip(("point", "ci95_lo", "ci95_hi"), bootstrap_diff(by_video, "A", "C"), strict=True)
            )
            cov = {
                a: (pooled[a]["coverage_hits"] / pooled[a]["coverage_of"])
                if pooled[a]["coverage_of"]
                else None
                for a in ARMS
            }
            e.summary["coverage_share"] = cov
            e.summary["coverage_guard_ok"] = None if cov["A"] is None else (cov["C"] or 0) >= cov["A"] - 0.10
        # blind label sheet: lines shuffled across arms, arm hidden (key kept separately, not for the labeller)
        rng = random.Random(settings.project_seed)
        rng.shuffle(label_rows)
        out_dir = REPO_ROOT / "data" / "eval_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"e01_{args.split}_texts.json").write_text(json.dumps(texts, ensure_ascii=False, indent=0))
        e.summary["texts_file"] = f"data/eval_outputs/e01_{args.split}_texts.json (git-ignored)"
        lab_dir = REPO_ROOT / "data" / "labels"
        lab_dir.mkdir(parents=True, exist_ok=True)
        with (lab_dir / f"e01_{args.split}_blind_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                [
                    "row",
                    "video",
                    "text",
                    "invented_name(0/1)",
                    "unsupported_claim(0/1)",
                    "restated_dialogue(0/1)",
                ]
            )
            for k, r in enumerate(label_rows):
                w.writerow([k, r["video"], r["text"], "", "", ""])
        (lab_dir / f"e01_{args.split}_blind_key.json").write_text(json.dumps(label_rows, indent=0))
        e.checks["evaluated_all_arms"] = all(a in pooled for a in ARMS)
        e.checks["strict_provider"] = True
        _ = read_jsonl

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
