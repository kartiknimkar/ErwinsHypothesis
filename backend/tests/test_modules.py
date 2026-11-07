"""Curve fitting, survival and contingency checked against known answers and
independent packages (lifelines; skipped if absent)."""
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import contingency, curvefit, survival
from app.main import app

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731


# ---- curve fitting: recover known parameters from noise-free data ---------

def test_dose_response_recovers_ic50():
    conc = np.array([0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000])
    b, t, ic50, h = 5.0, 100.0, 12.0, -1.2
    y = b + (t - b) / (1 + 10 ** ((math.log10(ic50) - np.log10(conc)) * h))
    r = curvefit.fit(conc, y, "dr_inhibit")
    p = {q["name"]: q["value"] for q in r["params"]}
    assert p["Bottom"] == approx(b) and p["Top"] == approx(t) and p["HillSlope"] == approx(h)
    assert r["derived"][0]["value"] == approx(ic50)
    assert r["r_squared"] == approx(1.0)


def test_dose_response_drops_zero_conc_and_accepts_log_x():
    conc = np.array([0, 1, 3, 10, 30, 100, 300])
    y = 100 / (1 + 10 ** ((1.5 - np.log10(np.where(conc > 0, conc, 1))) * 1.0))
    r = curvefit.fit(conc, y, "dr_stim")
    assert r["dropped"] == 1
    r2 = curvefit.fit(np.log10(conc[1:]), y[1:], "dr_stim", x_is_log=True)
    assert r2["derived"][0]["value"] == approx(10 ** 1.5, rel=1e-3)


def test_michaelis_and_exponentials():
    s = np.array([0.5, 1, 2, 4, 8, 16, 32])
    r = curvefit.fit(s, 120 * s / (3 + s), "michaelis")
    p = {q["name"]: q["value"] for q in r["params"]}
    assert p["Vmax"] == approx(120) and p["Km"] == approx(3)
    tt = np.linspace(0, 10, 12)
    r = curvefit.fit(tt, 90 * np.exp(-0.3 * tt) + 10, "exp_decay")
    hl = next(d for d in r["derived"] if d["name"] == "Half-life")
    assert hl["value"] == approx(math.log(2) / 0.3)
    r = curvefit.fit(tt, 2 * np.exp(0.25 * tt), "exp_growth")
    assert next(d for d in r["derived"] if d["name"] == "Doubling time")["value"] == approx(math.log(2) / 0.25)


def test_fit_standard_errors_match_known_formula():
    # A linear-in-parameters model: SEs from curve_fit equal OLS SEs. Use Michaelis
    # with noisy data and compare parameter CI width to t * SE.
    rng = np.random.default_rng(1)
    s = np.repeat([0.5, 1, 2, 4, 8, 16], 3)
    y = 100 * s / (2 + s) + rng.normal(0, 3, len(s))
    r = curvefit.fit(s, y, "michaelis")
    tcrit = sps.t.ppf(0.975, r["df"])
    for q in r["params"]:
        assert (q["ci"][1] - q["ci"][0]) / 2 == approx(tcrit * q["se"])


def test_fit_errors():
    with pytest.raises(ValueError):
        curvefit.fit([1, 2, 3], [1, 2, 3], "dr_inhibit")


# ---- survival ------------------------------------------------------------

