import itertools
import math

import numpy as np

from app import curvefit, stats


def test_exact_runs_distribution_by_enumeration():
    for n1, n2 in ((3, 4), (5, 5), (2, 6)):
        seqs = set(itertools.permutations([1] * n1 + [-1] * n2))
        counts = {}
        for sq in seqs:
            r = 1 + sum(a != b for a, b in zip(sq, sq[1:]))
            counts[r] = counts.get(r, 0) + 1
        total = len(seqs)
        assert total == math.comb(n1 + n2, n1)
        for r in range(2, n1 + n2 + 1):
            assert np.isclose(stats._runs_cdf(r, n1, n2), sum(v for k, v in counts.items() if k <= r) / total)


def test_runs_flags_wrong_model():
    x = np.linspace(0, 10, 15)
    y = 0.5 * x ** 2 + np.random.default_rng(1).normal(0, 0.3, 15)  # curved data, straight-line fit
    r = stats.linear_regression(x.tolist(), y.tolist())
    assert r["runs_test"]["deviates"] and r["runs_test"]["runs"] <= 4
    assert len(r["residuals"]["x"]) == 15


def test_nonlinear_fit_returns_residuals_in_user_units():
    conc = [0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100]
    resp = [98, 96, 92, 80, 52, 30, 13, 7, 6]
    f = curvefit.fit(conc, resp, "dr_inhibit")
    assert np.allclose(f["residuals"]["x"], conc) and f["runs_test"] is not None
