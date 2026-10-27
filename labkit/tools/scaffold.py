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
skeletons (`00_prepare`, `01_measure`, `02_analyze` — with `--model` the
prompt skeleton, without it the estimator skeleton; at low repeat cost without a
model the counting skeleton), the area README and the area's test under
`tests/`. `--explore` stamps only `experiments/explore/<name>.py`, the entry
before an area exists; the plain command later moves it into the area.
`--change-kind` restamps an area under another kind before its first
measurement (`change_kind`).

Every file is written only if absent: rerunning never overwrites. The pin
names the release tag `v<version>` of the installed labkit; until that tag is
pushed the pin does not install, so `--labkit-ref` names another ref (a pushed
commit) for development and tests.
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
from labkit.formats.runs import runs_path
from labkit.tools.protocol_fill import fill, fill_head
from labkit.formats.repo import (
    added_in,
    adopt_command,
    AREA_NAME,
    area_protocols,
    git_root,
    git_run,
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
LAB_DIRS = (
    "experiments",
    "data/raw",
    "data/prepared",
    "lib",
    "notes/theorie",
    "notes/messung",
    "notes/results",
)


def write_if_absent(path: Path, content: str, log: list[str]) -> bool:
    """Write CONTENT to PATH unless it exists; log either way. True when written."""
    if path.exists() or path.is_symlink():
        log.append(f"  skip (exists)  {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
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


def labkit_pin(ref: str | None = None) -> str:
    """The requirements line pinning labkit: the release tag of the installed
    version on GitHub, or REF when given (a pushed commit, for development).

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
    return f"labkit @ git+{LABKIT_REMOTE}@{ref or 'v' + version}"


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


def area_readme(nn: str, slug: str, skeleton: bool) -> str:
    """The area README: the one question, the route through the area, the contract on one page.

    A computation (`skeleton=False`: repeat cost low without a model) carries no blank:
    its question and contract live in the protocol, and a README placeholder
    was the one gate line left in the cloud probe (draw 11, 2026-10-13)."""
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
        "`02_analyze.py --check` and the test call it, and `finalize` holds the protocol's\n"
        "Answer line to the run's `metrics.json`."
    )
    recheck = "`02_analyze.py --check`"  # the one public recheck of every skeleton
    return f"""# Experiment {nn}: {slug}

*Self-contained: data, scripts, output and this description live here.*

{question}

<!-- labkit:route -->
**Trace it.**
- Contract and reported answer: `PROTOCOL-{slug}.md`
- Runs and provenance: `runlog .`
- Effective values: `labkit-params .`
- Where the ids are decided: `scripts/01_measure.py:evaluate_rows`
- Immutable record: `config.json` of the chosen run under `runs/`
<!-- /labkit:route -->

## Contract

{returns}

**The gates, in order.** `code-check` after every code change · at
`high`: `preflight` + the preflight audit, then freeze · the run
through `runlog` · `finalize` · `protocol-fill --from-run` writes the number back · {recheck}.

## State

- [ ] Registration written in the protocol (**before** the first run)
{"- [ ] `--probe` read, parser cases in the test" if skeleton else "- [ ] the area test green (`.venv/bin/python -m pytest tests/test_" + nn + "_" + slug.replace("-", "_") + ".py`)"}
- [ ] Run, `protocol-fill --from-run`, `finalize` green
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
    without `--kind` is refused (`asked_kind`)."""
    commands = "\n".join(
        f"  labkit-init exp {slug} --kind {kind}" for kind in protocol_block.KINDS
    )
    return (
        "\nNext: fill the cells, read the render, look at real output; when it "
        "holds, stamp the area under the kind its kept number asserts — one of\n"
        f"{commands}\n"
        f"{KIND_QUESTIONS}. With a model answering in the area add --model ALIAS "
        "(the explore file's MODEL)."
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
        proto.write_text(new, encoding="utf-8")
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
    is refused — nothing falls back to a computation (standard 0.22)."""
    slug = area_slug(name)
    experiments = root / "experiments"
    if not (root / "models.toml").is_file() or not experiments.is_dir():
        raise console.Refused(
            "labkit-init",
            f"{root} is not a lab repo (no models.toml / experiments/) — run `labkit-init lab` first",
        )
    existing = [
        p
        for p in experiments.iterdir()
        if p.is_dir() and split_area_name(p.name)[1] == slug
    ]
    if existing and report:
        _, blocks = pilot_and_report(CUT_MARK.sub("", template(PROTOCOL_TEMPLATE.name)))
        return existing[0], "\n".join(promote(existing[0], blocks))
    kind = asked_kind(kind)
    quick = standard_contract.lane(repeat_cost).cut == standard_contract.LOW_CUT
    skeleton = standard_contract.skeleton(repeat_cost, kind, bool(model))
    stamped = protocol_stamp(root, slug, repeat_cost, kind, model, report)
    existing = [
        p
        for p in experiments.iterdir()
        if p.is_dir() and split_area_name(p.name)[1] == slug
    ]
    if existing:
        raise console.Refused(
            "labkit-init",
            f"experiment already exists: {existing[0]} (add report fields: --report)",
        )
    nn = next_experiment_number(experiments)
    area = experiments / f"{nn}-{slug}"
    log: list[str] = []
    for d in ("data/raw", "data/prepared", "output"):
        write_if_absent(area / d / ".gitkeep", "", log)
    write_if_absent(
        area / "README.md",
        area_readme(nn, slug, skeleton=skeleton is not standard_contract.COMPUTE),
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
            pilot = estimator_placeholders(pilot, cut=True)
    elif skeleton is standard_contract.ESTIMATOR:
        pilot = estimator_placeholders(pilot)
    stamped = blank_before_headings(short_placeholders(clean if report else pilot))
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
    area = restampable_area(root, slug, kind)
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


def restampable_area(root: Path, slug: str, kind: str) -> Path:
    """The area of SLUG under ROOT that `--change-kind` may restamp: it
    exists, holds its one stamped protocol and has not measured. Raises
    `console.Refused` otherwise — after a run the kind is part of the
    registration the first measurement stood on
    (`report_check.registration_gaps`), so the way is a new registration."""
    experiments = root / "experiments"
    found = (
        [
            p
            for p in experiments.iterdir()
            if p.is_dir() and split_area_name(p.name)[1] == slug
        ]
        if experiments.is_dir()
        else []
    )
    if not found:
        raise console.Refused(
            "labkit-init",
            f"--change-kind: no area {slug!r} under {experiments} — "
            f"`labkit-init exp {slug} --kind {kind}` stamps a new one",
        )
    area = found[0]
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
        else:
            held.append(f"{path}: edited since the {kind} stamp")
    return held, earlier


def earlier_pin_text(root: Path, path: Path) -> tuple[str, str] | None:
    """(commit, text): PATH as the newest commit that added it holds it,
    when a pin file under ROOT (`repo_check.PIN_FILES`) names another
    labkit then than now (its `labkit` lines): the evidence that this
    labkit's templates are not the ones PATH was stamped from, so a
    difference from today's stamp shows no edit. None without that
    evidence: outside a git repo, PATH never committed, or no pin file
    with a labkit line both then and now that differs. Limit: an edit
    committed together with the stamp, under the earlier pin, reads as
    that pin's stamp — the commit keeps it. Reads git and the pin files,
    writes nothing; raises RuntimeError when git fails."""
    repo = git_root(root)
    if repo is None:
        return None
    commit = added_in(repo, path)
    if commit is None:
        return None
    for name in PIN_FILES:
        pins = root / name
        then = requirement_lines(text_at(repo, pins, commit) or "", "labkit")
        now = (
            requirement_lines(pins.read_text(encoding="utf-8"), "labkit")
            if pins.is_file()
            else []
        )
        if then and now and then != now:
            text = text_at(repo, path, commit)
            return None if text is None else (commit, text)
    return None


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
        nn, slug, skeleton=skeleton is not standard_contract.COMPUTE
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
    stamp, write the new kind's (scripts executable), write the protocol.
    Returns the log lines; one replaced on the evidence of an earlier pin
    names the commit that keeps it (`KindChange.earlier`)."""

    def earlier(path: Path) -> str:
        """` of an earlier pin, as committed in <commit>` for a PATH
        replaced on that evidence, else ""."""
        commit = plan.earlier.get(path)
        return f" of an earlier pin, as committed in {commit[:12]}" if commit else ""

    log: list[str] = []
    for path in plan.before:
        if path.is_file() and path not in plan.after:
            path.unlink()
            log.append(
                f"  removed        {path} (the {plan.old_kind} stamp{earlier(path)})"
            )
    for path, text in plan.after.items():
        replaced = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if path.parent == area / "scripts":
            path.chmod(0o755)  # a shebang nobody can run is a lint finding
        log.append(
            f"  {'replaced' if replaced else 'created':<14} {path}"
            + (f" (the stamp{earlier(path)})" if path in plan.earlier else "")
        )
    plan.protocol.write_text(plan.text, encoding="utf-8")
    log.append(
        f"  restamped      {plan.protocol} (same id, written fields kept"
        + (
            f"; the promise block{earlier(plan.protocol)} replaced"
            if plan.protocol in plan.earlier
            else ""
        )
        + ")"
    )
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
    if not ((root / ".git").exists() and (root / ".githooks").is_dir()):
        return
    r = git_run(["config", "core.hooksPath", ".githooks"], root)
    if r.returncode != 0:
        raise console.Refused(
            "labkit-init", f"git config core.hooksPath failed: {r.stderr.strip()}"
        )


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
    "(a threshold or prompt chosen on performance data counts)? yes: fit — also "
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


def next_steps(
    rel: Path, slug: str, nn: str, repeat_cost: str | None, kind: str, model: bool
) -> str:
    """What to do after `exp`, in order — the lane of AGENTS.md for this
    area, read off the contract: the preflight and its audit stand where
    the lane owes the freeze, the analysis audit where the lane owes it,
    the adoption at the end of every lane. Until 2026-10-19 the printed
    steps at high repeat cost skipped the preflight, both audits and the
    adoption while the stamped AGENTS.md named them; an agent following the
    console met the refusal at the run's start."""
    ln = standard_contract.lane(repeat_cost)
    sk = standard_contract.skeleton(repeat_cost, kind, model)
    protocol = f"PROTOCOL-{slug}.md"
    audit = f"labkit-audit {rel} --mode"
    code_check = f"after every code change `code-check {rel}`"
    if ln.cut == standard_contract.LOW_CUT:
        title = (
            f'repeat_cost = "{ln.repeat_cost}" — no freeze, no audit before the run, '
            "the run is the instrument check"
        )
        if sk is standard_contract.COMPUTE:
            fields = (
                "data, exclusions — no criterion, no promise table: a computation "
                "judges no prediction, so it has no bar to clear"
            )
            fill = "expected_ids(), rows(), evaluate_rows()"
        elif sk is standard_contract.MODEL:
            fields = "criterion, admissibility condition, prompt, null condition, data profile"
            fill = "PROMPT, parse_answer(), evaluate_rows(); --show 2, then the run"
        else:
            fields = (
                f"criterion, admissibility condition, null condition — kind = {kind!r}: "
                "the number judges a prediction, so it has a bar and its reference"
            )
            fill = "make_estimator(), SCORE, FEATURES_FIELD; --show 3, then the run"
        steps = [
            f"{protocol}: fill the low cut — `type` in the head, then question, unit,\n"
            f"     {fields}; `protocol-check --contract` names the labels.",
            f"scripts/01_measure.py: {fill}; {code_check}.",
        ]
    else:
        test = f"tests/test_{nn}_{slug.replace('-', '_')}.py"
        estimator = sk is standard_contract.ESTIMATOR
        title = f"lane {ln.repeat_cost}: light pilot, heavy report" + (
            " — the instrument is an estimator, no model call" if estimator else ""
        )
        steps = [
            f"{protocol}: fill the pilot part (head: type, repeat_cost; question, success, "
            f"admissibility, {'the estimator in Model / tool' if estimator else 'prompt'}, "
            "the null condition).",
            "scripts/00_prepare.py: raw -> prepared"
            + (", gold null for the unlabelled split" if estimator else "")
            + f"   ({rel}/scripts)",
            "scripts/01_measure.py: make_estimator(), SCORE, FEATURES_FIELD; --show 3 "
            "reads the config and feature rows"
            if estimator
            else "scripts/01_measure.py --show 3    read the prompts, no call",
            (
                "scripts/01_measure.py --probe 12  instrument check: a reduced estimator, "
                "both lanes, throwaway; the rows into the protocol's raw output"
                if estimator
                else "scripts/01_measure.py --probe 4   instrument check in the real "
                f"pipeline; raw answers into {test}"
            )
            + f"; {code_check}.",
            f"{test}: the resolution check as a test (LAB-016 Resolution check before freezing).",
        ]
    if ln.freeze:
        if standard_contract.PREFLIGHT_AUDIT in ln.audits:
            steps.append(
                f"`preflight {rel}`, then the preflight audit (`{audit} preflight`) "
                "in the background; decide its findings, its record's name into the "
                "head (`preflight_audit`; LAB-015 Preflight audit before freezing)."
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
        steps.append(
            "git add + commit, THEN scripts/01_measure.py, detached: "
            f"`runlog start {rel} -- .venv/bin/python scripts/01_measure.py` "
            f"(untracked code is in no diff); running processes: .venv/bin/runlog {rel}."
        )
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
    after = f"`finalize {rel}`" + (
        " checks the provenance (source frozen in the run, tracked in git)"
        if ln.provenance
        else ""
    )
    if standard_contract.ANALYSIS_AUDIT in ln.audits:
        after += f", then the analysis audit (`{audit} analysis`), decided"
    steps.append(after + ".")
    steps.append(
        f"`{adopt_command(rel / protocol)}` adopts the number: it runs "
        "report-check, whose last station is scripts/02_analyze.py --check."
    )
    return f"\nNext ({title}):\n" + "\n".join(
        f"  {i}. {step}" for i, step in enumerate(steps, 1)
    )


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
        root = a.dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        log = stamp_lab(root, a.name or root.name, a.labkit_ref)
        print(f"Lab repo -> {root}\n" + "\n".join(log))
        print(
            "\nnext: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/labkit-hooks install"
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
    if a.explore:
        print("\n".join(stamp_explore(root / "experiments", area_slug(a.name))))
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
