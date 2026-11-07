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
        # half-width of the 95% confidence interval of the mean
        "ci95": float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)) if n > 1 else float("nan"),
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
    if kind in ("paired", "wilcoxon"):
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
    elif kind == "wilcoxon":
        diffs = xb - xa
        if np.all(diffs == 0):
            raise ValueError("All differences are zero, so there's nothing to test.")
        r = stats.wilcoxon(diffs)
        result.update(
            test_name="Wilcoxon matched-pairs signed-rank test",
            statistic_name="W",
            statistic=float(r.statistic),
            df=None,
            p=float(r.pvalue),
            difference=float(np.median(diffs)),
            difference_label=f"Median of differences ({name_b} − {name_a})",
            ci_low=None,
            ci_high=None,
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
    if kind in ("paired", "wilcoxon"):
        result["normality"] = [normality(xb - xa)]
        result["normality_of"] = "differences"
    else:
        result["normality"] = [normality(xa), normality(xb)]
        result["normality_of"] = "groups"
    return result


def normality(values) -> dict | None:
    """Shapiro-Wilk normality test (needs 3+ values)."""
    x = _clean(values)
    if len(x) < 3 or np.ptp(x) == 0:
        return None
    r = stats.shapiro(x)
    return {"W": float(r.statistic), "p": float(r.pvalue), "normal": bool(r.pvalue >= 0.05)}


def _pairs(k: int):
    return [(i, j) for i in range(k) for j in range(i + 1, k)]


def one_way_anova(groups, names=None, kind: str = "ordinary", alpha: float = 0.05) -> dict:
    """Compare 3+ groups.

    kind: "ordinary" (one-way ANOVA + Tukey), "welch" (Welch's ANOVA + Games-Howell),
          "kruskal" (Kruskal-Wallis + Dunn's, Bonferroni-adjusted).
    Pairwise differences are reported as first − second for "A vs B".
    """
    xs = [_clean(g) for g in groups]
    names = list(names) if names else [chr(65 + i) for i in range(len(xs))]
    keep = [i for i, x in enumerate(xs) if len(x) > 0]
    xs = [xs[i] for i in keep]
    names = [names[i] for i in keep]
    k = len(xs)
    if k < 3:
        raise ValueError("Comparing 3 or more groups needs at least 3 columns with data.")
    if any(len(x) < 2 for x in xs):
        raise ValueError("Each group needs at least 2 values.")

    ns = np.array([len(x) for x in xs], dtype=float)
    means = np.array([x.mean() for x in xs])
    vars_ = np.array([x.var(ddof=1) for x in xs])
    N = ns.sum()
    conf = 1 - alpha
    res = {"kind": kind, "alpha": alpha, "k": k,
           "groups": [describe(x, n) for x, n in zip(xs, names)]}
    comps = []

    if kind == "ordinary":
        grand = np.concatenate(xs).mean()
        ssb = float(np.sum(ns * (means - grand) ** 2))
        ssw = float(np.sum((ns - 1) * vars_))
        dfb, dfw = k - 1, int(N - k)
        msb, msw = ssb / dfb, ssw / dfw
        F = msb / msw if msw > 0 else float("inf")
        p = float(stats.f.sf(F, dfb, dfw))
        res.update(test_name="Ordinary one-way ANOVA", posthoc_name="Tukey's multiple comparisons",
                   F=F, df_between=dfb, df_within=dfw, p=p, r_squared=ssb / (ssb + ssw),
                   table=[{"source": "Between groups", "SS": ssb, "df": dfb, "MS": msb},
                          {"source": "Within groups (residual)", "SS": ssw, "df": dfw, "MS": msw},
                          {"source": "Total", "SS": ssb + ssw, "df": int(N - 1), "MS": None}])
        tk = stats.tukey_hsd(*xs)
        ci = tk.confidence_interval(conf)
        for i, j in _pairs(k):
            comps.append({"a": names[i], "b": names[j], "i": i, "j": j, "diff": float(tk.statistic[i, j]),
                          "ci_low": float(ci.low[i, j]), "ci_high": float(ci.high[i, j]),
                          "p": float(tk.pvalue[i, j])})
        # Brown-Forsythe check for equal spread
        bf = stats.levene(*xs, center="median")
        res["variance_check"] = {"name": "Brown-Forsythe", "statistic": float(bf.statistic), "p": float(bf.pvalue)}
    elif kind == "welch":
        w = ns / vars_
        wsum = w.sum()
        mw = np.sum(w * means) / wsum
        a = np.sum(w * (means - mw) ** 2) / (k - 1)
        lam = np.sum((1 - w / wsum) ** 2 / (ns - 1))
        b = 1 + 2 * (k - 2) / (k ** 2 - 1) * lam
        F = float(a / b)
        df2 = float((k ** 2 - 1) / (3 * lam))
        p = float(stats.f.sf(F, k - 1, df2))
        res.update(test_name="Welch's ANOVA", posthoc_name="Games-Howell multiple comparisons",
                   F=F, df_between=k - 1, df_within=df2, p=p)
        for i, j in _pairs(k):
            vi, vj = vars_[i] / ns[i], vars_[j] / ns[j]
            se = math.sqrt((vi + vj) / 2)
            df = (vi + vj) ** 2 / (vi ** 2 / (ns[i] - 1) + vj ** 2 / (ns[j] - 1))
            diff = float(means[i] - means[j])
            q = abs(diff) / se
            qcrit = float(stats.studentized_range.ppf(conf, k, df))
            comps.append({"a": names[i], "b": names[j], "i": i, "j": j, "diff": diff,
                          "ci_low": diff - qcrit * se, "ci_high": diff + qcrit * se,
                          "p": float(min(1.0, stats.studentized_range.sf(q, k, df)))})
    elif kind == "kruskal":
        kw = stats.kruskal(*xs)
        res.update(test_name="Kruskal-Wallis test", posthoc_name="Dunn's multiple comparisons",
                   H=float(kw.statistic), df_between=k - 1, p=float(kw.pvalue))
        allv = np.concatenate(xs)
        ranks = stats.rankdata(allv)
        _, counts = np.unique(allv, return_counts=True)
        tie = np.sum(counts ** 3 - counts) / (12 * (N - 1))
        bounds = np.cumsum([0] + [len(x) for x in xs])
        mean_ranks = [ranks[bounds[g]:bounds[g + 1]].mean() for g in range(k)]
        m = len(_pairs(k))
        for i, j in _pairs(k):
            se = math.sqrt((N * (N + 1) / 12 - tie) * (1 / ns[i] + 1 / ns[j]))
            z = (mean_ranks[i] - mean_ranks[j]) / se
            p_raw = 2 * stats.norm.sf(abs(z))
            comps.append({"a": names[i], "b": names[j], "i": i, "j": j,
                          "diff": float(mean_ranks[i] - mean_ranks[j]), "ci_low": None, "ci_high": None,
                          "z": float(z), "p": float(min(1.0, p_raw * m))})
        res["diff_label"] = "Mean rank difference"
    else:
        raise ValueError(f"Unknown test type: {kind}")

    for c in comps:
        c["stars"] = stars(c["p"])
        c["significant"] = c["p"] < alpha
    res.setdefault("diff_label", "Mean difference")
    res["comparisons"] = comps
    res["stars"] = stars(res["p"])
    res["significant"] = res["p"] < alpha
    res["normality"] = [normality(x) for x in xs]
    return res


def correlation(x, y, alpha: float = 0.05) -> dict:
    """Pearson and Spearman correlation for paired (X, Y) values."""
    pairs = []
    for vx, vy in zip(list(x), list(y)):
        cx, cy = _clean([vx]), _clean([vy])
        if len(cx) and len(cy):
            pairs.append((cx[0], cy[0]))
    if len(pairs) < 3:
        raise ValueError("Correlation needs at least 3 complete (X, Y) points.")
    xs = np.array([p[0] for p in pairs]); ys = np.array([p[1] for p in pairs])
    pr = stats.pearsonr(xs, ys)
    ci = pr.confidence_interval(1 - alpha) if len(xs) > 3 else None
    sr = stats.spearmanr(xs, ys)
    return {"n": len(xs),
            "pearson_r": float(pr.statistic), "pearson_p": float(pr.pvalue),
            "pearson_ci": [float(ci.low), float(ci.high)] if ci is not None else None,
            "spearman_r": float(sr.statistic), "spearman_p": float(sr.pvalue)}


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
        "correlation": correlation(xs, ys, alpha),
        "points": {"x": xs.tolist(), "y": ys.tolist()},
        "line": {"x": grid.tolist(), "y": fit.tolist(),
                 "low": (fit - half).tolist(), "high": (fit + half).tolist()},
    }


