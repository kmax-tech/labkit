"""codex-hook — Codex lifecycle adapter for labkit's shared checks.

Codex sends canonical Bash and apply_patch events as JSON on stdin.
Pre-run and stop use exit 2 with stderr feedback; post-change returns
additionalContext. Stop keeps the shared once-per-turn continuation limit.
Contract: https://learn.chatgpt.com/docs/hooks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from labkit.formats import console
from labkit.gates import agent_hooks

EVENTS = {"pre-run": "PreToolUse", "post-change": "PostToolUse", "stop": "Stop"}


def codex_event(value: object, action: str) -> dict[str, object]:
    """Validate a Codex event and supply the shared checks' directory fields.

    Returns a copy; the session id and transcript path remain Codex's.
    Explicit project_dir prevents an inherited CLAUDE_PROJECT_DIR from
    selecting a different repository. Raises ValueError naming an invalid
    field, including an event name that disagrees with the requested action.
    """
    if not isinstance(value, dict):
        raise ValueError("hook event must be a JSON object")
    if value.get("hook_event_name") != EVENTS[action]:
        raise ValueError(f"hook_event_name must be {EVENTS[action]!r} for {action}")
    for field in ("session_id", "cwd"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ValueError(f"{field} must be a non-empty string")
    if not Path(value["cwd"]).is_absolute():
        raise ValueError("cwd must be an absolute path")
    transcript = value.get("transcript_path")
    if transcript is not None and not isinstance(transcript, str):
        raise ValueError("transcript_path must be a string or null")
    if action == "stop":
        if not isinstance(value.get("stop_hook_active"), bool):
            raise ValueError("stop_hook_active must be a boolean")
    else:
        _validate_tool_input(value)
    return {**value, "project_dir": value["cwd"], "hook_command": "codex-hook"}


def _validate_tool_input(value: dict[str, object]) -> None:
    """Validate canonical tool names and the command used by shell and patch."""
    tool_name = value.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("tool_name must be a non-empty string")
    tool_input = value.get("tool_input")
    if tool_name in {"Bash", "apply_patch"}:
        if not isinstance(tool_input, dict) or not isinstance(
            tool_input.get("command"), str
        ):
            raise ValueError("tool_input.command must be a string")


def main(argv: list[str]) -> int:
    """Read one Codex event and run its gate; invalid input returns 2.

    Help and unknown actions do not read stdin. The checks may record stop
    bases, session logs and content caches, as described in agent_hooks.
    """
    if not argv or argv[0] in ("-h", "--help"):
        return console.usage(
            "codex-hook",
            "usage: codex-hook pre-run | post-change | stop (hook JSON on stdin)",
            asked=bool(argv),
        )
    if len(argv) != 1 or argv[0] not in EVENTS:
        console.refuse("codex-hook", f"expected one of {', '.join(EVENTS)}")
        return 2
    action = argv[0]
    try:
        event = codex_event(json.loads(sys.stdin.read()), action)
    except ValueError as exc:
        console.refuse("codex-hook", str(exc))
        return 2
    if action == "pre-run":
        return agent_hooks.pre_run(event)
    if action == "post-change":
        return agent_hooks.post_change(event)
    return agent_hooks.stop(event)


def cli() -> None:
    """Console entry point of codex-hook."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
