# Part 4 — Questions a panel could ask

Short, honest answers you can say out loud. Each one points to the evidence in
[02_ARCHITECTURE.md](02_ARCHITECTURE.md), [03_MEASUREMENT.md](03_MEASUREMENT.md)
or [../AUDIT_2026-10-10.md](../AUDIT_2026-10-10.md).

**One rule for the room:** when a question exposes a weakness, **name it before
they finish**. "Yes, and here's how I know how big it is" beats any defence.

---

## A. The problem

**1. What problem does this solve?**
Ordinary people in India can't find the section of law that covers their
situation. Statutes are free online but written for lawyers, and organised by
section number, not by situation. Since 1 July 2024 it's harder still: the old
and new criminal codes both matter, and which one applies depends on when the
events happened.

**2. Why not just use ChatGPT?**
Language models answer from memory and sometimes invent citations — a real
section number attached to the wrong law. RAG makes the model answer from
retrieved text, so citations can be checked. My results show it still answers
from memory far more than you'd hope: 0 of 120 layman answers were fully
grounded.

**3. What exactly changed on 1 July 2024?**
The IPC was replaced by the BNS, the CrPC by the BNSS, and the Evidence Act by
the BSA. Most offences carried over but were renumbered — cheating went from IPC
420 to BNS 318(4). Some changed in substance: theft, IPC 379 → BNS 303(2), adds
community service for a first theft below a small value.

**4. If the IPC is repealed, why does it still matter?**
Savings provisions — BNS s.358 and s.6 of the General Clauses Act — keep the old
law for conduct before 1 July 2024, and Article 20(1) forbids retrospective
heavier punishment. So conduct in March 2023 is still judged under the IPC.

**5. Isn't this just a renumbering lookup table?**
No. The mapping is many-to-many: one IPC section can split across several BNS
sections and vice versa. Some offences changed in substance. And one IPC section
(161) has no counterpart at all — it was repealed in 1988. A system that only
translated numbers would still get the law wrong.

**6. What is your contribution, in one sentence?**
A measured account of how and why a retrieval-augmented legal system fails after
a recodification — including that searching by meaning alone favours the
repealed code, and that answers to ordinary-language questions come from the
model's memory rather than retrieved law — plus one date-aware fix that works
within a stated scope.

---

## B. Architecture and design

**7. Walk me through the system.**
Eight stages:
1. **Intake** (LLM) triages the question.
2. **Router** (rules) picks a law book.
3. Optionally, the **Date Resolver** works out when the events happened.
4. Optionally, the **Statute Mapper** switches to the governing code.
5. **Retrieval** embeds the question, searches 1,899 passages in Qdrant, keeps
   the best, and computes confidence.
6. **Answer** (LLM) writes from those passages.
7. **Reporter** makes a PDF.
8. **Verifier** checks the answer's citations against what was retrieved.

A run logger records everything.

**8. Is this really "multi-agent"?**
Honestly, it's a sequential multi-stage pipeline. Each stage is a specialised
component with typed inputs and outputs, which is what "agent" usually means in
these systems. But none of them chooses its own next action or loops. I'd
describe it as an eight-stage pipeline, two of whose stages use a language
model.

**9. Why only two LLM stages?**
Rules can be unit-tested and traced to the exact character that triggered them;
model calls can't. If behaviour changes, I want to blame a component, not
sampling noise.

**10. Why is the Router regex, not an LLM?**
Auditability. "It chose the IPC because the string 'ipc' matched" is a sentence
you can check. "The model decided" isn't.

**11. Why not LangChain or LangGraph?**
The pipeline is a fixed sequence of a few stages, and the whole value of the
project is that every decision is logged in my own schema. A framework would sit
between me and that. It's a few hundred lines of plain Python.

**12. Why Qdrant?**
An open-source vector database that runs locally in Docker, supports payload
filters (filter by corpus), and needs no paid service.

**13. Why OpenRouter, and how do you keep results reproducible?**
My original OpenAI key stopped working. OpenRouter gives one API in front of many
providers. To stop it silently switching providers, every call pins the
provider, disallows fallbacks, and sets `require_parameters`, so an unsupported
setting fails instead of being dropped. Temperature 0, a fixed seed, and the
provider and model are logged on every call. The seed is best-effort at the
provider — I say so.

**14. Which models?**
Generation: `google/gemini-3.7-flash`. Embeddings:
`openai/text-embedding-3-small` (1,536 dimensions). Both via OpenRouter.

**15. How many API calls per question?**
Three paid calls — Intake, the embedding, and Answer — plus one local Qdrant
search. About 10 seconds per question.

