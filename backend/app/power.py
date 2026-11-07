"""Power and sample size for common designs (two-sided tests).

t tests: noncentral t; one-way ANOVA: noncentral F with Cohen's f; two proportions: normal approximation
(Fleiss, without continuity correction). n is per group (pairs for the paired t test).
"""
from __future__ import annotations

import math

from scipy import optimize, stats


def _power_t(d: float, n: float, alpha: float, design: str) -> float:
    if design == "paired":
        df, nc = n - 1, d * math.sqrt(n)
    else:
        df, nc = 2 * n - 2, d * math.sqrt(n / 2)
    if df <= 0:
        return 0.0
    tc = stats.t.ppf(1 - alpha / 2, df)
    return float(stats.nct.sf(tc, df, nc) + stats.nct.cdf(-tc, df, nc))


def _power_anova(f: float, n: float, k: int, alpha: float) -> float:
    df1, df2 = k - 1, k * (n - 1)
    if df2 <= 0:
        return 0.0
    fc = stats.f.ppf(1 - alpha, df1, df2)
    return float(stats.ncf.sf(fc, df1, df2, f * f * k * n))


def _power_props(p1: float, p2: float, n: float, alpha: float) -> float:
    pbar = (p1 + p2) / 2
    za = stats.norm.ppf(1 - alpha / 2)
    sd0, sd1 = math.sqrt(2 * pbar * (1 - pbar)), math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    z = (abs(p1 - p2) * math.sqrt(n) - za * sd0) / sd1
    return float(stats.norm.cdf(z))


def _power(design, params, n, alpha):
    if design in ("unpaired", "paired"):
        return _power_t(params["d"], n, alpha, design)
    if design == "anova":
        return _power_anova(params["f"], n, params["k"], alpha)
    return _power_props(params["p1"], params["p2"], n, alpha)


def analyze(design: str, alpha: float = 0.05, power: float | None = 0.8, n: float | None = None,
            difference: float | None = None, sd: float | None = None, effect: float | None = None,
            k: int = 3, p1: float | None = None, p2: float | None = None) -> dict:
    """Give power to get n, or n to get power. Effect: difference + SD (t tests), Cohen's d / f, or two proportions."""
    if not 0 < alpha < 1:
        raise ValueError("Alpha must be between 0 and 1.")
    params, label = {}, ""
    if design in ("unpaired", "paired"):
        if effect is None:
            if difference is None or not sd or sd <= 0:
                raise ValueError("Enter the difference you want to detect and the SD (or Cohen's d directly).")
            effect = abs(difference) / sd
        if effect <= 0:
            raise ValueError("The effect size must be greater than 0.")
        params["d"] = float(effect); label = f"Cohen's d{'z' if design == 'paired' else ''} = {effect:.3g}"
    elif design == "anova":
        if effect is None or effect <= 0:
            raise ValueError("Enter Cohen's f (0.10 small, 0.25 medium, 0.40 large).")
        if k < 2:
            raise ValueError("Need at least 2 groups.")
        params.update(f=float(effect), k=int(k)); label = f"Cohen's f = {effect:.3g}, {k} groups"
    elif design == "proportions":
        if p1 is None or p2 is None or not (0 < p1 < 1 and 0 < p2 < 1) or p1 == p2:
            raise ValueError("Enter two different proportions between 0 and 1 (e.g. 0.30 and 0.50).")
        params.update(p1=float(p1), p2=float(p2)); label = f"{p1:.3g} vs {p2:.3g}"
    else:
        raise ValueError("Unknown design.")
    lo = 2 if design != "paired" else 2
    if n is None:
        if power is None or not 0 < power < 1:
            raise ValueError("Enter the power you want (e.g. 0.8) or a sample size.")
        if _power(design, params, 1e7, alpha) < power:
            raise ValueError("That effect is too small to detect with any practical sample size.")
        hi = 4
        while _power(design, params, hi, alpha) < power:
            hi *= 2
        n_exact = optimize.brentq(lambda m: _power(design, params, m, alpha) - power, lo, hi, xtol=1e-6)
        n_needed = max(lo, math.ceil(n_exact - 1e-9))
        achieved = _power(design, params, n_needed, alpha)
        mode = "n"
    else:
        if n < lo:
            raise ValueError(f"Sample size must be at least {lo}.")
        n_needed, n_exact, achieved, mode = int(n), float(n), _power(design, params, n, alpha), "power"
    top = max(n_needed * 2, 10)
    curve_n = sorted({max(lo, round(lo + (top - lo) * i / 40)) for i in range(41)})
    return {"test_name": "Power and sample size", "kind": "power", "design": design, "mode": mode, "alpha": alpha,
            "target_power": power, "n": n_needed, "n_exact": float(n_exact), "power": achieved, "effect_label": label,
            "total_n": n_needed * (params.get("k", 2) if design != "paired" else 1),
            "curve": {"n": curve_n, "power": [_power(design, params, m, alpha) for m in curve_n]}}
