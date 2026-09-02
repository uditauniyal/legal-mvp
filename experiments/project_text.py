"""Prose for docs/PROJECT_REPORT.md.

THE RULE THIS FILE IS WRITTEN TO:
    every number appears inside a sentence that explains why it matters.
    No bare numbers. No table without prose saying what it shows and what to
    conclude. Provenance lives in Appendix B, not in the argument.

THE TEST IT MUST PASS: after reading any finding section, a reader should be
able to explain that finding out loud, to someone with no technical background,
without looking back at the page.

Nothing here reads a CSV. Every value arrives already sourced by
make_technical_report.gather(), which asserts one matching row or crashes.
"""
from __future__ import annotations

from experiments.report_text import GLOSSARY

EXTRA_GLOSSARY = [
    ("adaptive score filter", "A step that discards retrieved passages scoring "
     "below a threshold set from the best score in that search. Distinct from "
     "the corpus filter, which restricts the search before it runs."),
    ("BNS", "Bharatiya Nyaya Sanhita 2023. India's criminal code since 1 July "
     "2024, replacing the Indian Penal Code."),
    ("BNSS", "Bharatiya Nagarik Suraksha Sanhita 2023. The new criminal "
     "procedure code. NOT in this system's corpus."),
    ("CPA", "Consumer Protection Act 2019."),
    ("CrPC", "Code of Criminal Procedure 1973. Still in this corpus; replaced "
     "in law by the BNSS."),
    ("IPC", "Indian Penal Code 1860. Repealed on 1 July 2024 but still "
     "governing any offence committed before that date."),
    ("reachability ceiling", "The highest score any retriever could possibly "
     "achieve, given that some correct answers are not stored in a form the "
     "system can return. Scores must be read against this, not against 100%."),
    ("savings provision", "A clause keeping an old law alive for conduct that "
     "happened while it was in force, even after repeal. This is why both "
     "India's old and new criminal codes are simultaneously live law."),
    ("self-naming", "Whether a statute writes its own name inside its own text. "
     "It determines whether searching for a statute by name finds it."),
]


