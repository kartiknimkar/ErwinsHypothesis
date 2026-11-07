import numpy as np
import pytest

from app import multivar

approx = lambda v, rel=1e-6: pytest.approx(v, rel=rel)  # noqa: E731
rng = np.random.default_rng(2)
A = rng.normal(0, 1, 40); B = A + rng.normal(0, 0.3, 40); C = rng.normal(5, 2, 40); D = -A + C / 2 + rng.normal(0, 0.5, 40)


def test_pca_eigenvalues_match_correlation_matrix():
    X = np.column_stack([A, B, C, D])
    r = multivar.pca([list(A), list(B), list(C), list(D)], ["A", "B", "C", "D"])
    ev = np.sort(np.linalg.eigvalsh(np.corrcoef(X, rowvar=False)))[::-1]
    assert r["eigenvalues"] == [approx(v) for v in ev]
    assert r["cumulative_pct"][-1] == approx(100.0)
    assert sum(r["variance_pct"]) == approx(100.0)
    # scores have variance equal to eigenvalues and are uncorrelated
    S = np.array(r["scores"])
    assert np.var(S[:, 0], ddof=1) == approx(ev[0])
    assert abs(np.corrcoef(S[:, 0], S[:, 1])[0, 1]) < 1e-8
    # loadings = correlation of variable with component
    assert r["loadings"][0][0] == approx(np.corrcoef(X[:, 0], S[:, 0])[0, 1], 1e-6)


def test_pca_errors_and_missing():
    with pytest.raises(ValueError):
        multivar.pca([[1, 2, 3], [1, 1, 1]], ["a", "b"])
    r = multivar.pca([list(A) + [None], list(B) + [1.0]], ["A", "B"])
    assert r["n"] == 40 and r["dropped"] == 1
