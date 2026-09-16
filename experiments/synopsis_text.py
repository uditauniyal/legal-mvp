"""The prose of the department synopsis.

SOURCING RULE: every numeric value is a `{key}` slot filled by make_synopsis.py
from results/*.csv using a one-row-or-crash filter. No number is typed here.

WRITING RULE: every section opens in plain English a non-specialist can follow,
then goes to the technical substance. No term is used before it is defined. She
defends this live; a sentence she cannot read aloud and explain is a defect.

LENGTH: the department format caps the document at 15 pages. Prose is therefore
compressed hard. Numbers, definitions and caveats survive compression; discursive
passages do not.

VERIFIED AGAINST CODE, 17 Sept 2026 — recheck before altering:
  - 6 unconditional stages + 2 conditional (app.py:175-191)
  - the date resolver runs AFTER the router (app.py:155 then :183)
  - the deployed confidence formula inverts the gap term (retriever.py:137-142)
  - ENTITY_NEUTRAL is 0.5, not 1.0 (retriever.py:45)
  - the live retriever is dense-only; BM25 is an experimental arm only
  - the corpus is English; nothing multilingual is measured
"""
from __future__ import annotations

TITLE = ("A Calibrated Multi-Agent RAG System for Indian Law: "
         "Design and Empirical Evaluation")
GROUP_ID = "IT118"
ROLL = "241H0360116"
STUDENT = "Udita Uniyal"
DEGREE = "B.Tech Information Technology, V Semester"
MENTOR = "Prof. Nisheeth Joshi, PhD"
MENTOR_DESIG = ("Professor, Speech and Language Processing Lab,\n"
                "Centre for Artificial Intelligence,\n"
                "Faculty of Mathematics and Computing")
DEPARTMENT = "Department of Computer Science"
INSTITUTE = "Banasthali Vidyapith"
SESSION = "Session 2026-27"

# IEEE style. Every entry verified 17 Sept 2026 against the publisher listing.
REFERENCES = [
    'S. Paul, R. Dogra, P. Goyal, and S. Ghosh, "ILSIC: Corpora for identifying '
    'Indian legal statutes from queries by laypeople," in Findings of the '
    'Association for Computational Linguistics: EACL 2026, 2026.',

    'H. de Martim, "Deterministic legal agents: A canonical primitive API for '
    'auditable reasoning over temporal knowledge graphs," arXiv:2510.06002, '
    'Oct. 2025, rev. Apr. 2026.',

    'P. Lewis et al., "Retrieval-augmented generation for knowledge-intensive '
    'NLP tasks," in Advances in Neural Information Processing Systems, vol. 33, '
    '2020, pp. 9459-9474.',

    'V. Magesh, F. Surani, M. Dahl, M. Suzgun, C. D. Manning, and D. E. Ho, '
    '"Hallucination-free? Assessing the reliability of leading AI legal research '
    'tools," Journal of Empirical Legal Studies, 2025.',

    'S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 '
    'and beyond," Foundations and Trends in Information Retrieval, vol. 3, '
    'no. 4, pp. 333-389, 2009.',

    'G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal rank fusion '
    'outperforms Condorcet and individual rank learning methods," in Proc. 32nd '
    'ACM SIGIR Conf. on Research and Development in Information Retrieval, 2009, '
    'pp. 758-759.',

    'J. Platt, "Probabilistic outputs for support vector machines and comparisons '
    'to regularized likelihood methods," in Advances in Large Margin Classifiers, '
    'MIT Press, 1999, pp. 61-74.',

    'C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger, "On calibration of modern '
    'neural networks," in Proc. 34th Int. Conf. on Machine Learning, 2017, '
    'pp. 1321-1330.',

    'E. B. Wilson, "Probable inference, the law of succession, and statistical '
    'inference," Journal of the American Statistical Association, vol. 22, '
    'no. 158, pp. 209-212, 1927.',

    'B. Efron and R. J. Tibshirani, An Introduction to the Bootstrap. New York, '
    'NY, USA: Chapman and Hall/CRC, 1993.',

    'J. A. Hanley and B. J. McNeil, "The meaning and use of the area under a '
    'receiver operating characteristic (ROC) curve," Radiology, vol. 143, no. 1, '
    'pp. 29-36, 1982.',

    'G. W. Brier, "Verification of forecasts expressed in terms of probability," '
    'Monthly Weather Review, vol. 78, no. 1, pp. 1-3, 1950.',

    'The Bharatiya Nyaya Sanhita, 2023 (Act No. 45 of 2023), Government of India. '
    'Commenced 1 July 2024.',

    'The Bharatiya Nagarik Suraksha Sanhita, 2023 (Act No. 46 of 2023), '
    'Government of India. Commenced 1 July 2024.',

    'The General Clauses Act, 1897 (Act No. 10 of 1897), s. 6, Government of '
    'India.',
]


