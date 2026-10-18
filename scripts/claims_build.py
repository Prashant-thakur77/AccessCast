"""Register claims from evidence files, then fill `<pending: id>` placeholders in public files from the registry.

Never type a number by hand: every value is read from an evidence file at a JSON pointer (or comes from a verified
`cited` fact in evidence/cited_claims.json), hashed, and written to evidence/public-claims.json. Placeholders whose
evidence does not exist yet are left in place, so submission-check keeps failing until the experiment runs.

Usage: python scripts/claims_build.py [--fill]
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accesscast.claims import PUBLIC_FILES, resolve_pointer
from accesscast.config import REPO_ROOT
from accesscast.project import sha256_file

EV = REPO_ROOT / "evidence"


@dataclass
class Spec:
    claim_id: str
    path: str
    pointer: str
    text: str  # plain-words sentence; {v} is the display value
    unit: str = ""
    fmt: Callable[[Any], str] = str
    split: str = "dev"


def pct(x: Any) -> str:
    return f"{float(x) * 100:.0f}%"


def money(x: Any) -> str:
    return f"${float(x):.4f}" if float(x) < 0.1 else f"${float(x):.2f}"


def secs(x: Any) -> str:
    return f"{float(x):.1f} s"


SPECS: list[Spec] = [
    # E1 (test split, headline)
    Spec(
        "e1.lines_planned",
        "e01_verifier_ab.json",
        "/summary/pooled/A/lines_planned",
        "description lines planned",
        "lines",
        split="test",
    ),
    Spec(
        "e1.fit_a",
        "e01_verifier_ab.json",
        "/summary/pooled/A/lines_fit",
        "lines that fit, Gemma 4 alone (arm A)",
        "lines",
        split="test",
    ),
    Spec(
        "e1.fit_b",
        "e01_verifier_ab.json",
        "/summary/pooled/B/lines_fit",
        "lines that fit, + checks (arm B)",
        "lines",
        split="test",
    ),
    Spec(
        "e1.fit_c",
        "e01_verifier_ab.json",
        "/summary/pooled/C/lines_fit",
        "lines that fit, + checks and Gemma repair (arm C)",
        "lines",
        split="test",
    ),
    Spec(
        "e1.sent_c",
        "e01_verifier_ab.json",
        "/summary/pooled/C/sent_to_person",
        "lines sent to a person in arm C",
        "lines",
        split="test",
    ),
    Spec(
        "e1.ci_lo",
        "e01_verifier_ab.json",
        "/summary/c_minus_a_share/ci95_lo",
        "lower end of the 95% interval for (C−A)/L",
        fmt=pct,
        split="test",
    ),
    Spec(
        "e1.ci_hi",
        "e01_verifier_ab.json",
        "/summary/c_minus_a_share/ci95_hi",
        "upper end of the 95% interval for (C−A)/L",
        fmt=pct,
        split="test",
    ),
    # E11
    Spec(
        "e11.total_leaks",
        "e11_adversarial.json",
        "/summary/total_leaks",
        "attack outputs that reached the viewer",
        "lines",
    ),
    # E13 / E14 / E8 / E9 / E10 / E15 / E16
    Spec(
        "e5.neg_gemma_k",
        "e05_easyread.json",
        "/summary/arms/gemma_alone_on_the_same_cues/negations_kept/k",
        "easy-read cues where Gemma alone kept every negation (test)",
        "cues",
        split="test",
    ),
    Spec(
        "e5.neg_gemma_n",
        "e05_easyread.json",
        "/summary/arms/gemma_alone_on_the_same_cues/negations_kept/n",
        "easy-read cues compared (test)",
        "cues",
        split="test",
    ),
    Spec(
        "e5.neg_ours_k",
        "e05_easyread.json",
        "/summary/arms/accesscast_published/negations_kept/k",
        "published AccessCast easy-read cues that kept every negation (test)",
        "cues",
        split="test",
    ),
    Spec(
        "e5.neg_ours_n",
        "e05_easyread.json",
        "/summary/arms/accesscast_published/negations_kept/n",
        "published AccessCast easy-read cues (test)",
        "cues",
        split="test",
    ),
    Spec(
        "e5.sent",
        "e05_easyread.json",
        "/summary/accesscast_routing/sent_to_person",
        "easy-read cues sent to a person (test)",
        "cues",
        split="test",
    ),
    Spec(
        "e5.of",
        "e05_easyread.json",
        "/summary/accesscast_routing/of",
        "easy-read cues in the test videos",
        "cues",
        split="test",
    ),
    Spec(
        "e5.wpm_source_k",
        "e05_easyread.json",
        "/summary/arms/source/at_or_under_130_wpm/k",
        "original caption cues at or under 130 words per minute (test)",
        "cues",
        split="test",
    ),
    Spec(
        "e5.wpm_ours_k",
        "e05_easyread.json",
        "/summary/arms/accesscast_published/at_or_under_130_wpm/k",
        "published easy-read cues at or under 130 words per minute (test)",
        "cues",
        split="test",
    ),
    Spec("e09.runs", "e09_determinism.json", "/config/runs", "fresh runs per clip in E9", "runs"),
    Spec(
        "e09.words_same",
        "e09_determinism.json",
        "/summary/clips/nasa_GSFC_20170614_Eclipse_m12534_Plane/identical_to_run1/words",
        "runs whose word timings were byte-identical to run 1 (NASA dev clip)",
    ),
    Spec(
        "e09.plane_diff",
        "e09_determinism.json",
        "/summary/clips/nasa_GSFC_20170614_Eclipse_m12534_Plane/differing_description_lines_per_run/0",
        "description lines that differed from run 1 in run 2 (NASA dev clip)",
        "lines",
    ),
    Spec(
        "e09.plane_lines",
        "e09_determinism.json",
        "/summary/clips/nasa_GSFC_20170614_Eclipse_m12534_Plane/description_lines",
        "description lines (NASA dev clip)",
        "lines",
    ),
    Spec(
        "e09.sintel_diff",
        "e09_determinism.json",
        "/summary/clips/blender_sintel_trailer/differing_description_lines_per_run/0",
        "description lines that differed from run 1 in run 2 (Sintel dev clip)",
        "lines",
    ),
    Spec(
        "e09.sintel_lines",
        "e09_determinism.json",
        "/summary/clips/blender_sintel_trailer/description_lines",
        "description lines (Sintel dev clip)",
        "lines",
    ),
    Spec(
        "e7.paired_k",
        "e07_similarity.json",
        "/summary/timing_agreement/accesscast/k",
        "W3C human description cues paired with an AccessCast line (test)",
        "cues",
        split="test",
    ),
    Spec(
        "e7.paired_n",
        "e07_similarity.json",
        "/summary/timing_agreement/accesscast/n",
        "W3C human description cues (test)",
        "cues",
        split="test",
    ),
    Spec(
        "cost.usd_per_min",
        "cost_estimate.json",
        "/summary/usd_per_finished_minute_gemma",
        "estimated Gemma cost per finished minute, all five versions, at a published list price",
        "USD",
        fmt=lambda x: f"${float(x):.4f}",
    ),
    Spec(
        "cost.usd_per_hour",
        "cost_estimate.json",
        "/summary/usd_per_hour_of_video_gemma",
        "estimated Gemma cost per hour of video, all five versions, at a published list price",
        "USD",
        fmt=lambda x: f"${float(x):.2f}",
    ),
    Spec(
        "e1.census_pauses",
        "e01_test_gap_census.json",
        "/summary/pauses",
        "pauses long enough for description in the 10 test videos",
        "pauses",
        split="test",
    ),
    Spec(
        "e1.census_pause_seconds",
        "e01_test_gap_census.json",
        "/summary/pause_seconds",
        "seconds of pause in the 10 test videos",
        "s",
        fmt=lambda x: f"{float(x):.1f}",
        split="test",
    ),
    Spec(
        "e1.census_minutes",
        "e01_test_gap_census.json",
        "/summary/video_minutes",
        "minutes of test video",
        "min",
        fmt=lambda x: f"{float(x):.1f}",
        split="test",
    ),
    Spec(
        "e1.census_no_pause",
        "e01_test_gap_census.json",
        "/summary/videos_with_no_pause",
        "test videos with no pause long enough for description",
        "videos",
        split="test",
    ),
    Spec(
        "e1.fit_energy_a",
        "e01_verifier_ab.json",
        "/summary/pooled/A/lines_fit_energy",
        "lines that fit by an energy speech detector, arm A",
        "lines",
        split="test",
    ),
    Spec(
        "e1.fit_energy_c",
        "e01_verifier_ab.json",
        "/summary/pooled/C/lines_fit_energy",
        "lines that fit by an energy speech detector, arm C",
        "lines",
        split="test",
    ),
    Spec(
        "e14.tokens_per_minute",
        "e14_cost.json",
        "/summary/tokens_per_finished_minute",
        "Gemma tokens per finished minute of video, all five versions (dev set)",
        "tokens",
        fmt=lambda x: f"{float(x):,.0f}",
    ),
    Spec(
        "e13.failed",
        "e13_serving_tokenfactory.json",
        "/summary/failed",
        "Gemma requests to AMD Token Factory that failed during the speed test",
        "requests",
    ),
    Spec(
        "e13.requests",
        "e13_serving_tokenfactory.json",
        "/summary/requests",
        "Gemma requests sent to AMD Token Factory during the speed test",
        "requests",
    ),
    Spec(
        "e13.best_tokens_per_s",
        "e13_serving_tokenfactory.json",
        "/summary/best/tokens_per_s",
        "generated tokens per second seen by our client, Gemma 4 31B on AMD Token Factory, best concurrency",
        "tokens/s",
        fmt=lambda x: f"{float(x):,.0f}",
    ),
    Spec(
        "e13.best_p95_s",
        "e13_serving_tokenfactory.json",
        "/summary/best/p95_s",
        "client-side p95 latency of a Gemma request on AMD Token Factory at that concurrency",
        "s",
        fmt=secs,
    ),
    Spec(
        "e1.pub_a",
        "e01_verifier_ab.json",
        "/summary/pooled/A/lines_published",
        "lines published, arm A",
        "lines",
        split="test",
    ),
    Spec(
        "e1.pub_b",
        "e01_verifier_ab.json",
        "/summary/pooled/B/lines_published",
        "lines published, arm B",
        "lines",
        split="test",
    ),
    Spec(
        "e1.pub_c",
        "e01_verifier_ab.json",
        "/summary/pooled/C/lines_published",
        "lines published, arm C",
        "lines",
        split="test",
    ),
    Spec(
        "e1.sent_b",
        "e01_verifier_ab.json",
        "/summary/pooled/B/sent_to_person",
        "lines sent to a person in arm B",
        "lines",
        split="test",
    ),
    Spec(
        "e1.cov_a",
        "e01_verifier_ab.json",
        "/summary/coverage_share/A",
        "share of human description positions covered, arm A",
        fmt=pct,
        split="test",
    ),
    Spec(
        "e1.cov_c",
        "e01_verifier_ab.json",
        "/summary/coverage_share/C",
        "share of human description positions covered, arm C",
        fmt=pct,
        split="test",
    ),
    Spec(
        "e09.summary",
        "e09_determinism.json",
        "/summary/all_artefacts_identical",
        "whether every artefact was byte-identical across runs",
        fmt=lambda x: (
            "every artefact byte-identical across 5 fresh runs"
            if x
            else "not every artefact was byte-identical (details in the evidence file)"
        ),
    ),
    Spec(
        "e16.player_passed",
        "e16_ui_a11y.json",
        "/summary/player/passed",
        "player accessibility tests passed (Playwright + axe-core)",
        "tests",
        split="none",
    ),
    Spec(
        "e16.player_total",
        "e16_ui_a11y.json",
        "/summary/player/total",
        "player accessibility tests run",
        "tests",
        split="none",
    ),
    Spec(
        "e16.review_passed",
        "e16_ui_a11y.json",
        "/summary/review/passed",
        "review-app accessibility tests passed (Playwright + axe-core)",
        "tests",
        split="none",
    ),
    Spec(
        "e16.review_total",
        "e16_ui_a11y.json",
        "/summary/review/total",
        "review-app accessibility tests run",
        "tests",
        split="none",
    ),
    Spec(
        "e15.wer_en_turbo",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/en/wer",
        "English word error rate, Whisper large-v3-turbo, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.wer_en_large",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3/en/wer",
        "English word error rate, Whisper large-v3, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.wer_hi_turbo",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/hi/wer",
        "Hindi word error rate, Whisper large-v3-turbo, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.wer_it_turbo",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/it/wer",
        "Italian word error rate, Whisper large-v3-turbo, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.n_per_lang",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/en/n",
        "FLEURS clips per language",
        "clips",
    ),
    Spec(
        "e15.boundary_aligned_median",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/aligned/median_ms",
        "median word-boundary error after forced alignment (synthetic dev clips)",
        "ms",
        fmt=lambda x: f"{float(x):.0f} ms",
    ),
    Spec(
        "e15.boundary_aligned_p95",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/aligned/p95_ms",
        "95th-percentile word-boundary error after forced alignment",
        "ms",
        fmt=lambda x: f"{float(x):.0f} ms",
    ),
    Spec(
        "e15.boundary_raw_median",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/raw/median_ms",
        "median word-boundary error of raw Whisper timestamps",
        "ms",
        fmt=lambda x: f"{float(x):.0f} ms",
    ),
    Spec(
        "e15.boundary_raw_p95",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/raw/p95_ms",
        "95th-percentile word-boundary error of raw Whisper timestamps",
        "ms",
        fmt=lambda x: f"{float(x):.0f} ms",
    ),
    Spec(
        "e15.boundary_n",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/aligned/n",
        "word boundaries measured",
        "words",
    ),
    Spec(
        "e15.guard_ms",
        "e15_asr.json",
        "/summary/decision/guard_ms",
        "guard band around speech, from the measured p95 word-boundary error",
        "ms",
    ),
]


def amd_specs() -> list[Spec]:
    """How much model work ran on AMD Token Factory, counted from our own call logs (scripts/amd_usage.py)."""
    f, n = "amd_usage.json", "none"
    thousands: Callable[[Any], str] = lambda x: f"{int(x):,}"  # noqa: E731
    return [
        Spec(
            "amd.requests",
            f,
            "/summary/requests_answered",
            "Gemma 4 31B requests answered by AMD Token Factory",
            "requests",
            thousands,
            n,
        ),
        Spec(
            "amd.tokens",
            f,
            "/summary/tokens_total",
            "tokens in those requests, as the server reported them",
            "tokens",
            thousands,
            n,
        ),
        Spec(
            "amd.tokens_millions",
            f,
            "/summary/tokens_total",
            "tokens in those requests, in millions",
            "tokens",
            lambda x: f"{int(x) / 1e6:.1f} million",
            n,
        ),
        Spec("amd.videos", f, "/summary/videos", "videos those requests worked on", "videos", str, n),
        Spec(
            "amd.video_minutes",
            f,
            "/summary/video_minutes",
            "minutes of video those requests worked on",
            "minutes",
            lambda x: f"{float(x):.1f}",
            n,
        ),
        Spec(
            "amd.videos_w3c",
            f,
            "/summary/video_groups/w3c_test",
            "of which W3C test videos",
            "videos",
            str,
            n,
        ),
        Spec("amd.videos_dev", f, "/summary/video_groups/dev_clips", "of which dev clips", "videos", str, n),
        Spec(
            "amd.videos_attack",
            f,
            "/summary/video_groups/attack_clips",
            "of which attack clips",
            "videos",
            str,
            n,
        ),
        Spec(
            "amd.requests_all",
            f,
            "/summary/requests_answered_all_models",
            "requests AMD Token Factory answered for us, Gemma and the models E17 compared",
            "requests",
            thousands,
            n,
        ),
        Spec(
            "amd.tokens_all_millions",
            f,
            "/summary/tokens_total_all_models",
            "tokens in all those requests, in millions",
            "tokens",
            lambda x: f"{int(x) / 1e6:.1f} million",
            n,
        ),
        Spec(
            "amd.no_answer",
            f,
            "/summary/no_answer_after_retries",
            "calls Token Factory never answered, after every retry",
            "calls",
            thousands,
            n,
        ),
        Spec(
            "amd.not_sent",
            f,
            "/summary/not_sent_circuit_open",
            "calls our circuit breaker held back without sending, after a call had failed every retry",
            "calls",
            thousands,
            n,
        ),
    ]


def e19_specs() -> list[Spec]:
    """E19 (dev): still pictures described on AMD Token Factory through the live API's code path."""
    f = "e19_pictures.json"
    rows = [
        ("e19.pictures", "/summary/pictures", "dev pictures described (one per scene)", "pictures"),
        ("e19.lines", "/summary/lines", "pictures that got a description line", "lines"),
        (
            "e19.first_broke",
            "/summary/first_line_broke_a_rule",
            "first lines that broke at least one rule",
            "lines",
        ),
        ("e19.first_passed", "/summary/first_line_passed", "first lines that passed every rule", "lines"),
        ("e19.after_repair", "/summary/published_after_repair", "lines that passed after repair", "lines"),
        ("e19.published", "/summary/published_total", "lines that passed every rule in the end", "lines"),
        ("e19.to_person", "/summary/left_for_a_person", "lines left for a person", "lines"),
    ]
    out = [Spec(cid, f, ptr, text, unit) for cid, ptr, text, unit in rows]
    out.append(
        Spec(
            "e19.seconds",
            f,
            "/summary/seconds_median",
            "median seconds per picture",
            "s",
            lambda x: f"{float(x):.0f} s",
        )
    )
    return out


