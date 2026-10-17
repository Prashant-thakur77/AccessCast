"""Charts for the README, deck and site, drawn only from evidence files (no typed numbers). Each chart names its
data split and the evidence file it reads. Run with the workers env (it has matplotlib):

    cd workers && uv run python ../scripts/make_charts.py      → docs/charts/*.png
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
OUT = ROOT / "docs" / "charts"
INK, RED, SUN, GREEN, GREY, PAPER = "#141B34", "#E4402A", "#F2B705", "#1E7A4C", "#9AA0B4", "#FFFFFF"
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 12,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": PAPER,
        "axes.facecolor": PAPER,
    }
)


def ev(name: str) -> dict[str, Any] | None:
    p = EV / name
    return json.loads(p.read_text()) if p.exists() else None


def finish(fig: Any, ax: Any, title: str, source: str, name: str) -> None:
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", pad=14)
    fig.text(0.01, 0.01, source, fontsize=9, color="#4A4F63")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=150)
    plt.close(fig)
    print(OUT / f"{name}.png")


def e5_negations() -> None:
    e = ev("e05_easyread.json")
    if not e:
        return
    s = e["summary"]
    rows = []
    for label, arm, color in (
        ("Gemma 4 alone", "gemma_alone_on_the_same_cues", GREY),
        ("AccessCast, as published", "accesscast_published", GREEN),
    ):
        kept = s["arms"][arm]["negations_kept"]  # the same pointers the claims registry uses
        rows.append((label, kept["k"], kept["n"], color))
    fig, ax = plt.subplots(figsize=(10, 3.2))
    for i, (_label, k, n, color) in enumerate(rows):
        ax.barh(i, 100 * k / n, color=color, height=0.55)
        ax.text(100 * k / n + 0.6, i, f"{k} of {n}", va="center", fontweight="bold")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.set_xlim(80, 103)
    ax.set_xlabel('easy-read captions that kept every "not", "never" and "no" (%)')
    ax.invert_yaxis()
    finish(
        fig,
        ax,
        'A dropped "not" flips the meaning',
        f"Split: {e['split']} (10 W3C videos never used for tuning). Source: evidence/e05_easyread.json",
        "e5_negations",
    )


def e11_attacks() -> None:
    e = ev("e11_adversarial.json")
    if not e:
        return
    cases = e["summary"]["cases"]
    names = list(cases)
    took = [cases[c]["production"]["gemma_failed"] + cases[c]["stress"]["gemma_failed"] for c in names]
    tries = [cases[c]["production"]["tries"] + cases[c]["stress"]["tries"] for c in names]
    leaks = [cases[c]["production"]["leaks"] + cases[c]["stress"]["leaks"] for c in names]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    y = range(len(names))
    ax.barh(y, tries, color="#E6E8EF", height=0.6, label="tries")
    ax.barh(y, took, color=RED, height=0.6, label="Gemma took the bait")
    for i in y:
        ax.text(
            tries[i] + 0.5,
            i,
            f"bait {took[i]} of {tries[i]} · reached a viewer {leaks[i]}",
            va="center",
            fontsize=10,
        )
    ax.set_yticks(list(y), [n.split("_", 1)[1].replace("_", " ") for n in names])
    ax.invert_yaxis()
    ax.set_xlim(0, max(tries) * 1.9)
    ax.set_xlabel("tries (production and stress settings)")
    ax.legend(loc="center right", frameon=False, fontsize=10)
    finish(
        fig,
        ax,
        f"We attacked our own system. Answers that reached a viewer: {sum(leaks)}",
        f"Split: {e['split']} (our own attack clips, not the test set). Source: evidence/e11_adversarial.json",
        "e11_attacks",
    )


def e4_translation() -> None:
    rows = []
    for f in ("e04_translation.json", "e04_translation_es_fr_pt.json"):
        e = ev(f)
        if not e or not e.get("passed"):
            continue
        for lang, r in e["summary"]["languages"].items():
            for metric, scale in (("comet", 100), ("chrf", 1)):
                d = r[metric]["gemma_minus_baseline"]
                rows.append(
                    (
                        f"{lang} · {metric.upper().replace('CHRF', 'chrF++')}",
                        d["diff"] * scale,
                        d["ci95_lo"] * scale,
                        d["ci95_hi"] * scale,
                        r["baseline"],
                        f,
                    )
                )
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(10, 0.7 * len(rows) + 1.6))
    for i, (_label, d, lo, hi, base, _) in enumerate(rows):
        color = GREEN if lo > 0 else RED if hi < 0 else GREY
        ax.errorbar(d, i, xerr=[[d - lo], [hi - d]], fmt="o", color=color, capsize=5, markersize=8, lw=2)
        ax.text(max(hi, 0) + 0.3, i, f"vs {base}", va="center", fontsize=10)
    ax.axvline(0, color=INK, lw=1)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel("Gemma 4 31B minus the baseline (COMET × 100, chrF++ points), with 95% interval")
    finish(
        fig,
        ax,
        "Translation against specialist models",
        "Green: Gemma better · red: baseline better · grey: no clear difference. FLORES+ devtest, 1012 sentences each. evidence/"
        + ", evidence/".join(sorted({r[5] for r in rows})),
        "e4_translation",
    )


def e14_tokens() -> None:
    e = ev("e14_cost.json")
    if not e:
        return
    by = e["summary"]["tokens_per_finished_minute_by_version"]
    labels = {
        "shared": "shared (looking at the frames, planning)",
        "description_en": "audio description",
        "easy_read": "easy-read",
        "subtitles_hi_it": "Hindi + Italian subtitles",
        "voiceover_hi_it": "Hindi + Italian voice-over",
    }
    colors = [INK, RED, SUN, "#4A6F92", "#8F4A3A"]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    left = 0
    for (k, v), c in zip(by.items(), colors, strict=False):
        ax.barh(0, v, left=left, color=c, height=0.5, label=f"{labels.get(k, k)}: {v:,}")
        left += v
    ax.set_yticks([])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=2, frameon=False, fontsize=10)
    finish(
        fig,
        ax,
        f"What one finished minute costs in Gemma tokens: {e['summary']['tokens_per_finished_minute']:,}",
        f"Split: {e['split']} ({e['summary']['videos_counted']} dev videos, {e['summary']['video_minutes']} minutes). Source: evidence/e14_cost.json",
        "e14_tokens",
    )


def amd_usage() -> None:
    e = ev("amd_usage.json")
    if not e:
        return
    s = e["summary"]
    days = s["days"]
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.bar(list(days), list(days.values()), color=RED, width=0.5)
    for i, (_d, v) in enumerate(days.items()):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontweight="bold")
    ax.set_ylabel("Gemma requests answered")
    finish(
        fig,
        ax,
        f"On AMD Token Factory: {s['requests_answered']:,} Gemma 4 31B requests, {s['tokens_total']:,} tokens",
        f"{s['videos']} videos, {s['video_minutes']} minutes; unanswered after every retry: {s['no_answer_after_retries']:,}. Source: evidence/amd_usage.json (our call logs)",
        "amd_usage",
    )


def e13_serving() -> None:
    e = ev("e13_serving_tokenfactory.json")
    if not e:
        return
    rows = [(r["concurrency"], r["tokens_per_s"], r.get("p50_s"), r.get("p95_s")) for r in e["results"]]
    fig, ax = plt.subplots(figsize=(10, 3.4))
    x = range(len(rows))
    ax.bar([i - 0.2 for i in x], [r[2] for r in rows], width=0.4, color=GREY, label="median seconds")
    ax.bar([i + 0.2 for i in x], [r[3] for r in rows], width=0.4, color=RED, label="95th percentile seconds")
    for i, r in enumerate(rows):
        ax.text(i, max(r[2], r[3]) + 0.5, f"{r[1]} tokens/s", ha="center", fontweight="bold")
    ax.set_xticks(list(x), [f"{r[0]} at a time" for r in rows])
    ax.set_ylabel("seconds per description request")
    ax.legend(frameon=False)
    finish(
        fig,
        ax,
        "Gemma 4 31B on AMD Token Factory, measured from our side",
        f"{e['summary']['requests']} requests, {e['summary']['failed']} refused by our key's rate limit. Source: evidence/e13_serving_tokenfactory.json",
        "e13_serving",
    )


def e17_ladder() -> None:
    e = ev("e17_model_ladder.json")
    if not e:
        return
    rows = [r for r in e["results"] if not r.get("missing") and r.get("tries")]
    fig, ax = plt.subplots(figsize=(10, 0.8 * len(rows) + 1.8))
    for i, r in enumerate(rows):
        bait = 100 * r["took_bait"] / r["tries"]
        ax.barh(i, bait, color=RED if bait else GREY, height=0.55)
        ax.text(
            bait + 1,
            i,
            f"bait {r['took_bait']} of {r['tries']} · no answer {r['no_output']} · reached a viewer {r['reached_viewer']}",
            va="center",
            fontsize=10,
        )
    ax.set_yticks(range(len(rows)), [r["model"] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 160)
    ax.set_xlabel("lines where the model took the bait (%)")
    finish(
        fig,
        ax,
        f"Other models on AMD Token Factory, same checks. Reached a viewer: {e['summary']['reached_viewer_total']}",
        f"Split: {e['split']} (our own attack clips). Source: evidence/e17_model_ladder.json",
        "e17_ladder",
    )


def e18_languages() -> None:
    e = ev("e18_language_checks.json")
    if not e:
        return
    names = {"hi": "Hindi", "it": "Italian", "es": "Spanish", "fr": "French", "pt": "Portuguese"}
    rows = [(names.get(k, k), v) for k, v in e["summary"]["by_language"].items() if v["lines"]]
    fig, ax = plt.subplots(figsize=(10, 0.7 * len(rows) + 1.8))
    for i, (_name, v) in enumerate(rows):
        pct = 100 * v["passed"] / v["lines"]
        ax.barh(i, pct, color=GREEN, height=0.55)
        top = ", ".join(list(v["held_by_rule"])[:2]) or "none"
        ax.text(
            pct + 0.8,
            i,
            f"{v['passed']} of {v['lines']} · held for a person {v['held_for_a_person']} (mostly {top})",
            va="center",
            fontsize=10,
        )
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 150)
    ax.set_xlabel("subtitle and voice-over lines that passed every check (%)")
    finish(
        fig,
        ax,
        "Every language goes through the same checks",
        f"Split: {e['split']} ({e['summary']['projects']} site drafts; CC001 = reading speed). Source: evidence/e18_language_checks.json",
        "e18_languages",
    )


def timeline(sha12: str = "dac08bcd9d7a") -> None:
    base = ROOT / "site" / "p" / sha12
    if not (base / "analysis.json").exists():
        return
    an = json.loads((base / "analysis.json").read_text())
    dec = json.loads((base / "decisions.json").read_text())
    idx = json.loads((base / "index.json").read_text())
    dur = an["duration_ms"] / 1000
    fig, ax = plt.subplots(figsize=(12, 3.0))
    for a, b in an["speech"]:
        ax.add_patch(plt.Rectangle((a / 1000, 1.1), (b - a) / 1000, 0.8, color=INK, alpha=0.75, lw=0))
    for a, b in an["gaps"]:
        ax.add_patch(plt.Rectangle((a / 1000, 1.1), (b - a) / 1000, 0.8, color=SUN, lw=0))
    std = [i for i in dec["items"] if i["kind"] == "ad" and not i["extended"]]
    ext = [i for i in dec["items"] if i["kind"] == "ad" and i["extended"]]
    for i in std:
        dur_s = ((i.get("tts") or {}).get("duration_ms") or 0) / 1000
        ax.add_patch(plt.Rectangle((i["anchor_ms"] / 1000, 0.15), max(dur_s, 0.3), 0.7, color=GREEN, lw=0))
    for i in ext:
        ax.plot([i["anchor_ms"] / 1000], [0.5], marker="v", color=RED, markersize=9)
    ax.set_xlim(0, dur)
    ax.set_ylim(0, 2.1)
    ax.set_yticks([0.5, 1.5], ["description", "sound"])
    ax.set_xlabel("seconds")
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(color=INK, alpha=0.75, label="speech"),
            Patch(color=SUN, label="pause"),
            Patch(color=GREEN, label=f"line spoken in a pause ({len(std)})"),
            Line2D(
                [], [], marker="v", color=RED, lw=0, label=f"line read while the picture holds ({len(ext)})"
            ),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.32),
        ncol=4,
        frameon=False,
        fontsize=10,
    )
    finish(
        fig,
        ax,
        f"One real clip: where the description goes ({idx.get('title', sha12)})",
        "Machine draft, not yet reviewed. Source: the clip's analysis.json and decisions.json on the site",
        "timeline_nasa",
    )


if __name__ == "__main__":
    for f in (
        e5_negations,
        e11_attacks,
        e4_translation,
        e14_tokens,
        amd_usage,
        e13_serving,
        e17_ladder,
        timeline,
    ):
        f()
