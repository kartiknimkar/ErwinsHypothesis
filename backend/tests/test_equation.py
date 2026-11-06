"""User-defined equations: safe parsing and correct fitting."""
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import curvefit, equation
from app.main import app

approx = lambda v, rel=1e-4: pytest.approx(v, rel=rel)  # noqa: E731


def test_parse_parameters_and_syntax():
    _, p = equation.parse("Y = A*exp(-K*X) + C")
    assert p == ["A", "K", "C"]
    _, p = equation.parse("Top/(1+(X/EC50)^Hill)")
    assert p == ["Top", "EC50", "Hill"]
    f, names = equation.compile_equation("Y = a*X^2 + b*X + c + 0*pi")
    assert f(np.array([2.0]), 1, 2, 3)[0] == approx(11)


@pytest.mark.parametrize("bad", [
    "__import__('os').system('x')", "X.__class__", "open('f')", "Y = [1,2]", "Y = 'a'",
    "Y = lambda: 1", "Y = A if X else B", "Y = exp", "Y = 2*X", "Z = A*X", "", "Y = (A*X",
    "Y = X[0]*A", "Y = A*X; import os",
])
def test_rejects_unsafe_or_invalid(bad):
    with pytest.raises(equation.EquationError):
        equation.parse(bad)


def test_custom_fit_matches_builtin():
    t = np.linspace(0, 10, 15)
    y = 90 * np.exp(-0.3 * t) + 10 + np.random.default_rng(3).normal(0, 1, len(t))
    built = curvefit.fit(t, y, "exp_decay")
    cust = curvefit.fit(t, y, "custom", equation="Y = (Y0 - P)*exp(-K*X) + P", initial={"Y0": 100, "P": 5, "K": 0.5})
    b = {q["name"]: q for q in built["params"]}
    c = {q["name"]: q for q in cust["params"]}
    assert c["K"]["value"] == approx(b["K"]["value"]) and c["K"]["se"] == approx(b["K"]["se"], 1e-3)
    assert cust["r_squared"] == approx(built["r_squared"])
    # constraints work on custom equations too
    fx = curvefit.fit(t, y, "custom", equation="Y = (Y0 - P)*exp(-K*X) + P", fixed={"P": 10})
    assert fx["df"] == len(t) - 2


def test_custom_fit_errors_and_endpoints():
    with pytest.raises(ValueError):
        curvefit.fit([1, 2, 3, 4], [1, 2, 3, 4], "custom", equation="Y = os.system")
    c = TestClient(app)
    assert c.post("/api/equation", json={"equation": "Y = A*X + B"}).json() == {"ok": True, "params": ["A", "B"]}
    assert c.post("/api/equation", json={"equation": "Y = A*"}).json()["ok"] is False
    r = c.post("/api/fit", json={"x": [1, 2, 3, 4, 5], "ys": [[2.1, 3.9, 6.2, 7.8, 10.1]], "model": "custom",
                                 "equation": "Y = M*X + B"}).json()
    assert {q["name"]: q["value"] for q in r["params"]}["M"] == approx(1.99, 1e-2)
