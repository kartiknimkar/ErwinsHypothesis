import numpy as np
import pandas as pd
import pytest

from app import anova2

approx = lambda v, rel=1e-6: pytest.approx(v, rel=rel)  # noqa: E731


def make(nA=5, nB=6, seed=1):
    rng = np.random.default_rng(seed)
    times = ["D0", "D7", "D14", "D21"]
    rows, colA, colB, recs = [], [], [], []
    subjA = [rng.normal(10, 1) + np.array([0, 1, 2, 3]) + rng.normal(0, .6, 4) for _ in range(nA)]
    subjB = [rng.normal(10, 1) + np.array([0, 2, 4, 7]) + rng.normal(0, .6, 4) for _ in range(nB)]
    for ti, t in enumerate(times):
        for k in range(max(nA, nB)):
            rows.append(t)
            colA.append(subjA[k][ti] if k < nA else None)
            colB.append(subjB[k][ti] if k < nB else None)
    for g, subs in (("A", subjA), ("B", subjB)):
        for k, v in enumerate(subs):
            for ti, t in enumerate(times):
                recs.append((f"{g}{k}", g, t, v[ti]))
    return rows, colA, colB, pd.DataFrame(recs, columns=["s", "g", "t", "y"])


@pytest.mark.parametrize("nA,nB", [(5, 5)])
def test_matches_pingouin_mixed_anova(nA, nB):
    """Balanced groups: identical to pingouin's mixed ANOVA (and to every textbook method)."""
    pg = pytest.importorskip("pingouin")
    rows, colA, colB, df = make(nA, nB)
    r = anova2.two_way_rm(rows, [colA, colB], ["A", "B"])
    ref = pg.mixed_anova(data=df, dv="y", within="t", between="g", subject="s", correction=True)
    t = {x["source"]: x for x in r["table"]}
    assert t["Column factor"]["F"] == approx(ref.loc[ref.Source == "g", "F"].iloc[0])
    assert t["Row factor"]["F"] == approx(ref.loc[ref.Source == "t", "F"].iloc[0])
    assert t["Interaction"]["F"] == approx(ref.loc[ref.Source == "Interaction", "F"].iloc[0])
    eps_col = "eps" if "eps" in ref else "epsilon"
    assert r["epsilon"] == approx(ref.loc[ref.Source == "t", eps_col].iloc[0], 1e-4)
    assert r["n_subjects"] == nA + nB


def test_incomplete_subjects_dropped_and_errors():
    rows, colA, colB, _ = make(5, 5)
    colA = list(colA); colA[0] = None  # subject 0 of A missing at D0
    r = anova2.two_way_rm(rows, [colA, colB], ["A", "B"])
    assert r["subjects_per_group"] == [4, 5]
    with pytest.raises(ValueError):
        anova2.two_way_rm(["T1", "T2"], [[1, 2], [None, None]], ["A", "B"])


def test_unbalanced_type3_matches_statsmodels():
    """Unequal group sizes: within-subject effects use Type III SS (as SPSS does by default),
    checked against statsmodels with subjects as fixed blocks; group effect = ANOVA on subject means."""
    smf = pytest.importorskip("statsmodels.formula.api")
    sm = pytest.importorskip("statsmodels.api")
    rows, colA, colB, df = make(5, 7)
    r = anova2.two_way_rm(rows, [colA, colB], ["A", "B"])
    t = {x["source"]: x for x in r["table"]}
    ref = sm.stats.anova_lm(smf.ols("y ~ C(s) + C(t, Sum) + C(t, Sum):C(g, Sum)", data=df).fit(), typ=3)
    assert t["Row factor"]["F"] == approx(ref.loc["C(t, Sum)", "F"])
    # (statsmodels' interaction term is rank-deficient here, so the interaction is checked against pingouin,
    #  whose interaction test does not depend on how unequal groups are weighted)
    pg = pytest.importorskip("pingouin")
    pref = pg.mixed_anova(data=df, dv="y", within="t", between="g", subject="s")
    assert t["Interaction"]["F"] == approx(pref.loc[pref.Source == "Interaction", "F"].iloc[0])
    means = df.groupby(["s", "g"]).y.mean().reset_index()
    from scipy import stats as sps
    assert t["Column factor"]["F"] == approx(sps.f_oneway(*[means[means.g == g].y for g in "AB"]).statistic)
