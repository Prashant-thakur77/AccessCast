from accesscast.schemas import Scene
from accesscast.write.evidence import check_evidence


def test_facts_as_strings_raise_cleanly_or_error():
    scene = Scene(scene_id="SC001", start_ms=0, end_ms=10000, shots=["SH001"])
    try:
        _ev, errors, _ = check_evidence({"visible_facts": ["a person", "a desk"]}, scene, 2, "", "")
    except Exception:
        return  # gather_evidence catches this and re-asks, then marks evidence_failed
    assert errors
