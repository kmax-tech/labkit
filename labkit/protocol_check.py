#!/usr/bin/env python3
"""Check experiment protocols: the head as data, the prose fields by label.

The head — standard, id, type, cost, frozen, preflight audit — is the
`[protocol]` table of the protocol's ```toml block, read by
`protocol_block` (typed, exact; a malformed head is one MUST failure that
names the field). The prose fields a human writes are held by their exact
template label (`FIELDS`): a field is present when a line `- **<label>:**`
carries it, filled when its value is not a `<…>` placeholder; an explicit
"n/a — <why>" counts, silence does not (scar 2026-08-13: two freely written
protocols omitted "Type" and "Model I/O"; each omission caused a bad run).

The checks, each stated as its current rule (the change history lives in the
commits, AS-075 Docs tragen den Stand):

  * **Two tiers, one template.** MUST is the pilot minimum; SHOULD is what
    a REPORTABLE run owes on top. `frozen = true` escalates every SHOULD
    field to MUST: an unfrozen pilot's numbers stay pilot numbers — "Pilot
    leicht, Bericht schwer" without a second template that would drift
    (2026-08-18). `cost = "seconds"` owes its own marked cut and nothing
    graduates, because nothing freezes (AS-017 Die Zahl der Audits folgt der Kostenstufe).
  * **Template-line detection.** Any line still identical to a line of the
    template is instruction, not content.
  * **Verbatim-block check.** A protocol with a Prompt field but no fenced
    example block paraphrases its prompt — a MUST failure; so is `frozen =
    true` without a single rendered example.
  * **A measure run demands a written result.** A documented run_id that
    is not a prepare/probe line makes empty `Answer to the question` / `Raw
    output` fields a MUST failure — the context that explains the numbers
    dies with the session (2026-08-24).
  * **Change-history prose is a warning** (AS-075 Docs tragen den Stand).

Usage:
    protocol-check PROTOCOL-foo.md [more files or directories ...]
    protocol-check --template experiment-protocol.md.template <files>

Directories are searched recursively for PROTOCOL-*.md. Exit code 1 if any
MUST field is missing or unfilled in any file; SHOULD fields only warn.

Protocols with a prose head (Standard 0.16/0.17) are read by labkit 0.47.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from labkit import promises, protocol_block
from labkit.repo import git_root, git_run
from labkit.scope_sha import audit_stamp_drift


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
    # Terms first: they precede the question they are asked in (AS-087 Begriff vor Gebrauch).
    Field("Terms of this protocol", "must", "s"),
    Field("Question / hypothesis", "must", "s"),
    Field("Success / failure criterion", "must", "s"),
    Field("Admissibility condition", "must", "s"),
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
    # The resolution check (AS-016 Auflösungsprobe vor dem Einfrieren): the criterion over synthetic extremes
    # by the REAL evaluate(), before freezing.
    Field("Resolution check", "should"),
    Field("Prediction for the follow-up run", "should"),
    # Written after the run: before it they cannot exist.
    Field("Answer to the question", "after", "s"),
    Field("Raw output", "after", "s"),
    Field("Question", "report"),
    Field("Did", "report"),
    Field("Result", "report"),
    Field("Status", "report"),
    Field("Outcome", "report"),
    Field("Rival check", "report"),
    Field("Caps/drops", "report"),
    # "fällig mit dem Zurückschreiben der Zahl" (AS-050 Auswertungs-Audit vor dem Berichten)
    Field("Analysis audit", "report", "s"),
)

#: a bold field label opening a line: `- **Label (gloss) †:** value`
_BULLET = r"^\s*(?:[-*]\s+|\d+[.)]\s+)?"  # `- `, `* `, `1. `, `1) ` or none
_FIELD_OPEN = re.compile(
    _BULLET + r"\*\*(?P<label>[^*]+?)(?::\*\*|\*\*\s*:)(?P<value>.*)$"
)
_MARKER = re.compile(r"<!--.*?-->")


def field_name(label: str) -> str:
    """`Prompt (verbatim, per variant)` → `prompt`; `Free knobs †` → `free knobs`."""
    return label.split("(")[0].replace("†", "").strip().casefold()


@dataclass(frozen=True)
class FieldLine:
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
    extremes):** <…>`); it is read whole."""
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
            and not lines[nxt].strip().startswith(("```", "- ", "* "))
            and not re.match(r"\d+[.)]\s", lines[nxt].strip())
        ):
            parts.append(lines[nxt].strip())
            nxt += 1
        value = _MARKER.sub("", " ".join(parts)).strip()
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
                block=below.lstrip().startswith(("```", "~~~")) or deeper,
                last=nxt,
            )
        )
    return out


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
        return bool(self.head and self.head.frozen)


