"""Nonlinear curve fitting (least squares), with the models labs use most."""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats


def _hill_guess(x, y, inhibit):
    lo, hi = float(np.min(y)), float(np.max(y))
    mid = (lo + hi) / 2
    # X closest to half-maximal response
    xm = float(x[np.argmin(np.abs(y - mid))])
    return [lo, hi, xm, -1.0 if inhibit else 1.0]


MODELS = {
    "dr_inhibit": {
        "name": "Dose-response: inhibition (IC50)",
        "short": "log(inhibitor) vs. response, variable slope (4 parameters)",
        "equation": "Y = Bottom + (Top − Bottom) / (1 + 10^((LogIC50 − X)·HillSlope))",
        "params": ["Bottom", "Top", "LogIC50", "HillSlope"],
        "f": lambda x, b, t, l, h: b + (t - b) / (1 + 10 ** ((l - x) * h)),
        "guess": lambda x, y: _hill_guess(x, y, True),
        "log_x": True, "derived": ("IC50", "LogIC50"),
    },
    "dr_stim": {
        "name": "Dose-response: stimulation (EC50)",
        "short": "log(agonist) vs. response, variable slope (4 parameters)",
        "equation": "Y = Bottom + (Top − Bottom) / (1 + 10^((LogEC50 − X)·HillSlope))",
        "params": ["Bottom", "Top", "LogEC50", "HillSlope"],
        "f": lambda x, b, t, l, h: b + (t - b) / (1 + 10 ** ((l - x) * h)),
        "guess": lambda x, y: _hill_guess(x, y, False),
        "log_x": True, "derived": ("EC50", "LogEC50"),
    },
    "dr_inhibit_fixed": {
        "name": "Dose-response: inhibition, standard slope (IC50)",
        "short": "log(inhibitor) vs. response, Hill slope fixed at −1 (3 parameters)",
        "equation": "Y = Bottom + (Top − Bottom) / (1 + 10^(X − LogIC50))",
        "params": ["Bottom", "Top", "LogIC50"],
        "f": lambda x, b, t, l: b + (t - b) / (1 + 10 ** (x - l)),
        "guess": lambda x, y: _hill_guess(x, y, True)[:3],
        "log_x": True, "derived": ("IC50", "LogIC50"),
    },
    "dr_stim_fixed": {
        "name": "Dose-response: stimulation, standard slope (EC50)",
        "short": "log(agonist) vs. response, Hill slope fixed at 1 (3 parameters)",
        "equation": "Y = Bottom + (Top − Bottom) / (1 + 10^(LogEC50 − X))",
        "params": ["Bottom", "Top", "LogEC50"],
        "f": lambda x, b, t, l: b + (t - b) / (1 + 10 ** (l - x)),
        "guess": lambda x, y: _hill_guess(x, y, False)[:3],
        "log_x": True, "derived": ("EC50", "LogEC50"),
    },
    "michaelis": {
        "name": "Michaelis-Menten (enzyme kinetics)",
        "short": "Vmax and Km",
        "equation": "Y = Vmax·X / (Km + X)",
        "params": ["Vmax", "Km"],
        "f": lambda x, v, k: v * x / (k + x),
        "guess": lambda x, y: [float(np.max(y)) * 1.1, float(np.median(x[x > 0])) if np.any(x > 0) else 1.0],
        "log_x": False,
    },
    "exp_decay": {
        "name": "Exponential decay (one phase)",
        "short": "half-life, rate constant",
        "equation": "Y = (Y0 − Plateau)·exp(−K·X) + Plateau",
        "params": ["Y0", "Plateau", "K"],
        "f": lambda x, y0, p, k: (y0 - p) * np.exp(-k * x) + p,
        "guess": lambda x, y: [float(y[np.argmin(x)]), float(np.min(y)), 1.0 / (float(np.ptp(x)) or 1.0)],
        "log_x": False, "halflife": True,
    },
    "two_phase_decay": {
        "name": "Exponential decay (two phase)",
        "short": "fast and slow components",
        "equation": "Y = Plateau + SpanFast·exp(−Kfast·X) + SpanSlow·exp(−Kslow·X)",
        "params": ["Plateau", "SpanFast", "Kfast", "SpanSlow", "Kslow"],
        "f": lambda x, p, sf, kf, ss, ks: p + sf * np.exp(-kf * x) + ss * np.exp(-ks * x),
        "guess": lambda x, y: [float(np.min(y)), (float(y[np.argmin(x)]) - float(np.min(y))) / 2,
                               5.0 / (float(np.ptp(x)) or 1.0), (float(y[np.argmin(x)]) - float(np.min(y))) / 2,
                               0.5 / (float(np.ptp(x)) or 1.0)],
        "log_x": False, "two_phase": True,
    },
    "exp_growth": {
        "name": "Exponential growth",
        "short": "doubling time",
        "equation": "Y = Y0·exp(K·X)",
        "params": ["Y0", "K"],
        "f": lambda x, y0, k: y0 * np.exp(k * x),
        "guess": lambda x, y: [float(y[np.argmin(x)]) or 1.0, 1.0 / (float(np.ptp(x)) or 1.0)],
        "log_x": False, "doubling": True,
    },
    "assoc": {
        "name": "One-phase association",
        "short": "rise to a plateau (binding, uptake)",
        "equation": "Y = Y0 + (Plateau − Y0)·(1 − exp(−K·X))",
        "params": ["Y0", "Plateau", "K"],
        "f": lambda x, y0, p, k: y0 + (p - y0) * (1 - np.exp(-k * x)),
        "guess": lambda x, y: [float(y[np.argmin(x)]), float(np.max(y)), 1.0 / (float(np.ptp(x)) or 1.0)],
        "log_x": False, "halflife": True,
    },
    "gaussian": {
        "name": "Gaussian (bell-shaped peak)",
        "short": "peak center and width",
        "equation": "Y = Amplitude·exp(−0.5·((X − Mean)/SD)²)",
        "params": ["Amplitude", "Mean", "SD"],
        "f": lambda x, a, m, s: a * np.exp(-0.5 * ((x - m) / s) ** 2),
        "guess": lambda x, y: [float(np.max(y)), float(x[np.argmax(y)]),
                               float(np.sqrt(abs(np.sum(y * (x - x[np.argmax(y)]) ** 2) / (np.sum(y) or 1)))) or float(np.ptp(x)) / 4 or 1.0],
        "log_x": False,
    },
    "boltzmann": {
        "name": "Boltzmann sigmoid",
        "short": "e.g. channel activation vs. voltage (X not logged)",
        "equation": "Y = Bottom + (Top − Bottom) / (1 + exp((V50 − X)/Slope))",
        "params": ["Bottom", "Top", "V50", "Slope"],
        "f": lambda x, b, t, v, s: b + (t - b) / (1 + np.exp((v - x) / s)),
        "guess": lambda x, y: [float(np.min(y)), float(np.max(y)), float(x[np.argmin(np.abs(y - (np.min(y) + np.max(y)) / 2))]),
                               (float(np.ptp(x)) / 10 or 1.0) * (1 if np.corrcoef(x, y)[0, 1] >= 0 else -1)],
        "log_x": False,
    },
}

