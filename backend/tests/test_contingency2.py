import numpy as np
import pytest
from scipy import stats as ss

from app import contingency


def test_trend_matches_linear_by_linear():
    t = np.array([[10, 40], [18, 32], [25, 25], [33, 17]])
    r = contingency.trend(t)
    sm = pytest.importorskip("statsmodels.stats.contingency_tables")
    ref = sm.Table(t).test_ordinal_association(row_scores=np.arange(1, 5), col_scores=np.array([1, 0]))
    N = t.sum()
    # Cochran-Armitage (Altman) = linear-by-linear association × N/(N−1)
    assert np.isclose(r["chi2"], ref.zscore ** 2 * N / (N - 1), rtol=1e-8)
    assert r["direction"] == "rising"
    full = contingency.analyze(t.tolist(), list("abcd"), ["yes", "no"])
    assert "trend" in full


def test_mcnemar():
    sm = pytest.importorskip("statsmodels.stats.contingency_tables")
    t = [[45, 12], [4, 39]]
    r = contingency.mcnemar(t, ["Before +", "Before −"], ["After +", "After −"])
    ref_exact = sm.mcnemar(np.array(t), exact=True)
    ref_chi = sm.mcnemar(np.array(t), exact=False, correction=True)
    assert np.isclose(r["p"], ref_exact.pvalue) and np.isclose(r["chi2"], ref_chi.statistic) and np.isclose(r["p_chi2"], ref_chi.pvalue)
    assert r["odds_ratio"]["value"] == 3


def test_goodness_of_fit():
    r = contingency.goodness_of_fit(["AA", "Aa", "aa"], [30, 52, 18], [25, 50, 25], expected_is_pct=True)
    ref = ss.chisquare([30, 52, 18], [25, 50, 25])
    assert np.isclose(r["chi2"], ref.statistic) and np.isclose(r["p"], ref.pvalue)
    b = contingency.goodness_of_fit(["M", "F"], [62, 38], [1, 1])
    assert np.isclose(b["binomial_p"], ss.binomtest(62, 100, 0.5).pvalue)
    with pytest.raises(ValueError):
        contingency.goodness_of_fit(["a", "b"], [1, 2], [0, 1])
