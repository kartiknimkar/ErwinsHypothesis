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
