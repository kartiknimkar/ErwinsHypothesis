import numpy as np
import pytest

from app import anova2


def _data(drop=0):
    rng = np.random.default_rng(3)
    A, B, C, Y = [], [], [], []
    for a in ("Male", "Female"):
        for b in ("Vehicle", "Drug"):
            for c in ("Day 1", "Day 7", "Day 14"):
                for r in range(4):
                    A.append(a); B.append(b); C.append(c)
                    Y.append(10 + (a == "Female") * 1 + (b == "Drug") * 2 * (1 + (c != "Day 1")) + rng.normal(0, 1))
    if drop:
        A, B, C, Y = A[drop:], B[drop:], C[drop:], Y[drop:]
    return A, B, C, Y


@pytest.mark.parametrize("drop", [0, 2])
def test_matches_statsmodels_type3(drop):
    smf = pytest.importorskip("statsmodels.formula.api")
    sm = pytest.importorskip("statsmodels.api")
    import pandas as pd
    fa, fb, fc, Y = _data(drop)  # (not named C: patsy's C() must stay visible to the formula)
    r = anova2.three_way([fa, fb, fc], Y, ["Sex", "Treatment", "Time"])
    df = pd.DataFrame({"a": fa, "b": fb, "c": fc, "y": Y})
    ref = sm.stats.anova_lm(smf.ols("y ~ C(a, Sum) * C(b, Sum) * C(c, Sum)", data=df).fit(), typ=3)
    keys = {"A": "C(a, Sum)", "B": "C(b, Sum)", "C": "C(c, Sum)", "A×B": "C(a, Sum):C(b, Sum)", "A×C": "C(a, Sum):C(c, Sum)",
            "B×C": "C(b, Sum):C(c, Sum)", "A×B×C": "C(a, Sum):C(b, Sum):C(c, Sum)"}
    for row in r["table"][:-1]:
        ref_row = ref.loc[keys[row["key"]]]
        assert np.isclose(row["SS"], ref_row["sum_sq"], rtol=1e-8) and np.isclose(row["p"], ref_row["PR(>F)"], rtol=1e-6)
    assert r["table"][-1]["df"] == ref.loc["Residual", "df"]
    assert r["balanced"] == (drop == 0)


def test_three_way_checks():
    A, B, C, Y = _data()
    with pytest.raises(ValueError):
        anova2.three_way([A, ["x"] * len(A), C], Y, ["a", "b", "c"])
