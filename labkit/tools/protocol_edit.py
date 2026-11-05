"""Text edits of a protocol by stable handles: a field's value by its label
(`fill`), the TOML head's stamped placeholders (`fill_head`), a promise's
sentence (`fill_sentence`), and several `LABEL=VALUE` assignments at once
(`fill_many`).

The template stamps every field as `- **Label †:** <placeholder>`, so the
label is the handle: the `<...>` value is replaced (multi-line
placeholders included) and everything else stays byte-identical. Each
function takes the protocol text and returns the new text; nothing here
reads or writes a file.
"""

from __future__ import annotations


import difflib
import re

from labkit.formats import (
    promises,
    protocol_block,
)
from labkit.formats.protocol_check import (
    field_name,
    fields,
    placeholder_fields,
)

# Bullet and indentation of a label line, kept when the line is rewritten.
_LEAD = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+)?")


def field_for(text: str, field: str, line_no: int | None = None) -> str:
    """The field name (`field_name`) FIELD means in TEXT: its own when a field
    has it, else the one field whose name it begins (`Terms` → `terms of
    this protocol`) — a label typed short names its field when no other
    begins the same. Raises ValueError naming the fields a prefix begins
    when several do, else the nearest names (`difflib`) and the open
    placeholder fields. Misaddressed head keys and promise ids name their
    existing write syntax instead. LINE_NO restricts the fields to that line."""
    want = field_name(field)
    names = sorted(
        {f.name for f in fields(text) if line_no is None or f.line == line_no}
    )
    if want in names:
        return want
    begun = [n for n in names if want and n.startswith(want)]
    if len(begun) == 1:
        return begun[0]
    where = f" at line {line_no}" if line_no else ""
    if begun:
        raise ValueError(
            f"{field!r}{where} begins {len(begun)} fields: "
            + " · ".join(begun)
            + " — name one in full"
        )
    hint = field_address_hint(text, field)
    if hint is not None:
        raise ValueError(hint)
    near = difflib.get_close_matches(want, names, n=3, cutoff=0.6)
    labels = sorted({lbl for _, lbl in placeholder_fields(text)})
    raise ValueError(
        f"no field labelled {field!r}{where}"
        + (f" — did you mean {' · '.join(near)}?" if near else "")
        + (
            " Open placeholder fields: " + " · ".join(labels)
            if labels
            else " No placeholder fields left."
        )
    )


def field_address_hint(text: str, label: str) -> str | None:
    """Explain a misaddressed head key, promise id or generated Runs section.

    Return None for other labels, including kept keys without a [kept]
    table. Call after matching real prose fields and their unique prefixes,
    so guidance does not reserve additional field names. No input is changed.
    """
    name = label.strip().lower()
    pid = name.removeprefix("[").removesuffix("]")
    if promises.is_block_id(pid):
        return (
            f"{label!r} names a promise, not a prose field — use "
            f'`"{pid} sentence=VALUE"` without --line; --list shows open entries'
        )
    if name == "runs":
        return (
            "Runs is a generated section, not a field — `labkit-adopt <area> "
            "<run_id>` records an adopted result; `runlog <area>` lists runs"
        )
    target = head_address_suggestion(name)
    if target is None:
        return None
    if target.startswith("kept."):
        span = protocol_block.toml_block_span(text)
        if span is None or _table_span(text.splitlines(), *span, "kept") is None:
            return None
    return f'{label!r} names a head key — use `"{target}=VALUE"`'


def head_address_suggestion(label: str) -> str | None:
    """Suggest existing head-key syntax for a known malformed address.

    LABEL is stripped lowercase text. This only supplies error guidance;
    it does not accept aliases or change the head-key catalogue.
    """
    if label == "key":
        return "kept.key"
    if label.startswith("[kept]"):
        target = label.replace("[kept]", "kept.", 1)
    elif label.startswith("protocol."):
        target = label.removeprefix("protocol.")
    else:
        return None
    return target if target in protocol_block.FILLABLE_HEAD_KEYS else None