def grubbs(values, alpha: float = 0.05) -> dict:
    """Iterative two-sided Grubbs' test: flags at most one point per round, repeats on the rest."""
    x = _clean(values)
    flagged = []
    rest = list(x)
    while len(rest) >= 3:
        arr = np.asarray(rest)
        sd = arr.std(ddof=1)
        if sd == 0:
            break
        dev = np.abs(arr - arr.mean())
        i = int(np.argmax(dev))
        G = dev[i] / sd
        n = len(arr)
        t = stats.t.ppf(1 - alpha / (2 * n), n - 2)
        g_crit = (n - 1) / math.sqrt(n) * math.sqrt(t ** 2 / (n - 2 + t ** 2))
        if G <= g_crit:
            break
        flagged.append({"value": float(arr[i]), "G": float(G), "critical": float(g_crit)})
        rest.pop(i)
    return {"outliers": flagged, "n": int(len(x)), "alpha": alpha}


def area_under_curve(x, y, baseline: float = 0.0) -> dict:
    """Trapezoid area under the curve of mean Y at each X (X sorted), relative to a baseline."""
    pts = {}
    for vx, vy in zip(x, y):
        pts.setdefault(float(vx), []).append(float(vy))
    xs = np.array(sorted(pts))
    if len(xs) < 2:
        raise ValueError("Area under the curve needs at least 2 different X values.")
    ys = np.array([np.mean(pts[v]) for v in xs]) - baseline
    seg = (ys[:-1] + ys[1:]) / 2 * np.diff(xs)
    # split segments that cross the baseline so positive and negative areas are exact
    pos = neg = 0.0
    for x0, x1, y0, y1 in zip(xs[:-1], xs[1:], ys[:-1], ys[1:]):
        if y0 >= 0 and y1 >= 0:
            pos += (y0 + y1) / 2 * (x1 - x0)
        elif y0 <= 0 and y1 <= 0:
            neg += (y0 + y1) / 2 * (x1 - x0)
        else:
            xc = x0 + (x1 - x0) * y0 / (y0 - y1)
            a0, a1 = y0 / 2 * (xc - x0), y1 / 2 * (x1 - xc)
            pos += max(a0, 0) + max(a1, 0)
            neg += min(a0, 0) + min(a1, 0)
    peak = int(np.argmax(ys))
    return {"total": float(seg.sum()), "positive": float(pos), "negative": float(neg), "baseline": baseline,
            "x_range": [float(xs[0]), float(xs[-1])], "peak_x": float(xs[peak]), "peak_y": float(ys[peak] + baseline),
            "n_x": int(len(xs))}


