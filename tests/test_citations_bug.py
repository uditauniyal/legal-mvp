"""Statute-to-section binding: the citation-unit rule (core/citations.py).

WHAT THIS FILE PINS

core/citations.py used to bind a statute to a section number by PROXIMITY --
it searched 60 characters either side of the number and took whichever Act
name sat nearest. Every test here exists because that rule was wrong in a way
that mattered specifically to this project.

India replaced the IPC (Indian Penal Code, 1860) with the BNS (Bharatiya
Nyaya Sanhita, 2023) on 1 July 2024, and both remain operative depending on
when the offence happened. So a CORRECT answer names both codes in one
paragraph. The proximity rule then read

    "Under the Indian Penal Code the offence was punishable, and the
     corresponding provision is now Section 190."

as IPC Section 190. Section 190 is BNS. The error was not spread evenly over
the corpus -- it landed on exactly the recodification queries the paper
studies, which means it correlated with the treatment being measured. Two
metrics were retired over it.

The replacement rule binds a statute only inside one CITATION UNIT: the
reference plus adjoining material that carries no meaning of its own
(whitespace, brackets, table pipes, "of"/"the"/"under", a year). Where the
unit names no Act, or names two different Acts, the result is an EXPLICIT
UNKNOWN -- Provision.statute is None and Provision.key renders '?'.

Every expectation below was worked out from the Indian statute itself and
from the rule, then asserted. None of it was copied from program output.
"""

import pytest

from core.citations import Provision, extract_provisions


def keys(text: str) -> list[str]:
    """['IPC:section:420', ...] -- statute, kind and number in one string."""
    return [p.key for p in extract_provisions(text)]


def statute_of(text: str, number: str) -> str | None:
    """The statute bound to `number`, or None. Fails loudly if not found."""
    matches = [p for p in extract_provisions(text) if p.number == number]
    assert matches, f"no provision numbered {number} was extracted from {text!r}"
    assert len(matches) == 1, f"{number} extracted more than once from {text!r}"
    return matches[0].statute


# ---------------------------------------------------------------------------
# 1. THE REGRESSION. This is the sentence the bug was found on.
# ---------------------------------------------------------------------------

REGRESSION = (
    "Under the Indian Penal Code the offence was punishable, and the "
    "corresponding provision is now Section 190."
)


def test_regression_penal_code_does_not_capture_a_bns_section():
    """"Indian Penal Code" is 90 characters away and separated from the number
    by a verb, a clause break and a conjunction. It is not in the same
    citation unit, so it must not be attributed."""
    assert statute_of(REGRESSION, "190") != "IPC"


def test_regression_yields_an_explicit_unknown_not_a_guess():
    """The honest answer is 'the text does not say'. That is statute=None,
    which Provision.key renders as '?'."""
    assert statute_of(REGRESSION, "190") is None
    assert keys(REGRESSION) == ["?:section:190"]


def test_a_full_stop_breaks_attribution():
    """A sentence boundary ends a citation unit. Nothing carries across it."""
    text = "The offence falls under the Indian Penal Code. Section 190 now applies."
    assert statute_of(text, "190") is None


# ---------------------------------------------------------------------------
# 2. PRESERVED BEHAVIOURS. These worked before and must still work.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        # statute AFTER the number -- the canonical Indian citation form
        ("Section 420 IPC", ["IPC:section:420"]),
        # statute BEFORE the number
        ("IPC Section 302", ["IPC:section:302"]),
        # words between: "of the" is connective filler, not content
        ("Sec 138 of the NI Act", ["NI:section:138"]),
        # an enumeration shares ONE statute across every number in the run
        ("Sections 299 and 300 IPC", ["IPC:section:299", "IPC:section:300"]),
    ],
)
def test_the_four_forms_that_must_keep_working(text, expected):
    assert keys(text) == expected


def test_enumeration_does_not_strand_the_first_number():
    """The enumeration IS the citation unit. If the fix had attributed each
    number separately, 299 would have come out UNKNOWN because "IPC" only
    touches 300. That failure mode is why this assertion is separate."""
    assert statute_of("Sections 299 and 300 IPC", "299") == "IPC"
    assert statute_of("Sections 299 and 300 IPC", "300") == "IPC"


def test_longer_enumeration_with_a_trailing_of_clause():
    assert keys("Secs 41, 41A and 50 of CrPC") == [
        "CRPC:section:41",
        "CRPC:section:41A",
        "CRPC:section:50",
    ]


def test_a_year_between_the_act_and_the_section_is_filler():
    """"Consumer Protection Act, 2019 Sec 2(6)" -- the comma and the year are
    how the Act is cited, not a break between two thoughts."""
    assert keys("Consumer Protection Act, 2019 Sec 2(6)") == ["CPA:section:2(6)"]


def test_unattributed_article_is_still_unattributed():
    """Article 22(1) is a Constitution provision, but the text does not say
    so. It was None before the fix and it is None after."""
    assert keys("Article 22(1) right to be informed") == ["?:article:22(1)"]


# ---------------------------------------------------------------------------
# 3. BOTH CODES IN ONE ANSWER -- the population the paper is about.
# ---------------------------------------------------------------------------


