"""commands — labkit's steps as commands: `Command` (a step's name, its
kind and the shell line its builder renders, the one spelling every gate
prints) and the builders of each line (`adopt_command`, `withdraw_command`,
`audit_command`, …). Pure: a builder reads at most a protocol's head to
name a registered report, and writes nothing.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import TypedDict
from pathlib import Path

from labkit.formats import protocol_block
from labkit.formats.repo import (
    area_protocols,
    layout_root,
    own_path,
    shown,
)
from labkit.formats.runs import MEASURE_SCRIPT


#: the command that adopts a run — what every printed adoption line starts with
ADOPT_TOOL = "labkit-adopt"

#: where a lab repo's environment keeps its commands, as the repo root
#: reaches it: a printed line names a command there when it may be read
#: outside the activated environment — in a git hook, before the first
#: install, from inside a run
VENV_BIN = ".venv/bin"
#: the repo's interpreter, which runs the area's scripts and tests
VENV_PYTHON = f"{VENV_BIN}/python"
#: the line that installs this labkit's hooks into the repo, or installs
#: them again — the way out of every hook gap `install_hooks.check` names
HOOKS_INSTALL = f"{VENV_BIN}/labkit-hooks install"
#: the line that installs what `requirements.txt` pins into the repo's
#: environment
PIP_INSTALL = f"{VENV_BIN}/pip install -r requirements.txt"
#: the line that writes the lock, the environment every run records
LOCK_WRITE = f"{VENV_BIN}/pip freeze > requirements.lock"

#: the kinds of a `Command`, fixed here so a reader of a finding's step —
#: and the `--do` proposal, if it is ever triggered — has nothing to decide:
#: MECHANICAL runs one of labkit's own checked writers (each refuses on its
#: own and leaves the files as they were), CONTENT writes words labkit
#: cannot know, RESEARCH is a model call or a judgement, DESTRUCTIVE
#: discards or overwrites work (printed, never run)
MECHANICAL, CONTENT, RESEARCH, DESTRUCTIVE = (
    "mechanical",
    "content",
    "research",
    "destructive",
)
#: the names of labkit's steps as commands (`Command.name`) and the kind of each
ADOPT, INTO, WITHDRAW, WAIT, RENDER, CHECK = (
    "adopt",
    "into",
    "withdraw",
    "wait",
    "render",
    "check",
)
DISCUSS, HANDOVER = "discuss", "handover"
REPORTED_THROUGH = "reported-through"
MEASURE, AUDIT, DECIDE, REVIEW = "measure", "audit", "decide", "review"
RESTORE, INIT = "restore", "init"
STAGE = "stage"
FREEZE = "freeze"
FILL, NEXT = "fill", "next"
COMMAND_KIND = {
    ADOPT: MECHANICAL,
    INTO: MECHANICAL,
    WITHDRAW: MECHANICAL,
    WAIT: MECHANICAL,
    RENDER: MECHANICAL,
    CHECK: MECHANICAL,
    DISCUSS: CONTENT,
    HANDOVER: CONTENT,
    REPORTED_THROUGH: MECHANICAL,
    MEASURE: RESEARCH,
    AUDIT: RESEARCH,
    DECIDE: RESEARCH,
    REVIEW: RESEARCH,
    RESTORE: DESTRUCTIVE,
    INIT: DESTRUCTIVE,
    STAGE: MECHANICAL,
    FREEZE: MECHANICAL,
    FILL: MECHANICAL,
    NEXT: MECHANICAL,
}


@dataclass(frozen=True)
class Command:
    """One of labkit's steps as a command: NAME (a key of `COMMAND_KIND`),
    its `kind` from that table, and LINE, the shell line as its builder
    renders it — the one spelling every gate prints. `str()` is the line,
    so a finding's text embeds a command as its line; code that decides
    (`next_step`, `report_check.adoption_order_note`) reads `name` and
    `kind`, never the line."""

    name: str
    line: str

    def __post_init__(self) -> None:
        if self.name not in COMMAND_KIND:
            raise ValueError(
                f"a command's name is one of {sorted(COMMAND_KIND)}, not {self.name!r}"
            )
        if not self.line.strip():
            raise ValueError(f"a {self.name} command without its line")

    @property
    def kind(self) -> str:
        """MECHANICAL, CONTENT, RESEARCH or DESTRUCTIVE (`COMMAND_KIND`)."""
        return COMMAND_KIND[self.name]

    def __str__(self) -> str:
        return self.line


def adopt_command(protocol: Path, run_id: str = "<run_id>") -> Command:
    """The `labkit-adopt` line that adopts RUN_ID as PROTOCOL's result — the
    adoption, the registered report's block and report-check in one step
    (`tools.adopt`) — the area named as the working directory reaches it,
    and `--protocol PROTOCOL` when the area holds more than one protocol
    (as `audit_command`). The single steps (`protocol-fill --from-run`,
    `--into`) stay for a targeted repair."""
    area = protocol.parent
    here = Path.cwd()
    # the run id is runlog's or a `<run_id>` slot: quoted, the slot reads as
    # part of the command
    line = f"{ADOPT_TOOL} {shlex.quote(shown(area, here))} {run_id}"
    if len(area_protocols(area)) > 1:
        line += f" --protocol {shlex.quote(shown(protocol, here))}"
    return Command(ADOPT, line)


def checkout_command(path: str | Path, rev: str = "HEAD") -> Command:
    """The `git checkout REV -- PATH` line that brings PATH back as REV holds
    it: PATH as one word (`path_word`: shell-quoted, a placeholder as
    written); REV, a commit hash or `HEAD`, as given — the one spelling of every restore from
    git a way out names."""
    return Command(RESTORE, f"git checkout {rev} -- {path_word(str(path))}")


def path_word(path: str) -> str:
    """PATH, as the caller names it, as one word of a printed line:
    shell-quoted, unless the whole of it is a placeholder (`<path>`,
    `protocol_block.is_stamp_placeholder`), which stays as written."""
    return path if protocol_block.is_stamp_placeholder(path) else shlex.quote(path)


def report_shown(text: str, root: Path) -> str | None:
    """The report the head in the protocol TEXT registers, under the repo
    ROOT, as the working directory reaches it — the `--into` target of every
    command that writes into it; None when the head registers none or does
    not read: the gate reading it holds that. Reads no file, for a pure
    check that holds the text (`AreaState.protocol_texts`)."""
    try:
        rel = protocol_block.head(text).report
    except protocol_block.BlockError:
        return None
    return shown(own_path(root / rel), Path.cwd()) if rel is not None else None


def registered_report_shown(protocol: Path) -> str | None:
    """`report_shown` for the PROTOCOL file as it stands, under its layout
    root; None as well when the file does not read."""
    try:
        text = protocol.read_text(encoding="utf-8")
    except OSError:
        return None
    return report_shown(text, layout_root(protocol))


def withdraw_command(protocol: Path) -> Command:
    """The `protocol-fill … --withdraw` line that withdraws PROTOCOL's result
    declaration, the protocol named as the working directory reaches it —
    the way to replace a declaration: withdraw, audit, adopt. Where the
    head registers a report, `--into` it: without, the report keeps the
    withdrawn run's result block and the commit refuses it. A protocol or
    head that does not read names no report here — the gate reading it
    holds that."""
    report = registered_report_shown(protocol)
    into = f" --into {shlex.quote(report)}" if report is not None else ""
    return Command(
        WITHDRAW,
        f'protocol-fill {shown(protocol, Path.cwd())} --withdraw --why "<why>"{into}',
    )


def measure_command(area: Path) -> Command:
    """The line that measures AREA: its stamped `scripts/01_measure.py` (every
    skeleton has one) with the repo's interpreter, the script as the working
    directory reaches it; the script opens its run through runlog."""
    script = shown(area / MEASURE_SCRIPT, Path.cwd())
    return Command(MEASURE, f"{VENV_PYTHON} {shlex.quote(script)}")


def measure_slot_command(slot: str) -> Command:
    """`measure_command` for a check that does not know the working
    directory: SLOT (`gate.AREA_SLOT`) stands for the area, unquoted — the
    gate that knows the area fills it shell-quoted (`gate.Findings.take`)."""
    return Command(MEASURE, f"{VENV_PYTHON} {slot}/{MEASURE_SCRIPT.as_posix()}")


def measure_anew(area: Path) -> str:
    """The way out where a run cannot be held to its code, rows or record:
    a new run of AREA (`measure_command`), then its analysis audit."""
    return f"measure anew (`{measure_command(area)}`) and audit that run"


def pytest_command(*files: str) -> Command:
    """The `.venv/bin/python -m pytest FILE …` line that runs the test FILES
    with the repo's interpreter (`VENV_PYTHON`): each file as the caller
    names it — as the working directory reaches it (`shown`), or as the
    repo root does in a stamped README —, shell-quoted here. Its kind is
    CHECK: it writes nothing. Raises ValueError without a file: the line
    would run every test the working directory holds."""
    if not files:
        raise ValueError("a pytest command names at least one test file")
    return Command(CHECK, shlex.join([VENV_PYTHON, "-m", "pytest", *files]))


def script_check_command(script: Path, *flags: str) -> Command:
    """The line that runs SCRIPT with the repo's interpreter (`VENV_PYTHON`)
    and FLAGS, where the flags make it a check that writes nothing
    (`standard_contract.check_command`): the script as the working
    directory reaches it (`shown`), every word shell-quoted. Not the
    measurement's line, `measure_command`, which opens a run."""
    words = [VENV_PYTHON, shown(script, Path.cwd()), *flags]
    return Command(CHECK, shlex.join(words))


