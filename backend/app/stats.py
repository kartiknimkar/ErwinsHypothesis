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


def _mw_null_cdf(m: int, n: int) -> np.ndarray:
    """Exact null CDF of the Mann-Whitney U statistic (no ties), index = u."""
    # f[j][u]: ways to get U = u with i values from sample 1 and j from sample 2 (built up over i)
    f = [np.zeros(m * n + 1) for _ in range(n + 1)]
    for j in range(n + 1):
        f[j][0] = 1.0
    for i in range(1, m + 1):
        g = [np.zeros(m * n + 1) for _ in range(n + 1)]
        g[0][0] = 1.0
        for j in range(1, n + 1):
            g[j] = g[j - 1].copy()
            g[j][j:] += f[j][:-j] if j else f[j]
        f = g
    counts = f[n]
    return np.cumsum(counts) / counts.sum()


def _signed_rank_null_cdf(n: int) -> np.ndarray:
    """Exact null CDF of the Wilcoxon signed-rank statistic T+ (no ties), index = t."""
    M = n * (n + 1) // 2
    c = np.zeros(M + 1); c[0] = 1.0
    for k in range(1, n + 1):
        c[k:] = c[k:] + c[:-k].copy()
    return np.cumsum(c) / c.sum()


def hodges_lehmann(a, b=None, alpha: float = 0.05) -> dict:
    """Hodges-Lehmann estimate and CI. Two samples: median of all differences b − a (Mann-Whitney based CI);
    one sample (paired differences in a): median of Walsh averages (signed-rank based CI). Exact for small samples,
    normal approximation otherwise."""
    z = stats.norm.ppf(1 - alpha / 2)
    if b is not None:
        x, y = np.asarray(a, float), np.asarray(b, float)
        m, n = len(x), len(y)
        d = np.sort((y[:, None] - x[None, :]).ravel())
        N = m * n
        if N <= 2500:
            cdf = _mw_null_cdf(m, n)
            c = int(np.sum(cdf <= alpha / 2))  # number of u values with P(U <= u) <= alpha/2  → lower index
        else:
            c = int(math.floor(N / 2 - z * math.sqrt(N * (m + n + 1) / 12)))
    else:
        dd = np.asarray(a, float)
        dd = dd[dd != 0]
        n = len(dd)
        i, j = np.triu_indices(n)
        d = np.sort((dd[i] + dd[j]) / 2)
        N = len(d)
        if n <= 60:
            cdf = _signed_rank_null_cdf(n)
            c = int(np.sum(cdf <= alpha / 2))
        else:
            c = int(math.floor(N / 2 - z * math.sqrt(n * (n + 1) * (2 * n + 1) / 24)))
    est = float(np.median(d))
    if c < 1:
        return {"estimate": est, "ci": None}
    return {"estimate": est, "ci": [float(d[c - 1]), float(d[N - c])]}


def _effect_two(kind, xa, xb, res) -> dict | None:
    """Effect sizes for two-group comparisons (difference is B − A)."""
    n1, n2 = len(xa), len(xb)
    out = {}
    if kind in ("unpaired", "welch"):
        sp = math.sqrt(((n1 - 1) * np.var(xa, ddof=1) + (n2 - 1) * np.var(xb, ddof=1)) / (n1 + n2 - 2))
        if sp > 0:
            d = (np.mean(xb) - np.mean(xa)) / sp
            j = 1 - 3 / (4 * (n1 + n2) - 9)
            se = math.sqrt((n1 + n2) / (n1 * n2) + d * d / (2 * (n1 + n2)))
            out.update(cohens_d=float(d), hedges_g=float(d * j), d_ci=[float(d - 1.96 * se), float(d + 1.96 * se)])
    elif kind in ("paired", "ratio_paired"):
        diff = (np.log10(xb) - np.log10(xa)) if kind == "ratio_paired" else (xb - xa)
        sd = np.std(diff, ddof=1)
        if sd > 0:
            out["cohens_dz"] = float(np.mean(diff) / sd)
    elif kind == "mannwhitney":
        out["rank_biserial"] = float(1 - 2 * res["statistic"] / (n1 * n2)) * (1 if np.median(xb) >= np.median(xa) else -1)
    if res.get("statistic_name") == "t" and res.get("df"):
        t, df = res["statistic"], res["df"]
        out["r_squared"] = float(t * t / (t * t + df))
    return out or None


