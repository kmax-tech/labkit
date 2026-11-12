"""protocol_check — the field contract of a protocol and its reading.

The head — standard, id, type, repeat_cost, frozen, preflight audit — is the
`[protocol]` table of the protocol's ```toml block, read by
`protocol_block` (typed, exact; a malformed head is one MUST failure that
names the field). The prose fields a human writes are held by their exact
template label (`FIELDS`): a field is present when a line `- **<label>:**`
carries it, filled when its value is not a `<…>` placeholder; an explicit
"n/a — <why>" counts, silence does not.

What lives here, each stated as its current rule:

  * **The fields** (`fields`, `FieldLine`): every `- **<label>:**` line
    with its value, span and whether it is still a placeholder.
  * **What a protocol owes** (`owed_fields`, `owed`, `check_fields`): two tiers, one
    template. MUST is the pilot minimum; SHOULD is what a REPORTABLE run
    owes on top. `frozen = true` escalates every SHOULD field to MUST and
    needs the preflight audit line and the promise tables; `repeat_cost =
    "low"` owes its own marked cut and nothing graduates, because
    nothing freezes (LAB-017 The number of audits follows the cost tier).
  * **The registration before a number** (`low_registration_missing`,
    `written_before_run`): what a run at low repeat cost owes first, and a report
    field filled while no run exists.
  * **The result section** (`recorded_results_field`, `recorded_results_without_run`,
    `answering_run.adopted_run`): the lines report-check and protocol-fill read; the
    declaration itself is the head's `[result] run`
    (`protocol_block.declared_run`), and it is what makes the result
    fields due.

The checks over the whole file — template lines left in, the verbatim
prompt block, a measure run without a written result, change-history prose,
the id against the repo — and the `protocol-check` command are
`protocol_report`'s. Read-only.
"""

import functools
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from labkit.formats import markdown
from labkit.formats.gate import OPEN_RULE, TECHNICAL_RULE, RuleAssignment, cited_rule
from labkit.formats import digests
from labkit import PACKAGE_DIR
from labkit.formats import (
    promises,
    protocol_block,
    standard_contract,
    answering_run,
)

LAB_004 = cited_rule("LAB-004 Identifiers make the intent addressable")
LAB_011 = cited_rule("LAB-011 Required-field check")
LAB_015 = cited_rule("LAB-015 Preflight audit before freezing")


@dataclass(frozen=True)
class Field:
    """One prose field of the template, held by its exact label.

    `label` is the template's label without `†` and without the
    parenthesised gloss (`Prompt (verbatim, per variant)` → `Prompt`).
    `level` says when the field is owed:

        must    by every pilot
        should  by a reportable run: a must once `frozen = true`
        after   once the head declares a result (`[result] run`, the write-back)
        report  once frozen AND a result is declared (the summary and
                the report half of the result; at low repeat cost never — the audit
                comes at promotion there)

    `low_cut`: owed in the low cut — "l" always, "lb" when the number
    judges a prediction (`kind` fit or apply: it has a bar), "lm" when a
    model answers through `models.toml` (`[model]`); after/report fields
    carry the template's marker but are owed by their level, not by the
    cut. The template's † marks exactly the
    should and report fields it stamps with `--report` (a test holds this).

    `needs`: what the full form owes the field for — "" always, "bar" a
    criterion (`kind` fit or apply), "instrument" a model or a bar (the
    computation's run is its own instrument check); "lm" fields are owed
    only with a model at every tier (`full_owed`).
    """

    label: str
    level: str
    low_cut: str = ""
    needs: str = ""


LEVELS = ("must", "should", "after", "report")

# The one home of what a protocol owes, by the template's exact labels — a
# test holds every label to the template, the low cut to its
# `<!-- l -->` markers and the † marks to the should/report levels. Labels,
# not keywords: a word anywhere would satisfy a field (`prompt` in a
# sentence covering "Model I/O"), and a narrow word fail a filled one
# (`**Terms:**` against `terms of`).
FIELDS = (
    # Terms first: they precede the question they are asked in (LAB-087 Term before use).
    Field("Terms of this protocol", "must", "l"),
    Field("Question / hypothesis", "must", "l"),
    Field(
        "Inference criterion", "must", "lb"
    ),  # a computation has no bar to clear; a fit or an apply has
    Field("Quality check", "must", "lb"),
    Field("Data / scope", "must", "l"),
    # read and judged before the measuring run, not just printed
    Field("Data profile", "must", "lm"),
    Field("Model / tool", "must", "lb"),
    Field("Model I/O", "must", needs="instrument"),
    Field("Prompt", "must", "lm"),
    Field("Null condition / anchors", "must", "lb"),
    Field("Exclusions / filters", "must", "l"),
    Field("Unit", "must", "l"),
    # A reportable run owes these on top ("pilot light, report heavy").
    Field("Problem in one sentence", "should"),
    Field("Why this design", "should"),
    Field("Rival explanations", "should"),
    Field("Out of scope", "should"),
    Field("Data preparation", "should"),
    Field("Meaning of the gold label", "should"),
    Field("Answer form + resolution", "should", needs="instrument"),
    Field("How measured", "should"),
    Field("Validation", "should"),
    Field("Noise ceiling → threshold", "should", needs="bar"),
    Field("Free knobs", "should"),
    Field("Randomness controls", "should"),
    Field("Instrument check", "should", needs="instrument"),
    Field("Yield per stage", "should"),
    # The resolution check (LAB-016 Resolution check before freezing): the criterion over synthetic extremes
    # by the REAL evaluate(), before freezing.
    Field("Resolution check", "should", needs="bar"),
    Field("Prediction for the follow-up run", "should"),
    # Written after the run: before it they cannot exist.
    Field("Recorded results", "after", "l"),
    Field("Raw output", "after", "lm"),  # a prompt+answer pair: only with a model
    # The Summary for a person, written after the run
    Field("Conclusion", "after", "l"),
    Field("Limitations", "after"),  # at low repeat cost the Summary requires Conclusion
    Field("Next step", "after"),
    Field("Question", "report"),
    Field("Did", "report"),
    Field("Expected or surprising", "report"),
    Field("Rival check", "report"),
    Field("Caps/drops", "report"),
    # "fällig mit dem Zurückschreiben der Zahl" (LAB-050 Analysis audit before reporting)
    Field("Analysis audit", "report"),
)

#: the fields an analysis record binds besides the registration: what the
#: protocol says before the run, which the audit reads and may judge — every
#: field owed before a pilot (`must`) but the Prompt block, which
#: `protocol-fill --prompts` writes from the code the record binds already,
#: and the registration's own fields, which `registration_stamp` binds field
#: by field (so a rewritten question is named as one). The fields written
#: after the audit (the Summary, Recorded results, the Limitation lines, the run
#: list) and the reportable run's further fields are not in it, so writing
#: them leaves the audit standing. Why: otherwise a corrected Data / scope
#: could never be followed up
REGISTERED_FIELDS = (
    standard_contract.REGISTRATION_FIELDS
    + standard_contract.REGISTRATION_FIELDS_WITH_BAR
    + standard_contract.REGISTRATION_FIELDS_WITH_MODEL
)
AUDITED_FIELDS = tuple(
    f.label
    for f in FIELDS
    if f.level == "must" and f.label != "Prompt" and f.label not in REGISTERED_FIELDS
)


#: the fields an audit record binds (`registration_stamp`, `audited_texts`)
#: — every field a comparison of registrations reads is among them
#: (`protocol_history.SCOPE_FIELDS`, `COMPARED_FIELDS`): each is written
#: once (`repeated_fields`)
BOUND_FIELDS = REGISTERED_FIELDS + AUDITED_FIELDS


def fold(value: str) -> str:
    """VALUE with every run of whitespace one space, ends stripped."""
    return " ".join(value.split())


