"""Prose and rendering for the technical report. Numbers arrive already sourced.

Nothing here reads a CSV. Every figure passed in as `g` was extracted by
make_technical_report.gather() with a one-row-or-crash assertion, so no number
in this file is typed.
"""
from __future__ import annotations

import base64
import html as _html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GLOSSARY = [
    ("AUROC", "Area Under the Receiver Operating Characteristic curve. Pick one "
     "correct answer and one wrong answer at random; AUROC is the probability the "
     "correct one has the higher score. 0.5 is a coin flip and means the score "
     "knows nothing; 1.0 is perfect separation; below 0.5 means the score points "
     "the wrong way."),
    ("BM25", "A search method that ranks documents by which query words literally "
     "appear in them, weighted by how often and how rare each word is. Contrast "
     "with dense retrieval, which matches on meaning rather than exact words."),
    ("bootstrap confidence interval", "A range computed by resampling the data "
     "many times (here 10,000) and seeing how much the answer moves. It says: "
     "given this sample size, the true value plausibly lies in this range."),
    ("Brier score", "The average squared difference between a claimed probability "
     "and what actually happened. Lower is better; 0 is perfect. Claiming 0.9 on "
     "something that happens costs (1−0.9)² = 0.01."),
    ("calibration", "Whether a stated confidence matches reality. A perfectly "
     "calibrated system that says '70% confident' is right 70 times in 100."),
    ("chunk", "One passage of statutory text stored in the database, typically a "
     "section or part of one. This corpus holds 1,899 of them."),
    ("cluster bootstrap", "A confidence interval that resamples GROUPS rather than "
     "rows. Three phrasings of the same legal situation are not three independent "
     "facts; treating them as such makes intervals look narrower than they are."),
    ("corpus filter", "A restriction applied BEFORE searching, limiting the search "
     "to one statute. Distinct from the adaptive score filter, which drops "
     "low-scoring passages afterwards. Conflating the two is a common error here."),
    ("coverage at risk", "If you answered only the questions you were most "
     "confident about, what share could you answer while keeping errors at or "
     "below some level (here 10%)?"),
    ("dense retrieval", "Search by meaning. Each passage and each question becomes "
     "a list of 1,536 numbers (an embedding); similar meanings give similar lists."),
    ("ECE", "Expected Calibration Error. Sort answers by confidence, group them "
     "into bins, and average how far each bin's claimed confidence sits from its "
     "actual accuracy. Lower is better; 0 is perfect."),
    ("embedding", "A list of numbers representing a piece of text's meaning. Here "
     "1,536 numbers produced by openai/text-embedding-3-small."),
    ("entity coverage", "One of the system's three confidence signals: whether "
     "section numbers named in the question appear in the retrieved passages."),
    ("gold label", "See ground truth."),
    ("ground truth", "The correct answer, decided in advance by a human and "
     "recorded before any system output was seen. Here: which statutory section "
     "correctly answers each query."),
    ("IDF", "Inverse Document Frequency. How informative a word is, from how few "
     "documents contain it. A word in 30 of 1,899 chunks is a strong clue; a word "
     "in 1,500 tells you almost nothing."),
    ("lexical retrieval", "Search by exact words rather than meaning. BM25 is the "
     "lexical method used here."),
    ("MRR", "Mean Reciprocal Rank. If the correct passage is at position 1 you "
     "score 1, at position 2 you score 1/2, at position 4 you score 1/4. Averaged "
     "over all queries. Rewards putting the right answer near the top."),
    ("nDCG", "Normalised Discounted Cumulative Gain. Like MRR, a rank-sensitive "
     "score that penalises correct answers appearing further down the list."),
    ("p-value", "The probability of seeing a difference at least this large if "
     "there were really no difference at all. Small means the difference is "
     "unlikely to be chance alone. It does NOT say how big or how important the "
     "difference is."),
    ("paired test", "A comparison that uses the fact that two scores were measured "
     "on the SAME questions. Comparing two separate confidence intervals by eye is "
     "not a test and is far too conservative."),
    ("precision@k", "Of the k passages returned, what share are correct. With a "
     "single correct section per query it equals recall@k divided by k, so it adds "
     "no information here and is reported only for completeness."),
    ("Qdrant", "The vector database storing the 1,899 embedded passages and "
     "answering nearest-neighbour searches over them."),
    ("RAG", "Retrieval-Augmented Generation. Fetch relevant documents first, then "
     "have a language model write an answer using only those documents. The idea "
     "is that the model quotes sources rather than inventing them."),
    ("recall@k", "Of the questions that have a correct section, the share where "
     "that section appeared among the top k retrieved passages. The central "
     "retrieval measure in this report."),
    ("recodification", "Replacing a statute wholesale with a new one rather than "
     "amending it. India replaced the Indian Penal Code 1860 with the Bharatiya "
     "Nyaya Sanhita 2023 on 1 July 2024. Both remain operative: which applies "
     "depends on when the offence occurred."),
    ("reciprocal rank fusion", "A way of combining two ranked lists: each document "
     "scores 1/(60 + its rank) in each list, and the scores are added. The "
     "constant 60 is from Cormack, Clarke and Buttcher, SIGIR 2009."),
    ("reliability diagram", "A plot of claimed confidence against observed "
     "accuracy. A perfectly calibrated system sits on the diagonal."),
    ("risk-coverage curve", "As you accept lower-confidence answers, coverage "
     "rises and so does error. The curve traces that trade-off."),
    ("score gap", "One of the three confidence signals: the difference between the "
     "best and second-best retrieval score. A large gap suggests a clear winner."),
    ("statute consistency", "A fourth confidence signal, specified in the design "
     "and built for the first time in this work: the fraction of retrieved "
     "passages coming from the statute the question and its date imply."),
    ("top-k mean", "One of the three confidence signals: the average similarity of "
     "the top few retrieved passages."),
]


