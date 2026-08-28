# Where your paper stands, and the plan ahead

**Written 2026-08-26.** Two things in one document:

1. **An honest scorecard** — for every part of your work, who has already published something similar, what they found, and how yours compares.
2. **The plan** — phases A to G, with real costs.

Plain language throughout. Every claim about other papers comes from a search I ran today, with the arXiv number so you can check it.

---

# Part 1 — Your paper in one page

Someone types a legal problem in their own words. Your program searches four Indian law books and writes an answer quoting sections.

On 1 July 2024 India replaced its main criminal law book. The old one (IPC) was swapped for a new one (BNS). Same crimes, different section numbers. **Which one is correct depends on when the incident happened.**

You measured what your system actually does. Three things came out.

**Finding 1 — it prefers the dead law.** Ask about the new book by name, and the system hands back the old one about half the time. Ask about the old book and it works almost perfectly. The bias runs one way.

**Finding 2 — for ordinary people, it barely uses your law books at all.** It names the right section about 9 times in 10, while actually finding it in your books about 1.5 times in 10. The answers come from the language model's own memory.

**Finding 3 — fixing the search did not fix the answer.** Your intervention took search accuracy from 0% to 100%. The answers improved by about 20 points and still fail a third of the time.

---

# Part 2 — Your question about layman queries

> *"How can I centre my paper around recodification if we are not considering layman queries?"*

**You are right. And I found the answer today, in logs you already paid for.**

## The tension you spotted was real

Finding 1 — the 97% vs 51% result — only holds when the question **names a law book**. Ordinary people never do. *"My husband beats me"* names nothing.

So the obvious attack on your paper was: *"your failure needs someone to name a code. Your users don't. Does your finding matter to them?"*

## The answer: it matters, by a completely different mechanism

I measured what your system retrieves for the 120 layman questions:

| Law book | Passages pulled | Share |
|---|---|---|
| **CrPC** — procedure, repealed 2024 | 428 | **70.4%** |
| IPC — penal, repealed 2024 | 91 | 15.0% |
| **BNS** — penal, in force today** | 46 | **7.6%** |
| CPA — consumer | 43 | 7.1% |

Two-thirds of layman questions come back dominated by the **CrPC** — the procedure book. Not the offence book. Not the book that answers *"what crime is this?"*

**Why?** Because the CrPC is the biggest book in your index — 39% of everything you loaded. With no filter, the search returns the biggest book by sheer weight of numbers.

And when the answers do name a penal provision, they name the **repealed IPC twice as often as the current BNS** (29.3% vs 14.6%).

**The date condition changes almost none of it** — 70% CrPC without a date, still 63% with one.

## So this is your layman-centred claim

> An access-to-justice system, asked an undated question in ordinary words, returns procedure it was not asked for, and names repealed law twice as often as law in force.

That is not "cross-statute confusion". It is a **silent default to dead law caused by corpus composition**. It is a different, simpler, and arguably more damning mechanism — and it is entirely about laypeople.

**My recommendation: make this the headline and demote the named-code result to supporting evidence.** The named-code experiment then explains *why* the machinery can't recover: even when told which book, dense search only gets it right half the time.

**Layman queries are not a side set. They are the paper.** You were right to push on this.

---

# Part 3 — Honest scorecard: what already exists

I searched arXiv across every area your paper touches. Here is what I found, area by area.

## 3.1 The recodification angle

**Searched:** `"Bharatiya Nyaya Sanhita" OR "recodification" OR (statute AND temporal AND retrieval)`

**Found: 3 papers. None studies the IPC→BNS transition as a retrieval problem.**

| Paper | What it does | Overlap with you |
|---|---|---|
| **Ovcharov**, *Temporal Decay of Co-Citation Predictability* (2605.17639) | Ukrainian statute retrieval, 20 years, 396M citations. Shows retrieval signal decays over time, worse after the 2017 judicial reform | ⚠️ **Nearest neighbour.** But his is *gradual decay over 20 years*; yours is *a single overnight switch with two books coexisting*. Different problem. **Must cite** |
| **Legal Assist AI** (2505.22003) | Indian legal RAG, corpus *includes* BNS and BNSS, scores 60.08% on the bar exam | Has both books in the corpus and **never studies the transition**. Cite as evidence the field has the data and hasn't asked the question |
| **Falkor-IRAC** (2605.14665) | Knowledge-graph legal reasoning, Indian judgments | Names *"outdated statute citations"* as a persistent failure mode — **but only names it, never measures it.** Says "evaluation against vector-only RAG baselines is left for future work" |

