"""commands — labkit's steps as commands: `Command` (a step's name, its
kind and the shell line its builder renders, the one spelling every gate
prints) and the builders of each line (`adopt_command`, `withdraw_command`,
`audit_command`, …). Pure: a builder reads at most a protocol's head to
name a registered report, and writes nothing.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import protocol_block
from labkit.formats.repo import (
    area_protocols,
    layout_root,
    own_path,
    shown,
)


#: the command that adopts a run — what every printed adoption line starts with
ADOPT_TOOL = "labkit-adopt"

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
    it: PATH shell-quoted, unless the whole of it is a placeholder (`<path>`,
    `protocol_block.is_stamp_placeholder`), which stays as written; REV, a
    commit hash or `HEAD`, as given — the one spelling of every restore from
    git a way out names."""
    target = str(path)
    placeholder = protocol_block.is_stamp_placeholder(target)
    return Command(
        RESTORE,
        f"git checkout {rev} -- {target if placeholder else shlex.quote(target)}",
    )


def withdraw_command(protocol: Path) -> Command:
    """The `protocol-fill … --withdraw` line that withdraws PROTOCOL's result
    declaration, the protocol named as the working directory reaches it —
    the way to replace a declaration: withdraw, audit, adopt. Where the
    head registers a report, `--into` it: without, the report keeps the
    withdrawn run's result block and the commit refuses it. A protocol or
    head that does not read names no report here — the gate reading it
    holds that."""
    try:
        rel = protocol_block.head(protocol.read_text(encoding="utf-8")).report
    except (OSError, protocol_block.BlockError):
        rel = None
    into = (
        f" --into {shlex.quote(shown(own_path(layout_root(protocol) / rel), Path.cwd()))}"
        if rel is not None
        else ""
    )
    return Command(
        WITHDRAW,
        f'protocol-fill {shown(protocol, Path.cwd())} --withdraw --why "<why>"{into}',
    )


def measure_command(area: Path) -> Command:
    """The line that measures AREA: its stamped `scripts/01_measure.py` (every
    skeleton has one) with the repo's interpreter, the script as the working
    directory reaches it; the script opens its run through runlog."""
    script = shown(area / "scripts" / "01_measure.py", Path.cwd())
    return Command(MEASURE, f".venv/bin/python {shlex.quote(script)}")


def measure_anew(area: Path) -> str:
    """The way out where a run cannot be held to its code, rows or record:
    a new run of AREA (`measure_command`), then its analysis audit."""
    return f"measure anew (`{measure_command(area)}`) and audit that run"


def gate_command(tool: str, target: Path) -> Command:
    """The line that runs labkit's read-only TOOL on TARGET — a check
    (`code-check`, `finalize`, `report-check`, `preflight`, `notes-check`,
    `protocol-check`) or `labkit-next`, which reads the gates —, TARGET
    shell-quoted as the working directory reaches it: the last step of a
    way out whose repair is by hand. Its kind is CHECK: it writes nothing."""
    return Command(CHECK, f"{tool} {shlex.quote(shown(target, Path.cwd()))}")


def contract_command(protocol: Path) -> Command:
    """The `protocol-check … --contract` line that prints the fields PROTOCOL
    owes by occasion, the protocol named as the working directory reaches
    it (`shown`)."""
    return Command(
        CHECK, f"protocol-check {shlex.quote(shown(protocol, Path.cwd()))} --contract"
    )


def fill_command(protocol: Path | None, assignment: str) -> Command:
    """The `protocol-fill … "<label>=<value>"` line that writes one field
    of PROTOCOL (named as the working directory reaches it, `shown`; None:
    the `<PROTOCOL>` placeholder, for a sentence that knows no path), with
    ASSIGNMENT as written, quoted once here."""
    named = (
        shlex.quote(shown(protocol, Path.cwd()))
        if protocol is not None
        else "<PROTOCOL>"
    )
    return Command(FILL, f'protocol-fill {named} "{assignment}"')


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
    named = (
        shlex.quote(shown(protocol, Path.cwd()))
        if protocol is not None
        else "<PROTOCOL>"
    )
    return Command(RENDER, f"protocol-fill {named} {flag}")


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


def into_command(protocol: Path, report: Path) -> Command:
    """The `protocol-fill PROTOCOL --into REPORT` line that writes PROTOCOL's
    result block into REPORT, both as the working directory reaches them
    (`shown`), shell-quoted: a protocol named relative to the report and a
    report relative to the repo runs from neither."""
    here = Path.cwd()
    return Command(
        INTO,
        shlex.join(
            ["protocol-fill", shown(protocol, here), "--into", shown(report, here)]
        ),
    )


def report_fields_command(area: Path) -> Command:
    """The `labkit-init exp AREA --report` line that appends the † fields to
    AREA's protocol, as the working directory reaches the area (`shown`):
    the step for a † field absent from the text, which `protocol-fill`
    cannot fill (`next_step._fill_line`)."""
    return Command(
        INIT, f"labkit-init exp {shlex.quote(shown(area, Path.cwd()))} --report"
    )


def freeze_command(protocol: Path, record: str | None = None) -> Command:
    """The `protocol-fill PROTOCOL --freeze [RECORD]` line that freezes
    PROTOCOL — `frozen = true`, `preflight_audit` naming the decided
    preflight RECORD (without one, the area's newest) — as the working
    directory reaches it (`shown`): the one writer of the freeze, which
    refuses what the freeze gate would hold and leaves the file as it was
    (`protocol_fill._freeze_file`)."""
    words = ["protocol-fill", shown(protocol, Path.cwd()), "--freeze"]
    if record:
        words.append(record)
    return Command(FREEZE, shlex.join(words))


def stage_command(area: Path) -> Command:
    """The `git add -- AREA` line that stages the whole area, as the working
    directory reaches it (`shown`): the pre-commit's way out while the
    area's tree differs from the index (`report_hold.staged_area_gap`)."""
    return Command(STAGE, f"git add -- {shlex.quote(shown(area, Path.cwd()))}")


def handover_command(protocol: Path | None, report: str = "REPORT.md") -> Command:
    """The `protocol-fill … --handover` line for PROTOCOL (None: the
    `<PROTOCOL>` placeholder, for a sentence that knows no path) into
    REPORT, its why and tried as placeholders; it runs no model."""
    named = (
        shlex.quote(shown(protocol, Path.cwd()))
        if protocol is not None
        else "<PROTOCOL>"
    )
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


def register_anew(pid: str = "<id>", per: str = "per change", kind: str = "…") -> str:
    """The way out of a registration that cannot be answered as written
    (K1): a new exploratory protocol of KIND naming the earlier one PID, its
    changes declared PER what the caller names — the one wording every
    layer prints for it: the ways out, report-check's and finalize's holds,
    the reference and kept-number checks."""
    return (
        f"register anew: a new protocol (`labkit-init exp <new-name> --kind {kind}`), "
        '`type = "exploratory"`, committed before its own first run, naming the '
        f'earlier one in `[replaces] protocol = "{pid}"` with one '
        f"`[[replaces.change]]` (what, from, to, why) {per}"
    )
