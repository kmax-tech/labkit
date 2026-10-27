"""protocol-fill — fill protocol fields, adopt a run or render recorded results.

Filling protocol fields by full-text replacement fails in rounds: the quoted
placeholder block never matches exactly (2026-09-09, twice in one day on the
same protocol — three attempts each until a regex sat). The template stamps
every field as `- **Label †:** <placeholder>`, so the LABEL is the stable
handle; this tool matches it, replaces the `<...>` value (multi-line
placeholders included) and leaves everything else byte-identical.

    protocol-fill PROTOCOL-x.md --list
    protocol-fill PROTOCOL-x.md "Meaning of the gold label" "positive = ..."
    protocol-fill PROTOCOL-x.md --line 27 Question "does Y move X?"
    protocol-fill PROTOCOL-x.md "C1 sentence=<the promise>"   a [[promise]]'s sentence, as a TOML string
    protocol-fill PROTOCOL-x.md type=exploratory repeat_cost=low kind=fit "model alias=haiku"   the TOML head's stamped placeholders
    protocol-fill PROTOCOL-x.md --prompts      the Prompt block from the scripts' PROMPT constants
    protocol-fill PROTOCOL-x.md --render       the result section written again from its sources:
                                               Recorded results, Limit lines (stray ones dropped), Prompt block
    protocol-fill PROTOCOL-x.md --into REPORT.md  the declared result as a generated block in a
                                               report outside the protocol (replaced in place,
                                               or appended); report-check holds the block to
                                               the protocol's rendering
    protocol-fill PROTOCOL-x.md --discuss RUN_ID --why "…" --into REPORT.md
                                               a run the report looks at without
                                               reporting it, as a discussion block
                                               (head: protocol, run, why; its line
                                               written from them)
    protocol-fill PROTOCOL-x.md --from-run [RUN_ID]   adopt the run as the result: `[result] run`
                                               in the TOML head (the declaration), Recorded results and
                                               Runs lines from its metrics.json (newest completed
                                               run by default), written only when report-check
                                               passes on them; the Summary's Conclusion — the
                                               question's answer in two sentences, within the
                                               Limits — stays yours

A field that is already filled is refused without --force — overwriting an
answer silently is how two truths happen.

`--from-run` is the write-back LAB-041 Generate numbers, don't retype them
asks for: twelve cold agents (cloud probes 2026-10-12) typed the number into
three protocol lines by hand, and one `--check` failed on the retyping. The
lines carry every metric key and value as the run recorded them, and the
run_id — exactly what `--check` (`recheck.cited`) holds the protocol to. Labels are matched with the †
marker and case ignored; an ambiguous label (same label in Summary and a
section) is refused with the line numbers, disambiguate with --line.

`--from-run` is also the one path by which a number becomes the result
(`adopt`): `[result].run` in the TOML head declares it reported, and
the declaration is not what makes it sound — the checks are. So the lines
are written, `report-check` runs on the written protocol (finalize clean, a
full run — no probe, no acknowledged run — a decided analysis audit of code,
promises and that run, `02_analyze.py --check` holding the written numbers;
frozen at high repeat cost), and a blocker puts the file back as it was. A
result adopted this way has passed every check labkit prescribes; the stop
hook and the pre-commit (`report-check --if-reported`) hold a hand-written or
later-changed answer to the same. A provisional number stays a sketch in
`runs/` and `output/`, never in Recorded results.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from labkit.formats import console, files, findings, promises, protocol_block, runs
from labkit.checks.result_render import Rendering, rendering
from labkit.formats.repo import shown
from labkit.checks import recheck, report_blocks
from labkit.gates import report_check
from labkit.checks.prompt_check import prompt_constants
from labkit.formats.protocol_check import (
    RECORDED_RESULTS_LABEL,
    BEFORE_RUN_CLAIMS,
    RUNS_PLACEHOLDER,
    field_name,
    fields,
    placeholder_fields,
)

# Bullet and indentation of a label line, kept when the line is rewritten.
_LEAD = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+)?")


def fill(
    text: str, field: str, value: str, line_no: int | None = None, force: bool = False
) -> str:
    """Return the protocol text with `field`'s placeholder replaced by `value`.

    Fields are read by `protocol_check.fields` — the one parser of labels
    and placeholders; a second one here mis-read a wrapped label as
    `extremes)` (usability probe 2026-10-07). The label line and its
    continuation lines become one line; everything else stays byte-identical.
    An id the stamp wrote before the placeholder (`[C1] <…>`) stays when
    VALUE names no id; a VALUE with its own ids replaces it.

    Raises ValueError with a human-readable reason (unknown label, ambiguous
    label, already filled without force) — the CLI prints it verbatim.
    """
    want = field_name(field)
    hits = [
        f
        for f in fields(text)
        if f.name == want and (line_no is None or f.line == line_no)
    ]
    if not hits:
        labels = sorted({lbl for _, lbl in placeholder_fields(text)})
        raise ValueError(
            f"no field labelled {field!r}"
            + (f" at line {line_no}" if line_no else "")
            + (
                ". Open placeholder fields: " + " · ".join(labels)
                if labels
                else ". No placeholder fields left."
            )
        )
    if len(hits) > 1:
        where = ", ".join(str(f.line) for f in hits)
        raise ValueError(
            f"label {field!r} matches lines {where} — disambiguate with --line <n>."
        )
    (f,) = hits
    if not f.placeholder and not force:
        raise ValueError(
            f"line {f.line} ({f.label!r}) is already filled: "
            f"{f.value[:80]!r}. Overwrite with --force."
        )
    # the id the stamp wrote before the placeholder stays when VALUE names
    # none: a criterion filled without it is a promise the prose drops
    stamped_id = promises.ID_PREFIX.match(f.value)
    if stamped_id and not promises.ids_in_prose(value):
        value = stamped_id.group(0).rstrip() + " " + value
    lines = text.splitlines()
    lead = _LEAD.match(lines[f.line - 1])
    assert lead is not None, "the pattern matches the empty prefix"
    lines[f.line - 1 : f.last] = [f"{lead.group(0)}**{f.label}:** {value}"]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


#: the head's stamped placeholders `protocol-fill` sets, by the label a fill
#: names: (the TOML key, its allowed values — None for a free string)
HEAD_KEYS: dict[str, tuple[str, tuple[str, ...] | None]] = {
    "type": ("type", protocol_block.TYPES),
    "repeat_cost": ("repeat_cost", protocol_block.REPEAT_COSTS),
    "kind": ("kind", protocol_block.KINDS),
    "model alias": ("alias", None),  # [model] alias, stamped by --model without a name
}
#: TOML key → its allowed values (None: free), for `head_open` and `fill_head`
HEAD_CHOICES: dict[str, tuple[str, ...] | None] = {
    key: choices for key, choices in HEAD_KEYS.values()
}


def _head_line(key: str) -> re.Pattern[str]:
    """The head's `KEY = "<…>"` placeholder line, its key and `=` kept."""
    return re.compile(rf'^({re.escape(key)}\s*=\s*)"<[^"\n]*>"\s*$')


