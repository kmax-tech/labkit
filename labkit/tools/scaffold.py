"""labkit-init — stamp a lab repo and its experiment areas from the templates that ship with labkit.

    labkit-init lab [DIR] [--name NAME] [--labkit-ref REF]
    labkit-init exp NAME [--repo DIR] [--repeat-cost low|high] --kind compute|fit|apply [--model [ALIAS]]
                         [--report] [--explore]
    labkit-init exp NAME --kind compute|fit|apply --change-kind

`lab` lays out a lab repo: `AGENTS.md` (and `CLAUDE.md` pointing at it),
`requirements.txt` pinning this labkit at its release tag on GitHub,
`models.toml`, the editor and type-checker settings, `experiments/`,
`data/raw` → `data/prepared`, `lib/`, `notes/{theorie,messung,results}` with the
lab's empty glossary `notes/theorie/terms.md` (the one home of a lab term,
LAB-084 Double-coinage check), and a test that the shared helpers resolve to
the package. The lab standard is not
copied: it comes with the pin (`python -m labkit.formats.rules show LAB-nnn`).

`exp` stamps one self-contained area `experiments/NN-<name>/`: the protocol
(the pilot part by default; `--report` adds the † fields, now or when the run
graduates; `--repeat-cost low` stamps the low cut instead), the script
skeletons the kind calls for (`standard_contract.skeleton`: a computation
the compute skeleton, `01_measure` and `02_analyze`; a fit, and an apply
without `--model`, the estimator skeleton; an apply with `--model` the
prompt skeleton — both with `00_prepare` before them), the area README and
the area's test under `tests/`. `--explore` stamps only
`experiments/explore/<name>.py`, the entry before an area exists; the plain
command later moves it into the area. `--change-kind` restamps an area under
another kind before its first measurement (`change_kind`).

Every file is written only if absent: rerunning never overwrites — except
`--change-kind`, which replaces or removes the old kind's stamp files and
rewrites the protocol, and is refused when that would lose an edit. The pin
names the release tag `v<version>` of the installed labkit; until that tag is
pushed the pin does not install, so `--labkit-ref` names another ref (a pushed
commit) for development and tests. Run from a source checkout (an editable
install), `lab` stamps only templates that ref holds unchanged
(`check_lab_pin`).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.metadata
import os
import re

from labkit.formats import console
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import promises, protocol_block, protocol_check, standard_contract
from labkit.gates import install_hooks
from labkit.formats.runs import runs_path
from labkit.formats.files import write_all, write_atomic
from labkit.tools.protocol_fill import fill, fill_head
from labkit.formats.repo import (
    EXPERIMENTS,
    commit_of,
    files_at,
    first_added,
    adopt_command,
    AREA_NAME,
    area_protocols,
    areas_named,
    git_root,
    lab_root,
    requirement_lines,
    split_area_name,
    text_at,
)
from labkit.tools.repo_check import PIN_FILES, PYPROJECT_VERSION_RE
from labkit.tools.protocol_cuts import (
    CUT_MARK,
    ProtocolBlocks,
    auto_fill_deterministic,
    bar_cut,
    count_placeholders,
    estimator_placeholders,
    insert_report_fields,
    name_promise_ids,
    new_protocol_id,
    owed_cut,
    pilot_and_report,
    quick_block,
    low_cut,
    short_placeholders,
)

TEMPLATES = PACKAGE_DIR / "templates"
PROTOCOL_TEMPLATE = protocol_check.PROTOCOL_TEMPLATE  # one home for the path
#: where every lab installs labkit from — a lab has no checkout of the package
LABKIT_REMOTE = "https://github.com/kmax-tech/labkit.git"

GITIGNORE = """\
# stamped by labkit-init — what a lab repo never commits
.venv
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
.runs.tsv.lock
# the run index: a local view, rebuilt from runs/<run_id>/ by `runlog reindex`
runs.tsv
"""

REQUIREMENTS = """\
# Shared lab helpers come as a PINNED package — never as file copies, never
# editable (a run records its environment; helpers that can change under a
# finished run make that record a lie). Install:
#   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
#   .venv/bin/labkit-hooks install    (the hooks of this labkit)
# Raise the pin on purpose, never silently.
{pin}