def field_values(text: str, normalise: Callable[[str], str] = fold) -> dict[str, str]:
    """Each field of TEXT by `field_name` — so case, a parenthesised gloss
    and † aside — to its value as NORMALISE reads it (default: whitespace
    folded): the one reading the stamps (`registration_stamp`,
    `audited_texts`) and the comparisons
    (`protocol_history.scope_differences`, `registration_differences`)
    share. A name written more than once maps to every copy in order, each
    normalised on its own, `(written N times) <first> | <second>`, so no
    reader picks one copy and a change in any copy is seen by all; the
    gates refuse it for BOUND_FIELDS (`repeated_fields`). Pure."""
    copies: dict[str, list[str]] = {}
    for f in fields(text):
        copies.setdefault(f.name, []).append(normalise(f.value))
    return {
        name: vs[0] if len(vs) == 1 else f"(written {len(vs)} times) " + " | ".join(vs)
        for name, vs in copies.items()
    }


#: the way out of a field written more than once (`repeated_fields`), the
#: one wording every gate and `labkit-next` give. Versions of a field send
#: no one to a successor protocol: that way has conditions of its own
#: (`commands.register_anew`), which the hold of the changed registration
#: names where they apply
REPEATED_WAY_OUT = (
    "keep one copy and delete the others; where the copies are versions of "
    "the registration (`(v2)`), keep the version the first measurement stood "
    "on (before any measurement: the one meant) — keeping another changes the "
    "registration, and the gates treat it as that change"
)


def repeated_fields(text: str) -> list[tuple[str, tuple[int, ...]]]:
    """(label, 1-based lines) for each of BOUND_FIELDS that TEXT writes more
    than once — a gloss such as `(v2)` makes no other field: which copy the
    registration means cannot be told, so the gates refuse it with
    REPEATED_WAY_OUT (`repeated_findings`; at low repeat cost also in the
    committed registration, `protocol_history.registration_missing`).
    Other fields may repeat (one Prompt label per variant). Empty when each
    is written at most once. Pure."""
    lines: dict[str, list[int]] = {}
    for f in fields(text):
        lines.setdefault(f.name, []).append(f.line)
    return [
        (label, tuple(at))
        for label in BOUND_FIELDS
        if len(at := lines.get(field_name(label), [])) > 1
    ]


def line_list(lines: Sequence[int]) -> str:
    """`1 and 2`, `1, 2 and 3`: line numbers that stay one item inside a
    comma-separated list."""
    *rest, last = map(str, lines)
    return f"{', '.join(rest)} and {last}" if rest else last


def repeated_findings(text: str) -> list[str]:
    """Per `repeated_fields` of TEXT the sentence every gate tells:
    `<label> written N times (lines a and b), so which copy is registered
    cannot be told` (`FieldReport.repeated`, the start check, the run
    hook)."""
    return [
        f"{label} written {len(at)} times (lines {line_list(at)}), so which copy "
        f"is registered cannot be told"
        for label, at in repeated_fields(text)
    ]


def audited_texts(text: str) -> str:
    """The values of TEXT's AUDITED_FIELDS as one canonical string — `label:
    value` per field in AUDITED_FIELDS' order, as `field_values` reads them
    (whitespace folded, so a reflowed line moves nothing), REGISTRATION_ABSENT
    for a field the text lacks — what an analysis record binds of the
    protocol's prose (`audit_binding.run_shown`)."""
    values = field_values(text)
    return "\n".join(
        f"{label}: {values.get(field_name(label), REGISTRATION_ABSENT)}"
        for label in AUDITED_FIELDS
    )


#: a bold field label opening a line: `- **Label (gloss) †:** value`
_BULLET = r"^\s*(?:[-*]\s+|\d+[.)]\s+)?"  # `- `, `* `, `1. `, `1) ` or none
_FIELD_OPEN = re.compile(
    _BULLET + r"\*\*(?P<label>[^*]+?)(?::\*\*|\*\*\s*:)(?P<value>.*)$"
)
#: the lead of a field's label line, its indent and list marker
#: (`protocol_edit` keeps it when it rewrites the line)
FIELD_LEAD = re.compile(_BULLET)
HTML_COMMENT = re.compile(r"<!--.*?-->")


def label_line(label: str, *, placeholder: bool = False) -> re.Pattern[str]:
    """The stamped line that opens field LABEL, `- **LABEL †:**`, the dagger
    optional: group 1 the line up to its `:**` — with PLACEHOLDER up to the
    stamped `<` that must follow, spaces included. The one pattern the
    template cutter (`protocol_cuts`) writes stamped fields by."""
    tail = r"\s*†?:\*\*" + (r"\s*)<" if placeholder else ")")
    return re.compile(r"^(\s*-\s*\*\*" + re.escape(label) + tail)


def display_label(label: str) -> str:
    """LABEL as a person reads it, the † that marks a result field dropped:
    `Recorded results †` → `Recorded results` (its gloss kept; `field_name`
    is the label normalised for comparison)."""
    return label.replace("†", "").strip()


def _continues(line: str, own: int) -> bool:
    """Does LINE, below a field opened at indent OWN, continue its value? A
    plain indented line does; a list item does when it sits deeper than the
    field's own line and opens no field of its own."""
    item = re.match(r"\s*(?:[-*]\s+|\d+[.)]\s)", line)
    if item is None:
        return True
    return len(line) - len(line.lstrip()) > own and not _FIELD_OPEN.match(line)


#: the one protocol template labkit stamps (`labkit-init exp`); the readers
#: that compare a protocol with it, or recognise its placeholders, start here
PROTOCOL_TEMPLATE = PACKAGE_DIR / "templates" / "experiment-protocol.md.template"


def template_text(path: Path | None) -> str | None:
    """The protocol template at PATH as text (the packaged one, or one
    named), None when none stands there — what `protocol_report` compares
    a written protocol against."""
    if path is None or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def stamp_placeholders() -> frozenset[str]:
    """Every `<…>` phrase of two or more words the protocol template writes
    in its prose, whitespace collapsed: the exact placeholders a stamp
    leaves, no heuristic. Read outside code fences and HTML comments (the
    TOML head's sentences are `promises.placeholder_sentences`, the Prompt
    block's `stamp_block_placeholders`); a one-word `<…>` (`<alias>`, `<name>`) is
    left out, since it also occurs in quoted commands as content
    (`PROTOCOL-<name>.md`). A `<…>` nested in another yields both phrases."""
    lines = PROTOCOL_TEMPLATE.read_text(encoding="utf-8").splitlines()
    fenced = markdown.fenced_lines(lines)
    prose = HTML_COMMENT.sub(
        "", "\n".join(ln for i, ln in enumerate(lines) if i not in fenced)
    )
    out: set[str] = set()
    open_at: list[int] = []
    for i, ch in enumerate(prose):
        if ch == "<":
            open_at.append(i)
        elif ch == ">" and open_at:
            phrase = " ".join(prose[open_at.pop() : i + 1].split())
            if " " in phrase:
                out.add(phrase)
    return frozenset(out)


def holds_stamp_placeholder(value: str) -> bool:
    """Does VALUE, whitespace collapsed, still hold one of `stamp_placeholders`?"""
    flat = " ".join(value.split())
    return any(phrase in flat for phrase in stamp_placeholders())


@functools.lru_cache(maxsize=1)
def stamp_block_placeholders() -> frozenset[str]:
    """The body of every code fence in the protocol template that starts
    with `<` and ends with `>`, whitespace collapsed — today one, the
    Prompt block a stamp leaves (`<the real prompt — …>`). A protocol's
    block is matched against these bodies whole (`is_stamp_placeholder_block`),
    so a prompt that opens and closes with a tag stays a prompt."""
    lines = PROTOCOL_TEMPLATE.read_text(encoding="utf-8").splitlines()
    bodies = (
        " ".join(" ".join(lines[start:end]).split())
        for _, start, end in markdown.fence_spans(lines)
    )
    return frozenset(b for b in bodies if protocol_block.is_stamp_placeholder(b))