def head_open(text: str, key: str) -> int | None:
    """Line number of the TOML head's `KEY = "<…>"` placeholder, KEY one of
    `HEAD_CHOICES`, or None once set; ValueError on another key.

    The stamp leaves `type` — and `repeat_cost`, when `labkit-init exp` got no
    `--repeat-cost` — as a placeholder in the head; `--list` named only the prose
    fields, so an agent filled those, hit the hook's "MISSING (must):
    [protocol] type" and edited the head by hand (cloud probe, Haiku 5.5,
    2026-10-13). Read inside the TOML block only (`protocol_block.toml_block_span`):
    a `type = "<…>"` line in a fenced example was taken for the head
    (audit 2026-10-15)."""
    if key not in HEAD_CHOICES:
        raise ValueError(
            f"the head's {key!r} is not a choice protocol-fill sets "
            f"({', '.join(HEAD_CHOICES)})"
        )
    lines = text.splitlines()
    span = protocol_block.toml_block_span(text)
    if span is None:
        return None
    start, end = span
    pattern = _head_line(key)
    for i in range(start, end):
        if pattern.match(lines[i]):
            return i + 1
    return None


def fill_head(text: str, key: str, value: str) -> str:
    """Set the head's KEY from its placeholder; VALUE one of `HEAD_CHOICES[key]`,
    or any non-empty string where the key is free (written by `toml_string`)."""
    n = head_open(text, key)
    choices = HEAD_CHOICES[key]
    if choices is not None and value not in choices:
        raise ValueError(f"{key} must be one of {' | '.join(choices)}, not {value!r}")
    if not value.strip():
        raise ValueError(f"{key}: an empty value")
    if n is None:
        raise ValueError(
            f"the head's {key} is already set (edit the TOML head to change it)"
        )
    lines = text.split("\n")
    written = protocol_block.toml_string(value)
    lines[n - 1] = _head_line(key).sub(lambda m: f"{m.group(1)}{written}", lines[n - 1])
    return "\n".join(lines)