def column_stats(values, name: str = "", hypothetical: float | None = None, alpha: float = 0.05) -> dict:
    """Prism-style column statistics for one column, plus optional one-sample tests."""
    x = _clean(values)
    n = len(x)
    if n < 1:
        raise ValueError("No values.")
    d = describe(x, name)
    q1, q3 = (np.percentile(x, [25, 75], method="weibull") if n >= 2 else (x[0], x[0]))
    d.update(q1=float(q1), q3=float(q3), iqr=float(q3 - q1), range=float(np.ptp(x)), sum=float(x.sum()),
             cv=float(100 * d["sd"] / d["mean"]) if n > 1 and d["mean"] != 0 else None)
    if n > 1:
        tq = stats.t.ppf(1 - alpha / 2, n - 1)
        d["ci_low"], d["ci_high"] = d["mean"] - tq * d["sem"], d["mean"] + tq * d["sem"]
    if np.all(x > 0):
        lx = np.log(x)
        d["geo_mean"] = float(np.exp(lx.mean()))
        d["geo_sd_factor"] = float(np.exp(lx.std(ddof=1))) if n > 1 else None
    if n >= 3 and np.ptp(x) > 0:
        d["skewness"] = float(stats.skew(x, bias=False))
        d["kurtosis"] = float(stats.kurtosis(x, bias=False)) if n >= 4 else None
        d["shapiro"] = normality(x)
        if n >= 8:
            dp = stats.normaltest(x)
            d["dagostino"] = {"K2": float(dp.statistic), "p": float(dp.pvalue), "normal": bool(dp.pvalue >= 0.05)}
    if hypothetical is not None and n >= 2:
        t = stats.ttest_1samp(x, hypothetical)
        d["one_sample_t"] = {"hypothetical": hypothetical, "t": float(t.statistic), "df": n - 1, "p": float(t.pvalue),
                             "stars": stars(float(t.pvalue)), "diff": d["mean"] - hypothetical}
        diffs = x - hypothetical
        if np.any(diffs != 0):
            w = stats.wilcoxon(diffs)
            d["wilcoxon"] = {"hypothetical": hypothetical, "W": float(w.statistic), "p": float(w.pvalue),
                             "stars": stars(float(w.pvalue)), "diff": float(np.median(x) - hypothetical)}
    return d