def runlog_placeholder_command(*, wait: bool = False) -> Command:
    """The `.venv/bin/runlog <area>` line (WAIT: `… --wait`) of a sentence
    printed from inside a run, which knows its output file and no area:
    `<area>` is a placeholder the reader replaces. Where the area is known
    the line names it: `gate_command("runlog", area)` lists its runs,
    `wait_command` waits for its open run."""
    line = f"{VENV_BIN}/runlog <area>"
    return Command(WAIT, f"{line} --wait") if wait else Command(CHECK, line)


def lab_stamp_command(name: str | None = None) -> Command:
    """The `.venv/bin/labkit-init lab .` line that stamps the lab repo's own
    files into the working directory, writing only the files that are
    absent; with NAME, shell-quoted, `--name NAME`: the project name the
    stamped `AGENTS.md` carries instead of the directory's."""
    line = f"{VENV_BIN}/labkit-init lab ."
    if name is not None:
        line += f" --name {shlex.quote(name)}"
    return Command(INIT, line)


def gate_command(tool: str, target: Path) -> Command:
    """The line that runs labkit's read-only TOOL on TARGET — a check
    (`code-check`, `finalize`, `report-check`, `preflight`, `notes-check`,
    `protocol-check`), `labkit-next`, which reads the gates, or `runlog`,
    which lists an area's runs —, TARGET
    shell-quoted as the working directory reaches it: the last step of a
    way out whose repair is by hand. Its kind is CHECK: it writes nothing."""
    return Command(CHECK, f"{tool} {shlex.quote(shown(target, Path.cwd()))}")


