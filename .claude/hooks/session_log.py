#!/usr/bin/env python3
"""Append-only raw session trail, plus the per-turn teaching rule.

Handles two hook events with one script:
  UserPromptSubmit  -> log what Udita asked, AND re-inject the teaching rule
  PostToolUse/Bash  -> log what command was run

WHY THE RULE IS INJECTED HERE AND NOT LEFT IN CLAUDE.md
  CLAUDE.md loads once, at session start. Over a long session the assistant
  drifts from it — Udita had to restate "explain from basics, define every
  term" roughly fifteen times in a single session despite it being written in
  CLAUDE.md, in project memory, and in docs/.

  A rule that loads once cannot fix a failure that recurs. UserPromptSubmit
  fires on EVERY turn, and hookSpecificOutput.additionalContext is injected
  straight into the model's context for that turn. So the rule arrives fresh
  each time instead of decaying.

Writes to docs/SESSION_LOG.md. This is the RAW trail — everything, in order,
timestamped. It is deliberately not readable as a narrative; docs/WORKLOG.md
is the curated version. The raw trail exists so that half-formed ideas,
things that were tried, and questions asked all survive, because those are
exactly what gets lost between sessions.

Only prompts and commands are logged, never assistant responses — those live
in Claude Code's own transcripts and would bloat this file roughly 10x.

Fails open: any exception exits silently rather than blocking the turn.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "docs" / "SESSION_LOG.md"

MAX_PROMPT_CHARS = 4000
MAX_COMMAND_CHARS = 600

HEADER = """# Session Log

Raw, append-only trail of prompts and commands. Written automatically by
`.claude/hooks/session_log.py`. Not curated — see `WORKLOG.md` for that.

"""


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def append(block: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not LOG.exists():
        LOG.write_text(HEADER, encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(block)


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [truncated, {len(text) - limit} more chars]"


TEACHING_RULE = """\
## Standing rule for this project — re-injected every turn

Udita has restated this ~15 times in one session. It has failed as a
CLAUDE.md entry. Treat it as binding.

**Define every term the first time you use it, inline, in the same sentence
or the next one.** Do not assume prior knowledge — not of pricing units, not
of "open-weight", "tier", "lite", "token", "output token", "provider",
"endpoint", "reasoning model", "ablation", "AUROC", or anything else.

Then explain twice: **plain English first, technical detail second.**

Checkable failures she can point at:
1. A term used without being defined  -> violation
2. Code produced before an explanation -> violation
3. More than one file written before stopping -> violation
4. Jargon-dense prose when a worked example would do -> violation

Prefer: short sentences · concrete numbers from HER system · worked examples
before abstractions · a table over a paragraph.

She is a 3rd-year B.Tech student doing this solo for a conference paper.
She is capable, not experienced. Build up; never talk down.
"""


def main() -> None:
    payload = json.load(sys.stdin)
    event = payload.get("hook_event_name", "")

    if event == "UserPromptSubmit":
        prompt = payload.get("prompt") or payload.get("user_prompt") or ""
        if prompt.strip():
            append(
                f"\n### {timestamp()} · prompt\n\n"
                f"{truncate(prompt, MAX_PROMPT_CHARS)}\n"
            )
        # Inject the rule into THIS turn's context.
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": TEACHING_RULE,
                },
                "suppressOutput": True,
            },
            sys.stdout,
        )
        return

    elif event in ("PostToolUse", "PreToolUse"):
        if payload.get("tool_name") == "Bash":
            cmd = (payload.get("tool_input") or {}).get("command", "")
            desc = (payload.get("tool_input") or {}).get("description", "")
            if cmd.strip():
                append(
                    f"\n`{timestamp()}` · **cmd** — {desc}\n"
                    f"```bash\n{truncate(cmd, MAX_COMMAND_CHARS)}\n```\n"
                )

    json.dump({"suppressOutput": True}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never block a turn because logging failed.
        try:
            json.dump({"suppressOutput": True}, sys.stdout)
        except Exception:
            pass
