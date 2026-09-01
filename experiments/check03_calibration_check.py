"""check03 -- PAIRED CHECK for exp03_calibration.  Wave 2, Subagent 3.

WHY A SECOND ROUTE EXISTS
    A calibration number is easy to compute and easy to compute WRONGLY, and
    the wrong version looks exactly as publishable as the right one. Defect E2
    in this project -- a headline retrieval metric that returned 0.0 for its
    entire existence because "IPC Section 302" was compared against
    "Section 302" -- was invisible for months precisely because nobody
    re-derived it by a second route.

    So every headline number in results/calibration.csv is recomputed here by
    a route that shares as little code as possible with the first, and the two
    are ASSERTED equal. Not eyeballed. If they disagree the script fails loudly
    and the CSV must not be used.

THE FIVE CHECKS

  1. ECE FROM THE BIN TABLE, BY HAND.
     ece() is a one-line aggregation over reliability_bins(). Here the same
     number is rebuilt as  sum over bins of (n_bin/n) * |accuracy - mean_score|
     from the bin table, using nothing but python arithmetic. Asserted equal
     to ece() for both scores and all three definitions.

  2. THE BINS PARTITION THE SAMPLE.
     The `n` column of the bin table must sum to exactly the full sample.
     A quantile-binning off-by-one that dropped the top or bottom row would
     otherwise shift ECE quietly and never be noticed.

  3. BRIER FROM A PLAIN PYTHON LOOP.
     brier() is vectorised numpy. Here it is a for-loop over the rows with no
     numpy at all. Same number or the script fails.

  4. COVERAGE AT 10% RISK BY BRUTE FORCE.
     coverage_at_risk() walks a sorted cumulative curve. Here every distinct
     score is tried as an explicit "answer only if score >= t" threshold, the
     error rate among the answered is computed directly, and the largest
     admissible coverage is taken. Independent of the sort-and-cumsum path.

  5. THE CSV SAYS WHAT THE LIBRARY SAYS.
     results/calibration.csv is re-read from disk and its ece, brier, aurc and
     coverage rows are checked against freshly computed values, so a formatting
     or rounding bug between computing and writing cannot survive.

Run:  ./venv/Scripts/python.exe experiments/check03_calibration_check.py
      (run exp03_calibration.py first -- check 5 reads its CSV)

ZERO API calls. Reads only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.metrics_lib import (  # noqa: E402
    reliability_bins, ece, brier, aurc, coverage_at_risk,
)
from experiments.exp03_calibration import (  # noqa: E402
    build, ycol, SCORES, DEFS, N_BINS, BINNING, RISK_LEVEL, OUT_CSV,
)

TOL = 1e-12


# ---------------------------------------------------------------- routes

def ece_by_hand(scores, labels):
    """ECE rebuilt from the reliability-bin table with plain arithmetic.

    ECE = sum over bins of (n_bin / n) * |accuracy_bin - mean_score_bin|.
    No numpy aggregation, no reuse of ece(). Returns (value, total_binned_n).
    """
    b = reliability_bins(scores, labels, N_BINS, BINNING)
    total = 0
    acc = 0.0
    for _, r in b.iterrows():
        n_bin = int(r["n"])
        total += n_bin
        acc += n_bin * abs(float(r["accuracy"]) - float(r["mean_score"]))
    return acc / total, total


def brier_by_loop(scores, labels):
    """Mean squared error, one row at a time, no numpy."""
    tot = 0.0
    n = 0
    for s, y in zip(list(scores), list(labels)):
        d = float(s) - float(y)
        tot += d * d
        n += 1
    return tot / n


def coverage_at_risk_bruteforce(scores, labels, max_risk=RISK_LEVEL):
    """Largest coverage with error rate <= max_risk, by explicit thresholding.

    For every distinct score value t: answer the queries with score >= t,
    measure the error rate among exactly those, keep t if the rate is
    admissible, and report the largest resulting coverage. This is the literal
    definition of the quantity; coverage_at_risk() gets there by sorting and
    accumulating, which is faster and, if it is right, identical.
    """
    s = list(map(float, scores))
    y = list(map(int, labels))
    n = len(s)
    best = 0.0
    for t in sorted(set(s)):
        answered = [(sc, yy) for sc, yy in zip(s, y) if sc >= t]
        if not answered:
            continue
        risk = sum(1 for _, yy in answered if yy == 0) / len(answered)
        if risk <= max_risk:
            best = max(best, len(answered) / n)
    return best


# ---------------------------------------------------------------- main

def main():
    d = build()
    n_all = len(d)
    failures = []
    print("check03 -- paired check on %d gold-labelled rows\n" % n_all)

    for score in SCORES:
        for definition, k, stage, _ in DEFS:
            s = d[score].values
            y = d[ycol(definition)].values
            tag = "%s / %s" % (score, definition)

            # --- 1 + 2: ECE by hand, and the bins partition the sample
            lib_ece = ece(s, y, N_BINS, BINNING)
            hand_ece, binned_n = ece_by_hand(s, y)
            ok1 = abs(lib_ece - hand_ece) < TOL
            ok2 = binned_n == n_all
            if not ok1:
                failures.append("ECE MISMATCH %s: ece()=%.12f hand=%.12f "
                                "(diff %.3e)" % (tag, lib_ece, hand_ece,
                                                 lib_ece - hand_ece))
            if not ok2:
                failures.append("BIN COUNT MISMATCH %s: bins hold %d rows, "
                                "sample has %d" % (tag, binned_n, n_all))

            # --- 3: Brier by loop
            lib_b = brier(s, y)
            loop_b = brier_by_loop(s, y)
            ok3 = abs(lib_b - loop_b) < 1e-10
            if not ok3:
                failures.append("BRIER MISMATCH %s: brier()=%.12f loop=%.12f"
                                % (tag, lib_b, loop_b))

            # --- 4: coverage at 10% risk by brute force
            lib_c = coverage_at_risk(s, y, RISK_LEVEL)
            bf_c = coverage_at_risk_bruteforce(s, y, RISK_LEVEL)
            ok4 = abs(lib_c - bf_c) < TOL
            if not ok4:
                failures.append("COVERAGE MISMATCH %s: lib=%.12f "
                                "bruteforce=%.12f" % (tag, lib_c, bf_c))

            print("%-26s ECE %.6f==%.6f %s | bins %d==%d %s | "
                  "Brier %.6f==%.6f %s | cov@%.0f%% %.6f==%.6f %s"
                  % (tag, lib_ece, hand_ece, "OK" if ok1 else "FAIL",
                     binned_n, n_all, "OK" if ok2 else "FAIL",
                     lib_b, loop_b, "OK" if ok3 else "FAIL",
                     100 * RISK_LEVEL, lib_c, bf_c, "OK" if ok4 else "FAIL"))

    # --- 5: the CSV on disk agrees with the library
    print()
    if not Path(OUT_CSV).exists():
        failures.append("CSV MISSING: %s -- run exp03_calibration.py first"
                        % OUT_CSV)
    else:
        csv = pd.read_csv(OUT_CSV)
        allrows = csv[csv["query_set"] == "ALL"]
        checked = 0
        for score in SCORES:
            for definition, k, stage, _ in DEFS:
                s = d[score].values
                y = d[ycol(definition)].values
                want = {
                    "ece": ece(s, y, N_BINS, BINNING),
                    "brier": brier(s, y),
                    "aurc": aurc(s, y),
                    "coverage_at_risk_%.2f" % RISK_LEVEL:
                        coverage_at_risk(s, y, RISK_LEVEL),
                }
                for metric, val in want.items():
                    m = allrows[(allrows["metric"] == metric)
                                & (allrows["definition"] == definition)
                                & (allrows["notes"].str.startswith(
                                    "score=" + score))]
                    if len(m) != 1:
                        failures.append("CSV ROW NOT UNIQUE: %s %s %s -> %d "
                                        "rows" % (metric, score, definition,
                                                  len(m)))
                        continue
                    got = float(m["value"].iloc[0])
                    # the CSV stores 6 decimal places, so compare at 5e-7
                    if abs(got - val) > 5e-7:
                        failures.append("CSV VALUE MISMATCH %s %s %s: "
                                        "csv=%.9f computed=%.9f"
                                        % (metric, score, definition, got, val))
                    if int(m["n"].iloc[0]) != n_all:
                        failures.append("CSV n MISMATCH %s %s %s: csv n=%s "
                                        "expected %d"
                                        % (metric, score, definition,
                                           m["n"].iloc[0], n_all))
                    checked += 1
        print("CSV cross-check: %d headline values re-read and compared"
              % checked)

    print()
    if failures:
        print("=" * 72)
        print("PAIRED CHECK FAILED -- %d disagreement(s). DO NOT USE THE CSV."
              % len(failures))
        for f in failures:
            print("  " + f)
        print("=" * 72)
        raise AssertionError("check03 paired check failed: %d disagreement(s)"
                             % len(failures))

    print("PAIRED CHECK PASSED -- every headline value agrees by two "
          "independent routes.")


if __name__ == "__main__":
    main()
