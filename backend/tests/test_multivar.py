import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import multivar
from app.main import app

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731
rng = np.random.default_rng(7)
A = rng.normal(0, 1, 30); B = A * 0.8 + rng.normal(0, 0.5, 30); C = rng.normal(0, 1, 30)


def test_correlation_matrix_matches_pandas_pairwise():
    cols = [list(A), list(B), list(C)]
    cols[2][3] = None  # pairwise deletion
    r = multivar.correlation_matrix(cols, ["A", "B", "C"])
    df = pd.DataFrame({"A": A, "B": B, "C": [None if i == 3 else v for i, v in enumerate(C)]}, dtype=float)
    ref = df.corr()
    assert r["r"][0][1] == approx(ref.loc["A", "B"]) and r["r"][0][2] == approx(ref.loc["A", "C"])
    assert r["n"][0][2] == 29 and r["pairs"][0]["a"] == "A" and r["pairs"][0]["b"] == "B"
    s = multivar.correlation_matrix([list(A), list(B)], ["A", "B"], method="spearman")
    assert s["r"][0][1] == approx(sps.spearmanr(A, B).statistic)


def test_roc_auc_equals_mann_whitney_and_known_values():
    ctrl, pat = [1, 2, 3, 4], [3, 5, 6, 7]
    r = multivar.roc(ctrl, pat)
    # P(patient > control) + 0.5 P(tie): patient 3 beats 1,2, ties 3 -> 2.5; others beat all 4 -> 14.5/16
    assert r["auc"] == approx(14.5 / 16)
    assert r["curve"][0] == {"fpr": 0.0, "tpr": 0.0, "cut": None} and r["curve"][-1]["tpr"] == 1.0
    # lower values in patients is detected
    r2 = multivar.roc(pat, ctrl)
    assert r2["auc"] == approx(14.5 / 16) and r2["direction"] == "lower"
    perfect = multivar.roc([1, 2, 3], [4, 5, 6])
    assert perfect["auc"] == 1.0 and perfect["best"]["sens"] == 100 and perfect["best"]["spec"] == 100


def test_bland_altman():
    a = [10, 12, 15, 20, 22, 30]; b = [11, 12.5, 15.2, 21, 23.5, 31]
    r = multivar.bland_altman(a, b)
    d = np.array(b) - np.array(a)
    assert r["bias"] == approx(d.mean()) and r["sd"] == approx(d.std(ddof=1))
    assert r["loa"][1] == approx(d.mean() + 1.959964 * d.std(ddof=1))
    assert r["p_bias"] == approx(sps.ttest_1samp(d, 0).pvalue)
    with pytest.raises(ValueError):
        multivar.bland_altman([1, 2], [1, 2])


def test_endpoint():
    c = TestClient(app)
    assert c.post("/api/multi", json={"columns": [list(A), list(B)], "names": ["A", "B"]}).status_code == 200
    assert c.post("/api/multi", json={"columns": [[1, 2, 3], [4, 5, 6]], "names": ["c", "p"], "analysis": "roc"}).json()["auc"] == 1.0
    assert c.post("/api/multi", json={"columns": [[1, 2]], "names": ["a"], "analysis": "bland_altman"}).status_code == 400


def test_bland_altman_pct_and_ratio():
    import numpy as np
    from app import multivar
    a = [5.1, 6.8, 4.4, 9.2, 7.5, 5.9, 8.1, 10.4]
    b = [5.3, 7.1, 4.3, 9.8, 7.6, 6.3, 8.2, 11.1]
    p = multivar.bland_altman(a, b, kind="pct")
    pct = 100 * (np.array(b) - np.array(a)) / ((np.array(a) + np.array(b)) / 2)
    assert np.isclose(p["bias"], pct.mean())
    r = multivar.bland_altman(a, b, kind="ratio")
    lr = np.log(np.array(b) / np.array(a))
    assert np.isclose(r["bias"], np.exp(lr.mean())) and np.isclose(r["loa"][1], np.exp(lr.mean() + 1.959964 * lr.std(ddof=1)), rtol=1e-5)
    assert np.isclose(r["points"]["diff"][0], b[0] / a[0])


def test_hosmer_lemeshow_and_classification():
    import numpy as np
    from app import multivar
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 300)
    p = 1 / (1 + np.exp(-(0.3 + 1.2 * x)))
    y = (rng.uniform(size=300) < p).astype(int)
    r = multivar.logistic(y.tolist(), [x.tolist()], "y", ["x"])
    hl = r["hosmer_lemeshow"]
    assert hl["df"] == 8 and sum(g["n"] for g in hl["groups"]) == 300 and hl["p"] > 0.01
    # hand check of the statistic
    pr = 1 / (1 + np.exp(-(r["coefs"][0]["estimate"] + r["coefs"][1]["estimate"] * x)))
    order = np.argsort(pr, kind="stable")
    chi = sum((y[i].sum() - pr[i].sum()) ** 2 / (pr[i].sum() * (1 - pr[i].sum() / len(i))) for i in np.array_split(order, 10))
    assert np.isclose(hl["chi2"], chi, rtol=1e-6)
    c = r["classification"]
    assert c["tp"] + c["fp"] + c["tn"] + c["fn"] == 300 and abs(c["accuracy"] - r["accuracy"]) < 1e-12
