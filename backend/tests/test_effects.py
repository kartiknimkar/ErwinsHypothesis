import numpy as np
import pytest

from app import stats

A = [4.2, 5.1, 3.8, 4.9, 5.5, 4.4, 4.0, 5.2]
B = [6.1, 7.3, 6.8, 5.9, 7.9, 6.5, 7.0, 6.2, 6.6]


def test_cohen_hedges_match_pingouin():
    pg = pytest.importorskip("pingouin")
    r = stats.t_test(A, B, kind="unpaired")["effect"]
    assert np.isclose(r["cohens_d"], pg.compute_effsize(B, A, eftype="cohen"), rtol=1e-8)
    assert np.isclose(r["hedges_g"], pg.compute_effsize(B, A, eftype="hedges"), rtol=1e-3)
    p = stats.t_test(A, B[:8], kind="paired")["effect"]
    diff = np.array(B[:8]) - np.array(A)
    assert np.isclose(p["cohens_dz"], diff.mean() / diff.std(ddof=1))


def test_anova_eta_omega():
    pg = pytest.importorskip("pingouin")
    import pandas as pd
    G = [A, B, [8.1, 7.7, 8.9, 9.2, 8.4]]
    r = stats.one_way_anova(G, ["a", "b", "c"])
    df = pd.DataFrame({"y": sum(G, []), "g": sum([[n] * len(x) for n, x in zip("abc", G)], [])})
    ref = pg.anova(data=df, dv="y", between="g", effsize="np2")
    assert np.isclose(r["effect"]["eta_squared"], ref["np2"].iloc[0], rtol=1e-8)
    assert 0 < r["effect"]["omega_squared"] < r["effect"]["eta_squared"]
