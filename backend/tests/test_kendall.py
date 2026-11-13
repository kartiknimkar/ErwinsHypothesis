"""Kendall tau and Spearman CI, validated against scipy and pingouin."""
import numpy as np
import pandas as pd
import pingouin as pg
from fastapi.testclient import TestClient
from scipy import stats as ss

from app import multivar, stats
from app.main import app

c = TestClient(app)
rng = np.random.default_rng(8)
X = rng.normal(size=25)
Y = X * 0.6 + rng.normal(size=25)
Y[3] = Y[7]  # a tie


def test_correlation_kendall_and_spearman_ci():
    r = stats.correlation(X, Y)
    kt = ss.kendalltau(X, Y)
    assert np.isclose(r["kendall_tau"], kt.statistic) and np.isclose(r["kendall_p"], kt.pvalue)
    ref = pg.corr(X, Y, method="spearman")
    assert np.isclose(r["spearman_r"], ref["r"].iloc[0])
    lo, hi = ref["CI95"].iloc[0]
    assert np.allclose(r["spearman_ci"], [lo, hi], atol=0.006)  # pingouin rounds the CI to 2 decimals
    # Fisher z interval, exact
    z, se = np.arctanh(r["spearman_r"]), 1 / np.sqrt(22)
    assert np.allclose(r["spearman_ci"], np.tanh([z - 1.959964 * se, z + 1.959964 * se]), atol=1e-6)


def test_kendall_matrix_and_spearman_matrix_ci():
    Z = rng.normal(size=25)
    res = multivar.correlation_matrix([X, Y, Z], ["X", "Y", "Z"], method="kendall")
    assert "Kendall" in res["test_name"]
    pair = next(p for p in res["pairs"] if {p["a"], p["b"]} == {"X", "Y"})
    assert np.isclose(pair["r"], ss.kendalltau(X, Y).statistic) and pair["ci"] is None
    df = pd.DataFrame({"X": X, "Y": Y, "Z": Z})
    ref = pg.pairwise_corr(df, method="kendall")
    row = ref[(ref.X == "X") & (ref.Y == "Y")].iloc[0]
    assert np.isclose(pair["r"], row["r"]) and np.isclose(pair["p"], row["p_unc"])
    sp = multivar.correlation_matrix([X, Y, Z], ["X", "Y", "Z"], method="spearman")
    assert next(p for p in sp["pairs"] if {p["a"], p["b"]} == {"X", "Y"})["ci"] is not None
    # through the API
    j = c.post("/api/multi", json={"columns": [X.tolist(), Y.tolist(), Z.tolist()], "names": ["X", "Y", "Z"], "method": "kendall"}).json()
    assert j["method"] == "kendall"
