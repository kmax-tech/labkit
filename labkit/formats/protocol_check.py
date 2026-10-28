"""protocol_check — the field contract of a protocol and its reading.

The head — standard, id, type, repeat_cost, frozen, preflight audit — is the
`[protocol]` table of the protocol's ```toml block, read by
`protocol_block` (typed, exact; a malformed head is one MUST failure that
names the field). The prose fields a human writes are held by their exact
template label (`FIELDS`): a field is present when a line `- **<label>:**`
carries it, filled when its value is not a `<…>` placeholder; an explicit
"n/a — <why>" counts, silence does not (scar 2026-08-13: two freely written
protocols omitted "Type" and "Model I/O"; each omission caused a bad run).

What lives here, each stated as its current rule:

  * **The fields** (`fields`, `FieldLine`): every `- **<label>:**` line
    with its value, span and whether it is still a placeholder.
  * **What a protocol owes** (`owed`, `check_fields`): two tiers, one
    template. MUST is the pilot minimum; SHOULD is what a REPORTABLE run
    owes on top. `frozen = true` escalates every SHOULD field to MUST and
    needs the preflight audit line and the promise tables; `repeat_cost =
    "low"` owes its own marked cut and nothing graduates, because
    nothing freezes (LAB-017 The number of audits follows the cost tier).
  * **The registration before a number** (`low_registration_missing`,
    `written_before_run`): what a run at low repeat cost owes first, and a report
    field filled while no run exists.
  * **The result section** (`recorded_results_field`, `recorded_results_without_run`,
    `result_due`): the lines report-check and protocol-fill read; the
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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import (
    promises,
    protocol_block,
    scope_sha,
    standard_contract,
    answering_run,
)


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
# `<!-- l -->` markers and the † marks to the should/report levels. Keyword
# search over the whole file is gone: a word anywhere satisfied a field
# (`prompt` in a sentence covered "Model I/O"), and a narrow word failed a
# filled one (`**Terms:**` against `terms of`).
FIELDS = (
    # Terms first: they precede the question they are asked in (LAB-087 Term before use).
    Field("Terms of this protocol", "must", "l"),
    Field("Question / hypothesis", "must", "l"),
    Field(
        "Success / failure criterion", "must", "lb"
    ),  # a computation has no bar to clear (2026-10-12); a fit or an apply has (0.104)
    Field("Admissibility condition", "must", "lb"),
    Field("Data / scope", "must", "l"),
    # read and judged before the measuring run, not just printed (review
    # 2026-10-21: a class-exclusive cue went unexamined in three judge probes)
    Field("Data profile", "must", "lm"),
    Field("Model / tool", "must", "lb"),
    Field("Model I/O", "must", needs="instrument"),
    Field("Prompt", "must", "lm"),
    Field("Null condition / anchors", "must", "lb"),
    Field("Exclusions / filters", "must", "l"),
    Field("Unit", "must", "l"),
    # A reportable run owes these on top (2026-08-18, "pilot light, report
    # heavy"): missing in all five freely written protocols of Aug 2026.
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
    # The Summary for a person, written after the run (2026-10-07)
    Field("Conclusion", "after", "l"),
    Field(
        "Limits", "after"
    ),  # at low repeat cost the Summary requires Conclusion (2026-10-12)
    Field("Next step", "after"),
    Field("Question", "report"),
    Field("Did", "report"),
    Field("Outcome", "report"),
    Field("Rival check", "report"),
    Field("Caps/drops", "report"),
    # "fällig mit dem Zurückschreiben der Zahl" (LAB-050 Analysis audit before reporting)
    Field("Analysis audit", "report"),
)

#: a bold field label opening a line: `- **Label (gloss) †:** value`
_BULLET = r"^\s*(?:[-*]\s+|\d+[.)]\s+)?"  # `- `, `* `, `1. `, `1) ` or none
_FIELD_OPEN = re.compile(
    _BULLET + r"\*\*(?P<label>[^*]+?)(?::\*\*|\*\*\s*:)(?P<value>.*)$"
)
HTML_COMMENT = re.compile(r"<!--.*?-->")

#: the one protocol template labkit stamps (`labkit-init exp`); the readers
#: that compare a protocol with it, or recognise its placeholders, start here
PROTOCOL_TEMPLATE = PACKAGE_DIR / "templates" / "experiment-protocol.md.template"


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
    fenced = protocol_block.fenced_lines(lines)
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
        for _, start, end in protocol_block.fence_spans(lines)
    )
    return frozenset(b for b in bodies if b.startswith("<") and b.endswith(">"))


def is_stamp_placeholder_block(body: str) -> bool:
    """Is BODY, a code fence's text, whitespace collapsed, one of
    `stamp_block_placeholders` — a block the stamp left unfilled?"""
    return " ".join(body.split()) in stamp_block_placeholders()


#: A list item that is nothing but stamped placeholders — `- <…>`,
#: `- <run_id> — <one sentence: …>`: no label, so no field sees it.
#: A field that points at another area by name only — "wie Bereich 07",
#: "as in area 07" — with no link: the reader has to go and find it, and
#: the one sentence that matters is not here (uniagent area 08, 2026-10-07:
#: five report fields read "wie Bereich 07" and nothing else).
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
        placeholder read as filled (the Model / tool arm lines, 2026-10-21).
        A value that merely starts with `<` (`<10% unparsed`) is content
        (review 2026-10-07: it read as a placeholder, while `TODO` read as
        filled and let a freeze through); a placeholder the author coins
        (`<fill later>`) inside their own prose is not recognised. The id a
        stamp writes before a placeholder (`[C1] <…>`) is not a value: the
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
            or (v.startswith("<") and v.endswith(">"))
            or holds_stamp_placeholder(v)
        )


def fields(text: str) -> list[FieldLine]:
    """Every bold field label in the prose, outside code fences. A label may
    wrap onto the next line (`- **Resolution check (ZERO calls, …\n
    extremes):** <…>`); it is read whole. Parsed once per text: the checker
    asks for a protocol's fields from seven places (owed fields, holes,
    the model, the measure runs, the leftovers, the references), and each
    parsed the file again (audit 2026-10-13)."""
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
    spans = {s - 1: (s, e) for _, s, e in protocol_block.fence_spans(lines)}
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
            if protocol_block.closes(line, fence):
                fence = None
            continue
        opened = protocol_block.FENCE.match(line)
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
        # `- **Label:**` with the text below is written, not empty (the 25er
        # protocol writes them that way; reading the first line only made
        # the registration gate refuse a written registration, review 2026-10-07).
        parts = [m.group("value")]
        while (
            nxt < len(lines)
            and lines[nxt].startswith((" ", "\t"))
            and lines[nxt].strip()
            and not protocol_block.FENCE.match(lines[nxt])
            and not lines[nxt].strip().startswith(("- ", "* "))
            and not re.match(r"\d+[.)]\s", lines[nxt].strip())
        ):
            parts.append(lines[nxt].strip())
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
                block=bool(protocol_block.FENCE.match(below)) or deeper,
                last=nxt,
            )
        )
    return tuple(out)


def placeholder_fields(text: str) -> list[tuple[int, str]]:
    """(line number, label) for every field whose value is still a placeholder."""
    return [(f.line, f.label) for f in fields(text) if f.placeholder]


@dataclass(frozen=True)
class FieldReport:
    """What one protocol owes and lacks. `head_error` set means the head
    could not be read — every other list is then empty."""

    head: protocol_block.Head | None
    head_error: str | None
    missing_must: list[str]
    missing_should: list[str]
    must_holes: list[tuple[int, str]]
    soft_holes: list[tuple[int, str]]

    @property
    def frozen(self) -> bool:
        """Whether the protocol's head says it is frozen."""
        return bool(self.head and self.head.frozen)


