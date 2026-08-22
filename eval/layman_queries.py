#!/usr/bin/env python3
"""Layman queries -- lived situations, not legal vocabulary, in four date conditions.

WHY THIS SET IS THE POINT OF THE PROJECT
    The system exists for people who do not know which law applies. Someone
    whose landlord kept their deposit does not type "Section 420 IPC". They
    type what happened to them.

    eval/generate_from_corpus.py measures the retrieval machinery precisely,
    but it phrases everything the way a statute does. It calibrates the
    instrument. It does not test the claim. THIS set tests the claim.

THE DATE DIMENSION, AND THE BUG THAT USED TO LIVE HERE
    Only an event date decides whether the IPC or the BNS governs. Real people
    rarely state one -- of 58 hand-written queries, exactly one contained a
    usable date. So each scenario appears in four date conditions.

    An earlier version of this file appended the date suffix but copied the
    gold label across unchanged. The result: 23 of 24 rows saying "This
    happened last month" -- where the BNS governs -- still carried IPC gold.
    A system citing CURRENT law was scored WRONG and a system citing REPEALED
    law was scored RIGHT. The experiment ran backwards.

    Fixed by translating gold through core/recodification.py per variant.

THE FOUR CONDITIONS

        no_date   ""                             -> UNKNOWN
        ipc_era   "This happened in March 2023." -> IPC_ERA
        bns_era   "This happened last month."    -> BNS_ERA
        vague     "a while back..."              -> UNKNOWN

WHAT COUNTS AS CORRECT WHEN THE DATE IS UNKNOWN
    There is no single right citation for an undated situation, so both eras'
    provisions are accepted (`gold_mode = "either_era"`). Scoring an undated
    query against one era would be scoring it against a coin flip.

    The genuinely better behaviour is to ASK for the date. Nothing in the
    current pipeline can do that -- the Date Resolver is Phase H -- so this
    run is deliberately the "before" half of that comparison.

WHY CPA SCENARIOS STILL GET ALL FOUR VARIANTS
    The Consumer Protection Act 2019 was untouched by the recodification, so
    its gold is identical in all four conditions. That makes it a CONTROL: if
    accuracy moves across date conditions for CPA scenarios, the date suffix
    is doing something other than what we think, and the IPC/BNS result is
    confounded. Marked `control_unchanged_statute`.

WHY SOME ROWS ARE MARKED UNANSWERABLE
    The corpus holds IPC, BNS, CrPC and CPA. It does NOT hold the BNSS. So a
    procedural scenario in the BNS era has gold (BNSS 100) that no retriever
    over this index can reach. Those rows are flagged
    `answerable_from_corpus = False` and are a refusal test, not a scoring
    target. Hiding them would inflate every headline number.

GOLD LABELS
    `expected_sections` is what the situation is chiefly about; `also_relevant`
    lists provisions a competent answer should raise. Scenarios where the right
    section is genuinely arguable carry gold_status "needs_review" and should
    not be counted until a human with legal training has checked them.

USAGE
    python eval/layman_queries.py
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "layman_queryset.jsonl"

from core.recodification import (  # noqa: E402
    CORPORA_IN_INDEX, UNCHANGED, answerable, for_regime, note_for, statute_of,
)
from eval.scenarios import SCENARIOS  # noqa: E402

# (name, text appended to the situation, regime it establishes, why)
DATE_VARIANTS = [
    ("no_date", "", "UNKNOWN",
     "how people actually ask -- no date, so the governing code is undeterminable"),
    ("ipc_era", " This happened in March 2023.", "IPC_ERA",
     "before 1 July 2024, so the IPC/CrPC governs"),
    ("bns_era", " This happened last month.", "BNS_ERA",
     "on or after 1 July 2024, so the BNS/BNSS governs"),
    ("vague", " This happened a while back, I do not remember exactly when.", "UNKNOWN",
     "a time reference that resolves nothing -- still undeterminable"),
]


def corpora_of(refs: list[str]) -> list[str]:
    """Distinct statutes named in a gold list, in first-seen order."""
    seen: list[str] = []
    for r in refs:
        s = statute_of(r)
        if s not in seen:
            seen.append(s)
    return seen


def build() -> list[dict]:
    rows: list[dict] = []
    n = 0
    for s_i, scenario in enumerate(SCENARIOS, 1):
        text, _corpus, primary, secondary, topic, review, messiness = scenario
        pair_id = "L%03d" % s_i
        control = all(statute_of(r) in UNCHANGED for r in primary)

        for variant, suffix, regime, why in DATE_VARIANTS:
            n += 1
            gold = for_regime(primary, regime)
            also = for_regime(secondary, regime) if secondary else []

            # A provision with no counterpart (IPC 161, repealed in 1988)
            # legitimately disappears in the BNS era. Record it rather than
            # letting the list quietly shrink.
            dropped = [r for r in secondary
                       if statute_of(r) not in UNCHANGED and not for_regime([r], regime)]

            corp = corpora_of(gold)
            notes = ["%s: %s" % (r, note_for(r)) for r in primary if note_for(r)]

            rows.append({
                "query_id": "L%04d" % n,
                "pair_id": pair_id,
                "text": text + suffix,
                "category": "layman_situation",
                "variant": variant,
                "numbering_scheme": "none",
                "applicable_regime": regime,
                "date_stated": variant in ("ipc_era", "bns_era"),

                # --- gold -------------------------------------------------
                "expected_sections": gold,
                "also_relevant": also,
                "expected_corpora": corp,
                "expected_corpus": corp[0] if len(corp) == 1 else "EITHER",
                "gold_mode": "either_era" if regime == "UNKNOWN" else "exact",
                "gold_status": "needs_review" if review else "uncontroversial",

                # --- honesty flags ---------------------------------------
                # In either_era mode any ONE of the accepted provisions counts,
                # so the row is answerable if at least one is reachable. In
                # exact mode there is a single governing code and it must be
                # present, or the row is unanswerable by construction.
                "answerable_from_corpus": (
                    any(statute_of(r) in CORPORA_IN_INDEX for r in gold)
                    if regime == "UNKNOWN" else answerable(gold)
                ),
                "unreachable_statutes": sorted(
                    {statute_of(r) for r in gold if statute_of(r) not in CORPORA_IN_INDEX}),
                "control_unchanged_statute": control,
                "no_counterpart_dropped": dropped,
                "substantive_change_notes": notes,

                # --- descriptive -----------------------------------------
                "n_words": len(text.split()),
                "messiness": messiness,
                "phrasing_register": "layman",
                "topic": topic,
                "notes": why,
            })
    return rows


def main() -> None:
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    var = collections.Counter(r["variant"] for r in rows)
    corp = collections.Counter(r["expected_corpus"] for r in rows)
    gold = collections.Counter(r["gold_status"] for r in rows)
    unans = [r for r in rows if not r["answerable_from_corpus"]]

    print("  wrote %d layman queries -> %s" % (len(rows), OUT.relative_to(ROOT)))
    print("  from %d situations x %d date conditions\n" % (len(SCENARIOS), len(DATE_VARIANTS)))
    print("  by date variant    : %s" % dict(var))
    print("  by expected corpus : %s" % dict(corp))
    print("  gold status        : %s" % dict(gold))
    print("  controls (CPA, unchanged by recodification) : %d"
          % sum(1 for r in rows if r["control_unchanged_statute"]))
    print("  unanswerable from this corpus : %d  %s"
          % (len(unans), sorted({s for r in unans for s in r["unreachable_statutes"]})))

    # The check that the old bug is gone. This is the whole point of the fix,
    # so it fails the build rather than printing a warning nobody reads.
    bns_rows = [r for r in rows
                if r["variant"] == "bns_era" and not r["control_unchanged_statute"]]
    leaked = [r for r in bns_rows
              if any(statute_of(s) in ("IPC", "CRPC") for s in r["expected_sections"])]
    print("\n  REGRESSION CHECK  bns_era rows: %d   still carrying old-code gold: %d   (must be 0)"
          % (len(bns_rows), len(leaked)))
    if leaked:
        raise SystemExit("  FAILED -- old-code gold leaked into the BNS era")

    print("\n  estimated run cost ~$%.2f  (~Rs %.0f)"
          % (len(rows) * 0.0059, len(rows) * 0.0059 * 88))
    print("\n  SAMPLE -- one situation across all four date conditions:")
    for r in [x for x in rows if x["pair_id"] == "L003"]:
        print("    [%-8s %-8s] gold=%-26s ...%s"
              % (r["variant"], r["applicable_regime"],
                 str(r["expected_sections"]), r["text"][-44:]))


if __name__ == "__main__":
    main()