# The stamped areas carry a test (tests/test_<NN>_<name>.py); preflight and
# finalize run it, and without pytest they only warn (cloud probe 2026-10-12).
pytest
"""

#: (template, destination) of the files `lab` copies verbatim
LAB_FILES = (
    ("models.toml.template", "models.toml"),
    ("pyrightconfig.json.template", "pyrightconfig.json"),
    ("vscode-settings.json.template", ".vscode/settings.json"),
    ("vscode-launch.json.template", ".vscode/launch.json"),
    (
        "test-shared-helpers.py.template",
        "tests/test_shared_helpers_come_from_labkit.py",
    ),
    (
        "terms.md.template",
        "notes/theorie/terms.md",
    ),  # the lab's glossary (LAB-084 Double-coinage check)
)
#: the templates `stamp_lab` writes — what the ref a lab's pin names must hold unchanged
LAB_TEMPLATES = ("AGENTS.md.template", *(tmpl for tmpl, _ in LAB_FILES))
LAB_DIRS = (
    EXPERIMENTS,
    "data/raw",
    "data/prepared",
    "lib",
    "notes/theorie",
    "notes/messung",
    "notes/results",
)


def write_if_absent(path: Path, content: str, log: list[str]) -> bool:
    """Write CONTENT to PATH unless it exists — whole or not at all
    (`files.write_atomic`), so a write that died leaves nothing a later
    stamp skips as existing; log either way. True when written."""
    if path.exists() or path.is_symlink():
        log.append(f"  skip (exists)  {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, content)
    log.append(f"  created        {path}")
    return True


def template(name: str) -> str:
    """The text of a shipped template; a missing one is a broken install, said so."""
    path = TEMPLATES / name
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} is missing — labkit was installed without its templates"
        )
    return path.read_text(encoding="utf-8")


def source_version() -> str | None:
    """The version `pyproject.toml` declares when labkit runs from a source
    checkout (an editable install: the file sits beside the package); None
    from a wheel in site-packages."""
    pyproject = PACKAGE_DIR.parent / "pyproject.toml"
    if not pyproject.is_file():
        return None
    m = PYPROJECT_VERSION_RE.search(pyproject.read_text(encoding="utf-8"))
    if m is None:
        raise RuntimeError(f"{pyproject} has no version line")
    return m.group(1)


def pinned_ref(ref: str | None = None) -> str:
    """The ref a lab's pin names: the release tag of the installed version,
    or REF when given (a pushed commit, for development).

    Refuses when the installed metadata and the source checkout disagree: an
    editable install keeps the version of its last `pip install -e` while
    the templates are read live, and the first re-stamp after the 0.88.7
    release pinned v0.88.5 under 0.88.7 templates (2026-10-13)."""
    version = importlib.metadata.version("labkit")
    source = source_version()
    if source is not None and source != version:
        raise console.Refused(
            "labkit-init",
            f"the installed metadata say {version}, the source "
            f"checkout declares {source} — an editable install keeps the "
            f"version of its last install; run `pip install -e '.[dev]'` "
            f"there, or the pin names a tag the templates do not belong to",
        )
    return ref or f"v{version}"


def labkit_pin(ref: str | None = None) -> str:
    """The requirements line pinning labkit on GitHub at `pinned_ref(REF)`."""
    return f"labkit @ git+{LABKIT_REMOTE}@{pinned_ref(ref)}"


def lab_templates_off_ref(checkout: Path, ref: str) -> list[str]:
    """The lab templates (`LAB_TEMPLATES`) whose text in CHECKOUT, as its
    working tree holds it, differs from REF's, or that REF lacks. Raises
    RuntimeError when CHECKOUT is no git repository or REF no commit in it
    (a tag not fetched): then nothing shows that the two agree."""
    if git_root(checkout) is None:
        raise RuntimeError(f"{checkout} is no git checkout")
    commit = commit_of(checkout, ref)
    if commit is None:
        raise RuntimeError(f"{ref} is no commit in {checkout}")
    templates = checkout / "labkit" / "templates"
    return [
        name
        for name in LAB_TEMPLATES
        if text_at(checkout, templates / name, commit)
        != (templates / name).read_text(encoding="utf-8")
    ]


def check_lab_pin(ref: str | None) -> None:
    """Refuse to stamp a lab from a source checkout whose lab templates are
    not those of the ref the pin names (`pinned_ref`, `lab_templates_off_ref`):
    the stamped `AGENTS.md` would describe commands the pinned labkit does
    not have (docs/notes/2026-10-27-lab-pin-templates.md). A check that
    cannot compare refuses too. An installed release stamps its own
    templates; then nothing is compared."""
    if source_version() is None:
        return
    pinned = pinned_ref(ref)
    checkout = PACKAGE_DIR.parent
    try:
        off = lab_templates_off_ref(checkout, pinned)
    except RuntimeError as e:
        raise console.Refused(
            "labkit-init",
            f"cannot tell whether the lab templates in {checkout} are "
            f"{pinned}'s, which the pin installs: {e} — `git fetch --tags "
            f"origin` there, or name a commit it holds with --labkit-ref",
        ) from e
    if off:
        raise console.Refused(
            "labkit-init",
            f"the lab templates in {checkout} differ from {pinned}, which "
            f"the pin installs ({', '.join(off)}): the stamped files would "
            f"describe a labkit the lab does not get. Release first (the "
            f"CHANGELOG entry, then `just release X.Y.Z` there), pin a pushed "
            f"commit that holds these templates (--labkit-ref <commit>), or "
            f"stamp from an installed release",
        )


# --- lab ----------------------------------------------------------------------


def stamp_lab(root: Path, name: str, ref: str | None = None) -> list[str]:
    """Lay out a lab repo in ROOT (see the module docstring); returns the log."""
    log: list[str] = []
    write_if_absent(
        root / "AGENTS.md",
        template("AGENTS.md.template").replace("<project>", name),
        log,
    )
    claude = root / "CLAUDE.md"
    if not (claude.exists() or claude.is_symlink()):
        os.symlink("AGENTS.md", claude)  # one entry file for every agent
        log.append(f"  created        {claude} -> AGENTS.md")
    write_if_absent(root / ".gitignore", GITIGNORE, log)
    write_if_absent(
        root / "requirements.txt", REQUIREMENTS.format(pin=labkit_pin(ref)), log
    )
    for tmpl, dest in LAB_FILES:
        write_if_absent(root / dest, template(tmpl), log)
    for d in LAB_DIRS:
        if write_if_absent(root / d / ".gitkeep", "", log):
            log[-1] = f"  created        {root / d}/"
    return log


# --- the protocol's three cuts ------------------------------------------------


# --- exp ----------------------------------------------------------------------


def next_experiment_number(experiments: Path) -> str:
    """Next free NN prefix ('01' when empty); archived areas keep their number reserved."""
    used = [
        int(m.group(1))
        for d in (experiments, experiments / "_archiv")
        if d.is_dir()
        for p in d.iterdir()
        if p.is_dir() and (m := AREA_NAME.match(p.name))
    ]
    return f"{max(used) + 1 if used else 1:02d}"


def area_slug(name: str) -> str:
    """The area name as a slug, without a typed `NN-` prefix (labkit owns the number)."""
    slug = split_area_name(re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-"))[1]
    if not slug:
        raise console.Refused("labkit-init", f"unusable experiment name: {name!r}")
    return slug


def area_readme(nn: str, slug: str, sk: standard_contract.Skeleton, probe: bool) -> str:
    """The area README: the one question, the route through the area, the contract on one page.

    A computation (SK the compute skeleton, kind compute at every tier) carries no blank:
    its question and contract live in the protocol, and a README placeholder
    was the one gate line left in the cloud probe (draw 11, 2026-10-13).
    PROBE: the lane allows a `--probe` before the run (`Lane.probe_allowed`);
    the State list names it only then, and parser cases only for the prompt
    skeleton, the one with a parser."""
    skeleton = sk is not standard_contract.COMPUTE
    test = f"`.venv/bin/python -m pytest tests/test_{nn}_{slug.replace('-', '_')}.py`"
    if not skeleton:
        state = f"the area test green ({test})"
    elif sk is standard_contract.MODEL:
        state = "parser cases in the test"
    else:
        state = f"the resolution check green ({test})"
    if probe and sk.probe:
        state = "`--probe` read, " + state
    question = (
        "**The one question.** <one sentence — the same question as in the protocol's\n"
        'Intent; if it needs an "and", it is two experiments>'
        if skeleton
        else f"**The one question** is the protocol's Question field (`PROTOCOL-{slug}.md`);\n"
        "a computation asks one and reports one number."
    )
    returns = (
        "**What `evaluate_rows()` returns.** <per registered promise its key, in the order\n"
        "of the decision — from the protocol's [[promise]] sentences, not from the\n"
        "skeleton: [A1] a1_pass …, [C1] c1_pass …, [B1] b1_branch; what comes back when\n"
        "an admissibility condition fails>. The formula lives once, in\n"
        "`scripts/01_measure.py` (`evaluate_rows()`); `02_analyze.py --check` and the\n"
        "test call it there, and `intent-check` holds the protocol's ids to these keys."
        if skeleton
        else "**What `evaluate_rows()` returns.** The number under `METRIC_KEY` of\n"
        "`scripts/01_measure.py`; a computation registers no ids. The formula lives once, there;\n"
        "`02_analyze.py --check` and the test call it, and `--check` holds the protocol's\n"
        "Recorded results line to the run's `metrics.json`."
    )
    recheck = "`02_analyze.py --check`"  # the one public recheck of every skeleton
    return f"""# Experiment {nn}: {slug}

*Self-contained: data, scripts, output and this description live here.*

{question}

<!-- labkit:route -->
**Trace it.**
- Contract and reported answer: `PROTOCOL-{slug}.md`
- Runs and provenance: `runlog experiments/{nn}-{slug}` (from the repo root)
- Effective values: `labkit-params experiments/{nn}-{slug}`
- Where the ids are decided: `scripts/01_measure.py:evaluate_rows`
- Immutable record: `config.json` of the chosen run under `runs/`
<!-- /labkit:route -->

## Contract

{returns}

**The gates, in order.** `code-check` after every code change · at
`high`: `preflight` + the preflight audit, then freeze · the run
through `runlog` · `finalize` · `labkit-audit <area> --mode analysis` ·
decide its findings (`labkit-audit <area> --findings` prints the commands) ·
write the Conclusion and obtain any required decision review ·
`protocol-fill --from-run` writes the number back and runs {recheck} through
`report-check`. `AGENTS.md` explains each step and the recovery choices.

## State