def repo_specs() -> list[Spec]:
    """Counts about the project itself, read from the code and the repo (scripts/repo_stats.py)."""
    f, n = "repo_stats.json", "none"
    thousands: Callable[[Any], str] = lambda x: f"{int(x):,}"  # noqa: E731
    rows = [
        ("repo.rules_total", "/summary/rules_total", "check rules in docs/rules.md", "rules"),
        ("repo.rules_ad", "/summary/rules_by_family/AD", "description rules", "rules"),
        ("repo.rules_er", "/summary/rules_by_family/ER", "easy-read rules", "rules"),
        ("repo.rules_cc", "/summary/rules_by_family/CC", "caption and subtitle rules", "rules"),
        ("repo.rules_vo", "/summary/rules_by_family/VO", "voice-over rules", "rules"),
        ("repo.rules_rn", "/summary/rules_by_family/RN", "render rules", "rules"),
        ("repo.stages", "/summary/pipeline_stages", "pipeline stages", "stages"),
        ("repo.versions", "/summary/viewer_versions", "versions a project can render", "versions"),
        ("repo.languages", "/summary/languages_total", "languages, English included", "languages"),
        (
            "repo.translation_languages",
            "/summary/translation_languages",
            "languages we translate into",
            "languages",
        ),
        ("repo.prompts", "/summary/prompts", "prompt files", "prompts"),
        (
            "repo.experiments_planned",
            "/summary/experiments_planned",
            "experiments planned (E1–E19)",
            "experiments",
        ),
        (
            "repo.experiments_run",
            "/summary/experiments_run",
            "experiments with an evidence file",
            "experiments",
        ),
        ("repo.incidents", "/summary/incidents", "dated incidents in docs/incidents.md", "incidents"),
        ("repo.charts", "/summary/charts", "charts drawn from evidence", "charts"),
        ("repo.pages", "/summary/site_pages", "pages on the site", "pages"),
    ]
    out = [Spec(cid, f, ptr, text, unit, str, n) for cid, ptr, text, unit in rows]
    out.append(
        Spec(
            "repo.python_lines",
            f,
            "/summary/python_lines_src",
            "lines of Python in src/accesscast",
            "lines",
            thousands,
            n,
        )
    )
    return out


