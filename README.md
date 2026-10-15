<pending: e1.headline> <!-- line 1 is the E1 headline, filled only from evidence/public-claims.json -->

Live demo: <pending: site.url> · [3-minute judge guide](JUDGES.md) · Demo video: <pending: video.url> · Deck (PDF): <pending: deck.url>

# AccessCast: one video, five ways to watch

AccessCast takes one video and makes a version for each viewer. Gemma 4 on an AMD Instinct MI300X does the seeing, listening, writing and translating. Code checks every line it writes. Gemma repairs what fails. A person approves what the viewer hears.

> **Status:** under construction for AMD Developer Hackathon ACT III. Sections marked `<pending: …>` are waiting for an experiment to run. We never type a number by hand; every number comes from a file in [`evidence/`](evidence/) through [`evidence/public-claims.json`](evidence/public-claims.json).

## What it does

| Who is watching | What they get |
|---|---|
| **"I can't see the screen"** | Spoken description placed in the pauses between dialogue. If the pauses are too short, the video can hold on a still frame while the description plays (extended description). |
| **"I can't hear"** | Captions for deaf and hard-of-hearing viewers: every word, speaker changes and sounds like [door slams]. |
| **"Simpler words, please"** | Easy-read captions: short sentences, one idea each, and a mode that waits for you to finish reading. |
| **"हिन्दी"** | Hindi subtitles, a Hindi voice-over and Hindi description. |
| **"Italiano"** | Italian subtitles, an Italian voice-over and Italian description. |

All five come from one analysis of the video, so they never disagree with each other.

## Try it in 60 seconds (no GPU)

```bash
make setup          # uv sync + assets
make demo-fixture   # whole pipeline in fake mode on a 20-second fixture, then serves the player
# open http://127.0.0.1:8080/?audience=judge
```

Fake mode uses canned model outputs and says so on screen. It shows the pipeline, the checks and the player. It is not evidence of model quality.

## Results

<pending: results.tables> — every table states its data split ("test set, never used for tuning" or "dev set") and links its evidence file.

## How quality is controlled

1. **Gemma proposes.** It lists what is visible first, then writes only from that list.
2. **Code decides.** Every line is checked against the real audio timeline (pauses measured from aligned words), a word budget, and rules for names, claims, sounds and restated dialogue. See [`docs/rules.md`](docs/rules.md).
3. **Gemma repairs.** A line that fails goes back to Gemma with the failed checks, up to three times.
4. **A person approves.** Nothing reaches a viewer until a reviewer approves it. The render step refuses to run while any line is still waiting.

## What runs on AMD

<pending: amd.section>

## What didn't work

<pending: negative.results>

## Honest scope

| Claim | Real | Simplified or not done |
|---|---|---|
| Description fits pauses | Measured by a script that does not use our checks | Caption timings are a stand-in for speech |
| Review tool for blind reviewers | Designed for it; keyboard-only; automatic accessibility checks | Not yet tested by a blind reviewer |
| No sign language, no live streams, no lip-sync dubbing | — | Out of scope |

## Prior work and how we differ

See [PLAN.md §21.1](PLAN.md). In short: AudioSight and ViddyScribe also write AI description. AccessCast fits description inside the pauses, checks every line in code against the audio timeline, uses extended description only when it is needed, makes five audience versions from one pass, and requires a person to approve before anything is published.

## Reproduce

See [JUDGES.md](JUDGES.md#reproduce) and [`deploy/`](deploy/).

## Licences and credits

Our code is MIT ([LICENSE](LICENSE)). Reused code and ideas: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Models, voices, datasets and clips: [MODEL_LICENSES.md](MODEL_LICENSES.md).