def t_test(a, b, kind: str = "unpaired", name_a: str = "A", name_b: str = "B",
           alpha: float = 0.05) -> dict:
    """Compare two groups.

    kind: "unpaired" (Student, equal variances), "welch" (unequal variances),
          "paired", or "mannwhitney" (nonparametric, unpaired).
    The difference is reported as mean(B) - mean(A).
    """
    raw_a, raw_b = list(a), list(b)
    if kind in ("paired", "wilcoxon", "ratio_paired"):
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
    elif kind == "ratio_paired":
        if np.any(xa <= 0) or np.any(xb <= 0):
            raise ValueError("The ratio paired t test needs all values greater than 0 (it works on logarithms).")
        la, lb = np.log10(xa), np.log10(xb)
        r = stats.ttest_rel(lb, la)
        ci = r.confidence_interval(conf)
        result.update(
            test_name="Ratio paired t test",
            statistic_name="t",
            statistic=abs(float(r.statistic)),
            df=float(r.df),
            p=float(r.pvalue),
            difference=float(10 ** np.mean(lb - la)),
            difference_label=f"Geometric mean of ratios ({name_b} / {name_a})",
            ci_low=float(10 ** ci.low),
            ci_high=float(10 ** ci.high),
            n_pairs=len(la),
        )
    elif kind == "ks":
        r = stats.ks_2samp(xb, xa)
        result.update(
            test_name="Kolmogorov-Smirnov test",
            statistic_name="D",
            statistic=float(r.statistic),
            df=None,
            p=float(r.pvalue),
            difference=float(np.median(xb) - np.median(xa)),
            difference_label=f"Median of {name_b} − median of {name_a}",
            ci_low=None,
            ci_high=None,
        )
    elif kind == "wilcoxon":
        diffs = xb - xa
        if np.all(diffs == 0):
            raise ValueError("All differences are zero, so there's nothing to test.")
        r = stats.wilcoxon(diffs)
        result.update(
            hodges_lehmann=hodges_lehmann(diffs, None, alpha),
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
        hl = hodges_lehmann(xa, xb, alpha)
        result["hodges_lehmann"] = hl
    else:
        raise ValueError(f"Unknown test type: {kind}")

    result["stars"] = stars(result["p"])
    result["significant"] = result["p"] < alpha
    result["effect"] = _effect_two(kind, xa, xb, result)
    if kind in ("paired", "wilcoxon"):
        result["normality"] = [normality(xb - xa)]
        result["normality_of"] = "differences"
    elif kind == "ratio_paired":
        result["normality"] = [normality(np.log10(xb) - np.log10(xa))]
        result["normality_of"] = "log ratios"
    else:
        result["normality"] = [normality(xa), normality(xb)]
        result["normality_of"] = "groups"
    return result


def normality(values) -> dict | None:
    """Shapiro-Wilk normality test (needs 3+ values)."""
    x = _clean(values)
    if len(x) < 3 or np.ptp(x) == 0:
        return None
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # SciPy warns that P is approximate above n = 5000
        r = stats.shapiro(x)
    return {"W": float(r.statistic), "p": float(r.pvalue), "normal": bool(r.pvalue >= 0.05)}


def anderson_darling(values) -> dict | None:
    """Anderson-Darling normality test; P value from D'Agostino & Stephens (1986), modified statistic A²*."""
    x = np.sort(_clean(values))
    n = len(x)
    if n < 8 or np.ptp(x) == 0:
        return None
    z = (x - x.mean()) / x.std(ddof=1)
    lcdf, lsf = stats.norm.logcdf(z), stats.norm.logsf(z)
    i = np.arange(1, n + 1)
    a2 = float(-n - np.sum((2 * i - 1) * (lcdf + lsf[::-1])) / n)
    a = a2 * (1 + 0.75 / n + 2.25 / n ** 2)
    if a >= 0.6:
        p = math.exp(1.2937 - 5.709 * a + 0.0186 * a * a)
    elif a >= 0.34:
        p = math.exp(0.9177 - 4.279 * a - 1.38 * a * a)
    elif a >= 0.2:
        p = 1 - math.exp(-8.318 + 42.796 * a - 59.938 * a * a)
    else:
        p = 1 - math.exp(-13.436 + 101.14 * a - 223.73 * a * a)
    p = min(1.0, max(0.0, p))
    return {"A2": a2, "p": p, "normal": bool(p >= 0.05)}


def ks_normality(values) -> dict | None:
    """Kolmogorov-Smirnov normality test with mean and SD estimated from the data (Lilliefors), P value by the
    Dallal-Wilkinson approximation, as Prism reports it ('P > 0.10' when the approximation exceeds 0.1)."""
    x = np.sort(_clean(values))
    n = len(x)
    if n < 5 or np.ptp(x) == 0:
        return None
    cdf = stats.norm.cdf((x - x.mean()) / x.std(ddof=1))
    i = np.arange(1, n + 1)
    D = float(max(np.max(i / n - cdf), np.max(cdf - (i - 1) / n)))
    kd, nd = (D, n) if n <= 100 else (D * (n / 100) ** 0.49, 100)
    p = math.exp(-7.01256 * kd ** 2 * (nd + 2.78019) + 2.99587 * kd * math.sqrt(nd + 2.78019) - 0.122119
                 + 0.974598 / math.sqrt(nd) + 1.67997 / nd)
    over = p > 0.1
    return {"D": D, "p": min(p, 1.0), "p_over_010": bool(over), "normal": bool(over or p >= 0.05)}


def _pairs(k: int):
    return [(i, j) for i in range(k) for j in range(i + 1, k)]


POSTHOC_NAMES = {"tukey": "Tukey's", "dunnett": "Dunnett's", "bonferroni": "Bonferroni's", "sidak": "Šídák's",
                 "holm": "Holm-Šídák", "lsd": "Fisher's LSD (uncorrected)"}


def _smm_cdf(c: float, m: int, df: float) -> float:
    """CDF of the studentized maximum modulus: P(max_i |Z_i| / S <= c) for m independent standard normals and
    S = sqrt(chi²_df / df). Used by Dunnett's T3."""
    from scipy import integrate
    if c <= 0:
        return 0.0
    if df > 1e5:
        return float((2 * stats.norm.cdf(c) - 1) ** m)
    logc = 0.5 * df * math.log(df) - (0.5 * df - 1) * math.log(2) - math.lgamma(0.5 * df)
    dens = lambda s_: math.exp(logc + (df - 1) * math.log(s_) - 0.5 * df * s_ * s_) if s_ > 0 else 0.0
    f = lambda s_: (2 * stats.norm.cdf(c * s_) - 1) ** m * dens(s_)
    peak = math.sqrt((df - 1) / df) if df > 1 else 0.5
    val = integrate.quad(f, 0, peak, limit=200)[0] + integrate.quad(f, peak, np.inf, limit=200)[0]
    return float(min(1.0, max(0.0, val)))


def _smm_ppf(q: float, m: int, df: float) -> float:
    from scipy import optimize as _opt
    return float(_opt.brentq(lambda c: _smm_cdf(c, m, df) - q, 1e-6, 100))


def _adjust(praw, method: str):
    """Multiplicity-adjusted P values for a family of m tests."""
    p = np.asarray(praw, float)
    m = len(p)
    if method == "bonferroni":
        return np.minimum(1, p * m)
    if method == "sidak":
        return 1 - (1 - p) ** m
    if method == "holm":  # Holm-Šídák step-down
        order = np.argsort(p)
        adj = np.empty(m)
        run = 0.0
        for rank, idx in enumerate(order):
            run = max(run, 1 - (1 - p[idx]) ** (m - rank))
            adj[idx] = min(1.0, run)
        return adj
    return p  # lsd: no correction


def _pairwise_pooled(xs, names, pairs, msw, dfw, method, alpha):
    """t tests using the pooled within-group variance (MS residual), then a multiplicity correction."""
    ns = [len(x) for x in xs]
    means = [x.mean() for x in xs]
    m = len(pairs)
    rows, praw = [], []
    for i, j in pairs:
        se = math.sqrt(msw * (1 / ns[i] + 1 / ns[j]))
        d = float(means[i] - means[j])
        t = d / se
        praw.append(2 * stats.t.sf(abs(t), dfw))
        rows.append((i, j, d, se, t))
    padj = _adjust(praw, method)
    a_ci = {"bonferroni": alpha / m, "sidak": 1 - (1 - alpha) ** (1 / m), "lsd": alpha}.get(method)
    tcrit = float(stats.t.ppf(1 - a_ci / 2, dfw)) if a_ci else None
    return [{"a": names[i], "b": names[j], "i": i, "j": j, "diff": d, "t": float(t), "p_raw": float(pr),
             "ci_low": d - tcrit * se if tcrit else None, "ci_high": d + tcrit * se if tcrit else None, "p": float(pa)}
            for (i, j, d, se, t), pr, pa in zip(rows, praw, padj)]


def one_way_anova(groups, names=None, kind: str = "ordinary", alpha: float = 0.05,
                  posthoc: str = "tukey", compare_to: str = "all") -> dict:
    """Compare 3+ groups.

    posthoc (ordinary ANOVA): tukey | dunnett | bonferroni | sidak | holm | lsd.
    compare_to: "all" pairs, or "control" (every group vs the first column). Tukey implies all pairs and
    Dunnett implies vs control. Kruskal-Wallis uses Dunn's test for either family.

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
        if posthoc == "tukey":
            compare_to = "all"
        if posthoc == "dunnett":
            compare_to = "control"
        res["effect"] = {"eta_squared": ssb / (ssb + ssw), "omega_squared": max(0.0, (ssb - dfb * msw) / (ssb + ssw + msw))}
        # post test for linear trend: do the means rise or fall steadily with column order?
        sc = np.arange(1, k + 1, dtype=float)
        sbar = np.sum(ns * sc) / N
        c = sc - sbar
        ss_lin = float(np.sum(ns * c * means) ** 2 / np.sum(ns * c * c))
        slope = float(np.sum(ns * c * means) / np.sum(ns * c * c))
        f_lin = ss_lin / msw if msw > 0 else float("inf")
        ss_nl = max(0.0, ssb - ss_lin)
        f_nl = (ss_nl / (k - 2)) / msw if msw > 0 and k > 2 else None
        res["trend"] = {"slope": slope, "F": f_lin, "df": [1, dfw], "p": float(stats.f.sf(f_lin, 1, dfw)),
                        "r_squared": ss_lin / (ssb + ssw) if ssb + ssw > 0 else None,
                        "nonlinear_F": f_nl, "nonlinear_df": [k - 2, dfw] if k > 2 else None,
                        "nonlinear_p": float(stats.f.sf(f_nl, k - 2, dfw)) if f_nl is not None else None}
        res.update(test_name="Ordinary one-way ANOVA", posthoc_name=f"{POSTHOC_NAMES.get(posthoc, posthoc)} multiple comparisons" + (" vs control" if compare_to == "control" else ""),
                   F=F, df_between=dfb, df_within=dfw, p=p, r_squared=ssb / (ssb + ssw),
                   table=[{"source": "Between groups", "SS": ssb, "df": dfb, "MS": msb},
                          {"source": "Within groups (residual)", "SS": ssw, "df": dfw, "MS": msw},
                          {"source": "Total", "SS": ssb + ssw, "df": int(N - 1), "MS": None}])
        pairs = _pairs(k) if compare_to != "control" else [(0, j) for j in range(1, k)]
        if posthoc == "tukey":
            tk = stats.tukey_hsd(*xs)
            ci = tk.confidence_interval(conf)
            for i, j in pairs:
                comps.append({"a": names[i], "b": names[j], "i": i, "j": j, "diff": float(tk.statistic[i, j]),
                              "ci_low": float(ci.low[i, j]), "ci_high": float(ci.high[i, j]),
                              "p": float(tk.pvalue[i, j])})
        elif posthoc == "dunnett":
            # multivariate-t integration is randomized in SciPy: a fixed seed makes results reproducible
            dn = stats.dunnett(*xs[1:], control=xs[0], rng=np.random.default_rng(12345))
            dci = dn.confidence_interval(conf)
            for n_, (i, j) in enumerate(pairs):
                # scipy reports treatment − control; we report first − second (control − treatment)
                comps.append({"a": names[i], "b": names[j], "i": i, "j": j, "diff": float(means[i] - means[j]),
                              "ci_low": -float(dci.high[n_]), "ci_high": -float(dci.low[n_]), "p": float(dn.pvalue[n_])})
        elif posthoc in ("bonferroni", "sidak", "holm", "lsd"):
            comps = _pairwise_pooled(xs, names, pairs, msw, dfw, posthoc, alpha)
        else:
            raise ValueError(f"Unknown multiple comparison method: {posthoc}")
        res["posthoc"], res["compare_to"] = posthoc, compare_to
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
        t3 = posthoc == "t3"
        pairs = _pairs(k) if compare_to != "control" else [(0, j) for j in range(1, k)]
        if not t3 and compare_to == "control":
            pairs = _pairs(k)  # Games-Howell is defined for all pairs
        res.update(test_name="Welch's ANOVA", posthoc_name=("Dunnett's T3 multiple comparisons" + (" vs control" if compare_to == "control" else "")) if t3 else "Games-Howell multiple comparisons",
                   F=F, df_between=k - 1, df_within=df2, p=p, posthoc="t3" if t3 else "games_howell", compare_to=compare_to if t3 else "all")
        for i, j in (pairs if t3 else []):
            vi, vj = vars_[i] / ns[i], vars_[j] / ns[j]
            se = math.sqrt(vi + vj)
            df = (vi + vj) ** 2 / (vi ** 2 / (ns[i] - 1) + vj ** 2 / (ns[j] - 1))
            diff = float(means[i] - means[j])
            m_ = len(pairs)
            crit = _smm_ppf(conf, m_, df)
            comps.append({"a": names[i], "b": names[j], "i": i, "j": j, "diff": diff, "t": diff / se, "df": float(df),
                          "ci_low": diff - crit * se, "ci_high": diff + crit * se,
                          "p": float(1 - _smm_cdf(abs(diff) / se, m_, df))})
        for i, j in ([] if t3 else _pairs(k)):
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
        res["effect"] = {"epsilon_squared": float(kw.statistic) / (N - 1)}
        allv = np.concatenate(xs)
        ranks = stats.rankdata(allv)
        _, counts = np.unique(allv, return_counts=True)
        tie = np.sum(counts ** 3 - counts) / (12 * (N - 1))
        bounds = np.cumsum([0] + [len(x) for x in xs])
        mean_ranks = [ranks[bounds[g]:bounds[g + 1]].mean() for g in range(k)]
        pairs = _pairs(k) if compare_to != "control" else [(0, j) for j in range(1, k)]
        m = len(pairs)
        if compare_to == "control":
            res["posthoc_name"] = "Dunn's multiple comparisons vs control"
        res["compare_to"] = compare_to
        for i, j in pairs:
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


def linear_regression(x, y, alpha: float = 0.05, band_points: int = 100, origin: bool = False) -> dict:
    """Simple least-squares linear regression of y on x, with confidence and prediction bands.
    origin=True forces the line through (0, 0) (no intercept)."""
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
    if origin:
        return _regression_origin(xs, ys, alpha, band_points)
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
    phalf = tcrit * sy_x * np.sqrt(1 + 1 / n + (grid - x_mean) ** 2 / sxx)

    x_intercept = -r.intercept / r.slope if r.slope != 0 else None
    p = float(r.pvalue)
    return {
        "test_name": "Simple linear regression",
        "n": n,
        "residuals": {"x": xs.tolist(), "y": resid.tolist()},
        "runs_test": runs_test(xs, resid),
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
                 "low": (fit - half).tolist(), "high": (fit + half).tolist(),
                 "pred_low": (fit - phalf).tolist(), "pred_high": (fit + phalf).tolist()},
    }


def _regression_origin(xs, ys, alpha, band_points):
    """Least squares line constrained through the origin: Y = slope·X."""
    n = len(xs)
    sxx0 = float(np.sum(xs * xs))
    if sxx0 == 0:
        raise ValueError("All X values are 0.")
    slope = float(np.sum(xs * ys) / sxx0)
    df = n - 1
    resid = ys - slope * xs
    ss_res = float(np.sum(resid ** 2))
    sy_x = math.sqrt(ss_res / df)
    se = sy_x / math.sqrt(sxx0)
    tcrit = stats.t.ppf(1 - alpha / 2, df)
    t = slope / se if se > 0 else float("inf")
    p = float(2 * stats.t.sf(abs(t), df))
    ss_tot = float(np.sum((ys - ys.mean()) ** 2))
    grid = np.linspace(min(0.0, xs.min()), xs.max(), band_points)
    fit = slope * grid
    half = tcrit * sy_x * np.abs(grid) / math.sqrt(sxx0)
    phalf = tcrit * sy_x * np.sqrt(1 + grid ** 2 / sxx0)
    return {
        "test_name": "Linear regression through the origin", "origin": True, "n": n,
        "residuals": {"x": xs.tolist(), "y": resid.tolist()}, "runs_test": runs_test(xs, resid),
        "slope": slope, "slope_se": se, "slope_ci": [slope - tcrit * se, slope + tcrit * se],
        "intercept": 0.0, "intercept_se": None, "intercept_ci": None, "x_intercept": 0.0,
        "r": None, "r_squared": 1 - ss_res / ss_tot if ss_tot > 0 else None, "sy_x": sy_x, "df": df,
        "F": t * t, "p": p, "stars": stars(p), "significant": p < alpha, "alpha": alpha,
        "equation": f"Y = {slope:.4g}·X", "correlation": correlation(xs, ys, alpha),
        "points": {"x": xs.tolist(), "y": ys.tolist()},
        "line": {"x": grid.tolist(), "y": fit.tolist(), "low": (fit - half).tolist(), "high": (fit + half).tolist(),
                 "pred_low": (fit - phalf).tolist(), "pred_high": (fit + phalf).tolist()},
    }


def _runs_cdf(r: int, n1: int, n2: int) -> float:
    """Exact P(number of runs <= r) for n1 positives and n2 negatives in random order."""
    total = math.comb(n1 + n2, n1)
    p = 0
    for runs in range(2, r + 1):
        k = runs // 2
        if runs % 2 == 0:
            p += 2 * math.comb(n1 - 1, k - 1) * math.comb(n2 - 1, k - 1)
        else:
            p += math.comb(n1 - 1, k - 1) * math.comb(n2 - 1, k) + math.comb(n1 - 1, k) * math.comb(n2 - 1, k - 1)
    return p / total


def runs_test(x, resid) -> dict | None:
    """Runs test: do the points sit on the curve in long runs on one side (the model doesn't fit the shape)?
    Residuals are averaged at each X (replicates), ordered by X; zeros are skipped. One-tailed P for too few runs."""
    x, resid = np.asarray(x, float), np.asarray(resid, float)
    xs = np.unique(x)
    m = np.array([resid[x == v].mean() for v in xs])
    sign = np.sign(m[np.abs(m) > 1e-12 * max(1.0, float(np.max(np.abs(m))) if len(m) else 1.0)])
    n1, n2 = int(np.sum(sign > 0)), int(np.sum(sign < 0))
    if n1 == 0 or n2 == 0:
        return None
    runs = 1 + int(np.sum(sign[1:] != sign[:-1]))
    n = n1 + n2
    expected = 2 * n1 * n2 / n + 1
    p = _runs_cdf(runs, n1, n2)
    return {"runs": runs, "expected": float(expected), "n_points": n, "p": float(min(1.0, p)), "deviates": bool(p < 0.05)}


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
    if n >= 2:
        # CI of the median from order statistics (exact binomial): largest j with P(Bin(n, 1/2) <= j - 1) <= alpha/2
        xs = np.sort(x)
        j = 0
        while j + 1 <= n and stats.binom.cdf(j, n, 0.5) <= alpha / 2:
            j += 1
        if j >= 1:
            d["median_ci"] = [float(xs[j - 1]), float(xs[n - j])]
            d["median_ci_conf"] = float(1 - 2 * stats.binom.cdf(j - 1, n, 0.5))
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
        d["anderson"] = anderson_darling(x)
        d["ks"] = ks_normality(x)
    if hypothetical is not None and n >= 2:
        t = stats.ttest_1samp(x, hypothetical)
        d["one_sample_t"] = {"hypothetical": hypothetical, "t": float(t.statistic), "df": n - 1, "p": float(t.pvalue),
                             "stars": stars(float(t.pvalue)), "diff": d["mean"] - hypothetical}
        diffs = x - hypothetical
        above, below = int(np.sum(diffs > 0)), int(np.sum(diffs < 0))
        if above + below:
            sp = float(stats.binomtest(above, above + below, 0.5).pvalue)
            d["sign_test"] = {"above": above, "below": below, "p": sp, "stars": stars(sp)}
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


def compare_summary(groups, kind: str = "welch", alpha: float = 0.05, err: str = "sd",
                    posthoc: str = "tukey", compare_to: str = "all") -> dict:
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
        res = one_way_anova(data, names, kind=k, alpha=alpha, posthoc=posthoc if k == "ordinary" else "tukey", compare_to=compare_to)
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
