"""labkit-init — stamp a lab repo and its experiment areas from the templates that ship with labkit.

    labkit-init lab [DIR] [--name NAME] [--labkit-ref REF]
    labkit-init exp NAME [--repo DIR] [--cost seconds|minutes|hours] [--model [ALIAS]]
                         [--report] [--explore]

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
graduates; `--cost seconds` stamps the seconds cut instead), the script
skeletons (`00_prepare`, `01_measure`, `02_analyze` — with `--model` the
prompt skeleton, without it the estimator skeleton; at seconds without a
model the counting skeleton), the area README and the area's test under
`tests/`. `--explore` stamps only `experiments/explore/<name>.py`, the entry
before an area exists; the plain command later moves it into the area.

Every file is written only if absent: rerunning never overwrites. The pin
names the release tag `v<version>` of the installed labkit; until that tag is
pushed the pin does not install, so `--labkit-ref` names another ref (a pushed
commit) for development and tests.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import re

from labkit.formats import console
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import protocol_block, standard_contract
from labkit.formats.repo import (
    adopt_command,
    AREA_NAME,
    area_protocols,
    git_run,
    lab_root,
    split_area_name,
)
from labkit.tools.repo_check import PYPROJECT_VERSION_RE
from labkit.tools.protocol_cuts import (
    ProtocolBlocks,
    auto_fill_deterministic,
    count_placeholders,
    estimator_placeholders,
    insert_report_fields,
    new_protocol_id,
    pilot_and_report,
    quick_block,
    seconds_cut,
    short_placeholders,
)

TEMPLATES = PACKAGE_DIR / "templates"
PROTOCOL_TEMPLATE = TEMPLATES / "experiment-protocol.md.template"
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

    A count (`skeleton=False`: cost seconds without a model) carries no blank:
    its question and contract live in the protocol, and a README placeholder
    was the one gate line left in the cloud probe (draw 11, 2026-10-13)."""
    question = (
        "**The one question.** <one sentence — the same question as in the protocol's\n"
        'Intent; if it needs an "and", it is two experiments>'
        if skeleton
        else f"**The one question** is the protocol's Question field (`PROTOCOL-{slug}.md`);\n"
        "a count asks one and reports one number."
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
        "`scripts/01_measure.py`; a count registers no ids. The formula lives once, there;\n"
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
`minutes`/`hours`: `preflight` + the preflight audit, then freeze · the run
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


def promote(area: Path, blocks: ProtocolBlocks) -> list[str]:
    """Fill the report-grade fields into an existing area's protocols."""
    protos = area_protocols(area)
    if not protos:
        raise console.Refused("labkit-init", f"no PROTOCOL-*.md in {area}")
    log = []
    for proto in protos:
        text = proto.read_text(encoding="utf-8")
        lane = standard_contract.lane(protocol_block.head(text).cost)
        if not lane.freeze:
            log.append(
                f"  skip (cost {lane.tier}: nothing freezes, no report fields)  {proto}"
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
    """The script skeletons and the area's test under tests/ — which ones
    is the contract's answer (`standard_contract.skeleton`: the count, the
    estimator or the prompt skeleton, every one with the check)."""
    log: list[str] = []
    (area / "scripts").mkdir(exist_ok=True)
    alias = model if isinstance(model, str) else "TODO-alias"
    tname = (f"test_{nn}_{slug}" if nn else f"test_{slug}").replace("-", "_") + ".py"
    for tmpl, dest in skeleton.scripts:
        # `<NN>_<name>` first: the scripts name the area's test file too (the
        # probe's "paste into tests/test_<NN>_<name>.py" stayed unreplaced,
        # cloud judge probe 2026-10-14)
        text = (
            template(tmpl)
            .replace("<NN>_<name>", tname[len("test_") : -3])
            .replace("<name>", slug)
            .replace("<model>", alias)
        )
        if write_if_absent(area / "scripts" / dest, text, log):
            (area / "scripts" / dest).chmod(
                0o755
            )  # a shebang nobody can run is a lint finding
    text = (
        template(skeleton.test)
        .replace("<area>", str(area.relative_to(root)))
        .replace("<NN>_<name>", tname[len("test_") : -3])
        .replace("<name>", slug)
    )
    write_if_absent(root / "tests" / tname, text, log)
    return log


def stamp_area(
    root: Path,
    name: str,
    cost: str | None = None,
    model: bool | str = False,
    report: bool = False,
) -> tuple[Path, str]:
    """Stamp `experiments/NN-<name>/` (or promote it with REPORT): the area
    and the report to print (what was written, then the next steps) — the
    caller prints; `stamp_lab` returns its log the same way."""
    slug = area_slug(name)
    experiments = root / "experiments"
    if not (root / "models.toml").is_file() or not experiments.is_dir():
        raise console.Refused(
            "labkit-init",
            f"{root} is not a lab repo (no models.toml / experiments/) — run `labkit-init lab` first",
        )
    # the cut and the skeleton are the contract's answers, not read off the
    # tier here (a tier compared by hand outside the contract is a copy)
    quick = standard_contract.lane(cost).cut == standard_contract.SECONDS_CUT
    skeleton = standard_contract.skeleton(cost, bool(model))
    tmpl = (
        template(PROTOCOL_TEMPLATE.name)
        .replace("<name>", slug, 1)
        .replace("<protocol-id>", new_protocol_id(root))
    )
    if cost:
        tmpl = tmpl.replace('cost = "<seconds | minutes | hours>"', f'cost = "{cost}"')
    clean = re.sub(
        r" ?<!-- sm? -->", "", tmpl
    )  # every written protocol is free of the cut markers
    pilot, blocks = pilot_and_report(clean)
    if quick:
        pilot, blocks = (
            seconds_cut(quick_block(tmpl, bool(model)), model=bool(model)),
            [],
        )
        if skeleton is standard_contract.COUNT:
            pilot = count_placeholders(pilot)
    elif skeleton is standard_contract.ESTIMATOR:
        pilot = estimator_placeholders(pilot)
    existing = [
        p
        for p in experiments.iterdir()
        if p.is_dir() and split_area_name(p.name)[1] == slug
    ]
    if existing:
        if not report:
            raise console.Refused(
                "labkit-init",
                f"experiment already exists: {existing[0]} (add report fields: --report)",
            )
        return existing[0], "\n".join(promote(existing[0], blocks))
    nn = next_experiment_number(experiments)
    area = experiments / f"{nn}-{slug}"
    log: list[str] = []
    for d in ("data/raw", "data/prepared", "output"):
        write_if_absent(area / d / ".gitkeep", "", log)
    write_if_absent(
        area / "README.md",
        area_readme(nn, slug, skeleton=skeleton is not standard_contract.COUNT),
        log,
    )
    pre = experiments / "explore" / f"{slug}.py"
    if pre.is_file():  # an explore file stamped before the area graduates with it
        (area / "explore").mkdir(exist_ok=True)
        pre.rename(area / "explore" / pre.name)
        log.append(f"  moved          {pre} -> {area / 'explore' / pre.name}")
    write_if_absent(
        area / f"PROTOCOL-{slug}.md",
        # a heading right after a cut item gets its blank line back
        re.sub(
            r"([^\n])\n(## )",
            r"\1\n\n\2",
            short_placeholders(clean if report else pilot),
        ),
        log,
    )
    log += stamp_scripts(root, area, nn, slug, skeleton, model)
    _point_hooks_at(root)
    return area, (
        f"{'Measurement' if quick else 'Experiment'} -> {area}\n"
        + "\n".join(log)
        + "\n"
        + next_steps(area.relative_to(root), slug, nn, cost, bool(model))
    )


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


def next_steps(rel: Path, slug: str, nn: str, cost: str | None, model: bool) -> str:
    """What to do after `exp`, in order — the lane of AGENTS.md for this
    area, read off the contract: the preflight and its audit stand where
    the lane owes the freeze, the analysis audit where the lane owes it,
    the adoption at the end of every lane. Until 2026-10-19 the printed
    steps at minutes/hours skipped the preflight, both audits and the
    adoption while the stamped AGENTS.md named them; an agent following the
    console met the refusal at the run's start."""
    ln = standard_contract.lane(cost)
    sk = standard_contract.skeleton(cost, model)
    protocol = f"PROTOCOL-{slug}.md"
    audit = f"labkit-audit {rel} --mode"
    code_check = f"after every code change `code-check {rel}`"
    if ln.cut == standard_contract.SECONDS_CUT:
        title = (
            f'cost = "{ln.tier}" — no freeze, no audit before the run, '
            "the run is the instrument check"
        )
        fields = (
            "criterion, admissibility condition, prompt, null condition"
            if model
            else "data, exclusions — no criterion, no promise table: a count has no bar to clear"
        )
        fill = (
            "PROMPT, parse_answer(), evaluate_rows(); --show 2, then the run"
            if model
            else "expected_ids(), rows(), evaluate_rows()"
        )
        steps = [
            f"{protocol}: fill the seconds cut — `type` in the head, then question, unit,\n"
            f"     {fields}; `protocol-check --contract` names the labels.",
            f"scripts/01_measure.py: {fill}; {code_check}.",
        ]
    else:
        test = f"tests/test_{nn}_{slug.replace('-', '_')}.py"
        estimator = sk is standard_contract.ESTIMATOR
        title = f"lane {ln.tier}: light pilot, heavy report" + (
            " — the instrument is an estimator, no model call" if estimator else ""
        )
        steps = [
            f"{protocol}: fill the pilot part (head: type, cost; question, success, "
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
                "in the background; decide its findings, the `scope sha` line into "
                "the head (LAB-015 Preflight audit before freezing)."
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
        "--cost",
        choices=protocol_block.COST_TIERS,
        help="stamp this tier into the head; seconds stamps the seconds cut",
    )
    exp.add_argument(
        "--model",
        nargs="?",
        const=True,
        default=False,
        metavar="ALIAS",
        help="a model in the loop (without it, minutes/hours stamp the estimator skeleton)",
    )
    exp.add_argument(
        "--report",
        action="store_true",
        help="add the † fields (now, or to an existing area)",
    )
    exp.add_argument(
        "--explore", action="store_true", help="only experiments/explore/<name>.py"
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
    if a.explore:
        print("\n".join(stamp_explore(root / "experiments", area_slug(a.name))))
        print(
            f"\nNext: fill the cells, read the render, look at real output; when it holds, `labkit-init exp {area_slug(a.name)}`."
        )
        return 0
    _, report = stamp_area(root, a.name, cost=a.cost, model=a.model, report=a.report)
    print(report)
    return 0


def cli() -> None:
    """Console entry point `labkit-init`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
