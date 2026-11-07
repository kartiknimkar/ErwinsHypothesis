"""Two-way ANOVA and repeated-measures designs.

two_way: general linear model with sum-to-zero coding and Type III sums of squares
(handles unequal group sizes); multiple comparisons within each row.
repeated_measures: one-way RM ANOVA with Geisser-Greenhouse correction, Friedman test.
"""
from __future__ import annotations

import itertools
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


def _family(pairs_by_group, k, ms_res, df_res, alpha):
    """pairs_by_group: [(label, [(name_a, name_b, diff, se, meta), ...])]. With 2 levels (one pair per group)
    Šídák corrects across all groups; with 3+ levels Tukey corrects within each group."""
    conf = 1 - alpha
    out = []
    if k == 2:
        m = len(pairs_by_group)
        tcrit = stats.t.ppf(1 - (1 - conf ** (1 / m)) / 2, df_res)
    else:
        qcrit = stats.studentized_range.ppf(conf, k, df_res)
    for label, pairs in pairs_by_group:
        for na, nb, diff, se, meta in pairs:
            if k == 2:
                p = 1 - (1 - 2 * stats.t.sf(abs(diff) / se, df_res)) ** m
                half = tcrit * se
            else:
                p = float(stats.studentized_range.sf(abs(diff) / (se / math.sqrt(2)), k, df_res))
                half = qcrit * se / math.sqrt(2)
            p = float(min(1.0, max(0.0, p)))
            out.append({"row": label, "a": na, "b": nb, "diff": float(diff), "ci_low": float(diff - half), "ci_high": float(diff + half),
                        "p": p, "stars": stars(p), "significant": p < alpha, **meta})
    return out


def _two_way_comparisons(compare, rows, names, mean, counts, ms_res, df_res, alpha):
    """compare: within_rows (columns compared at each row: simple effects), within_cols (rows compared in each
    column), col_means / row_means (main effects, using unweighted marginal means as Prism does)."""
    a, b = len(rows), len(names)
    tk = lambda k: "Šídák's" if k == 2 else "Tukey's"
    if compare == "within_cols":
        fam = [(names[j], [(rows[i1], rows[i2], mean[(i1, j)] - mean[(i2, j)], math.sqrt(ms_res * (1 / counts[i1, j] + 1 / counts[i2, j])),
                            {"kind": "within_cols", "j": j, "i1": i1, "i2": i2}) for i1 in range(a) for i2 in range(i1 + 1, a)]) for j in range(b)]
        return _family(fam, a, ms_res, df_res, alpha), f"{tk(a)} multiple comparisons (rows within each column)"
    if compare == "all_cells":
        cells_ = [(i, j) for i in range(a) for j in range(b)]
        lab = lambda c: f"{rows[c[0]]} · {names[c[1]]}"  # noqa: E731
        fam = [("Every cell", [(lab(c1), lab(c2), mean[c1] - mean[c2], math.sqrt(ms_res * (1 / counts[c1] + 1 / counts[c2])), {"kind": "all_cells"})
                               for x, c1 in enumerate(cells_) for c2 in cells_[x + 1:]])]
        return _family(fam, a * b, ms_res, df_res, alpha), "Tukey's multiple comparisons (every cell mean with every other)"
    if compare == "col_means":
        mm = [np.mean([mean[(i, j)] for i in range(a)]) for j in range(b)]
        fam = [("All rows (main effect)", [(names[j1], names[j2], mm[j1] - mm[j2],
                 math.sqrt(ms_res * sum(1 / counts[i, j1] + 1 / counts[i, j2] for i in range(a))) / a, {"kind": "col_means", "j1": j1, "j2": j2})
                 for j1 in range(b) for j2 in range(j1 + 1, b)])]
        return _family(fam, b, ms_res, df_res, alpha), f"{'Tukey' if b > 2 else 'Main effect'} comparisons of column means (averaged over rows)"
    if compare == "row_means":
        mm = [np.mean([mean[(i, j)] for j in range(b)]) for i in range(a)]
        fam = [("All columns (main effect)", [(rows[i1], rows[i2], mm[i1] - mm[i2],
                 math.sqrt(ms_res * sum(1 / counts[i1, j] + 1 / counts[i2, j] for j in range(b))) / b, {"kind": "row_means", "i1": i1, "i2": i2})
                 for i1 in range(a) for i2 in range(i1 + 1, a)])]
        return _family(fam, a, ms_res, df_res, alpha), f"{'Tukey' if a > 2 else 'Main effect'} comparisons of row means (averaged over columns)"
    fam = [(rows[i], [(names[j1], names[j2], mean[(i, j1)] - mean[(i, j2)], math.sqrt(ms_res * (1 / counts[i, j1] + 1 / counts[i, j2])),
                       {"kind": "within_rows", "i": i, "j1": j1, "j2": j2}) for j1 in range(b) for j2 in range(j1 + 1, b)]) for i in range(a)]
    return _family(fam, b, ms_res, df_res, alpha), f"{tk(b)} multiple comparisons (columns within each row)"