# pairs where the simpler model is a special case of the other (extra sum-of-squares F test applies)
NESTED = {("dr_inhibit_fixed", "dr_inhibit"), ("dr_stim_fixed", "dr_stim"), ("exp_decay", "two_phase_decay")}


def list_models():
    return [{"id": k, "name": m["name"], "short": m["short"], "equation": m["equation"],
             "log_x": m["log_x"], "params": m["params"]} for k, m in MODELS.items()]


def custom_model(equation_text: str, initial: dict | None = None) -> dict:
    """Build a model from a user-typed equation (see equation.py)."""
    from .equation import compile_equation
    f, names = compile_equation(equation_text)
    init = {k: float(v) for k, v in (initial or {}).items() if v is not None and str(v).strip() != ""}
    shown = equation_text.strip()
    if not shown.upper().startswith("Y"):
        shown = "Y = " + shown
    return {"name": f"User-defined: {shown}", "short": "", "equation": shown, "params": names, "f": f,
            "guess": lambda x, y: [init.get(n, 1.0) for n in names], "log_x": False}


def fit(x, y, model: str, x_is_log: bool = False, alpha: float = 0.05, curve_points: int = 200,
        fixed: dict | None = None, equation: str | None = None, initial: dict | None = None,
        rout_q: float | None = None, weighting: str = "none") -> dict:
    """Fit a model to (x, y) points. For dose-response models, X is concentration unless
    x_is_log is True (then X is already log10 of concentration).
    fixed: {parameter name: value} to hold parameters constant (constraints), e.g. {"Bottom": 0}.
    weighting: none | 1/Y | 1/Y2 | 1/X | 1/X2. Y weights use the Y of the fitted curve (not the data), found by
    iteratively reweighted least squares; X weights use the X values as entered (concentration)."""
    removed = []
    if rout_q:
        om = rout_mask(x, y, model, x_is_log, fixed, equation, initial, rout_q)
        removed = [{"x": float(a), "y": float(b)} for a, b in zip(np.asarray(x, float)[om], np.asarray(y, float)[om])]
        x, y = list(np.asarray(x, float)[~om]), list(np.asarray(y, float)[~om])
    if model == "custom":
        m = custom_model(equation or "", initial)
    elif model in MODELS:
        m = MODELS[model]
    else:
        raise ValueError(f"Unknown model: {model}")
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    dropped = 0
    if m["log_x"] and not x_is_log:
        pos = x > 0
        dropped = int(np.sum(~pos))
        x, y = np.log10(x[pos]), y[pos]
    names = m["params"]
    fixed = {k: float(v) for k, v in (fixed or {}).items()
             if k in names and v is not None and np.isfinite(float(v))}
    free = [i for i, nm in enumerate(names) if nm not in fixed]
    if not free:
        raise ValueError("Every parameter is fixed, so there is nothing to fit. Leave at least one blank.")
    p = len(free)
    if len(x) <= p:
        raise ValueError(f"This fit has {p} free parameters, so it needs at least {p + 1} points "
                         f"(you have {len(x)}).")
    if np.ptp(x) == 0:
        raise ValueError("All X values are the same.")

    def full(pf):
        vals = [fixed.get(nm) for nm in names]
        for i, v in zip(free, pf):
            vals[i] = v
        return vals

    def f_free(xx, *pf):
        return m["f"](xx, *full(pf))

    guess = m["guess"](x, y)
    p0 = [guess[i] for i in free]
    xu = 10 ** x if (m["log_x"] and not x_is_log) else x
    sigma = None
    if weighting in ("1/X", "1/X2"):
        if np.any(xu == 0):
            raise ValueError("Weighting by 1/X needs every X to be non-zero.")
        sigma = np.abs(xu) ** (0.5 if weighting == "1/X" else 1.0)
    try:
        pfit, pcov = optimize.curve_fit(f_free, x, y, p0=p0, sigma=sigma, maxfev=20000)
        if weighting in ("1/Y", "1/Y2"):
            k = 0.5 if weighting == "1/Y" else 1.0
            for _ in range(50):
                yhat = np.abs(f_free(x, *pfit))
                if np.any(yhat < 1e-300):
                    raise ValueError("Weighting by 1/Y needs the curve to stay away from Y = 0.")
                new, pcov = optimize.curve_fit(f_free, x, y, p0=pfit, sigma=yhat ** k, maxfev=20000)
                done = np.allclose(new, pfit, rtol=1e-9, atol=1e-12)
                pfit = new
                if done:
                    break
            sigma = np.abs(f_free(x, *pfit)) ** k
    except (RuntimeError, ValueError) as e:
        if "Weighting" in str(e):
            raise
        raise ValueError("The fit didn't converge. Check that the data have the expected shape "
                         "for this model, or try a different model.")
    w = np.ones(len(x)) if sigma is None else 1 / np.asarray(sigma) ** 2
    popt = np.array(full(pfit), float)
    if not np.all(np.isfinite(m["f"](x, *popt))):
        raise ValueError("The fitted curve isn't defined at some X values (e.g. log of a negative number). "
                         "Check the equation or the starting values.")
    resid = y - m["f"](x, *popt)
    from .stats import runs_test
    x_user = 10 ** x if (m["log_x"] and not x_is_log) else x  # residual plot uses the X the user entered
    resid_out = {"residuals": {"x": x_user.tolist(), "y": resid.tolist(), "fitted": (y - resid).tolist()}, "runs_test": runs_test(x, resid)}
    ss_res = float(np.sum(w * resid ** 2))
    yw = np.sum(w * y) / np.sum(w)
    ss_tot = float(np.sum(w * (y - yw) ** 2))
    df = len(x) - p
    sy_x = math.sqrt(ss_res / df)
    tcrit = float(stats.t.ppf(1 - alpha / 2, df))
    se_free = np.sqrt(np.clip(np.diag(pcov), 0, None)) if np.all(np.isfinite(pcov)) else np.full(p, np.nan)
    se = {i: s for i, s in zip(free, se_free)}
    params = []
    for i, (name, val) in enumerate(zip(names, popt)):
        if i in se:
            s_ = float(se[i])
            params.append({"name": name, "value": float(val), "se": s_,
                           "ci": [float(val - tcrit * s_), float(val + tcrit * s_)], "fixed": False})
        else:
            params.append({"name": name, "value": float(val), "se": None, "ci": None, "fixed": True})

    derived = []
    if m.get("two_phase"):
        # label the faster component "fast" even if the optimizer found them the other way round
        if params[2]["value"] < params[4]["value"]:
            for a_, b_ in ((1, 3), (2, 4)):
                params[a_]["value"], params[b_]["value"] = params[b_]["value"], params[a_]["value"]
                params[a_]["se"], params[b_]["se"] = params[b_]["se"], params[a_]["se"]
                params[a_]["ci"], params[b_]["ci"] = params[b_]["ci"], params[a_]["ci"]
                params[a_]["fixed"], params[b_]["fixed"] = params[b_]["fixed"], params[a_]["fixed"]
            popt = np.array([q["value"] for q in params])
        for label, q in (("Half-life (fast)", params[2]), ("Half-life (slow)", params[4])):
            k = q["value"]
            derived.append({"name": label, "value": math.log(2) / k if k > 0 else None, "ci": None})
        span = params[1]["value"] + params[3]["value"]
        if span:
            derived.append({"name": "Percent fast", "value": 100 * params[1]["value"] / span, "ci": None})
    if m.get("derived"):
        dname, lname = m["derived"]
        lp = next(q for q in params if q["name"] == lname)
        derived.append({"name": dname, "value": _pow10(lp["value"]),
                        "ci": [_pow10(lp["ci"][0]), _pow10(lp["ci"][1])] if lp["ci"] else None})
    if m.get("halflife") or m.get("doubling"):
        kp = next(q for q in params if q["name"] == "K")
        label = "Half-life" if m.get("halflife") else "Doubling time"
        k = kp["value"]
        ci = None
        if kp["ci"]:
            lo, hi = sorted([kp["ci"][0], kp["ci"][1]])
            ci = [math.log(2) / hi if hi > 0 else None, math.log(2) / lo if lo > 0 else None]
        derived.append({"name": label, "value": math.log(2) / k if k > 0 else None, "ci": ci})
        derived.append({"name": "Tau (1/K)", "value": 1 / k if k else None, "ci": None})

    xs = np.linspace(x.min(), x.max(), curve_points)
    if not m["log_x"] and x.min() >= 0:
        xs = np.linspace(0 if model in ("michaelis",) else x.min(), x.max(), curve_points)
    curve_y = m["f"](xs, *popt)
    n = len(x)
    K = p + 1  # free parameters + residual variance
    aicc = (n * math.log(ss_res / n) + 2 * K + 2 * K * (K + 1) / (n - K - 1)) if ss_res > 0 and n - K - 1 > 0 else None
    return {
        "aicc": aicc,
        "test_name": "Nonlinear regression", "model": model, "model_name": m["name"], "param_names": m["params"],
        "equation": m["equation"], "params": params, "derived": derived,
        "r_squared": 1 - ss_res / ss_tot if ss_tot > 0 else None,
        "sy_x": sy_x, "ss_res": ss_res, "df": df, "n": int(len(x)), "dropped": dropped,
        **({"outliers": removed, "rout_q": rout_q} if rout_q else {}),
        **resid_out, "weighting": weighting,
        "x_is_log": bool(m["log_x"]), "alpha": alpha, "fixed": fixed,
        "points": {"x": x.tolist(), "y": y.tolist()},
        "curve": {"x": xs.tolist(), "y": curve_y.tolist()},
    }


