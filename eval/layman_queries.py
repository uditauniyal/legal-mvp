#!/usr/bin/env python3
"""Layman queries -- lived situations, not legal vocabulary.

WHY THIS SET IS THE POINT OF THE PROJECT
    The system exists for people who do not know which law applies. Someone
    whose landlord kept their deposit does not type "Section 420 IPC". They
    type what happened to them.

    The generated set (eval/generate_from_corpus.py) measures the retrieval
    machinery precisely, but it phrases everything the way a statute does. It
    calibrates the instrument; it does not test the claim.

    THIS set tests the claim.

WHAT MAKES A QUERY LAYMAN, CONCRETELY
    - describes an event, not a legal category
    - names no section, no Act, no legal term of art
    - written the way a distressed person actually writes: partial, emotional,
      sometimes with details that do not matter and missing ones that do

        NOT layman:  "What is the law on criminal intimidation in India?"
        layman:      "A man keeps calling me and saying he will hurt my family."

THE DATE DIMENSION
    Only an event date decides whether the IPC or the BNS governs. Real people
    rarely state one -- of 58 hand-written queries, exactly one contained a
    usable date. So each scenario appears in four date conditions:

        no_date      how people actually ask        -> undeterminable
        ipc_era      "in March 2023"                -> IPC governs
        bns_era      "last month"                   -> BNS governs
        vague        "a while back"                 -> still undeterminable

    Comparing them measures whether stating a date helps at all, and whether
    the system uses it. Right now it cannot -- there is no Date Resolver -- so
    this gives the "before" half of that comparison for free.

GOLD LABELS
    Each scenario names the provision it is about. These are uncontroversial
    mappings -- "police arrested him without a warrant" is CrPC 41 by the
    section's own title, not by anyone's interpretation. Scenarios where the
    right section is genuinely arguable are marked needs_review=True and should
    not be counted until checked.

USAGE
    python eval/layman_queries.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "layman_queryset.jsonl"

from eval.scenarios import SCENARIOS  # noqa: E402


# Four date conditions. The suffix is appended to the situation text.
DATE_VARIANTS = [
    ("no_date", "", "UNKNOWN",
     "how people actually ask -- no date, so the applicable code is undeterminable"),
    ("ipc_era", " This happened in March 2023.", "IPC_ERA",
     "before 1 July 2024, so the IPC governs"),
    ("bns_era", " This happened last month.", "BNS_ERA",
     "after 1 July 2024, so the BNS governs"),
    ("vague", " This happened a while back, I do not remember exactly when.", "UNKNOWN",
     "a time reference that resolves nothing -- still undeterminable"),
]


def build() -> list[dict]:
    rows: list[dict] = []
    n = 0
    for s_i, (text, corpus, primary, secondary, topic, review, messiness) in enumerate(SCENARIOS, 1):
        pair_id = f"L{s_i:03d}"
        for variant, suffix, regime, why in DATE_VARIANTS:
            # Date variants only matter where two codes could apply.
            if corpus != "EITHER" and variant != "no_date":
                continue
            n += 1
            rows.append(
                {
                    "query_id": f"L{n:04d}",
                    "pair_id": pair_id,
                    "text": text + suffix,
                    "category": "layman_situation",
                    "variant": variant,
                    "numbering_scheme": "none",
                    "expected_corpus": corpus,
                    "expected_sections": primary,
                    "also_relevant": secondary,
                    "n_words": len(text.split()),
                    # 1 = fairly clear, 2 = typical, 3 = very fragmented.
                    # Recorded so accuracy can be correlated with messiness:
                    # if accuracy falls as messiness rises, that IS the
                    # access-to-justice claim, as a number.
                    "messiness": messiness,
                    "applicable_regime": regime,
                    "answerable_from_corpus": True,
                    "phrasing_register": "layman",
                    "topic": topic,
                    "gold_status": "needs_review" if review else "uncontroversial",
                    "date_stated": variant not in ("no_date", "vague"),
                    "notes": why,
                }
            )
    return rows


def main() -> None:
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    import collections
    var = collections.Counter(r["variant"] for r in rows)
    gold = collections.Counter(r["gold_status"] for r in rows)
    corp = collections.Counter(r["expected_corpus"] for r in rows)

    print(f"  wrote {len(rows)} layman queries -> {OUT.relative_to(ROOT)}")
    print(f"  from {len(SCENARIOS)} distinct situations\n")
    print(f"  by date variant : {dict(var)}")
    print(f"  by corpus       : {dict(corp)}")
    print(f"  gold status     : {dict(gold)}")
    print(f"\n  estimated run cost ~${len(rows)*0.0059:.2f}  (~Rs {len(rows)*0.0059*88:.0f})")
    print("\n  SAMPLE -- one situation across all four date conditions:")
    for r in [x for x in rows if x["pair_id"] == "L009"]:
        print(f"    [{r['variant']:<8} -> {r['applicable_regime']:<8}] {r['text'][:78]}")


if __name__ == "__main__":
    main()
