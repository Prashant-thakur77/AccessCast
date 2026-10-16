# E12: two people, about 40 minutes each (this is now the headline experiment)

E1 could not separate the arms on the W3C videos (they have almost no pauses; see README "What didn't work"). The pre-registered next headline is E12: how much person-time AccessCast saves. Two people each do two short tasks in the review app. The app times active work by itself (idle over 60 seconds is not counted). Nothing is published until these reviews are done, and the reviewed clips become the public site's videos.

The two clips (both under one minute, already processed):
- **M1 = NASA "Plane"** (music, no speech): project `8af59806d6b6`, empty copy `8af598scratc`
- **M2 = Blender "Sintel" trailer** (dialogue): project `cbf141ec3213`, empty copy `cbf141scratc`

## Start the app
```
ACCESSCAST_PROJECTS_DIR=projects/_people make review
```
Open http://127.0.0.1:8081, type your name in the box at the top (use `p1` or `p2` exactly), and press `?` to see the keys.

## Person 1 (`p1`)
1. **Review M1:** open `8af59806d6b6`. For every description line: listen (key `h`), then approve (`a`), fix the text and approve, or reject (`r`). Do the captions and translations it lists too. Press "Mark review complete" at the end.
2. **Write M2 from scratch:** open `cbf141scratc`. The description lane is empty. Watch the video and add your own description lines in the pauses (press `i`, or the "Add a description line" button: it starts where the video is now; then approve your line with `a`). Write what a blind viewer needs. Press "Mark review complete" at the end.

## Person 2 (`p2`)
1. **Write M1 from scratch:** open `8af598scratc` and add description lines as above.
2. **Review M2:** open `cbf141ec3213` and review every line as above.

## Rules
- Don't look at the other person's clip before your own turn on it.
- Work at your normal pace; breaks are fine (idle time is not counted).
- If only one person is available, Person 1 does both tasks and we say so next to the result.

When both are done, tell Claude "E12 done"; it runs `eval/e12_person_time.py` and publishes the reviewed clips.