def two_way(row_labels, columns, col_names, alpha: float = 0.05, compare: str = "within_rows") -> dict:
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

    comps, method = _two_way_comparisons(compare, rows, names, mean, counts, ms_res, df_res, alpha)
    inter = table[0]
    return {"test_name": "Two-way ANOVA", "rows": rows, "cols": names, "alpha": alpha,
            "table": table, "cells": cells, "comparisons": comps, "posthoc_name": method, "compare": compare,
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


def _bh(p):
    """Benjamini-Hochberg adjusted P values."""
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, p[i] * m / rank)
        adj[i] = prev
    return adj


def fdr_adjust(p, method: str = "bh", q: float = 0.05):
    """Returns (adjusted P / q values, discovery flags). method: bh | bky (two-stage step-up of Benjamini,
    Krieger & Yekutieli, Prism's default) | holm (Holm-Šídák) | bonferroni | none."""
    from .stats import _adjust
    p = np.asarray(p, float)
    m = len(p)
    if method == "bky":
        qp = q / (1 + q)
        bh = _bh(p)
        r1 = int(np.sum(bh <= qp))
        if r1 in (0, m):
            adj = np.minimum(1, bh * (1 + q))
            return adj, bh <= qp
        m0 = m - r1
        adj = np.minimum(1, bh * m0 / m * (1 + q))
        return adj, bh <= qp * m / m0
    if method in ("holm", "bonferroni", "none"):
        adj = _adjust(p, {"holm": "holm", "bonferroni": "bonferroni", "none": "lsd"}[method])
        return adj, adj < q
    adj = _bh(p)
    return adj, adj < q


def multiple_t(row_labels, col_a, col_b, names=("A", "B"), kind: str = "welch", q: float = 0.05, method: str = "bh") -> dict:
    """One t test per row name (rows sharing a name are replicates), with a multiplicity correction (default BH FDR)."""
    from .stats import t_test
    items = {}
    for lab, a, b in zip(row_labels, col_a, col_b):
        lab = str(lab or "").strip()
        if not lab:
            continue
        d = items.setdefault(lab, ([], []))
        if _num(a) is not None:
            d[0].append(_num(a))
        if _num(b) is not None:
            d[1].append(_num(b))
    results, skipped = [], []
    for lab, (va, vb) in items.items():
        try:
            r = t_test(va, vb, kind=kind, name_a=names[0], name_b=names[1])
        except ValueError:
            skipped.append(lab)
            continue
        ma, mb = r["groups"][0]["mean"], r["groups"][1]["mean"]
        results.append({"name": lab, "mean_a": ma, "mean_b": mb, "diff": mb - ma, "t": r["statistic"], "df": r["df"],
                        "p": r["p"], "n_a": len(va), "n_b": len(vb),
                        "log2fc": math.log2(mb / ma) if ma > 0 and mb > 0 else None})
    if not results:
        raise ValueError("Each row name needs at least 2 values in each of the two columns.")
    adj, disc = fdr_adjust([r["p"] for r in results], method, q)
    for r, a, d in zip(results, adj, disc):
        r["q"] = float(a)
        r["discovery"] = bool(d)
        r["stars"] = stars(r["p"])
    return {"test_name": "Multiple t tests", "kind": kind, "names": list(names), "q_level": q, "items": results, "method": method,
            "skipped": skipped, "n_discoveries": sum(r["discovery"] for r in results), "p": min(r["q"] for r in results)}