def model_named(text: str) -> bool:
    """Does the protocol declare a model in the loop — a `[model]` table in
    the head (`protocol_block.model`)? The one answer for the cut, the
    low registration and `labkit-init --report`. Until 0.100.0 the
    prose `Model / tool` line decided it, read with a pattern for "n/a",
    "none" and dashes (audit 2026-10-15: `—` was model-free here and a
    model there). False for a head that does not read: the head check
    names that."""
    try:
        return protocol_block.model(text) is not None
    except protocol_block.BlockError:
        return False


def bar_owed(f: Field, kind: str | None) -> bool:
    """Does a number of KIND owe `f` as far as its bar decides? Only the "lb"
    fields depend on it, at every tier: a computation owes no criterion (standard
    0.22); an undecided kind owes the most, never the least."""
    return f.low_cut != "lb" or kind is None or standard_contract.has_bar(kind)


def full_owed(f: Field, kind: str | None, model: bool) -> bool:
    """Does the full form owe `f` for a number of KIND, a model named or
    not (MODEL)? A bar field only with a bar (`bar_owed`), a model field
    ("lm") only with a model, a field that `needs` a bar or an instrument
    only with one — a high computation without a model was asked for its
    data profile, prompt, instrument and resolution checks (audit
    2026-10-27, third, I9). An undecided kind owes the most."""
    if not bar_owed(f, kind):
        return False
    if f.low_cut == "lm" and not model:
        return False
    if kind is None or not f.needs:
        return True
    has_bar = standard_contract.has_bar(kind)
    return has_bar if f.needs == "bar" else has_bar or model


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