T1 = [6, 6, 6, 7, 10, 13, 16, 22, 23, 6, 9, 10, 11, 17, 19, 20, 25, 32, 32, 34, 35]
E1 = [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
T2 = [1, 1, 2, 2, 3, 4, 4, 5, 5, 8, 8, 8, 8, 11, 11, 12, 12, 15, 17, 22, 23]
E2 = [1] * 21  # classic Gehan leukemia data (6-MP vs placebo)


def test_km_matches_lifelines():
    lf = pytest.importorskip("lifelines")
    km = survival.kaplan_meier(np.array(T1, float), np.array(E1))
    ref = lf.KaplanMeierFitter().fit(T1, E1)
    for st in km["steps"][1:]:
        assert st["s"] == approx(float(ref.survival_function_at_times(st["t"]).iloc[0]))
    assert km["median"] == approx(float(ref.median_survival_time_))


def test_logrank_matches_lifelines_and_known_value():
    lf = pytest.importorskip("lifelines.statistics")
    lr = survival.logrank([(np.array(T1, float), np.array(E1)), (np.array(T2, float), np.array(E2))])
    ref = lf.logrank_test(T1, T2, E1, E2)
    assert lr["chi2"] == approx(ref.test_statistic)
    assert lr["chi2"] == approx(16.79, rel=1e-3)  # textbook value for the Gehan data
    # three groups
    T3 = [3, 5, 7, 9, 11]; E3 = [1, 1, 0, 1, 1]
    lr3 = survival.logrank([(np.array(T1, float), np.array(E1)), (np.array(T2, float), np.array(E2)),
                            (np.array(T3, float), np.array(E3))])
    ref3 = lf.multivariate_logrank_test(T1 + T2 + T3, [0] * 21 + [1] * 21 + [2] * 5, E1 + E2 + E3)
    assert lr3["chi2"] == approx(ref3.test_statistic)


def test_survival_analyze_layout():
    # Prism-style layout: one time column, one outcome column per group (blank = not in group)
    times = T1 + T2
    g1 = E1 + [None] * 21
    g2 = [None] * 21 + E2
    r = survival.analyze(times, {"6-MP": g1, "Placebo": g2})
    assert [c["name"] for c in r["curves"]] == ["6-MP", "Placebo"]
    assert r["hazard_ratio"]["value"] > 1  # placebo dies faster
    with pytest.raises(ValueError):
        survival.analyze([1, 2], {"A": [2, 1]})


# ---- contingency ---------------------------------------------------------

def test_contingency_2x2():
    r = contingency.analyze([[10, 20], [30, 15]], ["Treated", "Control"], ["Died", "Alive"])
    assert r["fisher"]["p"] == approx(sps.fisher_exact([[10, 20], [30, 15]]).pvalue)
    assert r["odds_ratio"]["value"] == approx(10 * 15 / (20 * 30))
    assert r["relative_risk"]["value"] == approx((10 / 30) / (30 / 45))
    se = math.sqrt(1 / 10 + 1 / 20 + 1 / 30 + 1 / 15)
    assert r["odds_ratio"]["ci"][0] == approx(0.25 * math.exp(-1.959964 * se))
    assert r["chi_square"]["chi2"] == approx(sps.chi2_contingency([[10, 20], [30, 15]], correction=False).statistic)


def test_contingency_rxc_and_errors():
    r = contingency.analyze([[5, 10, 15], [10, 10, 10], [0, 0, 0]], ["A", "B", "C"], ["x", "y", "z"])
    assert r["rows"] == ["A", "B"] and r["chi_square"]["df"] == 2
    assert "fisher" not in r
    with pytest.raises(ValueError):
        contingency.analyze([[1.5, 2], [3, 4]], ["A", "B"], ["x", "y"])


def test_endpoints():
    c = TestClient(app)
    assert len(c.get("/api/models").json()["models"]) == 11
    r = c.post("/api/fit", json={"x": [1, 2, 3, 4], "ys": [[2, 4, 6, 8.1], [2.1, 4, None, 8]], "model": "linear"})
    assert r.status_code == 200 and r.json()["n"] == 7
    r = c.post("/api/survival", json={"times": [1, 2, 3, 4], "groups": [[1, 1, None, None], [None, None, 0, 1]],
                                      "names": ["A", "B"]})
    assert r.status_code == 200 and "logrank" in r.json()
    r = c.post("/api/contingency", json={"table": [[1, 2], [3, 4]], "rows": ["A", "B"], "cols": ["x", "y"]})
    assert r.status_code == 200


def test_gehan_wilcoxon_and_trend():
    lf = pytest.importorskip("lifelines.statistics")
    g = [(np.array(T1, float), np.array(E1)), (np.array(T2, float), np.array(E2))]
    w = survival.logrank(g, "wilcoxon")
    ref = lf.logrank_test(T1, T2, E1, E2, weightings="wilcoxon")
    assert np.isclose(w["chi2"], ref.test_statistic, rtol=1e-6) and np.isclose(w["p"], ref.p_value, rtol=1e-6)
    T3 = [3, 5, 7, 9, 11]; E3 = [1, 1, 0, 1, 1]
    g3 = g + [(np.array(T3, float), np.array(E3))]
    w3 = survival.logrank(g3, "wilcoxon")
    ref3 = lf.multivariate_logrank_test(T1 + T2 + T3, [0] * len(T1) + [1] * len(T2) + [2] * len(T3), E1 + E2 + E3, weightings="wilcoxon")
    assert np.isclose(w3["chi2"], ref3.test_statistic, rtol=1e-6)
    # with 2 groups the trend test is the log-rank test
    lr = survival.logrank(g)
    assert np.isclose(survival.trend_test(lr)["chi2"], lr["chi2"], rtol=1e-10)
    rt = survival.risk_table(g, ["a", "b"])
    assert rt["counts"]["a"][0] == len(T1) and rt["times"][0] == 0 and all(np.diff(rt["counts"]["b"]) <= 0)
