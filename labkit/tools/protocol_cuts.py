"""protocol_cuts — the protocol template cut to what a repeat cost and a lane owe.

The template's sections by key (`ProtocolBlocks`), the `low` cut and
the quick block, short placeholders, the pilot part and the report fields
inserted later (`pilot_and_report`, `insert_report_fields`), the fields a
deterministic area fills itself, the placeholders of the counting and the
estimator skeleton, and a new protocol's id. Pure text in, text out;
`scaffold` writes the result.
"""

from __future__ import annotations

import re

import uuid
from pathlib import Path
from labkit.formats import promises, protocol_block
from labkit.formats.protocol_check import model_named
from labkit.formats.repo import (
    repo_protocols,
)


# Report-grade fields live IN their section and carry a dagger in the label; a
# whole section is report-grade when its heading carries one. The pilot part
# leaves them out; `--report` fills them into their sections when a run
# graduates, so one topic never sits in two places.
DAGGER = "†"


LOW_TAG = "<!-- l -->"


LOW_MODEL_TAG = "<!-- lm -->"  # owed at low repeat cost only with a model in the loop
LOW_BAR_TAG = "<!-- lb -->"  # owed at low repeat cost when the number has a bar (kind fit or apply)
#: any cut mark with its leading blank — the one pattern every writer strips
CUT_MARK = re.compile(r" ?<!-- l[bm]? -->")


#: which template section a heading is about — a report field is placed by topic
SECTION_KEYS = (
    "summary",
    "intent",
    "result",
    "context",
    "setup",
    "checks",
    "runs",
    "follow-up",
    "notes",
)


FIELD_LABEL = re.compile(r"^-\s+\*\*(.+?)\s*:?\*\*")


ProtocolBlocks = list[tuple[str, str, list[list[str]]]]


def section_key(heading: str) -> str | None:
    """Which template section a '## …' heading corresponds to, by its first word."""
    low = heading.lstrip("#").strip().lower()
    return next((k for k in SECTION_KEYS if low.startswith(k)), None)


def _segments(text: str) -> list[tuple[str, list[str]]]:
    """[(heading line or '', body lines)] — the preamble comes as heading ''."""
    segs: list[tuple[str, list[str]]] = [("", [])]
    lines = text.splitlines()
    starts = set(protocol_block.section_starts(lines))
    for i, line in enumerate(lines):
        if i in starts:
            segs.append((line, []))
        else:
            segs[-1][1].append(line)
    return segs


def _items(body: list[str]) -> list[list[str]]:
    """A section body as bullet items; continuation lines stay with their item."""
    items: list[list[str]] = []
    fenced = protocol_block.fenced_lines(body)
    for i, line in enumerate(body):
        starts = line.startswith("- ") and i not in fenced
        if starts or not items:
            items.append([line])
        else:
            items[-1].append(line)
    return items


def _label_of(item: list[str]) -> str:
    m = FIELD_LABEL.match(item[0])
    return (m.group(1) if m else item[0]).replace(DAGGER, "").strip().lower()


def _untag(line: str) -> str:
    return CUT_MARK.sub("", line)


def low_cut(tmpl: str, kind: str, model: bool = False) -> str:
    """The `low` cut: the preamble, and of every section only the items
    tagged `<!-- l -->` — with a bar (KIND fit or apply) also `<!-- lb -->`,
    with a model also `<!-- lm -->` — under their heading."""
    from labkit.formats.standard_contract import has_bar

    tags = (LOW_TAG,)
    if has_bar(kind):
        tags += (LOW_BAR_TAG,)
    if model:
        tags += (LOW_MODEL_TAG,)
    out: list[str] = []
    for heading, body in _segments(tmpl):
        if not heading:
            out.extend(line for item in _items(body) for line in item)
            continue
        kept = [item for item in _items(body) if any(t in item[0] for t in tags)]
        if not kept:
            continue
        if out and out[-1].strip():
            out.append("")
        out += [heading, ""] + [_untag(line) for item in kept for line in item]
    return "\n".join(out).rstrip() + "\n"


