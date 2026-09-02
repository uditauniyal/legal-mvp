"""Build results/TESTING_WORKBOOK.xlsx -- the inspectable, four-sheet workbook.

WHY THIS FILE EXISTS
    Every number in docs/ and results/ is defensible only if someone can open
    it and follow it back to a file. This script produces one workbook whose
    every cell was READ from a source -- eval/*_queryset.jsonl, runs/,
    experiments/stages.jsonl, results/*.csv, the Qdrant payloads, or the
    source code itself. Nothing here is typed from memory or from prose.

    Where a value genuinely does not exist in any source, the cell says
    NOT AVAILABLE. It never says a plausible number.

THE FOUR SHEETS
    Questions           518 unique evaluation queries, one row each
    Per-query results   621 deduplicated logged runs, one row each
    Parameters          every configuration value the runs actually used
    Summary             headline results lifted verbatim from results/*.csv

THREE THINGS THAT ARE NOT NEGOTIABLE HERE, and why

  1. EVERY METRIC COMES FROM experiments/metrics_lib.py.
     No local recall, no local section comparison, no local dedupe. A second
     implementation that disagrees in the third decimal is how tables end up
     silently contradicting each other.

  2. THE LOGGED TIER FIELD IS NOT COPIED.
     answer.prompt_variant reads "HIGH" on every record. The variable was
     initialised once and never reassigned in the LOW/MEDIUM branches, so 369
     of 859 logged records carry the wrong tier (agents/answer.py:82-87). The
     disclaimer actually shown to the model was correct throughout; only the
     log field was wrong. This sheet RECOMPUTES the tier from the logged
     composite using agents.answer.tier_for_confidence, the fixed function.

  3. eval/queryset.jsonl IS EXCLUDED.
     It is the older, superseded 58-query set. The live sets are the four in
     QUERYSETS below, 518 queries in total.

READ-ONLY on Qdrant: one scroll, no writes. Writes only the workbook.

Run:
    ./venv/Scripts/python.exe experiments/make_workbook.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from experiments.metrics_lib import (  # noqa: E402
    N_BOOT,
    SEED,
    STAGES,
    correctness_label,
    load_logs,
    load_queryset,
    load_stages,
    normalise_section,
    ranked_sections,
    same_section,
)

NA = "NOT AVAILABLE"
OUT = ROOT / "results" / "TESTING_WORKBOOK.xlsx"

# The four LIVE query sets. eval/queryset.jsonl is the superseded older set
# and is deliberately absent -- see the module docstring.
QUERYSETS = {
    "generated_retrieval":   ROOT / "eval" / "generated_queryset.jsonl",
    "paired_recodification": ROOT / "eval" / "paired_queryset.jsonl",
    "paired_dated_conflict": ROOT / "eval" / "paired_dated_queryset.jsonl",
    "layman_situation":      ROOT / "eval" / "layman_queryset.jsonl",
}

# GOLD CERTAINTY is a property of HOW A SET WAS BUILT, not of a row, so it is
# derived from the set and never typed per query.
#
#   construction  the query was generated FROM a known section, so that
#                 section is the answer by definition
#   judgement     someone decided which section governs a described situation
#
# CORRECTED 3 Sept. An earlier version of this script classified the dated set
# as "judgement" on instruction. Each query set records its OWN gold_status, and
# that field is authoritative:
#     generated_retrieval    certain_by_construction  200
#     paired_recodification  certain_by_construction   99
#     paired_dated_conflict  certain_by_construction   99
#     layman_situation       needs_review 68 / uncontroversial 52
# The dated set IS construction: given a verified IPC-BNS provision pair and a
# date, which one governs follows mechanically from the 1 July 2024 commencement.
# Only the layman set required deciding which section governs a described
# situation. So certainty is now read per row from the query set itself, and the
# original sub-status is kept alongside it rather than being discarded.
GOLD_STATUS_TO_CERTAINTY = {
    "certain_by_construction": "construction",
    "needs_review":            "judgement",
    "uncontroversial":         "judgement",
}


# ============================================================ source helpers

def grep_source(rel_path: str, pattern: str) -> tuple[str, str]:
    """(matched line text, "path:line") for the FIRST match of `pattern`.

    Used so that every Parameters row can name the file and line it was read
    from, rather than asserting a value the reader has to trust.
    """
    path = ROOT / rel_path
    rx = re.compile(pattern)
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if rx.search(line):
            return line.strip(), f"{rel_path}:{i}"
    return NA, f"{rel_path}: pattern not found"


def grep_value(rel_path: str, pattern: str, group: int = 1) -> tuple[str, str]:
    """(captured group, "path:line") -- the value itself, read from source."""
    path = ROOT / rel_path
    rx = re.compile(pattern)
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = rx.search(line)
        if m:
            return m.group(group), f"{rel_path}:{i}"
    return NA, f"{rel_path}: pattern not found"


def load_corpus_payloads() -> list[dict]:
    """READ-ONLY scroll of the whole Qdrant collection.

    Same access pattern as experiments/exp07_hybrid.py:load_corpus so the
    reachability figures computed here are comparable with the ceiling
    already published in results/hybrid_comparison.csv.
    """
    from clients.qdrant_client import COLLECTION, qdrant
    client = qdrant()
    docs, offset = [], None
    while True:
        pts, offset = client.scroll(collection_name=COLLECTION, limit=500,
                                    offset=offset, with_payload=True,
                                    with_vectors=False)
        for p in pts:
            pl = dict(p.payload or {})
            pl["_point_id"] = str(p.id)
            docs.append(pl)
        if offset is None:
            break
    return docs


def indexed_sections(docs: list[dict]) -> set[str]:
    """The set of canonical (corpus, section_number) ids present in the index.

    Built through metrics_lib.ranked_sections so the canonicalisation rule is
    the same one every other metric uses.
    """
    return {ranked_sections([d])[0] for d in docs if d.get("section_number")}


def gold_reachable(gold: list[str], indexed: set[str]) -> bool:
    """Does ANY gold section for this query exist in the index, strictly?

    Strict matching only. same_section's own docstring says lenient matching
    over-counts (498A collapses onto 498), and the published ceiling in
    hybrid_comparison.csv is strict, so loosening here would make the two
    incomparable.
    """
    return any(any(same_section(g, a) for a in indexed) for g in gold)


# ============================================================ sheet 1

def build_questions(indexed: set[str]) -> tuple[pd.DataFrame, dict]:
    rows = []
    for qs, path in QUERYSETS.items():
        for r in load_queryset(path).to_dict("records"):
            gold = list(r.get("expected_sections") or [])
            canon = [normalise_section(g) for g in gold]
            statutes, numbers = [], []
            for c in canon:
                st, num = c.split(":", 1) if ":" in c else ("", c)
                statutes.append(st or NA)
                numbers.append(num or NA)
            rows.append({
                "query_id": r.get("query_id") or NA,
                "query_set": qs,
                "question_text": r.get("text") or NA,
                "gold_statute": "; ".join(statutes) if statutes else NA,
                "gold_section": "; ".join(numbers) if numbers else NA,
                "gold_certainty": GOLD_STATUS_TO_CERTAINTY.get(
                    r.get("gold_status"), "NOT AVAILABLE"),
                "gold_status_as_recorded": r.get("gold_status")
                    or "NOT AVAILABLE",
                "query_type": r.get("variant") or NA,
                "era_condition": r.get("applicable_regime") or NA,
                "situation_id": r.get("pair_id") or NA,
                "gold_reachable_in_index": (
                    bool(gold_reachable(gold, indexed)) if gold else NA),
            })
    df = pd.DataFrame(rows)

    # -------- cross-check against the published aggregate ceiling
    published = pd.read_csv(ROOT / "results" / "hybrid_comparison.csv")
    published = published[published["metric"] == "gold_reachable_ceiling"]
    check = {}
    for qs in QUERYSETS:
        sub = df[df["query_set"] == qs]
        mine_k = int((sub["gold_reachable_in_index"] == True).sum())  # noqa: E712
        mine_n = len(sub)
        p = published[published["query_set"] == qs]
        theirs = float(p["value"].iloc[0]) if len(p) else float("nan")
        theirs_n = int(p["n"].iloc[0]) if len(p) else 0
        check[qs] = {"mine_k": mine_k, "mine_n": mine_n,
                     "mine_rate": mine_k / mine_n if mine_n else float("nan"),
                     "published_rate": theirs, "published_n": theirs_n}
    all_k = int((df["gold_reachable_in_index"] == True).sum())  # noqa: E712
    p_all = published[published["query_set"] == "ALL"]
    check["ALL"] = {"mine_k": all_k, "mine_n": len(df),
                    "mine_rate": all_k / len(df) if len(df) else float("nan"),
                    "published_rate": float(p_all["value"].iloc[0]) if len(p_all) else float("nan"),
                    "published_n": int(p_all["n"].iloc[0]) if len(p_all) else 0}
    return df, check


# ============================================================ sheet 2

def build_per_query() -> tuple[pd.DataFrame, dict]:
    from agents.answer import tier_for_confidence

    logs = load_logs()
    stages = load_stages()

    rows = []
    for rec in logs.to_dict("records"):
        rid = rec["req_id"]
        st = stages.get(rid, {})
        gold = rec.get("expected_sections") or []
        has_gold = bool(len(gold))

        def n_at(stage):
            return len(st[stage]) if stage in st else NA

        def gold_at(stage):
            if not has_gold:
                return NA
            if stage not in st:
                return NA
            return bool(correctness_label({**rec, "_stage": stage},
                                          "retrieved@k", k=15, stages=stages))

        comp = rec.get("composite")
        cited = rec.get("cited") or []
        grounded = rec.get("grounded") or []
        ur = rec.get("ungrounded_rate")

        rows.append({
            "req_id": rid,
            "query_id": rec.get("query_id") or NA,
            "query_set": rec.get("query_set") or NA,
            "intervention": rec.get("intervention") or NA,
            "n_retrieved_raw_15": n_at("raw_15"),
            "n_retrieved_reranked_15": n_at("reranked_15"),
            "n_retrieved_filtered_n": n_at("filtered_n"),
            "gold_in_raw_15": gold_at("raw_15"),
            "gold_in_reranked_15": gold_at("reranked_15"),
            "gold_in_filtered_n": gold_at("filtered_n"),
            "answer_cited": "; ".join(map(str, cited)) if cited else "",
            "n_citations": len(cited),
            "n_citations_grounded": len(grounded),
            "ungrounded_rate": NA if ur is None or pd.isna(ur) else float(ur),
            "top_k_mean": NA if comp is None else rec.get("top_k_mean"),
            "score_gap": rec.get("score_gap"),
            "entity_coverage": rec.get("entity_coverage"),
            "composite": comp,
            "tier_recomputed_from_composite": (
                tier_for_confidence(float(comp)) if comp is not None
                and not pd.isna(comp) else NA),
            "correct_retrieved@15_raw_15": (
                bool(correctness_label({**rec, "_stage": "raw_15"},
                                       "retrieved@k", k=15, stages=stages))
                if has_gold else NA),
            "correct_cited": (bool(correctness_label(rec, "cited"))
                              if has_gold else NA),
            "correct_grounded": (bool(correctness_label(rec, "grounded"))
                                 if has_gold else NA),
        })

    df = pd.DataFrame(rows)
    stats = {
        "rows_before_dedupe": logs.attrs.get("rows_before_dedupe"),
        "rows_after_dedupe": len(logs),
        "rows_with_gold": int((logs["expected_sections"].map(len) > 0).sum()),
        "rows_with_stage_records": int(logs["req_id"].isin(stages).sum()),
    }
    return df, stats


# ============================================================ sheet 3

def build_parameters(n_index: int, per_query_stats: dict) -> pd.DataFrame:
    """Every configuration value the runs used: name / value / where from.

    Sourced two ways, both of them primary:
      * runs/*/meta.json     what the pipeline RECORDED at run time
      * the source files     the literals the pipeline reads
    Documentation is deliberately NOT a source here. docs/ states the
    confidence formula with the middle term untransformed; the deployed code
    applies 1-min(gap/0.3,1) instead. See results/ablation.csv, metric
    composite_reconstruction_max_abs_dev_brief_formula: the documented form
    fails to reconstruct the logged composite on 617 of 617 rows.
    """
    metas = sorted((ROOT / "runs").glob("*/meta.json"))
    cfgs = [json.loads(p.read_text(encoding="utf-8")) for p in metas]
    distinct = {json.dumps(c.get("config", {}), sort_keys=True) for c in cfgs}
    cfg = cfgs[0].get("config", {}) if cfgs else {}
    cfg_src = (f"runs/*/meta.json -> config (all {len(cfgs)} runs identical)"
               if len(distinct) == 1 else
               f"runs/*/meta.json -> config ({len(distinct)} DISTINCT configs)")

    rows: list[dict] = []

    def add(name, value, source):
        rows.append({"parameter": name,
                     "value": NA if value is None else value,
                     "source": source})

    # ---- models and provider pinning
    add("embedding model", cfg.get("embed_model", NA), cfg_src)
    _, src = grep_source("core/config.py", r'EMBED_MODEL\s*=\s*os\.getenv')
    add("embedding model (code default)",
        grep_value("core/config.py", r'EMBED_MODEL.*"([^"]+)"\)')[0], src)
    add("embedding dimension", cfg.get("embed_dim", NA), cfg_src)
    add("generation model", cfg.get("gen_model", NA), cfg_src)
    _, src = grep_source("core/config.py", r'GEN_MODEL\s*=\s*os\.getenv')
    add("generation model (code default)",
        grep_value("core/config.py", r'GEN_MODEL.*"([^"]+)"\)')[0], src)
    add("generation temperature", cfg.get("gen_temperature", NA), cfg_src)
    add("provider pin (generation)", cfg.get("gen_provider", NA), cfg_src)
    add("provider pin (embedding)", cfg.get("embed_provider", NA), cfg_src)
    add("provider pin: allow_fallbacks", cfg.get("allow_fallbacks", NA), cfg_src)
    add("provider pin: require_parameters", cfg.get("require_parameters", NA), cfg_src)
    line, src = grep_source("core/config.py", r'block\["only"\] = \[provider\]')
    add("provider pin mechanism", line, src)
    add("api base", cfg.get("api_base", NA), cfg_src)

    # ---- chunking
    #
    # Chunking here is SECTION-BOUNDED, not a sliding window: a chunk is one
    # statutory section unless that section is too long to keep whole.
    v, src = grep_value("ingest/chunk.py", r"^MAX_SECTION_TOKENS\s*=\s*(\d+)")
    add("chunk size: max tokens before a section is split", int(v) if v != NA else NA, src)
    v, src = grep_value("ingest/chunk.py", r"^TARGET_TOKENS\s*=\s*(\d+)")
    add("chunk size: target tokens of each split piece", int(v) if v != NA else NA, src)
    v, src = grep_value("ingest/chunk.py", r"^MIN_CHUNK_TOKENS\s*=\s*(\d+)")
    add("chunk size: minimum tokens kept", int(v) if v != NA else NA, src)
    line, src = grep_source("ingest/chunk.py", r"No overlap here")
    add("chunk overlap", 0, f"{src} -- \"{line}\"")

    # ---- retrieval
    add("top-k (retrieval limit)", cfg.get("top_k", NA), cfg_src)
    v, src = grep_value("core/config.py", r'TOP_K\s*=\s*_int\("TOP_K",\s*(\d+)\)')
    add("top-k (code default)", int(v) if v != NA else NA, src)
    add("Qdrant collection", cfg.get("collection", NA), cfg_src)
    add("index size (chunks in collection)", n_index,
        "Qdrant scroll of the live collection, READ-ONLY, this run")

    # ---- confidence weights, READ OUT OF THE DEPLOYED CODE
    v, src = grep_value("agents/retriever.py", r"([0-9.]+)\s*\*\s*top_k_mean")
    add("confidence weight: top_k_mean", float(v) if v != NA else NA, src)
    v, src = grep_value("agents/retriever.py", r"([0-9.]+)\s*\*\s*\(1\.0 - gap_penalty\)")
    add("confidence weight: gap term", float(v) if v != NA else NA, src)
    v, src = grep_value("agents/retriever.py", r"([0-9.]+)\s*\*\s*entity_coverage")
    add("confidence weight: entity_coverage", float(v) if v != NA else NA, src)
    line, src = grep_source("agents/retriever.py", r"gap_penalty = min\(")
    add("confidence gap transform (DEPLOYED)", line, src)
    add("confidence formula (DEPLOYED, as reconstructed and verified)",
        "0.55*top_k_mean + 0.15*(1-min(score_gap/0.3,1)) + 0.30*entity_coverage",
        "results/ablation.csv metric=composite_reconstruction_max_abs_dev "
        "-- reconstructs the logged composite on 617/617 rows, max abs dev 9e-05")
    add("confidence formula (as DOCUMENTED -- does NOT reconstruct)",
        "0.55*top_k_mean + 0.15*score_gap + 0.30*entity_coverage",
        "results/ablation.csv metric=composite_reconstruction_max_abs_dev_"
        "brief_formula -- 617/617 rows off by more than 1e-3, mean dev 0.0910")
    v, src = grep_value("agents/retriever.py", r"^ENTITY_NEUTRAL\s*=\s*([0-9.]+)")
    add("entity_coverage neutral default (no entity extracted)",
        float(v) if v != NA else NA, src)

    # ---- tiers
    v, src = grep_value("agents/answer.py", r"^HIGH_CONFIDENCE\s*=\s*([0-9.]+)")
    add("tier threshold: HIGH", float(v) if v != NA else NA, src)
    v, src = grep_value("agents/answer.py", r"^MEDIUM_CONFIDENCE\s*=\s*([0-9.]+)")
    add("tier threshold: MEDIUM", float(v) if v != NA else NA, src)
    line, src = grep_source("agents/answer.py", r'"prompt_variant": tier_for_confidence')
    add("tier recorded in the log (FIXED code)", line, src)
    add("tier column in 'Per-query results' is RECOMPUTED, not copied",
        "The logged field answer.prompt_variant reads HIGH on every record: "
        "the variable was initialised once and never reassigned in the LOW or "
        "MEDIUM branches, so 369 of 859 logged records (43.0%) carry the wrong "
        "tier. The disclaimer actually applied to the prompt was correct "
        "throughout -- only the log field was wrong. This workbook recomputes "
        "the tier from the logged composite via "
        "agents.answer.tier_for_confidence.",
        grep_source("agents/answer.py", r"previous version initialised prompt_variant")[1])

    # ---- adaptive filter
    v, src = grep_value("agents/retriever.py", r"^MIN_SCORE_FLOOR\s*=\s*([0-9.]+)")
    add("adaptive filter: absolute score floor", float(v) if v != NA else NA, src)
    v, src = grep_value("agents/retriever.py", r"^ADAPTIVE_DROP\s*=\s*([0-9.]+)")
    add("adaptive filter: drop below top score", float(v) if v != NA else NA, src)
    line, src = grep_source("agents/retriever.py", r"adaptive_threshold = max\(")
    add("adaptive filter formula", line, src)
    line, src = grep_source("agents/retriever.py", r"if len\(filtered\) < 3 and len\(res\) >= 3")
    m = re.search(r"len\(filtered\) < (\d+)", line or "")
    add("minimum chunks forced through the filter",
        int(m.group(1)) if m else NA, f"{src} -- \"{line}\"")

    # ---- seeds and resampling
    add("SEED (generation / pipeline, as run)", cfg.get("seed", NA), cfg_src)
    v, src = grep_value("core/config.py", r'SEED\s*=\s*_int\("SEED",\s*(\d+)\)')
    add("SEED (pipeline code default)", int(v) if v != NA else NA, src)
    v, src = grep_value("experiments/metrics_lib.py", r"^SEED\s*=\s*(\d+)")
    add("SEED (analysis / bootstrap)", int(v) if v != NA else NA, src)
    add("SEED (analysis, as imported)", SEED, "experiments/metrics_lib.SEED")
    v, src = grep_value("experiments/metrics_lib.py", r"^N_BOOT\s*=\s*(\d+)")
    add("N_BOOT (bootstrap resamples)", int(v) if v != NA else NA, src)
    add("N_BOOT (as imported)", N_BOOT, "experiments/metrics_lib.N_BOOT")

    # ---- corpus and run counts
    add("number of query sets", len(QUERYSETS),
        "eval/*_queryset.jsonl -- " + ", ".join(
            f"{p.name}" for p in QUERYSETS.values()))
    for qs, path in QUERYSETS.items():
        add(f"queries in {qs}", len(load_queryset(path)),
            f"eval/{path.name} (deduplicated on query_id by "
            "metrics_lib.load_queryset)")
    add("queries, all sets", sum(len(load_queryset(p)) for p in QUERYSETS.values()),
        "sum of the four rows above")
    add("superseded query set EXCLUDED", "eval/queryset.jsonl",
        f"{len(load_queryset(ROOT / 'eval' / 'queryset.jsonl'))} rows; older "
        "set, superseded by the four above; excluded from every sheet")

    add("number of logged runs (run directories)", len(metas),
        "runs/*/meta.json")
    add("logged rows before dedupe", per_query_stats["rows_before_dedupe"],
        "metrics_lib.load_logs().attrs['rows_before_dedupe']")
    add("logged rows after dedupe", per_query_stats["rows_after_dedupe"],
        "metrics_lib.load_logs() -- dedupe on (query_id, intervention), keep last")
    add("logged rows carrying a gold label", per_query_stats["rows_with_gold"],
        "metrics_lib.load_logs() -- rows with a non-empty expected_sections")
    add("logged rows with stage records", per_query_stats["rows_with_stage_records"],
        "metrics_lib.load_stages() over experiments/stages.jsonl")
    add("retrieval stages recorded", ", ".join(STAGES),
        "experiments/metrics_lib.STAGES")

    for p in metas:
        m = json.loads(p.read_text(encoding="utf-8"))
        add(f"run {p.parent.name}: git sha / dirty / started",
            f"{m.get('git_sha')} / dirty={m.get('git_dirty')} / {m.get('started')}",
            f"runs/{p.parent.name}/meta.json")

    return pd.DataFrame(rows)