def kind_gap(text: str, head: protocol_block.Head) -> str | None:
    """Why the head's `kind` contradicts its `[model]` table, or None. A
    computation over a model's outputs says what its number describes
    (`[model] number_describes`): the outputs, or a property of the data
    with the model as annotator — the latter names the evidence that the
    annotator suits (`annotation_validity`), the former names none, or the
    claim and the evidence disagree. A fit or an apply judges the model
    itself, so the claim keys say nothing there. Until the 0.22 rename a
    computation with a `[model]` table was refused outright: a model in the
    loop was taken to judge, though a share of model labels judges no
    prediction (TODO, `compute` plan item 2). Whether a bound protocol is an
    apply with a result is `protocol_history.check_annotation_validity`'s,
    which reads the repo; whether the evidence carries the annotation stays
    the audit's. Loud, never a fallback: a malformed table is the head
    check's."""
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
            )
        return None
    if m.number_describes is None:
        return (
            '[model] number_describes — kind = "compute" with a [model] table '
            'says what the number describes: "model_outputs" (what the model '
            'marked) or "target_property" (a property of the data, the model as '
            "annotator)"
        )
    if (
        m.number_describes == protocol_block.TARGET_PROPERTY
        and m.annotation_validity is None
    ):
        return (
            '[model] annotation_validity — number_describes = "target_property" '
            "claims a property of the data through the model's annotations; name "
            'the evidence the annotator suits: { protocol = "p-…" } (an apply '
            'protocol of this repo with a declared result) or { doi = "10.…" }'
        )
    if (
        m.number_describes == protocol_block.MODEL_OUTPUTS
        and m.annotation_validity is not None
    ):
        return (
            '[model] annotation_validity with number_describes = "model_outputs" '
            "— the number describes the model's outputs, so evidence about the "
            "data claims more than it; drop it or set number_describes = "
            '"target_property"'
        )
    return None


def open_holes(text: str, head: protocol_block.Head) -> list[tuple[int, str]]:
    """(line, label) of every placeholder still to fill.

    At `repeat_cost = "low"` only the cut's fields count: the rest of the full
    form is not owed there, and listing it buried the one real blocker
    under 10 to 20 warnings in every correct protocol at low repeat cost (usability
    probe 2026-10-07, 6 of 6 runs). Fields written after the run count only
    once the head declares a result — before it they cannot be filled, and
    every second agent read them as errors in the commit hook (re-measure
    2026-10-07; until 0.101.0 a run id in the Runs list, minus the words
    "prepare" and "probe", stood for the run)."""
    lines = fields(text)
    if result_due(text) is None:
        after = {f.label.casefold() for f in FIELDS if f.level == "after"}
        lines = [f for f in lines if f.name not in after]
    if standard_contract.lane(head.repeat_cost).cut == standard_contract.LOW_CUT:
        model = model_named(text)
        cut = {f.label.casefold() for f in FIELDS if in_cut(f, head.kind, model)}
        lines = [f for f in lines if f.name in cut]
    return [(f.line, f.label) for f in lines if f.placeholder]


def owed(text: str, head: protocol_block.Head) -> tuple[list[Field], list[Field]]:
    """(must, should) fields this protocol owes, by its cut, freeze and runs.

    The low cut owes its marked fields and nothing graduates — nothing
    freezes (LAB-017 The number of audits follows the cost tier). The full form owes every must
    its kind owes (`bar_owed`: a computation no bar field); `frozen = true` turns
    every should into a must (the graduation gate, in ONE place), and once a
    result is declared a frozen protocol owes its report fields too."""
    # which cut the protocol owes is the contract's answer; the marks on
    # the fields (`Field.low_cut`) are this module's
    if standard_contract.lane(head.repeat_cost).cut == standard_contract.LOW_CUT:
        model = model_named(text)
        must = [
            f
            for f in FIELDS
            if f.level in ("must", "should") and in_cut(f, head.kind, model)
        ]
        return must, []
    model = model_named(text)
    full = [f for f in FIELDS if full_owed(f, head.kind, model)]
    must = [f for f in full if f.level == "must"]
    should = [f for f in full if f.level == "should"]
    if not head.frozen:
        return must, should
    report = [f for f in full if f.level == "report"] if result_due(text) else []
    return must + should + report, []


