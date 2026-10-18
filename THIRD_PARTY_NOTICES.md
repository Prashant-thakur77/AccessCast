# Third-party notices

AccessCast is MIT-licensed. The libraries it installs are used under their own licences, listed below. Models, voices, datasets, clips, music and fonts are listed in `MODEL_LICENSES.md`.

## Python dependencies
Installed from PyPI under their own licences (see `uv.lock`). Notable: spaCy and `en_core_web_sm` (MIT), pydantic (MIT), FastAPI (MIT), httpx (BSD-3-Clause), jiwer (Apache-2.0), wordfreq (Apache-2.0 code; data CC BY-SA 4.0), textstat (MIT), NLTK (Apache-2.0; textstat uses it to read the CMU Pronouncing Dictionary, cmudict, which carries Carnegie Mellon University's BSD-style licence and is shipped with its README inside the public site's function bundle so the readability check runs there), webvtt-py (MIT), PySceneDetect (BSD-3-Clause), soundfile (BSD-3-Clause), pyannote.audio (MIT, diarization worker env `workers/diarize`).
