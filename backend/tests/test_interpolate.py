"""Reading unknown samples off a standard curve."""
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import curvefit, stats
from app.main import app

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731


def test_linear():
    r = stats.linear_regression([0, 5, 10, 20, 40], [0.02, 0.11, 0.21, 0.39, 0.83])
    r["model"] = "linear"
    out = curvefit.interpolate(r, [0.5, 5.0])
    assert out[0]["x"] == approx((0.5 - r["intercept"]) / r["slope"])
    assert out[1]["x"] is None and "range" in out[1]["note"]


def test_four_pl_recovers_concentration():
    conc = np.array([0.1, 0.3, 1, 3, 10, 30, 100])
    f = lambda c: 2 + (98) / (1 + 10 ** ((math.log10(5) - np.log10(c)) * 1.3))  # noqa: E731
    r = curvefit.fit(conc, f(conc), "dr_stim")
    r["x_was_log"] = False
    out = curvefit.interpolate(r, [float(f(np.array([2.0]))[0]), float(f(np.array([42.0]))[0]), 150.0])
    assert out[0]["x"] == approx(2.0, 1e-4) and out[1]["x"] == approx(42.0, 1e-4)
    assert out[2]["x"] is None


def test_custom_and_log_input():
    x = np.linspace(0, 10, 11)
    r = curvefit.fit(x, 3 * x ** 2 + 1, "custom", equation="Y = a*X^2 + b")
    assert curvefit.interpolate(r, [76.0], equation="Y = a*X^2 + b")[0]["x"] == approx(5.0)
    lx = np.log10([0.1, 1, 10, 100, 1000])
    r = curvefit.fit(lx, 100 / (1 + 10 ** ((1 - lx) * 1)), "dr_stim", x_is_log=True)
    r["x_was_log"] = True
    assert curvefit.interpolate(r, [50.0])[0]["x"] == approx(1.0, 1e-4)  # stays in log units


def test_endpoint_blank_x_rows_are_unknowns():
    c = TestClient(app)
    x = [0, 5, 10, 20, 40, None, ""]
    ys = [[0.02, 0.11, 0.21, 0.39, 0.83, 0.30, 0.6], [None, None, None, None, None, 0.32, None]]
    r = c.post("/api/fit", json={"x": x, "ys": ys, "model": "linear"}).json()
    assert r["n"] == 5
    u = r["unknowns"]
    assert [q["row"] for q in u] == [6, 7] and u[0]["y"] == approx(0.31) and u[0]["n"] == 2
    assert u[0]["x"] == approx((0.31 - r["intercept"]) / r["slope"])


def test_predict_y_for_x_without_y():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    x = [1, 2, 3, 4, 5, 2.5, 10]
    y = [2.1, 3.9, 6.2, 8.0, 9.8, None, None]
    r = c.post("/api/fit", json={"x": x, "ys": [y], "model": "linear"}).json()
    pred = {p["x"]: p for p in r["predicted"]}
    assert abs(pred[2.5]["y"] - (r["slope"] * 2.5 + r["intercept"])) < 1e-9 and pred[2.5]["note"] == ""
    assert pred[10]["note"] != ""
    conc = [0.01, 0.1, 1, 10, 100, 0.5]
    resp = [98, 90, 50, 10, 3, None]
    d = c.post("/api/fit", json={"x": conc, "ys": [resp], "model": "dr_inhibit"}).json()
    p = d["predicted"][0]
    assert p["x"] == 0.5 and 50 < p["y"] < 90