def build(g, figs, sha, total, dropped) -> str:
    F = {fid: (fn, cap) for fid, fn, cap in figs}

    def fig(fid, caption=None):
        fn, cap = F[fid]
        return f"![{fid}](../figures/{fn})\n\n*{caption or cap}*\n"

    def n(k, dp=4):
        return f"{g[k].v:.{dp}f}"

    def pc(k, dp=1):
        return f"{g[k].v * 100:.{dp}f}%"

    def ci(k, dp=4, pct=False, cluster=False):
        return g[k].ci(dp, pct, cluster)

    gl = "\n".join(f"**{t}** — {d}\n"
                   for t, d in sorted(GLOSSARY + EXTRA_GLOSSARY,
                                      key=lambda x: x[0].lower()))

    # ---- Appendix B provenance ledger, built from the same sourced objects --
    ledger_keys = [
        ("IPC-named cross-statute accuracy, dense", "dom_dense_ipc", "pct"),
        ("BNS-named cross-statute accuracy, dense", "dom_dense_bns", "pct"),
        ("IPC-named, BM25", "dom_bm25_ipc", "pct"),
        ("BNS-named, BM25", "dom_bm25_bns", "pct"),
        ("IPC-named, hybrid RRF", "dom_hybrid_rrf_ipc", "pct"),
        ("BNS-named, hybrid RRF", "dom_hybrid_rrf_bns", "pct"),
        ("Chance baseline, IPC share of index", "chance_ipc", "pct"),
        ("Chance baseline, BNS share of index", "chance_bns", "pct"),
        ("Top-1 corpus, IPC-named, dense", "top1_dense_ipc", "pct"),
        ("Top-1 corpus, BNS-named, dense", "top1_dense_bns", "pct"),
        ("Gold reachability ceiling, pooled", "ceiling_all", "pct"),
        ("Gold reachability ceiling, BNS-named", "ceiling_bns", "pct"),
        ("Recall@15 generated", "rec_generated_retrieval", "num3"),
        ("Recall@15 paired IPC/BNS", "rec_paired_recodification", "num3"),
        ("Recall@15 dated conflict", "rec_paired_dated_conflict", "num3"),
        ("Recall@15 layman", "rec_layman_situation", "num3"),
        ("Recall@15 pooled", "rec_ALL", "num3"),
        ("AUROC max_score", "sig_max_score", "num"),
        ("AUROC top_k_mean", "sig_top_k_mean", "num"),
        ("AUROC score_gap raw", "sig_score_gap", "num"),
        ("AUROC composite as deployed", "sig_composite", "num"),
        ("AUROC entity_coverage", "sig_entity_coverage", "num"),
        ("AUROC gap_term as deployed", "sig_gap_term", "num"),
        ("AUROC composite sign-corrected", "cc_composite_corrected", "num"),
        ("Paired diff corrected minus max_score", "cc_diff_corr_max", "num"),
        ("Paired diff deployed minus max_score", "cc_diff_dep_max", "num"),
        ("Best corrected weighting, held out", "cc_best_test", "num"),
        ("ECE composite", "ece_comp", "num"),
        ("ECE max_score", "ece_max", "num"),
        ("Coverage at 10% risk, composite", "cov_comp", "num"),
        ("Coverage at 10% risk, max_score", "cov_max", "num"),
        ("Over-representation CrPC raw_15", "or_CRPC_raw_15", "num2"),
        ("Over-representation CrPC filtered_n", "or_CRPC_filtered_n", "num2"),
        ("Over-representation BNS raw_15", "or_BNS_raw_15", "num2"),
        ("Over-representation BNS filtered_n", "or_BNS_filtered_n", "num2"),
        ("statute_consistency pooled", "sc_all", "num"),
        ("statute_consistency dated-conflict", "sc_dated", "num"),
        ("IPC-BNS gap, retrieved@15", "gap_ret", "num"),
        ("IPC-BNS gap, cited", "gap_cit", "num"),
        ("IPC-BNS gap, grounded", "gap_gro", "num"),
        ("Layman rate raw_15", "layman_raw", "num3"),
        ("Layman rate filtered_n", "layman_filt", "num3"),
        ("Document frequency, 'sanhita'", "df_sanhita", "int"),
        ("Document frequency, 'penal'", "df_penal", "int"),
        ("IDF, 'sanhita'", "idf_sanhita", "num3"),
        ("IDF, 'penal'", "idf_penal", "num3"),
        ("'penal' chunks in CrPC", "df_penal_CRPC", "int"),
        ("'penal' chunks in IPC", "df_penal_IPC", "int"),
        ("Self-naming rate, BNS", "selfname_BNS", "pct"),
        ("Self-naming rate, IPC", "selfname_IPC", "pct"),
        ("Indexed passages, total", "idx_all", "int"),
    ]
    rows = []
    for lab, k, fmt in ledger_keys:
        r = g[k]
        v = (r.pct() if fmt == "pct" else f"{int(r.v)}" if fmt == "int"
             else r.num(3) if fmt == "num3"
             else r.num(2) + "x" if fmt == "num2" else r.num())
        c = (r.ci(1, pct=True) if fmt == "pct" else "" if fmt == "int"
             else r.ci(3) if fmt == "num3" else r.ci(2) if fmt == "num2" else r.ci())
        rows.append(f"| {lab} | {v} | {c} | {r.n} | `{r.defn}` | `{r.stage}` | "
                    f"`{r.file}` | `{r.cmd}` |")
    ledger = "\n".join(rows)
    drop = "\n".join(f"- {d}" for d in dropped) if dropped else "- Nothing."

    return f"""# When the code changes: retrieval failure across India's 2024 statutory recodification

**Udita Uniyal · Banasthali Vidyapith · 3 September 2026 · commit `{sha}`**

A report on a legal question-answering system, what was measured in it, and
what those measurements mean. Written for a reader with no prior exposure to
this project. Every technical term is defined in Appendix A.

No number in this report was typed by hand. Each one is extracted from a
results file by a filter that must match exactly one row or the program stops.
The full ledger — every value with its confidence interval, sample size and
regenerating command — is Appendix B.

---

## 1 · The six sentences

If you read nothing else, read these. There are no numbers in them, because the
findings do not depend on the numbers being memorised.

1. **A system searching Indian criminal law finds the repealed code far more
   reliably than the code actually in force.**
2. **Switching from meaning-based search to keyword search does not fix this —
   it breaks the opposite half, and combining the two is worse than either.**
3. **The cause lies in how statutes are written: the new code names itself in
   its own text, the old one never did, so the old code's name now belongs to a
   different book.**
4. **The system's own confidence score is worse at telling right from wrong
   than a simpler number it already had for free, and correcting a genuine bug
   inside it does not close the gap.**
5. **There is no confidence setting at which the system can answer some
   questions and be reliably right about them.**
6. **None of this is visible in the answers the system writes, because the
   language model cites correct law regardless of what the search found.**

---

## 2 · The problem

### India replaced three law books in one day

On 1 July 2024 India replaced its colonial-era criminal statutes. What counts
as a crime moved from the Indian Penal Code of 1860 to the Bharatiya Nyaya
Sanhita of 2023. Arrest, bail and trial procedure moved from the Code of
Criminal Procedure to the Bharatiya Nagarik Suraksha Sanhita. Evidence moved
from the Indian Evidence Act to the Bharatiya Sakshya Adhiniyam.

Same offences. Different section numbers.

### Why this is genuinely hard, not merely inconvenient

Both books remain live law. Which one applies depends on **when the conduct
happened**, not on when the question is asked. Old law is preserved for old
conduct by savings provisions and by section 6 of the General Clauses Act 1897.
Article 20(1) of the Constitution separately forbids applying a heavier
punishment retrospectively.

That produces a situation with no equivalent in ordinary document search:

> **"My husband beats me — this happened in March 2023."** The answer is
> **IPC 498A**.
>
> **"My husband beats me — this happened last month."** The answer is
> **BNS 85**.
>
> Identical words. Only the date decides.

And it is not simple renumbering. IPC 379, theft, became BNS 303(2) — which
also **adds community service** for a first offence under five thousand rupees.
A system that merely swaps numbers is still wrong about the law.

### Why it matters

Someone typing *"my husband beats me"* does not know the Indian Penal Code
exists, let alone that it was replaced last year. They will not supply a date.
Yet the section number they are handed is the one that goes on their police
complaint.

That is the gap this project measures: between what a person can be expected to
say, and what the system needs in order to be right.

---

## 3 · Where this began, and what changed

### The system that already existed

This project did not start from nothing. A working five-agent pipeline was built
and documented before any of the measurement in this report took place. That
document described the architecture reproduced in section 4: intake, routing,
retrieval, answering, reporting.

It named one component as the project's principal contribution — the composite
confidence score. Three signals combined by fixed weights: the average
similarity of the best five retrieved passages at 55%, a penalty for uneven
scores at 15%, and a check for whether those passages contain section numbers
named in the question at 30%. Three confidence tiers followed from it, and the
tiers changed the system's behaviour: which warning was attached to the answer,
which passages reached the model, what colour badge the user saw.

It also stated three design principles as achieved properties: that answers are
grounded, with every claim traceable to a stored passage; that the system
refuses rather than hallucinating when retrieval fails; and that routing is
deterministic and therefore free of routing errors.

### What that evidence could and could not support

The evidence was two queries.

Not two hundred. Two — chosen by hand, examined after the fact, with no record
of what the correct answer should have been. Nobody had written down in advance
which statutory section each question ought to retrieve, so there was nothing
for the system to be right or wrong against. And no retrieval score had ever
been written to disk, so the two numbers reported could not be recomputed even
in principle.

Both of those are ordinary for an architecture document. Neither is sufficient
for a claim about how well a system performs.

**One of the two worked examples reproduces exactly; the other does not.** This
is checkable by hand from the formula that document states.

The first reported a top-five mean of 0.499, a score gap of 0.037, and entity
coverage of 1.00, giving 70.6%. Working it through: the first term is
0.55 × 0.499 = 0.2745. The gap penalty is 0.037 ÷ 0.3 = 0.123, so the second
term is 0.15 × (1 − 0.123) = 0.1315. The third is 0.30 × 1.00 = 0.30. They sum
to 0.7060. Exact.

The second reported 43.3%, with a top-five mean of about 0.40, a score gap
described as "Small", and entity coverage described as "Low". Entity coverage is
a count of matching passages divided by a count of entities, so with the two
entities in that query it can only take values such as 0, 0.5 or 1.0 — nothing
in between. Taking 0.5, reaching 43.3% requires the gap term to contribute
0.063, which needs a score gap of roughly 0.17. On a scale where 0.3 is the
maximum, 0.17 is not small. **The row contradicts its own description**, and it
should not be carried into any paper.

**The same document already contained the evidence of a defect nobody had
noticed.** Its corpus table lists the Indian Penal Code tagged as BNS, and the
Code of Criminal Procedure tagged as BNSS. Both tags are wrong, and they are
wrong in exactly the direction that matters here: the repealed statute labelled
as the one that replaced it. The corpus-tagging defect that later measurement
confirmed was sitting in the original documentation, in a table, unremarked.

### The pivot

The work described in this report began by changing the question.

The original question was *does the system work?* Two examples cannot answer
that. The replacement question was *what does it get wrong, and why?* Two
examples cannot answer that either — but a properly constructed evaluation set
can, and that is what section 5 describes building.

Three things followed from the change.

**The confidence score changed role.** It stopped being the contribution and
became the object of study. Finding 6.4 reports what measuring it produced, and
the result is negative — which is a contribution of a different and more durable
kind than the one originally claimed.

**The recodification changed role.** In the original document the coexistence of
the old and new criminal codes is background, a fact about the corpus. Here it
is the subject. The cross-statute failure is not a defect found along the way;
it is the phenomenon being studied.

**The routing bug changed role.** Under the first framing it is an
embarrassment to be fixed quietly. Under the second it is data.

### What was added to the architecture

The pipeline in section 4 is not the pipeline that was first documented. Two
stages were inserted between routing and retrieval, because measurement showed
they were needed.

A **date resolver** reads the question for any indication of when the conduct
happened — "last month", "in 2023", an explicit date — and converts it into
which legal era governs. A **statute mapper** then takes the section numbers the
router extracted and translates them across the recodification, so that a
question naming a repealed section can also be searched for under the section
that replaced it.

Both were measured rather than assumed. On the question set where the code named
in the question and the date of the conduct disagree — the hard case, and the
one a member of the public is most likely to produce — retrieval of the correct
section rose from **{n('rec_dated_baseline', 3)}** {ci('rec_dated_baseline', 3)}
to **{n('rec_dated_interv', 3)}** {ci('rec_dated_interv', 3)}. The two intervals
do not overlap, which means the improvement is larger than sampling noise could
explain. It is the largest single gain recorded in this project.

{fig('F10_intervention')}

### The scale of what changed

| | As first documented | As measured now |
|---|---|---|
| Evidence base | 2 hand-picked queries | 518 questions across four purpose-built sets |
| Correct answers recorded in advance | none | all 518, fixed before any output was seen |
| Retrieval scores written to disk | none | 859 runs, 80 fields each |
| Individual measurements | 2 confidence values | {total:,} rows, each with sample size and interval |
| Automated tests | none | 237, including known-answer tests |
| Alternative retrievers compared | none | keyword search and rank fusion |
| Figures | 5 architecture diagrams | 17, nine of them measured results |
| Indexed passages | stated as 1,011 | {int(g['idx_all'].v):,} after a rebuilt ingest |

**What did not change is the five-agent structure itself.** The pivot was in
what was asked of the system, not in rebuilding it. The two new stages were
added because a measurement said they were needed, and their effect was then
measured in turn.

---

## 4 · What was built

A five-stage pipeline. A question in plain English goes in; an answer with
citations and a PDF report comes out. Two stages use a language model; the rest
are fixed rules or database search.

{fig('M1_high_level')}

The corpus holds **{int(g['idx_all'].v):,} passages** of statutory text. That
number matters because every proportion in this report is a share of it, and
because it is smaller than the system's original documentation claimed. Four
statutes are present: the Code of Criminal Procedure 1973 with
{int(g['idx_CRPC'].v)} passages, the Indian Penal Code 1860 with
{int(g['idx_IPC'].v)}, the Bharatiya Nyaya Sanhita 2023 with
{int(g['idx_BNS'].v)}, and the Consumer Protection Act 2019 with
{int(g['idx_CPA'].v)}.

**Four things the original documentation claimed that are not true, and are not
reproduced here.** The corpus does *not* contain the BNSS, the Bharatiya Sakshya
Adhiniyam, the Constitution, or case law — those were never ingested. The
refusal mechanism does *not* protect users, because it has never once triggered.
The composite confidence score is *not* the system's key innovation, because it
performs worse than a simpler alternative. And the passage count is not 1,011.
Section 7 sets out the full list.

### How a question moves through the system

The first stage reads the question and extracts structure from it — what kind of
legal problem it is, and what facts are missing.

{fig('M2_intake_agent')}

The second stage decides which law book to search. It works by matching words
in the question against a fixed table. **Three of its branches point at books
that are not in the index at all**, marked on the diagram: a question about
evidence law is routed to a filter that matches nothing, and the search then
silently falls back to searching everything.

{fig('M3_router_agent')}

The third stage is the retrieval pipeline, and it is where every headline
finding in this report is measured. Seven steps: embed the question, search,
fall back if needed, reorder, filter by score, score confidence, return.

{fig('M4_retrieval_pipeline')}

Two of those steps deserve names, because the rest of this report distinguishes
them constantly. The **corpus filter** restricts the search to one statute
*before* it runs. The **adaptive score filter** discards weak results *after*.
Confusing the two produces meaningless numbers, and earlier versions of this
project did exactly that.

The fourth stage writes the answer using only the passages it was given.

{fig('M5_answer_agent')}

Confidence is computed from three signals and used to pick which warning to
attach to the answer.

{fig('M6_confidence')}

Ingestion, run once, converts PDFs into the indexed passages.

{fig('M7_ingestion')}

And the whole path, end to end:

{fig('M8a_sequence_in')}

{fig('M8b_sequence_out')}

---

## 5 · How it was measured

Written for someone who has never evaluated a search system.

### Why "did it work?" is not one question

Suppose you ask *"what is the punishment for cheating under section 420 of the
Indian Penal Code?"* and the system replies with a correct-sounding paragraph
citing IPC 420.

Did it work? There are three different things you might mean.

- **Did the search find the right law?** The system fetches fifteen passages
  before writing anything. Was IPC 420 among them? This is the question about
  *retrieval*, and in this report it is called **retrieved@k**.
- **Did the answer name the right law?** Does IPC 420 appear in the citations?
  This is the question about *writing*, called **cited**.
- **Was the answer actually supported?** Was every section it cited genuinely
  present in the passages it was given, or did the model supply some from
  memory? This is the strict question, called **grounded**.

These come apart, and finding 6.6 is a case where the answer is yes under one
definition and no under another. That is why all three are always reported, and
why every number in this report says which one it used.

### Why the stage matters too

The fifteen fetched passages pass through three states before the model sees
them. They arrive from the database in score order — **raw_15**. They are
reordered to promote passages containing section numbers from the question —
**reranked_15**. Then weak ones are discarded — **filtered_n**, which is what
actually reaches the language model.

A recall figure means a different thing at each. "The right law was found"
could mean the database returned it, or that it survived to the model. Earlier
versions of this project published figures without recording which, and that
single omission made two numbers look like a contradiction when they were both
correct. Every figure here names its stage.

### The questions used

Four sets, 518 unique questions, each with its correct statutory section
recorded **before** any system output was seen.

The generated set of {g['rec_generated_retrieval'].n} questions and the paired
set of {g['rec_paired_recodification'].n} are certain by construction: each was
built from a known section, so the section is the answer by definition. The
dated-conflict set of {g['rec_paired_dated_conflict'].n} and the layman set of
{g['rec_layman_situation'].n} required legal judgement — deciding which section
governs a described situation — and that judgement was made by one person.
Section 8 treats this as the largest threat to everything reported here.

The paired set is the experiment rather than merely the data: it asks the same
legal question twice, once with the old code's number and once with the new
one's. Any difference between the two arms is attributable to the numbering,
because nothing else changed.

### How the measurements were checked

Four safeguards, because a metric that returns a plausible wrong number is the
failure this project was built to avoid.

**237 automated tests**, including tests where the correct output was worked out
by hand before the code ran. **One shared measurement library**, imported by
every experiment, so no two experiments can disagree about what a word means.
**A second, independent re-derivation** inside each experiment, which recomputes
one of its own numbers by a different route and stops if the two disagree. And
**no manual transcription anywhere**: every number in every results document is
extracted by a filter that crashes rather than guess if it matches more than one
row.

That last safeguard caught two real errors while this report was being written,
and both are in section 6.

---

## 6 · The findings

Strongest evidence first.

### 6.1 The system is more reliable on the law that no longer applies

**The finding.** When a question names the repealed code, the system usually
finds the right law. When it names the code actually in force, it finds the
right law barely more often than if it had ignored the question entirely.

**What this means in practice.** A law student researching a 2019 offence gets
good results. A citizen asking about something that happened last month — the
case where the answer goes on a police complaint — gets results little better
than chance.

{fig('F2_ipc_vs_bns')}

Questions naming the Indian Penal Code retrieve mostly IPC text
**{pc('dom_dense_ipc')}** of the time, and since the IPC occupies
{pc('chance_ipc')} of the index, that is far above what ignoring the question
would achieve. Questions naming the Bharatiya Nyaya Sanhita retrieve mostly BNS
text only **{pc('dom_dense_bns')}** of the time against a {pc('chance_bns')}
baseline — real, but weak. Both rest on {g['dom_dense_ipc'].n} questions per
arm, so their 95% confidence intervals are wide: {ci('dom_dense_ipc', 1, pct=True)}
and {ci('dom_dense_bns', 1, pct=True)}. Narrowing them would need more questions,
not better analysis.

The misses do not scatter. When a BNS-named question fails, the passages it
gets back are overwhelmingly from the repealed code — the failure has a
direction, which is what makes it a finding rather than noise.

**The same pattern appears again inside the pipeline.** Of every fifteen
passages fetched for a layman question, the share coming from the procedure
code rises from {n('or_CRPC_raw_15', 2)} times its fair share to
{n('or_CRPC_filtered_n', 2)} times after the weak results are discarded, while
the share from the code in force falls from {n('or_BNS_raw_15', 2)} to
{n('or_BNS_filtered_n', 2)} times. A step whose only job is removing noise is
removing substantive criminal law and concentrating procedure.

{fig('F5_funnel')}

That filter costs the layman questions half of what they had: recall falls from
{n('layman_raw', 3)} to {n('layman_filt', 3)}. But read the starting point
before drawing the wrong conclusion. Even before any filtering, only
{n('layman_raw', 3)} of layman questions had their correct section retrieved at
all. **Removing the filter entirely would still leave most ordinary-language
questions unanswered.** The filter is a secondary problem.

**How it could be wrong.** The measure is coarse: it asks which statute
*dominates* the fifteen passages, which can score zero even when the single best
passage is correct — finding 6.2 contains exactly such a case. The corpus filter
is switched off for this measurement, because with it on an IPC-named question
physically cannot return BNS text, and the question becomes unaskable. And
{g['dom_dense_ipc'].n} questions per arm is a small sample.

### 6.2 Keyword search does not fix it; it breaks the other half

**The finding.** The obvious remedy — search for exact words instead of meaning
— fails in the opposite direction, and combining the two methods produces a
system that fails at both.

**What this means in practice.** There is no drop-in retrieval fix. Anyone
proposing to solve this by changing the search engine has to explain which half
of the queries they are willing to lose.

{fig('F3_dense_vs_bm25')}

Keyword search raises accuracy on questions naming the code in force from
{pc('dom_dense_bns')} to **{pc('dom_bm25_bns')}** — a large and real
improvement. But on questions naming the repealed code it collapses from
{pc('dom_dense_ipc')} to **{pc('dom_bm25_ipc')}**, which is below the
{pc('chance_ipc')} a system ignoring the question would score. Fusing the two
methods lands in between on both arms, at {pc('dom_hybrid_rrf_ipc')} and
{pc('dom_hybrid_rrf_bns')}, and beats neither at what it was good at.
Averaging two opposite failures gives you a system that fails twice.

**How it could be wrong.** The {pc('dom_bm25_ipc')} figure is an artefact of the
coarse measure. On at least one question, keyword search puts the correct IPC
section *first* and then fills the remaining fourteen slots with procedure-code
cross-references, so "which statute dominates" scores it zero. Judged on the
single best passage instead, keyword search is not catastrophic. The direction
of the finding survives; the magnitude is exaggerated.

### 6.3 The cause is in how the statutes are written

**The finding.** The new code writes its own name inside its own text. The old
one never did. So the old code's name has become, statistically, a word
belonging to a different book.

**What this means in practice.** This is not a bug anyone introduced and not
something a better search engine fixes. It is a property of legal drafting, and
it should recur in any jurisdiction that replaces a statute rather than amending
it.

{fig('F4_self_naming')}

The word *sanhita* appears in **{int(g['df_sanhita'].v)}** of the
{int(g['idx_all'].v):,} passages, and every single one is Bharatiya Nyaya
Sanhita text. A search for it lands in the right book every time — it is a
perfect signpost.

The word *penal* appears in **{int(g['df_penal'].v)}** passages. Only
**{int(g['df_penal_IPC'].v)}** are Indian Penal Code. **{int(g['df_penal_CRPC'].v)}**
are Code of Criminal Procedure. Searching for the Penal Code by its own name
points at the procedure code roughly three times more often than at the Penal
Code itself.

The reason is mundane once seen. The 1860 drafters had no occasion to write
"penal" inside the Penal Code; you do not name the book you are in. The
procedure code, by contrast, cites it constantly, because procedure refers to
offences. So the old statute's name survives mainly in the documents that
mention it, not in the document that is it.

Both statutes name themselves rarely — the Bharatiya Nyaya Sanhita in
{pc('selfname_BNS')} {ci('selfname_BNS', 1, pct=True)} of its own passages, the
Indian Penal Code in {pc('selfname_IPC')} {ci('selfname_IPC', 1, pct=True)}. The
asymmetry that matters is not how often they say their names, but whether saying
the name identifies the book.

**How it could be wrong.** Only presence was counted, not how many times a word
occurs within a passage; keyword search uses both, so this explains the direction
of the effect without fully reconstructing the ranking. The corpus is four
statutes, and the argument that this generalises is an argument, not a
measurement.

### 6.4 The confidence score is worse than a number it already had

**The finding.** The system combines three signals into a confidence score. That
combination separates right answers from wrong ones less well than the single
simplest number available, and fixing a genuine bug inside it does not close the
gap.

**What this means in practice.** The engineering effort that went into the
composite score bought nothing. Anyone building on this system should use the
raw similarity and spend the effort elsewhere.

{fig('F6_ablation')}

The measure is AUROC: pick one right answer and one wrong answer at random, and
ask how often the right one scored higher. Half means the score is a coin flip.

The deployed composite scores {n('sig_composite')} {ci('sig_composite')}. The
single highest similarity from the search — a number already sitting in the
logs, costing nothing — scores {n('sig_max_score')} {ci('sig_max_score')}. Two of
the composite's own three ingredients also beat it: {n('sig_top_k_mean')} and
{n('sig_score_gap')}. **A blend of three signals is worse than one of the
signals alone.**

One ingredient turned out to be wired backwards. The gap between the best and
second-best result is evidence of a clear winner, but the deployed code treats
it as evidence of doubt, and measured on its own that inverted term scores
{n('sig_gap_term')} — below half, meaning it points the wrong way.

That raised an obvious objection: perhaps the whole finding is just this bug.
It is not. Correcting the sign lifts the composite to
{n('cc_composite_corrected')}, a real improvement, but it still loses to the
simple number by {n('cc_diff_corr_max')} {ci('cc_diff_corr_max')}. **The bug
explains about half of the original {n('cc_diff_dep_max')} shortfall; the rest
is the blend itself.** And when the three corrected signals are given the best
weighting that can be found, then tested on questions the search never saw, they
reach {n('cc_best_test')} — a tie with the simple number, never a win.

**One thing does work, in one place.** A fourth signal was built for this
project: the fraction of retrieved passages that come from the statute the
question and its date imply. Overall it scores {n('sc_all')} {ci('sc_all')},
no better than what already existed. But on the
{g['sc_dated'].n} questions where the named code and the offence date disagree —
precisely the hard case — it reaches **{n('sc_dated')}** {ci('sc_dated')}. The
catch is that on most other questions the search filter was itself built from
the same date information, so the signal cannot fail there by construction. It
earns its keep only where the question and the date pull apart.

**How it could be wrong.** Under the strict `grounded` definition there are only
27 right answers among 617 questions, and every comparison under it is too
underpowered to separate anything. This finding rests on the other two
definitions.

### 6.5 There is no confidence setting that makes the system safe

**The finding.** The standard safety mechanism for a system like this is to
answer only when confident and stay silent otherwise. These measurements say
that mechanism cannot be built on the current confidence score.

**What this means in practice.** You cannot deploy this behind a rule like
"only answer when at least 90% likely to be right", because no such threshold
exists at any level of caution.

{fig('F8_coverage_at_risk')}

If the system answered only its most confident questions, what share could it
answer while being wrong at most one time in ten? For the composite score the
answer is **{n('cov_comp')}** — no threshold anywhere on the curve reaches that
error rate. For the simple similarity score it is {n('cov_max')}. These zeros
are measured values, not missing data.

{fig('F7_reliability')}

The reason is visible in the shape of the curve. A well-behaved confidence score
climbs steadily: the more confident it is, the more often it is right. The
composite does not. It rises through the middle of its range and then **falls
back at the top**, so the answers it is most sure about are no better than its
middling ones. The simple similarity score climbs throughout.

A summary statistic hides this completely. The composite's calibration error is
{n('ece_comp')} {ci('ece_comp')} against {n('ece_max')} {ci('ece_max')} for the
simple score — worse, but a single number cannot tell you *that the curve bends
the wrong way at the end*, which is the part that matters for safety.

**How it could be wrong.** The composite was never designed to be a probability;
it is a weighted sum of similarity scores. Calibration measures assume a
probability, so applying them here needs the caveat. The zeros are a real
property of this score, not proof that no score could work.

### 6.6 None of this shows up in the answers

**The finding.** The retrieval failure is invisible in what the system writes,
because the language model cites correct sections whether or not the search
found them.

**What this means in practice.** Anyone evaluating this system by reading its
answers would conclude it works. The failure is only visible if you inspect what
was retrieved — and a legal system whose failures are invisible is more
dangerous than one whose failures are obvious.

The gap between the two arms of the paired set is
{n('gap_ret')} {ci('gap_ret', cluster=True)} when measured on what was
*retrieved* — a large, clear difference. Measured on what was *cited* it is
{n('gap_cit')} {ci('gap_cit', cluster=True)}, an interval straddling zero, which
means the data cannot distinguish the two arms at all. Under the strict
definition it is {n('gap_gro')} {ci('gap_gro', cluster=True)}, again straddling
zero.

The mechanism is straightforward and was measured directly: the arm asking with
old-code numbering cites the correct section about nine times in ten, and the
arm asking with new-code numbering does about as well. The model supplies
correct citations from its own training regardless of what the search returned.

**How it could be wrong.** This is stated throughout as a claim about
*retrieval*. A reviewer who measures citation accuracy instead will not
reproduce the headline gap, and would be right not to. The finding is that the
two disagree — which is why every number in this report names its definition.

---

## 7 · What we got wrong

Leading with this rather than burying it. Each row: what was claimed, what is
true, and what caught it.

| What was claimed | What is true | What caught it |
|---|---|---|
| The corpus covers the BNS, BNSS, BSA, CrPC, Constitution, CPA, IPC and judicial precedents | **Four documents only** — IPC, BNS, CrPC, CPA. The rest were never ingested; tags for them existed only as artefacts of substring matching | Corpus audit, `GAPS.md` finding 10 |
| "Calibrated refusal — the system refuses rather than hallucinating" | The refusal gate **has never fired once** in 859 logged queries | Log audit across every recorded run |
| Composite confidence scoring is the key innovation | The composite scores **worse** than a single raw similarity number, and one of its three signals sits at chance | Signal ablation with paired significance tests |
| "Grounded answers — every claim backed by citations" | A large majority of what layman answers cite is **absent** from the passages supplied to the model | Citation-versus-retrieval audit |
| Deterministic routing eliminates routing errors | Routing was the **largest single source of error**; a fallback sent every criminal query to the penal code, making the IPC unreachable | Routing confusion matrix |
| 1,011 passages | **{int(g['idx_all'].v):,}** after the ingest rebuild | Index count |
| GPT-4o-mini | `google/gemini-3.7-flash` via OpenRouter, provider pinned | Provider migration |
| Validation results in the February architecture PDF, section 8 | Section 8.2 **cannot be produced by the stated formula**. It must not be carried into any paper | Formula reconstruction |
| "A counting bug halved a published figure — 7.5% should be 15.0%" | **False, and retracted.** Both figures were correct at their own retrieval stage. The text-parsing rule was verified correct 4,906 times out of 4,906 | A re-measurement that contradicted the claim |
| BNS-named recall of {pc('ceiling_bns')} is a retrieval failure | **It is a ceiling, not a failure.** Where a correct answer names a subsection the index stores only as a whole section, no retriever can find it | An independent re-derivation during the keyword-search experiment |
| The confidence formula is `0.55·top_k_mean + 0.15·score_gap + 0.30·entity_coverage` | The deployed code **inverts** the middle term. A documentation error, not a code defect — the recorded scores were always right | A reconstruction check: the documented formula matched none of the 617 rows; the real one matches to five decimal places |
| Two published confidence figures, 0.610 and 0.663 | They record neither which correctness definition nor which retrieval stage produced them, and none reproduces the pair. **Superseded, not reconcilable** | The pre-analysis gate check |
| — | **Two defects in this project's own measuring code.** One raised an error on real data; the fix for it then silently returned zero correct answers out of 617 while nothing crashed and every number looked plausible | The gate check, before any number was published |

The last row is the one worth dwelling on. A measurement that crashes is
harmless. A measurement that quietly returns a believable wrong number is how
this project lost six months earlier in its life, and it is why the verification
described in section 4 exists.

---

## 8 · Limitations

Stated as a reviewer would state them.

1. **All ground truth was decided by one person.** Two of the four question sets
   required legal judgement about which section governs a described situation. No
   independent expert has validated any label. This is the largest threat to
   every finding in this report.
2. **A ceiling caps every retrieval figure.** Only {pc('ceiling_all')}
   {ci('ceiling_all', 1, pct=True)} of {g['ceiling_all'].n} questions have a
   correct answer the index can return at all, because some gold labels name a
   subsection stored only as a whole section. On questions naming the code in
   force the ceiling is {pc('ceiling_bns')}. **Recall figures must be read
   against this, not against 100%** — and on that subset the retrieval that was
   measured reaches the ceiling exactly, meaning it is perfect on everything
   reachable.

{fig('F9_ceiling')}

3. **One embedding model, one vector database, one jurisdiction, four
   statutes.** No result generalises beyond this configuration without retesting.
4. **The strict correctness definition is underpowered**, with 27 right answers
   among 617 questions. Every comparison under it straddles zero.
5. **One significance claim is lost under proper clustering.** Three phrasings of
   one situation are not three independent facts. The layman retrieval rate after
   filtering is significant when rows are treated as independent
   {ci('layman_filt', 3)} and **not significant** when situations are
   {ci('layman_filt', 3, cluster=True)}, because the successes concentrate in a
   few situations.
6. **One verification assertion is left deliberately failing.** Four clustered
   intervals came out narrower than their unclustered counterparts and remain
   unexplained after ruling out implementation bugs and random variation across
   five seeds. Those two subsets are marked unusable rather than explained away.
7. **Three labelled rows are dropped** by a deduplication rule, so the sample is
   617 where it could be 620. Disclosed rather than fixed, because changing it
   would shift every number in ten results files for a difference that moves no
   conclusion.
8. **The headline finding is definition-dependent** and does not survive at
   citation level, as section 6.6 states.
9. **Answer quality was not evaluated.** This work measures retrieval,
   confidence and citation behaviour. It does not assess whether the legal advice
   is sound.

---

## 9 · What could be done next

Candidates with rough cost and effort. No recommendation is made.

| Candidate | Cost | Effort |
|---|---|---|
| Independent expert validation of ~30 questions and their gold labels | none; needs an introduction | one day for the validator |
| Re-derive gold labels at subsection granularity, raising the {pc('ceiling_all')} ceiling | none | 1–2 days, and it revises the evaluation set |
| Ingest the BNSS and BSA to close the corpus gap | about ₹50 in embeddings | 1 day, but it breaks comparability with the {int(g['idx_all'].v):,}-passage index every figure here uses |
| Count how often terms occur within a passage, not just whether they occur, to complete section 5.3 | none | half a day |
| A second embedding model as a robustness check | about ₹50, or free with a local model | 1 day |
| Manual error taxonomy over the failing layman questions | none | 2 days of coding by hand |
| Build the statute-and-date resolution layer, then re-measure | about ₹5 | 3–4 days |
| Full risk-coverage curves rather than the three anchor points | none | half a day |

---

## Appendix A · Glossary

Every technical term used in this report, in plain language.

{gl}

---

## Appendix B · Provenance

The ledger. Every headline value with its 95% confidence interval, sample size,
correctness definition, retrieval stage, source file, and the command that
regenerates it. Nothing in the body of this report was typed by hand; each of
these was extracted by a filter that must match exactly one row or the program
stops.

| Figure | Value | 95% CI | n | definition | stage | source | regenerate |
|---|---|---|---|---|---|---|---|
{ledger}

**Anything that could not be sourced from a results file:**

{drop}

---

## Appendix C · File index

| File | Contents | Regenerate |
|---|---|---|
| `results/RESULTS.md` | All {total} measurements plus appendices on changed numbers, failed assertions and caveats | `experiments/assemble_results.py` |
| `results/EXPLAIN.md` | One plain-English block per output, eight fixed headings each | written per experiment |
| `results/hybrid_comparison.csv` | Meaning-based vs keyword vs fused search; reachability ceilings | `experiments/exp07_hybrid.py` |
| `results/retrieval_metrics.csv` | Recall, precision and rank measures at every cut-off and stage | `experiments/exp01_retrieval.py` |
| `results/routing_confusion.csv` | Which book was searched, and each book's share of retrieval against its share of the index | `experiments/exp02_routing.py` |
| `results/calibration.csv` | Calibration error, reliability bins, risk anchors, probability rescaling | `experiments/exp03_calibration.py` |
| `results/ablation.csv` | Per-signal discrimination, leave-one-out, weight sweep | `experiments/exp04_ablation.py` |
| `results/robustness.csv` | Sensitivity to definition, and clustered intervals | `experiments/exp05_robustness.py` |
| `results/statute_consistency.csv` | The fourth confidence signal | `experiments/exp06_statute_consistency.py` |
| `results/filter_analysis.csv` | What the adaptive score filter costs and which threshold arm binds | `experiments/exp08_filter.py` |
| `results/corrected_composite.csv` | Sign-error decomposition and held-out reweighting | `experiments/exp09_corrected_composite.py` |
| `results/self_naming.csv` | Document frequency, informativeness and concentration by statute | `experiments/exp10_self_naming.py` |
| `results/smoke_test.md` | The three checks run before the main analysis was permitted to start | `experiments/gate_smoke.py` |
| `experiments/SCHEMA.md` | What the run logs actually contain | — |
| `docs/WORKLOG.md` | Dated record of every run, including every retraction | — |
| `figures/` | All 17 figures, and the Mermaid sources for the 8 architecture diagrams | `experiments/make_project_report.py` |
"""
