"""protocol_check — the field contract of a protocol and its reading.

The head — standard, id, type, cost, frozen, preflight audit — is the
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
    needs the preflight audit line and the promise tables; `cost =
    "seconds"` owes its own marked cut and nothing graduates, because
    nothing freezes (LAB-017 The number of audits follows the cost tier).
  * **The registration before a number** (`seconds_registration_missing`,
    `written_before_run`): what a run of seconds owes first, and a report
    field filled while no run exists.
  * **The result section** (`answering_run_field`, `answer_field`,
    `answer_without_run`, `answering_run_open`, `measure_runs`): the lines
    finalize, report-check and protocol-fill read.

The checks over the whole file — template lines left in, the verbatim
prompt block, a measure run without a written result, change-history prose,
the id against the repo — and the `protocol-check` command are
`protocol_report`'s. Read-only.
"""

import functools
import re
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import (
    promises,
    protocol_block,
    runs,
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
        after   once a measure run is documented (the result written back)
        report  once frozen AND a measure run is documented (the summary and
                the report half of the result; at seconds never — the audit
                comes at promotion there)

    `seconds`: owed in the seconds cut — "s" always, "sm" when a `Model /
    tool` is named; after/report fields carry the template's marker but are
    owed by their level, not by the cut. The template's † marks exactly the
    should and report fields it stamps with `--report` (a test holds this).
    """

    label: str
    level: str
    seconds: str = ""


LEVELS = ("must", "should", "after", "report")

# The one home of what a protocol owes, by the template's exact labels — a
# test holds every label to the template, the seconds cut to its
# `<!-- s -->` markers and the † marks to the should/report levels. Keyword
# search over the whole file is gone: a word anywhere satisfied a field
# (`prompt` in a sentence covered "Model I/O"), and a narrow word failed a
# filled one (`**Terms:**` against `terms of`).
FIELDS = (
    # Terms first: they precede the question they are asked in (LAB-087 Term before use).
    Field("Terms of this protocol", "must", "s"),
    Field("Question / hypothesis", "must", "s"),
    Field(
        "Success / failure criterion", "must", "sm"
    ),  # a count has no bar to clear (2026-10-12)
    Field("Admissibility condition", "must", "sm"),
    Field("Data / scope", "must", "s"),
    Field("Model / tool", "must", "sm"),
    Field("Model I/O", "must"),
    Field("Prompt", "must", "sm"),
    Field("Null condition / anchors", "must", "sm"),
    Field("Exclusions / filters", "must", "s"),
    Field("Unit", "must", "s"),
    # A reportable run owes these on top (2026-08-18, "pilot light, report
    # heavy"): missing in all five freely written protocols of Aug 2026.
    Field("Problem in one sentence", "should"),
    Field("Why this design", "should"),
    Field("Rival explanations", "should"),
    Field("Out of scope", "should"),
    Field("Gate labels", "should"),
    Field("Data preparation", "should"),
    Field("Meaning of the gold label", "should"),
    Field("Answer form + resolution", "should"),
    Field("How measured", "should"),
    Field("Validation", "should"),
    Field("Noise ceiling → threshold", "should"),
    Field("Free knobs", "should"),
    Field("Randomness controls", "should"),
    Field("Instrument check", "should"),
    Field("Yield per stage", "should"),
    # The resolution check (LAB-016 Resolution check before freezing): the criterion over synthetic extremes
    # by the REAL evaluate(), before freezing.
    Field("Resolution check", "should"),
    Field("Prediction for the follow-up run", "should"),
    # Written after the run: before it they cannot exist.
    Field("Answer to the question", "after", "s"),
    Field("Raw output", "after", "sm"),  # a prompt+answer pair: only with a model
    # The Summary for a person, written after the run (2026-10-07)
    Field("Result", "after", "s"),
    Field("Limits", "after"),  # at seconds the Summary is the Result line (2026-10-12)
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
    block: bool = (
        False  # content below the label: a code fence or deeper-indented lines
    )
    last: int = 0  # 1-based last line of the value

    @property
    def placeholder(self) -> bool:
        """Not yet filled: the template's `<…>`, an `n/a — <why>` left as
        stamped, `TODO`, or a bare label with nothing below it (a code block,
        sub-bullets or an indented paragraph count as its value). A value that merely starts with `<` (`<10% unparsed`) is
        content (review 2026-10-07: it read as a placeholder, while `TODO`
        read as filled and let a freeze through)."""
        v = self.value
        if not v:
            return not self.block
        return (
            v.startswith("TODO")
            or "<why>" in v
            or (v.startswith("<") and v.endswith(">"))
        )


def fields(text: str) -> list[FieldLine]:
    """Every bold field label in the prose, outside code fences. A label may
    wrap onto the next line (`- **Resolution check (ZERO calls, …\n
    extremes):** <…>`); it is read whole. Parsed once per text: the checker
    asks for a protocol's fields from seven places (owed fields, holes,
    the model, the measure runs, the leftovers, the references), and each
    parsed the file again (audit 2026-10-13)."""
    return list(_parsed_fields(text))


@functools.lru_cache(maxsize=64)
def _parsed_fields(text: str) -> tuple[FieldLine, ...]:  # noqa: C901 complexity baseline 2026-10-08
    out: list[FieldLine] = []
    lines = text.splitlines()
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
        # the seconds gate refuse a written registration, review 2026-10-07).
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
        below = next((ln for ln in lines[nxt:] if ln.strip()), "")
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


#: a `Model / tool` value that names no model
_NO_MODEL = re.compile(r"^(n/a|none|no model|—|–|-)", re.I)


def model_named(text: str) -> bool:
    """Does the protocol name a model in `Model / tool`? The one answer for
    the cut, the seconds registration and `labkit-init --report` — the
    scaffolder matched the raw text with its own spelling (audit 2026-10-15:
    `**Model / tool:** —` was model-free here and a model there)."""
    found: dict[str, list[FieldLine]] = {}
    for f in fields(text):
        found.setdefault(f.name, []).append(f)
    return model_named_in(found)


def model_named_in(found: dict[str, list[FieldLine]]) -> bool:
    """`model_named` over fields already grouped by name (FOUND)."""
    for f in found.get("model / tool", []):
        if f.value and not f.placeholder and not _NO_MODEL.match(f.value):
            return True
    return False


def in_cut(f: Field, model: bool) -> bool:
    """Is `f` part of the seconds cut — "s" always, "sm" with a model named?"""
    return f.seconds == "s" or (f.seconds == "sm" and model)


def open_holes(text: str, head: protocol_block.Head) -> list[tuple[int, str]]:
    """(line, label) of every placeholder still to fill.

    At `cost = "seconds"` only the cut's fields count: the rest of the full
    form is not owed there, and listing it buried the one real blocker
    under 10 to 20 warnings in every correct seconds protocol (usability
    probe 2026-10-07, 6 of 6 runs). Fields written after the run count only
    once a measure run is documented — before it they cannot be filled, and
    every second agent read them as errors in the commit hook (re-measure
    2026-10-07)."""
    lines = fields(text)
    if not measure_runs(text):
        after = {f.label.casefold() for f in FIELDS if f.level == "after"}
        lines = [f for f in lines if f.name not in after]
    if standard_contract.lane(head.cost).cut == standard_contract.SECONDS_CUT:
        found: dict[str, list[FieldLine]] = {}
        for f in lines:
            found.setdefault(f.name, []).append(f)
        model = model_named_in(found)
        cut = {f.label.casefold() for f in FIELDS if in_cut(f, model)}
        lines = [f for f in lines if f.name in cut]
    return [(f.line, f.label) for f in lines if f.placeholder]


def owed(text: str, head: protocol_block.Head) -> tuple[list[Field], list[Field]]:
    """(must, should) fields this protocol owes, by its cut, freeze and runs.

    The seconds cut owes its marked fields and nothing graduates — nothing
    freezes (LAB-017 The number of audits follows the cost tier). The full form owes every must; `frozen = true` turns
    every should into a must (the graduation gate, in ONE place), and once a
    measure run is documented a frozen protocol owes its report fields too."""
    found: dict[str, list[FieldLine]] = {}
    for f in fields(text):
        found.setdefault(f.name, []).append(f)
    # which cut the protocol owes is the contract's answer; the marks on
    # the fields (`Field.seconds`) are this module's
    if standard_contract.lane(head.cost).cut == standard_contract.SECONDS_CUT:
        model = model_named_in(found)
        must = [f for f in FIELDS if f.level in ("must", "should") and in_cut(f, model)]
        return must, []
    must = [f for f in FIELDS if f.level == "must"]
    should = [f for f in FIELDS if f.level == "should"]
    if not head.frozen:
        return must, should
    report = [f for f in FIELDS if f.level == "report"] if measure_runs(text) else []
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
    earlier = promises.earlier_ids(text)
    if earlier:
        missing_must.append(
            f"intent ids {', '.join(earlier)}: {promises.EARLIER_IDS_HELP}"
        )
    # Frozen means audited first (LAB-015 Preflight audit before freezing); at seconds nothing freezes, so a
    # frozen flag there would claim a freeze no gate held (review 2026-10-07).
    lane = standard_contract.lane(head.cost)
    if head.frozen and not lane.freeze:
        missing_must.append(
            f'[protocol] frozen = true at cost = "{head.cost}" — nothing '
            "freezes there; set frozen = false or choose minutes/hours"
        )
    elif head.frozen and not head.preflight_audit:
        missing_must.append(
            "[protocol] preflight_audit (frozen = true without the audit line)"
        )
    # Whether the tables are owed is decided in ONE place,
    # promises.promise_tables_owed: frozen, or at seconds (every run there is
    # the full run). No condition repeated here (cold reading 2026-10-09).
    try:
        tables_gap = promises.promise_tables_owed(
            promises.parse_block(text),
            frozen=head.frozen,
            full_run=lane.every_run_full,
            registers=promises.registers_ids(text),
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


def seconds_registration_missing(text: str) -> list[str]:
    """The registration a run of seconds owes before its number counts:
    the question written (not a placeholder), with a model named also
    criterion and admissibility condition, and the cost declared.
    Returns what is missing — empty means the gate is open (LAB-003 No run
    without an intent paragraph; a count has no bar to clear, 0.87.1)."""
    lines = fields(text)
    written = {f.name for f in lines if f.value and not f.placeholder}
    by_name: dict[str, list[FieldLine]] = {}
    for f in lines:
        by_name.setdefault(f.name, []).append(f)
    labels = standard_contract.registration_fields(model_named_in(by_name))
    missing = [label for label in labels if label.casefold() not in written]
    try:
        cost = protocol_block.head(text).cost
    except protocol_block.BlockError:
        cost = None
    return missing + ([] if cost else ["[protocol] cost"])


ANSWERING_RUN_LABEL = "answering run"


#: the fields that describe a run that happened — written back after it,
#: never before: filled while no completed run is bound and "Answering run"
#: is still the stamp's, they claim what did not happen (Sonnet t18, v2 and
#: v3, 2026-10-16: "Did: ran the 81-point grid and labelled the 55 test
#: molecules", and runs/ held only the preparation)
BEFORE_RUN_CLAIMS = (
    "Answer to the question",
    "Raw output",
    "Result",
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
    the protocol's "Answering run" is still open and no completed run is
    bound to its id — a report field written before any run. Exact in what
    it says (no run exists) and silent on what it cannot know (whether the
    text claims one); a value of `n/a — …` claims nothing. Empty for a cut
    without the "Answering run" line, or once a run is named there."""
    answering = answering_run_field(text)
    if answering is None or not answering_run_open(answering):
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


