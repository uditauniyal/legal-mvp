#!/usr/bin/env python3
"""Mirror Claude Code's out-of-repo context INTO the repo.

WHY THIS EXISTS
    Two important things live outside the project directory:

      ~/.claude/plans/<name>.md                     the agreed build plan
      ~/.claude/projects/<project>/memory/*.md      persistent project memory

    Claude Code reads them automatically. Nothing else does. Open this repo in
    Cursor, VS Code, or hand it to another model (GLM, GPT, a reviewer) and
    that context is simply invisible — they would see the code and docs/ but
    not the plan that produced them, nor the working agreements, nor the
    supervisor's directive.

    This script copies both into docs/ so the repository is self-contained.

WHAT IT WRITES
    docs/PLAN.md             the current build plan, verbatim
    docs/PROJECT_CONTEXT.md  all memory files concatenated, with a header
                             explaining what memory is

Re-run after any plan or memory change. It overwrites rather than appends, so
running it twice is harmless.

USAGE
    python scripts/sync_context.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PLANS_DIR = Path.home() / ".claude" / "plans"
MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--Users-uniya-legal-mvp" / "memory"

PLAN_OUT = DOCS / "PLAN.md"
CONTEXT_OUT = DOCS / "PROJECT_CONTEXT.md"

STAMP = datetime.now().strftime("%Y-%m-%d %H:%M")


def sync_plan() -> bool:
    """Copy the most recently modified plan file into docs/PLAN.md."""
    if not PLANS_DIR.exists():
        print("  no plans directory found")
        return False

    plans = sorted(PLANS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not plans:
        print("  no plan files found")
        return False

    latest = plans[0]
    header = (
        f"<!-- MIRRORED FILE — do not edit here.\n"
        f"     Source: {latest}\n"
        f"     Synced: {STAMP} by scripts/sync_context.py -->\n\n"
        f"> **This is a mirror.** The live plan lives in Claude Code's plan\n"
        f"> directory and is copied here so the repository is self-contained\n"
        f"> for anyone reading it outside Claude Code.\n\n"
        f"---\n\n"
    )
    PLAN_OUT.write_text(header + latest.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  docs/PLAN.md  <- {latest.name}  ({PLAN_OUT.stat().st_size/1000:.0f} KB)")
    return True


def sync_memory() -> bool:
    """Concatenate every memory file into docs/PROJECT_CONTEXT.md."""
    if not MEMORY_DIR.exists():
        print("  no memory directory found")
        return False

    files = sorted(MEMORY_DIR.glob("*.md"))
    if not files:
        print("  no memory files found")
        return False

    parts = [
        "<!-- MIRRORED FILES — do not edit here.\n"
        f"     Source: {MEMORY_DIR}\n"
        f"     Synced: {STAMP} by scripts/sync_context.py -->\n\n"
        "# Project Context\n\n"
        "> **What this is.** Claude Code keeps persistent notes about this\n"
        "> project — who is working on it, how they want to be worked with,\n"
        "> the supervisor's directive, known defects, and cost measurements.\n"
        "> Those notes live outside the repository, so they are mirrored here\n"
        "> for anyone reading this project in another editor or handing it to\n"
        "> another model.\n>\n"
        "> Each section below is one memory file, verbatim.\n\n"
        "---\n"
    ]

    # Index first so a reader can navigate.
    index = MEMORY_DIR / "MEMORY.md"
    if index.exists():
        parts.append("\n## Index\n\n")
        parts.append(index.read_text(encoding="utf-8"))
        parts.append("\n---\n")

    for f in files:
        if f.name == "MEMORY.md":
            continue
        parts.append(f"\n## `{f.name}`\n\n")
        parts.append(f.read_text(encoding="utf-8").strip())
        parts.append("\n\n---\n")

    CONTEXT_OUT.write_text("".join(parts), encoding="utf-8")
    n = len(files) - (1 if index.exists() else 0)
    print(f"  docs/PROJECT_CONTEXT.md  <- {n} memory files  ({CONTEXT_OUT.stat().st_size/1000:.0f} KB)")
    return True


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    print("Syncing out-of-repo context into docs/ …")
    sync_plan()
    sync_memory()
    print("Done. The repository is now self-contained.")


if __name__ == "__main__":
    main()
