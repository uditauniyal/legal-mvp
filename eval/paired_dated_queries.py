#!/usr/bin/env python3
"""Paired queries where the CODE NAMED and the DATE GIVEN disagree.

WHY THE EXISTING PAIRED SET CANNOT MEASURE THE STATUTE MAPPER
    eval/paired_queries.py names a code in every query and gives a date in
    none of them. With no date the Date Resolver returns UNKNOWN, and on
    UNKNOWN the Statute Mapper deliberately changes nothing -- with no date
    there is no basis to move someone off the code they named.

    So on that set the intervention is a no-op by design, and a baseline vs
    intervention comparison would measure nothing.

WHAT THIS SET DOES
    It puts the two signals in conflict:

        "What is the punishment for cheating under Section 420 of the Indian
         Penal Code? This happened last month."

    The words say IPC. The date says the conduct is after 1 July 2024, so
    BNS 318(4) governs and IPC 420 was repealed. Gold is the code the DATE
    selects, not the one the query names.

    Phase G's baseline behaviour on this is predictable and wrong: the Router
    reads "Indian Penal Code", filters to the IPC, and returns repealed law
    with high confidence. That is the failure the Statute Mapper exists to
    remove, and this is the set that measures whether it does.

THE THREE VARIANTS

    conflict_ipc_named   names the IPC, dated after the cutover
                         -> gold is the BNS provision
    conflict_bns_named   names the BNS, dated before the cutover
                         -> gold is the IPC provision
    agree_control        names the IPC, dated before the cutover
                         -> gold is the IPC provision

    The control matters as much as the conflicts. If the mapper improves the
    conflict cases but damages the control, it has simply learned to prefer
    the other code, which would be a different bug rather than a fix. A
    result is only real if the control holds still.

WHY THE DATE PHRASES ARE THE SAME ONES USED IN THE LAYMAN SET
    "This happened last month." and "This happened in March 2023." are copied
    verbatim from eval/layman_queries.py. Reusing them means a difference
    between the two sets cannot be blamed on different date wording.

REFERENCE DATE
    "Last month" is resolved against the reference date passed to the runner
    (default 2026-08-23, the day Phase G ran), never against the clock.

USAGE
    python eval/paired_dated_queries.py
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "paired_dated_queryset.jsonl"
MAP = ROOT / "data" / "recodification_map.json"

HUMAN_NAME = {
    "IPC": "the Indian Penal Code",
    "BNS": "the Bharatiya Nyaya Sanhita",
}

# Verbatim from eval/layman_queries.py.
AFTER_CUTOVER = " This happened last month."
BEFORE_CUTOVER = " This happened in March 2023."


def section_of(ref: str) -> str:
    return ref.split(" ", 1)[1]


def build() -> list[dict]:
    data = json.loads(MAP.read_text(encoding="utf-8"))
    rows: list[dict] = []
    n = 0

    for entry in data["mappings"]:
        if entry["confidence"] != "verified_in_corpus":
            continue
        old, new, subject = entry["from"], entry["to"][0], entry["subject"]
        pair_id = f"D_{old.replace(' ', '')}"

        def ask(ref: str) -> str:
            act = ref.split(" ", 1)[0]
            return (f"What is the punishment for {subject} under Section "
                    f"{section_of(ref)} of {HUMAN_NAME[act]}?")

        variants = [
            # Names the repealed code, describes recent conduct.
            ("conflict_ipc_named", ask(old) + AFTER_CUTOVER, "BNS_ERA",
             [new], "BNS", [old], True),
            # Names the current code, describes pre-recodification conduct.
            ("conflict_bns_named", ask(new) + BEFORE_CUTOVER, "IPC_ERA",
             [old], "IPC", [new], True),
            # Control: code named and date agree. Must not get worse.
            ("agree_control", ask(old) + BEFORE_CUTOVER, "IPC_ERA",
             [old], "IPC", [], False),
        ]

        for variant, text, regime, gold, corpus, named_but_wrong, conflict in variants:
            n += 1
            rows.append({
                "query_id": f"D{n:04d}",
                "pair_id": pair_id,
                "text": text,
                "category": "paired_dated_conflict",
                "variant": variant,
                "numbering_scheme": named_but_wrong[0].split(" ")[0] if named_but_wrong else corpus,
                "applicable_regime": regime,
                "date_stated": True,

                # --- gold: what the DATE selects, not what the query names --
                "expected_sections": gold,
                "expected_corpus": corpus,
                "expected_corpora": [corpus],
                "gold_mode": "exact",
                "gold_status": "certain_by_construction",

                # --- the measurement ---------------------------------------
                # Retrieving THIS is the specific failure: the system followed
                # the words in the query instead of the law in force.
                "wrong_era_sections": named_but_wrong,
                "conflict": conflict,

                "answerable_from_corpus": True,
                "phrasing_register": "technical",
                "subject": subject,
                "substantive_change_note": entry.get("note", ""),
                "notes": ("code named and date disagree; gold follows the date"
                          if conflict else
                          "control: code named and date agree"),
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

    print(f"  wrote {len(rows)} dated paired queries -> {OUT.relative_to(ROOT)}")
    print(f"  from {len({r['pair_id'] for r in rows})} verified IPC<->BNS pairs\n")
    print(f"  by variant         : {dict(var)}")
    print(f"  by expected corpus : {dict(corp)}")
    print(f"  conflicts          : {sum(1 for r in rows if r['conflict'])}"
          f"   controls: {sum(1 for r in rows if not r['conflict'])}")
    print(f"\n  estimated run cost ~${len(rows)*0.0059:.2f} per mode "
          f"(~Rs {len(rows)*0.0059*88:.0f})")

    print("\n  SAMPLE — one provision across all three variants:")
    for r in [x for x in rows if x["pair_id"] == "D_IPC420"]:
        print(f"    [{r['variant']:<19} -> gold {str(r['expected_sections']):<14}] {r['text'][-72:]}")


if __name__ == "__main__":
    main()