def tests_specs() -> list[Spec]:
    """Unit and golden tests and their line coverage, from one pytest run (scripts/test_stats.py)."""
    f, n = "tests.json", "none"
    return [
        Spec("tests.total", f, "/summary/tests_total", "unit and golden tests", "tests", str, n),
        Spec("tests.passed", f, "/summary/tests_passed", "unit and golden tests that pass", "tests", str, n),
        Spec("tests.files", f, "/summary/test_files", "test files", "files", str, n),
        Spec(
            "tests.coverage",
            f,
            "/summary/line_coverage_pct",
            "share of src/accesscast lines the tests run",
            "%",
            lambda x: f"{float(x):.0f}%",
            n,
        ),
    ]


def e18_specs() -> list[Spec]:
    """E18 (site drafts, dev): per language, translated lines that passed every check, and lines held for a person."""
    f = "e18_language_checks.json"
    out: list[Spec] = []
    for lang, name in (
        ("hi", "Hindi"),
        ("it", "Italian"),
        ("es", "Spanish"),
        ("fr", "French"),
        ("pt", "Portuguese"),
    ):
        L = f"/summary/by_language/{lang}"
        out += [
            Spec(f"e18.{lang}.lines", f, f"{L}/lines", f"{name} subtitle and voice-over lines made", "lines"),
            Spec(f"e18.{lang}.passed", f, f"{L}/passed", f"{name} lines that passed every check", "lines"),
            Spec(f"e18.{lang}.held", f, f"{L}/held_for_a_person", f"{name} lines held for a person", "lines"),
        ]
    return out