def fill(
    text: str, field: str, value: str, line_no: int | None = None, force: bool = False
) -> str:
    """Return the protocol text with `field`'s placeholder replaced by `value`.

    Fields are read by `protocol_check.fields` — the one parser of labels
    and placeholders; a second one here mis-read a wrapped label as
    `extremes)` (usability probe 2026-10-07). The label line and its
    continuation lines become one line; everything else stays byte-identical.
    An id the stamp wrote before the placeholder (`[criterion-1] <…>`) stays when
    VALUE names no id; a VALUE with its own ids replaces it.

    Raises ValueError with a human-readable reason (unknown label, ambiguous
    label, already filled without force) — the CLI prints it verbatim.
    """
    want = field_for(text, field, line_no)
    hits = [
        f
        for f in fields(text)
        if f.name == want and (line_no is None or f.line == line_no)
    ]
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


#: what `--list` says a free head value takes, by its label in protocol_block.FILLABLE_HEAD_KEYS
HEAD_HINTS: dict[str, str] = {
    "model alias": "the alias from models.toml",
    "kept.key": "the metrics.json key of the kept number",
    "kept.unit": 'its unit, "1" for a dimensionless number',
}
#: a `[kept]` value named the way agents write a table's key (`[kept] key`,
#: `[kept]key` as `[protocol]type` is read, `kept key`, `[kept].unit`): read as
#: its protocol_block.FILLABLE_HEAD_KEYS label `kept.<value>` (t34-r3, 2026-11-04)
KEPT_LABEL = re.compile(r"^\[?kept\]?\s*[.\s]?\s*(key|unit)$", re.I)
#: the head's freeze keys, written together by `set_freeze` (`protocol-fill
#: --freeze`), never by a fill — named so a fill of them says so instead of
#: "no field labelled" (audit 2026-10-27, third, I6)
FREEZE_KEYS = ("frozen", "preflight_audit")
#: a freeze key's line in the TOML head, whatever it holds
_FREEZE_LINE = {key: re.compile(rf"^\s*{key}\s*=") for key in FREEZE_KEYS}


def set_freeze(text: str, record: str) -> str:
    """TEXT with its head frozen: `frozen = true` and `preflight_audit =
    "RECORD"` in the TOML block (`FREEZE_KEYS`), whatever the lines held —
    a freeze after a change names the new record the same way. Pure: the
    caller checks the proposal (`audit_gaps.freeze_refusals`) and writes.
    Raises ValueError without the block or either line: the stamp writes
    both, a head without them is not labkit's."""
    span = protocol_block.toml_block_span(text)
    if span is None:
        raise ValueError("the head has no TOML block to freeze")
    lines = text.split("\n")
    written = {
        "frozen": "frozen = true",
        "preflight_audit": f"preflight_audit = {protocol_block.toml_string(record)}",
    }
    done: set[str] = set()
    for i in range(*span):
        for key, pattern in _FREEZE_LINE.items():
            if pattern.match(lines[i]):
                lines[i] = written[key]
                done.add(key)
    missing = [key for key in FREEZE_KEYS if key not in done]
    if missing:
        raise ValueError(
            f"the head has no {' and no '.join(missing)} line — the stamp writes both"
        )
    return "\n".join(lines)


#: a label that names a head key with its table, as agents write it
#: (`[protocol] type`, `[model] alias`): the table prefix `head_label` drops
TABLE_PREFIX = re.compile(r"^\[(protocol|model)\]\s*")
#: head parts `protocol-fill` does not write, by the label an agent gave, and
#: where they are written instead (round 2: `[reference]` filled as a field)
NOT_FILLED: dict[str, str] = {
    "reference": "the head's [reference] table is written by `labkit-init exp <name> "
    "--kind compute --reference VALUE[±TOL]` before the first measurement, or by "
    "hand in the TOML head (value, tolerance, relation, source; the key compared "
    "is `[kept] key`)",
    "result": "`[result] run` is written by `labkit-adopt <area> <run_id>`, never by hand",
    "standard": "`standard` is stamped and never edited: labkit refuses a protocol of "
    "another version",
}
#: TOML key → its allowed values (None: free), for `head_open` and `fill_head`
HEAD_CHOICES: dict[str, tuple[str, ...] | None] = {
    key: choices for key, choices in protocol_block.FILLABLE_HEAD_KEYS.values()
}


