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

# How far either side of the number we look for a statute name.
_STATUTE_WINDOW = 60


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


def _statute_near(text: str, start: int, end: int) -> str | None:
    """Find the statute named closest to a reference.

    Indian legal prose puts the Act on either side:
        "Section 420 IPC"     -> after
        "IPC Section 302"     -> before
        "Sec 138 of the NI Act" -> after, with words between

    We search a window on both sides and take whichever candidate sits
    nearest to the number, so that in a sentence naming two Acts the
    closer one wins.
    """
    left = text[max(0, start - _STATUTE_WINDOW) : start]
    right = text[end : end + _STATUTE_WINDOW]

    best: tuple[int, str] | None = None  # (distance, canonical)

    for m in _STATUTE_RE.finditer(left):
        distance = len(left) - m.end()
        canonical = STATUTE_ALIASES[m.group(0).lower()]
        if best is None or distance < best[0]:
            best = (distance, canonical)

    for m in _STATUTE_RE.finditer(right):
        distance = m.start()
        canonical = STATUTE_ALIASES[m.group(0).lower()]
        if best is None or distance < best[0]:
            best = (distance, canonical)

    return best[1] if best else None


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
        """
        statute = _statute_near(text, start, end)
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