def compare(x, y, model_a: str, model_b: str, x_is_log: bool = False, alpha: float = 0.05,
            fixed: dict | None = None, weighting: str = "none") -> dict:
    """Fit two models to the same data and say which the data support.

    Always reports AICc (works for any pair). For nested pairs (one model is a special
    case of the other) also runs the extra sum-of-squares F test, as Prism does.
    """
    if MODELS[model_a]["log_x"] != MODELS[model_b]["log_x"]:
        raise ValueError("These two models treat X differently (one uses log of X), so they can't be compared.")
    fa = fit(x, y, model_a, x_is_log=x_is_log, alpha=alpha, fixed=fixed, weighting=weighting)
    fb = fit(x, y, model_b, x_is_log=x_is_log, alpha=alpha, fixed=fixed, weighting=weighting)
    out = {"a": model_a, "b": model_b, "name_a": fa["model_name"], "name_b": fb["model_name"],
           "ss_a": fa["ss_res"], "df_a": fa["df"], "ss_b": fb["ss_res"], "df_b": fb["df"],
           "aicc_a": fa["aicc"], "aicc_b": fb["aicc"], "fit_b": fb}
    if fa["aicc"] is not None and fb["aicc"] is not None:
        d = fb["aicc"] - fa["aicc"]
        out["delta_aicc"] = d
        prob_a = 1 / (1 + math.exp(-0.5 * d)) if abs(d) < 700 else (1.0 if d > 0 else 0.0)
        out["prob_a"] = prob_a
        out["aicc_preferred"] = model_a if prob_a >= 0.5 else model_b
    nested = (model_a, model_b) in NESTED or (model_b, model_a) in NESTED
    if nested:
        simple, cplx = (fa, fb) if fa["df"] > fb["df"] else (fb, fa)
        ddf = simple["df"] - cplx["df"]
        if ddf > 0 and cplx["ss_res"] > 0:
            F = ((simple["ss_res"] - cplx["ss_res"]) / ddf) / (cplx["ss_res"] / cplx["df"])
            pval = float(stats.f.sf(max(F, 0.0), ddf, cplx["df"]))
            out["f_test"] = {"F": F, "dfn": ddf, "dfd": cplx["df"], "p": pval,
                             "simple": simple["model"], "complex": cplx["model"],
                             "preferred": cplx["model"] if pval < alpha else simple["model"]}
    return out