def is_stamp_placeholder_block(body: str) -> bool:
    """Is BODY, a code fence's text, whitespace collapsed, one of
    `stamp_block_placeholders` — a block the stamp left unfilled?"""
    return " ".join(body.split()) in stamp_block_placeholders()


#: A list item that is nothing but stamped placeholders — `- <…>`,
#: `- <run_id> — <one sentence: …>`: no label, so no field sees it.
#: A field that points at another area by name only — "wie Bereich 07",
#: "as in area 07" — with no link: the reader has to go and find it, and
#: the one sentence that matters is not here.
BARE_REFERENCE = re.compile(
    r"\b(?:wie|siehe|vgl\.|as in|same as|see)\s+(?:in\s+)?(?:Bereich|area)\s+\d+",
    re.I,
)
STAMPED_ITEM = re.compile(r"[-*]\s+(<[^<>]*>[\s—–-]*)+")
#: the stamped Runs entry, written by `protocol-fill --from-run` after the run
#: (group 1: the list marker with its indent — protocol_fill keeps it)
RUNS_PLACEHOLDER = re.compile(r"^(\s*[-*]\s+)<run_id>\s+[—–-]\s+<[^<>]*>\s*$")


def field_name(label: str) -> str:
    """`Prompt (verbatim, per variant)` → `prompt`; `Free knobs †` → `free knobs`."""
    return label.split("(")[0].replace("†", "").strip().casefold()


#: the three ways a place names no one field (`FieldPlaceError.kind`)
UNKNOWN_PLACE, AMBIGUOUS_PLACE, TWICE_WRITTEN = "unknown", "ambiguous", "twice"


class FieldPlaceError(ValueError):
    """PLACE names no one field, KIND says how: UNKNOWN_PLACE (it begins no
    field — a line number, a section, a label the text lacks),
    AMBIGUOUS_PLACE (it begins several: BEGUN names them), TWICE_WRITTEN
    (the field it names is written more than once: TWICE, its label)."""

    def __init__(
        self, place: str, begun: list[str], *, twice: str | None = None
    ) -> None:
        self.place = place
        self.begun = begun
        self.twice = twice
        self.kind = (
            TWICE_WRITTEN
            if twice is not None
            else AMBIGUOUS_PLACE
            if begun
            else UNKNOWN_PLACE
        )
        if twice is not None:
            why = f"{place!r} names {twice!r}, written more than once"
        elif begun:
            why = (
                f"{place!r} begins {len(begun)} fields: "
                + " · ".join(begun)
                + " — name one in full"
            )
        else:
            why = f"{place!r} names no field"
        super().__init__(why)


def field_meant(names: Iterable[str], place: str) -> str:
    """The field name PLACE means among NAMES (each a `field_name`): its own
    when one of NAMES is it, else the one name it begins (`Terms` → `terms
    of this protocol`) — exact first, then a unique prefix, the one rule for
    a field a person or an auditor names. Raises FieldPlaceError when PLACE
    begins several names or none."""
    want = field_name(place)
    pool = sorted(set(names))
    if want and want in pool:
        return want
    begun = [n for n in pool if want and n.startswith(want)]
    if len(begun) == 1:
        return begun[0]
    raise FieldPlaceError(place, begun)


def field_at(text: str, place: str) -> "FieldLine":
    """The field of TEXT that PLACE means (`field_meant` over the labels TEXT
    holds) — for a place an audit finding or a reading hint names. Raises
    FieldPlaceError when PLACE begins several fields or none (a line number
    and a section name none), or means a field TEXT writes more than once.
    What each caller makes of an unknown place / an ambiguous or twice
    written one:

    - `findings.corrected_field`: no correction (None, `field_or_none`) /
      raised;
    - finalize and the follow-up audit: — / an AuditError, a blocker
      (`ways_out.unclear_correction`);
    - `audit_decisions.repair_hint`: "any other repair" / "its place names
      no one field", told;
    - `audit_decisions.read_hints`: the hint left out, its reason told, for
      both;
    - `audit_prompt._field_change`: raised for both — it is called only for
      a field `corrected_field` named."""
    found = fields(text)
    name = field_meant([f.name for f in found], place)
    hits = [f for f in found if f.name == name]
    if len(hits) != 1:
        raise FieldPlaceError(place, [], twice=hits[0].label)
    return hits[0]


def field_or_none(text: str, place: str) -> "FieldLine | None":
    """`field_at`, None where PLACE names no field at all — a line number, a
    section, another field's text: a place need not name a field. Raises
    FieldPlaceError where it begins several fields or means one written
    twice: that place names a field, but which cannot be told."""
    try:
        return field_at(text, place)
    except FieldPlaceError as exc:
        if exc.kind != UNKNOWN_PLACE:
            raise
        return None


def named_field(text: str, place: str) -> "FieldLine | None":
    """The field of TEXT whose label PLACE names — `field_name` of both
    equal, so case, a parenthesised gloss and † aside, never a part of a
    label; None for a line number, a section, a label TEXT does not hold,
    or one it holds more than once. For a label the code itself names
    (`CONCLUSION_LABEL`); a place a finding or a hint names goes through
    `field_at`."""
    name = field_name(place)
    hits = [f for f in fields(text) if f.name == name]
    return hits[0] if len(hits) == 1 else None


@dataclass(frozen=True)
class FieldLine:
    """One labelled field of a protocol: where it is, what it says."""

    line: int  # 1-based line of the label
    name: str  # field_name() of the label
    label: str  # the label as written
    value: str  # the value with its continuation lines, cut markers removed
    # content below the label: a code fence or deeper-indented lines; the
    # stamp's own placeholder fence is none (`is_stamp_placeholder_block`)
    block: bool = False
    last: int = 0  # 1-based last line of the value

    @property
    def placeholder(self) -> bool:
        """Not yet filled: the template's `<…>`, an `n/a — <why>` left as
        stamped, `TODO`, a bare label with nothing below it (a code block,
        sub-bullets or an indented paragraph count as its value), or a value
        that still holds one of the stamp's own phrases
        (`holds_stamp_placeholder`): text written before or after a left
        placeholder would otherwise read as filled. A value that merely
        starts with `<` (`<10% unparsed`) is content; a placeholder the author coins
        (`<fill later>`) inside their own prose is not recognised. The id a
        stamp writes before a placeholder (`[criterion-1] <…>`) is not a value: the
        field is read without it, and an id alone is still a hole.

        A fence that holds only the stamp's placeholder (`<the real prompt
        — …>`) is no code block in this sense: the parser reads past it
        (`_content_below`), so `block` is False for it and an unfilled
        Prompt is a hole wherever the field is owed."""
        if not self.value:
            return not self.block
        v = promises.ID_PREFIX.sub("", self.value)
        return (
            not v
            or v.startswith("TODO")
            or "<why>" in v
            or protocol_block.is_stamp_placeholder(v)
            or holds_stamp_placeholder(v)
        )


def fields(text: str) -> list[FieldLine]:
    """Every bold field label in the prose, outside code fences. A label may
    wrap onto the next line (`- **Resolution check (ZERO calls, …\n
    extremes):** <…>`); it is read whole. Parsed once per text: the checker
    asks for a protocol's fields from seven places (owed fields, holes,
    the model, the measure runs, the leftovers, the references)."""
    return list(_parsed_fields(text))


