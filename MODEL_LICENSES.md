# Models, voices, datasets, clips and fonts

Every item is listed here with its licence and link **before** it is used. No non-commercial weights or voices anywhere in the product.

## Models
| Model | Role | Licence | Link | Status |
|---|---|---|---|---|
| google/gemma-4-31B-it | evidence, scene judge, description, easy-read, translation, repair | Apache-2.0 | https://huggingface.co/google/gemma-4-31B-it | used via AMD Token Factory (D-021) |
| google/gemma-4-E4B-it | ASR cross-check, sound events | Apache-2.0 | https://huggingface.co/google/gemma-4-E4B-it | not run (D-021: not on Token Factory, no droplet) |
| google/gemma-4-26B-A4B-it | E3 ablation only | Apache-2.0 | https://huggingface.co/google/gemma-4-26B-A4B-it | planned |
| openai/whisper-large-v3 / -turbo | word timing (E15 decides) | MIT | https://huggingface.co/openai/whisper-large-v3 | planned |
| Silero VAD | speech / no speech | MIT (LICENSE file checked 16 Oct 2026) | https://github.com/snakers4/silero-vad | planned |
| MIT/ast-finetuned-audioset-10-10-0.4593 (Audio Spectrogram Transformer) | sound labels for SDH captions in place of Gemma 4 E4B (D-021); AudioSet classes mapped to our closed vocabulary | BSD-3-Clause (model card, checked 16 Oct 2026) | https://huggingface.co/MIT/ast-finetuned-audioset-10-10-0.4593 | used (workstation) |
| hexgrad/Kokoro-82M | English description voice `af_heart`; hi `hf_alpha`, it `if_sara` | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M | planned |
| ResembleAI Chatterbox Multilingual (chatterbox-tts 0.1.7) | optional Hindi/Italian voice (`ACCESSCAST_TTS_ENGINE_HI_IT=chatterbox`); default stays Kokoro until a native speaker rates both | MIT; every clip carries an imperceptible Perth watermark, disclosed in the player and here | https://github.com/resemble-ai/chatterbox | integrated, own env `workers/chatterbox/` |
| torchaudio `WAV2VEC2_ASR_BASE_960H` (fairseq wav2vec 2.0 base, LibriSpeech 960 h) | English forced alignment | MIT (fairseq) | https://pytorch.org/audio/stable/generated/torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.html | in use (kept only if E15 shows it helps) |
| openai/whisper-base | local smoke tests only (never for published numbers) | MIT | https://huggingface.co/openai/whisper-base | dev only |
| spaCy en_core_web_sm 3.8.0 | English rule NLP (lemmas, POS, names) | MIT | https://github.com/explosion/spacy-models | in use |
| Unbabel/wmt22-comet-da (rev 2760a223) | E4 metric (COMET) | Apache-2.0 (model card, checked 16 Oct 2026) | https://huggingface.co/Unbabel/wmt22-comet-da | eval only |
| FacebookAI/xlm-roberta-large (config + tokenizer, loaded by COMET) | E4 metric encoder | MIT | https://huggingface.co/FacebookAI/xlm-roberta-large | eval only |
| microsoft/deberta-xlarge-mnli | E5/E7 metric (BERTScore, layer 40) | MIT (model card, checked 16 Oct 2026) | https://huggingface.co/microsoft/deberta-xlarge-mnli | eval only |
| sentence-transformers/LaBSE (rev 836121a0) | back-translation drift (AD020), E4 checks | Apache-2.0 (model card, checked 16 Oct 2026) | https://huggingface.co/sentence-transformers/LaBSE | eval only |
| Helsinki-NLP/opus-mt-en-it (rev be5a254d) | E4 Italian baseline translator | Apache-2.0 (model card metadata, checked 16 Oct 2026) | https://huggingface.co/Helsinki-NLP/opus-mt-en-it | eval only |
| ai4bharat/indictrans2-en-indic-1B (rev 89cd0007) | E4 Hindi baseline translator | MIT (model card metadata and IndicTrans2 README licence table, checked 16 Oct 2026); gated, `trust_remote_code` at the pinned revision | https://huggingface.co/ai4bharat/indictrans2-en-indic-1B | eval only |
| _not used:_ "Indic-Translate" | — | no AI4Bharat model by this name on Hugging Face (search of the `ai4bharat` org, 16 Oct 2026) | — | — |
| _not used:_ ai4bharat/IndicTrans3-beta | — | CC-BY-4.0, but tagged `gemma3` (a Gemma 3 fine-tune, so Gemma terms likely apply too) and labelled beta | https://huggingface.co/ai4bharat/IndicTrans3-beta | not used |
| _not used:_ ai4bharat/indic-seamless | — | CC-BY-NC-4.0 (non-commercial) | https://huggingface.co/ai4bharat/indic-seamless | **never** |
| _ablation only, not wired yet:_ google/translategemma-27b-it | E4 ablation | Gemma Terms of Use (gated) | https://huggingface.co/google/translategemma-27b-it | not used |
| Non-Gemma question answerer / judge on AMD Token Factory (model chosen with `--answerer-model`, e.g. a Qwen model if listed) | E6 answers, E7 1–5 judge | per provider and model; record the exact served id in the evidence file | AMD Token Factory | eval only |

