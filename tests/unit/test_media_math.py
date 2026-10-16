import pytest

from accesscast import constants as C
from accesscast.media.mix import gain_envelope
from accesscast.media.timeline import Insertion, build_timeline, ms_to_samples, remap_ms


def test_gain_envelope_dips_by_the_set_amount_with_ramps():
    n = ms_to_samples(10_000)
    env = gain_envelope(n, [(4000, 6000, 9.0)])
    lo = 10 ** (-9.0 / 20)
    assert env[ms_to_samples(1000)] == pytest.approx(1.0)
    assert env[ms_to_samples(5000)] == pytest.approx(lo, rel=1e-5)
    mid_ramp = env[ms_to_samples(4000 - C.DUCK_RAMP_MS // 2)]
    assert lo < mid_ramp < 1.0
    assert env[ms_to_samples(9000)] == pytest.approx(1.0)


def test_overlapping_dips_take_the_deeper_one():
    env = gain_envelope(ms_to_samples(5000), [(1000, 3000, 6.0), (2000, 4000, 12.0)])
    assert env[ms_to_samples(2500)] == pytest.approx(10 ** (-12 / 20), rel=1e-5)


def test_extended_timeline_maps_monotonically_and_adds_insertions():
    src = ms_to_samples(20_000)
    ins = [
        Insertion("a", ms_to_samples(5000), ms_to_samples(2000), ms_to_samples(150), ms_to_samples(150)),
        Insertion("b", ms_to_samples(12000), ms_to_samples(1000), ms_to_samples(150), ms_to_samples(150)),
    ]
    rows = build_timeline(src, ins)
    assert rows[-1]["output_end_ms"] == 20_000 + 2300 + 1300
    times = [remap_ms(rows, t) for t in range(0, 20_001, 500)]
    assert times == sorted(times)
    assert remap_ms(rows, 4000) == 4000 and remap_ms(rows, 6000) == 8300 and remap_ms(rows, 13000) == 16600


def test_insertion_outside_source_is_refused():
    with pytest.raises(ValueError):
        build_timeline(1000, [Insertion("x", 5000, 10, 1, 1)])
