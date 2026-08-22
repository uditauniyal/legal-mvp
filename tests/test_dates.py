"""Tests for the Date Resolver.

WHY THE REFERENCE DATE IS FIXED IN EVERY TEST
    "last month" means something different every month. If these tests used
    the real today, they would pass in August and fail in July, and the
    failure would look like a code bug rather than a test bug. Every case
    pins reference = 2026-08-23, the date Phase G ran.

WHY THE QUERY STRINGS ARE REAL
    Every layman string here is copied from eval/scenarios.py, and every
    date suffix from eval/layman_queries.py. A date parser written against
    invented input passes on invented input.

THE FOUR CASES THAT DECIDE THE EXPERIMENT
    Phase G's date experiment appends one of four suffixes to each situation.
    If the resolver gets any of them wrong, the whole comparison is wrong, so
    they are pinned first and explicitly.
"""

from __future__ import annotations

from datetime import date

import pytest

from core.dates import (
    BNS_ERA, BOTH_ERAS, CUTOVER, IPC_ERA, UNKNOWN,
    governing_statute, governing_statutes, names_a_statute, resolve,
)

REF = date(2026, 8, 23)          # the day Phase G ran
SITUATION = "husband beats. this is 2 yrs old problem. i went to police once"


class TestTheFourEvaluationVariants:
    """eval/layman_queries.py appends exactly these four."""

    def test_no_date_is_unknown(self):
        assert resolve("husband beats me", REF).era == UNKNOWN

    def test_march_2023_is_ipc_era(self):
        v = resolve("husband beats me This happened in March 2023.", REF)
        assert v.era == IPC_ERA
        assert v.evidence == "March 2023"
        assert v.resolved == date(2023, 3, 1)

    def test_last_month_is_bns_era(self):
        v = resolve("husband beats me This happened last month.", REF)
        assert v.era == BNS_ERA
        assert v.evidence == "last month"

    def test_vague_is_unknown_but_flagged_ambiguous(self):
        """'a while back' is NOT the same as saying nothing. The user tried to
        give a date and could not, which is a different conversation."""
        v = resolve("husband beats me This happened a while back, "
                    "I do not remember exactly when.", REF)
        assert v.era == UNKNOWN
        assert v.ambiguous is True
        assert v.rule == "vague_time_reference"


class TestStatuteYearsAreNotEventDates:
    """The trap that would invert the era on most technical queries.

    An earlier version blocked a fixed LIST of years, which also swallowed
    "since 2019" -- an ordinary way to say when domestic violence began. The
    test is now context: is the year preceded by words naming an Act?
    """

    @pytest.mark.parametrize("query", [
        "What does Section 420 of the Indian Penal Code, 1860 provide?",
        "What does Section 318 of the Bharatiya Nyaya Sanhita, 2023 provide?",
        "Section 41 of the Code of Criminal Procedure, 1973",
        "complaint under Consumer Protection Act 2019 for my fridge",
        "Bharatiya Sakshya Adhiniyam 2023 applies to evidence",
    ])
    def test_statute_year_is_ignored(self, query):
        assert resolve(query, REF).era == UNKNOWN

    def test_same_year_IS_read_when_it_describes_an_event(self):
        """2019 names an Act above and an event here. Only context separates
        them, which is exactly why the flat blocklist had to go."""
        assert resolve("husband beats me since 2019", REF).era == BOTH_ERAS

    def test_names_a_statute_directly(self):
        text = "the Indian Penal Code, 1860"
        assert names_a_statute(text, text.index("1860")) is True
        text2 = "it happened in 1860"
        assert names_a_statute(text2, text2.index("1860")) is False