## Datasets and clips
| Item | Use | Licence | Link | Committed? |
|---|---|---|---|---|
| W3C WAI "Web Accessibility Perspectives" videos and tracks | test set (never used for tuning) | W3C terms (link to page; use whole videos) | https://www.w3.org/WAI/perspective-videos/ | **No** (fetched by script; SHA-256 manifest only) |
| Synthetic fixture and adversarial clips (Kokoro voices + generated visuals) | fixture, dev, E11 | ours (MIT) | this repo | yes |
| FLORES+ devtest `eng_Latn`, `hin_Deva`, `ita_Latn` (openlanguagedata/flores_plus, rev e707e62e) | E4 translation | CC BY-SA 4.0 (gated) | https://huggingface.co/datasets/openlanguagedata/flores_plus | **No** (data/flores/, SHA-256 manifest only; per-sentence outputs stay in data/) |
| SIMPITIKI v2 (Tonelli, Palmero Aprosio, Saltori, CLiC-it 2016) | E5 Italian simplification check | CC-BY-4.0 (README, checked 16 Oct 2026) | https://github.com/dhfbk/simpitiki | **No** (data/simpitiki/, SHA-256 manifest only) |
| E6 multiple-choice questions written by a person from W3C's human description | E6 | ours; questions only, no W3C text copied | eval/questions/ | yes (questions only) |

## Fonts
| Font | Use | Licence |
|---|---|---|
| Anton (Vernon Adams), via @fontsource/anton 5.3.0; latin and latin-ext woff2 in `src/accesscast/player/static/assets/fonts/` | Display headings on the site | OFL-1.1 — https://github.com/fontsource/font-files/tree/main/fonts/google/anton (font: https://fonts.google.com/specimen/Anton) |
| Inter (Rasmus Andersson), variable weight, via @fontsource-variable/inter 5.3.0; latin and latin-ext woff2 | Body text and controls on the site | OFL-1.1 — https://github.com/rsms/inter/blob/master/LICENSE.txt |
| Noto Sans Devanagari (Google), via @fontsource/noto-sans-devanagari 5.3.0; devanagari subset, weights 400 and 700 | Every `lang="hi"` element on the site | OFL-1.1 — https://github.com/notofonts/devanagari/blob/main/OFL.txt |

## Evaluation libraries (workers/ environment)
| Library | Use | Licence | Link |
|---|---|---|---|
| unbabel-comet 2.2.7 | COMET scoring | Apache-2.0 | https://github.com/Unbabel/COMET |
| bert-score 0.3.13 | BERTScore | MIT | https://github.com/Tiiiger/bert_score |
| sentence-transformers | LaBSE embeddings | Apache-2.0 | https://github.com/UKPLab/sentence-transformers |
| sacrebleu | chrF++ | Apache-2.0 | https://github.com/mjpost/sacrebleu |
| sentencepiece | Opus-MT tokenizer | Apache-2.0 | https://github.com/google/sentencepiece |
| sacremoses | Moses tokenizer (Opus-MT, IndicTransToolkit) | MIT | https://github.com/hplt-project/sacremoses |
| IndicTransToolkit 1.1.1 | IndicTrans2 pre/post-processing | MIT | https://github.com/VarunGumma/IndicTransToolkit |
| indic-nlp-library-itt (via IndicTransToolkit) | Indic normalisation | MIT | https://pypi.org/project/indic-nlp-library-itt/ |
| CIDEr-D | E7 metric | our own implementation in eval/e07_similarity.py (idea from Vedantam et al., CVPR 2015; no pycocoevalcap code) | — |
