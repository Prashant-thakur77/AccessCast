Blind, deaf and slow-reading viewers, and people who speak Hindi, Italian, Spanish, French or Portuguese, each get their own version of the same video: Gemma 4 on AMD writes it, code checks every line, and a person approves it before anyone hears it.

![The AccessCast player plays the same clip for one viewer after another; the page changes colour for each viewer.](docs/media/five-ways.gif)

**[▶ Live demo](https://accesscast.vercel.app/?audience=judge)** · Demo video: <pending: video.url> · Deck (PDF): <pending: deck.url> · [3-minute judge guide](JUDGES.md) · [Proof page](https://accesscast.vercel.app/proof.html)

[![CI](https://github.com/Prashant-thakur77/AccessCast/actions/workflows/ci.yml/badge.svg)](https://github.com/Prashant-thakur77/AccessCast/actions/workflows/ci.yml) [![Live demo](https://img.shields.io/badge/live%20demo-accesscast.vercel.app-E4402A)](https://accesscast.vercel.app/?audience=judge) [![Gemma 4 31B on AMD Token Factory](https://img.shields.io/badge/Gemma%204%2031B-AMD%20Token%20Factory-141B34)](#gemma-4-on-amd) [![Accessible: keyboard and axe-core](https://img.shields.io/badge/our%20own%20UI-keyboard%20%2B%20axe--core-1E7A4C)](#results) [![MIT licence](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

# AccessCast: one video, made for every viewer

Most online video has no audio description, and most of it has captions only in one language, if any. AccessCast takes one video and makes a version for each viewer. Gemma 4 31B, served by AMD Token Factory, does the seeing, writing, translating and repairing. Code checks every line Gemma writes against the real audio timeline. Gemma repairs what fails. A person approves what the public hears.

> Built for AMD Developer Hackathon ACT III, track "Create a New Kind of Experience". Every number on this page comes from a file in [`evidence/`](evidence/) through [`evidence/public-claims.json`](evidence/public-claims.json); `make claims-check` fails if any number here is not registered. Places marked `<pending: …>` are waiting for an experiment to run.

## What the checks caught

With Gemma 4 31B on AMD Token Factory:

- **A dropped "not" flips a sentence.** On 10 W3C accessibility videos never used for tuning, asked to simplify captions, Gemma alone kept every "not", "never" and "no" in 105 of 114 captions. What AccessCast published kept them in 114 of 114; 7 captions went to a person instead.
- **A dropped time limit.** On our own attack clips (made to test the checks; not the W3C test set), told "press the button 3 times within 10 seconds", Gemma's easy-read rewrite dropped the 10 seconds in 20 of 20 tries. The number check caught every one, and Gemma's repair put it back. Across 8 attack cases, attack outputs that reached a viewer: 0. ([Proof page](https://accesscast.vercel.app/proof.html))

![Bar chart: easy-read captions that kept every negation, Gemma alone against AccessCast as published](docs/charts/e5_negations.png)

![Attack cases: tries, how often Gemma took the bait, and how many answers reached a viewer](docs/charts/e11_attacks.png)
- **What it costs.** The five versions we measured (description, captions, easy-read, Hindi, Italian) of one finished minute take about 41,818 Gemma tokens (measured on our dev videos). At a published list price for Gemma 4 31B that is about $0.0053 a minute, or $0.32 per hour of video (an estimate, not a price we paid), plus a person's review time. Today's list price for AI description with a human spot check is $4.25 a minute (3Play Media).

## What it does

| Who is watching | What they get |
|---|---|
| "I can't see the screen" | Spoken description placed in the pauses between dialogue, with the original sound dipped underneath. When the pauses are too short, an extended version holds a still frame while the description plays. A text description track is there for screen readers and braille displays. |
| "I can't hear" | Captions for deaf and hard-of-hearing viewers: every word, timed to the speech, and the sounds between words, like [music] or [applause]. (Speaker-change marks are built and switch on once the speaker model's licence is accepted.) |
| "Simpler words, please" | Easy-read captions with short sentences and one idea each. A "Give me time to read" mode pauses the video until you are ready. |
| "हिन्दी" | Hindi subtitles, a Hindi voice-over in the same time slots as the original speech, and Hindi description. |
| "Italiano" | Italian subtitles, an Italian voice-over and Italian description. |

![How AccessCast works: the video is analysed on our computer; Gemma 4 31B on AMD Token Factory looks and writes; code plans and checks every line and sends failures back; a person approves; voices and rendering run on our computer; a render gate refuses while any line waits; viewers pick their version](docs/architecture.png)

![One real clip, NASA's Life in the Universe: speech, the few pauses, the lines spoken in pauses, and the many lines read while the picture holds](docs/charts/timeline_nasa.png)

All five come from one analysis of the video (shots, scenes, every word with its timing, the pauses between words, sounds, on-screen text and what is visible), so they never disagree with each other. Profiles combine: a blind Hindi speaker gets the Hindi voice-over with Hindi description.

## AccessCast Studio

`make review` also serves the Studio at http://127.0.0.1:8081/app/studio.html. Choose a video and every step runs in front of you, in plain words: listening for words, finding pauses, Gemma looking at each scene, Gemma writing, code checking every line and Gemma repairing what fails, then captions, easy-read, Hindi and Italian. It ends with a table of the lines made per version and a link to review them. Nothing is published from the Studio; every line still goes through the review gate. It works with the keyboard alone and announces each finished step to screen readers.

## Gemma 4 on AMD

Gemma 4 31B does four jobs in every run, all on **AMD Token Factory**: it looks at the frames of each scene and lists what is visible, writes the description from that list only, rewrites captions as easy-read and translates them into Hindi and Italian, and repairs any line that fails a check, told exactly which check failed. Every answer is checked against the model name the server reports (`--strict-provider`), and the model never decides timing or whether a line is good enough: code does.

**Every Gemma call ran on AMD.** Counted from our own call logs (`scripts/amd_usage.py`): AMD Token Factory answered 3,510 Gemma 4 31B requests for us, 3,153,397 tokens in all, while working on 28 videos (32.8 minutes): 10 W3C test videos, 10 dev clips and our 8 attack clips. Every answer came from the same served model. The live attack on our site adds more calls, which these logs do not include.

![Gemma 4 31B requests answered by AMD Token Factory, by day, from our own call logs](docs/charts/amd_usage.png)

![Where the Gemma tokens of one finished minute go, by version](docs/charts/e14_tokens.png)

![Latency and tokens per second seen from our side at one and four requests at a time](docs/charts/e13_serving.png)

Gemma 4 31B ran on AMD Token Factory, AMD's hosted endpoint. These numbers are measured from our side of the connection (client-side), so they include the network and Token Factory's own queue.

| What we measured | Value | Evidence |
|---|---|---|
| Generated tokens per second seen by our client, best concurrency | 17 | `e13_serving_tokenfactory.json` |
| p95 latency of a description request at that concurrency | 13.9 s | `e13_serving_tokenfactory.json` |
| Gemma tokens per finished minute of video, the five versions we measured | 41,818 | `e14_cost.json` |
| Gemma requests answered by AMD Token Factory, all our work | 3,510 | `amd_usage.json` |
| Tokens in those requests | 3,153,397 | `amd_usage.json` |
| Calls Token Factory never answered, after every retry (outages; each one failed closed) | 20 | `amd_usage.json` |
| Calls our circuit breaker then held back without sending (each one failed closed) | 2,619 | `amd_usage.json` |

We could not create an MI300X droplet: AMD Developer Cloud asks for a payment card, and we did not have one it accepts. So this page has no GPU memory, users-per-GPU or GPU-dollar numbers. The scripts to measure them on a droplet are in `deploy/` and `eval/`, unchanged.

Each table names its data split. "Test set" means the 10 W3C WAI "Web Accessibility Perspectives" videos, which were never used for tuning: the ASR model, prompts, thresholds and every other setting were chosen on our dev set, and prompts were frozen at a git tag before the first test run ([`eval/PREREGISTRATION.md`](eval/PREREGISTRATION.md)). Gemma may have seen these public videos in pretraining, so we say "never used for tuning", not "never seen".

| Part | Where it ran |
|---|---|
| Gemma 4 31B: looking at frames, writing description, captions, easy-read, Hindi, Italian, Spanish, French and Portuguese, every repair, scene judgments | AMD Token Factory (`Gemma-4-31B-IT`), every call checked against the model name the server reports (`--strict-provider`) |
| Whisper, the wav2vec2 aligner, Silero VAD, the AST sound classifier, the Kokoro voices, the metric models | Our own workstation, not AMD hardware. The device is written in every worker response and evidence file |
| Gemma 4 E4B (listening: transcript cross-check, sound labels) | Not run. Token Factory does not offer it, and we had no droplet to serve it. Sound labels come from AST, a small non-Gemma classifier, instead (`docs/decisions.md` D-022) |

Token Factory had outages during our runs (it answered "no available workers" for minutes at a time). The pipeline fails closed: a scene whose evidence call fails goes to a person, and a re-run asks again only for the calls that failed. Requests that failed during the speed test are counted in its evidence file: 15 of 120 requests failed (client-side, dev requests replayed); every one was refused by Token Factory's rate limit for our key, not a model error.

## Results

<!-- results.more:start -->
- **Speech recognition (E15, dev set).** We chose Whisper large-v3-turbo: its English word error rate was 4.5% on 100 FLEURS clips, against 4.3% for the larger large-v3 (Hindi 32.4%, Italian 3.0%). After forced alignment, word boundaries were off by 54 ms at the median and 339 ms at the 95th percentile, on 224 word boundaries of our synthetic clips. Raw Whisper timestamps were closer at the median (32 ms) but worse in the tail (480 ms at the 95th percentile); the guard is set from the tail, so description keeps 340 ms clear of speech. Large-v3 could not produce word timings within our computer's memory, so it was not a candidate.
- **Translation (E4, FLORES+ devtest, 1012 sentences per language, not our videos).** Two scores: COMET, a model trained to match human quality ratings, and chrF++, which counts character and word overlap with one human translation. Italian: Gemma 4 31B scored higher than Opus-MT, a widely used open English–Italian model, on both: COMET 0.8898 against 0.8522 (difference +0.0376, 95% interval +0.0337 to +0.0417) and chrF++ 55.4 against 54.8 (+0.7, +0.1 to +1.3). Hindi was mixed: Gemma scored higher on COMET (0.8253 against 0.8157, +0.0095, +0.0063 to +0.0131), but IndicTrans2, a model built for Indian languages, scored higher on chrF++ (58.8 against 53.8; Gemma −5.0, −5.7 to −4.3). Gemma returned every sentence (0 missing in Hindi, 0 in Italian).

  ![Gemma minus the baseline for each language and score, with 95% intervals](docs/charts/e4_translation.png)
- **Easy-read (E5, 10 W3C videos never used for tuning).** Asked to simplify the captions, Gemma alone kept every "not", "never" and "no" in 105 of 114 cues; in the others the sentence lost its negation and so its meaning. The easy-read AccessCast published kept them in 114 of 114, and sent 7 of 121 cues to a person instead. Paced for slow reading (at most 130 words a minute): 106 of 114 published cues, against 57 of 121 original captions. These counts use a negation counter close to our own check, so a blind rating by people leads this experiment; it is still to come.
- **Every language through the same checks (E18, our two site drafts, dev).** Translated subtitle and voice-over lines that passed every check on their own: Hindi 74 of 81, Italian 74 of 81, Spanish 73 of 81, French 70 of 81, Portuguese 76 of 81. The rest went to a person, not to viewers. The check that held the most lines was CC001 (reading speed). Evidence: evidence/e18_language_checks.json.

  ![Lines per language that passed every check, and lines held for a person](docs/charts/e18_languages.png)
- **Accessibility (E16).** Automatic tests with keyboard-only runs and axe-core scans pass: player 27 of 27, review app and Studio 7 of 7. No blind tester has used it yet.
- **Tests.** 188 of 188 unit and golden tests pass, in 69 files; they run 53% of the lines in `src/accesscast` (`scripts/test_stats.py`, evidence/tests.json).
<!-- results.more:end -->

## Reliability and the live attack

On the live site, anyone can run our attack against Gemma 4 31B on AMD Token Factory, or type their own caption and watch the easy-read, Hindi, Italian, Spanish, French and Portuguese versions being made and checked ([proof page](https://accesscast.vercel.app/proof.html)). Nothing typed there is stored.

| Check | Result | Evidence |
|---|---|---|
| Soak test | Not run: it measures our own GPU server, and we had no droplet | — |
| Offline run | Not run: Gemma ran on a hosted endpoint, so a run cannot be offline | — |
| Same input, same output (dev) | Our own stages are repeatable: word timings identical in 3/3 runs, and so were the pauses and captions. Gemma on Token Factory is not: its scene evidence (temperature 0) and drafts (temperature 0.3, fixed seed) changed between runs, so 3 of 10 description lines differed on a NASA clip and 16 of 17 on the Sintel trailer. This is why a person reviews the final text, never a re-run. | `e09_determinism.json` |
| Live attacks on Gemma (8 cases, 20 tries each at the production temperature and 20 at a stress temperature) | outputs that reached the viewer: 0 | `e11_adversarial.json` |

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

## How quality is controlled

Gemma proposes and code decides. Gemma first lists what is visible in a scene (temperature 0), then writes description only from that list. Code then checks every line: [`docs/rules.md`](docs/rules.md) lists each rule with its source and what it measures. For example, AD001 measures the spoken line against the pause it has to fit and reports both numbers, AD009 blocks a name nobody said or showed, and AD018 blocks a line that obeys instructions written on a slide. A line that fails goes back to Gemma with the failed checks, up to three times. A line that still fails goes to a person; it is never published by default.

Nothing reaches a viewer until a person approves it. Confidence for each line is computed in code from measured signals (grounding, timing slack, ASR agreement, repairs), never asked of the model, and it orders the review queue. The render step is refused on the server while any line is waiting, and every render carries a `report.json` audit with `human_reviewed`, the reviewers and the review time.

## Who pays

The law already asks for this. The European Accessibility Act has applied since 28 June 2025 to services that give access to audiovisual media, and it names audio description and subtitles for deaf and hard-of-hearing viewers among the access services they must carry. Italy's transposition sets fines from €5,000 to €40,000. India's guidelines for OTT platforms, issued on 6 February 2026, give platforms 36 months to add accessibility features to their content. In the US, the ADA Title II web rule (WCAG 2.1 AA, which includes audio description) applies to large public bodies, including public universities, from 26 April 2027.

| Buyer | Why they pay |
|---|---|
| US public universities | ADA Title II deadline; large lecture archives; some already buy machine description |
| EU e-commerce, banks and transport with video | European Accessibility Act |
| Italian public bodies and private providers in scope | Stanca Law and D.Lgs. 82/2022 fines |
| Broadcasters and OTT platforms in the EU and India | access-service rules; Hindi, Italian, Spanish, French and Portuguese; unreleased content that can't leave the building, so on-premises open models matter |
| MOOC and training platforms | reach: many viewers read at a low level or watch with the sound off |

What description costs today (list prices, not our measurements): 3Play Media lists $4.25 a minute for AI description with a human spot check and $18 for a voice artist; the University of Michigan lists $0.90 a minute for machine description and $6.65 to $14.70 for human description. A human describer needs about 20 hours to script and voice a one-hour programme (Media Access Australia).

Our cost is Gemma tokens plus a person's review time: 41,818 Gemma tokens per finished minute of video for the five versions we measured (dev set), and review time from E12. AI-only services are cheap too, so price is not our pitch. Our difference is extended description, every audience from one analysis, a review workflow with an audit trail, and open models that can run on-premises. The pitch is coverage: reviewed description for the large share of video that has none today. ACB's 2025 proposal warns against text-to-speech description used "purely as a cost-saving measure", and we agree.

### How it is sold

- **First customer:** the accessibility office of a US public university. It has a deadline (ADA Title II applies to large public bodies from 26 April 2027), a large archive of lecture and outreach video with no description, and staff who can review lines but not write description from scratch for thousands of hours.
- **What they buy:** a price per finished minute for every version, set below today's list prices for AI description, with the review done by their own staff in our review app; or a yearly licence to run it on their own servers, because the models are open and the video never has to leave the building.
- **Who comes next:** broadcasters and streaming platforms in the EU and India, where the law names access services and where versions of the same video in their own languages are worth more than one more English track.
- **Why the cost works:** the model work is small (about $0.0053 of Gemma per finished minute at a published list price, an estimate). What the customer really pays for is a person's review time, which is why the review app is built for speed: confidence ordering, keyboard-only review, and lines that already passed every check.

### How it differs from tools that already exist

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

## What didn't work

- **Description in the pauses (E1)** did not separate Gemma alone from Gemma with checks on the test set, because these videos have almost no pauses (details below). We report it as pre-registered and did not re-tune.
- **Closeness to W3C's human description (E7)** could not be measured for the same reason: only 3 of 82 human description cues had one of our in-pause lines nearby to compare against.
- **Gemma never took the bait in 6 of our 8 attack cases** (E11), so for those cases the checks were never exercised live. The one case it failed every time (dropping a number in easy-read) was caught every time.
- **Hindi translation lost on one of two scores (E4).** On FLORES+ devtest, IndicTrans2 scored higher than Gemma on chrF++ (58.8 against 53.8), while Gemma scored higher on COMET. We kept Gemma for Hindi and changed nothing: Hindi lines still pass the same checks, and reviewers see a back-translation. Using a Hindi specialist model inside the pipeline is untested.
- **Hindi speech recognition is weak:** 32.4% word error rate on FLEURS, against 4.5% for English. Hindi subtitles start from the English transcript, so this does not reach them, but Hindi source videos would suffer.
- **Our first voice timing was wrong.** Lines inside their word budget still overran their pause; we refitted on dev lines and added a margin (D-024).
- **Extended description drifted from the picture** by up to a few frames until E9 caught it; the render and its length check are fixed (`docs/incidents.md`).
- **Token Factory was unreliable while we worked:** long stretches of "no available workers", and 15 of 120 requests refused by the rate limit in E13. Everything fails closed, but runs took hours.
- **Gemma on Token Factory does not repeat itself,** even at temperature 0 with a fixed seed (E9): re-running the same clip changed most of its description lines on the Sintel trailer. Determinism would need our own server.
- **Not done:** no MI300X droplet (no accepted payment card), no Gemma 4 E4B, no blind tester yet.

### Description in the pauses (E1): the pre-registered test that did not work
Test set: 10 W3C videos never used for tuning, 3 seeds, Gemma 4 31B on AMD Token Factory. The fit is measured by a script that imports none of our checks.

These videos leave almost no room for description between the words: 6 pauses long enough for a line, 10.5 seconds in 9.3 minutes of video, and 5 of the 10 videos have none at all. So the planner placed only 6 standard lines over the 3 seeds; everything else became extended description, where the video holds a frame while the line plays.

| Arm | What changes | Lines that fit (W3C caption timings) | Lines that fit (energy speech detector) | Lines published | Sent to a person |
|---|---|---|---|---|---|
| A | Gemma 4, same plan, no checks | 0 of 6 | 6 | 6 | none |
| B | + checks | 0 of 6 | — | 0 | 6 |
| C | + Gemma repair | 0 of 6 | 6 | 6 | 0 |

Every first draft failed at least one of our checks (arm B sent all of them to a person), and Gemma's repair made every one publishable (arm C). But the two independent speech references disagree on these lines, and with so few lines arms A and C come out the same. As pre-registered (`eval/PREREGISTRATION.md`, rule 4), E1 is reported here as a result that did not work, and the headline moves to the next measured experiment. Evidence: [`evidence/e01_verifier_ab.json`](evidence/e01_verifier_ab.json), [`evidence/e01_test_gap_census.json`](evidence/e01_test_gap_census.json).


## Honest scope

| Claim | Real | Simplified or not done |
|---|---|---|
| Description fits the pauses | Measured by a script that imports none of our checks, against W3C's human caption timings | Caption timings stand in for speech, so quiet speech outside captions can be missed |
| Human review | Nothing renders while a description or easy-read line waits for a person (the server refuses); captions and translations pass automatic checks | Our reviewers are not professional describers; the timed two-person review study (E12) has not run yet |
| Review tool for blind reviewers | Designed for it: keyboard only, live announcements, automatic accessibility tests pass (player 27 of 27, review app and Studio 7 of 7, including axe-core scans) | Not yet tested by a blind reviewer |
| Hindi, Italian, Spanish, French, Portuguese | Each language's subtitles and voice-over pass the same number, name and language checks; translated description has a back-translation for reviewers (Hindi, Italian) | Not a full professional language QA; native-speaker spot checks are not done yet. Spanish, French and Portuguese were added last |
| "Usefulness" (E6) | An LLM answers questions from our description | A proxy, not a study with blind viewers |
| Timing check clip (E15) | Word boundaries from the speech synthesizer | Not a human hand label |
| Where it ran | Gemma 4 31B on AMD Token Factory | Whisper, the aligner, the voices and the metric models ran on our own workstation, not on AMD hardware; each evidence file records the device. Gemma 4 E4B (listening) is not on Token Factory, so the transcript cross-check did not run and sound labels come from AST |
| Scope | Pre-recorded video | No sign language, no live streams, no lip-sync dubbing |

## Prior work and how we differ

AudioSight (2nd place, AMD DevMaster Multimodal) writes audio description with Qwen on a Radeon GPU and pauses the source at every insertion. ViddyScribe (Gemini API Developer Competition) adds description with freeze frames. AutoAD-Zero is a training-free research method that also writes from evidence first. AccessCast differs in four ways: it fits description inside the dialogue pauses and checks the timing in code against aligned words, it uses extended description only where the pauses are too short, it makes five audience versions from one analysis, and it puts a person and a server-side render gate between the model and the viewer. Commercial services (3Play Media, Verbit, Accedo, Visonic) offer AI description too; Visonic already offers Hindi and Italian, so languages alone are not our difference.

We reused or built on ideas from earlier hackathon winners; [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) lists each one with its licence.

## Bugs that taught us something

Dated entries with symptom, root cause and fix are in [`docs/incidents.md`](docs/incidents.md). One example: our determinism test found that the same description line came out a few milliseconds longer in one run than in the next, because the TTS vocoder draws random noise. Each line is now seeded from its own text, and the test reports the largest remaining difference instead of assuming there is none.

## Reproduce

```bash
make setup && make check            # tests, lint, types
bash deploy/droplet_bootstrap.sh    # only if you have a droplet: a fresh MI300X "vLLM Quick Start" droplet: images, Gemma, workers, weights
make doctor                         # writes evidence/doctor.json
make run VIDEO=path/to/video.mp4    # all stages into projects/<sha12>/
make review                         # approve lines, keyboard first; Studio (add a video, watch each step) at /app/studio.html
make render PROJECT=<sha12>         # refuses while anything is pending
make e01 … make e16                 # each experiment writes evidence/eNN_*.json, even when it fails
make submission-check
```

### Without a GPU

```bash
make setup          # Python env, worker env, voices and models pre-fetched
make demo-fixture   # whole pipeline in fake mode on our 20-second clip, then serves the player
# open http://127.0.0.1:8080/?audience=judge
```

Fake mode uses canned model outputs and says so on screen. It shows the pipeline, the checks, the review gate and the player. It is not evidence of model quality. The 20-second clip is ours: generated visuals and two Kokoro voices.

## Licences and credits

Our code is MIT ([LICENSE](LICENSE)). Reused code keeps its original licence header; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Models, voices, datasets and clips are listed with their licences in [MODEL_LICENSES.md](MODEL_LICENSES.md). Test videos: W3C WAI [Web Accessibility Perspectives](https://www.w3.org/WAI/perspective-videos/) (linked as their terms ask; our versions of them are never published). Dev clips: NASA (courtesy NASA), Prelinger Archives (public domain), Sintel (© copyright Blender Foundation | www.sintel.org) and Big Buck Bunny ((c) copyright 2008, Blender Foundation / www.bigbuckbunny.org).

## Team

<pending: team.names>
