"""standard_contract — what the lab standard demands, of which run, at which occasion.

The one home of the obligations the standard puts on a number: what a
protocol owes before the run, what a full run owes at its start, what
finalize checks after it, what the release demands when the number is
written back — and which artefacts the skeleton stamps so those checks have
something to hold. Every consumer asks here; none decides for itself.
Until this module existed each component spelled the rule it needed
(`head.repeat_cost == "low"` in seven modules, the registration's labels in
one, the check's script name in two), and the audit of 2026-10-19 found
them disagreeing: the gate demanded a script the skeleton never stamped.

What stands here is doctrine (docs/architecture.md, "Core and doctrine"):
another lab could set the tiers differently without being less scientific.
It belongs to the pinned labkit, not to a configuration file per experiment:
the standard is versioned with the package, and the experiment supplies its
facts — the head's repeat cost, whether a model is named, whether the run
declared itself a full run.

This module reads no file, runs nothing and writes nothing. It takes facts
a caller already holds and answers what is owed; reading the protocol, the
run record or the audit records stays with their homes
(`protocol_block.head`, `runs.read_run_config`, `findings.area_records`),
and the checks themselves stay with their modules — the contract says WHEN
each is due, not HOW it is made.

Rules of the lab standard the table states: LAB-017 The number of audits
follows the cost tier (the tiers), LAB-003 No run without an intent
paragraph (the registration), LAB-015 Preflight audit before freezing and
LAB-050 Analysis audit before reporting (the audits),
LAB-041 Generate numbers, don't retype them (the check).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labkit.formats.protocol_block import REPEAT_COSTS, KINDS

LOW, HIGH = REPEAT_COSTS
COMPUTE_KIND, FIT_KIND, APPLY_KIND = KINDS

#: the agent audits, by the mode `labkit-audit` and `findings` name them
PREFLIGHT_AUDIT = "preflight"
ANALYSIS_AUDIT = "analysis"

#: the two forms of a protocol: the low cut (the fields marked in the
#: template) and the full form (every must; every should once frozen; the
#: report fields once a result is declared) — `protocol_check.owed` reads it
LOW_CUT = "low"
FULL_FORM = "full"


def effective_repeat_cost(declared: str | None) -> str:
    """The repeat cost a head's `repeat_cost` stands for: DECLARED itself, or `high` while
    it is unfilled — an undeclared tier owes the most, never the least
    (preflight read it so since 2026-10-05)."""
    if declared is None:
        return HIGH
    if declared not in REPEAT_COSTS:
        raise ValueError(
            f"repeat_cost {declared!r} is not one of {', '.join(REPEAT_COSTS)}"
        )
    return declared


@dataclass(frozen=True)
class Lane:
    """What one repeat cost owes, as the standard's table states it
    (LAB-017 The number of audits follows the cost tier): the lane
    `AGENTS.md` walks an agent along. One row per decision the components used to make on
    their own; a consumer reads the field it needs and copies no rule.

    Attributes:
        repeat_cost: `low` or `high` (an unfilled repeat cost reads as high) — the record's `repeat_cost`.
        freeze: A full run owes `frozen = true` and the preflight audit line
            in the head — the preflight audit comes with the freeze
            (LAB-015 Preflight audit before freezing). At low repeat cost nothing
            freezes: a rerun costs nothing, so the freeze protects nothing.
        registration: A full run owes the written registration instead of
            the freeze — the question; for a number that judges a
            prediction (`kind` fit or apply) also the criterion, the
            admissibility condition and the null condition; with a model
            also the data profile (`registration_fields`); and the repeat_cost
            declared (LAB-003 No run without an intent paragraph).
            runlog reads it off the tree at the start; the release holds
            it to the commit of the first measurement
            (`report_check.registration_gaps`): what stood before the
            number is what that commit holds.
        audits: The agent audits the number owes, by mode: the analysis
            audit at every tier, when the number is written back
            (LAB-050 Analysis audit before reporting); the preflight audit
            only where the freeze is owed.
        analysis_rule: The rule a gate cites when the analysis audit is
            missing: at low repeat cost the one audit of the lane, owed at the
            promotion of the number (LAB-017 The number of audits follows
            the cost tier); elsewhere LAB-050 Analysis audit before
            reporting.
        cut: Which fields the protocol owes — the low cut or the full
            form (`protocol_check.FIELDS` carries the marks).
        probe_allowed: A separate instrument probe may precede the measurement.
            False at low repeat cost: repeat the full measurement to check the instrument.
        foreground: A full run may start in an agent's foreground shell:
            it ends within the harness's limit. Elsewhere the detach gate
            refuses it (`runlog.Run`, scar 2026-08-13).
        provenance: `finalize` holds the run's source frozen in the record
            and source and output tracked in git — at low repeat cost the machine
            checks what the audit would otherwise ask every time
            (LAB-017 The number of audits follows the cost tier).
    """

    repeat_cost: str
    freeze: bool
    registration: bool
    audits: tuple[str, ...]
    analysis_rule: str
    cut: str
    probe_allowed: bool
    foreground: bool
    provenance: bool


LOW_LANE = Lane(
    repeat_cost=LOW,
    freeze=False,
    registration=True,
    audits=(ANALYSIS_AUDIT,),
    analysis_rule="LAB-017 The number of audits follows the cost tier",
    cut=LOW_CUT,
    probe_allowed=False,
    foreground=True,
    provenance=True,
)


def lane(repeat_cost: str | None) -> Lane:
    """The lane of a head's `repeat_cost` — the one answer to "what does this tier
    owe", where every consumer read `repeat_cost == "low"` for itself."""
    t = effective_repeat_cost(repeat_cost)
    if t == LOW:
        return LOW_LANE
    return Lane(
        repeat_cost=t,
        freeze=True,
        registration=False,
        audits=(PREFLIGHT_AUDIT, ANALYSIS_AUDIT),
        analysis_rule="LAB-050 Analysis audit before reporting",
        cut=FULL_FORM,
        probe_allowed=True,
        foreground=False,
        provenance=False,
    )


