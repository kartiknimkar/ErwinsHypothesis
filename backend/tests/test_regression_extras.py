import numpy as np
import pytest

from app import stats

X = [1, 2, 3, 4, 5, 6, 7, 8]
Y = [2.3, 3.9, 6.4, 8.1, 9.7, 12.5, 13.8, 16.2]


def test_origin_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    r = stats.linear_regression(X, Y, origin=True)
    ref = sm.OLS(np.array(Y), np.array(X, float)).fit()
    assert np.isclose(r["slope"], ref.params[0]) and np.isclose(r["slope_se"], ref.bse[0]) and np.isclose(r["p"], ref.pvalues[0])
    pr = ref.get_prediction(np.array([r["line"]["x"][-1]])).summary_frame(alpha=0.05)
    assert np.isclose(r["line"]["pred_high"][-1], pr["obs_ci_upper"].iloc[0]) and np.isclose(r["line"]["high"][-1], pr["mean_ci_upper"].iloc[0])


def test_prediction_band_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    r = stats.linear_regression(X, Y)
    ref = sm.OLS(np.array(Y), sm.add_constant(np.array(X, float))).fit()
    xg = np.array(r["line"]["x"])
    fr = ref.get_prediction(sm.add_constant(xg)).summary_frame(alpha=0.05)
    assert np.allclose(r["line"]["pred_low"], fr["obs_ci_lower"]) and np.allclose(r["line"]["low"], fr["mean_ci_lower"])
