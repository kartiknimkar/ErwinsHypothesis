import numpy as np
import pytest
from scipy import stats as ss

from app import stats

G = [[10.2, 11.5, 9.8, 12.1, 10.9, 11.3], [13.4, 14.8, 12.9, 15.2, 14.1, 13.7], [18.2, 17.1, 19.5, 16.8, 18.9, 17.6], [11.0, 12.2, 10.4, 11.8, 12.6]]
N = ["Vehicle", "Low", "High", "Other"]


def test_dunnett_vs_control_matches_scipy():
    r = stats.one_way_anova(G, N, posthoc="dunnett")
    ref = ss.dunnett(*map(np.array, G[1:]), control=np.array(G[0]))
    assert [c["b"] for c in r["comparisons"]] == ["Low", "High", "Other"] and all(c["a"] == "Vehicle" for c in r["comparisons"])
    assert np.allclose([c["p"] for c in r["comparisons"]], ref.pvalue, rtol=1e-2, atol=1e-4)  # numerical integration (P < 0.0001 shown as such)
    ci = ref.confidence_interval(0.95)
    assert np.allclose([c["ci_high"] for c in r["comparisons"]], -ci.low, rtol=1e-2)
    assert np.allclose([c["diff"] for c in r["comparisons"]], [np.mean(G[0]) - np.mean(g) for g in G[1:]])


@pytest.mark.parametrize("method,sm_name", [("bonferroni", "bonferroni"), ("sidak", "sidak"), ("holm", "holm-sidak")])
def test_corrections_match_statsmodels(method, sm_name):
    mt = pytest.importorskip("statsmodels.stats.multitest")
    for compare_to in ("all", "control"):
        r = stats.one_way_anova(G, N, posthoc=method, compare_to=compare_to)
        praw = [c["p_raw"] for c in r["comparisons"]]
        ref = mt.multipletests(praw, method=sm_name)[1]
        assert np.allclose([c["p"] for c in r["comparisons"]], ref)
        assert len(r["comparisons"]) == (6 if compare_to == "all" else 3)


def test_pooled_t_and_lsd():
    r = stats.one_way_anova(G, N, posthoc="lsd")
    x = [np.array(g) for g in G]
    msw = sum(((g - g.mean()) ** 2).sum() for g in x) / (sum(map(len, x)) - 4)
    c = r["comparisons"][0]
    t = (x[0].mean() - x[1].mean()) / np.sqrt(msw * (1 / 6 + 1 / 6))
    assert np.isclose(c["t"], t) and np.isclose(c["p"], 2 * ss.t.sf(abs(t), 19))
    assert c["ci_low"] < c["diff"] < c["ci_high"]
    assert stats.one_way_anova(G, N, posthoc="holm")["comparisons"][0]["ci_low"] is None


def test_default_still_tukey_and_dunn_control():
    r = stats.one_way_anova(G, N)
    assert r["posthoc_name"].startswith("Tukey") and len(r["comparisons"]) == 6
    k = stats.one_way_anova(G, N, kind="kruskal", compare_to="control")
    assert len(k["comparisons"]) == 3 and "vs control" in k["posthoc_name"]


def test_linear_trend_equals_regression_on_column_number():
    r = stats.one_way_anova(G, N)
    y = np.concatenate([np.array(g, float) for g in G])
    x = np.concatenate([np.full(len(g), i + 1.0) for i, g in enumerate(G)])
    lr = ss.linregress(x, y)
    ss_tot = np.sum((y - y.mean()) ** 2)
    msw = sum(np.sum((np.array(g) - np.mean(g)) ** 2) for g in G) / (len(y) - len(G))
    assert np.isclose(r["trend"]["F"], lr.rvalue ** 2 * ss_tot / msw)
    assert np.isclose(r["trend"]["slope"], lr.slope) and r["trend"]["df"] == [1, len(y) - len(G)]
