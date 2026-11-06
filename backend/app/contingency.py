"""Contingency tables: chi-square, Fisher's exact test, odds ratio, relative risk."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def analyze(table, row_names, col_names, alpha: float = 0.05) -> dict:
    t = np.array([[float(v) if v not in (None, "") else 0.0 for v in row] for row in table])
    # drop empty rows/columns
    rk = t.sum(axis=1) > 0
    ck = t.sum(axis=0) > 0
    t = t[rk][:, ck]
    rows = [n for n, k in zip(row_names, rk) if k]
    cols = [n for n, k in zip(col_names, ck) if k]
    if t.shape[0] < 2 or t.shape[1] < 2:
        raise ValueError("Enter counts for at least 2 groups (rows) and 2 outcomes (columns).")
    if np.any(t < 0) or np.any(t != np.round(t)):
        raise ValueError("Contingency tables need whole-number counts (no negatives or decimals).")
    z = stats.norm.ppf(1 - alpha / 2)
    res = {"test_name": "Contingency table", "rows": rows, "cols": cols, "table": t.astype(int).tolist(),
           "row_pct": (t / t.sum(axis=1, keepdims=True) * 100).tolist(), "alpha": alpha,
           "total": int(t.sum())}
    chi = stats.chi2_contingency(t, correction=False)
    res["chi_square"] = {"chi2": float(chi.statistic), "df": int(chi.dof), "p": float(chi.pvalue),
                         "min_expected": float(chi.expected_freq.min())}
    if t.shape == (2, 2):
        a, b = t[0]; c, d = t[1]
        f = stats.fisher_exact(t)
        res["fisher"] = {"p": float(f.pvalue)}
        # Haldane correction when a cell is zero
        aa, bb, cc, dd = (a, b, c, d) if min(a, b, c, d) > 0 else (a + .5, b + .5, c + .5, d + .5)
        orr = aa * dd / (bb * cc)
        se_or = math.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
        res["odds_ratio"] = {"value": orr, "ci": [orr * math.exp(-z * se_or), orr * math.exp(z * se_or)]}
        r1, r2 = aa / (aa + bb), cc / (cc + dd)
        rr = r1 / r2
        se_rr = math.sqrt(1 / aa - 1 / (aa + bb) + 1 / cc - 1 / (cc + dd))
        res["relative_risk"] = {"value": rr, "ci": [rr * math.exp(-z * se_rr), rr * math.exp(z * se_rr)]}
        res["risk_difference"] = {"value": a / (a + b) - c / (c + d)}
        res["p"] = res["fisher"]["p"]
        res["primary"] = "Fisher's exact test"
    else:
        res["p"] = res["chi_square"]["p"]
        res["primary"] = "Chi-square test"
    return res
