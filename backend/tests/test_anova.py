"""ANOVA family, normality and correlation checked against hand calculations and
independent packages (statsmodels, pingouin, scikit-posthocs; skipped if absent)."""
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import stats
from app.main import app

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731

G = [[4, 5, 6], [6, 7, 8], [8, 9, 10]]
# Unequal sizes and spreads, for Welch / Games-Howell / Dunn
U = [[2.1, 3.4, 1.9, 2.8, 3.0], [4.5, 6.1, 3.2, 7.4, 5.0, 4.4], [9.0, 7.2, 12.5, 8.1]]


def test_ordinary_anova_by_hand():
    r = stats.one_way_anova(G, ["A", "B", "C"])
    # SSB = 24 (df 2), SSW = 6 (df 6) -> MSB 12, MSW 1, F 12
    assert r["F"] == approx(12)
    assert (r["df_between"], r["df_within"]) == (2, 6)
    assert r["p"] == approx(sps.f.sf(12, 2, 6))
    assert r["r_squared"] == approx(0.8)
    ac = next(c for c in r["comparisons"] if (c["a"], c["b"]) == ("A", "C"))
    assert ac["diff"] == approx(-4)
    q = 4 / math.sqrt(1 / 3)
    assert ac["p"] == approx(sps.studentized_range.sf(q, 3, 6), rel=1e-3)


def test_tukey_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.stats.multicomp")
    vals = np.concatenate([np.array(g, float) for g in U])
    labels = np.repeat(["A", "B", "C"], [len(g) for g in U])
    ref = sm.pairwise_tukeyhsd(vals, labels)
    r = stats.one_way_anova(U, ["A", "B", "C"])
    for c, p_ref, d_ref in zip(r["comparisons"], ref.pvalues, ref.meandiffs):
        assert c["p"] == approx(p_ref, rel=1e-2)
        assert c["diff"] == approx(-d_ref)  # statsmodels reports second − first


def test_welch_anova_and_games_howell_match_pingouin():
    pg = pytest.importorskip("pingouin")
    import pandas as pd
    df = pd.DataFrame({"y": np.concatenate(U), "g": np.repeat(["A", "B", "C"], [len(g) for g in U])})
    ref = pg.welch_anova(data=df, dv="y", between="g")
    r = stats.one_way_anova(U, ["A", "B", "C"], kind="welch")
    assert r["F"] == approx(ref["F"].iloc[0])
    assert r["df_within"] == approx(ref["ddof2"].iloc[0])
    assert r["p"] == approx(ref["p_unc"].iloc[0] if "p_unc" in ref else ref["p-unc"].iloc[0], rel=1e-3)
    gh = pg.pairwise_gameshowell(data=df, dv="y", between="g")
    for c, (_, row) in zip(r["comparisons"], gh.iterrows()):
        assert c["diff"] == approx(row["diff"])
        assert c["p"] == approx(row["pval"], rel=1e-2)


def test_kruskal_dunn_matches_scikit_posthocs():
    sp = pytest.importorskip("scikit_posthocs")
    r = stats.one_way_anova(U, ["A", "B", "C"], kind="kruskal")
    assert r["H"] == approx(sps.kruskal(*U).statistic)
    ref = sp.posthoc_dunn([np.array(g) for g in U], p_adjust="bonferroni").values
    for c in r["comparisons"]:
        assert c["p"] == approx(ref[c["i"], c["j"]], rel=1e-6)


def test_anova_errors_and_blank_columns():
    with pytest.raises(ValueError):
        stats.one_way_anova([[1, 2], [3, 4]])
    with pytest.raises(ValueError):
        stats.one_way_anova([[1, 2], [3, 4], [5]])
    r = stats.one_way_anova([[1, 2, 3], [], [4, 5, 6], [7, 8, 9]], ["A", "B", "C", "D"])
    assert [g["name"] for g in r["groups"]] == ["A", "C", "D"]


def test_normality_and_correlation():
    n = stats.normality([2.1, 3.4, 1.9, 2.8, 3.0])
    assert n["p"] == approx(sps.shapiro([2.1, 3.4, 1.9, 2.8, 3.0]).pvalue)
    assert stats.normality([1, 2]) is None
    c = stats.correlation([1, 2, 3, 4, 5], [2, 4, 5, 4, 5])
    # r = 6 / sqrt(10 * 6)
    assert c["pearson_r"] == approx(6 / math.sqrt(60))
    assert c["spearman_r"] == approx(sps.spearmanr([1, 2, 3, 4, 5], [2, 4, 5, 4, 5]).statistic)


def test_compare_endpoint_switches_by_group_count():
    c = TestClient(app)
    two = c.post("/api/compare", json={"groups": [[1, 2, 3], [4, 5, 6], []], "names": ["A", "B", "C"],
                                       "kind": "ordinary"}).json()
    assert two["test_name"] == "Unpaired t test" and two["n_groups"] == 2
    three = c.post("/api/compare", json={"groups": G, "names": ["A", "B", "C"], "kind": "welch"}).json()
    assert three["test_name"] == "Welch's ANOVA"
    bad = c.post("/api/compare", json={"groups": [[1, 2], []], "names": ["A", "B"]})
    assert bad.status_code == 400