- [ ] Registration written in the protocol (**before** the first run)
- [ ] {state}
- [ ] Run and `finalize` green
- [ ] Analysis audit decided; Conclusion written; required reviews upheld
- [ ] `protocol-fill --from-run` and `report-check` green
"""


def stamp_explore(experiments: Path, slug: str) -> list[str]:
    """`experiments/explore/<slug>.py` only — the entry before an area exists."""
    log: list[str] = []
    write_if_absent(
        experiments / "explore" / f"{slug}.py",
        template("explore-script.py.template").replace("<name>", slug),
        log,
    )
    return log


def explore_next(slug: str) -> str:
    """What `--explore` prints next: the area's stamp as one complete
    command per kind and the questions that choose among them
    (`KIND_QUESTIONS`) — the kind is not known while exploring, and `exp`
    without `--kind` is refused (`asked_kind`); the repeat cost named too,
    since without it the stamp took the high form with a placeholder cost
    (audit 2026-10-27, third, I8)."""
    commands = "\n".join(
        f"  labkit-init exp {slug} --kind {kind} --repeat-cost low"
        for kind in protocol_block.KINDS
    )
    return (
        "\nNext: fill the cells, read the render, look at real output; when it "
        "holds, stamp the area under the kind its kept number asserts — one of\n"
        f"{commands}\n"
        f"{KIND_QUESTIONS}. --repeat-cost high instead when a repeat of the run "
        "is expensive (preflight audit and freeze before it). With a model "
        "answering in the area add --model ALIAS (the explore file's MODEL)."
    )


def promote(area: Path, blocks: ProtocolBlocks) -> list[str]:
    """Fill the report-grade fields into an existing area's protocols."""
    protos = area_protocols(area)
    if not protos:
        raise console.Refused("labkit-init", f"no PROTOCOL-*.md in {area}")
    log = []
    for proto in protos:
        text = proto.read_text(encoding="utf-8")
        lane = standard_contract.lane(protocol_block.head(text).repeat_cost)
        if not lane.freeze:
            log.append(
                f"  skip (repeat_cost {lane.repeat_cost}: nothing freezes, no report fields)  {proto}"
            )
            continue
        new, added = insert_report_fields(text, blocks)
        if not added:
            log.append(f"  skip (report fields already there)  {proto}")
            continue
        new, auto = auto_fill_deterministic(new)
        write_atomic(proto, new)
        log.append(
            f"  filled in      {proto} ({added} report field(s), each in its section)"
        )
        if auto:
            log.append(
                f"  n/a stamped    {auto} field(s): no model, nothing to draw, nothing to parse"
            )
    return log


def stamp_scripts(
    root: Path,
    area: Path,
    nn: str,
    slug: str,
    skeleton: standard_contract.Skeleton,
    model: bool | str,
) -> list[str]:
    """Write the script skeletons and the area's test (`script_stamps`)
    where absent; a script written is made executable."""
    log: list[str] = []
    for path, text in script_stamps(root, area, nn, slug, skeleton, model).items():
        if write_if_absent(path, text, log) and path.parent == area / "scripts":
            path.chmod(0o755)  # a shebang nobody can run is a lint finding
    return log


def script_stamps(
    root: Path,
    area: Path,
    nn: str,
    slug: str,
    skeleton: standard_contract.Skeleton,
    model: bool | str,
) -> dict[Path, str]:
    """{path: text} of the script skeletons and the area's test under
    tests/ — which ones is the contract's answer (`standard_contract.skeleton`:
    the compute, estimator or prompt skeleton, every one with the check).
    Reads the templates, writes nothing."""
    out: dict[Path, str] = {}
    alias = model if isinstance(model, str) else "TODO-alias"
    tname = (f"test_{nn}_{slug}" if nn else f"test_{slug}").replace("-", "_") + ".py"
    for tmpl, dest in skeleton.scripts:
        # `<NN>_<name>` first: the scripts name the area's test file too (the
        # probe's "paste into tests/test_<NN>_<name>.py" stayed unreplaced,
        # cloud judge probe 2026-10-14)
        out[area / "scripts" / dest] = (
            template(tmpl)
            .replace("<NN>_<name>", tname[len("test_") : -3])
            .replace("<name>", slug)
            .replace("<model>", alias)
        )
    out[root / "tests" / tname] = (
        template(skeleton.test)
        .replace("<area>", str(area.relative_to(root)))
        .replace("<NN>_<name>", tname[len("test_") : -3])
        .replace("<name>", slug)
    )
    return out


def stamp_area(
    root: Path,
    name: str,
    repeat_cost: str | None = None,
    kind: str | None = None,
    model: bool | str = False,
    report: bool = False,
) -> tuple[Path, str]:
    """Stamp `experiments/NN-<name>/` (or promote it with REPORT): the area
    and the report to print (what was written, then the next steps) — the
    caller prints; `stamp_lab` returns its log the same way. KIND is what
    the kept number asserts (`protocol_block.KINDS`); a new area without it
    is refused — nothing falls back to a computation (standard 0.22).
    Raises `console.Refused` too for an area of NAME that exists without
    REPORT, and with REPORT where NAME names no one area
    (`existing_area`)."""
    slug = area_slug(name)
    experiments = root / EXPERIMENTS
    if not (root / "models.toml").is_file() or not experiments.is_dir():
        raise console.Refused(
            "labkit-init",
            f"{root} is not a lab repo (no models.toml / experiments/) — run `labkit-init lab` first",
        )
    # existing_area refuses a name several areas carry; None: stamp a new one
    if report and (found := existing_area(experiments, name)) is not None:
        _, blocks = pilot_and_report(CUT_MARK.sub("", template(PROTOCOL_TEMPLATE.name)))
        return found, "\n".join(promote(found, blocks))
    kind = asked_kind(kind)
    quick = standard_contract.lane(repeat_cost).cut == standard_contract.LOW_CUT
    skeleton = standard_contract.skeleton(repeat_cost, kind, bool(model))
    stamped = protocol_stamp(root, slug, repeat_cost, kind, model, report)
    existing = areas_named(experiments, slug)
    if existing:
        which = slug if len(existing) == 1 else existing[0].name
        raise console.Refused(
            "labkit-init",
            f"experiment already exists: {_area_names(existing)} under "
            f"{experiments} — add report fields with `labkit-init exp {which} "
            f"--report`",
        )
    nn = next_experiment_number(experiments)
    area = experiments / f"{nn}-{slug}"
    log: list[str] = []
    for d in ("data/raw", "data/prepared", "output"):
        write_if_absent(area / d / ".gitkeep", "", log)
    write_if_absent(
        area / "README.md",
        area_readme(
            nn, slug, skeleton, standard_contract.lane(repeat_cost).probe_allowed
        ),
        log,
    )
    pre = experiments / "explore" / f"{slug}.py"
    if pre.is_file():  # an explore file stamped before the area graduates with it
        (area / "explore").mkdir(exist_ok=True)
        pre.rename(area / "explore" / pre.name)
        log.append(f"  moved          {pre} -> {area / 'explore' / pre.name}")
    write_if_absent(area / f"PROTOCOL-{slug}.md", stamped, log)
    log += stamp_scripts(root, area, nn, slug, skeleton, model)
    _point_hooks_at(root)
    return area, (
        f"{'Measurement' if quick else 'Experiment'} -> {area}\n"
        + "\n".join(log)
        + "\n"
        + next_steps(area.relative_to(root), slug, nn, repeat_cost, kind, bool(model))
    )


