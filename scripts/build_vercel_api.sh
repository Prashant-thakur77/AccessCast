#!/usr/bin/env bash
# Build the live proof API as a Vercel Python function inside site/ (D-028): the API code plus a pruned copy of its
# dependencies (spaCy + en_core_web_sm, wordfreq data for en/hi/it only, no tests or caches, stripped binaries) so the
# function fits Vercel's 250 MB limit. The Token Factory key lives in Vercel's environment settings, never in files.
set -euo pipefail
cd "$(dirname "$0")/.."
V=site/api/_vendor
T=$(mktemp -d)
uv venv -q -p 3.12 "$T/venv"
VIRTUAL_ENV="$T/venv" uv pip install -q fastapi pydantic httpx pyyaml numpy wordfreq textstat python-dotenv \
  "spacy>=3.8,<3.9" \
  "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
rm -rf "$V"; mkdir -p "$V"
cp -r "$T/venv/lib/python3.12/site-packages/." "$V/"
( cd "$V"
  rm -rf pip* setuptools* _distutils_hack pygments* uv* _virtualenv*
  find . -name "__pycache__" -type d -prune -exec rm -rf {} +
  find . -path "*/tests" -type d -prune -exec rm -rf {} +
  ( cd wordfreq/data && ls | grep -v -E "^(large_en|large_it|small_en|small_hi|small_it)\.msgpack\.gz$" | xargs rm -f )
  find . -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true )
rsync -a --exclude "__pycache__" --exclude "player/static" --exclude "review/static" src/accesscast "$V/"
# textstat (ER009) needs NLTK's cmudict; ship it, since the function cannot download at run time
"$T/venv/bin/python" -c "import nltk; nltk.download('cmudict', download_dir='$V/nltk_data', quiet=True)"  # keeps the unzipped folder: textstat looks it up with nltk.data.find
du -sh "$V" | cut -f1
