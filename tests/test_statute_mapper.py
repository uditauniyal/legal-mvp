"""Tests for the Statute Mapper.

WHAT IT IS RESPONSIBLE FOR
    One thing: deciding which corpus to search, given the citations in the
    query and the era resolved from the date. It does not parse dates (that
    is core.dates) and it does not retrieve anything.

    Keeping it that narrow is what makes Phase H interpretable. The
    comparison against the Phase G baseline moves ONE variable; a component
    that also reranked, or also filtered by domain, would produce a delta
    nobody could attribute.

THE CASE THAT JUSTIFIES THE WHOLE MODULE
    "Section 420 IPC ... this happened last month"

    Every existing step behaves correctly and the answer is still repealed
    law. The Router is faithful to the WORDS; nothing in the pipeline knows
    the words are out of date.
"""

from __future__ import annotations

import pytest

from core.dates import BNS_ERA, BOTH_ERAS, IPC_ERA, UNKNOWN
from core.statute_mapper import map_query


class TestTheCaseThisExistsFor:
    def test_old_citation_recent_conduct_moves_to_the_new_code(self):
        m = map_query("What is the punishment under Section 420 IPC?", BNS_ERA)
        assert m.original == ["IPC 420"]
        assert m.governing == ["BNS 318(4)"]
        assert m.target_corpora == ["BNS"]
        assert m.changed is True
        assert m.rule == "translated_to_governing_code"

    def test_new_citation_old_conduct_moves_back(self):
        """The mirror case. Someone reads about the BNS and asks about it,
        but describes conduct from 2023 -- the IPC still governs that."""
        m = map_query("What does Section 318(4) of the Bharatiya Nyaya Sanhita provide?",
                      IPC_ERA)
        assert m.governing == ["IPC 420"]
        assert m.target_corpora == ["IPC"]
        assert m.changed is True


class TestNoDateChangesNothing:
    """The most common outcome, and the correct one."""

    def test_unknown_era_leaves_the_citation_alone(self):
        m = map_query("What is the punishment under Section 420 IPC?", UNKNOWN)
        assert m.governing == ["IPC 420"]
        assert m.changed is False
        assert m.rule == "era_unknown_no_change"

    def test_unknown_era_still_filters_to_the_named_corpus(self):
        """Not translating is not the same as not filtering. The Router's
        existing behaviour must be preserved exactly, or the Phase H
        comparison measures the loss of the filter instead of the gain from
        the mapper."""
        assert map_query("Section 420 IPC", UNKNOWN).target_corpora == ["IPC"]

    def test_no_citation_and_no_date_is_a_clean_no_op(self):
        m = map_query("husband beats me, what can i do", UNKNOWN)
        assert m.original == []
        assert m.target_corpora == []
        assert m.changed is False


class TestAlreadyGoverning:
    """Was a bug: asking to_old() for 'IPC 420' searches an index keyed by BNS
    references, finds nothing, and raised -- producing a 'no entry in the
    recodification map' warning for a citation that was already correct."""

    def test_ipc_citation_in_ipc_era_is_untouched_and_silent(self):
        m = map_query("Section 420 IPC", IPC_ERA)
        assert m.governing == ["IPC 420"]
        assert m.rule == "already_governing_code"
        assert not any("no entry" in w for w in m.warnings)

    def test_bns_citation_in_bns_era_is_untouched_and_silent(self):
        m = map_query("Section 318(4) BNS", BNS_ERA)
        assert m.governing == ["BNS 318(4)"]
        assert not any("no entry" in w for w in m.warnings)


class TestContinuingConduct:
    def test_both_eras_searches_both_halves(self):
        m = map_query("Section 420 IPC", BOTH_ERAS)
        assert set(m.target_corpora) == {"IPC", "BNS"}
        assert "IPC 420" in m.governing
        assert "BNS 318(4)" in m.governing
        assert m.rule == "both_eras_search_both"


class TestNoCounterpart:
    def test_repealed_without_a_successor_warns_rather_than_inventing(self):
        """IPC 161 was repealed in 1988 by the Prevention of Corruption Act,
        36 years before the BNS existed. There is no BNS equivalent, and
        producing one would be a fabrication."""
        m = map_query("bribe under Section 161 IPC", BNS_ERA)
        assert m.governing == ["IPC 161"]
        assert any("NO counterpart" in w for w in m.warnings)

    def test_the_substantive_change_note_is_carried_through(self):
        """IPC 379 -> BNS 303(2) is not a renumbering: the BNS adds community
        service for first-time theft under Rs 5,000. An answer that says only
        'the number changed' would be wrong."""
        m = map_query("theft under Section 379 IPC", BNS_ERA)
        assert m.governing == ["BNS 303(2)"]
        assert any("SUBSTANTIVE CHANGE" in n for n in m.notes)


class TestGoverningCodeNotIngested:
    """The BNSS is not in the index. Procedural queries in the BNS era have a
    governing provision that no retriever here can reach."""

    def test_falls_back_to_the_named_code_rather_than_dropping_the_filter(self):
        m = map_query("police arrested him under Section 41 CrPC", BNS_ERA)
        assert m.governing == ["BNSS 35"]
        assert m.target_corpora == ["CRPC"]
        assert any("not in the index" in w for w in m.warnings)

    def test_the_unreachability_is_stated_not_hidden(self):
        m = map_query("Section 41 CrPC", BNS_ERA)
        assert any("cannot be retrieved" in w or "not in the index" in w
                   for w in m.warnings)


class TestUnchangedStatutes:
    def test_consumer_protection_act_is_never_translated(self):
        """The CPA 2019 was untouched by the 2024 recodification."""
        m = map_query("complaint under Section 35 of the Consumer Protection Act", BNS_ERA)
        assert m.governing == ["CPA 35"]
        assert m.target_corpora == ["CPA"]
        assert m.changed is False


class TestLogging:
    def test_decision_serialises_for_the_run_log(self):
        log = map_query("Section 420 IPC", BNS_ERA).as_log()
        assert log["original"] == ["IPC 420"]
        assert log["governing"] == ["BNS 318(4)"]
        assert log["changed"] is True
        assert log["rule"] == "translated_to_governing_code"

    @pytest.mark.parametrize("era", [UNKNOWN, IPC_ERA, BNS_ERA, BOTH_ERAS])
    def test_target_corpora_only_ever_names_ingested_corpora(self, era):
        """A filter naming a corpus that does not exist matches nothing, which
        then silently falls back to an unfiltered search over an index that is
        39% CrPC. That is the mechanism behind the original routing drift."""
        for q in ["Section 420 IPC", "Section 41 CrPC", "Section 318 BNS", "nothing here"]:
            for c in map_query(q, era).target_corpora:
                assert c in {"IPC", "BNS", "CRPC", "CPA"}