def two_way_rm(row_labels, columns, col_names, alpha: float = 0.05) -> dict:
    """Mixed (split-plot) two-way ANOVA: rows = repeated factor (e.g. time) measured on the same
    subjects; columns = between-subjects groups. Subject k of a column = the k-th value under each
    row name in that column. Subjects missing any time point are left out."""
    rows = list(dict.fromkeys(str(l).strip() for l in row_labels if str(l or "").strip()))
    a = len(rows)
    if a < 2:
        raise ValueError("Repeated measures need at least 2 row names (e.g. time points).")
    subjects, groups_used = [], []  # each subject: (group index, [value per row level])
    for j, col in enumerate(columns):
        occ = {r: [] for r in rows}
        for lab, v in zip(row_labels, col):
            lab = str(lab or "").strip()
            if lab in occ:
                occ[lab].append(_num(v))
        k = max((len(v) for v in occ.values()), default=0)
        got = 0
        for s in range(k):
            vals = [occ[r][s] if s < len(occ[r]) else None for r in rows]
            if all(v is not None for v in vals):
                subjects.append((j, vals)); got += 1
        if got:
            groups_used.append(j)
    if len(groups_used) < 2:
        raise ValueError("Need at least 2 columns (groups), each with at least one subject measured at every row name.")
    gmap = {j: i for i, j in enumerate(groups_used)}
    names = [col_names[j] for j in groups_used]
    b = len(groups_used)
    G = np.array([gmap[s[0]] for s in subjects])
    Y = np.array([s[1] for s in subjects], float)          # subjects x a
    S = len(Y)
    if S - b < 1:
        raise ValueError("Need more than one subject in at least one group.")
    # between subjects: one-way ANOVA on subject means (x a)
    sm = Y.mean(axis=1)
    grand = Y.mean()
    ss_g = float(sum(a * np.sum(G == g) * (sm[G == g].mean() - grand) ** 2 for g in range(b)))
    ss_subj = float(a * sum(np.sum((sm[G == g] - sm[G == g].mean()) ** 2) for g in range(b)))
    df_g, df_subj = b - 1, S - b
    # within subjects via model comparison, subjects as fixed blocks (effect coding)
    y = Y.ravel()
    subj = np.repeat(np.arange(S), a)
    tidx = np.tile(np.arange(a), S)
    gidx = np.repeat(G, a)
    XS = np.zeros((S * a, S)); XS[np.arange(S * a), subj] = 1
    XT = _effect_cols(tidx, a)
    XG = _effect_cols(gidx, b)
    XTG = np.column_stack([XT[:, i] * XG[:, k] for i in range(a - 1) for k in range(b - 1)])
    full = np.column_stack([XS, XT, XTG])
    rss_full = _rss(full, y)
    df_err = (a - 1) * (S - b)
    ss_t = _rss(np.column_stack([XS, XTG]), y) - rss_full
    ss_tg = _rss(np.column_stack([XS, XT]), y) - rss_full
    ms_err, ms_subj = rss_full / df_err, ss_subj / df_subj
    # Geisser-Greenhouse epsilon from the pooled within-group covariance of the repeated measures
    resid = np.vstack([Y[G == g] - Y[G == g].mean(axis=0) for g in range(b)])
    Sp = resid.T @ resid / df_subj
    C = np.eye(a) - np.ones((a, a)) / a
    Sc = C @ Sp @ C
    eps = float(np.trace(Sc) ** 2 / ((a - 1) * np.sum(Sc ** 2))) if a > 2 and np.sum(Sc ** 2) > 0 else 1.0
    eps = min(1.0, max(1 / (a - 1), eps))
    ss_tot = float(np.sum((Y - grand) ** 2))

    def term(name, ss, df, msd, dfd, gg=False):
        F = (ss / df) / msd if msd > 0 else float("inf")
        p = float(stats.f.sf(F, df * eps, dfd * eps)) if gg else float(stats.f.sf(F, df, dfd))
        return {"source": name, "SS": ss, "df": df, "MS": ss / df, "F": F, "dfd": dfd, "p": p,
                "p_uncorrected": float(stats.f.sf(F, df, dfd)), "pct": 100 * ss / ss_tot, "stars": stars(p)}

    table = [term("Interaction", ss_tg, (a - 1) * (b - 1), ms_err, df_err, gg=True),
             term("Row factor", ss_t, a - 1, ms_err, df_err, gg=True),
             term("Column factor", ss_g, df_g, ms_subj, df_subj),
             {"source": "Subjects (within groups)", "SS": ss_subj, "df": df_subj, "MS": ms_subj, "F": None, "p": None, "pct": 100 * ss_subj / ss_tot},
             {"source": "Residual", "SS": rss_full, "df": df_err, "MS": ms_err, "F": None, "p": None, "pct": None}]
    cells = []
    for i in range(a):
        for g in range(b):
            d = describe(Y[G == g, i], f"{rows[i]} · {names[g]}")
            d.update(row=rows[i], col=names[g], i=i, j=g)
            cells.append(d)
    # simple effects: compare groups at each row level, error from that level's one-way ANOVA
    comps = []
    pairs = [(g1, g2) for g1 in range(b) for g2 in range(g1 + 1, b)]
    method = ("Šídák's multiple comparisons" if b == 2 else "Tukey's multiple comparisons") + " (columns at each row; separate error per row)"
    for i in range(a):
        col_i = [Y[G == g, i] for g in range(b)]
        ns = [len(c) for c in col_i]
        dfw = sum(ns) - b
        if dfw < 1:
            continue
        msw = sum(float(np.sum((c - c.mean()) ** 2)) for c in col_i) / dfw
        for g1, g2 in pairs:
            diff = float(col_i[g1].mean() - col_i[g2].mean())
            se = math.sqrt(msw * (1 / ns[g1] + 1 / ns[g2]))
            if b == 2:
                p_raw = 2 * stats.t.sf(abs(diff) / se, dfw) if se > 0 else 0.0
                p = 1 - (1 - p_raw) ** a
                half = stats.t.ppf(1 - (1 - (1 - alpha) ** (1 / a)) / 2, dfw) * se
            else:
                p = float(stats.studentized_range.sf(abs(diff) / (se / math.sqrt(2)), b, dfw)) if se > 0 else 0.0
                half = stats.studentized_range.ppf(1 - alpha, b, dfw) * se / math.sqrt(2)
            p = float(min(1.0, max(0.0, p)))
            comps.append({"row": rows[i], "a": names[g1], "b": names[g2], "i": i, "j1": g1, "j2": g2, "diff": diff,
                          "ci_low": diff - half, "ci_high": diff + half, "p": p, "stars": stars(p), "significant": p < alpha})
    subj_out = [{"group": names[G[s]], "values": Y[s].tolist()} for s in range(S)]
    return {"test_name": "Two-way repeated-measures ANOVA", "rm": True, "rows": rows, "cols": names, "alpha": alpha,
            "table": table, "cells": cells, "comparisons": comps, "posthoc_name": method, "epsilon": eps,
            "p": table[0]["p"], "n": int(S * a), "n_subjects": S, "subjects": subj_out,
            "subjects_per_group": [int(np.sum(G == g)) for g in range(b)], "balanced": len(set(np.bincount(G))) == 1}


