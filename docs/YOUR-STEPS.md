# Your steps, in order

Everything that doesn't need your accounts or other people is built, tested and pushed. These are the steps only you can do. Do them top to bottom. Each says how long it takes and what it unblocks. The safe deadline is **18 Oct 2026, 15:30 IST**.

## Step 1. Keys (10 minutes): unblocks everything
1. In the repo folder, create `.env` from the example: `cp .env.example .env`
2. Open `.env` and fill in:
   - `HF_TOKEN=` a Hugging Face read token (huggingface.co → Settings → Access Tokens).
   - `AMD_TF_API_KEY=` and `AMD_TF_BASE_URL=` from the AMD Token Factory console (notebooks.amd.com/tokenfactory).
   - `GPU_HOURLY_COST_USD=` the hourly price your droplet is actually billed (DigitalOcean's page listed 2.59 on 16 Oct).
3. While logged in to Hugging Face, open each page and click "Agree" if asked: `google/gemma-4-31B-it`, `google/gemma-4-E4B-it`, `openlanguagedata/flores_plus`, `ai4bharat/indictrans2-en-indic-1B`, `pyannote/speaker-diarization-community-1`, `ai4bharat/indic-parler-tts`.
4. Never paste keys into chat; the file stays on your machine (it is git-ignored).

## Step 2. The GPU droplet (15 minutes for you, then I take over)
1. Go to devcloud.amd.com, add a payment method, and add this SSH key: the contents of `~/.ssh/id_ed25519.pub`.
2. Create one droplet: **AMD Instinct MI300X × 1**, image **"vLLM Quick Start"**.
3. Tell me its IP address. (Or, if the console offers an API token, put it in `.env` as `DIGITALOCEAN_ACCESS_TOKEN=` and I will create, snapshot and destroy droplets myself.)
4. Copy `.env` to the droplet once I've cloned the repo there: `scp .env root@<ip>:/root/AccessCast/.env`

What I then run on the droplet (my estimate: 10–14 GPU hours in total, within the $100 credit; not measured):
```
bash deploy/droplet_bootstrap.sh     # images, Gemma 31B + E4B, workers, weights
bash deploy/run_session.sh m0        # health, Token Factory model list, image + audio smoke tests
bash deploy/run_session.sh e15       # ASR choice on dev data
bash deploy/run_session.sh dev       # all dev + adversarial clips; I look at drafts and fix prompts on DEV only
bash deploy/run_session.sh freeze    # prompts and code frozen before the test set
bash deploy/run_session.sh e01       # the headline, on the 10 W3C videos never used for tuning
bash deploy/run_session.sh core      # live attacks, serving, cost, determinism, offline, memory
bash deploy/run_session.sh ladder    # speed ladder on the MI300X
bash deploy/run_session.sh quality   # translation, easy-read, similarity
bash deploy/run_session.sh soak      # 4-hour soak while people review
```
A powered-off droplet still bills: when I say GPU work is done, snapshot it if you want, then **destroy** it.

## Step 3. E6 questions (1 hour, today, before the test run)
Someone writes about 5 multiple-choice questions per W3C video from W3C's own "Text Transcript with Description of Visuals", following `eval/questions/README.md`. This must happen before step 2's `e01` phase.

## Step 4. Review the dev videos (after `dev`, about 10–20 minutes per minute of video)
Run `make review`, open http://127.0.0.1:8081, type your name, and approve, fix or reject each line with the keyboard (`?` shows the keys). Nothing is published until a person approves it; the public site switches from the draft fixture to reviewed dev videos after this.

## Step 5. People for measured numbers (after the GPU runs)
- E12: two people, 30–45 minutes each (instructions in `docs/people-tasks.md` §3).
- E1 blind labels: one person, about 1 hour, using the sheet in `data/labels/`.
- Native Hindi and Italian speakers: about 20 minutes each, in the review app.
- If possible, a blind or low-vision tester.
- Someone outside the team watches the draft demo video and lists what they didn't follow.

## Step 6. Messages (5 minutes)
Send the Discord questions and the W3C email drafted in `docs/outreach.md`.

## Step 7. Submit on lablab.ai (20 minutes, after the results are in)
1. Make sure every team member is registered and on the team.
2. Paste the fields from `docs/lablab.md`.
3. Upload `docs/cover.png`, `docs/deck/deck.pdf` and the demo video. The video file is `data/demo/accesscast_demo.mp4`; upload it to YouTube (unlisted) and paste the link.
4. App URL: https://accesscast.vercel.app. Repo: https://github.com/Prashant-thakur77/AccessCast.
5. Track: **Create a New Kind of Experience**. Technologies: AMD ROCm, AMD Developer Cloud, AMD Instinct MI300X, Gemma, vLLM, Hugging Face. Do not tick Evolus.
6. Before you press submit, run `make submission-check`; it must say 0 failed.