def predict(res: dict, xs, x_was_log: bool = False, equation: str | None = None, initial: dict | None = None) -> list[dict]:
    """Y on the fitted curve at each X (X in the units the user entered). Flags X outside the data's range."""
    out = []
    if res.get("model") == "linear":
        lo, hi = min(res["points"]["x"]), max(res["points"]["x"])
        for x in xs:
            out.append({"x": x, "y": float(res["slope"] * x + res["intercept"]), "note": "" if lo <= x <= hi else "outside the data's X range"})
        return out
    model = res["model"]
    mdl = custom_model(equation or "", initial) if model == "custom" else MODELS[model]
    vals = [p["value"] for p in res["params"]]
    lo, hi = min(res["points"]["x"]), max(res["points"]["x"])
    for x in xs:
        xx = x
        if mdl["log_x"] and not x_was_log:
            if x <= 0:
                out.append({"x": x, "y": None, "note": "X must be > 0 for this model"})
                continue
            xx = math.log10(x)
        with np.errstate(all="ignore"):
            y = float(mdl["f"](np.array([xx]), *vals)[0])
        out.append({"x": x, "y": y if np.isfinite(y) else None, "note": "" if lo <= xx <= hi else "outside the data's X range"})
    return out


def interpolate(res: dict, ys, equation: str | None = None, initial: dict | None = None) -> list[dict]:
    """Read unknown samples off a fitted curve: for each Y, find X with f(X) = Y.

    Works for the straight line and every curve model. Only X values inside the range of the
    standards are reported (no extrapolation, as in Prism); X is returned in the units the
    user entered (concentration, not log) for dose-response models.
    """
    out = []
    if res.get("model") == "linear":
        m, b = res["slope"], res["intercept"]
        xs = res["points"]["x"]
        lo, hi = min(xs), max(xs)
        for y in ys:
            x = (y - b) / m if m else None
            ok = x is not None and lo <= x <= hi
            out.append({"y": y, "x": x if ok else None, "note": "" if ok else "outside the standards' range"})
        return out
    model = res["model"]
    mdl = custom_model(equation or "", initial) if model == "custom" else MODELS[model]
    vals = [p["value"] for p in res["params"]]
    f = lambda xx: mdl["f"](xx, *vals)  # noqa: E731
    lo, hi = min(res["points"]["x"]), max(res["points"]["x"])
    grid = np.linspace(lo, hi, 4001)
    with np.errstate(all="ignore"):
        fg = f(grid)
    for y in ys:
        d = fg - y
        idx = np.where(np.sign(d[:-1]) * np.sign(d[1:]) <= 0)[0]
        idx = [i for i in idx if np.isfinite(d[i]) and np.isfinite(d[i + 1])]
        if not idx:
            out.append({"y": y, "x": None, "note": "outside the curve's range"})
            continue
        i = idx[0]
        try:
            root = optimize.brentq(lambda xx: float(f(np.array([xx]))[0]) - y, grid[i], grid[i + 1]) \
                if d[i] != 0 else float(grid[i])
        except ValueError:
            root = float(grid[i])
        note = "more than one X gives this Y; first shown" if len(idx) > 1 and (idx[-1] - idx[0]) > 1 else ""
        x = 10 ** root if res.get("x_is_log") and mdl["log_x"] and not res.get("x_was_log") else root
        out.append({"y": y, "x": float(x), "note": note})
    return out


