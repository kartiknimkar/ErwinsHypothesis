"""Multiple-variable and diagnostic analyses: correlation matrix, ROC curve, Bland-Altman."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .stats import _clean, stars


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def correlation_matrix(columns, names, method: str = "pearson", alpha: float = 0.05) -> dict:
    """Pairwise correlations between variables (columns); each pair uses rows where both have values."""
    cols = [[_num(v) for v in c] for c in columns]
    keep = [i for i, c in enumerate(cols) if sum(v is not None for v in c) >= 3]
    if len(keep) < 2:
        raise ValueError("Enter at least 2 variables (columns), each with 3 or more values.")
    cols = [cols[i] for i in keep]
    names = [names[i] for i in keep]
    k = len(cols)
    R = [[None] * k for _ in range(k)]
    P = [[None] * k for _ in range(k)]
    N = [[0] * k for _ in range(k)]
    CI = [[None] * k for _ in range(k)]
    z = stats.norm.ppf(1 - alpha / 2)
    for i in range(k):
        for j in range(k):
            pairs = [(a, b) for a, b in zip(cols[i], cols[j]) if a is not None and b is not None]
            n = len(pairs)
            N[i][j] = n
            if i == j:
                R[i][j], P[i][j] = 1.0, 0.0
                continue
            if n < 3:
                continue
            a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])
            if np.ptp(a) == 0 or np.ptp(b) == 0:
                continue
            res = stats.pearsonr(a, b) if method == "pearson" else stats.spearmanr(a, b)
            r, p = float(res.statistic), float(res.pvalue)
            R[i][j], P[i][j] = r, p
            if method == "pearson" and n > 3 and abs(r) < 1:
                zr, se = math.atanh(r), 1 / math.sqrt(n - 3)
                CI[i][j] = [math.tanh(zr - z * se), math.tanh(zr + z * se)]
    pairs_out = []
    for i in range(k):
        for j in range(i + 1, k):
            if R[i][j] is not None:
                pairs_out.append({"a": names[i], "b": names[j], "r": R[i][j], "p": P[i][j], "n": N[i][j],
                                  "ci": CI[i][j], "stars": stars(P[i][j]), "significant": P[i][j] < alpha})
    pairs_out.sort(key=lambda d: d["p"])
    return {"test_name": f"Correlation matrix ({'Pearson' if method == 'pearson' else 'Spearman'})",
            "method": method, "names": names, "r": R, "p": P, "n": N, "pairs": pairs_out, "alpha": alpha,
            "describe": [{"name": nm, "n": len(_clean(c)), "mean": float(np.mean(_clean(c))),
                          "sd": float(np.std(_clean(c), ddof=1))} for nm, c in zip(names, cols)]}


def roc(controls, patients, names=("Controls", "Patients"), alpha: float = 0.05) -> dict:
    """ROC curve: how well a value separates patients from controls (higher = more likely patient
    unless the patients' values are lower, which is detected automatically)."""
    c = _clean(controls); p = _clean(patients)
    if len(c) < 2 or len(p) < 2:
        raise ValueError("Enter at least 2 values for controls (first column) and for patients (second column).")
    higher = np.median(p) >= np.median(c)
    sc, sp = (c, p) if higher else (-c, -p)
    # AUC = Mann-Whitney U / (n1 n2); SE by Hanley & McNeil
    u = stats.mannwhitneyu(sp, sc, alternative="two-sided")
    n1, n2 = len(sp), len(sc)
    auc = float(u.statistic / (n1 * n2))
    q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
    se = math.sqrt((auc * (1 - auc) + (n1 - 1) * (q1 - auc ** 2) + (n2 - 1) * (q2 - auc ** 2)) / (n1 * n2))
    z = stats.norm.ppf(1 - alpha / 2)
    pz = (auc - 0.5) / se if se > 0 else float("inf")
    pval = float(2 * stats.norm.sf(abs(pz)))
    # curve over every cutoff
    cuts = np.unique(np.concatenate([sc, sp]))
    pts = [{"fpr": 0.0, "tpr": 0.0, "cut": None}]
    table = []
    for t in cuts[::-1]:
        sens = float(np.mean(sp >= t)); spec = float(np.mean(sc < t))
        cut = float(t if higher else -t)
        pts.append({"fpr": 1 - spec, "tpr": sens, "cut": cut})
        table.append({"cut": cut, "sens": 100 * sens, "spec": 100 * spec, "lr": sens / (1 - spec) if spec < 1 else None})
    pts.append({"fpr": 1.0, "tpr": 1.0, "cut": None})
    best = max(table, key=lambda r: r["sens"] + r["spec"])
    return {"test_name": "ROC curve", "auc": auc, "se": se, "ci": [max(0.0, auc - z * se), min(1.0, auc + z * se)],
            "p": pval, "stars": stars(pval), "n_controls": n2, "n_patients": n1, "names": list(names),
            "direction": "higher" if higher else "lower", "curve": pts, "table": table,
            "best": best, "alpha": alpha}


def bland_altman(a, b, names=("Method A", "Method B"), alpha: float = 0.05) -> dict:
    """Agreement between two methods measuring the same samples (each row = one sample)."""
    pairs = [(x, y) for x, y in zip(map(_num, a), map(_num, b)) if x is not None and y is not None]
    if len(pairs) < 3:
        raise ValueError("Enter at least 3 samples measured by both methods (one row per sample).")
    x = np.array([p[0] for p in pairs]); y = np.array([p[1] for p in pairs])
    diff = y - x
    avg = (x + y) / 2
    n = len(diff)
    bias, sd = float(diff.mean()), float(diff.std(ddof=1))
    z = stats.norm.ppf(1 - alpha / 2)
    t = stats.t.ppf(1 - alpha / 2, n - 1)
    se_bias = sd / math.sqrt(n)
    se_loa = math.sqrt(3 * sd ** 2 / n)  # Bland & Altman (1986)
    lo, hi = bias - z * sd, bias + z * sd
    trend = stats.linregress(avg, diff) if np.ptp(avg) > 0 else None
    return {"test_name": "Bland-Altman", "n": n, "names": list(names), "bias": bias, "sd": sd,
            "bias_ci": [bias - t * se_bias, bias + t * se_bias],
            "loa": [lo, hi], "loa_lo_ci": [lo - t * se_loa, lo + t * se_loa], "loa_hi_ci": [hi - t * se_loa, hi + t * se_loa],
            "p_bias": float(stats.ttest_1samp(diff, 0).pvalue),
            "trend_p": float(trend.pvalue) if trend else None, "trend_slope": float(trend.slope) if trend else None,
            "points": {"avg": avg.tolist(), "diff": diff.tolist()}, "alpha": alpha}