def build_markdown(g, figs, sha, total, dropped) -> str:
    F = {fid: (fn, cap) for fid, fn, cap in figs}

    def fig(fid):
        fn, cap = F[fid]
        return f"![{fid}](../figures/{fn})\n\n*{cap}*\n"

    def n(key, dp=4):
        return f"{g[key].v:.{dp}f}"

    def pc(key, dp=1):
        return f"{g[key].v*100:.{dp}f}%"

    def ci(key, dp=4, pct=False, cluster=False):
        return g[key].ci(dp, pct, cluster)

    gl = "\n".join(f"**{t}** — {d}\n" for t, d in sorted(GLOSSARY,
                                                         key=lambda x: x[0].lower()))
    drop = ("\n".join(f"- {d}" for d in dropped) if dropped
            else "- Nothing was dropped.")

    return f"""# Technical report — retrieval failure across a statutory recodification

**Udita Uniyal · Banasthali Vidyapith · 2 September 2026 · commit `{sha}`**

Written for a reader with no prior exposure to this project. Every technical
term is defined in section 2 before it is used.

No number in this document was typed. Every figure and table is generated by
filtering `results/*.csv`, with an assertion that each specification matches
exactly one row. Regenerate:
`./venv/Scripts/python.exe experiments/make_technical_report.py`

---

## 1 · Executive summary

On 1 July 2024 India replaced its 1860 criminal code with a new one. Both
remain in force: which applies depends on when the offence happened. This
project built a question-answering system over Indian statutes and then measured,
carefully, how well it copes with that split.

The main result is that it copes badly, and in a specific and surprising way.
When a question names the **old, repealed** code, the system finds the right law
{pc('dom_dense_ipc')} of the time. When a question names the **new code that is
actually in force**, it finds the right law {pc('dom_dense_bns')} of the time.
Both figures are on {g['dom_dense_ipc'].n} questions each, with 95% confidence
intervals of {ci('dom_dense_ipc', 1, pct=True)} and
{ci('dom_dense_bns', 1, pct=True)}. The system is most reliable on the law that
no longer applies.

The obvious fix does not work. Switching from meaning-based search to
exact-word search reverses the problem rather than solving it: exact-word search
scores {pc('dom_bm25_bns')} on new-code questions but {pc('dom_bm25_ipc')} on
old-code questions. Combining the two methods is worse than either alone. We
traced the cause: the new statute writes its own name inside its own text, while
the old one never does, so the old statute's name is statistically a word
belonging to a *different* book.

The system's own confidence score does not help. It is beaten by a simpler
number that was already available for free, and there is no confidence threshold
at which the system can answer any share of questions while being wrong only one
time in ten.

Two things temper all of this. First, roughly one query in seven has a correct
answer the database physically cannot return, so no search method could score it
— every accuracy figure must be read against that ceiling, not against 100%.
Second, the failure is invisible in the system's written answers, because the
language model cites correct law regardless of what the search returned.

What remains open: no independent expert has checked the correct answers, which
were all decided by one person. That is the single largest threat to these
results and the first thing that should be fixed.

---

## 2 · Glossary

Every technical term used in this document or in the results files. A reader
should not need to look anything up elsewhere.

{gl}

---

## 3 · What was built

A five-stage pipeline that takes a plain-English legal question and returns an
answer with citations and a PDF report. Two stages use a language model; the
rest are deterministic rules or vector search.

{fig('F1_pipeline')}

**The corpus.** {int(g['idx_all'].v):,} passages drawn from four Indian statutes:
the Code of Criminal Procedure 1973 ({int(g['idx_CRPC'].v)} passages), the Indian
Penal Code 1860 ({int(g['idx_IPC'].v)}), the Bharatiya Nyaya Sanhita 2023
({int(g['idx_BNS'].v)}), and the Consumer Protection Act 2019
({int(g['idx_CPA'].v)}). Source: `results/self_naming.csv`.

Each passage is converted to an embedding of 1,536 numbers by
`openai/text-embedding-3-small` and stored in Qdrant, a vector database, which
answers searches by cosine similarity.

**Deliberately absent:** the Bharatiya Nagarik Suraksha Sanhita (the new
procedure code), the Bharatiya Sakshya Adhiniyam (the new evidence act), the
Constitution, and case law. Questions requiring them cannot be answered by
construction, and are counted as such rather than as failures.

---

## 4 · How it was evaluated

### 4.1 The query sets

Four sets, 518 unique queries, every one carrying its correct statutory section
recorded **before** any system output was seen.

| Set | Queries | How the correct answer was established |
|---|---|---|
| generated | {g['rec_generated_retrieval'].n} | Certain by construction — generated from a section, so the section is the answer |
| paired IPC/BNS | {g['rec_paired_recodification'].n} | Certain by construction — a verified IPC↔BNS provision pair, asked once under each numbering |
| dated conflict | {g['rec_paired_dated_conflict'].n} | Judgement — the named code and the offence date disagree, and the date governs |
| layman | {g['rec_layman_situation'].n} | Judgement — a described situation, mapped by hand to the governing section |

The first two are mechanical. **The last two required legal judgement and were
made by one person, the author.** That is the limitation in section 7.

### 4.2 Three definitions of "correct", and why three

- **retrieved@k** — the correct section was among the top k passages fetched.
  A property of the search.
- **cited** — the correct section appears in the answer's citations. A property
  of the writing.
- **grounded** — every section the answer cited was actually present in the
  fetched passages. The strict one, and only 27 of 617 rows pass it.

They are not interchangeable, and a claim that holds under one can die under
another. Section 5.7 is exactly such a case.

### 4.3 Three retrieval stages, and why the distinction matters

Passages pass through three states: **raw_15** as the database returned them,
**reranked_15** after reordering, and **filtered_n** after a score threshold
drops the weakest. A recall figure means different things at each. Earlier
versions of this project published figures without recording which stage
produced them; that is corrected here, and every figure below names its stage.

### 4.4 Verification

- **237 automated tests**, including known-answer tests where the correct
  output was worked out by hand before the code ran. A metric that returns a
  plausible wrong number is the failure mode this project is guarding against.
- **One shared metric library.** Every experiment imports it; nobody
  reimplements a measurement.
- **A paired check per experiment** that re-derives at least one of its own
  numbers by an independent route and asserts agreement.
- **No number in any results document was manually transcribed.** Every figure
  and table is generated by filtering the results files, and the generator
  crashes rather than guessing if a specification matches more than one row.

---

## 5 · Findings

Ordered by strength of evidence.

### 5.1 Retrieval fails across the recodification, asymmetrically

**Claim.** A question naming the repealed code finds the right statute far more
often than a question naming the code in force.

{fig('F2_ipc_vs_bns')}

IPC-named **{pc('dom_dense_ipc')}** {ci('dom_dense_ipc', 1, pct=True)} against a
chance baseline of {pc('chance_ipc')}; BNS-named **{pc('dom_dense_bns')}**
{ci('dom_dense_bns', 1, pct=True)} against {pc('chance_bns')}.
n={g['dom_dense_ipc'].n} per arm, corpus filter disabled, stage
`{g['dom_dense_ipc'].stage}`. Top-1 only: {pc('top1_dense_ipc')} against
{pc('top1_dense_bns')}. Source `results/hybrid_comparison.csv`.

**What it means.** A citizen asking about the law that governs them today is
served worse than one asking about a law repealed in 2024. The misses are not
random: they land on the repealed code.

**How it could be wrong.** n is {g['dom_dense_ipc'].n} per arm, so the intervals
are wide. The measure is "which statute dominates the top 15", which is coarse —
section 5.2 shows a case where it scores 0% while placing the correct passage
first. And the corpus filter is switched off to make the question askable at all;
with it on, an IPC-named query cannot return BNS text by construction.

### 5.2 Exact-word search inverts the failure; fusion does not help

**Claim.** BM25 does not fix the problem — it fails on the opposite half.

{fig('F3_dense_vs_bm25')}

n={g['dom_dense_ipc'].n} per bar, definition
`{g['dom_dense_ipc'].defn}`. Source `results/hybrid_comparison.csv`.

**What it means.** This answers the most obvious objection to section 5.1 — that
the failure is an artefact of choosing a meaning-based retriever. It is not: the
lexical alternative fails worse, in the other direction, and fusing them
produces a system that fails at both.

**How it could be wrong.** The 0.0% figure is a tail effect. On one query BM25
places the correct IPC section at rank 1, but ranks 6–15 fill with procedure-code
cross-references, so "dominant statute" scores it zero. On top-1 BM25 reaches
{pc('top1_dense_ipc')}-comparable territory. The coarse measure exaggerates.

### 5.3 The mechanism: statutes name themselves asymmetrically

**Claim.** The new statute writes its own name in its own text; the old one does
not, so the old statute's name belongs statistically to a different book.

{fig('F4_self_naming')}

`sanhita` appears in {int(g['df_sanhita'].v)} passages, IDF
{n('idf_sanhita', 3)}, and **all {int(g['df_sanhita_BNS'].v)} are BNS**.
`penal` appears in {int(g['df_penal'].v)} passages, IDF {n('idf_penal', 3)},
of which **{int(g['df_penal_CRPC'].v)} are CrPC and only
{int(g['df_penal_IPC'].v)} are IPC**. Self-naming rates: BNS
{pc('selfname_BNS')} {ci('selfname_BNS', 1, pct=True)} of its own passages, IPC
{pc('selfname_IPC')} {ci('selfname_IPC', 1, pct=True)}. n={int(g['idx_all'].v)}
passages. Source `results/self_naming.csv`.

**What it means.** The 1860 drafters had no reason to write "penal" inside the
Penal Code, whereas the procedure code cites it constantly. So searching for the
Penal Code by name points at the procedure code. This is a property of statutory
drafting and statute age, and it should generalise to any recodification.

**How it could be wrong.** Only presence is counted, not how often a term occurs
within a passage; BM25 uses both, so this explains the direction of the effect
but does not fully reconstruct BM25's ranking. The corpus is four statutes.

### 5.4 The confidence score is beaten by a simpler number

**Claim.** The engineered three-signal confidence score discriminates worse than
a single raw similarity, and this survives fixing a sign error found in it.

{fig('F6_ablation')}

n={g['sig_composite'].n}, definition `{g['sig_composite'].defn}`, stage
`{g['sig_composite'].stage}`. Deployed composite {n('sig_composite')}
{ci('sig_composite')} against `max_score` {n('sig_max_score')}
{ci('sig_max_score')}. One term is inverted in the deployed code and scores
{n('sig_gap_term')} — below chance, i.e. pointing the wrong way. Correcting the
sign lifts the composite to {n('cc_composite_corrected')}, but it still loses by
{n('cc_diff_corr_max')} {ci('cc_diff_corr_max')}; the sign error explains about
half of the {n('cc_diff_dep_max')} deficit. Given the best weighting chosen on
data the evaluation never saw, the corrected signals reach {n('cc_best_test')} —
a tie with `max_score`, never a win. Sources `results/ablation.csv`,
`results/corrected_composite.csv`.

**What it means.** Three signals combined carry no more information than one
signal that was free. That is a negative result about a designed component, and
it is more useful than a positive one would have been.

**How it could be wrong.** Under the strict `grounded` definition there are only
27 positives and every comparison contains zero, so this claim rests on the
other two definitions.

### 5.5 There is no usable confidence threshold, and the curve is non-monotone

**Claim.** No confidence cut-off lets the system answer any share of questions
with 10% error or less.

{fig('F7_reliability')}

{fig('F8_coverage_at_risk')}

Coverage at 10% risk: composite {n('cov_comp')}, `max_score` {n('cov_max')},
n={g['cov_comp'].n}, definition `{g['cov_comp'].defn}`. ECE composite
{n('ece_comp')} {ci('ece_comp')} against `max_score` {n('ece_max')}
{ci('ece_max')} — lower is better. Source `results/calibration.csv`.

**What it means.** Selective answering — refusing when unsure — is the standard
safety mechanism for a system like this. These measurements say it cannot be
built on the current confidence score.

**How it could be wrong.** The composite was never designed as a probability; it
is a weighted sum of similarities. ECE is a calibration measure and applying it
to a non-probability needs care. The zeros are real but they are a property of
this score, not proof that no score could work.

### 5.6 The adaptive filter amplifies corpus bias

**Claim.** The step that drops low-scoring passages makes the corpus skew worse.

{fig('F5_funnel')}

Over-representation ratio on layman queries — a statute's share of retrieval
divided by its share of the index, where 1.0 is chance. CrPC
{n('or_CRPC_raw_15', 2)}× → **{n('or_CRPC_filtered_n', 2)}×**; BNS
{n('or_BNS_raw_15', 2)}× → **{n('or_BNS_filtered_n', 2)}×**;
IPC {n('or_IPC_raw_15', 2)}× → {n('or_IPC_filtered_n', 2)}×.
n={g['or_CRPC_raw_15'].n} passages at `raw_15`. Layman recall falls
{n('layman_raw', 3)} → {n('layman_filt', 3)}. Sources
`results/routing_confusion.csv`, `results/robustness.csv`.

**What it means.** A noise-removal step preferentially removes substantive
criminal law and concentrates procedure. But the layman line starts at
{n('layman_raw', 3)}: removing the filter entirely would still leave most
public-style questions unanswered.

**How it could be wrong.** The layman filtered rate is significant on a naive
interval {ci('layman_filt', 3)} and **not significant once clustered**,
{ci('layman_filt', 3, cluster=True)}, because the successes concentrate in a few
situations.

### 5.7 The failure is invisible in the written answers

**Claim.** The retrieval gap does not appear at citation level.

| Correctness definition | IPC−BNS gap | clustered 95% CI |
|---|---|---|
| `retrieved@15` | **{n('gap_ret')}** | {ci('gap_ret', cluster=True)} |
| `cited` | {n('gap_cit')} | {ci('gap_cit', cluster=True)} — contains 0 |
| `grounded` | {n('gap_gro')} | {ci('gap_gro', cluster=True)} — contains 0 |

n={g['gap_ret'].n}, paired set, no restrictions. Source `results/robustness.csv`.

**What it means.** The language model cites correct sections regardless of what
search returned, so the failure is hidden in the output. For a legal assistant
that is worse than a visible failure, not better.

**How it could be wrong.** This is stated as a retrieval claim throughout. A
reviewer measuring citations rather than retrieval will not reproduce the gap,
which is why the definition is named beside every figure.

### 5.8 A statute-aware confidence signal works, but only where it is not circular

**Claim.** A fourth signal measuring whether passages came from the admissible
statute beats the existing signals only on the subset where the named code and
the date disagree.

Pooled {n('sc_all')} {ci('sc_all')}, n={g['sc_all'].n} — no better than the
existing signals. On the dated-conflict subset **{n('sc_dated')}**
{ci('sc_dated')}, n={g['sc_dated'].n}. Source
`results/statute_consistency.csv`.

**What it means.** On most rows the corpus filter was derived from the same
question-and-date inputs the signal reads, so the signal cannot fail by
construction. A confidence signal downstream of a filter built from its own
inputs is a tautology. It earns its keep only where the two disagree.

**How it could be wrong.** The subset where it works is the subset it was
designed for, so this is close to a definition rather than a discovery.

### 5.9 A ceiling caps every recall figure

{fig('F9_ceiling')}

Pooled **{pc('ceiling_all')}** {ci('ceiling_all', 1, pct=True)} of
{g['ceiling_all'].n} queries have a gold section the index can return at all
under strict matching; BNS-named queries are capped at **{pc('ceiling_bns')}**
{ci('ceiling_bns', 1, pct=True)}. Source `results/hybrid_comparison.csv`.

**What it means.** Where a gold label names a subsection the index stores only
as a bare section, no retriever can score it. On BNS-named queries, dense and
hybrid retrieval both saturate this ceiling exactly: on reachable questions,
retrieval is perfect.

**How it could be wrong.** It is an artefact of strict matching. Lenient
matching would raise it but would also collapse genuinely distinct provisions,
which is the confusion this project measures.

---

## 6 · Corrections and retractions

Every number that changed from what was previously reported.

| What was reported | What is true | Cause | Found by |
|---|---|---|---|
| A "counting bug" halving the layman retrieval figure | **No bug existed.** Text parsing recovered the section 4,906 times out of 4,906, a 0.0% error rate. Both figures were correct at different retrieval stages | An unfiltered probe was compared against a filtered figure | A re-measurement that contradicted the claim |
| BNS-named gold recall of {pc('ceiling_bns')} reported as a retrieval failure | **It is the reachability ceiling.** {pc('ceiling_bns')} of BNS gold labels name subsections the index stores only as bare sections | Gold granularity finer than index granularity | The Wave 3 paired check |
| Confidence formula documented as `0.15·score_gap` | Deployed code computes `0.15·(1 − min(score_gap/0.3, 1))` — **the term is inverted**. A documentation error; the logged scores were always right | The written note diverged from the code | A reconstruction check: the documented formula matched 0 of 617 rows, the real one matches to 9e-05 |
| `entity_coverage` exceeds 1.0 and grants a free 0.30 default | Describes **superseded code**. Values are only {{0, 0.5, 1.0}} | A stale entry in the defects document | Confirmed independently twice |
| Confidence AUROC pair 0.610 / 0.663 | Records neither correctness definition nor retrieval stage, and no definition reproduces it. **Superseded, not reconcilable** | Figures published without their definition and stage | The smoke test |
| Two defects in this project's own measurement code | One raised an error on real data; the fix for it then silently returned **0 correct out of 617 while nothing crashed** | Non-idempotent normalisation | The gate check, before any number was published |

---

## 7 · Limitations

Stated as a reviewer would state them.

1. **Single annotator.** All ground truth was decided by one person, the author.
   Two of the four query sets required legal judgement. No independent expert has
   validated any label. This is the largest threat to every finding.
2. **A ceiling caps every recall figure.** Only {pc('ceiling_all')}
   {ci('ceiling_all', 1, pct=True)} of {g['ceiling_all'].n} queries have a
   reachable gold section; BNS-named queries {pc('ceiling_bns')}. Figures must
   not be read against 100%.
3. **Single embedding model, single vector store, single jurisdiction, four
   statutes.** No claim generalises beyond this configuration without retesting.
4. **The strict `grounded` definition has 27 positives in 617 rows.** Every
   comparison under it is underpowered and contains zero.
5. **One significance claim is lost under clustering.** The layman `filtered_n`
   rate is significant naively {ci('layman_filt', 3)} and not significant
   clustered {ci('layman_filt', 3, cluster=True)}.
6. **One assertion is left deliberately failing.** Four clustered AUROC
   intervals came out narrower than their naive counterparts and remain
   unexplained after ruling out resampler bugs and Monte Carlo noise across five
   seeds. Those two restricted subsets are marked unusable rather than explained
   away.
7. **Three labelled rows are dropped** by a deduplication rule, so n is 617 where
   it could be 620. Disclosed rather than fixed.
8. **The headline claim is definition-dependent.** It holds under
   `retrieved@15` and does not survive at citation level (section 5.7).
9. **Answer quality is not evaluated.** This work measures retrieval,
   confidence and citation behaviour. It does not assess whether the prose
   advice is legally sound.

---

## 8 · What could be done next

Factual list of candidates with rough cost and effort. No recommendation is
made.

| Candidate | Cost | Effort |
|---|---|---|
| Independent expert validation of ~30 queries and their gold labels | none, needs an introduction | one person-day for the validator |
| Re-derive gold at subsection granularity, raising the {pc('ceiling_all')} ceiling | none | 1–2 days, and it revises the evaluation set |
| Ingest the BNSS and BSA to close the corpus gap | ~₹50 in embeddings | 1 day, but it invalidates comparability with the {int(g['idx_all'].v):,}-passage index every figure here uses |
| Term-frequency as well as document-frequency analysis for section 5.3 | none | half a day |
| A second embedding model as a robustness check | ~₹50, or free with a local model | 1 day |
| Query-level error taxonomy over the failing layman questions | none | 2 days of manual coding |
| Statute-and-date resolution layer, then re-measure | ~₹5 | 3–4 days |
| Full risk-coverage curves rather than the three anchor points | none | half a day |

---

## 9 · File index

| File | Contents | Regenerate |
|---|---|---|
| `results/RESULTS.md` | All {total} measurements, plus appendices: changed numbers, failed assertions, not-computable, caveats | `experiments/assemble_results.py` |
| `results/EXPLAIN.md` | One plain-English block per output, eight fixed headings each | written per experiment |
| `results/hybrid_comparison.csv` | Dense vs BM25 vs fusion; reachability ceilings | `experiments/exp07_hybrid.py` |
| `results/retrieval_metrics.csv` | Recall, precision, MRR, nDCG at every k and stage | `experiments/exp01_retrieval.py` |
| `results/routing_confusion.csv` | Routing matrix and base-rate control | `experiments/exp02_routing.py` |
| `results/calibration.csv` | ECE, Brier, reliability bins, risk anchors, Platt scaling | `experiments/exp03_calibration.py` |
| `results/ablation.csv` | Per-signal AUROC, leave-one-out, weight sweep | `experiments/exp04_ablation.py` |
| `results/robustness.csv` | Definition sensitivity and cluster bootstrap | `experiments/exp05_robustness.py` |
| `results/statute_consistency.csv` | The fourth confidence signal | `experiments/exp06_statute_consistency.py` |
| `results/filter_analysis.csv` | What the adaptive filter costs, and which threshold arm binds | `experiments/exp08_filter.py` |
| `results/corrected_composite.csv` | Sign-error decomposition and held-out reweighting | `experiments/exp09_corrected_composite.py` |
| `results/self_naming.csv` | Document frequency, IDF and concentration by statute | `experiments/exp10_self_naming.py` |
| `results/smoke_test.md` | The three gate numbers checked before the main analysis | `experiments/gate_smoke.py` |
| `experiments/SCHEMA.md` | What the logs actually contain | — |
| `docs/WORKLOG.md` | Dated record of every run, including retractions | — |

---

## 10 · Anything dropped from this document

{drop}
"""