def answering_run_field(text: str) -> str | None:
    """The value of the protocol's `Answering run` field, None when the
    protocol has no such line (a cut without the Result section)."""
    for f in fields(text):
        if f.name == ANSWERING_RUN_LABEL:
            return f.value.strip()
    return None


ANSWER_LABEL = "answer to the question"


def answer_field(text: str) -> str | None:
    """The value of the protocol's `Answer to the question` field — the one
    line that declares a result reported: written by `protocol-fill
    --from-run` with the number and the run_id, held by finalize to the
    answering run. None while the field is absent or still a placeholder."""
    for f in fields(text):
        if f.name == ANSWER_LABEL and not f.placeholder:
            return f.value.strip()
    return None


def answer_without_run(text: str) -> str | None:
    """A WARNING when the Answer is written but names no run_id, or None.
    A result is declared reported by its run_id in that line (report-check
    holds it at the stop and the commit); an answer without one is neither
    a reported result nor the open field of an exploration — it says a
    number without saying where it came from. Static evidence: the hint,
    not a gate (plan 2026-10-19, TODO 2)."""
    value = answer_field(text)
    if value is None or runs.RUN_ID.search(value):
        return None
    return (
        "WARNING: `Answer to the question` is written but names no run_id — a "
        "reported result names its run (`protocol-fill --from-run <run_id>` "
        "writes both; report-check then holds it at the stop and the commit); "
        "an exploration that reports no result leaves the field open "
        "(LAB-041 Generate numbers, don't retype them)"
    )


