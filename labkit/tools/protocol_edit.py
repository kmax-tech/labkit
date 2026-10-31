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
    placeholder fields. LINE_NO restricts the fields to that line."""
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


#: the head's stamped placeholders `protocol-fill` sets, by the label a fill
#: names: (the TOML key, its allowed values — None for a free string)
HEAD_KEYS: dict[str, tuple[str, tuple[str, ...] | None]] = {
    "type": ("type", protocol_block.TYPES),
    "repeat_cost": ("repeat_cost", protocol_block.REPEAT_COSTS),
    "kind": ("kind", protocol_block.KINDS),
    "model alias": ("alias", None),  # [model] alias, stamped by --model without a name
    # [model] number_describes, a MUST of a computation with a model that no
    # tool could set and `--list` never named (audit 2026-10-27, third, I5)
    "number_describes": ("number_describes", protocol_block.NUMBER_DESCRIBES),
}
#: the head's freeze keys: a deliberate edit by the author once preflight is
#: clean and the preflight audit decided, not a fill — named so a fill of
#: them says so instead of "no field labelled" (audit 2026-10-27, third, I6)
FREEZE_KEYS = ("frozen", "preflight_audit")
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


def fill_many(
    text: str,
    assignments: list[tuple[str, str]],
    line_no: int | None = None,
    force: bool = False,
) -> str:
    """`fill` applied in order — `fill_head` for the head's `type`, `repeat_cost`,
    `model alias` and `number_describes` (`HEAD_KEYS`), `fill_sentence` for
    `<id> sentence`; the freeze keys (`FREEZE_KEYS`) are refused with how to
    set them by hand;
    the first ValueError leaves the caller's file untouched — all or
    nothing."""
    for label, value in assignments:
        if not label.strip() or not value.strip():
            raise ValueError(f"empty label or value in {label}={value!r}")
        sentence = SENTENCE_LABEL.match(label)
        if sentence and not promises.is_block_id(sentence.group(1)):
            sentence = None  # a prose label such as "Key sentence"
        if label.strip().lower() in FREEZE_KEYS:
            raise ValueError(
                f"{label.strip()} is the freeze, set by hand in the TOML head once "
                "`preflight` is clean and the preflight audit decided: "
                '`preflight_audit = "<the record file labkit-audit wrote>"`, '
                "`frozen = true` — the protocol is the author's to edit; audit and "
                "run records are not"
            )
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


def as_filled(text: str, label: str) -> str:
    """LABEL as the fill line tells it: with the field a prefix named
    (`Terms → terms of this protocol`), else as typed."""
    try:
        meant = field_for(text, label)
    except ValueError:
        return label  # a head key or a promise's sentence: not a prose field
    return label if meant == field_name(label) else f"{label} → {meant}"
