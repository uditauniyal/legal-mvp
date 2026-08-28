"""Citation audit — does the answer cite what the system actually retrieved?

THE QUESTION THIS ANSWERS
    A retrieval-augmented system is supposed to work like an open-book exam:
    look up passages, then answer using only those passages. This module checks
    whether that happened, by comparing the statutory provisions cited in the
    answer against the provisions present in the passages that were retrieved.

    Observed on one recorded query already:
        answer cited        BNSS 35, 47, 48, 58, Constitution Art 22(1)
        retrieval contained BNS 193, 203, 190, 176, 2, 136
        overlap             ZERO

TERMINOLOGY (established, so the paper is findable)
    grounded        the cited provision IS in the retrieved passages
    ungrounded      it is NOT — "extrinsic hallucination" (Ji et al. 2023)
    out_of_corpus   the Act itself was never indexed, so the model could not
                    possibly have retrieved it
    corpus-vintage mismatch
                    the answer cites one side of a recodification pair while
                    the index holds only the other — e.g. citing BNSS 35 when
                    the corpus holds CrPC 41. Specific to jurisdictions that
                    have recodified.

                    NOT called a "vintage error". Whether the citation is
                    legally wrong depends on when the conduct happened, which
                    this module does not know. What it CAN say is that the
                    cited provision was unreachable from this index — a
                    property of the corpus, not a verdict on the law. The two
                    are separate findings and conflating them would overclaim.

                    Counted in two directions, because they are different
                    failures with different causes:

                      cited_successor    cited BNSS/BNS, index holds CrPC/IPC.
                                         The model reached past the corpus into
                                         its training data for the newer code.

                      cited_predecessor  cited CrPC/IPC, index holds only the
                                         successor. The model fell back to the
                                         repealed numbering that dominates the
                                         legal corpora it was trained on.

    Note: ungrounded is NOT the same as wrong. A provision can be correct law
    and still be ungrounded, because groundedness is about whether the SOURCES
    support it, not about whether it is true.

THREE METRICS
    ungrounded_rate       cited but not retrieved
    out_of_corpus_rate    cited but not even indexed
    panel_prose_jaccard   overlap between the sources SHOWN to the user and the
                          provisions CITED in the prose

    The third has no published baseline. It measures something ALCE and RAGAS
    do not model: both assume citations are inline, bound to claims. Here the
    citation panel is a separate display channel with no binding at all, so a
    diligent user who checks every listed source will never encounter the
    provision the answer actually relied on.

Fully deterministic — no LLM, no randomness. Same input, same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from core.citations import (
    Provision, extract_provisions, provision_in, same_provision,
)


@dataclass
class CorpusIndex:
    """What is actually searchable.

    acts      canonical codes present, e.g. {"IPC", "BNS", "CRPC", "CPA"}
    sections  the provisions found in those documents
    """

    acts: set[str] = field(default_factory=set)
    sections: list[Provision] = field(default_factory=list)

    def has_act(self, statute: str | None) -> bool:
        # A reference with no Act named cannot be ruled out.
        return True if statute is None else statute in self.acts

    def has_provision(self, prov: Provision, lenient: bool = False) -> bool:
        return provision_in(prov, self.sections, lenient=lenient)


@dataclass
class AuditResult:
    cited: list[Provision] = field(default_factory=list)
    grounded: list[Provision] = field(default_factory=list)
    ungrounded: list[Provision] = field(default_factory=list)
    out_of_corpus: list[Provision] = field(default_factory=list)
    retrieved: list[Provision] = field(default_factory=list)
    panel: list[Provision] = field(default_factory=list)
    vintage_mismatches: list[dict] = field(default_factory=list)

    # strict metrics (headline)
    ungrounded_rate: float = 0.0
    out_of_corpus_rate: float = 0.0
    panel_prose_jaccard: float = 0.0
    # lenient variant: a sub-section may match its parent (41A counts as 41)
    ungrounded_rate_lenient: float = 0.0

    @property
    def n_cited(self) -> int:
        return len(self.cited)

    def summary(self) -> dict:
        return {
            "n_cited": self.n_cited,
            "n_grounded": len(self.grounded),
            "n_ungrounded": len(self.ungrounded),
            "n_out_of_corpus": len(self.out_of_corpus),
            "ungrounded_rate": round(self.ungrounded_rate, 4),
            "ungrounded_rate_lenient": round(self.ungrounded_rate_lenient, 4),
            "out_of_corpus_rate": round(self.out_of_corpus_rate, 4),
            "panel_prose_jaccard": round(self.panel_prose_jaccard, 4),
            "n_vintage_mismatch": len(self.vintage_mismatches),
            # Reported separately: they are different failures, and a single
            # total would let one direction mask the other.
            "n_cited_successor": sum(
                1 for v in self.vintage_mismatches if v["relation"] == "cited_successor"),
            "n_cited_predecessor": sum(
                1 for v in self.vintage_mismatches if v["relation"] == "cited_predecessor"),
        }


# Old scheme -> new scheme, for detecting "right law, wrong code" citations.
# This is Act-level only; the section-level map is a separate data artifact.
RECODIFICATION = {"IPC": "BNS", "CRPC": "BNSS", "IEA": "BSA"}
REVERSE_RECODIFICATION = {v: k for k, v in RECODIFICATION.items()}


def _vintage_relation(cited: str | None, corpus_acts: set[str]) -> tuple[str, str] | None:
    """Detect a corpus-vintage mismatch and name its direction.

    Fires only when the cited Act is ABSENT from the index and its
    recodification partner is PRESENT. Both conditions matter:

      - if the cited Act is in the index, there is no mismatch to report; the
        citation may still be ungrounded, but that is the other metric's job
      - if neither side is indexed, the citation is simply out_of_corpus, and
        calling it a vintage mismatch would attribute it to the recodification
        when the real cause is that we never loaded the statute

    With the current index (IPC, BNS, CrPC, CPA) both halves of the IPC/BNS
    pair are present, so that pair never fires -- correctly. The reachable
    case is a BNSS citation against a CrPC-only index.

    Returns (act_present_in_corpus, relation).
    """
    if not cited:
        return None
    if cited in REVERSE_RECODIFICATION:                 # cited the SUCCESSOR code
        predecessor = REVERSE_RECODIFICATION[cited]
        if predecessor in corpus_acts and cited not in corpus_acts:
            return predecessor, "cited_successor"
    if cited in RECODIFICATION:                         # cited the PREDECESSOR code
        successor = RECODIFICATION[cited]
        if successor in corpus_acts and cited not in corpus_acts:
            return successor, "cited_predecessor"
    return None


_SECTION_HEAD = re.compile(r"Section\s+(\d+[A-Za-z]?)")


def provisions_from_chunks(chunks: Iterable[dict]) -> list[Provision]:
    """The provisions retrieval ACTUALLY returned, with authoritative statutes.

    WHY THIS EXISTS
        extract_provisions() reads free text and guesses which Act a section
        number belongs to by looking for an Act name within 60 characters.
        That is the only option for prose. It is NOT the only option for a
        retrieved chunk: the chunk carries a `corpus` field written by the
        ingest pipeline from an explicit filename lookup. That label is a
        fact, not an inference.

        Using it removes the guess from one whole side of every comparison.

    FALLBACK, AND ITS LIMIT
        `section_number` is present on every chunk in the index but was not
        being copied into the run log, so older records only have `text_head`.
        Section-split chunks usually begin "Section 190. ...", so the number
        is recoverable -- but NOT always: a continuation piece can begin
        "Explanation.—A threat to injure ...", with no number at all.

        Those chunks are skipped rather than guessed at. Skipping under-counts
        what was retrieved, which biases the grounding rate DOWNWARD -- the
        safe direction for a claim about how ungrounded a system is.
    """
    out: list[Provision] = []
    for c in chunks:
        corpus = c.get("corpus")
        if not corpus:
            continue
        number = c.get("section_number")
        if not number:
            m = _SECTION_HEAD.search(c.get("text_head") or c.get("text") or "")
            number = m.group(1) if m else None
        if not number:
            continue
        out.append(Provision(raw=f"{corpus} Section {number}",
                             statute=corpus, kind="section", number=str(number).upper()))
    return out


def reattribute(cited: Iterable[Provision],
                retrieved: Iterable[Provision]) -> tuple[list[Provision], list[dict]]:
    """Fix statute labels the proximity heuristic got wrong.

    THE BUG THIS REMOVES
        Observed in the Phase H run: an answer cited BNS 190 and was recorded
        as "IPC Section 190", because the phrase "Indian Penal Code" appeared
        earlier in the same answer -- it was in the QUESTION. Retrieval had
        returned BNS chunks only. The metric then reported 100% wrong-era
        citations both before AND after the intervention, and so could not
        distinguish "wrongly relied on repealed law" from "correctly explained
        the law changed". Two opposite behaviours, one number.

    THE RULE, DELIBERATELY CONSERVATIVE
        Re-attribute only when BOTH hold:

          1. nothing retrieved matches the cited statute AND number, and
          2. exactly one retrieved STATUTE matches the number alone.

        So "you cited IPC 190; no IPC 190 was retrieved, but BNS 190 was, and
        nothing else numbered 190" -> the proximity guess was wrong, correct it.

        If the cited statute IS present in the retrieval, the citation is left
        alone -- the model may well have meant it. If several statutes share
        the number, it is genuinely ambiguous and nothing is changed. Both
        cases fail toward leaving the original label, because a wrong
        correction is worse than a missed one.

    Returns (possibly-corrected citations, a record of every change made).
    """
    retrieved = list(retrieved)
    corrections: list[dict] = []
    out: list[Provision] = []

    for p in cited:
        exact = [r for r in retrieved if same_provision(p, r)]
        if exact or not p.statute:
            out.append(p)
            continue
        by_number = [r for r in retrieved if r.kind == p.kind and r.number == p.number]
        statutes = {r.statute for r in by_number if r.statute}
        if len(statutes) == 1:
            corrected = statutes.pop()
            if corrected != p.statute:
                corrections.append({"from": str(p), "to": f"{corrected} Section {p.number}",
                                    "reason": "proximity attribution contradicted by retrieval"})
                out.append(Provision(raw=p.raw, statute=corrected,
                                     kind=p.kind, number=p.number))
                continue
        out.append(p)
    return out, corrections


def _dedupe(provs: Iterable[Provision]) -> list[Provision]:
    """Collapse exact repeats, preserving order. A provision cited three times
    in one answer is one provision, not three."""
    seen: set[str] = set()
    out: list[Provision] = []
    for p in provs:
        if p.key not in seen:
            seen.add(p.key)
            out.append(p)
    return out


def _jaccard(a: Iterable[Provision], b: Iterable[Provision]) -> float:
    """Overlap of two provision sets: |intersection| / |union|.

    1.0 = identical, 0.0 = completely disjoint. Both empty counts as 1.0 —
    nothing claimed and nothing shown is consistent, not divergent.

    WHY THIS IS NOT set(a.key) & set(b.key)
        It used to be, and it returned 0.0 on PERFECT grounding.

        Statutory text never names its own statute. A retrieved chunk reads
        "Section 302. Punishment for murder.—", so it parses with
        statute=None and key '?:section:302'. The prose reads "Section 302
        IPC" and parses to 'IPC:section:302'. String equality on those keys
        is never satisfied, so the metric measured nothing and reported a
        confident zero.

        same_provision() already encodes the right rule -- an unattributed
        reference matches on kind and number, because we cannot rule out that
        it belongs to the statute it is being compared against. This function
        now uses that rule, which makes the metric agree with the grounding
        check sitting beside it instead of contradicting it.

    WHY GREEDY ONE-TO-ONE MATCHING
        The rule is not transitive: '?:section:302' matches both
        'IPC:section:302' and 'BNS:section:302'. Counting every satisfied
        pair would let one item on the left consume several on the right and
        push the ratio above 1.0. Matching each left item to at most one
        unclaimed right item keeps |intersection| <= min(|a|, |b|), so the
        result stays in [0, 1].
    """
    sa, sb = _dedupe(a), _dedupe(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0

    unclaimed = list(sb)
    intersection = 0
    for p in sa:
        for i, q in enumerate(unclaimed):
            if same_provision(p, q):
                intersection += 1
                unclaimed.pop(i)
                break
    union = len(sa) + len(sb) - intersection
    return intersection / union


def audit_answer(
    answer_text: str,
    retrieved_text: str,
    corpus: CorpusIndex,
    panel_text: str | None = None,
    retrieved_chunks: Iterable[dict] | None = None,
) -> AuditResult:
    """Compare what an answer CITED against what was actually RETRIEVED.

    answer_text     the generated prose, including any provisions table
    retrieved_text  concatenated text of the chunks sent to the model
    corpus          what exists in the index at all
    panel_text      what the UI displayed as "Citations / Sources"; defaults to
                    retrieved_text, since that is what the UI shows
    """
    result = AuditResult()
    result.cited = extract_provisions(answer_text)
    result.retrieved = extract_provisions(retrieved_text)
    result.panel = extract_provisions(
        panel_text if panel_text is not None else retrieved_text
    )

    for prov in result.cited:
        if not corpus.has_act(prov.statute):
            # The Act was never indexed, so this citation cannot have come from
            # retrieval. It came from the model's training data.
            result.out_of_corpus.append(prov)
            result.ungrounded.append(prov)
        elif provision_in(prov, result.retrieved):
            result.grounded.append(prov)
        else:
            result.ungrounded.append(prov)

        rel = _vintage_relation(prov.statute, corpus.acts)
        if rel:
            corpus_act, relation = rel
            result.vintage_mismatches.append(
                {"cited": str(prov), "corpus_has": corpus_act, "relation": relation}
            )

    n = len(result.cited)
    if n:
        result.ungrounded_rate = len(result.ungrounded) / n
        result.out_of_corpus_rate = len(result.out_of_corpus) / n
        lenient_grounded = sum(
            1
            for p in result.cited
            if corpus.has_act(p.statute)
            and provision_in(p, result.retrieved, lenient=True)
        )
        result.ungrounded_rate_lenient = (n - lenient_grounded) / n

    result.panel_prose_jaccard = _jaccard(result.cited, result.panel)
    return result
