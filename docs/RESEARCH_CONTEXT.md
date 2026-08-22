# Legal MVP — Research Context

**What this document is:** why this project exists as research, what the supervisor has directed, what the literature says, and where it could be published. The correspondence is preserved verbatim so the reasoning survives even when memory doesn't.

**Author:** Udita Uniyal, B.Tech IT (3rd year), Banasthali Vidyapith
**Supervisor:** Prof. Nisheeth Joshi
**Status as of 2026-08-17:** evaluation not started; blocking defects identified but unfixed.

---

## The stakes

This single artifact serves two purposes:

1. The **official third-year B.Tech project** — done solo, where most students work in teams.
2. A **first attempt at peer-reviewed publication.**

That dual role constrains the work. A shortcut acceptable for a college demo — hard-coded results, patching the database instead of the code, reporting numbers from a code version that no longer exists — is disqualifying in review. Where the two standards differ, the publication standard governs.

---

## Correspondence

### 1 · Udita → Prof. Joshi, 5 August 2026

> Dear Sir,
>
> I hope you are doing well. I wanted to update you on the Legal MVP work, share some reading I have been doing, and get your thoughts on where we might take it.
>
> The system is complete and running end to end. A question in plain language is triaged into a structured case context, routed to the right corpus with the relevant sections extracted, matched against the Qdrant index with reranking and adaptive filtering, answered with citations attached, and written out as a PDF advisory. The corpus covers the BNS 2023, IPC 1860, CrPC 1973 and the Consumer Protection Act 2019. The confidence score is the part I consider our contribution: instead of a single similarity average, it combines the strength of the top matches, their consistency, and whether the sections the user asked about actually appear in what was retrieved, and it then governs filtering, disclaimers and refusal.
>
> I have tested across four query categories, straightforward, vague, complex and reasoning. Reviewing those runs, I found two gaps. The confidence scores and individual signal values were not logged, so the results cannot support the claims a paper needs. And on civil or consumer phrasings the retrieval seems to drift towards the CrPC even where the Consumer Protection Act would be correct, which I suspect is because the Router only matches keywords like ipc and crpc. I would like to measure both properly rather than rely on impressions.
>
> I have also been reading around our topic. On Indian legal NLP the key references are Malik et al., ILDC for CJPE (ACL-IJCNLP 2021, arXiv:2105.13562), Paul et al. on InLegalBERT (arXiv:2209.06049), and Paul et al., LeSICiN on statute identification (AAAI 2022, arXiv:2112.14731). On motivation, Dahl et al., Large Legal Fictions (Journal of Legal Analysis 2024, arXiv:2401.01301) and Magesh et al., Hallucination-Free? (Journal of Empirical Legal Studies 2025, arXiv:2405.20362) are the strongest, the latter finding that even commercial legal RAG tools hallucinate between seventeen and thirty-three per cent of the time. On the confidence mechanism, the closest prior work is Yan et al., Corrective RAG (arXiv:2401.15884) and Asai et al., Self-RAG (ICLR 2024, arXiv:2310.11511), with Jeong et al., Adaptive-RAG (NAACL 2024, arXiv:2403.14403) relevant to routing, and Soudani, Kanoulas and Hasibi (Findings of ACL 2025) showing that reliable confidence estimation in RAG remains an open problem. Gao et al. (EMNLP 2023, arXiv:2305.14627) offers a principled way to check whether our citations actually support our answers.
>
> This has shifted how I think we should position the work. Scoring retrieval quality and gating generation on it is fairly well established, so the composite score may be less novel than I assumed. What seems genuinely ours is the empirical side, a careful study of where a multi-agent legal RAG system fails on real Indian queries, with confidence tiers calibrated to how embeddings actually behave on Indian statutory text. I would value your view on whether that reading is right.
>
> With that in mind, here is what I think we could do. I could re-run the evaluation over fifty or more queries with full logging and ground-truth sections noted in advance, which would give us retrieval metrics, a comparison of confidence tiers against correctness, a calibration analysis, an ablation over the three weights and a baseline comparison. I would also like to diagnose the routing problem and try a hybrid keyword and dense retriever, reporting the before and after. I have the compute and think it is a few sessions of work.
>
> *[venue list — reproduced in the Venues section below]*
>
> Sir, I would be grateful if you could guide me on what our next step should be, what you feel we should take up, and what I can begin working on from my side in the meantime. I am still learning how all of this works, and your direction would help me a great deal.
>
> The August dates are tight but reachable if we move quickly; the later ones would let us do the evaluation properly first. I am not sure which trade-off is wiser and would value your judgement.
>
> I would be happy to prepare the draft and send it for your review, or to write it together if you would prefer to shape the framing yourself, whichever suits you better.
>
> Whenever convenient, I would really appreciate your feedback on the framing, on whether this plan makes sense, and on which venue you think we should aim for.
>
> Thank you for your guidance.
>
> With regards,
> Udita Uniyal
> B. Tech - IT, III Year

