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


## 2026-10-31 — Refuse unresolved relative Python scripts

**Problem.** An invoked relative Python script missing from the session
cwd was treated as no measurement. Its actual tool workdir is absent from
the event. Searching the repository for the basename would guess an area,
including when several areas use the same stamped filename.

**Solution.** The Codex adapter requires relative invoked Python scripts
to resolve using the shared command parser. A missing script raises
`UnresolvedScriptError`; the adapter returns exit 2 with an absolute `cd`
or absolute script-path retry. This checks missing context, not scientific
intent. The Claude adapter keeps its existing behavior. The existing
throwaway flags remain exempt per simple command. Even ordinary helpers
need the explicit directory when their relative path cannot be found.
`LABKIT_PREFLIGHT=skip` does not waive the missing context check.

**Verification.** Installed Codex CLI 0.166.0, the same local Responses SSE
method as above, isolated temporary project/config directories and hook
input/result capture. The bare `python 01_measure.py` with tool workdir
set to the frozen area's scripts produced only the command in tool_input
and the session root as cwd again; it was refused with exit 2. Explicit
`cd` and an absolute measurement path both reached the frozen area's
preflight and were refused for its blockers. A non-measuring helper at an
absolute path passed, executed and wrote a marker whose contents were
checked. `apply_patch` post-change feedback, stop continuation `[2, 0]`
and the clean stop `[0]` also passed. No external model was called.

**Remaining limit.** An existing same-name script at the session-relative
path cannot be distinguished from a different script in an omitted
workdir. Relative `cd` also depends on that initial directory. The retry
therefore names absolute paths. Codex must supply the effective tool
directory to close this ambiguity transparently; this change closes the
observed unresolved-script case only. Existing shell-recognition limits
remain; the hook does not interpret arbitrary shell programs.
