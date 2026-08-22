"""Translate a statutory citation between the pre- and post-2024 Indian codes.

WHAT PROBLEM THIS SOLVES
    On 1 July 2024 India replaced three colonial-era codes at once:

        Indian Penal Code 1860        -> Bharatiya Nyaya Sanhita 2023
        Code of Criminal Procedure    -> Bharatiya Nagarik Suraksha Sanhita
        Indian Evidence Act 1872      -> Bharatiya Sakshya Adhiniyam

    Which one governs depends on WHEN the conduct happened, not on when the
    question is asked. So the same situation has two correct answers:

        "husband beats me, this happened in March 2023"  -> IPC 498A
        "husband beats me, this happened last month"     -> BNS 85

    Every gold label in the evaluation therefore needs to be era-aware. This
    module is what makes that possible.

WHY IT IS A SEPARATE FILE AND A SEPARATE JSON
    The map is DATA, not logic. Keeping it in data/recodification_map.json
    means it can be released alongside the paper, cited, corrected by someone
    with legal training, and diffed in version control without touching code.

WHAT "MAPPING" DOES AND DOES NOT MEAN
    This is NOT renumbering. IPC 379 -> BNS 303(2) is not a relabelling: the
    BNS adds community service as a punishment for first-time theft under
    Rs 5,000. Several entries carry changes like that; see the `note` field.

    Sub-sections are load-bearing. "BNS 318" alone is the DEFINITION of
    cheating; the punishment that answers "what happens for a Rs 420 scam" is
    BNS 318(4). A bare section number is often materially incomplete.

    One entry has no counterpart at all. IPC 161 was repealed in 1988 by the
    Prevention of Corruption Act, 36 years before the BNS existed. Asking for
    "the BNS equivalent of IPC 161" has no answer, and the map says so rather
    than inventing one.

HOW FAR THE VERIFICATION GOES
    The 33 IPC->BNS entries were checked by pulling the target section out of
    this project's own Qdrant index and reading the bare-Act text to confirm
    the subject matches. That is SECTION-level verification. Sub-section
    attribution was not machine-checked and remains my reading.

    The 10 CrPC->BNSS entries could not be checked at all, because the BNSS is
    not in the corpus. They are marked `unverified_not_in_corpus` and are
    unreachable by the retriever by construction -- which makes them a
    legitimate refusal test rather than a defect to hide.

USAGE
    >>> to_new("IPC 420")
    ['BNS 318(4)']
    >>> to_old("BNS 85")
    ['IPC 498A']
    >>> for_regime(["IPC 498A"], "BNS_ERA")
    ['BNS 85']
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_MAP_PATH = Path(__file__).resolve().parents[1] / "data" / "recodification_map.json"

# Which corpora are actually ingested. A gold label naming anything else is
# unanswerable by construction, and the query set must say so out loud rather
# than scoring the system wrong for a corpus gap we created.
CORPORA_IN_INDEX = frozenset({"IPC", "BNS", "CRPC", "CPA"})

# Statutes untouched by the 2024 recodification. Their section numbers are the
# same in both eras, so "translating" them is a no-op, not a missing entry.
UNCHANGED = frozenset({"CPA"})

OLD_TO_NEW_STATUTE = {"IPC": "BNS", "CRPC": "BNSS", "IEA": "BSA"}
NEW_TO_OLD_STATUTE = {v: k for k, v in OLD_TO_NEW_STATUTE.items()}


class UnmappedProvision(KeyError):
    """Raised when a citation has no entry in the map.

    Deliberately loud. A silent fall-through would put an old-code citation
    into a new-code gold label, which is exactly the bug this module exists to
    remove -- it would score a system RIGHT for citing repealed law.
    """


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _forward() -> dict[str, list[str]]:
    return {r["from"]: list(r["to"]) for r in _load()["mappings"]}


@lru_cache(maxsize=1)
def _backward() -> dict[str, list[str]]:
    """New -> old. Many-to-one is real: BNS 303(2) came from IPC 379, and
    BNS 318(4) from IPC 420, but BNS 351(2) and 351(3) both come from IPC 506,
    so the reverse of 351(2) is a single-element list while a lookup of a
    merged section can legitimately return several old sections."""
    back: dict[str, list[str]] = {}
    for r in _load()["mappings"]:
        for t in r["to"]:
            back.setdefault(t, []).append(r["from"])
    return back


@lru_cache(maxsize=1)
def _meta_by_from() -> dict[str, dict]:
    return {r["from"]: r for r in _load()["mappings"]}


def statute_of(ref: str) -> str:
    """'IPC 498A' -> 'IPC'."""
    return ref.split(" ", 1)[0].upper()


def to_new(ref: str) -> list[str]:
    """Old-code citation -> new-code citation(s). Empty list = no counterpart."""
    if statute_of(ref) in UNCHANGED:
        return [ref]
    try:
        return list(_forward()[ref])
    except KeyError:
        raise UnmappedProvision(
            f"{ref!r} has no entry in {_MAP_PATH.name}. Add it rather than "
            f"letting an old-code citation through as new-code gold."
        ) from None


def _base_number(ref: str) -> str:
    """'BNS 305(a)' -> 'BNS 305'. Drops the sub-section only."""
    statute, number = ref.split(" ", 1)
    m = re.match(r"\d+[A-Za-z]?", number.strip())
    return f"{statute} {m.group(0)}" if m else ref


@lru_cache(maxsize=1)
def _backward_by_base() -> dict[str, list[str]]:
    """New-code refs grouped by base section number.

    Needed because the citation extractor reports "Section 305(a)" as number
    "305" -- the sub-section is dropped -- while the map stores the key as
    "BNS 305(a)". An exact reverse lookup then misses a mapping that exists.
    """
    out: dict[str, list[str]] = {}
    for new_ref, old_refs in _backward().items():
        out.setdefault(_base_number(new_ref), []).extend(old_refs)
    return out


def to_old(ref: str) -> list[str]:
    """New-code citation -> old-code citation(s)."""
    if statute_of(ref) in UNCHANGED:
        return [ref]
    try:
        return list(_backward()[ref])
    except KeyError:
        pass

    # Fall back to the base section number, but ONLY when it is unambiguous.
    #
    # BNS 305(a) is the sole entry with base 305, so "BNS 305" resolves
    # cleanly to IPC 380. BNS 318 is not: 318(1) came from IPC 415 (the
    # definition of cheating) and 318(4) from IPC 420 (cheating and
    # dishonestly inducing delivery). Those are different offences carrying
    # different punishments, and picking one would be a coin flip presented
    # as a lookup. Ambiguity raises instead.
    candidates = list(dict.fromkeys(_backward_by_base().get(_base_number(ref), [])))
    if len(candidates) == 1:
        return candidates
    if len(candidates) > 1:
        raise UnmappedProvision(
            f"{ref!r} is ambiguous without its sub-section: base "
            f"{_base_number(ref)!r} maps to {candidates}. Cite the sub-section."
        )
    raise UnmappedProvision(f"{ref!r} has no reverse entry in {_MAP_PATH.name}.")


def for_regime(refs: list[str], regime: str) -> list[str]:
    """Rewrite a whole gold list into the code that governs in `regime`.

    regime is one of IPC_ERA (conduct before 1 July 2024), BNS_ERA (on or
    after), or UNKNOWN. UNKNOWN returns both eras, because with no date there
    is genuinely no single correct citation -- see eval/layman_queries.py.

    Order is preserved and duplicates are dropped, so the result is stable
    across runs and safe to write into a fixed-seed query set.
    """
    out: list[str] = []
    for r in refs:
        if regime == "IPC_ERA":
            cand = [r] if statute_of(r) in OLD_TO_NEW_STATUTE or statute_of(r) in UNCHANGED else to_old(r)
        elif regime == "BNS_ERA":
            cand = to_new(r) if statute_of(r) in OLD_TO_NEW_STATUTE else [r]
        elif regime == "UNKNOWN":
            cand = [r] + (to_new(r) if statute_of(r) in OLD_TO_NEW_STATUTE else [])
        else:
            raise ValueError(f"unknown regime {regime!r}")
        for c in cand:
            if c not in out:
                out.append(c)
    return out


def note_for(ref: str) -> str:
    """The substantive-change note, if the map records one."""
    return (_meta_by_from().get(ref) or {}).get("note", "")


def confidence_for(ref: str) -> str:
    return (_meta_by_from().get(ref) or {}).get("confidence", "absent")


def answerable(refs: list[str]) -> bool:
    """True only if EVERY cited statute is actually ingested."""
    return bool(refs) and all(statute_of(r) in CORPORA_IN_INDEX for r in refs)
