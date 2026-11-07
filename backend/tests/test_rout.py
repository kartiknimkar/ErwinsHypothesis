import numpy as np

from app import outliers


def _bh_reference(p, q):
    """Benjamini-Hochberg step-up (statsmodels-free): reject the k smallest P with P_(k) < q k / n."""
    n = len(p)
    order = np.argsort(p)
    ok = np.nonzero(p[order] < q * np.arange(1, n + 1) / n)[0]
    mask = np.zeros(n, bool)
    if len(ok):
        mask[order[: ok[-1] + 1]] = True
    return mask


def test_fdr_rule_equals_bh_step_up_on_residual_p_values():
    from scipy import stats
    rng = np.random.default_rng(3)
    for _ in range(50):
        r = rng.standard_t(3, 25)
        k = 2
        s = outliers.rsdr(r, k)
        p = 2 * stats.t.sf(np.abs(r) / s, len(r) - k)
        assert (outliers.fdr_outliers(r, k, 0.05) == _bh_reference(p, 0.05)).all()


def test_rsdr_formula():
    r = np.array([-3, -1, 0.5, 1, 2, 4, -0.2, 0.1])
    assert np.isclose(outliers.rsdr(r, 2), np.percentile(np.abs(r), 68.27) * 8 / 6)


def test_column_finds_gross_outlier_only():
    x = [10.1, 9.8, 10.4, 10.0, 9.7, 10.2, 10.3, 9.9, 25.0]
    r = outliers.rout_column(x, 0.01)
    assert [o["value"] for o in r["outliers"]] == [25.0]
    assert abs(r["robust_center"] - 10.05) < 0.3
    # two outliers: Grubbs is often masked here, ROUT finds both
    r2 = outliers.rout_column(x + [24.0], 0.01)
    assert sorted(o["value"] for o in r2["outliers"]) == [24.0, 25.0]


def test_gaussian_data_rarely_flagged():
    rng = np.random.default_rng(0)
    flagged = sum(bool(outliers.rout_column(rng.normal(0, 1, 20).tolist(), 0.01)["outliers"]) for _ in range(300))
    assert flagged / 300 < 0.08  # Prism's documentation: about 2-3% of Gaussian experiments at Q = 1%


def test_curve_fit_with_rout_removes_outlier_and_refits():
    from app import curvefit
    x = np.array([-9, -8.5, -8, -7.5, -7, -6.5, -6, -5.5, -5] * 2, float)
    top, bottom, ic50, h = 100, 0, -7, -1
    y = bottom + (top - bottom) / (1 + 10 ** ((x - ic50) * -h))
    rng = np.random.default_rng(5)
    y = y + rng.normal(0, 2, len(y))
    y[4] += 45  # gross outlier
    res = curvefit.fit((10 ** x).tolist(), y.tolist(), "dr_inhibit", rout_q=0.01)
    assert len(res["outliers"]) == 1 and abs(res["outliers"][0]["y"] - y[4]) < 1e-9
    assert res["n"] == len(x) - 1
    clean = curvefit.fit((10 ** np.delete(x, 4)).tolist(), np.delete(y, 4).tolist(), "dr_inhibit")
    names = [p["name"] for p in res["params"]]
    for nm in names:
        a = next(p for p in res["params"] if p["name"] == nm)["value"]
        b = next(p for p in clean["params"] if p["name"] == nm)["value"]
        assert np.isclose(a, b, rtol=1e-5, atol=1e-6)


def test_api_linear_and_groups_with_rout():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    x = list(range(1, 13))
    y = [2.1, 3.9, 6.2, 8.0, 9.8, 12.1, 30.0, 16.1, 17.9, 20.2, 21.8, 24.1]
    r = c.post("/api/fit", json={"x": x, "ys": [y], "model": "linear", "rout_q": 0.01}).json()
    assert r["outliers"] == [{"x": 7.0, "y": 30.0}] and r["n"] == 11
    assert abs(r["slope"] - 2.0) < 0.05
    g = c.post("/api/compare", json={"groups": [[10.1, 9.8, 10.4, 10.0, 9.7, 10.2, 25.0], [12, 13, 12.5, 12.2, 13.1, 12.8]],
                                     "names": ["A", "B"], "kind": "welch", "outliers": True, "outlier_method": "rout"}).json()
    assert g["outliers"][0]["outliers"] == [{"value": 25.0}] and g["outliers"][1]["outliers"] == []
