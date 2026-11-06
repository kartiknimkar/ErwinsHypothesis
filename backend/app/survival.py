"""Survival analysis: Kaplan-Meier curves, log-rank test, hazard ratio."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def _clean_pairs(times, events):
    t, e = [], []
    for ti, ei in zip(times, events):
        if ti is None or ei is None:
            continue
        try:
            tf, ef = float(ti), float(ei)
        except (TypeError, ValueError):
            continue
        if math.isnan(tf) or math.isnan(ef):
            continue
        if ef not in (0.0, 1.0):
            raise ValueError("Outcome values must be 1 (event, e.g. death) or 0 (censored).")
        if tf < 0:
            raise ValueError("Times can't be negative.")
        t.append(tf)
        e.append(int(ef))
    return np.array(t, float), np.array(e, int)


def kaplan_meier(t: np.ndarray, e: np.ndarray, alpha: float = 0.05) -> dict:
    """Product-limit estimate with Greenwood SE and log-log (asymmetric) confidence limits."""
    z = stats.norm.ppf(1 - alpha / 2)
    times = np.unique(t[e == 1])
    s, gw = 1.0, 0.0
    steps = [{"t": 0.0, "s": 1.0, "lo": 1.0, "hi": 1.0, "at_risk": int(len(t))}]
    for ti in times:
        n = int(np.sum(t >= ti))
        d = int(np.sum((t == ti) & (e == 1)))
        s *= 1 - d / n
        if n > d:
            gw += d / (n * (n - d))
        if 0 < s < 1 and gw > 0:
            se_ll = math.sqrt(gw) / abs(math.log(s))
            ll = math.log(-math.log(s))
            lo, hi = math.exp(-math.exp(ll + z * se_ll)), math.exp(-math.exp(ll - z * se_ll))
        else:
            lo = hi = s
        steps.append({"t": float(ti), "s": s, "lo": lo, "hi": hi, "at_risk": n})
    median = next((st["t"] for st in steps if st["s"] <= 0.5), None)
    censored = sorted(float(x) for x in t[e == 0])
    cens_s = [next(st["s"] for st in reversed(steps) if st["t"] <= c) for c in censored]
    return {"steps": steps, "median": median, "n": int(len(t)), "events": int(e.sum()),
            "censored": {"t": censored, "s": cens_s}}


def logrank(groups: list[tuple[np.ndarray, np.ndarray]]) -> dict:
    """k-group log-rank (Mantel-Cox) test. Returns chi2, df, p, observed/expected per group."""
    k = len(groups)
    all_t = np.concatenate([g[0] for g in groups])
    all_e = np.concatenate([g[1] for g in groups])
    O = np.zeros(k); E = np.zeros(k); V = np.zeros((k, k))
    for ti in np.unique(all_t[all_e == 1]):
        n = np.array([np.sum(g[0] >= ti) for g in groups], float)
        d = np.array([np.sum((g[0] == ti) & (g[1] == 1)) for g in groups], float)
        N, D = n.sum(), d.sum()
        O += d
        E += n * D / N
        if N > 1:
            f = D * (N - D) / (N - 1)
            V += f * (np.diag(n / N) - np.outer(n, n) / N ** 2)
    diff = (O - E)[:-1]
    chi2 = float(diff @ np.linalg.pinv(V[:-1, :-1]) @ diff)
    df = k - 1
    return {"chi2": chi2, "df": df, "p": float(stats.chi2.sf(chi2, df)),
            "observed": O.tolist(), "expected": E.tolist(), "variance": V.diagonal().tolist()}


def analyze(times: list, groups: dict[str, list], alpha: float = 0.05) -> dict:
    """times: one list shared by all rows; groups: {name: outcome column (1/0/blank)}."""
    curves = []
    data = []
    for name, outcome in groups.items():
        t, e = _clean_pairs(times, outcome)
        if len(t) == 0:
            continue
        data.append((t, e))
        km = kaplan_meier(t, e, alpha)
        km["name"] = name
        curves.append(km)
    if not curves:
        raise ValueError("Enter times in the first column and 1 (event) or 0 (censored) in a group column.")
    res = {"test_name": "Survival analysis (Kaplan-Meier)", "curves": curves, "alpha": alpha}
    if len(curves) >= 2:
        if sum(c["events"] for c in curves) == 0:
            raise ValueError("No events (1s) yet, so survival can't be compared.")
        lr = logrank(data)
        res["logrank"] = lr
        res["p"] = lr["p"]
        if len(curves) == 2:
            # Mantel-Haenszel hazard ratio, second group relative to the first
            O2, E2, V2 = lr["observed"][1], lr["expected"][1], lr["variance"][1]
            if V2 > 0:
                z = stats.norm.ppf(1 - alpha / 2)
                lhr = (O2 - E2) / V2
                res["hazard_ratio"] = {"value": math.exp(lhr), "ci": [math.exp(lhr - z / math.sqrt(V2)),
                                       math.exp(lhr + z / math.sqrt(V2))],
                                       "label": f"{curves[1]['name']} vs {curves[0]['name']}"}
            m1, m2 = curves[0]["median"], curves[1]["median"]
            if m1 and m2:
                res["median_ratio"] = m2 / m1
    return res