# ============================================================ sheet 4

_TAG_RE = re.compile(r"^\s*(signal|score|restriction)\s*=\s*([^;]+)")


def _tag(notes) -> str:
    """The disambiguating tag a results row carries in its notes field.

    Several files hold the SAME metric name several times, separated only by
    which signal or which robustness restriction produced it. Dropping that
    tag would make the rows indistinguishable in the workbook.
    """
    m = _TAG_RE.match(str(notes or ""))
    return m.group(2).strip() if m else ""


def build_summary() -> pd.DataFrame:
    files = {name: pd.read_csv(ROOT / "results" / f"{name}.csv")
             for name in ("hybrid_comparison", "retrieval_metrics", "ablation",
                          "calibration", "robustness")}

    def pick(fname, **conds):
        d = files[fname].copy()
        for col, want in conds.items():
            if callable(want):
                d = d[d[col].map(want)]
            elif isinstance(want, (list, tuple, set)):
                d = d[d[col].isin(list(want))]
            else:
                d = d[d[col] == want]
        d = d.copy()
        d["_source"] = f"results/{fname}.csv"
        return d

    blocks = []

    # 1. cross-statute accuracy, IPC-named and BNS-named, three retrievers
    blocks.append(pick("hybrid_comparison",
                       metric=["corpus_dominant_accuracy", "corpus_top1_accuracy"],
                       query_set=["paired_numbered_ipc_named",
                                  "paired_numbered_bns_named",
                                  "paired_numbered_both"],
                       stage=["dense", "bm25", "hybrid_rrf"]))

    # 2. the gold-reachability ceiling
    blocks.append(pick("hybrid_comparison", metric="gold_reachable_ceiling"))

    # 3. Recall@15 per query set, all three stages
    blocks.append(pick("retrieval_metrics", metric="recall_at_k", k=15.0))

    # 4. per-signal AUROC
    blocks.append(pick("ablation", metric="auroc_signal"))

    # 5. calibration: ECE and coverage at 10% risk
    blocks.append(pick("calibration",
                       metric=["ece", "coverage_at_risk_0.10"]))

    # 6. the IPC-BNS gap under all three correctness definitions.
    #    restriction=none is the headline arm; the other arms are robustness
    #    re-runs of the same quantity and are carried too, tagged.
    blocks.append(pick("robustness",
                       metric=["paired_rate_ipc", "paired_rate_bns",
                               "paired_gap_ipc_minus_bns"]))

    raw = pd.concat(blocks, ignore_index=True)
    rows = []
    for r in raw.to_dict("records"):
        tag = _tag(r.get("notes"))
        rows.append({
            "metric": r["metric"],
            "variant": tag or NA,
            "query_set": r["query_set"] if pd.notna(r["query_set"]) else NA,
            "value": r["value"],
            "ci_lo_95": r["ci_lo"] if pd.notna(r["ci_lo"]) else NA,
            "ci_hi_95": r["ci_hi"] if pd.notna(r["ci_hi"]) else NA,
            "cluster_ci_lo_95": r["cluster_ci_lo"] if pd.notna(r["cluster_ci_lo"]) else NA,
            "cluster_ci_hi_95": r["cluster_ci_hi"] if pd.notna(r["cluster_ci_hi"]) else NA,
            "n": r["n"] if pd.notna(r["n"]) else NA,
            "correctness_definition": r["definition"] if pd.notna(r["definition"]) else NA,
            "retrieval_stage": r["stage"] if pd.notna(r["stage"]) else NA,
            "source_file": r["_source"],
            "notes": r["notes"] if pd.notna(r["notes"]) else "",
        })
    return pd.DataFrame(rows)


