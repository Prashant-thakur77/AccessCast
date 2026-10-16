"""Every tunable number in AccessCast, each with the source it came from.

Values marked "dev-tuned" may change only from dev-set measurements, and are frozen by
`make freeze-prompts` (the SHA-256 of this file is in evidence/test_freeze.json).
"""

from __future__ import annotations

# ---------------------------------------------------------------- schema ids
SCHEMA_EVIDENCE = "accesscast/evidence/v1"
SCHEMA_CLAIMS = "accesscast/public-claims/v1"
SCHEMA_REPAIR = "accesscast/repair/v1"
SCHEMA_REPORT = "accesscast/report/v1"
SCHEMA_WORKER_REQUEST = "accesscast/worker-request/v1"
SCHEMA_WORKER_RESPONSE = "accesscast/worker-response/v1"
EVENT_PREFIX = "@@AC_EVENT@@"  # CLAUDE.md §6: worker progress lines on stderr

# ---------------------------------------------------------------- media (S0)
MASTER_SAMPLE_RATE = 48_000  # PLAN §9 S0: master48k.wav
ASR_SAMPLE_RATE = 16_000  # Whisper input rate (openai/whisper model card)
PROXY_HEIGHT = 480  # PLAN §9 S0: proxy480.mp4

# ---------------------------------------------------------------- shots and scenes (S1)
# Thresholds re-implemented from AudioSight's README/design description (Apache-2.0), PLAN §9 S1.
SCENE_CROP_TOP_FRACTION = 0.62  # AudioSight: compare top 62% of frame (ignores burned-in subtitles)
SCENE_W_DHASH = 0.45  # AudioSight similarity weight for dHash
SCENE_W_HIST = 0.55  # AudioSight similarity weight for H/S histogram correlation
SCENE_MERGE_DIALOGUE = 0.82  # AudioSight: merge when dialogue continues
SCENE_MERGE_IDENTICAL = 0.92  # AudioSight: near-identical visuals
SCENE_SPLIT_BELOW = 0.45  # AudioSight: split when no dialogue bridge
SCENE_DIALOGUE_BRIDGE_MS = 1_200  # AudioSight: words within 1,200 ms across the cut
SCENE_MIN_S = 6.0  # AudioSight scene clamp
SCENE_MAX_S = 45.0  # AudioSight scene clamp

# ---------------------------------------------------------------- gaps (S4)
ASR_MODEL = "openai/whisper-large-v3"  # PLAN §9 S2 default; replaced by E15's dev-set decision
GUARD_MS = 120  # PLAN §9 S4 start value; replaced by E15's measured boundary error (dev-tuned)
MIN_GAP_MS = 1_200  # PLAN §9 S4
ASR_VAD_GATE_PAD_MS = (
    400  # dev-tuned: drop Whisper words more than this far from any Silero speech (hallucination over music)
)
ASR_CROSSCHECK_WER = 0.15  # PLAN §9 S2b: chunk WER above this marks asr_disagreement (dev-tuned)
ASR_CHUNK_S = 30.0  # Gemma 4 audio input limit: 30 s per clip (Gemma 4 model card)

# ---------------------------------------------------------------- sounds (S3)
SOUND_WINDOW_MAX_S = 5.0  # PLAN §9 S3
SOUND_MIN_REGION_S = 1.0  # PLAN §9 S3
SOUND_RMS_SILENCE = 0.01  # GemmaClip's silence gate idea (re-implemented), PLAN §9 S3
SOUND_VOCAB: tuple[str, ...] = (
    "music",
    "music_with_lyrics",
    "applause",
    "laughter",
    "door",
    "knock",
    "phone",
    "footsteps",
    "typing",
    "engine",
    "alarm",
    "crowd",
    "silence",
    "other",
)  # PLAN §9 S3 closed vocabulary

# ---------------------------------------------------------------- evidence (S5)
EVIDENCE_ANCHORS: tuple[float, ...] = (0.05, 0.35, 0.65, 0.95)  # GemmaClip frame-anchor idea, PLAN §9 S5
EVIDENCE_HIGH_CHANGE_FRAMES = 2  # PLAN §9 S5
EVIDENCE_FRAME_PX = 512  # PLAN §9 S5
VISION_SOFT_TOKENS = 140  # PLAN §9 S5 (E2 V3 compares 280 vs 140)
NAME_SOURCES_ALLOWED: tuple[str, ...] = (
    "direct_address",
    "self_introduction",
    "on_screen_text",
)  # PLAN §9 S5


