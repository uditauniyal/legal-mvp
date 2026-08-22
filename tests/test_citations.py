"""Tests for statutory-reference extraction (core/citations.py).

This module produces the numbers in the paper's citation-grounding
experiment, so its behaviour is pinned here. A regression that silently
under-counts citations would flatter the system.
"""

import pytest

from core.citations import (
    Provision,
    extract_provisions,
    provision_in,
    same_provision,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Section 420 IPC for cheating", ["IPC Section 420"]),
        ("IPC Section 302 punishment for murder", ["IPC Section 302"]),
        ("Sec 138 of the Negotiable Instruments Act, 1881", ["NI Section 138"]),
        ("Article 22(1) right to be informed", ["Article 22(1)"]),
        ("BNSS Sec 35 arrest without warrant", ["BNSS Section 35"]),
        ("s. 41A CrPC notice of appearance", ["CRPC Section 41A"]),
        ("Order 37 CPC summary suit", ["CPC Order 37"]),
        ("CrPC Sec 437(3) conditions", ["CRPC Section 437(3)"]),
        ("Consumer Protection Act, 2019 Sec 2(6)", ["CPA Section 2(6)"]),
        ("§ 482 CrPC quashing", ["CRPC Section 482"]),
    ],
)
def test_single_reference_formats(text, expected):
    assert [str(p) for p in extract_provisions(text)] == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("under Sections 299 and 300 IPC", ["IPC Section 299", "IPC Section 300"]),
        (
            "Secs 41, 41A and 50 of CrPC",
            ["CRPC Section 41", "CRPC Section 41A", "CRPC Section 50"],
        ),
    ],
)
def test_enumerations(text, expected):
    """Legal prose lists provisions. Missing these under-counts citations."""
    assert [str(p) for p in extract_provisions(text)] == expected


def test_suffix_does_not_swallow_following_word():
    """Regression: the old suffix pattern allowed a space before the letters,
    so "Section 420 IPC" parsed as number "420 IP" -- which also destroyed the
    statute lookup by leaving only "PC" to match against."""
    got = extract_provisions("Section 420 IPC")[0]
    assert got.number == "420"
    assert got.statute == "IPC"


def test_deduplicates_repeated_references():
    text = "Section 420 IPC ... later, Section 420 IPC again"
    assert len(extract_provisions(text)) == 1


def test_empty_and_none_safe():
    assert extract_provisions("") == []
    assert extract_provisions("no legal references here at all") == []


# --- matching policy (docs/DECISIONS.md) ----------------------------------

A41 = Provision("Sec 41", "CRPC", "section", "41")
A41A = Provision("Sec 41A", "CRPC", "section", "41A")
IPC420 = Provision("Sec 420", "IPC", "section", "420")
BNS420 = Provision("Sec 420", "BNS", "section", "420")
BARE420 = Provision("Sec 420", None, "section", "420")


def test_strict_is_the_default_and_41A_is_not_41():
    """41 is 'when police may arrest'; 41A is 'notice of appearance'. A user
    who checks a source for 41A and finds 41 has not had it verified."""
    assert same_provision(A41A, A41) is False


def test_lenient_allows_subsection_to_match_parent():
    assert same_provision(A41A, A41, lenient=True) is True


def test_different_statutes_never_match():
    assert same_provision(IPC420, BNS420) is False


def test_unattributed_reference_matches_on_number():
    """'Section 420' with no Act named cannot be ruled out."""
    assert same_provision(BARE420, IPC420) is True


def test_provision_in_pool():
    pool = [IPC420, A41]
    assert provision_in(IPC420, pool) is True
    assert provision_in(A41A, pool) is False
    assert provision_in(A41A, pool, lenient=True) is True
