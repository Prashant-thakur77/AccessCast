import pytest

from accesscast.project import write_jsonl
from accesscast.review import gate
from accesscast.review.store import ReviewStore, RevisionConflict
from accesscast.schemas import ItemKind
from tests.unit.conftest import make_item


@pytest.fixture
def store(tmp_path):
    (tmp_path / "items").mkdir()
    write_jsonl(tmp_path / "items" / "ad.en.jsonl", [make_item("The woman presses Tab.", id="ad.en.0001")])
    sdh = make_item("Hello there.", id="sdh.en.0001", kind=ItemKind.SDH, budget=None)
    write_jsonl(tmp_path / "items" / "sdh.en.jsonl", [sdh])
    s = ReviewStore(tmp_path)
    s.init_from_items()
    return s


def test_patch_needs_expected_revision(store):
    cur = store.patch("ad.en.0001", 0, {"status": "approved"}, who="reviewer-1")
    assert cur["revision"] == 1 and cur["reviewer"] == "reviewer-1"
    with pytest.raises(RevisionConflict) as e:
        store.patch("ad.en.0001", 0, {"status": "rejected"}, who="reviewer-2")
    assert e.value.current == 1
    assert len(store.hist_p.read_text().splitlines()) == 1


def test_gate_refuses_pending_and_binds_to_state_hash(store, tmp_path):
    res = gate.evaluate(store.merged(), ["blind.en"], store.state_sha256())
    assert not res.ok and res.blocking == ["ad.en.0001"]
    store.patch("ad.en.0001", 0, {"status": "approved"}, who="reviewer-1")
    res = gate.evaluate(store.merged(), ["blind.en"], store.state_sha256())
    assert res.ok and res.human_reviewed
    gate.write_validation(tmp_path, res)
    gate.check_fresh(tmp_path, store)
    store.patch("ad.en.0001", 1, {"reviewer_note": "late edit"}, who="reviewer-1")
    with pytest.raises(PermissionError):
        gate.check_fresh(tmp_path, store)


def test_auto_approval_never_counts_as_human_for_description(store):
    store.auto_approve(["ad.en.0001"], "test")
    res = gate.evaluate(store.merged(), ["blind.en"], store.state_sha256())
    assert res.ok and not res.human_reviewed


def test_fields_outside_contract_rejected(store):
    with pytest.raises(ValueError):
        store.patch("ad.en.0001", 0, {"draft": "sneaky"}, who="x")
