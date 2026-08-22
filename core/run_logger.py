"""Structured per-query logging — Prof. Joshi's item 2, and the unblocker.

WHY THIS EXISTS
    Today the pipeline calls print(). Print goes to a terminal window and is
    gone when it closes. The system has never recorded a single retrieval
    score, which is why docs/DATAFLOW.md contains illustrative numbers instead
    of measured ones, and why the architecture PDF's section 8 has hedged
    values like "~0.40" rather than figures.

    Every number in the paper has to come from somewhere permanent. This is
    that somewhere.

WHAT IT WRITES
    runs/<timestamp>_<git-sha>/
        meta.json      one file: when, which commit, which models, dirty tree?
        queries.jsonl  one LINE per query, complete

    JSONL (one JSON object per line) rather than one big JSON file because:
      - appending never rewrites what is already there
      - a crash at query 63 leaves queries 1-62 perfectly valid
      - pandas.read_json(path, lines=True) gives you a table in one call
      - it is plain text, so grep and git diff work

THE FOUR FLAGS THAT MATTER MOST
    intake.fallback_used                  the Intake LLM failed and defaults
                                          were substituted, silently
    router.decision_path                  WHICH rule chose the corpus, not
                                          just which corpus
    retrieval.filter_fallback_fired       the corpus filter was silently
                                          dropped (causes the CrPC drift)
    confidence.entity_coverage_default_used   the free 0.30 was granted

    Each one currently fails without any signal at all. See docs/GAPS.md.

USAGE
    from core.run_logger import get_run_logger

    rec = get_run_logger().new_record(query_id="Q042", query_raw=q)
    rec.set("intake", scenario=..., fallback_used=False)
    rec.set("router", target_corpora=["BNS"], decision_path="act_map")
    ...
    rec.finish()          # writes the line; safe to call once
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"

# Stage buckets a record can hold. Anything else raises, so a typo in a stage
# name fails loudly instead of writing data into a key nobody reads.
STAGES = (
    "language",
    "intake",
    "date",
    "router",
    "mapper",
    "retrieval",
    "confidence",
    "answer",
    "verifier",
)


def _git(*args: str) -> str:
    """Run a git command, returning '' if git is unavailable or errors."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:
        return ""


def git_sha() -> str:
    return _git("rev-parse", "--short", "HEAD") or "nogit"


def git_dirty() -> bool:
    """True if there are uncommitted changes.

    A dirty tree means the recorded SHA does not fully describe the code that
    produced the numbers. Recorded, not blocked — run_eval.py is where it
    becomes a hard stop.
    """
    return bool(_git("status", "--porcelain"))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class QueryRecord:
    """One query's worth of data, accumulated across pipeline stages."""

    def __init__(self, logger: "RunLogger", query_id: str, query_raw: str):
        self._logger = logger
        self._written = False
        self._started = datetime.now(timezone.utc)
        self.data: dict[str, Any] = {
            "req_id": uuid.uuid4().hex[:12],
            "timestamp": now_iso(),
            "query_id": query_id,
            "query_raw": query_raw,
            "git_sha": logger.sha,
            **{stage: {} for stage in STAGES},
        }

    def set(self, stage: str, **fields: Any) -> "QueryRecord":
        """Merge fields into a stage bucket. Call as often as you like."""
        if stage not in STAGES:
            raise KeyError(f"unknown stage {stage!r}; expected one of {STAGES}")
        self.data[stage].update(fields)
        return self

    def error(self, stage: str, exc: BaseException) -> "QueryRecord":
        """Record that a stage blew up, without losing the rest of the record."""
        return self.set(stage, error=f"{type(exc).__name__}: {exc}")

    def finish(self) -> dict[str, Any]:
        """Write the record. Idempotent — a second call is a no-op."""
        if self._written:
            return self.data
        elapsed = datetime.now(timezone.utc) - self._started
        self.data["total_latency_ms"] = int(elapsed.total_seconds() * 1000)
        self._logger._append(self.data)
        self._written = True
        return self.data


class RunLogger:
    """Owns one run directory and appends records to it."""

    def __init__(self, run_dir: Path | None = None, config: dict | None = None):
        self.sha = git_sha()
        self.dirty = git_dirty()
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        self.dir = run_dir or (RUNS_DIR / f"{stamp}_{self.sha}")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.jsonl = self.dir / "queries.jsonl"
        self._write_meta(config or {})

    def _write_meta(self, config: dict) -> None:
        meta = {
            "started": now_iso(),
            "git_sha": self.sha,
            "git_dirty": self.dirty,
            "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "gen_model": os.getenv("MODEL_NAME", ""),
            "embed_model": os.getenv("EMBED_MODEL", ""),
            "api_base": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "config": config,
        }
        (self.dir / "meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    def new_record(self, query_id: str, query_raw: str) -> QueryRecord:
        return QueryRecord(self, query_id, query_raw)

    def _append(self, record: dict) -> None:
        with self.jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def count(self) -> int:
        if not self.jsonl.exists():
            return 0
        with self.jsonl.open(encoding="utf-8") as fh:
            return sum(1 for _ in fh)


_ACTIVE: RunLogger | None = None


def get_run_logger(config: dict | None = None) -> RunLogger:
    """Process-wide logger. First call creates the run directory."""
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = RunLogger(config=config)
    return _ACTIVE


def start_new_run(config: dict | None = None) -> RunLogger:
    """Force a fresh run directory — used by scripts/run_eval.py per sweep."""
    global _ACTIVE
    _ACTIVE = RunLogger(config=config)
    return _ACTIVE