def test_both_codes_named_each_section_binds_to_its_own_code():
    """Section 190 BNS and Section 149 IPC both define unlawful assembly
    liability; 190 is the BNS re-enactment of 149. An answer explaining the
    change names both, and each number must reach its own Act."""
    text = "Section 190 of the Bharatiya Nyaya Sanhita replaced Section 149 IPC."
    assert statute_of(text, "190") == "BNS"
    assert statute_of(text, "149") == "IPC"


def test_paired_citation_with_the_act_after_each_number():
    """"Section 357C CrPC / Section 397 BNSS" -- victim's right to free medical
    treatment under the old code and the new. A space only, so each Act binds
    to the number it follows."""
    text = "Under Section 357C of the CrPC / Section 397 of the BNSS, all hospitals"
    assert statute_of(text, "357C") == "CRPC"
    assert statute_of(text, "397") == "BNSS"


def test_paired_citation_with_the_act_before_each_number():
    """The mirror image: "CrPC Section 154(3) / BNSS Section 175(3)". Here BNSS
    follows 154(3), but a '/' divides them and BNSS is glued to its own
    Section 175(3). The old proximity rule read 154(3) as BNSS."""
    text = "a representation to the SP (under CrPC Section 154(3) / BNSS Section 175(3))"
    assert statute_of(text, "154(3)") == "CRPC"
    assert statute_of(text, "175(3)") == "BNSS"


def test_markdown_table_row_is_one_citation_unit():
    """The system answers in markdown tables. A row binds its Act cell to its
    section cell structurally, so the pipe does not break the unit."""
    text = "| Indian Penal Code (IPC) | Sec 302 | Punishment for murder |"
    assert statute_of(text, "302") == "IPC"


def test_table_row_naming_two_codes_binds_neither():
    """A header cell reading "BNS / (IPC)" does not say which code Sec 103
    belongs to. It is BNS -- 103 is the BNS murder provision, IPC 302 is the
    old one -- but the TEXT does not establish that, so the parser must not
    claim it. The old rule confidently said IPC, because "(IPC)" sat nearest."""
    text = "| **Bharatiya Nyaya Sanhita (BNS)** / *(IPC)* | Sec 103 | Murder |"
    assert statute_of(text, "103") is None


def test_two_aliases_of_the_same_code_are_one_statute_not_a_conflict():
    """"Code of Criminal Procedure (CrPC)" names CRPC twice, not two codes."""
    assert statute_of("Section 154 of the Code of Criminal Procedure (CrPC)", "154") == "CRPC"


# ---------------------------------------------------------------------------
# 4. UNKNOWN IS A VALUE, NOT AN ERROR.
# ---------------------------------------------------------------------------


def test_bare_section_number_is_unknown():
    assert extract_provisions("Section 190")[0].statute is None


def test_unknown_uses_none_and_not_a_sentinel_string():
    """Reusing None keeps three existing behaviours working, all of which were
    checked before this was decided:

      - Provision.key already renders None as '?'
      - same_provision() treats a statute-less reference as matching on number
        alone, which is what makes prose match statutory text (a retrieved
        chunk reads "Section 302. Punishment for murder" and names no Act)
      - core/statute_mapper.py filters with `if p.statute`, and
        core/verifier.py guards with `if not p.statute` and `if not cited`

    A sentinel string such as "UNKNOWN" would be truthy and would silently
    walk past all four of those guards."""
    p = extract_provisions("Section 190")[0]
    assert p.statute is None
    assert p.key == "?:section:190"
    assert p == Provision(raw="Section 190", statute=None, kind="section", number="190")


def test_unknown_and_attributed_are_different_provisions():
    """'?:section:190' and 'BNS:section:190' are distinct keys, so an answer
    that cites 190 once bound and once loose reports both. That is deliberate:
    collapsing them would hide the loose one."""
    text = "Section 190 of the BNS is the provision. Section 190 is what applies."
    assert keys(text) == ["BNS:section:190", "?:section:190"]


# ---------------------------------------------------------------------------
# 5. THE BOUNDARY OF THE RULE, stated so it is not mistaken for a bug.
# ---------------------------------------------------------------------------


def test_an_act_named_in_the_previous_sentence_is_not_attributed():
    """This is under-attribution, and it is the intended trade. A human would
    bind 420 to the IPC here; the parser will not, because a sentence boundary
    and a content word stand in the way. Wrong-but-confident was the failure
    that cost two metrics; silent-and-honest is recoverable."""
    text = "The IPC punishes cheating. Section 420 covers it."
    assert statute_of(text, "420") is None


def test_a_conjunction_breaks_the_unit_even_inside_one_sentence():
    """"or" is not filler. 200 gets CrPC; 156(3) does not."""
    text = "before the Magistrate under Section 156(3) or Section 200 of the CrPC"
    assert statute_of(text, "200") == "CRPC"
    assert statute_of(text, "156(3)") is None


def test_the_rule_never_invents_a_statute_where_the_old_one_found_none():
    """Attribution can only get stricter, never looser. Measured over all 6,687
    citation units in runs/*/queries.jsonl, zero units gained a statute."""
    assert extract_provisions("Section 190")[0].statute is None
    assert extract_provisions("Article 21")[0].statute is None
    assert extract_provisions("Order 39 Rule 1")[0].statute is None
