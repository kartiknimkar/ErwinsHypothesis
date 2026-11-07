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
    if t.shape[1] == 2 and t.shape[0] >= 3:
        res["trend"] = trend(t)
    return res


def trend(t) -> dict:
    """Chi-square test for trend (Cochran-Armitage) for a k×2 table with rows in a meaningful order
    (scores 1..k): is the proportion in the first column rising or falling across rows? df = 1."""
    t = np.asarray(t, float)
    a, n = t[:, 0], t.sum(axis=1)
    N = n.sum()
    p = a.sum() / N
    sc = np.arange(1, len(n) + 1, dtype=float)
    T = float(np.sum(sc * (a - n * p)))
    var = p * (1 - p) * (np.sum(n * sc ** 2) - np.sum(n * sc) ** 2 / N)
    chi2 = T * T / var if var > 0 else float("nan")
    return {"chi2": float(chi2), "df": 1, "p": float(stats.chi2.sf(chi2, 1)),
            "direction": "rising" if T > 0 else "falling"}


def mcnemar(table, row_names, col_names, alpha: float = 0.05) -> dict:
    """McNemar's test for paired yes/no data. Rows = first measurement (or case), columns = second
    (or matched control); only the discordant cells b (row 1, col 2) and c (row 2, col 1) matter."""
    t = np.array([[float(v) if v not in (None, "") else 0.0 for v in row] for row in table])
    if t.shape != (2, 2):
        raise ValueError("McNemar's test needs exactly 2 rows and 2 columns (a 2×2 table of pairs).")
    if np.any(t < 0) or np.any(t != np.round(t)):
        raise ValueError("Enter whole-number counts of pairs.")
    b, c = int(t[0, 1]), int(t[1, 0])
    if b + c == 0:
        raise ValueError("There are no discordant pairs (pairs that changed), so the test can't be done.")
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)  # with continuity correction
    exact = float(stats.binomtest(b, b + c, 0.5).pvalue)
    z = stats.norm.ppf(1 - alpha / 2)
    bb, cc = (b, c) if min(b, c) > 0 else (b + .5, c + .5)
    orr = bb / cc
    se = math.sqrt(1 / bb + 1 / cc)
    return {"test_name": "McNemar's test", "kind": "mcnemar", "rows": row_names[:2], "cols": col_names[:2], "table": t.astype(int).tolist(),
            "b": b, "c": c, "chi2": float(chi2), "df": 1, "p_chi2": float(stats.chi2.sf(chi2, 1)), "p": exact,
            "odds_ratio": {"value": orr, "ci": [orr * math.exp(-z * se), orr * math.exp(z * se)]},
            "row_pct": (t / t.sum(axis=1, keepdims=True) * 100).tolist(), "alpha": alpha, "total": int(t.sum())}


def goodness_of_fit(names, observed, expected, expected_is_pct: bool = False, alpha: float = 0.05) -> dict:
    """Do observed counts match the expected numbers (or percentages)? Chi-square goodness of fit;
    with 2 categories also the exact binomial test."""
    rows = [(n, o, e) for n, o, e in zip(names, observed, expected) if o not in (None, "") and e not in (None, "")]
    if len(rows) < 2:
        raise ValueError("Enter at least 2 categories, each with an observed count and an expected value.")
    o = np.array([float(r[1]) for r in rows]); e = np.array([float(r[2]) for r in rows])
    if np.any(o < 0) or np.any(o != np.round(o)):
        raise ValueError("Observed values must be whole-number counts.")
    if np.any(e <= 0):
        raise ValueError("Expected values must be greater than 0.")
    e = e / e.sum() * o.sum()  # works for expected counts, percentages or ratios
    chi2 = float(np.sum((o - e) ** 2 / e))
    df = len(o) - 1
    res = {"test_name": "Chi-square goodness of fit", "kind": "gof", "names": [str(r[0]) for r in rows], "observed": o.astype(int).tolist(),
           "expected": e.tolist(), "chi2": chi2, "df": df, "p": float(stats.chi2.sf(chi2, df)), "alpha": alpha,
           "min_expected": float(e.min()), "total": int(o.sum()),
           "residuals": ((o - e) / np.sqrt(e)).tolist()}
    if len(o) == 2:
        res["binomial_p"] = float(stats.binomtest(int(o[0]), int(o.sum()), e[0] / o.sum()).pvalue)
    return res
