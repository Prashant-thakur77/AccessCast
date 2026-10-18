# Compliance matrix

A navigation aid for judges, not a scoring claim. Each row points to where the proof is. Every number it leads to
comes from a file in [`evidence/`](../evidence/) through [`evidence/public-claims.json`](../evidence/public-claims.json).

## Submission requirements (event page)

| Requirement | Where | Status |
|---|---|---|
| Cover image | [`docs/cover.png`](cover.png) (a real frame and a real description line from the Sintel draft) | done |
| Demo video | link in [`README.md`](../README.md) and [`docs/lablab.md`](lablab.md) | uploaded by the team |
| Slide deck | [`docs/deck/deck.pdf`](deck/deck.pdf) (source [`deck.md`](deck/deck.md)) | done |
| Public GitHub repository | https://github.com/Prashant-thakur77/AccessCast | done |
| Demo platform | Web | done |
| App URL | https://accesscast.vercel.app (player, every viewer, how it works, results, live proof) | live; checked after every deploy (`evidence/live_check.json`) |
| AMD technology | Gemma 4 31B on **AMD Token Factory** for every vision, writing, translation and repair call; strict check of the served model on every answer | done (`evidence/amd_usage.json`) |
| Original work, MIT | [`LICENSE`](../LICENSE); reused code keeps its licence ([`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)) | done |

## Track brief: "Create a New Kind of Experience"

| The brief asks | What we did | Fastest proof |
|---|---|---|
| Show the experience changing for at least two audiences | One player, eight viewer choices on the same video: can't see, can't hear, simpler words, and five languages | [Live player](https://accesscast.vercel.app/watch.html); [Every viewer](https://accesscast.vercel.app/five-ways.html) |
| Explain what was created and what the models decided | Per-line record: frames shown to Gemma, the pause, the budget, the draft, checks that fired, repairs, the final text and the reviewer | "What the models decided" drawer; [How it works](https://accesscast.vercel.app/how.html); `decisions.json` |
| Show how quality and consistency were controlled | Rules in code against the audio timeline, Gemma repair, human approval, server-side render gate, one shared analysis | [`docs/rules.md`](rules.md); `src/accesscast/review/gate.py`; E9, E11, E17, E18 |
| Give the cost per experience | Gemma tokens per finished minute from real call logs, priced at a published list price (labelled an estimate), plus review time | `evidence/e14_cost.json`; README "Who pays" |
| Say who pays and why | Laws with dates and fines, named buyers, list prices labelled as list prices | README "Who pays"; `evidence/cited_claims.json` |

## Must-haves

| # | Must-have | Evidence | Status |
|---|---|---|---|
| 1 | Headline number against a named baseline, one change | E5: Gemma alone against AccessCast as published, on test videos never used for tuning (`evidence/e05_easyread.json`) | done |
| 2 | Baselines judges respect | Gemma alone (E1, E5, E11), IndicTrans2 and Opus-MT (E4), Whisper large-v3 (E15), other Token Factory models (E17) | done |
| 3 | Data never used for tuning | `evidence/test_freeze.json`, `evidence/test_runs.jsonl`, [`eval/PREREGISTRATION.md`](../eval/PREREGISTRATION.md) | done |
| 4 | Every number from a script | `evidence/public-claims.json`, `make claims-check` in CI | done |
| 5 | A negative result | README "What didn't work" (E1, E4 chrF++, E7) | done |
| 6 | AMD story in numbers | `amd_usage.json`, `e13_serving_tokenfactory.json`, `e14_cost.json`, `e17_model_ladder.json` | done on Token Factory; no MI300X droplet, so no GPU-memory numbers |
| 7 | Live adversarial case | `e11_adversarial.json`; [proof page](https://accesscast.vercel.app/proof.html) runs it live | done |
| 8 | Reliability | `e09_determinism.json`, `tests.json`, `e16_ui_a11y.json`, `live_check.json`, [`docs/incidents.md`](incidents.md) | done; soak and offline runs need our own GPU server |
| 9 | Page, README and deck consistent | `make claims-check` in CI | done |
| 10 | Demo awake; plain pitch | Vercel static site with a live API; `evidence/uptime.json`; [`docs/demo-script.md`](demo-script.md) | done |