def _content_below(
    lines: list[str], start: int, spans: Mapping[int, tuple[int, int]]
) -> str:
    """The first line of content below a field's value, from the 0-based
    index START: the next non-blank line, past every fence that holds only
    a stamp placeholder (`is_stamp_placeholder_block`) — "" when nothing
    follows. SPANS maps a fence's opening line to its body (`fence_spans`)."""
    i = start
    while True:
        i = next((j for j in range(i, len(lines)) if lines[j].strip()), len(lines))
        span = spans.get(i)
        if span is None or not is_stamp_placeholder_block(
            "\n".join(lines[span[0] : span[1]])
        ):
            return lines[i] if i < len(lines) else ""
        i = span[1] + 1


@functools.lru_cache(maxsize=64)
def _parsed_fields(text: str) -> tuple[FieldLine, ...]:  # noqa: C901 complexity baseline 2026-10-08
    out: list[FieldLine] = []
    lines = text.splitlines()
    # opening line -> (first body line, line after the body), 0-based
    spans = {s - 1: (s, e) for _, s, e in markdown.fence_spans(lines)}
    fence: str | None = None  # the open fence's marker; nested fences are body
    comment = False  # inside a multi-line <!-- … --> — not prose
    for i, line in enumerate(lines):
        if comment:
            comment = "-->" not in line
            continue
        if line.strip().startswith("<!--") and "-->" not in line:
            comment = True
            continue
        if fence is not None:
            if markdown.closes(line, fence):
                fence = None
            continue
        opened = markdown.FENCE.match(line)
        if opened:
            fence = opened.group(2)
            continue
        if "**" not in line:
            continue
        joined, nxt = line, i + 1
        if (
            re.match(_BULLET + r"\*\*", line)
            and ":**" not in line
            and i + 1 < len(lines)
        ):
            joined, nxt = line + " " + lines[i + 1].strip(), i + 2
        m = _FIELD_OPEN.match(joined)
        if not m:
            continue
        # The value runs on over indented continuation lines: a bare
        # `- **Label:**` with the text below is written, not empty (reading
        # the first line only, the registration gate would refuse a written
        # registration). Sub-bullets deeper than the field's own line are its
        # value too, as the placeholder rule already counts them: read as
        # nothing, a Data / scope written as a list would compare empty in the
        # scope hold and hide its source digest. A deeper
        # line that opens a field of its own (`- **registered:**`) ends it.
        own = len(line) - len(line.lstrip())
        parts = [m.group("value")]
        while (
            nxt < len(lines)
            and lines[nxt].startswith((" ", "\t"))
            and lines[nxt].strip()
            and not markdown.FENCE.match(lines[nxt])
            and _continues(lines[nxt], own)
        ):
            parts.append(re.sub(_BULLET, "", lines[nxt]).strip())
            nxt += 1
        value = HTML_COMMENT.sub("", " ".join(parts)).strip()
        label = " ".join(m.group("label").split())
        # for every field: a fence holding only a stamp placeholder is
        # skipped, not read as content (the template has one, under Prompt)
        below = _content_below(lines, nxt, spans)
        indent = len(line) - len(line.lstrip())
        deeper = len(below) - len(
            below.lstrip()
        ) > indent and not below.lstrip().startswith("#")
        out.append(
            FieldLine(
                line=i + 1,
                name=field_name(label),
                label=label,
                value=value,
                block=bool(markdown.FENCE.match(below)) or deeper,
                last=nxt,
            )
        )
    return tuple(out)


def promise_names(text: str) -> dict[str, str]:
    """Every promise id TEXT's prose writes before a field's value, mapped to
    that field's name: `- **Null condition / anchors (in the same run):**
    [quality-check-2] …` → {"quality-check-2": "null condition / anchors"}. An id written nowhere at
    a field's start has no name here. Pure."""
    out: dict[str, str] = {}
    for f in fields(text):
        if m := promises.ID_PREFIX.match(f.value):
            out.setdefault(m.group(0).strip(" []"), field_name(f.label))
    return out


def named_ids(ids: Iterable[str], names: Mapping[str, str]) -> str:
    """IDS as a message names them, each with its field's name from NAMES
    (`promise_names`): "criterion-1 (inference criterion), quality-check-2 (null
    condition / anchors)" — an id without a name stands alone. The id
    `quality-check-2` alone does not tell which condition it is."""
    return ", ".join(f"{i} ({names[i]})" if i in names else i for i in ids)


def placeholder_fields(text: str) -> list[tuple[int, str]]:
    """(line number, label) for every field whose value is still a placeholder."""
    return [(f.line, f.label) for f in fields(text) if f.placeholder]


#: what is the matter with a thing a protocol must carry (`MustGap.state`),
#: each the word its line starts with: not there; there and still the
#: stamp's placeholder; there and not usable as it stands
MISSING = "MISSING"
PLACEHOLDER = "PLACEHOLDER"
INVALID = "INVALID"
MUST_STATES = (MISSING, PLACEHOLDER, INVALID)


@dataclass(frozen=True)
class MustGap:
    """One entry of what a protocol must carry and does not (`check_fields`),
    with the rule its cause breaks.

    Attributes:
        label: The field's label, or the sentence naming the gap.
        rule: The rule assignment of the cause — a required field absent
            is the required-field rule's, a table that has no place on
            the kind the technical contract, a promise block that does
            not read the rule its error names
            (`promises.PromiseError.rule`).
        state: What is the matter with the owed thing, said by the cause:
            MISSING (it is not there), PLACEHOLDER (it still holds the
            stamp's `<…>`) or INVALID (it is there and does not read, has
            no place on this kind, or contradicts another part of the
            head). The mark a teller prints (`told`) follows from it.
        way: What closes the gap where writing the field does not — a
            promise block that does not read is repaired (REPAIR_TABLES);
            None for a field to write. A teller reads `repair`.
        block_unread: Whether the gap is the promise block that does not
            read — the cause code-check tells too
            (`code_check.promise_block_findings`), so a gate that runs
            both tells it once, here.
    """

    label: str
    rule: RuleAssignment
    state: str
    way: str | None = None
    block_unread: bool = False

    def __post_init__(self) -> None:
        if self.state not in MUST_STATES:
            raise ValueError(
                f"a must gap's state is one of {MUST_STATES}, not {self.state!r}"
            )

    @property
    def told(self) -> str:
        """The gap as a line names it: `<STATE> (must): <label>`."""
        return f"{self.state} (must): {self.label}"

    @property
    def repair(self) -> str:
        """The way out as a teller starts it: `way`, else writing the field."""
        return self.way or "write the field"


#: the way out of a promise block that does not read, as a gap tells it
REPAIR_TABLES = "repair the [[promise]] tables as the sentence says"


def head_rule(exc: protocol_block.BlockError) -> RuleAssignment:
    """The rule a head that raised EXC breaks: the required-field rule for
    a part that is not there (`protocol_block.HeadPartMissing`), the
    technical contract for a head that does not read."""
    return (
        LAB_011 if isinstance(exc, protocol_block.HeadPartMissing) else TECHNICAL_RULE
    )


@dataclass(frozen=True)
class FieldReport:
    """What one protocol owes and lacks. `head_error` set means the head
    could not be read — `head_rule` then names the rule that breaks
    (`head_rule`), and every list is empty."""

    head: protocol_block.Head | None
    head_error: str | None
    head_rule: RuleAssignment | None
    must_gaps: list[MustGap]
    missing_should: list[str]
    must_holes: list[tuple[int, str]]
    soft_holes: list[tuple[int, str]]
    #: bound fields written more than once (`repeated_findings`): no field is
    #: missing, the copies disagree on which is registered — a must finding
    #: of its own, whose way out is keeping one copy
    repeated: list[str] = field(default_factory=list)

    @property
    def missing_must(self) -> list[str]:
        """The labels of `must_gaps`, in their order — every gap, whatever
        its state (`MustGap.state`)."""
        return [g.label for g in self.must_gaps]

    @property
    def must_told(self) -> list[str]:
        """`must_gaps` as lines name them (`MustGap.told`), in their order."""
        return [g.told for g in self.must_gaps]

    @property
    def frozen(self) -> bool:
        """Whether the protocol's head says it is frozen."""
        return bool(self.head and self.head.frozen)


