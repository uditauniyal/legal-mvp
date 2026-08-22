"""Tests for the composite confidence score.

Both defects these tests were written to pin are now FIXED, and the
assertions have been flipped to the correct values. The old expectations are
recorded in each docstring, because a reader seeing 0.6873 here should be able
to tell it was ever 1.0.

Defect 1 (docs/GAPS.md #1) -- entity_coverage divided a CHUNK count by an
ENTITY count, so it reached 5.0 and saturated the min(confidence, 1.0) clamp.
Fixed: the numerator now counts entities, bounding the value to [0, 1].

Defect 2 (docs/GAPS.md #2) -- when no entity was extracted the signal defaulted
to 1.0, granting its full 0.30 weight for free. Since the HIGH threshold is
0.55, almost any no-entity query reached HIGH -- and layman queries, the ones
this project exists for, name a section almost never. Fixed: the fallback is
ENTITY_NEUTRAL (0.5), meaning "unknown".

EVERY EXPECTED VALUE HERE IS WORKED OUT BY HAND in the docstring that carries
it. A metric test whose expectation was produced by running the code proves
only that the code is deterministic.
"""

import pytest

from agents.retriever import ENTITY_NEUTRAL, compute_confidence


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


def test_no_entities_uses_the_neutral_value_and_flags_it():
    """Was 1.0 -- full credit for a signal that could not be computed.

    Now ENTITY_NEUTRAL (0.5): neither rewarded nor punished. The flag must
    still be set either way, so the ablation can recompute the old behaviour
    offline from the log without re-querying.
    """
    out = compute_confidence(GOOD_SCORES, [], [FakeChunk("x")] * 5)
    assert out["entity_coverage"] == ENTITY_NEUTRAL
    assert out["entity_coverage_default_used"] is True


def test_entities_present_does_not_flag_the_default():
    out = compute_confidence(GOOD_SCORES, ["Section 41"], [FakeChunk("Section 41 arrest")] * 5)
    assert out["entity_coverage_default_used"] is False


# ---------------------------------------------------------------------------
# The two defects, now fixed. Each test names the value it used to assert.
# ---------------------------------------------------------------------------

def test_entity_coverage_is_a_fraction_of_entities_found():
    """Was pinned at 3.0 (GAPS.md #1) -- three matching CHUNKS divided by one
    ENTITY. Different units on each side of the division.

    Now: one entity, present in the retrieved text, so 1/1 = 1.0.
    """
    chunks = [FakeChunk("Section 41 arrest")] * 3 + [FakeChunk("unrelated")] * 2
    out = compute_confidence(GOOD_SCORES, ["Section 41"], chunks)
    assert out["entity_coverage"] == 1.0


def test_entity_coverage_partial_match():
    """Two entities, only one findable -> 0.5. The case that proves the
    numerator counts entities: under the old arithmetic four matching chunks
    over two entities gave 2.0."""
    chunks = [FakeChunk("Section 41 arrest procedure")] * 4 + [FakeChunk("unrelated")]
    out = compute_confidence(GOOD_SCORES, ["Section 41", "Section 438"], chunks)
    assert out["entity_coverage"] == pytest.approx(0.5)


def test_entity_coverage_never_exceeds_one():
    """The invariant, stated directly. One entity repeated across every chunk
    is still one entity found."""
    chunks = [FakeChunk("Section 41 arrest")] * 15
    out = compute_confidence(GOOD_SCORES, ["Section 41"], chunks)
    assert 0.0 <= out["entity_coverage"] <= 1.0


def test_confidence_no_longer_saturates():
    """Was pinned at 1.0, where the min(confidence, 1.0) clamp was hiding a raw
    composite of ~1.27 produced by the unbounded entity signal.

    Worked by hand from the weights in compute_confidence:
        top_k_mean   (0.52+0.50+0.48+0.47+0.46)/5   = 0.486
        score_gap    0.52 - 0.46                    = 0.06
        gap_penalty  min(0.06/0.3, 1.0)             = 0.2
        entity_cov   1 entity found / 1 entity      = 1.0

        0.55*0.486 + 0.15*(1-0.2) + 0.30*1.0
          = 0.2673  + 0.12        + 0.30           = 0.6873
    """
    chunks = [FakeChunk("Section 41 arrest")] * 3 + [FakeChunk("unrelated")] * 2
    out = compute_confidence(GOOD_SCORES, ["Section 41"], chunks)
    assert out["confidence"] == pytest.approx(0.6873, abs=1e-4)
    assert out["confidence"] < 1.0


def test_no_entity_query_on_mediocre_scores_no_longer_reaches_high():
    """GAPS.md #2, fixed.

    These scores are deliberately poor -- the sort of thing returned when the
    corpus does not contain the answer at all. They used to clear the HIGH
    tier (0.55) purely on the free 0.30 the entity signal gave away.

    Worked by hand:
        top_k_mean   (0.41+0.40+0.39+0.39+0.38)/5  = 0.394
        score_gap    0.41 - 0.38                   = 0.03
        gap_penalty  min(0.03/0.3, 1.0)            = 0.1
        entity_cov   ENTITY_NEUTRAL                = 0.5

        0.55*0.394 + 0.15*(1-0.1) + 0.30*0.5
          = 0.2167  + 0.135       + 0.15          = 0.5017   -> below HIGH
    """
    mediocre = [0.41, 0.40, 0.39, 0.39, 0.38]
    out = compute_confidence(mediocre, [], [FakeChunk("irrelevant")] * 5)
    assert out["confidence"] == pytest.approx(0.5017, abs=1e-4)
    assert out["confidence"] < 0.55


def test_gap_signal_rewards_uniform_irrelevance():
    """A known perversity, pinned rather than fixed.

    When every retrieved chunk is equally irrelevant the scores are almost
    identical, so score_gap is near zero and the signal awards its full 0.15
    for "consistency". Consistently wrong looks the same as consistently
    right to this signal.

    Left in place deliberately: it is one of the three signals under ablation
    in EVALUATION_PLAN E6, and removing it before measuring would destroy the
    comparison. Recorded here so it is a known property, not a surprise.
    """
    flat_and_bad = [0.30, 0.30, 0.30, 0.30, 0.30]
    out = compute_confidence(flat_and_bad, [], [FakeChunk("irrelevant")] * 5)
    assert out["score_gap"] == 0.0
    assert out["confidence"] == pytest.approx(0.55 * 0.30 + 0.15 * 1.0 + 0.30 * 0.5, abs=1e-4)


def test_signals_are_reported_separately_for_ablation():
    """All three signals must be recoverable from the output, or the
    ablation in EVALUATION_PLAN.md E6 cannot be computed offline."""
    out = compute_confidence(GOOD_SCORES, ["Section 41"], [FakeChunk("Section 41")] * 5)
    for key in ("top_k_mean", "score_gap", "entity_coverage", "confidence"):
        assert key in out
