#!/usr/bin/env bash
# The demo's "close your eyes" scene: 14 s of a NASA dev clip's original sound, then the same 14 s with AccessCast's
# description (a watermarked draft render of a copy of the project under the prototype-auto policy; drafts only,
# labelled "machine draft, before review" on screen). Writes data/demo/ab.mp4.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC=projects/_dev/beecab6041ea; P=projects/_demo_draft/beecab6041ea; T=$(mktemp -d)
FB=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf; F=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
rm -rf projects/_demo_draft && mkdir -p projects/_demo_draft && cp -r "$SRC" projects/_demo_draft/
rm -rf "$P/review" "$P/render"
ACCESSCAST_PROJECTS_DIR=projects/_demo_draft ACCESSCAST_REVIEW_POLICY=prototype-auto uv run python -c "
from pathlib import Path
from accesscast.config import load_settings
from accesscast.project import Project
from accesscast.pipeline import open_run, stage_review_init
from accesscast.render_stage import render_all
run = open_run(load_settings(), Project(Path('$P')))
stage_review_init(run)
render_all(run, mode='draft', versions=['blind.en'])"
ffmpeg -loglevel error -y -f lavfi -i color=c=black:s=1920x1080:r=30:d=14 -t 14 -i "$SRC/media/source.mp4" -map 0:v -map 1:a \
  -vf "drawtext=fontfile=$FB:text='Close your eyes.':x=(w-text_w)/2:y=420:fontsize=80:fontcolor=white,drawtext=fontfile=$F:text='This is a NASA video, as a blind viewer hears it today.':x=(w-text_w)/2:y=560:fontsize=44:fontcolor=0xc9d3ea" \
  -c:v libx264 -crf 22 -pix_fmt yuv420p -c:a aac -ar 48000 -ac 2 -shortest "$T/a.mp4"
ffmpeg -loglevel error -y -f lavfi -i color=c=0x0f1b33:s=1920x1080:r=30:d=14 -t 14 -i "$P/render/blind.en.mp4" -map 0:v -map 1:a \
  -vf "drawtext=fontfile=$FB:text='The same 14 seconds, with AccessCast.':x=(w-text_w)/2:y=420:fontsize=72:fontcolor=white,drawtext=fontfile=$F:text='Description written by Gemma 4 on AMD and checked in code (machine draft, before review).':x=(w-text_w)/2:y=560:fontsize=38:fontcolor=0xffc857" \
  -c:v libx264 -crf 22 -pix_fmt yuv420p -c:a aac -ar 48000 -ac 2 -shortest "$T/b.mp4"
printf "file '%s'\nfile '%s'\n" "$T/a.mp4" "$T/b.mp4" > "$T/l.txt"
ffmpeg -loglevel error -y -f concat -safe 0 -i "$T/l.txt" -c copy data/demo/ab.mp4
echo "data/demo/ab.mp4"
