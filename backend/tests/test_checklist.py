"""Assumptions checklist on 2+ group comparisons."""
import math

import numpy as np
from fastapi.testclient import TestClient
from scipy import stats as ss

from app import stats
from app.main import app

c = TestClient(app)


def _items(r):
    return {i["check"]: i for i in r["checklist"]}


def test_rank_test_minimum_p_matches_scipy():
    # 3 vs 3 Mann-Whitney: smallest possible exact P = 2 / C(6,3) = 0.1
    r = c.post("/api/compare", json={"groups": [[1, 2, 3], [4, 5, 6]], "names": ["A", "B"], "kind": "mannwhitney"}).json()
    it = _items(r)
    assert it["Sample size"]["status"] == "warn" and "0.1" in it["Sample size"]["text"]
    assert math.isclose(ss.mannwhitneyu([1, 2, 3], [4, 5, 6]).pvalue, 0.1)
    assert it["Normal distribution"]["status"] == "info"
    # 5 pairs Wilcoxon: smallest P = 2/32
    r = c.post("/api/compare", json={"groups": [[1, 2, 3, 4, 5], [2, 3.5, 5, 6.6, 8.1]], "names": ["A", "B"], "kind": "wilcoxon"}).json()
    assert "0.0625" in _items(r)["Sample size"]["text"]
    assert math.isclose(ss.wilcoxon([1, 2, 3, 4, 5], [2, 3.5, 5, 6.6, 8.1]).pvalue, 0.0625)


def test_flags_skew_unequal_sd_and_outliers():
    rng = np.random.default_rng(1)
    a, b = rng.lognormal(size=20), rng.lognormal(size=20) * 3
    b[0] = 200
    r = c.post("/api/compare", json={"groups": [a.tolist(), b.tolist()], "names": ["Ctrl", "Drug"], "kind": "unpaired"}).json()
    it = _items(r)
    assert it["Normal distribution"]["status"] == "warn" and "Drug" in it["Normal distribution"]["text"]
    assert it["Equal spread (SD)"]["status"] == "warn" and "Welch" in it["Equal spread (SD)"]["text"]
    assert it["Outliers"]["status"] == "warn" and "200" in it["Outliers"]["text"]
    # Welch doesn't need equal SDs
    r = c.post("/api/compare", json={"groups": [a.tolist(), b.tolist()], "names": ["Ctrl", "Drug"], "kind": "welch"}).json()
    assert _items(r)["Equal spread (SD)"]["status"] == "ok"


def test_clean_normal_data_all_ok():
    rng = np.random.default_rng(7)
    G = [rng.normal(10 + i, 1, 12).round(3).tolist() for i in range(3)]
    r = c.post("/api/compare", json={"groups": G, "names": ["A", "B", "C"], "kind": "ordinary"}).json()
    it = _items(r)
    assert all(it[k]["status"] == "ok" for k in ("Sample size", "Normal distribution", "Equal spread (SD)", "Outliers"))
    assert it["Independent values"]["status"] == "info"


def test_repeated_measures_residual_normality_and_sphericity():
    rng = np.random.default_rng(3)
    subj = rng.normal(0, 3, 10)
    cols = [(subj + m + rng.normal(0, 1, 10)).tolist() for m in (5, 6, 8)]
    r = c.post("/api/compare", json={"groups": cols, "names": ["T0", "T1", "T2"], "kind": "rm"}).json()
    it = _items(r)
    assert "Sphericity" in it and "Geisser-Greenhouse" in it["Sphericity"]["text"]
    Y = np.array(cols).T
    resid = (Y - Y.mean(1, keepdims=True) - Y.mean(0) + Y.mean()).ravel()
    assert (ss.shapiro(resid).pvalue >= 0.05) == (it["Normal distribution"]["status"] == "ok")
    assert "subjects" in it["Sample size"]["text"]


