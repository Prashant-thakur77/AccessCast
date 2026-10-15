# Compliance matrix

A navigation aid for judges, not a scoring claim. Each row points to where the proof is. Rows marked "pending" are listed in [`docs/milestones.md`](milestones.md).

## Submission requirements (event page, read 14–16 Oct 2026)

| Requirement | Where | Status |
|---|---|---|
| Cover image | [`docs/cover.png`](cover.png) | draft |
| Demo video | link in [`docs/lablab.md`](lablab.md) | pending |
| Slide deck | [`docs/deck/deck.pdf`](deck/deck.pdf) (source [`deck.md`](deck/deck.md)) | draft, numbers pending |
| Public GitHub repository | https://github.com/Prashant-thakur77/AccessCast | done |
| Demo platform | Web | done |
| App URL | https://accesscast.vercel.app | live (fixture draft until reviewed dev videos replace it) |
| AMD technology | Gemma 4 served with vLLM on ROCm on an AMD Instinct MI300X; AMD Token Factory for the always-on proof endpoint | pending the droplet |
| Original work, MIT | [`LICENSE`](../LICENSE); reused code keeps its licence ([`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)) | done |

## Track brief: "Create a New Kind of Experience"

| The brief asks | What we did | Fastest proof |
|---|---|---|
| Show the experience changing for at least two audiences | Five profiles in one player, switchable on the same video | Live player; `five-ways.html` |
| Explain what was created and what the models decided | Per-line record: frames shown to Gemma, the pause, the budget, the draft, checks that fired, repairs, the final text and the reviewer | "What the models decided" drawer; `reports/decisions.json` |
| Show how quality and consistency were controlled | Rules in code against the audio timeline, Gemma repair, human approval, server-side render gate, one shared analysis | [`docs/rules.md`](rules.md); `review/gate.py`; E9 determinism |
| Give the cost per experience | GPU time at the hourly price, split per version, plus measured review time | `evidence/e14_cost.json` (pending) |
| Say who pays and why | Laws with dates and fines, buyers, list prices labelled as list prices | README "Who pays" (pending verified citations) |

## Must-haves (PLAN §5)

| # | Must-have | Evidence | Status |
|---|---|---|---|
| 1 | Headline number against a named baseline, one change | `evidence/e01_verifier_ab.json` | harness ready; needs the GPU |
| 2 | Baselines judges respect | E1 arm A, E3 bigger model, E2 V0, E7 naive captioner, E4 translators, E12 manual time | harnesses ready |
| 3 | Data never used for tuning | `evidence/test_freeze.json`, `evidence/test_runs.jsonl`, [`eval/PREREGISTRATION.md`](../eval/PREREGISTRATION.md) | pre-registration done |
| 4 | Every number from a script | `evidence/public-claims.json`, `make claims-check` | checker done; registry filling |
| 5 | A negative result | README "What didn't work" | pending results |
| 6 | AMD story in numbers | `e13_serving_*.json`, `e14_cost.json`, `doctor.json`, `e02_ladder_*.json` | harnesses ready |
| 7 | Live adversarial case | `e11_adversarial.json`, `/proof` | clips and harness ready; proof API written |
| 8 | Soak, determinism, offline | `e08_soak.json`, `e09_determinism.json`, `e10_offline.json` | harnesses ready and smoke-tested |
| 9 | Page, README and deck consistent | `make claims-check` in CI | done |
| 10 | Demo awake; plain pitch | Vercel static site; `evidence/uptime.json` (every 30 min); [`docs/demo-script.md`](demo-script.md) | site live; script drafted |
