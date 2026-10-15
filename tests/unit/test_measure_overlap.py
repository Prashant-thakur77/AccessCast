from eval.measure_overlap import Span, coverage, fits


def test_fits_and_tolerance():
    cues = [Span(0, 1000), Span(5000, 6000)]
    assert fits(Span(1200, 4900), cues)[0]
    assert fits(Span(960, 3000), cues)[0]  # 40 ms overlap is within the 50 ms tolerance
    assert not fits(Span(900, 3000), cues)[0]
    ok, _, why = fits(Span(4000, 5200), cues)
    assert not ok


def test_coverage_window():
    assert coverage([Span(1000, 2000)], [3500, 9000]) == (1, 2)