def protocol_stamp(
    root: Path,
    slug: str,
    repeat_cost: str | None,
    kind: str,
    model: bool | str,
    report: bool,
    pid: str | None = None,
) -> str:
    """The protocol `exp` stamps for these answers: the low cut, or the
    pilot part — with REPORT the whole — under a fresh id, or PID. Reads
    the template (and, without PID, the ids taken under ROOT); writes
    nothing. The cut and the skeleton are the contract's answers, not read
    off the tier here (a tier compared by hand outside the contract is a
    copy)."""
    quick = standard_contract.lane(repeat_cost).cut == standard_contract.LOW_CUT
    skeleton = standard_contract.skeleton(repeat_cost, kind, bool(model))
    tmpl = stamped_head(
        template(PROTOCOL_TEMPLATE.name), root, slug, repeat_cost, kind, model, pid
    )
    clean = CUT_MARK.sub(
        "", bar_cut(tmpl, kind)
    )  # every written protocol is free of the cut markers
    pilot, _ = pilot_and_report(clean)
    if quick:
        pilot = low_cut(quick_block(tmpl, kind), kind, model=bool(model))
        if skeleton is standard_contract.COMPUTE:
            pilot = count_placeholders(pilot)
        elif skeleton is standard_contract.ESTIMATOR:
            pilot = estimator_placeholders(
                pilot, cut=True, kind=kind, model=bool(model)
            )
    elif skeleton is standard_contract.ESTIMATOR:
        pilot = estimator_placeholders(pilot, kind=kind, model=bool(model))
    if (
        report
        and skeleton is standard_contract.ESTIMATOR
        and kind == standard_contract.APPLY_KIND
    ):
        clean = estimator_placeholders(clean, kind=kind, model=bool(model))
    stamped = blank_before_headings(short_placeholders(clean if report else pilot))
    if not quick:
        stamped = owed_cut(stamped)  # the full form owes by kind and model too
    stamped = name_promise_ids(stamped, kind)
    check_stamped_head(stamped, repeat_cost, kind, bool(model))
    return stamped


#: the field `--report` adds; its presence says the protocol carries the
#: report fields, and a restamp keeps them
REPORT_FIELD = "Deviations after freeze"


@dataclass(frozen=True)
class KindChange:
    """What `--change-kind` would do to one area, computed before anything
    is written (`plan_kind_change`).

    Attributes:
        old_kind: The kind the protocol declares now.
        before: The old kind's stamp files, path to stamped text.
        after: The new kind's stamp files, path to text to write.
        protocol: The protocol file; `text` is its restamped content.
        text: The new protocol: same id, the written fields carried.
        held: Why the change would lose work — empty when it may go ahead.
        next_steps: The new kind's next steps, to print after the change.
        earlier: The files (the protocol: its promise block) that differ
            from this labkit's stamp of the old kind but are unchanged
            since a commit under an earlier pin (`earlier_pin_text`): path
            to that commit, which the log names.
    """

    old_kind: str
    before: dict[Path, str]
    after: dict[Path, str]
    protocol: Path
    text: str
    held: list[str]
    next_steps: str
    earlier: dict[Path, str]


def change_kind(root: Path, name: str, kind: str | None) -> tuple[Path, str]:
    """`exp NAME --kind KIND --change-kind`: restamp the area NAME, stamped
    under another kind, before its first measurement (`plan_kind_change`
    says what changes and what holds it, `write_kind_change` writes it).
    Raises `console.Refused`, with nothing changed, when the plan holds.
    Returns (area, report to print)."""
    kind = asked_kind(kind)
    slug = area_slug(name)
    area = restampable_area(root, name, kind)
    plan = plan_kind_change(root, area, slug, kind)
    if plan.held:
        raise console.Refused(
            "labkit-init",
            f"--change-kind {plan.old_kind} -> {kind} would lose work, nothing "
            f"changed — move it out (e.g. into {area / 'explore'}/) or change the "
            f"kind by hand:\n  " + "\n  ".join(plan.held),
        )
    log = write_kind_change(area, plan)
    return area, (
        f"Kind {plan.old_kind} -> {kind} in {area}\n"
        + "\n".join(log)
        + "\n"
        + plan.next_steps
    )


def existing_area(experiments: Path, name: str) -> Path | None:
    """The existing area `exp NAME` means under EXPERIMENTS — the one
    `--report` promotes and `--change-kind` restamps. NAME is spelled as
    `area_slug` reads it; the areas of its slug are `repo.areas_named`'s.
    A number typed with it (`02-x`) picks the area of that number; without
    one the slug must name a single area. None when no area carries the
    slug. Raises `console.Refused`, naming the candidates and how to name
    one, when the typed number names none of them, or several carry the
    slug and no number was typed: taking the first in directory order, or
    another number's area, was a guess (audit 2026-10-27)."""
    slug = area_slug(name)
    found = areas_named(experiments, slug)
    number = split_area_name(name.strip())[0]
    if number is not None and found:
        picked = [p for p in found if p.name == f"{number}-{slug}"]
        if not picked:
            raise console.Refused(
                "labkit-init",
                f"no area {number}-{slug} under {experiments} — {slug!r} names "
                f"{_area_names(found)}; {_name_one(found)}",
            )
        found = picked
    if len(found) > 1:
        raise console.Refused(
            "labkit-init",
            f"{len(found)} areas under {experiments} carry the name {slug!r}: "
            f"{_area_names(found)} — {_name_one(found)}",
        )
    return found[0] if found else None


def _area_names(areas: list[Path]) -> str:
    """AREAS by their directory names, as a refusal lists them."""
    return ", ".join(p.name for p in areas)


def _name_one(areas: list[Path]) -> str:
    """How to name one of AREAS, the areas of one slug: by its number; an
    area without a number cannot be named apart from the others."""
    numbered = [p.name for p in areas if split_area_name(p.name)[0] is not None]
    how = (
        [f"name the one you mean by its number (`labkit-init exp {numbered[0]} …`)"]
        if numbered
        else []
    )
    how += [
        f"{p.name} has no number to be named by — rename it NN-{p.name} to choose it"
        for p in areas
        if split_area_name(p.name)[0] is None
    ]
    return "; ".join(how)


def restampable_area(root: Path, name: str, kind: str) -> Path:
    """The area NAME names under ROOT (`existing_area`) that `--change-kind`
    may restamp: it exists, holds its one stamped protocol and has not
    measured. Raises `console.Refused` otherwise — after a run the kind is
    part of the registration the first measurement stood on
    (`report_check.registration_gaps`), so the way is a new registration."""
    experiments = root / EXPERIMENTS
    slug = area_slug(name)
    area = existing_area(experiments, name)
    if area is None:
        raise console.Refused(
            "labkit-init",
            f"--change-kind: no area {slug!r} under {experiments} — "
            f"`labkit-init exp {slug} --kind {kind}` stamps a new one",
        )
    protocol = area / f"PROTOCOL-{slug}.md"
    if area_protocols(area) != [protocol]:
        raise console.Refused(
            "labkit-init",
            f"--change-kind: {area} holds {len(area_protocols(area))} protocol(s), "
            f"the stamp holds one ({protocol.name}) — change the kind by hand",
        )
    runs_dir = runs_path(area)
    if runs_dir.is_dir() and any(runs_dir.iterdir()):
        raise console.Refused(
            "labkit-init",
            f"--change-kind: {area} has measured ({runs_dir} is not empty) — the "
            f"kind is part of the registration that stood before the first "
            f"measurement, and changing it now does not change what stood then. "
            f"A model trained here is a new registration: `labkit-init exp "
            f"<new-name> --kind {kind}`, committed before its first run; this "
            f"area keeps its runs and their verdict, and the new protocol's "
            f"Context names it and why it was replaced",
        )
    return area