#: a promise's sentence as `--list` names it and a fill addresses it:
#: `C1 sentence` — the word before "sentence" is a promise id
#: (`promises.is_block_id`), else the label is a prose field's
SENTENCE_LABEL = re.compile(r"^\s*(\S+)\s+sentence\s*$", re.I)
#: a one-line `sentence = <string>` with an optional comment, the key bare
#: or quoted, the value a basic or a literal string — the form a fill rewrites
_ONE_LINE_SENTENCE = re.compile(
    r"""^(\s*(?:sentence|"sentence"|'sentence')\s*=\s*)"""
    r"""(?:"(?:[^"\\]|\\.)*"|'[^']*')(\s*(?:#.*)?)$"""
)
_SENTENCE_KEY = re.compile(r"""^\s*(?:sentence|"sentence"|'sentence')\s*=""")


def sentence_lines(text: str) -> dict[str, int]:
    """{promise id: line number of its `sentence =`} in the TOML head. The
    ids come from `promises.parse_block`, in table order; this function
    only counts `[[promise]]` headers and finds each table's sentence key,
    so every valid spelling of the id reads (a comment after it, single
    quotes, a quoted key dropped the table, review 2026-10-20). Lines are
    cut as the fence walker cuts them (`str.splitlines`). An id is missing
    when its table has no one-line sentence key, or when the headers do not
    count the tables (an inline array of tables). Raises
    promises.PromiseError on a malformed block."""
    block = promises.parse_block(text)
    span = protocol_block.toml_block_span(text)
    if block is None or span is None:
        return {}
    lines = text.splitlines()
    tables: list[int | None] = []
    inside = False
    for i in range(span[0], span[1]):
        if protocol_block.PROMISE_HEADER.match(lines[i]):
            tables.append(None)
            inside = True
        elif protocol_block.TABLE_HEADER.match(lines[i]):
            inside = False
        elif inside and tables[-1] is None and _SENTENCE_KEY.match(lines[i]):
            tables[-1] = i + 1
    if len(tables) != len(block.promises):
        return {}
    return {p.id: n for p, n in zip(block.promises, tables) if n is not None}


def open_sentences(text: str) -> list[tuple[int | None, str]]:
    """(line, `<id> sentence`) of every [[promise]] sentence still holding the
    stamp's `<…>`, the line None where `sentence_lines` cannot place it —
    named all the same: the pre-commit refuses each one where the tables
    are owed (judge probes, 2026-10-20). Raises promises.PromiseError on a
    malformed block."""
    block = promises.parse_block(text)
    if block is None:
        return []
    where = sentence_lines(text)
    return [
        (where.get(pid), f"{pid} sentence")
        for pid in promises.placeholder_sentences(block)
    ]


