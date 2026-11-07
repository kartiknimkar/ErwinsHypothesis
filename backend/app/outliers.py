"""ROUT outlier detection (Motulsky & Brown 2006, BMC Bioinformatics 7:123).

1. Robust fit: least squares with a Lorentzian (Cauchy) merit function, sum of ln(1 + (r/RSDR)^2),
   where RSDR (robust SD of residuals) = 68.27th percentile of |residuals| × N/(N − K).
   The scale is updated and the fit repeated until it settles.
2. Outlier test on the robust residuals (FDR approach): sort |residuals| from smallest to largest,
   t_i = |r_i| / RSDR, two-tailed P from the t distribution with N − K df, compare with
   alpha_i = Q·(N − (i − 1))/N. The first point (from the smallest residual) with P < alpha_i and every
   point with a larger residual are outliers.
3. The caller then refits by ordinary least squares without the outliers.
"""
from __future__ import annotations

import numpy as np
from scipy import optimize, stats


def rsdr(resid: np.ndarray, k: int) -> float:
    n = len(resid)
    return float(np.percentile(np.abs(resid), 68.27) * n / (n - k)) if n > k else float("nan")


def fdr_outliers(resid, k: int, q: float = 0.01, scale: float | None = None) -> np.ndarray:
    """Boolean mask of outliers among residuals from a robust fit with k parameters."""
    r = np.asarray(resid, float)
    n = len(r)
    mask = np.zeros(n, bool)
    if n - k < 1:
        return mask
    s = rsdr(r, k) if scale is None else scale
    if not s > 0:
        return mask
    order = np.argsort(np.abs(r), kind="stable")
    p = 2 * stats.t.sf(np.abs(r[order]) / s, n - k)
    alphas = q * (n - np.arange(n)) / n
    hit = np.nonzero(p < alphas)[0]
    if len(hit):
        mask[order[hit[0]:]] = True
    return mask


def robust_fit(f, p0, x, y, max_iter: int = 30):
    """Lorentzian robust fit of y ≈ f(x, *p). Returns (params, residuals, RSDR)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    p = np.asarray(p0, float)
    k = len(p)
    res = lambda pp: y - f(x, *pp)
    # start from ordinary least squares, then switch to the robust merit function
    try:
        p = optimize.least_squares(res, p, method="lm" if len(y) > k else "trf").x
    except Exception:
        pass
    scale = rsdr(res(p), k)
    for _ in range(max_iter):
        if not scale > 0:
            break
        new = optimize.least_squares(res, p, loss="cauchy", f_scale=scale).x
        new_scale = rsdr(res(new), k)
        done = np.allclose(new, p, rtol=1e-7, atol=1e-10) and abs(new_scale - scale) <= 1e-7 * max(scale, 1e-300)
        p, scale = new, new_scale
        if done:
            break
    return p, res(p), scale


def rout_column(values, q: float = 0.01) -> dict:
    """ROUT for one column of values: the robust 'fit' is a single location parameter."""
    x = np.asarray([v for v in values if v is not None and np.isfinite(v)], float)
    out = {"method": "rout", "q": q, "n": int(len(x)), "outliers": []}
    if len(x) < 3 or np.ptp(x) == 0:
        return out
    const = lambda _x, m: np.full(len(_x), m)
    p, resid, scale = robust_fit(const, [float(np.median(x))], np.zeros(len(x)), x)
    mask = fdr_outliers(resid, 1, q, scale)
    out["robust_center"], out["rsdr"] = float(p[0]), scale
    out["outliers"] = [{"value": float(v)} for v in x[mask]]
    return out
