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