def bar_cut(tmpl: str, kind: str) -> str:
    """TMPL as a KIND without a bar is stamped at every tier: the fields a
    bar owes (tagged `<!-- lb -->`: criterion, admissibility condition,
    Model / tool, null condition) and the promise tables go — a computation owes
    its question (standard 0.22). A fit or an apply comes back unchanged.
    The low cut keeps fewer fields still (`low_cut`)."""
    from labkit.formats.standard_contract import has_bar

    if has_bar(kind):
        return tmpl
    out: list[str] = []
    for heading, body in _segments(tmpl):
        if heading:
            out.append(heading)
        for item in _items(body):
            if LOW_BAR_TAG not in item[0]:
                out.extend(item)
    return without_promise_tables("\n".join(out).rstrip() + "\n")


def quick_block(tmpl: str, kind: str) -> str:
    """The promise tables of the low cut. A number with a bar (KIND fit
    or apply) keeps them: the measure skeletons read `margin`, `max_empty`
    and the null band from the block. (Until 0.92 they became a commented
    hint here, a rule written for the count; once the count lost its tables
    in 0.87.0 the hint hit only the model case, and every judge area stamped
    at low repeat cost failed its first run with a TypeError — found by a low-lane
    probe, 2026-10-15.) For a computation the tables go: it has no bar to clear."""
    from labkit.formats.standard_contract import has_bar

    if has_bar(kind):
        return tmpl
    # a deterministic computation has no bar to clear: no promise tables, no
    # criterion — five cold agents each invented a tautological [C1]
    # (cloud probes 2026-10-12); the number is held by --check and finalize
    return without_promise_tables(tmpl)


def without_promise_tables(text: str) -> str:
    """TEXT with every `[[promise]]` table of its TOML block removed, and
    the comment lines right above each; nothing outside the block changes.
    The tables are found by the block's own structure (the fence walker,
    then table headers), not by a pattern over the text: a pattern took the
    block's closing fence with the last table, and every count stamped at
    low repeat cost ended inside its TOML block (count probes, 2026-10-20). Reads
    the block back and raises ValueError unless `[protocol]` is unchanged,
    no promise is left and the block is still closed."""
    span = protocol_block.toml_block_span(text)
    if span is None:
        return text
    lines = text.splitlines(keepends=True)
    start, end = span
    body = lines[start:end]
    keep: list[str] = []
    in_promise = False
    for line in body:
        if protocol_block.PROMISE_HEADER.match(line):
            in_promise = True
            while keep and keep[-1].lstrip().startswith("#"):
                keep.pop()  # the comment that introduces the tables
            continue
        if protocol_block.TABLE_HEADER.match(line):
            in_promise = False
        if not in_promise:
            keep.append(line)
    while keep and not keep[-1].strip():
        keep.pop()
    new = "".join(lines[:start] + keep + lines[end:])
    before, after = (
        protocol_block.parse_toml_block(text),
        protocol_block.parse_toml_block(new),
    )
    new_span = protocol_block.toml_block_span(new)
    closed = new_span is not None and new_span[1] < len(new.splitlines())
    if (
        "promise" in after
        or after.get("protocol") != before.get("protocol")
        or (end < len(lines) and not closed)
    ):
        raise ValueError(
            "without_promise_tables: the block did not read back as the same "
            "[protocol] without promises, closed"
        )
    return new


PLACEHOLDER_WIDTH = 72  # a one-line hint; the long form is `protocol-check --guide`


def short_placeholders(text: str) -> str:
    """Every stamped `<…>` placeholder on one line. The template's placeholders
    carry the field guide's prose — a third of a cold agent's reading time
    (cloud probes 2026-10-12, five of five); the stamped protocol keeps the
    label and a one-line hint, `protocol-check --guide` the long form.
    Fenced blocks and the TOML head are untouched."""
    out: list[str] = []
    lines = text.split("\n")
    fenced = protocol_block.fenced_lines(lines)
    i = 0
    while i < len(lines):
        line = lines[i]
        head = re.match(
            r"^(- \*\*[^*]+\*\*:?\s*(?:<!-- l[bm]? -->\s*)?|\s+(?:[^<*]*\*\*:?\s*)?)<(?!!--)(.*)$",
            line,
        )
        if i in fenced or head is None or line.rstrip().endswith(">"):
            out.append(line)
            i += 1
            continue
        # a placeholder opened on this line and not closed: gather its continuation
        body = [head.group(2)]
        j = i + 1
        while (
            j < len(lines)
            and lines[j].startswith("  ")
            and not lines[j].startswith("  ```")
        ):
            body.append(lines[j].strip())
            j += 1
        full = " ".join(body).rstrip(">").strip()
        cut = full
        for mark in (" — ", "; ", " (", ": "):
            k = cut.find(mark)
            if 0 < k < PLACEHOLDER_WIDTH:
                cut = cut[:k]
        if len(cut) > PLACEHOLDER_WIDTH:
            cut = cut[:PLACEHOLDER_WIDTH].rsplit(" ", 1)[0]
        out.append(f"{head.group(1)}<{cut.rstrip(' ,.')}…>")
        i = j
    return "\n".join(out)