**16. Why are the date components off by default?**
So the system without them stays runnable exactly as before, as a **control**.
Any improvement is then a measured difference, not a claim.

**17. Why section-bounded chunks?**
One statutory section becomes one passage, so a provision is never cut
mid-sentence and each chunk has a clear identity. Only sections over 800 words
are split further.

**18. Why does the refusal gate check Act names instead of scores?**
I measured it. An out-of-corpus question (Hindu Marriage Act, never indexed)
scored 0.519 — higher than five of six legitimate questions. Similarity can't
tell "we don't hold this law" apart from "hard question". A name check can.

---

## C. The stages

**19. What fields does Intake produce?**
`scenario`, `user_persona`, `urgency`, `financial_status`, `complexity`,
`predicted_legal_domain`, `legal_issues`, `missing_facts`, plus logging fields
(`llm_ok`, `fallback_used`, `llm_error`).

**20. What does Intake actually contribute?** ⚠ *Name this yourself.*
In all 859 recorded runs, the domain came back "General" and the issues list
came back empty, even though the call succeeded. The prompt doesn't fix the JSON
key names, and the parser accepts only two spellings, so those two fields fall
back to defaults. Scenario, persona, urgency and complexity do work, and reach
the UI and the PDF. But domain and issues never reached retrieval. That's a
known fix: specify the keys in the prompt and log the raw reply.

**21. What does the Router output?**
A `QueryPlan`: `rewritten_query`, `intent`, `target_corpus`, `target_corpora`,
`entities` (e.g. "Section 379"), `boost_terms`, `decision_path`. In the logs, it
filtered by a named Act 605 times and searched unfiltered 254 times.

**22. How does Retrieval decide what to keep?**
It takes Qdrant's top 15, moves passages that mention the asked-about section to
the front, keeps those within 0.15 of the best score (and at least 0.35), and
always keeps at least 3.

**23. Your floor is 0.35 — so nothing below it reaches the model?** ⚠
Not quite. If fewer than 3 survive, the first 3 are forced through whatever
their score. 229 passages below 0.35 reached the model across all runs. It's a
soft floor.

**24. Explain your confidence formula.**
`C = 0.55·m + 0.15·(1 − g) + 0.30·e`, where:
- `m` = mean of the 5 best scores;
- `g` = (best − 5th best) / 0.3, capped at 1;
- `e` = share of named sections found in the top passages, or 0.5 if none were
  named.

Below 0.38 is LOW, below 0.55 is MEDIUM, otherwise HIGH. The tier adds a
disclaimer to the answer prompt.

**25. Why is the no-entity value 0.5, not 1?**
At 1.0, every question that named no section got the full 0.30 for free. That
pushed exactly the layman questions — the ones with the least evidence — into
the HIGH tier. 0.5 means "unknown".

**26. What does the Verifier check?**
It extracts every provision the answer cites and checks whether each was present
in the retrieved text. Strict: a sub-section must match exactly. It logs
cited / grounded / ungrounded and the ungrounded rate.

**27. What's wrong with the Verifier?** ⚠
Two things, and they push in opposite directions:
- It compares against 200-character snippets, not full passages, which could
  inflate "ungrounded".
- Retrieved passages carry no statute name, so it matches by number only, which
  inflates "grounded".

I re-checked the headline at section level against everything the model was
sent: still 0 of 120.

**28. What does the Statute Mapper actually change?** ⚠
The **book** it searches — `target_corpora` — but not the section number it
looks for. After mapping IPC 379 → BNS 303(2), it searches the BNS but still
looks for "Section 379". That happened in 121 of 129 remapped runs. The fix
still worked; it's probably under-reported.

---

## D. Data and corpus

**29. What's in the corpus?**
Four statutes, 1,899 passages: CrPC 742 (39.1%), IPC 595 (31.3%), BNS 424
(22.3%), Consumer Protection Act 138 (7.3%). No BNSS, BSA, Constitution or case
law.

**30. Why not the BNSS?**
A scoping choice. The project is about the IPC→BNS transition, where both sides
are in the index. Questions needing the BNSS are counted as unanswerable by
construction, not scored as failures.

**31. How many test questions, and how were they built?**
518:
- **200 generated** from known sections;
- **99 paired** — 33 offences asked under the IPC number, the BNS number, and
  neither;
- **99 dated** — the same offences where the named code and the date disagree,
  plus a control;
- **120 layman** — 30 real situations, each phrased 4 ways.

The answers were fixed before any output was seen.

