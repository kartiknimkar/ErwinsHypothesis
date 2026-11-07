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


def bland_altman(a, b, names=("Method A", "Method B"), alpha: float = 0.05, kind: str = "diff") -> dict:
    """Agreement between two methods measuring the same samples (each row = one sample).
    kind: diff (B − A), pct (100·(B − A)/mean of the two), ratio (B/A; analyzed as log ratios and back-transformed,
    as Bland & Altman recommend when the differences grow with the size of the measurement)."""
    pairs = [(x, y) for x, y in zip(map(_num, a), map(_num, b)) if x is not None and y is not None]
    if len(pairs) < 3:
        raise ValueError("Enter at least 3 samples measured by both methods (one row per sample).")
    x = np.array([p[0] for p in pairs]); y = np.array([p[1] for p in pairs])
    avg = (x + y) / 2
    if kind == "pct":
        if np.any(avg == 0):
            raise ValueError("Percent differences need averages that aren't 0.")
        diff = 100 * (y - x) / avg
    elif kind == "ratio":
        if np.any(x <= 0) or np.any(y <= 0):
            raise ValueError("Ratios need all values greater than 0.")
        diff = np.log(y / x)
    else:
        diff = y - x
    n = len(diff)
    bias, sd = float(diff.mean()), float(diff.std(ddof=1))
    z = stats.norm.ppf(1 - alpha / 2)
    t = stats.t.ppf(1 - alpha / 2, n - 1)
    se_bias = sd / math.sqrt(n)
    se_loa = math.sqrt(3 * sd ** 2 / n)  # Bland & Altman (1986)
    lo, hi = bias - z * sd, bias + z * sd
    trend = stats.linregress(avg, diff) if np.ptp(avg) > 0 else None
    if kind == "ratio":  # back to the ratio scale: geometric mean ratio and limits as ratios
        e = np.exp
        out = {"bias": float(e(bias)), "bias_ci": [float(e(bias - t * se_bias)), float(e(bias + t * se_bias))],
               "loa": [float(e(lo)), float(e(hi))], "loa_lo_ci": [float(e(lo - t * se_loa)), float(e(lo + t * se_loa))],
               "loa_hi_ci": [float(e(hi - t * se_loa)), float(e(hi + t * se_loa))], "sd_log": sd}
        return {"test_name": "Bland-Altman", "kind": "ratio", "n": n, "names": list(names), "sd": sd, **out,
                "p_bias": float(stats.ttest_1samp(diff, 0).pvalue),
                "trend_p": float(trend.pvalue) if trend else None, "trend_slope": float(trend.slope) if trend else None,
                "points": {"avg": avg.tolist(), "diff": np.exp(diff).tolist()}, "alpha": alpha}
    return {"test_name": "Bland-Altman", "kind": kind, "n": n, "names": list(names), "bias": bias, "sd": sd,
            "bias_ci": [bias - t * se_bias, bias + t * se_bias],
            "loa": [lo, hi], "loa_lo_ci": [lo - t * se_loa, lo + t * se_loa], "loa_hi_ci": [hi - t * se_loa, hi + t * se_loa],
            "p_bias": float(stats.ttest_1samp(diff, 0).pvalue),
            "trend_p": float(trend.pvalue) if trend else None, "trend_slope": float(trend.slope) if trend else None,
            "points": {"avg": avg.tolist(), "diff": diff.tolist()}, "alpha": alpha}


def _design(y_col, x_cols):
    """Complete rows only. Returns y, X (with intercept column), number of rows dropped."""
    rows = []
    dropped = 0
    for i, yv in enumerate(y_col):
        vals = [_num(yv)] + [_num(c[i]) if i < len(c) else None for c in x_cols]
        if all(v is not None for v in vals):
            rows.append(vals)
        elif any(v is not None for v in vals):
            dropped += 1
    A = np.array(rows, float)
    if A.size == 0:
        raise ValueError("No rows have a value in every column.")
    return A[:, 0], np.column_stack([np.ones(len(A)), A[:, 1:]]), dropped


