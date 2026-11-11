import numpy as np

from app.demo.check_confidence import paired_bootstrap, wape


def test_wape_is_total_error_over_total_sold():
    assert wape(np.array([2.0, 0.0]), np.array([1.0, 3.0])) == 1.0


def test_point_values_match_plain_wape():
    actual = np.array([5.0, 0.0, 10.0, 3.0])
    chosen = np.array([4.0, 1.0, 9.0, 3.0])
    baseline = np.array([2.0, 2.0, 6.0, 5.0])
    stats = paired_bootstrap(chosen, baseline, actual, resamples=300)
    assert stats["chosen"][0] == wape(chosen, actual)
    assert stats["baseline"][0] == wape(baseline, actual)
    assert abs(stats["gain"][0] - (1 - wape(chosen, actual) / wape(baseline, actual))) < 1e-12


def test_interval_contains_point_and_is_ordered():
    rng = np.random.default_rng(0)
    actual = rng.poisson(5, 400).astype(float)
    chosen = actual + rng.normal(0, 1, 400)
    baseline = actual + rng.normal(0, 3, 400)
    for low_high in paired_bootstrap(chosen, baseline, actual, resamples=500).values():
        point, low, high = low_high
        assert low <= point <= high


def test_same_seed_gives_same_interval():
    actual = np.arange(1.0, 50.0)
    a = paired_bootstrap(actual * 1.1, actual * 1.5, actual, resamples=200, seed=3)
    b = paired_bootstrap(actual * 1.1, actual * 1.5, actual, resamples=200, seed=3)
    assert a == b
