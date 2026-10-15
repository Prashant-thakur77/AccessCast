from accesscast.schemas import Gap, SceneEvidence
from accesscast.write.plan_ad import Calibration, plan_description


def test_pauses_in_failed_scenes_go_to_a_person():
    gaps = [Gap(gap_id="G0001", start_ms=2000, end_ms=8000, len_ms=6000, scene_id="SC001")]
    ev = {"SC001": SceneEvidence(scene_id="SC001", frames=[], status="evidence_failed")}
    plans = plan_description(gaps, ev, [], [], Calibration(voice="af_heart", wps_voice=2.6))
    assert len(plans) == 1 and plans[0].facts == [] and plans[0].gap is gaps[0]
