import numpy as np
from scipy import optimize

from app import curvefit

CONC = [0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100] * 2
RESP = [98, 96, 92, 80, 52, 30, 13, 7, 6, 101, 99, 88, 76, 55, 27, 15, 8, 5]


def _f(x, b, t, l, h):
    return b + (t - b) / (1 + 10 ** ((l - x) * h))


def test_x_weighting_equals_curve_fit_sigma():
    r = curvefit.fit(CONC, RESP, "dr_inhibit", weighting="1/X2")
    lx = np.log10(CONC)
    ref, _ = optimize.curve_fit(_f, lx, RESP, p0=[5, 100, 0, -1], sigma=np.array(CONC, float), maxfev=20000)
    vals = {p["name"]: p["value"] for p in r["params"]}
    assert np.allclose([vals["Bottom"], vals["Top"], vals["LogIC50"], vals["HillSlope"]], ref, rtol=1e-5, atol=1e-6)


def test_y_weighting_is_a_fixed_point_with_curve_weights():
    r = curvefit.fit(CONC, RESP, "dr_inhibit", weighting="1/Y2")
    v = [next(p["value"] for p in r["params"] if p["name"] == n) for n in ("Bottom", "Top", "LogIC50", "HillSlope")]
    lx = np.log10(CONC)
    sigma = np.abs(_f(lx, *v))
    again, _ = optimize.curve_fit(_f, lx, RESP, p0=v, sigma=sigma, maxfev=20000)
    assert np.allclose(again, v, rtol=1e-6, atol=1e-8)
    unweighted = curvefit.fit(CONC, RESP, "dr_inhibit")
    assert r["weighting"] == "1/Y2" and r["ss_res"] != unweighted["ss_res"]
