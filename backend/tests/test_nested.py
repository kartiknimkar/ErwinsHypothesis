import numpy as np
import pytest
from scipy import stats

from app import nested


def _make(seed, sizes, reps, effect=(0, 2, 3)):
    rng = np.random.default_rng(seed)
    g_of, vals = [], []
    for g, ns in enumerate(sizes):
        for s in range(ns):
            u = rng.normal(0, 1.5)
            n = reps if isinstance(reps, int) else reps[g][s]
            g_of.append(g); vals.append((10 + effect[g] + u + rng.normal(0, 1, n)).tolist())
    return g_of, vals


def test_balanced_equals_anova_on_subject_means():
    g_of, vals = _make(1, [5, 5, 5], 4)
    r = nested.nested(g_of, vals, ["A", "B", "C"])
    means = [[np.mean(v) for g, v in zip(g_of, vals) if g == k] for k in range(3)]
    ref = stats.f_oneway(*means)
    assert np.isclose(r["F"], ref.statistic, rtol=1e-6) and np.isclose(r["p"], ref.pvalue, rtol=1e-5)
    assert r["df_n"] == 2 and r["df_d"] == 12
    t = nested.nested(g_of[:10], vals[:10], ["A", "B"])
    tref = stats.ttest_ind(means[0], means[1])
    assert np.isclose(abs(t["t"]), abs(tref.statistic), rtol=1e-6) and np.isclose(t["comparisons"][0]["p"], tref.pvalue, rtol=1e-5)


def test_unbalanced_matches_statsmodels_reml():
    sm = pytest.importorskip("statsmodels.formula.api")
    import pandas as pd
    reps = [[2, 5, 3, 4], [6, 2, 3, 3, 4], [3, 3, 5]]
    g_of, vals = _make(4, [4, 5, 3], reps)
    rows = [(g, s, v) for s, (g, vv) in enumerate(zip(g_of, vals)) for v in vv]
    df = pd.DataFrame(rows, columns=["g", "s", "y"])
    m = sm.mixedlm("y ~ 0 + C(g)", df, groups=df["s"]).fit(reml=True)
    r = nested.nested(g_of, vals, ["A", "B", "C"])
    assert np.allclose([gr["mean"] for gr in r["groups"]], m.fe_params.values, rtol=1e-5)
    # SEs: we use the standard GLS covariance (X'V^-1 X)^-1 at the REML variances (as SAS/lme4 do); statsmodels'
    # bse_fe comes from its numerical Hessian, so allow a small difference
    assert np.allclose([gr["se"] for gr in r["groups"]], m.bse_fe.values, rtol=1e-2)
    assert np.isclose(r["var_residual"], m.scale, rtol=1e-4)
    assert np.isclose(r["var_subject"], float(m.cov_re.iloc[0, 0]), rtol=1e-3)


def test_subjects_test_and_checks():
    g_of, vals = _make(2, [4, 4], 3, effect=(0, 0))
    r = nested.nested(g_of, vals, ["A", "B"])
    assert r["subjects_df"] == [6, 16] and 0 <= r["subjects_p"] <= 1 and 0 <= r["icc"] <= 1
    with pytest.raises(ValueError):
        nested.nested([0, 0], [[1, 2], [3, 4]], ["A", "B"])
