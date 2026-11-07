import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import multivar
from app.main import app

approx = lambda v, rel=1e-5: pytest.approx(v, rel=rel)  # noqa: E731
rng = np.random.default_rng(11)
N = 60
X1 = rng.normal(50, 10, N); X2 = rng.normal(25, 4, N); X3 = rng.normal(0, 1, N)
Y = 10 + 0.5 * X1 - 1.2 * X2 + rng.normal(0, 3, N)


def test_mlr_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    ref = sm.OLS(Y, sm.add_constant(np.column_stack([X1, X2, X3]))).fit()
    r = multivar.multiple_linear(list(Y), [list(X1), list(X2), list(X3)], "Y", ["X1", "X2", "X3"])
    assert [c["estimate"] for c in r["coefs"]] == [approx(v) for v in ref.params]
    assert [c["se"] for c in r["coefs"]] == [approx(v) for v in ref.bse]
    assert [c["p"] for c in r["coefs"]] == [approx(v, 1e-4) for v in ref.pvalues]
    assert r["r_squared"] == approx(ref.rsquared) and r["adj_r_squared"] == approx(ref.rsquared_adj)
    assert r["F"] == approx(ref.fvalue)
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    ex = sm.add_constant(np.column_stack([X1, X2, X3]))
    assert r["coefs"][1]["vif"] == approx(variance_inflation_factor(ex, 1), 1e-4)


def test_logistic_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    eta = -8 + 0.12 * X1 + 0.05 * X2
    yb = (rng.random(N) < 1 / (1 + np.exp(-eta))).astype(int)
    ref = sm.Logit(yb, sm.add_constant(np.column_stack([X1, X2]))).fit(disp=0)
    r = multivar.logistic(list(yb), [list(X1), list(X2)], "Event", ["X1", "X2"])
    assert [c["estimate"] for c in r["coefs"]] == [approx(v, 1e-4) for v in ref.params]
    assert [c["se"] for c in r["coefs"]] == [approx(v, 1e-4) for v in ref.bse]
    assert r["loglik"] == approx(ref.llf, 1e-6) and r["lr_chi2"] == approx(ref.llr, 1e-5)
    assert r["mcfadden_r2"] == approx(ref.prsquared, 1e-5)


def test_errors_and_missing_rows():
    with pytest.raises(ValueError):
        multivar.logistic([0, 1, 2, 1], [[1, 2, 3, 4]], "y", ["x"])
    with pytest.raises(ValueError):
        multivar.multiple_linear([1, 2, 3, 4, 5], [[1, 2, 3, 4, 5], [2, 4, 6, 8, 10]], "y", ["a", "b"])
    r = multivar.multiple_linear([1, 2, 3, 4, 5, 6, None], [[1, 2, 3, 4, 5, 7, 8]], "y", ["x"])
    assert r["n"] == 6 and r["dropped"] == 1
    c = TestClient(app)
    res = c.post("/api/multi", json={"columns": [list(Y), list(X1), list(X2), []], "names": ["Y", "X1", "X2", "empty"], "analysis": "mlr"})
    assert res.status_code == 200 and len(res.json()["coefs"]) == 3


def test_logistic_large_intercept_is_not_separation():
    # predictors in large units give a large intercept; that must not be mistaken for separation
    rng2 = np.random.default_rng(3)
    age = rng2.uniform(40, 80, 200)
    yb = (rng2.random(200) < 1 / (1 + np.exp(-(-30 + 0.5 * age)))).astype(int)
    r = multivar.logistic(list(yb), [list(age)], "y", ["Age"])
    assert abs(r["coefs"][0]["estimate"]) > 25 and r["coefs"][1]["or"] > 1
    with pytest.raises(ValueError):
        multivar.logistic([0, 0, 0, 1, 1, 1], [[1, 2, 3, 4, 5, 6]], "y", ["x"])


def test_standardized_coefficients():
    import numpy as np
    from app import multivar
    rng = np.random.default_rng(8)
    x1, x2 = rng.normal(0, 3, 40), rng.normal(5, 1, 40)
    y = 2 + 0.5 * x1 - 1.5 * x2 + rng.normal(0, 1, 40)
    r = multivar.multiple_linear(y.tolist(), [x1.tolist(), x2.tolist()], "y", ["x1", "x2"])
    z = lambda v: (v - v.mean()) / v.std(ddof=1)  # noqa: E731
    beta = np.linalg.lstsq(np.column_stack([np.ones(40), z(x1), z(x2)]), z(y), rcond=None)[0]
    assert np.allclose([c["std_beta"] for c in r["coefs"][1:]], beta[1:])