def reported_check_command(report: Path) -> Command:
    """The `report-check --if-reported REPORT` line — the check the stop and
    the commit run on REPORT —, the report shell-quoted as the working
    directory reaches it (`shown`): the last step after a report is
    repaired by hand."""
    return Command(
        CHECK,
        f"report-check --if-reported {shlex.quote(shown(report, Path.cwd()))}",
    )


def contract_command(protocol: Path) -> Command:
    """The `protocol-check … --contract` line that prints the fields PROTOCOL
    owes by occasion, the protocol named as the working directory reaches
    it (`shown`)."""
    return Command(
        CHECK, f"protocol-check {shlex.quote(shown(protocol, Path.cwd()))} --contract"
    )


def repair_head_way(protocol: Path | None) -> str:
    """The way out of a protocol head that does not read: repair it as the
    sentence beside it says, with the `--contract` line that shows its
    fields — PROTOCOL as the working directory reaches it
    (`contract_command`), the `<PROTOCOL>` placeholder where the sentence
    knows no path. The one wording for every gate that tells such a head."""
    line = (
        contract_command(protocol).line
        if protocol is not None
        else f"protocol-check {protocol_word(None)} --contract"
    )
    return f"repair the head as the sentence says (`{line}` shows its fields)"


def protocol_word(protocol: Path | None) -> str:
    """PROTOCOL as a printed command names it: shell-quoted as the working
    directory reaches it (`shown`); None: the `<PROTOCOL>` placeholder, for
    a sentence that knows no path."""
    if protocol is None:
        return "<PROTOCOL>"
    return shlex.quote(shown(protocol, Path.cwd()))


def fill_command(protocol: Path | None, assignment: str) -> Command:
    """The `protocol-fill … "<label>=<value>"` line that writes one field
    of PROTOCOL (`protocol_word`), with ASSIGNMENT as written, quoted once
    here."""
    return Command(FILL, f'protocol-fill {protocol_word(protocol)} "{assignment}"')


