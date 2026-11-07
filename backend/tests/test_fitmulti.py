import math

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import curvefit
from app.main import app

approx = lambda v, rel=1e-5: pytest.approx(v, rel=rel)  # noqa: E731
CONC = np.array([0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100])


def curve(ic50, seed, hill=-1.0):
    rng = np.random.default_rng(seed)
    return 5 + 95 / (1 + 10 ** ((math.log10(ic50) - np.log10(CONC)) * hill)) + rng.normal(0, 2.5, len(CONC))


def test_ic50_comparison_detects_difference_or_not():
    same = curvefit.fit_multi(list(CONC), [list(curve(1, 1)), list(curve(1, 2))], ["A", "B"], "dr_inhibit", compare="LogIC50")
    diff = curvefit.fit_multi(list(CONC), [list(curve(1, 3)), list(curve(10, 4))], ["A", "B"], "dr_inhibit", compare="LogIC50")
    assert same["comparison"]["p"] > 0.05 and diff["comparison"]["p"] < 0.0001
    assert diff["comparison"]["dfn"] == 1 and diff["comparison"]["dfd"] == 2 * (9 - 4)
    ic = [f["derived"][0]["value"] for f in diff["fits"]]
    assert ic[0] == approx(1, 0.3) and ic[1] == approx(10, 0.3)


def test_slope_comparison_equals_ancova_interaction():
    smf = pytest.importorskip("statsmodels.formula.api")
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(9)
    x = np.arange(1, 11, dtype=float)
    ya = 2 * x + 1 + rng.normal(0, 1, 10); yb = 2.6 * x + 0.5 + rng.normal(0, 1, 10)
    r = curvefit.fit_multi(list(x), [list(ya), list(yb)], ["A", "B"], "linear", compare="Slope")
    df = pd.DataFrame({"x": np.r_[x, x], "y": np.r_[ya, yb], "g": ["A"] * 10 + ["B"] * 10})
    ref = sm.stats.anova_lm(smf.ols("y ~ x * g", data=df).fit(), typ=2)
    assert r["comparison"]["F"] == approx(ref.loc["x:g", "F"], 1e-6)
    assert r["comparison"]["p"] == approx(ref.loc["x:g", "PR(>F)"], 1e-5)
    # "all": one line for both datasets vs two lines
    allr = curvefit.fit_multi(list(x), [list(ya), list(yb)], ["A", "B"], "linear", compare="all")
    assert allr["comparison"]["dfn"] == 2 and allr["comparison"]["different"]


def test_endpoint_and_errors():
    c = TestClient(app)
    r = c.post("/api/fitmulti", json={"x": list(CONC), "ys": [list(curve(1, 5)), list(curve(5, 6))], "names": ["A", "B"],
                                     "model": "dr_inhibit", "compare": "LogIC50"}).json()
    assert len(r["fits"]) == 2 and r["comparison"]["p"] < 0.05
    bad = c.post("/api/fitmulti", json={"x": [1, 2], "ys": [[1, None]], "names": ["A"], "model": "linear"})
    assert bad.status_code == 400
