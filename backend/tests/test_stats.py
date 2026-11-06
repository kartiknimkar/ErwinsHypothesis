"""Checks the statistics engine against hand-computed and published reference values."""
import math

import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import stats
from app.main import app


def approx(v, rel=1e-4):
    return pytest.approx(v, rel=rel)


# ---- t tests -------------------------------------------------------------

def test_unpaired_t_by_hand():
    a, b = [1, 2, 3, 4, 5], [3, 4, 5, 6, 7]
    r = stats.t_test(a, b, kind="unpaired")
    # pooled SD = sqrt(2.5); SE of difference = 1.0; t = 2; df = 8
    assert r["difference"] == approx(2.0)
    assert r["statistic"] == approx(2.0)
    assert r["df"] == approx(8)
    assert r["p"] == approx(2 * sps.t.sf(2.0, 8))
    tc = sps.t.ppf(0.975, 8)
    assert r["ci_low"] == approx(2 - tc) and r["ci_high"] == approx(2 + tc)
    assert r["stars"] == "ns"


def test_welch_df_by_hand():
    a, b = [10, 12, 11, 13, 9, 11], [20, 25, 15, 30]
    r = stats.t_test(a, b, kind="welch")
    va, vb = 2.0, 125 / 3  # sample variances
    se2 = va / 6 + vb / 4
    df = se2 ** 2 / ((va / 6) ** 2 / 5 + (vb / 4) ** 2 / 3)
    assert r["df"] == approx(df)
    assert r["statistic"] == approx((22.5 - 11) / math.sqrt(se2))


def test_paired_t_by_hand():
    a, b = [1, 2, 3, 4, 5], [2, 4, 5, 5, 8]
    r = stats.t_test(a, b, kind="paired")
    d = [1, 2, 2, 1, 3]
    sd = math.sqrt(sum((x - 1.8) ** 2 for x in d) / 4)
    t = 1.8 / (sd / math.sqrt(5))
    assert r["statistic"] == approx(t)
    assert r["df"] == approx(4)
    assert r["p"] == approx(2 * sps.t.sf(t, 4))
    assert r["stars"] == "**"


def test_paired_drops_incomplete_rows():
    r = stats.t_test([1, 2, None, 4, 5], [2, 4, 5, "", 8], kind="paired")
    assert r["n_pairs"] == 3


def test_blank_cells_ignored_and_errors():
    r = stats.t_test([1, "", 3, None, 5], [2, 4, 6], kind="unpaired")
    assert r["groups"][0]["n"] == 3
    with pytest.raises(ValueError):
        stats.t_test([1], [2, 3])


def test_mann_whitney_known_value():
    # Complete separation, n=4 and 4: U = 0, exact two-sided p = 2/70
    r = stats.t_test([1, 2, 3, 4], [5, 6, 7, 8], kind="mannwhitney")
    assert r["statistic"] == 0
    assert r["p"] == approx(2 / 70)


# ---- linear regression ---------------------------------------------------

ANSCOMBE_X = [10, 8, 13, 9, 11, 14, 6, 4, 12, 7, 5]
ANSCOMBE_Y = [8.04, 6.95, 7.58, 8.81, 8.33, 9.96, 7.24, 4.26, 10.84, 4.82, 5.68]


def test_regression_anscombe():
    # Published values for Anscombe's quartet, data set I
    r = stats.linear_regression(ANSCOMBE_X, ANSCOMBE_Y)
    assert r["slope"] == approx(0.500090909, rel=1e-6)
    assert r["intercept"] == approx(3.000090909, rel=1e-6)
    assert r["r_squared"] == approx(0.666542, rel=1e-5)
    assert r["slope_se"] == approx(0.117906, rel=1e-4)
    assert r["df"] == 9
    assert r["p"] == approx(0.00217, rel=1e-2)
    # confidence band contains the fitted line
    for lo, f, hi in zip(r["line"]["low"], r["line"]["y"], r["line"]["high"]):
        assert lo < f < hi


def test_regression_errors():
    with pytest.raises(ValueError):
        stats.linear_regression([1, 2], [1, 2])
    with pytest.raises(ValueError):
        stats.linear_regression([3, 3, 3], [1, 2, 3])


# ---- API -----------------------------------------------------------------

def test_api_roundtrip():
    c = TestClient(app)
    assert c.get("/api/health").json()["status"] == "ok"
    r = c.post("/api/ttest", json={"a": [1, 2, 3], "b": [4, 5, 6]})
    assert r.status_code == 200 and r.json()["test_name"] == "Unpaired t test"
    r = c.post("/api/ttest", json={"a": [1], "b": [4, 5, 6]})
    assert r.status_code == 400
    r = c.post("/api/regression", json={"x": ANSCOMBE_X, "y": ANSCOMBE_Y})
    assert r.status_code == 200
    assert c.get("/vendor/plotly.min.js").status_code == 200