def list_command(protocol: Path) -> Command:
    """The `protocol-fill PROTOCOL --list` line that names every open field
    of PROTOCOL with its values, the protocol shell-quoted as the working
    directory reaches it (`shown`). Its kind is CHECK: it writes nothing."""
    return Command(CHECK, f"protocol-fill {protocol_word(protocol)} --list")


def wait_command(area: Path) -> Command:
    """The `runlog AREA --wait` line that waits for AREA's open run, the
    area shell-quoted as the working directory reaches it (`shown`)."""
    return Command(WAIT, f"runlog {shlex.quote(shown(area, Path.cwd()))} --wait")


def detached_start_command(area: Path, command: str = "<the same command>") -> Command:
    """The `runlog start AREA -- COMMAND` line that starts a run of AREA
    detached, the area shell-quoted as the working directory reaches it
    (`shown`); COMMAND as given — a placeholder for the measurement's own
    line, which the reader replaces."""
    return Command(
        MEASURE, f"runlog start {shlex.quote(shown(area, Path.cwd()))} -- {command}"
    )


def data_counts_command(protocol: Path, run_id: str) -> Command:
    """The `protocol-fill PROTOCOL --data-counts RUN_ID` line that writes
    the counts preparation run RUN_ID recorded as the end of PROTOCOL's
    Data / scope, the protocol as the working directory reaches it
    (`shown`), every word shell-quoted."""
    return Command(
        FILL,
        shlex.join(
            ["protocol-fill", shown(protocol, Path.cwd()), "--data-counts", run_id]
        ),
    )


def builds_on_command(protocol: Path, basis: str) -> Command:
    """The `protocol-fill … --builds-on BASIS` line that writes PROTOCOL's
    step on run BASIS with its changes computed (`tools.protocol_step`),
    the step's name, occasion and reason left for the agent to fill — the
    one wording of an exploratory hold's way out."""
    return Command(
        FILL,
        f"protocol-fill {shlex.quote(shown(protocol, Path.cwd()))} --builds-on "
        f'{basis} --step-id <step> --occasion <observation | planned | repair> --why "…"',
    )


def explored_in_command(protocol: Path | None) -> Command:
    """The `protocol-fill … --explored-in EXPLORATION_PROTOCOL` line that
    writes PROTOCOL's link to its exploration (`tools.protocol_exploration`),
    the exploratory protocol left for the agent to name — the one wording
    of the way out where a link is refused."""
    return Command(
        FILL,
        f"protocol-fill {protocol_word(protocol)} --explored-in <EXPLORATION_PROTOCOL>",
    )


def step_command(area: Path) -> Command:
    """The `labkit-next …` line that names AREA's one next step, the area
    named as the working directory reaches it (`shown`)."""
    return Command(NEXT, f"labkit-next {shlex.quote(shown(area, Path.cwd()))}")


def render_command(protocol: Path | None = None, *, from_run: bool = False) -> Command:
    """The `protocol-fill … --render` line that writes the result section's
    generated lines again (FROM_RUN: `--from-run`, the Recorded results
    line from the run) — the projection of an adoption; PROTOCOL named as
    the working directory reaches it, or the `<PROTOCOL>` placeholder where
    the check knows no path (`result_render`)."""
    flag = "--from-run" if from_run else "--render"
    return Command(RENDER, f"protocol-fill {protocol_word(protocol)} {flag}")


def report_fields_step(protocol: Path) -> str:
    """The step between the decided analysis audit and the adoption, as
    every line that prints the adoption names it: the Conclusion and the
    report fields PROTOCOL owes once frozen and a result is declared
    (`protocol_report.OwedFields.once_reported`, which the contract line
    prints). The adoption declares the result and runs protocol-check on
    it, which refuses a frozen protocol without them."""
    return (
        f"write the Conclusion and the report fields "
        f"(`{contract_command(protocol)}`, once frozen and adopted)"
    )


def next_after_run(protocol: Path, run_id: str) -> str:
    """The steps after a measurement of PROTOCOL, in the order the gates
    accept them: finalize, the analysis audit and its decisions, the
    Conclusion and the report fields (`report_fields_step`), then the
    adoption of RUN_ID — what every skeleton prints at the end of a run.
    Printed alone, the adoption sends an agent into its refusal."""
    area = protocol.parent
    return (
        f"next: finalize {shlex.quote(shown(area, Path.cwd()))} · "
        f"{audit_command(area, '--mode', 'analysis', protocol=protocol)}, then "
        f"decide its findings · {report_fields_step(protocol)} · then "
        f"{adopt_command(protocol, run_id)} (writes Recorded results, [result] run "
        f"and the run entry from metrics.json, and the registered report's block)"
    )


