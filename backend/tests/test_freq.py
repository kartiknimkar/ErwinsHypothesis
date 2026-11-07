import numpy as np
from scipy import stats as ss

from app import stats


def test_counts_and_edges():
    x = [1, 1.5, 2, 2, 2.9, 3, 4.99, 5]
    r = stats.frequency_distribution([x], ["A"], bin_width=1, bin_start=1)
    assert r["edges"] == [1, 2, 3, 4, 5, 6]
    # [1,2): 1, 1.5 | [2,3): 2, 2, 2.9 | [3,4): 3 | [4,5): 4.99 | [5,6): 5  (edge values go to the higher bin)
    assert r["groups"][0]["counts"] == [2, 3, 1, 1, 1]
    assert r["centers"][0] == 1.5
    pct = stats.frequency_distribution([x], ["A"], bin_width=1, bin_start=1, y="percent", cumulative=True)
    assert pct["groups"][0]["values"][-1] == 100
    assert abs(pct["groups"][0]["values"][0] - 25) < 1e-9


def test_auto_width_is_readable_and_covers_data():
    rng = np.random.default_rng(1)
    a, b = rng.normal(50, 10, 200), rng.normal(60, 8, 150)
    r = stats.frequency_distribution([a.tolist(), b.tolist()], ["a", "b"])
    h = r["bin_width"]
    m = h / 10 ** np.floor(np.log10(h))
    assert any(abs(m - k) < 1e-9 for k in (1, 2, 2.5, 5))
    assert r["edges"][0] <= min(a.min(), b.min()) and r["edges"][-1] > max(a.max(), b.max())
    assert sum(r["groups"][0]["counts"]) == 200 and sum(r["groups"][1]["counts"]) == 150
    assert np.allclose(np.histogram(a, bins=r["edges"])[0], r["groups"][0]["counts"])


def test_qq_matches_r_qqnorm_positions():
    x = [3.1, 2.2, 5.0, 4.4, 3.9, 2.8, 4.1, 3.3, 3.6, 4.8, 2.5, 3.0]
    q = stats.frequency_distribution([x], ["A"])["groups"][0]["qq"]
    n = len(x)
    ppoints = (np.arange(1, n + 1) - 0.5) / n  # R ppoints for n > 10
    assert np.allclose(q["z"], ss.norm.ppf(ppoints))
    assert q["actual"] == sorted(x)
    small = stats.frequency_distribution([x[:6]], ["A"])["groups"][0]["qq"]
    assert np.allclose(small["z"], ss.norm.ppf((np.arange(1, 7) - 0.375) / 6.25))


def test_bad_inputs():
    import pytest
    with pytest.raises(ValueError):
        stats.frequency_distribution([[1, 2, 3]], ["A"], bin_width=0)
    with pytest.raises(ValueError):
        stats.frequency_distribution([[1, 2, 3]], ["A"], bin_width=1e-6)
    with pytest.raises(ValueError):
        stats.frequency_distribution([[1, 2, 3]], ["A"], bin_width=1, bin_start=2)