def fill_sentence(text: str, pid: str, value: str, force: bool = False) -> str:
    """Set [[promise]] PID's sentence to VALUE, written by
    `protocol_block.toml_string` — the escaping an agent got wrong by hand
    (an unescaped quote, count probe 2026-10-20). The line keeps its key,
    comment and line ending; every other byte stays. Refuses a written
    sentence without force, and a sentence not on one line (edit that by
    hand); reads the block back and raises unless it holds exactly VALUE."""
    block = promises.parse_block(text)
    ids = [p.id for p in block.promises] if block is not None else []
    match = [i for i in ids if i == pid.upper()]
    if not match:
        raise ValueError(
            f"no [[promise]] {pid!r} in the TOML head"
            + (f" (ids: {', '.join(ids)})" if ids else "")
        )
    (pid,) = match
    assert block is not None
    if pid not in promises.placeholder_sentences(block) and not force:
        raise ValueError(
            f"[[promise]] {pid}'s sentence is already written. Overwrite with --force."
        )
    n = sentence_lines(text).get(pid)
    lines = text.splitlines(keepends=True)
    body = lines[n - 1].splitlines()[0] if n is not None else ""
    m = _ONE_LINE_SENTENCE.match(body) if n is not None else None
    if n is None or m is None:
        raise ValueError(
            f'[[promise]] {pid}\'s sentence is not one `sentence = "..."` line '
            f"— edit it in the TOML head by hand"
        )
    ending = lines[n - 1][len(body) :]
    lines[n - 1] = m.group(1) + protocol_block.toml_string(value) + m.group(2) + ending
    new = "".join(lines)
    after = promises.parse_block(new)
    written = {p.id: p.sentence for p in after.promises} if after else {}
    if written.get(pid) != value:
        raise ValueError(
            f"[[promise]] {pid}: the sentence did not read back as written"
        )
    return new


RUNS_HEADING = re.compile(r"^## Runs\b")

#: how `--from-run` names the declaration among what it filled
RESULT_LABEL = "[result] run"
_PROTOCOL_HEADER = re.compile(r"^\s*\[\s*protocol\s*\]\s*(?:#.*)?$")
_RESULT_HEADER = re.compile(r"^\s*\[\s*result\s*\]\s*(?:#.*)?$")
#: the `[result]` table's one line, its key and `=` and a trailing comment kept
_RESULT_RUN_LINE = re.compile(r'^(\s*run\s*=\s*)"[^"\n]*"(\s*(?:#.*)?)$')


def fill_result_run(text: str, run_id: str, force: bool = False) -> str:
    """Declare RUN_ID as the protocol's reported result: `[result] run =
    "<id>"` in the TOML block, the one declaration report-check holds the
    protocol to (`protocol_block.declared_run`). Without a `[result]` the
    table is written right after the `[protocol]` table's last key; one
    naming RUN_ID already leaves the text as it is; one naming another run
    is refused without FORCE. Every other byte stays, and the block is read
    back and must declare exactly RUN_ID. Raises BlockError on a head that
    does not read, ValueError on the refusal or a block without
    `[protocol]`."""
    current = protocol_block.declared_run(text)
    if current == run_id:
        return text
    if current is not None and not force:
        raise ValueError(
            f"[result] declares {current}, not {run_id} — --force to replace it"
        )
    span = protocol_block.toml_block_span(text)
    if span is None:
        raise ValueError("no ```toml block — the head is where the result is declared")
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
#: question's answer in two plain sentences, read within the Limit lines;
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
    line, the Limit lines and the Runs entry as `runs/<run_id>/metrics.json`
    and the covering records render them (`result_render.rendering`; newest
    completed run when RUN_ID is None), a Limit line of a record that covers
    the run no longer dropped; the Summary's Conclusion stays the author's
    (`WRITTEN_AFTER_RUN`). Returns (text, what was filled, run_id). A filled
    Recorded results, or a `[result]` naming another run, is refused without `force`."""
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
    declared = fill_result_run(text, run.name, force=force)
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
    # a Limit line of a record that no longer covers the run is labkit's own
    # stale line, never the author's prose: it goes with the write-back
    text, dropped = drop_stray_limits(text, r.limits)
    filled += [f"dropped {label}" for label in dropped]
    return text, filled, run.name


def drop_stray_limits(
    text: str, keep: tuple[tuple[str, str], ...]
) -> tuple[str, list[str]]:
    """TEXT without the Limit lines no covering record decides (labels not in
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
            f"no [result] run declared — `--from-run <run_id>` declares the run "
            f"and writes the result; {why}"
        )
    run = runs.run_path(area, declared)
    if not runs.metrics_path(run).is_file():
        raise ValueError(
            f"[result] declares {declared}, but runs/{declared}/metrics.json is not there"
        )
    return run


