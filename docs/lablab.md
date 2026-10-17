# lablab.ai submission text (ready to paste)

**Title:** AccessCast: one video, five ways to watch

**Short description:** Blind, deaf, slow-reading, Hindi and Italian viewers each get their own version of the same video: Gemma 4 on AMD writes it, code checks every line, and a person approves it before anyone hears it.

**Long description:**

Most online video has no audio description, and many viewers can't use it as it is: people who can't see the screen, people who can't hear, people who need simpler words, and people who speak another language.

AccessCast takes one video and makes a version for each of them. Blind and low-vision viewers hear description placed in the pauses between dialogue, and when the pauses are too short the video holds a still frame while the description plays. Deaf viewers get captions with every word and the sounds between words. Viewers who need simpler words get easy-read captions and a mode that waits for them to finish reading. Hindi and Italian speakers get subtitles, a voice-over and their own description. All five are made from one analysis of the video, so they never disagree.

Gemma 4 31B, served by AMD Token Factory, looks at the frames and writes, translates and repairs. Code checks every line against the real audio timeline, a word budget, and rules against invented names, unsupported claims, sounds and instructions hidden in on-screen text. Lines that fail go back to Gemma with the failed checks. A person approves every description line, and the server refuses to render while any line is waiting.

On 10 W3C accessibility videos never used for tuning (Gemma 4 31B on AMD Token Factory): asked to simplify captions, Gemma alone kept every "not", "never" and "no" in 105 of 114 captions; the easy-read AccessCast published kept them in 114 of 114 and sent 7 to a person. On our own attack clips (not the test set), Gemma's easy-read dropped a time limit in 20 of 20 tries; the number check caught every one, and 0 attack outputs reached a viewer across 8 cases. On 1012 FLORES+ sentences per language, Gemma 4 31B translated Italian better than Opus-MT on both scores we used (COMET and chrF++); for Hindi it beat IndicTrans2 on COMET but lost on chrF++, and we report that loss.

Every Gemma call runs on AMD Token Factory (Gemma-4-31B-IT), checked against the model the server reports. Counted from our own logs, Token Factory answered 3,162 Gemma requests for us (3.0 million tokens) across 28 videos. Measured from our side: 17 tokens/s at the best concurrency, p95 13.9 s, and 41,818 Gemma tokens per finished minute for all five versions.

The European Accessibility Act has applied since 28 June 2025; India's OTT accessibility guidelines date from 6 February 2026; the US ADA Title II deadline for large public bodies is 26 April 2027. Most video still has no description. AccessCast makes reviewed versions practical for the rest: open models, five audiences from one analysis, and a person approves every description line. The model work is small: at a published list price for Gemma 4 31B, all five versions of one finished minute cost about $0.0053 of Gemma (an estimate), so what a customer pays for is review time. Our first customer is a US public university's accessibility office with an ADA deadline and years of undescribed video; broadcasters and streaming platforms in the EU, Italy and India come next.

What didn't work: our pre-registered headline test (description inside pauses) could not separate the arms, because the test videos have only 6 usable pauses in 9.3 minutes; we report it instead of re-tuning.

Live demo: https://accesscast.vercel.app/?audience=judge · Code: https://github.com/Prashant-thakur77/AccessCast · Judge guide: https://github.com/Prashant-thakur77/AccessCast/blob/main/JUDGES.md · Demo video: <pending: video.url>

**Track:** Create a New Kind of Experience

**Technologies:** AMD Token Factory, Gemma, Hugging Face. Tick AMD Developer Cloud only if the organisers confirm Token Factory counts as part of it. (Do not select Evolus. Do not tick MI300X, ROCm or vLLM: we did not run them ourselves.)

**Cover image:** `docs/cover.png` (1920×1080). **Slide deck:** `docs/deck/deck.pdf`. **Demo platform:** Web. **App URL:** https://accesscast.vercel.app
