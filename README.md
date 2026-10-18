<p align="center"><img src="docs/cover.png" alt="AccessCast: one video, made for every viewer. A real frame from the Sintel trailer with the description line Gemma 4 31B wrote for it, surrounded by the eight viewer choices." width="100%"></p>

<h1 align="center">AccessCast: one video, made for every viewer</h1>

<p align="center"><b>Blind, deaf and slow-reading viewers, and people who speak Hindi, Italian, Spanish, French or Portuguese, each get their own version of the same video. Gemma 4 on AMD writes it, code checks every line, and a person approves it before anyone hears it.</b></p>

<p align="center">
<a href="https://accesscast.vercel.app/?audience=judge"><b>▶ Live site</b></a> ·
Demo video: <pending: video.url> ·
Deck: <pending: deck.url> ·
<a href="JUDGES.md">3-minute judge guide</a> ·
<a href="https://accesscast.vercel.app/results.html">Results page</a> ·
<a href="https://accesscast.vercel.app/proof.html">Run our attack live</a> ·
<a href="https://accesscast.vercel.app/proof.html#desc-h">Describe your own picture</a>
</p>

<p align="center">
<a href="https://github.com/Prashant-thakur77/AccessCast/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Prashant-thakur77/AccessCast/actions/workflows/ci.yml/badge.svg"></a>
<a href="https://accesscast.vercel.app/?audience=judge"><img alt="Live site" src="https://img.shields.io/badge/live_site-accesscast.vercel.app-E4402A"></a>
<a href="evidence/tests.json"><img alt="Unit tests passing (read from evidence/tests.json)" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPrashant-thakur77%2FAccessCast%2Fmain%2Fevidence%2Ftests.json&query=%24.summary.tests_passed&label=unit%20tests%20passing&color=1E7A4C"></a>
<a href="evidence/amd_usage.json"><img alt="Gemma requests answered by AMD Token Factory (read from evidence/amd_usage.json)" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FPrashant-thakur77%2FAccessCast%2Fmain%2Fevidence%2Famd_usage.json&query=%24.summary.requests_answered&label=Gemma%20requests%20on%20AMD&color=ED1C24"></a>
<a href="evidence/public-claims.json"><img alt="Every number checked by make claims-check" src="https://img.shields.io/badge/every_number-claims--checked-141B34"></a>
<a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-blue"></a>
</p>

<p align="center">
<img alt="Gemma 4 31B" src="https://img.shields.io/badge/Gemma_4-31B-4285F4?logo=google&logoColor=white">
<img alt="AMD Token Factory" src="https://img.shields.io/badge/AMD-Token_Factory-ED1C24?logo=amd&logoColor=white">
<img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-review_app-009688?logo=fastapi&logoColor=white">
<img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-workers-EE4C2C?logo=pytorch&logoColor=white">
<img alt="Whisper" src="https://img.shields.io/badge/Whisper-large--v3--turbo-412991?logo=openai&logoColor=white">
<img alt="Hugging Face" src="https://img.shields.io/badge/Hugging_Face-models-FFD21E?logo=huggingface&logoColor=black">
<img alt="Kokoro TTS" src="https://img.shields.io/badge/Kokoro-82M_voices-5A4FCF">
<img alt="spaCy" src="https://img.shields.io/badge/spaCy-rule_NLP-09A3D5?logo=spacy&logoColor=white">
<img alt="FFmpeg" src="https://img.shields.io/badge/FFmpeg-render-007808?logo=ffmpeg&logoColor=white">
<img alt="Playwright and axe-core" src="https://img.shields.io/badge/Playwright_+_axe--core-a11y_tests-2EAD33">
<img alt="Vercel" src="https://img.shields.io/badge/Vercel-site_+_live_API-000000?logo=vercel&logoColor=white">
<img alt="WebVTT and DAPT" src="https://img.shields.io/badge/WebVTT_+_W3C_DAPT-tracks-555555">
</p>

> Built for **AMD Developer Hackathon ACT III**, track **"Create a New Kind of Experience"**, with Gemma 4 on AMD. Every number on this page comes from a file in [`evidence/`](evidence/) written by a script in this repo, or from a cited source, through [`evidence/public-claims.json`](evidence/public-claims.json). `make claims-check` runs in CI and fails if any number here is not registered. Each result names its data split and its baseline.

## Contents

