"""New curve models and model comparison."""
import math

import numpy as np
import pytest
from scipy import stats as sps

from app import curvefit

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731
CONC = np.repeat([0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100], 3)


def dr(conc, hill, noise=0, seed=0):
    y = 5 + 95 / (1 + 10 ** ((0 - np.log10(conc)) * hill))
    return y + np.random.default_rng(seed).normal(0, noise, len(conc)) if noise else y


def p(r):
    return {q["name"]: q["value"] for q in r["params"]}


def test_new_models_recover_parameters():
    r = curvefit.fit(CONC, dr(CONC, -1), "dr_inhibit_fixed")
    assert r["derived"][0]["value"] == approx(1.0)
    x = np.linspace(-5, 5, 25)
    assert p(curvefit.fit(x, 3 * np.exp(-0.5 * ((x - 1.2) / 1.7) ** 2), "gaussian")) == {
        "Amplitude": approx(3), "Mean": approx(1.2), "SD": approx(1.7)}
    v = np.linspace(-80, 20, 21)
    b = p(curvefit.fit(v, 0.1 + 0.9 / (1 + np.exp((-30 - v) / 6)), "boltzmann"))
    assert b["V50"] == approx(-30) and b["Slope"] == approx(6)
    t = np.linspace(0, 20, 30)
    r = curvefit.fit(t, 2 + 60 * np.exp(-1.5 * t) + 30 * np.exp(-0.1 * t), "two_phase_decay")
    q = p(r)
    assert q["Kfast"] == approx(1.5, 1e-3) and q["Kslow"] == approx(0.1, 1e-3) and q["SpanFast"] == approx(60, 1e-3)
    assert next(d for d in r["derived"] if d["name"] == "Half-life (slow)")["value"] == approx(math.log(2) / 0.1, 1e-3)


def test_aicc_formula():
    r = curvefit.fit(CONC, dr(CONC, -1, noise=3), "dr_inhibit")
    n, K = r["n"], 5
    assert r["aicc"] == approx(n * math.log(r["ss_res"] / n) + 2 * K + 2 * K * (K + 1) / (n - K - 1))


def test_compare_prefers_right_model():
    # true Hill slope = -1: the simpler standard-slope model should be kept
    c = curvefit.compare(CONC, dr(CONC, -1, noise=3, seed=1), "dr_inhibit_fixed", "dr_inhibit")
    ft = c["f_test"]
    assert ft["preferred"] == "dr_inhibit_fixed"
    F = ((c["ss_a"] - c["ss_b"]) / (c["df_a"] - c["df_b"])) / (c["ss_b"] / c["df_b"])
    assert ft["F"] == approx(F) and ft["p"] == approx(sps.f.sf(F, 1, c["df_b"]))
    # true Hill slope = -2.5: variable slope wins on both criteria
    c = curvefit.compare(CONC, dr(CONC, -2.5, noise=3, seed=2), "dr_inhibit_fixed", "dr_inhibit")
    assert c["f_test"]["preferred"] == "dr_inhibit" and c["aicc_preferred"] == "dr_inhibit"
    assert 0 <= c["prob_a"] <= 1
    # non-nested pair: AICc only; mismatched X handling is refused
    t = np.linspace(0, 10, 15)
    c = curvefit.compare(t, 5 * np.exp(-0.4 * t) + 1, "exp_decay", "assoc")
    assert "f_test" not in c and c["aicc_preferred"] == "exp_decay"
    with pytest.raises(ValueError):
        curvefit.compare(CONC, dr(CONC, -1), "dr_inhibit", "michaelis")


def test_constraints_match_reduced_model():
    from scipy import optimize
    y = dr(CONC, -1.3, noise=3, seed=4)
    r = curvefit.fit(CONC, y, "dr_inhibit", fixed={"Bottom": 0, "Top": 100})
    q = {x["name"]: x for x in r["params"]}
    assert q["Bottom"]["fixed"] and q["Bottom"]["value"] == 0 and q["Bottom"]["ci"] is None
    assert r["df"] == len(CONC) - 2
    # same fit done by hand with only LogIC50 and HillSlope free
    f = lambda x, l, h: 0 + 100 / (1 + 10 ** ((l - x) * h))  # noqa: E731
    popt, pcov = optimize.curve_fit(f, np.log10(CONC), y, p0=[0, -1])
    assert q["LogIC50"]["value"] == approx(popt[0], 1e-5) and q["HillSlope"]["se"] == approx(math.sqrt(pcov[1, 1]), 1e-3)
    # ignores unknown names; refuses fixing everything
    assert curvefit.fit(CONC, y, "dr_inhibit", fixed={"Nope": 3})["df"] == len(CONC) - 4
    with pytest.raises(ValueError):
        curvefit.fit(CONC, y, "dr_inhibit_fixed", fixed={"Bottom": 0, "Top": 100, "LogIC50": 0})
    # fixing K: no CI for half-life, but a value
    t = np.linspace(0, 10, 12)
    r = curvefit.fit(t, 90 * np.exp(-0.3 * t) + 10, "exp_decay", fixed={"K": 0.3})
    hl = next(d for d in r["derived"] if d["name"] == "Half-life")
    assert hl["value"] == approx(math.log(2) / 0.3) and hl["ci"] is None