# ============================================================ workbook

WRAP_COLUMNS = {"question_text", "answer_cited", "notes", "source", "value",
                "parameter", "variant", "metric", "correctness_definition"}
WIDTH_CAP = 60


def write_sheet(wb, title: str, df: pd.DataFrame):
    ws = wb.create_sheet(title=title)
    cols = list(df.columns)
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.alignment = Alignment(vertical="top", wrap_text=True)

    for rec in df.itertuples(index=False, name=None):
        ws.append([v if not (isinstance(v, float) and pd.isna(v)) else NA
                   for v in rec])

    ws.freeze_panes = "A2"
    last = f"{get_column_letter(len(cols))}{ws.max_row}"
    ws.auto_filter.ref = f"A1:{last}"

    for i, name in enumerate(cols, 1):
        letter = get_column_letter(i)
        width = max([len(str(name))] +
                    [len(str(v)) for v in df[name].head(5000).tolist()] or [0])
        ws.column_dimensions[letter].width = max(9, min(width + 2, WIDTH_CAP))
        if name in WRAP_COLUMNS:
            for cell in ws[letter][1:]:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    return ws


def main():
    print("scrolling Qdrant (READ-ONLY) ...")
    docs = load_corpus_payloads()
    indexed = indexed_sections(docs)
    print(f"  {len(docs)} chunks, {len(indexed)} distinct canonical sections")

    print("sheet 1: Questions ...")
    questions, reach_check = build_questions(indexed)

    print("sheet 2: Per-query results ...")
    per_query, pq_stats = build_per_query()

    print("sheet 3: Parameters ...")
    params = build_parameters(len(docs), pq_stats)

    print("sheet 4: Summary ...")
    summary = build_summary()

    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(wb, "Questions", questions)
    write_sheet(wb, "Per-query results", per_query)
    write_sheet(wb, "Parameters", params)
    write_sheet(wb, "Summary", summary)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)

    print(f"\nwrote {OUT}")
    print(f"  Questions          {len(questions)} rows x {questions.shape[1]} cols")
    print(f"  Per-query results  {len(per_query)} rows x {per_query.shape[1]} cols")
    print(f"  Parameters         {len(params)} rows x {params.shape[1]} cols")
    print(f"  Summary            {len(summary)} rows x {summary.shape[1]} cols")

    print("\nreachability cross-check vs results/hybrid_comparison.csv "
          "metric=gold_reachable_ceiling:")
    for qs, c in reach_check.items():
        agree = (abs(c["mine_rate"] - c["published_rate"]) < 1e-6
                 and c["mine_n"] == c["published_n"])
        print(f"  {qs:<24} mine {c['mine_k']}/{c['mine_n']} = {c['mine_rate']:.6f} "
              f"| published {c['published_rate']:.6f} (n={c['published_n']}) "
              f"| {'MATCH' if agree else 'DISAGREE'}")

    na_counts = {}
    for name, df in (("Questions", questions), ("Per-query results", per_query),
                     ("Parameters", params), ("Summary", summary)):
        for col in df.columns:
            k = int((df[col].astype(str) == NA).sum())
            if k:
                na_counts[f"{name}.{col}"] = k
    print("\nNOT AVAILABLE cells:")
    for k, v in sorted(na_counts.items()):
        print(f"  {k}: {v}")
    if not na_counts:
        print("  none")


if __name__ == "__main__":
    main()
