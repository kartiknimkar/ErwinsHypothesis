import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app import anova2
from app.main import app

approx = lambda v, rel=1e-6: pytest.approx(v, rel=rel)  # noqa: E731


def test_multiple_t_matches_scipy_and_bh():
    smm = pytest.importorskip("statsmodels.stats.multitest")
    rng = np.random.default_rng(5)
    labels, a, b, ref = [], [], [], []
    for g in range(12):
        va = rng.normal(10, 1, 4); vb = rng.normal(10 + (3 if g < 3 else 0), 1, 4)
        for x, y in zip(va, vb):
            labels.append(f"Gene{g}"); a.append(x); b.append(y)
        ref.append(sps.ttest_ind(vb, va, equal_var=False).pvalue)
    r = anova2.multiple_t(labels, a, b, ("Ctrl", "KO"))
    ps = [it["p"] for it in r["items"]]
    assert ps == [approx(p) for p in ref]
    assert [it["q"] for it in r["items"]] == [approx(q) for q in smm.multipletests(ref, method="fdr_bh")[1]]
    assert r["n_discoveries"] >= 2


def test_skips_and_errors():
    r = anova2.multiple_t(["A", "A", "B", "B", "C"], [1, 2, 5, 6, 1], [3, 4, 9, 9.5, 2], ("x", "y"))
    assert r["skipped"] == ["C"] and len(r["items"]) == 2
    with pytest.raises(ValueError):
        anova2.multiple_t(["A"], [1], [2])
    c = TestClient(app)
    assert c.post("/api/multit", json={"rows": ["A", "A"], "columns": [[1, 2], [3, 4], [5, 6]], "names": ["a", "b", "c"]}).status_code == 400


def test_fdr_methods_match_statsmodels():
    import numpy as np
    import pytest
    mt = pytest.importorskip("statsmodels.stats.multitest")
    from app import anova2
    rng = np.random.default_rng(4)
    for _ in range(20):
        p = np.concatenate([rng.uniform(0, 0.01, rng.integers(1, 8)), rng.uniform(0, 1, 25)])
        adj, disc = anova2.fdr_adjust(p, "bky", 0.05)
        rej, padj, *_ = mt.fdrcorrection_twostage(p, alpha=0.05, method="bky", maxiter=1)
        assert (disc == rej).all() and np.allclose(adj, padj)
        a2, d2 = anova2.fdr_adjust(p, "bh", 0.05)
        assert np.allclose(a2, mt.multipletests(p, method="fdr_bh")[1])
        a3, _ = anova2.fdr_adjust(p, "holm", 0.05)
        assert np.allclose(a3, mt.multipletests(p, method="holm-sidak")[1])