def check_fields(text: str) -> FieldReport:
    """The field findings of one protocol: head, missing fields, placeholders."""
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        return FieldReport(None, str(exc), [], [], [], [])
    must, should = owed(text, head)
    present = {f.name for f in fields(text)}
    missing_must = [f.label for f in must if f.label.casefold() not in present]
    missing_should = [f.label for f in should if f.label.casefold() not in present]
    missing_must += [f"[protocol] {name}" for name in head.placeholders]
    contradiction = kind_gap(text, head)
    if contradiction:
        missing_must.append(contradiction)
    earlier = promises.earlier_ids(text)
    if earlier:
        missing_must.append(
            f"intent ids {', '.join(earlier)}: {promises.EARLIER_IDS_HELP}"
        )
    # Frozen means audited first (LAB-015 Preflight audit before freezing); at low repeat cost nothing freezes, so a
    # frozen flag there would claim a freeze no gate held (review 2026-10-07).
    lane = standard_contract.lane(head.repeat_cost)
    if head.frozen and not lane.freeze:
        missing_must.append(
            f'[protocol] frozen = true at repeat_cost = "{head.repeat_cost}" — nothing '
            "freezes there; set frozen = false or choose high repeat cost"
        )
    elif head.frozen and not head.preflight_audit:
        missing_must.append(
            "[protocol] preflight_audit (frozen = true without the decided preflight record named)"
        )
    # Whether the tables are owed is decided in ONE place,
    # promises.promise_tables_owed: frozen, or at low repeat cost (every run there is
    # the full run). No condition repeated here (cold reading 2026-10-09).
    try:
        tables_gap = promises.promise_tables_owed(
            promises.parse_block(text),
            frozen=head.frozen,
            full_run=lane.registration,
            # a computation registers nothing unless its prose names an id; a fit
            # or an apply registers by its kind (standard 0.22)
            registers=head.kind != standard_contract.COMPUTE_KIND
            or promises.registers_ids(text),
        )
    except promises.PromiseError as exc:
        tables_gap = f"[[promise]] tables: {exc}"
    if tables_gap:
        missing_must.append(tables_gap)
    must_names = {f.label.casefold() for f in must}
    must_holes, soft_holes = [], []
    for line, label in open_holes(text, head):
        (must_holes if field_name(label) in must_names else soft_holes).append(
            (line, label)
        )
    return FieldReport(head, None, missing_must, missing_should, must_holes, soft_holes)


def low_registration_missing(text: str, kind_now: str | None = None) -> list[str]:
    """The registration a run at low repeat cost owes before its number counts:
    the question written (not a placeholder); for a number that judges a
    prediction (kind fit or apply) also criterion, admissibility condition
    and null condition; with a model named also the judged data profile;
    the repeat_cost and the kind declared, and the kind not contradicting the
    head (`kind_gap`). Returns what is missing — empty means the gate is
    open (LAB-003 No run without an intent paragraph; a computation has no bar to
    clear, 0.87.1; the kind since standard 0.22). A head that does not read
    is named as such: nothing falls back to a computation.

    KIND_NOW, when TEXT is an earlier version of the protocol: the kind it
    declares today. The fields are then owed by that kind, and a TEXT that
    declared another kind misses the kind itself — a fit's criterion added
    after a computation measured was not registered before that number
    (review 2026-10-26)."""
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
    contradiction = kind_gap(text, head)
    return missing + ([contradiction] if contradiction else [])


#: the key of the kind in a registration stamp, beside the field labels
REGISTRATION_KIND = "kind"
#: a registration field the protocol does not carry, as its stamp names it
REGISTRATION_ABSENT = "<absent>"


