# Writing the E6 questions

E6 asks: does our audio description help someone follow the video? To test it, a computer model that is not Gemma answers questions about each video. It reads only a written record of the video. It gets the speech alone, or the speech plus AccessCast's description, or the speech plus W3C's own human description. We count how many questions it gets right in each case.

This is an **LLM proxy, not a test with blind viewers**. Every result says so.

The questions only mean something if you write them **before AccessCast has made anything for these videos**. The script checks this. It refuses to run if a question file's `written_at` time is later than the first AccessCast run on the test set.

## What you need

- The 10 W3C "Web Accessibility Perspectives" videos: https://www.w3.org/WAI/perspective-videos/
- For each video, W3C's "Text Transcript with Description of Visuals" on its page, or the description track `<video-id>_desc.en.vtt` (run `python -m eval.datasets.fetch_w3c_wai` to fetch the tracks into `data/w3c/`).

Do not look at anything AccessCast has made for these videos. If you are unsure whether something was made by AccessCast, do not open it.

## What to write

For each video, write **5 multiple-choice questions** about things a viewer can only know by **seeing** the video, as told by W3C's human description. Good questions:

- ask about something visible: who is on screen, where they are, what they do, what is shown on a screen or sign.
- **cannot be answered from the speech alone.** Read the speech too. If someone says the answer out loud, pick another question.
- have **one clearly right answer** and **three wrong answers that sound possible** (same kind of thing, similar length).
- use plain words and one idea each.

Avoid:

- questions about tiny details the description does not state.
- "all of the above" or "none of the above".
- copying long passages of W3C's text. Put the question in your own words.

Mix up where the right answer goes (0, 1, 2 or 3), so it is not always in the same place.

## The file

Copy `template.json` to `eval/questions/<video-id>.json`, for example `eval/questions/perspectives_keyboard.json`. The video ids are listed in `eval/datasets/fetch_w3c_wai.py`.

Fill in:

- `video_id`: the same id as the file name.
- `written_by`: your name.
- `written_at`: the time you **finished** writing, with your time zone, for example `2026-10-17T09:30:00+05:30`. A time without a zone is refused.
- `questions`: a list. Each question has `q` (the question), `options` (exactly 4 answers) and `answer_index` (the number of the right answer: 0 for the first option, 1 for the second, 2 for the third, 3 for the fourth).

Then commit the files **before** anyone runs AccessCast on the test set. The commit time is a second record that the questions came first.

## Check your file

```
uv run python -c "import json,sys; from eval.e06_questions import validate_questions as v; d=json.load(open(sys.argv[1])); print(v(d, d.get('video_id')) or 'ok')" eval/questions/<video-id>.json
```

It prints `ok`, or a list of problems to fix.