def sections(V):
    """V holds every value, already sourced from results/*.csv."""
    return [

# =============================================================== 1. INTRODUCTION
("1. Introduction", [
 ("p", "On 1 July 2024 India replaced three foundational legal codes on a single "
       "day. The Indian Penal Code of 1860, which defines what counts as a crime, "
       "was replaced by the Bharatiya Nyaya Sanhita, 2023. The Code of Criminal "
       "Procedure of 1973, governing arrest, bail and trial, was replaced by the "
       "Bharatiya Nagarik Suraksha Sanhita. The Indian Evidence Act of 1872 was "
       "replaced by the Bharatiya Sakshya Adhiniyam. The offences are largely the "
       "same. The section numbers are not."),

 ("p", "Both codes remain live law simultaneously. Which applies depends on "
       "when the conduct happened, not when the question is asked: conduct "
       "before 1 July 2024 is still governed by the old code, preserved by the "
       "savings provisions of the new Acts and by section 6 of the General "
       "Clauses Act, 1897 [15]. Article 20(1) of the Constitution separately "
       "forbids applying a heavier punishment retrospectively."),

 ("fig", "SYN2_problem",
  "The research problem. The same question has two correct answers, separated "
  "only by the date of the conduct."),

 ("p", "Figure 1 states the problem. \"My husband beats me\" maps to Section 498A "
       "of the Indian Penal Code if the conduct occurred in March 2023, and to "
       "Section 85 of the Bharatiya Nyaya Sanhita if it occurred last month. The "
       "words are identical; only the date decides. A person asking that question "
       "does not know the Indian Penal Code exists, let alone that it was "
       "replaced, and will not supply a date unprompted."),

 ("h2", "1.1 Retrieval-Augmented Generation"),

 ("p", "The system studied here is a Retrieval-Augmented Generation system, or "
       "RAG. It answers in two steps rather than one: it searches a document "
       "collection for the passages most relevant to the question, then passes "
       "them to a large language model to compose an answer using only what it "
       "was given [3]. The intent is that it quotes real sources rather than "
       "producing text from memory, which matters in law, where an invented "
       "section number is not a harmless error."),

 ("p", "Search here is dense retrieval: search by meaning rather than exact "
       "words. Each passage and each question becomes a list of 1,536 numbers "
       "called an embedding, and passages whose embeddings point in a similar "
       "direction to the question's are returned. Its strength is that it "
       "needs no shared vocabulary. That strength is the source of the failure "
       "measured here: to a dense retriever, Section 420 of the old code and "
       "Section 318 of the new describe the same offence in nearly the same "
       "words."),

 ("p", "This work builds such a system for Indian statutory law and measures "
       "where and why it fails: the system is the instrument, the measurement "
       "is the contribution. The corpus is four statutes totalling {n_chunks} "
       "indexed passages; the evaluation set is {n_queries} questions, each "
       "carrying the section that correctly answers it, recorded before any "
       "output was seen."),
]),

# =========================================================== 2. LITERATURE REVIEW
("2. Literature Review", [
 ("p", "Four bodies of work bear on this problem: Indian legal natural "
       "language processing, evaluation of legal RAG systems, retrieval over "
       "law that changes with time, and confidence calibration."),

 ("h2", "2.1 Indian legal natural language processing"),

 ("p", "The closest prior work is ILSIC [1], from Findings of EACL 2026. It "
       "builds a corpus of queries written by laypeople rather than lawyers, "
       "covering over 500 Indian statutes, for Legal Statute Identification: "
       "deciding which provision a described situation falls under. Its "
       "central finding is directly relevant. Models trained on the language "
       "of court judgments perform poorly on the language ordinary people use, "
       "establishing the layperson setting as a distinct and harder problem."),

 ("p", "ILSIC does not address the recodification; its corpus predates it. The "
       "same holds for Indian legal NLP resources generally, which were "
       "assembled before July 2024 and are built on the numbering of the "
       "repealed codes."),

 ("h2", "2.2 Evaluation of legal retrieval systems"),

 ("p", "Magesh et al. [4] audited three commercial legal research tools and "
       "found all three produced hallucinated citations at material rates. "
       "Their methodological contribution matters as much: they separate an "
       "answer being correct from an answer being grounded in the sources "
       "actually retrieved. That distinction is adopted here as one of the "
       "three correctness definitions in Section 5.4."),

 ("p", "Benchmarks here are typically small: the AILA shared tasks at FIRE "
       "used 50 and 10 test queries in successive years, and COLIEE Task 3 "
       "between 73 and 109. Resource papers are larger, ILSIC reporting 836. "
       "The set built here, at {n_queries} queries, is deliberately "
       "constructed rather than sampled."),

 ("h2", "2.3 Retrieval over law that changes with time"),

 ("p", "Nearest in spirit is de Martim [2], which models legal material as a "
       "temporal knowledge graph supporting point-in-time version retrieval, "
       "so a query can ask what a provision said on a given date. That is the "
       "right solution for a statute amended over time, where each provision "
       "has a linear version history."),

 ("p", "India's 2024 transition is a different shape: not one instrument "
       "amended through versions, but one repealed and another enacted in its "
       "place, with many-to-many renumbering. Section 379 of the old code, "
       "theft, corresponds to Section 303(2) of the new, which additionally "
       "introduces community service for a first offence below a monetary "
       "threshold. A system that merely translated numbers would still be "
       "wrong about the law. Version-aware retrieval over a single instrument "
       "does not, by construction, address a cross-instrument replacement."),

 ("h2", "2.4 Confidence calibration"),

 ("p", "A confidence score is a number a system attaches to its own answer to "
       "indicate how far it should be trusted. Calibration asks whether that "
       "number means what it claims: a perfectly calibrated system reporting "
       "70 per cent confidence is correct on 70 per cent of those occasions. "
       "Guo et al. [8] showed modern neural networks are systematically "
       "overconfident and established Expected Calibration Error as the "
       "standard measure. Platt scaling [7] is the standard remedy, fitting a "
       "two-parameter logistic function mapping a score onto a probability. "
       "Both are used here."),

 ("h2", "2.5 The gap"),

 ("p", "The layperson setting has been studied but not across the "
       "recodification; legal RAG evaluation has established the grounding "
       "distinction but on pre-2024 corpora; temporal retrieval has been "
       "solved for versioned single instruments but not cross-instrument "
       "replacement; and calibration has been studied for classifiers but not "
       "for the composite retrieval-confidence scores these systems deploy. A "
       "full-text arXiv search for \"recodification\" with \"legal\" returns no "
       "results. This work therefore claims only that the author is not aware "
       "of prior work framing the Indian recodification as a retrieval "
       "problem, since repositories outside arXiv were not exhaustively "
       "searched."),
]),

# =============================================== 3. MOTIVATION AND RELEVANCE
("3. Motivation/Justification and Relevance", [
 ("p", "India has a population exceeding 1.4 billion and a severe shortage of "
       "accessible legal guidance. A system answering plain-language legal "
       "questions with accurate statutory citations would matter most to those "
       "least able to obtain that information otherwise. That is the reason to "
       "build one. The reason to measure it carefully before trusting it is "
       "sharper: the section number a citizen is given is the number that goes "
       "onto their police complaint, and a wrong one can mean a complaint "
       "drafted under a repealed provision, delay at the police station, or an "
       "admission the person did not understand they were making."),

 ("p", "The reason to measure it carefully before trusting it is sharper. The "
       "section number a citizen is given is the number that goes onto their "
       "police complaint. A wrong number can mean a complaint drafted under a "
       "repealed provision, delay at the police station, or an admission the "
       "person did not understand they were making."),


 ("p", "The methodological emphasis has a separate justification. An earlier "
       "version of this system reported favourable results on two hand-picked "
       "examples. Those results could not be reproduced, because no retrieval "
       "score had been written to disk and no correct answer recorded in "
       "advance. Measurement infrastructure is therefore treated here as a "
       "primary deliverable."),
]),

# ==================================================================== 4. OBJECTIVES
("4. Objectives", [
 ("p", "Each objective is stated so that it is answerable by a measurement rather "
       "than an opinion, and each is mapped to its result in Section 7."),

 ("num", [
  "To construct an annotated evaluation set of Indian legal queries in which each "
  "query carries the statutory section that correctly answers it, recorded before "
  "any system output is seen, spanning both the repealed and the current criminal "
  "codes.",

  "To instrument the pipeline so that every retrieval score, routing decision, "
  "confidence signal and citation is written to disk, making every reported "
  "number reproducible from a stored record.",

  "To measure whether retrieval accuracy differs between queries naming the "
  "repealed Indian Penal Code and queries naming the Bharatiya Nyaya Sanhita now "
  "in force, and whether any such difference is directional.",

  "To determine whether the failure is a property of dense retrieval "
  "specifically, by comparing it against lexical retrieval and a fusion of the "
  "two, and to identify the mechanism responsible.",

  "To evaluate whether the composite confidence score discriminates correct "
  "answers from incorrect ones, whether it is calibrated, and whether each "
  "constituent signal contributes information.",

  "To establish whether retrieval failure is observable in the written output, or "
  "whether the generating model conceals it by citing provisions retrieval did "
  "not supply.",
 ]),
]),

# =================================================================== 5. METHODOLOGY
("5. Methodology", [
 ("h2", "5.1 System architecture"),

 ("p", "The system is a sequential pipeline of eight stages. Two call a large "
       "language model; the other six are deterministic rules or vector "
       "search. The split is deliberate: a rule produces the same output every "
       "time and can be tested, whereas a model call cannot, and a failure "
       "inside it cannot be attributed to one cause. Confining the model to "
       "two stages makes a change in behaviour traceable to a component rather "
       "than to sampling. Each stage boundary is a typed contract enforced by "
       "Pydantic, so a malformed output fails at the boundary rather than "
       "propagating."),

 ("fig", "SYN1_pipeline",
  "The eight-stage pipeline in execution order. Two stages call a language "
  "model. The date resolver and statute mapper are conditional and are evaluated "
  "as a treatment condition."),

 ("p", "Two stages do not run by default. The date resolver reads the query "
       "for any indication of when the conduct occurred and converts it into a "
       "legal era; the statute mapper then translates extracted section "
       "numbers across the recodification, so a query naming a repealed "
       "provision can also be searched under its replacement. Both are "
       "activated by an explicit flag, so that the pipeline without them "
       "remains runnable as a control and every result attributable to them is "
       "a measured difference against that control rather than an assertion."),

 ("p", "One limitation of the present implementation should be stated here "
       "rather than discovered later. The design placed the date resolver "
       "before the router, so that an inferred legal era could inform which "
       "statute is searched. It is implemented after the router, which means "
       "it can correct a query that already names a code but cannot supply a "
       "statute for one that names none. The consequence is measurable and is "
       "reported in Section 7: the benefit is demonstrated on queries that "
       "name a code, and the layman set, which names none, cannot benefit from "
       "the component as currently placed."),

 ("h2", "5.2 Corpus construction"),

 ("p", "Four statutes were ingested, with text extracted by PyMuPDF and an "
       "optical character recognition fallback that activates only when a page "
       "yields fewer than twenty extractable characters. The corpus is "
       "entirely English; the recognition stage is configured for additional "
       "scripts, but no non-English statutory text has been ingested and no "
       "multilingual capability is claimed or evaluated."),

 ("p", "Chunking is section-bounded rather than windowed. Most systems cut "
       "documents into overlapping fixed-length windows; here text is split at "
       "statutory section headings, so one section becomes one passage and a "
       "provision is never divided mid-sentence. Only a section exceeding 800 "
       "tokens is sub-divided, targeting 450 tokens per piece. There is no "
       "overlap: the pieces share a section number, so context is carried by "
       "metadata."),

 ("tbl", "Corpus composition, a census of the live index.",
  ["Statute", "Status", "Passages", "Share"],
  [["Code of Criminal Procedure, 1973", "Repealed 1 July 2024",
    "{c_crpc}", "{s_crpc}"],
   ["Indian Penal Code, 1860", "Repealed 1 July 2024", "{c_ipc}", "{s_ipc}"],
   ["Bharatiya Nyaya Sanhita, 2023", "In force", "{c_bns}", "{s_bns}"],
   ["Consumer Protection Act, 2019", "In force", "{c_cpa}", "{s_cpa}"],
   ["Total", "", "{n_chunks}", "100.00%"]]),

 ("p", "The Bharatiya Nagarik Suraksha Sanhita and Bharatiya Sakshya Adhiniyam "
       "were deliberately not ingested. The corpus boundary is declared in "
       "code as an explicit set, and retrieval consults it to detect when a "
       "query requires a statute the index does not hold. Such questions are "
       "unanswerable by construction and counted as such rather than scored as "
       "failures."),

 ("h2", "5.3 The evaluation set"),

 ("p", "Four query sets were constructed, totalling {n_queries} unique "
       "questions, each carrying the section that correctly answers it, fixed "
       "before any output was seen. Three are certain by construction: the "
       "query was generated from a known section, so that section is the "
       "answer by definition. Only the layman set required judgement, in "
       "reading a described situation and deciding which provision governs it."),

 ("tbl", "The four evaluation query sets.",
  ["Query set", "n", "Construction", "What it isolates"],
  [["Generated retrieval", "{q_gen}", "By construction",
    "Baseline retrieval across all four statutes"],
   ["Paired recodification", "{q_paired}", "By construction",
    "The same offence asked once under each code"],
   ["Paired dated conflict", "{q_dated}", "By construction",
    "Named code and conduct date disagree"],
   ["Layman situation", "{q_layman}", "Judgement",
    "Ordinary language, no statutory vocabulary"],
   ["Total", "{n_queries}", "", ""]]),


 ("h2", "5.4 Three definitions of a correct answer"),

 ("p", "Asking whether the system answered correctly is not one question. Three "
       "things might be meant:"),

 ("bul", [
  "Retrieved at k: the correct section appeared among the k passages the search "
  "returned. A property of retrieval alone.",
  "Cited: the correct section appears in the citations of the written answer. A "
  "property of the generated text.",
  "Grounded: every section the answer cited was genuinely present in the passages "
  "supplied to the model. The strict definition, which detects a model citing "
  "from memory rather than from evidence.",
 ]),

 ("p", "These come apart: Section 7.1 reports a finding that holds under the "
       "first and vanishes under the other two, so every result names its "
       "definition. Retrieval is likewise measured at three points, since "
       "passages are transformed between database and model: they arrive in "
       "similarity order, are reordered to promote passages containing section "
       "numbers from the query, then filtered by score. Every figure names its "
       "stage."),

 ("h2", "5.5 Verification infrastructure"),

 ("p", "A metric that crashes is harmless because it is noticed; one that "
       "quietly returns a plausible but wrong number is not. Four safeguards "
       "address this: {n_tests} automated tests, including tests whose correct "
       "output was worked out by hand before the code was written; one shared "
       "measurement library imported by every experiment; an independent "
       "re-derivation inside each experiment that halts if two routes to a "
       "number disagree; and no hand transcription of any figure, each being "
       "extracted from a stored results file by a filter that halts rather "
       "than guess. These have caught real errors, including two in the "
       "measurement code itself, one of which silently returned zero correct "
       "answers out of {n_rows} while raising no error."),

 ("p", "These have detected real errors, including two defects in the measurement "
       "code itself. One silently returned zero correct answers out of {n_rows} "
       "while raising no error and producing entirely plausible figures. That "
       "class of failure is why the infrastructure exists."),
]),

# ============================================================ 6. TOOLS & TECHNIQUES
("6. Tools and Techniques", [
 ("h2", "6.1 The composite confidence score"),

 ("p", "The system computes one confidence value from three signals: the mean "
       "similarity of the five best passages, capturing the quality of the "
       "best evidence while ignoring the weak tail; the gap between the best "
       "and fifth-best similarity, intended to detect a single lucky match "
       "among poor results; and entity coverage, the fraction of section "
       "numbers named in the query that appear in the retrieved text. They "
       "combine as a fixed weighted sum."),

 ("eq", "C  =  0.55 m  +  0.15 (1 - g)  +  0.30 e", 1),

 ("p", "Here m is the mean of the top five similarity scores, e is entity "
       "coverage, and g is the normalised gap of Equation (2). Where the query "
       "names no section number, e takes a neutral 0.5 rather than counting as a "
       "failure. The result is clamped to a maximum of 1.0 and rounded to four "
       "decimal places."),

 ("eq", "g  =  min( ( s1 - s5 ) / 0.3 ,  1.0 )", 2),

 ("p", "The sign of the second term deserves attention, and Section 7.1 "
       "reports what measurement found. A large gap between best and "
       "fifth-best is ordinarily read as evidence of a clear winner; the "
       "deployed formula subtracts it, treating a large gap as evidence of "
       "doubt."),

 ("p", "The confidence value selects one of three response tiers determining "
       "the disclaimer attached to the answer: below 0.38 low, 0.38 to below "
       "0.55 medium, 0.55 and above high. These thresholds were fixed before "
       "any evaluation score was recorded, so they cannot have been tuned to "
       "the evaluation data."),

 ("h2", "6.2 Retrieval and the adaptive filter"),

 ("p", "Retrieval returns the fifteen passages closest to the query embedding by "
       "cosine similarity. A threshold then discards the weakest, keeping any "
       "passage above the value in Equation (3), subject to a floor of three "
       "passages always passing regardless of score."),

 ("eq", "t  =  max( s_top - 0.15 ,  0.35 )", 3),

 ("h2", "6.3 Comparison retrievers"),

 ("p", "Two alternative methods were evaluated as comparison arms. Neither is "
       "part of the deployed system, which is dense-only. BM25 [5] is lexical, "
       "scoring documents by which query words literally appear, weighted by "
       "frequency and rarity. Rarity is inverse document frequency, Equation "
       "(4), where N is the passage count and n the number containing the "
       "term."),

 ("eq", "idf(q)  =  ln( ( N - n + 0.5 ) / ( n + 0.5 ) )", 4),

 ("p", "The two ranked lists were combined by Reciprocal Rank Fusion [6], scoring "
       "each passage by the reciprocal of its rank in each list with a constant "
       "of 60 as specified in the original work."),

 ("eq", "RRF(d)  =  SUM over lists of  1 / ( 60 + rank(d) )", 5),

 ("h2", "6.4 Statistical methods"),

 ("p", "Discrimination is measured by the area under the receiver operating "
       "characteristic curve, AUROC [11]: pick one correct and one incorrect "
       "answer at random, and AUROC is the probability the correct one scored "
       "higher. A value of 0.5 is a coin flip, meaning the score carries no "
       "information; below 0.5 means it is actively misleading."),

 ("p", "Calibration is measured by Expected Calibration Error [8], which sorts "
       "answers by confidence, bins them, and averages the distance between "
       "each bin's claimed confidence and its observed accuracy; the Brier "
       "score [12] is reported alongside, and Platt scaling [7] is applied on "
       "a stratified split. Intervals for proportions use the Wilson score "
       "interval [9], which unlike the normal approximation does not claim "
       "certainty at zero or one; others use the bootstrap [10] with 10,000 "
       "resamples under a fixed seed. Where several phrasings of one situation "
       "appear, the cluster bootstrap resamples situations rather than rows, "
       "because three phrasings are not three independent observations."),

 ("h2", "6.5 Software"),

 ("p", "FastAPI with Pydantic typed contracts between stages; Qdrant for "
       "vectors, cosine similarity over 1,536-dimensional "
       "text-embedding-3-small embeddings; generation pinned to one named "
       "provider endpoint at temperature zero with a fixed seed, so runs are "
       "reproducible. Extraction uses PyMuPDF and pdfplumber with Tesseract; "
       "reports use fpdf2. Analysis uses NumPy, pandas, SciPy and Matplotlib; "
       "the comparison retriever uses rank-bm25; tests run under pytest."),
]),

# ========================================================= 7. EXPECTED OUTCOME
("7. Expected Outcome of the Research", [
 ("p", "This section separates results already obtained, reported with sample "
       "sizes and confidence intervals, from outcomes still expected, stated as "
       "plans rather than findings."),

 ("h2", "7.1 Results obtained"),

 ("p", "Six findings are established, computed from {n_rows} analysed query "
       "runs drawn from {n_raw} recorded executions. Table 3 summarises them; "
       "each is reported with the correctness definition and retrieval stage "
       "that produced it."),

 ("p", "First, retrieval across the recodification fails asymmetrically. A query "
       "naming the repealed Indian Penal Code retrieves predominantly correct "
       "text {ipc_dense} of the time against a chance baseline of {chance_ipc}, "
       "that baseline being the share of the index the statute occupies and "
       "therefore what a retriever ignoring the question entirely would score. A "
       "query naming the Bharatiya Nyaya Sanhita, the code in force, manages "
       "{bns_dense} against {chance_bns}. Both rest on {n_arm} queries per arm, "
       "with 95 per cent Wilson intervals of {ipc_dense_ci} and {bns_dense_ci}. "
       "The system is most reliable on the law that no longer applies."),

 ("fig", "F2_ipc_vs_bns",
  "Cross-statute retrieval accuracy with 95 per cent Wilson intervals. Red marks "
  "indicate the chance baseline."),

 ("p", "Second, this is not an artefact of choosing dense retrieval. Lexical "
       "retrieval does not repair the failure; it inverts it, raising accuracy "
       "on queries naming the code in force to {bns_bm25} while collapsing "
       "accuracy on queries naming the repealed code to {ipc_bm25}, below its "
       "chance baseline. Fusing the two yields {ipc_rrf} and {bns_rrf}, "
       "beating neither method at what it was individually good at."),

 ("fig", "F3_dense_vs_bm25",
  "Dense, lexical and fused retrieval on the same queries. The two methods fail "
  "on opposite halves of the set."),

 ("p", "Third, the mechanism lies in how the statutes are drafted. The word "
       "\"sanhita\" occurs in {df_sanhita} of the {n_chunks} passages and every "
       "one belongs to the Bharatiya Nyaya Sanhita, giving an inverse document "
       "frequency of {idf_sanhita} and making it a perfect signpost. The word "
       "\"penal\" occurs in {df_penal} passages, but only {penal_ipc} belong to "
       "the Indian Penal Code while {penal_crpc} belong to the Code of "
       "Criminal Procedure. The drafters of 1860 had no occasion to write "
       "\"penal\" inside the Penal Code; the procedure code refers to it "
       "constantly. The repealed statute's own name has become, statistically, "
       "a word belonging to a different book."),

 ("fig", "F4_self_naming",
  "Document frequency and inverse document frequency of statute-identifying "
  "terms across the index."),

 ("p", "Fourth, the composite confidence score discriminates worse than a "
       "single quantity the system already computes: {auroc_composite} against "
       "{auroc_max} for the highest similarity from the same search. Two of "
       "the composite's own three inputs also beat the blend."),

 ("p", "The cause is identified rather than merely observed. The gap term as "
       "deployed, entering Equation (1) at weight 0.15, reaches an AUROC of "
       "{auroc_gapterm}. A value that far below 0.5 is not an absence of "
       "information but inverted information: the signal points systematically "
       "the wrong way. Without the inversion the same quantity reaches "
       "{auroc_scoregap}. Recomputing the composite with the sign corrected "
       "raises it to {auroc_corrected}, a significant improvement that still "
       "falls significantly short of the single similarity score. The sign "
       "error accounts for roughly half the shortfall; the remainder is the "
       "blend itself."),

 ("fig", "F6_ablation",
  "Discrimination of each confidence signal with 95 per cent bootstrap "
  "intervals. The dashed line marks 0.5, the value of a coin flip."),

 ("p", "Fifth, no confidence threshold makes selective answering viable. The "
       "largest fraction of questions answerable while holding the error rate "
       "at or below 10 per cent is {cov_composite} for the composite -- a "
       "measured value, not a missing one, since no threshold anywhere on the "
       "curve achieves that rate. Expected Calibration Error is "
       "{ece_composite} for the composite against {ece_max} for the single "
       "similarity score, lower being better."),

 ("p", "Sixth, the failure is invisible in the answers. Measured on what was "
       "retrieved, the gap between the two arms of the paired set is "
       "{gap_retrieved}, clustered interval {gap_retrieved_ci}. Measured on "
       "what the answer cited it is {gap_cited}, interval {gap_cited_ci}, "
       "which contains zero. The generating model supplies correct section "
       "numbers from its own training regardless of what search returned, so a "
       "reviewer assessing this system by reading its answers would conclude "
       "it works."),

 ("tbl", "Summary of obtained results.",
  ["Finding", "Value", "95% interval", "n", "Definition"],
  [["IPC-named retrieval accuracy", "{ipc_dense}", "{ipc_dense_ci}", "{n_arm}",
    "Dominant corpus"],
   ["BNS-named retrieval accuracy", "{bns_dense}", "{bns_dense_ci}", "{n_arm}",
    "Dominant corpus"],
   ["Composite confidence AUROC", "{auroc_composite}", "{auroc_composite_ci}",
    "{n_rows}", "Retrieved at k"],
   ["Single similarity AUROC", "{auroc_max}", "{auroc_max_ci}", "{n_rows}",
    "Retrieved at k"],
   ["Deployed gap term AUROC", "{auroc_gapterm}", "{auroc_gapterm_ci}",
    "{n_rows}", "Retrieved at k"],
   ["Coverage at 10% error", "{cov_composite}", "not applicable", "{n_rows}",
    "Retrieved at k"],
   ["IPC minus BNS gap, retrieved", "{gap_retrieved}", "{gap_retrieved_ci}",
    "{n_paired}", "Retrieved at 15"],
   ["IPC minus BNS gap, cited", "{gap_cited}", "{gap_cited_ci}", "{n_paired}",
    "Cited"]]),

 ("h2", "7.2 A constraint on interpretation"),

 ("p", "One limitation bears on every retrieval figure above. Where a gold "
       "label names a subsection, such as Section 318(4), and the index stores "
       "only the parent section, no retriever can score that query correct "
       "under strict matching. Only {ceiling_all} of the {n_queries} queries "
       "have a gold section the index can return at all, and for queries "
       "naming the Bharatiya Nyaya Sanhita the ceiling is {ceiling_bns}. "
       "Figures must be read against that ceiling, not against 100 per cent. "
       "On the reachable subset, dense retrieval attains the ceiling exactly."),

 ("h2", "7.3 Expected outcomes"),

 ("p", "Three outcomes are expected and not yet obtained. The first is "
       "independent validation of the gold labels, all of which were decided "
       "by a single annotator. Three of the four sets are certain by "
       "construction and carry limited annotation risk, but the layman set "
       "required judgement, and no second reader has verified those decisions. "
       "The expected outcome is validation of approximately thirty queries by "
       "a second annotator with legal training, reported with an "
       "inter-annotator agreement statistic. This is the largest outstanding "
       "threat to validity and the highest priority."),

 ("p", "The second is submission for peer review, targeting the 49th European "
       "Conference on Information Retrieval, ECIR 2027, held 21 to 25 March "
       "2027 in Southampton, United Kingdom. The short paper and "
       "reproducibility track closes on 12 October 2026, with notification on "
       "7 December 2026. A separate resource paper track closing 2 November "
       "2026 is a plausible second route, since the annotated evaluation set "
       "is itself a reusable artefact."),

 ("p", "The third is language coverage, which was designed, scoped and then "
       "deliberately deferred. A Language Handler was specified as Stage 0 of "
       "the architecture, ahead of intake, with three routes: pass an English "
       "query straight through, translate a regional-language query, or embed "
       "it directly using a multilingual model. A companion experiment was "
       "scoped at Hindi and Tamil, fifty queries, five arms."),

 ("p", "It was deferred for a stated methodological reason. The corpus is "
       "entirely English, so a Hindi query must be translated before it can "
       "match anything, and the resulting measurement would describe the "
       "quality of the translation step rather than any property of legal "
       "retrieval. Adding it would also double every table at a point where "
       "the confidence intervals reported in Section 7.1 are already wide. The "
       "deferral is recorded rather than implicit, and Stage 0 was placed at "
       "the front of the pipeline precisely so that it could be added later "
       "without disturbing the stages behind it or invalidating any gold "
       "label."),

 ("p", "Two properties of the present implementation make that extension a "
       "configuration change rather than a redesign: ingestion already records "
       "a detected language for every passage, and the optical character "
       "recognition stage is already configured for Devanagari, Tamil and "
       "Telugu. One engineering constraint is known and will need attention, "
       "in that the report generator sanitises text to the Latin-1 character "
       "set, so Devanagari or Tamil cannot presently survive into a generated "
       "PDF. A nearer observation is available within the existing evaluation "
       "set: twelve of the {q_layman} layman queries are code-mixed, using "
       "Hindi vocabulary written in Roman script, which is how a large "
       "fraction of Indian users type. That is a register rather than a "
       "language. Reporting those twelve as a separate stratum costs nothing "
       "and is the immediate next step; genuinely multilingual statutory "
       "material is the phase after it."),
]),

    ]
