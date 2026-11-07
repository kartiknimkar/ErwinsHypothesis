import numpy as np
import pytest

from app import anova2


def _data():
    rng = np.random.default_rng(5)
    n, rows, cols = 6, ["Day 1", "Day 2", "Day 3"], ["Left", "Right"]
    subj = rng.normal(0, 2, n)
    Y = {(r, c): [10 + subj[k] + i * 1.2 + j * 0.8 + (i * j) * 0.9 + rng.normal(0, 1) for k in range(n)]
         for i, r in enumerate(rows) for j, c in enumerate(cols)}
    labels, colvals = [], [[] for _ in cols]
    for r in rows:
        for k in range(n):
            labels.append(r)
            for j, c in enumerate(cols):
                colvals[j].append(Y[(r, c)][k])
    return labels, colvals, cols, Y, n, rows


def test_matches_pingouin_two_within():
    pg = pytest.importorskip("pingouin")
    import pandas as pd
    labels, colvals, cols, Y, n, rows = _data()
    r = anova2.two_way_rm_both(labels, colvals, cols)
    df = pd.DataFrame([(k, rw, c, Y[(rw, c)][k]) for rw in rows for c in cols for k in range(n)], columns=["s", "t", "side", "y"])
    ref = pg.rm_anova(data=df, dv="y", within=["t", "side"], subject="s", correction=True)
    m = {"Row factor": "t", "Column factor": "side", "Interaction": "t * side"}
    for row in r["table"][:3]:
        rr = ref[ref["Source"] == m[row["source"]]].iloc[0]
        assert np.isclose(row["F"], rr["F"], rtol=1e-6)
        assert np.isclose(row["p_uncorrected"], rr["p_unc"], rtol=1e-6)
        if "eps" in rr and not np.isnan(rr["eps"]) and row["df"] > 1:
            assert np.isclose(row["epsilon"], rr["eps"], rtol=1e-4)


def test_incomplete_subject_dropped():
    labels, colvals, cols, *_ = _data()
    colvals[0][0] = None  # subject 1 missing at Day 1 / Left
    r = anova2.two_way_rm_both(labels, colvals, cols)
    assert r["n_subjects"] == 5 and len(r["comparisons"]) == 3
