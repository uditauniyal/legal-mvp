"""Tests for corpus tagging (ingest/chunk.py::guess_corpus).

The corpus tag decides which documents a filtered search can reach. A wrong
tag makes the right answer unreachable no matter how good the embeddings are,
so this is pinned carefully.

Measured behaviour on the real PDFs (docs/GAPS.md #3):
    BNS 2023 -> BNS   100%       correct, by luck of the filename
    CrPC     -> BNSS  100%       correct, by luck of the filename
    IPC 1860 -> Unknown 95.2%    WRONG
    CPA 2019 -> Unknown 86.1%    WRONG
"""

from ingest.chunk import guess_corpus


def test_bns_document_tags_correctly():
    assert guess_corpus("Bharatiya_Nyaya_Sanhita_2023.pdf", "Chapter I") == "BNS"


def test_crpc_document_tags_correctly():
    assert guess_corpus("the_code_of_criminal_procedure,_1973.pdf", "Chapter I") == "BNSS"


def test_DEFECT_ipc_document_tags_as_unknown():
    """The filename is 'repealedfileopen.pdf' and a statute never calls itself
    'IPC' in its own text -- it says 'this Code'. So 95% of the IPC is
    unreachable through any IPC query.

    Pins the defect so the Phase E fix is visible.
    """
    ipc_text = "Whoever dishonestly induces the person so deceived to deliver any property"
    assert guess_corpus("repealedfileopen.pdf", ipc_text) == "Unknown", (
        "Expected the current (incorrect) Unknown tag. If this now fails, the "
        "document registry landed -- update to assert 'IPC'."
    )


def test_DEFECT_consumer_protection_act_tags_as_unknown():
    cpa_text = "A complaint may be filed with the District Commission by a consumer"
    assert guess_corpus("a2019-35.pdf", cpa_text) == "Unknown"


def test_DEFECT_procedure_keyword_can_mistag_consumer_text_as_bnss():
    """'procedure' is in the BNSS keyword list, and the Consumer Protection Act
    is full of the word. This is how CPA chunks leak into a criminal corpus."""
    text = "The procedure for filing a complaint before the District Commission"
    assert guess_corpus("a2019-35.pdf", text) == "BNSS"


def test_phantom_corpora_are_reachable_from_stray_words():
    """docs/GAPS.md #10 -- Constitution/BSA/Judgments tags exist even though no
    such document was ever ingested, because a single word triggers them."""
    assert guess_corpus("some.pdf", "as held on appeal by the court") == "Judgments"
    assert guess_corpus("some.pdf", "the evidence adduced was sufficient") == "BSA"