#: the fields a full run at low repeat cost owes written (not a placeholder) before
#: it starts, by what the kept number asserts (`protocol_block.KINDS`): a
#: computation registers its question — it judges no prediction, so it has no bar
#: to clear (0.87.1); a fit or an apply registers the bar (criterion), what
#: must hold before it is read (admissibility) and what it is held against
#: (the null condition or anchors, computed in the same run); with a model
#: answering through `models.toml` also the judged data profile — read
#: before the model is asked, or a cue in the data answers in its place
#: (LAB-003 No run without an intent paragraph; review 2026-10-21; writing
#: probe 2026-10-22, `docs/notes/2026-10-22-kind-writing-probe.md`). The
#: labels are the template's, held to `protocol_check.FIELDS` by a test.
REGISTRATION_FIELDS = ("Question / hypothesis",)
REGISTRATION_FIELDS_WITH_BAR = (
    "Success / failure criterion",
    "Admissibility condition",
    "Null condition / anchors",
)
REGISTRATION_FIELDS_WITH_MODEL = ("Data profile",)


def has_bar(kind: str) -> bool:
    """Does a number of KIND judge a prediction — so a trivial instrument
    could pass, and a bar is owed? Raises ValueError for a kind the head
    cannot carry: nothing falls back to a computation."""
    if kind not in KINDS:
        raise ValueError(f"kind {kind!r} is not one of {', '.join(KINDS)}")
    return kind != COMPUTE_KIND


def registration_fields(kind: str, model: bool) -> tuple[str, ...]:
    """The labels the registration owes written for a number of KIND, with
    or without a model answering through `models.toml`."""
    return (
        REGISTRATION_FIELDS
        + (REGISTRATION_FIELDS_WITH_BAR if has_bar(kind) else ())
        + (REGISTRATION_FIELDS_WITH_MODEL if model else ())
    )