LINE = {"name": "Straight line", "short": "", "equation": "Y = Slope·X + Intercept", "params": ["Slope", "Intercept"],
        "f": lambda x, m, b: m * x + b,
        "guess": lambda x, y: list(np.polyfit(x, y, 1)) if np.ptp(x) > 0 else [0.0, float(np.mean(y))], "log_x": False}


def _model(model, equation=None, initial=None):
    if model == "linear":
        return LINE
    if model == "custom":
        return custom_model(equation or "", initial)
    if model in MODELS:
        return MODELS[model]
    raise ValueError(f"Unknown model: {model}")


def _pow10(v):
    """10**v that gives inf/0 instead of raising for an ambiguous fit's huge CI limits."""
    try:
        return 10.0 ** v
    except OverflowError:
        return float("inf") if v > 0 else 0.0


def rout_mask(x, y, model, x_is_log=False, fixed=None, equation=None, initial=None, q=0.01) -> np.ndarray:
    """ROUT outliers (see outliers.py) for the points (x, y), as a boolean mask in input order.
    Points the fit would drop anyway (missing, or X <= 0 for log-X models) are never outliers."""
    from .outliers import robust_fit, fdr_outliers
    m = _model(model, equation, initial)
    x = np.asarray(x, float); y = np.asarray(y, float)
    use = np.isfinite(x) & np.isfinite(y)
    if m["log_x"] and not x_is_log:
        use &= np.where(np.isfinite(x), x, -1) > 0
    mask = np.zeros(len(x), bool)
    xx, yy = x[use], y[use]
    if m["log_x"] and not x_is_log:
        xx = np.log10(xx)
    names = m["params"]
    fixed = {k: float(v) for k, v in (fixed or {}).items() if k in names and v is not None and np.isfinite(float(v))}
    free = [i for i, nm in enumerate(names) if nm not in fixed]
    k = len(free)
    if len(xx) <= k + 1 or not free:
        return mask

    def f_free(xv, *pf):
        vals = [fixed.get(nm) for nm in names]
        for i, v in zip(free, pf):
            vals[i] = v
        return m["f"](xv, *vals)

    guess = m["guess"](xx, yy)
    try:
        _, resid, scale = robust_fit(f_free, [guess[i] for i in free], xx, yy)
    except Exception:
        return mask
    mask[np.nonzero(use)[0]] = fdr_outliers(resid, k, q, scale)
    return mask


