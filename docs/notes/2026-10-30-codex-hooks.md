# 2026-10-30 — Codex live-hook adapter and runtime limits

**Problem.** labkit installed Claude Code's hook configuration only. Codex
supports the same lifecycle event names and the same exit-2 feedback for
the three labkit hooks, but discovers its own config and canonicalizes tool
inputs. Duplicating the gate implementation would let the two drift.

**Solution.** Move the checks to `gates/agent_hooks.py`, retain the Claude
command adapter and add `codex-hook`. Generate both configs from one
installer. Codex gets an explicit project directory from its event so an
inherited `CLAUDE_PROJECT_DIR` cannot select a different repository.

**Runtime probe.** Installed Codex CLI 0.165.0, temporary git repositories
using the shared tests' protocol/run fixtures, an isolated Codex config
directory and a stdlib HTTP server speaking Responses SSE. The server
supplied deterministic tool calls and final messages; no external model
was called. The real Codex executable loaded the generated project config,
called a wrapper around the real adapter, and consumed its exit codes and
JSON. The wrapper recorded each stdin event and result. Project trust was
set for each fixture's canonical path; the hook-trust bypass was limited
to this isolated test configuration whose definitions were inspected.

Observed and asserted:

- A frozen area's measurement command with preflight blockers returned 2
  and was denied; a shell command without a run returned 0 and executed.
- `apply_patch` produced `PostToolUse` with `tool_name = "apply_patch"`
  and the patch under `tool_input.command`. Creating a measurement note
  returned the note check as `additionalContext`.
- A protocol declaring the wrong answering run produced a stop with exit
  2. Codex made another model request and sent a second stop event with
  `stop_hook_active = true`; it returned 0 while retaining the findings.
- The correct declared result passed the first stop, without continuation.
- Ephemeral sessions supplied `transcript_path = null`. A shell pre-hook
  kept the stop base, so both stop cases still checked the session state.

**Working directory limit.** A real `exec_command` with
`cmd = "python 01_measure.py"` and `workdir` set to the area's scripts
directory produced only `tool_input = {"command": "python 01_measure.py"}`
and the session root as `cwd`. The hook could not find that script from
the event and returned 0. The twin command
`cd experiments/01-x/scripts && python 01_measure.py` returned 2. Do not
infer full pre-run coverage from an adapter test whose event cwd already
equals the tool directory. Repository-relative or absolute script paths
and explicit `cd` make the recognized command checkable; the CLI would
need to supply the effective tool directory for transparent coverage.

The [official contract](https://learn.chatgpt.com/docs/hooks) warns that
specialized tool paths can bypass hooks and that transcript format is not
stable. The port establishes these observed paths, not all harness paths
or foreground-process survival across session shutdown.