def registration_stamp(text: str) -> dict[str, str]:
    """The scientific basis an audit judged, as its record binds it: the
    head's `kind` (REGISTRATION_KIND), and per registration field the kind
    owes (`standard_contract.registration_fields`, the most while the kind
    is unset) the digest of its value, whitespace collapsed so a reflowed
    line moves nothing; a field the text lacks is REGISTRATION_ABSENT. The
    report fields written after a run (Conclusion, Recorded results, the
    run list) are not in it: writing them leaves an audit standing. A head
    that does not read counts as an unset kind — the head check names it."""
    try:
        kind = protocol_block.head(text).kind
    except protocol_block.BlockError:
        kind = None
    labels = standard_contract.registration_fields(
        kind or standard_contract.APPLY_KIND, model_named(text)
    )
    values: dict[str, str] = {}
    for f in fields(text):
        values.setdefault(f.name, f.value)
    out = {REGISTRATION_KIND: kind or REGISTRATION_ABSENT}
    for label in labels:
        value = values.get(field_name(label))
        out[label] = (
            REGISTRATION_ABSENT
            if value is None
            else scope_sha.digest(" ".join(value.split()).encode("utf-8"))
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
#: no `[result] run`, they claim what did not happen (Sonnet t18, v2 and
#: v3, 2026-10-16: "Did: ran the 81-point grid and labelled the 55 test
#: molecules", and runs/ held only the preparation)
BEFORE_RUN_CLAIMS = (
    "Recorded results",
    "Raw output",
    "Conclusion",
    "Limits",
    "Next step",
    "Did",
    "Outcome",
    "Rival check",
    "Caps/drops",
)
_NA = re.compile(r"(?i)^n/a\b")


def written_before_run(
    area: Path, text: str, head: protocol_block.Head
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
        if answering_run.bound_answering_run(area, head.id).run_dir is None
        else []
    )


RECORDED_RESULTS_LABEL = "Recorded results"
CONCLUSION_LABEL = "Conclusion"


def reported_claim(text: str) -> list[tuple[str, str]]:
    """(label, value) of the claim the author makes of the result — the
    Conclusion, as written, a placeholder included — what a decision
    review judged (`reviews.claim_digest`); rewritten afterwards it is
    another claim. The Recorded results line and the Limit lines are not
    part of it: they are generated from the run and the records and held
    exactly to them (`result_render.render_gaps`), so the record's
    decision and the run's `shown_sha` bind them already — and
    `protocol-fill --from-run` writes them after the decision, which
    would make every review stale at the adoption (end-to-end test,
    2026-10-22)."""
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
    the hint, not a gate (plan 2026-10-19, TODO 2). None for a head that
    does not read (the head check names that)."""
    if recorded_results_field(text) is None:
        return None
    try:
        if protocol_block.declared_run(text) is not None:
            return None
    except protocol_block.BlockError:
        return None
    return (
        "WARNING: `Recorded results` is written but the head declares no "
        "`[result] run` — a reported result is declared by `protocol-fill <PROTOCOL> "
        "--from-run <run_id>`, which writes the table and Recorded results; report-check "
        "then holds it at the stop and the commit; an exploration that reports no "
        "result leaves the field open (LAB-041 Generate numbers, don't retype them)"
    )


#: the fields a declared result makes due; empty is a placeholder or
#: nothing but dashes. A bare "Label:" at end of line is NOT empty —
#: multi-line values start on the next line (the 25er protocol writes them
#: that way; the first version false-alarmed).
RESULT_FIELDS = tuple(f.label.casefold() for f in FIELDS if f.level == "after")


def field_label(name: str) -> str:
    """The template label of a casefolded field name."""
    return next(f.label for f in FIELDS if f.label.casefold() == name)


DASHES_ONLY = re.compile(r"^[—–-]+$")


def result_due(text: str) -> str | None:
    """The run the head declares (`protocol_block.declared_run`) — from the
    write-back on, the result fields are due (`RESULT_FIELDS`, the report
    fields of a frozen protocol); None while nothing is declared, and for a
    head that does not read (the head check names that). Until 0.101.0 a
    run id in the Runs list, minus the words "prepare" and "probe", stood
    for a measure run and made the result due."""
    try:
        return protocol_block.declared_run(text)
    except protocol_block.BlockError:
        return None


def conclusion_written(text: str) -> bool:
    """Is the Conclusion written — present and no placeholder? The claim the
    review binds to (`reviews.claim_digest`)."""
    return any(
        f.name == field_name(CONCLUSION_LABEL) and f.value.strip() and not f.placeholder
        for f in fields(text)
    )