def answering_run_open(value: str) -> bool:
    """Is this `Answering run` value still the stamp's — `none yet …` or a
    `<…>` placeholder — rather than a run id? The one answer finalize (warn:
    not written yet) and protocol-fill --from-run (write it) share; the stamp's
    `none yet` is no `<…>` placeholder, so `fill` read it as filled and
    --from-run skipped the line silently (cold Sonnet, 2026-10-14)."""
    return value.startswith("none yet") or value.startswith("<")


# runlog run ids as they appear in the run index: 2026-08-23T20-37-21_afbe. A
# line carrying one that is NOT data preparation or a throwaway probe is a
# measure run — from then on an empty Result is a MUST gap, pilot or not.
SETUP_RUN = re.compile(r"prepare|probe|wegwerf|trockenlauf|dry.?run", re.I)
#: the fields a documented measure run makes due; empty is a placeholder or
#: nothing but dashes. A bare "Label:" at end of line is NOT empty —
#: multi-line values start on the next line (the 25er protocol writes them
#: that way; the first version false-alarmed).
RESULT_FIELDS = tuple(f.label.casefold() for f in FIELDS if f.level == "after")


def field_label(name: str) -> str:
    """The template label of a casefolded field name."""
    return next(f.label for f in FIELDS if f.label.casefold() == name)


DASHES_ONLY = re.compile(r"^[—–-]+$")


def measure_runs(text: str) -> list[tuple[int, str]]:
    """(line, run_id) of every documented run that is not data preparation
    or a throwaway probe — from the first one on, the result is due."""
    return [
        (n, m.group(0))
        for n, ln in enumerate(text.splitlines(), 1)
        if (m := runs.RUN_ID.search(ln)) and not SETUP_RUN.search(ln)
    ]
