#!/usr/bin/env python3
"""Backfill docs/SESSION_LOG.md from Claude Code's own transcripts.

WHY THIS EXISTS
    The session-logging hooks were installed on 2026-08-22, partway through a
    long working session. Everything before that — the original request, the
    architecture brainstorming, the research decisions, every plan — was never
    captured by them.

    Nothing was lost: Claude Code writes a full JSONL transcript of every
    session to ~/.claude/projects/<project>/<session-id>.jsonl. This script
    reads those transcripts and reconstructs the raw trail retroactively, so
    SESSION_LOG.md contains the whole history rather than only what happened
    after the hooks existed.

WHAT IT EXTRACTS
    - every user prompt (what was asked)
    - every Bash command run, with its description (what was done)

    Assistant prose is deliberately excluded: it lives in the transcripts, and
    including it would make this file roughly 10x larger and unreadable.

USAGE
    python scripts/backfill_session_log.py            # all sessions
    python scripts/backfill_session_log.py --dry-run  # count, write nothing

Safe to re-run: it rewrites the file from scratch each time rather than
appending duplicates.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "SESSION_LOG.md"
TRANSCRIPTS = Path.home() / ".claude" / "projects" / "C--Users-uniya-legal-mvp"

MAX_PROMPT_CHARS = 4000
MAX_COMMAND_CHARS = 600

HEADER = """# Session Log

Raw, append-only trail of prompts and commands.

Entries from 2026-08-22 onward are written live by
`.claude/hooks/session_log.py`. Everything before that was reconstructed from
Claude Code's own transcripts by `scripts/backfill_session_log.py`, because
the hooks did not exist yet.

Not curated — see `WORKLOG.md` for the readable version.

"""


def text_of(content) -> str:
    """A message's content is either a string or a list of typed blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def truncate(s: str, limit: int) -> str:
    s = s.strip()
    return s if len(s) <= limit else s[:limit] + f"\n… [truncated, {len(s)-limit} more chars]"


def stamp(raw: str | None) -> str:
    if not raw:
        return "unknown time"
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        return raw


def is_noise(text: str) -> bool:
    """Skip harness-generated user turns that are not things Udita typed."""
    t = text.strip()
    if not t:
        return True
    markers = (
        "<system-reminder>",
        "[SYSTEM NOTIFICATION",
        "<task-notification>",
        "<local-command-",
        "Caveat: The messages below were generated",
        "tool_use_id",
    )
    return any(m in t[:400] for m in markers)


def harvest(path: Path) -> list[dict]:
    """Pull prompts and Bash commands out of one transcript, in order."""
    events: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue

            rtype = rec.get("type")
            msg = rec.get("message") or {}
            ts = rec.get("timestamp")

            if rtype == "user":
                body = text_of(msg.get("content"))
                if not is_noise(body):
                    events.append({"kind": "prompt", "ts": ts, "text": body})

            elif rtype == "queue-operation" and rec.get("operation") == "enqueue":
                # Messages sent WHILE a turn is running are recorded here, not
                # as type "user". Missing these loses every mid-turn steer —
                # e.g. the Sarvam question and "also use sub agents".
                body = rec.get("content") or ""
                if isinstance(body, str) and not is_noise(body):
                    events.append({"kind": "prompt", "ts": ts, "text": body})

            elif rtype == "assistant":
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "tool_use"
                            and block.get("name") in ("Bash", "PowerShell")
                        ):
                            inp = block.get("input") or {}
                            events.append(
                                {
                                    "kind": "cmd",
                                    "ts": ts,
                                    "text": inp.get("command", ""),
                                    "desc": inp.get("description", ""),
                                }
                            )
    return events


def render(events: list[dict]) -> str:
    out = [HEADER]
    for e in events:
        if e["kind"] == "prompt":
            out.append(
                f"\n### {stamp(e['ts'])} · prompt\n\n{truncate(e['text'], MAX_PROMPT_CHARS)}\n"
            )
        else:
            if not e["text"].strip():
                continue
            out.append(
                f"\n`{stamp(e['ts'])}` · **cmd** — {e.get('desc','')}\n"
                f"```bash\n{truncate(e['text'], MAX_COMMAND_CHARS)}\n```\n"
            )
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report counts, write nothing")
    args = ap.parse_args()

    if not TRANSCRIPTS.exists():
        print(f"No transcript directory at {TRANSCRIPTS}")
        return

    files = sorted(TRANSCRIPTS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    events: list[dict] = []
    for f in files:
        got = harvest(f)
        print(f"  {f.name[:12]}…  {len(got):>4} events  ({f.stat().st_size/1_000_000:.1f} MB)")
        events.extend(got)

    prompts = sum(1 for e in events if e["kind"] == "prompt")
    cmds = sum(1 for e in events if e["kind"] == "cmd")
    print(f"\ntotal: {prompts} prompts, {cmds} commands")

    if args.dry_run:
        print("dry run — nothing written")
        return

    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(render(events), encoding="utf-8")
    print(f"wrote {LOG.relative_to(ROOT)}  ({LOG.stat().st_size/1000:.0f} KB)")


if __name__ == "__main__":
    main()
