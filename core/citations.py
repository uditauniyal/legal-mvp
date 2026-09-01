"""Extract statutory references from free text.

This is the foundation of the Verifier (Stage 4.5). Everything the citation
audit reports depends on this module finding the same references a human
would find, and normalising them the same way every time.

Deterministic on purpose: no LLM, no randomness. The numbers this feeds
into go in a paper, so the same input must always give the same output.

WHAT COUNTS AS A REFERENCE
    "Section 420 IPC"        -> Provision(statute="IPC",  kind="section", number="420")
    "IPC Section 302"        -> Provision(statute="IPC",  kind="section", number="302")
    "Sec 138 of the NI Act"  -> Provision(statute="NI",   kind="section", number="138")
    "Article 22(1)"          -> Provision(statute=None,   kind="article", number="22(1)")
    "BNSS Sec 35"            -> Provision(statute="BNSS", kind="section", number="35")
    "s. 41A CrPC"            -> Provision(statute="CRPC", kind="section", number="41A")

ATTRIBUTION POLICY (revised 2026-09-01 -- see _statute_for_unit)
    A statute is bound to a number ONLY when the two sit in the same CITATION
    UNIT: the reference phrase itself, extended over connective filler only
    ("of", "the", "under", a year, punctuation, whitespace). Anything else
    between them -- a verb, a noun, a clause break -- and the statute is NOT
    attributed.

    Where nothing is attributable the statute is None, which renders as '?'
    in Provision.key. That is an EXPLICIT UNKNOWN, not a failure: it is the
    honest output when the text does not say which code a number belongs to.

    This replaced a nearest-name-within-60-characters rule that produced
    silently wrong labels on exactly the sentences this project studies --
    an answer that legitimately names both the IPC and the BNS.

MATCHING POLICY (decided 2026-08-22, see docs/DECISIONS.md)
    Strict by default: "41A" != "41". They are different provisions with
    different content, and a user who checks a source for 41A and finds 41
    has not had their citation verified.

    `same_provision(a, b, lenient=True)` also allows a sub-section to match
    its parent, so both a strict and a lenient rate can be reported. Strict
    is the headline number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# --------------------------------------------------------------------------
# Statute vocabulary
# --------------------------------------------------------------------------
# Maps every way a statute gets written in Indian legal prose to one canonical
# code. Order matters below: longer aliases are matched first so that
# "indian penal code" is not shadowed by a stray "ipc".

STATUTE_ALIASES: dict[str, str] = {
    # Penal
    "indian penal code": "IPC",
    "penal code": "IPC",
    "i.p.c": "IPC",
    "ipc": "IPC",
    "bharatiya nyaya sanhita": "BNS",
    "nyaya sanhita": "BNS",
    "bns": "BNS",
    # Procedure
    "code of criminal procedure": "CRPC",
    "criminal procedure code": "CRPC",
    "cr.p.c": "CRPC",
    "crpc": "CRPC",
    "bharatiya nagarik suraksha sanhita": "BNSS",
    "nagarik suraksha sanhita": "BNSS",
    "bnss": "BNSS",
    # Evidence
    "indian evidence act": "IEA",
    "evidence act": "IEA",
    "bharatiya sakshya adhiniyam": "BSA",
    "sakshya adhiniyam": "BSA",
    "bsa": "BSA",
    "iea": "IEA",
    # Civil / consumer / other Acts that appear in answers
    "consumer protection act": "CPA",
    "civil procedure code": "CPC",
    "code of civil procedure": "CPC",
    "c.p.c": "CPC",
    "cpc": "CPC",
    "negotiable instruments act": "NI",
    "ni act": "NI",
    "indian contract act": "CONTRACT",
    "contract act": "CONTRACT",
    "limitation act": "LIMITATION",
    "dowry prohibition act": "DOWRY",
    "hindu marriage act": "HMA",
    "legal services authorities act": "LSA",
    "information technology act": "IT",
    "it act": "IT",
    # Constitution
    "constitution of india": "CONSTITUTION",
    "constitution": "CONSTITUTION",
}

# Longest-first so multi-word aliases win over their own substrings.
_ALIASES_BY_LENGTH = sorted(STATUTE_ALIASES, key=len, reverse=True)
_STATUTE_RE = re.compile(
    "|".join(re.escape(a) for a in _ALIASES_BY_LENGTH), re.IGNORECASE
)

# --------------------------------------------------------------------------
# Reference patterns
# --------------------------------------------------------------------------
# A provision number is a run of digits, optionally followed by a letter
# suffix (41A, 304B) and/or a bracketed sub-clause (2(6), 437(3), 22(1)).
#
# NOTE the letter suffix must touch the digits with no space, and must end on
# a word boundary. Without both constraints "Section 420 IPC" parses as number
# "420 IP", which also destroys the statute lookup by leaving only "PC".
_NUM = r"\d+(?:[A-Za-z]{1,2}\b)?(?:\s*\(\s*\d+\s*\))?"

# Legal prose enumerates: "Sections 299 and 300", "Secs 41, 41A and 50".
# Capture the whole run after the keyword, then split it afterwards.
_SEP = r"(?:\s*(?:,|and|&|/|to)\s*)"
_NUM_LIST = rf"{_NUM}(?:{_SEP}{_NUM})*"

# "Section 420", "Sec. 420", "S. 420", "§420"  — the keyword comes first
_SECTION_RE = re.compile(
    rf"\b(?:sections|section|secs|sec|ss|s)\s*\.?\s*({_NUM_LIST})|§\s*({_NUM_LIST})",
    re.IGNORECASE,
)

# "Article 22(1)", "Art. 21", "Articles 14 and 21"
_ARTICLE_RE = re.compile(
    rf"\b(?:articles|article|arts|art)\s*\.?\s*({_NUM_LIST})", re.IGNORECASE
)

# "Order 39", "Rule 4" — CPC-style references
_ORDER_RE = re.compile(rf"\b(orders?|rules?)\s*\.?\s*({_NUM_LIST})", re.IGNORECASE)

# Pulls the individual numbers back out of a captured enumeration.
_SINGLE_NUM_RE = re.compile(_NUM)

# --------------------------------------------------------------------------
# Citation units
# --------------------------------------------------------------------------
# A CITATION UNIT is the reference itself plus every character adjoining it
# that carries no propositional content. Two kinds of token may adjoin:
#
#   FILLER  whitespace , ( ) [ ] * | /   punctuation, markdown and table pipes
#           of  the  under               the function words Indian drafting
#                                        puts between an Act and a section
#           1860  2019                   the year an Act is cited with
#
#   ALIAS   any statute name in STATUTE_ALIASES
#
# Deliberately NOT filler: every content word, every conjunction ("and",
# "or", "which", "read with"), and the sentence-level marks . ; : - — .
# Those are what end one assertion and begin the next, so they must break
# attribution. Excluding "." is what makes
#     "...the Indian Penal Code. Section 190 now applies"
# come out UNKNOWN instead of IPC.
#
# The pipe and slash are filler because this system's answers cite in markdown
# tables -- "| Indian Penal Code (IPC) | Sec 302 | Punishment for murder |".
# One row is one citation unit: the Act cell and the section cell are bound by
# the table's own structure, not by proximity. (Found by reading the real
# answers in runs/, not assumed -- see results/_explain_w1_s3.md section 8.)
_FILLER_TOKEN = r"[\s,()\[\]*|/]|of\b|the\b|under\b|\d{4}\b"

_ALIAS_ALT = "|".join(re.escape(a) for a in _ALIASES_BY_LENGTH)

# One token of a citation unit. Atomic: once a token has matched, the engine
# never re-enters it to try a different alias. Without that, a long run of
# aliases and filler can backtrack exponentially.
_UNIT_TOKEN = rf"(?>(?:{_ALIAS_ALT})\b|{_FILLER_TOKEN})"

# The longest run of unit tokens ENDING where the reference begins.
_UNIT_BEFORE_RE = re.compile(rf"(?:{_UNIT_TOKEN})*\Z", re.IGNORECASE)
# The longest run of unit tokens STARTING where the reference ends.
_UNIT_AFTER_RE = re.compile(rf"^(?:{_UNIT_TOKEN})*", re.IGNORECASE)
# Filler with no statute names in it, used to test whether an Act is glued to
# the reference on its OTHER side.
_FILLER_RUN_RE = re.compile(rf"(?:{_FILLER_TOKEN})*", re.IGNORECASE)

# Filler that divides one list item from the next, as opposed to filler that
# merely joins words. "Section 302 IPC" is joined; "Section 302 | IPC" is not.
_LIST_SEPARATORS = "/|,;"

# Only a bound on how much text is sliced, NOT part of the rule. A run of pure
# connective filler longer than this does not occur in legal prose; the cap
# exists so the regexes never scan a whole 4,000-character answer per match.
_UNIT_SCAN = 200


@dataclass(frozen=True)
class Provision:
    """One statutory reference, normalised.

    raw      : the text exactly as it appeared, for debugging and logs
    statute  : canonical code ("IPC", "BNS", ...) or None if unattributed
    kind     : "section" | "article" | "order" | "rule"
    number   : normalised number, uppercased, whitespace stripped ("41A", "2(6)")
    """

    raw: str
    statute: str | None
    kind: str
    number: str

    @property
    def key(self) -> str:
        """Canonical string form, e.g. 'IPC:section:420' or '?:article:22(1)'."""
        return f"{self.statute or '?'}:{self.kind}:{self.number}"

    def __str__(self) -> str:  # pragma: no cover - display only
        prefix = f"{self.statute} " if self.statute else ""
        return f"{prefix}{self.kind.capitalize()} {self.number}"


def _normalise_number(num: str) -> str:
    """'41 A' -> '41A';  '2 ( 6 )' -> '2(6)'."""
    return re.sub(r"\s+", "", num).upper()


def _reference_starts_at(text: str, pos: int) -> bool:
    """Does a new statutory reference begin exactly at `pos`?"""
    return any(r.match(text, pos) for r in (_SECTION_RE, _ARTICLE_RE, _ORDER_RE))


def _trailing_statutes(right: str) -> set[str]:
    """Acts that FOLLOW a reference and belong to it.

    An Act that is really the heading of the NEXT reference does not belong to
    this one. Both of these list a provision under each code, and they differ
    only in which side of its number each Act sits on:

        "Section 357A CrPC / Section 396 BNSS"    -> CRPC 357A, BNSS 396
        "CrPC Section 154(3) / BNSS Section 175(3)" -> CRPC 154(3), BNSS 175(3)

    In the second, the Act following 154(3) is BNSS -- but a list SEPARATOR
    stands between them, and BNSS is glued to its own "Section 175(3)". It is
    that citation's Act, not this one's. Dropping it lets the leading "CrPC"
    be used instead, which is the right answer.

    In the first, nothing but a space stands between 357A and CrPC, so CrPC is
    this citation's Act even though another reference follows it.

    So an Act is discarded only when BOTH hold: a separator (/ | , ;) divides
    it from this reference, AND a reference begins right after it.
    """
    run = _UNIT_AFTER_RE.match(right)
    out: set[str] = set()
    for m in _STATUTE_RE.finditer(run.group(0)):
        separated = any(c in _LIST_SEPARATORS for c in right[: m.start()])
        gap = _FILLER_RUN_RE.match(right, m.end())
        if separated and _reference_starts_at(right, gap.end()):
            continue
        out.add(STATUTE_ALIASES[m.group(0).lower()])
    return out


def _statute_for_unit(text: str, start: int, end: int) -> str | None:
    """The statute in the SAME CITATION UNIT as a reference, or None.

    Indian legal prose attaches the Act on either side of the number:
        "Section 420 IPC"         -> after
        "IPC Section 302"         -> before
        "Sec 138 of the NI Act"   -> after, connective words between

    All three are one citation unit: nothing stands between the Act and the
    number except connective filler. This function attributes ONLY in that
    case.

    WHAT THIS REPLACED, AND WHY
        The previous rule took whichever statute name sat NEAREST within 60
        characters, on either side. On a corpus of Indian legal answers that
        is not a small inaccuracy, it is a targeted one. India replaced the
        IPC with the BNS on 1 July 2024 and both remain operative depending
        on the date of the offence, so a correct answer names both codes in
        one paragraph:

            "Under the Indian Penal Code the offence was punishable, and the
             corresponding provision is now Section 190."

        Section 190 is BNS. "Indian Penal Code" was the nearest name, so the
        old rule recorded IPC Section 190 -- confidently, silently, and
        wrongly. The error concentrated on exactly the recodification queries
        this project is about, which is worse than a uniform error rate:
        it correlated with the treatment.

        Under the unit rule, "is now" is not connective filler, so nothing
        attaches and the provision is returned with statute=None.

    A TRAILING STATUTE IS DECISIVE
        Indian citation form writes the Act AFTER the number -- "Section 420
        IPC", "Sec 138 of the NI Act". When exactly one Act follows the
        number through filler alone, that is a citation, and it settles the
        question on its own:

            "Sec 154 CrPC / Sec 173 BNSS"   ->  CRPC 154 and BNSS 173

        A LEADING Act is a different thing: a heading, a table header cell,
        a topic sentence. It is used only as a fallback, and only when the
        whole unit names one code.

    MORE THAN ONE STATUTE, NONE OF THEM TRAILING
        Then the unit must name exactly ONE code or nothing is bound:

            "| Bharatiya Nyaya Sanhita (BNS) / (IPC) | Sec 103 (Sec 302 IPC) |"

        The header cell names two codes and neither trails Sec 103, so the
        text does not say which one Sec 103 belongs to -> None. The old rule
        answered IPC here with full confidence. The right answer is BNS.

        Naming two aliases of the SAME code ("Indian Penal Code (IPC)") is one
        statute, not two: the comparison is over canonical codes.
    """
    left = text[max(0, start - _UNIT_SCAN) : start]
    right = text[end : end + _UNIT_SCAN]

    before = _UNIT_BEFORE_RE.search(left)

    trailing = _trailing_statutes(right)
    if len(trailing) == 1:
        return trailing.pop()

    unit = trailing | named_statutes(before.group(0) if before else "")
    return unit.pop() if len(unit) == 1 else None


def extract_provisions(text: str) -> list[Provision]:
    """Pull every statutory reference out of a block of text.

    Returns them in order of appearance, de-duplicated by `key` so that an
    Act mentioned five times in one answer counts once.
    """
    if not text:
        return []

    found: list[Provision] = []
    seen: set[str] = set()

    def add_run(raw: str, kind: str, number_run: str, start: int, end: int) -> None:
        """Record every number in an enumeration, all sharing one statute.

        "Sections 299 and 300 IPC" yields IPC 299 and IPC 300 — the statute is
        resolved once against the whole match, then applied to each number.

        The enumeration IS the citation unit. "IPC" is attached to the run,
        not to "300" alone, so every number in the run inherits it. Splitting
        the run first and attributing each number separately would leave 299
        unattributed, which is why attribution happens here and not inside
        the loop.
        """
        statute = _statute_for_unit(text, start, end)
        for nm in _SINGLE_NUM_RE.finditer(number_run):
            prov = Provision(
                raw=raw.strip(),
                statute=statute,
                kind=kind,
                number=_normalise_number(nm.group(0)),
            )
            if prov.key not in seen:
                seen.add(prov.key)
                found.append(prov)

    for m in _SECTION_RE.finditer(text):
        number_run = m.group(1) or m.group(2)
        if number_run:
            add_run(m.group(0), "section", number_run, m.start(), m.end())

    for m in _ARTICLE_RE.finditer(text):
        add_run(m.group(0), "article", m.group(1), m.start(), m.end())

    for m in _ORDER_RE.finditer(text):
        kind = m.group(1).lower().rstrip("s")
        add_run(m.group(0), kind, m.group(2), m.start(), m.end())

    return found


def same_provision(a: Provision, b: Provision, lenient: bool = False) -> bool:
    """Do two references point at the same provision?

    Strict (default):
        statute and number must match exactly. "41A" != "41".

    Lenient:
        additionally allows a sub-provision to match its parent, so
        "41A" matches "41" and "2(6)" matches "2". Reported as a second
        number alongside the strict one; never as the headline.

    A reference with no statute attached ("Article 22(1)" alone) matches on
    kind and number only, because we cannot rule out that it belongs to the
    statute it is being compared against.
    """
    if a.kind != b.kind:
        return False

    if a.statute and b.statute and a.statute != b.statute:
        return False

    if a.number == b.number:
        return True

    if not lenient:
        return False

    return _base_number(a.number) == _base_number(b.number)


def _base_number(number: str) -> str:
    """'41A' -> '41';  '2(6)' -> '2';  '437(3)' -> '437'."""
    return re.match(r"\d+", number).group(0) if re.match(r"\d+", number) else number


def provision_in(target: Provision, pool: Iterable[Provision], lenient: bool = False) -> bool:
    """Is `target` present anywhere in `pool`?"""
    return any(same_provision(target, p, lenient=lenient) for p in pool)


def named_statutes(text: str) -> set[str]:
    """Every statute NAMED in the text, whether or not a section is cited.

    extract_provisions() needs a section number to anchor to, so it finds
    nothing in

        "what are the grounds for divorce under the Hindu Marriage Act"

    even though the user named the Act unmistakably. This function answers the
    weaker question -- which Acts were mentioned at all -- which is what a
    corpus-boundary check needs.

    WHY THIS EXISTS AT ALL
        Measured on this index: the highest similarity score for an
        OUT-of-corpus query (Hindu Marriage Act divorce, 0.519) is higher than
        five of six IN-corpus queries, the lowest of which is 0.278. The two
        distributions are not merely overlapping, they are inverted, so no
        similarity threshold can tell "we do not hold this law" from "this is
        a hard question about a law we do hold".

        Naming is the one signal that is not noisy: if the user says
        "Negotiable Instruments Act" and we never indexed it, that is certain,
        not probabilistic.

    LIMITATION, STATED PLAINLY
        It fires only when a statute is named. Layman queries name nothing --
        "husband beats me, what can I do" mentions no Act at all -- so this
        gate cannot help them. That is a real hole, not a bug to be patched
        with a threshold, and it is exactly what the Router is for.

    >>> sorted(named_statutes("Section 138 of the NI Act and Section 420 IPC"))
    ['IPC', 'NI']
    """
    return {
        STATUTE_ALIASES[m.group(0).lower()]
        for m in _STATUTE_RE.finditer(text or "")
    }