def report_review_command(area: Path, report: Path, protocol: Path) -> Command:
    """The command that reviews REPORT on AREA, paths as seen from the
    working directory; `--protocol` only when the area has more than one."""
    line = audit_command(
        area, "--report-review", shown(report, Path.cwd()), protocol=protocol
    ).line
    return Command(REVIEW, line)


def claim_decide_command(
    area: Path, report: Path, n: int, record: str, protocol: Path
) -> Command:
    """The line that decides claim N of the report review RECORD (its file
    name) on REPORT `false-positive`, the one decision a claim takes
    (`report_reviews.claim_refusal`): `labkit-audit … --report-review
    REPORT --decide N false-positive --why "<why>" --record RECORD`, the
    reason a placeholder the reader replaces."""
    return Command(
        DECIDE,
        f"{report_review_command(area, report, protocol)} --decide {n} "
        f'false-positive --why "<why>" --record {shlex.quote(record)}',
    )


def claim_review_command(area: Path, record: str, protocol: Path) -> Command:
    """The line that has a second reviewer judge the decided claims of the
    report review RECORD (its file name): `labkit-audit … --review --record
    RECORD` (`gates/claim_review`)."""
    line = audit_command(area, "--review", "--record", record, protocol=protocol).line
    return Command(REVIEW, line)


def into_command(protocol: Path | None, report: Path) -> Command:
    """The `protocol-fill PROTOCOL --into REPORT` line that writes PROTOCOL's
    result block into REPORT, both as the working directory reaches them
    (`shown`), shell-quoted: a protocol named relative to the report and a
    report relative to the repo runs from neither. PROTOCOL None: the
    `<PROTOCOL>` placeholder (`protocol_word`)."""
    return Command(
        INTO,
        f"protocol-fill {protocol_word(protocol)} --into "
        f"{shlex.quote(shown(report, Path.cwd()))}",
    )


def report_fields_command(area: Path) -> Command:
    """The `labkit-init exp AREA --report` line that appends the † fields to
    AREA's protocol, as the working directory reaches the area (`shown`):
    the step for a † field absent from the text, which `protocol-fill`
    cannot fill (`next_step.fill_line`)."""
    return Command(
        INIT, f"labkit-init exp {shlex.quote(shown(area, Path.cwd()))} --report"
    )


def freeze_command(protocol: Path | None, record: str | None = None) -> Command:
    """The `protocol-fill PROTOCOL --freeze [RECORD]` line that freezes
    PROTOCOL — `frozen = true`, `preflight_audit` naming the decided
    preflight RECORD (without one, the area's newest) — as the working
    directory reaches it (`shown`; None: the `<PROTOCOL>` placeholder,
    `protocol_word`): the one writer of the freeze, which refuses what the
    freeze gate would hold and leaves the file as it was
    (`protocol_fill._freeze_file`)."""
    line = f"protocol-fill {protocol_word(protocol)} --freeze"
    if record:
        line += f" {shlex.quote(record)}"
    return Command(FREEZE, line)


def stage_command(*paths: Path) -> Command:
    """The `git add -- PATH …` line that stages PATHS — an area as a whole,
    or files —, each shell-quoted as the working directory reaches it
    (`shown`): the one spelling of every staging a way out names. Raises
    ValueError without a path: `git add --` alone stages nothing."""
    if not paths:
        raise ValueError("a stage command names at least one path")
    here = Path.cwd()
    return Command(
        STAGE, shlex.join(["git", "add", "--", *(shown(p, here) for p in paths)])
    )


def handover_command(protocol: Path | None, report: str | None = None) -> Command:
    """The `protocol-fill … --handover` line for PROTOCOL (None: the
    `<PROTOCOL>` placeholder, for a sentence that knows no path) into
    REPORT — when not given, the report PROTOCOL's head registers
    (`registered_report_shown`), else `REPORT.md` —, its why and tried as
    placeholders; it runs no model."""
    named = protocol_word(protocol)
    if report is None:
        registered = registered_report_shown(protocol) if protocol is not None else None
        report = registered if registered is not None else "REPORT.md"
    return Command(
        HANDOVER,
        f"protocol-fill {named} --handover "
        f'--why "<what blocks>" --tried "<what you tried>" --into {shlex.quote(report)}',
    )