def _synthetic(mean: float, sd: float, n: int) -> np.ndarray:
    """n values with exactly this mean and SD. Parametric tests depend only on the mean, variance
    and n of each group, so running them on these values reproduces the summary-data result exactly."""
    if n == 1:
        return np.array([mean], float)
    z = np.linspace(-1, 1, n)
    z = (z - z.mean()) / z.std(ddof=1)
    return mean + sd * z


def compare_summary(groups, kind: str = "welch", alpha: float = 0.05, err: str = "sd") -> dict:
    """Compare groups given as {name, mean, sd (or sem), n}. Only tests that are exact from
    summary statistics are allowed: unpaired/Welch t test, ordinary/Welch one-way ANOVA."""
    clean = []
    for g in groups:
        try:
            m, s_, n = float(g["mean"]), float(g["sd"]), int(round(float(g["n"])))
        except (TypeError, ValueError, KeyError):
            continue
        if n < 2 or s_ < 0 or not (math.isfinite(m) and math.isfinite(s_)):
            raise ValueError(f"{g.get('name') or 'A group'}: n must be at least 2 and SD can't be negative.")
        sd = s_ * math.sqrt(n) if err == "sem" else s_
        clean.append((str(g.get("name") or f"Group {len(clean) + 1}"), m, sd, n))
    if len(clean) < 2:
        raise ValueError("Enter a mean, SD and n for at least 2 groups (one group per row).")
    data = [_synthetic(m, sd, n) for _, m, sd, n in clean]
    names = [c[0] for c in clean]
    if len(clean) == 2:
        k = kind if kind in ("welch", "unpaired") else "welch"
        res = t_test(data[0], data[1], kind=k, name_a=names[0], name_b=names[1], alpha=alpha)
    else:
        k = kind if kind in ("ordinary", "welch") else "ordinary"
        res = one_way_anova(data, names, kind=k, alpha=alpha)
        res.pop("variance_check", None)  # Brown-Forsythe needs the raw values
    res.pop("normality", None)
    res.pop("normality_of", None)
    for g in res["groups"]:
        for key in ("median", "min", "max"):
            g[key] = None
    res["n_groups"] = len(clean)
    res["summary_data"] = True
    return res


def _nice_width(w: float) -> float:
    """Round a bin width to 1, 2, 2.5 or 5 × 10^k so bin edges are readable."""
    if not w > 0 or not math.isfinite(w):
        return 1.0
    e = 10 ** math.floor(math.log10(w))
    for m in (1, 2, 2.5, 5, 10):
        if w <= m * e * 1.0000001:
            return m * e
    return 10 * e


