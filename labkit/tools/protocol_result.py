"""The result section of a protocol written from its sources: the run's
number into Recorded results and the `[result]` declaration (`from_run`),
the section rendered again from the run and the audit records
(`render_result`), the Prompt block from the scripts (`fill_prompts`), and
the declaration withdrawn (`withdraw`).

Each returns the new text; `protocol_fill` writes it, and a number becomes
the result only through report-check (`protocol_fill.adopt`).
"""

from __future__ import annotations


import re
from pathlib import Path

from labkit.formats import (
    findings,
    protocol_block,
    runs,
)
from labkit.checks.result_render import Rendering, rendering
from labkit.checks import recheck
from labkit.checks.prompt_check import prompt_constants
from labkit.formats.protocol_check import (
    RECORDED_RESULTS_LABEL,
    BEFORE_RUN_CLAIMS,
    RUNS_PLACEHOLDER,
    field_name,
    fields,
)
from labkit.tools.protocol_edit import fill


RUNS_HEADING = re.compile(r"^## Runs\b")

#: how `--from-run` names the declaration among what it filled
RESULT_LABEL = "[result] run"
_PROTOCOL_HEADER = re.compile(r"^\s*\[\s*protocol\s*\]\s*(?:#.*)?$")
_RESULT_HEADER = re.compile(r"^\s*\[\s*result\s*\]\s*(?:#.*)?$")
#: the `[result]` table's one line, its key and `=` and a trailing comment kept
_RESULT_RUN_LINE = re.compile(r'^(\s*run\s*=\s*)"[^"\n]*"(\s*(?:#.*)?)$')


def fill_result_run(text: str, run_id: str) -> str:
    """Declare RUN_ID as the protocol's reported result: `[result] run =
    "<id>"` in the TOML block, the one declaration report-check holds the
    protocol to (`protocol_block.declared_run`). Without a `[result]` the
    table is written right after the `[protocol]` table's last key; one
    naming RUN_ID already leaves the text as it is; one naming another run
    is refused, --force or not: a declaration is withdrawn (`--withdraw`),
    then the run that answers is audited and adopted — an audit made while
    another run is declared does not cover the new one (file-check case,
    2026-10-28). Every other byte stays, and the block is read back and
    must declare exactly RUN_ID. Raises BlockError on a head that does not
    read, ValueError on the refusal or a block without `[protocol]`."""
    current = protocol_block.declared_run(text)
    if current == run_id:
        return text
    if current is not None:
        raise ValueError(
            f"[result] names {current}, not {run_id} — an adoption is not "
            f'replaced: withdraw it (`--withdraw --why "<why>"`), audit the run that '
            f"answers, then adopt it"
        )
    span = protocol_block.toml_block_span(text)
    if span is None:
        raise ValueError("no ```toml block — the head is where the result is adopted")
    lines = text.split("\n")
    if current is not None:
        _replace_result_run(lines, span, run_id)
    else:
        _insert_result_table(lines, span, run_id)
    new = "\n".join(lines)
    if protocol_block.declared_run(new) != run_id:
        raise ValueError("[result] run did not read back as written")
    return new


def _replace_result_run(lines: list[str], span: tuple[int, int], run_id: str) -> None:
    """Set the `run = "…"` line of the `[result]` table in LINES[SPAN] to RUN_ID."""
    inside = False
    for i in range(*span):
        if _RESULT_HEADER.match(lines[i]):
            inside = True
            continue
        if protocol_block.TABLE_HEADER.match(lines[i]):
            inside = False
            continue
        m = _RESULT_RUN_LINE.match(lines[i]) if inside else None
        if m:
            lines[i] = f'{m.group(1)}"{run_id}"{m.group(2)}'
            return
    raise ValueError(
        '[result] has no one-line `run = "…"` — edit the TOML head by hand'
    )


def _insert_result_table(lines: list[str], span: tuple[int, int], run_id: str) -> None:
    """Write `[result]` with RUN_ID after the last key of the `[protocol]`
    table in LINES[SPAN] — before the comments and tables that follow it."""
    start, end = span
    for i in range(start, end):
        if not _PROTOCOL_HEADER.match(lines[i]):
            continue
        last_key = i
        for j in range(i + 1, end):
            if protocol_block.TABLE_HEADER.match(lines[j]):
                break
            if lines[j].strip() and not lines[j].lstrip().startswith("#"):
                last_key = j
        lines[last_key + 1 : last_key + 1] = ["", "[result]", f'run = "{run_id}"']
        return
    raise ValueError("no [protocol] table in the ```toml block")


