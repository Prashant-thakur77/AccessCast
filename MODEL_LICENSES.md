# Models, voices, datasets, clips and fonts

Every item is listed here with its licence and link **before** it is used. No non-commercial weights or voices anywhere in the product.

## Models
| Model | Role | Licence | Link | Status |
|---|---|---|---|---|
| google/gemma-4-31B-it | evidence, scene judge, description, easy-read, translation, repair | Apache-2.0 | https://huggingface.co/google/gemma-4-31B-it | planned |
| google/gemma-4-E4B-it | ASR cross-check, sound events | Apache-2.0 | https://huggingface.co/google/gemma-4-E4B-it | planned |
| google/gemma-4-26B-A4B-it | E3 ablation only | Apache-2.0 | https://huggingface.co/google/gemma-4-26B-A4B-it | planned |
| openai/whisper-large-v3 / -turbo | word timing (E15 decides) | MIT | https://huggingface.co/openai/whisper-large-v3 | planned |
| Silero VAD | speech / no speech | MIT (LICENSE file checked 16 Oct 2026) | https://github.com/snakers4/silero-vad | planned |
| hexgrad/Kokoro-82M | English description voice `af_heart`; hi `hf_alpha`, it `if_sara` | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M | planned |
| ResembleAI Chatterbox Multilingual | Hindi/Italian voice (adds an inaudible watermark — disclosed in the player) | MIT | https://github.com/resemble-ai/chatterbox | planned |
| spaCy en_core_web_sm 3.8.0 | English rule NLP (lemmas, POS, names) | MIT | https://github.com/explosion/spacy-models | in use |

## Datasets and clips
| Item | Use | Licence | Link | Committed? |
|---|---|---|---|---|
| W3C WAI "Web Accessibility Perspectives" videos and tracks | test set (never used for tuning) | W3C terms (link to page; use whole videos) | https://www.w3.org/WAI/perspective-videos/ | **No** (fetched by script; SHA-256 manifest only) |
| Synthetic fixture and adversarial clips (Kokoro voices + generated visuals) | fixture, dev, E11 | ours (MIT) | this repo | yes |

## Fonts
| Font | Use | Licence |
|---|---|---|
| _(system UI fonts only so far)_ | | |
