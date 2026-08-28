# Thirteen answers — and one thing I got wrong

**Written 2026-08-26.** Answers to the questions you asked after coming back to the project.

Each section is **plain English first**, then a **real-life comparison**, then the **technical version**. The last section is a menu with prices — nothing there happens until you say so.

| | Question |
|---|---|
| [1](#1-how-is-the-documentation-happening-is-there-a-loop) | How is the documentation happening? Is there a loop? |
| [2](#2-are-we-still-using-the-casecontext-fields) | Are we still using the CaseContext fields? |
| [3](#3-why-did-the-architecture-change-my-error) | Why did the architecture change? **← I got this wrong** |
| [4](#4-what-does-each-stages-output-type-is-the-next-stages-input-type-mean) | "Each stage's output type is the next stage's input type" |
| [5](#5-why-so-many-queries-what-is-an-evaluation-run) | Why so many queries? What is an evaluation run? |
| [6](#6-superpowers--honest-pros-and-cons) | Superpowers — honest pros and cons |
| [7](#7-auroc-0492-composite-0610-vs-raw-0663) | AUROC 0.492, composite 0.610 vs raw 0.663 |
| [8](#8-hybrid-routing-bm25-and-ablation) | Hybrid routing, BM25, and ablation |
| [9](#9-why-negative-results-are-assets) | Why negative results are assets |
| [10](#10-can-we-bypass-the-legal-expert-validation) | Can we bypass the legal-expert validation? |
| [11](#11-n33-with-overlapping-intervals-and-one-model-one-embedding) | n=33 overlapping intervals; one model, one embedding |
| [12](#12-the-measurement-discipline-point) | The "measurement discipline" point |
| [13](#13-where-does-the-languages-phase-come-in) | Where does the languages phase come in? |
| [14](#14-costs-and-the-menu) | Costs, and the menu |

---

## 1. How is the documentation happening? Is there a loop?

**Short answer: no loop.** Nothing runs on a timer. Documentation happens because four small programs fire at fixed moments and make skipping it a deliberate act rather than an accident.

These are called **hooks** — a hook is a command the tool runs automatically when a specific event happens. They live in `.claude/settings.json` inside your repo, so they travel with the project.

```
  one working session, left to right
  ────●──────────────●──────────────────●──────────────●────────▶
      │              │                  │              │
 SessionStart   UserPromptSubmit    PreToolUse       Stop
      │              │                  │              │
 reads STATE.md  appends to         blocks the two  prompts the
 + WORKLOG,      SESSION_LOG.md     forbidden       WORKLOG
 injects it      AND re-injects     commands        entry
                 your plain-
 so I start      English rule       a guardrail,
 informed                           not a doc
                 ★ fires on EVERY
                   single message
```

**Real-life comparison.** It works like a hospital ward round. Nobody schedules "documentation hour". Instead the chart is at the foot of the bed, and you physically cannot hand over a patient without writing on it. The hooks are the chart being where you can't avoid it.

### What each file is for

| File | Rule | Why |
|---|---|---|
| `WORKLOG.md` | append-only | What happened, in order. Never edited — if an old entry was wrong, a new one corrects it. Rewriting history is how you lose the record of a mistake |
| `DECISIONS.md` | append-only | Why something is the way it is. A reversed decision is *superseded*, not deleted |
| `OPEN_QUESTIONS.md` | never delete | Settled questions move to a Resolved section with the answer and date, so it is also a record of settled uncertainty |
| `STATE.md` | rewritten | The only one replaced. It answers "where are we today", and stale is worse than absent |
| `results/PHASE_*.md` | frozen | Every number with its confidence interval and the commit that produced it |
| `SESSION_LOG.md` | automatic | Written by the hook, not by me |

**Technical.** The `UserPromptSubmit` hook is the important one. Your plain-English rule failed as a `CLAUDE.md` entry, because `CLAUDE.md` is read once at session start and then competes with everything else in my context. Re-injecting it on every turn means it is always the most recent instruction I have seen. That is why it finally stuck.

---

## 2. Are we still using the CaseContext fields?

**Short answer: mostly no.** The Intake agent produces eight pieces of analysis. Only **two** change what the system does. The other six are recorded and displayed but never influence the answer.

I checked the code rather than trusting memory.

```
   INTAKE produces                          what happens to it
   ───────────────────────                  ──────────────────────────

   predicted_legal_domain  ══════════════▶  ROUTER  ═══▶  RETRIEVAL  ═══▶  ANSWER
   legal_issues            ══════════════▶  (picks corpus, boosts,
                                             rewrites the query)

   user_persona            ─ ─ ─ ─ ─ ─ ─▶  ┐
   urgency                 ─ ─ ─ ─ ─ ─ ─▶  │
   financial_status        ─ ─ ─ ─ ─ ─ ─▶  ├─ LOG + PDF display only
   complexity              ─ ─ ─ ─ ─ ─ ─▶  │  recorded, shown, never acted on
   scenario                ─ ─ ─ ─ ─ ─ ─▶  │
   missing_facts           ─ ─ ─ ─ ─ ─ ─▶  ┘

   ═══  changes the output          ─ ─ ─  dead end
```

| Field | Read at | Effect |
|---|---|---|
| `predicted_legal_domain` | `router.py:134,137` | ✅ changes retrieval |
| `legal_issues` | `router.py:142,147` | ✅ boosts + rewrites the query |
| `user_persona` | `app.py` log + PDF | ❌ no effect |
| `urgency` | `app.py` log + PDF | ❌ no effect |
| `financial_status` | `app.py` log + PDF | ❌ no effect |
| `complexity` | `app.py` log + PDF | ❌ no effect |
| `scenario` | `app.py` log + PDF | ❌ no effect |
| `missing_facts` | `app.py` log + PDF | ❌ no effect |

Verified by search: **the Answer agent never sees CaseContext at all.** Zero references in `agents/answer.py`.

**Real-life comparison.** It's like a hospital intake form that asks your occupation, your insurance status and your emergency contact — and then the doctor treats you based only on your symptoms. Collecting it isn't wrong. But claiming the treatment was personalised to your income would be false.

### Does it matter?

**You are paying for it.** The Intake agent is a separate call to the language model on every query — roughly ₹0.09 of your ₹0.46 per query, about **20% of your entire API spend**. Six-eighths of its output is decoration.

**You must not claim it in the paper.** If you write "the system adapts its answer to the user's financial situation", a reviewer who reads the code will find it does not. That kind of finding costs credibility on everything else.

**There is a good version of this.** `missing_facts` — the things the user should have told you — is genuinely useful and currently thrown away. For an access-to-justice system, *"you didn't say when this happened, and that decides which law applies"* is arguably the most valuable thing the whole pipeline could produce.

---

## 3. Why did the architecture change? (My error)

> **You are right and I was wrong.**
>
> `docs/TARGET_ARCHITECTURE.md` line 181 specifies **Stage 1.5 — Date Resolver**, running after Intake and **before** the Router. Line 262 puts the Statute Mapper at 2.5, after it.
>
> I built both **after** the Router, at 2.5 and 2.6. **I changed an agreed design without flagging it, and the change has a real cost.** That is exactly the churn you told me to stop, and I did it silently, which is worse than doing it openly.

### What the difference actually is

```
AS DESIGNED  ·  TARGET_ARCHITECTURE.md
─────────────────────────────────────────────────────────────────────
  ┌─────────┐   ┌──────────────────┐   ┌──────────┐   ┌───────────┐
  │ 1 Intake│──▶│ 1.5 Date Resolver│──▶│ 2 Router │──▶│3 Retrieval│
  └─────────┘   │   → era          │   │ can USE  │   └───────────┘
                └──────────────────┘   │ the era  │
                                       └──────────┘
  ✅ Works for EVERY query — the Router knows the era even when
     no statute is named.


AS BUILT  ·  what actually runs
─────────────────────────────────────────────────────────────────────
  ┌─────────┐   ┌──────────┐   ┌──────────────────┐   ┌──────────────┐
  │ 1 Intake│──▶│ 2 Router │──▶│ 2.5 Date Resolver│──▶│2.6 Statute   │──▶ 3 Retrieval
  └─────────┘   │ decides  │   └──────────────────┘   │    Mapper    │
                │  BLIND   │◀── ─ ─ overrides ─ ─ ─ ─ │ only fires if│
                └──────────┘                          │ a code is    │
                                                      │ NAMED        │
                                                      └──────────────┘
  ❌ Works ONLY when the query names a statute. Layman queries name
     none, so the date is computed and then discarded.
```

**Verified:** `"husband beats me since 2019"` → era resolves correctly to `BOTH_ERAS` → the Statute Mapper returns **no filter**, because there is no citation to translate.

**Real-life comparison.** Imagine a pharmacy. The *designed* version asks your age at the counter, then the pharmacist picks the right dose. The *built* version lets the pharmacist pick a dose blind, then a supervisor checks your age and corrects them — **but only if you brought a prescription**. Walk in without one and your age is noted and ignored.

### Why I drifted, honestly

I built the Statute Mapper first, because the Phase G result pointed at citations. Then I let the Date Resolver land wherever the Mapper needed it — immediately before. It was convenience, not a decision. I never re-read line 181.

### What it cost you

**This is the actual reason Phase H is only proven on queries that name a code.** It is not a limitation of the idea; it is a limitation of where I put the component. Your layman set — the whole point of the project — cannot benefit from the fix as built.

Fixing it means letting the Router's fallback use the era: *criminal domain + BNS_ERA + no statute named → filter to BNS*. About two hours. It is the missing precondition for "re-run Phase H on the layman set", which I listed as a next step without noticing it was blocked.

**Technical.** `map_query()` derives `target_corpora` from citations extracted out of the query text, plus statute names. With neither present it returns an empty list, meaning "no filter". The era is logged but never reaches `QueryPlan.target_corpora`. Moving date resolution before `router.route()` and passing the era into the domain-fallback branch closes it. The `governing_statutes()` helper already returns the right corpus list for every era including `BOTH_ERAS`, so the plumbing exists.

---

## 4. What does "each stage's output type is the next stage's input type" mean?

**Short answer.** Each step hands over a **specific, named shape of data** — not a loose bag of text. If a step produces the wrong thing, the next step cannot quietly paper over it, because it is expecting that exact shape.

```
Intake     produces  CaseContext      (8 named fields, each with a type)
Router     consumes  CaseContext
Router     produces  QueryPlan        (target_corpus, entities, decision_path…)
Retrieval  consumes  QueryPlan
Retrieval  produces  RetrievalResult
Answer     consumes  RetrievalResult
```

**Real-life comparison.** A hospital where each department hands over a **filled-in form**, not a verbal message. If Radiology writes the wrong patient number on the form, Surgery notices — the form has a box labelled "patient number" and it doesn't match the wristband. If they'd shouted it down a corridor, the error would arrive as a plausible sentence.

### Why that made the Router bug findable

The Router's job is to fill in `QueryPlan.target_corpus`. When the bug set it to `"BNS"` for every criminal query, that value sat in a labelled box, got written to the log, and showed up in my analysis as a column:

```
ipc_numbered   filter=IPC   33
bns_numbered   filter=BNS   33
```

I could look at that and immediately see the confusion matrix was rigged. Had the Router just passed modified text to the retriever, the mistake would have been invisible — nothing would have been labelled "which corpus did we decide on".

### The second part: why regex, not an LLM

**Regex** (regular expression) is a pattern for matching text — *"a number, then a space, then the word 'years', then 'ago'"*. Fixed rules, no intelligence.

| | Regex | LLM call |
|---|---|---|
| **Auditable** | "BNS because it matched `last month` at characters 34–44 and resolved that to July 2026" — checkable | "the model decided" — not checkable |
| **Reproducible** | Same answer in August and December | Not guaranteed |
| **Cost** | Free, instant | ~₹0.09 and ~2s per query |
| **Coverage** | ⚠️ Only phrasings it knows | Handles anything |

**The trade is deliberate, and it turns on which way it fails:**

```
regex MISSES a date    →  returns UNKNOWN  →  system changes nothing  →  SAFE
LLM INVENTS a date     →  returns BNS_ERA  →  system picks a statute  →  SILENTLY WRONG
```

A gap you can see beats a mistake you cannot. In a system that gives people legal information, that asymmetry is the whole argument.

**Technical.** These are Pydantic models — Python classes with declared field types, validated at construction. Passing a string where a `CaseContext` is expected raises immediately. The original `tests/test_router.py` failed on its first line for exactly this reason: it passed a raw string to `route()`. It had never actually run.

---

## 5. Why so many queries? What is an "evaluation run"?

**Short answer.** An **evaluation run** is: take a list of questions whose correct answers you already know, send every one through the system, record what happened. It is the only way to say anything true about how well it works.

**Real-life comparison.** It is a mock exam with a marking scheme. You cannot say "the student scores 70%" by watching them answer one question. And you cannot mark the paper at all unless you wrote the answer key first.

### Where the 859 queries went

| Run | Queries | What it bought you |
|---|---|---|
| Phase G — paired | 99 | The cross-statute finding |
| Phase G — layman | 120 | "Barely retrieval-augmented" — 7.5% vs 85.0% |
| Phase G — generated | 200 | The 68% ceiling under ideal conditions |
| Phase H — baseline | 99 | The "before" half of the intervention |
| Phase H — intervention | 99 | The "after" half. 0% → 100% |
| Earlier / killed / resumed runs | 242 | Interrupted runs. Some genuine waste |
| **Total** | **859** | **₹395** |

### Why not just 20 questions?

Because of how uncertainty works. Ask 5 questions, get 4 right, and the honest statement is *"somewhere between 38% and 96%"* — useless. The range only tightens as you add questions:

```
  the SAME underlying result (80% correct), measured three times

  n =   5   │        ├──────────────────────────────────┤        58 points wide
  n =  33   │                    ├────────────────┤              27 points
  n = 120   │                        ├────────┤                  13 points
            └────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
             0%           25%          50%          75%      100%

  More questions do not change the answer. They narrow the range
  you can honestly claim.
```

### Why 20 more runs would cost ₹1,500

A "full run" is one complete query set through the whole pipeline — roughly 100–200 questions at ₹0.46 each, so **₹50–90 per run**. Twenty of those is ₹1,500.

**But you almost certainly do not need twenty.** That was a ceiling, not a plan. Realistically three or four more — and the cheapest experiments cost nothing at all:

```
retrieval-only experiments  →  NO language model call  →  ~₹0.05 per run
```

Your headline finding — 97.0% vs 51.5% — cost **under one rupee**, because it never asks the model to write anything (`scripts/ablate_filter.py`). Only experiments needing a written answer are expensive.

---

## 6. Superpowers — honest pros and cons

**Superpowers** is a plugin that adds workflow skills. It is currently *enabled* on your machine, and I have deliberately *not* used it.

| Skill | Would it help you? |
|---|---|
| `test-driven-development` | ✅ Write the test before the code. Exactly the discipline that caught eight metric bugs |
| `systematic-debugging` | ✅ Forces a hypothesis before a fix. Would have caught the `ocs/SESSION_LOG.md` parser bug faster |
| `verification-before-completion` | ✅ "Evidence before assertions." Directly against overclaiming |
| `brainstorming` | 🟡 Structured requirement exploration before building |
| `subagent-driven-development` | ❌ Farms work to background agents. **Directly conflicts with your "explain before implementing" rule** |
| `using-git-worktrees` | ❌ Isolation complexity you don't need solo |

### The honest downsides

**It burns context.** Every skill description loads into my working memory at session start. In a session this long, context is the scarcest resource — it is why you had to switch accounts.

**Two of its skills actively fight your rules.** If I follow `subagent-driven-development`, work happens in background agents you never see explained. The opposite of what you've asked for fifteen times.

**Known Windows bug.** Its session-start hook can fail *silently* on Windows — appears to work while doing nothing.

**My recommendation:** the three useful skills describe disciplines I'm already applying by hand, where you can see me applying them. The plugin's value is mostly in reminding a model that isn't already doing it. Leave it enabled and keep ignoring it, or disable it to save context. Either is fine; it is not costing you correctness.

---

## 7. AUROC 0.492, composite 0.610 vs raw 0.663

**Short answer.** **AUROC** answers one question: *if I pick one good answer and one bad answer at random, how often does the score rank the good one higher?* **0.5 means a coin flip.** 1.0 means perfect.

**Real-life comparison.** A doctor claims a blood test predicts a disease. Take 100 sick people and 100 healthy people, pair them randomly, check: does the sick person score higher? If it happens 50% of the time, the test measures nothing. That is 0.5 — it does not mean the test is *broken*, it means the test is *uninformative*.

### What your numbers say

Your confidence score is three signals added with weights:

```
confidence = 0.55 × top_k_mean       (how similar the best matches were)
           + 0.15 × (1 - score_gap)  (how consistent they were)
           + 0.30 × entity_coverage  (how many asked-about things we found)
```

Can each signal tell a fully-grounded answer from an ungrounded one? Measured on 419 queries:

| Signal | AUROC | Reading |
|---|---|---|
| `entity_coverage` — **30% of the weight** | **0.492** | **Chance. Carries no information at all** |
| the full composite | 0.610 | Weakly informative |
| `score_gap` | 0.645 | Weakly informative |
| `top_k_mean` | 0.659 | Weakly informative |
| **raw max similarity** — one plain number | **0.663** | **The best of all of them** |

**Two findings, both uncomfortable, both publishable.**

**One:** a signal carrying 30% of the weight is at chance. It contributes noise dressed as evidence.

**Two — the sharper one:** the elaborate three-signal score (0.610) is *worse* than simply using the single raw similarity number it was built to improve on (0.663). The weighting is **destroying information**.

**Real-life comparison.** You build a student-ranking formula from attendance, marks and a teacher rating. Then you find marks alone predict exam results better than your formula. The formula isn't just useless — it is diluting the one signal that worked.

**Technical.** AUROC = area under the receiver operating characteristic curve, computed here as the Mann-Whitney U statistic: the proportion of positive–negative pairs correctly ordered, ties counted as 0.5. One caveat stated in the results doc: only 27 of 419 answers were fully grounded, so the positive class is small and these estimates are noisy. The *ranking* among signals is more trustworthy than any single value.

---

## 8. Hybrid routing, BM25, and ablation

### The two ways to search — you use only one

```
  query:  "punishment under Section 318(4) BNS"

  ┌────────────────────────────┐   ┌────────────────────────────┐
  │ DENSE   (what you have)    │   │ BM25    (not built)        │
  │ matches by MEANING         │   │ matches EXACT WORDS        │
  │                            │   │                            │
  │ ✅ finds paraphrases        │   │ ✅ "318" matches only 318   │
  │ ❌ "318" and "420" look     │   │ ❌ misses "cheating" when   │
  │    nearly identical to it  │   │    the text says "deceiving"│
  └────────────┬───────────────┘   └────────────┬───────────────┘
               │                                │
               └──────────────┬─────────────────┘
                              ▼
              ┌──────────────────────────────────────┐
              │ HYBRID — merge both ranked lists     │
              │ Reciprocal Rank Fusion:              │
              │ rank 1 in EITHER list scores high    │
              └──────────────────┬───────────────────┘
                                 ▼
                     one merged list → the answer
```

**Real-life comparison.** Looking for a book. **Dense** is asking a well-read librarian *"something about a boy wizard at a magic school"* — great at meaning, hopeless if you need edition number 318 specifically. **BM25** is Ctrl-F on the catalogue — perfect for "318", useless if you don't know the exact word. **Hybrid** asks both and combines their shortlists.

### Why this is your biggest gap

Your professor's item 4 said explicitly: *compare the current router against a hybrid routing strategy.* It is unbuilt.

And it is not just a checkbox. A reviewer will say:

> *"You show dense retrieval confuses IPC 420 and BNS 318(4). But exact-match search would trivially separate them. Have you shown your problem is real, or just an artefact of choosing the wrong retriever?"*

You need an answer — and **you win either way**:

| If hybrid… | Your paper says |
|---|---|
| **fixes it** | "Dense retrieval alone fails at the recodification boundary; a lexical component is *necessary*, not optional. Here is the measured gain." A constructive, useful finding |
| **does not fix it** | "The failure survives hybrid retrieval, so it is architectural rather than a retriever-choice artefact." A **much stronger** claim than you currently have |

### And "ablation"?

**Ablation** means: remove one part, measure what breaks. That is how you learn which parts were doing work.

**Real-life comparison.** A recipe with eight ingredients. Cook it eight more times, each time leaving one out, and taste. The one you can remove without noticing was never earning its place. Your `entity_coverage` at 0.492 is exactly that ingredient.

You have already done this for confidence: each of the three signals measured alone, plus raw similarity as the baseline. **Item 5 is genuinely complete.**

---

## 9. Why negative results are assets

**Short answer.** A negative result is *"we tried this properly and it did not work"*. It is only worthless if you measured badly. If you measured well, it saves everyone else the same wasted effort — and that is a real contribution.

**Real-life comparison.** A drug trial showing a treatment doesn't work is not a failed trial. It is a successful trial with a negative outcome, and it stops thousands of patients receiving something useless. What *would* be a failure is a badly run trial that shows nothing either way.

### Your three negative results

| Finding | Why it is worth publishing |
|---|---|
| A confidence signal at chance (0.492) | Three-signal confidence scores are common in RAG systems. Showing one signal is decorative is useful to everyone building them |
| Composite (0.610) worse than raw similarity (0.663) | Says *added complexity made it worse*. Rare, uncomfortable, and exactly what a field over-engineering scores needs to hear |
| Refusal gate fires 0 times in 419 | Shows abstention-by-threshold cannot work when out-of-corpus questions score *higher* than real ones |

### Why the "must not claim" list is unusual

Your results documents contain a section that says, in effect: *"we measured these three things, we do not trust the measurement, do not cite them."*

Almost no student paper does that. The usual pressure runs the other way — you have a table, the deadline is close, so it goes in with a hedge.

Three reasons it works in your favour:

- **It buys credibility for everything else.** A reviewer who sees you voluntarily discard a favourable-looking number will believe the numbers you *do* report.
- **It pre-empts the attack.** If a reviewer finds your messiness table runs backwards and you haven't flagged it, that's a rejection. If you flagged it first with the reason, it's a limitation.
- **It is the honest thing.** Which matters most, because this system gives people legal information about their own lives.

---

## 10. Can we bypass the legal-expert validation?

**Short answer: partly — and you have already bypassed most of it without realising.** But not entirely, and the remainder is worth one afternoon of someone's time.

### What you already avoided

Two of your four query sets have gold answers needing **no legal judgement whatsoever**, because of how they were built:

```
the index contains:   "Section 378. Theft.—Whoever, intending to take
                       dishonestly any movable property..."

question generated:   "What does Section 378 of the Indian Penal Code provide?"
correct answer:       IPC 378     ← certain BY CONSTRUCTION

Nobody needs to verify this. It is true because of how the question was made.
```

That covers **299 of your 518 questions**. The `paired` set is the same — both ends of every mapping were read out of the actual Act text.

### What genuinely cannot be bypassed

The layman set. When someone writes *"my sir at work has been doing things"*, deciding that this is IPC 354A rather than 509 or 506 **is a legal judgement**. I marked 68 of 120 as `needs_review` for exactly that reason.

### Four options, honestly ranked

| Option | Cost | Assessment |
|---|---|---|
| **1. Report only the certain-gold sets as headline; layman as illustration** | free | ✅ **Strongest.** Your headline finding *already* uses only certain gold. A framing change, not new work |
| **2. Ask Prof. Joshi for one law student, ~30 queries** | one afternoon | ✅ **Best value.** Turns "no expert validation" into "expert-validated subsample with agreement reported". Standard practice |
| **3. Report agreement between your own two passes** | 2 hrs | 🟡 Weak. Better than nothing, but a reviewer knows you are not a lawyer |
| **4. Drop the layman set entirely** | free | ❌ No. It is the access-to-justice claim and your professor's framing |

**Do 1 and 2 together.** Option 1 costs nothing and immediately removes the sharpest objection, because your cross-statute finding never depended on contested gold. Option 2 is a single email.

---

## 11. n=33 with overlapping intervals; one model, one embedding

### Part A — overlapping intervals

**Short answer.** You measured 33 questions and got 39.4% before, 63.6% after. That *looks* like a 24-point improvement. But with only 33 questions the honest ranges around those numbers overlap — so you cannot yet rule out that they are the same.

```
  before  39.4%   ├───────────────────────┤              [24.7 – 56.3]
  after   63.6%                ├──────────────────────┤  [46.6 – 77.8]
                               ▓▓▓▓▓▓▓▓▓▓▓▓
                               they overlap here: 46.6 – 56.3

          └────┬─────┬─────┬─────┬─────┬─────┬─────┬────┐
           0%       25%         50%         75%       100%
```

Both true values could sit inside the shaded overlap. The improvement is *likely* real but not yet *demonstrated*.

**Real-life comparison.** Two students score 39% and 64% — on a 33-question test. Is the second genuinely better, or did they get luckier on the questions that came up? With 300 questions you'd know. With 33 you're guessing.

**Important:** this does **not** apply to your headline finding. 97.0% [84.7–99.5] versus 51.5% [35.2–67.5] do **not** overlap. That one is solid. Only the Phase H answer-quality result is under-powered.

**Fix:** generate more pairs. Your recodification map has 33 verified entries; extending to ~80 would roughly halve the interval width. About a day of careful checking plus ~₹50 of runs.

### Part B — one model, one embedding

**Short answer.** Everything you have measured used **one** language model and **one** embedding model. So a reviewer can ask: is this a fact about *Indian law*, or a quirk of *these two specific models*?

**Real-life comparison.** You test one thermometer and find it reads 2° high in humidity. Is that a fact about humidity, or about that thermometer? You cannot tell until you test a second one.

The vulnerable claim is your headline. If the reason BNS retrieval underperforms is that *this particular* embedding model saw little BNS text in training, then your finding is about the model, not the law.

**The cheapest defence is genuinely cheap.** The cross-statute experiment is *retrieval only* — no written answers, no expensive calls. Re-embedding your 1,899 chunks with a second model costs about **₹1** and takes twenty minutes. If the asymmetry survives, your claim becomes much harder to attack.

**Technical.** A strong second choice is `BAAI/bge-m3` run locally — free, no API, and it removes the "provider-specific artefact" objection entirely. A domain-pretrained alternative like InLegalBERT is more interesting scientifically, but is trained on the *repealed* codes, which would itself be an interesting result. Either goes into a second Qdrant collection; nothing existing is disturbed.

---

## 12. The "measurement discipline" point

**Short answer.** Your system is ordinary. **The care you took measuring it is not.** That is the part that would impress a reviewer, and most papers in this area do not have it.

### The five things, one at a time

**1. Eight metric bugs found and fixed before reporting anything.** The tempting order is: run the experiment, get numbers, publish, fix bugs later. Every one of those eight produced a *believable* number, so they would have gone into a paper unnoticed.

**2. Every expected value worked out by hand.** This is the subtle one.

```
The WRONG way to test a metric:
    run the code, see it returns 0.6873, write  assert result == 0.6873
    → this only proves the code is DETERMINISTIC. It gives the same
      wrong answer every time, and the test agrees with it.

The RIGHT way — what your tests now do:
    top_k_mean   (0.52+0.50+0.48+0.47+0.46)/5  = 0.486
    score_gap    0.52 - 0.46                   = 0.06
    gap_penalty  min(0.06/0.3, 1.0)            = 0.2
    entity_cov   1 entity found / 1 entity     = 1.0
    0.55*0.486 + 0.15*(1-0.2) + 0.30*1.0       = 0.6873
    → worked out on paper FIRST. Now the test can catch the code.
```

**Real-life comparison.** Checking a calculator by typing 2+2 and writing down whatever it says. If it answers 5, your "test" records 5 as correct. You have to know the answer is 4 *before* you look.

**3. Two metrics publicly retired mid-analysis.** I was about to report "the fix didn't help citations", read one answer, and found the measurement was mislabelling BNS as IPC. The easy path was to report the number. Instead both metrics are marked unusable, in writing, with the reason.

**4. A "do not claim" section.** Covered in §9.

**5. 142 tests, every number traceable to a commit.** Any figure in your paper traces to the exact code version that produced it. Your evaluation runner physically refuses to start if code is unsaved — which is why it blocked five times, twice for real bugs.

### Why this is above the field

From the literature searches: several published Indian legal RAG papers report 70–90% success on **≤40 synthetic questions**, scored with **ROUGE** — a measure of word overlap with a reference answer, which cannot tell "cites the correct section" from "uses similar vocabulary" — or with an **LLM-as-judge** whose agreement with human judgement was never checked.

You have 518 questions, deterministic metrics, hand-verified expectations, confidence intervals throughout, and a published list of what you refuse to claim.

---

## 13. Where does the languages phase come in?

**Short answer.** Phase I. It is **last, optional, and droppable** — and my honest advice is to drop it for this paper.

The idea was handling questions in Hindi and other Indian languages. The access-to-justice argument is strong: the people least served by English-only legal help are exactly the people this system is for.

### Why not now

**Your corpus is English-only.** All four PDFs are English. A Hindi question would have to be translated before it could match anything — so you'd be measuring a translation step, not a legal-retrieval finding.

**It multiplies every experiment.** Every table doubles. Your intervals are already too wide at n=33.

**It dilutes a sharp paper.** You currently have one clear claim. "And also we did Hindi" makes it a survey of two half-finished things.

**Your queries are already partly code-mixed.** Several layman scenarios are Hinglish — *"ek aadmi ne mujhse paise liye saying double karke dega"*. You can report how those performed as a small observation, at zero extra cost. That gets the honesty of the point without the cost of the phase.

**Where it belongs:** the Future Work section, one paragraph — and a natural second paper once the first is out.

---

## 14. Costs, and the menu

> **New standing rule.** From now on I state the expected cost **before** running anything that touches your API key, and report the actual cost afterwards. If an estimate turns out wrong, I say so.

### Spent so far

| Item | Tokens | Cost |
|---|---|---|
| Answer agent — input | 2,401,487 | $0.90 |
| Answer agent — output | 1,435,725 | $2.69 |
| Intake agent *(estimated, not logged)* | ~815,000 | ~$0.88 |
| Embeddings | 326,559 | $0.007 |
| **Total · 859 queries** | | **$4.48 · ₹395** |

A **token** is a chunk of text slightly smaller than a word; 100 tokens ≈ 75 English words. You pay for both input and output, and **output costs 5× input**. That works out to **₹0.46 per query**.

### The menu — nothing happens until you say so

| # | Work | API cost | My time | Why |
|---|---|---|---|---|
| **A** | **Move the Date Resolver to 1.5**, as originally designed | ₹0 | ~2 hrs | Fixes *my* deviation. Unblocks the layman re-run, currently impossible |
| **B** | **Bind citations to their supporting passage** | ₹0 | ~4 hrs | Re-analyses existing logs. Brings **three dead metrics** back to life |
| **C** | **Second embedding model** (bge-m3, local, free) | ~₹1 | ~2 hrs | Kills the "artefact of one model" objection on your **headline** finding |
| **D** | **Hybrid routing + BM25 comparison** | ~₹100 | ~1 day | Prof. Joshi's item 4. Strongest reviewer objection. **You win either result** |
| **E** | **Re-run Phase H on the layman set** *(needs A first)* | ~₹110 | ~1 hr | Tests the fix on the queries the project exists for |
| **F** | **Extend the map to ~80 pairs** | ~₹50 | ~1 day | Halves your interval widths. Fixes the n=33 weakness |
| **G** | **Ingest BNSS + BSA** | ~₹1 | ~1 hr | Unblocks procedural queries, currently unanswerable by construction |
| **H** | **Re-gold CPA controls, fix messiness confound** | ₹0 | ~3 hrs | Makes two unusable tables interpretable |
| | **Everything above** | **~₹262** | **~4 days** | |

**My recommendation, in order:** **A → B → C** first. Together they cost about **₹1** and half a day, and they respectively fix my architectural error, revive three metrics, and defend your headline finding against the "one model" attack.

Then **D** (hybrid routing) as the single most valuable day of work — it closes your professor's outstanding item and pre-empts the sharpest review objection.

---

## Current state of the working tree

`core/verifier.py` is **mid-edit** from a partial start on item B, stopped on your instruction. Two new functions added (`provisions_from_chunks`, `reattribute`), one parameter added to `audit_answer`, and it is missing an `import re` that the new code needs. **Nothing is committed.** Last clean commit is `a68d8cf`.

**Waiting on you:** finish item B, or revert `core/verifier.py` to the last commit and hold.
