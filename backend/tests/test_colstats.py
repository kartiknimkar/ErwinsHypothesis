import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import stats
from app.main import app

approx = lambda v, rel=1e-6: pytest.approx(v, rel=rel)  # noqa: E731
X = [12.1, 9.8, 11.4, 10.2, 13.7, 10.9, 11.8, 9.5, 12.6, 10.4]


def test_column_stats():
    d = stats.column_stats(X, "A", hypothetical=10)
    x = np.array(X)
    assert d["q1"] == approx(np.percentile(x, 25, method="weibull")) and d["iqr"] == approx(d["q3"] - d["q1"])
    assert d["cv"] == approx(100 * x.std(ddof=1) / x.mean())
    assert d["geo_mean"] == approx(sps.gmean(x))
    assert d["skewness"] == approx(sps.skew(x, bias=False)) and d["kurtosis"] == approx(sps.kurtosis(x, bias=False))
    assert d["dagostino"]["p"] == approx(sps.normaltest(x).pvalue)
    assert d["one_sample_t"]["p"] == approx(sps.ttest_1samp(x, 10).pvalue)
    assert d["wilcoxon"]["p"] == approx(sps.wilcoxon(x - 10).pvalue)
    # Prism-style quartiles: (n+1)p rank. For 1..10, Q1 = 2.75 and Q3 = 8.25
    q = stats.column_stats(list(range(1, 11)))
    assert (q["q1"], q["q3"]) == (approx(2.75), approx(8.25))
    assert "geo_mean" not in stats.column_stats([-1, 2, 3])


def test_endpoint():
    c = TestClient(app)
    r = c.post("/api/colstats", json={"groups": [X, [], [1, 2]], "names": ["A", "B", "C"], "hypothetical": None}).json()
    assert r["n_groups"] == 2 and r["groups"][1]["name"] == "C" and "one_sample_t" not in r["groups"][0]


def test_median_ci_order_statistics():
    import numpy as np
    from scipy import stats as ss
    from app import stats
    x = [3.1, 2.2, 5.0, 4.4, 3.9, 2.8, 4.1, 3.3, 3.6, 4.8, 2.5, 3.0]
    d = stats.column_stats(x)
    xs = sorted(x)
    # n = 12: P(Bin(12, .5) <= 2) = 0.0193 <= 0.025, P(<= 3) = 0.073 > 0.025 -> j = 3: x(3) .. x(10)
    assert d["median_ci"] == [xs[2], xs[9]]
    assert np.isclose(d["median_ci_conf"], 1 - 2 * ss.binom.cdf(2, 12, 0.5))
    assert "median_ci" not in stats.column_stats([1, 2, 3, 4])  # too few values for a 95% interval
