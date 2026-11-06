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
}


def list_models():
    return [{"id": k, "name": m["name"], "short": m["short"], "equation": m["equation"],
             "log_x": m["log_x"]} for k, m in MODELS.items()]


def fit(x, y, model: str, x_is_log: bool = False, alpha: float = 0.05, curve_points: int = 200) -> dict:
    """Fit a model to (x, y) points. For dose-response models, X is concentration unless
    x_is_log is True (then X is already log10 of concentration)."""
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
    p = len(m["params"])
    if len(x) <= p:
        raise ValueError(f"This model has {p} parameters, so it needs at least {p + 1} points "
                         f"(you have {len(x)}).")
    if np.ptp(x) == 0:
        raise ValueError("All X values are the same.")

    p0 = m["guess"](x, y)
    try:
        popt, pcov = optimize.curve_fit(m["f"], x, y, p0=p0, maxfev=20000)
    except (RuntimeError, ValueError):
        raise ValueError("The fit didn't converge. Check that the data have the expected shape "
                         "for this model, or try a different model.")
    resid = y - m["f"](x, *popt)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    df = len(x) - p
    sy_x = math.sqrt(ss_res / df)
    tcrit = float(stats.t.ppf(1 - alpha / 2, df))
    se = np.sqrt(np.clip(np.diag(pcov), 0, None)) if np.all(np.isfinite(pcov)) else np.full(p, np.nan)
    params = []
    for name, val, s in zip(m["params"], popt, se):
        params.append({"name": name, "value": float(val), "se": float(s),
                       "ci": [float(val - tcrit * s), float(val + tcrit * s)]})

    derived = []
    if m.get("derived"):
        dname, lname = m["derived"]
        lp = next(q for q in params if q["name"] == lname)
        derived.append({"name": dname, "value": 10 ** lp["value"],
                        "ci": [10 ** lp["ci"][0], 10 ** lp["ci"][1]]})
    if m.get("halflife") or m.get("doubling"):
        kp = next(q for q in params if q["name"] == "K")
        label = "Half-life" if m.get("halflife") else "Doubling time"
        k = kp["value"]
        lo, hi = sorted([kp["ci"][0], kp["ci"][1]])
        ci = [math.log(2) / hi if hi > 0 else None, math.log(2) / lo if lo > 0 else None]
        derived.append({"name": label, "value": math.log(2) / k if k > 0 else None, "ci": ci})
        derived.append({"name": "Tau (1/K)", "value": 1 / k if k else None, "ci": None})

    xs = np.linspace(x.min(), x.max(), curve_points)
    if not m["log_x"] and x.min() >= 0:
        xs = np.linspace(0 if model in ("michaelis",) else x.min(), x.max(), curve_points)
    curve_y = m["f"](xs, *popt)
    return {
        "test_name": "Nonlinear regression", "model": model, "model_name": m["name"],
        "equation": m["equation"], "params": params, "derived": derived,
        "r_squared": 1 - ss_res / ss_tot if ss_tot > 0 else None,
        "sy_x": sy_x, "ss_res": ss_res, "df": df, "n": int(len(x)), "dropped": dropped,
        "x_is_log": bool(m["log_x"]), "alpha": alpha,
        "points": {"x": x.tolist(), "y": y.tolist()},
        "curve": {"x": xs.tolist(), "y": curve_y.tolist()},
    }
