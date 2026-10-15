from accesscast.repair.loop import run_repair_loop
from accesscast.verify.base import Finding, VerificationResult

BAD = Finding("AD007", "error", "13 words", "≤ 10", "Shorten.", "write_ad")


def _verify(text, facts):
    return VerificationResult(
        ok=len(text.split()) <= 3, violations=[] if len(text.split()) <= 3 else [BAD], warnings=[]
    )


def test_repairs_then_passes():
    out = run_repair_loop("a b c d e", ["F1"], _verify, lambda k, t, v: (" ".join(t.split()[:-1]), ["F1"]))
    assert out.ok and out.stop_reason == "safe_model_revision" and out.attempts == 2


def test_never_promotes_failure():
    out = run_repair_loop("a b c d e f g h", ["F1"], _verify, lambda k, t, v: (t, ["F1"]))
    assert not out.ok and out.stop_reason == "repair_limit_reached" and len(out.history) == 4


def test_generation_failure_fails_closed():
    def boom(k, t, v):
        raise RuntimeError("endpoint down")

    out = run_repair_loop("a b c d e", ["F1"], _verify, boom)
    assert not out.ok and out.stop_reason == "revision_generation_failed"


def test_arm_b_does_not_repair():
    out = run_repair_loop("a b c d e", ["F1"], _verify, lambda k, t, v: ("a", []), enabled=False)
    assert not out.ok and out.attempts == 0
