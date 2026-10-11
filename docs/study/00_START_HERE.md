# Study guide — start here

This folder explains the whole project from first principles: the ideas, the
system, how it was measured, and the questions an examiner is likely to ask.
It was written on 11 October 2026 against the code on branch `metrics/sept-01`,
and every number in it comes from a file in `results/` or from the run logs.

## Read in this order

| # | File | What it gives you | Time |
|---|---|---|---|
| 1 | [01_FUNDAMENTALS.md](01_FUNDAMENTALS.md) | Every idea the project rests on, explained twice — once like you're five, once technically. The law, APIs, language models, embeddings, vector search, RAG, BM25, agents | 60 min |
| 2 | [02_ARCHITECTURE.md](02_ARCHITECTURE.md) | The system itself: every stage, its input and output fields, the API calls, why it was built that way, what was added later and why, a real query traced end to end, and the file structure | 75 min |
| 3 | [03_MEASUREMENT.md](03_MEASUREMENT.md) | How it was tested: the answer key, the statistics, every experiment, every result, and what each result does *not* say | 75 min |
| 4 | [04_GRILLING_QA.md](04_GRILLING_QA.md) | About 60 questions a panel could ask, with short, honest answers and where the evidence lives | 45 min |

Supporting material:

- [`../AUDIT_2026-10-10.md`](../AUDIT_2026-10-10.md) — the pre-presentation audit: what is right, what is wrong, and where.
- [`../../results/RESULTS.md`](../../results/RESULTS.md) — every measurement, generated from the CSVs.

## If you only have ten minutes

1. **The problem.** India replaced its criminal codes on 1 July 2024. The old
   IPC and the new BNS are both still relevant, and which one applies depends on
   *when* something happened. Ordinary people don't know which code they need,
   or that a second code exists.
2. **What was built.** A pipeline of stages: understand the question, choose
   which law book to search, search it by meaning, write an answer from what was
   found, check the answer's citations, and save a record of everything.
3. **What was found.**
   - Searching by meaning alone strongly favours the *repealed* code (97.0% vs 51.5%).
   - The deployed router fixes this, but only when the user *names* the code.
   - Ordinary-language questions — the people the system exists for — get the
     right section in only 15.0% of searches.
   - **Not one** of the 120 ordinary-language answers had all its citations
     backed by what was retrieved.
   - The confidence score does worse than one raw number it already computes.
   - Two date-aware components lift accuracy on date-conflict questions from
     0 out of 66 to 39 out of 65.
4. **The contribution.** Not a better legal chatbot. A measured account of how
   and why this kind of system fails after a recodification, and one fix that
   works within a stated scope.

## Using these files with Claude

These files are plain Markdown on GitHub. Point Claude at the **branch**, not
just the repository. The default branch (`main`) is older than this guide:

```
https://github.com/uditauniyal/legal-mvp/tree/metrics/sept-01
```

Good prompts to start with:

- "Read `docs/study/01_FUNDAMENTALS.md` and quiz me on embeddings and cosine similarity."
- "Using `docs/study/02_ARCHITECTURE.md`, explain the Retrieval stage's input and output fields, then check that I can repeat them."
- "Act as a hostile examiner. Use `docs/study/04_GRILLING_QA.md` and `docs/AUDIT_2026-10-10.md` to ask me ten hard questions."
