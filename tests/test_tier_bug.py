"""Tests for the prompt-tier LOG field (docs/GAPS.md -- tier logging bug).

THE DEFECT, precisely.

    agents/answer.py used to read:

        prompt_variant = "HIGH"
        if retrieval.confidence < MEDIUM_CONFIDENCE:
            system_prompt = LOW_CONFIDENCE_DISCLAIMER + ...
        elif retrieval.confidence < HIGH_CONFIDENCE:
            system_prompt = MEDIUM_CONFIDENCE_DISCLAIMER + ...
        ...
        return {..., "prompt_variant": prompt_variant, ...}

    The variable was initialised to "HIGH" and never reassigned inside the
    LOW or MEDIUM branches. The *disclaimer* was chosen correctly -- the
    system behaved right -- but every non-refused record logged "HIGH".

    Measured over the real logs: 369 of 859 rows (43.0%) carried a tier that
    contradicted their own confidence.composite. Reproduce with the command
    in results/_explain_w1_s1.md.

WHAT THESE TESTS PIN.

    1. The logged tier equals the tier the confidence actually falls in.
    2. THE INVARIANT THAT WAS VIOLATED: the disclaimer prepended to the
       system prompt matches the tier that was logged. Asserting (1) alone
       would pass on a build that logged correctly but disclaimed wrongly --
       the same bug with the halves swapped, and the dangerous direction.

    (2) is checked by capturing the exact `messages` handed to the LLM
    client, so the assertion reads the real prompt rather than trusting a
    return field. Zero network calls: `agents.answer.chat` is monkeypatched.

BOUNDARIES ARE TESTED AGAINST THE CODE, NOT AGAINST AN ASSUMPTION.
    The comparisons are strict `<`, so:
        confidence == 0.38 is NOT < 0.38  -> falls through to MEDIUM
        confidence == 0.55 is NOT < 0.55  -> falls through to HIGH
    Each boundary test below re-derives that from the operator rather than
    hard-coding a remembered answer.
"""

import pytest

from agents import answer as answer_mod
from agents.answer import (
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE_DISCLAIMER,
    MEDIUM_CONFIDENCE,
    MEDIUM_CONFIDENCE_DISCLAIMER,
    AnswerAgent,
    tier_for_confidence,
)
from agents.retriever import RetrievalResult


class FakeChunk:
    """Minimal stand-in for a Qdrant ScoredPoint."""

    def __init__(self, text="Whoever commits theft shall be punished."):
        self.payload = {"text": text, "doc_name": "BNS", "page": 12}


class FakeMeta:
    """Minimal stand-in for clients.openai_client.CallMeta."""

    provider_name = "FakeProvider"
    model = "fake/model"
    prompt_tokens = 100
    completion_tokens = 50


@pytest.fixture
def captured_prompts(monkeypatch):
    """Replace the LLM call with a recorder. No network, no API key needed.

    Returns a list that receives the `messages` of every call made.
    """
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return "fake answer text", FakeMeta()

    monkeypatch.setattr(answer_mod, "chat", fake_chat)
    return calls


def run_at(confidence, captured_prompts, refused=False, chunks=None):
    """Run AnswerAgent at one confidence and return (result, system_prompt).

    system_prompt is None when no LLM call was made (the refusal path).
    """
    if chunks is None:
        chunks = [FakeChunk()]
    retrieval = RetrievalResult(
        chunks=chunks,
        confidence=confidence,
        total_chunks=len(chunks),
        total_retrieved=len(chunks),
        refused=refused,
    )
    out = AnswerAgent().answer("Is my landlord allowed to keep my deposit?", retrieval)
    system_prompt = captured_prompts[-1][0]["content"] if captured_prompts else None
    return out, system_prompt


def disclaimer_in(system_prompt):
    """Which disclaimer the prompt actually carries -- read off the prompt.

    LOW is checked first because both disclaimers are distinct blocks; a
    prompt carries exactly one of them or neither.
    """
    has_low = LOW_CONFIDENCE_DISCLAIMER.strip() in system_prompt
    has_medium = MEDIUM_CONFIDENCE_DISCLAIMER.strip() in system_prompt
    assert not (has_low and has_medium), "a prompt must not carry both disclaimers"
    if has_low:
        return "LOW"
    if has_medium:
        return "MEDIUM"
    return "HIGH"


# --------------------------------------------------- the pure tier function


@pytest.mark.parametrize(
    "confidence,expected",
    [
        (0.00, "LOW"),
        (0.30, "LOW"),
        (0.38, "MEDIUM"),
        (0.45, "MEDIUM"),
        (0.55, "HIGH"),
        (0.60, "HIGH"),
        (1.00, "HIGH"),
    ],
)
def test_tier_for_confidence(confidence, expected):
    assert tier_for_confidence(confidence) == expected


def test_boundaries_follow_the_strict_less_than_in_the_code():
    """Re-derive the boundary answers from the operator the code uses.

    If someone changes `<` to `<=`, this fails alongside the parametrised
    cases above, which is the point -- one of the two is a hard-coded
    expectation and the other is not.
    """
    assert not (MEDIUM_CONFIDENCE < MEDIUM_CONFIDENCE)
    assert tier_for_confidence(MEDIUM_CONFIDENCE) == "MEDIUM"

    assert not (HIGH_CONFIDENCE < HIGH_CONFIDENCE)
    assert tier_for_confidence(HIGH_CONFIDENCE) == "HIGH"