**Verdict: 🟢 Genuinely novel.** Nobody has measured this.

## 3.2 Laypeople asking legal questions

**This is where you have real competition, and you need to know it.**

| Paper | What it does | Why it matters to you |
|---|---|---|
| **ILSIC** (2602.00881, Findings of EACL 2026, IIT Kharagpur) | **Laypeople queries → Indian statutes.** 500+ statutes, 836 test queries. Finds models trained on court judgments fail on laypeople queries | 🔴 **Your closest competitor.** They own "laypeople + Indian statute identification". **But their corpus is IPC and CrPC — the repealed books. They never mention the BNS.** |
| **LegalQA** (2409.07713) | Access-to-justice QA, expert-written answers with citations | US/Canada. Establishes the genre |
| **Mina** (2511.08605) | Bangladesh legal assistant, multilingual, access to justice | Shows the framing is publishable |
| **bBSARD** (2412.07462) | Belgian statute retrieval, French + Dutch | **Critical finding for you: "BM25 remains a competitive baseline compared to many zero-shot dense models."** Direct support for hybrid search |

**Verdict: 🟡 Not novel alone.** ILSIC got there first on laypeople + Indian statutes.

**But your combination is:** laypeople **×** recodification. ILSIC has laypeople but works entirely in the repealed books. You have both — and you can point out that a 2026 benchmark for laypeople was built on law that was repealed in 2024. **That is a pointed and defensible observation.**

## 3.3 Your citation-grounding findings

| Paper | Finding | Yours vs theirs |
|---|---|---|
| **Das et al.** (2608.14210, Aug 2026) | 8 legal RAG systems, GDPR + French law. Hallucination "under 10% for the best, nearly half in the worst" | ⚠️ **Not directly comparable.** They count *claims*; you count *citations*. Do NOT write "83.8% vs their 50%" — a reviewer will catch it |
| **Reuter et al.** (2510.06999, NLLP 2025) | Names **DRM** — retrieving from entirely the wrong source document. Fixes it with summary-augmented chunking | 🟢 **Your best framing hook.** Your failure is a *temporal instance of DRM*: the two "different documents" are the same law at two points in time |
| **HalluGraph** (2512.01659) | Graph-based hallucination detection for legal RAG | Different method, same concern |

**Verdict: 🟡 The phenomenon is known. Your specific measurement is not.**

## 3.4 Your confidence-score findings

**This is where I have to be blunt with you.**

| Paper | Finding |
|---|---|
| **Soudani et al.** (2505.07459), *Why Uncertainty Estimation Methods Fall Short in RAG* | "Current uncertainty methods **cannot reliably assess correctness** in the RAG setting." Proposes five axioms; **no existing method satisfies all** |
| **Chifu et al.** (2504.01101), *Uncovering the Limitations of Query Performance Prediction* | Confidence signals "**do not generalise**" across collections. "Selective query processing offers only **marginal gains**" |
| **NOVA** (2601.11004) | LLMs are poorly calibrated in RAG, "**especially when noisy contexts are retrieved**" |

**Your three signals — top-k mean, score gap, entity coverage — are a re-derivation of Query Performance Prediction (QPP), a field that has existed in information retrieval since the early 2000s.** And that field has already published that these signals don't generalise.

**Verdict: 🔴 Not novel as a phenomenon.** Do not present "our confidence score doesn't work" as a discovery.

**What IS still yours, and worth reporting:**

- The **specific, concrete result** that a hand-weighted three-signal composite (AUROC 0.610) performs **worse than its own single best input** (0.663). That is a sharp, quotable instance of a general claim.
- One signal sitting at **exactly chance (0.492)** while carrying **30% of the weight**.
- It satisfies your professor's item 5 completely.

**Frame it as: "we confirm, in the Indian legal domain, what Soudani et al. and Chifu et al. found in general IR — and we add a concrete case where the composite is worse than its input."** That is honest, citable, and still a contribution.

## 3.5 Your refusal-gate finding