#: the label `--from-run` writes from the run's metrics.json — `--list` sets
#: it apart, since filling it before the run makes --from-run refuse
WRITTEN_BY_RUN = (RECORDED_RESULTS_LABEL,)
#: the fields about the run that the author writes after it — Conclusion: the
#: question's answer in two plain sentences, read within the Limitation lines;
#: Raw output from the run's rows (which pair shows a finding is a choice
#: no record makes). `--list` sets them apart too, and `--from-run` names
#: the open ones with the run's output files.
WRITTEN_AFTER_RUN = tuple(
    label for label in BEFORE_RUN_CLAIMS if label not in WRITTEN_BY_RUN
)


def runs_line(text: str, run_id: str, sentence: str) -> tuple[str, bool]:
    """Add a run entry to the protocol run list (`## Runs`).

    The stamped `<run_id>` placeholder becomes the entry, else one is
    appended. A list already naming `run_id` is left alone.
    Returns (text, changed).
    """
    lines = text.split("\n")
    heading = next(
        (
            i
            for i in protocol_block.section_starts(lines)
            if RUNS_HEADING.match(lines[i])
        ),
        None,
    )
    if heading is None:
        raise ValueError("no `## Runs` section to name the run in")
    end = protocol_block.section_end(lines, heading)
    section = range(heading + 1, end)
    if any(run_id in lines[i] for i in section):
        return text, False
    entry = f"- {run_id} — {sentence}"
    for i in section:
        if RUNS_PLACEHOLDER.match(lines[i]):
            lines[i] = entry
            return "\n".join(lines), True
    k = end
    while k > heading + 1 and not lines[k - 1].strip():
        k -= 1
    lines.insert(k, entry)
    return "\n".join(lines), True


def from_run(
    text: str, area: Path, run_id: str | None = None, force: bool = False
) -> tuple[str, list[str], str]:
    """Write the run back: `[result] run` in the TOML head (the one
    declaration that the number is reported, `fill_result_run`), the Recorded results
    line, the Limitation lines and the Runs entry as `runs/<run_id>/metrics.json`
    and the covering records render them (`result_render.rendering`; the
    protocol's answering run, `recheck.chosen_run`, when RUN_ID is None), a Limitation line of a record that covers
    the run no longer dropped; the Summary's Conclusion stays the author's
    (`WRITTEN_AFTER_RUN`). Returns (text, what was filled, run_id). A filled
    Recorded results is refused without `force`; a `[result]` naming another
    run is refused always (`fill_result_run`: withdraw it first)."""
    run = recheck.chosen_run(area, text, run_id)
    r = rendering(area, text, run)
    filled: list[str] = []
    for label in WRITTEN_BY_RUN:
        try:
            text = fill(text, label, r.recorded_results, force=force)
            filled.append(label)
        except ValueError as exc:
            if "no field labelled" in str(exc):
                continue  # a cut without this line (the Summary of a report-grade full form carries it)
            raise
    declared = fill_result_run(text, run.name)
    if declared != text:
        text = declared
        filled.append(RESULT_LABEL)
    text, changed = runs_line(
        text, run.name, "the kept run; its metrics.json is the number"
    )
    if changed:
        filled.append("Runs")
    text, written = limit_lines(text, r.limits, force)
    filled += written
    # a Limitation line of a record that no longer covers the run is labkit's own
    # stale line, never the author's prose: it goes with the write-back
    text, dropped = drop_stray_limits(text, r.limits)
    filled += [f"dropped {label}" for label in dropped]
    return text, filled, run.name


def drop_stray_limits(
    text: str, keep: tuple[tuple[str, str], ...]
) -> tuple[str, list[str]]:
    """TEXT without the Limitation lines no covering record decides (labels not in
    KEEP) — written by hand or from an older record. (text, labels dropped)."""
    keep_labels = {label for label, _ in keep}
    dropped: list[str] = []
    lines = text.split("\n")
    for f in sorted(fields(text), key=lambda f: -f.line):
        label = f.label.replace("†", "").strip()
        if label.startswith(findings.LIMIT_PREFIX) and label not in keep_labels:
            del lines[f.line - 1 : f.last]
            dropped.append(label)
    return "\n".join(lines), dropped


