"""claude-hook — Claude Code adapter for labkit's shared live-hook checks.

Reads Claude Code hook JSON from stdin. Pre-run and stop return exit 2
with findings on stderr to block; post-change returns additionalContext.
The shared checks also provide the git gate and session-log commands.
"""

import json
import sys

from labkit.formats import console
from labkit.gates import agent_hooks


def main(argv: list[str]) -> int:
    """Command line of `claude-hook`: dispatch the hook named in argv, the event JSON on stdin."""
    if not argv or argv[0] in ("-h", "--help"):
        text = (
            (__doc__ or "").strip().splitlines()[0] + "\n"
            "usage: claude-hook pre-run | post-change | stop   (hook event JSON on stdin)\n"
            "       claude-hook undecided <paths…>\n"
            "       claude-hook sessions [--run RUN_ID]\n"
            "exit codes: pre-run 0 or 2 (block); stop 0 or 2 (keep working); "
            "post-change 0; undecided 0 or 1 (findings); sessions 0 or 1 (none "
            "made the run); usage error 2"
        )
        return console.usage("claude-hook", text, asked=bool(argv))
    if argv[0] == "sessions":
        return agent_hooks.sessions(argv[1:])
    if argv[0] == "undecided":
        return agent_hooks.undecided(argv[1:])
    event = json.loads(sys.stdin.read() or "{}")
    if argv[0] == "pre-run":
        return agent_hooks.pre_run(event)
    if argv[0] == "post-change":
        return agent_hooks.post_change(event)
    if argv[0] == "stop":
        return agent_hooks.stop(event)
    console.refuse("claude-hook", f"unknown event {argv[0]!r}")
    return 2


def cli() -> None:
    """Console entry point of `claude-hook`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
