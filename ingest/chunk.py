"""Split documents into chunks — following the statute's own structure.

WHY NOT JUST COUNT TOKENS
    The previous version accumulated sentences until it hit ~450 tokens, then
    cut. That boundary lands wherever the count runs out, which is usually in
    the middle of a provision:

        chunk 1 ends:   "...Section 41. Any police officer may without an"
        chunk 2 begins: "order from a Magistrate arrest any person who..."

    Neither half means much alone. Embed them separately and you get two vague
    vectors instead of one sharp one.

    Statutes announce their own boundaries. "Section 41." starts a provision and
    runs until "Section 42." begins. The data hands us the seams, so we use them.

WHAT A CHUNK CARRIES NOW
    section_number   "41", "41A", "304B"    -- lets the verifier match citations
                                               exactly rather than by substring
    statute_code     "IPC" | "BNS" | ...    -- from the registry, not guessed
    in_force_from    date                   -- which era this provision governs
    chunk_id         deterministic          -- so re-ingesting REPLACES rather
                                               than duplicating

DETERMINISTIC IDs — THE DUPLICATE BUG
    618 of 1,813 points in the live index (34%) were duplicate text. Cause:
    app.py overwrote chunk_id with uuid.uuid4(), a fresh random label every
    run. The database matches records by ID, so a new random ID meant "this is
    new" and it inserted another copy.

    chunk_id here is derived from (document, page, position). Same input, same
    ID, every time -- so a second ingest updates in place.
"""

from __future__ import annotations

import re

from langdetect import detect

from ingest.registry import lookup

# Sentence boundary, used when a single section is too long to keep whole.
SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")

# Statutory PDFs print provisions as a bare number: "41." at the start of a
# line. Normalise to "Section 41." so the word is literally present -- both the
# retriever's entity matching and the verifier's citation check look for it.
SECTION_NORMALISE = re.compile(r"(?m)^\s*(\d+\s?[A-Za-z]?)\s*\.")

# A section heading, once normalised.
SECTION_HEADING = re.compile(r"(?m)^\s*Section\s+(\d+[A-Za-z]?)\s*\.")

# --- front-matter detection --------------------------------------------
# Statutory PDFs open with a table of contents: many section headings, each
# with no body. Measured on the CrPC, pages 2-14 produce 5-7 such entries per
# page and account for 20.7% of all chunks.
#
# These are actively harmful to retrieval. A contents line reads
#   "Section 36. Powers of superior officers of police."
# in 15 tokens of pure topic words, while the real provision is buried in 400
# tokens of prose elsewhere. The listing can out-score the law it points to,
# and the system would then cite a page-number index as its authority.
# Measured on the CrPC:
#   contents pages (2-14):  404 sections, em-dash in   0%, max  28 tokens
#   real content pages:      29 sections, em-dash in  45%, max 534 tokens
#
# Indian statutes separate a section's TITLE from its BODY with an em-dash:
#     Section 41. When police may arrest without warrant.-(1) Any police...
#                                                         ^ body starts here
# A contents listing has the title and stops. So: keep a section if it has a
# body marker OR is substantial; drop it otherwise.
#
# Filtering happens per SECTION, not per page. An earlier page-level rule
# discarded page 69 entirely -- which contains Section 126 (maintenance
# procedure) with 380 tokens of real law -- because the page also held four
# short cross-page fragments that dragged the median down.
BODY_MARKERS = ("—", ".-", ".–")   # em-dash, hyphen, en-dash
CONTENTS_MAX_TOKENS = 35    # below this AND no body marker => contents listing
# How much longer a twin must be before it counts as shadowing a fragment.
# Observed contents/law ratios on the real PDFs: 3.7x (CRPC 36), 3.8x (CRPC
# 143), 6.5x (CRPC 431), 11.6x (IPC 153), 14.3x (CRPC 81). Set at 2 because
# nothing real sits near it -- the gap between the two populations is wide.
SHADOW_RATIO = 2.0

MAX_SECTION_TOKENS = 800   # above this, split within the section
MIN_CHUNK_TOKENS = 15      # below this, a fragment is page furniture, not law
TARGET_TOKENS = 450        # fallback window when no headings are found


def tokens(text: str) -> int:
    """Approximate token count. A token is roughly 3/4 of a word; whitespace
    counting is close enough for a size budget and costs nothing."""
    return max(1, len(text.split()))


def normalise_sections(text: str) -> str:
    return SECTION_NORMALISE.sub(r"Section \1.", text)


def split_on_sections(text: str) -> list[tuple[str | None, str]]:
    """Break page text into (section_number, body) pairs.

    Text before the first heading -- page numbers, chapter titles, the tail of
    the previous page's section -- comes back with section_number None.
    """
    matches = list(SECTION_HEADING.finditer(text))
    if not matches:
        return [(None, text)]

    parts: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            parts.append((None, preamble))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start() : end].strip()
        if body:
            parts.append((m.group(1).upper().replace(" ", ""), body))
    return parts


