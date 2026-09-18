"""The prose of the department synopsis.

SOURCING RULE: every numeric value is a `{key}` slot filled by make_synopsis.py
from results/*.csv using a one-row-or-crash filter. No number is typed here.

WRITING RULE -- binding:
  * Plain English FIRST, technical detail SECOND.
  * No term used before it is defined, inline, at first use.
  * Short sentences; a worked example before an abstraction.
  * She defends this live. A sentence she cannot read aloud and explain in her
    own words is a defect, not a style preference.

ORDER OF SECTION 1 -- fixed by the author, do not revert:
  access to justice -> what RAG is -> what the recodification is -> why India
  is a harder case than a versioned statute -> what this work does.

LENGTH -- MEASURED, not estimated. The department format is Letter 8.5x11in,
Times New Roman 12pt, 1.5 line spacing, and caps the document at 15 pages.
At that spec a page holds ~372 words of prose, and the fixed furniture (title
page, contents, 6 figures, 4 tables, 5 equations) costs ~4.3 pages. The prose
budget is therefore ~3,900 words INCLUDING references. An earlier draft ran to
5,900 words and 20 pages. Check with:
    ./venv/Scripts/python.exe experiments/make_synopsis.py
then open in Word -> ComputeStatistics(2). Do not estimate the page count.

VERIFIED AGAINST CODE, 18 Sept 2026 -- recheck before altering:
  - 6 unconditional stages + 2 conditional (app.py:164-191)
  - the date resolver and statute mapper ARE implemented and integrated
    (core/dates.py 368 lines, core/statute_mapper.py 225 lines, wired at
    app.py:173-190). OFF BY DEFAULT so every intervention result is a measured
    delta against a reproducible baseline. They are not fallbacks.
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

# IEEE style. [1]-[15] verified 17 Sept 2026; [16]-[18] recovered from the
# August research sessions and re-verified on arXiv 18 Sept 2026.
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

    # No month for [16]: the listing records 8 July 2026 while the identifier
    # 2608 implies August. Not worth asserting either way in a bibliography.
    'Y. Huang, S. Zheng, Q. Liu, S. Peng, Y. Kong, K. Funakoshi, C. Xiao, '
    'M. Okumura, and Y. Cao, "When do LLMs apply the wrong law? Diagnosing '
    'LLM failures in temporal legal reasoning," arXiv:2608.14610, 2026.',

    'M. Prior, A. Schultz, and M. Grabmair, "Asking for an old friend: '
    'Diagnosing and mitigating temporal failure modes in LLM-based statutory '
    'question answering," arXiv:2605.23497, May 2026.',

    'R. Cymbler, D. Guez, and L. Fabre, "Temporal misgrounding in legal RAG: '
    'A versioned-corpus benchmark for French tax law," in Proc. ICML 2026 '
    'Workshop on AI for Law (AI4Law), Seoul, 2026.',
]


def sections(V):
    """V holds every value, already sourced from results/*.csv."""
    return [

# =============================================================== 1. INTRODUCTION
("1. Introduction", [

 ("h2", "1.1 The problem this work begins from"),

 ("p", "A woman in a small town is being beaten by her husband. She wants to "
       "file a police complaint. To do that she needs the one thing she does "
       "not have: the number of the section of law her situation falls under. "
       "She does not know such a number exists, and cannot afford the lawyer "
       "who would tell her. That is the ordinary shape of the "
       "access-to-justice problem in India, and the reason to build this. The "
       "obstacle is not secrecy -- every Indian statute is published free "
       "online -- but that statutes are written for readers who already have "
       "legal training and are organised by section number, not by the "
       "situation a person is in. A search engine finds Section 498A for "
       "someone who already knows to ask for Section 498A. It cannot find it "
       "for someone who can only say what happened to her."),

 ("h2", "1.2 Retrieval-Augmented Generation"),

 ("p", "A large language model is a program trained to predict the next word "
       "of text, which is what lets it answer a question written in ordinary "
       "English. Asked a legal question directly it will sometimes produce a "
       "citation that does not exist: a real section number attached to the "
       "wrong statute, stated with complete confidence. That is not a "
       "harmless error; it is the number that goes onto a police complaint. "
       "Retrieval-Augmented Generation, abbreviated RAG, is the standard "
       "remedy [3]: it searches a fixed collection of documents for the "
       "passages most relevant to the question, then gives only those "
       "passages to the model and instructs it to answer from them alone, so "
       "every citation can be checked against a passage actually retrieved."),

 ("p", "The search step here is dense retrieval, meaning search by meaning "
       "rather than by matching words. Every passage and every question "
       "becomes a list of 1,536 numbers called an embedding, arranged so that "
       "texts about the same thing get similar lists; closeness is cosine "
       "similarity, a value between 0 and 1 where higher means more alike. "
       "Its strength is that the user need share no vocabulary with the "
       "statute -- and that strength is the source of the failure measured "
       "here."),

 ("h2", "1.3 What changed on 1 July 2024"),

 ("p", "On a single day India replaced three foundational legal codes. This "
       "was a recodification, meaning the law was rewritten and renumbered "
       "from the beginning rather than amended clause by clause. The offences "
       "are largely the same; the section numbers are not. Cheating was "
       "Section 420 of the Indian Penal Code and is now Section 318 of the "
       "Bharatiya Nyaya Sanhita."),

 ("tbl", "The three codes replaced on 1 July 2024.",
  ["Repealed", "Replaced by", "What it governs"],
  [["Indian Penal Code, 1860", "Bharatiya Nyaya Sanhita, 2023",
    "What counts as a crime"],
   ["Code of Criminal Procedure, 1973",
    "Bharatiya Nagarik Suraksha Sanhita, 2023", "Arrest, bail and trial"],
   ["Indian Evidence Act, 1872", "Bharatiya Sakshya Adhiniyam, 2023",
    "What may be proved, and how"]]),

 ("p", "Both codes remain live law at once. Which applies depends on when the "
       "conduct happened, not when the question is asked: conduct before "
       "1 July 2024 is still governed by the repealed code, preserved by the "
       "savings provisions of the new Acts and by section 6 of the General "
       "Clauses Act, 1897 [15]. Article 20(1) of the Constitution separately "
       "forbids applying a heavier punishment retrospectively."),

 ("h2", "1.4 Why this is a hard retrieval problem"),

 ("fig", "SYN2_problem",
  "The research problem. The same question has two correct answers, separated "
  "only by the date of the conduct."),

 ("p", "Figure 1 states the problem with the query this work began from. "
       "\"My husband beats me\" is answered by Section 498A of the Indian "
       "Penal Code if the conduct occurred in March 2023, and by Section 85 "
       "of the Bharatiya Nyaya Sanhita if it occurred last month. The words "
       "are identical; only the date decides, and a person asking it does not "
       "know the Indian Penal Code exists, let alone that it was replaced. "
       "For a search that matches meaning the difficulty is sharper still: "
       "Section 420 of the repealed code and Section 318 of the current one "
       "describe the same offence in nearly the same words, so their "
       "embeddings are nearly the same numbers, and the one thing "
       "distinguishing them -- which book they belong to -- is precisely what "
       "a meaning-based search is designed to ignore."),

 ("h2", "1.5 What this work contributes"),

 ("p", "A working system is built for Indian statutory law and then used as "
       "an instrument to measure where and why it fails: the system is the "
       "instrument, the measurement is the contribution. The corpus is four "
       "statutes totalling {n_chunks} indexed passages, and the evaluation "
       "set {n_queries} questions, each carrying the section that correctly "
       "answers it, recorded before any output was seen."),
]),

# =========================================================== 2. LITERATURE REVIEW
("2. Literature Review", [
 ("p", "Four bodies of work bear on this problem: Indian legal natural "
       "language processing, evaluation of legal RAG systems, retrieval over "
       "law that changes with time, and confidence calibration."),

 ("h2", "2.1 Indian legal NLP, and evaluation of legal retrieval"),

 ("p", "The closest prior work is ILSIC [1], from Findings of EACL 2026: a "
       "corpus of layperson queries over more than 500 Indian statutes for "
       "Legal Statute Identification, the task of deciding which provision a "
       "described situation falls under. Models trained on the language of "
       "court judgments perform poorly on the language ordinary people use, "
       "which makes the layperson setting harder, not easier. ILSIC does not "
       "address the recodification: its corpus predates it, as do Indian "
       "legal NLP resources generally."),

 ("p", "Magesh et al. [4] audited three commercial legal research tools and "
       "found all three produced hallucinated citations at material rates. "
       "Their methodological contribution matters as much: they separate an "
       "answer being correct from an answer being grounded in the sources "
       "actually retrieved, a distinction adopted here in Section 5.4. "
       "Benchmarks here are small -- AILA at FIRE used 50 and then 10 test "
       "queries, COLIEE Task 3 between 73 and 109, ILSIC 836. The set built "
       "here, at {n_queries} queries, is constructed rather than sampled."),

 ("h2", "2.2 Retrieval over law that changes with time"),

 ("p", "Nearest in method is de Martim [2], which models legal material as a "
       "temporal knowledge graph supporting point-in-time version retrieval: "
       "the right solution for a statute amended over time, where each "
       "provision has one linear version history. Nearest in phenomenon is "
       "Huang et al. [16], who examine Chinese civil law and classify "
       "citation faults by direction: old-to-new, where the governing "
       "provision is the earlier version but the model cites the newer one, "
       "and new-to-old, the reverse. Old-to-new dominates -- models apply the "
       "most recently enacted law regardless of when the facts occurred. "
       "Prior et al. [17] report the same recency bias on 312 "
       "expert-validated German statutory questions, and Cymbler et al. [18] "
       "for French tax law across 32,436 article-versions."),

 ("p", "Two differences place this work outside that line. Those studies "
       "measure what the generating model does; the failure reported in "
       "Section 7.1 is a property of retrieval, one stage earlier, measured "
       "before any text reaches a model. And its direction is the opposite of "
       "the recency bias they report: this system is most accurate on the "
       "repealed code. India's transition is also a different shape -- not "
       "one instrument amended through versions but one repealed and another "
       "enacted in its place, with many-to-many renumbering. Section 379, "
       "theft, corresponds to Section 303(2), which adds community service "
       "for a first offence below a monetary threshold, so a system that "
       "merely translated the number would still be wrong about the law."),

 ("h2", "2.3 Confidence calibration, and the gap this work occupies"),

 ("p", "A confidence score is a number a system attaches to its own answer to "
       "say how far it should be trusted, and calibration asks whether that "
       "number means what it claims: a perfectly calibrated system reporting "
       "70 per cent confidence is correct on 70 per cent of those occasions. "
       "Guo et al. [8] showed modern neural networks are systematically "
       "overconfident and established Expected Calibration Error as the "
       "standard measure; Platt scaling [7] is the standard remedy."),

 ("p", "Each literature stops short. The layperson setting has not been "
       "studied across the recodification; legal RAG evaluation established "
       "the grounding distinction only on pre-2024 corpora; temporal "
       "retrieval solves versioned single instruments, not cross-instrument "
       "replacement; and calibration has been studied for classifiers, not "
       "for the composite scores these systems deploy. A full-text arXiv "
       "search for \"recodification\" with \"legal\" returns no results, "
       "so this work claims only that the author is not aware of prior work "
       "framing the Indian recodification as a retrieval problem."),
]),

# =============================================== 3. MOTIVATION AND RELEVANCE
("3. Motivation/Justification and Relevance", [
 ("p", "India has a population exceeding 1.4 billion and a severe shortage of "
       "accessible legal guidance. A system answering plain-language legal "
       "questions with accurate citations would matter most to those least "
       "able to obtain that information any other way."),

 ("p", "The justification for measuring it carefully first is sharper. The "
       "section number a citizen is given goes onto their police complaint, "
       "and a wrong one can mean a complaint drafted under a repealed "
       "provision, delay at the police station, or an admission the person "
       "did not understand they were making. Such a system is not usable "
       "until its failure modes are quantified."),

]),

# ==================================================================== 4. OBJECTIVES
("4. Objectives", [
 ("p", "Each objective is settled by a measurement rather than an opinion, "
       "and each is mapped to its result in Section 7."),

 ("num", [
  "To construct an annotated evaluation set in which each query carries the "
  "section that correctly answers it, recorded before any output is seen, "
  "spanning both the repealed and the current criminal codes.",

  "To instrument the pipeline so every retrieval score, routing decision, "
  "confidence signal and citation is written to disk, making every reported "
  "number reproducible from a stored record.",

  "To measure whether retrieval accuracy differs between queries naming the "
  "repealed Indian Penal Code and those naming the Bharatiya Nyaya Sanhita, "
  "and whether any difference is directional.",

  "To determine whether the failure is specific to dense retrieval, by "
  "comparing it against lexical retrieval and a fusion of the two, and to "
  "identify the mechanism.",

  "To evaluate whether the composite confidence score distinguishes correct "
  "from incorrect answers, whether it is calibrated, and whether each signal "
  "contributes information.",

  "To establish whether retrieval failure is visible in the written output, "
  "or whether the model conceals it by citing provisions retrieval never "
  "supplied.",
 ]),
]),

# =================================================================== 5. METHODOLOGY
("5. Methodology", [
 ("h2", "5.1 System architecture"),

 ("p", "The system is a sequential pipeline of eight stages. Each takes the "
       "previous stage output as its input, and each boundary is a typed "
       "contract enforced by Pydantic, so a malformed output fails at the "
       "boundary instead of propagating. Two stages call a large language "
       "model; the other six are deterministic, producing the same output for "
       "the same input. That split is deliberate: a rule can be unit-tested "
       "and its decision traced to the character that triggered it, so a "
       "change in behaviour is attributable to a component, not to sampling."),

 ("fig", "SYN1_pipeline",
  "The eight-stage pipeline in execution order. Two stages call a language "
  "model. The date resolver and statute mapper are implemented and integrated, "
  "and are evaluated as a treatment condition against the pipeline without "
  "them."),

 ("p", "Two stages are disabled by default, for an experimental rather than a "
       "technical reason. The date resolver reads the query for any "
       "indication of when the conduct occurred and converts it into a legal "
       "era; the statute mapper then translates section numbers across the "
       "recodification, so a query naming a repealed provision is also "
       "searched under its replacement. Both are fully implemented and wired "
       "into the request path, switched on by an explicit flag so the "
       "pipeline without them stays runnable as a control and any benefit is "
       "a measured difference rather than an assertion. One limitation is "
       "stated rather than left to be discovered: the design placed the date "
       "resolver before the router but it is implemented after it, so it "
       "cannot supply a statute for a query naming none -- and the layman set "
       "names none."),

 ("h2", "5.2 Corpus construction"),

 ("p", "Four statutes were ingested, text extracted by PyMuPDF with an "
       "optical character recognition fallback for pages yielding fewer than "
       "twenty extractable characters. The corpus is entirely English; no "
       "multilingual capability is claimed. Chunking -- cutting documents "
       "into the passages that are indexed -- is section-bounded rather than "
       "windowed: text is split at statutory section headings, so one section "
       "becomes one passage and a provision is never divided mid-sentence."),

 ("tbl", "Corpus composition, a census of the live index.",
  ["Statute", "Status", "Passages", "Share"],
  [["Code of Criminal Procedure, 1973", "Repealed 1 July 2024",
    "{c_crpc}", "{s_crpc}"],
   ["Indian Penal Code, 1860", "Repealed 1 July 2024", "{c_ipc}", "{s_ipc}"],
   ["Bharatiya Nyaya Sanhita, 2023", "In force", "{c_bns}", "{s_bns}"],
   ["Consumer Protection Act, 2019", "In force", "{c_cpa}", "{s_cpa}"],
   ["Total", "", "{n_chunks}", "100.00%"]]),

 ("p", "These shares matter for reading every later result: a statute holding "
       "{s_crpc} of the index will appear in that share of results by chance "
       "alone, so retrieval figures are reported against a chance baseline, "
       "not against zero. The Bharatiya Nagarik Suraksha Sanhita and "
       "Bharatiya Sakshya Adhiniyam were deliberately not ingested; questions "
       "needing them are unanswerable by construction and counted as such "
       "rather than scored as failures."),

 ("h2", "5.3 The evaluation set"),

 ("p", "Four query sets were constructed, totalling {n_queries} unique "
       "questions, each carrying the section that correctly answers it, fixed "
       "before any output was seen so no result could influence the "
       "definition of correctness. They are generated retrieval ({q_gen} "
       "questions, baseline retrieval across all four statutes), paired "
       "recodification ({q_paired}, the same offence asked once under each "
       "code), paired dated conflict ({q_dated}, where the named code and the "
       "conduct date disagree) and layman situation ({q_layman}, ordinary "
       "language with no statutory vocabulary). The first three are certain "
       "by construction, the query having been generated from a known "
       "section; only the layman set required judgement. Because the paired "
       "sets are analysed as two arms each, {n_rows} query runs are analysed "
       "in all."),

 ("h2", "5.4 Three definitions of a correct answer"),

 ("p", "Asking whether the system answered correctly is not one question but "
       "three:"),

 ("bul", [
  "Retrieved at k: the correct section appeared among the k passages the "
  "search returned. A property of retrieval alone.",
  "Cited: the correct section appears in the citations of the written "
  "answer. A property of the generated text.",
  "Grounded: every section the answer cited was genuinely present in the "
  "passages supplied to the model -- the strict definition, which detects a "
  "model citing from memory rather than from evidence.",
 ]),

 ("p", "These come apart in practice: Section 7.1 reports a finding that "
       "holds under the first and vanishes under the other two, so every "
       "result names its definition and its retrieval stage."),

 ("h2", "5.5 Verification infrastructure"),

 ("p", "A metric that crashes is harmless, because it is noticed; one that "
       "quietly returns a plausible but wrong number is not. Four safeguards "
       "address this: {n_tests} automated tests, one shared measurement "
       "library so no metric has two implementations, an independent "
       "re-derivation inside each experiment that halts if two routes to a "
       "number disagree, and no hand transcription of any figure. They caught "
       "two defects in the measurement code itself, one of which silently "
       "returned zero correct answers out of {n_rows} while raising no "
       "error."),
]),

# ============================================================ 6. TOOLS & TECHNIQUES
("6. Tools and Techniques", [
 ("h2", "6.1 The composite confidence score"),

 ("p", "The system computes one confidence value from three signals: the mean "
       "similarity of the five best passages; the gap between the best and "
       "fifth-best, intended to detect a single lucky match among otherwise "
       "poor results; and entity coverage, the fraction of section numbers "
       "named in the query that appear in the retrieved text."),

 ("eq", "C  =  0.55 m  +  0.15 (1 - g)  +  0.30 e", 1),

 ("p", "Here m is the mean of the top five similarity scores, e is entity "
       "coverage, and g is the normalised gap of Equation (2); where the "
       "query names no section number, e takes a neutral 0.5."),

 ("eq", "g  =  min( ( s1 - s5 ) / 0.3 ,  1.0 )", 2),

 ("p", "The sign of the second term deserves attention, and Section 7.1 "
       "reports what measurement found: a large gap is ordinarily read as "
       "evidence of a clear winner, but the deployed formula subtracts it. "
       "The confidence value selects one of three tiers, which set the "
       "disclaimer attached to the answer: below 0.38 low, 0.38 to below 0.55 "
       "medium, 0.55 and above high. These were fixed before any evaluation "
       "score was recorded, so they cannot have been tuned to it."),

 ("h2", "6.2 Retrieval and the adaptive filter"),

 ("p", "Retrieval returns the fifteen passages closest to the query embedding "
       "by cosine similarity, then discards any scoring below the value in "
       "Equation (3), subject to a floor of three always passing."),

 ("eq", "t  =  max( s_top - 0.15 ,  0.35 )", 3),

 ("h2", "6.3 Comparison retrievers"),

 ("p", "Two alternatives were evaluated as comparison arms; neither is part "
       "of the deployed system, which is dense-only. BM25 [5] is lexical: it "
       "scores a passage by which query words literally appear in it, "
       "weighted by how often they occur and how rare they are across the "
       "collection, rarity being inverse document frequency. The two ranked "
       "lists were then combined by Reciprocal Rank Fusion [6], which scores "
       "each passage by the reciprocal of its rank in each list with a "
       "constant of 60, as in the original work."),

 ("h2", "6.4 Statistical methods"),

 ("p", "Discrimination -- the ability of a score to separate correct answers "
       "from incorrect ones -- is measured by the area under the receiver "
       "operating characteristic curve, AUROC [11]: pick one correct and one "
       "incorrect answer at random, and AUROC is the probability the correct "
       "one scored higher. 0.5 is a coin flip; below 0.5 the score is "
       "actively misleading. Calibration is measured by Expected Calibration "
       "Error [8], with the Brier score [12] alongside and Platt scaling [7] "
       "on a stratified split. Intervals for proportions use the Wilson score "
       "interval [9], which unlike the normal approximation does not claim "
       "certainty at zero or one; others use the bootstrap [10] with 10,000 "
       "resamples under a fixed seed, clustered on situation."),

 ("h2", "6.5 Software"),

 ("p", "FastAPI with Pydantic typed contracts; Qdrant for vectors, cosine "
       "similarity over 1,536-dimensional text-embedding-3-small embeddings; "
       "generation pinned to one named provider endpoint at temperature zero "
       "with a fixed seed. Extraction uses PyMuPDF with Tesseract; analysis "
       "uses NumPy, pandas, SciPy and Matplotlib; tests run under pytest."),
]),

# ========================================================= 7. EXPECTED OUTCOME
("7. Expected Outcome of the Research", [
 ("p", "This section separates results already obtained from outcomes still "
       "expected, which are stated as plans rather than findings."),

 ("h2", "7.1 Results obtained"),

 ("p", "Seven findings are established, computed from {n_rows} analysed query "
       "runs drawn from {n_raw} recorded executions. Table 4 gives each with "
       "its 95 per cent interval, sample size, correctness definition and "
       "retrieval stage; the prose below states what each one means."),

 ("p", "First, retrieval across the recodification fails asymmetrically. A "
       "query naming the repealed Indian Penal Code retrieves predominantly "
       "correct text {ipc_dense} of the time; one naming the Bharatiya Nyaya "
       "Sanhita, the code actually in force, manages {bns_dense} on the same "
       "{n_arm} queries per arm. The chance baselines -- the share of the "
       "index each statute occupies, and so what a retriever ignoring the "
       "question entirely would score -- are {chance_ipc} and {chance_bns}. "
       "The system is most reliable on the law that no longer applies."),

 ("fig", "F2_ipc_vs_bns",
  "Cross-statute retrieval accuracy with 95 per cent Wilson intervals. Red "
  "marks indicate the chance baseline."),

 ("p", "Second, this is not an artefact of choosing dense retrieval. Lexical "
       "retrieval does not repair the failure; it inverts it, raising "
       "accuracy on queries naming the code in force to {bns_bm25} while "
       "collapsing it on queries naming the repealed code to {ipc_bm25}. "
       "Fusing the two yields {ipc_rrf} and {bns_rrf}, beating neither at "
       "what it was good at: the retrievers have not complementary strengths "
       "but opposite biases, and fusing opposite biases averages them rather "
       "than cancelling them."),


 ("p", "Third, the mechanism lies in how the statutes are drafted. The word "
       "\"sanhita\" occurs in {df_sanhita} of the {n_chunks} passages and "
       "every one belongs to the Bharatiya Nyaya Sanhita, an inverse document "
       "frequency of {idf_sanhita}: a perfect signpost. The word \"penal\" "
       "occurs in {df_penal} passages, but only {penal_ipc} belong to the "
       "Indian Penal Code against {penal_crpc} in the Code of Criminal "
       "Procedure -- the drafters of 1860 had no occasion to write "
       "\"penal\" inside the Penal Code, while the procedure code refers to "
       "it constantly. The repealed statute's own name has become, "
       "statistically, a word belonging to a different book, so the failure "
       "is a property of the source text, not of the implementation."),


 ("p", "Fourth, the people the system exists for are the ones it serves "
       "worst. On the layman set -- situations described in ordinary words, "
       "with no section number -- the correct provision reaches the retrieved "
       "passages {layman_raw} of the time, and the adaptive filter of "
       "Equation (3) halves that to {layman_filt}, because a weak but correct "
       "passage is exactly what a score threshold discards. The answer "
       "nevertheless names the correct provision {layman_cited} of the time; "
       "and in {layman_grounded_count} answers was every provision it cited "
       "actually present in the passages the model was given. A question that "
       "names its own section is answered from evidence; a person who can "
       "only say what happened to her is answered from memory."),

 ("p", "Fifth, the composite confidence score discriminates worse than a "
       "single quantity the system already computes: {auroc_composite} "
       "against {auroc_max} for the highest similarity from the same search; "
       "two of its own three inputs also beat the blend. The cause is "
       "identified, not merely observed: the gap term as deployed enters "
       "Equation (1) at weight 0.15 and reaches {auroc_gapterm}. A value that "
       "far below 0.5 is not an absence of information but inverted "
       "information -- the signal points the wrong way. Uninverted it reaches "
       "{auroc_scoregap}, and recomputing the composite with the sign "
       "corrected, as analysis only and without altering the deployed system, "
       "raises it to {auroc_corrected}: a real improvement that still falls "
       "short."),


 ("p", "Sixth, no confidence threshold makes selective answering viable -- "
       "that is, refusing the questions the system is least sure of in "
       "exchange for being more reliable on the rest. The largest fraction "
       "answerable while holding the error rate at or below 10 per cent is "
       "{cov_composite} for the composite: a measured value, not a missing "
       "one, since no threshold anywhere on the curve achieves that rate. "
       "Expected Calibration Error is {ece_composite} against {ece_max} for "
       "the single similarity score, lower being better."),

 ("p", "Seventh, the failure is invisible in the answers. Measured on what "
       "was retrieved, the gap between the two arms of the paired set is "
       "{gap_retrieved}; measured on what the answer cited it is "
       "{gap_cited}, an interval containing zero. The generating model "
       "supplies correct section numbers from its own training regardless of "
       "what search returned, so a reviewer reading only the answers would "
       "conclude the system works. This is the strongest argument here for "
       "instrumenting every stage rather than only the output."),

 ("tbl", "Summary of obtained results.",
  ["Finding", "Value", "95% interval", "n", "Definition"],
  [["IPC-named retrieval accuracy", "{ipc_dense}", "{ipc_dense_ci}", "{n_arm}",
    "Dominant corpus"],
   ["BNS-named retrieval accuracy", "{bns_dense}", "{bns_dense_ci}", "{n_arm}",
    "Dominant corpus"],
   ["Layman retrieval, raw", "{layman_raw}", "{layman_raw_ci}",
    "{layman_raw_n}", "Retrieved at 15"],
   ["Layman, fully grounded answers", "{layman_grounded_count}", "see 7.1",
    "{layman_grounded_n}", "Grounded"],
   ["Composite confidence AUROC", "{auroc_composite}", "{auroc_composite_ci}",
    "{n_rows}", "Retrieved at k"],
   ["Single similarity AUROC", "{auroc_max}", "{auroc_max_ci}", "{n_rows}",
    "Retrieved at k"],
   ["Coverage at 10% error", "{cov_composite}", "not applicable", "{n_rows}",
    "Retrieved at k"],
   ["IPC minus BNS gap, retrieved", "{gap_retrieved}", "{gap_retrieved_ci}",
    "{n_paired}", "Retrieved at 15"]]),

 ("h2", "7.2 A constraint on interpretation"),

 ("p", "One limitation bears on every retrieval figure above. Where a "
       "recorded correct answer names a subsection, such as Section 318(4), "
       "and the index stores only the parent section, no retriever can score "
       "that query correct under strict matching. Only {ceiling_all} of the "
       "{n_queries} queries have a correct section the index can return at "
       "all, and for queries naming the Bharatiya Nyaya Sanhita the ceiling "
       "is {ceiling_bns}. Every figure must be read against that ceiling, not "
       "against 100 per cent; on the reachable subset dense retrieval attains "
       "it exactly."),

 ("h2", "7.3 Expected outcomes"),

 ("p", "Five outcomes are expected and not yet obtained. The first is "
       "independent validation of the recorded correct answers, all decided "
       "by a single annotator. Three of the four sets are certain by "
       "construction, but the layman set required judgement and no second "
       "reader has verified it. About thirty queries will be validated by a "
       "second annotator with legal training, reported with an "
       "inter-annotator agreement statistic. This is the largest outstanding "
       "threat to validity."),

 ("p", "The second is an explicit statute-metadata ablation -- a controlled "
       "comparison in which exactly one component changes and everything else "
       "is held fixed, so any difference is attributable to that component. "
       "Since a statute identity is barely present in its own text, the "
       "obvious intervention is to supply it: prepend the statute name and "
       "year to every passage before embedding, rebuild the index, re-measure "
       "the paired sets. If the {bns_dense} arm rises towards the "
       "{ipc_dense} arm the failure is repairable at ingestion; if not, the "
       "cause lies deeper and the finding is stronger. Both outcomes are "
       "informative, which is why this runs next."),

 ("p", "The third is a second dense retriever. Every retrieval figure here "
       "comes from one embedding model, text-embedding-3-small, so a reviewer "
       "may fairly ask whether the asymmetry is a property of Indian "
       "statutory law or of that model. Re-running the paired sets against a "
       "further model, run locally so no paid endpoint is needed, settles it; "
       "the prediction is that the asymmetry survives, its cause lying in the "
       "source text rather than in any encoder."),

 ("p", "The fourth is submission for peer review, targeting the 49th European "
       "Conference on Information Retrieval, ECIR 2027, held 21 to 25 March "
       "2027 in Southampton. The full paper track closes 5 October 2026 and "
       "requires an abstract by 21 September 2026; the short paper and "
       "reproducibility track closes 12 October 2026; notification for both "
       "is 7 December 2026. A resource track closing 2 November 2026 is a "
       "third route, the evaluation set being itself a reusable artefact."),

 ("p", "The fifth is language coverage, designed and scoped and then "
       "deliberately deferred. A Language Handler was specified as Stage 0, "
       "ahead of intake, with three routes: pass an English query through "
       "unchanged, translate a regional-language query, or embed it with a "
       "multilingual model. The corpus is entirely English, so a Hindi query "
       "must be translated before it can match anything and the measurement "
       "would describe the translation step rather than legal retrieval. "
       "Stage 0 sits at the front of the pipeline so it can be added later "
       "without disturbing the stages behind it. A nearer step exists: twelve "
       "of the {q_layman} layman queries are code-mixed, Hindi vocabulary in "
       "Roman script, and reporting those separately costs nothing."),
]),

    ]