def multiple_linear(y_col, x_cols, y_name, x_names, alpha: float = 0.05) -> dict:
    """Ordinary least squares with several predictors."""
    y, X, dropped = _design(y_col, x_cols)
    n, k = X.shape
    if n <= k:
        raise ValueError(f"Need more rows than predictors + 1 (have {n} complete rows, {k - 1} predictors).")
    if np.linalg.matrix_rank(X) < k:
        raise ValueError("Some predictors are exact copies or combinations of others (or constant). Remove one.")
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fit = X @ beta
    resid = y - fit
    df = n - k
    sse = float(resid @ resid)
    mse = sse / df
    cov = mse * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), df)
    tc = stats.t.ppf(1 - alpha / 2, df)
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - sse / sst if sst > 0 else None
    adj = 1 - (1 - r2) * (n - 1) / df if r2 is not None else None
    F = ((sst - sse) / (k - 1)) / mse if k > 1 and mse > 0 else None
    pF = float(stats.f.sf(F, k - 1, df)) if F is not None else None
    # variance inflation factors (multicollinearity check)
    vif = [None]
    for j in range(1, k):
        others = np.delete(X, j, axis=1)
        b, *_ = np.linalg.lstsq(others, X[:, j], rcond=None)
        r = X[:, j] - others @ b
        ss = float(np.sum((X[:, j] - X[:, j].mean()) ** 2))
        r2j = 1 - float(r @ r) / ss if ss > 0 else 0
        vif.append(1 / (1 - r2j) if r2j < 1 else None)
    names = ["Intercept"] + list(x_names)
    coefs = [{"name": nm, "estimate": float(b), "se": float(s), "ci": [float(b - tc * s), float(b + tc * s)],
              "t": float(tt), "p": float(pp), "stars": stars(float(pp)), "vif": v}
             for nm, b, s, tt, pp, v in zip(names, beta, se, t, p, vif)]
    return {"test_name": "Multiple linear regression", "kind": "linear", "y_name": y_name, "n": n, "dropped": dropped,
            "df": df, "coefs": coefs, "r_squared": r2, "adj_r_squared": adj, "sy_x": math.sqrt(mse), "F": F,
            "p": pF, "stars": stars(pF) if pF is not None else "", "alpha": alpha,
            "points": {"actual": y.tolist(), "predicted": fit.tolist()}}


def logistic(y_col, x_cols, y_name, x_names, alpha: float = 0.05) -> dict:
    """Binary logistic regression (Newton-Raphson / IRLS). Y must be 0 or 1."""
    y, X, dropped = _design(y_col, x_cols)
    if not np.all(np.isin(y, (0, 1))):
        raise ValueError("For logistic regression the outcome (first column) must be 0 or 1.")
    n, k = X.shape
    if y.sum() == 0 or y.sum() == n:
        raise ValueError("The outcome needs both 0s and 1s.")
    if n <= k:
        raise ValueError("Need more rows than predictors + 1.")
    beta = np.zeros(k)
    for _ in range(100):
        eta = np.clip(X @ beta, -35, 35)
        pr = 1 / (1 + np.exp(-eta))
        W = pr * (1 - pr)
        H = X.T @ (X * W[:, None])
        try:
            step = np.linalg.solve(H, X.T @ (y - pr))
        except np.linalg.LinAlgError:
            raise ValueError("The model couldn't be fitted (predictors may be redundant).")
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    eta = np.clip(X @ beta, -35, 35)
    pr = 1 / (1 + np.exp(-eta))
    # complete separation: the model predicts every case perfectly and coefficients run off to infinity
    perfect = bool(np.all(np.where(y == 1, pr > 1 - 1e-6, pr < 1e-6)))
    sd = X[:, 1:].std(axis=0)
    huge = bool(np.any(np.abs(beta[1:]) * sd > 15))
    if perfect or huge:
        raise ValueError("The predictors separate the 0s and 1s (almost) perfectly, so odds ratios are infinite "
                         "(complete separation). Use fewer predictors or more data.")
    W = pr * (1 - pr)
    cov = np.linalg.inv(X.T @ (X * W[:, None]))
    se = np.sqrt(np.diag(cov))
    z = beta / se
    p = 2 * stats.norm.sf(np.abs(z))
    zc = stats.norm.ppf(1 - alpha / 2)
    ll = float(np.sum(y * np.log(pr + 1e-300) + (1 - y) * np.log(1 - pr + 1e-300)))
    p0 = y.mean()
    ll0 = float(n * (p0 * math.log(p0) + (1 - p0) * math.log(1 - p0)))
    lr = 2 * (ll - ll0)
    plr = float(stats.chi2.sf(lr, k - 1)) if k > 1 else None
    names = ["Intercept"] + list(x_names)
    coefs = [{"name": nm, "estimate": float(b), "se": float(s), "z": float(zz), "p": float(pp), "stars": stars(float(pp)),
              "or": float(math.exp(b)), "or_ci": [float(math.exp(b - zc * s)), float(math.exp(b + zc * s))]}
             for nm, b, s, zz, pp in zip(names, beta, se, z, p)]
    roc_res = roc(pr[y == 0], pr[y == 1], alpha=alpha) if 0 < y.sum() < n else None
    pred = (pr >= 0.5).astype(int)
    return {"test_name": "Logistic regression", "kind": "logistic", "y_name": y_name, "n": n, "dropped": dropped,
            "n_events": int(y.sum()), "coefs": coefs, "loglik": ll, "lr_chi2": lr, "p": plr,
            "stars": stars(plr) if plr is not None else "", "mcfadden_r2": 1 - ll / ll0 if ll0 else None,
            "tjur_r2": float(pr[y == 1].mean() - pr[y == 0].mean()), "auc": roc_res["auc"] if roc_res else None,
            "roc_curve": roc_res["curve"] if roc_res else None,
            "accuracy": float(np.mean(pred == y)), "alpha": alpha,
            "points": {"actual": y.tolist(), "predicted": pr.tolist()}}


