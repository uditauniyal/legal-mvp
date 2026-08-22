"""Search the code that GOVERNS, not the code the user happened to name.

THE GAP THIS FILLS, IN ONE EXAMPLE
    A person types:

        "What is the punishment under Section 420 IPC? This happened last month."

    The Router sees "IPC", filters the search to the IPC, and returns IPC 420.
    Every step behaves correctly. The answer is still wrong law: the conduct
    is after 1 July 2024, so BNS 318(4) governs and IPC 420 was repealed.

    The filter is faithful to the WORDS. It has no way to know the words are
    out of date. That is the whole gap.

WHY THIS IS THE INTERVENTION PHASE G POINTED AT
    Phase G measured two things that look contradictory until you separate
    the symbolic layer from the dense one:

      With the corpus filter ON, cross-statute confusion nearly vanishes --
      BNS-numbered queries retrieved their gold 97.0% of the time.

      With the filter OFF, the embeddings alone manage 51.5% against a 22.3%
      chance baseline, and a query naming the Bharatiya Nyaya Sanhita gets an
      IPC chunk as its top result 19 times in 33.

    So the filter is doing real work and must stay. What it cannot do is
    notice that the code named in the query is no longer in force for the
    conduct described. This module adds exactly that, and nothing else.

WHAT IT DOES NOT DO
    It does not touch the embeddings, the reranker, or the scores. It changes
    ONE thing: which corpus the filter names. That is deliberate -- Phase H
    compares against Phase G, and a change that moves several parts at once
    produces a delta nobody can attribute.

THE THREE OUTCOMES

    era UNKNOWN         leave the user where they are. With no date there is
                        no basis to move them off the code they named, and
                        switching silently would be a guess dressed as a fact.

    era IPC_ERA/BNS_ERA translate through data/recodification_map.json and
                        search the governing code.

    era BOTH_ERAS       continuing conduct spanning the cutover. Search BOTH
                        halves of the pair, because incidents on either side
                        of 1 July 2024 answer to different codes and picking
                        one would drop half the answer.

WHEN THERE IS NO COUNTERPART
    IPC 161 (public servant taking gratification) was repealed in 1988 by the
    Prevention of Corruption Act -- thirty-six years before the BNS existed.
    Asking for "the BNS equivalent of IPC 161" has no answer. The map says so
    rather than inventing one, and this module surfaces that as a warning
    instead of silently dropping the citation.

SUBSTANTIVE CHANGE IS NOT RENUMBERING
    IPC 379 -> BNS 303(2) is not a relabelling: the BNS adds community
    service for first-time theft under Rs 5,000. Where the map records a
    change of that kind it is carried through as a note, so the answer can
    say the punishment moved rather than implying the provision merely
    changed number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.citations import Provision, extract_provisions, named_statutes
from core.dates import BOTH_ERAS, UNKNOWN, governing_statutes
from core.recodification import (
    CORPORA_IN_INDEX, UNCHANGED, UnmappedProvision, confidence_for, note_for, to_new, to_old,
)


@dataclass
class MappingDecision:
    """What to search, and a record of why -- so the change is auditable."""

    target_corpora: list[str] = field(default_factory=list)
    #   Corpora the retriever should restrict to. Empty means no filter.
    original: list[str] = field(default_factory=list)
    #   Citations exactly as the user wrote them.
    governing: list[str] = field(default_factory=list)
    #   The same citations under the code that actually governs.
    changed: bool = False
    #   True when translation moved something. The whole point of the log.
    rule: str = "no_change"
    warnings: list[str] = field(default_factory=list)
    #   Provisions with no counterpart, and unverified mappings.
    notes: list[str] = field(default_factory=list)
    #   Substantive changes carried across the recodification.

    def as_log(self) -> dict:
        return {
            "target_corpora": self.target_corpora,
            "original": self.original,
            "governing": self.governing,
            "changed": self.changed,
            "rule": self.rule,
            "warnings": self.warnings,
            "notes": self.notes,
        }


def _ref(p: Provision) -> str:
    """Provision -> the 'IPC 420' form the recodification map is keyed by."""
    return f"{p.statute} {p.number}"


def _translate(ref: str, era: str) -> tuple[list[str], str | None]:
    """One citation into the governing code. Returns (results, warning)."""
    statute = ref.split(" ", 1)[0].upper()

    if statute in UNCHANGED:
        return [ref], None                       # CPA was not recodified

    try:
        if era == BOTH_ERAS:
            # Both halves. to_new/to_old raise if the direction has no entry,
            # so each is attempted independently rather than as a pair.
            out: list[str] = []
            for fn in (to_new, to_old):
                try:
                    out.extend(fn(ref))
                except UnmappedProvision:
                    pass
            out = list(dict.fromkeys([ref, *out]))
            return out, None
        # Already written in the code that governs -> nothing to do.
        #
        # Checked BEFORE attempting a lookup, because the map is keyed
        # old -> new. Asking to_old() for "IPC 420" searches the reverse
        # index, whose keys are BNS references, finds nothing, and raises --
        # producing a "no entry in the recodification map" warning for a
        # citation that is perfectly correct and needs no mapping at all.
        target = governing_statutes(statute, era)
        if target and statute == target[0]:
            return [ref], None

        translated = to_new(ref) if era != "IPC_ERA" else to_old(ref)
    except UnmappedProvision:
        return [ref], (
            f"{ref} has no entry in the recodification map; left as written"
        )

    if not translated:
        return [ref], (
            f"{ref} has NO counterpart in the other code — it was repealed "
            f"separately, so there is nothing to translate it to"
        )
    return translated, None


def map_query(text: str, era: str) -> MappingDecision:
    """Decide which corpora to search, given the query and the resolved era.

    `era` comes from core.dates.resolve(). This function does not parse dates
    itself: keeping the two apart means the date logic can be tested against
    date strings and the mapping logic against citations, instead of every
    test needing both.
    """
    d = MappingDecision()
    provisions = [p for p in extract_provisions(text or "") if p.statute]
    d.original = list(dict.fromkeys(_ref(p) for p in provisions))

    # No date resolved -> change nothing. Stated as a rule rather than falling
    # out of the code by accident, because "do nothing" is the correct and
    # most common outcome: layman queries carry no date at all.
    if era == UNKNOWN:
        named = sorted(named_statutes(text or "") & CORPORA_IN_INDEX)
        d.target_corpora = named
        d.governing = list(d.original)
        d.rule = "era_unknown_no_change"
        return d

    # Citations the user wrote, moved into the code that governs.
    governing: list[str] = []
    for ref in d.original:
        translated, warning = _translate(ref, era)
        governing.extend(translated)
        if warning:
            d.warnings.append(warning)
        if note_for(ref):
            d.notes.append(f"{ref}: {note_for(ref)}")
        if confidence_for(ref) == "unverified_not_in_corpus":
            d.warnings.append(
                f"{ref} maps to a statute that is not in the index, so the "
                f"governing provision cannot be retrieved"
            )
    d.governing = list(dict.fromkeys(governing))

    # A query may name an Act without citing a section: "what does the IPC
    # say about cheating". Those still need the corpus moved.
    statutes = {r.split(" ", 1)[0].upper() for r in d.governing}
    for s in named_statutes(text or ""):
        statutes.update(governing_statutes(s, era))

    d.target_corpora = sorted(s for s in statutes if s in CORPORA_IN_INDEX)

    # The governing code may not be ingested. "Section 41 CrPC, last month"
    # resolves to BNSS 35, and the BNSS is not in the index -- which would
    # leave target_corpora empty and silently widen the search to all 1,899
    # chunks, 39% of which are CrPC anyway.
    #
    # Falling back to the code the user NAMED is better on both counts: it
    # retrieves something relevant, and the warning already attached above
    # says plainly that the provision actually in force cannot be reached.
    # An unfiltered search would have looked like a decision; this is one.
    if not d.target_corpora and d.original:
        fallback = sorted({r.split(" ", 1)[0].upper() for r in d.original}
                          & set(CORPORA_IN_INDEX))
        if fallback:
            d.target_corpora = fallback
            d.warnings.append(
                f"governing code not in the index; searching {fallback} "
                f"(the code named in the query) instead"
            )
    d.changed = d.governing != d.original and bool(d.original)
    d.rule = (
        "both_eras_search_both" if era == BOTH_ERAS
        else "translated_to_governing_code" if d.changed
        else "already_governing_code"
    )
    return d