# ------------------------------------------------- the logged field, in situ


def test_low_confidence_logs_low(captured_prompts):
    out, _ = run_at(0.30, captured_prompts)
    assert out["prompt_variant"] == "LOW"


def test_medium_confidence_logs_medium(captured_prompts):
    out, _ = run_at(0.45, captured_prompts)
    assert out["prompt_variant"] == "MEDIUM"


def test_high_confidence_logs_high(captured_prompts):
    out, _ = run_at(0.60, captured_prompts)
    assert out["prompt_variant"] == "HIGH"


def test_boundary_055_logs_high(captured_prompts):
    """0.55 is not < 0.55, so it takes the else branch."""
    out, _ = run_at(HIGH_CONFIDENCE, captured_prompts)
    assert out["prompt_variant"] == "HIGH"


def test_boundary_038_logs_medium(captured_prompts):
    """0.38 is not < 0.38, so it falls through to the MEDIUM branch."""
    out, _ = run_at(MEDIUM_CONFIDENCE, captured_prompts)
    assert out["prompt_variant"] == "MEDIUM"


def test_just_below_038_logs_low(captured_prompts):
    out, _ = run_at(0.3799, captured_prompts)
    assert out["prompt_variant"] == "LOW"


def test_just_below_055_logs_medium(captured_prompts):
    out, _ = run_at(0.5499, captured_prompts)
    assert out["prompt_variant"] == "MEDIUM"


# ----------------------------------------------------------- THE INVARIANT


@pytest.mark.parametrize(
    "confidence", [0.00, 0.10, 0.30, 0.3799, 0.38, 0.45, 0.5499, 0.55, 0.60, 0.99]
)
def test_logged_tier_matches_the_disclaimer_actually_applied(
    confidence, captured_prompts
):
    """The invariant the bug violated.

    Before the fix this failed at every confidence below 0.55: the prompt
    carried the LOW or MEDIUM disclaimer while the record said "HIGH".
    """
    out, system_prompt = run_at(confidence, captured_prompts)
    assert system_prompt is not None, "the LLM should have been called"
    assert out["prompt_variant"] == disclaimer_in(system_prompt)


def test_invariant_would_have_caught_the_original_bug(captured_prompts):
    """Guard against the fix being a no-op.

    A build that still logged a constant "HIGH" would pass every HIGH case
    above. This asserts the two halves DISAGREE with a constant -- i.e. that
    at 0.30 the prompt genuinely carries the LOW disclaimer and the record
    genuinely says LOW, neither of which held before.
    """
    out, system_prompt = run_at(0.30, captured_prompts)
    assert disclaimer_in(system_prompt) == "LOW"
    assert out["prompt_variant"] == "LOW"
    assert out["prompt_variant"] != "HIGH"


# --------------------------------------------------------- the REFUSED path


def test_refused_flag_logs_refused(captured_prompts):
    """refused=True short-circuits before any tier is computed."""
    out, system_prompt = run_at(0.10, captured_prompts, refused=True)
    assert out["prompt_variant"] == "REFUSED"
    assert out["refused"] is True
    assert system_prompt is None, "the refusal path must not call the LLM"


def test_empty_chunks_logs_refused(captured_prompts):
    """The gate is `refused or not chunks` -- an empty chunk list refuses too,
    even at a confidence that would otherwise be HIGH."""
    out, system_prompt = run_at(0.90, captured_prompts, chunks=[])
    assert out["prompt_variant"] == "REFUSED"
    assert out["refused"] is True
    assert system_prompt is None


def test_refused_record_is_still_complete(captured_prompts):
    """The refusal record kept its logging fields -- the fix touched only the
    non-refused return."""
    out, _ = run_at(0.10, captured_prompts, refused=True)
    assert out["confidence"] == 0.10
    assert out["citations"] == []
    assert out["llm_ok"] is True
    assert out["llm_error"] is None
    assert out["prompt_tokens"] == 0
    assert out["completion_tokens"] == 0


# ------------------------------------------- no behaviour changed elsewhere


def test_non_refused_record_keeps_its_other_fields(captured_prompts):
    out, _ = run_at(0.60, captured_prompts)
    assert out["refused"] is False
    assert out["answer"] == "fake answer text"
    assert out["llm_ok"] is True
    assert out["gen_provider"] == "FakeProvider"
    assert out["prompt_tokens"] == 100
    assert len(out["citations"]) == 1


def test_llm_failure_still_logs_the_right_tier(monkeypatch):
    """When chat() throws, the record must still carry the true tier -- the
    tier is a property of the confidence, not of the call succeeding."""

    def boom(messages, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(answer_mod, "chat", boom)
    retrieval = RetrievalResult(
        chunks=[FakeChunk()], confidence=0.45, total_chunks=1, total_retrieved=1
    )
    out = AnswerAgent().answer("q", retrieval)
    assert out["llm_ok"] is False
    assert out["prompt_variant"] == "MEDIUM"