| Paper | Finding |
|---|---|
| **GRAB-RAG** (2608.22228, Aug 2026) | Prompt-based abstention "**fails under misleading context**". Models answer 41.6% of misleading questions even when told to abstain |
| **Energy-based abstention** (2509.04482) | Healthcare. Energy scoring beats probability-based confidence |
| **ERA** (2604.20854) | Scalar confidence "fails to distinguish" uncertainty types |

**Verdict: 🟡 Known problem, novel mechanism.**

Your specific result is unusual and worth reporting: **out-of-corpus questions score HIGHER than in-corpus ones.** The highest out-of-corpus score (0.519, Hindu Marriage Act) beat five of six legitimate queries, the lowest being 0.278. **The distributions are inverted, not just overlapping.** I have not seen that reported elsewhere. It is a clean demonstration of *why* threshold-based abstention cannot work here.

## 3.6 Your "answers come from memory" finding

| Paper | Term they use |
|---|---|
| **Chen et al.** (2605.14473) | **"context compliance"** — *did the model follow retrieved evidence, rely on its parametric prior, or produce a post-hoc rationale?* They call it an open observability problem |
| **RADIANT** (2507.02949) | "RAG-ability", "Entity-Context Divergence" |
| **Micro-Act**, **CARE**, **SHIFT** | All tackle "knowledge conflict" / "context-memory conflict" |

**Verdict: 🟢 Your Phase H is a rare natural experiment.**

These papers all *study* the problem. **Your Phase H accidentally ran the cleanest possible experiment on it:** you changed retrieval from 0% correct to 100% correct and measured how much the answer followed. Answer: about 20 points, and it still fails a third of the time.

That is a causal measurement of context compliance in a real domain. **Lead with this framing** — it lifts your Phase H from "our fix half-worked" to "we provide a controlled measurement of a problem the field has named but not measured."

---

# Part 4 — So what is actually novel?

| Element | Novel? | Honest assessment |
|---|---|---|
| IPC→BNS as a retrieval problem | 🟢 **Yes** | Zero prior work found |
| Corpus-composition default to dead law (70.4% CrPC) | 🟢 **Yes** | New today. Nobody reports this mechanism |
| Naming a code helps for the old book, not the new (97% vs 51.5%) | 🟢 **Yes** | Asymmetric and directional. Unreported |
| Routing filter *conceals* the failure it prevents | 🟢 **Yes** | Methodological, and reviewers respect this kind of self-scrutiny |
| Phase H as a context-compliance experiment | 🟢 **Yes** | Rare controlled measurement |
| The verified IPC↔BNS mapping table | 🟢 **Yes** | A citable data artifact |
| Laypeople + Indian statutes | 🟡 Partly | ILSIC owns this. Your angle is laypeople × recodification |
| Legal RAG hallucination | 🔴 No | Well covered. Cite Das et al. |
| Confidence signals don't work | 🔴 No | QPP field said this years ago. Cite Soudani, Chifu |
| Threshold abstention fails | 🟡 Partly | Known — but your *inverted distributions* are a fresh demonstration |

## How robust is it?

**Strong:**
- 518 questions across four sets — 299 with gold that needs no legal judgement
- Confidence intervals on everything
- Deterministic metrics, no LLM judge
- A published "must not claim" list
- Every number traceable to a code commit
- 142 automated tests

**Weak:**
- One language model, one embedding model
- No legal-expert validation on the layman set
- n=33 per cell in Phase H
- BNSS and BSA not loaded
- No BM25 / hybrid comparison
- **One published number is currently wrong** (7.5% should be 15.0%)

---

# Part 5 — The plan

Seven phases. **The important discovery: most of this is nearly free**, because the experiments that matter are *retrieval-only* — they don't ask the model to write anything, and writing is what costs money.

## Phase A · Fix the counting bug — ₹0, half a day

**What.** My analysis identified a retrieved passage by reading the first 160 characters of its text and looking for "Section 190." Passages starting mid-provision have no number there and were counted as failures. The `section_number` field was in your database the whole time.

**Why first.** It already halved one published number (7.5% → 15.0%). Every retrieval number in Phase G and Phase H uses the same broken counting.

**Output.** Corrected `PHASE_G.md` and `PHASE_H.md`.

**Nothing else can be trusted until this is done.**

## Phase B · Build the layman story — ₹0, 1 day

**What.** Turn today's 70.4% CrPC finding into proper tables: corpus dominance by date condition, retrieved-vs-cited by law book, the repealed-vs-current citation ratio.

