import numpy as np
import pytest

from app import multivar


def _data():
    rng = np.random.default_rng(11)
    true = rng.uniform(2, 12, 30)
    x = true + rng.normal(0, 0.4, 30)
    y = 0.3 + 1.08 * true + rng.normal(0, 0.6, 30)
    return x, y


def test_equal_precision_is_orthogonal_regression():
    x, y = _data()
    r = multivar.deming(x.tolist(), y.tolist())
    # total least squares: first principal axis of the centered data
    X = np.column_stack([x - x.mean(), y - y.mean()])
    v = np.linalg.svd(X, full_matrices=False)[2][0]
    assert np.isclose(r["slope"], v[1] / v[0], rtol=1e-10)
    assert np.isclose(r["intercept"], y.mean() - r["slope"] * x.mean())


def test_unequal_precision_matches_scipy_odr():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        odr = pytest.importorskip("scipy.odr")  # deprecated in SciPy 1.17, removed in 1.19
    x, y = _data()
    ratio = 1.5  # SD of Y error / SD of X error
    r = multivar.deming(x.tolist(), y.tolist(), sd_ratio=ratio)
    fit = odr.ODR(odr.RealData(x, y, sx=np.full(len(x), 1.0), sy=np.full(len(y), ratio)), odr.unilinear, beta0=[1.0, 0.0]).run()
    assert np.isclose(r["slope"], fit.beta[0], rtol=1e-5) and np.isclose(r["intercept"], fit.beta[1], rtol=1e-4)  # ODR iterates to ~1e-6


def test_jackknife_and_tests():
    x, y = _data()
    r = multivar.deming(x.tolist(), y.tolist())
    assert r["slope_ci"][0] < r["slope"] < r["slope_ci"][1] and r["slope_se"] > 0
    assert 0 <= r["p_slope_1"] <= 1 and len(r["line"]["x"]) == 50