class TestOngoingConduct:
    """Conduct spanning the cutover: two codes genuinely apply."""

    def test_since_a_year_before_the_cutover_is_both_eras(self):
        v = resolve("husband beats me since 2019", REF)
        assert v.era == BOTH_ERAS
        assert set(v.candidates) == {IPC_ERA, BNS_ERA}

    def test_since_a_year_after_the_cutover_is_bns_only(self):
        assert resolve("tenant not paying since 2025", REF).era == BNS_ERA

    def test_since_offset_marker_first(self):
        v = resolve("husband beats. this is since 2 yrs.", REF)
        assert v.era == BNS_ERA          # 2 years before Aug 2026 = Aug 2024
        assert v.rule == "ongoing_since_offset"

    def test_since_offset_marker_last(self):
        v = resolve("its been 3 days since they took my father", REF)
        assert v.era == BNS_ERA
        assert v.rule == "ongoing_since_offset"

    def test_long_duration_crossing_cutover(self):
        """5 years back from Aug 2026 is Aug 2021 -- before the cutover, with
        the conduct continuing to now. Both codes apply."""
        assert resolve("harassment going on since 5 years now", REF).era == BOTH_ERAS

    def test_both_eras_is_not_unknown(self):
        """The distinction that justifies a fourth value: UNKNOWN means ask
        the user, BOTH_ERAS means we know and the answer is two codes."""
        assert BOTH_ERAS != UNKNOWN
        assert resolve("husband beats me since 2019", REF).is_known is True


class TestPointInTime:
    def test_bare_year(self):
        assert resolve("Booked flat 2021, paid 18 lakh", REF).era == IPC_ERA

    def test_relative_offset_words(self):
        assert resolve("this happened few years back i think", REF).era == IPC_ERA

    def test_relative_offset_digits(self):
        assert resolve("about 6 months ago", REF).era == BNS_ERA

    def test_recent(self):
        assert resolve("it happened yesterday", REF).era == BNS_ERA

    def test_year_range_same_side_of_cutover(self):
        v = resolve("i think 2021 or 2022", REF)
        assert v.era == IPC_ERA

    def test_year_range_straddling_the_cutover_is_undecidable(self):
        """2024-or-2025 cannot be resolved: 2024 could be either side of
        1 July. Guessing here would pick a statute on a coin flip."""
        v = resolve("this was in 2024 or 2025", REF)
        assert v.era == UNKNOWN
        assert v.ambiguous is True


class TestCutoverBoundary:
    """Off-by-one at the boundary changes the governing code."""

    def test_the_day_before_is_ipc(self):
        assert resolve("this happened in June 2024", REF).era == IPC_ERA

    def test_the_month_of_commencement_is_bns(self):
        assert resolve("this happened in July 2024", REF).era == BNS_ERA

    def test_cutover_constant_is_the_commencement_date(self):
        assert CUTOVER == date(2024, 7, 1)


class TestGoverningStatute:
    def test_bns_era_moves_ipc_forward(self):
        assert governing_statute("IPC", BNS_ERA) == "BNS"
        assert governing_statute("CRPC", BNS_ERA) == "BNSS"

    def test_ipc_era_moves_bns_back(self):
        assert governing_statute("BNS", IPC_ERA) == "IPC"

    def test_unknown_leaves_the_user_where_they_are(self):
        """With no date there is no basis to move someone off the code they
        named. Switching silently would be a guess dressed as a fact."""
        assert governing_statute("IPC", UNKNOWN) == "IPC"
        assert governing_statute("BNS", UNKNOWN) == "BNS"

    def test_both_eras_returns_both_for_retrieval(self):
        assert governing_statutes("IPC", BOTH_ERAS) == ["BNS", "IPC"]

    def test_single_era_returns_one(self):
        assert governing_statutes("IPC", BNS_ERA) == ["BNS"]

    def test_unchanged_statute_is_untouched(self):
        """The Consumer Protection Act was not recodified."""
        assert governing_statute("CPA", BNS_ERA) == "CPA"


class TestReproducibility:
    def test_reference_date_is_an_argument_not_a_clock(self):
        """The same text must resolve differently against different reference
        dates, and identically against the same one. Without this an
        evaluation re-run in December would not reproduce August."""
        early = resolve("last month", date(2024, 3, 15))
        late = resolve("last month", date(2026, 8, 23))
        assert early.era == IPC_ERA
        assert late.era == BNS_ERA
        assert resolve("last month", REF).era == resolve("last month", REF).era

    def test_verdict_serialises_for_the_run_log(self):
        log = resolve("This happened in March 2023.", REF).as_log()
        assert log["era"] == IPC_ERA
        assert log["resolved"] == "2023-03-01"
        assert log["evidence"] == "March 2023"
        assert log["rule"] == "month_year"

    def test_empty_and_none_are_safe(self):
        assert resolve("", REF).era == UNKNOWN
        assert resolve(None, REF).era == UNKNOWN
