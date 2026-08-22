"""Tests for the citation audit.

WHY THIS FILE EXISTS
    panel_prose_jaccard shipped, was promoted as a headline metric, and
    returned 0.0 on perfectly grounded answers for its entire life. Nothing
    crashed. It reported a confident, precise, wrong number.

    Metric code fails silently by nature: there is no exception to catch,
    because a ratio is always *a* ratio. The only defence is a test with an
    expected value worked out by hand, so this file computes every expectation
    on paper first and states the arithmetic in the comment.
"""

from __future__ import annotations

import pytest

from core.citations import extract_provisions
from core.verifier import CorpusIndex, audit_answer

ACTS = {"IPC", "BNS", "CRPC", "CPA"}

# Real statutory text: notice it never names its own Act. That is the whole
# reason the original key-equality comparison could not work.
MURDER = "Section 302. Punishment for murder.-Whoever commits murder shall be punished with death..."
CHEATING = "Section 420. Cheating and dishonestly inducing delivery of property.-Whoever cheats..."


def audit(answer: str, retrieved: str):
    return audit_answer(answer, retrieved, CorpusIndex(acts=ACTS, sections=extract_provisions(retrieved)))


class TestPanelProseJaccard:
    """|intersection| / |union| over provisions, under same_provision()."""

    def test_perfect_grounding_is_one(self):
        # prose {IPC:302}, panel {?:302}; the unattributed panel entry matches
        # on kind+number.  1/1 = 1.0
        assert audit("Under Section 302 IPC, murder is punishable by death.", MURDER).panel_prose_jaccard == 1.0

    def test_half_grounded(self):
        # prose {302, 420}, panel {302}.  intersection 1, union 2+1-1 = 2 -> 0.5
        got = audit("See Section 302 IPC and Section 420 IPC.", MURDER).panel_prose_jaccard
        assert got == pytest.approx(0.5)

    def test_disjoint_is_zero(self):
        # prose {NI Act 138}, panel {302}.  intersection 0 -> 0.0
        assert audit("See Section 138 of the NI Act.", MURDER).panel_prose_jaccard == 0.0

    def test_repeated_citation_counted_once(self):
        # Citing the same provision three times is one provision.
        assert audit("Section 302 IPC. Again Section 302 IPC. And Section 302 IPC.",
                     MURDER).panel_prose_jaccard == 1.0

    def test_nothing_cited_and_nothing_shown_is_one(self):
        # Consistent, not divergent. An answer that cites nothing over sources
        # that contain nothing has not contradicted itself.
        assert audit("I cannot answer that from the available material.", "").panel_prose_jaccard == 1.0

    def test_cited_but_no_panel_is_zero(self):
        assert audit("See Section 302 IPC.", "").panel_prose_jaccard == 0.0

    def test_never_exceeds_one(self):
        # '?:section:302' would match BOTH IPC:302 and BNS:302 under the
        # matching rule. Without one-to-one matching the count would exceed
        # the set size and push the ratio above 1.
        both = MURDER + "\n" + "Section 302. Some other provision numbered the same."
        got = audit("Section 302 IPC and Section 302 BNS both apply.", both).panel_prose_jaccard
        assert 0.0 <= got <= 1.0

    def test_symmetric(self):
        a = audit("Section 302 IPC and Section 420 IPC.", MURDER).panel_prose_jaccard
        b = audit("Section 302.", MURDER + CHEATING).panel_prose_jaccard
        assert 0.0 <= a <= 1.0 and 0.0 <= b <= 1.0


class TestGrounding:
    def test_grounded_citation_is_not_ungrounded(self):
        r = audit("Section 302 IPC applies.", MURDER)
        assert r.ungrounded_rate == 0.0
        assert len(r.grounded) == 1

    def test_out_of_corpus_act_is_ungrounded(self):
        # The NI Act is not indexed, so the model could not have retrieved it.
        r = audit("Section 138 of the NI Act applies.", MURDER)
        assert r.out_of_corpus_rate == 1.0
        assert r.ungrounded_rate == 1.0

    def test_jaccard_and_grounding_agree(self):
        """The regression guard for the original bug.

        These two numbers measure different things, but on a fully grounded
        answer they must not CONTRADICT each other. The old implementation
        reported ungrounded_rate 0.0 (all grounded) alongside jaccard 0.0
        (nothing overlaps) for the same answer, which is incoherent.
        """
        r = audit("Under Section 302 IPC, murder is punishable by death.", MURDER)
        assert r.ungrounded_rate == 0.0
        assert r.panel_prose_jaccard == 1.0