def pca(columns, names, standardize: bool = True) -> dict:
    """Principal component analysis on complete rows. Standardized (correlation-based) by default."""
    cols = [[_num(v) for v in c] for c in columns]
    keep = [i for i, c in enumerate(cols) if sum(v is not None for v in c) >= 3]
    cols = [cols[i] for i in keep]; names = [names[i] for i in keep]
    if len(cols) < 2:
        raise ValueError("PCA needs at least 2 variables (columns) with values.")
    rows = [r for r in zip(*cols) if all(v is not None for v in r)]
    n, p = len(rows), len(cols)
    if n < 3:
        raise ValueError("PCA needs at least 3 rows with a value in every column.")
    X = np.array(rows, float)
    sd = X.std(axis=0, ddof=1)
    if np.any(sd == 0):
        raise ValueError("A variable has the same value in every row; remove it.")
    Z = (X - X.mean(axis=0)) / (sd if standardize else 1)
    U, S, Vt = np.linalg.svd(Z, full_matrices=False)
    eig = S ** 2 / (n - 1)
    # sign convention: largest loading of each component is positive
    for k in range(len(S)):
        if Vt[k, np.argmax(np.abs(Vt[k]))] < 0:
            Vt[k] *= -1; U[:, k] *= -1
    scores = Z @ Vt.T
    var = eig / eig.sum()
    m = min(p, n - 1)
    loadings = (Vt[:m].T * np.sqrt(eig[:m]))  # correlation of each variable with each component (standardized)
    return {"test_name": "Principal component analysis", "kind": "pca", "names": names, "n": n, "standardized": standardize,
            "eigenvalues": eig[:m].tolist(), "variance_pct": (100 * var[:m]).tolist(), "cumulative_pct": (100 * np.cumsum(var[:m])).tolist(),
            "kaiser": int(np.sum(eig[:m] > 1)), "vectors": Vt[:m].tolist(), "loadings": loadings.tolist(),
            "scores": scores[:, :m].tolist(), "dropped": int(len(list(zip(*cols))) - n)}