def plan_kind_change(root: Path, area: Path, slug: str, kind: str) -> KindChange:
    """The change of AREA's protocol and stamp files to KIND, and what
    holds it (`KindChange.held`): a stamped script, README or test edited
    since the old kind's stamp; a file of the author's where the new kind
    stamps; a promise block that differs from the old stamp's; a written
    `[model]` claim a non-compute kind does not carry; a written field the
    new protocol has no place for, or one over several lines. "Edited" and
    "differs" are measured against this labkit's stamp, unless git shows
    the file (the block) unchanged since a commit under an earlier pin
    (`earlier_pin_text`, `KindChange.earlier`). The protocol
    keeps its id, `type`, model alias and report fields; a written field is
    carried when it differs from the old stamp's own value. Reads files
    and git, writes nothing. Raises `console.Refused` for a protocol
    without kind or id, or already of KIND."""
    nn = split_area_name(area.name)[0] or ""
    protocol = area / f"PROTOCOL-{slug}.md"
    old = protocol.read_text(encoding="utf-8")
    head = protocol_block.head(old)
    if head.kind is None or head.id is None:
        raise console.Refused(
            "labkit-init",
            f"--change-kind: {protocol.name} declares no kind or no id — fill the "
            f"head (`protocol-fill … kind=…`) instead",
        )
    if head.kind == kind:
        raise console.Refused(
            "labkit-init",
            f"--change-kind: {protocol.name} already says kind = {kind!r}",
        )
    declared = protocol_block.model(old)
    model: bool | str = (declared.alias or True) if declared is not None else False
    report = any(
        f.name == protocol_check.field_name(REPORT_FIELD)
        for f in protocol_check.fields(old)
    )
    rc = head.repeat_cost
    before = stamp_files(root, area, nn, slug, rc, head.kind, model)
    after = stamp_files(root, area, nn, slug, rc, kind, model)
    held, earlier = edited_stamps(root, before, head.kind)
    held += [
        f"{path}: a file of yours where the {kind} stamp writes"
        for path in after
        if path not in before and path.exists()
    ]
    fresh_old = protocol_stamp(root, slug, rc, head.kind, model, report, head.id)
    if promises.block_stamp(old) != promises.block_stamp(fresh_old):
        found = earlier_pin_text(root, protocol)
        if found is not None and same_promises(found[1], old):
            earlier[protocol] = found[0]
        else:
            held.append(
                f"{protocol.name}: the promise block differs from the {head.kind} "
                f"stamp — the {kind} stamp would replace it"
            )
    if (
        declared is not None
        and kind != standard_contract.COMPUTE_KIND
        and (declared.number_describes or declared.annotation_validity)
    ):
        held.append(
            f"{protocol.name}: [model] number_describes / annotation_validity are "
            f"written — a {kind} has no place for them"
        )
    text, unplaced = carried_fields(
        old, fresh_old, protocol_stamp(root, slug, rc, kind, model, report, head.id)
    )
    held += [f"{protocol.name}:{why}" for why in unplaced]
    if head.type is not None:
        text = fill_head(text, "type", head.type)
    steps = next_steps(area.relative_to(root), slug, nn, rc, kind, bool(model))
    return KindChange(head.kind, before, after, protocol, text, held, steps, earlier)


def edited_stamps(
    root: Path, stamps: dict[Path, str], kind: str
) -> tuple[list[str], dict[Path, str]]:
    """Of the stamp files STAMPS (path to this labkit's stamp of KIND)
    that exist and differ from it: the ones edited since the stamp, as
    held lines, and the ones git shows unchanged since a commit under an
    earlier pin (`earlier_pin_text`), path to that commit — this labkit's
    stamp measures an edit only of a file it stamped. Reads files and git,
    writes nothing."""
    held: list[str] = []
    earlier: dict[Path, str] = {}
    for path, stamped in stamps.items():
        if not path.is_file():
            continue
        now = path.read_text(encoding="utf-8")
        if now == stamped:
            continue
        found = earlier_pin_text(root, path)
        if found is not None and found[1] == now:
            earlier[path] = found[0]
        elif _never_committed(root, path):
            # git sees the file but no commit holds it: nothing tells an
            # edit from an earlier labkit's stamp
            held.append(
                f"{path}: differs from the {kind} stamp and was never committed — "
                f"no evidence whose text it is"
            )
        else:
            held.append(f"{path}: edited since the {kind} stamp")
    return held, earlier


def _never_committed(root: Path, path: Path) -> bool:
    """Is ROOT inside a repository whose index lacks PATH (`repo.files_at`)?
    False outside a repository: there the stamp of this labkit is all there
    is to compare with."""
    repo = git_root(root)
    held = None if repo is None else files_at(repo, path.parent)
    return held is not None and path.name not in held


def earlier_pin_text(root: Path, path: Path) -> tuple[str, str] | None:
    """(commit, text): PATH as the commit that first added it holds it
    (`repo.first_added`, renames followed), when a pin file under ROOT
    (`repo_check.PIN_FILES`) pins another labkit then than now (its
    `labkit` lines, a trailing comment aside): the evidence that this
    labkit's templates are not the ones PATH was stamped from, so a
    difference from today's stamp shows no edit. None without that
    evidence: outside a git repo, PATH never committed, deleted and added
    again, a shallow clone, or no pin file with a labkit line both then
    and now that pins another. Limit: an edit committed together with the
    stamp, under the earlier pin, reads as that pin's stamp — the commit
    keeps it. Reads git and the pin files, writes nothing; raises
    RuntimeError when git fails."""
    repo = git_root(root)
    if repo is None:
        return None
    found = first_added(repo, path)
    if found is None:
        return None
    commit, then_path = found
    for name in PIN_FILES:
        pins = root / name
        then = _pins(text_at(repo, pins, commit) or "")
        now = _pins(pins.read_text(encoding="utf-8")) if pins.is_file() else []
        if then and now and then != now:
            text = text_at(repo, then_path, commit)
            return None if text is None else (commit, text)
    return None


def _pins(text: str) -> list[str]:
    """The `labkit` lines of a pin file's TEXT without a trailing comment
    (pip reads ` #` as one): what they pin, a note beside it aside."""
    return [re.sub(r"\s+#.*$", "", ln) for ln in requirement_lines(text, "labkit")]


def same_promises(then: str, now: str) -> bool:
    """Do the protocol texts THEN and NOW declare the same promise block
    (`promises.block_stamp`)? A block in THEN this labkit cannot read is
    not NOW's; one in NOW raises PromiseError."""
    want = promises.block_stamp(now)
    try:
        got = promises.block_stamp(then)
    except promises.PromiseError:
        return False
    return got == want


def stamp_files(
    root: Path,
    area: Path,
    nn: str,
    slug: str,
    repeat_cost: str | None,
    kind: str,
    model: bool | str,
) -> dict[Path, str]:
    """The stamp files of KIND besides the protocol: scripts, the area's
    test and README, path to text (`script_stamps`, `area_readme`)."""
    skeleton = standard_contract.skeleton(repeat_cost, kind, bool(model))
    out = script_stamps(root, area, nn, slug, skeleton, model)
    out[area / "README.md"] = area_readme(
        nn, slug, skeleton, standard_contract.lane(repeat_cost).probe_allowed
    )
    return out


def carried_fields(old: str, old_stamp: str, new: str) -> tuple[str, list[str]]:
    """NEW with every field OLD has written — not a placeholder and not the
    value OLD_STAMP already carried — set by its label, and the fields that
    found no place (`<line> <label>: why`). Pure."""
    stamped = {f.name: f.value for f in protocol_check.fields(old_stamp)}
    unplaced: list[str] = []
    for f in protocol_check.fields(old):
        if not f.value or f.placeholder or stamped.get(f.name) == f.value:
            continue
        if f.block:
            unplaced.append(f"{f.line} {f.label}: a value over several lines")
            continue
        try:
            new = fill(new, f.label, f.value, force=True)
        except ValueError as exc:
            unplaced.append(f"{f.line} {f.label}: no place in the new stamp ({exc})")
    return new, unplaced


