from accesscast.schemas import SceneEvidence, VadSegment, VisibleFact
from accesscast.write.plan_ad import Calibration, plan_description
from tests.unit.conftest import make_words

CAL = Calibration(voice="af_heart", wps_voice=3.0)


def _ev(frame_ms: int) -> dict[str, SceneEvidence]:
    f = VisibleFact(fid="F001", frames=[0], text="A red door opens.", priority=4, important=True)
    return {
        "SC001": SceneEvidence(scene_id="SC001", frames=["f00.jpg"], frame_ms=[frame_ms], visible_facts=[f])
    }


def test_extended_line_holds_at_a_breath_near_the_event_not_seconds_later():
    # One long VAD segment (continuous narration 0–30 s), a 300 ms breath at 15.0 s, event at 15.5 s.
    words = make_words([("one", 1000, 14000), ("two", 15300, 29000)])
    vad = [VadSegment(start_ms=900, end_ms=29500)]
    plans = plan_description([], _ev(15500), words, vad, CAL)
    assert len(plans) == 1 and plans[0].extended
    assert plans[0].anchor_ms == 14000


def test_extended_line_never_splits_a_word_when_no_breath_is_near():
    words = make_words([("one", 1000, 29000)])
    vad = [VadSegment(start_ms=900, end_ms=29500)]
    plans = plan_description([], _ev(15500), words, vad, CAL)
    assert plans[0].anchor_ms == 29500  # next boundary after the event; AD005 then sends it to a person


def test_long_pause_holds_several_lines_in_time_order_with_disjoint_slots():
    from accesscast.schemas import Gap

    facts = [
        VisibleFact(
            fid=f"F00{i}", frames=[i], text=f"Fact number {i} is visible.", priority=4, important=True
        )
        for i in range(3)
    ]
    ev = {
        "SC001": SceneEvidence(
            scene_id="SC001", frames=["a", "b", "c"], frame_ms=[1000, 6000, 11000], visible_facts=facts
        )
    }
    gap = Gap(gap_id="G001", start_ms=0, end_ms=15000, len_ms=15000, scene_id="SC001")
    plans = plan_description([gap], ev, [], [], CAL)
    assert [p.extended for p in plans] == [False, False, False]
    assert [p.anchor_ms for p in plans] == [0, 4000, 9000]
    for a, b in zip(plans, plans[1:], strict=False):
        assert a.slot_end_ms <= b.anchor_ms
