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
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from string import Template
from pathlib import Path

from labkit.formats import markdown
from labkit.formats import (
    evidence,
    finding_limits,
    protocol_block,
    runs,
)
from labkit.checks.result_render import Rendering, rendering
from labkit.checks import recheck
from labkit.checks.prompt_check import prompt_constants
from labkit.formats.protocol_check import (
    display_label,
    PLACEHOLDER_IN_PROMPT,
    RECORDED_RESULTS_LABEL,
    BEFORE_RUN_CLAIMS,
    RUNS_PLACEHOLDER,
    field_lines,
    field_name,
    field_region_end,
    fields,
    insert_line,
    is_stamp_placeholder_block,
    replace_lines,
    as_compared,
    odd_separator_refusal,
    PromptBlock,
    field_prompt_blocks,
)
from labkit.tools.protocol_edit import fill


#: how `--from-run` names the declaration among what it filled
RESULT_LABEL = "[result] run"
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
    another run is declared does not cover the new one. Every other byte
    stays, and the block is read back and
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
    body = protocol_block.table_span(lines, *span, "result")
    for i in range(*body) if body is not None else ():
        m = _RESULT_RUN_LINE.match(lines[i])
        if m:
            lines[i] = f'{m.group(1)}"{run_id}"{m.group(2)}'
            return
    raise ValueError(
        '[result] has no one-line `run = "…"` — edit the TOML head by hand'
    )


