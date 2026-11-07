import itertools

import numpy as np
from scipy import stats as ss

from app import stats


def test_null_distributions_by_enumeration():
    m, n = 3, 4
    us = [sum(1 for i in comb for j in set(range(7)) - set(comb) if j < i) for comb in itertools.combinations(range(7), m)]
    # U counted as (# of sample-2 values below each sample-1 value) over all rank assignments
    emp = np.cumsum(np.bincount(us, minlength=m * n + 1)) / len(us)
    assert np.allclose(stats._mw_null_cdf(m, n), emp)
    nn = 5
    ts = [sum(k + 1 for k in range(nn) if (mask >> k) & 1) for mask in range(2 ** nn)]
    emp2 = np.cumsum(np.bincount(ts, minlength=nn * (nn + 1) // 2 + 1)) / 2 ** nn
    assert np.allclose(stats._signed_rank_null_cdf(nn), emp2)


def test_hl_estimates_and_coverage():
    a, b = [1.1, 2.3, 1.8, 2.9, 2.2, 1.5], [3.4, 2.8, 4.1, 3.9, 3.0, 4.4, 3.6]
    r = stats.hodges_lehmann(a, b)
    assert np.isclose(r["estimate"], np.median(np.subtract.outer(b, a)))
    assert r["ci"][0] <= r["estimate"] <= r["ci"][1]
    rng = np.random.default_rng(1)
    hits = 0
    for _ in range(400):
        x, y = rng.normal(0, 1, 8), rng.normal(1, 1, 9)
        ci = stats.hodges_lehmann(x, y)["ci"]
        hits += ci[0] <= 1 <= ci[1]
    assert hits / 400 >= 0.93
    w = stats.t_test(a, b[:6], kind="wilcoxon")
    assert w["hodges_lehmann"]["ci"] is not None
    mw = stats.t_test(a, b, kind="mannwhitney")
    assert np.isclose(mw["hodges_lehmann"]["estimate"], r["estimate"])