def max_facts(scene_seconds: float) -> int:
    """PLAN §9 S5: fact count <= max(3, min(64, round(scene_seconds * 1.2)))."""
    return max(3, min(64, round(scene_seconds * 1.2)))


# ---------------------------------------------------------------- planning and writing (S6, S7)
AD_EVENT_BEFORE_MS = 2_000  # W3C WAI "at or just before the visual"; PLAN §9 S6
AD_EVENT_AFTER_MS = 1_000  # PLAN §9 S6
AD_EXT_MIN_BREAK_MS = (
    150  # dev-tuned: shortest pause between two words where extended description may hold the video
)
AD_PAD_BEFORE_MS = 150  # AudioSight pads; PLAN §9 S7
AD_PAD_AFTER_MS = 150  # AudioSight pads; PLAN §9 S7
AD_WORDS_MIN = 2  # PLAN §9 S7 clamp
AD_MIN_USEFUL_WORDS = 3  # our setting: a pause too short for 3 words is not used (dev-tuned)
AD_WORDS_MAX = 40  # PLAN §9 S7 clamp
AD_MAX_WORDS_PER_LINE = 25  # PLAN §9 S7
AD_BREATH_MS = 400  # PLAN §9 S7: breath between two lines in a long gap
AD_BATCH_GAPS = 8  # AudioSight batched 8 per request; PLAN §9 S7
WPS_VOICE_DEFAULT = 2.6  # placeholder until tts/calibrate.py measures the voice; never published
DETAIL_LEVELS: dict[str, dict[str, float]] = {
    # priority cut-off (lower = more important; 1 = on-screen text ... 5 = finer detail) and rate factor
    "brief": {"max_priority": 2, "rate": 0.9},
    "standard": {"max_priority": 4, "rate": 1.0},
    "detailed": {"max_priority": 5, "rate": 1.0},
}  # AudioSight's sparse/standard/detailed idea; PLAN §9 S6

# ---------------------------------------------------------------- temperatures and seeds
TEMP_EVIDENCE = 0.0  # PLAN §14.7
TEMP_SCENE_JUDGE = 0.0  # PLAN §14.7
TEMP_WRITE = 0.3  # PLAN §9 S7
TEMP_REPAIR = 0.2  # ProteinLoop's repair setting; PLAN §11.1
TEMP_STRESS = 1.0  # PLAN §17 labelled stress setting
REPAIR_MAX_ATTEMPTS = 3  # ProteinLoop; PLAN §11.1
PROJECT_SEED_DEFAULT = 20261018  # CLAUDE.md §5

# ---------------------------------------------------------------- AD rules (PLAN §10.2)
AD_NEAR_WORD_MS = 100  # AudioSight near-word warning
AD_RESTATE_NGRAM = 4  # PLAN §10.2 AD008
AD_RESTATE_WINDOW_MS = 10_000  # PLAN §10.2 AD008
AD_RESTATE_JACCARD = 0.5  # PLAN §10.2 AD008
AD_GROUNDING_ERROR_FRACTION = 1 / 3  # PLAN §10.2 AD012
AD_ONSCREEN_MIN_WORDS = 3  # PLAN §10.2 AD013
AD_HINDI_DEVANAGARI_MIN = 0.90  # PLAN §10.2 AD016
AD_BACKTRANSLATION_MIN_COS = 0.75  # PLAN §10.2 AD020 (advisory)

# ---------------------------------------------------------------- easy-read (PLAN §10.3)
EASY_WPM_MAX = 130  # DCMP Captioning Key, lower-level educational media
EASY_CPS_MAX = 17  # Netflix children's programming cps
EASY_SENTENCE_WORDS_MAX = 12  # Inclusion Europe "keep sentences short" (12 is our setting)
EASY_ZIPF_HARD = 3.5  # wordfreq Zipf scale; our setting
EASY_FLESCH_MIN_EN = 70  # textstat Flesch Reading Ease
EASY_GULPEASE_MIN_IT = 60  # textstat Gulpease
EASY_HOLD_WPS = 2.2  # PLAN §13.2 "Give me time to read" (dev-tuned)

