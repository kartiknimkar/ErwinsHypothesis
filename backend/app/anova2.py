"""Two-way ANOVA and repeated-measures designs.

two_way: general linear model with sum-to-zero coding and Type III sums of squares
(handles unequal group sizes); multiple comparisons within each row.
repeated_measures: one-way RM ANOVA with Geisser-Greenhouse correction, Friedman test.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .stats import describe, stars


def _num(v):
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _effect_cols(idx: np.ndarray, levels: int) -> np.ndarray:
    """Sum-to-zero (effect) coding: levels-1 columns; last level coded -1."""
    X = np.zeros((len(idx), levels - 1))
    for c in range(levels - 1):
        X[:, c] = (idx == c).astype(float)
    X[idx == levels - 1, :] = -1.0
    return X


def _rss(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r)


def two_way(row_labels, columns, col_names, alpha: float = 0.05) -> dict:
    """row_labels: one label per data row (rows with the same label are replicates).
    columns: one list per column-factor level, aligned with row_labels."""
    obs = []
    for i, lab in enumerate(row_labels):
        lab = str(lab or "").strip()
        if not lab:
            continue
        for j, col in enumerate(columns):
            v = _num(col[i]) if i < len(col) else None
            if v is not None:
                obs.append((lab, j, v))
    rows = list(dict.fromkeys(o[0] for o in obs))
    cols_used = sorted(set(o[1] for o in obs))
    if len(rows) < 2 or len(cols_used) < 2:
        raise ValueError("Two-way ANOVA needs at least 2 row names (first column) and 2 data columns with values.")
    cmap = {j: k for k, j in enumerate(cols_used)}
    names = [col_names[j] for j in cols_used]
    a, b = len(rows), len(cols_used)
    A = np.array([rows.index(o[0]) for o in obs])
    B = np.array([cmap[o[1]] for o in obs])
    y = np.array([o[2] for o in obs])
    N = len(y)
    counts = np.zeros((a, b), int)
    for ai, bi in zip(A, B):
        counts[ai, bi] += 1
    if np.any(counts == 0):
        missing = [f"{rows[i]} / {names[j]}" for i in range(a) for j in range(b) if counts[i, j] == 0]
        raise ValueError("Every row name needs at least one value in every column. Missing: " + ", ".join(missing[:4]))

    XA, XB = _effect_cols(A, a), _effect_cols(B, b)
    XAB = np.column_stack([XA[:, i] * XB[:, j] for i in range(a - 1) for j in range(b - 1)])
    one = np.ones((N, 1))
    full = np.column_stack([one, XA, XB, XAB])
    df_res = N - full.shape[1]
    if df_res < 1:
        raise ValueError("Not enough replicates: enter more than one value for at least some row/column combinations.")
    rss_full = _rss(full, y)
    ms_res = rss_full / df_res
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    terms = [("Interaction", XAB, (a - 1) * (b - 1), np.column_stack([one, XA, XB])),
             ("Row factor", XA, a - 1, np.column_stack([one, XB, XAB])),
             ("Column factor", XB, b - 1, np.column_stack([one, XA, XAB]))]
    table = []
    for name, _, df, reduced in terms:
        ss = _rss(reduced, y) - rss_full
        F = (ss / df) / ms_res if ms_res > 0 else float("inf")
        p = float(stats.f.sf(F, df, df_res))
        table.append({"source": name, "SS": ss, "df": df, "MS": ss / df, "F": F, "p": p,
                      "pct": 100 * ss / ss_tot if ss_tot > 0 else None, "stars": stars(p)})
    table.append({"source": "Residual", "SS": rss_full, "df": df_res, "MS": ms_res, "F": None, "p": None, "pct": None})

    # cell statistics
    cells = []
    for i in range(a):
        for j in range(b):
            v = y[(A == i) & (B == j)]
            d = describe(v, f"{rows[i]} · {names[j]}")
            d.update(row=rows[i], col=names[j], i=i, j=j)
            cells.append(d)
    mean = {(c["i"], c["j"]): c["mean"] for c in cells}

    # multiple comparisons: within each row, compare the columns
    comps = []
    pairs = [(j1, j2) for j1 in range(b) for j2 in range(j1 + 1, b)]
    conf = 1 - alpha
    if b == 2:
        method = "Šídák's multiple comparisons (columns within each row)"
        m = a
        a_adj = 1 - conf ** (1 / m)
        tcrit = stats.t.ppf(1 - a_adj / 2, df_res)
    else:
        method = "Tukey's multiple comparisons (columns within each row)"
        qcrit = stats.studentized_range.ppf(conf, b, df_res)
    for i in range(a):
        for j1, j2 in pairs:
            diff = mean[(i, j1)] - mean[(i, j2)]
            se = math.sqrt(ms_res * (1 / counts[i, j1] + 1 / counts[i, j2]))
            if b == 2:
                p_raw = 2 * stats.t.sf(abs(diff) / se, df_res)
                p = 1 - (1 - p_raw) ** m
                half = tcrit * se
            else:
                q = abs(diff) / (se / math.sqrt(2))
                p = float(stats.studentized_range.sf(q, b, df_res))
                half = qcrit * se / math.sqrt(2)
            p = float(min(1.0, max(0.0, p)))
            comps.append({"row": rows[i], "a": names[j1], "b": names[j2], "i": i, "j1": j1, "j2": j2,
                          "diff": diff, "ci_low": diff - half, "ci_high": diff + half, "p": p,
                          "stars": stars(p), "significant": p < alpha})
    inter = table[0]
    return {"test_name": "Two-way ANOVA", "rows": rows, "cols": names, "alpha": alpha,
            "table": table, "cells": cells, "comparisons": comps, "posthoc_name": method,
            "p": inter["p"], "n": N, "balanced": bool(np.all(counts == counts[0, 0]))}


def repeated_measures(columns, names, kind: str = "rm", alpha: float = 0.05) -> dict:
    """Same subjects (rows) measured in every column. Only complete rows are used.
    kind: "rm" (RM one-way ANOVA + Tukey, Geisser-Greenhouse corrected) or "friedman" (+ Dunn's)."""
    k = len(columns)
    rows = []
    for vals in zip(*columns):
        nums = [_num(v) for v in vals]
        if all(v is not None for v in nums):
            rows.append(nums)
    Y = np.array(rows, float)
    n = len(Y)
    if k < 3:
        raise ValueError("Repeated-measures ANOVA needs 3 or more columns (use a paired test for 2).")
    if n < 2:
        raise ValueError("Need at least 2 subjects (rows) with a value in every column.")
    res = {"kind": kind, "alpha": alpha, "k": k, "n_subjects": n,
           "groups": [describe(Y[:, j], names[j]) for j in range(k)]}
    pairs = [(i, j) for i in range(k) for j in range(i + 1, k)]
    comps = []
    if kind == "rm":
        grand = Y.mean()
        ss_tot = float(np.sum((Y - grand) ** 2))
        ss_g = float(n * np.sum((Y.mean(axis=0) - grand) ** 2))
        ss_s = float(k * np.sum((Y.mean(axis=1) - grand) ** 2))
        ss_e = ss_tot - ss_g - ss_s
        df_g, df_s, df_e = k - 1, n - 1, (k - 1) * (n - 1)
        ms_e = ss_e / df_e
        F = (ss_g / df_g) / ms_e if ms_e > 0 else float("inf")
        p = float(stats.f.sf(F, df_g, df_e))
        # Geisser-Greenhouse epsilon from the double-centered covariance matrix
        S = np.cov(Y, rowvar=False)
        C = np.eye(k) - np.ones((k, k)) / k
        Sc = C @ S @ C
        eps = float(np.trace(Sc) ** 2 / ((k - 1) * np.sum(Sc ** 2))) if np.sum(Sc ** 2) > 0 else 1.0
        eps = min(1.0, max(1 / (k - 1), eps))
        p_gg = float(stats.f.sf(F, eps * df_g, eps * df_e))
        res.update(test_name="Repeated-measures one-way ANOVA", posthoc_name="Tukey's multiple comparisons",
                   F=F, df_between=df_g, df_within=df_e, p_uncorrected=p, epsilon=eps, p=p_gg,
                   r_squared=ss_g / (ss_g + ss_e) if ss_g + ss_e > 0 else None,
                   table=[{"source": "Treatment (between columns)", "SS": ss_g, "df": df_g, "MS": ss_g / df_g},
                          {"source": "Individual (between rows)", "SS": ss_s, "df": df_s, "MS": ss_s / df_s if df_s else None},
                          {"source": "Residual", "SS": ss_e, "df": df_e, "MS": ms_e},
                          {"source": "Total", "SS": ss_tot, "df": n * k - 1, "MS": None}])
        qcrit = stats.studentized_range.ppf(1 - alpha, k, df_e)
        se = math.sqrt(ms_e / n)
        for i, j in pairs:
            diff = float(Y[:, i].mean() - Y[:, j].mean())
            pp = float(min(1.0, stats.studentized_range.sf(abs(diff) / se, k, df_e)))
            comps.append({"a": names[i], "b": names[j], "i": i, "j": j, "diff": diff,
                          "ci_low": diff - qcrit * se, "ci_high": diff + qcrit * se, "p": pp})
        res["diff_label"] = "Mean difference"
    elif kind == "friedman":
        fr = stats.friedmanchisquare(*[Y[:, j] for j in range(k)])
        res.update(test_name="Friedman test", posthoc_name="Dunn's multiple comparisons",
                   chi2=float(fr.statistic), df_between=k - 1, p=float(fr.pvalue))
        R = np.apply_along_axis(stats.rankdata, 1, Y).sum(axis=0)
        se = math.sqrt(n * k * (k + 1) / 6)
        m = len(pairs)
        for i, j in pairs:
            z = (R[i] - R[j]) / se
            comps.append({"a": names[i], "b": names[j], "i": i, "j": j, "diff": float(R[i] - R[j]),
                          "ci_low": None, "ci_high": None, "z": float(z),
                          "p": float(min(1.0, 2 * stats.norm.sf(abs(z)) * m))})
        res["diff_label"] = "Rank sum difference"
    else:
        raise ValueError(f"Unknown test type: {kind}")
    for c in comps:
        c["stars"] = stars(c["p"])
        c["significant"] = c["p"] < alpha
    res["comparisons"] = comps
    res["stars"] = stars(res["p"])
    res["significant"] = res["p"] < alpha
    return res