def _helmert(k: int) -> np.ndarray:
    """k × (k−1) orthonormal contrasts."""
    H = np.zeros((k, k - 1))
    for j in range(1, k):
        H[:j, j - 1] = 1
        H[j, j - 1] = -j
        H[:, j - 1] /= np.linalg.norm(H[:, j - 1])
    return H


def two_way_rm_both(row_labels, columns, col_names, alpha: float = 0.05) -> dict:
    """Two-way ANOVA with both factors repeated: every subject is measured at every row level and in every column.
    Subject k = the k-th value under each row name, in every column. Incomplete subjects are left out.
    Each effect is tested against its own subject × effect error, with the Geisser-Greenhouse correction."""
    rows = list(dict.fromkeys(str(l).strip() for l in row_labels if str(l or "").strip()))
    a, b = len(rows), len(columns)
    if a < 2 or b < 2:
        raise ValueError("Need at least 2 row names and 2 columns.")
    per = {}
    for j, col in enumerate(columns):
        occ = {r: [] for r in rows}
        for lab, v in zip(row_labels, col):
            lab = str(lab or "").strip()
            if lab:
                occ[lab].append(_num(v))
        per[j] = occ
    nmax = max(len(per[j][r]) for j in range(b) for r in rows)
    subjects = []
    for k in range(nmax):
        vals = [[per[j][r][k] if k < len(per[j][r]) else None for j in range(b)] for r in rows]
        if all(v is not None for row in vals for v in row):
            subjects.append(vals)
    n = len(subjects)
    if n < 2:
        raise ValueError("Need at least 2 subjects with a value in every row and column (subject k = k-th value under each row name).")
    Y = np.array(subjects, float)            # n × a × b
    flat = Y.reshape(n, a * b)
    ua, ub = np.ones((a, 1)) / math.sqrt(a), np.ones((b, 1)) / math.sqrt(b)
    terms = [("Row factor", np.kron(_helmert(a), ub)), ("Column factor", np.kron(ua, _helmert(b))), ("Interaction", np.kron(_helmert(a), _helmert(b)))]
    ss_tot = float(np.sum((Y - Y.mean()) ** 2))
    table = []
    for name, Cm in terms:
        Z = flat @ Cm
        df = Cm.shape[1]
        zbar = Z.mean(axis=0)
        ss = float(n * zbar @ zbar)
        E = Z - zbar
        sse = float(np.sum(E ** 2))
        dfe = df * (n - 1)
        Sz = E.T @ E / (n - 1)
        eps = float(np.trace(Sz) ** 2 / (df * np.sum(Sz ** 2))) if df > 1 and np.sum(Sz ** 2) > 0 else 1.0
        eps = min(1.0, max(1 / df, eps))
        F = (ss / df) / (sse / dfe) if sse > 0 else float("inf")
        p = float(stats.f.sf(F, df * eps, dfe * eps))
        table.append({"source": name, "SS": ss, "df": df, "MS": ss / df, "F": F, "dfd": dfe, "p": p, "epsilon": eps,
                      "p_uncorrected": float(stats.f.sf(F, df, dfe)), "pct": 100 * ss / ss_tot if ss_tot > 0 else None, "stars": stars(p),
                      "error_SS": sse})
    table = [table[2], table[0], table[1]]  # Interaction, Row factor, Column factor (as in the other two-way results)
    subj_means = Y.mean(axis=(1, 2))
    ss_subj = float(a * b * np.sum((subj_means - Y.mean()) ** 2))
    table.append({"source": "Subjects", "SS": ss_subj, "df": n - 1, "MS": ss_subj / (n - 1), "F": None, "p": None, "pct": 100 * ss_subj / ss_tot})
    cells = []
    for i in range(a):
        for j in range(b):
            d = describe(Y[:, i, j], f"{rows[i]} · {col_names[j]}")
            d.update(row=rows[i], col=col_names[j], i=i, j=j)
            cells.append(d)
    # columns compared at each row with paired t tests (each comparison's own error), Šídák over the whole family
    pairs = [(j1, j2) for j1 in range(b) for j2 in range(j1 + 1, b)]
    m = a * len(pairs)
    a_s = 1 - (1 - alpha) ** (1 / m)
    comps = []
    for i in range(a):
        for j1, j2 in pairs:
            dvec = Y[:, i, j1] - Y[:, i, j2]
            diff, se = float(dvec.mean()), float(dvec.std(ddof=1) / math.sqrt(n))
            p_raw = float(2 * stats.t.sf(abs(diff) / se, n - 1)) if se > 0 else 0.0
            p = float(min(1.0, 1 - (1 - p_raw) ** m))
            half = float(stats.t.ppf(1 - a_s / 2, n - 1) * se)
            comps.append({"row": rows[i], "a": col_names[j1], "b": col_names[j2], "i": i, "j1": j1, "j2": j2, "diff": diff,
                          "ci_low": diff - half, "ci_high": diff + half, "p": p, "stars": stars(p), "significant": p < alpha})
    return {"test_name": "Two-way repeated-measures ANOVA (both factors)", "rm": True, "rm_both": True, "rows": rows, "cols": list(col_names),
            "alpha": alpha, "table": table, "cells": cells, "comparisons": comps,
            "posthoc_name": "Šídák's multiple comparisons (paired, columns at each row)", "p": table[0]["p"], "n": int(n * a * b),
            "n_subjects": n, "subjects": [], "subjects_per_group": [n] * b, "epsilon": min(t["epsilon"] for t in table[:3]), "balanced": True}


