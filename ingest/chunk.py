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


def is_contents_entry(section_number: str | None, body: str) -> bool:
    """A bare heading from the table of contents, carrying no law.

    Kept if EITHER condition holds:
      - it contains a body marker (em-dash), so a provision follows the title
      - it is at least CONTENTS_MAX_TOKENS long, so there is substance

    Dropped only when both fail.
    """
    if not section_number:
        return False
    if any(m in body for m in BODY_MARKERS):
        return False
    return tokens(body) < CONTENTS_MAX_TOKENS


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