def declared_run_dir(text: str, area: Path, why: str) -> Path:
    """The run directory TEXT's head declares as its result, in AREA.
    Raises ValueError without a declaration (WHY says what the caller
    needs it for) or without the run's metrics.json."""
    declared = protocol_block.declared_run(text)
    if declared is None:
        raise ValueError(
            f"no run adopted ([result] run) — `--from-run <run_id>` adopts the run "
            f"and writes the result; {why}"
        )
    run = runs.run_path(area, declared)
    if not runs.metrics_path(run).is_file():
        raise ValueError(
            f"[result] names {declared}, but runs/{declared}/metrics.json is not there"
        )
    return run


def render_result(text: str, area: Path) -> tuple[str, list[str]]:
    """`--render`: the result section written again from its sources for the
    declared run — the Recorded results line, the Limitation lines (stray ones dropped) and,
    where the scripts' PROMPT constants read statically, the Prompt block.
    Idempotent: a text that says what its sources say comes back unchanged.
    (text, what was written). Raises ValueError without a declared run or
    without `runs/<id>/` for it — `--from-run` declares first."""
    run = declared_run_dir(text, area, "--render only writes the result again")
    r: Rendering = rendering(area, text, run)
    written: list[str] = []
    before = text
    text = fill(text, RECORDED_RESULTS_LABEL, r.recorded_results, force=True)
    if text != before:
        written.append(RECORDED_RESULTS_LABEL)
    text, limits_written = limit_lines(text, r.limits, force=True)
    written += limits_written
    text, dropped = drop_stray_limits(text, r.limits)
    written += [f"dropped {label}" for label in dropped]
    constants = prompt_constants(area)
    if constants:
        before = text
        text = fill_prompts(text, constants)
        if text != before:
            written.append("Prompt")
    return text, written


def limit_lines(
    text: str, limits: tuple[tuple[str, str], ...], force: bool = False
) -> tuple[str, list[str]]:
    """Each LIMITS entry (label, value — `result_render.Rendering.limits`) as
    its `- **<label>:** <value>` line, below Recorded results: added when missing,
    left when it says that already, replaced only with FORCE. (text, labels
    written). Raises ValueError on a differing line without FORCE, or with
    no Recorded results line to stand under."""
    written: list[str] = []
    for label, value in limits:
        lines = text.split("\n")
        by_label = {f.label.replace("†", "").strip(): f for f in fields(text)}
        line = f"- **{label}:** {value}"
        have = by_label.get(label)
        if have is not None:
            if have.value == value:
                continue
            if not force:
                raise ValueError(
                    f"line {have.line} ({label!r}) says {have.value[:80]!r}, the "
                    f"record says otherwise — --force to write the record's"
                )
            lines[have.line - 1 : have.last] = [line]
        else:
            answer = next(
                (
                    f
                    for f in fields(text)
                    if f.name == field_name(RECORDED_RESULTS_LABEL)
                ),
                None,
            )
            if answer is None:
                raise ValueError(f"no Recorded results line to write {label!r} under")
            # below Recorded results and the Limitation lines already under it: in
            # record order (inserted right below Recorded results, three limits
            # read #3, #2, #1 — the final audits, 2026-10-21)
            at = answer.last
            for f in fields(text):
                if f.line == at + 1 and f.label.startswith(findings.LIMIT_PREFIX):
                    at = f.last
            lines.insert(at, line)
        text = "\n".join(lines)
        written.append(label)
    return text, written