def render_result(text: str, area: Path) -> tuple[str, list[str]]:
    """`--render`: the result section written again from its sources for the
    declared run — the Recorded results line, the Limit lines (stray ones dropped) and,
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
            # below Recorded results and the Limit lines already under it: in
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


def adopt(protocol: Path, before: str, after: str) -> int:
    """Adopt the result AFTER writes into PROTOCOL: write it, run report-check
    on the written protocol, and on a blocker put BEFORE back and return 1.
    The one path by which a number becomes the result: whatever stands in
    Recorded results through here has passed every check (the write-back is the
    declaration, the check is what makes it hold; a declaration the check
    refuses is no weaker kind of result, it is none). The gates at the stop
    and the commit (`report-check --if-reported`) hold the same line to a
    hand-written or later-changed answer. A check that ends in an exception
    puts BEFORE back too and re-raises: until 0.99.0 only a blocker exit
    restored the file, and the unchecked declaration stayed (audit
    2026-10-19, a check script printing a byte no codec reads). Both writes
    go whole or not at all (`files.write_atomic`): a reader, or the next
    check, sees the protocol as it was or as proposed, never half of
    either; the check is told it holds the proposal (`report_check.PROPOSED`)."""
    files.write_atomic(protocol, after)
    try:
        rc = report_check.report_check(
            protocol.parent, protocol, state=report_check.PROPOSED, text=after
        )
    except BaseException:
        files.write_atomic(protocol, before)
        raise
    if rc == 0:
        return 0
    files.write_atomic(protocol, before)
    print(
        f"protocol-fill: not adopted — report-check refuses the written result "
        f"(above); {protocol.name} is as it was. Pass the checks first, or leave "
        f"the number a sketch in runs/ (an exploration reports no result). A "
        f"refusal is a finding to report, not an obstacle to route around: a "
        f"report that mentions this run without adopting it discusses it — "
        f"`{report_blocks.discuss_command(shown(protocol, Path.cwd()), '<run_id>', '<REPORT>')}` "
        f"— and leaves the question open; the run's numbers are not the result."
    )
    return 1


def _write_back(args: argparse.Namespace, text: str) -> int:
    """`--from-run`: the number from the run's metrics.json into the protocol,
    adopted as the result only when report-check passes on it (`adopt`)."""
    protocol = args.protocol.resolve()
    try:
        new, filled, run_id = from_run(
            text,
            protocol.parent,
            None if args.from_run == "newest" else args.from_run,
            force=args.force,
        )
    except ValueError as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    print(
        f"filled from run {run_id}: {', '.join(filled) or 'nothing (all written already)'}"
        f" — adopting as the result:"
    )
    rc = adopt(protocol, text, new)
    if rc == 0:
        _name_yours(
            new, protocol.parent, recheck.chosen_run(protocol.parent, new, run_id)
        )
    return rc


def _name_yours(text: str, area: Path, run: Path) -> None:
    """After an adopted write-back: the after-run fields still open, which
    the author writes (Conclusion: the question's answer in two sentences within
    the Limits; Raw output from the rows), and the run's output files — the
    post hook asked for Raw output only after the commit, and two of three
    cold agents filled it in a second round (sandbox, 2026-10-21)."""
    open_ = [
        (n, label)
        for n, label in placeholder_fields(text)
        if label in WRITTEN_AFTER_RUN
    ]
    if not open_:
        return
    outputs = runs.read_outputs(run) or []
    where = ", ".join(shown(o.path, area) for o in outputs) or f"{shown(run, area)}/"
    print(f"still yours, after the run (its rows: {where}):")
    for n, label in open_:
        print(f"{n:4d}  {label}")


def _list_open(text: str) -> int:
    """`--list`: every open field, the TOML head's placeholders (`HEAD_KEYS`)
    and open promise sentences first; then, each under its own line, the fields `--from-run`
    writes and the after-run fields the author writes. Listed among the rest
    they read as owed before the run: cold agents filled them with "pending
    run" or "filled after the run", and the write after the run was then
    refused without --force (cloud 2026-10-14, sandbox 2026-10-21)."""
    sentences: list[tuple[int | None, str]] = [
        (n, f"{label}  (TOML head: this promise in one sentence)")
        for n, label in open_sentences(text)
    ]
    head: list[tuple[int | None, str]] = [
        (
            n,
            f"{label}  (TOML head: "
            f"{' | '.join(choices) if choices else 'the alias from models.toml'})",
        )
        for label, (key, choices) in HEAD_KEYS.items()
        if (n := head_open(text, key)) is not None
    ]
    holes = head + sentences + list(placeholder_fields(text))
    if not holes:
        print("no placeholder fields left")
    after = WRITTEN_BY_RUN + WRITTEN_AFTER_RUN
    groups = (
        (None, [(n, label) for n, label in holes if label not in after]),
        (
            "after the run — `protocol-fill <PROTOCOL> --from-run` writes these; leave them:",
            [(n, label) for n, label in holes if label in WRITTEN_BY_RUN],
        ),
        (
            "after the run — yours, once its rows exist (`--from-run` names them); leave them now:",
            [(n, label) for n, label in holes if label in WRITTEN_AFTER_RUN],
        ),
    )
    for title, group in groups:
        if title is not None and group:
            print(title)
        for n, label in group:
            # a sentence the table walk cannot place is named all the same
            print(f"{n:4d}  {label}" if n is not None else f"   ?  {label}")
    return 0


def assignments_of(field: str | None, value: list[str]) -> list[tuple[str, str]]:
    """The (label, value) pairs a command line asks for: `FIELD VALUE...` is
    one pair, `LABEL=VALUE [LABEL=VALUE ...]` (every word carries `=`; a
    value with spaces is one quoted word) one pair per word. Empty when the
    line names no value. Why the one-call form: seven cold agents filled six
    fields in six calls and named it their largest sink (cloud probes,
    2026-10-13)."""
    if not field:
        return []
    words = [field, *value]
    if all("=" in w for w in words):
        return [(lb, v) for lb, v in (w.split("=", 1) for w in words)]
    if not value:
        return []
    return [(field, " ".join(value))]


def fill_many(
    text: str,
    assignments: list[tuple[str, str]],
    line_no: int | None = None,
    force: bool = False,
) -> str:
    """`fill` applied in order — `fill_head` for the head's `type`, `repeat_cost`
    and `model alias` (`HEAD_KEYS`), `fill_sentence` for `<id> sentence`;
    the first ValueError leaves the caller's file untouched — all or
    nothing."""
    for label, value in assignments:
        if not label.strip() or not value.strip():
            raise ValueError(f"empty label or value in {label}={value!r}")
        sentence = SENTENCE_LABEL.match(label)
        if sentence and not promises.is_block_id(sentence.group(1).upper()):
            sentence = None  # a prose label such as "Key sentence"
        if label.strip().lower() in HEAD_KEYS:
            text = fill_head(text, HEAD_KEYS[label.strip().lower()][0], value)
        elif sentence:
            if line_no is not None:
                raise ValueError(
                    f"--line names a prose field; {label.strip()!r} is a "
                    f"promise's sentence, addressed by its id"
                )
            text = fill_sentence(text, sentence.group(1), value, force=force)
        else:
            text = fill(text, label, value, line_no=line_no, force=force)
    return text


def _prompts_file(protocol: Path, text: str) -> int:
    """`--prompts` on PROTOCOL: the Prompt block from the scripts' PROMPT constants."""
    try:
        new = fill_prompts(text, prompt_constants(protocol.resolve().parent))
    except ValueError as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    files.write_atomic(protocol, new)
    print("filled: Prompt (from the scripts' PROMPT constants)")
    return 0


