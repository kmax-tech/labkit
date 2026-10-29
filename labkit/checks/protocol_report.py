"""protocol_report — the report on one protocol file, and `protocol-check`.

`check_protocol` reads a protocol file and collects what the checks say
about it: the fields (`protocol_check.check_fields`), the runs it lists
and the ones it leaves unreported, section and prose budgets, the id
against the repo and git (`protocol_history`), a constant of the promise
block the prose never mentions. `print_report` tells it, `check_files`
walks files and directories, `main` is the console command
(`--contract` prints the field contract, `--guide` the field guide's
path). Read-only.

Usage:
    protocol-check PROTOCOL-foo.md [more files or directories ...]
    protocol-check --template experiment-protocol.md.template <files>

Directories are searched recursively for PROTOCOL-*.md. Exit code 1 if any
MUST field is missing or unfilled in any file; SHOULD fields only warn.
Protocols with a prose head (Standard 0.16/0.17) are read by labkit 0.47.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console, promises, protocol_block, standard_contract
from labkit.formats.repo import adopt_command, git_root, protocol_link, repo_protocols
from labkit.formats.findings import audit_record_gap
from labkit.formats.gate import BLOCKER, EXIT_CONTRACT, GateFinding
from labkit.formats.protocol_history import (
    check_annotation_validity,
    check_protocol_id,
    repeat_cost_lowered,
)
from labkit.formats.protocol_block import repo_protocol_ids
from labkit.formats.protocol_check import (
    BARE_REFERENCE,
    PROTOCOL_TEMPLATE,
    FIELDS,
    RUNS_PLACEHOLDER,
    DASHES_ONLY,
    HTML_COMMENT,
    STAMPED_ITEM,
    example_owed,
    field_label,
    kind_registers,
    model_named,
    owed_fields,
    recorded_results_without_run,
    check_fields,
    fields,
    result_due,
    written_before_run,
)


def unreported(text: str, head: protocol_block.Head) -> list[str]:
    """The result fields still missing, a placeholder or only dashes, of
    those HEAD's protocol owes after the run (`owed_fields`): a model-only
    field (`lm`, Raw output) only with a model named — a computation has no
    prompt+answer pair to show; at low repeat cost only the cut's fields (the
    Summary requires Conclusion, 2026-10-12)."""
    lines = fields(text)
    found = {f.name: f for f in lines}
    owed = [
        f
        for f in owed_fields(head.repeat_cost, head.kind, model_named(text))
        if f.level == "after"
    ]
    return [
        f.label.casefold()
        for f in owed
        if f.label.casefold() not in found
        or found[f.label.casefold()].placeholder
        or DASHES_ONLY.match(found[f.label.casefold()].value)
    ]


# A follow-up registration appended to the SAME protocol — the pattern that
# grew one file to 649 lines out of three experiments ("Lauf B — ...
# (deklariert vor dem Lauf)", "Stufe 2 ..."): each such heading is a second
# question in a one-question file. The series rule (LAB-061 Sub-experiment series carry their number in the name)
# gives every follow-up its own PROTOCOL-s<N>-<slug>.md. Warning only.
SERIES_HEAD = re.compile(
    r"(?im)^##.*\((deklariert|registriert) vor dem( jeweils \w+)? "
    r"(lauf|vote|pilot)|declared before the run\)?"
)


# The protocol run list is mandatory content (one entry per run_id), not
# prose: a long list must not consume the registration's prose budget.
PROTOCOL_RUN_LIST_HEAD = re.compile(r"(?i)^##\s.*(runs|l[\u00e4a]ufe)")


# Change-history prose — the doc should carry the current rule, the commit the
# change (LAB-075 Docs carry the state, commits the change). Warning only.
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


def prose_lines(text: str) -> list[tuple[str | None, str]]:
    """(the `## ` line of the current section or None, stripped line) for
    every PROSE line: code fences (rendered examples are the raw-output MUST)
    and table rows (confound profiles, error directions) are not prose.
    Section lines themselves are included. The one count behind the length
    check and the section budgets — raw-line counting had flagged three
    registration-dense protocols as journals, one of which never even ran
    (2026-08-25)."""
    out: list[tuple[str | None, str]] = []
    section: str | None = None
    lines = text.splitlines()
    fenced = protocol_block.fenced_lines(lines)
    starts = set(protocol_block.section_starts(lines))
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i in fenced or stripped.startswith("|"):
            continue
        if i in starts:
            section = stripped
        out.append((section, stripped))
    return out


def oversized_sections(text: str) -> list[tuple[str, int, int]]:
    """(label, prose lines, budget) for each section over budget; the
    section line itself does not count."""
    budget_of: dict[str, str | None] = {}
    counts: dict[str, int] = {}
    for section, stripped in prose_lines(text):
        if section is None or stripped == section:  # the heading line itself
            continue
        if section not in budget_of:
            head = section[3:].lower()
            budget_of[section] = next(
                (lb for lb, pat, _ in SECTION_BUDGET if re.search(pat, head)), None
            )
        label = budget_of[section]
        if label:
            counts[label] = counts.get(label, 0) + 1
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
    in_head = False  # `## Head`: the pointer and the toml block stay by design
    lines = path.read_text(encoding="utf-8").splitlines()
    starts = set(protocol_block.section_starts(lines))
    for i, line in enumerate(lines):
        # The written protocol carries no cut markers; compared with them,
        # the stamped Runs line `- <run_id> — <…> <!-- l -->` never matched
        # its leftover (uniagent area 08, 2026-10-07: frozen and reported).
        s = HTML_COMMENT.sub("", line).strip()
        if i in starts:
            in_body = True
            in_head = s.startswith("## Head")
        if in_head:
            continue
        # Only lines long enough to be distinctive; headings are meant to recur.
        if in_body and len(s) >= 40 and not s.startswith("#"):
            keep.add(s)
    return keep


def find_template(explicit: str | None) -> Path | None:
    """The protocol template to check against: the one named, else the packaged one."""
    if explicit:
        return Path(explicit)
    here = PROTOCOL_TEMPLATE
    return here if here.exists() else None


def find_field_guide() -> Path | None:
    """The packaged protocol field guide, or None outside the package."""
    here = PACKAGE_DIR / "docs" / "protocol-field-guide.md"
    return here if here.exists() else None


#: the tier table's rows `protocol-check --contract` prints without a
#: protocol: (repeat_cost, kind, model named)
COMMON_ROWS = (
    (standard_contract.LOW, standard_contract.COMPUTE_KIND, False),
    (standard_contract.LOW, standard_contract.FIT_KIND, False),
    (standard_contract.LOW, standard_contract.APPLY_KIND, True),
    (standard_contract.LOW, standard_contract.APPLY_KIND, False),
    (standard_contract.HIGH, standard_contract.COMPUTE_KIND, False),
    (standard_contract.HIGH, standard_contract.FIT_KIND, False),
    (standard_contract.HIGH, standard_contract.APPLY_KIND, True),
)


def low_cut_line() -> str:
    """The low cut in one sentence, its conditions spelled out — the first
    line of `protocol-check --contract` without a protocol."""
    return (
        'at repeat_cost = "low" (nothing freezes, no SHOULD) the protocol owes: '
        + ", ".join(
            f.label
            for f in FIELDS
            if f.low_cut == "l" and f.level in ("must", "should")
        )
        + "; with a bar (kind fit or apply) also the criterion, the admissibility "
        "condition, the null condition and Model / tool; with a `[model]` table also "
        + ", ".join(
            f.label
            for f in FIELDS
            if f.low_cut == "lm" and f.level in ("must", "should")
        )
        + "; after the run: "
        + ", ".join(f.label for f in FIELDS if f.low_cut == "l" and f.level == "after")
        + "; with a model also "
        + ", ".join(f.label for f in FIELDS if f.low_cut == "lm" and f.level == "after")
        + "."
    )


def full_form_lines() -> list[str]:
    """Every field of the full form by level, unfiltered by kind and model —
    the last lines of `protocol-check --contract` without a protocol."""
    out: list[str] = []
    for level, title in (
        ("must", "MUST (every pilot of the full form)"),
        ("should", "SHOULD (MUST once frozen = true)"),
        ("after", "after the run (owed once a result is declared)"),
        ("report", "report (owed once frozen = true and a result is declared)"),
    ):
        out += ["", f"  {title}"] + [
            f"    {f.label}" for f in FIELDS if f.level == level
        ]
    return out


@dataclass(frozen=True)
class OwedFields:
    """The field labels one protocol owes, by occasion — `owed_fields` split
    by `Field.level` and the lane — and whether the freeze owes it a
    rendered example (`example_owed`).

    Attributes:
        low: The low cut: nothing freezes, what it marks is owed now.
        now: Owed at every commit (protocol-check's must).
        once_frozen: Owed on top once `frozen = true` (the shoulds).
        after_run: Owed once the head declares a result (`[result] run`).
        once_reported: Owed once frozen and a result is declared.
        example: `frozen = true` owes a fenced block besides the TOML head.
    """

    low: bool
    now: list[str]
    once_frozen: list[str]
    after_run: list[str]
    once_reported: list[str]
    example: bool


def owed_by_occasion(head: protocol_block.Head, model: bool) -> OwedFields:
    """What a protocol of HEAD, a model named or not (MODEL), owes by
    occasion — the fields protocol-check holds it to."""
    owed_here = owed_fields(head.repeat_cost, head.kind, model)
    low = standard_contract.lane(head.repeat_cost).cut == standard_contract.LOW_CUT

    def labels(level: str) -> list[str]:
        return [f.label for f in owed_here if f.level == level]

    return OwedFields(
        low=low,
        now=labels("must") + (labels("should") if low else []),
        once_frozen=[] if low else labels("should"),
        after_run=labels("after"),
        once_reported=labels("report"),
        example=example_owed(head.repeat_cost, head.kind, model),
    )


#: the rendered example as `protocol-check PROTOCOL --contract` names it
RENDERED_EXAMPLE = (
    "a rendered example (a fenced block besides the TOML head: the instrument "
    "check's real input and its output, LAB-014 One fully rendered example "
    "pair per gold class; `n/a` does not stand in for it)"
)

#: the promise sentences as `protocol-check PROTOCOL --contract` names them:
#: owed once frozen where the kind registers (`protocol_check.kind_registers`)
PROMISE_SENTENCES = (
    "one explicit sentence per [[promise]] table (the stamp's `<…>` sentence "
    'registers nothing; `protocol-fill PROTOCOL "<id> sentence=<the promise>"` '
    "writes one)"
)


def owed_field_lines(
    name: str, head: protocol_block.Head, model: bool, *, registers: bool
) -> list[str]:
    """What protocol NAME owes field by field (`owed_by_occasion`), one line
    per occasion — what `protocol-check NAME --contract` prints first. The
    freeze line also names the rendered example where the freeze owes one
    and the promise sentences where the kind REGISTERS
    (`protocol_check.kind_registers`) — the two things the freeze refuses
    besides the fields; at low repeat cost, where every run is the full
    run, the sentences are owed now. An occasion that owes nothing is left
    out."""
    owed_here = owed_by_occasion(head, model)
    occasions = (
        (
            "now — protocol-check refuses the commit without them"
            + (" (nothing freezes at low repeat cost)" if owed_here.low else ""),
            owed_here.now
            + ([PROMISE_SENTENCES] if registers and owed_here.low else []),
        ),
        (
            "once frozen = true also (the † ones come with "
            "`labkit-init exp <name> --report`)",
            owed_here.once_frozen
            + ([RENDERED_EXAMPLE] if owed_here.example else [])
            + ([PROMISE_SENTENCES] if registers and not owed_here.low else []),
        ),
        (
            "after the run, once the head declares a result (`[result] run`)",
            owed_here.after_run,
        ),
        (
            "once frozen = true and a result is declared also",
            owed_here.once_reported,
        ),
    )
    return [
        f"the fields {name} owes — its repeat_cost, kind"
        + ("" if head.kind else " (undecided: the most a kind owes)")
        + " and model, the ones protocol-check holds it to:"
    ] + [f"  {when}: {', '.join(what)}" for when, what in occasions if what]


def print_contract(protocol: Path | None = None) -> None:
    """The checker's contract in one screen (2026-10-05: two cold agents
    learnt the budgets from the pre-commit hook and the field words from
    the checker's source, four rewrite rounds each). The fields owed and
    the fill command come first: last, five of six agents found the low cut
    only after reading the whole list, and none found protocol-fill
    (2026-10-07). With PROTOCOL, the fields that protocol owes by occasion
    (`owed_field_lines`) and the tier table's one row of its repeat_cost,
    kind (the most a kind owes while undecided) and model (`model_named`);
    else the low cut, the common rows and the full form's field lists.
    Raises OSError, UnicodeError or protocol_block.BlockError when PROTOCOL
    does not read."""
    if protocol is not None:
        text = protocol.read_text(encoding="utf-8")
        head = protocol_block.head(text)
        model = model_named(text)
        top = owed_field_lines(
            protocol.name, head, model, registers=kind_registers(head.kind, text)
        )
        rows_title = (
            f"what {protocol.name} owes, by occasion — its repeat_cost, kind"
            + ("" if head.kind else " (undecided: the most a kind owes)")
            + " and model, from the one table every gate reads (standard_contract):"
        )
        rows = [(head.repeat_cost, head.kind or standard_contract.APPLY_KIND, model)]
        fields_where = (
            f" The fields {protocol.name} owes stand in the first lines of this output."
        )
        tail: list[str] = []
    else:
        top = [low_cut_line()]
        rows_title = (
            "what each tier owes, by occasion — the one table every gate reads "
            "(standard_contract); `protocol-check PROTOCOL --contract` prints "
            "one protocol's row:"
        )
        rows = list(COMMON_ROWS)
        fields_where = (
            ' The lists below are the FULL form (repeat_cost = "high"); at '
            'repeat_cost = "low" only the first line of this output counts:'
        )
        tail = full_form_lines()
    for line in top:
        print(line)
    print(
        "fill a field by its label, multi-line placeholders included: "
        'protocol-fill PROTOCOL-x.md "<Label>=<value>" ["<Label>=<value>" …]; what is still open: '
        "protocol-fill PROTOCOL-x.md --list; the Prompt block from the scripts' "
        "PROMPT constants: protocol-fill PROTOCOL-x.md --prompts\n"
    )
    print(rows_title)
    for repeat_cost, kind, with_model in rows:
        first, *rest = standard_contract.describe(repeat_cost, kind, with_model)
        print(f"  {first}")
        for line in rest:
            print(f"    {line}")
    print()
    print(
        "head: the ```toml block's [protocol] table — "
        + ", ".join(protocol_block.PROTOCOL_HEAD_KEYS)
        + f"; standard = {protocol_block.STANDARD!r}, type one of "
        + ", ".join(protocol_block.TYPES)
        + ", repeat_cost one of "
        + ", ".join(protocol_block.REPEAT_COSTS)
        + ", kind one of "
        + ", ".join(protocol_block.KINDS)
        + " (what the kept number asserts: a computation judges no prediction, a fit "
        "judges a model trained or adjusted here, an apply a model used unchanged)."
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
        + fields_where
    )
    for line in tail:
        print(line)


def code_blocks(text: str) -> int:
    """Top-level fenced blocks other than the TOML head — the rendered examples."""
    return sum(1 for info, _ in protocol_block.fenced_blocks(text) if info != "toml")


def collect_protocols(paths: list[str]) -> list[Path]:
    """The protocol files the arguments name: every `PROTOCOL-*.md` under a directory, or the files given."""
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(repo_protocols(p))
        else:
            files.append(p)
    return files


#: prose lines a whole protocol may hold (tables and code excluded). By
#: 2026-08-20 one had grown to 646 lines because every re-freeze APPENDED its
#: narrative instead of replacing it — presence was checked, length never.
#: The condensed version of that same protocol (all fields, all numbers, four
#: code blocks) has 296 lines; 350 leaves room.
PROSE_LINE_BUDGET = 350


@dataclass(frozen=True)
class FileReport:
    """Everything `protocol-check` decides about one protocol, as data.
    `head_error` set means the head could not be read — nothing else is
    filled. `print_report` is the one rendering; `blocks` the exit code's
    half. Held as locals of `main`, the findings existed only as printed
    text and every test read them back from stdout (audit 2026-10-13)."""

    path: Path
    head_error: str | None
    frozen: bool = False
    audit_drift: str | None = None
    id_findings: list[GateFinding] = field(default_factory=list)
    repeat_cost_lowered: str | None = (
        None  # a WARNING: the tier sank since the first commit
    )
    answer_unbound: str | None = None  # a WARNING: an Recorded results without a run_id
    pilot_note: str = ""
    missing_must: list[str] = field(default_factory=list)
    #: owed should-fields; unfrozen they fold into the pilot note, frozen
    #: or at low repeat cost `owed()` has made them must — kept as data, never printed
    missing_should: list[str] = field(default_factory=list)
    must_holes: list[tuple[int, str]] = field(default_factory=list)
    soft_holes: list[tuple[int, str]] = field(default_factory=list)
    left: list[str] = field(default_factory=list)
    runs_stamped: bool = False
    no_block: bool = False
    #: frozen without a rendered example where one is owed (`example_owed`)
    frozen_without_io: bool = False
    n_lines: int = 0
    big: list[tuple[str, int, int]] = field(default_factory=list)
    series: list[tuple[int, str]] = field(default_factory=list)
    declared: str | None = None  # the run the head declares, when it does
    run_unreported: list[str] = field(default_factory=list)
    history: list[tuple[int, str]] = field(default_factory=list)
    bare_refs: list[tuple[int, str]] = field(default_factory=list)
    #: report fields filled before any completed run is bound (warning)
    before_run: list[tuple[int, str]] = field(default_factory=list)
    #: registered constants no sentence names and no scope file reads (warning)
    unmentioned_constants: list[str] = field(default_factory=list)

    @property
    def too_long(self) -> bool:
        """Over the whole-protocol prose budget."""
        return self.n_lines > PROSE_LINE_BUDGET

    @property
    def clean(self) -> bool:
        """No finding at all — what lets `print_report` say OK. The pilot note
        and the Runs hint are notes, not findings. Every finding counts,
        also those printed above the OK line (a doubled id stood above "OK
        — must fields filled", review 2026-10-20)."""
        return not (
            self.audit_drift
            or self.id_findings
            or self.repeat_cost_lowered
            or self.answer_unbound
            or self.bare_refs
            or self.missing_must
            or self.missing_should
            or self.must_holes
            or self.soft_holes
            or self.left
            or self.no_block
            or self.frozen_without_io
            or self.too_long
            or self.big
            or self.run_unreported
            or self.history
            or self.series
            or self.before_run
            or self.unmentioned_constants
        )

    @property
    def musts(self) -> list[str]:
        """The must findings in one list — repeated last in the report: in a
        commit hook they sat among 20 warning lines and were missed
        (usability probe 2026-10-07)."""
        return (
            list(self.missing_must)
            + [f"{label} (line {n}, placeholder)" for n, label in self.must_holes]
            + (["a prompt code block"] if self.no_block else [])
            + (["a rendered example (frozen)"] if self.frozen_without_io else [])
            + [f"{field_label(n)} (a result is declared)" for n in self.run_unreported]
            + (
                ["a shorter protocol (frozen)"]
                if self.frozen and (self.too_long or self.big)
                else []
            )
        )

    @property
    def blocks(self) -> bool:
        """Whether this protocol fails the check (exit 1)."""
        return bool(
            self.head_error
            or self.musts
            or any(f.grade == BLOCKER for f in self.id_findings)
        )


def constants_unmentioned(area: Path, text: str) -> list[str]:
    """`promises.unmentioned_constants` over the protocol's block, as the
    warning lines of this check; a block or scope that cannot be read is
    said, not skipped (the tables gap and the stamp name the cause)."""
    try:
        block = promises.parse_block(text)
        return promises.unmentioned_constants(block, area) if block else []
    except promises.PromiseError as exc:
        return [f"constants not held to sentence and scope: {exc}"]


def check_protocol(
    path: Path, text: str, tmpl: set[str], ids: dict[str, list[Path]]
) -> FileReport:
    """Every finding of `protocol-check` on one protocol, against the
    template's instruction lines `tmpl` (`template_lines`) and the repo's
    protocol ids `ids` (`repo_protocol_ids`)."""
    report = check_fields(text)
    if report.head is None:
        return FileReport(path, report.head_error)
    head, frozen = report.head, report.frozen
    lane = standard_contract.lane(head.repeat_cost)
    audit_drift = None
    if frozen and lane.freeze and head.preflight_audit:
        # a warning: after the run, analysis scripts change legitimately;
        # `n/a` at high repeat cost waives an audit nobody may waive (0.99.0)
        audit_drift = audit_record_gap(path.parent, head.preflight_audit, text)
    field_lines = fields(text)
    missing_should = report.missing_should
    pilot_note = ""
    if not frozen and missing_should:
        pilot_note = (
            f"pilot (frozen = false) — {len(missing_should)} "
            f"should-field(s) due only at report time "
            f"({', '.join(missing_should)}; append them: labkit-init exp <name> --report)"
        )
        missing_should = []
    # A placeholder is reported as one already, and a comment can never
    # be "filled" — neither is left-over template text (review 2026-10-07:
    # a correctly filled protocol at low repeat cost was never clean).
    in_placeholder = {
        n for f in field_lines if f.placeholder for n in range(f.line, f.last + 1)
    }
    left = sorted(
        {
            s
            for n, s in enumerate((ln.strip() for ln in text.splitlines()), 1)
            if (s in tmpl or STAMPED_ITEM.fullmatch(s))
            and not s.startswith("<!--")
            and n not in in_placeholder
        }
    )
    # Before the run the Runs entry is stamped by design: --from-run writes
    # it. Counted as a leftover, it made every registration read as
    # unfinished and two cold agents stopped to see whether it blocks
    # (Haiku H6, H7, 2026-10-13). Frozen, the stamped entry is the scar of
    # uniagent area 08 and stays a leftover.
    runs_stamped = not frozen and any(RUNS_PLACEHOLDER.match(s) for s in left)
    if runs_stamped:
        left = [s for s in left if not RUNS_PLACEHOLDER.match(s)]
    examples = code_blocks(text)
    # "mentions a prompt" means a Prompt FIELD, not the word: the stamped
    # legend says "prompt" in every protocol, and a count protocol cut
    # without the field was blocked for it (2026-10-05).
    no_block = not examples and any(
        f.name == "prompt" and not f.value.lower().startswith("n/a")
        for f in field_lines
    )
    # A protocol is a registration, not a lab journal: only prose counts,
    # and the protocol run list is not the registration.
    n_lines = sum(
        1
        for section, _ in prose_lines(text)
        if not (section and PROTOCOL_RUN_LIST_HEAD.match(section))
    )
    numbered = list(enumerate((ln.strip() for ln in text.splitlines()), 1))
    # Post-run: a declared result makes an empty result field a MUST gap —
    # pilot suppression does not apply (write back, don't go quiet).
    declared = result_due(text)
    return FileReport(
        path=path,
        head_error=None,
        frozen=frozen,
        audit_drift=audit_drift,
        id_findings=check_protocol_id(path, head, ids)
        + check_annotation_validity(path, text, ids),
        repeat_cost_lowered=repeat_cost_lowered(path, head),
        answer_unbound=recorded_results_without_run(text),
        pilot_note=pilot_note,
        missing_must=report.missing_must,
        missing_should=missing_should,
        must_holes=report.must_holes,
        soft_holes=report.soft_holes,
        left=left,
        runs_stamped=runs_stamped,
        no_block=no_block,
        frozen_without_io=frozen
        and not examples
        and example_owed(head.repeat_cost, head.kind, model_named(text)),
        n_lines=n_lines,
        big=oversized_sections(text),
        series=[(n, s) for n, s in numbered if SERIES_HEAD.match(s)],
        declared=declared,
        run_unreported=unreported(text, head) if declared else [],
        history=[(n, s) for n, s in numbered if CHANGELOG.search(s)],
        bare_refs=[
            (fl.line, fl.label)
            for fl in field_lines
            if BARE_REFERENCE.search(fl.value) and "](" not in fl.value
        ],
        before_run=written_before_run(path.parent, text, head),
        unmentioned_constants=constants_unmentioned(path.parent, text),
    )


def print_report(r: FileReport) -> None:  # noqa: C901 one print per finding, in report order (2026-10-13)
    """The report as `protocol-check` prints it: one line per finding, the
    must findings repeated last."""
    f = r.path
    if r.head_error is not None:
        print(f"{f}: HEAD (must): {r.head_error}")
        return
    if r.audit_drift:
        print(f"{f}: WARNING: preflight_audit: {r.audit_drift}")
    for finding in r.id_findings:
        print(finding.line)
    if r.repeat_cost_lowered:
        print(r.repeat_cost_lowered)
    if r.answer_unbound:
        print(f"{f}: {r.answer_unbound}")
    if r.runs_stamped:
        print(
            f"{f}: Runs: the stamped entry is written by "
            f"`{adopt_command(f)}` after the run"
        )
    if r.clean:
        if r.pilot_note:
            print(f"{f}: OK — must fields filled; {r.pilot_note}")
        else:
            print(f"{f}: OK — all must and should fields filled")
        return
    if r.pilot_note:
        print(f"{f}: {r.pilot_note}")
    for label in r.missing_must:
        print(f"{f}: MISSING (must): {label}")
    # no `missing (should)` lines: unfrozen they are named in the pilot
    # note above, frozen or at low repeat cost `owed()` makes them MUST (2026-10-09)
    for n, label in r.must_holes:
        print(f"{f}:{n}: PLACEHOLDER ONLY (must): {label}")
    for n, label in r.soft_holes:
        print(f"{f}:{n}: placeholder only: {label}")
    if r.left:
        print(f"{f}: {len(r.left)} line(s) still verbatim template text, e.g.:")
        for s in r.left[:3]:
            print(f"    {s[:88]}")
    if r.no_block:
        print(
            f"{f}: MISSING (must): mentions a prompt but contains no code "
            f"block — a verbatim prompt belongs in ``` ```, anything else "
            f"is a paraphrase."
        )
    if r.frozen_without_io:
        print(
            f"{f}: MISSING (must): `frozen = true`, but not a "
            f"single rendered example (code block). Instrument check "
            f"first, then freeze — otherwise the error freezes in."
        )
    sev = "OVERSIZED (must)" if r.frozen else "oversized"
    if r.too_long:
        print(
            f"{f}: {sev}: {r.n_lines} prose lines (tables/code excluded) "
            f"— a protocol is a registration, not a lab journal. "
            f"Narratives (freeze history, diagnoses) belong in commit "
            f"messages or a note; ONE sentence per freeze stays here."
        )
    for lb, n, lim in r.big:
        print(
            f"{f}: {sev}: section '{lb}': {n} prose lines (budget "
            f"{lim}) — one field is one line; if a justification needs "
            f"more, it goes into a note and the [[wikilink]] stays "
            f"here."
        )
    if r.run_unreported:
        print(
            f"{f}: MISSING (must): the head declares run {r.declared} but "
            f"{', '.join(field_label(n) for n in r.run_unreported)} empty — write "
            f"the result in the SAME session: `protocol-fill --render` for the "
            f"Recorded results; Conclusion (the question's answer in two sentences, within the "
            f"Limits) and Raw output are yours."
        )
    for n, ln in r.series:
        print(
            f"{f}:{n}: follow-up registration in the same protocol "
            f"({ln[:60]!r}) — one question per protocol: a declared "
            f"follow-up gets its own PROTOCOL-s<N>-<slug>.md "
            f"(series rule, LAB-061 Sub-experiment series carry their number in the name)."
        )
    for n, label in r.bare_refs:
        print(
            f"{f}:{n}: reference without a link: {label} — give the link "
            f"([area NN](../NN-<name>/PROTOCOL-<name>.md)) and the sentence "
            f"that matters here"
        )
    for n, label in r.before_run:
        print(
            f"{f}:{n}: WARNING: {label} written before any run — no completed "
            f"run is bound to this protocol and the head declares no `[result] run`; "
            f"a report field describes a run that happened (write it with "
            f"`{adopt_command(f)}` after the run)"
        )
    for line in r.unmentioned_constants:
        print(f"{f}: WARNING: {line}")
    for n, ln in r.history:
        print(
            f"{f}:{n}: change history in the text ({ln[:60]!r}) — docs "
            f"carry the current state, the why of the change goes in the "
            f"commit message (LAB-075 Docs carry the state, commits the change)."
        )
    if r.musts:
        print(
            f"{f}: must fields missing or empty — fill them in, or "
            f"justify as 'n/a — <why>' (the reason must be there, not "
            f"just the angle brackets): {'; '.join(r.musts)}"
        )


def check_files(files: list[Path], tmpl: set[str]) -> bool:
    """Check and print every protocol in FILES; True when any blocks, a
    symbolic link among them too (`repo.protocol_link`). The repo's
    protocol ids are read once per repo for this call."""
    ids_by_root: dict[Path | None, dict[str, list[Path]]] = {}
    failed = False
    for f in files:
        if f.is_symlink():
            print(protocol_link(f, "tree"))
            failed = True
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{f}: not readable ({exc})")
            failed = True
            continue
        root = git_root(f)
        if root not in ids_by_root:
            ids_by_root[root] = repo_protocol_ids(f)
        report = check_protocol(f, text, tmpl, ids_by_root[root])
        print_report(report)
        failed = failed or report.blocks
    return failed


def _contract(named: list[str]) -> int:
    """`--contract` with NAMED, at most one protocol: its row, or every
    common row without one (`print_contract`); exit 2 when it does not
    read."""
    if len(named) > 1:
        console.refuse("protocol-check", "--contract takes at most one protocol")
        return 2
    try:
        print_contract(Path(named[0]) if named else None)
    except (OSError, UnicodeError, protocol_block.BlockError) as exc:
        console.refuse("protocol-check", f"{' '.join(named)}: {exc}")
        return 2
    return 0


def main(argv: list[str]) -> int:
    """Command line of `protocol-check`: check protocols against the template and their own head."""
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
            "it recognises — read it BEFORE writing, not from the pre-commit hook; "
            "with one PROTOCOL, what its repeat cost, kind and model owe"
        )
        print(EXIT_CONTRACT)
        return 0
    # `protocol-check PROTOCOL --contract` read the flag as a file name
    # ("not readable: '--contract'", 2026-10-13): a flag is a flag anywhere.
    if "--contract" in argv:
        return _contract([a for a in argv if a != "--contract"])
    if "--guide" in argv:
        fg = find_field_guide()
        print(fg or "field guide not found")
        return 0 if fg else 1
    tmpl_arg = None
    if argv and argv[0] == "--template":
        if len(argv) < 2:
            console.refuse("protocol-check", "--template needs a path")
            return 2
        tmpl_arg, argv = argv[1], argv[2:]
    if not argv:
        console.refuse(
            "protocol-check",
            "no protocol named\nusage: protocol-check [--template PATH] <PROTOCOL-*.md | dir> ...",
        )
        return 2
    files = collect_protocols(argv)
    if not files:
        console.refuse("protocol-check", "no PROTOCOL-*.md found")
        return 2

    tmpl = template_lines(find_template(tmpl_arg))
    return 1 if check_files(files, tmpl) else 0


def cli() -> None:
    """Entry point for the installed `protocol-check` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
