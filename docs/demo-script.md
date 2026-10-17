# Demo video script

Generated from `docs/demo/storyboard.json` by `scripts/storyboard_to_script.py`; the video is built from the same file by `scripts/make_demo_video.py`. Every number is filled from `evidence/public-claims.json`. No W3C video appears: the footage is NASA (Life in the Universe, the eclipse animation), the Blender Foundation's Sintel trailer (CC BY 3.0) and our own pages. Narration is synthetic speech (Kokoro, voice af_heart), and the video has burned-in captions.

| Picture | Words (read aloud) |
|---|---|
| The problem, over NASA footage of the Hubble Ultra Deep Field (dimmed): how much video is uploaded | Every minute, YouTube receives more than 500 hours of new video. |
| The problem: people who are blind | 43.3 million people are blind. To follow a video, they need to hear what is on screen. |
| The problem: people with disabling hearing loss | 430 million people live with disabling hearing loss. They need captions that also say what sounds. |
| The problem: adults who read at the lowest levels | And 26% of adults read at the lowest levels. They need simpler words, at a slower pace. Others need the video in their own language. |
| Why most video is left out: the time and price of doing it by hand | Doing this by hand takes about 20 hours of work for one hour of TV, and costs $15 to $75 a minute. So most video never gets it. |
| Black screen, "Close your eyes." The NASA clip's own sound only. | (the clip's own sound, no narration) |
| Card: "This is Hubble's famous photograph." / But what does it show? | He said: this is Hubble's famous photograph. If you can't see the screen, you never find out what it shows. |
| Black screen, "The same video, with AccessCast." The extended description version's sound (machine draft, labelled). | (the clip's own sound, no narration) |
| "Open your eyes." The extended render itself: Hubble Ultra Deep Field, each description line as text, "picture held" while it is read. | (the clip's own sound, no narration) |
| Card: No pause to speak in? / The picture holds. | There was no pause in his speech, so AccessCast held the picture while the description was read. Every word was written by Gemma, and checked by code. |
| 3D animation: one video card splits into five, each labelled with its audience | This is AccessCast. One video, made into five: for people who can't see the screen, people who can't hear, people who want simpler words, and for Hindi and Italian speakers. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `blind`) | If you can't see the screen, a voice describes what happens in the pauses. Where there is no pause, a second version holds the picture. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `deaf`) | If you can't hear, captions show what is said, and the sounds. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `easy`) | If reading is hard, the same lines in simpler words. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `hi`) | In Hindi, with subtitles and a Hindi voice. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `it`) | And in Italian. |
| How it works at a glance: seven steps light up in turn (Gemma steps marked AMD, the check marked code) | How does it work? Whisper listens. Gemma 4 31B, running on AMD, looks and writes. Code checks every line, and Gemma repairs what fails. A person approves. Then all five versions are made. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-listen`) | Here is one real clip, step by step. First, Whisper writes down every word, and a second model pins each word to the moment it is said. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-pauses`) | Then the code measures the pauses between the words. This clip is mostly talk, so there are only a few. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-look`) | Gemma 4 31B, on AMD, looks at still frames from each scene, and lists only what it can see. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-write`) | From that list, and nothing else, Gemma writes one line, inside a word budget. Here it wrote: a man in a NASA polo shirt speaks to the camera. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-check`) | Code checks the line. This one is stopped: it describes speech, and a blind viewer can already hear him speak. The model never decides whether its own line is good enough. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-repair`) | The line goes back to Gemma with the exact rule it broke. Gemma rewrites it: he looks at the camera. The code checks again, and it passes. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-fit`) | A line that fits a pause is spoken in it. Where there is no pause, the extended version holds the picture while the line is read. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-person`) | Then a person decides. Every description line waits for a reviewer, and nothing is published while a line is waiting. |
| The review app: frames Gemma saw, checks, repair history, keyboard approval | Reviewers use our review app with the keyboard alone. They see the frames Gemma saw, the checks, and every repair, and they approve, edit or reject each line. |
| AccessCast Studio: a video dropped in, every stage listed as it runs | And anyone can drop in their own video, and watch every step run, live. |
| The live site's proof page: "Run the attack" pressed live, then each try and the tally (step `pressed`) | We ask Gemma to simplify: press the button three times within ten seconds. On our site, anyone can run this attack live. |
| The live site's proof page: "Run the attack" pressed live, then each try and the tally (step `result`) | Every answer is checked as it arrives. An answer that drops the ten seconds is blocked and never reaches a viewer. In our recorded test, Gemma dropped it in 20 of 20 tries, and our checks blocked every one. |
| Bars: easy-read captions that kept every negation, Gemma alone against AccessCast as published | On ten W3C accessibility videos we never tuned on, Gemma alone kept every not in 105 of 114 easy-read captions. What AccessCast published kept 114 of 114. |
| Card: Translation, 1012 test sentences per language / Italian: Gemma beat Opus-MT on both scores / Hindi: Gemma won on one score, lost on the other | For translation, Gemma beat a standard Italian model on both of our scores. For Hindi it won on one score and lost on the other, and we report that loss. |
| Counters from our own call logs: Gemma requests answered by AMD Token Factory, tokens, videos; tokens and estimated cost per finished minute | Every Gemma call runs on AMD's Token Factory. Counted from our own logs: 3,162 requests and 3.0 million tokens, across 28 videos. One finished minute, in all five versions, takes about 41,818 Gemma tokens: about $0.0053 at a published list price. |
| Three law dates: EU, India, US | The law already asks for this: in Europe since 28 June 2025, in India since 6 February 2026, and for US public universities from 26 April 2027. They pay per finished minute, and their own staff approve every line. |
| Card: What didn't work / Our first test needed pauses. / These videos barely have any. | What didn't work: our first test measured description inside pauses, and our test videos have almost none. It could not show a difference, and we report it anyway. |
| Closing line over NASA footage of Earth, with the links | AccessCast. Every viewer, the same video. Everything, including what didn't work, is in the repo. |

## How it is made
- Motion scenes: `docs/demo/motion/index.html`, rendered frame by frame with a transparent background (`scripts/render_motion.mjs`) and composited over real footage.
- Opening: `scripts/make_hook_scenes.py`, from the NASA clip's draft render and its extended timeline.
- Screen recordings: `scripts/record_demo.mjs` against the live site (https://accesscast.vercel.app), with a time mark at each step so narration lines up with the picture.
- Export: H.264, AAC, two-pass loudness to −16 LUFS.
