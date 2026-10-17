# AccessCast Judge Guide

The shortest route through the submission.

## Three-Minute Review
1. Watch the demo video: <pending: video.url>
2. Open the live player: https://accesscast.vercel.app/watch.html. Pick "I can't see the screen", then "Italiano".
3. Open [`/proof.html`](https://accesscast.vercel.app/proof.html) and press **Run the attack**. It asks Gemma 4 31B on AMD Token Factory five times, live (usually under a minute), to simplify "press the button 3 times within 10 seconds", and shows each answer, the check that blocked it, and Gemma's repair. Below it is the recorded E11 run of 20 tries. Then write your own sentence in **Try your own caption**: Gemma makes the easy-read, Hindi and Italian versions live on AMD, and the page shows which of our checks stopped any answer. Put a number, a "not" or a name in it.
4. Open the three key evidence files: [`evidence/e01_verifier_ab.json`](evidence/), [`evidence/e13_serving_tokenfactory.json`](evidence/e13_serving_tokenfactory.json), [`evidence/e14_cost.json`](evidence/).
5. Optional, no GPU: `make demo-fixture`, then open http://127.0.0.1:8080/?audience=judge

## What To Inspect
- The "What the models decided" drawer on any video: the frames Gemma saw, the pause each line had to fit, Gemma's first draft, the checks that failed, each repair, and who approved it.
- A public render refused because no person has approved the lines yet, next to the labelled draft the same project is allowed (`evidence/gallery/refused_public_render.json`).
- The review app, keyboard only (`make review`).
- [`evidence/public-claims.json`](evidence/public-claims.json) and `make claims-check`.

## Track Brief Map
| The brief asks | What we did | Fastest proof |
|---|---|---|
| The experience changes for at least two audiences | Five audience profiles in one player, switchable live on the same video | Player picker; `five-ways.html` |
| Explain what was created and what the models decided | Per-line decisions in a drawer and in `decisions.json` | Drawer; `reports/decisions.json` |
| Show how quality and consistency were controlled | Checks in code, Gemma repair, a person approves, render refused while anything waits | [`docs/rules.md`](docs/rules.md); gallery |
| Cost per experience | Gemma tokens per finished minute of video, from real call logs (no GPU dollars: D-021) | 41,818 tokens |
| Who pays and why | Laws with deadlines, list prices next to our measured cost | README "Who pays" |

## Rubric Map
These labels do not pre-award points; judges keep full scoring authority.

| Criterion | What we did | Fastest proof |
|---|---|---|
| Application of Technology | Gemma 4 31B sees, writes, translates and repairs, served by AMD Token Factory; code checks every line | README "Gemma 4 on AMD" |
| Presentation | Plain-words demo video; live player that never sleeps | <pending: video.url> |
| Business Value | Named buyers and legal deadlines; GPU cost plus measured review time | README "Who pays" |
| Originality | Checks tied to the real audio timeline; five versions from one analysis; extended description only when needed | `docs/rules.md` |

## Model Selection
Gemma 4 31B does every vision, writing, translation and repair task. The planned comparison with a smaller Gemma 4 plus our checks (E3) needs our own GPU server, so it was not run (`docs/decisions.md` D-021). Sound labels come from a small non-Gemma audio classifier (AST), because Gemma 4 E4B, the Gemma model that listens, is not on Token Factory (D-022).

## Current Results
See README "Results": description in the pauses (E1, a negative result), what the checks caught (E5, E11), translation against specialist models (E4, including a Hindi loss on one score), and the AMD numbers (E13, E14). Every number there comes from `evidence/public-claims.json`.

## AMD Boundary
- **On AMD Token Factory:** Gemma 4 31B for every vision, writing, translation and repair call, the live attack page, and a non-Gemma judge for two evaluations. Counted from our logs: 3,162 Gemma requests answered and 3,002,402 tokens, across 28 videos (`evidence/amd_usage.json`).
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
