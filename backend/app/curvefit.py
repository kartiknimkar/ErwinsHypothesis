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


def fit(x, y, model: str, x_is_log: bool = False, alpha: float = 0.05, curve_points: int = 200,
        fixed: dict | None = None) -> dict:
    """Fit a model to (x, y) points. For dose-response models, X is concentration unless
    x_is_log is True (then X is already log10 of concentration).
    fixed: {parameter name: value} to hold parameters constant (constraints), e.g. {"Bottom": 0}."""
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")
    m = MODELS[model]
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
    try:
        pfit, pcov = optimize.curve_fit(f_free, x, y, p0=p0, maxfev=20000)
    except (RuntimeError, ValueError):
        raise ValueError("The fit didn't converge. Check that the data have the expected shape "
                         "for this model, or try a different model.")
    popt = np.array(full(pfit), float)
    resid = y - m["f"](x, *popt)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
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
        derived.append({"name": dname, "value": 10 ** lp["value"],
                        "ci": [10 ** lp["ci"][0], 10 ** lp["ci"][1]] if lp["ci"] else None})
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
        "test_name": "Nonlinear regression", "model": model, "model_name": m["name"],
        "equation": m["equation"], "params": params, "derived": derived,
        "r_squared": 1 - ss_res / ss_tot if ss_tot > 0 else None,
        "sy_x": sy_x, "ss_res": ss_res, "df": df, "n": int(len(x)), "dropped": dropped,
        "x_is_log": bool(m["log_x"]), "alpha": alpha, "fixed": fixed,
        "points": {"x": x.tolist(), "y": y.tolist()},
        "curve": {"x": xs.tolist(), "y": curve_y.tolist()},
    }


def compare(x, y, model_a: str, model_b: str, x_is_log: bool = False, alpha: float = 0.05,
            fixed: dict | None = None) -> dict:
    """Fit two models to the same data and say which the data support.

    Always reports AICc (works for any pair). For nested pairs (one model is a special
    case of the other) also runs the extra sum-of-squares F test, as Prism does.
    """
    if MODELS[model_a]["log_x"] != MODELS[model_b]["log_x"]:
        raise ValueError("These two models treat X differently (one uses log of X), so they can't be compared.")
    fa = fit(x, y, model_a, x_is_log=x_is_log, alpha=alpha, fixed=fixed)
    fb = fit(x, y, model_b, x_is_log=x_is_log, alpha=alpha, fixed=fixed)
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
