# Pre-registration (written before any test-set run)

This file is committed before the first run on the test set. It fixes the hypotheses, the metrics, the thresholds, and which sentence becomes the headline under each outcome, so we cannot pick the story after seeing the numbers. Changes after the first test run are allowed only as dated addenda at the bottom, and never change what was registered above them.

## Data
- **Test set:** the 10 W3C WAI "Web Accessibility Perspectives" videos, whole, with W3C's human captions and description tracks (`eval/datasets/manifests/w3c_wai.json`, SHA-256 per file). **Never used for tuning:** ASR choice, ladder steps, thresholds, prompts, lexicons and confidence weights are all decided on the dev set. We say "never used for tuning", not "never seen", because Gemma may have seen these public videos in pretraining. Any memorisation helps every arm equally, since E1 compares arms on the same videos.
- **Dev set:** `eval/datasets/manifests/dev_clips.json` plus our synthetic clips.
- **Freeze:** `make freeze-prompts` tags `test-freeze-<n>` and hashes every prompt, `constants.py`, `confidence.py` and the lexicons. Test runs refuse to start if any of them changed. Every test run is appended to `evidence/test_runs.jsonl`.

## E1 (headline)
**Hypothesis:** Gemma 4 writing from the same plan with no checks puts some description lines on top of dialogue or past the end of their pause. AccessCast's checks plus Gemma repair raise the number of lines that fit, at the same coverage, measured independently of the checks.

**Arms:** A (Gemma 4, same plan, no checks) → B (+ checks, failures go to a person) → C (+ Gemma repair, ≤ 3). All three arms share the attempt-0 draft for each seed. 3 seeds with distinct run labels.

**Primary metric:** lines that fit, pooled over 10 videos × 3 seeds, out of the planned standard lines L. A line fits if its rendered span (measured from the rendered description stem) overlaps no W3C human caption cue by more than 50 ms and ends before the next cue starts. The script (`eval/measure_overlap.py`) imports no verifier code.

**Secondary metrics:**
- the same measure against an energy-detector speech reference (reported separately)
- lines published and lines sent to a person, per arm
- coverage: W3C human description positions with one of our lines within ±3 s
- blind human labels for invented names, unsupported claims and restated dialogue (the labeller does not know the arm)
- first-pass k of L, and after-repair m of L

**Interval:** 95% bootstrap interval for (C − A) / L, resampling videos (10,000 resamples). With 10 videos we say "on L lines from 10 videos", never "significant".

**Coverage guard:** if C's coverage is more than 10 points below A's, the headline must say so in the same sentence.

**Which sentence becomes the headline:**
1. If C − A > 0 and the interval excludes 0, and the coverage guard holds: "On 10 W3C accessibility videos never used for tuning, AccessCast's timing checks and Gemma repair raised description lines that fit the pauses in dialogue from `a` of `L` (Gemma 4 with the same plan and no checks) to `b` of `L`."
2. If C − A > 0 but the interval includes 0: the same sentence, followed by "(the 95% interval includes no change)".
3. If C − A > 0 but the coverage guard fails: the same sentence, followed by ", while covering `x`% of the human description positions against `y`% without checks".
4. If C − A ≤ 0 (Gemma alone already fits as well): E1 is reported as a negative result in "What didn't work", with its numbers. The headline then moves to the first of these that has a clean measured result, in this order: E12 (person-minutes per finished minute, reviewing vs writing from scratch), E6 (questions answered from dialogue + our description vs dialogue only), E3 (smaller Gemma with checks vs Gemma 31B without).

The ProteinLoop framing is used in the README in every case: "`a` of `L` lines fitted on Gemma's first try; with checks and repair, `b`; the other `L − b` went to a person." We never headline "0 overlaps published", because that is true by construction once checks block bad lines.

## E3 (bigger model)
**Hypothesis:** a smaller Gemma 4 (26B-A4B or E4B) with AccessCast's checks fits more lines than Gemma 4 31B with no checks. Metric: E1's measure. A model is chosen for deployment on the dev set. The test set is run once after the freeze, and the result is reported as "a deployment decision, not a universal ranking".

## E4 (translation)
Gemma 4 31B against the strongest available AI4Bharat model (Hindi) and Opus-MT en-it (Italian), on FLORES+ devtest. Metrics: COMET (wmt22-comet-da) and chrF. If a baseline beats Gemma for a language, we report it in "What didn't work" and say what we did about it.

## E5 (easy-read)
Led by a blind human rating of 30 cues per arm ("easier to read?", "same meaning?"), with arms hidden from the rater. Automatic metrics are secondary and overlap with our own rules; we say so.

## E6 (usefulness, LLM proxy)
Multiple-choice questions written from W3C's human description **before** any AccessCast output on W3C exists. A non-Gemma answerer reads dialogue only / dialogue + AccessCast / dialogue + human description. Always labelled "LLM proxy, not blind viewers".

## E7 (closeness to human description)
CIDEr, BERTScore, an LLM-AD-eval score from a non-Gemma judge (1–5), and timing agreement with human cue positions. Baselines: a naive per-gap captioner (Gemma describes the middle frame of each gap), and Gemma alone.

## E12 (person-time)
Crossed design on two dev minutes: person 1 reviews minute 1 and writes minute 2 from scratch; person 2 does the opposite. Metric: minutes of work per finished minute. Published estimates (≈20–30 min per finished minute) are shown separately and labelled.

## Performance and reliability (E2, E8–E11, E13–E15)
- **E2:** a ladder step is adopted only if it gains ≥ 5% on the dev set with the quality guard held.
- **E13:** users per GPU, defined before measuring as the largest number of simultaneous jobs where every job finishes within its video's length.
- **E11:** each attack case runs K = 20 times at the production temperature and 20 times at temperature 1.0 (labelled stress), each with its own seed. The case shown live is chosen from the measured failure rates. If Gemma never fails a case, we say so.

## Addenda
_(none yet)_
