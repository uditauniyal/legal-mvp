"""Work out WHEN the conduct happened, and therefore which code governs.

THE PROBLEM, IN ONE EXAMPLE
    A person types:

        "my husband beats me. this happened last month."

    Nothing in that sentence names a statute. But the answer depends entirely
    on the date: cruelty by a husband was IPC 498A until 30 June 2024 and has
    been BNS 85 since 1 July 2024. Same facts, different citation, and only
    the date decides which.

    Phase G measured what happens without this module. Told "last month" --
    so the BNS governs -- the system's ability to name the applicable
    provision fell from 96.4% to 60.9%, because nothing in the pipeline read
    the date at all. The Router chose a corpus from the WORDS in the query,
    and the words said nothing about time.

WHY THIS IS DETERMINISTIC AND NOT AN LLM CALL
    Three reasons, in order of importance:

    1. It has to be auditable. "The system said BNS because it read 'last
       month' at characters 34-44 and resolved it to July 2026" is a sentence
       you can check. "The model decided" is not.
    2. It has to be reproducible. A regex gives the same answer in August and
       in December; a model does not necessarily.
    3. It is free and instant, and this runs on every query.

    The cost is coverage: it only catches date expressions it knows. That is
    the right trade, because a MISSED date returns UNKNOWN, and UNKNOWN is a
    safe state -- it means "ask the user" -- whereas a hallucinated date
    silently selects the wrong statute.

UNKNOWN IS AN ANSWER, NOT A FAILURE
    Of 58 hand-written layman queries, exactly one contained a usable date.
    People do not date their own suffering. So UNKNOWN will be the most
    common result, and that is correct: the honest response to an undated
    question is to ask when it happened, not to guess a code.

THE CUTOVER
    1 July 2024. On that date BNS s.358(1) repealed the IPC, BNSS s.531(1)
    repealed the CrPC, and BSA s.170(1) repealed the Evidence Act.

    Conduct BEFORE that date is still governed by the old codes, preserved by
    the savings provisions and by s.6 of the General Clauses Act 1897.
    Article 20(1) of the Constitution separately bars applying a heavier
    penalty retrospectively.

    A caveat this module does NOT resolve, and must not pretend to: for
    PROCEDURE the position is contested. BNSS s.531(2)(a) saves matters
    pending on 1 July 2024, but says little about an offence committed before
    that date with no proceeding yet pending, and the High Courts have split.
    So the era returned here is reliable for the SUBSTANTIVE offence and
    should be treated as advisory for procedure.

REFERENCE DATE
    "Last month" is meaningless without knowing today. The reference date is
    an explicit argument, never datetime.now() inside the logic, so an
    evaluation run in December reproduces exactly what August produced.

USAGE
    >>> from datetime import date
    >>> resolve("husband beats me. this happened last month.", date(2026, 8, 23)).era
    'BNS_ERA'
    >>> resolve("this happened in March 2023").era
    'IPC_ERA'
    >>> resolve("i don't remember exactly when").era
    'UNKNOWN'
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from core.recodification import NEW_TO_OLD_STATUTE, OLD_TO_NEW_STATUTE

# The day the three new codes commenced.
CUTOVER = date(2024, 7, 1)

IPC_ERA = "IPC_ERA"
BNS_ERA = "BNS_ERA"
UNKNOWN = "UNKNOWN"

# CONTINUING CONDUCT THAT SPANS THE CUTOVER.
#
#     "husband beats me. this is since 2019."
#
# Beatings before 1 July 2024 are IPC 498A. Beatings after are BNS 85. Both
# codes genuinely apply, to different incidents in the same course of conduct.
#
# This is NOT the same as UNKNOWN, and the difference is not pedantic.
# UNKNOWN means "we could not work out when this happened, so ask." BOTH_ERAS
# means "we worked it out, and the answer is that two codes apply." Collapsing
# the second into the first would throw away a fact we established and would
# prompt a question the user has already answered.
#
# Domestic violence, dowry harassment and stalking -- three of the most common
# situations in the layman set -- are typically described exactly this way.
BOTH_ERAS = "BOTH_ERAS"

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

# Years we will accept as an event date. Below 1950 is almost certainly a
# statute's own year ("the Indian Penal Code, 1860") rather than something
# that happened to the person asking.
YEAR_MIN, YEAR_MAX = 1950, 2100

# A year can name a STATUTE rather than an event:
#
#     "Section 420 of the Indian Penal Code, 1860"      <- statute
#     "husband beats me since 2019"                     <- event
#
# Reading 1860 as an event date would send that query to the IPC era on false
# evidence -- right answer, wrong reason, and wrong the moment the query is
# about the Bharatiya Nyaya Sanhita, 2023.
#
# A FLAT LIST OF YEARS CANNOT DO THIS, and the first version of this module
# tried. It blocked 2019 because of the Consumer Protection Act 2019, which
# also silently discarded "since 2019" -- an ordinary way to describe when
# domestic violence began. Blocking 2023 would do the same to any conduct
# from that year.
#
# So the test is CONTEXT, not the year itself: is the year immediately
# preceded by words that name an Act?
_STATUTE_CONTEXT = re.compile(
    r"(act|code|sanhita|adhiniyam|samhita|penal|procedure|evidence|"
    r"constitution|amendment|ordinance)\s*[,\-–—]?\s*$", re.I)

# How far back to look for those words. "the Indian Penal Code, 1860" needs
# about 6 characters; 24 is generous without reaching into an unrelated clause.
_STATUTE_CONTEXT_WINDOW = 24


def names_a_statute(text: str, year_start: int) -> bool:
    """Is the year at `year_start` part of an Act's name rather than a date?"""
    left = text[max(0, year_start - _STATUTE_CONTEXT_WINDOW):year_start]
    return bool(_STATUTE_CONTEXT.search(left))


