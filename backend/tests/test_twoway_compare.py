import numpy as np
import pytest

from app import anova2


def _data(unbalanced=False):
    rng = np.random.default_rng(7)
    rows, cols = [], [[], [], []]
    for lab, eff in (("Male", 0), ("Female", 1.5)):
        n = 6
        for r in range(n):
            rows.append(lab)
            for j, ce in enumerate((0, 2, 3.5)):
                drop = unbalanced and lab == "Female" and j == 1 and r >= 3
                cols[j].append(None if drop else 10 + eff + ce + rng.normal(0, 1))
    return rows, cols


@pytest.mark.parametrize("unbalanced", [False, True])
def test_two_level_main_effect_equals_type3_F(unbalanced):
    rows, cols = _data(unbalanced)
    # rows have 2 levels: the main-effect comparison of row means must reproduce the Type III row-factor test
    r = anova2.two_way(rows, cols, ["A", "B", "C"], compare="row_means")
    F = next(t for t in r["table"] if t["source"] == "Row factor")
    assert len(r["comparisons"]) == 1
    assert np.isclose(r["comparisons"][0]["p"], F["p"], rtol=1e-8)
    # two columns: column main effect = column-factor test
    r2 = anova2.two_way(rows, cols[:2], ["A", "B"], compare="col_means")
    F2 = next(t for t in r2["table"] if t["source"] == "Column factor")
    assert np.isclose(r2["comparisons"][0]["p"], F2["p"], rtol=1e-8)


def test_marginal_means_and_families():
    rows, cols = _data()
    r = anova2.two_way(rows, cols, ["A", "B", "C"], compare="col_means")
    means = {(c["i"], c["j"]): c["mean"] for c in r["cells"]}
    c0 = r["comparisons"][0]
    assert np.isclose(c0["diff"], np.mean([means[(i, 0)] for i in range(2)]) - np.mean([means[(i, 1)] for i in range(2)]))
    assert len(r["comparisons"]) == 3 and "Tukey" in r["posthoc_name"]
    w = anova2.two_way(rows, cols, ["A", "B", "C"], compare="within_cols")
    assert len(w["comparisons"]) == 3 and all(c["kind"] == "within_cols" for c in w["comparisons"]) and "Šídák" in w["posthoc_name"]
    d = anova2.two_way(rows, cols, ["A", "B", "C"])
    assert len(d["comparisons"]) == 6 and d["compare"] == "within_rows"


def test_all_cells_tukey():
    from scipy import stats as ss
    rows, cols = _data()
    r = anova2.two_way(rows, cols, ["A", "B", "C"], compare="all_cells")
    assert len(r["comparisons"]) == 15 and "every cell" in r["posthoc_name"]
    c = r["comparisons"][0]
    ms, df = r["table"][-1]["MS"], r["table"][-1]["df"]
    q = abs(c["diff"]) / np.sqrt(ms * (1 / 6 + 1 / 6) / 2)
    assert np.isclose(c["p"], ss.studentized_range.sf(q, 6, df))
