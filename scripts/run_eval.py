#!/usr/bin/env python3
"""Run the evaluation query set against the live system.

WHAT THIS DOES
    Reads eval/queryset.jsonl, sends each question to the running FastAPI
    server, and collects the results. The server writes one detailed record per
    query (see core/run_logger.py); this script drives it and writes a summary
    alongside.

WHY IT REFUSES TO RUN ON A DIRTY WORKING TREE
    "Dirty" means you have edits that are not committed to git. Every result
    records a git SHA -- the fingerprint identifying the exact code that
    produced it. If the code was not committed, that fingerprint does not
    describe what actually ran, so the result cannot be reproduced and any
    claim that it can is false.

    Being blocked for thirty seconds beats publishing an unreproducible number.
    Override with --allow-dirty for local experiments only; the run is then
    marked dirty in its metadata so it can never be mistaken for a clean one.

WHY IT IS RESUMABLE
    58 queries take about 14 minutes. If it dies at query 40, re-running with
    --resume skips the 39 already done rather than paying for them again.

WHY IT KEEPS GOING ON FAILURE
    One query erroring should not cost you the other 57. Failures are recorded
    with their error text and the run continues.

COST
    Measured on a live query: ~$0.0059 (about Rs 0.50) each.
    58 queries is roughly $0.34 (about Rs 30).

USAGE
    python scripts/run_eval.py --dry-run          list what would run, send nothing
    python scripts/run_eval.py                    run everything
    python scripts/run_eval.py --limit 5          first 5 only, for a smoke test
    python scripts/run_eval.py --category procedural
    python scripts/run_eval.py --resume runs/2026-08-23_1030_abc1234
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
QUERYSET = ROOT / "eval" / "queryset.jsonl"
RUNS = ROOT / "runs"
DEFAULT_URL = "http://127.0.0.1:8000"


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return ""


def load_queries(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"No query set at {path}. Run: python eval/build_queryset.py")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def server_ready(base_url: str) -> tuple[bool, str]:
    try:
        health = requests.get(f"{base_url}/healthz", timeout=5).json()
        env = requests.get(f"{base_url}/diag/env", timeout=5).json()
    except Exception as exc:
        return False, f"cannot reach {base_url} ({exc}). Start it with: uvicorn app:app"
    if not env.get("ok", False):
        return False, "server config has problems: " + "; ".join(env.get("problems", []))
    return True, f"build {health.get('build')}  |  {env['config']['gen_model']}"


def already_done(run_dir: Path) -> set[str]:
    """query_ids already recorded in this run directory.

    Reads eval_summary.jsonl -- the file THIS script writes. It used to read
    queries.jsonl, which is written by the SERVER and named differently, so
    the set came back empty and --resume silently re-ran and re-paid for
    everything it was supposed to skip.
    """
    jsonl = run_dir / "eval_summary.jsonl"
    if not jsonl.exists():
        return set()
    done = set()
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        try:
            done.add(json.loads(line)["query_id"])
        except Exception:
            continue
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--queryset", type=Path, default=QUERYSET,
                    help="which query set to run (default eval/queryset.jsonl)")
    ap.add_argument("--workers", type=int, default=1,
                    help="concurrent requests. The endpoint is synchronous, so "
                         "FastAPI runs it in a threadpool and several queries can "
                         "be in flight at once. Keep this low: every worker is a "
                         "separate billed call to the same provider, and the point "
                         "of the run is reproducible numbers, not speed.")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N")
    ap.add_argument("--category", help="restrict to one category")
    ap.add_argument("--dry-run", action="store_true", help="list what would run, send nothing")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="run with uncommitted changes; marks the run dirty")
    ap.add_argument("--resume", type=Path, help="continue an existing run directory")
    ap.add_argument("--timeout", type=int, default=180, help="seconds per query")
    args = ap.parse_args()

    # Accept a relative path from anywhere; every later use assumes it is
    # absolute and under ROOT.
    args.queryset = (args.queryset if args.queryset.is_absolute()
                     else (Path.cwd() / args.queryset)).resolve()
    queries = load_queries(args.queryset)
    if args.category:
        queries = [q for q in queries if q.get("category") == args.category]
    if args.limit:
        queries = queries[: args.limit]

    sha, dirty = git("rev-parse", "--short", "HEAD") or "nogit", bool(git("status", "--porcelain"))

    print(f"  query set   {args.queryset.relative_to(ROOT)}  ({len(queries)} to run)")
    print(f"  git         {sha}{'  DIRTY' if dirty else '  clean'}")

    if args.dry_run:
        print("\n  would run:")
        for q in queries:
            print(f"    {q['query_id']}  [{q['category']:<20}] {q['text'][:60]}")
        est = len(queries) * 0.0059
        print(f"\n  estimated cost ~${est:.2f}  (~Rs {est*88:.0f})")
        print("  dry run - nothing sent")
        return

    if dirty and not args.allow_dirty:
        raise SystemExit(
            "\n  REFUSING TO RUN: you have uncommitted changes.\n"
            "  Every result records a git SHA. With uncommitted code that SHA does\n"
            "  not describe what ran, so the results cannot be reproduced.\n\n"
            "  Either:  git add -A && git commit -m 'checkpoint before eval'\n"
            "  Or:      re-run with --allow-dirty (the run is then marked dirty)\n"
        )

    ok, message = server_ready(args.url)
    print(f"  server      {message}")
    if not ok:
        raise SystemExit(f"\n  {message}")

    if args.resume:
        run_dir = args.resume
        done = already_done(run_dir)
        print(f"  resuming    {run_dir.name}  ({len(done)} already done)")
    else:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        run_dir = RUNS / f"eval_{stamp}_{sha}{'_DIRTY' if dirty else ''}"
        run_dir.mkdir(parents=True, exist_ok=True)
        done = set()

    summary_path = run_dir / "eval_summary.jsonl"
    todo = [q for q in queries if q["query_id"] not in done]
    print(f"  to run      {len(todo)}   (skipping {len(queries)-len(todo)})")
    print(f"  output      {run_dir.relative_to(ROOT)}\n")

    started = time.time()
    counts = {"ok": 0, "fail": 0}
    # One lock guards BOTH the file append and the counters. Without it two
    # workers finishing together can interleave a half-written line, and a
    # corrupt JSONL row loses that query's result silently.
    write_lock = threading.Lock()

    def run_one(idx_and_query: tuple[int, dict]) -> None:
        i, q = idx_and_query
        label = f"[{i}/{len(todo)}] {q['query_id']}"
        try:
            t0 = time.time()
            resp = requests.post(
                f"{args.url}/query",
                json={"query": q["text"], "query_id": q["query_id"]},
                timeout=args.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed = time.time() - t0

            audit = data.get("citation_audit") or {}
            row = {
                **{k: v for k, v in q.items()},
                "req_id": data.get("req_id"),
                "refused": data.get("refused"),
                "confidence": data.get("confidence"),
                "n_citations": len(data.get("citations") or []),
                "retrieved_docs": sorted({c.get("source") for c in (data.get("citations") or [])}),
                "citation_audit": audit,
                "latency_s": round(elapsed, 1),
                "error": None,
            }
            line = (
                f"  {label:<18} {elapsed:5.1f}s  conf={data.get('confidence')}"
                f"  ungrounded={audit.get('ungrounded_rate', '-')}"
                f"  {'REFUSED' if data.get('refused') else ''}"
            )
            outcome = "ok"
        except Exception as exc:
            row = {**q, "error": f"{type(exc).__name__}: {exc}", "refused": None}
            line = f"  {label:<18} FAILED  {type(exc).__name__}: {str(exc)[:70]}"
            outcome = "fail"

        with write_lock:
            counts[outcome] += 1
            print(line, flush=True)
            with summary_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    work = list(enumerate(todo, 1))
    if args.workers <= 1:
        for item in work:
            run_one(item)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(run_one, work))

    ok_count, fail_count = counts["ok"], counts["fail"]
    elapsed = time.time() - started
    print(f"\n  done in {elapsed/60:.1f} min   {ok_count} ok, {fail_count} failed")
    print(f"  summary  {summary_path.relative_to(ROOT)}")
    print(f"  detailed records are in the newest runs/*/queries.jsonl written by the server")


if __name__ == "__main__":
    main()