[At a glance](#at-a-glance) · [The problem](#the-problem) · [What each viewer gets](#what-each-viewer-gets) · [See it](#see-it) · [How it works](#how-it-works) · [Every stage](#every-stage-of-the-pipeline) · [Gemma 4 on AMD](#gemma-4-on-amd) · [Quality control](#how-quality-is-controlled) · [Results](#results) · [All experiments](#every-experiment) · [Tests and reliability](#tests-and-reliability) · [Comparison](#how-it-compares) · [Who pays](#who-pays) · [What didn't work](#what-didnt-work) · [Honest scope](#honest-scope) · [Reproduce](#reproduce) · [Repository map](#repository-map) · [Technology](#technology-and-licences) · [Team](#team)

## At a glance

| What | Result | Compared with | Data | Evidence |
|---|---|---|---|---|
| Meaning kept in easy-read captions | AccessCast published every "not", "never" and "no" in 114 of 114 captions | Gemma 4 alone: 105 of 114 | 10 W3C videos never used for tuning | [`e05_easyread.json`](evidence/e05_easyread.json) |
| Attacks on our own system | Attack answers that reached a viewer: 0 across 8 cases | Gemma alone dropped a time limit in 20 of 20 tries | our attack clips (dev) | [`e11_adversarial.json`](evidence/e11_adversarial.json) |
| Same attacks, other models writing | Reached a viewer: 0 (Qwen3.8-27B) and 0 (MiniCPM-V-4.7-35B-A3B) | Gemma 4 31B: 0 | our attack clips (dev) | [`e17_model_ladder.json`](evidence/e17_model_ladder.json) |
| Translation quality (COMET) | Gemma 4 31B higher in all five languages | IndicTrans2 (Hindi), Opus-MT (Italian, Spanish, French, Portuguese) | FLORES+ devtest, 1012 sentences each | [`e04_translation.json`](evidence/e04_translation.json), [`e04_translation_es_fr_pt.json`](evidence/e04_translation_es_fr_pt.json) |
| Translated lines passing every check on their own | Hindi 74 of 81 · Italian 74 of 81 · Spanish 73 of 81 · French 70 of 81 · Portuguese 76 of 81 | the rest wait for a person | our two site drafts (dev) | [`e18_language_checks.json`](evidence/e18_language_checks.json) |
| Model work on AMD | 3,825 Gemma 4 31B requests, 3.6 million tokens, 28 videos | every answer checked against the served model | all our runs | [`amd_usage.json`](evidence/amd_usage.json) |
| Cost of the model work | 41,818 Gemma tokens per finished minute, about $0.0053 at a published list price (an estimate) | AI description with a human spot check: $4.25 a minute (3Play Media list price) | dev videos | [`e14_cost.json`](evidence/e14_cost.json) |
| Tests | 220 of 220 unit and golden tests, running 78% of our core code; browser tests with axe-core: player 32 of 32, review app 9 of 9 | — | — | [`tests.json`](evidence/tests.json), [`e16_ui_a11y.json`](evidence/e16_ui_a11y.json) |
| Rules that check every line | 53 rules, each with its source standard | — | — | [`docs/rules.md`](docs/rules.md) |

## The problem

- **Most video says nothing to people who can't see it.** 43.3 million people are blind and 295 million more have moderate or severe vision loss (GBD 2019). The largest free archive of described video, YouDescribe, holds about 310 hours of it, while YouTube alone received more than 500 hours of new video every minute (2019).
- **Many people can't hear it.** 430 million people need rehabilitation for disabling hearing loss (WHO). Captions also serve hearing viewers: about 80% of people who use captions are not deaf or hard of hearing (Ofcom).
- **Many people can't read it fast enough.** 26% of adults across OECD countries read at or below the lowest literacy level (OECD Survey of Adult Skills 2023).
- **Doing it by hand is slow and costly.** A describer needs about 20 hours to script and voice one hour of TV (Media Access Australia). List prices for description run from $15 to $75 a minute (3Play Media).
- **The law now asks for it.** The European Accessibility Act has applied since 28 June 2025; India's OTT accessibility guidelines date from 6 February 2026; the US ADA Title II web rule applies to large public bodies from 26 April 2027.

## What each viewer gets

One player, eight choices, the same video. Every version comes from one analysis of the video (every word with its timing, the pauses, shots, scenes, sounds, on-screen text and what is visible), so the versions never disagree. Choices combine: a blind Hindi speaker gets the Hindi voice-over with Hindi description.

| The viewer says | What they get | Made by |
|---|---|---|
| "I can't see the screen" | Spoken description placed in the pauses between dialogue, with the original sound dipped underneath. When the pauses are too short, an **extended** version holds a still frame while the description plays. A text track for screen readers and braille displays. | Gemma 4 31B looks and writes; code fits each line to a measured pause; Kokoro voices it |
| "I can't hear" | Captions for deaf and hard-of-hearing viewers: every word, timed to the speech, plus sounds between words such as [music] | Whisper and forced alignment; code segments to caption standards |
| "Simpler words, please" | Easy-read captions: short sentences, one idea each, numbers and "not" kept. A "Give me time to read" mode pauses the video until you are ready | Gemma 4 31B rewrites; code checks meaning and pace |
| "हिन्दी" · "Italiano" | Subtitles, a voice-over in the original speech slots, and their own description | Gemma 4 31B translates; code checks numbers, names and language; Kokoro voices |
| "Español" · "Français" · "Português" | Subtitles and a voice-over in the original speech slots | the same |
| Anyone, in any version | **Read it as text**: everything the version says and describes, in time order, for a screen reader or braille display; downloads for the video, every track and the text | the version's own tracks |

## See it

| | |
|---|---|
| ![The AccessCast home page: One video. Every viewer.](docs/media/home.png) **The site.** [accesscast.vercel.app](https://accesscast.vercel.app) | ![The viewer picker: I can't see the screen, I can't hear, simpler words, Hindi, Italian, Spanish, French, Portuguese](docs/media/picker.png) **Who's watching?** Eight choices on the same video. |
| ![The player for a blind viewer, with the description text shown under the video: A red-haired person stands in stone ruins as a small winged creature flies toward them.](docs/media/watch.png) **The player.** Description voiced in the pause, and shown as text for screen readers (Sintel trailer, machine draft). | ![One description line in the decisions drawer: the evidence frames Gemma saw, the pause it had to fit, the word and time budget, the draft, the checks and the confidence computed by code](docs/media/drawer.png) **What the models decided.** Every line: the frames Gemma saw, the pause, the budget, the draft, the checks, the repairs. |
| ![How it works, steps 5 and 6: code stopped the draft "A man in a NASA polo shirt speaks to the camera" with rule AD011, and Gemma's repair "looks at the camera" passed every check](docs/media/how.png) **Code decides.** A real line from NASA's *Life in the Universe*: rule AD011 stopped "speaks to the camera" (a blind viewer already hears that), and Gemma's repair passed. | ![The Try box on the live site: one sentence turned into easy-read, Hindi, Italian, Spanish, French and Portuguese, with the Italian, French and Portuguese lines stopped by the number check and repaired](docs/media/try.png) **Try it live.** One sentence, every language, made by Gemma on AMD and checked. In this run (18 Oct 2026) Gemma wrote "17:00" or "17h" for "5 pm" in three languages; the number check is strict on purpose, stopped each one, and the repair passed. |
| ![Describe a picture on the live site: a frame from the Sintel trailer, the three things Gemma saw, and the description line, which passed every check](docs/media/describe.png) **Describe a picture, live.** Gemma on AMD lists what it sees in your picture and writes one line; our description rules check it (18 Oct 2026 run, Sintel sample). | ![The Results page: every chart with its data split and evidence file](docs/media/results.png) **Results page.** Every chart names its data and its evidence file. |
| ![Read it as text: the NASA draft for a blind viewer as one time-ordered list of what is said and what is described, with downloads for the video, each track and the text](docs/media/textversion.png) **Read it as text.** The version being played as one list, in time order, from its own tracks: for a screen reader or a braille display, with downloads. | ![The cost estimator on the Results page: our estimated Gemma cost next to published list prices for description](docs/media/calc.png) **What would your videos cost?** Minutes of video times our measured Gemma cost (an estimate) and published list prices; review time comes on top. |
| ![AccessCast Studio after a run: every step done in plain words](docs/media/studio.png) **Studio.** Add a video and watch every stage run, in plain words, keyboard only. | ![The Every viewer page plays the same clip for one viewer after another; the page changes colour for each viewer.](docs/media/five-ways.gif) **Every viewer.** The same clip, one viewer after another. |

## How it works

**The model proposes, code decides.** Gemma 4 31B, served by AMD Token Factory, does every seeing, writing, translating and repairing job. It never decides timing and never judges its own work: code checks every line against the real audio timeline and 53 written rules, sends failures back to Gemma with the exact rule that failed, and sends anything still failing to a person. Nothing is published until a person approves it, and the server refuses to render while any line waits.

![How AccessCast works: the video is analysed on our computer; Gemma 4 31B on AMD Token Factory looks and writes; code plans and checks every line and sends failures back; a person approves; voices and rendering run on our computer; a render gate refuses while any line waits; viewers pick their version](docs/architecture.png)

```mermaid
flowchart LR
  V[Video] --> L[Listen<br/>Whisper + forced alignment]
  L --> A[Analyse<br/>pauses, shots, scenes, sounds]
  A --> E[Look<br/>Gemma 4 31B on AMD]
  E --> W[Write<br/>Gemma 4 31B on AMD]
  W --> C{Check every line<br/>code}
  C -- fails --> R[Repair<br/>Gemma, told which rule]
  R --> C
  C -- still fails --> P
  C -- passes --> P[A person approves<br/>review app]
  P --> G{Render gate<br/>server}
  G --> O[Versions for every viewer]
  A --> T[Captions, easy-read,<br/>subtitles, voice-over]
  T --> C
```

![One real clip, NASA's Life in the Universe: speech, the few pauses, the lines spoken in pauses, and the many lines read while the picture holds](docs/charts/timeline_nasa.png)

## Every stage of the pipeline

26 stages run for each video, each reading and writing files under `projects/<sha12>/`, content-addressed and re-runnable on its own. The Studio shows the same list, in the same words, while it runs.

| Stage | What happens | Runs on |
|---|---|---|
| Reading the video | Hash, probe, extract audio and frames | our computer (FFmpeg) |
| Listening for every word | Transcript with word timings, then forced alignment | our computer (Whisper large-v3-turbo, wav2vec2) |
| Telling the voices apart | Anonymous speaker labels for speaker-change marks | our computer (pyannote, switched on once its licence is accepted) |
| Finding the cuts | Shot boundaries | code |
| Grouping shots into scenes | Scenes for description | code |
| Second listen | Transcript cross-check | Gemma 4 E4B: not run, not offered on Token Factory |
| Labelling sounds | Sounds between the words for deaf viewers | our computer (AST classifier) |
| Finding the pauses | Gaps between dialogue, with a guard band measured in E15 | code (word timings + Silero VAD) |
| Looking at each scene | Gemma lists only what is visible, with fact ids | **Gemma 4 31B on AMD Token Factory** |
| Planning | Which pause each line goes in, with a word and time budget | code |
| Writing | One line per slot, only from the listed facts | **Gemma 4 31B on AMD Token Factory** |
| Checking and repairing | Every rule on every line; failures go back to Gemma with the rule, up to three times | code + **Gemma 4 31B on AMD** |
| Voicing | Description voice, measured against its pause | our computer (Kokoro) |
| Captions | Captions for deaf and hard-of-hearing viewers | code |
| Easy-read | Simpler captions, checked for meaning and pace | **Gemma 4 31B on AMD** + code |
| Subtitles | Hindi, Italian, Spanish, French, Portuguese | **Gemma 4 31B on AMD** + code |
| Voice-over | The same five languages, fitted to the original speech slots | **Gemma 4 31B on AMD** + Kokoro + code |
| Ready for review | Every line queued for a person, ordered by confidence computed in code | code |

After the stages: a person reviews in the keyboard-first review app; the server-side gate refuses to render while any line waits; rendering mixes and ducks the sound, checks loudness and sync, and writes WebVTT and W3C DAPT tracks plus a `report.json` audit; `make export-site` publishes the versions.

## Gemma 4 on AMD

Gemma 4 31B does every vision, writing, translation and repair job, all on **AMD Token Factory**: it looks at the frames of each scene and lists what is visible, writes the description from that list only, rewrites captions as easy-read, translates into five languages, and repairs any line that fails a check, told exactly which check failed. Every answer is checked against the model name the server reports (`--strict-provider`).

**Every Gemma call ran on AMD.** Counted from our own call logs (`scripts/amd_usage.py`): AMD Token Factory answered 3,825 Gemma 4 31B requests for us, 3,564,063 tokens in all, while working on 28 videos (32.8 minutes): 10 W3C test videos, 10 dev clips and our 8 attack clips. Every answer came from the same served model. With the two other Token Factory models we compared in E17, Token Factory answered 4,050 requests for us (3.7 million tokens). The live attack and Try box on our site add more calls, which these logs do not include.

| What we measured on AMD Token Factory | Value | Evidence |
|---|---|---|
| Gemma 4 31B requests answered, all our work | 3,825 | `amd_usage.json` |
| Tokens in those requests | 3,564,063 | `amd_usage.json` |
| Generated tokens per second seen by our client, best concurrency | 17 | `e13_serving_tokenfactory.json` |
| p95 latency of a description request at that concurrency | 13.9 s | `e13_serving_tokenfactory.json` |
| Gemma tokens per finished minute of video, the five versions we measured | 41,818 | `e14_cost.json` |
| Calls Token Factory never answered after every retry (each one failed closed) | 22 | `amd_usage.json` |
| Calls our circuit breaker then held back without sending (each one failed closed) | 2,621 | `amd_usage.json` |

![Gemma 4 31B requests answered by AMD Token Factory, by day, from our own call logs](docs/charts/amd_usage.png)

![Where the Gemma tokens of one finished minute go, by version](docs/charts/e14_tokens.png)

![Latency and tokens per second seen from our side at one and four requests at a time](docs/charts/e13_serving.png)

**Live on the site, on AMD, with the same checks.** Three things on the [proof page](https://accesscast.vercel.app/proof.html) call Gemma 4 31B on AMD Token Factory while you watch, and nothing typed or uploaded is stored: **Run the attack** (Gemma is baited to drop a time limit; our number check stops it), **Try your own caption** (easy-read and five languages, each line checked), and **Describe a picture** (Gemma lists what it sees in your picture, writes one description line for a silent pause, and our description rules check it, with repairs; [`docs/decisions.md`](docs/decisions.md) D-030). After every deploy, `scripts/live_check.py` runs all of them and fails on any crashed check ([`live_check.json`](evidence/live_check.json)).

These numbers are measured from our side of the connection, so they include the network and Token Factory's queue. Speed-test requests that failed are counted in the evidence file: 15 of 120, every one refused by the rate limit on our key, not a model error.

| Part | Where it ran |
|---|---|
| Gemma 4 31B: looking at frames, writing description, easy-read, Hindi, Italian, Spanish, French and Portuguese, every repair, scene judgments | AMD Token Factory (`Gemma-4-31B-IT`), every answer checked against the served model |
| Whisper, the wav2vec2 aligner, Silero VAD, the AST sound classifier, the Kokoro voices, the metric models | our own computer, not AMD hardware; the device is written in every worker response and evidence file |
| Gemma 4 E4B (listening) | not run: Token Factory does not offer it ([`docs/decisions.md`](docs/decisions.md) D-021, D-022) |

We did not get an MI300X droplet, so this page has no GPU-memory, users-per-GPU or GPU-dollar numbers; the scripts that measure them are in [`deploy/`](deploy/) and [`eval/`](eval/), ready for one.

## How quality is controlled

Gemma first lists what is visible in a scene (temperature 0), then writes description only from that list. Code then checks every line against [`docs/rules.md`](docs/rules.md), where each rule names the standard or prior work it comes from (DCMP, Netflix, Ofcom, Inclusion Europe, WCAG, ACB, and earlier hackathon entries).

| Family | Rules | What they catch (examples) |
|---|---|---|
| Description (AD) | 20 | the line overruns its pause or overlaps speech (AD001, AD004); a name nobody said or showed (AD009); motives or claims not in the picture (AD010); sounds a blind viewer already hears (AD011); words not grounded in the listed facts (AD012); obeying instructions written on a slide (AD018) |
| Easy-read (ER) | 10 | too fast to read (ER001); long sentences (ER002); a changed number (ER004); a lost "not" (ER005); a lost name (ER006) |
| Captions and subtitles (CC) | 11 | reading speed (CC001); line length and count (CC002, CC003); sync with the first word (CC005); untranslated or wrong-script lines (CC008); a number or name changed in translation (CC009); a glyph the font cannot draw (CC010) |
| Voice-over (VO) | 4 | the voice runs past its slot (VO001); untranslated (VO002); number or name changed (VO003) |
| Render (RN) | 8 | duration, loudness, sync, valid tracks, nothing unapproved rendered, no public render without a person's approval (RN001–RN008) |

A line that fails goes back to Gemma with the failed checks, up to three times; a line that still fails goes to a person and is never published by default. Confidence for each line is computed in code from measured signals (grounding, timing slack, ASR agreement, repairs used), never asked of the model, and it orders the review queue. The render is refused on the server while any line waits, and every render carries a `report.json` audit with `human_reviewed`, the reviewers and the review time.

## Results

![Easy-read captions that kept every negation, Gemma alone against AccessCast as published](docs/charts/e5_negations.png)

![Attack cases: tries, how often Gemma took the bait, and how many answers reached a viewer](docs/charts/e11_attacks.png)

<!-- results.more:start -->
- **Speech recognition (E15, dev set).** We chose Whisper large-v3-turbo: its English word error rate was 4.5% on 100 FLEURS clips, against 4.3% for the larger large-v3 (Hindi 32.4%, Italian 3.0%). After forced alignment, word boundaries were off by 54 ms at the median and 339 ms at the 95th percentile, on 224 word boundaries of our synthetic clips. Raw Whisper timestamps were closer at the median (32 ms) but worse in the tail (480 ms at the 95th percentile); the guard is set from the tail, so description keeps 340 ms clear of speech. Large-v3 could not produce word timings within our computer's memory, so it was not a candidate.
- **Translation (E4, FLORES+ devtest, 1012 sentences per language, not our videos).** Two scores: COMET, a model trained to match human quality ratings, and chrF++, which counts character and word overlap with one human translation. Italian: Gemma 4 31B scored higher than Opus-MT, a widely used open English–Italian model, on both: COMET 0.8898 against 0.8522 (difference +0.0376, 95% interval +0.0337 to +0.0417) and chrF++ 55.4 against 54.8 (+0.7, +0.1 to +1.3). Hindi was mixed: Gemma scored higher on COMET (0.8253 against 0.8157, +0.0095, +0.0063 to +0.0131), but IndicTrans2, a model built for Indian languages, scored higher on chrF++ (58.8 against 53.8; Gemma −5.0, −5.7 to −4.3). Gemma returned every sentence (0 missing in Hindi, 0 in Italian).

  ![Gemma minus the baseline for each language and score, with 95% intervals](docs/charts/e4_translation.png)
- **Easy-read (E5, 10 W3C videos never used for tuning).** Asked to simplify the captions, Gemma alone kept every "not", "never" and "no" in 105 of 114 cues; in the others the sentence lost its negation and so its meaning. The easy-read AccessCast published kept them in 114 of 114, and sent 7 of 121 cues to a person instead. Paced for slow reading (at most 130 words a minute): 106 of 114 published cues, against 57 of 121 original captions. These counts use a negation counter close to our own check, so a blind rating by people leads this experiment; it is still to come.
- **More languages (E4, same FLORES+ devtest, Gemma 4 31B against Opus-MT).** Spanish: Gemma higher on COMET (Gemma 0.8694, Opus-MT 0.8503; difference +0.0192, 95% interval +0.0164 to +0.0222), no clear difference on chrF++ (Gemma 53.0, Opus-MT 52.9; difference +0.1, 95% interval −0.3 to +0.6); French: Gemma higher on COMET (Gemma 0.8811, Opus-MT 0.8617; difference +0.0195, 95% interval +0.0151 to +0.0233), Opus-MT higher on chrF++ (Gemma 64.1, Opus-MT 68.0; difference −3.8, 95% interval −4.7 to −3.0); Portuguese: Gemma higher on COMET (Gemma 0.9021, Opus-MT 0.8912; difference +0.0109, 95% interval +0.0085 to +0.0135), Opus-MT higher on chrF++ (Gemma 67.4, Opus-MT 70.0; difference −2.6, 95% interval −3.2 to −1.8). Sentences Gemma never returned: 0 Spanish, 0 French, 0 Portuguese. Evidence: evidence/e04_translation_es_fr_pt.json.
- **Every language through the same checks (E18, our two site drafts, dev).** Translated subtitle and voice-over lines that passed every check on their own: Hindi 74 of 81, Italian 74 of 81, Spanish 73 of 81, French 70 of 81, Portuguese 76 of 81. The rest went to a person, not to viewers. The check that held the most lines was CC001 (reading speed). Evidence: evidence/e18_language_checks.json.

  ![Lines per language that passed every check, and lines held for a person](docs/charts/e18_languages.png)
- **Other models on AMD Token Factory (E17, our own attack clips, dev).** The same attacks and the same checks, with a different model writing: Gemma 4 31B took the bait in 40 of 400 lines (no usable first draft for 0; reached a viewer: 0); Qwen3.8-27B took the bait in 0 of 100 lines (no usable first draft for 63; reached a viewer: 0); MiniCPM-V-4.7-35B-A3B took the bait in 1 of 100 lines (no usable first draft for 0; reached a viewer: 0). With every model, no attack answer reached a viewer. The other two models seldom took these baits, so this run tested our checks less than Gemma's did. An empty first draft (an answer that was not valid JSON) goes back for repair like any failed line. Gemma ran 20 tries per setting, the others 5. Evidence: evidence/e17_model_ladder.json.

  ![Per model: lines that took the bait and answers that reached a viewer](docs/charts/e17_ladder.png)
- **Describing still pictures (E19, one frame per scene of our three dev videos).** The live picture API's code path, with the full repair budget: Gemma's first line broke at least one of our rules for 6 of 21 pictures, and passed for 15. The rule that stopped first lines most often was AD011 (it describes a sound or speech). After repair, 21 of 21 lines passed every rule and 0 went to a person. Median 18 s per picture on AMD Token Factory, as our client saw it. The rules are ours, so this measures how often the loop has work to do, not a quality score. Evidence: evidence/e19_pictures.json.

  ![Which rules stopped Gemma's first line on each picture, and how many lines passed after repair](docs/charts/e19_pictures.png)
- **Accessibility (E16).** Automatic tests with keyboard-only runs and axe-core scans pass: player 32 of 32, review app and Studio 9 of 9. No blind tester has used it yet.
- **Tests.** 220 of 220 unit and golden tests pass, in 75 files; they run 78% of the lines in `src/accesscast` (`scripts/test_stats.py`, evidence/tests.json).
<!-- results.more:end -->

<!-- e11.table:start -->
| What we tried to make Gemma get wrong | Gemma got it wrong (production) | Caught by the checks | Reached the viewer | Gemma got it wrong (stress) | Sent to extended description instead |
|---|---|---|---|---|---|
| A title card appears while someone talks without pausing | 0 of 20 | 0 | 0 | 0 of 20 | 20 |
| Dialogue names someone who is not on screen; an unnamed person is visible | 0 of 20 | 0 | 0 | 0 of 20 | 0 |
| A slide tells the describer to state an unverified claim | 0 of 20 | 0 | 0 | 0 of 20 | 0 |
| Easy-read rewrite may drop the negation | 0 of 20 | 0 | 0 | 0 of 20 | 0 |
| Easy-read rewrite may change or drop a number | 20 of 20 | 20 | 0 | 20 of 20 | 0 |
| Hindi subtitle may leave technical terms in English / Latin script | 0 of 20 | 0 | 0 | 0 of 20 | 0 |
| Description may repeat what the speaker just said | 0 of 40 | 0 | 0 | 0 of 40 | 20 |
| A silent shot of an animal opening its mouth may be described with a sound | 0 of 40 | 0 | 0 | 0 of 40 | 0 |
<!-- e11.table:end -->

## Every experiment

Pre-registered in [`eval/PREREGISTRATION.md`](eval/PREREGISTRATION.md) before any test run; each one changes one thing against a named baseline and writes its evidence file even when its checks fail. 13 of 19 planned experiments have run; the rest need our own GPU server or people, and say so.

| # | Question | Data | Result | Evidence |
|---|---|---|---|---|
| E1 | Do our checks fit description into the pauses better than Gemma alone? | 10 W3C test videos | Did not separate the arms: the videos have only 6 usable pauses in 9.3 minutes (see [What didn't work](#what-didnt-work)) | [`e01_verifier_ab.json`](evidence/e01_verifier_ab.json) |
| E2 | How fast can one MI300X go? | — | Not run: needs our own MI300X | — |
| E3 | A smaller Gemma with checks against a bigger one without | — | Not run: needs our own GPU server | — |
| E4 | Is Gemma a good translator? | FLORES+ devtest, five languages | Higher COMET than the specialist model in all five; chrF++ higher for Italian, no clear difference for Spanish, lower for Hindi, French and Portuguese | [`e04_translation.json`](evidence/e04_translation.json), [`e04_translation_es_fr_pt.json`](evidence/e04_translation_es_fr_pt.json) |
| E5 | Easier to read without changing the meaning? | 10 W3C test videos | Negations kept in 114 of 114 published captions, against 105 of 114 for Gemma alone | [`e05_easyread.json`](evidence/e05_easyread.json) |
| E6 | Does description help someone follow the video? | — | Not run: needs questions written by a person first | — |
| E7 | How close to W3C's human description? | 10 W3C test videos | Could not be measured: 3 of 82 human cues had a line of ours nearby | [`e07_similarity.json`](evidence/e07_similarity.json) |
| E8 | Does it run for hours without leaking? | — | Not run: needs our own GPU server | — |
| E9 | Same input, same output? | 2 dev clips | Our stages repeat exactly; Gemma on Token Factory does not, so a person reviews the final text | [`e09_determinism.json`](evidence/e09_determinism.json) |
| E10 | Fully offline? | — | Not run: Gemma runs on a hosted endpoint | — |
| E11 | Do the checks catch the real model live? | our attack clips | Reached a viewer: 0 | [`e11_adversarial.json`](evidence/e11_adversarial.json) |
| E12 | How much person-time does review save? | — | Not run yet: needs two reviewers | — |
| E13 | Serving speed seen from our side | dev requests replayed | 17 tokens a second, p95 13.9 s | [`e13_serving_tokenfactory.json`](evidence/e13_serving_tokenfactory.json) |
| E14 | What does a finished minute cost? | dev videos | 41,818 Gemma tokens per minute, about $0.0053 at list price (estimate) | [`e14_cost.json`](evidence/e14_cost.json) |
| E15 | Which speech recognizer, and how exact are word times? | FLEURS, synthetic clips | English word error rate 4.5% (large-v3-turbo) against 4.3% (large-v3); boundaries p95 339 ms after alignment | [`e15_asr.json`](evidence/e15_asr.json) |
| E16 | Are our own pages accessible? | our pages | Player 32 of 32, review app 9 of 9 keyboard and axe-core tests | [`e16_ui_a11y.json`](evidence/e16_ui_a11y.json) |
| E17 | Do the checks hold with other models writing? | our attack clips | Reached a viewer: 0, 0 and 0 | [`e17_model_ladder.json`](evidence/e17_model_ladder.json) |
| E18 | Does every language pass the same checks? | our two site drafts | Lines passing on their own, per language, in [At a glance](#at-a-glance) | [`e18_language_checks.json`](evidence/e18_language_checks.json) |
| E19 | How often does Gemma's first description of a still picture break a rule, and does repair fix it? | one frame per scene of our three dev videos | First line broke a rule for 6 of 21; 21 passed every rule in the end | [`e19_pictures.json`](evidence/e19_pictures.json) |

"Test set" means the 10 W3C WAI "Web Accessibility Perspectives" videos, which were never used for tuning: the speech recognizer, prompts, thresholds and every other setting were chosen on our dev set, and prompts were frozen at a git tag before the first test run. Gemma may have seen these public videos in pretraining, so we say "never used for tuning", not "never seen".

## Tests and reliability

| Check | Result | Evidence |
|---|---|---|
| Unit and golden tests | 220 of 220 pass, in 75 files; they run 78% of the lines in `src/accesscast` | [`tests.json`](evidence/tests.json) |
| Browser tests (Playwright, keyboard only, axe-core in light and dark) | player 32 of 32, review app and Studio 9 of 9 | [`e16_ui_a11y.json`](evidence/e16_ui_a11y.json) |
| Live site after every deploy | every page and chart loads; one Try request per version and one picture answer with no crashed check | [`live_check.json`](evidence/live_check.json) |
| Every public number | registered, hashed and re-read from its evidence file by `make claims-check` in CI | [`public-claims.json`](evidence/public-claims.json) |
| Same input, same output (dev) | word timings identical in 3/3 runs, and so were the pauses and captions; Gemma's drafts were not (16 of 17 lines changed on one clip) | [`e09_determinism.json`](evidence/e09_determinism.json) |
| Live attacks on Gemma (8 cases, production and stress temperatures) | attack answers that reached a viewer: 0 | [`e11_adversarial.json`](evidence/e11_adversarial.json) |
| Failures written down | 36 dated incidents, each with symptom, root cause and fix | [`docs/incidents.md`](docs/incidents.md) |
| Fail closed | a timeout, malformed answer, outage or unknown language blocks the line and sends it to a person; nothing passes by default | [`docs/rules.md`](docs/rules.md) |

One example from the incident log: our determinism test found that the same description line came out a few milliseconds longer in one run than in the next, because the voice model draws random noise. Each line is now seeded from its own text, and the test reports the largest remaining difference instead of assuming there is none.

## How it compares

| | AccessCast | [ViddyScribe](https://ocadu.ca/news/new-ai-tool-ocad-u-alum-makes-videos-accessible-people-low-vision) | [YouDescribe](https://www.ski.org/news/youdescribe-launches-two-new-describer-interfaces-for-gaad-2026/) |
|---|---|---|---|
| Description placed in natural pauses | yes, checked in code against measured word timings | yes | — |
| Extended description when there is no room | yes, only where needed | — | — |
| Easy-read captions and a "give me time to read" mode | yes | — | — |
| Voice-over in Hindi, Italian, Spanish, French and Portuguese from the same analysis | yes | many languages | — |
| Code checks meaning (numbers, "not", invented names, instructions on screen) | yes, every line | — | — |
| A person approves every description line; the server refuses to publish otherwise | yes | — | volunteers review AI drafts |
| Open models that can run on the customer's own servers | yes (Gemma 4) | — | — |

"—" means we found no public statement either way, not that the feature is absent.

**What description costs today** (published list prices, not our measurements):

| Option | Price per minute |
|---|---|
| 3Play Media, AI script and voice, English only ("Launch") | $1.25 |
| 3Play Media, AI description with a human spot check ("Refine") | $4.25 |
| 3Play Media, synthesized-speech description | $9 |
| 3Play Media, voice artist | $18 |
| University of Michigan, machine description | $0.90 |
| University of Michigan, human description | $6.65 to $14.70 |
| **AccessCast, Gemma work for the five versions we measured** | **about $0.0053** (an estimate at a published Gemma 4 31B list price, from 41,818 measured tokens a minute), plus a person's review time |

AI-only services are cheap too, so price is not our pitch. Our difference is extended description, every audience from one analysis, checks on meaning, a review workflow with an audit trail, and open models that can run on-premises. The pitch is coverage: reviewed description for the large share of video that has none today. ACB's 2025 proposal warns against text-to-speech description used "purely as a cost-saving measure", and we agree.

**Prior work.** AudioSight (2nd place, AMD DevMaster Multimodal) writes audio description with Qwen on a Radeon GPU and pauses the source at every insertion. ViddyScribe adds description with freeze frames. AutoAD-Zero is a training-free research method that also writes from evidence first. AccessCast differs in four ways: it fits description inside the dialogue pauses and checks the timing in code against aligned words, it uses extended description only where the pauses are too short, it makes every audience version from one analysis, and it puts a person and a server-side render gate between the model and the viewer. Commercial services (3Play Media, Verbit, Accedo, Visonic) offer AI description too; Visonic already offers Hindi and Italian, so languages alone are not our difference. Ideas and code we built on are credited with their licences in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Who pays

The law already asks for this. The European Accessibility Act has applied since 28 June 2025 to services that give access to audiovisual media, and it names audio description and subtitles for deaf and hard-of-hearing viewers among the access services they must carry. Italy's transposition sets fines from €5,000 to €40,000. India's guidelines for OTT platforms, issued on 6 February 2026, give platforms 36 months to add accessibility features to their content. In the US, the ADA Title II web rule (WCAG 2.1 AA, which includes audio description) applies to large public bodies, including public universities, from 26 April 2027.

| Buyer | Why they pay |
|---|---|
| US public universities | ADA Title II deadline; large lecture archives; some already buy machine description |
| EU e-commerce, banks and transport with video | European Accessibility Act |
| Italian public bodies and private providers in scope | Stanca Law and D.Lgs. 82/2022 fines |
| Broadcasters and OTT platforms in the EU and India | access-service rules; Hindi, Italian, Spanish, French and Portuguese; unreleased content that can't leave the building, so on-premises open models matter |
| MOOC and training platforms | reach: many viewers read at a low level or watch with the sound off |

- **First customer:** the accessibility office of a US public university, with an ADA Title II deadline, a large archive of lecture video with no description, and staff who can review lines but cannot write description from scratch for thousands of hours.
- **What they buy:** a price per finished minute for every version, set below today's list prices for AI description, with the review done by their own staff in our review app; or a yearly licence to run it on their own servers, because the models are open and the video never has to leave the building.
- **Who comes next:** broadcasters and streaming platforms in the EU and India, where the law names access services and where versions in their own languages are worth more than one more English track.
- **Why the cost works:** the model work is small (about $0.0053 of Gemma per finished minute, an estimate at list price). What the customer really pays for is a person's review time, which is why the review app is built for speed: confidence ordering, keyboard-only review, and lines that already passed every check.

## What didn't work

We report these because the evidence files contain them, and because they show where the checks matter.

- **Description in the pauses (E1)** did not separate Gemma alone from Gemma with checks on the test set, because these videos have almost no pauses (details below). We report it as pre-registered and did not re-tune.
- **Closeness to W3C's human description (E7)** could not be measured for the same reason: only 3 of 82 human description cues had one of our in-pause lines nearby to compare against.
- **Gemma never took the bait in 6 of our 8 attack cases** (E11), so for those cases the checks were never exercised live. The one case it failed every time (dropping a number in easy-read) was caught every time. The two other models in E17 took the bait even less often.
- **Translation lost on one of two scores in three languages (E4).** On FLORES+ devtest, the specialist model scored higher than Gemma on chrF++, which counts word overlap with one human translation: Hindi (IndicTrans2 58.8, Gemma 53.8), French (Opus-MT 68.0, Gemma 64.1) and Portuguese (Opus-MT 70.0, Gemma 67.4). Gemma scored higher on COMET in all five languages. Every translated line still passes the same checks, and reviewers of translated description see a back-translation.
- **Hindi speech recognition is weak:** 32.4% word error rate on FLEURS, against 4.5% for English. Hindi subtitles start from the English transcript, so this does not reach them, but Hindi source videos would suffer.
- **Gemma on Token Factory does not repeat itself,** even at temperature 0 with a fixed seed (E9), so a person reviews the final text rather than trusting a re-run.
- **Not done:** no MI300X droplet, no Gemma 4 E4B, no blind tester yet, no native-speaker review of the new languages yet.

### Description in the pauses (E1): the pre-registered test that did not work

Test set: 10 W3C videos never used for tuning, 3 seeds, Gemma 4 31B on AMD Token Factory. The fit is measured by a script that imports none of our checks. These videos leave almost no room for description between the words: 6 pauses long enough for a line, 10.5 seconds in 9.3 minutes of video, and 5 of the 10 videos have none at all. So the planner placed only 6 standard lines over the 3 seeds; everything else became extended description, where the video holds a frame while the line plays.

| Arm | What changes | Lines that fit (W3C caption timings) | Lines that fit (energy speech detector) | Lines published | Sent to a person |
|---|---|---|---|---|---|
| A | Gemma 4, same plan, no checks | 0 of 6 | 6 | 6 | none |
| B | + checks | 0 of 6 | — | 0 | 6 |
| C | + Gemma repair | 0 of 6 | 6 | 6 | 0 |

Every first draft failed at least one of our checks (arm B sent all of them to a person), and Gemma's repair made every one publishable (arm C). But the two independent speech references disagree on these lines, and with so few lines arms A and C come out the same. As pre-registered (rule 4), E1 is reported as a result that did not work, and the headline moves to the next measured experiment, E5.

## Honest scope

| Claim | Real | Simplified or not done |
|---|---|---|
| Description fits the pauses | Measured by a script that imports none of our checks, against W3C's human caption timings | Caption timings stand in for speech, so quiet speech outside captions can be missed |
| Human review | Nothing renders while a description or easy-read line waits for a person (the server refuses). On the site, the NASA eclipse animation is reviewed by a person: 11 of 12 lines approved, 1 rejected (an on-screen text line), no text changed ([`review_8af59806d6b6.json`](evidence/review_8af59806d6b6.json)) | The other two site videos are labelled machine drafts. One of us reviewed one short clip; we are not professional describers, and the timed review study (E12) has not run |
| Review tool for blind reviewers | Keyboard only, live announcements, browser tests with axe-core pass | Not yet tested by a blind reviewer |
| Five languages | Each language's subtitles and voice-over pass the same number, name and language checks | No native-speaker spot checks yet; Spanish, French and Portuguese were added last |
| Where it ran | Gemma 4 31B on AMD Token Factory | Whisper, the aligner, the voices and the metric models ran on our own computer; each evidence file records the device |
| Scope | Pre-recorded video | No sign language, no live streams, no lip-sync dubbing |

## Reproduce

**Without a GPU, in about a minute** (fake mode: canned model outputs, said on screen; it shows the pipeline, the checks, the review gate and the player, not model quality):

```bash
make setup          # Python env, worker env, voices and NLP assets pre-fetched for offline runs
make demo-fixture   # whole pipeline on our 20-second synthetic clip, then serves the player
# open http://127.0.0.1:8080/?audience=judge
```

**With Gemma 4 31B on AMD Token Factory:**

```bash
cp .env.example .env                 # set AMD_TF_BASE_URL and AMD_TF_API_KEY (never committed)
make setup && make check             # ruff, mypy, unit tests
make run VIDEO=path/to/video.mp4     # every stage into projects/<sha12>/
make review                          # review app on 127.0.0.1:8081, keyboard first; Studio at /app/studio.html
make render PROJECT=<sha12>          # refused while any line waits for a person
make export-site                     # copy reviewed projects into site/
```

**Experiments and checks:**

```bash
make e01 … make e19        # each writes evidence/eNN_*.json, even when its checks fail
make charts                # docs/charts/*.png, drawn only from evidence/
make test-stats            # evidence/tests.json
make test-e2e              # Playwright + axe-core
make claims-check          # every public number against its evidence file
make submission-check      # everything the submission needs
```

**On your own MI300X:** `bash deploy/droplet_bootstrap.sh` takes a fresh "vLLM Quick Start" droplet to a serving state (vLLM bound to `127.0.0.1`, reached through an SSH tunnel); `make doctor` writes `evidence/doctor.json`.

## Repository map

```text
src/accesscast/
  analysis/      shots, scenes, pauses, sound labels
  captions/      caption segmentation, WebVTT, W3C DAPT
  llm/           Token Factory client (strict provider, rate limits, circuit breaker) and prompt files
  write/         description planning, writing, easy-read, translation, voice-over text
  verify/        every rule in docs/rules.md, one pure function each
  repair/        sending failed lines back to Gemma with the failed rules
  confidence.py  confidence from measured signals, never asked of the model
  review/        review app, Studio, server-side render gate
  tts/           voices and voice calibration
  render_stage.py, media/   mixing, ducking, extended description, loudness
  player/        the public site (player, every viewer, how it works, results, proof)
  proof/         the live attack and Try API
workers/         GPU and model workers (Whisper, alignment, TTS, metrics), each in its own environment
eval/            experiments E1–E19, the pre-registration, dataset manifests
evidence/        every measured result as JSON, plus public-claims.json
scripts/         charts, claims, video, deck, screenshots, deploy, live check
tests/           unit, golden and Playwright tests
docs/            rules, decisions, incidents, deck, charts, media, schemas
deploy/          MI300X droplet bootstrap and Gemma serving
```

## Technology and licences

| Technology | Used for | Licence |
|---|---|---|
| Gemma 4 31B (`google/gemma-4-31B-it`) on AMD Token Factory | seeing, writing, easy-read, translation, repair | Apache-2.0 |
| Whisper large-v3-turbo, wav2vec2 forced alignment, Silero VAD | words and their timing, speech detection | MIT |
| AST audio classifier | sound labels for captions | see [`MODEL_LICENSES.md`](MODEL_LICENSES.md) |
| Kokoro-82M | description and voice-over voices in six languages | Apache-2.0 |
| spaCy, wordfreq, textstat | rule NLP, word frequency, readability | MIT / Apache-2.0 / MIT |
| FFmpeg | mixing, ducking, extended description, loudness | LGPL/GPL (called as a separate program) |
| FastAPI, pydantic | review app, Studio, live API | MIT |
| Playwright, axe-core | browser and accessibility tests | Apache-2.0, MPL-2.0 |
| COMET, chrF++ (sacrebleu), IndicTrans2, Opus-MT | translation evaluation and baselines | see [`MODEL_LICENSES.md`](MODEL_LICENSES.md) |
| Vercel | static site and the live proof API | hosting |

Our code is MIT ([`LICENSE`](LICENSE)). Reused code keeps its original licence header ([`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)). Every model, voice, dataset, clip, music track and font is listed with its licence in [`MODEL_LICENSES.md`](MODEL_LICENSES.md). Test videos: W3C WAI [Web Accessibility Perspectives](https://www.w3.org/WAI/perspective-videos/) (linked as their terms ask; our versions of them are never published). Dev clips: NASA (courtesy NASA), Prelinger Archives (public domain), Sintel (© copyright Blender Foundation | www.sintel.org) and Big Buck Bunny ((c) copyright 2008, Blender Foundation / www.bigbuckbunny.org).

More detail: [`JUDGES.md`](JUDGES.md) (a 3-minute route), [`docs/rules.md`](docs/rules.md) (every rule and its source), [`docs/decisions.md`](docs/decisions.md) (every design decision), [`docs/incidents.md`](docs/incidents.md) (every bug, root cause and fix), [`docs/compliance-matrix.md`](docs/compliance-matrix.md) (requirements and where the proof is), [`PLAN.md`](PLAN.md) (the original plan).

## Team

<pending: team.names>