def pilot_and_report(tmpl: str) -> tuple[str, ProtocolBlocks]:
    """(pilot part, report blocks) of the template. A report block is (section key,
    heading, items): a daggered section whole, or the daggered items of a section."""
    pilot: list[str] = []
    report: ProtocolBlocks = []
    for heading, body in _segments(tmpl):
        if not heading:
            # the preamble may MENTION the dagger (legend) — it stays pilot
            pilot.extend(line for item in _items(body) for line in item)
            continue
        if DAGGER in heading:
            report.append((section_key(heading) or heading, heading, _items(body)))
            continue
        keep = [
            i for i in _items(body) if not (i[0].startswith("- ") and DAGGER in i[0])
        ]
        moved = [i for i in _items(body) if i[0].startswith("- ") and DAGGER in i[0]]
        pilot.append(heading)
        pilot.extend(line for item in keep for line in item)
        if moved:
            report.append((section_key(heading) or heading, heading, moved))
    return "\n".join(_untag(line) for line in pilot).rstrip() + "\n", report


def insert_report_fields(text: str, blocks: ProtocolBlocks) -> tuple[str, int]:
    """Fill the daggered fields into their sections; (text, fields added).
    A section the protocol lacks comes in whole, before the next one it has."""
    order = [key for key, _, _ in blocks]
    segs = _segments(text)
    keys = [section_key(h) if h else None for h, _ in segs]
    present = {lab for _, body in segs for lab in map(_label_of, _items(body))}
    added = 0
    pending: ProtocolBlocks = []
    for key, heading, items in blocks:
        fresh = [
            i for i in items if i[0].startswith("- ") and _label_of(i) not in present
        ]
        if not fresh:
            continue
        added += len(fresh)
        if key not in keys:
            pending.append((key, heading, items))
            continue
        body = segs[keys.index(key)][1]
        while body and not body[-1].strip():
            body.pop()
        body.extend(line for item in fresh for line in item)
        body.append("")
    for key, heading, items in pending:
        later = [k for k in order[order.index(key) + 1 :] if k in keys]
        at = keys.index(later[0]) if later else len(segs)
        body = [line for item in items for line in item]
        while body and not body[-1].strip():
            body.pop()
        segs.insert(at, (heading, body + [""]))
        keys.insert(at, key)
    out = [
        line for heading, body in segs for line in ([heading] if heading else []) + body
    ]
    return "\n".join(out).rstrip() + "\n", added


# A protocol that names no model has nothing to parse; --report fills that
# field when the Model / tool field says so (`protocol_check.model_named`,
# the one reading of that field). Until 2026-10-17 it also wrote "no seed,
# repetition spread 0" into Randomness controls and Noise ceiling: "no
# language model" is not "no source of randomness" — a seeded forest, a
# fold shuffle and a permutation are ones, and the pilot that got the line
# (labkit-paper area 09, Sonnet v2 t5) named seed 0 three lines below it
# while the next round measured a null-AUC spread of 0.116 over ten seeds.
# Those two fields stay owed: an estimator with a seed owes them.
DETERMINISTIC_NA = {
    "Parser cases harvested": "n/a — no model, nothing to parse (auto-filled by --report)",
}


def _replace_placeholder(lines: list[str], label: str, value: str) -> bool:
    """In place: the stamped `<…>` placeholder of LABEL (one line or wrapped)
    becomes VALUE on the label line; False when the field is not stamped."""
    head = re.compile(r"^(\s*-\s*\*\*" + re.escape(label) + r"\s*†?:\*\*\s*)<")
    for i, line in enumerate(lines):
        if m := head.match(line):
            j = i
            while ">" not in lines[j]:
                j += 1
            lines[i : j + 1] = [m.group(1) + value]
            return True
    return False