@dataclass
class DateVerdict:
    """What was found, what it means, and why -- so it can be argued with."""

    era: str = UNKNOWN
    resolved: date | None = None          # the event date, if pinned down
    evidence: str = ""                    # the exact words that decided it
    rule: str = "no_date_expression"      # which pattern fired
    ambiguous: bool = False               # a date-ish phrase that resolves nothing
    candidates: list[str] = field(default_factory=list)

    @property
    def is_known(self) -> bool:
        return self.era != UNKNOWN

    def as_log(self) -> dict:
        return {
            "era": self.era,
            "resolved": self.resolved.isoformat() if self.resolved else None,
            "evidence": self.evidence,
            "rule": self.rule,
            "ambiguous": self.ambiguous,
        }


def _era_for(d: date) -> str:
    return BNS_ERA if d >= CUTOVER else IPC_ERA


# --- patterns --------------------------------------------------------------
#
# Ordered most-specific first. A full "March 2023" must win over the bare
# "2023" inside it, or the month is discarded for no reason.

_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

_MONTH_YEAR = re.compile(rf"\b({_MONTH_ALT})\s+(\d{{4}})\b", re.I)
_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
_YEAR_RANGE = re.compile(r"\b(19\d{2}|20\d{2})\s*(?:or|to|-|/)\s*(19\d{2}|20\d{2})\b", re.I)

# "3 years back", "two yrs ago", "about 6 months back"
_WORD_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "couple": 2,
             "few": 3, "several": 4}
_AGO = re.compile(
    rf"\b(\d+|{'|'.join(_WORD_NUM)})\s*(year|yr|month|mnth|week|day)s?\s*(ago|back|before)\b",
    re.I)

# "since 2 yrs", "3 days since they took him", "going on since 2019".
# Describes a DURATION rather than a point, so it can span the cutover.
#
# Two shapes, because the marker can sit on either side of the number:
#     "since 2 yrs" / "for 8 months"      -> marker first
#     "3 days since" / "2 years now"      -> marker last
_SINCE_OFFSET = re.compile(
    rf"\b(?:(?:since|for|from)\s+(\d+|{'|'.join(_WORD_NUM)})\s*"
    rf"(year|yr|month|mnth|week|day)s?"
    rf"|(\d+|{'|'.join(_WORD_NUM)})\s*(year|yr|month|mnth|week|day)s?"
    rf"\s+(?:since|now|already))\b", re.I)