def audit_command(
    area: Path, *step: str, protocol: Path | None = None, base: Path | None = None
) -> Command:
    """The `labkit-audit` line for STEP on AREA, paths as BASE (the working
    directory by default) reaches them, every word shell-quoted, and
    `--protocol PROTOCOL` when the area holds more than one protocol — the
    command refuses to choose there (`the_protocol`). The one builder of
    every printed audit step; STEP's words are given as BASE reaches them.
    Without PROTOCOL in such an area the line names none, and the command
    as printed refuses with the choice it needs."""
    here = base or Path.cwd()
    words = ["labkit-audit", shown(area, here), *step]
    if protocol is not None and len(area_protocols(area)) > 1:
        words += ["--protocol", shown(protocol, here)]
    return Command(AUDIT, shlex.join(words))


def preflight_command(
    area: Path, protocol: Path | None = None, base: Path | None = None
) -> Command:
    """The `preflight AREA` line, paths as BASE (the working directory by
    default) reaches them, shell-quoted, and `--protocol PROTOCOL` when the
    area holds more than one protocol — the gate refuses to choose there
    (`choose_protocol`), as `audit_command` does. Without PROTOCOL in such
    an area the line names none, and the gate as printed refuses with the
    choice it needs. Its kind is CHECK."""
    here = base or Path.cwd()
    words = ["preflight", shown(area, here)]
    if protocol is not None and len(area_protocols(area)) > 1:
        words += ["--protocol", shown(protocol, here)]
    return Command(CHECK, shlex.join(words))


class AreaSlots(TypedDict):
    """The two slot values of `area_slots`."""

    area: str
    audit: str


def area_slots(
    area: Path, protocol: Path | None = None, base: Path | None = None
) -> AreaSlots:
    """The values that fill the slots a check leaves for AREA
    (`gate.AREA_SLOT`, `gate.AUDIT_SLOT`), as `gate.Findings(area=…, audit=…)`
    and `gate.fill_slots` take them: AREA as BASE (the working directory by
    default) reaches it, and the audit command's head, `--protocol PROTOCOL`
    where the area holds several (`audit_command`); without PROTOCOL the head
    names none, also in such an area."""
    here = base or Path.cwd()
    return {
        "area": shown(area, here),
        "audit": audit_command(area, protocol=protocol, base=here).line,
    }


def decide_command(
    area: Path,
    n: int,
    status: str,
    reason: str,
    record: str,
    *,
    not_assessable: str | None = None,
    protocol: Path | None = None,
    base: Path | None = None,
) -> Command:
    """The `labkit-audit … --decide N STATUS --why "REASON"
    [--not-assessable IDS] --record RECORD` line (`audit_command`): REASON
    in double quotes as given — a placeholder the reader replaces
    (`<why>`), never a ready-made reason —, IDS as given, RECORD as the
    caller shows it. The one builder of a printed decision."""
    ids = f" --not-assessable {not_assessable}" if not_assessable is not None else ""
    return Command(
        DECIDE,
        f"{audit_command(area, protocol=protocol, base=base)} --decide {n} "
        f'{status} --why "{reason}"{ids} --record {shlex.quote(record)}',
    )


def stamp_command(name: str = "<new-name>", kind: str = "…") -> Command:
    """The `labkit-init exp NAME --kind KIND` line that stamps a new area
    and its protocol under a fresh id — or, NAME naming an area without a
    protocol, that area's protocol — the one way labkit writes an id;
    no command gives an existing protocol a new one."""
    return Command(INIT, f"labkit-init exp {name} --kind {kind}")


def register_anew(pid: str = "<id>", per: str = "per change", kind: str = "…") -> str:
    """The way out of a registration that cannot be answered as written
    (K1): a new protocol of KIND naming the earlier one PID, exploratory
    unless its data are unseen for the changed question (no gate holds the
    type, `report_replacement.replacement_gaps`), its
    changes declared PER what the caller names — the one wording every
    layer prints for it: the ways out, report-check's and finalize's holds,
    the reference and kept-number checks."""
    return (
        f"register anew: a new protocol (`{stamp_command(kind=kind)}`), "
        '`type = "exploratory"` (`confirmatory` only on data not yet evaluated for '
        "the changed question), committed before its own first run, naming the "
        f'earlier one in `[replaces] protocol = "{pid}"` with one '
        f"`[[replaces.change]]` (what, from, to, why) {per}"
    )
