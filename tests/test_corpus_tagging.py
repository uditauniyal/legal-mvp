"""Tests for corpus tagging (ingest/chunk.py::guess_corpus).

The corpus tag decides which documents a filtered search can reach. A wrong
tag makes the right answer unreachable no matter how good the embeddings are,
so this is pinned carefully.

HISTORY -- WHY THESE ASSERTIONS FLIPPED
    Tagging used to be inferred from filename keywords plus a scan of the
    document's own text. Both signals are unreliable for Indian statutes:

        - a statute never names itself. The IPC calls itself "this Code",
          never "IPC", so 95.2% of it tagged as "Unknown"
        - the IPC's scanned filename is 'repealedfileopen.pdf', which carries
          no signal at all
        - 'procedure' appears throughout the Consumer Protection Act, and
          'procedure' was a BNSS keyword, so consumer text leaked into a
          criminal corpus
        - stray words conjured corpora for documents that were never ingested:
          "on appeal" produced a 'Judgments' tag, "evidence" produced 'BSA'

    Those cases used to be pinned here as test_DEFECT_* so the defect stayed
    visible. ingest/registry.py replaced inference with an explicit
    filename -> statute lookup, so the defects are gone and these tests now
    assert the CORRECT behaviour. The old expectations are recorded in the
    comment on each test, because a reader seeing "IPC" here should be able to
    tell it was ever anything else.
"""

import pytest

from ingest.chunk import guess_corpus
from ingest.registry import UnknownDocumentError


def test_bns_document_tags_correctly():
    assert guess_corpus("Bharatiya_Nyaya_Sanhita_2023.pdf", "Chapter I") == "BNS"


def test_crpc_document_tags_as_crpc_not_bnss():
    """Was 'BNSS'. The file IS the 1973 Code of Criminal Procedure -- the
    repealed one -- so tagging it as its 2023 successor made every CrPC
    provision answer to the wrong statute name."""
    assert guess_corpus("the_code_of_criminal_procedure,_1973.pdf", "Chapter I") == "CRPC"


def test_ipc_document_tags_as_ipc():
    """Was 'Unknown' 95.2% of the time. Filename carries no signal and the
    text never says 'IPC'; the registry supplies it."""
    ipc_text = "Whoever dishonestly induces the person so deceived to deliver any property"
    assert guess_corpus("repealedfileopen.pdf", ipc_text) == "IPC"


def test_consumer_protection_act_tags_as_cpa():
    """Was 'Unknown' 86.1% of the time."""
    cpa_text = "A complaint may be filed with the District Commission by a consumer"
    assert guess_corpus("a2019-35.pdf", cpa_text) == "CPA"


def test_procedure_keyword_no_longer_mistags_consumer_text():
    """Was 'BNSS'. The word 'procedure' used to be enough to move a chunk into
    a criminal corpus. The registry ignores body text entirely, so content can
    no longer override the document's identity."""
    text = "The procedure for filing a complaint before the District Commission"
    assert guess_corpus("a2019-35.pdf", text) == "CPA"


def test_unregistered_document_raises_instead_of_inventing_a_corpus():
    """Was: 'as held on appeal' -> 'Judgments', 'evidence adduced' -> 'BSA'.

    Neither document was ever ingested. Phantom tags are worse than a crash:
    they make a filtered search silently return nothing, which reads as "no
    such law" rather than "you never loaded that law". Failing loudly at
    ingest time is the point.
    """
    with pytest.raises(UnknownDocumentError):
        guess_corpus("some.pdf", "as held on appeal by the court")
    with pytest.raises(UnknownDocumentError):
        guess_corpus("some.pdf", "the evidence adduced was sufficient")


def test_only_ingested_corpora_are_reachable():
    """The four corpora in the index, and nothing else. If a fifth ever
    appears, something has started inferring again."""
    registered = {
        "Bharatiya_Nyaya_Sanhita_2023.pdf": "BNS",
        "the_code_of_criminal_procedure,_1973.pdf": "CRPC",
        "repealedfileopen.pdf": "IPC",
        "a2019-35.pdf": "CPA",
    }
    assert {guess_corpus(f, "any text at all") for f in registered} == {"BNS", "CRPC", "IPC", "CPA"}