def write_kind_change(area: Path, plan: KindChange) -> list[str]:
    """Write PLAN: remove the old kind's stamp files the new kind does not
    stamp, write the new kind's (scripts executable) and the protocol — all
    staged before any is replaced (`files.write_all`), so a write that
    fails changes nothing, and the old kind's files are removed only after.
    Returns the log lines; one replaced on the evidence of an earlier pin
    names the commit that keeps it (`KindChange.earlier`)."""

    def earlier(path: Path) -> str:
        """` of an earlier pin, as committed in <commit>` for a PATH
        replaced on that evidence, else ""."""
        commit = plan.earlier.get(path)
        return f" of an earlier pin, as committed in {commit[:12]}" if commit else ""

    removed = [p for p in plan.before if p.is_file() and p not in plan.after]
    replaced = {path: path.exists() for path in plan.after}
    for path in plan.after:
        path.parent.mkdir(parents=True, exist_ok=True)
    write_all({**plan.after, plan.protocol: plan.text})
    log = [
        f"  removed        {path} (the {plan.old_kind} stamp{earlier(path)})"
        for path in removed
    ]
    for path in plan.after:
        if path.parent == area / "scripts":
            path.chmod(0o755)  # a shebang nobody can run is a lint finding
        log.append(
            f"  {'replaced' if replaced[path] else 'created':<14} {path}"
            + (f" (the stamp{earlier(path)})" if path in plan.earlier else "")
        )
    log.append(
        f"  restamped      {plan.protocol} (same id, written fields kept"
        + (
            f"; the promise block{earlier(plan.protocol)} replaced"
            if plan.protocol in plan.earlier
            else ""
        )
        + ")"
    )
    for path in removed:
        path.unlink()
    return log


def asked_kind(kind: str | None) -> str:
    """The kind a new area is stamped with — the one asked, held to
    `protocol_block.KINDS`; nothing falls back to a computation (standard
    0.22). A computation with `--model` is stamped, not refused: its head
    says what the number describes (`COMPUTE_CLAIM`). Raises
    `console.Refused` naming the choice."""
    if kind is None:
        raise console.Refused(
            "labkit-init",
            "--kind compute|fit|apply: what the kept number asserts; nothing is "
            f"stamped without it. {KIND_QUESTIONS}.",
        )
    if kind not in protocol_block.KINDS:
        raise console.Refused(
            "labkit-init", f"--kind {kind!r}: one of {', '.join(protocol_block.KINDS)}"
        )
    return kind


def _point_hooks_at(root: Path) -> None:
    """`core.hooksPath = .githooks` where the repo has both: the hook runs
    only where that setting points at it (2026-10-05)."""
    if not ((root / ".git").exists() and (root / install_hooks.HOOKS_DIR).is_dir()):
        return
    try:
        install_hooks.point_hooks_at(root)
    except RuntimeError as exc:
        raise console.Refused("labkit-init", str(exc)) from exc


def blank_before_headings(text: str) -> str:
    """TEXT with a blank line before every `## ` heading that follows a
    non-blank line — a heading right after a cut item gets its blank line
    back. Lines inside a fenced block are no headings and stay as they are
    (`protocol_block.fenced_lines`)."""
    lines = text.split("\n")
    starts = set(protocol_block.section_starts(lines))
    out: list[str] = []
    for i, line in enumerate(lines):
        if i in starts and out and out[-1].strip():
            out.append("")
        out.append(line)
    return "\n".join(out)


#: the questions that decide `--kind`, asked in this order; the help, the
#: refusal without `--kind` and a computation's next steps print this one
#: text. Training comes first and covers a deliverable of predictions:
#: an agent told to "train a random forest" called it a cheap computation
#: (docs/notes/2026-10-26-kind-choice.md)
KIND_QUESTIONS = (
    "(1) Does this area train, adjust or select a model or prediction procedure "
    "(a threshold, window or prompt chosen after seeing results, or to agree "
    "with reference annotations, counts; a rule fixed in advance that derives a "
    "parameter from each input itself — a threshold at k times each signal's "
    "own noise level, k fixed — does not)? yes: fit — also "
    "when the deliverable is predictions on unlabelled rows; the kept number is "
    "then the model's score on held-out labelled rows. (2) Otherwise: does the "
    "number judge how well a model used unchanged predicts, against gold labels "
    "or targets? yes: apply, no: compute. Repeat cost does not decide the kind: "
    "a fit that takes seconds is a fit"
)


#: what a computation with a model in the loop stamps below the alias: what
#: its number describes, and — with a property of the data — the evidence
#: that the model suits as annotator (`protocol_check.kind_gap`)
COMPUTE_CLAIM = (
    'number_describes = "<model_outputs | target_property>"\n'
    '# annotation_validity = { protocol = "p-…" }   # or { doi = "10.…" }; '
    "with target_property only\n"
)


def stamped_head(
    tmpl: str,
    root: Path,
    slug: str,
    repeat_cost: str | None,
    kind: str,
    model: bool | str,
    pid: str | None = None,
) -> str:
    """The template with its head tokens replaced: the name once, a fresh
    protocol id (PID when given), COST when asked, KIND always, and with MODEL a `[model]`
    table after `preflight_audit` — the alias when --model named one, else
    its placeholder for `protocol-fill "model alias=…"` (phase 4, 2026-10-21),
    and for a computation the claim keys (`COMPUTE_CLAIM`)."""
    out = tmpl.replace("<name>", slug, 1).replace(
        "<protocol-id>", pid or new_protocol_id(root)
    )
    if repeat_cost:
        out = out.replace(
            'repeat_cost = "<low | high>"', f'repeat_cost = "{repeat_cost}"'
        )
    out = out.replace('kind = "<compute | fit | apply>"', f'kind = "{kind}"')
    if model:
        alias = model if isinstance(model, str) else "<alias from models.toml>"
        claim = COMPUTE_CLAIM if kind == standard_contract.COMPUTE_KIND else ""
        out = out.replace(
            'preflight_audit = ""\n',
            f'preflight_audit = ""\n\n[model]\nalias = {protocol_block.toml_string(alias)}\n'
            + claim,
            1,
        )
    return out


def check_stamped_head(
    text: str, repeat_cost: str | None, kind: str, model: bool = False
) -> None:
    """Raise ValueError unless the stamped protocol's head carries a real
    id, the KIND asked, when COST was asked for that tier, and when MODEL was
    asked for a `[model]` table. The stamp writes them by replacing template
    tokens; a token the template no longer carried would leave the
    placeholder without a word."""
    head = protocol_block.head(text)
    if head.id is None:
        raise ValueError("labkit-init: the stamped head has no protocol id")
    if head.kind != kind:
        raise ValueError(
            f"labkit-init: the stamped head says kind = {head.kind!r}, asked {kind!r}"
        )
    if repeat_cost is not None and head.repeat_cost != repeat_cost:
        raise ValueError(
            f"labkit-init: the stamped head says repeat_cost = {head.repeat_cost!r}, asked {repeat_cost!r}"
        )
    if model and protocol_block.model(text) is None:
        raise ValueError("labkit-init: --model asked, the stamped head has no [model]")


# The stamp writes example numbers into the [[promise]] constants; a fit kept
# the stamped margin 0.25 while its sentence said 0.15 (SAB-like draw,
# 2026-10-27), and three of three readers asked whether they may stand.
CONSTANTS = (
    ", the [[promise]] constants (the stamp's numbers are examples — set each "
    "to the value its sentence states)"
)


