"""Statistics engine for Erwin's Hypothesis.

Every function takes plain Python lists and returns a plain dict, so results
can be sent to the interface as JSON and checked in tests against reference
values from established software.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def _clean(values) -> np.ndarray:
    """Turn a list that may contain blanks/None/strings into a float array."""
    out = []
    for v in values:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        f = float(v)
        if not math.isnan(f):
            out.append(f)
    return np.asarray(out, dtype=float)


def stars(p: float) -> str:
    """Significance summary in the conventional style."""
    if p < 0.0001:
        return "****"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def describe(values, name: str = "") -> dict:
    x = _clean(values)
    n = len(x)
    sd = float(np.std(x, ddof=1)) if n > 1 else float("nan")
    return {
        "name": name,
        "n": n,
        "mean": float(np.mean(x)) if n else float("nan"),
        "sd": sd,
        "sem": sd / math.sqrt(n) if n > 1 else float("nan"),
        "median": float(np.median(x)) if n else float("nan"),
        "min": float(np.min(x)) if n else float("nan"),
        "max": float(np.max(x)) if n else float("nan"),
    }


def t_test(a, b, kind: str = "unpaired", name_a: str = "A", name_b: str = "B",
           alpha: float = 0.05) -> dict:
    """Compare two groups.

    kind: "unpaired" (Student, equal variances), "welch" (unequal variances),
          "paired", or "mannwhitney" (nonparametric, unpaired).
    The difference is reported as mean(B) - mean(A).
    """
    raw_a, raw_b = list(a), list(b)
    if kind == "paired":
        # keep only rows where both values exist
        pairs = []
        for va, vb in zip(raw_a, raw_b):
            ca, cb = _clean([va]), _clean([vb])
            if len(ca) and len(cb):
                pairs.append((ca[0], cb[0]))
        if len(pairs) < 2:
            raise ValueError("A paired t test needs at least 2 complete pairs.")
        xa = np.array([p[0] for p in pairs])
        xb = np.array([p[1] for p in pairs])
    else:
        xa, xb = _clean(raw_a), _clean(raw_b)
        if len(xa) < 2 or len(xb) < 2:
            raise ValueError("Each group needs at least 2 values.")

    result = {
        "kind": kind,
        "groups": [describe(xa, name_a), describe(xb, name_b)],
        "alpha": alpha,
    }
    conf = 1 - alpha

    if kind in ("unpaired", "welch"):
        equal = kind == "unpaired"
        r = stats.ttest_ind(xb, xa, equal_var=equal)
        ci = r.confidence_interval(conf)
        diff = float(np.mean(xb) - np.mean(xa))
        result.update(
            test_name="Unpaired t test" if equal else "Welch's t test",
            statistic_name="t",
            statistic=abs(float(r.statistic)),
            df=float(r.df),
            p=float(r.pvalue),
            difference=diff,
            difference_label=f"Mean of {name_b} − mean of {name_a}",
            ci_low=float(ci.low),
            ci_high=float(ci.high),
        )
        if equal:
            # F test for equal variances, a common sanity check
            va, vb = np.var(xa, ddof=1), np.var(xb, ddof=1)
            if va > 0 and vb > 0:
                f = max(va, vb) / min(va, vb)
                dfn = (len(xa) if va >= vb else len(xb)) - 1
                dfd = (len(xb) if va >= vb else len(xa)) - 1
                p_f = min(1.0, 2 * stats.f.sf(f, dfn, dfd))
                result["variance_check"] = {"F": float(f), "dfn": dfn, "dfd": dfd, "p": float(p_f)}
    elif kind == "paired":
        r = stats.ttest_rel(xb, xa)
        ci = r.confidence_interval(conf)
        diffs = xb - xa
        result.update(
            test_name="Paired t test",
            statistic_name="t",
            statistic=abs(float(r.statistic)),
            df=float(r.df),
            p=float(r.pvalue),
            difference=float(np.mean(diffs)),
            difference_label=f"Mean of differences ({name_b} − {name_a})",
            ci_low=float(ci.low),
            ci_high=float(ci.high),
            n_pairs=len(diffs),
        )
    elif kind == "mannwhitney":
        r = stats.mannwhitneyu(xb, xa, alternative="two-sided")
        result.update(
            test_name="Mann-Whitney test",
            statistic_name="U",
            statistic=float(min(r.statistic, len(xa) * len(xb) - r.statistic)),
            df=None,
            p=float(r.pvalue),
            difference=float(np.median(xb) - np.median(xa)),
            difference_label=f"Median of {name_b} − median of {name_a}",
            ci_low=None,
            ci_high=None,
        )
    else:
        raise ValueError(f"Unknown test type: {kind}")

    result["stars"] = stars(result["p"])
    result["significant"] = result["p"] < alpha
    return result


def linear_regression(x, y, alpha: float = 0.05, band_points: int = 100) -> dict:
    """Simple least-squares linear regression of y on x, with a confidence band."""
    pairs = []
    for vx, vy in zip(list(x), list(y)):
        cx, cy = _clean([vx]), _clean([vy])
        if len(cx) and len(cy):
            pairs.append((cx[0], cy[0]))
    if len(pairs) < 3:
        raise ValueError("Linear regression needs at least 3 complete (X, Y) points.")
    xs = np.array([p[0] for p in pairs])
    ys = np.array([p[1] for p in pairs])
    if np.ptp(xs) == 0:
        raise ValueError("All X values are the same, so no line can be fitted.")

    n = len(xs)
    r = stats.linregress(xs, ys)
    df = n - 2
    tcrit = stats.t.ppf(1 - alpha / 2, df)
    resid = ys - (r.intercept + r.slope * xs)
    ss_res = float(np.sum(resid ** 2))
    sy_x = math.sqrt(ss_res / df) if df > 0 else float("nan")
    x_mean = float(np.mean(xs))
    sxx = float(np.sum((xs - x_mean) ** 2))

    grid = np.linspace(xs.min(), xs.max(), band_points)
    fit = r.intercept + r.slope * grid
    half = tcrit * sy_x * np.sqrt(1 / n + (grid - x_mean) ** 2 / sxx)

    x_intercept = -r.intercept / r.slope if r.slope != 0 else None
    p = float(r.pvalue)
    return {
        "test_name": "Simple linear regression",
        "n": n,
        "slope": float(r.slope),
        "slope_se": float(r.stderr),
        "slope_ci": [float(r.slope - tcrit * r.stderr), float(r.slope + tcrit * r.stderr)],
        "intercept": float(r.intercept),
        "intercept_se": float(r.intercept_stderr),
        "intercept_ci": [float(r.intercept - tcrit * r.intercept_stderr),
                         float(r.intercept + tcrit * r.intercept_stderr)],
        "x_intercept": float(x_intercept) if x_intercept is not None else None,
        "r": float(r.rvalue),
        "r_squared": float(r.rvalue ** 2),
        "sy_x": sy_x,
        "df": df,
        "F": float((r.slope / r.stderr) ** 2) if r.stderr > 0 else None,
        "p": p,
        "stars": stars(p),
        "significant": p < alpha,
        "alpha": alpha,
        "equation": f"Y = {r.slope:.4g}·X {'+' if r.intercept >= 0 else '−'} {abs(r.intercept):.4g}",
        "points": {"x": xs.tolist(), "y": ys.tolist()},
        "line": {"x": grid.tolist(), "y": fit.tolist(),
                 "low": (fit - half).tolist(), "high": (fit + half).tolist()},
    }