def _cox_efron(beta, T, E, X):
    """Efron partial log-likelihood, gradient and Hessian (handles tied event times)."""
    eta = X @ beta
    eta = eta - eta.max()  # stabilizes exp; the partial likelihood is unchanged by a constant shift
    w = np.exp(eta)
    k = X.shape[1]
    ll, g, H = 0.0, np.zeros(k), np.zeros((k, k))
    for t in np.unique(T[E == 1]):
        R = T >= t
        D = (T == t) & (E == 1)
        d = int(D.sum())
        s0R, s1R = w[R].sum(), (w[R, None] * X[R]).sum(0)
        s2R = (X[R].T * w[R]) @ X[R]
        s0D, s1D = w[D].sum(), (w[D, None] * X[D]).sum(0)
        s2D = (X[D].T * w[D]) @ X[D]
        ll += eta[D].sum()
        g += X[D].sum(0)
        for l in range(d):
            f = l / d
            phi, s1, s2 = s0R - f * s0D, s1R - f * s1D, s2R - f * s2D
            ll -= math.log(phi)
            g -= s1 / phi
            H -= s2 / phi - np.outer(s1, s1) / phi ** 2
    return ll, g, H


def cox(time_col, event_col, x_cols, x_names, alpha: float = 0.05) -> dict:
    """Cox proportional hazards regression (Efron ties, Newton-Raphson with step halving).
    Event column: 1 = event (e.g. death), 0 = censored."""
    rows, dropped = [], 0
    for i, tv in enumerate(time_col):
        vals = [_num(tv), _num(event_col[i]) if i < len(event_col) else None] + [_num(c[i]) if i < len(c) else None for c in x_cols]
        if all(v is not None for v in vals):
            rows.append(vals)
        elif any(v is not None for v in vals):
            dropped += 1
    if not rows:
        raise ValueError("No rows have a value in every column.")
    A = np.array(rows, float)
    T, E, X = A[:, 0], A[:, 1], A[:, 2:]
    if not np.all(np.isin(E, (0, 1))):
        raise ValueError("The event column (second column) must be 1 (event happened) or 0 (censored).")
    if np.any(T < 0):
        raise ValueError("Times can't be negative.")
    n, k = X.shape
    ne = int(E.sum())
    if ne < 2:
        raise ValueError("Need at least 2 events (rows with 1 in the event column).")
    if np.any(X.std(axis=0) == 0):
        raise ValueError("A predictor has the same value in every row; remove it.")
    # fit on centered predictors (same coefficients, better numerics)
    Xc = X - X.mean(axis=0)
    beta = np.zeros(k)
    ll0, _, _ = _cox_efron(beta, T, E, Xc)
    ll = ll0
    for _ in range(60):
        ll, g, H = _cox_efron(beta, T, E, Xc)
        try:
            step = np.linalg.solve(-H, g)
        except np.linalg.LinAlgError:
            raise ValueError("The model couldn't be fitted (predictors may be redundant).")
        new, t = beta + step, 1.0
        while _cox_efron(new, T, E, Xc)[0] < ll - 1e-12 and t > 1e-4:
            t /= 2
            new = beta + t * step
        beta = new
        if np.max(np.abs(t * step)) < 1e-10:
            break
    ll, g, H = _cox_efron(beta, T, E, Xc)
    if np.any(np.abs(beta) * X.std(axis=0) > 15):
        raise ValueError("A predictor separates events from non-events (almost) perfectly, so the hazard ratio is infinite. "
                         "Use fewer predictors or more data.")
    cov = np.linalg.inv(-H)
    se = np.sqrt(np.diag(cov))
    z = beta / se
    p = 2 * stats.norm.sf(np.abs(z))
    zc = stats.norm.ppf(1 - alpha / 2)
    lr = 2 * (ll - ll0)
    plr = float(stats.chi2.sf(lr, k))
    _, g0, H0 = _cox_efron(np.zeros(k), T, E, Xc)
    score = float(g0 @ np.linalg.solve(-H0, g0))
    wald = float(beta @ np.linalg.solve(cov, beta))
    # Harrell's concordance: among comparable pairs, does the higher risk score die first?
    risk = X @ beta
    conc = disc = tied = 0
    for i in range(n):
        if E[i] != 1:
            continue
        later = (T > T[i]) | ((T == T[i]) & (E == 0))  # censored at the same time counts as surviving longer
        conc += int(np.sum(risk[later] < risk[i])); disc += int(np.sum(risk[later] > risk[i])); tied += int(np.sum(risk[later] == risk[i]))
    pairs = conc + disc + tied
    coefs = [{"name": nm, "estimate": float(b), "se": float(s), "z": float(zz), "p": float(pp), "stars": stars(float(pp)),
              "hr": float(math.exp(b)), "hr_ci": [float(math.exp(b - zc * s)), float(math.exp(b + zc * s))]}
             for nm, b, s, zz, pp in zip(x_names, beta, se, z, p)]
    return {"test_name": "Cox proportional hazards regression", "kind": "cox", "n": n, "n_events": ne, "dropped": dropped,
            "coefs": coefs, "loglik": float(ll), "loglik0": float(ll0), "lr_chi2": float(lr), "df": k, "p": plr, "stars": stars(plr),
            "score_chi2": score, "score_p": float(stats.chi2.sf(score, k)), "wald_chi2": wald, "wald_p": float(stats.chi2.sf(wald, k)),
            "concordance": (conc + 0.5 * tied) / pairs if pairs else None, "ties": "efron", "alpha": alpha}


