import numpy as np
import pytest
from scipy import stats as ss

from app import stats


def _samples():
    rng = np.random.default_rng(9)
    return [rng.normal(10, 2, 30), rng.exponential(2, 40), rng.lognormal(0, 0.8, 25), rng.normal(0, 1, 150), rng.uniform(0, 1, 60)]


def test_anderson_darling_matches_statsmodels():
    diag = pytest.importorskip("statsmodels.stats.diagnostic")
    for x in _samples():
        r = stats.anderson_darling(x)
        a2, p = diag.normal_ad(x)
        assert np.isclose(r["A2"], a2, rtol=1e-8) and np.isclose(r["p"], p, rtol=1e-6, atol=1e-12)


def test_ks_lilliefors_matches_statsmodels_dallal_wilkinson():
    diag = pytest.importorskip("statsmodels.stats.diagnostic")
    for x in _samples():
        r = stats.ks_normality(x)
        D, p = diag.lilliefors(x, pvalmethod="approx")
        assert np.isclose(r["D"], D, rtol=1e-8)
        if not r["p_over_010"]:
            assert np.isclose(r["p"], p, rtol=1e-6)


def test_ks_two_sample_and_ratio_paired():
    a = [3.1, 2.8, 4.0, 3.5, 2.9, 3.8, 3.3, 3.6]
    b = [4.6, 4.1, 6.2, 5.0, 4.3, 5.9, 4.8, 5.7]
    r = stats.t_test(a, b, kind="ks")
    assert np.isclose(r["p"], ss.ks_2samp(b, a).pvalue)
    rp = stats.t_test(a, b, kind="ratio_paired")
    ref = ss.ttest_rel(np.log10(b), np.log10(a))
    assert np.isclose(rp["p"], ref.pvalue)
    assert np.isclose(rp["difference"], np.exp(np.mean(np.log(np.array(b) / np.array(a)))))
    with pytest.raises(ValueError):
        stats.t_test([1, -2, 3], [2, 3, 4], kind="ratio_paired")
