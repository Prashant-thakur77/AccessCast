<pending: e1.headline>

[Live demo](https://accesscast.vercel.app/?audience=judge) · [3-minute judge guide](JUDGES.md) · Demo video: <pending: video.url> · Deck (PDF): <pending: deck.url>

# AccessCast: one video, five ways to watch

Most online video has no audio description, and most of it has captions only in one language, if any. AccessCast takes one video and makes a version for each viewer. Gemma 4 31B, served by AMD Token Factory, does the seeing, writing, translating and repairing. Code checks every line Gemma writes against the real audio timeline. Gemma repairs what fails. A person approves what the public hears.

> Built for AMD Developer Hackathon ACT III, track "Create a New Kind of Experience". Every number on this page comes from a file in [`evidence/`](evidence/) through [`evidence/public-claims.json`](evidence/public-claims.json); `make claims-check` fails if any number here is not registered. Places marked `<pending: …>` are waiting for an experiment to run.

## What it does

| Who is watching | What they get |
|---|---|
| "I can't see the screen" | Spoken description placed in the pauses between dialogue, with the original sound dipped underneath. When the pauses are too short, an extended version holds a still frame while the description plays. A text description track is there for screen readers and braille displays. |
| "I can't hear" | Captions for deaf and hard-of-hearing viewers: every word, speaker changes, and sounds like [door slams]. |
| "Simpler words, please" | Easy-read captions with short sentences and one idea each. A "Give me time to read" mode pauses the video until you are ready. |
| "हिन्दी" | Hindi subtitles, a Hindi voice-over in the same time slots as the original speech, and Hindi description. |
| "Italiano" | Italian subtitles, an Italian voice-over and Italian description. |

All five come from one analysis of the video (shots, scenes, every word with its timing, the pauses between words, sounds, on-screen text and what is visible), so they never disagree with each other. Profiles combine: a blind Hindi speaker gets the Hindi voice-over with Hindi description.

## Try it in 60 seconds (no GPU)

```bash
make setup          # Python env, worker env, voices and models pre-fetched
make demo-fixture   # whole pipeline in fake mode on our 20-second clip, then serves the player
# open http://127.0.0.1:8080/?audience=judge
```

Fake mode uses canned model outputs and says so on screen. It shows the pipeline, the checks, the review gate and the player. It is not evidence of model quality. The 20-second clip is ours: generated visuals and two Kokoro voices.

## Results

### Headline: description lines that fit the pauses (E1)
Test set: 10 W3C videos never used for tuning, 3 seeds, measured by a script that imports none of our checks against W3C's human caption timings.

| Arm | What changes | Lines that fit | Lines published | Sent to a person |
|---|---|---|---|---|
| A | Gemma 4, same plan, no checks | <pending: e1.fit_a> of <pending: e1.lines_planned> | <pending: e1.pub_a> | none |
| B | + checks | <pending: e1.fit_b> of <pending: e1.lines_planned> | <pending: e1.pub_b> | <pending: e1.sent_b> |
| C | + Gemma repair | <pending: e1.fit_c> of <pending: e1.lines_planned> | <pending: e1.pub_c> | <pending: e1.sent_c> |

95% interval for the gain from A to C, as a share of planned lines (bootstrap over videos): <pending: e1.ci_lo> to <pending: e1.ci_hi>. Coverage of W3C's human description positions (one of our lines within 3 seconds): A <pending: e1.cov_a>, C <pending: e1.cov_c>. Evidence: [`evidence/e01_verifier_ab.json`](evidence/e01_verifier_ab.json).

### Other results
<pending: results.more>

### On AMD
Gemma 4 31B ran on AMD Token Factory, AMD's hosted endpoint. These numbers are measured from our side of the connection (client-side), so they include the network and Token Factory's own queue.

| What we measured | Value | Evidence |
|---|---|---|
| Generated tokens per second seen by our client, best concurrency | 17 | `e13_serving_tokenfactory.json` |
| p95 latency of a description request at that concurrency | 13.9 s | `e13_serving_tokenfactory.json` |
| Gemma tokens per finished minute of video, all five versions | <pending: e14.tokens_per_minute> | `e14_cost.json` |

We could not create an MI300X droplet: AMD Developer Cloud asks for a payment card, and we did not have one it accepts. So this page has no GPU memory, users-per-GPU or GPU-dollar numbers. The scripts to measure them on a droplet are in `deploy/` and `eval/`, unchanged.

Each table names its data split. "Test set" means the 10 W3C WAI "Web Accessibility Perspectives" videos, which were never used for tuning: the ASR model, prompts, thresholds and every other setting were chosen on our dev set, and prompts were frozen at a git tag before the first test run ([`eval/PREREGISTRATION.md`](eval/PREREGISTRATION.md)). Gemma may have seen these public videos in pretraining, so we say "never used for tuning", not "never seen".

## AccessCast Studio

`make review` also serves the Studio at http://127.0.0.1:8081/app/studio.html. Choose a video and every step runs in front of you, in plain words: listening for words, finding pauses, Gemma looking at each scene, Gemma writing, code checking every line and Gemma repairing what fails, then captions, easy-read, Hindi and Italian. It ends with a table of the lines made per version and a link to review them. Nothing is published from the Studio; every line still goes through the review gate. It works with the keyboard alone and announces each finished step to screen readers.

## How quality is controlled

Gemma proposes and code decides. Gemma first lists what is visible in a scene (temperature 0), then writes description only from that list. Code then checks every line: [`docs/rules.md`](docs/rules.md) lists each rule with its source and what it measures. For example, AD001 measures the spoken line against the pause it has to fit and reports both numbers, AD009 blocks a name nobody said or showed, and AD018 blocks a line that obeys instructions written on a slide. A line that fails goes back to Gemma with the failed checks, up to three times. A line that still fails goes to a person; it is never published by default.

Nothing reaches a viewer until a person approves it. Confidence for each line is computed in code from measured signals (grounding, timing slack, ASR agreement, repairs), never asked of the model, and it orders the review queue. The render step is refused on the server while any line is waiting, and every render carries a `report.json` audit with `human_reviewed`, the reviewers and the review time.

## Reliability and the live attack

| Check | Result | Evidence |
|---|---|---|
| Soak test | Not run: it measures our own GPU server, and we had no droplet | — |
| Offline run | Not run: Gemma ran on a hosted endpoint, so a run cannot be offline | — |
| Same input, same output | <pending: e09.summary> | `e09_determinism.json` |
| Live attacks on Gemma (8 cases, 20 tries each at the production temperature and 20 at a stress temperature) | outputs that reached the viewer: <pending: e11.total_leaks> | `e11_adversarial.json` |

<pending: e11.table>

## What runs on AMD

| Part | Where it ran |
|---|---|
| Gemma 4 31B: looking at frames, writing description, captions, easy-read, Hindi and Italian, every repair, scene judgments | AMD Token Factory (`Gemma-4-31B-IT`), every call checked against the model name the server reports (`--strict-provider`) |
| Whisper, the wav2vec2 aligner, Silero VAD, the Kokoro voices, the metric models | Our own workstation, not AMD hardware. The device is written in every worker response and evidence file |
| Gemma 4 E4B (listening: transcript cross-check, sound labels) | Not run. Token Factory does not offer it, and we had no droplet to serve it |

Token Factory had outages during our runs (it answered "no available workers" for minutes at a time). The pipeline fails closed: a scene whose evidence call fails goes to a person, and a re-run asks again only for the calls that failed. Requests that failed during the speed test are counted in its evidence file: 15 of 120 requests failed (client-side, dev requests replayed).

## Who pays

The law already asks for this. The European Accessibility Act has applied since 28 June 2025 to services that give access to audiovisual media, and it names audio description and subtitles for deaf and hard-of-hearing viewers among the access services they must carry. Italy's transposition sets fines from €5,000 to €40,000. India's guidelines for OTT platforms, issued on 6 February 2026, give platforms 36 months to add accessibility features to their content. In the US, the ADA Title II web rule (WCAG 2.1 AA, which includes audio description) applies to large public bodies, including public universities, from 26 April 2027.

| Buyer | Why they pay |
|---|---|
| US public universities | ADA Title II deadline; large lecture archives; some already buy machine description |
| EU e-commerce, banks and transport with video | European Accessibility Act |
| Italian public bodies and private providers in scope | Stanca Law and D.Lgs. 82/2022 fines |
| Broadcasters and OTT platforms in the EU, Italy and India | access-service rules; Hindi and Italian; unreleased content that can't leave the building, so on-premises open models matter |
| MOOC and training platforms | reach: many viewers read at a low level or watch with the sound off |

What description costs today (list prices, not our measurements): 3Play Media lists $4.25 a minute for AI description with a human spot check and $18 for a voice artist; the University of Michigan lists $0.90 a minute for machine description and $6.65 to $14.70 for human description. A human describer needs about 20 hours to script and voice a one-hour programme (Media Access Australia).

Our cost is GPU time plus a person's review time, both measured: <pending: business.our_cost>. AI-only services are cheap too, so price is not our pitch. Our difference is extended description, five audiences from one analysis, a review workflow with an audit trail, and open models that can run on-premises. The pitch is coverage: reviewed description for the large share of video that has none today. ACB's 2025 proposal warns against text-to-speech description used "purely as a cost-saving measure", and we agree.

## What didn't work

<pending: negative.results>

## Honest scope

| Claim | Real | Simplified or not done |
|---|---|---|
| Description fits the pauses | Measured by a script that imports none of our checks, against W3C's human caption timings | Caption timings stand in for speech, so quiet speech outside captions can be missed |
| Human review | Every description and easy-read line is approved by a person; captions and translations pass automatic checks, and a random sample is checked by people | Our reviewers are not professional describers |
| Review tool for blind reviewers | Designed for it: keyboard only, live announcements, automatic accessibility tests pass (player 23 of 23, review app 6 of 6, including axe-core scans) | Not yet tested by a blind reviewer |
| Hindi and Italian | Back-translation shown to reviewers | Not a full professional language QA; native-speaker spot checks are <pending: native.checks> |
| "Usefulness" (E6) | An LLM answers questions from our description | A proxy, not a study with blind viewers |
| Timing check clip (E15) | Word boundaries from the speech synthesizer | Not a human hand label |
| Where it ran | Gemma 4 31B on AMD Token Factory | Whisper, the aligner, the voices and the metric models ran on our own workstation, not on AMD hardware; each evidence file records the device. Gemma 4 E4B (listening) is not on Token Factory, so the transcript cross-check and sound labels did not run |
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

## Licences and credits

Our code is MIT ([LICENSE](LICENSE)). Reused code keeps its original licence header; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Models, voices, datasets and clips are listed with their licences in [MODEL_LICENSES.md](MODEL_LICENSES.md). Test videos: W3C WAI [Web Accessibility Perspectives](https://www.w3.org/WAI/perspective-videos/) (linked as their terms ask; our versions of them are never published). Dev clips: NASA (courtesy NASA), Prelinger Archives (public domain), Sintel (© copyright Blender Foundation | www.sintel.org) and Big Buck Bunny ((c) copyright 2008, Blender Foundation / www.bigbuckbunny.org).

## Team

<pending: team.names>