_SINCE_YEAR = re.compile(r"\bsince\s+(19\d{2}|20\d{2})\b", re.I)

_LAST_UNIT = re.compile(r"\b(?:last|past|previous)\s+(year|month|week)\b", re.I)
_THIS_UNIT = re.compile(r"\b(?:this|current)\s+(year|month|week)\b", re.I)
_RECENT = re.compile(r"\b(yesterday|today|last night|just now|recently|"
                     r"few days back|couple of days back)\b", re.I)

# Phrases that SOUND temporal but pin nothing down. Detecting these matters:
# they are the difference between "the user gave no date" and "the user tried
# to give a date and could not", which are different conversations.
_VAGUE = re.compile(
    r"\b(a while (?:back|ago)|long (?:back|ago|time (?:back|ago))|"
    r"some time (?:back|ago)|many years (?:back|ago)|"
    r"don'?t remember|do not remember|not sure when|can'?t recall|cannot recall|"
    r"when i was (?:younger|a child|small)|years back)\b", re.I)


def _shift(ref: date, n: int, unit: str) -> date:
    unit = unit.lower()
    if unit.startswith(("year", "yr")):
        return ref.replace(year=ref.year - n)
    if unit.startswith(("month", "mnth")):
        total = (ref.year * 12 + ref.month - 1) - n
        return date(total // 12, total % 12 + 1, min(ref.day, 28))
    days = n * (7 if unit.startswith("week") else 1)
    return date.fromordinal(max(1, ref.toordinal() - days))


def resolve(text: str, reference: date | None = None) -> DateVerdict:
    """Decide which code governs the conduct described in `text`.

    `reference` is "today" for relative expressions. It is an argument rather
    than datetime.now() so that a run in December reproduces August exactly.
    Defaults to the cutover only as a last resort, which is deliberately a
    date that makes relative expressions obviously wrong rather than subtly
    wrong -- callers should pass a real one.
    """
    text = text or ""
    ref = reference or CUTOVER
    v = DateVerdict()

    # 1. Explicit month + year. The most reliable signal there is.
    m = _MONTH_YEAR.search(text)
    if m:
        year = int(m.group(2))
        if YEAR_MIN <= year <= YEAR_MAX:
            d = date(year, MONTHS[m.group(1).lower()], 1)
            return DateVerdict(_era_for(d), d, m.group(0), "month_year")

    # 2. Ongoing conduct: "since 2019", "this is since 2 yrs".
    #
    #    Checked BEFORE the point-in-time forms, because a duration that
    #    reaches back across 1 July 2024 means two codes apply to one course
    #    of conduct -- a fact that resolving it to a single start date would
    #    silently discard.
    m = _SINCE_YEAR.search(text)
    if m:
        year = int(m.group(1))
        if YEAR_MIN <= year <= YEAR_MAX and not names_a_statute(text, m.start(1)):
            start = date(year, 1, 1)
            era = _era_for(start) if _era_for(start) == _era_for(ref) else BOTH_ERAS
            return DateVerdict(era, start, m.group(0), "ongoing_since_year",
                               candidates=[IPC_ERA, BNS_ERA] if era == BOTH_ERAS else [])

    m = _SINCE_OFFSET.search(text)
    if m:
        raw, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        raw = raw.lower()
        n = int(raw) if raw.isdigit() else _WORD_NUM.get(raw, 1)
        start = _shift(ref, n, unit)
        era = _era_for(start) if _era_for(start) == _era_for(ref) else BOTH_ERAS
        return DateVerdict(era, start, m.group(0), "ongoing_since_offset",
                           candidates=[IPC_ERA, BNS_ERA] if era == BOTH_ERAS else [])

    # 3. Relative offsets: "3 years back", "six months ago".
    m = _AGO.search(text)
    if m:
        raw = m.group(1).lower()
        n = int(raw) if raw.isdigit() else _WORD_NUM.get(raw, 1)
        d = _shift(ref, n, m.group(2))
        return DateVerdict(_era_for(d), d, m.group(0), "relative_offset")

    # 3. "last month" / "this year".
    m = _LAST_UNIT.search(text)
    if m:
        d = _shift(ref, 1, m.group(1))
        return DateVerdict(_era_for(d), d, m.group(0), "last_unit")
    m = _THIS_UNIT.search(text) or _RECENT.search(text)
    if m:
        return DateVerdict(_era_for(ref), ref, m.group(0), "recent")

    # 4. A bare year, or a range of them.
    #
    #    Checked AFTER the relative forms and filtered against STATUTE_YEARS,
    #    because "Section 420 of the Indian Penal Code, 1860" contains a year
    #    that describes the statute, not the conduct. Reading 1860 as an event
    #    date would send every such query to the IPC era on false evidence --
    #    right answer, wrong reason, and wrong the moment the query is about
    #    the Bharatiya Nyaya Sanhita, 2023.
    m = _YEAR_RANGE.search(text)
    if m:
        years = [int(m.group(1)), int(m.group(2))]
        if (all(YEAR_MIN <= y <= YEAR_MAX for y in years)
                and not names_a_statute(text, m.start(1))):
            eras = {_era_for(date(y, 1, 1)) for y in years}
            if len(eras) == 1:
                # "2021 or 2022" -- vague, but both fall the same side.
                d = date(min(years), 1, 1)
                return DateVerdict(eras.pop(), d, m.group(0), "year_range_same_era")
            # Straddles the cutover: genuinely undecidable from the query.
            return DateVerdict(UNKNOWN, None, m.group(0), "year_range_straddles_cutover",
                               ambiguous=True, candidates=[str(y) for y in years])

    years = [int(mm.group(1)) for mm in _YEAR.finditer(text)
             if YEAR_MIN <= int(mm.group(1)) <= YEAR_MAX
             and not names_a_statute(text, mm.start(1))]
    if years:
        d = date(min(years), 1, 1)
        return DateVerdict(_era_for(d), d, str(min(years)), "bare_year")

    # 5. Tried to give a date and could not.
    m = _VAGUE.search(text)
    if m:
        return DateVerdict(UNKNOWN, None, m.group(0), "vague_time_reference", ambiguous=True)

    # 6. Nothing temporal at all.
    return v


def governing_statute(old_statute: str, era: str) -> str:
    """Which code applies, given the code the user named and the era.

    'IPC' + BNS_ERA -> 'BNS'.  'IPC' + UNKNOWN -> 'IPC' (unchanged): with no
    date there is no basis to move the user off the code they named, and
    silently switching would be a guess wearing the clothes of a fact.
    """
    s = (old_statute or "").upper()
    if era == BNS_ERA:
        return OLD_TO_NEW_STATUTE.get(s, s)
    if era == IPC_ERA:
        return NEW_TO_OLD_STATUTE.get(s, s)
    if era == BOTH_ERAS:
        # Continuing conduct: the current code governs the ongoing part, so it
        # is the right SINGLE answer. Callers that can handle two corpora
        # should use governing_statutes() instead and search both.
        return OLD_TO_NEW_STATUTE.get(s, s)
    return s


def governing_statutes(statute: str, era: str) -> list[str]:
    """Every code that could apply, in the order they should be searched.

    Returns two entries only for BOTH_ERAS. Retrieval can use this directly as
    a corpus filter: continuing conduct legitimately needs both halves of the
    recodification pair, and picking one would drop half the answer.
    """
    s = (statute or "").upper()
    if era != BOTH_ERAS:
        one = governing_statute(s, era)
        return [one] if one else []
    new = OLD_TO_NEW_STATUTE.get(s, s)
    old = NEW_TO_OLD_STATUTE.get(s, s)
    return list(dict.fromkeys([new, old]))