def _qq(x: np.ndarray) -> dict:
    """Normal Q-Q data. Plotting positions as R's qqnorm (ppoints): (i − a)/(n + 1 − 2a), a = 3/8 if n ≤ 10 else 1/2.
    'predicted' is the value expected from a normal distribution with the sample's mean and SD."""
    n = len(x)
    a = 0.375 if n <= 10 else 0.5
    p = (np.arange(1, n + 1) - a) / (n + 1 - 2 * a)
    z = stats.norm.ppf(p)
    xs = np.sort(x)
    m, sd = float(np.mean(x)), float(np.std(x, ddof=1)) if n > 1 else 0.0
    return {"z": z.tolist(), "actual": xs.tolist(), "predicted": (m + sd * z).tolist()}


def frequency_distribution(groups, names, bin_width=None, bin_start=None, y: str = "count",
                           cumulative: bool = False) -> dict:
    """Histogram counts on shared bins for every column (Prism's 'Frequency distribution'), plus
    normal Q-Q data and normality tests per column. Bins are [start, end): a value on an edge goes
    into the higher bin. y = count | percent | fraction. Default bin width: Freedman-Diaconis
    (2·IQR·n^−1/3 on all values), rounded to a readable number."""
    cols = [(nm, _clean(g)) for nm, g in zip(names, groups)]
    cols = [(nm, x) for nm, x in cols if len(x)]
    if not cols:
        raise ValueError("Enter values in at least one column.")
    if y not in ("count", "percent", "fraction"):
        raise ValueError("Unknown Y choice.")
    allx = np.concatenate([x for _, x in cols])
    lo, hi = float(allx.min()), float(allx.max())
    if bin_width is not None:
        h = float(bin_width)
        if not h > 0:
            raise ValueError("Bin width must be greater than 0.")
        auto = False
    else:
        n = len(allx)
        q1, q3 = np.percentile(allx, [25, 75])
        h = 2 * (q3 - q1) / n ** (1 / 3) if q3 > q1 else (hi - lo) / (1 + math.log2(n)) if hi > lo else 1.0
        h = _nice_width(h)
        auto = True
    start = float(bin_start) if bin_start is not None else math.floor(lo / h + 1e-9) * h
    if start > lo:
        raise ValueError(f"The first bin starts at {start:g}, above the smallest value ({lo:g}). Choose a lower start.")
    nb = int(math.floor((hi - start) / h + 1e-9)) + 1
    if nb > 500:
        raise ValueError(f"That bin width makes {nb} bins. Choose a wider bin (the data range is {lo:g} to {hi:g}).")
    edges = start + h * np.arange(nb + 1)
    out = []
    for nm, x in cols:
        idx = np.floor((x - start) / h + 1e-9).astype(int)
        counts = np.bincount(np.clip(idx, 0, nb - 1), minlength=nb).astype(float)
        vals = np.cumsum(counts) if cumulative else counts.copy()
        if y == "percent":
            vals = vals / len(x) * 100
        elif y == "fraction":
            vals = vals / len(x)
        sw = normality(x)
        dag = None
        if len(x) >= 8:
            k2, p = stats.normaltest(x)
            dag = {"k2": float(k2), "p": float(p), "normal": bool(p >= 0.05)}
        out.append({"name": nm, "n": int(len(x)), "counts": counts.astype(int).tolist(), "values": vals.tolist(),
                    "mean": float(np.mean(x)), "sd": float(np.std(x, ddof=1)) if len(x) > 1 else None,
                    "median": float(np.median(x)), "min": float(x.min()), "max": float(x.max()),
                    "skewness": float(stats.skew(x, bias=False)) if len(x) >= 3 else None,
                    "shapiro": sw, "dagostino": dag, "qq": _qq(x)})
    return {"kind": "freq", "test_name": "Frequency distribution", "bin_width": h, "bin_start": start, "auto_width": auto,
            "edges": edges.tolist(), "centers": ((edges[:-1] + edges[1:]) / 2).tolist(), "y": y, "cumulative": cumulative,
            "groups": out, "n_groups": len(out)}
