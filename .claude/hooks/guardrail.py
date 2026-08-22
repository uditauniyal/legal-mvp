#!/usr/bin/env python3
"""PreToolUse guardrail — turns the two ⚠ rules in CLAUDE.md into enforcement.

CLAUDE.md carries two warnings that, if ignored, cost real work:

  1. `fix_corpus_tags.py` patches the Qdrant DATABASE instead of the code in
     ingest/chunk.py. Running it makes the index and the source disagree, and
     any later re-ingest silently reverts to broken corpus tags. This is the
     exact mistake that hid the tagging defect for six months.

  2. `pip install -r requirements.txt` currently installs none of this
     project's real dependencies and pulls ~2.5GB of unrelated computer-vision
     packages. It would damage a working venv.

A warning in a markdown file is advice. This makes it a wall.

Blocks by returning permissionDecision "deny" with a reason, which Claude Code
surfaces instead of running the command.
"""
import json
import re
import sys

# (compiled pattern, short label, why it is blocked)
BLOCKED = [
    (
        re.compile(r"\bfix_corpus_tags\.py\b"),
        "fix_corpus_tags.py",
        "This patches the Qdrant database instead of ingest/chunk.py, making the "
        "index and the code disagree. Any re-ingest silently reverts to broken "
        "corpus tags. Fix guess_corpus() in the code and re-ingest instead. "
        "See docs/GAPS.md #4.",
    ),
    (
        re.compile(r"pip\s+install\b[^\n]*-r\s+\S*requirements\.txt"),
        "pip install -r requirements.txt",
        "requirements.txt lists none of this project's actual dependencies and "
        "pulls ~2.5GB of unrelated CV packages (torch, ultralytics, opencv). It "
        "would damage the working venv. Regenerate it first. See docs/GAPS.md #13.",
    ),
]


def main() -> None:
    payload = json.load(sys.stdin)

    if payload.get("tool_name") not in ("Bash", "PowerShell"):
        json.dump({"suppressOutput": True}, sys.stdout)
        return

    command = (payload.get("tool_input") or {}).get("command", "") or ""

    for pattern, label, reason in BLOCKED:
        if pattern.search(command):
            json.dump(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"BLOCKED: {label}\n\n{reason}",
                    }
                },
                sys.stdout,
            )
            return

    json.dump({"suppressOutput": True}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail open — a broken guardrail must never block ordinary work.
        try:
            json.dump({"suppressOutput": True}, sys.stdout)
        except Exception:
            pass