def into_report(text: str, area: Path, report: str, protocol: str) -> tuple[str, str]:
    """`--into`: REPORT with the declared result as a generated block — the
    protocol's Recorded results and Limit lines as rendered (`report_blocks.block_body`),
    replaced in place or appended (`report_blocks.write_block`).
    PROTOCOL is the protocol's path relative to the report, the block's
    owner: its blocks are replaced whichever run they showed. (report text,
    run id). Raises ValueError without a declared run or its metrics.json,
    and on a block in REPORT that does not read."""
    run = declared_run_dir(text, area, "a report shows a declared result only")
    body = report_blocks.block_body(rendering(area, text, run))
    return report_blocks.write_block(report, protocol, run.name, body), run.name


def _into_file(protocol: Path, text: str, report: Path) -> int:
    """`--into` on PROTOCOL: write REPORT's block when it differs, say so."""
    before = report.read_text(encoding="utf-8") if report.is_file() else ""
    try:
        new, run_id = into_report(
            text,
            protocol.resolve().parent,
            before,
            report_blocks.path_from_report(protocol, report),
        )
    except (ValueError, protocol_block.BlockError) as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    if new != before:
        files.write_atomic(report, new)
    print(
        f"{report}: the result block for run {run_id} "
        + ("written" if new != before else "unchanged — it says what its sources say")
    )
    return 0


