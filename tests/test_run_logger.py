"""Tests for the per-query run logger (core/run_logger.py)."""

import json
import shutil

import pytest

from core.run_logger import RunLogger


@pytest.fixture
def logger(tmp_path):
    log = RunLogger(run_dir=tmp_path / "run")
    yield log
    shutil.rmtree(log.dir, ignore_errors=True)


def test_creates_run_dir_and_meta(logger):
    assert logger.dir.exists()
    meta = json.loads((logger.dir / "meta.json").read_text(encoding="utf-8"))
    assert "git_sha" in meta and "started" in meta


def test_writes_one_line_per_record(logger):
    for i in range(3):
        logger.new_record(f"Q{i}", "text").finish()
    assert logger.count() == 3
    lines = logger.jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert all(json.loads(l)["query_id"].startswith("Q") for l in lines)


def test_finish_is_idempotent(logger):
    """A double-write would duplicate a query in the evaluation."""
    rec = logger.new_record("Q1", "text")
    rec.finish()
    rec.finish()
    assert logger.count() == 1


def test_unknown_stage_raises(logger):
    """A typo'd stage name must fail loudly, not write data nobody reads."""
    with pytest.raises(KeyError):
        logger.new_record("Q1", "t").set("retreival", x=1)   # note the typo


def test_set_merges_rather_than_replaces(logger):
    rec = logger.new_record("Q1", "t")
    rec.set("retrieval", n_retrieved=15)
    rec.set("retrieval", filter_fallback_fired=True)
    data = rec.finish()
    assert data["retrieval"] == {"n_retrieved": 15, "filter_fallback_fired": True}


def test_error_is_captured_without_losing_the_record(logger):
    rec = logger.new_record("Q1", "t")
    try:
        raise ValueError("boom")
    except Exception as e:
        rec.error("intake", e)
    data = rec.finish()
    assert "ValueError: boom" in data["intake"]["error"]
    assert logger.count() == 1


def test_all_stage_buckets_present(logger):
    """Every record has the same shape, so pandas can read the file as a table."""
    data = logger.new_record("Q1", "t").finish()
    for stage in ("intake", "router", "retrieval", "confidence", "answer", "verifier"):
        assert stage in data