def model_named(text: str) -> bool:
    """Does the protocol declare a model in the loop — a `[model]` table in
    the head (`protocol_block.model`)? The one answer for the cut, the
    low registration and `labkit-init --report`. False for a head that does not read: the head check
    names that."""
    try:
        return protocol_block.model(text) is not None
    except protocol_block.BlockError:
        return False


def bar_owed(f: Field, kind: str | None) -> bool:
    """Does a number of KIND owe `f` as far as its bar decides? Only the "lb"
    fields depend on it, at every tier: a computation owes no criterion; an
    undecided kind owes the most, never the least."""
    return f.low_cut != "lb" or kind is None or standard_contract.has_bar(kind)


def full_owed(f: Field, kind: str | None, model: bool) -> bool:
    """Does the full form owe `f` for a number of KIND, a model named or
    not (MODEL)? A bar field only with a bar (`bar_owed`), a model field
    ("lm") only with a model, a field that `needs` a bar or an instrument
    only with one — a high computation without a model owes no data
    profile, prompt, instrument or resolution check. An undecided kind owes
    the most."""
    if not bar_owed(f, kind):
        return False
    if f.low_cut == "lm" and not model:
        return False
    if kind is None or not f.needs:
        return True
    has_bar = standard_contract.has_bar(kind)
    return has_bar if f.needs == "bar" else has_bar or model


#: the field a rendered example is the evidence of: the instrument check
#: puts one real input and its output into the protocol as a fenced block
#: (LAB-008 Instrument check before freezing, LAB-014 One fully rendered
#: example pair per gold class)
INSTRUMENT_CHECK = "Instrument check"


def example_owed(repeat_cost: str | None, kind: str | None, model: bool) -> bool:
    """Does `frozen = true` owe a rendered example — a fenced block other than
    the TOML head — for a protocol of REPEAT_COST and KIND, a model named or
    not (MODEL)? Exactly where it owes the Instrument check (`owed_fields`):
    the full form of a fit, an apply, a model named, an undecided kind. A
    computation without a model has no probe, its run is the instrument
    check (the compute skeleton), and the low cut freezes nothing."""
    return any(
        f.label == INSTRUMENT_CHECK for f in owed_fields(repeat_cost, kind, model)
    )


def not_owed(text: str) -> set[str]:
    """The labels of the must, should and after-run fields this protocol's
    full form does not owe (`full_owed`, by its kind and model: Raw output
    only with a model) — the stamp leaves them out (`owed_cut`),
    `protocol-fill --list` sets apart those an older stamp still carries,
    and `--from-run` does not name them as the author's. Empty when the
    head does not read."""
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError:
        return set()
    model = model_named(text)
    return {
        f.label
        for f in FIELDS
        if f.level in ("must", "should", "after") and not full_owed(f, head.kind, model)
    }


def in_cut(f: Field, kind: str | None, model: bool) -> bool:
    """Is `f` part of the low cut — "l" always, "lb" when the number has
    a bar (`bar_owed`), "lm" with a model named?"""
    if f.low_cut == "l":
        return True
    if f.low_cut == "lb":
        return bar_owed(f, kind)
    return f.low_cut == "lm" and model


def owed_fields(
    repeat_cost: str | None, kind: str | None, model: bool
) -> tuple[Field, ...]:
    """Every field a protocol of REPEAT_COST and KIND, a model named or not
    (MODEL), owes, each at its level's occasion (`Field.level`): the low
    cut's marked fields (`in_cut`; nothing graduates there, and no report
    field is owed), else the full form's (`full_owed`). The one answer
    `owed`, protocol-check's result check and `protocol-check PROTOCOL
    --contract` read."""
    if standard_contract.lane(repeat_cost).cut == standard_contract.LOW_CUT:
        return tuple(f for f in FIELDS if in_cut(f, kind, model))
    return tuple(f for f in FIELDS if full_owed(f, kind, model))


def _kind_gap(text: str, head: protocol_block.Head) -> tuple[str, str] | None:
    """`kind_gap`'s sentence with the state its cause names (`MustGap.state`):
    a key that has no place on the kind or claims more than the number
    is INVALID, a key the kind owes and lacks is MISSING. None without a
    gap."""
    try:
        m = protocol_block.model(text)
    except protocol_block.BlockError:
        return None
    if m is None or head.kind is None:
        return None
    if head.kind != standard_contract.COMPUTE_KIND:
        if m.claim_keys:
            return (
                f"[model] {', '.join(sorted(m.claim_keys))} with kind = "
                f'"{head.kind}" — a fit or an apply judges the model itself, so '
                "what a computation over its outputs claims has no place here; "
                "drop the key(s)"
            ), INVALID
        return None
    if m.number_describes is None:
        return (
            '[model] number_describes — kind = "compute" with a [model] table '
            'says what the number describes: "model_outputs" (what the model '
            'marked) or "target_property" (a property of the data, the model as '
            "annotator)"
        ), MISSING
    if (
        m.number_describes == protocol_block.TARGET_PROPERTY
        and m.annotation_validity is None
    ):
        return (
            '[model] annotation_validity — number_describes = "target_property" '
            "claims a property of the data through the model's annotations; name "
            'the evidence the annotator suits: { protocol = "p-…" } (an apply '
            'protocol of this repo with an adopted result) or { doi = "10.…" }'
        ), MISSING
    if (
        m.number_describes == protocol_block.MODEL_OUTPUTS
        and m.annotation_validity is not None
    ):
        return (
            '[model] annotation_validity with number_describes = "model_outputs" '
            "— the number describes the model's outputs, so evidence about the "
            "data claims more than it; drop it or set number_describes = "
            '"target_property"'
        ), INVALID
    return None


def kind_gap(text: str, head: protocol_block.Head) -> str | None:
    """Why the head's `kind` contradicts its `[model]` table, or None. A
    computation over a model's outputs says what its number describes
    (`[model] number_describes`): the outputs, or a property of the data
    with the model as annotator — the latter names the evidence that the
    annotator suits (`annotation_validity`), the former names none, or the
    claim and the evidence disagree. A fit or an apply judges the model
    itself, so the claim keys say nothing there. A computation with a
    `[model]` table is not refused for it: a share of model labels judges no
    prediction. Whether a bound protocol is an
    apply with a result is `protocol_history.check_annotation_validity`'s,
    which reads the repo; whether the evidence carries the annotation stays
    the audit's. Loud, never a fallback: a malformed table is the head
    check's."""
    gap = _kind_gap(text, head)
    return gap[0] if gap else None


def open_holes(
    text: str, head: protocol_block.Head, *, adopting: bool = False
) -> list[tuple[int, str]]:
    """(line, label) of every placeholder still to fill.

    At `repeat_cost = "low"` only the cut's fields count: the rest of the full
    form is not owed there, and listing it would bury the one real blocker
    under 10 to 20 warnings in every correct protocol at low repeat cost.
    Fields written after the run count only once the head declares a result
    — before it they cannot be filled, and an agent would read them as
    errors in the commit hook. ADOPTING asks it of the state
    an adoption makes, where the result is declared (`owed`)."""
    lines = fields(text)
    if answering_run.adopted_run(text) is None and not adopting:
        after = {f.label.casefold() for f in FIELDS if f.level == "after"}
        lines = [f for f in lines if f.name not in after]
    if standard_contract.lane(head.repeat_cost).cut == standard_contract.LOW_CUT:
        model = model_named(text)
        cut = {f.label.casefold() for f in FIELDS if in_cut(f, head.kind, model)}
        lines = [f for f in lines if f.name in cut]
    return [(f.line, f.label) for f in lines if f.placeholder]