def step_fields(sk: standard_contract.Skeleton, kind: str, model: bool) -> str:
    """The protocol fields the first next step names: what every kind
    fills (terms, question, unit, data, exclusions — AGENTS.md's "every kind";
    terms left out until 2026-10-28, when the pre-commit hook refused it;
    the high steps of a fit or an apply named neither unit nor data, audit
    2026-10-27, third, I12), then the bar by KIND
    (`standard_contract.has_bar`), the prompt and the data profile whenever
    a model is named — the low cut's marks (`protocol_check.in_cut`). Only
    the prompt skeleton's `00_prepare.py --audit` prints a data-profile
    aid; elsewhere the step names none."""
    every = "terms, question, unit, data, exclusions"
    if not standard_contract.has_bar(kind):
        bar = (
            f"{every} — no criterion, no promise table: a computation "
            "judges no prediction, so it has no bar to clear"
        )
    elif sk is standard_contract.MODEL:
        bar = f"{every}, criterion, admissibility condition, prompt, null condition{CONSTANTS}"
    else:
        bar = (
            f"{every}, criterion, admissibility condition, null condition{CONSTANTS} — "
            f"kind = {kind!r}: "
            "the number judges a prediction, so it has a bar and its reference"
        )
    if sk is standard_contract.MODEL:
        return bar + (
            ", data profile — your judgement of the data before the run, "
            "`scripts/00_prepare.py --audit` prints an aid"
        )
    if model:
        return bar + (
            "; a model is named: also prompt and data profile — your judgement, "
            "before the run, whether a surface feature could answer the question "
            "without the model"
            + (
                # a MUST the steps never named (audit 2026-10-27, third, I5)
                "; and what the number describes, `protocol-fill "
                "PROTOCOL number_describes=model_outputs|target_property`"
                if not standard_contract.has_bar(kind)
                else ""
            )
        )
    return bar


def estimator_fill(kind: str) -> str:
    """What the estimator skeleton's `01_measure.py` asks to be filled, by
    KIND: at apply the unchanged predictor, at fit the estimator. One
    sentence for both cuts — it stood twice in `next_steps` (audit
    2026-10-27, third, M7)."""
    if kind == standard_contract.APPLY_KIND:
        return (
            "make_estimator() loads the unchanged predictor (the null lane permutes "
            "the labels); SCORE, FEATURES_FIELD"
        )
    return "make_estimator(), SCORE, FEATURES_FIELD"


def next_steps(
    rel: Path, slug: str, nn: str, repeat_cost: str | None, kind: str, model: bool
) -> str:
    """What to do after `exp`, in order — the lane of AGENTS.md for this
    area, read off the contract: the fields and files first
    (`_first_steps`), then the freeze and the run (`_run_steps`), then
    the closing (`_closing_steps`: finalize, the analysis audit where the
    lane owes it, the adoption at the end of every lane). A computation
    first checks its kind. Until 2026-10-19 the printed steps at high
    repeat cost skipped the preflight, both audits and the adoption while
    the stamped AGENTS.md named them; an agent following the console met
    the refusal at the run's start."""
    ln = standard_contract.lane(repeat_cost)
    protocol = f"PROTOCOL-{slug}.md"
    title, steps = _first_steps(ln, rel, slug, nn, kind, model)
    steps += _run_steps(ln, rel, slug)
    if kind == standard_contract.COMPUTE_KIND:
        # first, before any field is filled: a model fitted under compute
        # owes a criterion its protocol has no place for
        steps.insert(
            0,
            f"Check the kind before anything else. {KIND_QUESTIONS}. If (1) "
            f"is yes: `labkit-init exp {slug} --kind fit --change-kind` — before "
            f"the first measurement; it keeps what you wrote and refuses to "
            f"replace a file you changed.",
        )
    steps += _closing_steps(ln, rel, protocol)
    return f"\nNext ({title}):\n" + "\n".join(
        f"  {i}. {step}" for i, step in enumerate(steps, 1)
    )


def _first_steps(
    ln: standard_contract.Lane, rel: Path, slug: str, nn: str, kind: str, model: bool
) -> tuple[str, list[str]]:
    """(title, steps) before the freeze: the protocol's fields, the stamped
    scripts and the area test, by the lane's cut and the skeleton — the
    files and flags follow the skeleton: a computation has no
    `00_prepare.py` and no `--show`/`--probe`. `next_steps` held all three
    shapes inline, 142 lines (audit 2026-10-27, third, M7)."""
    sk = standard_contract.skeleton(ln.repeat_cost, kind, model)
    protocol = f"PROTOCOL-{slug}.md"
    fields = step_fields(sk, kind, model)
    code_check = f"after every code change `code-check {rel}`"
    test = f"tests/test_{nn}_{slug.replace('-', '_')}.py"
    if ln.cut == standard_contract.LOW_CUT:
        return _low_steps(ln, sk, protocol, fields, kind, code_check, test)
    # the key the head carries, `repeat_cost`, rather than "lane": the
    # reader fills the head, not `standard_contract.lane` (I12)
    title = f'repeat_cost = "{ln.repeat_cost}": light pilot, heavy report'
    if sk is standard_contract.COMPUTE:
        return title + " — a computation, the run is the instrument check", [
            f"{protocol}: fill the pilot part (head: type, repeat_cost; "
            f"{fields}); `protocol-check --contract` names the labels.",
            f"scripts/01_measure.py: expected_ids(), rows(), evaluate_rows(); {code_check}.",
            f"{test}: the counting function at two edges — no criterion, so no "
            "resolution check.",
        ]
    if sk is standard_contract.ESTIMATOR:
        title += " — the instrument is an estimator" + (
            "" if model else ", no model call"
        )
        probe = (
            "scripts/01_measure.py --probe 12  instrument check: "
            + (
                "the unchanged predictor, "
                if kind == standard_contract.APPLY_KIND
                else "a reduced estimator, "
            )
            + "both lanes, throwaway; scores read, never reported"
        )
        return title, [
            f"{protocol}: fill the pilot part (head: type, repeat_cost; {fields}; "
            "the estimator in Model / tool); `protocol-check --contract` names the labels.",
            f"scripts/00_prepare.py: raw -> prepared, gold null for the unlabelled "
            f"split   ({rel}/scripts)",
            f"scripts/01_measure.py: {estimator_fill(kind)}; --show 3 reads the "
            "config and feature rows",
            *(
                [
                    "scripts/01_measure.py --calibrate-null  null_band from "
                    "permutations of the gold, predictions fixed — register it before "
                    "the first run"
                ]
                if kind == standard_contract.APPLY_KIND
                else []
            ),
            f"{probe}; {code_check}.",
            f"{test}: the resolution check as a test (LAB-016 Resolution check before freezing).",
        ]
    return title, [
        f"{protocol}: fill the pilot part (head: type, repeat_cost; {fields}); "
        "`protocol-check --contract` names the labels.",
        f"scripts/00_prepare.py: raw -> prepared   ({rel}/scripts)",
        "scripts/01_measure.py --show 3    read the prompts, no call",
        "scripts/01_measure.py --probe 4   instrument check in the real pipeline; "
        f"its answers as parser cases into {test}; {code_check}.",
        f"{test}: the resolution check as a test (LAB-016 Resolution check before freezing).",
    ]


