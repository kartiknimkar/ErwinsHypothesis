"""Nested t test / nested one-way ANOVA (Prism's 'Nested' table).

Layout: each subject (e.g. one animal, one culture) belongs to one group and has several replicate
measurements. Model: y = group mean + subject effect (random, variance σ²_subject) + residual (σ²_residual),
fitted by REML. Group means are compared with a Wald F test whose denominator df is the number of
subjects minus the number of groups (containment df). For balanced data this is exactly one-way ANOVA
on the subject means.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats

from .stats import stars


def _fit(subjects, G, theta):
    """GLS for a given variance ratio theta = σ²_subject/σ²_residual. Returns β, (X'WX)^-1, r'Wr, Σlog|V_s|."""
    XtWX = np.zeros((G, G)); XtWy = np.zeros(G)
    logdet = 0.0
    for g, y in subjects:
        n = len(y)
        c = theta / (1 + n * theta)
        # X_s is a column of ones for group g; W_s = I − c J
        XtWX[g, g] += n - c * n * n
        XtWy[g] += y.sum() - c * n * y.sum()
        logdet += math.log(1 + n * theta)
    C = np.linalg.inv(XtWX)
    beta = C @ XtWy
    rWr = 0.0
    for g, y in subjects:
        r = y - beta[g]
        c = theta / (1 + len(y) * theta)
        rWr += r @ r - c * r.sum() ** 2
    return beta, C, rWr, logdet, XtWX


def _neg_reml(theta, subjects, G, N):
    beta, C, rWr, logdet, XtWX = _fit(subjects, G, theta)
    s2 = rWr / (N - G)
    return 0.5 * ((N - G) * math.log(s2) + logdet + math.log(np.linalg.det(XtWX)))


def nested(group_of, values, group_names, alpha: float = 0.05) -> dict:
    """group_of: group index per subject; values: list of replicate lists per subject."""
    subjects = [(int(g), np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)) for g, vals in zip(group_of, values)]
    subjects = [(g, y) for g, y in subjects if len(y)]
    G = len(group_names)
    used = sorted({g for g, _ in subjects})
    if len(used) < 2:
        raise ValueError("Enter subjects in at least two groups.")
    remap = {g: i for i, g in enumerate(used)}
    names = [group_names[g] for g in used]
    subjects = [(remap[g], y) for g, y in subjects]
    G = len(used)
    S, N = len(subjects), sum(len(y) for _, y in subjects)
    per_group = [sum(1 for g, _ in subjects if g == k) for k in range(G)]
    if min(per_group) < 2 and S - G < 1:
        raise ValueError("Each group needs at least 2 subjects.")
    if S - G < 1:
        raise ValueError("Need more subjects than groups.")
    if N - S < 1:
        raise ValueError("Each subject needs replicate values (more than one measurement for at least one subject).")
    # REML for theta >= 0, searched on a log scale, and theta = 0 checked as the boundary
    res = optimize.minimize_scalar(lambda lt: _neg_reml(math.exp(lt), subjects, G, N), bounds=(-20, 12), method="bounded",
                                   options={"xatol": 1e-10})
    theta = math.exp(res.x)
    if _neg_reml(0.0, subjects, G, N) <= res.fun:
        theta = 0.0
    beta, C, rWr, _, _ = _fit(subjects, G, theta)
    s2e = rWr / (N - G)
    s2u = theta * s2e
    cov = s2e * C
    df_d = S - G
    L = np.zeros((G - 1, G)); L[:, 0] = 1; L[np.arange(G - 1), np.arange(1, G)] = -1
    Lb = L @ beta
    F = float(Lb @ np.linalg.solve(L @ cov @ L.T, Lb) / (G - 1))
    p = float(stats.f.sf(F, G - 1, df_d))
    # do subjects differ within groups? exact one-way ANOVA F test of subjects nested in groups
    ss_err = sum(((y - y.mean()) ** 2).sum() for _, y in subjects)
    gm = [np.concatenate([y for g, y in subjects if g == k]).mean() for k in range(G)]
    ss_subj = sum(len(y) * (y.mean() - gm[g]) ** 2 for g, y in subjects)
    f_subj = (ss_subj / (S - G)) / (ss_err / (N - S)) if ss_err > 0 else float("inf")
    p_subj = float(stats.f.sf(f_subj, S - G, N - S))
    tcrit = float(stats.t.ppf(1 - alpha / 2, df_d))
    se = np.sqrt(np.diag(cov))
    groups = []
    for k in range(G):
        means = [float(y.mean()) for g, y in subjects if g == k]
        groups.append({"name": names[k], "mean": float(beta[k]), "se": float(se[k]), "ci": [float(beta[k] - tcrit * se[k]), float(beta[k] + tcrit * se[k])],
                       "n_subjects": per_group[k], "n_values": int(sum(len(y) for g, y in subjects if g == k)),
                       "subject_means": means, "sd_of_subject_means": float(np.std(means, ddof=1)) if len(means) > 1 else None})
    comparisons = []
    if G >= 2:
        q_dist = stats.studentized_range if G > 2 else None
        for i in range(G):
            for j in range(i + 1, G):
                d = float(beta[j] - beta[i])
                sed = float(math.sqrt(cov[i, i] + cov[j, j] - 2 * cov[i, j]))
                t = d / sed
                if G == 2:
                    padj = float(2 * stats.t.sf(abs(t), df_d)); half = tcrit * sed
                else:
                    padj = float(q_dist.sf(abs(t) * math.sqrt(2), G, df_d))
                    half = float(q_dist.ppf(1 - alpha, G, df_d) / math.sqrt(2) * sed)
                comparisons.append({"i": i, "j": j, "a": names[i], "b": names[j], "diff": d, "se": sed, "t": float(t),
                                    "ci": [d - half, d + half], "p": padj, "stars": stars(padj), "significant": padj < alpha})
    out = {"test_name": "Nested t test" if G == 2 else "Nested one-way ANOVA", "kind": "nested", "names": names, "alpha": alpha,
           "n_groups": G, "n_subjects": S, "n_values": N, "F": F, "df_n": G - 1, "df_d": df_d, "p": p, "stars": stars(p),
           "significant": p < alpha, "groups": groups, "comparisons": comparisons,
           "var_subject": float(s2u), "var_residual": float(s2e),
           "icc": float(s2u / (s2u + s2e)) if s2u + s2e > 0 else None,
           "subjects_F": float(f_subj), "subjects_df": [S - G, N - S], "subjects_p": p_subj}
    if G == 2:
        c = comparisons[0]
        out.update({"t": c["t"], "df": df_d, "diff": c["diff"], "diff_ci": c["ci"]})
    return out