def test_small_paired_uses_differences():
    r = stats.t_test([1, 2, 3, 4], [1.5, 2.7, 3.1, 4.9], kind="paired")
    it = _items({"checklist": stats.assumption_checklist(r, [[1, 2, 3, 4], [1.5, 2.7, 3.1, 4.9]], "paired")})
    assert it["Sample size"]["status"] == "warn" and "pairs" in it["Sample size"]["text"]
    assert "Equal spread (SD)" not in it
    assert "differences" in it["Normal distribution"]["text"].lower()


def test_fit_checklist_flags_wrong_model_and_uneven_scatter():
    rng = np.random.default_rng(2)
    x = np.repeat(np.linspace(1, 20, 10), 3)
    y = 3 * x + 2 + rng.normal(0, 1, len(x)) * x * 0.5
    r = c.post("/api/fit", json={"x": x.tolist(), "ys": [y.tolist()], "model": "linear"}).json()
    it = _items(r)
    fitted = np.array(r["residuals"]["fitted"]); res = np.array(r["residuals"]["y"])
    assert np.allclose(fitted + res, y)
    rho, p = ss.spearmanr(fitted, np.abs(res))
    assert p < 0.05 and it["Equal scatter"]["status"] == "warn" and f"{rho:.2f}" in it["Equal scatter"]["text"]
    # a line through exponential data: runs test fails
    x2 = np.linspace(0, 5, 20); y2 = np.exp(x2) + rng.normal(0, .5, 20)
    it2 = _items(c.post("/api/fit", json={"x": x2.tolist(), "ys": [y2.tolist()], "model": "linear"}).json())
    assert it2["Points scatter randomly around the curve"]["status"] == "warn"


def test_fit_checklist_good_dose_response_and_weighting():
    rng = np.random.default_rng(5)
    x = np.repeat(np.logspace(-9, -5, 9), 3)
    y = 5 + 95 / (1 + 10 ** ((-7 - np.log10(x)) * 1.0)) + rng.normal(0, 3, len(x))
    r = c.post("/api/fit", json={"x": x.tolist(), "ys": [y.tolist()], "model": "dr_stim"}).json()
    it = _items(r)
    assert it["Number of points"]["status"] == "ok" and "4 fitted parameters" in it["Number of points"]["text"]
    assert it["Points scatter randomly around the curve"]["status"] == "ok"
    assert "Well-determined parameters" not in it
    r = c.post("/api/fit", json={"x": x.tolist(), "ys": [y.tolist()], "model": "dr_stim", "weighting": "1/Y2"}).json()
    assert "weighting" in _items(r)["Equal scatter"]["text"]
    # ROUT on: reports what it removed instead of re-testing
    r = c.post("/api/fit", json={"x": x.tolist(), "ys": [y.tolist()], "model": "dr_stim", "rout_q": 0.01}).json()
    assert "ROUT" in _items(r)["Outliers"]["text"]


def test_fit_checklist_few_points_and_poor_parameter():
    # 5 points for a 4-parameter curve that never reaches its top
    x = [1e-9, 3e-9, 1e-8, 3e-8, 1e-7]
    y = [2, 4, 9, 15, 27]
    r = c.post("/api/fit", json={"x": x, "ys": [y], "model": "dr_stim"}).json()
    it = _items(r)
    assert it["Number of points"]["status"] == "warn"
    assert it["Well-determined parameters"]["status"] == "warn" and "Top" in it["Well-determined parameters"]["text"]
    assert r["derived"][0]["ci"][1] is None  # huge CI limit no longer crashes the fit (was OverflowError)