def _prep_xy(m, x, y, x_is_log):
    x = np.asarray(x, float); y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if m["log_x"] and not x_is_log:
        pos = x > 0
        x, y = np.log10(x[pos]), y[pos]
    return x, y


def _global_fit(m, data, shared_names, fixed, p0_sets):
    """Fit all datasets together. Parameters in shared_names take one value for all datasets;
    the others are fitted separately per dataset. Returns (SS, df, per-dataset parameter values)."""
    names = m["params"]
    free = [n for n in names if n not in fixed]
    shared = [n for n in free if n in shared_names]
    local = [n for n in free if n not in shared_names]
    k = len(data)
    X = np.concatenate([d[0] for d in data]); Y = np.concatenate([d[1] for d in data])
    idx = np.concatenate([np.full(len(d[0]), i) for i, d in enumerate(data)])

    def unpack(theta):
        sv = dict(zip(shared, theta[:len(shared)]))
        rest = theta[len(shared):]
        sets = []
        for i in range(k):
            lv = dict(zip(local, rest[i * len(local):(i + 1) * len(local)]))
            sets.append([fixed.get(n, sv.get(n, lv.get(n))) for n in names])
        return sets

    def f(_, *theta):
        sets = unpack(np.array(theta))
        out = np.empty_like(Y)
        for i in range(k):
            sel = idx == i
            out[sel] = m["f"](X[sel], *sets[i])
        return out

    p0 = [np.mean([p[names.index(n)] for p in p0_sets]) for n in shared]
    for i in range(k):
        p0 += [p0_sets[i][names.index(n)] for n in local]
    theta, _ = optimize.curve_fit(f, X, Y, p0=p0, maxfev=40000)
    ss = float(np.sum((Y - f(X, *theta)) ** 2))
    df = len(Y) - len(theta)
    return ss, df, unpack(theta)


