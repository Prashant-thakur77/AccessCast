# lablab.ai submission text (ready to paste)

**Title:** AccessCast: one video, five ways to watch

**Short description:** <pending: e1.headline>

**Long description:**

Most online video has no audio description, and many viewers can't use it as it is: people who can't see the screen, people who can't hear, people who need simpler words, and people who speak another language.

AccessCast takes one video and makes a version for each of them. Blind and low-vision viewers hear description placed in the pauses between dialogue, and when the pauses are too short the video holds a still frame while the description plays. Deaf viewers get captions with speakers and sounds. Viewers who need simpler words get easy-read captions and a mode that waits for them to finish reading. Hindi and Italian speakers get subtitles, a voice-over and their own description. All five are made from one analysis of the video, so they never disagree.

Gemma 4 does the model work on an AMD Instinct MI300X: Gemma 4 31B looks at the frames and writes, translates and repairs; Gemma 4 E4B listens to check the transcript and label sounds. Code checks every line against the real audio timeline, a word budget, and rules against invented names, unsupported claims, sounds and instructions hidden in on-screen text. Lines that fail go back to Gemma with the failed checks. A person approves every description line, and the server refuses to render while any line is waiting.

<pending: lablab.results>

<pending: lablab.amd>

<pending: lablab.business>

What didn't work: <pending: negative.short>

Live demo: https://accesscast.vercel.app/?audience=judge · Code: https://github.com/Prashant-thakur77/AccessCast · Judge guide: https://github.com/Prashant-thakur77/AccessCast/blob/main/JUDGES.md · Demo video: <pending: video.url>

**Track:** Create a New Kind of Experience

**Technologies:** AMD ROCm, AMD Developer Cloud, AMD Instinct MI300X, Gemma, vLLM, Hugging Face. (Do not select Evolus.)

**Cover image:** `docs/cover.png` (1920×1080). **Slide deck:** `docs/deck/deck.pdf`. **Demo platform:** Web. **App URL:** https://accesscast.vercel.app