**32. Why 617 runs, not 518?**
The dated set was run twice — with the date components off (99) and on (98).
Plus 3 legacy questions; minus 2 deliberately dropped generated rows. So
198 + 99 + 197 + 120 + 3 = 617.

**33. Who wrote the gold labels? Are they right?** ⚠
I did — a single annotator. Three sets are certain by construction, because each
question was generated from its answer. The layman set needed judgement, and 68
of its 120 rows are flagged `needs_review`. Validation of about 30 by a legally
trained reader is the top next step. I also found template flaws, e.g. 9
offences ask for the punishment but list the definition section. I re-ran the
key results without those rows and they hold.

**34. Read me question D0040.** ⚠
*"What is the punishment for theft - definition under Section 378 of the Indian
Penal Code? This happened last month."* Gold: BNS 303(1), the *definition*. The
punishment is 303(2). It's a template bug. Removing all 14 such conflict rows
raises the intervention result from 60.0% to 66.7%.

---

## E. Measurement and statistics

**35. What is AUROC, in one sentence?**
The probability that a randomly chosen correct case gets a higher score than a
randomly chosen incorrect one. 0.5 is a coin toss.

**36. What is a Wilson interval, and why use it?**
A 95% confidence interval for a proportion. Unlike the textbook formula, it
doesn't claim certainty at 0% or 100% — at 33/33 the textbook gives ±0.

**37. Why a cluster bootstrap?**
Four phrasings of one situation aren't four independent data points. Resampling
whole situations gives honest, wider intervals.

**38. What are your three definitions of "correct"?**
- Retrieved: the gold section is in the top 15.
- Cited: the answer cites it.
- Grounded: every citation was in the retrieved text.

They measure the search, the answer, and whether the answer used the evidence.

**39. What is ECE?**
Expected Calibration Error: group answers by stated confidence, compare each
group's confidence with how often it was actually right, and average the gaps.

**40. What is the reachability ceiling?**
The best score any retriever could get, given which gold sections exist as
labels in the index. Sub-sections like "318(4)" can't be matched because the
index stores "318". Pooled it's 85.7%; for BNS-named paired questions only 33.3%.

**41. How do you know your metrics are right?**
- One shared metric library, so nothing has two implementations.
- Known-answer tests, with answers worked out by hand.
- A second, independent route for each experiment that halts on disagreement.
- Every number in every document is pulled from a results file by a filter that
  must match exactly one row.

That machinery caught a bug in my own code that silently zeroed every retrieval
metric.

**42. How many tests?** 237, all passing.

---

## F. Results

**43. What's your main finding?**
Searching by meaning alone strongly favours the repealed code:

| Question names… | Right book |
|---|---|
| the IPC | 97.0% [84.7, 99.5] |
| the BNS | 51.5% [35.2, 67.5] |

33 questions each, filter off.

**44. Does your deployed system fail that way?** ⚠ *Say this before they ask.*
Not when the user names the code — the Router then sends it to the right book
33 out of 33 times, each way. It fails when nothing is named, and that's exactly
the ordinary-person case.

**45. Doesn't adding keyword search fix it?**
No. Keyword search reverses it: 0.0% on IPC-named, 97.0% on BNS-named. Fusing
the two gives 62.1% pooled — between the two, not better than both. The two
methods have opposite biases.

**46. Why does keyword search fail on the IPC?**
The BNS uses the word "sanhita" — in 30 passages, all BNS — a perfect signpost.
The word "penal" is in 110 passages, but 82 are CrPC and only 23 IPC, because
the procedure code cites the Penal Code constantly. The IPC barely names itself.

**47. And why does meaning search favour the IPC?** ⚠
That's open. Self-naming explains the keyword result, but not the meaning
result — the BNS actually names itself more (7.1%) than the IPC (3.9%). The
experiment to test it is planned: add each statute's name to its passages and
re-measure.

**48. How do ordinary-language questions do?**
The right section reaches the retrieved passages 15.0% of the time — 7.5% after
the threshold. Yet answers cite the right section 66.7% of the time, and 0 of
120 answers had every citation in the retrieved text. The model was answering
from memory.

**49. Why does the CrPC dominate layman retrieval?**
With no code named there's no filter. The CrPC is the biggest book (39% of the
index) and mentions offences constantly while describing procedure. It makes up
58.2% of retrieved layman passages, rising to 70.2% after the threshold — 1.80×
its share of the index.

**50. Does the confidence score work?**
No:
- It separates good from bad retrieval at AUROC 0.663, worse than using the
  single best match score alone (0.784). That holds under all three definitions
  of correct.
