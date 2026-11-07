"""hook_pre_run — the pre-run hook: whether a shell command starts a run
(`run_scripts`, `executed_py`) and, for its area, preflight before a full
run or the registration note at low repeat cost (`before_run`, `pre_run`).
What it holds and why: `agent_hooks`' docstring, "pre-run".
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from labkit.gates.hook_session import keep_stop_base
from labkit.gates.hook_session import session_repo
from labkit.gates.hook_session import tell_context
from labkit.formats import (
    protocol_block,
    protocol_check,
    standard_contract,
)
from labkit.formats.gate import Findings, with_way_out
from labkit.formats.shell import segments
from labkit.gates import preflight
from labkit.formats.repo import (
    area_protocols,
    find_area,
)


# The stamps' throwaway stages (`standard_contract.NO_RUN_FLAGS`): none of
# them opens a run, and the probe is what comes BEFORE preflight, so gating
# it would invert the order.
THROWAWAY_FLAGS = re.compile(
    r"(^|\s)(" + "|".join(map(re.escape, standard_contract.NO_RUN_FLAGS)) + r")\b"
)


PY_TOKEN = re.compile(r"[\w./~-]+\.py")


# A .py file is RUN when an interpreter precedes it (`python`, `python3.12`,
# `.venv/bin/python`, flags between allowed), when it starts a command
# command (`./x.py`, first in a `shell.segments` command, after
# `runlog start --`, `nohup`, `time`, `exec`), never when it is merely named (`sed -n 1,5p lib/x.py`, a path in
# a heredoc): uniagent 2026-10-10, 85 of 272 hook lines in one session said
# "opens a run" about a lib module someone was reading.
INTERPRETER = re.compile(r"(?:^|/)python[\d.]*$")


SHELL_ASSIGNMENT = re.compile(r"[a-zA-Z_]\w*=.*", re.DOTALL)


COMMAND_PREFIX = {"--", "nohup", "time", "exec"}


STRIP = "\"'`();"  # around a token: quotes, parentheses, a trailing ;


# A script opens a run when its text calls runlog, or builds the `lanes.Lanes`
# whose `main` opens it (`run/lanes.py`) — the prompt skeleton names no runlog
# call of its own.
OPENS_RUN = re.compile(r"runlog\.(run|Run)\(|lanes\.Lanes\(")


PROTOCOL_IN_SCRIPT = re.compile(r"PROTOCOL-[\w.-]+\.md")


SKIP_TOKEN = "LABKIT_PREFLIGHT=skip"


class UnresolvedScriptError(ValueError):
    """A relative Python script cannot be located for the pre-run check."""


def before_run(script: Path, stop: Path | None) -> tuple[bool, str]:
    """What stands before SCRIPT opens a full run, as (blocks, line): the
    area above it (searched up to STOP), its protocol's head, then the
    lane's gate — the registration at low repeat cost
    (`_low_registration_line`), else preflight with the stations' findings
    as data. Blocks only a frozen protocol with preflight blockers — an
    unreadable head or a missing protocol never blocks here, they are
    notes; every
    other case is a note. Without a blocker the note carries every
    warning as the station told it, then the summary: the summary alone
    counts the warnings, and an open audit finding (`undecided in …`) is
    one of them. One script per call: `pre_run` held all of this inline
    (audit 2026-10-27, third, M7)."""
    area = find_area(script, stop)
    if area is None:
        return False, with_way_out(
            f"{script.name}: opens a run, but no PROTOCOL-*.md above it — unbound "
            f"runs keep no number (LAB-003 No run without an intent paragraph)",
            "stamp an area for it with `labkit-init exp <name> --kind …` and "
            "measure with the script stamped there",
        )
    protocol = protocol_named_in(script, area)
    texts = [
        p.read_text(encoding="utf-8")
        for p in ([protocol] if protocol else area_protocols(area))
    ]
    head = f"preflight {area.name}" + (
        f" --protocol {protocol.name}" if protocol else ""
    )
    try:
        heads = [protocol_block.head(t) for t in texts]
    except protocol_block.BlockError as exc:
        return False, with_way_out(
            f"{head}: protocol head unreadable — {exc}",
            "repair the head as the sentence says (`protocol-check <PROTOCOL> "
            "--contract` shows its fields)",
        )
    # which gate stands before a full run is the lane's answer: the
    # registration (low) or preflight (`standard_contract.lane`)
    if all(standard_contract.lane(h.repeat_cost).registration for h in heads):
        return False, _low_registration_line(head, texts)
    # the stations' findings as data, not the printed report read back:
    # tell=None collects only and prints nothing, and preflight_area tells
    # every line through it (`SilentCollectors` in tests/test_next_step.py)
    found = Findings(tell=None)
    rc = preflight.preflight_area(area, protocol, found)
    said = "\n".join(found.summary("preflight", "freezing"))
    if rc == 1 and any(h.frozen for h in heads):
        return True, (
            f"{head}: BLOCKED — the protocol is frozen and "
            f"preflight reports blockers:\n{said}"
        )
    if rc == 1:
        return False, (
            f"{head}: blockers, protocol not frozen (pilot) — "
            f"the full run will not start until they are fixed:\n{said}"
        )
    if rc == 2:
        return False, with_way_out(
            f"{head}: could not run preflight — no protocol to hold the area to",
            "name the protocol the script runs under "
            "(`runlog.run(..., protocol=PROTOCOL)`)",
        )
    if found.warned:
        # on exit 0 every finding is a warning; the summary names only their count
        told = "\n".join(f"  {f.line}" for f in found.found)
        return False, f"{head}:\n{told}\n{said}"
    return False, f"{head}: {said}"


def _low_registration_line(head: str, texts: list[str]) -> str:
    """The note for a full run at low repeat cost: no gate runs, and runlog
    refuses the run while a registration field of TEXTS is open."""
    missing = sorted(
        {m for t in texts for m in protocol_check.low_registration_missing(t)}
    )
    repeated = sorted({r for t in texts for r in protocol_check.repeated_findings(t)})
    if repeated:
        return (
            f"{head}: repeat cost low, but {'; '.join(repeated)} — runlog "
            f"refuses a full run until one copy is left: "
            f"{protocol_check.REPEATED_WAY_OUT}."
        )
    if not missing:
        return (
            f"{head}: repeat cost low — gate not run, the rerun is "
            f"the probe; registration written (LAB-017 The number of audits follows the cost tier)."
        )
    return (
        f"{head}: repeat cost low, but {', '.join(missing)} still "
        f"empty or a placeholder — runlog refuses a full run "
        f"until the registration is written (LAB-003 No run without an intent paragraph, LAB-017 The number of audits follows the cost tier)."
    )


def executed_py(words: list[str]) -> list[str]:
    """The .py paths one simple command (WORDS, a `shell.segments` entry)
    RUNS, in order: preceded by an interpreter (flags in between allowed),
    first in the command or after a prefix (`nohup`, `--`). A
    .py path that is only named — read, edited, inside a quoted `-c` string
    — is not among them. Leading shell variable assignments precede the
    command, so `NAME=value ./x.py` runs the script too."""
    tokens = words
    while tokens and SHELL_ASSIGNMENT.fullmatch(tokens[0]):
        tokens = tokens[1:]
    out: list[str] = []
    for i, raw in enumerate(tokens):
        tok = raw.strip(STRIP)
        if not PY_TOKEN.fullmatch(tok):
            continue
        j = i - 1
        while j >= 0 and tokens[j].startswith("-") and tokens[j] not in COMMAND_PREFIX:
            j -= 1  # interpreter flags: python -u x.py
        before = tokens[j].strip(STRIP) if j >= 0 else None
        runs = (
            before is None
            or before in COMMAND_PREFIX
            or INTERPRETER.search(before) is not None
        )
        if runs and (j == i - 1 or (before is not None and INTERPRETER.search(before))):
            out.append(tok)
    return out


def run_scripts(
    command: str, cwd: Path, *, require_resolved_scripts: bool = False
) -> list[Path]:
    """The .py files the command runs that open a run — resolved against the
    directory the command stands in at that point (a `cd` is followed) and
    existing; a segment with a throwaway flag (`THROWAWAY_FLAGS`) opens no
    run. Each simple command of the line
    (`shell.segments`) is judged on its own: read as one, `cd AREA && python
    scripts/01_measure.py` found no script, and one `--probe` freed every
    command of the line (audit 2026-10-15).

    With require_resolved_scripts, an unresolved relative script raises
    UnresolvedScriptError: Codex omits the tool's workdir, so absence at its session
    cwd cannot establish that no measurement runs. Absolute missing paths
    cannot be redirected by workdir. See docs/codex-hooks.md.
    """
    out = []
    here = cwd
    for seg in segments(command):
        if seg[0].strip(STRIP) == "cd":
            target = seg[1].strip(STRIP) if len(seg) > 1 else "~"
            here = here / os.path.expanduser(target)  # an absolute target replaces
            continue
        if THROWAWAY_FLAGS.search(" ".join(seg)):
            continue
        for tok in executed_py(seg):
            p = Path(os.path.expanduser(tok))
            if not p.is_absolute():
                p = here / p
                if require_resolved_scripts and not p.is_file():
                    raise UnresolvedScriptError(
                        f"cannot check Python script {tok!r} from {here}: "
                        "Codex does not supply exec_command.workdir to hooks. "
                        "Next: rerun with an explicit cd to the absolute scripts "
                        "directory in the command, or an absolute script path"
                    )
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if OPENS_RUN.search(text):
                out.append(p.resolve())
    return out


def protocol_named_in(script: Path, area: Path) -> Path | None:
    """The single PROTOCOL-*.md the script names, if it names exactly one
    and it exists in the area — the series case where preflight would
    otherwise refuse to pick."""
    names = sorted(set(PROTOCOL_IN_SCRIPT.findall(script.read_text(encoding="utf-8"))))
    if len(names) != 1:
        return None
    p = area / names[0]
    return p if p.is_file() else None


def pre_run(event: dict, *, require_resolved_scripts: bool = False) -> int:
    """Keep the stop base, resolve scripts, then check full runs before Bash.

    Preflight blockers refuse the command (exit 2). When
    require_resolved_scripts is true, unresolved relative Python scripts
    raise UnresolvedScriptError for the adapter to refuse with the
    explicit-directory retry; throwaway commands remain exempt. Other
    commands pass (exit 0).
    """
    if event.get("tool_name", "Bash") != "Bash":
        return 0
    repo = session_repo(event)
    if repo is not None:
        keep_stop_base(repo, event)
    command = (event.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    cwd = Path(event.get("cwd") or os.getcwd())
    scripts = run_scripts(
        command, cwd, require_resolved_scripts=require_resolved_scripts
    )
    if not scripts:
        return 0
    if SKIP_TOKEN in command:
        tell_context(
            "PreToolUse",
            f"{event.get('hook_command', 'claude-hook')} pre-run: {SKIP_TOKEN} — preflight "
            f"gate skipped on request; the transcript carries it.",
        )
        return 0

    # the walk to an area ends at the repo root, not at the project
    # directory: a session started in `<area>/scripts` must still find the
    # area above its script
    project = event.get("project_dir") or os.environ.get("CLAUDE_PROJECT_DIR")
    stop = repo if repo is not None else (Path(project) if project else None)
    blocked: list[str] = []
    notes: list[str] = []
    for script in scripts:
        blocks, line = before_run(script, stop)
        (blocked if blocks else notes).append(line)
    if blocked:
        sys.stderr.write("\n\n".join(blocked) + "\n")
        if notes:
            sys.stderr.write("\n" + "\n".join(notes) + "\n")
        return 2
    if notes:
        tell_context("PreToolUse", "\n\n".join(notes))
    return 0
