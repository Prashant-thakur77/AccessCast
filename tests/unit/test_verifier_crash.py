from accesscast.verify.base import run_rules
from tests.unit.conftest import make_item


def _boom(item, ctx):
    raise RuntimeError("bad input")


def test_crash_fails_closed(ctx):
    res = run_rules(make_item("The woman presses Tab."), ctx, [_boom])
    assert not res.ok
    assert res.violations[0].rule == "VERIFIER_CRASH"
    assert res.violations[0].repairable is False