def test_two_way_checklist_matches_scipy():
    rng = np.random.default_rng(11)
    rows = ["M"] * 5 + ["F"] * 5
    cols = [rng.normal(10, 1, 10).tolist(), rng.normal(12, 1, 10).tolist(), (rng.normal(12, 1, 10) * np.r_[np.ones(5), np.full(5, 6)]).tolist()]
    r = c.post("/api/twoway", json={"rows": rows, "columns": cols, "names": ["A", "B", "C"]}).json()
    it = _items(r)
    groups = [np.array(cols[j][s:s + 5]) for s in (0, 5) for j in range(3)]
    bf = ss.levene(*groups, center="median")
    assert (bf.pvalue < 0.05) == (it["Equal spread (SD)"]["status"] == "warn")
    assert f"{bf.pvalue:.3g}" in it["Equal spread (SD)"]["text"]
    resid = np.concatenate([g - g.mean() for g in groups])
    assert f"{ss.shapiro(resid).pvalue:.3g}" in it["Normal distribution"]["text"]
    assert it["Sample size"]["status"] == "ok"
    # a combination with a single value
    cols2 = [c_[:] for c_ in cols]
    cols2[1] = cols2[1][:6] + [None] * 4
    it2 = _items(c.post("/api/twoway", json={"rows": rows, "columns": cols2, "names": ["A", "B", "C"]}).json())
    assert it2["Sample size"]["status"] == "warn" and "only 1 value" in it2["Sample size"]["text"]
    assert "Every combination has data" not in it2


def test_two_way_rm_and_three_way_checklists():
    rng = np.random.default_rng(4)
    rows = ["T0"] * 6 + ["T1"] * 6
    cols = [rng.normal(10, 1, 12).tolist(), rng.normal(11, 1, 12).tolist()]
    it = _items(c.post("/api/twoway", json={"rows": rows, "columns": cols, "names": ["Ctl", "Drug"], "rm": True}).json())
    assert "Equal spread (SD)" not in it and "Independent values" in it
    A = ["a1", "a2"] * 12; B = (["b1"] * 2 + ["b2"] * 2) * 6; C_ = (["c1"] * 4 + ["c2"] * 4) * 3
    y = rng.normal(5, 1, 24).tolist()
    r = c.post("/api/threeway", json={"factors": [A, B, C_], "values": y, "names": ["A", "B", "C"]}).json()
    it = _items(r)
    assert it["Sample size"]["text"].startswith("3 values")
    assert "Every combination has data" not in it


def test_contingency_checklist_expected_counts_match_scipy():
    t = [[2, 8, 1], [3, 9, 0], [10, 12, 2]]
    r = c.post("/api/contingency", json={"table": t, "rows": ["a", "b", "c"], "cols": ["x", "y", "z"]}).json()
    it = _items(r)
    e = ss.chi2_contingency(np.array(t)).expected_freq
    assert it["Expected counts"]["status"] == "warn"
    assert f"{int((e < 5).sum())} of 9" in it["Expected counts"]["text"] and f"{e.min():.3g}" in it["Expected counts"]["text"]
    # 2x2 uses Fisher: fine at any size
    r = c.post("/api/contingency", json={"table": [[1, 4], [5, 1]], "rows": ["a", "b"], "cols": ["x", "y"]}).json()
    assert _items(r)["Expected counts"]["status"] == "ok"
    # rows adding to 100 look like percentages
    r = c.post("/api/contingency", json={"table": [[30, 70], [45, 55]], "rows": ["a", "b"], "cols": ["x", "y"]}).json()
    assert _items(r)["Counts, not percentages"]["status"] == "warn"
    # k x 2 with order: trend hint
    r = c.post("/api/contingency", json={"table": [[10, 40], [20, 30], [30, 20]], "rows": ["lo", "mid", "hi"], "cols": ["yes", "no"]}).json()
    it = _items(r)
    assert it["Expected counts"]["status"] == "ok" and "Order of rows" in it


def test_mcnemar_and_gof_checklists():
    r = c.post("/api/contingency", json={"table": [[20, 3], [2, 15]], "rows": ["+", "−"], "cols": ["+", "−"], "analysis": "mcnemar"}).json()
    it = _items(r)
    assert it["Discordant pairs"]["status"] == "warn" and "5 pairs" in it["Discordant pairs"]["text"]
    r = c.post("/api/contingency", json={"table": [[3, 1], [10, 8], [7, 1]], "rows": ["AA", "Aa", "aa"], "cols": ["obs", "exp"], "analysis": "gof"}).json()
    it = _items(r)
    assert it["Expected counts"]["status"] == "warn" and "2 of 3 categories expect fewer than 5" in it["Expected counts"]["text"]