def auto_fill_deterministic(text: str) -> tuple[str, int]:
    """Fill the placeholder a model-free protocol cannot answer — the parser
    field, nothing about randomness (DETERMINISTIC_NA); (text, fields filled)."""
    if model_named(text):
        return text, 0
    lines = text.split("\n")
    filled = sum(
        _replace_placeholder(lines, lb, v) for lb, v in DETERMINISTIC_NA.items()
    )
    return "\n".join(lines), filled


#: What a computation's registration owes, said in the placeholder: three cold
#: agents (Haiku, 2026-10-13) wrote a Terms sentence for a plain count — "n/a"
#: was allowed by the check but unsaid by the stamp — and one read
#: "hypothesis" as an expectation to invent, then reworded it with --force.
COMPUTE_PLACEHOLDERS = {
    "Terms of this protocol": '<one line per coined house word — or "n/a — no coinage">',
    "Question / hypothesis": (
        "<the one question: what is computed, over which items — a computation tests no hypothesis>"
    ),
}


#: The pilot protocol of an estimator area: the model-shaped fields answered
#: as what they are here, the promise sentences in the estimator's words.
#: No `: `, ` — `, `; ` or ` (` inside a `<…>`: `short_placeholders` cuts there.
ESTIMATOR_FIELDS = {
    # a filled value, no `<…>` tail: an "n/a — …" line ending in a hole read
    # as filled, and protocol-check let the hole through (BERT example on
    # the branch, 2026-10-18); its parameters and seed are owed in the report
    # fields Free knobs and Randomness controls (`--report`, C1)
    "Model / tool": "n/a — no model call; the instrument is the estimator of `make_estimator()` in scripts/01_measure.py",
    "Prompt (verbatim, per variant)": "n/a — no prompt; the instrument is an estimator",
    "Model I/O": "<in · the feature fields per item · out · one prediction per item, scored out of fold>",
    "Null condition / anchors (in the same run)": "<the same estimator on labels permuted inside each fitting fold, expected at chance_of() within null_band>",
    "Raw output": "<one registered row and one test row as --probe prints them>",
    "Render check (ZERO calls, `--show N`)": "n/a — no prompt; `--show N` prints the config and N feature rows",
    "Instrument check (real pipeline, ~10 calls, `--probe N`)": "<`--probe N` · a reduced estimator on N labelled items, both lanes, throwaway · scores read, never reported>",
    "Parser cases harvested": "n/a — no model text to parse",
}


ESTIMATOR_PROMISES = (
    (
        r'sentence = "<the criterion in one sentence:[^"]*"',
        "sentence = \"<the criterion · the registered lane's out-of-fold SCORE is at least the null lane's plus margin>\"",
    ),
    (
        r'sentence = "<the yield condition:[^"]*"',
        'sentence = "<the yield · at most max_empty labelled items without an out-of-fold prediction>"',
    ),
    (r"constants = \{ max_empty = 2 \}", "constants = { max_empty = 0 }"),
    (
        r'sentence = "<the null condition:[^"]*"',
        'sentence = "<the null condition · the permuted-label lane scores within null_band of chance>"',
    ),
    (r"constants = \{ null_band_items = 1 \}", "constants = { null_band = 0.1 }"),
)


APPLY_FIELDS = {
    "Model / tool": "n/a — no model call; the unchanged predictor is loaded by `make_estimator()` in scripts/01_measure.py",
    "Model I/O": "<in · the feature fields per item · out · one prediction from each unchanged instrument without fitting>",
    "Null condition / anchors (in the same run)": "<the unchanged predictor's predictions scored against the gold labels permuted with the seed, expected at chance_of() within null_band — or the registered fixed null of make_null_predictor() and why it targets chance>",
    "Raw output": "<one registered row and one null row as --probe prints them>",
    "Instrument check (real pipeline, ~10 calls, `--probe N`)": "<`--probe N` · the unchanged predictor on N labelled items, both lanes · scores read, never reported>",
}


def _replace_field(lines: list[str], label: str, value: str) -> bool:
    """In place: the stamped field LABEL becomes VALUE on its label line, and
    the stamped continuation below it (indented placeholder lines, a fenced
    example block) goes; False when the field is not stamped."""
    head = re.compile(r"^(\s*-\s*\*\*" + re.escape(label) + r"\s*†?:\*\*)")
    for i, line in enumerate(lines):
        if not head.match(line):
            continue
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or lines[j].startswith("  ")):
            j += 1
        lines[i:j] = [f"{head.match(line).group(1)} {value}"]  # type: ignore[union-attr]
        return True
    return False


