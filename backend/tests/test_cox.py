import numpy as np
import pytest

from app import multivar


def _data(seed=2, n=80, ties=False):
    rng = np.random.default_rng(seed)
    age = rng.normal(60, 10, n)
    treat = rng.integers(0, 2, n).astype(float)
    hazard = np.exp(0.04 * (age - 60) - 0.7 * treat)
    t = rng.exponential(10 / hazard)
    c = rng.exponential(15, n)
    T = np.minimum(t, c)
    if ties:
        T = np.ceil(T)
    E = (t <= c).astype(float)
    return T, E, age, treat


@pytest.mark.parametrize("ties", [False, True])
def test_cox_matches_lifelines(ties):
    lifelines = pytest.importorskip("lifelines")
    import pandas as pd
    T, E, age, treat = _data(ties=ties)
    r = multivar.cox(T.tolist(), E.tolist(), [age.tolist(), treat.tolist()], ["Age", "Treated"])
    df = pd.DataFrame({"T": T, "E": E, "Age": age, "Treated": treat})
    ref = lifelines.CoxPHFitter().fit(df, "T", "E")  # Efron ties (lifelines default)
    # lifelines stops at a looser convergence tolerance; our optimum has an equal or higher likelihood
    assert r["loglik"] >= ref.log_likelihood_ - 1e-9
    for c in r["coefs"]:
        assert np.isclose(c["estimate"], ref.params_[c["name"]], rtol=1e-4, atol=1e-6)
        assert np.isclose(c["se"], ref.standard_errors_[c["name"]], rtol=1e-4)
        assert np.isclose(c["p"], ref.summary.loc[c["name"], "p"], rtol=1e-3, atol=1e-12)
    assert np.isclose(r["loglik"], ref.log_likelihood_, rtol=1e-8)
    lr = ref.log_likelihood_ratio_test()
    assert np.isclose(r["lr_chi2"], lr.test_statistic, rtol=1e-5)
    assert np.isclose(r["concordance"], ref.concordance_index_, rtol=1e-6)


def test_cox_input_checks():
    with pytest.raises(ValueError):
        multivar.cox([1, 2, 3], [1, 2, 0], [[1, 2, 3]], ["x"])
    with pytest.raises(ValueError):
        multivar.cox([1, 2, 3], [0, 0, 1], [[1, 2, 3]], ["x"])
