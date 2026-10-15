# Verifier rules

Each rule is a small pure function in `src/accesscast/verify/` with a passing and a failing test in `tests/unit/test_rule_<id>.py`. Every finding states what was observed and the limit. A rule that crashes produces `VERIFIER_CRASH`, which blocks the line (fail closed). **Error** findings block a line; **warnings** are shown to the reviewer and lower confidence.

**Timing convention.** A description line's `anchor_ms` is the start of its padded region: 150 ms of silence, the voice, then 150 ms of silence. So the voice starts at `anchor + 150 ms`, and the line fits when `voice + 300 ms ≤ pause end − anchor`. This matches the plan's budget formula (PLAN §9 S7).

**Languages.** English uses spaCy `en_core_web_sm` (MIT). Hindi and Italian use rules only, because spaCy's Italian models are not under a licence we accept for production and there is no Hindi model. The rules marked *(en only)* or *(weaker for hi/it)* are less reliable there, and the reviewer sees the back-translation.

## Description lines (`ad`, `ad_translation`) — PLAN §10.2

| Rule | Severity | Check | Source |
|---|---|---|---|
| AD001 `GAP_OVERFLOW` | error | voice + 300 ms > pause end − anchor (estimated from the measured voice rate before TTS; re-run on the measured clip after TTS) | AudioSight pads; our timing model |
| AD002 `ANCHOR_INSIDE_DIALOGUE_WORD` | error | a word has start < anchor < end | AudioSight |
| AD003 `ANCHOR_NEAR_DIALOGUE_WORD` | warning | anchor within 100 ms of a word edge | AudioSight |
| AD004 `OVERLAPS_SPEECH` | error | the voice span overlaps any padded speech span (words ∪ VAD, padded by `guard_ms`) | ours |
| AD005 `ANCHOR_FAR_FROM_EVENT` | error | anchor outside [event start − 2.0 s, event end + 1.0 s]; or the line cites a fact id that does not exist | W3C WAI "at or just before the visual" |
| AD006 `NON_MONOTONIC_OR_OVERLAPPING_AD` | error | two description voices overlap, or ids are out of time order | AudioSight |
| AD007 `WORD_BUDGET_EXCEEDED` | error | words > `words_max` (never truncated) | AudioSight (theirs only warned) |
| AD008 `RESTATES_DIALOGUE` | error | shares a lemmatised 4-word phrase with dialogue within ±10 s, or content-word Jaccard > 0.5 | AudioSight; DCMP; Ofcom 4.8 |
| AD009 `INVENTED_NAME` | error | a proper noun that is not an allowed name (direct address, self-introduction, on-screen text) and not in the line's own facts *(weaker for hi/it)* | AudioSight; Netflix; Ofcom 4.9 |
| AD010 `UNSUPPORTED_CLAIM` | error | motive, relationship, destination, occupation, off-screen, deadline or certainty phrases not in the facts | GemmaClip's claim types, our own lexicon (en/hi/it) |
| AD011 `SOUND_IN_DESCRIPTION` | error | sound, speech or music words (outside quoted on-screen text) | GemmaClip's audio-claim idea |
| AD012 `NOT_GROUNDED` | error if > 1/3 of nouns unsupported, else warning | each noun appears in the facts, on-screen text, cast or setting (with a small synonym list) *(weaker for hi/it)* | ours |
| AD013 `ONSCREEN_TEXT_NOT_READ` | warning | a title or slide of ≥ 3 words that OCR confirmed is not read by any line in the scene | DCMP; W3C WAI |
| AD014 `COMMENTARY` | warning | "we see", "the camera", "seems to", "appears to" | ACB; DCMP |
| AD015 `NOT_PRESENT_TENSE` | warning | a finite past-tense verb *(en only)* | DCMP; Ofcom 4.1; Netflix |
| AD016 `WRONG_LANGUAGE` | error | Hindi < 90% Devanagari letters; Devanagari in a Latin-script language; Italian identical to the English | ours |
| AD017 `EMOTION_INFERRED` | warning | an emotion word not backed by a visible expression in the facts | DCMP |
| AD018 `INJECTION_ECHO` | error | repeats an instruction-like on-screen text without "On screen: …" / "A sign reads: …" framing | ours (case A3) |
| AD019 `EMPTY_OR_FILLER` | error | empty, under 2 words, or filler ("Something happens.") | ours |
| AD020 `BACKTRANSLATION_DRIFT` | warning (advisory) | LaBSE cosine of back-translation vs approved English < 0.75 | ours |