def fill_prompts(text: str, constants: dict[str, str]) -> str:
    """Return the protocol text with the Prompt field's code block written
    from the scripts' `PROMPT` / `PROMPT_<VARIANT>` constants, `PROMPT`
    first, each under a `── NAME ──` line when there are several.

    The block is what `code-check` holds the script to (prompt drift); three
    of three cold agents wrote it by a Python snippet because the label fill
    could not reach a code block (re-measure 2026-10-07). Replaces the block
    that follows the label (within three lines), or inserts one."""
    if not constants:
        raise ValueError(
            "no PROMPT constant readable in the area's scripts (an f-string "
            "renders at run time and cannot be copied) — write the block by hand"
        )
    hits = [f for f in fields(text) if f.name == "prompt"]
    if len(hits) != 1:
        where = ", ".join(str(f.line) for f in hits) or "none"
        raise ValueError(f"expected one Prompt field, found {where}")
    (f,) = hits
    lines = text.splitlines()
    names = sorted(constants, key=lambda n: (n != "PROMPT", n))
    body: list[str] = []
    for name in names:
        if len(names) > 1:
            body.append(f"── {name} ──")
        body += constants[name].splitlines()
    start = end = f.last  # 0-based index just after the field's value
    for j in range(f.last, min(f.last + 3, len(lines))):
        m = protocol_block.FENCE.match(lines[j])
        if m:
            # the one fence rule (protocol_block.closes): until 0.96.0 a line
            # merely starting with the marker closed it (audit 2026-10-15)
            k = next(
                (
                    k
                    for k in range(j + 1, len(lines))
                    if protocol_block.closes(lines[k], m.group(2))
                ),
                None,
            )
            if k is None:
                raise ValueError(f"line {j + 1}: the Prompt block never closes")
            start, end = j, k + 1
            break
    block = ["  ```text", *[f"  {ln}" if ln else "" for ln in body], "  ```"]
    if start == end:  # no block yet: a blank line, then the block
        block = ["", *block]
    lines[start:end] = block
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def without_result(text: str) -> str:
    """Withdraw only the result declaration — the `[result]` table, also one
    that does not read; preserve registration and run evidence."""
    span = protocol_block.toml_block_span(text)
    if span is None:
        return text
    lines = text.split("\n")
    start = next((i for i in range(*span) if _RESULT_HEADER.match(lines[i])), None)
    if start is None:
        return text
    end = next(
        (
            i
            for i in range(start + 1, span[1])
            if protocol_block.TABLE_HEADER.match(lines[i])
        ),
        span[1],
    )
    del lines[start:end]
    result = "\n".join(lines)
    if protocol_block.declared_run(result) is not None:
        raise ValueError("[result] adoption could not be withdrawn")
    return result


def withdrawn_runs_entry(text: str, run_id: str, day: str, why: str) -> str:
    """TEXT with the `## Runs` entry of RUN_ID marked `· withdrawn DAY: WHY`
    — the trace a withdrawal leaves where the run list stands and every
    later adoption keeps (`runs_line` only appends); an entry is added when
    the list does not name the run. Raises ValueError without a `## Runs`
    section."""
    mark = f" · withdrawn {day}: {why}"
    if not runs.RUN_ID.match(run_id):
        # a declaration that did not read names no run: its own entry
        text, _ = runs_line(text, f"[result] {run_id}", f"withdrawn {day}: {why}")
        return text
    text, _ = runs_line(text, run_id, "the run adopted as the result")
    lines = text.split("\n")
    heading = next(
        i for i in protocol_block.section_starts(lines) if RUNS_HEADING.match(lines[i])
    )
    end = protocol_block.section_end(lines, heading)
    at = next(i for i in range(heading + 1, end) if run_id in lines[i])
    lines[at] += mark
    return "\n".join(lines)


#: what Recorded results says after a withdrawal: a placeholder again (the
#: next `--from-run` fills it without --force), naming what was withdrawn
WITHDRAWN_RESULTS = (
    "<withdrawn {day}: run {run} is no longer the result — {why}; "
    "protocol-fill --from-run writes this field for the run adopted next>"
)


def withdraw(text: str, why: str, day: str) -> tuple[str, str]:
    """`--withdraw`: TEXT without its result declaration (`without_result`),
    the lines `--from-run` generated reset — Recorded results to a
    placeholder naming the withdrawal (WITHDRAWN_RESULTS), every Limitation line
    dropped — and the run's Runs entry marked with DAY and WHY
    (`withdrawn_runs_entry`). Audit records, findings and runs are not
    touched: a withdrawal releases nothing and settles nothing. Returns
    (text, the run withdrawn). Raises ValueError when TEXT declares no
    result or WHY is empty."""
    run_id = protocol_block.declared_run_shown(text)
    if run_id is None:
        raise ValueError(
            "the protocol has adopted no result ([result] run) — nothing to withdraw"
        )
    if not why.strip():
        raise ValueError(
            "--withdraw needs --why: one line, why the run is no longer the result"
        )
    new = without_result(text)
    new = fill(
        new,
        RECORDED_RESULTS_LABEL,
        WITHDRAWN_RESULTS.format(day=day, run=run_id, why=why.strip()),
        force=True,
    )
    new, _ = drop_stray_limits(new, ())
    return withdrawn_runs_entry(new, run_id, day, why.strip()), run_id
