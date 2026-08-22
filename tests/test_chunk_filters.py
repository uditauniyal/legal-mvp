"""Tests for the two filters that decide what counts as law.

WHY THIS MATTERS MORE THAN IT LOOKS
    Everything downstream trusts these. A table-of-contents listing that
    reaches the index is 15 tokens of pure topic words with no prose around
    them, so it can out-score the 215-token provision it points at -- and the
    system then cites a page index as its authority. An amendment footnote
    that reaches the index under a real section number means a query for
    "IPC Section 8" can return a 1950 Adaptation Order note instead of the
    definition of gender.

    Both failures are silent. Retrieval still returns something.

REAL TEXT, NOT INVENTED TEXT
    Every string here was copied out of the actual PDFs in tests/data/, with
    the page it came from recorded. Filters written against imagined input are
    how the first version passed while leaking fourteen entries.
"""

from __future__ import annotations

from ingest.chunk import (
    CONTENTS_MAX_TOKENS, drop_shadowed_fragments, footnote_verdict,
    has_body_marker, is_contents_entry,
)

# ---------------------------------------------------------------------------
# Real strings from the PDFs. Page numbers are the source of truth for whether
# something is law: pages 2-6 of these documents are the contents listing.
# ---------------------------------------------------------------------------

# CrPC p.45 -- real law that happens to be short
CRPC_57_LAW = ("Section 57. Person arrested not to be detained more than twenty-four "
               "hours.—No police officer shall")

# CrPC p.2 -- contents. The dash belongs to "B.–AID", the NEXT sub-heading.
CRPC_36_TOC = ("Section 36. Powers of superior officers of police. "
               "B.–AID TO THE MAGISTRATES AND THE POLICE")

# CrPC p.38 -- the same section, for real
CRPC_36_LAW = ("Section 36. Powers of superior officers of police.—Police officers "
               "superior in rank to an officer in charge of a police station may exercise "
               "the same powers, throughout the local area to which they are appointed, as "
               "may be exercised by such officer within the limits of his station. "
               "B.—AID TO THE MAGISTRATES AND THE POLICE")

# IPC p.6 -- contents, but with a genuine dash inside the TITLE. Locally
# indistinguishable from law; only the cross-page check catches it.
IPC_212_TOC = ("Section 212. Harbouring offender.— if a capital offence; if punishable "
               "with imprisonment for life, or with imprisonment.")

IPC_212_LAW = ("Section 212. Harbouring offender.—Whenever an offence has been committed, "
               "whoever harbours or conceals a person whom he knows or has reason to believe "
               "to be the offender, with the intention of screening him from legal punishment, "
               "if a capital offence.—shall, if the offence is punishable with death, be "
               "punished with imprisonment of either description for a term which may extend "
               "to five years, and shall also be liable to fine.")

# IPC p.15 -- real law, short, and NOT shadowed by anything
IPC_8_LAW = ('Section 8. Gender.—The pronoun “he” and its derivatives are used '
             'of any person, whether male or female.')

# IPC p.21 and p.14 -- amendment footnotes whose leading number parsed as a
# section heading. Both collide with IPC 8.
IPC_8_FOOTNOTE = ('Section 8. Subs. by the A.O. 1950, for “the Provincial Government of '
                  'the Province within which the offender shall be found”.')
IPC_8_FOOTNOTE_WEAK = ('Section 8. The Original words “the limits of the said '
                       'territories” have successively been amended by the A.O. 1937.')


def chunk(corpus: str, section: str | None, page: int, text: str) -> dict:
    return {"corpus": corpus, "section_number": section, "page": page, "text": text}


class TestBodyMarker:
    def test_dash_after_a_title_is_a_body_marker(self):
        assert has_body_marker(CRPC_57_LAW)

    def test_dash_belonging_to_a_subheading_is_not(self):
        """'B.–AID' is the next sub-heading on a contents page. The old rule
        searched the whole body and accepted this as proof of a provision."""
        assert not has_body_marker(CRPC_36_TOC)

    def test_real_law_survives_even_with_a_trailing_subheading(self):
        """CrPC 36's real text ends with the same 'B.—AID' sub-heading. The
        rule must blank the sub-heading and still find the genuine dash."""
        assert has_body_marker(CRPC_36_LAW)