def discuss_into(
    text: str, area: Path, report: str, protocol: str, run_id: str, why: str
) -> str:
    """`--discuss RUN_ID --why WHY --into`: REPORT with the block discussing
    RUN_ID of the protocol whose TEXT is given — its head holding PROTOCOL
    (the protocol's path relative to the report), the run and WHY, its
    line written from them (`report_blocks.write_discussion`): the block of
    that protocol and run replaced in place, or one appended; other
    discussions stay. Raises ValueError when the protocol declares RUN_ID
    as its result (the result block shows it: `--into` without
    `--discuss`), when AREA holds no `runs/<RUN_ID>/`, on a why or a head
    string the block cannot hold (`report_blocks.discussion_lines`), and on
    a block in REPORT that does not read or is there twice."""
    if protocol_block.declared_run(text) == run_id:
        raise ValueError(
            f"run {run_id} is the protocol's declared result — a declared result "
            f"is reported, not discussed: `--into` without `--discuss` writes its "
            f"result block"
        )
    if not runs.run_path(area, run_id).is_dir():
        raise ValueError(
            f"no runs/{run_id}/ in {area.name} — a discussion names a run of the "
            f"protocol's area"
        )
    return report_blocks.write_discussion(report, protocol, run_id, why)


def _discuss_file(
    protocol: Path, text: str, report: Path, run_id: str, why: str
) -> int:
    """`--discuss … --into` on PROTOCOL: write REPORT's discussion block of
    RUN_ID when it differs, say so."""
    before = report.read_text(encoding="utf-8") if report.is_file() else ""
    try:
        new = discuss_into(
            text,
            protocol.resolve().parent,
            before,
            report_blocks.path_from_report(protocol, report),
            run_id,
            why,
        )
    except (ValueError, protocol_block.BlockError) as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    if new != before:
        files.write_atomic(report, new)
    print(
        f"{report}: the discussion block of run {run_id} "
        + ("written" if new != before else "unchanged")
    )
    return 0


def _render_file(protocol: Path, text: str) -> int:
    """`--render` on PROTOCOL: write the rendering when it differs, say what changed."""
    try:
        new, written = render_result(text, protocol.resolve().parent)
    except (ValueError, protocol_block.BlockError) as exc:
        console.refuse("protocol-fill", str(exc))
        return 2
    if new != text:
        files.write_atomic(protocol, new)
    print(
        "rendered: "
        + (
            ", ".join(written)
            or "nothing changed — the result says what its sources say"
        )
    )
    return 0


def _run_mode(args: argparse.Namespace, text: str) -> int | None:
    """The exit code of the mode ARGS name (--list, --prompts, --render,
    --into, --from-run), or None when they name none: a field fill."""
    if args.list:
        try:
            return _list_open(text)
        except promises.PromiseError as exc:
            console.refuse("protocol-fill", str(exc))
            return 2
    if args.prompts:
        return _prompts_file(args.protocol, text)
    if args.render:
        return _render_file(args.protocol, text)
    if args.discuss is not None:
        return _discuss_file(args.protocol, text, args.into, args.discuss, args.why)
    if args.into is not None:
        return _into_file(args.protocol, text, args.into)
    if args.from_run is not None:
        return _write_back(args, text)
    return None


