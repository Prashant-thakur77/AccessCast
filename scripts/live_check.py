"""After a deploy: does the live site work for every viewer? Fails (exit 7) on any missing page or chart, any Try
request that does not answer, or any check that crashed instead of running (VERIFIER_CRASH), in any language.

Writes evidence/live_check.json always, including when something fails. Six Try requests and one picture through
the public APIs, one at a time (our key's rate limit), exactly as a visitor's browser makes them.

Usage: python scripts/live_check.py [https://accesscast.vercel.app]
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.common import Experiment, run_experiment  # noqa: E402

PAGES = (
    "index.html",
    "watch.html",
    "five-ways.html",
    "how.html",
    "results.html",
    "proof.html",
    "data/claims.json",
)
CHARTS = (
    "e5_negations",
    "e11_attacks",
    "e4_translation",
    "e14_tokens",
    "amd_usage",
    "e13_serving",
    "e17_ladder",
    "e18_languages",
    "timeline_nasa",
)
VERSIONS = ("easy", "hi", "it", "es", "fr", "pt")
TEXT = "Do not press the red button before 5 pm."  # a negation and a number: the checks that matter most


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "https://accesscast.vercel.app").rstrip("/")
    exp = Experiment("live_check", "none", config={"site": base, "text": TEXT, "versions": list(VERSIONS)})

    def body(e: Experiment) -> None:
        with httpx.Client(timeout=130, follow_redirects=True) as c:
            missing = []
            for path in [*PAGES, *(f"charts/{n}.png" for n in CHARTS)]:
                code = c.get(f"{base}/{path}").status_code
                e.results.append({"get": path, "status": code})
                if code != 200:
                    missing.append(path)
            crashed, unanswered = [], []
            for v in VERSIONS:
                r = c.post(f"{base}/api/try", params={"version": v}, json={"text": TEXT})
                row: dict[str, object] = {"try": v, "status": r.status_code}
                if r.status_code == 200:
                    cues = r.json().get("cues", [])
                    rules = sorted({f["rule"] for cue in cues for f in cue.get("findings", [])})
                    row.update(rules=rules, published=[cue.get("published") for cue in cues])
                    if "VERIFIER_CRASH" in rules:
                        crashed.append(v)
                    if not cues:
                        unanswered.append(v)
                else:
                    unanswered.append(v)
                e.results.append(row)
            # one sample picture through the live picture API: it must answer, and no check may crash; a provider
            # outage that fails closed (no facts, nothing published) is the correct behaviour, recorded as such
            import base64

            img = c.get(f"{base}/assets/samples/nasa-eclipse.jpg")
            picture: dict[str, object] = {"describe": "nasa-eclipse.jpg", "sample_status": img.status_code}
            if img.status_code == 200:
                url = "data:image/jpeg;base64," + base64.b64encode(img.content).decode()
                r = c.post(f"{base}/api/describe", json={"image": url})
                picture["status"] = r.status_code
                if r.status_code == 200:
                    d = r.json()
                    rules = sorted({f["rule"] for ln in d.get("lines", []) for f in ln.get("findings", [])})
                    picture.update(
                        facts=len(d.get("facts", [])),
                        lines=[ln.get("published") for ln in d.get("lines", [])],
                        rules=rules,
                        evidence_problem=d.get("evidence_problem"),
                    )
                    if "VERIFIER_CRASH" in rules:
                        crashed.append("describe")
                else:
                    unanswered.append("describe")
            else:
                missing.append("assets/samples/nasa-eclipse.jpg")
            e.results.append(picture)
        e.summary = {"missing": missing, "crashed": crashed, "unanswered": unanswered}
        e.checks["every_page_and_chart"] = not missing
        e.checks["no_check_crashed"] = not crashed
        e.checks["every_version_answered"] = not unanswered

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
