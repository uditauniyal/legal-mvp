"""Tests for the composite confidence score.

These tests DOCUMENT CURRENT BEHAVIOUR, including two defects. They are
written to fail loudly when those defects are fixed in Phase E, so the fix
cannot happen silently and un-measured.

Defect 1 (docs/GAPS.md #1) -- entity_coverage divides a CHUNK count by an
ENTITY count, so it can exceed 1.0 and saturate the min(confidence, 1.0) clamp.

Defect 2 (docs/GAPS.md #2) -- when no entity is extracted the signal defaults
to 1.0, granting its full 0.30 weight for free. Since the HIGH threshold is
0.55, almost any no-entity query reaches HIGH.
"""

import pytest

from agents.retriever import compute_confidence


class FakeChunk:
    """Minimal stand-in for a Qdrant ScoredPoint."""

    def __init__(self, text: str):
        self.payload = {"text": text}


GOOD_SCORES = [0.52, 0.50, 0.48, 0.47, 0.46]


def test_empty_scores_returns_zero():
    out = compute_confidence([], [], [])
    assert out["confidence"] == 0.0
    assert out["top_k_mean"] == 0.0


def test_top_k_mean_is_mean_of_best_five():
    scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.1, 0.1]
    out = compute_confidence(scores, [], [FakeChunk("x")] * 7)
    assert out["top_k_mean"] == pytest.approx((0.9 + 0.8 + 0.7 + 0.6 + 0.5) / 5)


def test_score_gap_is_first_minus_fifth():
    out = compute_confidence([0.9, 0.8, 0.7, 0.6, 0.5], [], [FakeChunk("x")] * 5)
    assert out["score_gap"] == pytest.approx(0.4)


def test_no_entities_flags_the_default():
    """The free 0.30 must be visible in the output, not silent."""
    out = compute_confidence(GOOD_SCORES, [], [FakeChunk("x")] * 5)
    assert out["entity_coverage"] == 1.0
    assert out["entity_coverage_default_used"] is True


def test_entities_present_does_not_flag_the_default():
    out = compute_confidence(GOOD_SCORES, ["Section 41"], [FakeChunk("Section 41 arrest")] * 5)
    assert out["entity_coverage_default_used"] is False


# ---------------------------------------------------------------------------
# The two defects, pinned. Both are EXPECTED TO FAIL once Phase E lands.
# ---------------------------------------------------------------------------

def test_DEFECT_entity_coverage_exceeds_one():
    """GAPS.md #1: three matching chunks / one entity == 3.0, not a fraction."""
    chunks = [FakeChunk("Section 41 arrest")] * 3 + [FakeChunk("unrelated")] * 2
    out = compute_confidence(GOOD_SCORES, ["Section 41"], chunks)
    assert out["entity_coverage"] == 3.0, (
        "entity_coverage should be a FRACTION in [0,1]. Getting 3.0 means it is "
        "counting chunks and dividing by entities. If this test now fails, the "
        "defect was fixed -- update it to assert the correct fraction."
    )


def test_DEFECT_confidence_saturates_at_one():
    """The clamp hides defect 1: the raw composite is ~1.27, reported as 1.0."""
    chunks = [FakeChunk("Section 41 arrest")] * 3 + [FakeChunk("unrelated")] * 2
    out = compute_confidence(GOOD_SCORES, ["Section 41"], chunks)
    assert out["confidence"] == 1.0


def test_DEFECT_no_entity_query_reaches_high_tier_on_mediocre_scores():
    """GAPS.md #2: mediocre retrieval still clears HIGH (0.55) with no entity.

    These scores are deliberately poor -- the sort of thing returned when the
    corpus does not contain the answer at all.
    """
    mediocre = [0.41, 0.40, 0.39, 0.39, 0.38]
    out = compute_confidence(mediocre, [], [FakeChunk("irrelevant")] * 5)
    assert out["confidence"] > 0.55, (
        "Expected the free 0.30 to push mediocre retrieval into the HIGH tier."
    )


def test_signals_are_reported_separately_for_ablation():
    """All three signals must be recoverable from the output, or the
    ablation in EVALUATION_PLAN.md E6 cannot be computed offline."""
    out = compute_confidence(GOOD_SCORES, ["Section 41"], [FakeChunk("Section 41")] * 5)
    for key in ("top_k_mean", "score_gap", "entity_coverage", "confidence"):
        assert key in out