E17_MODELS = (
    ("gemma", "Gemma-4-31B-IT", "Gemma 4 31B"),
    ("qwen", "Qwen3.8-27B", "Qwen3.8-27B"),
    ("minicpm", "MiniCPM-V-4.7-35B-A3B", "MiniCPM-V-4.7-35B-A3B"),
)


def e17_specs() -> list[Spec]:
    """E17 (attack clips, dev): per model, lines written, lines that took the bait, answers that reached a viewer."""
    f = "e17_model_ladder.json"
    out: list[Spec] = []
    for slug, model, name in E17_MODELS:
        M = f"/summary/by_model/{model}"
        out += [
            Spec(f"e17.{slug}.tries", f, f"{M}/tries", f"attack lines {name} wrote", "lines"),
            Spec(
                f"e17.{slug}.bait",
                f,
                f"{M}/took_bait",
                f"of those, lines where {name} took the bait",
                "lines",
            ),
            Spec(
                f"e17.{slug}.reached",
                f,
                f"{M}/reached_viewer",
                f"{name} attack answers that reached a viewer",
            ),
            Spec(
                f"e17.{slug}.no_output",
                f,
                f"{M}/no_output",
                f"lines where {name}'s first draft was empty",
                "lines",
            ),
        ]
    return out


def signed(nd: int) -> Callable[[Any], str]:
    return lambda x: f"{float(x):+.{nd}f}".replace("-", "−")


