"""Known-answer tests for experiments/metrics_lib.py.

WHY EVERY EXPECTATION IS WORKED OUT IN ADVANCE
    A metric never crashes. It returns a number, and a wrong number is
    believable. Feeding a function data whose correct answer you already know
    is the only way to catch that. Running the code and recording whatever it
    printed would prove only that the code is deterministic.

    This project lost six months to exactly that failure: a headline metric
    returned 0.0 on perfect input for its entire existence, and nothing
    noticed, because 0.0 is a plausible number.

IF ANY TEST HERE FAILS, every number that function would ever produce is
worthless. Stop; do not work around it.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.metrics_lib import (
    N_BOOT, SEED, auroc, auroc_bootstrap_ci, brier, coverage_at_risk, ece,
    ndcg_at_k, normalise_section, paired_bootstrap_auroc_diff, platt_scale,
    precision_at_k, recall_at_k, reciprocal_rank, reliability_bins,
    risk_coverage_curve, same_section, wilson,
)


class TestAuroc:
    def test_perfectly_separable_is_one(self):
        # every positive scores above every negative -> perfect ranking
        scores = [0.9, 0.8, 0.7, 0.3, 0.2, 0.1]
        labels = [1, 1, 1, 0, 0, 0]
        assert auroc(scores, labels) == 1.0

    def test_perfectly_inverted_is_zero(self):
        assert auroc([0.1, 0.2, 0.3, 0.7, 0.8, 0.9], [1, 1, 1, 0, 0, 0]) == 0.0

    def test_random_labels_is_half(self):
        rng = np.random.default_rng(SEED)
        s = rng.random(4000)
        y = rng.integers(0, 2, 4000)
        assert abs(auroc(s, y) - 0.5) < 0.05

    def test_all_tied_scores_is_exactly_half(self):
        # no information at all -- every pair is a tie, counted as 0.5
        assert auroc([0.5] * 8, [1, 1, 1, 1, 0, 0, 0, 0]) == 0.5

    def test_single_class_is_nan(self):
        assert np.isnan(auroc([0.1, 0.9], [1, 1]))

    def test_bootstrap_ci_brackets_the_point(self):
        rng = np.random.default_rng(SEED)
        s = np.concatenate([rng.normal(1, 1, 300), rng.normal(0, 1, 300)])
        y = np.array([1] * 300 + [0] * 300)
        point, lo, hi = auroc_bootstrap_ci(s, y, n_boot=400, seed=SEED)
        assert lo <= point <= hi
        assert 0.0 <= lo < hi <= 1.0


class TestPairedBootstrap:
    def test_identical_inputs_give_zero_difference(self):
        rng = np.random.default_rng(SEED)
        s = rng.random(200)
        y = rng.integers(0, 2, 200)
        out = paired_bootstrap_auroc_diff(s, s, y, n_boot=300, seed=SEED)
        assert out["diff"] == 0.0
        assert out["p_two_sided"] == pytest.approx(1.0, abs=1e-9)

    def test_clearly_better_score_has_positive_difference(self):
        rng = np.random.default_rng(SEED)
        y = np.array([1] * 200 + [0] * 200)
        good = np.concatenate([rng.normal(2, 1, 200), rng.normal(0, 1, 200)])
        noise = rng.random(400)
        out = paired_bootstrap_auroc_diff(good, noise, y, n_boot=300, seed=SEED)
        assert out["diff"] > 0.2
        assert out["ci_lo"] > 0.0          # interval excludes "no difference"


class TestRetrievalMetrics:
    def test_recall_at_1_gold_always_first(self):
        assert recall_at_1_helper() == 1.0

    def test_mrr_gold_always_at_rank_two(self):
        # 1/2 by definition
        assert reciprocal_rank([":999", ":302", ":420"], "IPC:302") == 0.5

    def test_reciprocal_rank_is_zero_when_gold_absent(self):
        assert reciprocal_rank([":1", ":2"], "IPC:302") == 0.0

    def test_recall_is_monotone_non_decreasing_in_k(self):
        ranked = [f":{n}" for n in range(1, 16)]
        vals = [recall_at_k(ranked, ":12", k) for k in range(1, 16)]
        assert all(b >= a for a, b in zip(vals, vals[1:]))

    def test_precision_equals_recall_over_k_for_single_gold(self):
        ranked = [":1", ":2", ":302", ":4", ":5"]
        for k in (1, 3, 5):
            assert precision_at_k(ranked, "IPC:302", k) == pytest.approx(
                recall_at_k(ranked, "IPC:302", k) / k)

    def test_ndcg_is_monotone_in_rank(self):
        # earlier is better; nDCG must fall as the gold sinks
        vals = [ndcg_at_k([":9"] * i + [":302"] + [":9"] * (10 - i), ":302", 15)
                for i in range(0, 5)]
        assert all(b <= a for a, b in zip(vals, vals[1:]))

    def test_ndcg_at_rank_one_is_one(self):
        assert ndcg_at_k([":302", ":1"], ":302", 5) == 1.0


def recall_at_1_helper():
    return recall_at_k([":302", ":1", ":2"], "IPC:302", 1)


class TestSectionIdentity:
    """Defect E2 lived here: 'IPC Section 302' compared against 'Section 302'
    and called different, so a headline metric returned 0.0 forever."""

    def test_unattributed_reference_matches_an_attributed_one(self):
        # THE plan asked for normalise_section("IPC Section 302") ==
        # normalise_section("Section 302") as STRING equality. That is
        # implemented here as same_section() instead, deliberately.
        #
        # String equality would require dropping the statute from the
        # canonical form -- which would make IPC 302 and BNS 302 identical.
        # Those are different provisions in different codes, and telling them
        # apart is the entire subject of this paper. Collapsing them would
        # manufacture the very confusion being measured.
        #
        # same_section() keeps the statute but treats a MISSING one as
        # "cannot be ruled out", which is correct: statute text never names
        # its own statute.
        assert same_section("IPC Section 302", "Section 302") is True
        assert same_section("Section 302", "IPC Section 302") is True

    def test_two_different_codes_do_NOT_match(self):
        assert same_section("IPC Section 302", "BNS Section 302") is False

    def test_canonical_forms(self):
        assert normalise_section("IPC Section 302") == "IPC:302"
        assert normalise_section("Section 302") == ":302"
        assert normalise_section("BNS 318(4)") == "BNS:318(4)"
        assert normalise_section("IPC 304B") == "IPC:304B"
        assert normalise_section("s. 41A CrPC") == ":41A"

    def test_subsection_is_distinct_under_strict_matching(self):
        assert same_section("BNS 318(4)", "BNS 318") is False
        assert same_section("BNS 318(4)", "BNS 318", lenient=True) is True

    def test_a_letter_suffix_is_a_DIFFERENT_section_even_leniently(self):
        # This is the one place this library deliberately differs from the
        # older core/citations.py lenient rule, which stripped any trailing
        # letter and so collapsed 498A onto 498.
        #
        # That was wrong, and it inflated the Phase G "lenient" column.
        # A parenthesised number is a PART of one section: 318(4) really is
        # inside 318. A letter suffix is a SEPARATE section inserted by
        # amendment: IPC 498A (cruelty by a husband, inserted 1983) is a
        # different offence from IPC 498 (enticing a married woman).
        #
        # So lenient widens subsections and nothing else.
        assert same_section("IPC 498A", "IPC 498") is False
        assert same_section("IPC 498A", "IPC 498", lenient=True) is False
        assert same_section("BNS 318(4)", "BNS 318", lenient=True) is True

    def test_empty_never_matches(self):
        assert same_section("", "IPC 302") is False
        assert normalise_section(None) == ""


class TestCalibration:
    def test_ece_near_zero_on_perfectly_calibrated_data(self):
        # construct data where P(correct) really does equal the score
        rng = np.random.default_rng(SEED)
        s = rng.uniform(0.05, 0.95, 20000)
        y = (rng.random(20000) < s).astype(int)
        assert ece(s, y, n_bins=10) < 0.02

    def test_ece_large_on_systematically_overconfident_data(self):
        rng = np.random.default_rng(SEED)
        s = rng.uniform(0.8, 1.0, 4000)      # claims ~90%
        y = (rng.random(4000) < 0.3).astype(int)   # actually right 30%
        assert ece(s, y, n_bins=10) > 0.4

    def test_reliability_bins_cover_every_row(self):
        rng = np.random.default_rng(SEED)
        s = rng.random(1000)
        y = rng.integers(0, 2, 1000)
        assert reliability_bins(s, y, n_bins=10)["n"].sum() == 1000

    def test_quantile_bins_are_roughly_equal_mass(self):
        rng = np.random.default_rng(SEED)
        s = np.concatenate([rng.normal(0.5, 0.02, 900), rng.random(100)])
        b = reliability_bins(s, rng.integers(0, 2, 1000), n_bins=5, strategy="quantile")
        assert b["n"].max() / b["n"].min() < 4      # uniform bins would be far worse

    def test_brier_bounds(self):
        assert brier([1.0, 0.0], [1, 0]) == 0.0
        assert brier([0.0, 1.0], [1, 0]) == 1.0

    def test_platt_recovers_a_known_logistic(self):
        rng = np.random.default_rng(SEED)
        x = rng.uniform(-3, 3, 6000)
        p = 1 / (1 + np.exp(-(2.0 * x + 0.5)))
        y = (rng.random(6000) < p).astype(int)
        out = platt_scale(x, y, np.array([0.0]))
        assert out[0] == pytest.approx(1 / (1 + np.exp(-0.5)), abs=0.06)


class TestSelectivePrediction:
    def test_risk_is_zero_at_low_coverage_when_top_scores_are_correct(self):
        s = [0.9, 0.8, 0.7, 0.2, 0.1]
        y = [1, 1, 1, 0, 0]
        c = risk_coverage_curve(s, y)
        assert c.iloc[0]["risk"] == 0.0
        assert c.iloc[-1]["risk"] == pytest.approx(0.4)

    def test_coverage_at_risk_is_full_when_everything_is_correct(self):
        assert coverage_at_risk([0.9, 0.8, 0.7], [1, 1, 1], 0.10) == 1.0

    def test_coverage_at_risk_is_zero_when_the_top_answer_is_wrong(self):
        assert coverage_at_risk([0.9, 0.8], [0, 0], 0.10) == 0.0


class TestWilson:
    def test_does_not_claim_certainty_at_the_boundary(self):
        # the reason Wilson is used: the normal interval gives +/-0.00 here
        p, lo, hi = wilson(33, 33)
        assert p == 1.0
        assert lo < 1.0

    def test_interval_narrows_as_n_grows(self):
        _, lo1, hi1 = wilson(4, 5)
        _, lo2, hi2 = wilson(80, 100)
        assert (hi1 - lo1) > (hi2 - lo2)

    def test_zero_of_zero_is_safe(self):
        assert wilson(0, 0) == (0.0, 0.0, 0.0)
