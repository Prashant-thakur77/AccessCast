# lablab.ai submission text (ready to paste)

**Title:** AccessCast: one video, made for every viewer

**Short description:** Blind, deaf and slow-reading viewers, and people who speak Hindi, Italian, Spanish, French or Portuguese, each get their own version of the same video: Gemma 4 on AMD writes it, code checks every line, and a person approves it before anyone hears it.

**Long description** (fits the form's character limit):

Most online video has no audio description, and many viewers can't use it as it is. AccessCast takes one video and makes a version for each viewer: description in the pauses for blind viewers (the video holds a frame when a pause is too short), captions with sounds for deaf viewers, easy-read captions, and subtitles and voice-over in Hindi, Italian, Spanish, French and Portuguese. Every version comes from one analysis of the video.

Gemma 4 31B on AMD Token Factory looks at the frames and writes, translates and repairs. Code checks every line against the audio timeline, a word budget and rules against invented names and unsupported claims; failed lines go back to Gemma. A person approves every description line before the public hears it. On the site, one video is reviewed by a person; the other two are labelled drafts.

On 10 W3C videos never used for tuning, Gemma alone kept every "not", "never" and "no" in 105 of 114 easy-read captions; what AccessCast published kept 114 of 114 and sent 7 to a person. On our attack clips, Gemma dropped a time limit in 20 of 20 tries; the number check caught every one, and 0 attack outputs reached a viewer. On the live site, anyone can run the attack, type a caption or describe a picture, and watch Gemma on AMD write while our checks test each line.

Token Factory answered 3,825 Gemma requests for us (3.6 million tokens). Gemma work for five versions of one finished minute costs about $0.0053 (an estimate), so the real cost is a person's review time.

The European Accessibility Act has applied since 28 June 2025, and the US ADA Title II deadline is 26 April 2027. Our first target customer: a US public university's accessibility office with years of undescribed video.

What didn't work: our pre-registered pause test could not separate the arms (only 6 usable pauses in 9.3 minutes); we report it.

Live: https://accesscast.vercel.app · Code: https://github.com/Prashant-thakur77/AccessCast

**Demo video** (its own field in the form): <pending: video.url>

**Track:** Track 4, Create a New Kind of Experience (by partner Vibe Generation). It is the only track brief AccessCast fits; the other three (industry, health, commerce) are judged on their own briefs.

**Partner prize:** Google (Gemma): every model call is Gemma 4 31B. Not Evolus (we do not build on Evolus).

**Technology tags:** Token Factory, Gemma, AMD Developer Cloud. The event FAQ says the event is hosted on notebooks.amd.com/tokenfactory and needs only a Token Factory key, so Token Factory is the event's AMD platform. (Do not tick AMD ROCm, MI300X or vLLM: we did not run them ourselves.)

**Cover image:** `docs/cover.png` (1920×1080). **Slide deck:** `docs/deck/deck.pdf`. **Demo platform:** Web. **App URL:** https://accesscast.vercel.app