E4_LANGS = (
    ("e04_translation.json", "hi", "Hindi", "IndicTrans2"),
    ("e04_translation.json", "it", "Italian", "Opus-MT"),
    ("e04_translation_es_fr_pt.json", "es", "Spanish", "Opus-MT"),
    ("e04_translation_es_fr_pt.json", "fr", "French", "Opus-MT"),
    ("e04_translation_es_fr_pt.json", "pt", "Portuguese", "Opus-MT"),
)


def e4_specs() -> list[Spec]:
    """E4 (translation, FLORES+ devtest): per language, COMET and chrF++ for Gemma and the baseline, and the paired
    bootstrap difference (Gemma − baseline) with its 95% interval."""
    out = [
        Spec(
            "e4.n",
            "e04_translation.json",
            "/summary/languages/hi/n",
            "FLORES+ devtest sentences per language",
            "sentences",
            split="none",
        )
    ]
    for ef, lang, name, base in E4_LANGS:
        L = f"/summary/languages/{lang}"
        out += [
            Spec(
                f"e4.{lang}.comet_gemma",
                ef,
                f"{L}/comet/gemma",
                f"{name} COMET, Gemma 4 31B",
                fmt=lambda x: f"{float(x):.4f}",
                split="none",
            ),
            Spec(
                f"e4.{lang}.comet_base",
                ef,
                f"{L}/comet/baseline_{lang}",
                f"{name} COMET, {base}",
                fmt=lambda x: f"{float(x):.4f}",
                split="none",
            ),
            Spec(
                f"e4.{lang}.comet_diff",
                ef,
                f"{L}/comet/gemma_minus_baseline/diff",
                f"{name} COMET, Gemma minus {base}",
                fmt=signed(4),
                split="none",
            ),
            Spec(
                f"e4.{lang}.comet_lo",
                ef,
                f"{L}/comet/gemma_minus_baseline/ci95_lo",
                f"{name} COMET difference, 95% interval low end",
                fmt=signed(4),
                split="none",
            ),
            Spec(
                f"e4.{lang}.comet_hi",
                ef,
                f"{L}/comet/gemma_minus_baseline/ci95_hi",
                f"{name} COMET difference, 95% interval high end",
                fmt=signed(4),
                split="none",
            ),
            Spec(
                f"e4.{lang}.chrf_gemma",
                ef,
                f"{L}/chrf/gemma",
                f"{name} chrF++, Gemma 4 31B",
                fmt=lambda x: f"{float(x):.1f}",
                split="none",
            ),
            Spec(
                f"e4.{lang}.chrf_base",
                ef,
                f"{L}/chrf/baseline_{lang}",
                f"{name} chrF++, {base}",
                fmt=lambda x: f"{float(x):.1f}",
                split="none",
            ),
            Spec(
                f"e4.{lang}.chrf_diff",
                ef,
                f"{L}/chrf/gemma_minus_baseline/diff",
                f"{name} chrF++, Gemma minus {base}",
                fmt=signed(1),
                split="none",
            ),
            Spec(
                f"e4.{lang}.chrf_lo",
                ef,
                f"{L}/chrf/gemma_minus_baseline/ci95_lo",
                f"{name} chrF++ difference, 95% interval low end",
                fmt=signed(1),
                split="none",
            ),
            Spec(
                f"e4.{lang}.chrf_hi",
                ef,
                f"{L}/chrf/gemma_minus_baseline/ci95_hi",
                f"{name} chrF++ difference, 95% interval high end",
                fmt=signed(1),
                split="none",
            ),
            Spec(
                f"e4.{lang}.never_aligned",
                ef,
                f"{L}/gemma_never_aligned",
                f"{name} sentences Gemma never returned (scored as empty)",
                "sentences",
                split="none",
            ),
        ]
    return out


def e11_specs() -> list[Spec]:
    f = EV / "e11_adversarial.json"
    if not f.exists():
        return []
    out = []
    for case, st in json.loads(f.read_text())["summary"].get("cases", {}).items():
        for setting in st:
            for key in ("tries", "gemma_failed", "blocked", "leaks", "extended"):
                out.append(
                    Spec(
                        f"e11.{case}.{setting}.{key}",
                        "e11_adversarial.json",
                        f"/summary/cases/{case}/{setting}/{key}",
                        f"E11 {case} ({setting}): {key}",
                        "tries",
                    )
                )
    return out


def e11_table() -> str | None:
    f = EV / "e11_adversarial.json"
    if not f.exists():
        return None
    cases = json.loads(f.read_text())["summary"].get("cases", {})
    lines = [
        "| What we tried to make Gemma get wrong | Gemma got it wrong (production) | Caught by the checks | "
        "Reached the viewer | Gemma got it wrong (stress) | Sent to extended description instead |",
        "|---|---|---|---|---|---|",
    ]
    for c in cases:
        spec = REPO_ROOT / "data" / "adversarial" / f"{c}.json"
        what = json.loads(spec.read_text()).get("baits", c) if spec.exists() else c
        lines.append(
            f"| {what[:1].upper() + what[1:]} | <pending: e11.{c}.production.gemma_failed> of "
            f"<pending: e11.{c}.production.tries> | <pending: e11.{c}.production.blocked> | "
            f"<pending: e11.{c}.production.leaks> | <pending: e11.{c}.stress.gemma_failed> of "
            f"<pending: e11.{c}.stress.tries> | <pending: e11.{c}.production.extended> |"
        )
    return "\n".join(lines)