def must_and_soft_holes(
    text: str, head: protocol_block.Head, *, adopting: bool = False
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """The placeholders still to fill (`open_holes`, each as (line, label))
    in two lists: those in a field the protocol owes as a must now (`owed`),
    and those in every other field. ADOPTING as in `owed`."""
    must, _ = owed(text, head, adopting=adopting)
    must_names = {f.label.casefold() for f in must}
    must_holes, soft_holes = [], []
    for line, label in open_holes(text, head, adopting=adopting):
        (must_holes if field_name(label) in must_names else soft_holes).append(
            (line, label)
        )
    return must_holes, soft_holes


def owed(
    text: str, head: protocol_block.Head, *, adopting: bool = False
) -> tuple[list[Field], list[Field]]:
    """(must, should) fields this protocol owes, by its cut, freeze and runs.

    Which fields, by its repeat cost, kind and model, is `owed_fields`'s
    answer; here, when. The low cut owes its marked fields and nothing
    graduates — nothing freezes (LAB-017 The number of audits follows the
    cost tier). The full form owes its musts; `frozen = true` turns every
    should into a must (the graduation gate, in ONE place), and once a
    result is declared a frozen protocol owes its report fields too —
    ADOPTING asks that question of the state an adoption makes, before it
    is made: what `labkit-next` names before `labkit-adopt`, so the two
    agree by construction. A result adopted or being
    adopted owes its answer, the Conclusion, at both cuts: the report's
    result block shows it (`report_blocks.block_body`), and the adoption
    refuses without it, leaving the protocol as it was."""
    # which cut the protocol owes is the contract's answer; the marks on
    # the fields (`Field.low_cut`) are this module's
    owed_here = owed_fields(head.repeat_cost, head.kind, model_named(text))
    # a declared result, or one being adopted, makes the result fields due;
    # its answer, the Conclusion, joins the must on every branch below
    due = adopting or answering_run.adopted_run(text) is not None
    answer = [f for f in owed_here if f.label == CONCLUSION_LABEL] if due else []
    if standard_contract.lane(head.repeat_cost).cut == standard_contract.LOW_CUT:
        return [f for f in owed_here if f.level in ("must", "should")] + answer, []
    must = [f for f in owed_here if f.level == "must"]
    should = [f for f in owed_here if f.level == "should"]
    if not head.frozen:
        return must + answer, should
    report = [f for f in owed_here if f.level == "report"] if due else []
    return must + should + report + answer, []


def kind_registers(kind: str | None, text: str) -> bool:
    """Does a protocol of KIND register promises — the one condition under
    which its [[promise]] tables are owed (`promises.promise_tables_owed`):
    a fit or an apply registers by its kind, a computation only when its
    prose names an id (`promises.prose_names_ids`); an
    undecided kind registers, the most a kind owes."""
    return kind != standard_contract.COMPUTE_KIND or promises.prose_names_ids(text)


def reference_gap(text: str, head: protocol_block.Head) -> str | None:
    """Why the head's `kind` contradicts its `[reference]` table, or None:
    a fit or an apply compares its number in a criterion — one with its
    constants, judged against the null condition —, so the stated value a
    computation compares with (`protocol_block.reference`) has no place on
    a kind with a bar (`standard_contract.has_bar`). The one refusal of
    the table by kind: `protocol-check`, the start of a low run
    (`low_registration_missing`) and finalize read it. The table is
    refused by its presence, whatever it holds: a fit carries no `[kept]`,
    so its `[reference]` never reads, and the way out is to drop it. A
    block that does not parse is the head check's."""
    try:
        present = "reference" in protocol_block.parse_toml_block(text)
    except protocol_block.BlockError:
        return None
    if not present or head.kind is None or not standard_contract.has_bar(head.kind):
        return None
    return (
        f'[reference] with kind = "{head.kind}" — a {head.kind} compares its number '
        f"in a criterion (`[criterion-…]`, with its constants, held against the null condition); "
        f"a comparison with a stated value is a computation's. Drop the table, or "
        f"stamp the area as a compute (`labkit-init exp <name> --kind compute "
        f"--change-kind`)"
    )


def kept_gaps(text: str, head: protocol_block.Head) -> list[MustGap]:
    """What the head owes or refuses of its `[kept]` table by its kind, one
    entry each with the rule its cause breaks, or []: a computation names its kept number there — the
    table missing, or a value still the placeholder (`[kept]
    key`, `[kept] unit`, unfilled fields); a fit or an apply binds its
    answer through its promise keys, so the table is refused there; a
    table that does not read is named by its sentence. A table or value
    that is owed and missing breaks the required-field rule; a table that
    has no place on the kind, the technical contract; a promise block that
    does not read, the rule its error names (`promises.PromiseError.rule`).
    Nothing while the kind is undecided. The one answer `protocol-check`, the start of a low
    run (`low_registration_missing`) and finalize read."""
    try:
        k = protocol_block.kept(text)
    except protocol_block.BlockError as exc:
        return [MustGap(str(exc), TECHNICAL_RULE, INVALID)]
    if head.kind is None:
        return []
    if head.kind != standard_contract.COMPUTE_KIND:
        if k is None:
            return []
        return [
            MustGap(
                f'[kept] with kind = "{head.kind}" — a {head.kind} binds its answer '
                f"through its promise keys (`[[promise]] key`), so the kept number a "
                f"computation names has no place here; drop the table",
                TECHNICAL_RULE,
                INVALID,
            )
        ]
    if k is None:
        return [
            MustGap(
                '[kept] — kind = "compute" names its kept number in the head: '
                '`[kept]` with `key = "<metrics.json key>"` and `unit = "<unit>"` '
                '("1" for a dimensionless number); the run must hold that key as a '
                "finite number",
                LAB_011,
                MISSING,
            )
        ]
    return [MustGap(label, LAB_011, PLACEHOLDER) for label in k.placeholders]


def freeze_must_gaps(text: str, head: protocol_block.Head) -> list[MustGap]:
    """What the head's freeze and repeat cost owe and TEXT lacks, each with
    the rule its cause breaks: `frozen = true` where nothing freezes, a
    freeze without its preflight record named, the `[[promise]]` tables
    owed (`promises.promise_tables_owed`) or not reading."""
    must_gaps: list[MustGap] = []
    # Frozen means audited first (LAB-015 Preflight audit before freezing); at low repeat cost nothing freezes, so a
    # frozen flag there would claim a freeze no gate held.
    lane = standard_contract.lane(head.repeat_cost)
    if head.frozen and not lane.freeze:
        must_gaps.append(
            MustGap(
                f'[protocol] frozen = true at repeat_cost = "{head.repeat_cost}" — nothing '
                "freezes there; set frozen = false or choose high repeat cost",
                OPEN_RULE,
                INVALID,
            )
        )
    elif head.frozen and not head.preflight_audit:
        must_gaps.append(
            MustGap(
                "[protocol] preflight_audit (frozen = true without the decided preflight record named)",
                LAB_015,
                MISSING,
            )
        )
    # Whether the tables are owed is decided in ONE place,
    # promises.promise_tables_owed: frozen, or at low repeat cost (every run there is
    # the full run). No condition repeated here.
    try:
        block = promises.parse_block(text)
        tables_gap = promises.promise_tables_owed(
            block,
            frozen=head.frozen,
            full_run=lane.registration,
            registers=kind_registers(head.kind, text),
        )
    except promises.PromiseError as exc:
        # the requirement broken names its rule where the block is read
        must_gaps.append(
            MustGap(
                f"[[promise]] tables: {exc}",
                exc.rule,
                INVALID,
                way=REPAIR_TABLES,
                block_unread=True,
            )
        )
    else:
        if tables_gap:
            # owed with a block: only a sentence still the stamp's `<…>`
            # (`promises.promise_tables_owed`); without one, no tables
            must_gaps.append(
                MustGap(tables_gap, LAB_004, MISSING if block is None else PLACEHOLDER)
            )
    return must_gaps


def check_fields(text: str, *, adopting: bool = False) -> FieldReport:
    """The field findings of one protocol: head, missing fields (absent from
    the text, `must_gaps`, each with the rule its cause breaks),
    placeholders (`must_holes`); ADOPTING judges the state an adoption
    makes (`owed`)."""
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        return FieldReport(None, str(exc), head_rule(exc), [], [], [], [])
    must, should = owed(text, head, adopting=adopting)
    present = {f.name for f in fields(text)}
    must_gaps = [
        MustGap(f.label, LAB_011, MISSING)
        for f in must
        if f.label.casefold() not in present
    ]
    missing_should = [f.label for f in should if f.label.casefold() not in present]
    must_gaps += [
        MustGap(f"[protocol] {name}", LAB_011, PLACEHOLDER)
        for name in head.placeholders
    ]
    # a claim about the model on the wrong kind is a duty no decided rule
    # states; a [reference] where a criterion judges can never be evaluated
    kind = _kind_gap(text, head)
    if kind:
        must_gaps.append(MustGap(kind[0], OPEN_RULE, kind[1]))
    reference = reference_gap(text, head)
    if reference:  # a table that has no place on the kind
        must_gaps.append(MustGap(reference, TECHNICAL_RULE, INVALID))
    must_gaps += kept_gaps(text, head)
    earlier = promises.earlier_ids(text)
    if earlier:
        # a form labkit no longer reads
        must_gaps.append(
            MustGap(
                f"intent ids {', '.join(earlier)}: {promises.EARLIER_IDS_HELP}",
                TECHNICAL_RULE,
                INVALID,
            )
        )
    must_gaps += freeze_must_gaps(text, head)
    must_holes, soft_holes = must_and_soft_holes(text, head, adopting=adopting)
    return FieldReport(
        head,
        None,
        None,
        must_gaps,
        missing_should,
        must_holes,
        soft_holes,
        repeated_findings(text),
    )


def low_registration_missing(text: str, kind_now: str | None = None) -> list[str]:
    """The registration a run at low repeat cost owes before its number counts:
    the question written (not a placeholder); for a number that judges a
    prediction (kind fit or apply) also criterion, quality check
    and null condition; with a model named also the judged data profile;
    the repeat_cost and the kind declared, the kind not contradicting the
    head (`kind_gap`, `reference_gap`), and a computation's kept number
    named (`kept_gaps`). Returns what is missing — empty means the gate is
    open (LAB-003 No run without an intent paragraph; a computation has no bar to
    clear). A head that does not read
    is named as such: nothing falls back to a computation.

    KIND_NOW, when TEXT is an earlier version of the protocol: the kind it
    declares today. The fields are then owed by that kind, and a TEXT that
    declared another kind misses the kind itself — a fit's criterion added
    after a computation measured was not registered before that number."""
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        return [f"[protocol] head: {exc}"]
    lines = fields(text)
    written = {f.name for f in lines if f.value and not f.placeholder}
    kind = kind_now or head.kind
    # the most is owed while the kind is undecided — and the kind itself
    labels = standard_contract.registration_fields(
        kind or standard_contract.APPLY_KIND, model_named(text)
    )
    missing = (
        [f"[protocol] kind = {kind_now!r} (it said {head.kind!r} then)"]
        if kind_now is not None and head.kind is not None and head.kind != kind_now
        else []
    )
    missing += [label for label in labels if label.casefold() not in written]
    missing += [] if head.repeat_cost else ["[protocol] repeat_cost"]
    missing += [] if head.kind else ["[protocol] kind"]
    contradictions = (kind_gap(text, head), reference_gap(text, head))
    return (
        missing
        + [c for c in contradictions if c]
        + [g.label for g in kept_gaps(text, head)]
    )


#: the key of the kind in a registration stamp, beside the field labels
REGISTRATION_KIND = "kind"
#: a registration field the protocol does not carry, as its stamp names it
REGISTRATION_ABSENT = "<absent>"
#: the key of a computation's `[reference]` in a registration stamp — only
#: while the head carries one: a stamp without the key is a protocol
#: without the table, so a record that lacks the key drifts nowhere
REGISTRATION_REFERENCE = "reference"
#: the key of a computation's `[kept]` in a registration stamp — only while
#: the head carries one, as REGISTRATION_REFERENCE
REGISTRATION_KEPT = "kept"


def registration_stamp(text: str) -> dict[str, str]:
    """The scientific basis an audit judged, as its record binds it: the
    head's `kind` (REGISTRATION_KIND), and per registration field the kind
    owes (`standard_contract.registration_fields`, the most while the kind
    is unset) the digest of its value as `field_values` reads it (whitespace
    folded, so a reflowed line moves nothing; a field written more than once
    is every copy); a field the text lacks is REGISTRATION_ABSENT. The
    report fields written after a run (Conclusion, Recorded results, the
    run list) are not in it: writing them leaves an audit standing. A
    computation's `[reference]` is in it (REGISTRATION_REFERENCE, the
    digest of the table as `protocol_block.reference_toml` writes it): a
    stated value changed, added or dropped after the audit is a changed
    registration. So is its `[kept]` (REGISTRATION_KEPT, the digest of
    `protocol_block.kept_toml`): the kept number named anew after the audit
    is a changed registration. A head that does not read counts as an unset
    kind — the head check names it; a `[reference]` or a `[kept]` that does
    not read counts as none."""
    try:
        kind = protocol_block.head(text).kind
    except protocol_block.BlockError:
        kind = None
    try:
        ref = protocol_block.reference(text)
    except protocol_block.BlockError:
        ref = None
    try:
        kept = protocol_block.kept(text)
    except protocol_block.BlockError:
        kept = None
    labels = standard_contract.registration_fields(
        kind or standard_contract.APPLY_KIND, model_named(text)
    )
    values = field_values(text)
    out = {REGISTRATION_KIND: kind or REGISTRATION_ABSENT}
    if kept is not None:
        out[REGISTRATION_KEPT] = digests.digest(
            protocol_block.kept_toml(kept).encode("utf-8")
        )
    if ref is not None:
        out[REGISTRATION_REFERENCE] = digests.digest(
            protocol_block.reference_toml(ref).encode("utf-8")
        )
    for label in labels:
        value = values.get(field_name(label))
        out[label] = (
            REGISTRATION_ABSENT
            if value is None
            else digests.digest(value.encode("utf-8"))
        )
    return out


def registration_drift(audited: Mapping[str, str], now: Mapping[str, str]) -> list[str]:
    """The registration entries (`registration_stamp`) that differ between
    what an audit judged and the protocol now — the kind or a field label —
    in the order now names them, then those only the audit had. Empty when
    the audit judged this registration."""
    changed = [k for k in now if audited.get(k) != now[k]]
    return changed + [k for k in audited if k not in now]


#: the fields that describe a run that happened — written back after it,
#: never before: filled while no completed run is bound and the head declares
#: no `[result] run`, they claim what did not happen
BEFORE_RUN_CLAIMS = (
    "Recorded results",
    "Raw output",
    "Conclusion",
    "Limitations",
    "Next step",
    "Did",
    "Expected or surprising",
    "Rival check",
    "Caps/drops",
)
_NA = re.compile(r"(?i)^n/a\b")


class AnsweringChoice(Protocol):
    """What this check reads of what the area measured of the protocol —
    the shape of `area_state.Measured` it needs (`answering`), named here
    so the state can import this module without a cycle."""

    def answering(self, adopted: str | None) -> answering_run.AnsweringRun:
        """The run every check holds the protocol to."""
        ...


def written_before_run(
    measured: AnsweringChoice, text: str, head: protocol_block.Head
) -> list[tuple[int, str]]:
    """(line, label) of every BEFORE_RUN_CLAIMS field that is filled while
    the head declares no `[result] run` and no completed run is bound to
    the protocol's id — a report field written before any run. Exact in
    what it says (no run exists) and silent on what it cannot know (whether
    the text claims one); a value of `n/a — …` claims nothing. Empty once a
    run is declared, and for a head that does not read (the head check
    names that)."""
    try:
        if protocol_block.declared_run(text) is not None:
            return []
    except protocol_block.BlockError:
        return []
    names = {field_name(label) for label in BEFORE_RUN_CLAIMS}
    filled = [
        (f.line, f.label)
        for f in fields(text)
        if f.name in names
        and not f.placeholder
        and not DASHES_ONLY.match(f.value)
        and not _NA.match(f.value.strip())
    ]
    if not filled or head.id is None:
        return filled
    return (
        filled
        if measured.answering(answering_run.adopted_run(text)).run_dir is None
        else []
    )


RECORDED_RESULTS_LABEL = "Recorded results"
CONCLUSION_LABEL = "Conclusion"
#: the question registered before the run, anchored at the first
#: measurement (`protocol_history.UNCORRECTABLE_FIELDS`) — not the Summary's
#: `Question †`, its plain rewording written after the run
QUESTION_LABEL = "Question / hypothesis"


def reported_claim(text: str) -> list[tuple[str, str]]:
    """(label, value) of the claim the author makes of the result — the
    Conclusion, as written, a placeholder included — what a decision
    review judged (`reviews.claim_digest`); rewritten afterwards it is
    another claim. The Recorded results line and the Limitation lines are not
    part of it: they are generated from the run and the records and held
    exactly to them (`result_render.render_gaps`), so the record's
    decision and the run's `shown_sha` bind them already — and
    `protocol-fill --from-run` writes them after the decision, which
    would make every review stale at the adoption."""
    return [
        (f.label, f.value.strip())
        for f in fields(text)
        if f.name == field_name(CONCLUSION_LABEL)
    ]


def recorded_results_field(text: str) -> str | None:
    """The generated metrics, run id and limits note in `Recorded results`.

    `protocol-fill --from-run` writes the field and report-check compares
    it with its sources. The head's `[result].run` declares the result
    reported. None while the field is absent or still a placeholder.
    """
    for f in fields(text):
        if f.name == field_name(RECORDED_RESULTS_LABEL) and not f.placeholder:
            return f.value.strip()
    return None


def recorded_results_without_run(text: str) -> str | None:
    """A WARNING when Recorded results is written while the head declares no
    `[result] run`, or None. A result is declared reported by that table
    (report-check holds it at the stop and the commit); an answer without
    it is neither a reported result nor the open field of an exploration —
    it says a number without declaring where it came from. Static evidence:
    the hint, not a gate. None for a head that
    does not read (the head check names that)."""
    if recorded_results_field(text) is None:
        return None
    try:
        if protocol_block.declared_run(text) is not None:
            return None
    except protocol_block.BlockError:
        return None
    return (
        "WARNING: `Recorded results` is written but the head has adopted no run "
        "(`[result] run`) — a reported result is adopted by `labkit-adopt <area> "
        "<run_id>`, which writes the table and Recorded results; report-check "
        "then holds it at the stop and the commit; an exploration that reports no "
        "result leaves the field open (LAB-041 Generate numbers, don't retype them)"
    )


#: the fields a declared result makes due; empty is a placeholder or
#: nothing but dashes. A bare "Label:" at end of line is NOT empty —
#: multi-line values start on the next line.
RESULT_FIELDS = tuple(f.label.casefold() for f in FIELDS if f.level == "after")


def field_label(name: str) -> str:
    """The template label of a casefolded field name."""
    return next(f.label for f in FIELDS if f.label.casefold() == name)


DASHES_ONLY = re.compile(r"^[—–-]+$")


def adoption_owes(text: str) -> tuple[list[str], list[str]]:
    """(absent, holes): the MUST fields newly owed by adopting a result
    into TEXT — owed then, not as TEXT stands; a gap open already is
    another station's. ABSENT not in the text, HOLES
    still a placeholder (`check_fields` with and without `adopting`): the
    Conclusion, and a frozen protocol's † result fields. The one answer
    `labkit-next` names before the adoption and `protocol-fill --from-run`
    refuses on before its first write, so the two agree by construction."""
    now = check_fields(text)
    then = check_fields(text, adopting=True)
    absent = [f for f in then.missing_must if f not in now.missing_must]
    holes = [
        label for at, label in then.must_holes if (at, label) not in now.must_holes
    ]
    return absent, holes


def written_line(text: str, label: str) -> str | None:
    """LABEL's value in TEXT on one line, whitespace collapsed, or None when
    the field is not written, written twice, a placeholder or only dashes:
    a value a report shows verbatim (`report_blocks.block_body`)."""
    f = named_field(text, label)
    if f is None or f.placeholder:
        return None
    value = " ".join(f.value.split())
    return None if not value or DASHES_ONLY.match(value) else value


def conclusion_written(text: str) -> bool:
    """Is the Conclusion written — once, no placeholder, not only dashes
    (`written_line`)? The claim the review binds to (`reviews.claim_digest`)
    and the answer the result block shows, so a review never binds to a
    Conclusion the block refuses."""
    return written_line(text, CONCLUSION_LABEL) is not None


#: a prompt line that shows an item's field: filled per item, so held to no
#: registered line (`prompt_check.check_prompt_drift`, `lanes.Lanes.prompt_drift`)
PLACEHOLDER_IN_PROMPT = re.compile(r"\{[^{}]*\}")


def prompt_blocks(protocol: Path) -> list[str]:
    """Every fenced block under a `Prompt` field, up to the next field at the
    same depth or the next heading — one block per variant is a written
    form, and reading only the first would make a null prompt in a second
    block look missing. The field is the one label parser's (`fields`), the
    blocks the one fence walker's (`markdown.fence_spans`)."""
    text = protocol.read_text(encoding="utf-8")
    lines = text.splitlines()
    found = fields(text)
    blocks: list[str] = []
    for n, f in enumerate(found):
        if f.name != "prompt":
            continue
        indent = len(lines[f.line - 1]) - len(lines[f.line - 1].lstrip())
        end = len(lines)
        for g in found[n + 1 :]:
            deeper = len(lines[g.line - 1]) - len(lines[g.line - 1].lstrip()) > indent
            if not deeper:
                end = g.line - 1
                break
        for j in range(f.line, end):
            if lines[j].startswith("#"):
                end = j
                break
        region = lines[f.line : end]
        blocks += ["\n".join(region[s:e]) for _, s, e in markdown.fence_spans(region)]
    return blocks


def registered_prompt_blocks(protocol: Path) -> list[str]:
    """`prompt_blocks` without the fence the stamp left unfilled
    (`is_stamp_placeholder_block`): the prompts the protocol registers.
    A block that opens and closes with a tag (`<instructions>…`) is one of
    them; empty when the protocol registers no prompt."""
    return [b for b in prompt_blocks(protocol) if not is_stamp_placeholder_block(b)]


def unheld_prompt_lines(prompt: str, blocks: Sequence[str]) -> list[str]:
    """Each fixed line of PROMPT (non-empty, without a `{placeholder}`),
    stripped and in order, that no line of BLOCKS holds stripped — the
    one comparison of a sent prompt with its registration, for the static
    check (`prompt_check.check_prompt_drift`) and the run
    (`lanes.Lanes.prompt_drift`). Every fixed line, when BLOCKS is empty."""
    have = {ln.strip() for b in blocks for ln in b.splitlines() if ln.strip()}
    return [
        ln.strip()
        for ln in prompt.splitlines()
        if ln.strip()
        and not PLACEHOLDER_IN_PROMPT.search(ln)
        and ln.strip() not in have
    ]
