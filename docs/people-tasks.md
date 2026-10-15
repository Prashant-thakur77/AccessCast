# Tasks only a person can do

Each task turns a placeholder into a measured number, or makes a claim true. Times are rough guesses for planning, not measurements. Do them in this order; the first one has a deadline.

## 1. Write the E6 questions (today, before any test run on W3C videos)
Why a person: the questions must come from W3C's own description, written before any AccessCast output on those videos exists, so they can't be tuned to our output.

What to do: read `eval/questions/README.md` and follow it. For each of the 10 W3C videos, open its page (links in `eval/datasets/manifests/w3c_wai.json`), read the "Text Transcript with Description of Visuals", and write about 5 multiple-choice questions that can only be answered from what is shown, not what is said. Save each as `eval/questions/<video_id>.json` with `written_by` and `written_at`. About 1 hour.

## 2. Review the dev videos (after the GPU run)
Why a person: nothing is published until a person approves every description and easy-read line.

What to do: run `make review`, open http://127.0.0.1:8081, type your name in the reviewer box, and work through the queue with the keyboard. Press `?` to see the keys. Approve lines that are right, fix and approve lines that are close, and reject lines that are wrong. About 10–20 minutes per minute of video.

## 3. E12, review vs writing from scratch (after the GPU run, two people)
Why people: this measures how much person-time AccessCast saves.

What to do: use two one-minute dev clips, M1 and M2. Person 1 reviews AccessCast's lines for M1, then writes description for M2 from scratch (`accesscast scratch-copy --project <M2>` makes an empty copy). Person 2 does the opposite. The review app times active work by itself. About 30–45 minutes each.

## 4. E1 blind labels (after the test run)
Why a person: invented names, unsupported claims and restated dialogue need a human judgement, made without knowing which arm wrote the line.

What to do: open `data/labels/e01_test_blind_sheet.csv` (this file is not in git, because it contains W3C-derived text) and mark each line 0 or 1 in the three columns. About 1 hour.

## 5. Native Hindi and Italian checks
Why a person: we can't judge the language ourselves.

What to do: in the review app, filter by Hindi, then by Italian, and rate about 10 lines each for accuracy and natural speech. If both voices are available, also say which one sounds better (Kokoro or Chatterbox). About 20 minutes per language.

## 6. A blind or low-vision tester, if possible
Why a person: until someone who uses a screen reader tries the player and the review app, we only say "designed for blind reviewers". If you can arrange it, ask them to try both with their own screen reader, and quote them only with their written consent.

## 7. Someone outside the team watches the draft demo video
Why a person: judges have docked past teams for pitches non-technical people couldn't follow. List every sentence they didn't follow; we fix all of them.

## 8. Things only your accounts can do
- `.env`: `AMD_TF_API_KEY`, `AMD_TF_BASE_URL`, `HF_TOKEN` (never paste keys into chat).
- The MI300X droplet, or an AMD Developer Cloud API token so it can be managed automatically.
- Hugging Face gated licences: `google/gemma-4-31B-it`, `google/gemma-4-E4B-it` (if asked), `openlanguagedata/flores_plus`, `ai4bharat/indictrans2-en-indic-1B`, `pyannote/speaker-diarization-community-1`, `ai4bharat/indic-parler-tts`.
- lablab.ai: team registration and the final submit (the text is ready in `docs/lablab.md`).
- Send the two messages in `docs/outreach.md` (Discord questions, W3C email).