### 2 · Prof. Joshi → Udita, 6 August 2026

> Dear Udita,
>
> Thank you for the detailed update. You have made very good progress, and I am pleased to see that the system is now working end-to-end. The architecture and confidence-aware pipeline appear to be well thought out, and the documentation is comprehensive.
>
> I also appreciate the literature review you have done. Based on what you have found, I agree that the strongest contribution is unlikely to be the confidence score by itself. Instead, the paper should focus on a rigorous empirical evaluation of confidence calibration, retrieval quality, routing behaviour, and failure analysis for an Indian legal RAG system.
>
> As the immediate next step, I suggest that you:
>
> 1. Build a well-annotated evaluation set (at least 50–100 representative legal queries) with ground-truth statutory sections.
> 2. Add complete logging for all retrieval signals, confidence values, routing decisions, and retrieved sections.
> 3. Evaluate retrieval performance, confidence calibration, and answer correctness.
> 4. Investigate the routing issue and compare the current router with a hybrid routing strategy.
> 5. Perform an ablation study on the confidence score components and compare against suitable baselines.
>
> Once these experiments are complete, we can decide the exact framing of the paper and identify the most appropriate venue.
>
> Regarding submissions, I would recommend prioritizing the quality of the evaluation over meeting the earliest deadlines. A stronger paper with solid experimental evidence will have a better chance at a good venue than a rushed submission. If substantial results are ready in time, we can consider NLLP or FIRE; otherwise, ACL Rolling Review or JURIX would be better options.
>
> Please begin the evaluation and logging work immediately. Prepare the experimental results, figures, and tables as they become available, and then we can decide the final narrative and venue.
>
> Good work so far. Keep me updated on your progress, and we can discuss the results once the evaluation is complete.
>
> Best wishes,
> Nisheeth

---

## The directive, as a checklist

| # | Task | Status | Blocked by |
|---|---|---|---|
| 1 | Annotated eval set, 50–100 queries with ground-truth sections | ⬜ Not started | Nothing — can start now |
| 2 | Complete logging: signals, confidence, routing, retrieved sections | ⬜ Not started | Nothing — **the unblocker** |
| 3 | Evaluate retrieval, calibration, answer correctness | ⬜ Not started | Items 1, 2 + [`GAPS.md`](GAPS.md) #1, #2 |
| 4 | Investigate routing; compare against hybrid | 🟡 Diagnosed, not measured | Item 2 + `GAPS.md` #3–6 |
| 5 | Ablation on confidence components; baselines | ⬜ Not started | Items 2, 3 + `GAPS.md` #1, #2 |

