# AccessCast Judge Guide

The shortest route through the submission.

## Three-Minute Review
1. Watch the demo video: <pending: video.url>
2. Open the live player: <pending: site.url>. Pick "I can't see the screen", then "Italiano".
3. Open `/proof.html` and press "Run the attack". Watch Gemma's line get blocked.
4. Open the three key evidence files: [`evidence/e01_verifier_ab.json`](evidence/), [`evidence/e13_serving.json`](evidence/), [`evidence/e14_cost.json`](evidence/).
5. Optional, no GPU: `make demo-fixture`, then open http://127.0.0.1:8080/?audience=judge

## What To Inspect
- The "What the models decided" drawer on any video: the frames Gemma saw, the pause each line had to fit, Gemma's first draft, the checks that failed, each repair, and who approved it.
- A refused render next to a published one (`evidence/gallery/`).
- The review app, keyboard only (`make review`).
- [`evidence/public-claims.json`](evidence/public-claims.json) and `make claims-check`.

## Track Brief Map
| The brief asks | What we did | Fastest proof |
|---|---|---|
| The experience changes for at least two audiences | Five audience profiles in one player, switchable live on the same video | Player picker; `five-ways.html` |
| Explain what was created and what the models decided | Per-line decisions in a drawer and in `decisions.json` | Drawer; `reports/decisions.json` |
| Show how quality and consistency were controlled | Checks in code, Gemma repair, a person approves, render refused while anything waits | [`docs/rules.md`](docs/rules.md); gallery |
| Cost per experience | Gemma tokens per finished minute of video, from real call logs (no GPU dollars: D-021) | <pending: e14.tokens_per_minute> tokens |
| Who pays and why | Laws with deadlines, list prices next to our measured cost | README "Who pays" |

## Rubric Map
These labels do not pre-award points; judges keep full scoring authority.

| Criterion | What we did | Fastest proof |
|---|---|---|
| Application of Technology | Gemma 4 31B sees, writes, translates and repairs, served by AMD Token Factory; code checks every line | README "What runs on AMD" |
| Presentation | Plain-words demo video; live player that never sleeps | <pending: video.url> |
| Business Value | Named buyers and legal deadlines; GPU cost plus measured review time | README "Who pays" |
| Originality | Checks tied to the real audio timeline; five versions from one analysis; extended description only when needed | `docs/rules.md` |

## Model Selection
Gemma 4 31B does every vision, writing, translation and repair task. The planned comparison with a smaller Gemma 4 plus our checks (E3) needs our own GPU server, so it was not run (`docs/decisions.md` D-021). Sound labels come from a small non-Gemma audio classifier (AST), because Gemma 4 E4B, the Gemma model that listens, is not on Token Factory (D-022).

## Current Results
<pending: results.tables> — generated from `evidence/public-claims.json`.

## AMD Boundary
- **On AMD Token Factory:** Gemma 4 31B for every vision, writing, translation and repair call, the live attack page, and a non-Gemma judge for two evaluations.
- **Not on AMD:** Whisper, the aligner, the voices and the metric models ran on our own workstation; every evidence file records the device.
- **Not done:** we had no MI300X droplet (AMD Developer Cloud needs a payment card we did not have), so there are no MI300X serving, memory, soak or offline numbers. The droplet scripts are in `deploy/`.
- **Never leaves the machine:** the video, the review state and every intermediate file.

## Reproduce
```bash
make setup
make demo-fixture                 # no GPU
# only with an MI300X "vLLM Quick Start" droplet:
bash deploy/droplet_bootstrap.sh  # images, Gemma servers, worker env, model weights
make doctor
make run VIDEO=path/to/video.mp4
make review                       # approve lines (keyboard)
make render PROJECT=<sha12>
make submission-check
```

## Honest Scope
See [README.md#honest-scope](README.md#honest-scope).
