#!/usr/bin/env python3
"""Stop hook — remind to update the work log, but only when it's actually stale.

The Stop event fires every time Claude finishes a turn. A reminder on every
turn would be spam, and a spammed reminder gets ignored — which is worse than
no reminder at all.

So this stays silent unless it has something real to say: it compares the
mtime of the live source tree against docs/WORKLOG.md. If code has changed
more recently than the log, the log is behind and the reminder fires.
Otherwise the hook prints nothing.

Output contract: JSON on stdout. `systemMessage` is shown to the user.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKLOG = ROOT / "docs" / "WORKLOG.md"

# Only the live request path — debug scripts and orphaned trees don't count.
# See docs/FILE_STRUCTURE.md for why these specifically.
WATCHED_DIRS = ["agents", "ingest", "clients", "core", "report"]
WATCHED_FILES = ["app.py", "streamlit_app.py", "requirements.txt"]


def newest_source_change():
    """(mtime, relative path) of the most recently modified live source file."""
    newest = (0.0, None)
    candidates = []

    for d in WATCHED_DIRS:
        candidates.extend((ROOT / d).rglob("*.py"))
    for f in WATCHED_FILES:
        candidates.append(ROOT / f)

    for path in candidates:
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        mtime = path.stat().st_mtime
        if mtime > newest[0]:
            newest = (mtime, path.relative_to(ROOT).as_posix())
    return newest


def main() -> None:
    if not WORKLOG.exists():
        json.dump(
            {"systemMessage": "docs/WORKLOG.md is missing — the documentation "
                              "protocol in CLAUDE.md expects it."},
            sys.stdout,
        )
        return

    log_mtime = WORKLOG.stat().st_mtime
    src_mtime, src_path = newest_source_change()

    if src_path and src_mtime > log_mtime:
        json.dump(
            {
                "systemMessage": (
                    f"Docs are behind the code — {src_path} changed after "
                    f"docs/WORKLOG.md was last written.\n"
                    f"Before finishing: append to docs/WORKLOG.md, and update "
                    f"DECISIONS.md / OPEN_QUESTIONS.md if this turn produced a "
                    f"design choice or an unknown. (CLAUDE.md → Documentation protocol)"
                )
            },
            sys.stdout,
        )
        return

    # Nothing to say. Stay quiet.
    json.dump({"suppressOutput": True}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never block the turn from ending.
        json.dump({"suppressOutput": True}, sys.stdout)
