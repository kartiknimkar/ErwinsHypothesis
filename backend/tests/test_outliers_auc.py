import math

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import stats
from app.main import app

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731


def test_grubbs_flags_obvious_outlier_only():
    data = [10.1, 9.8, 10.3, 10.0, 9.9, 10.2, 14.5]
    r = stats.grubbs(data)
    assert [o["value"] for o in r["outliers"]] == [14.5]
    x = np.array(data)
    G = abs(14.5 - x.mean()) / x.std(ddof=1)
    n = 7
    t = sps.t.ppf(1 - 0.05 / (2 * n), n - 2)
    assert r["outliers"][0]["G"] == approx(G)
    assert r["outliers"][0]["critical"] == approx((n - 1) / math.sqrt(n) * math.sqrt(t * t / (n - 2 + t * t)))
    assert stats.grubbs([1, 2, 3, 4, 5])["outliers"] == []
    assert stats.grubbs([1, 1, 1])["outliers"] == []


def test_auc_trapezoid_and_baseline_crossing():
    r = stats.area_under_curve([0, 1, 2, 3], [0, 2, 2, 0])
    assert r["total"] == approx(4.0) and r["peak_y"] == 2 and r["negative"] == 0
    # replicates are averaged per X; X need not be sorted
    r = stats.area_under_curve([2, 0, 1, 1], [0, 0, 1, 3])
    assert r["total"] == approx(2.0)
    # crossing the baseline: triangle +0.5 then -0.5
    r = stats.area_under_curve([0, 1, 2], [1, 0, -1])
    assert r["positive"] == approx(0.5) and r["negative"] == approx(-0.5) and r["total"] == approx(0)
    r = stats.area_under_curve([0, 1, 2], [3, 3, 3], baseline=1)
    assert r["total"] == approx(4.0)


def test_endpoints():
    c = TestClient(app)
    r = c.post("/api/compare", json={"groups": [[10.1, 9.8, 10.3, 10.0, 9.9, 10.2, 14.5], [12, 13, 12.5, 13.2]],
                                     "names": ["A", "B"], "outliers": True}).json()
    assert r["outliers"][0]["outliers"][0]["value"] == 14.5 and r["outliers"][1]["outliers"] == []
    r = c.post("/api/fit", json={"x": [0, 30, 60, 120], "ys": [[5, 12, 9, 6]], "model": "linear", "auc": True, "baseline": 5}).json()
    assert r["auc"]["total"] == approx((0 + 7) / 2 * 30 + (7 + 4) / 2 * 30 + (4 + 1) / 2 * 60)