**One ordering constraint he could not have known**, discovered 2026-08-17: items 3 and 5 cannot produce meaningful numbers while `entity_coverage` is miscomputed ([`GAPS.md`](GAPS.md) #1) — the composite saturates near 1.0, so a reliability diagram is a spike and a weight ablation is uninterpretable. **Item 2 must come first**, then the fixes, then 3 and 5.

He should be told this. It strengthens rather than weakens the position: it is exactly the kind of thing his instruction to prioritise quality over deadlines was meant to catch.

---

## Where the contribution actually is

### What is not novel

Scoring retrieval quality and gating generation on it is well established:

- **Self-RAG** (Asai et al., ICLR 2024) trains a model to emit reflection tokens judging its own retrieval and generation.
- **Corrective RAG** (Yan et al., 2024) uses a retrieval evaluator to classify results as correct / ambiguous / incorrect and act accordingly.
- **Adaptive-RAG** (Jeong et al., NAACL 2024) routes queries to different strategies by predicted complexity.

Both Udita and her supervisor independently concluded the composite score alone will not carry a paper. That judgement is correct and should be stated plainly in the paper rather than defended against.

### What is defensible

**A rigorous failure analysis of a multi-agent legal RAG system on Indian statutory law**, with mechanism-level explanations rather than aggregate error rates.

Three things make it more than a bug report:

1. **The failures are compositional, not component-level.** In the traced arrest query ([`DATAFLOW.md`](DATAFLOW.md)), five independent mechanisms — a domain fallback, a corpus filter, an emptiness-triggered retry, a neutral default, and a refusal condition — each behaved exactly as specified, and their composition produced a confidently wrong answer about someone's liberty. Multi-agent pipelines fail at the seams, and the seams are under-studied.

2. **Confidence-signal design has a measurable failure mode.** A "neutral default" of 1.0 for a 30%-weighted signal is a plausible engineering choice that silently guarantees a high tier for the majority of queries. That generalises beyond this system.

3. **The Indian setting is genuinely different.** The 2023–24 IPC→BNS and CrPC→BNSS transitions mean two numbering schemes coexist in live use. A system can be substantively right about the law and cite section numbers from the wrong scheme — a failure mode that does not exist in US or EU legal RAG, and that the Dahl and Magesh methodologies do not measure.

### The strongest single result so far

**Six of seven sampled answers cite statutory authority that was never retrieved** ([`GAPS.md`](GAPS.md) #8) — including Acts absent from the corpus entirely. Meanwhile the citation panel displays unrelated retrieved chunks, giving the appearance of grounding.

This is the Dahl / Magesh phenomenon reproduced on a system whose internals are fully observable, with a mechanistic account of *why*. Their studies measure commercial black boxes; this can show the causal chain.

**Caveat to respect:** n=7, one category, and from a code version predating confidence scoring. Directionally strong, not yet publishable. Scaling this to the annotated set is the single highest-value experiment.

### Honest framing of the confidence score

Do not claim novelty for the composite. Claim instead: *"we instrument a deployed confidence mechanism, show it fails to discriminate on real queries, and explain why in terms any comparable design would share."* That is a contribution the literature supports and a reviewer can verify.

---

## Literature

### Indian legal NLP

| Work | Venue | Relevance |
|---|---|---|
| Malik et al., **ILDC for CJPE** — arXiv:2105.13562 | ACL-IJCNLP 2021 | The reference Indian legal NLP dataset/task. Cite for setting; task differs (judgment prediction vs retrieval QA). |
| Paul et al., **InLegalBERT** — arXiv:2209.06049 | 2022 | Domain-pretrained encoders for Indian law. **A natural baseline** — would InLegalBERT embeddings beat `text-embedding-3-small` on this corpus? |
| Paul et al., **LeSICiN** — arXiv:2112.14731 | AAAI 2022 | Statute identification from facts. Closest prior work to the routing problem; a strong comparison point for item 4. |

### Motivation — legal hallucination

| Work | Venue | Relevance |
|---|---|---|
| Dahl et al., **Large Legal Fictions** — arXiv:2401.01301 | J. Legal Analysis 2024 | Establishes legal hallucination as a measured phenomenon. |
| Magesh et al., **Hallucination-Free?** — arXiv:2405.20362 | J. Empirical Legal Studies 2025 | **The key motivating citation.** Commercial legal RAG tools hallucinate 17–33%. Directly supports "RAG is not a solved safeguard." |

### Confidence and adaptive RAG

| Work | Venue | Relevance |
|---|---|---|
| Asai et al., **Self-RAG** — arXiv:2310.11511 | ICLR 2024 | Nearest prior art on self-assessment. Establishes the idea is known. |
| Yan et al., **Corrective RAG** — arXiv:2401.15884 | 2024 | Retrieval evaluator gating generation — closest to this design. |
| Jeong et al., **Adaptive-RAG** — arXiv:2403.14403 | NAACL 2024 | Query-complexity routing. Relevant to item 4. |
| Soudani, Kanoulas & Hasibi | Findings of ACL 2025 | **Useful for framing:** reliable confidence estimation in RAG remains open. Supports positioning a negative result as a contribution. |

### Citation verification

| Work | Venue | Relevance |
|---|---|---|
| Gao et al., **ALCE** — arXiv:2305.14627 | EMNLP 2023 | **Methodologically the most important.** Provides citation precision/recall — the principled way to measure finding #8. Adopt its protocol rather than inventing one. |

### Gaps worth filling

- **Calibration methodology** — ECE, reliability diagrams, temperature scaling. Guo et al. (ICML 2017), *On Calibration of Modern Neural Networks*, is the standard reference.
- **Hybrid retrieval** — BM25 + dense fusion for item 4. Reciprocal Rank Fusion is the usual baseline.
- **Legal RAG outside the US** — check whether comparable work exists for other multilingual or recently-recodified jurisdictions.

---

## Venues

Reproduced from the 5 August email, **annotated with status as of 2026-08-17.**

| Venue | Deadline | Status today | Notes |
|---|---|---|---|
| **NLLP 2026** @ EMNLP | 11 Aug (direct) | ⛔ **passed** | 4 pages, ACL Anthology, no fee. CFP names RAG, calibration, access to justice. |
| **NLLP 2026** via ARR | 27 Aug | ⚠️ **10 days** | Only viable if results are near-ready. They are not. |
| **FIRE 2026**, ISI Kolkata | 15 Aug | ⛔ **passed** | ACM proceedings, 9 pages, in India. |
| **ICON 2026**, Gauhati | 25 Aug | ⚠️ **8 days** | ACL Anthology indexed. Very tight. |
| **JURIX 2026**, Toulouse | abstract 28 Aug, full 5 Sep | 🟡 **11 / 19 days** | Established AI & Law venue. **In-person required** — check funding. |
| **Insights from Negative Results** @ EMNLP | ~September | 🟢 **plausible** | Possibly the most natural home if framed as failure analysis. Confirm the date. |
| **ECIR 2027**, Southampton | Oct–Nov | 🟢 **comfortable** | Has a **reproducibility track** — a good fit given the emphasis on reproducible measurement. |
| **ACL Rolling Review** | 12 Oct | 🟢 **comfortable** | Submit once, choose venue after reviews. **Lowest-risk option.** |
| **CODS 2026**, ACM India, Gandhinagar | TBA (Dec) | 🟢 | Historically open to work in progress; least expensive. |

**Recommendation, consistent with the supervisor's guidance.** The August deadlines are not reachable — the blocking defects in [`GAPS.md`](GAPS.md) mean no trustworthy number exists yet, and submitting the current §8 figures would be worse than not submitting. Target **ARR on 12 October**, with **Insights from Negative Results** as a strong alternative if its date lands favourably. That leaves roughly eight weeks: enough to fix, instrument, annotate 50–100 queries, and run all five experiments properly.

Verify the two dates marked TBA / unconfirmed before committing.

---

## Paper skeleton (provisional)

Written down so it can be argued with, not because it is settled.

| Section | Content |
|---|---|
| **1 · Introduction** | Access to justice in India; RAG as apparent remedy; Magesh et al.'s 17–33%; contribution = mechanism-level failure analysis of a deployed multi-agent legal RAG system |
| **2 · Related work** | Indian legal NLP; legal hallucination; confidence-gated RAG; citation verification. State plainly that composite scoring is not novel |
| **3 · System** | The five-agent pipeline as the object of study, not the contribution |
| **4 · Evaluation setup** | Corpus (1,011 chunks, 4 statutes); annotated query set; metrics; the ALCE-derived citation-support protocol |
| **5 · Results** | Retrieval quality; calibration; routing accuracy; citation support; ablation |
| **6 · Failure analysis** | **The core.** Compositional failures; the arrest-query trace as the worked example |
| **7 · Discussion** | What generalises; the IPC/BNS numbering hazard; implications for legal RAG design |
| **8 · Limitations** | Corpus of four statutes, no case law; single embedding model; single-jurisdiction |

The arrest query traced in [`DATAFLOW.md`](DATAFLOW.md) should be **Figure 1**. It carries the entire argument in one diagram.

---

## Related documents

- [`EVALUATION_PLAN.md`](EVALUATION_PLAN.md) — the five items as runnable experiments
- [`GAPS.md`](GAPS.md) — findings, with what each blocks
- [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) — unresolved research decisions