def e13_failed_sentence() -> str | None:
    if not (EV / "e13_serving_tokenfactory.json").exists():
        return None
    return "<pending: e13.failed> of <pending: e13.requests> requests failed (client-side, dev requests replayed)."


def results_more() -> str | None:
    """Plain-words lines for every experiment that has run, regenerated on each build (markers keep the block)."""
    rows = []
    if (EV / "e15_asr.json").exists():
        rows.append(
            "- **Speech recognition (E15, dev set).** We chose Whisper large-v3-turbo: its English word error rate was "
            "<pending: e15.wer_en_turbo> on <pending: e15.n_per_lang> FLEURS clips, against <pending: e15.wer_en_large> "
            "for the larger large-v3 (Hindi <pending: e15.wer_hi_turbo>, Italian <pending: e15.wer_it_turbo>). After "
            "forced alignment, word boundaries were off by <pending: e15.boundary_aligned_median> at the median and "
            "<pending: e15.boundary_aligned_p95> at the 95th percentile, on <pending: e15.boundary_n> word boundaries of "
            "our synthetic clips. Raw Whisper timestamps were closer at the median (<pending: e15.boundary_raw_median>) "
            "but worse in the tail (<pending: e15.boundary_raw_p95> at the 95th percentile); the guard is set from the "
            "tail, so description keeps "
            "<pending: e15.guard_ms> ms clear of speech. Large-v3 could not produce word timings within our "
            "computer's memory, so it was not a candidate."
        )
    e4 = EV / "e04_translation.json"
    if e4.exists() and json.loads(e4.read_text()).get("passed"):
        rows.append(
            "- **Translation (E4, FLORES+ devtest, <pending: e4.n> sentences per language, not our videos).** "
            "Two scores: COMET, a model trained to match human quality ratings, and chrF++, which counts character "
            "and word overlap with one human translation. Italian: Gemma 4 31B scored higher than Opus-MT, a "
            "widely used open English–Italian model, on both: COMET <pending: e4.it.comet_gemma> against "
            "<pending: e4.it.comet_base> (difference <pending: e4.it.comet_diff>, 95% interval "
            "<pending: e4.it.comet_lo> to <pending: e4.it.comet_hi>) and chrF++ <pending: e4.it.chrf_gemma> against "
            "<pending: e4.it.chrf_base> (<pending: e4.it.chrf_diff>, <pending: e4.it.chrf_lo> to "
            "<pending: e4.it.chrf_hi>). Hindi was mixed: Gemma scored higher on COMET (<pending: e4.hi.comet_gemma> "
            "against <pending: e4.hi.comet_base>, <pending: e4.hi.comet_diff>, <pending: e4.hi.comet_lo> to "
            "<pending: e4.hi.comet_hi>), but IndicTrans2, a model built for Indian languages, scored higher on "
            "chrF++ (<pending: e4.hi.chrf_base> against <pending: e4.hi.chrf_gemma>; Gemma "
            "<pending: e4.hi.chrf_diff>, <pending: e4.hi.chrf_lo> to <pending: e4.hi.chrf_hi>). Gemma returned "
            "every sentence (<pending: e4.hi.never_aligned> missing in Hindi, <pending: e4.it.never_aligned> in "
            "Italian).\n\n  ![Gemma minus the baseline for each language and score, with 95% intervals](docs/charts/e4_translation.png)"
        )
    if (EV / "e05_easyread.json").exists():
        rows.append(
            "- **Easy-read (E5, 10 W3C videos never used for tuning).** Asked to simplify the captions, Gemma alone "
            'kept every "not", "never" and "no" in <pending: e5.neg_gemma_k> of <pending: e5.neg_gemma_n> '
            "cues; in the others the sentence lost its negation and so its meaning. The easy-read AccessCast "
            "published kept them in <pending: e5.neg_ours_k> of <pending: e5.neg_ours_n>, and sent "
            "<pending: e5.sent> of <pending: e5.of> cues to a person instead. Paced for slow reading (at most 130 "
            "words a minute): <pending: e5.wpm_ours_k> of <pending: e5.neg_ours_n> published cues, against "
            "<pending: e5.wpm_source_k> of <pending: e5.of> original captions. These counts use a negation counter "
            "close to our own check, so a blind rating by people leads this experiment; it is still to come."
        )
    more_e4 = e4_more_languages()
    if more_e4:
        rows.append(more_e4)
    e18 = e18_row()
    if e18:
        rows.append(e18)
    e17 = e17_row()
    if e17:
        rows.append(e17)
    e19 = e19_row()
    if e19:
        rows.append(e19)
    if (EV / "e16_ui_a11y.json").exists():
        rows.append(
            "- **Accessibility (E16).** Automatic tests with keyboard-only runs and axe-core scans pass: player "
            "<pending: e16.player_passed> of <pending: e16.player_total>, review app and Studio "
            "<pending: e16.review_passed> of <pending: e16.review_total>. No blind tester has used it yet."
        )
    if (EV / "tests.json").exists():
        rows.append(
            "- **Tests.** <pending: tests.passed> of <pending: tests.total> unit and golden tests pass, in "
            "<pending: tests.files> files; they run <pending: tests.coverage> of the lines in `src/accesscast` "
            "(`scripts/test_stats.py`, evidence/tests.json)."
        )
    return "\n".join(rows) if rows else None


