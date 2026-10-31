# Codex live hooks

`labkit-hooks install` writes the installed package's git hooks,
`.claude/settings.json` and `.codex/hooks.json`. It preserves other keys
and foreign handlers, including handlers in the same matcher group.
`labkit-hooks check` checks their contents and git's `core.hooksPath`;
it does not establish whether a running agent loaded or trusted them.

Install labkit in the repository's `.venv`, then run:

```sh
.venv/bin/labkit-hooks install
.venv/bin/labkit-hooks check
```

Start Codex in the repository, trust the project and use `/hooks` to review
and trust the new or changed definitions. A changed definition needs review
again. The installer neither modifies user-wide settings nor grants trust.
Codex commands name the repository's `.venv/bin/codex-hook` by absolute
path; reinstall after moving the repository or raising its labkit pin.

## Event contract

The [official Codex hook contract](https://learn.chatgpt.com/docs/hooks)
defines the configuration, canonical tool names and stdin/stdout protocol.
The installer generates the configuration; it is not copied here.

| Codex event | Matcher | Command | Effect |
|---|---|---|---|
| `PreToolUse` | `^Bash$` | `codex-hook pre-run` | Keeps the session's stop base before a shell command. Recognized measurement scripts get the same registration/preflight checks as Claude Code; a frozen area's blocker denies the call with exit 2 and stderr feedback. |
| `PostToolUse` | `^(Bash\|apply_patch)$` | `codex-hook post-change` | Checks changed protocols, notes, reports and evidence using git status. Returns `hookSpecificOutput.additionalContext`, exit 0. |
| `Stop` | none | `codex-hook stop` | Checks the changed and committed state before the turn ends. A blocker returns exit 2 and stderr feedback, asking Codex to continue once. |

Codex maps shell and `exec_command` calls to `Bash`; both shell and patch
events carry `tool_input.command`. The adapter validates event names,
session ids, working directories and the input fields it uses. Codex's
`cwd` selects the repository even when `CLAUDE_PROJECT_DIR` was inherited.
Its session id and transcript path remain unchanged in labkit's session log
(`claude-hook sessions` reads the shared log for either harness).

`gates/agent_hooks.py` owns the checks, stop bases, session log and content
cache. `gates/claude_hooks.py` and `gates/codex_hooks.py` are the command
adapters. There is one implementation of the preflight, evidence and report
obligations, with the same repeat-cost rules and the same stop time budget.

## Limitations and verification

These hooks add feedback and bounded continuation to the existing gates.
They do not judge whether an announced task was completed. In particular,
an exploration with no declared result may end; the stop checks explicit
result declarations, affected reports and audit evidence. After one
continuation (`stop_hook_active`), findings remain visible but the turn may
end. The next turn checks them again. `SessionEnd` is not a substitute for
this turn-end gate.

Tool hooks cover the Codex paths that emit those events. Specialized paths
can opt out, and input sent through `write_stdin` does not trigger another
pre-tool check. Hook trust, disabled hooks or a harness terminating a hook
can also prevent enforcement. Git gates and the explicit labkit commands
remain available independently.

**Codex CLI omits `exec_command.workdir` from its canonical hook input
and reports the session directory as `cwd`** (observed in 0.165.0 and 0.166.0).
The Codex adapter therefore refuses an invoked relative Python script
that cannot be found from that directory and any explicit `cd` in the
command. The feedback asks for an absolute script path or an explicit
`cd` to the absolute scripts directory. This refusal states missing
execution context; it does not assert a preflight violation in an
unidentified area. It also applies to ordinary helper scripts whose
paths cannot be resolved. Reads such as `sed … file.py` and the existing
throwaway stages (`--probe`, `--show`, etc.) remain exempt; flags free
only their own simple command. `LABKIT_PREFLIGHT=skip` does not bypass
this directory check.

For example, replace `python 01_measure.py` plus a separate `workdir`
with `cd /absolute/repo/experiments/01-x/scripts && python 01_measure.py`,
or `python /absolute/repo/experiments/01-x/scripts/01_measure.py`.
The normal preflight checks then apply to the resolved measurement.

This closes the observed missing-script path, not every working-directory
ambiguity: if another script exists at the session-relative path, the
hook cannot distinguish it from the one in an omitted workdir. A relative
`cd` also depends on the omitted initial directory; an absolute `cd`
avoids that ambiguity. No repository search guesses the intended area.
Full transparent coverage requires Codex to supply the effective tool
working directory. The stop's repository-wide checks still run.

The shared transcript fallback reads only the first record's timestamp.
Codex does not promise a stable transcript format: a missing usable start
and missing stop base hold the stop instead of declaring unchecked commits
clean. Foreground process survival across session shutdown is a separate
integration question; this port does not establish it.

Adapter tests exercise Codex events with the shared stop contract and its
passing twins. A real Codex CLI 0.165.0 run against a local Responses test
server exercised shell refusal, allowed commands, `apply_patch` context,
stop continuation and its clean twin. It also reproduced the working
directory limit above. Evidence and method:
[runtime probe](notes/2026-10-30-codex-hooks.md).
