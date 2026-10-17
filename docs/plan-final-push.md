# Final push plan (18 Oct 2026, deadline 15:30 IST)

Inputs: gap analysis of the reference repos and the ACT III brief (subagent report, 18 Oct), the user's direction
(more languages, more metrics and charts, more tests, more AMD, a stronger video and site), and CLAUDE.md's rules.
Each phase ends with its checks green: `make check`, `make claims-check`, E16, and a look at the live site.

## Phase A — correctness and honesty (first: wrong claims cost more than missing features)
- A1. E11 runs on our own attack clips (split `dev`). README "What the checks caught", deck slide 8 and lablab text
  must not put it under "10 W3C videos never used for tuning".
- A2. E15: say the raw Whisper median (32 ms) is better than the aligned median (54 ms); alignment fixes the tail
  (p95 480 → 339 ms). Register the raw median as a claim.
- A3. Home page Results block: lead with E5 (negations) and E11 (attack), then AMD usage and tests; E1 belongs in
  "What didn't work", not first on the page.
- A4. JUDGES.md: fix dead pointers (`evidence/gallery/`, the README section name).
- A5. Architecture diagram: label where each part runs (AMD Token Factory, our computer, browser, a person).

## Phase B — Spanish and French, end to end
- B1. Core: constants, voices + calibration, checks' word tables, pipeline loops, gate, render, Studio, try API,
  prompt, fixture canned text. Unit tests for the number, name and untranslated checks in both languages. (done)
- B2. Site: player version names and picker, five-ways steps, Try box cards; e2e tests updated; E16 re-run.
- B3. Site drafts: run the caption + voice-over stages for es/fr on the Sintel and NASA projects, re-render, deploy.
- B4. E4 for es/fr: FLORES+ devtest, Gemma 4 31B (Token Factory) against Opus-MT en-es / en-fr, COMET + chrF++
  with paired bootstrap intervals; evidence + claims; README/deck lines. Until it runs, no number is stated.
- B5. Wording: "five ways" becomes "five kinds of viewer, four languages" where it would now be wrong.

## Phase C — charts from evidence (no hand-typed numbers)
- C1. `scripts/make_charts.py` → `docs/charts/*.png`: E5 negation bars, E11 attack funnel, E4 differences with 95%
  intervals (incl. the Hindi chrF++ loss), E14 Gemma tokens per finished minute by version, AMD requests by day,
  E13 latency against concurrency. Every value read from `evidence/`; each chart names its split and source file.
- C2. A timeline figure of one real clip: speech, pauses, placed lines, extended holds.
- C3. Charts in README, deck, and the site (Results page).

## Phase D — more measurement on AMD
- D1. E4 es/fr (B4).
- D2. E17 model ladder (pre-registered here): the same 8 attack cases on other Token Factory models
  (Qwen3.8-27B, MiniCPM-V-4.7-35B-A3B, GLM-5.3-Flash) with the same checks; reports how often each model takes the
  bait and how many answers reached a viewer. Baseline: Gemma 4 31B's E11 run 2. One change: the model.

## Phase E — tests and robustness
- E1. e2e: es/fr in the player and Try box; unit tests for each new script's pure parts.
- E2. Coverage report (pytest-cov) and a test-count badge from the real numbers.

## Phase F — presentation
- F1. README: badge row, charts under each result, refusal gallery (a render refused next to a published one).
- F2. Deck: charts, one big number per slide, screenshots. New cover from a real frame.
- F3. Video: mention four languages, show a chart scene, keep under ~5:30.
- F4. GitHub repo description, homepage and topics.

## Phase H — iteration 2 (01:00–06:00 IST, 18 Oct): finish what is measured, then show it
Status of the phases above: A, B1–B3, C, E1, F1, F2, F4 done; B4/D1 (E4 es/fr/pt) and D2 (E17) run now.
- H1. E17 on Token Factory (Qwen3.8-27B, MiniCPM-V-4.7-35B-A3B; k = 5 per setting). An empty answer is counted as
  "no output", never as "took the bait". Claims, chart, README row, Results card, deck "It holds up".
- H2. E18 per-language check results on both site drafts after the es/fr/pt stages; claims, chart, README row,
  Results card.
- H3. E4 es/fr/pt (chunk 12 = the translation batch cap). Direction words ("higher", "lower", "no clearly
  different") come from each 95% interval in code, never typed. Results card and the video's chart scene follow
  the result.
- H4. AMD usage refreshed after H1–H3: Gemma counted apart from E17's models, plus an all-model total.
- H5. Tests as evidence (`scripts/test_stats.py` → evidence/tests.json: 188 of 188, line coverage), a Results card,
  a README row; the Results e2e test now fails on any broken chart or any number still "Measuring". Keys 1–8 pick
  every viewer on the Watch page (tested).
- H6. Site: export both drafts with every language, deploy, check Try and Results live.
- H7. Video: es/fr/pt voice clips from the NASA render, home page re-recorded, wording ("every version"), rebuilt;
  target about 5:00–5:30 with no silence over 1 s and no hard cut.
- H8. Deck and lablab text refreshed from claims; `make check`, E16, claims-check, submission-check.

- H9. Review app: the list of lines is one Tab stop with arrow keys, Home and End (it was one Tab stop per line;
  with five languages a keyboard user passed many lines before the header). Tested.

Status at 03:30 IST: H1–H9 done. E17 (0 reached a viewer for every model; the others seldom took the bait),
E18, E4 es/fr/pt (Gemma higher on COMET in all five languages; chrF++ lower for Hindi, French, Portuguese),
tests 190/190, E16 27/27 and 9/9, live check 6 of 6 versions, video 5:25 with no silence, deck and site deployed.
Left for the person: upload the video and deck, send their links and the team names.

## Phase G — close
- `make submission-check`, final claims-check, tag `act3-submission`, hand the user the upload checklist.