#: a `Model / tool` value that names no model
_NO_MODEL = re.compile(r"^(n/a|none|no model|—|–|-)", re.I)


def _model_named(found: dict[str, list[FieldLine]]) -> bool:
    for f in found.get("model / tool", []):
        if f.value and not f.placeholder and not _NO_MODEL.match(f.value):
            return True
    return False


def _in_cut(f: Field, model: bool) -> bool:
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
    if head.cost == "seconds":
        found: dict[str, list[FieldLine]] = {}
        for f in lines:
            found.setdefault(f.name, []).append(f)
        model = _model_named(found)
        cut = {f.label.casefold() for f in FIELDS if _in_cut(f, model)}
        lines = [f for f in lines if f.name in cut]
    return [(f.line, f.label) for f in lines if f.placeholder]


def owed(text: str, head: protocol_block.Head) -> tuple[list[Field], list[Field]]:
    """(must, should) fields this protocol owes, by its cut, freeze and runs.

    The seconds cut owes its marked fields and nothing graduates — nothing
    freezes (AS-017 Die Zahl der Audits folgt der Kostenstufe). The full form owes every must; `frozen = true` turns
    every should into a must (the graduation gate, in ONE place), and once a
    measure run is documented a frozen protocol owes its report fields too."""
    found: dict[str, list[FieldLine]] = {}
    for f in fields(text):
        found.setdefault(f.name, []).append(f)
    if head.cost == "seconds":
        model = _model_named(found)
        must = [
            f for f in FIELDS if f.level in ("must", "should") and _in_cut(f, model)
        ]
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
    # Frozen means audited first (AS-015 Preflight-Audit vor dem Einfrieren); at seconds nothing freezes, so a
    # frozen flag there would claim a freeze no gate held (review 2026-10-07).
    if head.frozen and head.cost == "seconds":
        missing_must.append(
            '[protocol] frozen = true at cost = "seconds" — nothing '
            "freezes there; set frozen = false or choose minutes/hours"
        )
    elif head.frozen and not head.preflight_audit:
        missing_must.append(
            "[protocol] preflight_audit (frozen = true without the audit line)"
        )
    must_names = {f.label.casefold() for f in must}
    must_holes, soft_holes = [], []
    for line, label in open_holes(text, head):
        (must_holes if field_name(label) in must_names else soft_holes).append(
            (line, label)
        )
    return FieldReport(head, None, missing_must, missing_should, must_holes, soft_holes)


def intent_missing(text: str) -> list[str]:
    """The registration a run of seconds owes before its number counts:
    question, criterion and admissibility condition written (not a
    placeholder) and the cost declared. Returns what is missing — empty
    means the gate is open (AS-003 Kein Lauf ohne Intent-Absatz)."""
    written = {f.name for f in fields(text) if f.value and not f.placeholder}
    missing = [
        label
        for label in (
            "Question / hypothesis",
            "Success / failure criterion",
            "Admissibility condition",
        )
        if label.casefold() not in written
    ]
    try:
        cost = protocol_block.head(text).cost
    except protocol_block.BlockError:
        cost = None
    return missing + ([] if cost else ["[protocol] cost"])