def main(argv: list[str]) -> int:
    """Fill fields, adopt a run, render the protocol or write a report block."""

    ap = argparse.ArgumentParser(
        prog="protocol-fill",
        description="Fill protocol fields, adopt a run or render recorded results "
        "in a protocol or report. Fields in a PROTOCOL-*.md are matched "
        "by label (never by quoting the placeholder text): "
        "`FIELD VALUE...` fills one, `LABEL=VALUE [LABEL=VALUE ...]` "
        "fills several in one call (all or nothing). --list shows what "
        "is still open.",
    )
    ap.add_argument("protocol", type=Path)
    ap.add_argument("field", nargs="?", help="field label († optional), or LABEL=VALUE")
    ap.add_argument(
        "value", nargs="*", help="the field's new value, or further LABEL=VALUE"
    )
    ap.add_argument(
        "--list", action="store_true", help="list open placeholder fields and exit"
    )
    ap.add_argument(
        "--prompts",
        action="store_true",
        help="write the Prompt block from the area scripts' PROMPT constants",
    )
    ap.add_argument(
        "--render",
        action="store_true",
        help="write the result section again from its sources for the declared run: "
        "the Recorded results line, the Limit lines (stray ones dropped), the Prompt block",
    )
    ap.add_argument(
        "--into",
        type=Path,
        default=None,
        metavar="REPORT",
        help="write the declared result into REPORT (a report outside the protocol) "
        "as a generated block: Recorded results and Limit lines as rendered; the "
        "protocol's block is replaced (also after a new run), else one is appended",
    )
    ap.add_argument(
        "--discuss",
        default=None,
        metavar="RUN_ID",
        help="with --why and --into: write a discussion block of RUN_ID into REPORT — "
        "a run the report looks at without reporting it; the block's head holds the "
        "protocol, the run and the why, its line is written from them (replaced in "
        "place for the same protocol and run, else appended)",
    )
    ap.add_argument(
        "--why",
        default=None,
        help="with --discuss: what refused the adoption, what was found — one line",
    )
    ap.add_argument(
        "--from-run",
        nargs="?",
        const="newest",
        default=None,
        metavar="RUN_ID",
        help="adopt the run as the result: declare it as `[result] run` in the TOML head and write Recorded results and Runs lines from its metrics.json, kept only when report-check passes "
        "(the area's newest completed run without RUN_ID); the Summary's Conclusion stays yours — the question's answer in two sentences, within the Limits",
    )
    ap.add_argument(
        "--line",
        type=int,
        default=None,
        help="line number, when the label is ambiguous",
    )
    ap.add_argument(
        "--force", action="store_true", help="overwrite a field that is already filled"
    )
    args = ap.parse_args(argv)
    if (args.discuss is None) != (args.why is None) or (
        args.discuss is not None and args.into is None
    ):
        ap.error("--discuss RUN_ID goes with --why TEXT and --into REPORT")
    if not args.protocol.is_file():
        console.refuse("protocol-fill", f"no such file: {args.protocol}")
        return 2
    text = args.protocol.read_text(encoding="utf-8")
    moded = _run_mode(args, text)
    if moded is not None:
        return moded
    assignments = assignments_of(args.field, args.value)
    if not assignments:
        ap.error(
            "need FIELD and VALUE, LABEL=VALUE..., --list, --render, --into or --from-run"
        )
    if args.line is not None and len(assignments) > 1:
        ap.error("--line goes with one FIELD, not with LABEL=VALUE")
    try:
        new = fill_many(text, assignments, line_no=args.line, force=args.force)
    except ValueError as exc:  # all or nothing: the file is untouched
        console.refuse("protocol-fill", str(exc))
        return 2
    files.write_atomic(args.protocol, new)
    print("filled: " + ", ".join(label for label, _ in assignments))
    return 0


def cli() -> None:
    """Entry point for the installed `protocol-fill` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
