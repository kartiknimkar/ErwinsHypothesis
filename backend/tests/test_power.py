import numpy as np
import pytest

from app import power


def test_t_tests_match_statsmodels():
    sp = pytest.importorskip("statsmodels.stats.power")
    r = power.analyze("unpaired", power=0.8, difference=5, sd=10)
    ref = sp.TTestIndPower().solve_power(effect_size=0.5, power=0.8, alpha=0.05)
    assert r["n"] == int(np.ceil(ref)) and np.isclose(r["n_exact"], ref, rtol=1e-4)
    p = power.analyze("unpaired", n=20, effect=0.5)
    assert np.isclose(p["power"], sp.TTestIndPower().power(0.5, 20, 0.05), rtol=1e-6)
    pr = power.analyze("paired", power=0.9, effect=0.4)
    assert np.isclose(pr["n_exact"], sp.TTestPower().solve_power(effect_size=0.4, power=0.9, alpha=0.05), rtol=1e-4)


def test_anova_matches_statsmodels():
    sp = pytest.importorskip("statsmodels.stats.power")
    r = power.analyze("anova", n=20, effect=0.25, k=4)
    ref = sp.FTestAnovaPower().power(effect_size=0.25, nobs=80, alpha=0.05, k_groups=4)
    assert np.isclose(r["power"], ref, rtol=1e-6)


def test_proportions_textbook():
    r = power.analyze("proportions", power=0.8, p1=0.3, p2=0.5)
    assert r["n"] == 93  # Fleiss formula without continuity correction
    with pytest.raises(ValueError):
        power.analyze("proportions", power=0.8, p1=0.3, p2=0.3)