_ID_INDEX: dict[Path, dict[str, list[Path]]] = {}


def _id_of(text: str) -> str | None:
    """The head's id, None when the head is missing, malformed or unstamped."""
    try:
        return protocol_block.head(text).id
    except protocol_block.BlockError:
        return None


def repo_protocol_ids(start: Path) -> dict[str, list[Path]]:
    """Every protocol id in the repo, mapped to the files carrying it.

    Uniqueness cannot be settled at the stamp alone: copying a protocol or
    editing the id by hand makes a duplicate long after `lib exp` ran, and
    two protocols with one id bind their runs to the same thing.
    """
    root = git_root(start)
    if root is None:
        return {}
    if root not in _ID_INDEX:
        index: dict[str, list[Path]] = {}
        for f in sorted(root.rglob("PROTOCOL-*.md")):
            try:
                pid = _id_of(f.read_text(encoding="utf-8"))
            except OSError:
                continue
            if pid:
                index.setdefault(pid, []).append(f)
        _ID_INDEX[root] = index
    return _ID_INDEX[root]


def id_in_head(path: Path) -> str | None:
    """The id the committed version of this file carries — None when the file
    is new, git is absent, or the call fails. Never a proof of immutability:
    after the next commit a changed id IS the state. It catches the edit
    while it is still in the working tree."""
    root = git_root(path)
    if root is None:
        return None
    rel = path.resolve().relative_to(root)
    r = git_run(["show", f"HEAD:{rel}"], root)
    return _id_of(r.stdout) if r.returncode == 0 else None


def check_protocol_id(path: Path, head: protocol_block.Head) -> list[str]:
    """Uniqueness and working-tree divergence of the protocol id; its shape
    is the head parser's job, an unstamped id a must placeholder."""
    if head.id is None:
        return []
    out = []
    others = [
        q
        for q in repo_protocol_ids(path).get(head.id, [])
        if q.resolve() != path.resolve()
    ]
    if others:
        out.append(
            f"{path}: DUPLICATE protocol id {head.id} — also carried by "
            + ", ".join(str(q) for q in others)
            + ". An id binds runs to ONE protocol; re-stamp the copy."
        )
    was = id_in_head(path)
    if was and was != head.id:
        out.append(
            f"{path}: WARNING: protocol id changed against HEAD "
            f"({was} -> {head.id}) — runs bound to the old id stop "
            f"resolving."
        )
    return out


# runlog run ids as they appear in the run index: 2026-08-23T20-37-21_afbe. A
# line carrying one that is NOT data preparation or a throwaway probe is a
# measure run — from then on an empty Result is a MUST gap, pilot or not.
RUN_ID = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_[0-9a-f]{2,12}\b")
SETUP_RUN = re.compile(r"prepare|probe|wegwerf|trockenlauf|dry.?run", re.I)
#: the fields a documented measure run makes due; empty is a placeholder or
#: nothing but dashes. A bare "Label:" at end of line is NOT empty —
#: multi-line values start on the next line (the 25er protocol writes them
#: that way; the first version false-alarmed).
RESULT_FIELDS = tuple(f.label.casefold() for f in FIELDS if f.level == "after")
_DASHES = re.compile(r"^[—–-]+$")


def measure_runs(text: str) -> list[tuple[int, str]]:
    """(line, run_id) of every documented run that is not data preparation
    or a throwaway probe — from the first one on, the result is due."""
    return [
        (n, m.group(0))
        for n, ln in enumerate(text.splitlines(), 1)
        if (m := RUN_ID.search(ln)) and not SETUP_RUN.search(ln)
    ]


def unreported(text: str) -> list[str]:
    """The result fields still missing, a placeholder or only dashes."""
    found = {f.name: f for f in fields(text)}
    return [
        name
        for name in RESULT_FIELDS
        if name not in found
        or found[name].placeholder
        or _DASHES.match(found[name].value)
    ]