- One ingredient, as deployed, scores 0.270 — below a coin toss.
- Flipping its sign gives 0.721 — still worse than the single score.
- No threshold achieves 10% error at the retrieval level.

**51. Was the gap term a bug?** ⚠
A design hypothesis that turned out wrong. It assumed a small gap between the
best and fifth-best scores meant "consistent relevance". The data say a large
gap means a clear, correct winner. The code did what was intended; the intention
was refuted.

**52. Your title says "Calibrated", but your finding is that it isn't.**
The title names what was designed; the work measures whether it holds. It
doesn't: ECE 0.241. That's the finding.

**53. Did your date fix work?**
On the 66 questions where the named code and the date disagree:

| Date components | Correct provision retrieved |
|---|---|
| off | 0 times |
| on | 39 of 65 (60.0%) |

On 33 control questions where they agree, nothing changed (87.9% before and
after). So it follows the date rule rather than favouring one code.

**54. Why only 34.4% when the question names the IPC?** ⚠
22 of those 33 gold labels are sub-sections like 103(1), which the index can't
match exactly. On reachable questions it's 39 of 44 — 88.6%.

**55. Did it improve the final answers?**
I measured retrieval, not answer quality, for this result. The August analysis
found citation attribution unreliable on these questions, because answers
mention both codes. So I don't claim an answer-level improvement.

**56. What was the "0.293 → 0.694" in your report?** ⚠
That pooled all three variants, including the control, which was already right.
The conflict-only figure is 0 → 39 of 65. The report's wording was wrong; the
abstract is correct.

---

## G. Weaknesses and limitations

**57. What's the biggest weakness?**
A single annotator for the gold labels, and small samples (33 per arm, one run
per condition). Independent legal validation is the first next step.

**58. Is your result specific to one embedding model?**
Possibly. Everything uses `text-embedding-3-small`. Re-running with a second,
locally hosted model is planned.

**59. Can someone reproduce your results?**
The code, test sets, results files and metric library are public. The raw run
logs aren't — `runs/` is git-ignored — so re-deriving from raw logs needs those
files. `requirements.txt` is also missing the analysis packages (numpy, pandas,
scipy, matplotlib, openpyxl, rank-bm25). I know, and I'm fixing it.

**60. What would you do differently?**
- Log the raw LLM reply in Intake.
- Have the Mapper rewrite the section number as well as the book.
- Tell the HIGH-tier prompt to cite only retrieved text.
- Get gold labels reviewed before running.
- Build sub-section-aware chunks, so labels like 318(4) are reachable.

**61. Any bugs a user could hit today?** ⚠
Yes — in date handling:
- "on 15/08/2024" or just "in 2024" is read as before the cutover;
- "Rs 2000" is read as a year;
- "under BNS 2023" can rewrite a correct BNS citation to the IPC.

None appears in my test questions, so no reported number is affected. They're
listed fixes.

**62. Is it multilingual?**
No. A language-handling stage was designed and deliberately deferred. The corpus
is English-only, so a Hindi question would have to be translated first, and I'd
be measuring the translator rather than legal retrieval. Three of the 30 layman
situations are written in code-mixed Hinglish — Hindi words in Roman script —
so 12 of the 120 layman questions (`eval/scenarios.py`). Reporting those
separately is the nearest next step.

---

## H. Safety and ethics

**63. Could this harm someone?**
Yes. A wrong section number goes onto a police complaint. That's why the
measurement came before deployment: such a system shouldn't be used until its
failure modes are known. The answer always recommends a lawyer at lower
confidence, and the refusal gate exists — though it never fired on the test set.

**64. Does it ever refuse?**
It can refuse when:
- nothing is retrieved;
- every Act named is outside the index;
- the best score is below 0.25.

It refused 0 times in 859 runs. Out-of-corpus questions mostly name no Act, so
the name gate doesn't engage.

---

## I. Future work

**65. What next?**
1. Independent validation of about 30 gold labels.
2. The statute-metadata ablation — does adding each statute's name to its
   passages fix meaning search?
3. A second embedding model.
4. Fixing the Intake parsing and the Mapper's section rewrite.
5. Submission to ECIR 2027's short-paper or resource track.

---

## J. About the work

**66. You did this alone?**
Yes. Design, build, evaluation design, and analysis. I used AI coding
assistance, and I'm open about it. The design decisions are mine; every number is
reproducible from a script; and the verification machinery exists precisely so
that nothing — mine or a tool's — is taken on trust.

**67. What did you learn?**
That a system which *sounds* right can be measurably wrong in ways you only see
by instrumenting every stage. The answers looked fine; the logs showed they came
from memory.
