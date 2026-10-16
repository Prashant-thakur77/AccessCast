# Milestone task list (PLAN §22)

Status: `[x]` done and verified · `[~]` in progress · `[ ]` not started · `[!]` blocked on a person (see `docs/outreach.md` and the batched request)

## M0 Accounts and endpoints (P0)
- [x] ~~MI300X droplet~~ not available (no accepted payment card): D-021, Gemma 4 31B on AMD Token Factory instead
- [x] Token Factory key → `GET /models` → `evidence/tokenfactory_models.json`
- [~] HF token in `.env`; gated licences accepted except pyannote community-1 (speaker labels wait for it)
- [x] `deploy/droplet_bootstrap.sh`, `deploy/serve_gemma.sh`, `make serve-gemma`, health loop (untested until the droplet exists)
- [x] 31B answers image prompts on Token Factory (every dev run); E4B not available (D-021: sound labels from AST, D-022)
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
- [x] S0 ingest, S1 shots + scene merge, S2 Whisper + forced alignment + VAD gate, S2c speaker labels (waiting for the gated model), S3 sounds (AST), S4 gap map: real runs on 20 dev clips; S2b not run (D-021)
- [x] timeline view (review app lanes: words, gaps, description, captions, voice-over) ; gap-map unit tests
- [~] E15 runs tonight on dev data (FLEURS + synthetic boundary clips), then its decision is applied

## M3 First described video (P0) — from here `main` is always submittable
- [x] S5 evidence, S6 plan (several lines per pause, extended holds), S7 write, S8 verify + repair, S9 TTS (calibration refitted on dev, D-024): real Gemma 4 31B runs on 20 dev clips
- [x] all §10.2 rules with pass/fail tests; `docs/rules.md`
- [!] `report.json` written per run; a person reviews and listens to the two site clips (Plane, Sintel)

## M4 Review and gate (P0)
- [x] review app (keyboard, live re-verify, 409, history, timer, ARIA live region)
- [x] server-side gate, `auto_approved` routing, `human_reviewed` stamp
- [x] E16 on the review app (axe-core 0, keyboard-only e2e) — `evidence/e16_ui_a11y.json`

## M5 Captions and player (P0)
- [x] SDH, easy-read, hi/it subtitles + rules (real-model quality needs the GPU)
- [x] player: five-profile picker, "Give me time to read", decisions drawer, "Same 20 seconds, five ways"
- [x] E16 on the player; static site deployed at https://accesscast.vercel.app (fixture draft; reviewed dev videos replace it)

## M6 Voice-over and extended (P1)
- [~] hi/it voice-over + description; extended version with `source_to_output`; remapped tracks; RN001–RN008 (RN004 not wired yet; Chatterbox not added; Kokoro hi/it voices in use)

## M7 Evaluation (P0 for E1)
- [~] datasets fetched + hashed; `eval/PREREGISTRATION.md` (done); `make freeze-prompts` (script done)
- [~] harnesses for E1, E4, E5, E6, E7, E12, E15 written and smoke-tested; 49 outside facts verified and registered; runs need the GPU / people

## M8 AMD and reliability (P0 for E13/E14)
- [~] harnesses for E2, E3, E13, E14, E8, E9, E10, E11 written and smoke-tested; proof API written; runs need the GPU

## M9 Judge package and submission (P0)
- [ ] README, JUDGES.md, deck PDF, demo video, cover, `docs/lablab.md`; `make submission-check` green; consistency pass; uptime check; competition re-check; release tag `act3-submission`

## M10 Extras (P2)
- [x] DAPT export (best effort, D-017)
- [~] diarization: worker and stage done; runs once the gated model is accepted
- [x] AccessCast Studio (local "try your own clip": upload, every stage live, then review; e2e with axe-core)
- [ ] detail levels in the player, YouDescribe second test set, more languages