def _low_steps(
    ln: standard_contract.Lane,
    sk: standard_contract.Skeleton,
    protocol: str,
    fields: str,
    kind: str,
    code_check: str,
    test: str,
) -> tuple[str, list[str]]:
    """(title, steps) of the low cut before its run: fill the cut, prepare
    the data where the skeleton reads prepared rows, fill the script and
    the area test — no freeze, no audit, the run is the instrument check."""
    title = (
        f'repeat_cost = "{ln.repeat_cost}" — no freeze, no audit before the run, '
        "the run is the instrument check"
    )
    if sk is standard_contract.COMPUTE:
        fill = "expected_ids(), rows(), evaluate_rows()"
    elif sk is standard_contract.MODEL:
        fill = "PROMPT, parse_answer(), evaluate_rows(); --show 3, then the run"
    else:
        # the apply null calibrates before its run; at fit the null refits
        calibrate = (
            "--calibrate-null for null_band (register it), "
            if kind == standard_contract.APPLY_KIND
            else ""
        )
        fill = f"{estimator_fill(kind)}; --show 3, {calibrate}then the run"
    prepare = (
        []
        if sk is standard_contract.COMPUTE
        else [
            "scripts/00_prepare.py: raw -> data/prepared/, which 01_measure.py reads"
            + (
                " — gold null for the unlabelled split"
                if sk is standard_contract.ESTIMATOR
                else ""
            )
            + "; run it before the measurement."
        ]
    )
    return title, [
        f"{protocol}: fill the low cut — `type` in the head, then\n"
        f"     {fields}; `protocol-check --contract` names the labels.",
        *prepare,
        f"scripts/01_measure.py: {fill}; {code_check}; {test} on hand-checked cases.",
    ]


def _run_steps(ln: standard_contract.Lane, rel: Path, slug: str) -> list[str]:
    """The freeze where the lane owes it — preflight and its audit, the
    report fields, `frozen = true` — then the commit and the run: in the
    foreground where the lane says so, else detached through `runlog
    start` from the repo root."""
    steps: list[str] = []
    if ln.freeze:
        if standard_contract.PREFLIGHT_AUDIT in ln.audits:
            steps.append(
                f"`preflight {rel}`, then the preflight audit (`labkit-audit {rel} "
                "--mode preflight`) in the background; decide its findings, its "
                "record's name into the head (`preflight_audit`; LAB-015 Preflight "
                "audit before freezing)."
            )
        steps.append(
            f"reportable? `labkit-init exp {slug} --report` adds the report fields; "
            "only now `frozen = true`."
        )
    if ln.foreground:
        steps.append(
            "git add + commit, then scripts/01_measure.py — in the foreground; it is "
            "the instrument check too."
        )
    else:
        # runlog start runs the command in the caller's directory: both paths
        # from the repo root, where every other printed command runs
        steps.append(
            "git add + commit, THEN scripts/01_measure.py, detached, from the repo root: "
            f"`.venv/bin/runlog start {rel} -- .venv/bin/python "
            f"{(rel / 'scripts' / '01_measure.py').as_posix()}` "
            f"(untracked code is in no diff); running processes: .venv/bin/runlog {rel}."
        )
    return steps


def _closing_steps(ln: standard_contract.Lane, rel: Path, protocol: str) -> list[str]:
    """After the run: finalize (with the provenance where the lane owes
    it), the analysis audit where the lane owes it, then the adoption."""
    after = f"`finalize {rel}`" + (
        " checks the provenance (source frozen in the run, tracked in git)"
        if ln.provenance
        else ""
    )
    if standard_contract.ANALYSIS_AUDIT in ln.audits:
        after += (
            f", then the analysis audit (`labkit-audit {rel} --mode analysis`), decided"
        )
    return [
        after + ".",
        f"the Conclusion, then `{adopt_command(rel / protocol)}` adopts the "
        "number: it runs report-check, whose last station is scripts/02_analyze.py "
        "--check; a task's output file is written from that run only after it.",
    ]


# --- command line -------------------------------------------------------------


def main(argv: list[str]) -> int:
    """`labkit-init lab|exp` — see the module docstring."""
    ap = argparse.ArgumentParser(
        prog="labkit-init", description=(__doc__ or "").split("\n\n")[0]
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    lab = sub.add_parser("lab", help="lay out a lab repo")
    lab.add_argument("dir", nargs="?", type=Path, default=Path("."))
    lab.add_argument(
        "--name", help="project name for AGENTS.md (default: the directory's name)"
    )
    lab.add_argument(
        "--labkit-ref",
        help="pin this ref instead of the release tag (a pushed commit, for development)",
    )
    exp = sub.add_parser("exp", help="stamp an experiment area")
    exp.add_argument("name")
    exp.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="the lab repo (default: the nearest directory, here or above, "
        "holding models.toml and experiments/)",
    )
    exp.add_argument(
        "--repeat-cost",
        choices=protocol_block.REPEAT_COSTS,
        help="stamp this repeat cost into the head; low stamps the low cut",
    )
    exp.add_argument(
        "--kind",
        choices=protocol_block.KINDS,
        help="what the kept number asserts, required for a new area (the skeleton "
        f"and the registration follow it). {KIND_QUESTIONS}. A compute with "
        "--model also says what the number describes (number_describes; see the "
        "protocol field guide)",
    )
    exp.add_argument(
        "--model",
        nargs="?",
        const=True,
        default=False,
        metavar="ALIAS",
        help="a model answering through models.toml: writes `[model] alias`; with "
        "--kind apply the prompt skeleton; with --kind compute also "
        "`number_describes` and the `annotation_validity` it may owe",
    )
    exp.add_argument(
        "--report",
        action="store_true",
        help="add the † fields (now, or to an existing area)",
    )
    exp.add_argument(
        "--explore", action="store_true", help="only experiments/explore/<name>.py"
    )
    exp.add_argument(
        "--change-kind",
        action="store_true",
        help="restamp the existing area NAME under --kind before its first "
        "measurement: the stamped scripts, README and test follow the new kind, "
        "the protocol keeps its id and every written field; refused when a run "
        "exists or when it would replace a file you changed",
    )
    a = ap.parse_args(argv)
    if a.cmd == "lab":
        check_lab_pin(a.labkit_ref)
        root = a.dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        log = stamp_lab(root, a.name or root.name, a.labkit_ref)
        print(f"Lab repo -> {root}\n" + "\n".join(log))
        print(
            "\nnext: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/labkit-hooks install"
            " && .venv/bin/pip freeze > requirements.lock  (the lock pins the environment every run records)"
        )
        return 0
    # the nearest lab repo above the working directory, as git finds its
    # repo; the directory itself when none, so stamp_area names what it
    # was asked about (an area directory, cloud judge probe 2026-10-14)
    root = (
        a.repo.resolve()
        if a.repo is not None
        else lab_root(Path.cwd()) or Path.cwd().resolve()
    )
    # before the explore branch returns, or `--explore --change-kind` stamps
    # the explore file and exits 0 (audit 2026-10-27, C13)
    if a.change_kind and (a.repeat_cost or a.model or a.report or a.explore):
        ap.error(
            "--change-kind takes only --kind: the repeat cost, the model and "
            "the report fields come from the protocol, and --explore stamps no area"
        )
    if a.explore and (a.kind or a.repeat_cost or a.model or a.report):
        ap.error(
            "--explore stamps only experiments/explore/<name>.py: --kind, "
            "--repeat-cost, --model and --report belong to the area's stamp, the "
            "step --explore prints next"
        )
    if a.explore:
        print("\n".join(stamp_explore(root / EXPERIMENTS, area_slug(a.name))))
        print(explore_next(area_slug(a.name)))
        return 0
    if a.change_kind:
        _, report = change_kind(root, a.name, a.kind)
        print(report)
        return 0
    _, report = stamp_area(
        root,
        a.name,
        repeat_cost=a.repeat_cost,
        kind=a.kind,
        model=a.model,
        report=a.report,
    )
    print(report)
    return 0


def cli() -> None:
    """Console entry point `labkit-init`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