def _deming_fit(x, y, delta):
    """Deming slope and intercept; delta = (error variance of Y) / (error variance of X)."""
    mx, my = x.mean(), y.mean()
    sxx, syy, sxy = np.mean((x - mx) ** 2), np.mean((y - my) ** 2), np.mean((x - mx) * (y - my))
    if sxy == 0:
        raise ValueError("The two methods show no relationship, so a Deming line can't be fitted.")
    b = (syy - delta * sxx + math.sqrt((syy - delta * sxx) ** 2 + 4 * delta * sxy ** 2)) / (2 * sxy)
    return b, my - b * mx


def deming(a, b, names=("Method A", "Method B"), sd_ratio: float | None = None, alpha: float = 0.05) -> dict:
    """Deming regression of method B (Y) on method A (X), allowing for measurement error in both.
    sd_ratio = SD of method B's error / SD of method A's error (default 1: equally precise, orthogonal regression).
    Standard errors and CIs by jackknife (leave-one-out), as is standard for method comparison."""
    pairs = [(x, y) for x, y in zip(map(_num, a), map(_num, b)) if x is not None and y is not None]
    n = len(pairs)
    if n < 4:
        raise ValueError("Enter at least 4 samples measured by both methods (one row per sample).")
    x = np.array([p[0] for p in pairs]); y = np.array([p[1] for p in pairs])
    r = float(sd_ratio) if sd_ratio else 1.0
    if not r > 0:
        raise ValueError("The SD ratio must be greater than 0.")
    delta = r * r
    slope, icpt = _deming_fit(x, y, delta)
    jk = np.array([_deming_fit(np.delete(x, i), np.delete(y, i), delta) for i in range(n)])
    se = np.sqrt((n - 1) / n * np.sum((jk - jk.mean(axis=0)) ** 2, axis=0))
    t = stats.t.ppf(1 - alpha / 2, n - 2)
    ci_s = [slope - t * se[0], slope + t * se[0]]
    ci_i = [icpt - t * se[1], icpt + t * se[1]]
    p_slope = float(2 * stats.t.sf(abs(slope - 1) / se[0], n - 2))
    p_icpt = float(2 * stats.t.sf(abs(icpt) / se[1], n - 2))
    xs = np.linspace(min(x.min(), y.min()), max(x.max(), y.max()), 50)
    ols = stats.linregress(x, y)
    return {"test_name": "Deming regression", "kind": "deming", "names": list(names), "n": n, "sd_ratio": r,
            "slope": float(slope), "intercept": float(icpt), "slope_se": float(se[0]), "intercept_se": float(se[1]),
            "slope_ci": [float(v) for v in ci_s], "intercept_ci": [float(v) for v in ci_i],
            "p_slope_1": p_slope, "p_intercept_0": p_icpt, "stars_slope": stars(p_slope), "stars_intercept": stars(p_icpt),
            "pearson_r": float(ols.rvalue), "ols_slope": float(ols.slope), "alpha": alpha,
            "points": {"x": x.tolist(), "y": y.tolist()}, "line": {"x": xs.tolist(), "y": (icpt + slope * xs).tolist()}}
