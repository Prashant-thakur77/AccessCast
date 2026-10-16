# The alignment-safe batch translation (numbered segments, {id, snippet, translation}, snippet check,
# batch halving N → N/2 → … → 1, then single retries) follows src/text_translator.py from
# video-voice-translator (https://github.com/icuic/video-voice-translator), MIT License,
# Copyright (c) 2025 Video Voice Translator Contributors. Rewritten for AccessCast with English prompts,
# our LLM client and fail-closed behaviour: a segment that never aligns is `needs_revision`, never
# silently left in English.
"""S10/S11 text versions: easy-read, hi/it subtitles, hi/it voice-over scripts, hi/it description."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from accesscast import confidence
from accesscast import constants as C
from accesscast.errors import LlmOutputError, ModelEndpointError
from accesscast.llm.client import LlmClient, LlmRequest
from accesscast.repair.loop import feedback_violations, run_repair_loop
from accesscast.schemas import Item, ItemKind, ItemStatus, RepairInfo, RepairStep, Slot
from accesscast.seeds import derive_seed
from accesscast.verify import nlp
from accesscast.verify.base import Finding, Rule, VerificationResult, VerifyContext, run_rules
from accesscast.verify.rules_ad import AD_RULES
from accesscast.verify.rules_text import EASY_RULES, SUBTITLE_RULES

BATCH = 12  # segments or lines per request for voice-over and description translation (output-length safety)


@dataclass
class TextOptions:
    run_label: str = "run0"
    project_seed: int = C.PROJECT_SEED_DEFAULT
    repair: bool = True
    temperature: float | None = None  # E11 stress setting; None = the prompt's own temperature


def _apply_loop(
    item: Item,
    ctx: VerifyContext,
    rules: Sequence[Rule],
    revise: Callable[[int, str, list[Finding]], tuple[str, list[str]]] | None,
) -> Item:
    def verify(text: str, _f: list[str]) -> VerificationResult:
        return run_rules(item.model_copy(update={"draft": text}), ctx, rules)

    out = run_repair_loop(
        item.draft, [], verify, revise or (lambda k, t, v: (t, [])), enabled=revise is not None
    )
    res = out.final_result or verify(out.text, [])
    return item.model_copy(
        update={
            "final": out.text if out.attempts else None,
            "status": ItemStatus.PENDING if out.ok else ItemStatus.NEEDS_REVISION,
            "violations": [f.to_model() for f in res.violations],
            "warnings": [f.to_model() for f in res.warnings],
            "repair": RepairInfo(
                attempts=out.attempts,
                stop_reason=out.stop_reason,
                history=[RepairStep(attempt=h.attempt, text=h.text, rules=h.rules) for h in out.history],
            ),
        }
    )


# ---------------------------------------------------------------- easy-read
def group_sdh(sdh: Sequence[Item], max_ms: int = 12_000) -> list[list[Item]]:
    groups: list[list[Item]] = []
    for it in sorted(sdh, key=lambda i: i.anchor_ms):
        if "sound_tag" in it.flags:
            continue
        if (
            groups
            and it.slot.start_ms - groups[-1][-1].slot.end_ms < 600
            and it.slot.end_ms - groups[-1][0].slot.start_ms <= max_ms
        ):
            groups[-1].append(it)
        else:
            groups.append([it])
    return groups


def make_easy(client: LlmClient, sdh: Sequence[Item], ctx: VerifyContext, opts: TextOptions) -> list[Item]:
    items: list[Item] = []
    for gi, group in enumerate(group_sdh(sdh)):
        span_s = (group[-1].slot.end_ms - group[0].slot.start_ms) / 1000
        words_max = max(3, int(span_s * C.EASY_WPM_MAX / 60))
        cues = [{"id": c.id, "text": c.text.replace("\n", " ").lstrip("- ")} for c in group]
        seed = derive_seed(opts.project_seed, f"easy:{gi}:{opts.run_label}")
        try:
            resp = client.call(
                LlmRequest(
                    "easy",
                    {"lang": "en", "seconds": round(span_s, 2), "words_max": words_max, "cues": cues},
                    seed=seed,
                    temperature=opts.temperature,
                    label=f"easy:{gi}",
                )
            )
            got = {
                str(x.get("id")): str(x.get("text", ""))
                for x in resp.obj.get("items") or []
                if isinstance(x, dict)
            }
            err = None
        except (LlmOutputError, ModelEndpointError) as e:
            got, err = {}, str(e)[:200]
        for c in group:
            text = got.get(c.id, "")
            it = Item(
                id=f"easy.en.{len(items) + 1:04d}",
                kind=ItemKind.EASY,
                lang="en",
                audiences=["easy"],
                anchor_ms=c.slot.start_ms,
                slot=Slot(start_ms=c.slot.start_ms, end_ms=c.slot.end_ms),
                draft=_wrap2(text),
                source_text=c.text.replace("\n", " ").lstrip("- "),
                source_ids=[c.id],
                flags=[f"generation_error:{err}"] if err else [],
            )
            if (
                nlp.word_count(text) / max(0.001, (c.slot.end_ms - c.slot.start_ms) / 1000) * 60
                > C.EASY_WPM_MAX
            ):
                it = it.model_copy(update={"needs_pause": True})

            def revise(
                k: int, t: str, v: list[Finding], it: Item = it, words_max: int = words_max
            ) -> tuple[str, list[str]]:
                s = derive_seed(opts.project_seed, f"{it.id}:{opts.run_label}:repair:{k}")
                r = client.call(
                    LlmRequest(
                        "repair_easy",
                        {
                            "current_state": {
                                "cues": [{"id": it.id, "text": it.source_text}],
                                "words_max": words_max,
                            },
                            "rejected_output": {"items": [{"id": it.id, "text": t}]},
                            "violations": feedback_violations(VerificationResult(False, v, [])),
                            "hard_limits": {"sentence_words_max": C.EASY_SENTENCE_WORDS_MAX},
                        },
                        seed=s,
                        label=f"repair_easy:{it.id}:{k}",
                    )
                )
                confidence.reject_model_confidence(r.obj)
                arr = r.obj.get("items") or []
                if not arr or not isinstance(arr[0], dict) or not str(arr[0].get("text", "")).strip():
                    raise LlmOutputError("repair returned nothing")
                return _wrap2(str(arr[0]["text"])), []

            items.append(_apply_loop(it, ctx, EASY_RULES, revise if opts.repair else None))
    return items


def _wrap2(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= C.CHARS_PER_LINE_MAX:
        return text
    words = text.split()
    best = text
    best_score = 10**9
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        if (
            len(a) <= C.CHARS_PER_LINE_MAX
            and len(b) <= C.CHARS_PER_LINE_MAX
            and abs(len(a) - len(b)) < best_score
        ):
            best, best_score = f"{a}\n{b}", abs(len(a) - len(b))
    return best


# ---------------------------------------------------------------- alignment-safe batch translation
def _snippet_ok(snippet: str, src: str) -> bool:
    s = snippet.strip().lower()
    t = src[:10].strip().lower()
    if not s:
        return False
    if t.startswith(s) or s.startswith(t):
        return True
    common = sum(1 for a, b in zip(s, t, strict=False) if a == b)
    return common >= max(1, len(t) // 2)


def translate_batch(
    client: LlmClient,
    segs: list[dict[str, Any]],
    lang: str,
    opts: TextOptions,
    prompt_id: str = "translate_subs",
) -> dict[int, str]:
    """Return id → translation for every segment that aligned; misaligned ids are absent."""
    done: dict[int, str] = {}
    pending = list(segs)
    size = len(pending)
    single_tries = 0
    calls = 0
    while pending and calls < 4 * len(segs) + 10:
        calls += 1
        batch = pending[:size]
        seed = derive_seed(
            opts.project_seed, f"{prompt_id}:{lang}:{batch[0]['id']}:{size}:{calls}:{opts.run_label}"
        )
        arr: Any = None
        try:
            resp = client.call(
                LlmRequest(
                    prompt_id,
                    {"target_lang": lang, "segments": batch},
                    seed=seed,
                    temperature=opts.temperature,
                    label=f"{prompt_id}:{lang}:{batch[0]['id']}",
                )
            )
            arr = resp.obj.get("items")
            ok = (
                isinstance(arr, list)
                and len(arr) == len(batch)
                and all(
                    isinstance(got, dict)
                    and int(got.get("id", -1)) == want["id"]
                    and _snippet_ok(str(got.get("snippet", "")), want["text"])
                    and bool(str(got.get("translation", "")).strip())
                    for want, got in zip(batch, arr, strict=True)
                )
            )
        except (LlmOutputError, ModelEndpointError, ValueError, TypeError):
            ok = False
        if ok:
            for want, got in zip(batch, arr, strict=True):
                done[want["id"]] = str(got["translation"]).strip()
            pending = pending[len(batch) :]
            single_tries = 0
            size = min(len(pending), size)
        elif size > 1:
            size //= 2  # N -> N/2 -> ... -> 1
        else:
            single_tries += 1
            if single_tries >= 3:  # 3 single retries, then this segment fails closed (never left in English)
                pending = pending[1:]
                single_tries = 0
                size = min(len(pending), 1)
    return done


def make_subtitles(
    client: LlmClient, sdh: Sequence[Item], lang: str, ctx: VerifyContext, opts: TextOptions
) -> list[Item]:
    src_items = [i for i in sdh if "sound_tag" not in i.flags]
    limit = C.CPS_MAX[(lang, "subtitle")]
    segs: list[dict[str, Any]] = [
        {
            "id": k,
            "text": i.source_text or i.text.replace("\n", " "),
            "seconds": round((i.slot.end_ms - i.slot.start_ms) / 1000, 2),
            "chars_max": int((i.slot.end_ms - i.slot.start_ms) / 1000 * limit),
        }
        for k, i in enumerate(src_items)
    ]
    got = translate_batch(client, segs, lang, opts)
    out: list[Item] = []
    for k, i in enumerate(src_items):
        tr = got.get(k)
        nxt = (
            src_items[k + 1].slot.start_ms
            if k + 1 < len(src_items)
            else i.slot.end_ms + int(C.CUE_MAX_S * 1000)
        )
        need = round(len((tr or "").replace("\n", " ")) / limit * 1000)
        end = max(
            i.slot.end_ms, min(nxt - 1, i.slot.start_ms + int(C.CUE_MAX_S * 1000), i.slot.start_ms + need)
        )
        it = Item(
            id=f"subs.{lang}.{k + 1:04d}",
            kind=ItemKind.SUBTITLE,
            lang=lang,
            audiences=[lang],
            anchor_ms=i.slot.start_ms,
            slot=Slot(start_ms=i.slot.start_ms, end_ms=end),
            draft=_wrap2(tr or ""),
            source_text=segs[k]["text"],
            source_ids=[i.id],
            flags=[] if tr else [f"misaligned:segment {k} never aligned"],
        )

        def revise(n: int, t: str, v: list[Finding], it: Item = it) -> tuple[str, list[str]]:
            r = client.call(
                LlmRequest(
                    "repair_subs",
                    {
                        "source": it.source_text,
                        "target_lang": lang,
                        "rejected_output": t,
                        "violations": feedback_violations(VerificationResult(False, v, [])),
                        "hard_limits": {"chars_max": int((it.slot.end_ms - it.slot.start_ms) / 1000 * limit)},
                    },
                    seed=derive_seed(opts.project_seed, f"{it.id}:{opts.run_label}:repair:{n}"),
                    label=f"repair_subs:{it.id}:{n}",
                )
            )
            new = str(r.obj.get("translation", "")).strip()
            if not new:
                raise LlmOutputError("repair returned nothing")
            return _wrap2(new), []

        lctx = VerifyContext(**{**ctx.__dict__, "lang": lang})
        out.append(_apply_loop(it, lctx, SUBTITLE_RULES, revise if opts.repair else None))
    return out


def make_voiceover(
    client: LlmClient,
    sdh: Sequence[Item],
    lang: str,
    wps: float,
    ctx: VerifyContext,
    opts: TextOptions,
    duration_ms: int | None = None,
) -> list[Item]:
    """One voice-over line per speech segment group (consecutive SDH cues)."""
    groups = group_sdh(sdh, max_ms=15_000)
    segs: list[dict[str, Any]] = []
    for gi, g in enumerate(groups):
        secs = (g[-1].slot.end_ms - g[0].slot.start_ms) / 1000
        segs.append(
            {
                "id": f"vo.{lang}.{gi + 1:04d}",
                "text": " ".join((c.source_text or c.text) for c in g),
                "seconds": round(secs, 2),
                "words_max": max(2, int(secs * wps * C.VO_TEMPO_MAX) - 1),
            }
        )
    got: dict[str, str] = {}
    for b in range(
        0, len(segs), BATCH
    ):  # batched: one request per 12 segments, so long videos fit the output
        chunk = segs[b : b + BATCH]
        try:
            resp = client.call(
                LlmRequest(
                    "voiceover",
                    {"target_lang": lang, "segments": chunk},
                    seed=derive_seed(opts.project_seed, f"vo:{lang}:{b}:{opts.run_label}"),
                    label=f"voiceover:{lang}:{b}",
                )
            )
            got.update(
                {
                    str(x.get("id")): str(x.get("text", ""))
                    for x in resp.obj.get("items") or []
                    if isinstance(x, dict)
                }
            )
        except (LlmOutputError, ModelEndpointError):
            continue  # missing ids become `misaligned` lines (GEN001 / CC007): never silently English
    out = []
    for gi, (g, seg) in enumerate(zip(groups, segs, strict=True)):
        nxt = groups[gi + 1][0].slot.start_ms if gi + 1 < len(groups) else g[-1].slot.end_ms + C.VO_TAIL_MS
        end = max(g[-1].slot.end_ms, min(nxt - C.VO_GAP_BEFORE_NEXT_MS, g[-1].slot.end_ms + C.VO_TAIL_MS))
        if duration_ms is not None:
            end = min(end, duration_ms)
        it = Item(
            id=seg["id"],
            kind=ItemKind.VOICEOVER,
            lang=lang,
            audiences=[lang],
            anchor_ms=g[0].slot.start_ms,
            slot=Slot(start_ms=g[0].slot.start_ms, end_ms=end),
            draft=got.get(seg["id"], ""),
            source_text=seg["text"],
            source_ids=[c.id for c in g],
            flags=[] if seg["id"] in got else ["misaligned:missing from model output"],
        )
        out.append(it)
    return out


def shorten_voiceover(
    client: LlmClient, it: Item, lang: str, wps: float, opts: TextOptions, k: int, viol: list[Finding]
) -> str:
    """Repair step for VO001: ask Gemma for a shorter spoken line (same meaning, numbers, names)."""
    secs = (it.slot.end_ms - it.slot.start_ms) / 1000
    r = client.call(
        LlmRequest(
            "repair_subs",
            {
                "source": it.source_text,
                "target_lang": lang,
                "rejected_output": it.text,
                "violations": feedback_violations(VerificationResult(False, viol, [])),
                "hard_limits": {"words_max": max(2, int(secs * wps * C.VO_TEMPO_MAX) - 1), "spoken": True},
            },
            seed=derive_seed(opts.project_seed, f"{it.id}:{opts.run_label}:repair:{k}"),
            label=f"repair_vo:{it.id}:{k}",
        )
    )
    new = str(r.obj.get("translation", "")).strip()
    if not new:
        raise LlmOutputError("repair returned nothing")
    return new


def make_ad_translations(
    client: LlmClient,
    approved_ad: Sequence[Item],
    lang: str,
    wps: float,
    ctx: VerifyContext,
    opts: TextOptions,
) -> list[Item]:
    """Translate APPROVED English description lines (S11); reviewer sees the back-translation."""
    lines: list[dict[str, Any]] = [
        {
            "id": f"ad.{lang}.{i.id.split('.')[-1]}",
            "text": i.text,
            "words_max": max(
                2,
                int(
                    (i.budget.words_max if i.budget else 10)
                    * wps
                    / max(i.budget.wps_voice if i.budget else wps, 0.1)
                ),
            ),
        }
        for i in approved_ad
    ]
    got: dict[str, dict[str, Any]] = {}
    for b in range(0, len(lines), BATCH):
        chunk = lines[b : b + BATCH]
        try:
            resp = client.call(
                LlmRequest(
                    "ad_translate",
                    {"target_lang": lang, "lines": chunk},
                    seed=derive_seed(opts.project_seed, f"adtr:{lang}:{b}:{opts.run_label}"),
                    label=f"ad_translate:{lang}:{b}",
                )
            )
            got.update({str(x.get("id")): x for x in resp.obj.get("items") or [] if isinstance(x, dict)})
        except (LlmOutputError, ModelEndpointError):
            continue
    out = []
    lctx = VerifyContext(
        **{
            **ctx.__dict__,
            "lang": lang,
            "wps_voice": wps,
            "approved_english": {i.id: i.text for i in approved_ad},
        }
    )
    rules = tuple(
        r
        for r in AD_RULES
        if r.__name__
        not in (
            "ad008_restates_dialogue",
            "ad012_not_grounded",
            "ad015_not_present_tense",
            "ad009_invented_name",
            "ad006_non_monotonic",
            "ad013_onscreen_not_read",
        )
    )
    for src, line in zip(approved_ad, lines, strict=True):
        x = got.get(line["id"], {})
        budget = (
            src.budget.model_copy(update={"words_max": line["words_max"], "wps_voice": wps})
            if src.budget
            else None
        )
        it = src.model_copy(
            update={
                "id": line["id"],
                "kind": ItemKind.AD_TRANSLATION,
                "lang": lang,
                "audiences": ["blind", lang],
                "draft": str(x.get("text", "")),
                "final": None,
                "status": ItemStatus.PENDING,
                "source_ids": [src.id],
                "source_text": src.text,
                "back_translation": str(x.get("back_translation", "")) or None,
                "budget": budget,
                "tts": None,
                "reviewer": None,
                "reviewed_at": None,
                "revision": 0,
                "repair": RepairInfo(),
                "flags": [] if x else ["misaligned:missing from model output"],
            }
        )
        out.append(_apply_loop(it, lctx, rules, None))
    return out