def _verdict(lo: float, hi: float, label: str) -> str:
    """Words for a paired difference (Gemma − baseline) from its 95% interval, never from the point estimate alone."""
    return (
        f"Gemma higher on {label}"
        if lo > 0
        else f"Opus-MT higher on {label}"
        if hi < 0
        else f"no clear difference on {label}"
    )


def e4_more_languages() -> str | None:
    """E4 for Spanish, French and Portuguese: one sentence per language, direction read from the interval."""
    f = EV / "e04_translation_es_fr_pt.json"
    if not f.exists() or not json.loads(f.read_text()).get("passed"):
        return None
    langs = json.loads(f.read_text())["summary"]["languages"]
    parts = []
    for ef, lang, name, _base in E4_LANGS:
        if ef != f.name or lang not in langs:
            continue
        L = langs[lang]
        words = []
        for m, label in (("comet", "COMET"), ("chrf", "chrF++")):
            d = L[m]["gemma_minus_baseline"]
            v = _verdict(float(d["ci95_lo"]), float(d["ci95_hi"]), label)
            words.append(
                f"{v} (Gemma <pending: e4.{lang}.{m}_gemma>, Opus-MT <pending: e4.{lang}.{m}_base>; difference "
                f"<pending: e4.{lang}.{m}_diff>, 95% interval <pending: e4.{lang}.{m}_lo> to "
                f"<pending: e4.{lang}.{m}_hi>)"
            )
        parts.append(f"{name}: {words[0]}, {words[1]}")
    if not parts:
        return None
    return (
        "- **More languages (E4, same FLORES+ devtest, Gemma 4 31B against Opus-MT).** "
        + "; ".join(parts)
        + ". Sentences Gemma never returned: <pending: e4.es.never_aligned> Spanish, "
        "<pending: e4.fr.never_aligned> French, <pending: e4.pt.never_aligned> Portuguese. Evidence: "
        "evidence/e04_translation_es_fr_pt.json."
    )


def e19_row() -> str | None:
    f = EV / "e19_pictures.json"
    if not f.exists() or not json.loads(f.read_text()).get("checks", {}).get("no_endpoint_errors"):
        return None
    rules = json.loads(f.read_text())["summary"].get("rules_on_first_lines") or {}
    top = next(iter(rules), None)
    why = (
        f" The rule that stopped first lines most often was {top} ({RULE_WORDS[top]})."
        if top in RULE_WORDS
        else ""
    )
    return (
        "- **Describing still pictures (E19, one frame per scene of our three dev videos).** The live picture API's "
        "code path, with the full repair budget: Gemma's first line broke at least one of our rules for "
        "<pending: e19.first_broke> of <pending: e19.lines> pictures, and passed for <pending: e19.first_passed>."
        + why
        + " After repair, <pending: e19.published> of <pending: e19.lines> lines passed every rule and "
        "<pending: e19.to_person> went to a person. Median <pending: e19.seconds> per picture on AMD Token Factory, "
        "as our client saw it. The rules are ours, so this measures how often the loop has work to do, not a quality "
        "score. Evidence: evidence/e19_pictures.json.\n\n  ![Which rules stopped Gemma's first line on each picture, "
        "and how many lines passed after repair](docs/charts/e19_pictures.png)"
    )


def _e17_caveat(by_model: dict[str, dict[str, int]]) -> str:
    """Said when the other models seldom took the bait: then the run tested the checks less than Gemma's did."""
    gemma = by_model.get("Gemma-4-31B-IT", {})
    others = [v for k, v in by_model.items() if k != "Gemma-4-31B-IT"]
    g_rate = gemma.get("took_bait", 0) / max(1, gemma.get("tries", 0))
    o_rate = sum(v.get("took_bait", 0) for v in others) / max(1, sum(v.get("tries", 0) for v in others))
    if others and o_rate < g_rate / 2:
        return "The other two models seldom took these baits, so this run tested our checks less than Gemma's did. "
    return ""


def e17_row() -> str | None:
    f = EV / "e17_model_ladder.json"
    if not f.exists() or not json.loads(f.read_text()).get("checks", {}).get("every_model_ran"):
        return None
    parts = [
        f"{name} took the bait in <pending: e17.{slug}.bait> of <pending: e17.{slug}.tries> lines "
        f"(no usable first draft for <pending: e17.{slug}.no_output>; reached a viewer: "
        f"<pending: e17.{slug}.reached>)"
        for slug, _model, name in E17_MODELS
    ]
    return (
        "- **Other models on AMD Token Factory (E17, our own attack clips, dev).** The same attacks and the same "
        "checks, with a different model writing: "
        + "; ".join(parts)
        + (
            ". With every model, no attack answer reached a viewer. "
            if int(json.loads(f.read_text())["summary"]["reached_viewer_total"]) == 0
            else ". Some attack answers reached a viewer; we list each one in the evidence file. "
        )
        + _e17_caveat(json.loads(f.read_text())["summary"]["by_model"])
        + "An empty first draft (an answer that was not valid JSON) goes back for repair like any failed line. "
        "Gemma ran 20 tries per setting, the others 5. "
        "Evidence: evidence/e17_model_ladder.json.\n\n  ![Per model: lines that took the bait and answers "
        "that reached a viewer](docs/charts/e17_ladder.png)"
    )


