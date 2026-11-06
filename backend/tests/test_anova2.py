"""Two-way ANOVA and repeated measures, cross-checked against statsmodels and pingouin."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import anova2, stats
from app.main import app

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731

# Unbalanced 2 (sex) x 3 (treatment) design
ROWS = ["M", "M", "M", "F", "F", "F", "F"]
COLS = [[5.1, 4.8, 5.5, 6.0, 6.3, 5.8, 6.1],
        [6.9, 7.4, None, 7.0, 7.7, 7.2, None],
        [8.2, 8.8, 8.5, 7.1, 7.6, 7.9, 7.4]]
NAMES = ["Vehicle", "Low", "High"]


def long_df():
    recs = [(ROWS[i], NAMES[j], v) for j, col in enumerate(COLS) for i, v in enumerate(col) if v is not None]
    return pd.DataFrame(recs, columns=["A", "B", "y"])


def test_two_way_type3_matches_statsmodels():
    smf = pytest.importorskip("statsmodels.formula.api")
    sm = pytest.importorskip("statsmodels.api")
    model = smf.ols("y ~ C(A, Sum) * C(B, Sum)", data=long_df()).fit()
    ref = sm.stats.anova_lm(model, typ=3)
    r = anova2.two_way(ROWS, COLS, NAMES)
    t = {row["source"]: row for row in r["table"]}
    assert t["Interaction"]["F"] == approx(ref.loc["C(A, Sum):C(B, Sum)", "F"])
    assert t["Row factor"]["F"] == approx(ref.loc["C(A, Sum)", "F"])
    assert t["Column factor"]["SS"] == approx(ref.loc["C(B, Sum)", "sum_sq"])
    assert t["Column factor"]["p"] == approx(ref.loc["C(B, Sum)", "PR(>F)"])
    assert t["Residual"]["df"] == int(ref.loc["Residual", "df"])
    assert not r["balanced"]


def test_two_way_comparisons_and_errors():
    r = anova2.two_way(ROWS, COLS, NAMES)
    assert len(r["comparisons"]) == 2 * 3  # 2 rows x 3 column pairs
    c = next(c for c in r["comparisons"] if c["row"] == "M" and c["a"] == "Vehicle" and c["b"] == "High")
    assert c["diff"] == approx(np.mean([5.1, 4.8, 5.5]) - np.mean([8.2, 8.8, 8.5]))
    # two columns -> Sidak
    r2 = anova2.two_way(ROWS, COLS[:2], NAMES[:2])
    assert r2["posthoc_name"].startswith("Šídák")
    with pytest.raises(ValueError):
        anova2.two_way(["M", "F"], [[1, None], [2, 3]], ["a", "b"])  # empty cell


SUBJ = [[10, 12, 15], [8, 11, 13], [11, 11, 16], [9, 13, 14], [12, 14, 18], [10, 10, 15]]


def test_rm_anova_matches_pingouin():
    pg = pytest.importorskip("pingouin")
    Y = np.array(SUBJ, float)
    df = pd.DataFrame([(s, f"T{j}", Y[s, j]) for s in range(len(Y)) for j in range(3)], columns=["s", "t", "y"])
    ref = pg.rm_anova(data=df, dv="y", within="t", subject="s", correction=True, detailed=True)
    r = anova2.repeated_measures([Y[:, j].tolist() for j in range(3)], ["T0", "T1", "T2"])
    assert r["F"] == approx(ref["F"].iloc[0])
    assert r["epsilon"] == approx(ref["eps"].iloc[0], rel=1e-3)
    pcol = "p_GG_corr" if "p_GG_corr" in ref else "p-GG-corr"
    assert r["p"] == approx(ref[pcol].iloc[0], rel=1e-3)


def test_friedman_and_incomplete_rows():
    cols = [[r[j] for r in SUBJ] + [None] for j in range(3)]
    cols[0][-1] = 99  # incomplete row is ignored
    r = anova2.repeated_measures(cols, ["A", "B", "C"], kind="friedman")
    assert r["n_subjects"] == 6
    assert r["chi2"] == approx(sps.friedmanchisquare(*[[s[j] for s in SUBJ] for j in range(3)]).statistic)


def test_wilcoxon_signed_rank():
    a, b = [1, 2, 3, 4, 5, 6, 7], [2, 4, 3.5, 7, 9, 8, 12]
    r = stats.t_test(a, b, kind="wilcoxon")
    assert r["p"] == approx(sps.wilcoxon(np.array(b) - np.array(a)).pvalue)


def test_endpoints():
    c = TestClient(app)
    r = c.post("/api/twoway", json={"rows": ROWS, "columns": COLS, "names": NAMES})
    assert r.status_code == 200 and r.json()["test_name"] == "Two-way ANOVA"
    cols = [[r[j] for r in SUBJ] for j in range(3)]
    r = c.post("/api/compare", json={"groups": cols, "names": ["A", "B", "C"], "kind": "rm"})
    assert r.json()["test_name"] == "Repeated-measures one-way ANOVA"