class TestIsContentsEntry:
    def test_short_law_with_a_body_marker_is_kept(self):
        assert not is_contents_entry("57", CRPC_57_LAW)

    def test_contents_entry_on_a_borrowed_dash_is_dropped(self):
        assert is_contents_entry("36", CRPC_36_TOC)

    def test_preamble_without_a_section_number_is_never_a_contents_entry(self):
        assert not is_contents_entry(None, "short unattributed text")

    def test_long_text_is_kept_regardless(self):
        long_text = "Section 1. " + " ".join(["word"] * (CONTENTS_MAX_TOKENS + 5))
        assert not is_contents_entry("1", long_text)

    def test_dash_inside_the_title_defeats_this_filter(self):
        """Documented limitation, not an oversight. IPC 212's contents entry
        carries a real dash right after the title, so it passes here and must
        be caught by drop_shadowed_fragments()."""
        assert not is_contents_entry("212", IPC_212_TOC)


class TestFootnoteVerdict:
    def test_strong_opener_is_dropped(self):
        assert footnote_verdict("8", IPC_8_FOOTNOTE) == "drop"

    def test_weak_opener_with_amendment_evidence_is_dropped(self):
        assert footnote_verdict("8", IPC_8_FOOTNOTE_WEAK) == "drop"

    def test_real_law_is_untouched(self):
        assert footnote_verdict("8", IPC_8_LAW) == "law"
        assert footnote_verdict("57", CRPC_57_LAW) == "law"
        assert footnote_verdict("212", IPC_212_LAW) == "law"

    def test_weak_opener_without_evidence_is_left_alone(self):
        """Bias toward keeping. A section genuinely beginning 'The words' with
        no amending Act, date or Adaptation Order named is treated as law --
        wrongly deleting a provision is far worse than leaving noise."""
        assert footnote_verdict("509", "Section 509. The words uttered were intended to insult.") == "law"

    def test_long_chunk_is_demoted_not_deleted(self):
        """A chunk that opens with a footnote but continues into real content
        keeps its text and loses only the false section number."""
        text = "Section 1. Ins. by Act 13 of 2013, s. 24 (w.e.f. 3-2-2013). " + " ".join(["law"] * 200)
        assert footnote_verdict("1", text) == "demote"

    def test_unattributed_chunk_is_law(self):
        assert footnote_verdict(None, IPC_8_FOOTNOTE) == "law"


class TestDropShadowedFragments:
    def test_contents_entry_shadowed_by_the_real_provision_is_dropped(self):
        toc = chunk("IPC", "212", 6, IPC_212_TOC)
        law = chunk("IPC", "212", 55, IPC_212_LAW)
        kept, dropped = drop_shadowed_fragments([toc, law])
        assert dropped == [toc]
        assert kept == [law]

    def test_short_law_with_no_twin_survives(self):
        """IPC 8 'Gender' is 17 tokens and appears once. Nothing shadows it."""
        law = chunk("IPC", "8", 15, IPC_8_LAW)
        kept, dropped = drop_shadowed_fragments([law])
        assert dropped == []
        assert kept == [law]

    def test_split_tail_on_the_same_page_is_never_shadowed(self):
        """split_long_body() produces several chunks for one section, all from
        ONE page, and the last piece can be short. Requiring the shadowing
        twin to sit on a DIFFERENT page is what protects them -- this is the
        reason the rule is written that way rather than by page distance."""
        head = chunk("CRPC", "154", 78, "Section 154. " + " ".join(["law"] * 400))
        tail = chunk("CRPC", "154", 78, "and shall be signed by the informant.")
        kept, dropped = drop_shadowed_fragments([head, tail])
        assert dropped == []
        assert len(kept) == 2

    def test_shadowing_requires_a_substantially_longer_twin(self):
        """Two similar short chunks do not shadow each other."""
        a = chunk("IPC", "319", 77, "Section 319. Hurt.—Whoever causes bodily pain to any person.")
        b = chunk("IPC", "319", 78, "Section 319. Hurt.—Whoever causes disease to any person.")
        kept, dropped = drop_shadowed_fragments([a, b])
        assert dropped == []

    def test_chunks_without_a_section_number_are_left_alone(self):
        c = chunk("IPC", None, 4, "some preamble text")
        long = chunk("IPC", "1", 40, " ".join(["law"] * 200))
        kept, dropped = drop_shadowed_fragments([c, long])
        assert dropped == []

    def test_different_corpora_do_not_shadow_each_other(self):
        """IPC 302 and BNS 302 are different provisions that share a number."""
        short = chunk("IPC", "302", 60, "Section 302. Punishment for murder.—Whoever commits murder.")
        long = chunk("BNS", "302", 70, "Section 302. " + " ".join(["different"] * 200))
        kept, dropped = drop_shadowed_fragments([short, long])
        assert dropped == []