#: the one public recheck of every area, relative to the area: the analysis
#: script's `--check` pins the output to the run, recomputes the metrics
#: and holds the note to them (`recheck.holds`; LAB-041 Generate numbers,
#: don't retype them). Every skeleton stamps it (`Skeleton.scripts`), and
#: report-check runs it for recomputation — the counting skeleton carried its
#: check inside `01_measure.py` until 0.99.0 and the gate asked for a file
#: the skeleton never wrote (audit 2026-10-19).
CHECK_SCRIPT = Path("scripts") / "02_analyze.py"
CHECK_FLAG = "--check"


def check_command(area: Path) -> list[str]:
    """The recheck of AREA as a command line, without its interpreter (the
    caller picks the repo's own, `preflight.area_test_python`)."""
    return [str(area / CHECK_SCRIPT), CHECK_FLAG]


@dataclass(frozen=True)
class Skeleton:
    """What `labkit-init exp` stamps for one instrument, and what the stamped
    area then has: the script skeletons (template, destination under
    `scripts/`), the area's test template, and whether a `--probe` stage
    comes before the run. Every skeleton stamps `CHECK_SCRIPT`, so the
    release's check (`check_command`) is one command for every area.

    Attributes:
        instrument: `compute`, `estimator` or `model` — the three instruments
            (README, Terms).
        scripts: (template name, destination under scripts/), in order.
        test: The template of `tests/test_<NN>_<name>.py`.
        probe: The skeleton has a throwaway instrument check (`--probe`).
            The compute skeleton has none: its run is the instrument check. Whether
            the probe precedes a run is the lane's answer too — at low repeat cost
            a separate probe is not allowed (`Lane.probe_allowed`).
    """

    instrument: str
    scripts: tuple[tuple[str, str], ...]
    test: str
    probe: bool
    # the metrics.json key the measure script keeps [C1]'s number under
    # (its `C1_VALUE_KEY`); None for the compute skeleton, which has no
    # criterion. One home for the probes, which named it by hand and scored
    # three draws "absent" (2026-10-28); tests hold each template to it
    criterion_key: str | None = None


COMPUTE = Skeleton(
    instrument="compute",
    scripts=(
        ("measure-quick-script.py.template", "01_measure.py"),
        ("analyze-quick-script.py.template", "02_analyze.py"),
    ),
    test="test-quick.py.template",
    probe=False,
)
ESTIMATOR = Skeleton(
    instrument="estimator",
    scripts=(
        ("prepare-estimator-script.py.template", "00_prepare.py"),
        ("measure-estimator-script.py.template", "01_measure.py"),
        ("analyze-script.py.template", "02_analyze.py"),
    ),
    test="test-estimator.py.template",
    probe=True,
    criterion_key="c1_score",
)
MODEL = Skeleton(
    instrument="model",
    scripts=(
        ("prepare-script.py.template", "00_prepare.py"),
        ("measure-script.py.template", "01_measure.py"),
        ("analyze-script.py.template", "02_analyze.py"),
    ),
    test="test-area.py.template",
    probe=True,
    criterion_key="c1_accuracy",
)
SKELETONS = (COMPUTE, ESTIMATOR, MODEL)

#: The stamped scripts' stages that open no run: each script's usage says
#: so ("no write", "no fit", "throwaway output", "No run, nothing
#: written"). The prompt skeleton's are `lanes.Lanes`'s, the estimator's
#: and the producers' their templates'. The pre-run hook lets a command
#: carrying one pass (`claude_hooks.THROWAWAY_FLAGS`); a test holds every
#: flag those scripts define to this list or to the run's own flags.
NO_RUN_FLAGS = (
    "--show",
    "--probe",
    "--eval-only",
    "--audit",
    "--calibrate-null",
    "--write",
)