def three_way(factors, values, factor_names, alpha: float = 0.05, compare: str = "none") -> dict:
    """Three-way ANOVA (Type III sums of squares, effect coding) from long-format data:
    factors = [levels of A per row, levels of B per row, levels of C per row]; values = one number per row."""
    obs = []
    for i, v in enumerate(values):
        y = _num(v)
        labs = [str(f[i] if i < len(f) and f[i] is not None else "").strip() for f in factors]
        if y is not None and all(labs):
            obs.append((*labs, y))
    if len(obs) < 3:
        raise ValueError("Enter one row per measurement: the level of each of the three factors, then the value.")
    lev = [list(dict.fromkeys(o[k] for o in obs)) for k in range(3)]
    for k in range(3):
        if len(lev[k]) < 2:
            raise ValueError(f"'{factor_names[k]}' needs at least 2 different levels.")
    idx = [np.array([lev[k].index(o[k]) for o in obs]) for k in range(3)]
    y = np.array([o[3] for o in obs])
    N = len(y)
    shape = tuple(len(l) for l in lev)
    counts = np.zeros(shape, int)
    for a, b, c in zip(*idx):
        counts[a, b, c] += 1
    if np.any(counts == 0):
        miss = [f"{lev[0][a]} / {lev[1][b]} / {lev[2][c]}" for a, b, c in zip(*np.nonzero(counts == 0))]
        raise ValueError("Every combination of the three factors needs at least one value. Missing: " + ", ".join(miss[:4]))
    X = [_effect_cols(idx[k], shape[k]) for k in range(3)]
    inter = lambda *ms: np.column_stack([np.prod(np.column_stack(c), axis=1) for c in itertools.product(*[[m[:, j] for j in range(m.shape[1])] for m in ms])])
    blocks = {"A": X[0], "B": X[1], "C": X[2], "A×B": inter(X[0], X[1]), "A×C": inter(X[0], X[2]), "B×C": inter(X[1], X[2]),
              "A×B×C": inter(X[0], X[1], X[2])}
    one = np.ones((N, 1))
    full = np.column_stack([one, *blocks.values()])
    df_res = N - full.shape[1]
    if df_res < 1:
        raise ValueError("Not enough replicates: enter more than one value for at least some combinations.")
    rss_full = _rss(full, y)
    ms_res = rss_full / df_res
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    label = {"A": factor_names[0], "B": factor_names[1], "C": factor_names[2]}
    nice = lambda key: " × ".join(label[p] for p in key.split("×"))
    table = []
    for key, Xk in blocks.items():
        reduced = np.column_stack([one, *[v for k2, v in blocks.items() if k2 != key]])
        ss = _rss(reduced, y) - rss_full
        df = Xk.shape[1]
        F = (ss / df) / ms_res if ms_res > 0 else float("inf")
        p = float(stats.f.sf(F, df, df_res))
        table.append({"source": nice(key), "key": key, "SS": ss, "df": df, "MS": ss / df, "F": F, "p": p,
                      "pct": 100 * ss / ss_tot if ss_tot > 0 else None, "stars": stars(p)})
    table.append({"source": "Residual", "key": "res", "SS": rss_full, "df": df_res, "MS": ms_res, "F": None, "p": None, "pct": None})
    cells = []
    for a in range(shape[0]):
        for b in range(shape[1]):
            for c in range(shape[2]):
                v = y[(idx[0] == a) & (idx[1] == b) & (idx[2] == c)]
                d = describe(v, f"{lev[0][a]} · {lev[1][b]} · {lev[2][c]}")
                d.update(a=a, b=b, c=c)
                cells.append(d)
    comps, method = [], None
    if compare in ("A", "B", "C"):
        f = "ABC".index(compare)
        others = [k for k in range(3) if k != f]
        mean = {(c["a"], c["b"], c["c"]): c["mean"] for c in cells}
        fam = []
        for o1 in range(shape[others[0]]):
            for o2 in range(shape[others[1]]):
                def key(level):
                    k = [0, 0, 0]; k[f] = level; k[others[0]] = o1; k[others[1]] = o2
                    return tuple(k)
                label = f"{lev[others[0]][o1]} · {lev[others[1]][o2]}"
                pairs = [(lev[f][l1], lev[f][l2], mean[key(l1)] - mean[key(l2)],
                          math.sqrt(ms_res * (1 / counts[key(l1)] + 1 / counts[key(l2)])), {"kind": compare, "l1": l1, "l2": l2, "o1": o1, "o2": o2})
                         for l1 in range(shape[f]) for l2 in range(l1 + 1, shape[f])]
                fam.append((label, pairs))
        comps = _family(fam, shape[f], ms_res, df_res, alpha)
        method = f"{'Šídák' if shape[f] == 2 else 'Tukey'}'s multiple comparisons: levels of {factor_names[f]} within each combination of {factor_names[others[0]]} and {factor_names[others[1]]}"
    return {"test_name": "Three-way ANOVA", "kind": "threeway", "factors": list(factor_names), "levels": lev, "alpha": alpha,
            "table": table, "cells": cells, "n": N, "balanced": bool(np.all(counts == counts.flat[0])),
            "comparisons": comps, "posthoc_name": method, "compare": compare}
