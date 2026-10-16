# Your steps, in order

We are not using a GPU droplet (no payment card; `docs/decisions.md` D-021). Gemma 4 31B runs on AMD Token Factory with your key, and everything else runs on this workstation. I run all the experiments. These are the steps only a person can do. The safe deadline is **18 Oct 2026, 15:30 IST**.

## Links
- Hackathon page: https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii
- lablab Discord: https://discord.gg/lablabai
- AMD Token Factory (your key's usage and limits): https://notebooks.amd.com/tokenfactory
- Live site: https://accesscast.vercel.app · Repo: https://github.com/Prashant-thakur77/AccessCast

## 1. Today: one Discord message (5 minutes)
Post in the ACT III channel (text in `docs/outreach.md`, first message). Ask:
- Does Gemma 4 31B through AMD Token Factory count as "Gemma on AMD Developer Cloud" for the Google prize?
- Is there a hosted MI300X notebook or pod for teams that can't add a card?
- Token Factory's Gemma-4-31B-IT often answers "no available workers": is that known?

Tell me what they answer. If they offer a GPU, I switch back to the droplet plan (`deploy/` is ready).

## 2. Rotate your keys (5 minutes, any time)
You pasted the Hugging Face token and the Token Factory key into chat. Make new ones, put them in `.env`, and delete the old ones.

## 3. Review the dev videos (10–20 minutes per minute of video, after I say the dev runs are done)
```
make review
```
Open http://127.0.0.1:8081, type your name, and approve, fix or reject each line (`?` shows the keys). Only approved lines reach the public site. Start with the clips I list; you don't have to do all of them.

## 4. Optional, but each one replaces a "not measured" with a number
- **E12 (two people, 30–45 minutes each):** one writes description from scratch, timed, and one reviews ours, timed. Instructions: `docs/people-tasks.md` §3. Without it, review time stays "not measured".
- **E6 questions (1 hour):** about 5 multiple-choice questions per W3C video, written from W3C's own transcript. Follow `eval/questions/README.md`.
- **Native speakers (20 minutes each):** a Hindi and an Italian speaker check a few lines in the review app.
- **Someone outside the team** watches the draft demo video and lists anything they didn't follow.

## 5. Submit on lablab.ai (20 minutes, when I say everything is in)
1. Every team member registered and on the team.
2. Paste the fields from `docs/lablab.md`.
3. Upload `docs/cover.png`, `docs/deck/deck.pdf`, and the demo video (upload `data/demo/accesscast_demo.mp4` to YouTube as unlisted and paste the link).
4. App URL: https://accesscast.vercel.app. Repo: https://github.com/Prashant-thakur77/AccessCast.
5. Track: **Create a New Kind of Experience**. Technologies: as listed in `docs/lablab.md`. Don't tick MI300X, ROCm or vLLM: we did not run them ourselves.
6. Before pressing submit, run `make submission-check`; it must say 0 failed.
