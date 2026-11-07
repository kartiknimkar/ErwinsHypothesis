import math

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import stats
from app.main import app

approx = lambda v, rel=1e-9: pytest.approx(v, rel=rel)  # noqa: E731


def test_t_tests_match_scipy_from_stats():
    g = [{"name": "A", "mean": 4.6, "sd": 0.6, "n": 8}, {"name": "B", "mean": 6.7, "sd": 1.1, "n": 6}]
    for kind, eq in (("unpaired", True), ("welch", False)):
        r = stats.compare_summary(g, kind=kind)
        ref = sps.ttest_ind_from_stats(6.7, 1.1, 6, 4.6, 0.6, 8, equal_var=eq)
        assert r["statistic"] == approx(abs(ref.statistic)) and r["p"] == approx(ref.pvalue)


def test_sem_input_and_anova_equal_raw_data():
    rng = np.random.default_rng(4)
    raw = [rng.normal(10, 1, 7), rng.normal(12, 2, 9), rng.normal(11, 1.5, 6)]
    summ = [{"name": n, "mean": x.mean(), "sd": x.std(ddof=1), "n": len(x)} for n, x in zip("ABC", raw)]
    for kind in ("ordinary", "welch"):
        a = stats.compare_summary(summ, kind=kind)
        b = stats.one_way_anova(raw, list("ABC"), kind=kind)
        assert a["F"] == approx(b["F"]) and a["p"] == approx(b["p"])
        assert [c["p"] for c in a["comparisons"]] == [approx(c["p"], 1e-7) for c in b["comparisons"]]
    sem = [{**g, "sd": g["sd"] / math.sqrt(g["n"])} for g in summ]
    assert stats.compare_summary(sem, kind="ordinary", err="sem")["F"] == approx(stats.one_way_anova(raw, list("ABC"))["F"])


def test_errors_and_endpoint():
    with pytest.raises(ValueError):
        stats.compare_summary([{"name": "A", "mean": 1, "sd": 1, "n": 1}, {"name": "B", "mean": 2, "sd": 1, "n": 5}])
    with pytest.raises(ValueError):
        stats.compare_summary([{"name": "A", "mean": 1, "sd": 1, "n": 5}])
    c = TestClient(app)
    r = c.post("/api/summary", json={"groups": [{"name": "A", "mean": 1, "sd": 0.5, "n": 5}, {"name": "B", "mean": 2, "sd": 0.5, "n": 5}]}).json()
    assert r["summary_data"] and r["groups"][0]["median"] is None and "normality" not in r