Extended-description lines (inserted while the video holds a frame) skip AD001–AD004 and AD006, because they do not sit in a dialogue pause.

## Easy-read captions (`easy`) — PLAN §10.3

| Rule | Severity | Check | Source |
|---|---|---|---|
| ER001 `TOO_FAST` | error | > 130 words per minute over the cue, unless flagged `needs_pause` | DCMP lower-level media |
| ER002 `SENTENCE_TOO_LONG` | error | a sentence > 12 words | Inclusion Europe (12 is our setting) |
| ER003 `MORE_THAN_ONE_IDEA` | warning | two finite verbs joined by a coordinating word | Inclusion Europe |
| ER004 `NUMBER_CHANGED` | error | numbers (digits and number words) differ from the source | Inclusion Europe; Clearsheet/ClearCare lesson |
| ER005 `NEGATION_FLIPPED` | error | negation count differs from the source (en/hi/it lists) | ours (case A4) |
| ER006 `NAME_OR_TERM_LOST` | error | a name or glossary term from the source is missing | ours |
| ER007 `ABBREVIATION` | error | "e.g.", "etc.", "i.e." or unexplained capitals | Inclusion Europe |
| ER008 `HARD_WORD` | warning | Zipf frequency < 3.5 (`wordfreq`) | Inclusion Europe |
| ER009 `READABILITY` | warning | Flesch < 70 (en) / Gulpease < 60 (it); none for Hindi (no validated formula) | textstat |
| ER010 `LAYOUT` | error | > 42 characters a line or > 2 lines | Netflix |

## SDH captions and subtitles (`sdh`, `subtitle`) — PLAN §10.4

| Rule | Severity | Check | Source |
|---|---|---|---|
| CC001 `CPS` | error for subtitles (repairable); warning for verbatim SDH | > 20 cps (en, it SDH), > 25 (hi SDH), > 17 (it subtitles), > 22 (hi subtitles) | Netflix guides |
| CC002 `CHARS_PER_LINE` | error | > 42 | Netflix |
| CC003 `LINES` | error | > 2 | Netflix; DCMP |
| CC004 `DURATION` | error | < 40 frames or > 6 s | DCMP Captioning Key |
| CC005 `SYNC` | error | cue start > 100 ms from its first word | our setting, modelled on EN 301 549 7.1.2 |
| CC006 `NOT_VERBATIM` | error (automatic cues only) | cue words ≠ aligned words | DCMP |
| CC007 `SEGMENT_MISALIGNED` | error | translation ids or snippets do not match the batch | video-voice-translator |
| CC008 `UNTRANSLATED` | error | same as the English, or mostly English/Latin script | QuestBridge's lesson |
| CC009 `NUMBER_OR_NAME_CHANGED` | error | numbers differ; Italian loses a name | ours |
| CC010 `MISSING_GLYPH` | error | the caption font cannot draw a character | Rivet A11 |
| CC011 `CONTRAST` | error (burned-in only) | contrast < 4.5:1 | WCAG 1.4.3 (not used yet: we ship text tracks, not burned-in captions) |

## Voice-over (`voiceover`) — PLAN §10.5

| Rule | Severity | Check |
|---|---|---|
| VO001 `SLOT_OVERFLOW` | error | measured TTS duration > slot × 1.15. The slot runs from the speech start to the next speech − 200 ms, at most 1.5 s past the original speech end |
| VO002 | error | as CC008 |
| VO003 | error | as CC009 |
| VO004 `TOO_SHORT` | warning | TTS < 50% of the slot |

## Render (`render`) — PLAN §10.6

| Rule | Severity | Check |
|---|---|---|
| RN001 `DURATION` | error | standard: source ± 40 ms (+ one audio frame of container slack); extended: source + insertions |
| RN002 `ITEMS_MATCH_APPROVED` | error | every approved item rendered; nothing else |
| RN003 `LOUDNESS` | error | integrated loudness within ±1 LU of target; true peak ≤ −1 dBTP |
| RN004 `DUCK_DEPTH` | warning | original dip outside 6–12 dB under description |
| RN005 `AV_SYNC` | error | audio/video start offset > 40 ms |
| RN006 `VTT_VALID` | error | every track parses and cues are in order |
| RN007 `HUMAN_REVIEWED` | error for public export | `human_reviewed` must be true |
| RN008 `NO_OVERLAP_IN_RENDER` | error (production) | the rendered description stem overlaps the original's word spans by > 50 ms. Off for all arms in E1 |
