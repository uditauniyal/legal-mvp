"""Which law is in which file — stated explicitly, not guessed.

THE PROBLEM THIS REPLACES
    ingest/chunk.py::guess_corpus() decides which law a document belongs to by
    searching its filename and first 200 characters for keywords like "ipc" or
    "bns". Measured against the real PDFs, that produced:

        Bharatiya Nyaya Sanhita 2023 -> BNS   100%   correct, by luck of filename
        CrPC 1973                    -> BNSS  100%   correct, by luck of filename
        IPC 1860                     -> Unknown 95.2%   WRONG
        Consumer Protection Act 2019 -> Unknown 86.1%   WRONG

    Two reasons it fails:
      1. The IPC's file is named "repealedfileopen.pdf" -- no keyword in it.
      2. A statute never refers to itself by acronym. The IPC's own text says
         "this Code", never "IPC". So there is nothing to match on.

    A guess can be wrong. A registry cannot be wrong about a file it names.

WHY THE DATES MATTER
    India replaced the IPC with the BNS on 1 July 2024. Both remain valid law:
    which one applies depends on WHEN the offence happened, not on when the
    question is asked. Recording in_force_from / in_force_until on every chunk
    is what will later let retrieval filter by the date of the events.

IF YOU ADD A DOCUMENT
    Add it here. If it is missing, ingestion raises rather than silently
    tagging it "Unknown" -- a loud failure beats an invisible one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# The day the three new criminal codes came into force.
RECODIFICATION_DATE = date(2024, 7, 1)


@dataclass(frozen=True)
class StatuteInfo:
    """One law, and the window during which it governs conduct."""

    statute_code: str          # "IPC", "BNS", "CRPC", "CPA"
    corpus: str                # the tag stored on each chunk and filtered on
    display_name: str
    in_force_from: date
    in_force_until: date | None   # None = still in force
    superseded_by: str | None = None
    supersedes: str | None = None

    @property
    def is_current(self) -> bool:
        return self.in_force_until is None


DOCUMENT_REGISTRY: dict[str, StatuteInfo] = {
    "repealedfileopen.pdf": StatuteInfo(
        statute_code="IPC",
        corpus="IPC",
        display_name="Indian Penal Code, 1860",
        in_force_from=date(1862, 1, 1),
        in_force_until=RECODIFICATION_DATE,
        superseded_by="BNS",
    ),
    "Bharatiya_Nyaya_Sanhita_2023.pdf": StatuteInfo(
        statute_code="BNS",
        corpus="BNS",
        display_name="Bharatiya Nyaya Sanhita, 2023",
        in_force_from=RECODIFICATION_DATE,
        in_force_until=None,
        supersedes="IPC",
    ),
    "the_code_of_criminal_procedure,_1973.pdf": StatuteInfo(
        statute_code="CRPC",
        corpus="CRPC",
        display_name="Code of Criminal Procedure, 1973",
        in_force_from=date(1974, 4, 1),
        in_force_until=RECODIFICATION_DATE,
        superseded_by="BNSS",
    ),
    "a2019-35.pdf": StatuteInfo(
        statute_code="CPA",
        corpus="CPA",
        display_name="Consumer Protection Act, 2019",
        in_force_from=date(2020, 7, 20),
        in_force_until=None,
    ),
}


class UnknownDocumentError(ValueError):
    """Raised when a file is not in the registry.

    Deliberately fatal. The old behaviour -- tagging it "Unknown" and carrying
    on -- is what made 95% of the IPC unreachable without anyone noticing.
    """


def lookup(doc_name: str) -> StatuteInfo:
    """Which law is this file? Raises if we do not know."""
    info = DOCUMENT_REGISTRY.get(doc_name)
    if info is None:
        known = "\n  ".join(sorted(DOCUMENT_REGISTRY))
        raise UnknownDocumentError(
            f"{doc_name!r} is not in the document registry.\n"
            f"Add it to ingest/registry.py before ingesting. Known files:\n  {known}"
        )
    return info


def corpus_for(doc_name: str) -> str:
    return lookup(doc_name).corpus


def applicable_on(when: date) -> list[StatuteInfo]:
    """Which laws governed conduct on a given date.

    Used later by the Date Resolver: an offence on 2023-05-01 is governed by
    the IPC, one on 2025-01-01 by the BNS.
    """
    return [
        s
        for s in DOCUMENT_REGISTRY.values()
        if s.in_force_from <= when and (s.in_force_until is None or when < s.in_force_until)
    ]
