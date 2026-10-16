# Demo video script (target 3 min 30 s)

Plain words, short sentences, one number on screen at a time. Every number shown or spoken comes from `evidence/public-claims.json`; before recording, check each one by hand against that file. No W3C video appears anywhere in this video: all footage is our fixture, our synthetic adversarial clips, NASA, Prelinger or Blender material. The video itself has burned-in captions, and an audio-described version made by AccessCast is published next to it.

Before recording, someone outside the team watches a draft and lists anything they didn't follow. Fix all of it.

| Time | Picture | Words (read aloud) |
|---|---|---|
| 0:00–0:12 | Black screen. Eight seconds of a dev clip's audio only (NASA explainer). Then the same eight seconds again, now with AccessCast's description in the pauses. | "43.3 million people are blind. For many of them, this is what a video sounds like. … And this is the same video with AccessCast." |
| 0:12–0:30 | One number at a time on a plain background: the E1 headline; then GPU cost and review minutes per minute of video. | "We tested on ten W3C accessibility videos that we never used for tuning." Then read the headline sentence exactly as in `public-claims.json` (`e1.headline`). Then: "<pending: e14.bundle_cost_sentence>" |
| 0:30–1:20 | The player, "Same 20 seconds, five ways": blind (standard, then extended), deaf (captions with sounds), simpler words (the video pauses until the viewer is ready), Hindi, Italian. | "One video. Five ways to watch. If you can't see the screen, the description fits in the pauses. If there's no room, the video waits. If you can't hear, the captions show who speaks and what sounds. Simpler words, at your pace. And Hindi and Italian, with their own voice and description. It's all made from one analysis, so the versions never disagree." |
| 1:20–2:00 | The "What the models decided" drawer on one line where a real Gemma 4 31B draft (from a recorded dev-set run, never the canned fixture) failed a check; the check fires, Gemma repairs it, a reviewer approves with the keyboard. Then the render button is refused while one line is still waiting. | "Gemma writes. Code checks." Then describe the recorded failure in plain words, from the run's decisions.json: "<pending: demo.real_failure_sentence>". Then: "Gemma fixed it. A person approved it, with the keyboard. And nothing goes out while a line is still waiting for a person." |
| 2:00–2:25 | `/proof`, "Run the attack", on the case with the highest measured failure rate in E11: N live tries and the tally. | Written only after E11 has run, from its numbers: "<pending: e11.proof_sentence>" |
| 2:25–2:50 | AMD: Gemma 4 31B on AMD Token Factory, E13 client-side p95 and tokens per second, Gemma tokens per finished minute. | "Gemma 4 runs on AMD's Token Factory." Then one sentence per number, read from `public-claims.json`: "<pending: amd.voiceover>" |
| 2:50–3:15 | Who pays: the European Accessibility Act date, Italy's fines, India's OTT guidelines, the US ADA Title II deadline; our cost (GPU plus review time) next to today's list prices, labelled as list prices. | "The law already asks for this. <pending: business.voiceover> Most video still has no description at all. AccessCast makes reviewed versions practical for the rest of it." |
| 3:15–3:30 | One negative result; the links. | "What didn't work: <pending: negative.voiceover>. Everything, including the failures, is in the repo." |

## Recording notes
- Screen recordings come from the live site (https://accesscast.vercel.app) and the review app, recorded with Playwright at 1920×1080, 30 fps.
- Narration: a person's voice if a team member records it; otherwise Kokoro `af_heart`, disclosed in the video's description ("narration voiced by synthetic speech").
- Captions burned in at 42 characters per line or fewer, 2 lines.
- Export: H.264, AAC, −16 LUFS (measured with the same `ebur128` check as RN003).