# ---------------------------------------------------------------- captions (PLAN §10.4)
CHARS_PER_LINE_MAX = 42  # Netflix timed-text guides
LINES_MAX = 2  # Netflix, DCMP
CPS_MAX: dict[tuple[str, str], int] = {
    ("en", "sdh"): 20,  # Netflix English TTSG (adult)
    ("it", "sdh"): 20,  # Netflix Italian TTSG SDH
    ("hi", "sdh"): 25,  # Netflix Hindi TTSG SDH
    ("it", "subtitle"): 17,  # Netflix Italian TTSG
    ("hi", "subtitle"): 22,  # Netflix Hindi TTSG
    ("en", "subtitle"): 20,  # Netflix English TTSG
}
CUE_MIN_FRAMES = 40  # DCMP Captioning Key: at least 40 frames
CUE_MAX_S = 6.0  # DCMP Captioning Key
CUE_SYNC_MS = 100  # our setting, modelled on EN 301 549 7.1.2
UNTRANSLATED_ENGLISH_FRACTION = 0.5  # PLAN §10.4 CC008
SDH_AUTO_APPROVE_CONFIDENCE = 0.6  # PLAN §11.3

# ---------------------------------------------------------------- voice-over (PLAN §10.5)
VO_TEMPO_MAX = 1.15  # PLAN §9 S11 (video-voice-translator's 2.0x is too fast)
VO_TOO_SHORT_FRACTION = 0.5  # PLAN §10.5 VO004
VO_DIP_DB = 12.0  # PLAN §9 S11: original dipped -12 dB under voice-over
VO_TAIL_MS = 1_500  # our setting: a voice-over may run up to 1.5 s into the following silence
VO_GAP_BEFORE_NEXT_MS = 200  # our setting: and must end 200 ms before the next speech

# ---------------------------------------------------------------- render (PLAN §9 S14, §10.6)
DUCK_DB = 9.0  # Netflix AD guide: dip 6-12 dB; our default
DUCK_DB_MIN = 6.0  # Netflix AD guide
DUCK_DB_MAX = 12.0  # Netflix AD guide
DUCK_RAMP_MS = 300  # our setting (Netflix: transitions <= 5 s)
LUFS_BROADCAST = -23.0  # EBU R 128
LUFS_WEB = -16.0  # common web/streaming target; ffmpeg loudnorm default is -24, always set I
LUFS_TOLERANCE = 1.0  # PLAN §10.6 RN003
TRUE_PEAK_MAX = -1.0  # PLAN §10.6 RN003 (dBTP)
RENDER_DURATION_TOL_MS = 40  # PLAN §10.6 RN001
AV_SYNC_TOL_MS = 40  # PLAN §10.6 RN005
RENDER_OVERLAP_TOL_MS = 50  # PLAN §10.6 RN008
EXT_PAD_MS = 150  # AudioSight expanded timeline pads
EXT_FADE_MS = 10  # AudioSight expanded timeline fades

# ---------------------------------------------------------------- confidence (PLAN §11.2; dev-tuned)
CONF_SLACK_FULL_MS = 600  # min(1, slack / 600 ms)
CONF_ASR_DISAGREE_FACTOR = 0.8
CONF_OCR_DISAGREE_FACTOR = 0.85
CONF_REPAIR_PENALTY = 0.10
CONF_WARNING_PENALTY = 0.05

# ---------------------------------------------------------------- review (PLAN §12)
REVIEW_IDLE_S = 60  # idle > 60 s excluded from review timer
REVIEW_DEBOUNCE_MS = 550  # PolicyCut's debounce
REVIEW_CONTEXT_S = 2.0  # "Play in context (±2 s)"

# ---------------------------------------------------------------- LLM client (PLAN §14.3)
LLM_TIMEOUT_S = 180.0
LLM_MAX_RETRIES = 10  # Token Factory returned 503 "no available workers" for minutes at a time (16 Oct)
LLM_BACKOFF_MAX_S = 120.0  # with 10 retries a call waits out an outage of about 15 minutes before failing closed
LLM_RETRY_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)
LLM_LOG_TRUNCATE = 300  # GemmaClip's diagnostics rule idea: truncate text in logs
GPU_HOURLY_COST_USD = 2.59  # AMD Developer Cloud MI300X on-demand price, cited.amd.devcloud_mi300x_hourly (16 Oct 2026); replaced by the billed rate

# ---------------------------------------------------------------- languages
LANGS: tuple[str, ...] = ("en", "hi", "it")