def split_long_body(body: str, target: int = TARGET_TOKENS) -> list[str]:
    """A section too long to keep whole is split at sentence boundaries.

    No overlap here: the pieces share a section_number, so context is carried
    by the metadata rather than by repeating text.
    """
    sentences = [s.strip() for s in SENT_SPLIT.split(body) if s.strip()]
    out, cur, cur_len = [], [], 0
    for s in sentences:
        n = tokens(s)
        if cur and cur_len + n > target:
            out.append(" ".join(cur))
            cur, cur_len = [], 0
        cur.append(s)
        cur_len += n
    if cur:
        out.append(" ".join(cur))
    return out or [body]


# A dash belonging to a STRUCTURAL SUB-HEADING, not to a section title.
#
# Indian statutes group sections under lettered sub-headings, and a contents
# page prints them inline right after the entry above:
#
#     Section 36. Powers of superior officers of police. B.–AID TO THE ...
#                                                         ^^^ not Section 36's
#
# The old rule searched the whole body for any dash and kept the chunk if it
# found one. On contents pages it kept finding the NEXT sub-heading's dash and
# reading it as proof that Section 36 had a body. Eight table-of-contents
# entries reached the index that way, where they compete with the real law:
# a 15-token listing of pure topic words can out-score the 215-token provision
# it points to, and the system would then cite an index as its authority.
SUBHEADING_DASH = re.compile(r"\s[A-Z]\.\s*[—–-]")


def has_body_marker(body: str) -> bool:
    """Does a provision actually follow the section title?

    A dash counts only if it is NOT the sub-heading punctuation described
    above. Checked by blanking out sub-heading labels first, so what remains
    is only dashes that could genuinely separate a title from its body.
    """
    cleaned = SUBHEADING_DASH.sub(" ", body)
    return any(m in cleaned for m in BODY_MARKERS)


def is_contents_entry(section_number: str | None, body: str) -> bool:
    """A bare heading from the table of contents, carrying no law.

    Kept if EITHER condition holds:
      - a body marker follows the title, so a provision follows it
      - it is at least CONTENTS_MAX_TOKENS long, so there is substance

    Dropped only when both fail.

    This catches most of it, but not all: a handful of contents entries carry
    a genuine dash inside the TITLE itself --

        Section 212. Harbouring offender.— if a capital offence; ...

    -- which is indistinguishable from a real provision by local inspection.
    Those need the cross-page check in drop_shadowed_fragments().
    """
    if not section_number:
        return False
    if has_body_marker(body):
        return False
    return tokens(body) < CONTENTS_MAX_TOKENS


# AMENDMENT FOOTNOTES PARSED AS SECTIONS
#
# Indian bare-Act PDFs print amendment history as numbered footnotes at the
# bottom of the page:
#
#     8. Subs. by the A.O. 1950, for "the Provincial Government of the ..."
#
# The extractor sees a number, a full stop and text, which is exactly the
# shape of a section heading, so this became "Section 8" of the IPC -- sitting
# in the index alongside the real Section 8 ("Gender.—The pronoun 'he' ...").
#
# Measured on the four PDFs: 13 such chunks, and ALL 13 collide with a real
# section of the same number. Two consequences, both bad:
#   - a query for IPC 8 can retrieve a 1950 amendment note instead of the law
#   - the note is sometimes LONGER than the short definition it collides with,
#     so drop_shadowed_fragments() deleted the law and kept the note
#
# These openers are editorial apparatus. No answer should ever cite one.
# Two tiers, because one regex cannot be both safe and complete here.
#
# STRONG openers are unambiguous: no provision of the IPC begins "Subs. by".
# WEAK openers ("The words ...", "The Original words ...") are how the other
# half of the footnotes start, but a real section could plausibly begin with
# a similar phrase, so a weak match must also carry AMENDMENT EVIDENCE -- a
# commencement date, an amending Act, or an Adaptation Order -- before the
# chunk is treated as editorial.
#
# Being wrong in the permissive direction leaves noise in the index. Being
# wrong in the strict direction DELETES LAW, which is what happened to IPC
# s.8 ("Gender") on the first attempt. The asymmetry is deliberate.
FOOTNOTE_STRONG = re.compile(
    r"^Section\s+\S+\s*\.\s*"
    r"(Subs\.|Ins\.|Rep\.|Cl\.|Added\b|Omitted\b|Renumbered\b|"
    r"Substituted\b|Inserted\b|Repealed\b)",
    re.I)

FOOTNOTE_WEAK = re.compile(
    r"^Section\s+\S+\s*\.\s*((The|Certain)\s+)?(original\s+)?words\b",
    re.I)

FOOTNOTE_EVIDENCE = re.compile(
    r"(A\.\s?O\.\s*19|w\.e\.f\.|Act\s+\d+\s+of\s+\d{4}|successively|"
    r"omitted by|subs\.\s*by|ins\.\s*by|amended by)",
    re.I)

# Above this, the chunk carries more than the footnote it opens with, so the
# text is kept and only the false section attribution is removed. The one
# observed case is 361 tokens; every pure footnote is under 50.
FOOTNOTE_KEEP_TEXT_TOKENS = 100