# A follow-up registration appended to the SAME protocol — the pattern that
# grew one file to 649 lines out of three experiments ("Lauf B — ...
# (deklariert vor dem Lauf)", "Stufe 2 ..."): each such heading is a second
# question in a one-question file. The series rule (Arbeitsstandard AS-061 Subexperiment-Serien tragen ihre Nummer im Namen)
# gives every follow-up its own PROTOCOL-s<N>-<slug>.md. Warning only.
SERIES_HEAD = re.compile(
    r"(?im)^##.*\((deklariert|registriert) vor dem( jeweils \w+)? "
    r"(lauf|vote|pilot)|declared before the run\)?"
)

# The documented runs are mandatory content (one line per run_id), not prose —
# counting it against the length budget taught people not to document runs
# (found 2026-09-06: 93 of a protocol's 409 lines were its run list).
# "ledger" stays in the pattern, not in the vocabulary: protocols written
# before 2026-09-26 head the section "## Runs (ledger — ...)".
DOCUMENTED_RUNS_HEAD = re.compile(r"(?i)^##\s.*(runs|ledger|l[\u00e4a]ufe)")

# Change-history prose — the doc should carry the current rule, the commit the
# change (AS-075 Docs tragen den Stand). Warning only.
CHANGELOG = re.compile(
    r"seit 20\d\d-\d\d|wieder drau[ßs]+en|wieder drin\b|hie[ßs]+ bis"
    r"|vorher (stand|galt)|fr[üu]her hie[ßs]+|umbenannt am",
    re.I,
)

# Line budget per section. The global 350 only bites once a protocol is
# already unreadable; the per-section budgets sit between the corpus median
# and its upper quartile, so they flag roughly the top third instead of
# everything (a warning that fires on every file is background noise).
# Calibration 2026-09-15, 94 protocols with an Intent section across
# ~/projects + ~/work: Intent median 25, Q3 38 — but confirmatory protocols
# (n=59) sit at median 30, because the intent ids moved mandatory
# registrations INTO Intent; the disciplined confirmatory cluster tops out
# at 35 prose lines, so the budget sits at that ceiling and still flags the
# top quarter. Setup as before (median 42, top quartile above 54; only 556
# of 3344 Setup lines are code blocks — the length is prose, not evidence).
# Needs more room? That is a note, and here stands its [[wikilink]].
SECTION_BUDGET = [
    ("Summary", r"summary|zusammenfassung", 20),
    ("Context", r"context|einordnung", 20),
    ("Intent", r"intent|absicht|hypothese und kriterien|die eine frage", 35),
    ("Setup", r"setup|aufbau", 45),
]


def oversized_sections(text: str) -> list[tuple[str, int, int]]:
    """(label, prose lines, budget) for each section over budget.

    Counted like the global length check: code fences (rendered examples are
    mandatory raw output) and table rows do not count against the budget.
    """
    counts: dict[str, int] = {}
    cur, fence = None, False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fence = not fence
            continue
        if fence or stripped.startswith("|"):
            continue
        if stripped.startswith("## "):
            head = stripped[3:].lower()
            cur = next(
                (lb for lb, pat, _ in SECTION_BUDGET if re.search(pat, head)), None
            )
            continue
        if cur:
            counts[cur] = counts.get(cur, 0) + 1
    return [
        (lb, counts[lb], lim)
        for lb, _, lim in SECTION_BUDGET
        if counts.get(lb, 0) > lim
    ]


def template_lines(path: Path | None) -> set[str]:
    """Instruction lines of the template, normalised for comparison.

    The preamble — everything before the first `## ` section — is the
    stamped legend (field-id key, standard version, guide pointer). It is
    MEANT to survive filling, so it must not count as "still verbatim
    template text": counting it flagged every freshly stamped protocol
    forever and taught people to delete the legend (2026-09-14/15, two
    sessions of false positives on a correctly filled protocol).
    """
    if path is None or not path.exists():
        return set()
    keep = set()
    in_body = False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("## "):
            in_body = True
        # Only lines long enough to be distinctive; headings are meant to recur.
        if in_body and len(s) >= 40 and not s.startswith("#"):
            keep.add(s)
    return keep


