# Demo video script

Generated from `docs/demo/storyboard.json` by `scripts/storyboard_to_script.py`; the video is built from the same file by `scripts/make_demo_video.py`. Every number is filled from `evidence/public-claims.json`. No W3C video appears: the footage is NASA (Life in the Universe, the eclipse animation), the Blender Foundation's Sintel trailer (CC BY 3.0) and our own pages. Narration is synthetic speech (Kokoro, voice af_heart), and the video has burned-in captions.

| Picture | Words (read aloud) |
|---|---|
| The problem, over stock footage of a family watching TV (Pexels): how much video is uploaded | Every minute, more than 500 hours of new video go up on YouTube. Most of it only works if you can see it, and hear it. |
| The problem: people who are blind (stock footage of a blind man reading Braille; the picture fades to black) | 43.3 million people are blind. They need to hear what is on screen. |
| A real person's words: Erika Wolf (American Council of the Blind, Braille Forum, February 2021), over stock footage of a blind man walking (Pexels) | Erika Wolf, writing for the American Council of the Blind, remembers leaving shows not having any inkling of what really took place. |
| The problem: people with disabling hearing loss (stock footage of people signing) | 430 million live with disabling hearing loss. They need captions that also say what sounds. |
| The problem: adults who read at the lowest levels (stock footage of an older man reading his phone) | 26% of adults read at the lowest levels. They need simpler words, at a slower pace. And many people need the video in their own language. |
| Why most video is left out: the time and price of doing it by hand (stock footage of a video editor at night) | Doing this by hand takes about 20 hours of work for one hour of TV, and costs $15 to $75 a minute. So most video never gets it. |
| Black screen, "Close your eyes." The NASA clip's own sound only. | (the clip's own sound, no narration) |
| Card: "This is Hubble's famous photograph." / But what does it show? | He said: this is Hubble's famous photograph. But if you can't see the screen, you never find out what it shows. |
| Black screen, "The same video, with AccessCast." The extended description version's sound (machine draft, labelled). | (the clip's own sound, no narration) |
| "Open your eyes." The extended render itself: Hubble Ultra Deep Field, each description line as text, "picture held" while it is read. | (the clip's own sound, no narration) |
| Card: No pause to speak in? / The picture holds. | There was no pause in his speech, so AccessCast held the picture while the description was read. Gemma 4, running on AMD, wrote every word, and code checked it. |
| 3D animation: one video card splits into five, each labelled with its audience | This is AccessCast. One video, made for every viewer: for people who can't see the screen, people who can't hear, people who want simpler words, and for people who speak Hindi, Italian, Spanish, French or Portuguese. |
| The live site's home page (step `page`) | On our site, every viewer picks what they need, and the same video plays for them. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `blind`) | If you can't see the screen, a voice describes what happens, in the pauses. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `deaf`) | If you can't hear, captions show what is said, and the sounds. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `easy`) | If reading is hard, the same lines, in simpler words. |
| The live site's "Same clip, five ways" page on the Sintel trailer (labelled draft) (step `hi`) | And in Hindi, Italian, Spanish, French and Portuguese, each with its own voice. Listen. |
| The NASA clip's Hindi version: its own Hindi voice and subtitles (machine draft, labelled) | (the clip's own sound, no narration) |
| The NASA clip's Italian version: its own Italian voice and subtitles (machine draft, labelled) | (the clip's own sound, no narration) |
| The NASA clip's Spanish version: its own voice and subtitles (machine draft, labelled) | (the clip's own sound, no narration) |
| The NASA clip's French version: its own voice and subtitles (machine draft, labelled) | (the clip's own sound, no narration) |
| The NASA clip's Portuguese version: its own voice and subtitles (machine draft, labelled) | (the clip's own sound, no narration) |
| How it works at a glance: seven steps light up in turn (Gemma steps marked AMD, the check marked code) | How does it work? Whisper listens. Gemma 4 31B, on AMD, looks at the frames and writes. Code checks every line, and Gemma repairs what fails. A person approves. Then every version is made. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-listen`) | Here is that NASA clip, step by step. Whisper writes down every word, and pins each one to the moment it is said. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-pauses`) | The code measures the pauses between the words. This clip is mostly talk, so there are only a few. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-look`) | Gemma looks at still frames from each scene, and lists only what it can see. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-write`) | From that list alone, Gemma writes one line, inside a word budget: a man in a NASA polo shirt speaks to the camera. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-check`) | Code checks it, and stops it. A blind viewer can already hear him speak, so it wastes the pause. The model never decides whether its own line is good enough. |
| The live site's "How it works" page on the NASA clip, one step at a time (step `s-repair`) | The line goes back to Gemma with the exact rule it broke. The new line: he looks at the camera. The code checks again, and it passes. |
| The review app: frames Gemma saw, checks, repair history, keyboard approval | Reviewers work in our review app by keyboard alone, with the frames, the checks and every repair in front of them. |
| AccessCast Studio: a video dropped in, every stage listed as it runs | Anyone can drop in their own video, and watch every step run. |
| Animation: Gemma's real answer is stopped at the code-check gate for dropping a number, its repair passes to the viewer (both texts from the recorded attack test) | This is the rule at the heart of AccessCast: the model proposes, code decides. An answer that breaks a rule is sent back, with the reason. Only an answer that passes every check reaches a viewer. |
| The live site's proof page: "Run the attack" pressed live, then each try and the tally (step `pressed`) | We attack it on purpose. We ask Gemma to simplify: press the button three times within ten seconds. On our site, anyone can run this live. |
| The live site's proof page: "Run the attack" pressed live, then each try and the tally (step `result`) | An answer that drops the ten seconds is blocked, and never reaches a viewer. In our recorded test, Gemma dropped it in 20 of 20 tries, and our checks blocked every one. |
| The live site's proof page: a caption typed in "Try your own caption", then the three live versions and the checks (step `page`) | Or type your own caption, and watch it happen live. |
| The live site's proof page: a caption typed in "Try your own caption", then the three live versions and the checks (step `result`) | In about half a minute, Gemma on AMD made the easy-read, Hindi and Italian versions. Our number check stopped one Italian line that turned 5 pm into 17:00, and the repair passed. |
| Bars: easy-read captions that kept every negation, Gemma alone against AccessCast as published | On ten W3C accessibility videos we never tuned on, Gemma alone kept every not in 105 of 114 easy-read captions. What AccessCast published kept 114 of 114. |
| res_tr | Against specialist translation models, Gemma won on one of our two scores in all five languages. On the other score it lost for Hindi, French and Portuguese, and we report that. |
| Counters from our own call logs: Gemma requests answered by AMD Token Factory, tokens, videos; tokens and estimated cost per finished minute | Every Gemma call runs on AMD's Token Factory. From our own logs: 3,730 requests and 3.5 million tokens, across 28 videos. One finished minute of the five versions we measured costs about $0.0053 of Gemma, at list price. |
| Three law dates: EU, India, US | The law already asks for this: in Europe since 28 June 2025, in India since 6 February 2026, and for US public universities from 26 April 2027. They pay per finished minute, and their own staff approve every line. |
| Closing line over stock footage of a family watching TV, with the links and footage credits | AccessCast. Every viewer, the same video. |

## How it is made
- Motion scenes: `docs/demo/motion/index.html`, rendered frame by frame with a transparent background (`scripts/render_motion.mjs`) and composited over real footage.
- Opening: `scripts/make_hook_scenes.py`, from the NASA clip's draft render and its extended timeline.
- Screen recordings: `scripts/record_demo.mjs` against the live site (https://accesscast.vercel.app), with a time mark at each step so narration lines up with the picture.
- Editing: scenes crossfade; each narration line keeps only a short pause; a soft tone made with ffmpeg (no music, so no licence) sits under the narration and fades out where a video's own sound plays.
- Export: H.264, AAC, two-pass loudness to −16 LUFS.
