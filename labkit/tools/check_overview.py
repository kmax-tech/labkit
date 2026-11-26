"""check_overview — one checked-in page of every finding site: what it
tells, under which rule, and which test files reach it.

    python -m labkit.tools.check_overview [--check]

Writes `docs/checks-overview.md` of the checkout labkit is installed from,
or with `--check` compares the file with what it would write and exits 1
on a difference. The page has two sources and adds nothing to them:

  - the source, scanned now (`check_inventory.finding_sites`): each site's
    function, channel, grade, evidence kind, recorded rule and the constant
    text of its message; and the commands whose code reaches a module's
    sites (`check_inventory.reaching_commands`, a static estimate)
  - `docs/checks-reach.tsv`, written by the last traced run of the suite
    (`python -m labkit.tools.test_inventory --reach docs/checks-reach.tsv`):
    per site its standing, the number of tests that reached it, how many
    of them carry the mark `rule`, and their test files

A site is known across the two by `test_inventory.SiteKey` — its function, channel and
message text, never a line number —, so the page changes only when a site,
its message or its reach changes (the key's limits: `SiteKey` — a message
is compared as the scan cuts it). A site added or reworded since the
traced run reads `not in the last trace`; a row of the trace no site
stands for any more is left out, and the head counts both.

Its limits, which the page repeats: the message text is the site's own
wording, not the name of the condition it checks — which condition a site
holds, and whether a test asserts it, is established by reading; reaching
a site is not asserting it; the trace's limits are `test_inventory`'s.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console
from labkit.formats.rules import load_ledger, rule_heads
from labkit.tools import test_inventory
from labkit.tools.check_inventory import (
    FindingSite,
    call_graph,
    entry_points,
    finding_sites,
    read_modules,
    reaching_commands,
)

USAGE = "usage: python -m labkit.tools.check_overview [--check]"
#: the page and the trace's reach, relative to the checkout
OVERVIEW = Path("docs") / "checks-overview.md"
REACH = Path("docs") / "checks-reach.tsv"
#: the code standard, whose heads name the `CODE-nnn` rules a site records
CODE_STANDARD = Path("docs") / "coding-style.md"
#: what the page says of a site the reach file holds no row for
NOT_IN_TRACE = "not in the last trace"
#: what it says of a site of the `printed` channel, which no run traces
NEVER_TRACED = "not traced (printed line)"


def _cell(text: str) -> str:
    """TEXT for a table cell; `—` for an empty one."""
    return text or "—"


def render_overview(
    sites: list[FindingSite],
    commands: dict[str, set[str]],
    rule_names: dict[str, str],
    reach: test_inventory.TracedReach,
) -> str:
    """The page as markdown: the head with its counts and limits, the
    commands with the modules whose sites their code reaches, then per
    module one row per site of SITES by line. COMMANDS maps a unit
    to the commands that reach it, RULE_NAMES a rule id to its title. Pure."""
    keys = test_inventory.site_keys(sites)
    known = set(keys.values())
    untraced = [s for s in sites if s.channel == "printed"]
    missing = [
        s
        for s in sites
        if s.channel != "printed"
        and keys[(s.path, s.line, s.channel)] not in reach.by_site
    ]
    gone = [k for k in reach.by_site if k not in known]
    by_channel = Counter(s.channel for s in sites)
    out = [
        "# Checks overview — what each finding site tells, its rule, and the tests that reach it",
        "",
        "Generated, do not edit: `python -m labkit.tools.check_overview` writes "
        "this page from the source and from `docs/checks-reach.tsv`, and "
        "`tests/test_check_overview.py` holds it equal to what the command "
        "writes. After a change to a finding site run the command again; the "
        "reach columns change only with a traced run of the suite "
        "(`python -m labkit.tools.test_inventory --reach docs/checks-reach.tsv`).",
        "",
        f"{len(sites)} finding sites: {by_channel['finding']} gate findings, "
        f"{by_channel['exit']} exits (`raise SystemExit(<message>)`), "
        f"{by_channel['printed']} printed lines. Reach as traced: {reach.run}. "
        f"{len(missing)} sites are not in that trace (added or reworded since, "
        f"or the reach file holds no row yet), "
        f"{len(gone)} rows of the trace name a site that is gone and are left "
        f"out, the {len(untraced)} printed lines are never traced.",
        "",
        "How to read it. *Tells* is the constant text of the site's message, "
        "every value as `{…}` — the site's own words, not the name of the "
        "condition it checks; which condition a site holds, and whether a "
        "test asserts it, is established by reading the code and the test. "
        "*Rule* is the rule assignment the finding records as data; an exit "
        "and a printed line record none. *Reached*: `direct` — some test "
        "entered below a whole command; `only through commands`; `unreached`. "
        "Reaching a site is not asserting it. *Rule tests* counts the tests "
        "marked `rule` among those that reach the site. The commands of a "
        "module are a static estimate (a call graph by name), not a trace. "
        "Line numbers are left out on purpose: "
        "`python -m labkit.tools.check_inventory` prints them.",
        "",
        "## Commands and the modules whose sites their code reaches",
        "",
        "| Command | Modules (sites) |",
        "|---|---|",
    ]
    per_command: dict[str, Counter[str]] = defaultdict(Counter)
    for s in sites:
        for command in commands.get(s.unit, ()):
            per_command[command][s.path] += 1
    for command in sorted(per_command):
        modules = ", ".join(
            f"`{path}` ({n})" for path, n in sorted(per_command[command].items())
        )
        out.append(f"| `{command}` | {modules} |")
    by_module: dict[str, list[FindingSite]] = defaultdict(list)
    for s in sites:
        by_module[s.path].append(s)
    for path in sorted(by_module):
        out += [
            "",
            f"## `{path}`",
            "",
            "| Function | Tells | Channel | Grade | Evidence kind | Rule | Reached | Tests | Rule tests | Test files |",  # noqa: E501 one table header line
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for s in sorted(by_module[path], key=lambda s: (s.line, s.channel)):
            found = reach.by_site.get(keys[(s.path, s.line, s.channel)])
            if found is None:
                standing = NEVER_TRACED if s.channel == "printed" else NOT_IN_TRACE
                counts, files = "— | —", "—"
            else:
                standing = found.standing
                counts = f"{found.tests} | {found.rule_tests}"
                files = _cell(", ".join(f"`{f}`" for f in found.files))
            rule = s.assignment
            if rule in rule_names:
                rule = f"{rule} {rule_names[rule]}"
            function = s.unit.removeprefix("labkit.").split(".", 2)[-1]
            out.append(
                f"| `{function}` | {_cell(s.wording)} | {s.channel} | {s.grade} | "
                f"{s.evidence_kind} | {rule} | {standing} | {counts} | {files} |"
            )
    return "\n".join(out) + "\n"


def overview(package_dir: Path, reach_text: str, reach_name: str) -> str:
    """The page for the package at PACKAGE_DIR from its sources, its
    ledger, the `pyproject.toml` and the code standard beside it and the
    reach file's
    REACH_TEXT (called REACH_NAME in an error).

    Raises:
        ValueError: The reach file does not read (`read_reach`).
    """
    modules = read_modules(package_dir)
    pyproject = (package_dir.parent / "pyproject.toml").read_text(encoding="utf-8")
    # a rule is cited with its name: the standard's from its ledger, the
    # code standard's (`CODE-nnn`) from the heads of its text
    names = {r.id: r.title for r in load_ledger(package_dir / "docs" / "rules.tsv")}
    code_standard = package_dir.parent / CODE_STANDARD
    names |= {
        h.id: h.title for h in rule_heads(code_standard.read_text(encoding="utf-8"))
    }
    return render_overview(
        finding_sites(modules),
        reaching_commands(call_graph(modules), entry_points(pyproject)),
        names,
        test_inventory.read_reach(reach_text, reach_name),
    )


def write_or_compare(
    tool: str, page: Path, text: str, *, check: bool, sources: str
) -> int:
    """Write the generated page PAGE (relative to the checkout) as TEXT, or
    with CHECK compare the file with TEXT: 0, or 1 when the page on disk is
    not TEXT. TOOL is the module that generates the page, named in every
    line and as the command that writes it anew; SOURCES says what the
    page follows from (`the source gives`).

    Side effects:
        Without CHECK, creates or overwrites PAGE in the checkout; prints
        one line, on a difference to stderr.
    """
    file = PACKAGE_DIR.parent / page
    if check:
        if file.is_file() and file.read_text(encoding="utf-8") == text:
            print(f"{tool}: {page} is current")
            return 0
        print(
            f"{tool}: {page} is not what {sources} — write it anew: "
            f"python -m labkit.tools.{tool}",
            file=sys.stderr,
        )
        return 1
    file.write_text(text, encoding="utf-8")
    print(f"{tool}: wrote {page}")
    return 0


def main(argv: list[str]) -> int:
    """Write the page, or with `--check` compare it: 0, or 1 when the page
    on disk is not what would be written.

    Side effects:
        Without `--check`, creates or overwrites `docs/checks-overview.md`
        of the checkout.
    """
    if argv in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    if argv not in ([], ["--check"]):
        raise console.Refused("check_overview", USAGE)
    repo = PACKAGE_DIR.parent
    reach_file = repo / REACH
    if not reach_file.is_file():
        raise console.Refused(
            "check_overview",
            f"{reach_file}: no reach file — labkit's own checkout holds one; "
            f"a traced run writes it "
            f"(`python -m labkit.tools.test_inventory --reach {REACH}`)",
        )
    try:
        text = overview(PACKAGE_DIR, reach_file.read_text(encoding="utf-8"), str(REACH))
    except ValueError as exc:
        raise console.Refused("check_overview", str(exc)) from exc
    return write_or_compare(
        "check_overview",
        OVERVIEW,
        text,
        check=argv == ["--check"],
        sources=f"the source and {REACH} give",
    )


def cli() -> None:
    """Console entry: `main` with the process's arguments."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
