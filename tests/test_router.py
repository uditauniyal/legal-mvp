"""Tests for the Router (agents/router.py).

The previous version of this file raised AttributeError on its first case:
it passed a string to route(), which takes a CaseContext. It never ran.

The Router decides WHICH corpus is searched. That decision happens before
retrieval, so a routing error cannot be recovered from downstream -- which is
why it is deterministic, and why every branch is pinned here.
"""

import pytest

from agents.intake import CaseContext
from agents.router import RouterAgent


def ctx(query: str, domain: str = "Criminal") -> CaseContext:
    return CaseContext(
        original_query=query,
        scenario="test",
        user_persona="Layman",
        urgency="Deferred",
        financial_status="Unknown",
        complexity="Low",
        predicted_legal_domain=domain,
        legal_issues=[],
        missing_facts=[],
    )


@pytest.fixture
def router():
    return RouterAgent()


# --- corpus selection, branch by branch -----------------------------------

def test_single_act_named_selects_that_corpus(router):
    plan = router.route(ctx("What is Section 420 IPC?"))
    assert plan.target_corpus == "BNS"          # ACT_MAP maps ipc -> BNS
    assert plan.decision_path == "act_map_single"


def test_two_acts_named_drops_the_filter(router):
    """Filtering to one corpus would guarantee half the answer is missing."""
    plan = router.route(ctx("compare IPC and CrPC provisions"))
    assert plan.target_corpus is None
    assert plan.decision_path == "act_map_multi_no_filter"


def test_no_act_named_falls_back_to_domain(router):
    plan = router.route(ctx("police arrested my brother", domain="Criminal"))
    assert plan.decision_path == "domain_fallback_criminal"


def test_civil_domain_searches_everything(router):
    plan = router.route(ctx("my landlord kept my deposit", domain="Civil"))
    assert plan.target_corpus is None
    assert plan.decision_path == "domain_fallback_civil_no_filter"


def test_unmatched_query_records_no_match(router):
    plan = router.route(ctx("what is income tax", domain="Taxation"))
    assert plan.decision_path == "no_match"


# --- entity extraction -----------------------------------------------------

def test_section_number_is_extracted(router):
    plan = router.route(ctx("What does Section 41 say?"))
    assert "Section 41" in plan.entities
    assert plan.intent == "statute"


def test_article_is_extracted(router):
    plan = router.route(ctx("Explain Article 21"))
    assert any("21" in e for e in plan.entities)


def test_no_entities_when_none_mentioned(router):
    plan = router.route(ctx("someone cheated me out of money"))
    assert plan.entities == []


# --- the defect this router currently has ---------------------------------

def test_DEFECT_procedural_query_routed_to_penal_code(router):
    """docs/GAPS.md #6 -- 'Criminal' is treated as a synonym for the penal code.

    Arrest, bail, FIR and jurisdiction are PROCEDURE (CrPC/BNSS), not offence
    definitions (IPC/BNS). This test pins the wrong behaviour so that fixing
    it in Phase E is visible rather than silent.
    """
    plan = router.route(ctx("can police arrest without a warrant", domain="Criminal"))
    assert plan.target_corpus == "BNS", (
        "Expected the current (incorrect) penal-code routing. If this now "
        "fails, the domain fallback was fixed -- update to assert BNSS/CRPC."
    )


def test_decision_path_is_always_set(router):
    """Every plan must record which rule fired, or the routing analysis in
    EVALUATION_PLAN.md E4 has nothing to group by."""
    for q, d in [("Section 420 IPC", "Criminal"), ("nothing here", "General"),
                 ("landlord dispute", "Civil"), ("IPC and CrPC", "Criminal")]:
        assert router.route(ctx(q, d)).decision_path != "unset"