def fit_multi(x, ys, names, model, x_is_log=False, alpha=0.05, fixed=None, compare=None,
              equation=None, initial=None) -> dict:
    """Fit one curve per dataset (each Y column is a separate dataset).
    compare: a parameter name ("is it different between datasets?") or "all" (one curve fits all?)."""
    m = _model(model, equation, initial)
    fixed = {k: float(v) for k, v in (fixed or {}).items() if k in m["params"] and v is not None}
    fits, data, used = [], [], []
    for name, y in zip(names, ys):
        xx = [a for a, b in zip(x, y) if a is not None and b is not None]
        yy = [b for a, b in zip(x, y) if a is not None and b is not None]
        if len(xx) < 2:
            continue
        try:
            if model == "linear":
                from .stats import linear_regression
                r = linear_regression(xx, yy, alpha=alpha)
                r["params"] = [{"name": "Slope", "value": r["slope"], "se": r["slope_se"], "ci": r["slope_ci"], "fixed": False},
                               {"name": "Intercept", "value": r["intercept"], "se": r["intercept_se"], "ci": r["intercept_ci"], "fixed": False}]
                r["derived"] = []; r["ss_res"] = r["sy_x"] ** 2 * r["df"]; r["model"] = "linear"
                r["curve"] = r["line"]
            else:
                r = fit(xx, yy, model, x_is_log=x_is_log, alpha=alpha, fixed=fixed, equation=equation, initial=initial)
        except ValueError as e:
            fits.append({"name": name, "error": str(e)}); continue
        r["name"] = name
        fits.append(r); data.append(_prep_xy(m, xx, yy, x_is_log)); used.append(r)
    if not used:
        raise ValueError("Enter X values and at least one Y column with 3 or more points per curve.")
    res = {"test_name": "Curve comparison" if len(used) > 1 else "Nonlinear regression", "multi": True, "model": model,
           "model_name": m["name"], "equation": m["equation"], "fits": fits, "alpha": alpha,
           "x_is_log": bool(m["log_x"]), "param_names": m["params"]}
    if compare and len(used) >= 2:
        p0_sets = [[p["value"] for p in r["params"]] for r in used]
        ss_sep = float(sum(r["ss_res"] for r in used)); df_sep = int(sum(r["df"] for r in used))
        free = [n for n in m["params"] if n not in fixed]
        shared = free if compare == "all" else [compare]
        if compare != "all" and compare not in free:
            raise ValueError(f"{compare} isn't a fitted parameter of this model.")
        try:
            ss_sh, df_sh, sets = _global_fit(m, data, shared, fixed, p0_sets)
        except (RuntimeError, ValueError):
            res["comparison"] = {"error": "The shared fit didn't converge."}
            return res
        ddf = df_sh - df_sep
        F = ((ss_sh - ss_sep) / ddf) / (ss_sep / df_sep) if ddf > 0 and ss_sep > 0 else None
        p = float(stats.f.sf(max(F, 0.0), ddf, df_sep)) if F is not None else None
        res["comparison"] = {"param": compare, "F": F, "dfn": ddf, "dfd": df_sep, "p": p,
                             "ss_separate": ss_sep, "ss_shared": ss_sh, "different": p is not None and p < alpha,
                             "shared_value": sets[0][m["params"].index(compare)] if compare != "all" else None}
    return res
