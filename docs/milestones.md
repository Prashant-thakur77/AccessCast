# Milestone task list (PLAN §22)

Status: `[x]` done and verified · `[~]` in progress · `[ ]` not started · `[!]` blocked on a person (see `docs/outreach.md` and the batched request)

## M0 Accounts and endpoints (P0)
- [!] MI300X droplet (team creates, or gives an API token)
- [!] Token Factory key → `GET /models` → `evidence/tokenfactory_models.json`
- [!] HF token + gated licences
- [x] `deploy/droplet_bootstrap.sh`, `deploy/serve_gemma.sh`, `make serve-gemma`, health loop (untested until the droplet exists)
- [ ] 31B answers an image prompt; E4B answers a 10 s audio prompt
- [ ] `accesscast doctor --deep` → `evidence/doctor.json`; `deploy/versions.lock` pinned by digest

## M1 Skeleton (P0)
- [x] repo layout, pyproject, policy updates, decisions summary
- [x] schemas (§8) + JSON Schema export to `docs/schemas/`
- [x] CLI with every stage (S0–S15) runnable; fake worker mode with canned outputs
- [x] 20 s committed fixture; `make demo-fixture` serves the player at `:8080/?audience=judge`
- [x] events log, LLM call log
- [x] unit tests + GitHub Actions CI (CPU)
- [x] README / JUDGES.md / `public-claims.json` skeletons; `make claims-check` passes on the empty registry

## M2 Analysis (P0)
- [x] Silero VAD licence resolved (MIT)
- [~] S0 ingest, S1 shots + scene merge, S2 Whisper + forced alignment, S2b E4B cross-check, S3 sounds, S4 gap map (code done; real-model runs need the droplet)
- [ ] debug timeline page; gap-map unit tests
- [ ] E15 on FLEURS + dev clips → ASR choice, aligner on/off, `guard_ms`

## M3 First described video (P0) — from here `main` is always submittable
- [ ] S5 evidence (+ Tesseract), S6 plan, S7 write, S8 verify + repair, S9 TTS (+ calibration), S14 standard mix
- [x] all §10.2 rules with pass/fail tests; `docs/rules.md`
- [ ] `report.json`; a person listens

## M4 Review and gate (P0)
- [ ] review app (keyboard, live re-verify, 409, history, timer, ARIA live region)
- [ ] server-side gate, `auto_approved` routing, `human_reviewed` stamp
- [ ] E16 on the review app (axe-core 0, keyboard-only e2e)

## M5 Captions and player (P0)
- [ ] SDH, easy-read, hi/it subtitles + rules
- [ ] player: five-profile picker, "Give me time to read", decisions drawer, "Same 20 seconds, five ways"
- [ ] E16 on the player; static site deployed (live URL from here on)

## M6 Voice-over and extended (P1)
- [ ] hi/it voice-over + description; extended version with `source_to_output`; remapped tracks; RN001–RN008

## M7 Evaluation (P0 for E1)
- [~] datasets fetched + hashed; `eval/PREREGISTRATION.md` (done); `make freeze-prompts` (script done)
- [ ] E1, E4, E5, E6, E7, E12, E15; claims added

## M8 AMD and reliability (P0 for E13/E14)
- [ ] E2 ladder, E3, E13, E14, E8, E9, E10, E11; memory table; users per GPU; `/proof`

## M9 Judge package and submission (P0)
- [ ] README, JUDGES.md, deck PDF, demo video, cover, `docs/lablab.md`; `make submission-check` green; consistency pass; uptime check; competition re-check; release tag `act3-submission`

## M10 Extras (P2)
- [ ] DAPT export, diarization, "try your own clip", detail levels, YouDescribe second test set, more languages
