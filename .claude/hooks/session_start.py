#!/usr/bin/env python3
"""SessionStart hook — inject current project state into every new session.

CLAUDE.md carries the *static* context automatically. This carries the
*changing* context: what happened last, and what's still unresolved.
Those are the parts that go stale, and the parts that were lost when this
project was picked up again after six months.

Output contract: a single JSON object on stdout with
hookSpecificOutput.additionalContext — that string is injected into the
model's context at session start.

Kept deliberately short. A hook that dumps 200 lines into every session
gets ignored, and an ignored reminder is worse than no reminder.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKLOG = ROOT / "docs" / "WORKLOG.md"
QUESTIONS = ROOT / "docs" / "OPEN_QUESTIONS.md"

MAX_NEXT_LINES = 12
MAX_QUESTIONS = 8


def latest_worklog_entry() -> str:
    """Heading of the most recent dated entry, plus its '### Next' block."""
    if not WORKLOG.exists():
        return ""
    lines = WORKLOG.read_text(encoding="utf-8", errors="replace").splitlines()

    start = next((i for i, l in enumerate(lines) if l.startswith("## 20")), None)
    if start is None:
        return ""

    out = [lines[start].removeprefix("## ").strip()]

    # Find the '### Next' block inside this entry only.
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):          # next entry begins
            break
        if lines[i].strip().lower() == "### next":
            for nxt in lines[i + 1:]:
                if nxt.startswith("#") or nxt.strip() == "---":
                    break
                if nxt.strip():
                    out.append(nxt.rstrip())
                if len(out) > MAX_NEXT_LINES:
                    break
            break
    return "\n".join(out)


def open_questions() -> list:
    """Headings of unresolved questions — strictly between '# Open' and '# Resolved'.

    Anchoring on '# Open' skips the template block at the top of the file,
    which otherwise leaks its 'QNN' placeholder into every session.
    """
    if not QUESTIONS.exists():
        return []
    found, in_open = [], False
    for line in QUESTIONS.read_text(encoding="utf-8", errors="replace").splitlines():
        # Exact match: the file's own title is "# Open Questions", and a
        # startswith() check would match it and swallow the template block.
        if line.strip() == "# Open":
            in_open = True
            continue
        if line.strip() == "# Resolved":
            break
        if in_open and line.startswith("## Q"):
            found.append(line.removeprefix("## ").strip())
    return found[:MAX_QUESTIONS]


def main() -> None:
    parts = ["## Project state (injected by SessionStart hook)"]

    entry = latest_worklog_entry()
    if entry:
        parts.append(f"**Last session — docs/WORKLOG.md**\n{entry}")

    questions = open_questions()
    if questions:
        listed = "\n".join(f"- {q}" for q in questions)
        parts.append(f"**Unresolved — docs/OPEN_QUESTIONS.md**\n{listed}")

    parts.append(
        "Read `docs/STATE.md` before substantive work. Documentation is "
        "non-negotiable on this project: end the session by appending to "
        "`docs/WORKLOG.md`. See CLAUDE.md for the protocol."
    )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n\n".join(parts),
            },
            "suppressOutput": True,
        },
        sys.stdout,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A broken hook must never block a session from starting.
        json.dump({"suppressOutput": True}, sys.stdout)
