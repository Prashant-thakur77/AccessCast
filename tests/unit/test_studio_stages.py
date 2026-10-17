from accesscast.review.studio import STAGE_WORDS, stage_states


def test_stage_states_follow_the_latest_event_and_keep_the_order():
    events = [
        {"stage": "ingest", "event": "start"},
        {"stage": "ingest", "event": "done", "wall_s": 1.5},
        {"stage": "asr", "event": "start"},
        {"stage": "asr_crosscheck", "event": "skipped", "reason": "ACCESSCAST_AUDIO_MODEL=none"},
        {"stage": "evidence", "event": "error", "error": "ModelEndpointError: 503"},
        {"stage": "asr", "event": "progress"},
    ]
    st = {s["stage"]: s for s in stage_states(events)}
    assert [s["stage"] for s in stage_states(events)] == [s for s, _ in STAGE_WORDS]
    assert st["ingest"]["state"] == "done" and st["ingest"]["seconds"] == 1.5
    assert st["asr"]["state"] == "running"
    assert st["asr_crosscheck"]["state"] == "skipped" and "none" in st["asr_crosscheck"]["note"]
    assert st["evidence"]["state"] == "failed" and "503" in st["evidence"]["note"]
    assert st["tts"]["state"] == "waiting"


def test_a_skipped_stage_that_then_reports_done_shows_as_not_run():
    events = [
        {"stage": "speakers", "event": "start"},
        {"stage": "speakers", "event": "skipped", "reason": "gated model not accepted"},
        {"stage": "speakers", "event": "done", "wall_s": 0.1},
    ]
    st = {s["stage"]: s for s in stage_states(events)}
    assert st["speakers"]["state"] == "skipped" and "gated" in st["speakers"]["note"]