def _insert_result_table(lines: list[str], span: tuple[int, int], run_id: str) -> None:
    """Write `[result]` with RUN_ID after the last key of the `[protocol]`
    table in LINES[SPAN] — before the comments and tables that follow it."""
    body = protocol_block.table_span(lines, *span, "protocol")
    if body is None:
        raise ValueError("no [protocol] table in the ```toml block")
    last_key = body[0] - 1  # the header, when the table holds no key
    for j in range(*body):
        if lines[j].strip() and not lines[j].lstrip().startswith("#"):
            last_key = j
    lines[last_key + 1 : last_key + 1] = ["", "[result]", f'run = "{run_id}"']


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
    heading = protocol_block.runs_section(lines)
    if heading is None:
        raise ValueError("no `## Runs` section to name the run in")
    end = markdown.section_end(lines, heading)
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
    protocol's answering run, `recheck.chosen_run`, when RUN_ID is None), a
    Limitation line of a record that no longer covers the run dropped; the
    Summary's Conclusion stays the author's (`WRITTEN_AFTER_RUN`). Returns
    (text, what was filled, run_id). A filled Recorded results is refused
    without `force`; a `[result]` naming another run is refused always
    (`fill_result_run`: withdraw it first)."""
    run = recheck.chosen_run(area, text, run_id)
    r = rendering(area, text, run, found=evidence.decision_reviews_in_tree(area))
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
    lines = field_lines(text)
    for f in sorted(fields(text), key=lambda f: -f.line):
        label = display_label(f.label)
        if label.startswith(finding_limits.LIMIT_PREFIX) and label not in keep_labels:
            del lines[f.line - 1 : f.last]
            dropped.append(label)
    return "".join(lines), dropped


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
    r: Rendering = rendering(
        area, text, run, found=evidence.decision_reviews_in_tree(area)
    )
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
        lines = field_lines(text)
        by_label = {display_label(f.label): f for f in fields(text)}
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
            replace_lines(lines, have.line, have.last, line)
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
            # would read #3, #2, #1)
            at = answer.last
            for f in fields(text):
                if f.line == at + 1 and f.label.startswith(finding_limits.LIMIT_PREFIX):
                    at = f.last
            insert_line(lines, at, line)
        text = "".join(lines)
        written.append(label)
    return text, written


#: what the Prompt field's line says once `fill_prompts` wrote its blocks
#: below an empty one: the sentences above the blocks are not sent
PROMPT_FIELD_NOTE = (
    "The model receives exactly the text inside each block; the sentence above "
    "a block names its constant and how its placeholders are filled, and is "
    "not sent."
)


def _sentence(name: str, slots: Iterable[str]) -> str:
    """`` `NAME` — <what it is for; `slot`: how it is filled …> ``, each of
    SLOTS once, in order. Pure."""
    how = "".join(f"; `{slot}`: how it is filled" for slot in dict.fromkeys(slots))
    return f"`{name}` — <what it is for{how}>"


def prompt_sentence(name: str, prompt: str) -> str:
    """The sentence `fill_prompts` writes above the block of constant NAME
    until someone fills it: the name, then a placeholder for what the
    prompt is for and how each `{placeholder}` of PROMPT is filled, in the
    order of first use. Pure."""
    return _sentence(name, PLACEHOLDER_IN_PROMPT.findall(prompt))


def template_sentence(name: str, template: str) -> str:
    """`prompt_sentence` for a template file a pipeline fills with
    `string.Template` (stagekit): its placeholders are `$name`, each named
    as `$name`. Pure."""
    return _sentence(name, (f"${n}" for n in Template(template).get_identifiers()))


@dataclass(frozen=True)
class PromptSource:
    """What `fill_prompts` writes for one name: the SENTENCE above its block
    until someone fills it, and the LINES of the block."""

    sentence: str
    lines: list[str]


def prompt_sources(
    constants: Mapping[str, str], templates: Mapping[str, str]
) -> dict[str, PromptSource]:
    """Every PROMPT constant and template file by name, as `fill_prompts`
    writes it: a constant's lines as `str.splitlines` gives them, a
    template's as the exact comparison reads it (`as_compared`, split at
    LF only), each with its placeholder sentence (`prompt_sentence`,
    `template_sentence`). Raises ValueError for a name that is both, and
    for a template carrying a line separator no protocol line can hold
    (`odd_separator_refusal`). Pure."""
    both = sorted(set(constants) & set(templates))
    if both:
        raise ValueError(f"{both} named both as a PROMPT constant and as a template")
    for name, template in templates.items():
        refusal = odd_separator_refusal(name, template)
        if refusal is not None:
            raise ValueError(refusal)
    return {
        **{
            k: PromptSource(prompt_sentence(k, v), v.splitlines())
            for k, v in constants.items()
        },
        **{
            k: PromptSource(template_sentence(k, v), as_compared(v).split("\n"))
            for k, v in templates.items()
        },
    }


def fill_prompts(
    text: str,
    constants: dict[str, str],
    templates: Mapping[str, str] | None = None,
) -> str:
    """Return the protocol text with the Prompt field written from the
    scripts' `PROMPT` / `PROMPT_<VARIANT>` constants, `PROMPT` first, and
    from TEMPLATES, template files by the name their pipeline registers
    them under (`protocol-fill --prompt-file`): one block per constant or
    template, holding exactly what the model receives, under a sentence
    that names it (`` `NAME` — … ``) and is not sent. A sentence written
    for a name stays as written; for a new one the sentence is
    `prompt_sentence`'s placeholder (`template_sentence`'s for a template).
    An empty field line gets PROMPT_FIELD_NOTE; a written one stays.

    The blocks are what `code-check` holds the script to (prompt drift);
    the label fill cannot reach a code block. What stands below the field
    (`protocol_check.field_region_end`) is written anew, except a block
    whose sentence names a constant the scripts do not hold as a PROMPT
    (`EXTRA_CONTEXT`, a person's instruction): it stays. The blocks keep
    the order they stand in; a constant not yet there is added after
    them. A block no sentence names is:

    - the stamp's placeholder: replaced;
    - while no block has a sentence, the one block an earlier fill wrote:
      replaced;
    - any other: refused (ValueError, nothing written), as it would be lost.

    Raises ValueError, too, without a constant or template, for a name
    that is both, without exactly one Prompt field, for a block that never
    closes, and for prose below the field that is no sentence."""
    sources = prompt_sources(constants, templates or {})
    if not sources:
        raise ValueError(
            "no PROMPT constant readable in the area's scripts (an f-string "
            "renders at run time and cannot be copied) — write the block by hand"
        )
    found = fields(text)
    hits = [n for n, f in enumerate(found) if f.name == "prompt"]
    if len(hits) != 1:
        where = ", ".join(str(found[n].line) for n in hits) or "none"
        raise ValueError(f"expected one Prompt field, found {where}")
    (n,) = hits
    f = found[n]
    lines = text.splitlines()
    end = field_region_end(lines, found, n)
    kept = _prompt_segments(
        lines, range(f.last, end), field_prompt_blocks(lines, found, n), sources
    )
    new = sorted(
        set(sources) - {s.name for s in kept}, key=lambda c: (c != "PROMPT", c)
    )
    below: list[str] = []
    for s in [*kept, *[PromptSegment(name, "", ()) for name in new]]:
        if s.name not in sources:  # another constant's block, as written
            below += ["", *s.lines]
            continue
        below += [
            "",
            f"  {s.sentence or sources[s.name].sentence}",
            "",
            "  ```text",
            *[f"  {ln}" if ln else "" for ln in sources[s.name].lines],
            "  ```",
        ]
    if end < len(lines):  # a blank line before the next field or heading
        below.append("")
    head = lines[f.line - 1 : f.last]
    if not f.value.strip():
        head[-1] = f"{head[-1].rstrip()} {PROMPT_FIELD_NOTE}"
    lines[f.line - 1 : end] = [*head, *below]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


@dataclass(frozen=True)
class PromptSegment:
    """One block below the Prompt field as `fill_prompts` keeps it: the
    constant its sentence NAMEs, that SENTENCE as written, and — for a
    constant the scripts hold as no PROMPT — its LINES from sentence to
    closing fence, kept as they stand (empty for a PROMPT constant, whose
    block is written anew)."""

    name: str
    sentence: str
    lines: tuple[str, ...]


def _prompt_segments(
    lines: list[str],
    below: range,
    blocks: list[PromptBlock],
    constants: Collection[str],
) -> list[PromptSegment]:
    """What `fill_prompts` keeps of the lines BELOW the Prompt field's value
    (0-based indexes into LINES), whose blocks are BLOCKS
    (`protocol_check.field_prompt_blocks`): each block a sentence names, in
    the order they stand (`PromptSegment`; LINES only for a constant not
    among CONSTANTS). Blank lines, the stamp's placeholder block and —
    while no block has a sentence — one unnamed block, an earlier fill's,
    are dropped. Raises ValueError for any other unnamed block, or a line
    that is none of these. Pure."""
    kept: list[PromptSegment] = []
    unnamed: list[int] = []
    covered: set[int] = set()
    for b in blocks:
        covered.update(range(b.opening, b.closing + 1))
        if b.sentence is None or b.name is None:
            if not is_stamp_placeholder_block("\n".join(b.body)):
                unnamed.append(b.opening + 1)
            continue
        covered.add(b.sentence)
        own = () if b.name in constants else tuple(lines[b.sentence : b.closing + 1])
        kept.append(PromptSegment(b.name, lines[b.sentence].strip(), own))
    # an unnamed block is the one an earlier fill wrote only where no block
    # has a sentence yet; beside named blocks it is someone's own
    allowed = 0 if kept else 1
    if len(unnamed) > allowed:
        raise ValueError(
            f"line{'s' if len(unnamed) > 1 else ''} "
            f"{', '.join(map(str, unnamed))}: {len(unnamed)} Prompt block(s) no "
            f"sentence names — --prompts replaces only the block an earlier fill "
            f"wrote, before any block had a sentence; name each with a sentence "
            f"above it (`NAME` — what it is for), or remove it"
        )
    stray = [j for j in below if lines[j].strip() and j not in covered]
    if stray:
        raise ValueError(
            f"line {stray[0] + 1}: prose below the Prompt field that is "
            f"no sentence above a block — --prompts would drop it; move it into "
            f"the field's line or a sentence (`NAME` — …)"
        )
    return kept


def without_result(text: str) -> str:
    """Withdraw only the result declaration — the `[result]` table, also one
    that does not read; preserve registration and run evidence."""
    span = protocol_block.toml_block_span(text)
    if span is None:
        return text
    lines = text.split("\n")
    body = protocol_block.table_span(lines, *span, "result")
    if body is None:
        return text
    del lines[body[0] - 1 : body[1]]  # the header and its body
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
    heading = protocol_block.runs_section(lines)
    assert heading is not None, "runs_line wrote the section's entry"
    end = markdown.section_end(lines, heading)
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