**Why.** This becomes your headline, and it is entirely free — the data is already in your logs.

**Output.** A new results section, and a reframed paper.

## Phase C · Hybrid search comparison — ~₹2, 1 day

**What.** Build BM25 (exact word matching) alongside your existing meaning-based search, merge the two ranked lists, and compare all three on the same questions.

**I priced this wrong before.** I said ₹100. Comparing *which passages come back* needs no written answers — so it is **retrieval-only, about ₹2**.

**Why.** It is your professor's outstanding item 4. It is the sharpest reviewer objection. And bBSARD found BM25 competitive with dense models for exactly this task, so a reviewer *will* ask.

**You win either way:** if hybrid fixes it, you show a lexical component is necessary; if it doesn't, your failure is architectural — a stronger claim.

## Phase D · Second embedding model — ₹0, half a day

**What.** Re-embed your 1,899 passages with `bge-m3`, a free model that runs on your own machine, into a second collection. Re-run the headline experiment.

**Why.** Kills the objection *"is this a fact about Indian law, or about one embedding model?"*

**Cost: zero** — it runs locally, no API.

## Phase E · Fix the four unbuilt design decisions — ₹0, 1 day

Four things we agreed and I did not build:

| # | Decision | What it means |
|---|---|---|
| 1 | Date unknown → **search both books and say so** | Currently the system silently picks one. Legally wrong |
| 3 | Statute mapper **always runs** | Currently only when a code is named |
| 5 | `missing_facts` **functional** | Ask the user for what they left out — starting with the date |
| — | Date Resolver at stage 1.5 | Where we agreed it goes |

**Honest note:** I tested this today. It will **not** improve accuracy — 3 of 120 questions changed. Build it for legal correctness and because we agreed it, not for the numbers.

## Phase F · Full re-run — ~₹150, 1 day ⚠️ needs your key limit raised

**What.** Run the layman and paired sets through the fixed system with answers generated, so the end-to-end effect can be measured.

**This is the only phase that costs real money**, because it generates written answers.

**Blocked:** your key has ~₹32 left against its own cap. Raising the cap in OpenRouter settings unblocks it — you have ₹2,700 sitting on the account.

## Phase G · Write — ₹0, 1 week

Structure, with the reframing:

1. **Intro** — access to justice + the 2024 recodification
2. **Related work** — Ovcharov, Reuter (DRM), ILSIC, Das et al., Soudani, Chifu, bBSARD
3. **System** — one paragraph. Never the contribution
4. **The layman finding** — 70.4% CrPC, repealed law 2:1. **Your headline**
5. **The named-code experiment** — why the machinery can't recover
6. **The methodological catch** — routing concealed the failure
7. **Context compliance** — Phase H as a controlled measurement
8. **Negative results** — confidence, abstention, with proper citations
9. **Limitations + Ethics** — mandatory for this venue class

---

# Part 6 — Money

## Where you stand

| | |
|---|---|
| Account balance | ~$30.59 ≈ ₹2,700 |
| **This key's remaining cap** | **~$0.36 ≈ ₹32** |
| Spent on this key all-time | ~$19.64 ≈ ₹1,728 |

## What the plan costs

| Phase | API cost | Time | Fits in ₹32? |
|---|---|---|---|
| A · Fix counting | **₹0** | half day | ✅ |
| B · Layman story | **₹0** | 1 day | ✅ |
| C · Hybrid search | **~₹2** | 1 day | ✅ |
| D · Second embedding | **₹0** | half day | ✅ |
| E · Architecture fixes | **₹0** | 1 day | ✅ |
| F · Full re-run | **~₹150** | 1 day | ❌ needs cap raised |
| G · Write | **₹0** | 1 week | ✅ |
| **Total** | **~₹152** | **~5 days + writing** | |

**Phases A through E — everything that changes your paper — cost about ₹2 in total.** Only the final confirmation run needs money.

---

# What I need from you

**1. Do you approve this plan?** Especially the reframing: layman corpus-dominance becomes the headline, named-code becomes supporting evidence.

**2. `core/verifier.py` is half-edited** from a fix I started and you stopped. Finish it, or undo it?

**3. Raise your key's cap** when convenient — not needed until Phase F.

Once you approve, I run A → B → C → D → E in order, reporting after each, and stop before F to confirm the spend.