RULE_WORDS = {
    "AD001": "too long for the pause",
    "AD007": "over the word budget",
    "AD009": "a name nobody said or showed",
    "AD010": "a claim the picture does not support",
    "AD011": "it describes a sound or speech",
    "AD012": "words not grounded in what Gemma saw",
    "AD014": "commentary instead of description",
    "AD017": "an emotion the picture does not show",
    "AD019": "empty or filler",
    "CC001": "reading speed",
    "CC002": "line length",
    "CC009": "a name or number changed",
    "VO001": "the voice runs past its slot",
    "VO003": "a name or number changed",
}  # plain words for docs/rules.md ids


def e18_row() -> str | None:
    """E18 (dev): per language, lines that passed every check; names the rule that held the most lines."""
    f = EV / "e18_language_checks.json"
    if not f.exists():
        return None
    by = json.loads(f.read_text())["summary"]["by_language"]
    names = {"hi": "Hindi", "it": "Italian", "es": "Spanish", "fr": "French", "pt": "Portuguese"}
    held: dict[str, int] = {}
    for r in by.values():
        for rule, n in r["held_by_rule"].items():
            held[rule] = held.get(rule, 0) + int(n)
    parts = [f"{names[k]} <pending: e18.{k}.passed> of <pending: e18.{k}.lines>" for k in names if k in by]
    top = max(held, key=lambda k: held[k]) if held else None
    tail = (
        f" The check that held the most lines was {top} ({RULE_WORDS[top]})."
        if top and top in RULE_WORDS
        else ""
    )
    return (
        "- **Every language through the same checks (E18, our two site drafts, dev).** Translated subtitle and "
        "voice-over lines that passed every check on their own: "
        + ", ".join(parts)
        + ". The rest went to a person, not to viewers."
        + tail
        + " Evidence: evidence/e18_language_checks.json.\n\n  ![Lines per language that passed every check, "
        "and lines held for a person](docs/charts/e18_languages.png)"
    )


SECTIONS: dict[str, Callable[[], str | None]] = {
    "e11.table": e11_table,
    "e13.failed_sentence": e13_failed_sentence,
    "results.more": results_more,
}
REGENERATED = (
    "results.more",
    "e11.table",
)  # kept between markers and rebuilt every time, as experiments land


def register() -> dict[str, Any]:
    reg_p = EV / "public-claims.json"
    reg = json.loads(reg_p.read_text())
    by_id = {c["claim_id"]: c for c in reg["claims"]}
    for s in [
        *SPECS,
        *e11_specs(),
        *e4_specs(),
        *amd_specs(),
        *tests_specs(),
        *e18_specs(),
        *e17_specs(),
        *repo_specs(),
        *e19_specs(),
    ]:
        f = EV / s.path
        if not f.exists():
            continue
        doc = json.loads(f.read_text())
        if doc.get("checks", {}).get("no_endpoint_errors") is False:
            continue  # a run the provider failed (outage, rate limit) measured nothing about the model
        try:
            val = resolve_pointer(doc, s.pointer)
        except (KeyError, IndexError, ValueError):
            continue
        if val is None:
            continue
        # keep the files already recorded as quoting this claim: `--fill` replaces each placeholder with its
        # value, so after the first fill the placeholder scan alone would forget where the number appears
        known = list(by_id.get(s.claim_id, {}).get("public_files", []))
        by_id[s.claim_id] = {
            "claim_id": s.claim_id,
            "text": s.text,
            "value": val,
            "unit": s.unit,
            "status": "measured",
            "split": doc.get("split", s.split),
            "evidence": [{"path": f"evidence/{s.path}", "sha256": sha256_file(f), "pointer": s.pointer}],
            "public_files": known,
            "display": [s.fmt(val)],
        }
    cited = EV / "cited_claims.json"
    if cited.exists():
        for c in json.loads(cited.read_text()).get("verified", []):
            known = by_id.get(c["claim_id"], {}).get("public_files", [])
            files = list(dict.fromkeys([*known, *c.get("public_files", [])]))
            by_id[c["claim_id"]] = {**c, "evidence": [], "public_files": files}
    reg["claims"] = sorted(by_id.values(), key=lambda c: c["claim_id"])
    reg_p.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    return {c["claim_id"]: c for c in reg["claims"]}


def fill(claims: dict[str, Any]) -> int:
    n = 0
    for rel in PUBLIC_FILES:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for (
            sec,
            gen,
        ) in SECTIONS.items():  # expand generated sections first; their cells are claim placeholders
            start, end = f"<!-- {sec}:start -->", f"<!-- {sec}:end -->"
            if sec in REGENERATED and start in text and end in text:
                block = gen()
                if block:
                    a, b = text.index(start) + len(start), text.index(end)
                    text = text[:a] + "\n" + block + "\n" + text[b:]
                continue
            block = gen() if f"<pending: {sec}>" in text else None
            if block:
                wrapped = f"{start}\n{block}\n{end}" if sec in REGENERATED else block
                text = text.replace(f"<pending: {sec}>", wrapped)

        def sub(m: re.Match[str], rel: str = rel) -> str:
            nonlocal n
            c = claims.get(m.group(1))
            if c and c.get("display"):
                n += 1
                if rel not in c["public_files"]:
                    c["public_files"].append(rel)
                return str(c["display"][0])
            return m.group(0)

        new = re.sub(r"<pending:\s*([\w.\-]+)\s*>", sub, text)
        if new != text:
            p.write_text(new, encoding="utf-8")
    reg_p = EV / "public-claims.json"
    reg = json.loads(reg_p.read_text())
    reg["claims"] = sorted(claims.values(), key=lambda c: c["claim_id"])
    reg_p.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    return n


if __name__ == "__main__":
    claims = register()
    print(f"{len(claims)} claims registered")
    if "--fill" in sys.argv:
        print(f"{fill(claims)} placeholders filled")
    _ = Path
