import numpy as np
from scipy import stats as ss

from app import stats


def test_smm_large_df_is_sidak():
    for m in (2, 3, 6):
        c = ss.norm.ppf((1 + 0.95 ** (1 / m)) / 2)
        assert abs(stats._smm_cdf(c, m, 1e6) - 0.95) < 1e-9
        assert abs(stats._smm_cdf(c, m, 5000) - 0.95) < 2e-3


def test_smm_matches_simulation():
    rng = np.random.default_rng(0)
    m, df, n = 3, 8, 400_000
    z = np.abs(rng.standard_normal((n, m))).max(axis=1)
    s = np.sqrt(rng.chisquare(df, n) / df)
    for c in (2.0, 3.0):
        assert abs(stats._smm_cdf(c, m, df) - np.mean(z / s <= c)) < 3e-3


def test_t3_in_welch_anova():
    G = [[10.2, 11.5, 9.8, 12.1, 10.9, 11.3], [13.4, 18.8, 10.9, 17.2, 14.1, 11.7], [18.2, 17.1, 19.5, 16.8, 18.9, 17.6]]
    r = stats.one_way_anova(G, ["A", "B", "C"], kind="welch", posthoc="t3")
    assert r["posthoc"] == "t3" and len(r["comparisons"]) == 3
    c = r["comparisons"][0]
    # T3 is never less conservative than an uncorrected Welch t test, and P stays within Bonferroni
    welch = ss.ttest_ind(G[0], G[1], equal_var=False).pvalue
    assert welch <= c["p"] <= min(1, 3 * welch) + 1e-9
    gh = stats.one_way_anova(G, ["A", "B", "C"], kind="welch")
    assert gh["posthoc_name"].startswith("Games-Howell")