def criterion_key(sk: Skeleton) -> str:
    """The key SK's measure script keeps [C1]'s number under
    (`Skeleton.criterion_key`). Raises ValueError for a skeleton without a
    criterion: a computation keeps its own keys."""
    if sk.criterion_key is None:
        raise ValueError(f"the {sk.instrument} skeleton keeps no criterion key")
    return sk.criterion_key


def skeleton(repeat_cost: str | None, kind: str, model: bool) -> Skeleton:
    """The skeleton an area gets, by what its number asserts: a computation
    the compute skeleton at every tier (it has no bar); a fit the estimator
    (nine of nine pilot attempts were classical ML, labkit-paper area 09,
    2026-10-16 — at low repeat cost too since 0.104: a RandomForest at low repeat cost got
    the count's skeleton and no criterion, fifth haiku round); an apply the
    prompt skeleton when a model answers through `models.toml`, else the
    estimator template's apply path (the unchanged predictor, never
    fitted; its null lane scores the same predictions against labels
    permuted with the seed). The fit path alone trains estimators, its
    null lane fitted on permuted labels.
    COST decides nothing here any more; the lane still decides the cut and
    whether a probe may precede the run. Raises ValueError for a kind the
    head cannot carry."""
    if not has_bar(kind):
        return COMPUTE
    if kind == APPLY_KIND and model:
        return MODEL
    return ESTIMATOR


def describe(repeat_cost: str | None, kind: str, model: bool) -> list[str]:
    """The contract of one tier and kind in sentences, by occasion — what
    `protocol-check --contract` prints, so an agent reads the obligations
    where it reads the fields, instead of learning them from a refusal."""
    ln, sk = lane(repeat_cost), skeleton(repeat_cost, kind, model)
    check = " ".join((CHECK_SCRIPT.as_posix(), CHECK_FLAG))
    before = (
        "the registration written and committed (the first measurement is held "
        "to what its commit holds): "
        + ", ".join(registration_fields(kind, model))
        # runlog checks these; the pre-commit hook every must field of the
        # cut, so the commit holds all of them (Haiku start reading
        # 2026-10-28: three of three asked which list applies)
        + " — runlog checks these; the pre-commit hook holds every field the "
        "low cut owes (the first lines above name them), so the commit carries "
        "all of them"
        if ln.registration
        else "`preflight` clean, the preflight audit decided and its record named "
        "in the head (`preflight_audit`), `frozen = true`"
    )
    return [
        f"repeat_cost = {ln.repeat_cost!r}"
        + (" (an unfilled repeat cost reads so)" if repeat_cost is None else "")
        + f", kind = {kind!r}, {'a model named' if model else 'no model'}: the {sk.instrument} skeleton "
        + f"({', '.join(dest for _, dest in sk.scripts)}"
        + (
            ", a --probe stage before the run)"
            if sk.probe and ln.probe_allowed
            else "; the run is the instrument check)"
        ),
        *(
            [
                "instrument: the unchanged predictor, exposing predict(X); no training; "
                "its null lane scores the same predictions against labels permuted "
                "with the seed (or a registered fixed null predictor)"
            ]
            if kind == APPLY_KIND and not model
            else []
        ),
        f"before a full run: {before}"
        + (
            "; the run may start in the foreground"
            if ln.foreground
            else "; the run starts detached"
        ),
        "after the run: `finalize` clean — the answering run bound and cited, the "
        "promises answered, the scopes unchanged"
        + (
            ", the source frozen in the run and tracked in git" if ln.provenance else ""
        ),
        "at the release (`protocol-fill --from-run`, the stop, the commit): "
        + (
            "frozen, "
            if ln.freeze
            else "no freeze owed, the registration as committed at the first "
            "measurement, "
        )
        + "finalize clean, a full run (no probe, no acknowledged run), a decided "
        + f"{ANALYSIS_AUDIT} audit of code, promises and that run (a BLOCKER accepted "
        + "with `stands` upheld by a decision review, `labkit-audit --review`), "
        + f"`{check}` passing",
    ]
