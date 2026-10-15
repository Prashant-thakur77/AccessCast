"""E6: does our description help someone follow the video? LLM PROXY, NOT BLIND VIEWERS. (PLAN §15.3)

The one change: the description source. A non-Gemma model on AMD Token Factory (so Gemma never grades Gemma)
answers multiple-choice questions about each W3C video from a written record:
  a  dialogue only                                   (W3C's human captions)
  b  dialogue + AccessCast's description            (E1 arm C lines: checks + Gemma repair, no human review)
  c  dialogue + W3C's human description              (<id>_desc.en.vtt)
Both descriptions are given to the answerer with the same label ("Visual description"), so it cannot tell them
apart. The answerer may say "the record does not tell me" (-1); that counts as not correct and is reported.

The questions are written BY A PERSON from W3C's human description BEFORE any AccessCast output on W3C exists
(eval/questions/README.md). This script refuses to run if a question file's `written_at` is not earlier than the
first AccessCast output on that video: the first entry in evidence/test_runs.jsonl that may cover it, or the
creation time of its project folder, whichever is earlier.

Report: accuracy k/N per condition (and per video), cannot-tell counts, errors. Every label says
"LLM proxy, not blind viewers". Test split only (after the freeze); `--dry-run` checks the wiring in fake mode on
the fixture clip with built-in synthetic questions.

Usage: python -m eval.e06_questions --answerer-model <Token Factory model id> [--videos ids] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accesscast import constants as C
from accesscast.config import REPO_ROOT, Settings, load_settings
from accesscast.errors import ConfigError, LlmOutputError, ModelEndpointError
from accesscast.llm.client import LlmClient, LlmRequest
from accesscast.llm.fake import FakeModel
from accesscast.llm.promptlib import Prompt
from accesscast.seeds import derive_seed
from eval.common import EVIDENCE, TEST_RUNS, Experiment, run_experiment
from eval.e04_translation import EVAL_WORK, Cue, LogTail, dry_run_env, read_vtt_cues, write_outputs

QUESTIONS = REPO_ROOT / "eval" / "questions"
W3C_MANIFEST = REPO_ROOT / "eval" / "datasets" / "manifests" / "w3c_wai.json"
PROXY_LABEL = "LLM proxy, not blind viewers"
CONDITIONS = ("dialogue_only", "dialogue_plus_accesscast", "dialogue_plus_human")


# ------------------------------------------------------------------ question files
def parse_ts(s: str) -> datetime:
    """ISO 8601; a trailing Z is UTC; a time without a zone is refused (we cannot order it safely)."""
    t = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError(f"timestamp without a time zone: {s!r} (write e.g. 2026-10-17T09:30:00+05:30)")
    return t.astimezone(UTC)


def validate_questions(doc: Any, video_id: str) -> list[str]:
    """Problems with a question file (empty list = fine)."""
    if not isinstance(doc, dict):
        return ["the file must be one JSON object"]
    errs = []
    if doc.get("video_id") != video_id:
        errs.append(f"video_id is {doc.get('video_id')!r}, expected {video_id!r}")
    if not str(doc.get("written_by", "")).strip():
        errs.append("written_by is empty (name the person who wrote the questions)")
    try:
        parse_ts(str(doc.get("written_at", "")))
    except ValueError as e:
        errs.append(f"written_at: {e}")
    qs = doc.get("questions")
    if not isinstance(qs, list) or not qs:
        return [*errs, "questions must be a non-empty list"]
    for k, q in enumerate(qs):
        if not isinstance(q, dict) or not str(q.get("q", "")).strip():
            errs.append(f"question {k}: missing text in 'q'")
            continue
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) != 4 or not all(str(o).strip() for o in opts):
            errs.append(f"question {k}: needs exactly 4 non-empty options")
        elif len({str(o).strip().lower() for o in opts}) != 4:
            errs.append(f"question {k}: two options are the same")
        a = q.get("answer_index")
        if not isinstance(a, int) or isinstance(a, bool) or not 0 <= a <= 3:
            errs.append(f"question {k}: answer_index must be 0, 1, 2 or 3")
    return errs


def earliest_accesscast_output(
    video_id: str, test_runs: Sequence[dict[str, Any]], project_created_at: str | None
) -> datetime | None:
    """The earliest moment AccessCast output on this video may have existed. A test-run entry without a
    `videos` list is assumed to cover every video (conservative)."""
    times = [
        parse_ts(str(r["ts"]))
        for r in test_runs
        if r.get("ts") and (not r.get("videos") or video_id in r["videos"])
    ]
    if project_created_at:
        times.append(parse_ts(project_created_at))
    return min(times) if times else None


def questions_fresh(written_at: str, earliest_output: datetime | None) -> bool:
    """True only if the questions were written strictly before any AccessCast output on the video."""
    return earliest_output is None or parse_ts(written_at) < earliest_output


def read_test_runs(path: Path = TEST_RUNS) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def project_created_at(video_id: str) -> str | None:
    """created_at of projects/<sha12>/ for this W3C video, if the pipeline ever ingested it."""
    if not W3C_MANIFEST.exists():
        return None
    man = json.loads(W3C_MANIFEST.read_text())
    for r in man.get("files", []):
        if r.get("video_id") == video_id and r.get("kind") == "video" and r.get("sha256"):
            pj = REPO_ROOT / "projects" / r["sha256"][:12] / "project.json"
            if pj.exists():
                return str(json.loads(pj.read_text()).get("created_at") or "") or None
    return None


def load_question_file(
    video_id: str, *, test_runs: Sequence[dict[str, Any]], created_at: str | None, qdir: Path = QUESTIONS
) -> dict[str, Any]:
    p = qdir / f"{video_id}.json"
    if not p.exists():
        raise ConfigError(
            f"no question file eval/questions/{p.name}: a person writes it first (eval/questions/README.md)"
        )
    doc = json.loads(p.read_text(encoding="utf-8"))
    errs = validate_questions(doc, video_id)
    if errs:
        raise ConfigError(f"{p.name}: " + "; ".join(errs))
    first = earliest_accesscast_output(video_id, test_runs, created_at)
    if not questions_fresh(doc["written_at"], first):
        raise ConfigError(
            f"refusing E6: {p.name} was written at {doc['written_at']}, not before the first "
            f"AccessCast output on {video_id} ({first.isoformat() if first else '?'}). Questions "
            "must be written before any AccessCast output exists."
        )
    return dict(doc)


# ------------------------------------------------------------------ the non-Gemma answerer
def _fake_answers(prompt: Prompt, req: LlmRequest) -> dict[str, Any]:
    """Fake mode only: canned, labelled answers so the wiring runs without an endpoint."""
    if prompt.id == "e06_answer":
        return {"answer_index": 0, "quote": "fake mode"}
    if prompt.id == "e07_judge":
        return {"score": 3, "reason": "fake mode"}
    return FakeModel(None)(prompt, req)


class NonGemmaClient(LlmClient):
    """LlmClient pointed at one named, non-Gemma Token Factory model. client.py is unchanged: only the endpoint
    lookup is overridden here. Never falls back to another model or provider."""

    def __init__(self, settings: Settings, model: str, log_path: Path) -> None:
        if not model or "gemma" in model.lower():
            raise ConfigError(
                f"the answerer/judge must not be a Gemma model (got {model!r}): Gemma never grades Gemma"
            )
        super().__init__(
            settings,
            provider="tokenfactory",
            strict_provider=True,
            log_path=log_path,
            fake_handler=_fake_answers,
        )
        self.model = model

    def _endpoint(self, provider: str) -> tuple[str, str, dict[str, str]]:
        if provider != "tokenfactory":
            raise ModelEndpointError(f"answerer client only talks to tokenfactory, not {provider!r}")
        base, _gemma, headers = super()._endpoint(provider)
        return base, self.model, headers

    def check_listed(self) -> None:
        if self.settings.worker_mode == "fake":
            return
        listed = self.list_models("tokenfactory")
        if self.model not in listed:
            raise ModelEndpointError(
                f"{self.model!r} is not listed by Token Factory GET /models ({len(listed)} "
                "models listed); pick one from evidence/tokenfactory_models.json"
            )


def answerer(settings: Settings, exp_name: str, model: str) -> tuple[NonGemmaClient, LogTail]:
    log = EVAL_WORK / exp_name / "answerer_calls.jsonl"
    c = NonGemmaClient(settings, model, log)
    c.check_listed()
    return c, LogTail(log)


def answerer_served_id(tail: LogTail) -> str | None:
    ids = tail.served()
    if len(ids) > 1:
        raise ModelEndpointError(f"answerer served by more than one model id: {ids}")
    if ids and "gemma" in ids[0].lower():
        raise ModelEndpointError(f"answerer was served by a Gemma model ({ids[0]})")
    return ids[0] if ids else None


# ------------------------------------------------------------------ records and descriptions
def _mmss(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


def record_lines(dialogue: Sequence[Cue], description: Sequence[tuple[int, str]] | None) -> list[str]:
    """One written record: speech and (optionally) visual description, merged in time order."""
    rows = [(c.start_ms, 0, f"[{_mmss(c.start_ms)}] Speech: {c.text}") for c in dialogue]
    rows += [
        (t, 1, f"[{_mmss(t)}] Visual description: {' '.join(x.split())}")
        for t, x in description or []
        if x.strip()
    ]
    return [r[2] for r in sorted(rows)]


def human_description(v: dict[str, Any]) -> list[tuple[int, str]]:
    p = Path(v["human_desc"]) if v.get("human_desc") else None
    if p is None or not p.exists():
        raise FileNotFoundError(
            f"{v['id']}: W3C human description track missing (eval/datasets/fetch_w3c_wai.py)"
        )
    return [(c.start_ms, c.text) for c in read_vtt_cues(p)]


def dialogue(v: dict[str, Any], settings: Settings, provider: str) -> list[Cue]:
    if v.get("captions") and Path(v["captions"]).exists():
        return read_vtt_cues(Path(v["captions"]))
    from eval.e05_easyread import dev_sdh  # dev / dry run: our own caption cues

    return [
        Cue(i.slot.start_ms, i.slot.end_ms, i.text.replace("\n", " "))
        for i in dev_sdh(settings, Path(v["video"]), provider)
    ]


def e1_lines(
    settings: Settings,
    v: dict[str, Any],
    split: str,
    provider: str,
    freeze_tag: str | None,
) -> dict[str, list[tuple[int, str]]]:
    """Description lines for arm A (Gemma alone) and arm C (AccessCast) on seed 0, as E1 makes them.
    Read from E1's evidence when it covers this video under the same freeze; otherwise generated the same way
    (same run label `e01:<split>:s0`, so the same seeds and prompts as E1)."""
    ev = EVIDENCE / ("_smoke" if settings.worker_mode == "fake" else "") / "e01_verifier_ab.json"
    if ev.exists():
        doc = json.loads(ev.read_text())
        rows = [r for r in doc.get("results", []) if r.get("video") == v["id"] and r.get("seed") == 0]
        if (
            doc.get("split") == split
            and doc.get("freeze_tag") == freeze_tag
            and rows
            and all("text" in r and "span_ms" in r for r in rows)
        ):
            got = {
                arm: sorted((int(r["span_ms"][0]), str(r["text"])) for r in rows if r["arm"] == arm)
                for arm in ("A", "C")
            }
            if got["A"] or got["C"]:
                return got
    return generate_e1_lines(settings, v, split, provider)


def generate_e1_lines(
    settings: Settings, v: dict[str, Any], split: str, provider: str
) -> dict[str, list[tuple[int, str]]]:
    from accesscast.pipeline import ANALYSIS, open_run, stage_evidence, stage_ingest, verify_context
    from accesscast.tts.engine import VOICES, load_calibration
    from accesscast.write.plan_ad import plan_description
    from accesscast.write.write_ad import WriteOptions, verify_and_repair, write_drafts
    from eval.e01_verifier_ab import arm_outcome

    proj = stage_ingest(settings, Path(v["video"]))
    base = open_run(settings, proj, provider=provider, strict=True)
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
    label = f"e01:{split}:s0"
    run = open_run(settings, proj, provider=provider, strict=True, run_label=label)
    opts = WriteOptions(run_label=label, project_seed=settings.project_seed)
    drafts = write_drafts(run.client, plans, ctx.evidence, ctx, opts)
    a = verify_and_repair(run.client, plans, drafts, ctx, WriteOptions(**{**opts.__dict__, "checks": False}))
    c = verify_and_repair(run.client, plans, drafts, ctx, opts)
    return {
        arm: [(i.anchor_ms + C.AD_PAD_BEFORE_MS, i.text) for i in arm_outcome(items, arm)]
        for arm, items in (("A", a), ("C", c))
    }


# ------------------------------------------------------------------ dry run fixtures (synthetic, labelled)
DRY_QUESTIONS: dict[str, Any] = {
    "video_id": "fixture20",
    "written_by": "synthetic (dry run, not a person)",
    "written_at": "2000-01-01T00:00:00Z",
    "questions": [
        {
            "q": "What is on the screen at the start?",
            "options": ["A laptop", "A car", "A dog", "A tree"],
            "answer_index": 0,
        },
        {
            "q": "What does the speaker warn about?",
            "options": ["Rain", "Unplugging", "Noise", "Cold"],
            "answer_index": 1,
        },
    ],
}
DRY_HUMAN = [(1000, "A laptop sits on a desk."), (9000, "A progress bar fills up.")]


# ------------------------------------------------------------------ scoring
def score(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"label": PROXY_LABEL}
    for cond in CONDITIONS:
        rs = [r for r in rows if r["condition"] == cond]
        out[cond] = {
            "correct": {"k": sum(1 for r in rs if r["correct"]), "n": len(rs)},
            "cannot_tell": sum(1 for r in rs if r["answer_index"] == -1),
            "errors": sum(1 for r in rs if r["error"]),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answerer-model", default="", help="Token Factory model id; must not be a Gemma model")
    ap.add_argument("--videos", default="")
    ap.add_argument("--provider", default="local", help="provider for generating AccessCast lines if needed")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry_run_env(args.dry_run)
    settings = load_settings()
    split = "dev" if args.dry_run else "test"
    model = args.answerer_model or ("fake-answerer" if args.dry_run else "")
    exp = Experiment(
        "e06_questions",
        split,
        config={
            "question": "Does our description help someone follow the video?",
            "label": PROXY_LABEL,
            "one_change": "description source",
            "conditions": {
                "dialogue_only": "W3C human captions only",
                "dialogue_plus_accesscast": "+ AccessCast description (E1 arm C, seed 0: checks + Gemma repair, no human review)",
                "dialogue_plus_human": "+ W3C human description",
            },
            "answerer_model_requested": model,
            "answerer_provider": "tokenfactory",
            "strict_provider": True,
            "cannot_tell": "the answerer may return -1; counted as not correct",
            "worker_mode": settings.worker_mode,
            "dry_run": args.dry_run,
        },
    )

    def body(e: Experiment) -> None:
        from eval.e01_verifier_ab import video_list

        if not model:
            raise ConfigError("--answerer-model is required (a non-Gemma model listed by Token Factory)")
        if args.dry_run:
            vids = [v for v in video_list("dev", ["fixture20"])]
            docs: dict[str, dict[str, Any]] = {"fixture20": DRY_QUESTIONS}
        else:
            vids = video_list("test", [x for x in args.videos.split(",") if x])
            runs = read_test_runs()
            # freshness is checked for EVERY video before anything is generated or asked
            docs = {
                v["id"]: load_question_file(v["id"], test_runs=runs, created_at=project_created_at(v["id"]))
                for v in vids
            }
        client, tail = answerer(settings, e.experiment, model)
        outputs: list[dict[str, Any]] = []
        for v in vids:
            dia = dialogue(v, settings, args.provider)
            ours = e1_lines(settings, v, split, args.provider, e.freeze_tag)["C"]
            human = DRY_HUMAN if args.dry_run else human_description(v)
            records = {
                "dialogue_only": record_lines(dia, None),
                "dialogue_plus_accesscast": record_lines(dia, ours),
                "dialogue_plus_human": record_lines(dia, human),
            }
            for qi, q in enumerate(docs[v["id"]]["questions"]):
                for cond in CONDITIONS:
                    ans, quote, err = ask(
                        client,
                        records[cond],
                        q,
                        derive_seed(settings.project_seed, f"e06:{v['id']}:{qi}:{cond}"),
                    )
                    e.results.append(
                        {
                            "video": v["id"],
                            "q_index": qi,
                            "condition": cond,
                            "answer_index": ans,
                            "correct": ans == q["answer_index"],
                            "error": err,
                        }
                    )
                    outputs.append({"video": v["id"], "q_index": qi, "condition": cond, "quote": quote})
            e.summary.setdefault("per_video", {})[v["id"]] = {
                **score([r for r in e.results if r["video"] == v["id"]]),
                "accesscast_lines": len(ours),
                "human_lines": len(human),
            }
        e.summary["all"] = score(e.results)
        e.summary["answerer_served_model_id"] = answerer_served_id(tail)
        e.summary["outputs"] = write_outputs(e.experiment, f"answers_{split}", outputs)
        e.summary["note"] = (
            f"{PROXY_LABEL}. Accuracy is k of N questions; no significance test on this sample."
        )
        e.checks["every_question_answered_without_error"] = all(not r["error"] for r in e.results)
        e.checks["strict_provider"] = True

    return run_experiment(exp, body)


def ask(
    client: LlmClient, record: list[str], q: dict[str, Any], seed: int
) -> tuple[int | None, str, str | None]:
    """(answer_index or None on error, quote, error). Malformed answers fail closed: never counted correct."""
    try:
        r = client.call(
            LlmRequest(
                "e06_answer",
                {
                    "record": record,
                    "question": q["q"],
                    "options": {str(i): o for i, o in enumerate(q["options"])},
                },
                seed=seed,
                label="e06_answer",
            )
        )
    except (LlmOutputError, ModelEndpointError) as ex:
        return None, "", f"{type(ex).__name__}: {str(ex)[:200]}"
    a = r.obj.get("answer_index")
    if isinstance(a, str) and a.strip().lstrip("-").isdigit():
        a = int(a)
    if not isinstance(a, int) or isinstance(a, bool) or a not in (-1, 0, 1, 2, 3):
        return None, "", f"bad answer_index {a!r}"
    return a, str(r.obj.get("quote", ""))[:300], None


if __name__ == "__main__":
    raise SystemExit(main())