def find_template(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    here = Path(__file__).resolve().parent / "experiment-protocol.md.template"
    return here if here.exists() else None


def find_field_guide() -> Path | None:
    here = Path(__file__).resolve().parent / "protocol-field-guide.md"
    return here if here.exists() else None


def print_contract() -> None:
    """The checker's contract in one screen (2026-10-05: two cold agents
    learnt the budgets from the pre-commit hook and the field words from
    the checker's source, four rewrite rounds each). The seconds cut and the
    fill command come first: last, five of six agents found them only after
    reading the whole list, and none found protocol-fill (2026-10-07)."""
    print(
        'at cost = "seconds" (nothing freezes, no SHOULD) the protocol owes: '
        + ", ".join(
            f.label
            for f in FIELDS
            if f.seconds == "s" and f.level in ("must", "should")
        )
        + "; with a model named in `Model / tool` also "
        + ", ".join(f.label for f in FIELDS if f.seconds == "sm")
        + "; after the run: "
        + ", ".join(f.label for f in FIELDS if f.seconds == "s" and f.level == "after")
        + "."
    )
    print(
        "fill a field by its label, multi-line placeholders included: "
        'protocol-fill PROTOCOL-x.md "<label>" "<value>"; what is still open: '
        "protocol-fill PROTOCOL-x.md --list; the Prompt block from the scripts' "
        "PROMPT constants: protocol-fill PROTOCOL-x.md --prompts\n"
    )
    print(
        "head: the ```toml block's [protocol] table — "
        + ", ".join(protocol_block.HEAD_FIELDS)
        + f"; standard = {protocol_block.STANDARD!r}, type one of "
        + ", ".join(protocol_block.TYPES)
        + ", cost one of "
        + ", ".join(protocol_block.COST_TIERS)
        + "."
    )
    print(
        "\nprose-line budget per section (code blocks, table rows exempt; "
        "a MUST once frozen):"
    )
    for label, _, limit in SECTION_BUDGET:
        print(f"  {label:<9} {limit}")
    print(
        "\nfields, by their exact template label (`- **<label>:** <value>`; a "
        "parenthesised gloss and † may follow the label; `n/a — <the reason>` "
        "counts as filled, `<…>`, `TODO`, an empty label and a bare `n/a — <why>` do not)."
        ' The lists below are the FULL form (cost = "minutes" | "hours"); at '
        'cost = "seconds" only the first line of this output counts:'
    )
    for level, title in (
        ("must", "MUST (every pilot of the full form)"),
        ("should", "SHOULD (MUST once frozen = true)"),
        ("after", "after the run (owed once a measure run is documented)"),
        ("report", "report (owed once frozen = true and a measure run is documented)"),
    ):
        print(f"\n  {title}")
        for f in FIELDS:
            if f.level == level:
                print(f"    {f.label}")


def code_blocks(text: str) -> int:
    """Top-level fenced blocks other than the TOML head — the rendered examples."""
    return sum(1 for info, _ in protocol_block.fenced_blocks(text) if info != "toml")


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(sorted(p.rglob("PROTOCOL-*.md")))
        else:
            files.append(p)
    return files


def main(argv: list[str]) -> int:
    _ID_INDEX.clear()  # one scan per invocation; never a stale one
    if argv and argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: protocol-check [--template PATH] <PROTOCOL-*.md | dir> ...")
        print(
            "  --template PATH  check against this template instead of the packaged one"
        )
        print("  --guide          print the path to the protocol field guide")
        print(
            "  --contract       print what the checker holds a protocol to: the "
            "prose-line budget per section and the exact label of each field "
            "recognised by — read it BEFORE writing, not from the pre-commit hook"
        )
        return 0
    if argv and argv[0] == "--contract":
        print_contract()
        return 0
    if argv and argv[0] == "--guide":
        fg = find_field_guide()
        print(fg or "field guide not found")
        return 0 if fg else 1
    tmpl_arg = None
    if argv and argv[0] == "--template":
        if len(argv) < 2:
            print("--template needs a path")
            return 2
        tmpl_arg, argv = argv[1], argv[2:]
    if not argv:
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: protocol-check [--template PATH] <PROTOCOL-*.md | dir> ...")
        return 2
    files = collect(argv)
    if not files:
        print("protocol-check: no PROTOCOL-*.md found")
        return 2

    tmpl = template_lines(find_template(tmpl_arg))
    failed = False
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{f}: not readable ({exc})")
            failed = True
            continue

        report = check_fields(text)
        if report.head is None:
            print(f"{f}: HEAD (must): {report.head_error}")
            failed = True
            continue
        if (
            report.frozen
            and report.head.cost != "seconds"
            and report.head.preflight_audit
        ):
            drift = audit_stamp_drift(f.parent, report.head.preflight_audit)
            if drift:  # a warning: after the run, analysis scripts change legitimately
                print(f"{f}: WARNING: preflight_audit: {drift}")
        for finding in check_protocol_id(f, report.head):
            print(finding)
            if "WARNING" not in finding:
                failed = True
        frozen = report.frozen
        missing_must, missing_should = report.missing_must, report.missing_should
        must_holes, soft_holes = report.must_holes, report.soft_holes
        holes = must_holes + soft_holes
        examples = code_blocks(text)
        pilot_note = ""
        if not frozen and missing_should:
            pilot_note = (
                f"pilot (frozen = false) — {len(missing_should)} "
                f"should-field(s) due only at report time "
                f"(append them: lib exp <name> --report)"
            )
            missing_should = []
        # A placeholder is reported as one already, and a comment can never
        # be "filled" — neither is left-over template text (review 2026-10-07:
        # a correctly filled seconds protocol was never clean).
        in_placeholder = {
            n for f in fields(text) if f.placeholder for n in range(f.line, f.last + 1)
        }
        left = sorted(
            {
                s
                for n, s in enumerate((ln.strip() for ln in text.splitlines()), 1)
                if s in tmpl and not s.startswith("<!--") and n not in in_placeholder
            }
        )
        # "mentions a prompt" means a Prompt FIELD, not the word: the stamped
        # legend says "prompt" in every protocol, and a count protocol cut
        # without the field was blocked for it (2026-10-05).
        no_block = not examples and any(
            f.name == "prompt" and not f.value.lower().startswith("n/a")
            for f in fields(text)
        )
        frozen_without_io = frozen and not examples
        # A protocol is a registration, not a lab journal. By 2026-08-20 one
        # had grown to 646 lines because every re-freeze APPENDED its
        # narrative instead of replacing it — presence was checked, length
        # never. The condensed version of that same protocol (all fields,
        # all numbers, four code blocks) has 296 lines; 350 leaves room.
        # Only PROSE counts: code fences (rendered examples are the raw-output
        # MUST) and table rows (confound profiles, error directions) do not —
        # raw-line counting had flagged three registration-dense protocols
        # as journals, one of which never even ran (2026-08-25).
        in_fence, in_runs, n_lines = False, False, 0
        for _l in text.splitlines():
            _s = _l.strip()
            if _s.startswith("```"):
                in_fence = not in_fence
                continue
            if _s.startswith("## "):
                in_runs = bool(DOCUMENTED_RUNS_HEAD.match(_s))
            if not in_fence and not in_runs and not _s.startswith("|"):
                n_lines += 1
        too_long = n_lines > 350
        big = oversized_sections(text)
        series = [
            (n, ln.strip())
            for n, ln in enumerate(text.splitlines(), 1)
            if SERIES_HEAD.match(ln)
        ]

        # Post-run: a documented measure run makes an empty Result a MUST
        # gap — pilot suppression does not apply (write back, don't go quiet).
        measured = measure_runs(text)
        run_unreported = bool(measured) and bool(unreported(text))
        history = [
            (n, ln.strip())
            for n, ln in enumerate(text.splitlines(), 1)
            if CHANGELOG.search(ln)
        ]

        clean = not (
            missing_must
            or missing_should
            or holes
            or left
            or no_block
            or frozen_without_io
            or too_long
            or big
            or run_unreported
            or history
            or series
        )
        if clean:
            if pilot_note:
                print(f"{f}: OK — must fields filled; {pilot_note}")
            else:
                print(f"{f}: OK — all must and should fields filled")
            continue

        if pilot_note:
            print(f"{f}: {pilot_note}")
        for label in missing_must:
            print(f"{f}: MISSING (must): {label}")
        for label in missing_should:
            print(f"{f}: missing (should): {label}")
        for n, label in must_holes:
            print(f"{f}:{n}: PLACEHOLDER ONLY (must): {label}")
        for n, label in soft_holes:
            print(f"{f}:{n}: placeholder only: {label}")
        if left:
            print(f"{f}: {len(left)} line(s) still verbatim template text, e.g.:")
            for s in left[:3]:
                print(f"    {s[:88]}")
        if no_block:
            print(
                f"{f}: MISSING (must): mentions a prompt but contains no code "
                f"block — a verbatim prompt belongs in ``` ```, anything else "
                f"is a paraphrase."
            )
        if frozen_without_io:
            print(
                f"{f}: MISSING (must): `frozen = true`, but not a "
                f"single rendered example (code block). Instrument check "
                f"first, then freeze — otherwise the error freezes in."
            )
        if too_long:
            sev = "OVERSIZED (must)" if frozen else "oversized"
            print(
                f"{f}: {sev}: {n_lines} prose lines (tables/code excluded) "
                f"— a protocol is a registration, not a lab journal. "
                f"Narratives (freeze history, diagnoses) belong in commit "
                f"messages or a note; ONE sentence per freeze stays here."
            )
        for lb, n, lim in big:
            sev = "OVERSIZED (must)" if frozen else "oversized"
            print(
                f"{f}: {sev}: section '{lb}': {n} prose lines (budget "
                f"{lim}) — one field is one line; if a justification needs "
                f"more, it goes into a note and the [[wikilink]] stays "
                f"here."
            )
        if run_unreported:
            print(
                f"{f}:{measured[0][0]}: MISSING (must): measure run in the "
                f"run list ({measured[0][1]}) but Result/Raw output empty — "
                f"write the result back in the SAME session."
            )
        for n, ln in series:
            print(
                f"{f}:{n}: follow-up registration in the same protocol "
                f"({ln[:60]!r}) — one question per protocol: a declared "
                f"follow-up gets its own PROTOCOL-s<N>-<slug>.md "
                f"(series rule, Arbeitsstandard AS-061 Subexperiment-Serien tragen ihre Nummer im Namen)."
            )
        for n, ln in history:
            print(
                f"{f}:{n}: change history in the text ({ln[:60]!r}) — docs "
                f"carry the current state, the why of the change goes in the "
                f"commit message (AS-075 Docs tragen den Stand)."
            )
        # The must findings again, last: in a commit hook they sat among
        # 20 warning lines and were missed (usability probe 2026-10-07).
        musts = (
            list(missing_must)
            + [f"{label} (line {n}, placeholder)" for n, label in must_holes]
            + (["a prompt code block"] if no_block else [])
            + (["a rendered example (frozen)"] if frozen_without_io else [])
            + (["Result / Raw output for the measured run"] if run_unreported else [])
            + (["a shorter protocol (frozen)"] if frozen and (too_long or big) else [])
        )
        if musts:
            failed = True
            print(
                f"{f}: must fields missing or empty — fill them in, or "
                f"justify as 'n/a — <why>' (the reason must be there, not "
                f"just the angle brackets): {'; '.join(musts)}"
            )
    return 1 if failed else 0


def cli() -> None:
    """Entry point for the installed `protocol-check` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