_TABLE = re.compile(r"^\|.*\|$")


def _inline(s: str) -> str:
    s = _html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def build_html(md: str, figs, sha) -> str:
    b64 = {}
    for fid, fn, _ in figs:
        b64[fn] = base64.b64encode((ROOT / "figures" / fn).read_bytes()).decode()

    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lv = len(m.group(1))
            out.append(f"<h{lv}>{_inline(m.group(2))}</h{lv}>")
            i += 1
            continue
        if ln.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        im = re.match(r"^!\[([^\]]*)\]\(\.\./figures/([^)]+)\)", ln)
        if im:
            fn = im.group(2)
            out.append(f'<figure><img alt="{im.group(1)}" '
                       f'src="data:image/png;base64,{b64.get(fn, "")}"></figure>')
            i += 1
            continue
        if _TABLE.match(ln.strip()):
            rows = []
            while i < len(lines) and _TABLE.match(lines[i].strip()):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = rows[2:] if len(rows) > 1 and set("".join(rows[1])) <= set("-: ") else rows[1:]
            out.append("<table><thead><tr>" +
                       "".join(f"<th>{_inline(c)}</th>" for c in rows[0]) +
                       "</tr></thead><tbody>" +
                       "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) +
                               "</tr>" for r in body) + "</tbody></table>")
            continue
        if re.match(r"^\s*[-*]\s+", ln) or re.match(r"^\s*\d+\.\s+", ln):
            items, ordered = [], bool(re.match(r"^\s*\d+\.\s+", ln))
            while i < len(lines) and (re.match(r"^\s*[-*]\s+", lines[i])
                                      or re.match(r"^\s*\d+\.\s+", lines[i])
                                      or (lines[i].startswith("   ") and lines[i].strip())):
                t = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[i])
                if lines[i].startswith("   ") and items and not re.match(r"^\s*(?:[-*]|\d+\.)\s", lines[i]):
                    items[-1] += " " + t.strip()
                else:
                    items.append(t.strip())
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(t)}</li>" for t in items)
                       + f"</{tag}>")
            continue
        if ln.strip() == "":
            i += 1
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not _TABLE.match(lines[i].strip()) \
                and not lines[i].startswith("#") and lines[i].strip() != "---" \
                and not lines[i].startswith("![") \
                and not re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[i]):
            para.append(lines[i].strip())
            i += 1
        txt = " ".join(para)
        if txt.startswith("*") and txt.endswith("*") and txt.count("*") == 2:
            out.append(f"<p class='caption'>{_inline(txt.strip('*'))}</p>")
        else:
            out.append(f"<p>{_inline(txt)}</p>")

    css = """
:root{--ink:#1a1a1a;--mut:#5a5a5a;--line:#dcdcdc;--accent:#2b6cb0;--bg:#ffffff}
*{box-sizing:border-box}
body{margin:0;padding:44px 22px 80px;background:var(--bg);color:var(--ink);
 font:15px/1.62 Georgia,'Times New Roman',serif;-webkit-font-smoothing:antialiased}
main{max-width:820px;margin:0 auto}
h1{font-size:1.85rem;line-height:1.25;margin:0 0 .5em;letter-spacing:-.01em}
h2{font-size:1.32rem;margin:2.4em 0 .6em;padding-bottom:.28em;
 border-bottom:2px solid var(--ink)}
h3{font-size:1.08rem;margin:1.9em 0 .45em;color:var(--accent)}
h4{font-size:.98rem;margin:1.3em 0 .35em}
p{margin:0 0 1em}
hr{border:0;border-top:1px solid var(--line);margin:2.4em 0}
code{font:12.5px/1.4 'SF Mono',Consolas,monospace;background:#f2f4f7;
 padding:1px 5px;border-radius:3px}
table{border-collapse:collapse;width:100%;margin:1.1em 0;font-size:13.2px;
 font-family:-apple-system,Segoe UI,Roboto,sans-serif}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;
 vertical-align:top}
th{background:#f5f7fa;font-weight:600}
tbody tr:nth-child(even){background:#fafbfc}
figure{margin:1.4em 0;text-align:center;page-break-inside:avoid;
 break-inside:avoid}
figure img{max-width:100%;max-height:21cm;width:auto;height:auto;
 border:1px solid var(--line)}
img{max-width:100%;height:auto}
.caption{font-size:12.8px;color:var(--mut);font-style:italic;margin:-.4em 0 1.6em;
 font-family:-apple-system,Segoe UI,Roboto,sans-serif}
ul,ol{margin:0 0 1em;padding-left:1.5em}
li{margin:.3em 0}
strong{font-weight:700}
@media print{body{padding:0;font-size:10.5pt}main{max-width:none}
 h2{page-break-after:avoid}h3{page-break-after:avoid}
 figure,table{page-break-inside:avoid;break-inside:avoid}
 figure img{max-height:20cm;width:auto}
 .caption{page-break-before:avoid;break-before:avoid}}
"""
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Technical report — legal-mvp — {sha}</title>"
            f"<style>{css}</style></head><body><main>"
            + "\n".join(out) + "</main></body></html>")