def footnote_verdict(section_number: str | None, body: str) -> str:
    """One of "law", "drop", "demote".

    demote = keep the text, discard the section_number. Used when a chunk
    opens with a footnote but continues into real content: deleting it would
    lose law, and keeping the number would misattribute it.
    """
    if not section_number:
        return "law"
    head = " ".join(body.split())
    is_note = bool(FOOTNOTE_STRONG.match(head)) or (
        bool(FOOTNOTE_WEAK.match(head)) and bool(FOOTNOTE_EVIDENCE.search(head[:400]))
    )
    if not is_note:
        return "law"
    return "demote" if tokens(body) > FOOTNOTE_KEEP_TEXT_TOKENS else "drop"


def drop_shadowed_fragments(chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Remove short chunks that a much longer copy of the same section shadows.

    THE SIGNAL
        Every leaked contents entry has a twin: the real provision, on a much
        later page, several times longer.

            CRPC 81   page 4, 15 words   <- contents
            CRPC 81   page 49, 215 words <- the law

        Genuinely short sections have no twin. CrPC 57 ("Person arrested not
        to be detained more than twenty-four hours") is 15 words and appears
        exactly once, so it survives.

    WHY "ON A DIFFERENT PAGE" IS PART OF THE RULE, NOT AN OPTIMISATION
        split_long_body() cuts an over-long section into several chunks that
        share a section_number, and the final piece can be short. Those pieces
        are always produced from ONE page, so they always share it. Requiring
        the shadowing twin to sit on a DIFFERENT page means a real split tail
        can never be mistaken for a contents entry -- no page-distance
        threshold to tune, and no arbitrary constant to defend in the paper.

    Returns (kept, dropped). The dropped list is returned rather than
    discarded so the ingest log can report exactly what was removed; a filter
    that silently eats content is how the last corpus defect survived six
    months.
    """
    longest: dict[tuple, dict] = {}
    for c in chunks:
        if not c.get("section_number"):
            continue
        key = (c["corpus"], c["section_number"])
        if key not in longest or tokens(c["text"]) > tokens(longest[key]["text"]):
            longest[key] = c

    kept, dropped = [], []
    for c in chunks:
        sec = c.get("section_number")
        if not sec or tokens(c["text"]) >= CONTENTS_MAX_TOKENS:
            kept.append(c)
            continue
        twin = longest.get((c["corpus"], sec))
        shadowed = (
            twin is not None
            and twin is not c
            and twin.get("page") != c.get("page")
            and tokens(twin["text"]) >= SHADOW_RATIO * tokens(c["text"])
        )
        (dropped if shadowed else kept).append(c)
    return kept, dropped


def detect_lang(text: str) -> str:
    try:
        return detect(text)
    except Exception:
        return "en"


def chunk_page(doc_name: str, page: int, text: str, **_legacy) -> list[dict]:
    """Turn one page into chunks.

    **_legacy swallows the old target_tokens / overlap_sentences arguments so
    existing callers keep working while the boundary rule changes underneath.
    """
    info = lookup(doc_name)          # raises if the document is unregistered
    text = normalise_sections(text or "")

    pieces: list[tuple[str | None, str]] = []
    for section_number, body in split_on_sections(text):
        if tokens(body) > MAX_SECTION_TOKENS:
            pieces.extend((section_number, part) for part in split_long_body(body))
        else:
            pieces.append((section_number, body))

    out: list[dict] = []
    for idx, (section_number, body) in enumerate(pieces):
        body = body.strip()
        if tokens(body) < MIN_CHUNK_TOKENS:
            continue

        # Amendment footnotes are not law. Run this BEFORE the contents check
        # so a demoted chunk is never judged as a section it does not belong to.
        verdict = footnote_verdict(section_number, body)
        if verdict == "drop":
            continue
        editorial = verdict == "demote"
        if editorial:
            section_number = None

        if is_contents_entry(section_number, body):
            continue

        # Deterministic: same document + page + position -> same id, always.
        chunk_id = f"{doc_name}:{page:04d}:{idx:03d}"

        out.append(
            {
                "doc_name": doc_name,
                "page": page,
                "chunk_index": idx,
                "chunk_id": chunk_id,
                "text": body,
                "section_number": section_number,
                # True when the chunk opens with an amendment footnote and was
                # stripped of its (false) section number. Recorded so the
                # evaluation can tell "retrieved editorial apparatus" apart
                # from "retrieved the wrong law".
                "editorial_note": editorial,
                "corpus": info.corpus,
                "statute_code": info.statute_code,
                "statute_name": info.display_name,
                "in_force_from": info.in_force_from.isoformat(),
                "in_force_until": info.in_force_until.isoformat() if info.in_force_until else None,
                "lang_detected": detect_lang(body),
            }
        )
    return out


def guess_corpus(doc_name: str, text: str = "") -> str:
    """Kept for backwards compatibility; now a registry lookup.

    The old keyword-matching version left the IPC 95% "Unknown" and the
    Consumer Protection Act 86% "Unknown". It guessed; this does not.
    """
    return lookup(doc_name).corpus