def _head_line(key: str) -> re.Pattern[str]:
    """The head's `KEY = "<…>"` placeholder line, its key and `=` kept; of a
    dotted KEY (`kept.key`) the part after the table."""
    bare = key.rsplit(".", 1)[-1]
    return re.compile(rf'^({re.escape(bare)}\s*=\s*)"<[^"\n]*>"\s*$')


def _table_span(
    lines: list[str], start: int, end: int, table: str
) -> tuple[int, int] | None:
    """The line range (start, end) of the TOML block's `[TABLE]` body within
    LINES[START:END] — from below its header to the next table header — or
    None without the table."""
    header = re.compile(rf"^\s*\[\s*{re.escape(table)}\s*\]\s*(?:#.*)?$")
    for i in range(start, end):
        if header.match(lines[i]):
            j = i + 1
            while j < end and not protocol_block.TABLE_HEADER.match(lines[j]):
                j += 1
            return i + 1, j
    return None


def head_open(text: str, key: str) -> int | None:
    """Line number of the TOML head's `KEY = "<…>"` placeholder, KEY one of
    `HEAD_CHOICES`, or None once set — or, for a dotted KEY (`kept.key`),
    without its table; ValueError on another key. A dotted KEY is read
    inside its table only (`[kept]`), so a `key = "<…>"` elsewhere is not it.

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
    if "." in key:
        table = _table_span(lines, start, end, key.split(".", 1)[0])
        if table is None:
            return None
        start, end = table
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
        table = key.split(".", 1)[0] if "." in key else None
        span = protocol_block.toml_block_span(text)
        if (
            table is not None
            and span is not None
            and _table_span(text.splitlines(), *span, table) is None
        ):
            raise ValueError(
                f"the head has no [{table}] table to fill — add it to the TOML head "
                f'by hand: `[{table}]` with `key = "<metrics.json key>"` and '
                f'`unit = "<unit>"`'
            )
        raise ValueError(
            f"the head's {key} is already set (edit the TOML head to change it)"
        )
    lines = text.split("\n")
    written = protocol_block.toml_string(value)
    lines[n - 1] = _head_line(key).sub(lambda m: f"{m.group(1)}{written}", lines[n - 1])
    return "\n".join(lines)


#: the label a fill names the head's `[protocol] report` by (with or without
#: its table, `TABLE_PREFIX`)
REPORT_KEY = "report"
#: a `report = …` line of the head, whatever its value's spelling
_REPORT_LINE = re.compile(r"^\s*report\s*=")
#: a `key = …` line of a TOML table body (not a comment, not blank)
_KEY_LINE = re.compile(r"^\s*[\w.\"'-]+\s*=")


def is_report_label(label: str) -> bool:
    """Does LABEL name the head's `[protocol] report` (`report`,
    `[protocol] report`)?"""
    return TABLE_PREFIX.sub("", label.strip()).lower() == REPORT_KEY


def set_report(text: str, value: str, *, force: bool) -> str:
    """TEXT with the head's `[protocol] report` registering VALUE, a path
    relative to the repository root as `protocol_block.report_field` reads
    it (normalized there): a `report = "…"` line added after the last key of
    the `[protocol]` table when the head registers none; TEXT unchanged when
    it registers the same file; the line replaced, with FORCE only, when it
    registers another. Raises ValueError on a value `report_field` refuses,
    a head without a `[protocol]` table, and another file without FORCE.
    The caller (`protocol_fill`) checks the proposed report against the
    historical binding; restoration may pass after measurement, redirection
    may not. This pure editor enforces only the overwrite requirement."""
    try:
        wanted = protocol_block.report_field(value)
        now = protocol_block.head(text).report
    except protocol_block.BlockError as exc:
        raise ValueError(str(exc)) from exc
    assert wanted is not None, "report_field returns None only for None"
    if now == wanted:
        return text
    if now is not None and not force:
        raise ValueError(
            f"the head registers {now} as its report already — `--force` registers "
            f"{wanted} instead; protocol-fill still checks the measured binding"
        )
    lines = text.split("\n")
    span = protocol_block.toml_block_span(text)
    table = _table_span(lines, *span, "protocol") if span is not None else None
    if table is None:
        raise ValueError("the head has no [protocol] table to register a report in")
    start, end = table
    written = f"report = {protocol_block.toml_string(wanted)}"
    for i in range(start, end):
        if _REPORT_LINE.match(lines[i]):
            lines[i] = written
            return "\n".join(lines)
    last = max(
        (i for i in range(start, end) if _KEY_LINE.match(lines[i])), default=None
    )
    if last is None:
        raise ValueError("the head's [protocol] table holds no key to register after")
    lines.insert(last + 1, written)
    return "\n".join(lines)


#: a promise's sentence as `--list` names it and a fill addresses it:
#: `criterion-1 sentence` — the word before "sentence" is a promise id
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
    match = [i for i in ids if i == pid]
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


def head_label(label: str) -> str:
    """LABEL as `fill_many` reads it: a head key named with its table
    (`[protocol] type`, `[model] alias`) is the key (`TABLE_PREFIX`), a
    `[kept]` value its dotted label (`[kept] key` → `kept.key`,
    `KEPT_LABEL`); a head
    part `protocol-fill` does not write (`NOT_FILLED`: `[reference]`,
    `[result]`, `standard`, with or without brackets or a subkey) raises
    ValueError naming where it is written; any other label is returned as
    given."""
    kept = KEPT_LABEL.match(label.strip())
    if kept:
        return f"kept.{kept.group(1).lower()}"
    bare = TABLE_PREFIX.sub("", label.strip())
    table = re.match(r"^\[?(\w+)\]?", bare)
    if (
        table
        and table.group(1).lower() in NOT_FILLED
        and (bare.startswith("[") or bare.lower().split()[0] in NOT_FILLED)
    ):
        raise ValueError(
            f"{label.strip()!r} is not a field: {NOT_FILLED[table.group(1).lower()]}"
        )
    if bare != label.strip() and bare.lower() in protocol_block.FILLABLE_HEAD_KEYS:
        return bare
    return label


def fill_many(
    text: str,
    assignments: list[tuple[str, str]],
    line_no: int | None = None,
    force: bool = False,
) -> str:
    """`fill` applied in order — `fill_head` for the head's `type`, `repeat_cost`,
    `model alias`, `number_describes`, `kept.key` and `kept.unit`
    (`protocol_block.FILLABLE_HEAD_KEYS`), `set_report` for `report` (FORCE passed on), `fill_sentence` for
    `<id> sentence`; the freeze keys (`FREEZE_KEYS`) are refused with how to
    set them by hand;
    the first ValueError leaves the caller's file untouched — all or
    nothing."""
    for label, value in assignments:
        if not label.strip() or not value.strip():
            raise ValueError(f"empty label or value in {label}={value!r}")
        label = head_label(label)
        sentence = SENTENCE_LABEL.match(label)
        if sentence and not promises.is_block_id(sentence.group(1)):
            sentence = None  # a prose label such as "Key sentence"
        if label.strip().lower() in FREEZE_KEYS:
            raise ValueError(
                f"{label.strip()} is the freeze — `protocol-fill <PROTOCOL> --freeze "
                "[RECORD]` sets both keys once `preflight` is clean and the "
                "preflight audit decided, and refuses what the freeze gate would "
                "hold; the protocol is the author's to edit, audit and run records "
                "are not"
            )
        if is_report_label(label):
            text = set_report(text, value, force=force)
        elif label.strip().lower() in protocol_block.FILLABLE_HEAD_KEYS:
            text = fill_head(
                text, protocol_block.FILLABLE_HEAD_KEYS[label.strip().lower()][0], value
            )
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


def as_filled(text: str, label: str) -> str:
    """LABEL as the fill line tells it: with the field a prefix named
    (`Terms → terms of this protocol`), else as typed."""
    try:
        meant = field_for(text, label)
    except ValueError:
        return label  # a head key or a promise's sentence: not a prose field
    return label if meant == field_name(label) else f"{label} → {meant}"