#: the prose field that states each stamped promise — its id is written
#: before the placeholder, because the cut placeholder loses the template's
#: `[C…]` hint and a cold agent then writes `C1:`, which no check reads
PROMISE_FIELDS = {
    "Success / failure criterion": "C1",
    "Admissibility condition": "A1",
    "Null condition / anchors (in the same run)": "A2",
}


def name_promise_ids(text: str, kind: str) -> str:
    """The stamped promise ids written before the placeholders of the fields
    that state them (PROMISE_FIELDS): `- **Success / failure criterion:**
    [C1] <…>` — for a KIND with a bar; a computation's text comes back unchanged
    (an id in its prose would register a promise). Raises ValueError when a
    field is not stamped or the stamped block does not declare its id: the
    prose names only what the block already promises."""
    from labkit.formats.standard_contract import has_bar

    if not has_bar(kind):
        return text
    block = promises.parse_block(text)
    declared = {p.id for p in block.promises} if block is not None else set()
    lines = text.split("\n")
    for label, pid in PROMISE_FIELDS.items():
        if pid not in declared:
            raise ValueError(f"name_promise_ids: the stamped block declares no {pid}")
        head = re.compile(r"^(\s*-\s*\*\*" + re.escape(label) + r"\s*†?:\*\*\s*)<")
        for i, line in enumerate(lines):
            if m := head.match(line):
                lines[i] = f"{m.group(1)}[{pid}] {line[m.end() - 1 :]}"
                break
        else:
            raise ValueError(
                f"name_promise_ids: the stamp has no `{label}` placeholder"
            )
    return "\n".join(lines)


def estimator_placeholders(text: str, cut: bool = False, *, kind: str = "fit") -> str:
    """The pilot protocol of an estimator area (kind fit, or apply without a
    model): fields and promise sentences describe fitting at KIND fit, or
    the unchanged predictor at KIND apply (its null lane on permuted
    labels). The
    constants and score formulas are shared. Raises when KIND is neither
    fit nor apply or the stamp lacks a field or a table line
    — a silently unfilled field is the leftover this exists to remove; in
    the low CUT only the fields the cut carries are owed, the others
    are not stamped at all."""
    if kind not in ("fit", "apply"):
        raise ValueError(
            f"estimator_placeholders: kind must be fit or apply, got {kind!r}"
        )
    values = ESTIMATOR_FIELDS | (APPLY_FIELDS if kind == "apply" else {})
    lines = text.split("\n")
    for label, value in values.items():
        if not _replace_field(lines, label, value) and not cut:
            raise ValueError(
                f"estimator_placeholders: the stamp has no `{label}` field"
            )
    out = "\n".join(lines)
    for pattern, replacement in ESTIMATOR_PROMISES:
        if kind == "apply":
            replacement = replacement.replace("out-of-fold SCORE", "SCORE")
            replacement = replacement.replace(
                "an out-of-fold prediction", "a prediction"
            )
        out, n = re.subn(pattern, lambda _m, r=replacement: r, out, count=1, flags=re.M)
        if n != 1:
            raise ValueError(
                f"estimator_placeholders: the stamp's block has no line matching {pattern!r}"
            )
    return out


def count_placeholders(text: str) -> str:
    """The low cut without a model, its Terms and Question placeholders
    replaced by COMPUTE_PLACEHOLDERS. Raises when the cut lacks one of them."""
    lines = text.split("\n")
    for label, value in COMPUTE_PLACEHOLDERS.items():
        if not _replace_placeholder(lines, label, value):
            raise ValueError(
                f"count_placeholders: the cut has no stamped `{label}` field"
            )
    return "\n".join(lines)


def new_protocol_id(root: Path) -> str:
    """`p-` + 16 hex, checked against every protocol id already in the repo.

    Not derived from name or path: renaming a protocol or moving an area must
    leave the identity a run bound to intact; the scan catches a protocol
    copied as the start of the next one.
    """
    taken = {
        protocol_block.id_of(f.read_text(encoding="utf-8"))
        for f in repo_protocols(root)
    }
    while True:
        pid = "p-" + uuid.uuid4().hex[:16]
        if protocol_block.ID_SHAPE.match(pid) and pid not in taken:
            return pid
