"""S7 write description (Gemma 4 31B) and S8 verify → repair → confidence → route (PLAN §9, §11)."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from accesscast import confidence
from accesscast import constants as C
from accesscast.errors import LlmOutputError, ModelEndpointError
from accesscast.llm.client import LlmClient, LlmRequest, LlmResponse
from accesscast.repair.loop import NON_REPAIRABLE, feedback_violations, run_repair_loop
from accesscast.schemas import (
    FindingModel,
    Item,
    ItemKind,
    ItemStatus,
    ModelRef,
    RepairInfo,
    RepairStep,
    SceneEvidence,
    Slot,
)
from accesscast.seeds import derive_seed
from accesscast.verify import rules_ad
from accesscast.verify.base import Finding, Rule, VerificationResult, VerifyContext, run_rules
from accesscast.write.plan_ad import PlannedLine

EXTENDED_SKIP = {
    "ad001_gap_overflow",
    "ad002_anchor_inside_word",
    "ad003_anchor_near_word",
    "ad004_overlaps_speech",
    "ad006_non_monotonic",
}


def ad_rules(extended: bool) -> tuple[Rule, ...]:
    if not extended:
        return rules_ad.AD_RULES
    return tuple(r for r in rules_ad.AD_RULES if r.__name__ not in EXTENDED_SKIP)


@dataclass
class WriteOptions:
    run_label: str = "run0"
    project_seed: int = C.PROJECT_SEED_DEFAULT
    checks: bool = True  # E1 arm A: False
    repair: bool = True  # E1 arm B: False
    temperature: float | None = None  # E11 stress setting
    concurrency: int = 16


def _model_ref(resp: LlmResponse, seed: int | None) -> ModelRef:
    return ModelRef(
        name="google/gemma-4-31B-it",
        endpoint=resp.provider,
        temperature=resp.temperature,
        seed=seed,
        prompt_id=resp.prompt.ref,
        prompt_sha=resp.prompt.sha256,
        served_model_id=resp.served_model_id,
    )


def _payload_gap(p: PlannedLine, ev: SceneEvidence | None, ctx: VerifyContext) -> dict[str, Any]:
    return {
        "gap_id": p.item_id,
        "gap_index": p.gap_index,
        "seconds": p.budget.seconds_max,
        "words_max": p.budget.words_max,
        "facts": [{"fid": f.fid, "text": f.text, "priority": f.priority} for f in p.facts],
        "on_screen_text": p.on_screen_text,
        "cast": [
            {"cid": c.cid, "appearance": c.appearance, "name": c.name} for c in (ev.characters if ev else [])
        ],
        "dialogue_before": ctx.dialogue_text(p.anchor_ms - 8000, p.anchor_ms),
        "dialogue_after": ctx.dialogue_text(p.slot_end_ms, p.slot_end_ms + 8000),
        "extended": p.extended,
    }


def write_drafts(
    client: LlmClient,
    plans: Sequence[PlannedLine],
    evidence: dict[str, SceneEvidence],
    ctx: VerifyContext,
    opts: WriteOptions,
) -> dict[str, tuple[str, list[str], ModelRef | None, str | None]]:
    """Returns item_id → (draft, fact_ids, model, error). Batches of up to 8 gaps per request."""
    out: dict[str, tuple[str, list[str], ModelRef | None, str | None]] = {}

    for p in plans:  # no facts (evidence failed): a person writes this line; Gemma is not asked
        if not p.facts:
            out[p.item_id] = ("", [], None, "evidence_failed: a person writes this line")
    plans = [p for p in plans if p.facts]
    batches = [list(plans[i : i + C.AD_BATCH_GAPS]) for i in range(0, len(plans), C.AD_BATCH_GAPS)]

    def one(batch: list[PlannedLine]) -> None:
        seed = derive_seed(opts.project_seed, f"{batch[0].item_id}:{opts.run_label}")
        payload = {"gaps": [_payload_gap(p, evidence.get(p.scene_id), ctx) for p in batch]}
        try:
            resp = client.call(
                LlmRequest(
                    "write_ad",
                    payload,
                    seed=seed,
                    temperature=opts.temperature,
                    label=f"write_ad:{batch[0].item_id}:{opts.run_label}",
                )
            )
            confidence.reject_model_confidence(resp.obj)
            got = {str(x.get("gap_id")): x for x in resp.obj.get("items") or [] if isinstance(x, dict)}
            for p in batch:
                x = got.get(p.item_id)
                if x is None or not isinstance(x.get("text"), str):
                    out[p.item_id] = ("", [], _model_ref(resp, seed), "missing from model output")
                else:
                    fids = [str(f) for f in x.get("fact_ids") or []] or [f.fid for f in p.facts]
                    out[p.item_id] = (x["text"].strip(), fids, _model_ref(resp, seed), None)
        except (LlmOutputError, ModelEndpointError) as e:
            for p in batch:
                out[p.item_id] = ("", [], None, f"generation failed: {e}"[:200])

    with ThreadPoolExecutor(max_workers=max(1, opts.concurrency)) as ex:
        list(ex.map(one, batches))
    return out


def _repair_payload(
    item: Item, p: PlannedLine, ctx: VerifyContext, k: int, text: str, viol: list[Finding]
) -> dict[str, Any]:
    return {
        "schema_version": C.SCHEMA_REPAIR,
        "repair_attempt": k,
        "current_state": {
            "item_kind": "ad",
            "lang": item.lang,
            "gap_ms": item.slot.end_ms - item.slot.start_ms,
            "words_max": p.budget.words_max,
            "allowed_facts": [{"fid": f.fid, "text": f.text, "priority": f.priority} for f in p.facts],
            "allowed_names": sorted(ctx.allowed_names),
            "dialogue_before": ctx.dialogue_text(item.anchor_ms - 8000, item.anchor_ms),
            "dialogue_after": ctx.dialogue_text(item.slot.end_ms, item.slot.end_ms + 8000),
        },
        "rejected_output": {"text": text},
        "violations": feedback_violations(VerificationResult(False, viol, [])),
        "hard_limits": {"words_max": p.budget.words_max, "tense": "present", "person": "third"},
        "required_output": {"type": "json_object", "fields": {"text": "string", "fact_ids": "array"}},
    }


def verify_and_repair(
    client: LlmClient,
    plans: Sequence[PlannedLine],
    drafts: dict[str, tuple[str, list[str], ModelRef | None, str | None]],
    ctx: VerifyContext,
    opts: WriteOptions,
    asr_probs: dict[str, list[float]] | None = None,
    asr_disagree: set[str] | None = None,
) -> list[Item]:
    items: list[Item] = []
    for p in plans:
        text, fids, model, err = drafts[p.item_id]
        items.append(
            Item(
                id=p.item_id,
                kind=ItemKind.AD,
                lang=ctx.lang,
                audiences=["blind"],
                scene_id=p.scene_id,
                gap_id=p.gap.gap_id if p.gap else None,
                anchor_ms=p.anchor_ms,
                slot=Slot(start_ms=p.slot_start_ms, end_ms=p.slot_end_ms),
                budget=p.budget,
                fact_ids=fids,
                draft=text,
                extended=p.extended,
                model=model,
                flags=[f"generation_error:{err}"] if err else [],
            )
        )
    by_id = {p.item_id: p for p in plans}

    def process(item: Item) -> Item:
        p = by_id[item.id]
        local = VerifyContext(**{**ctx.__dict__, "other_items": [i for i in items if not i.extended]})
        rules = ad_rules(item.extended)

        def verify(text: str, facts: list[str]) -> VerificationResult:
            return run_rules(item.model_copy(update={"draft": text, "fact_ids": facts}), local, rules)

        def revise(k: int, text: str, viol: list[Finding]) -> tuple[str, list[str]]:
            seed = derive_seed(opts.project_seed, f"{item.id}:{opts.run_label}:repair:{k}")
            resp = client.call(
                LlmRequest(
                    "repair_ad",
                    _repair_payload(item, p, local, k, text, viol),
                    seed=seed,
                    label=f"repair_ad:{item.id}:{opts.run_label}:{k}",
                )
            )
            confidence.reject_model_confidence(resp.obj)
            new = resp.obj.get("text")
            if not isinstance(new, str) or not new.strip():
                raise LlmOutputError("repair returned no text")
            return new.strip(), [str(f) for f in resp.obj.get("fact_ids") or []]

        if any(f.startswith("generation_error:evidence_failed") for f in item.flags):
            return item.model_copy(update={"status": ItemStatus.NEEDS_REVISION, "confidence": 0.0,
                                           "repair": RepairInfo(attempts=0, stop_reason=NON_REPAIRABLE)})
        if not opts.checks:  # E1 arm A: attempt 0 accepted as written
            res = verify(item.draft, item.fact_ids)
            return item.model_copy(
                update={
                    "status": ItemStatus.PENDING if item.draft else ItemStatus.NEEDS_REVISION,
                    "violations": [f.to_model() for f in res.violations],  # recorded, not acted on
                    "warnings": [f.to_model() for f in res.warnings],
                    "flags": [*item.flags, "checks_off"],
                }
            )
        out = run_repair_loop(item.draft, item.fact_ids, verify, revise, enabled=opts.repair)
        res = out.final_result or verify(out.text, out.fact_ids)
        final = out.text if out.attempts else None
        status = ItemStatus.PENDING if out.ok else ItemStatus.NEEDS_REVISION
        flags = list(item.flags)
        if not out.ok and any(f.rule in ("AD001", "AD004") for f in res.violations) and not item.extended:
            flags.append("extended_candidate")
        upd = item.model_copy(
            update={
                "final": final,
                "fact_ids": out.fact_ids,
                "status": status,
                "flags": flags,
                "violations": [f.to_model() for f in res.violations],
                "warnings": [f.to_model() for f in res.warnings],
                "repair": RepairInfo(
                    attempts=out.attempts,
                    stop_reason=out.stop_reason,
                    history=[RepairStep(attempt=h.attempt, text=h.text, rules=h.rules) for h in out.history],
                ),
            }
        )
        return with_confidence(upd, local, asr_probs or {}, asr_disagree or set())

    with ThreadPoolExecutor(max_workers=max(1, opts.concurrency)) as ex:
        return list(ex.map(process, items))


def with_confidence(
    item: Item, ctx: VerifyContext, asr_probs: dict[str, list[float]], asr_disagree: set[str]
) -> Item:
    grounding = rules_ad.grounding_share(item, ctx)
    start, end = rules_ad.clip_span(item, ctx)
    slack = None if item.extended else item.slot.end_ms - (end + C.AD_PAD_AFTER_MS)
    probs = [w.prob for w in ctx.words if abs(w.start_ms - item.anchor_ms) < 10_000]
    ocr_bad = False
    ev = ctx.evidence.get(item.scene_id or "")
    if ev is not None:
        ocr_bad = any(
            t.source == "model" and not t.ocr_agrees and t.kind in ("title", "slide")
            for t in ev.on_screen_text
        ) and any(w.startswith("EV001") for w in ev.warnings)
    value, terms = confidence.compute(
        grounding=grounding,
        slack_ms=slack,
        asr_probs=probs or asr_probs.get(item.id, []),
        asr_disagreement=item.id in asr_disagree,
        ocr_disagrees=ocr_bad,
        repairs_used=item.repair.attempts,
        warnings_count=len(item.warnings),
    )
    return item.model_copy(update={"confidence": value, "confidence_terms": terms})


def findings_to_models(fs: Sequence[Finding]) -> list[FindingModel]:
    return [f.to_model() for f in fs]
