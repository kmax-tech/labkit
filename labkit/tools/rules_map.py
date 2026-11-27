"""rules_map — one checked-in page of the lab standard's rules and the code
that holds them: per rule the finding sites that record it, what each does
when its condition holds, and where the rule is written down; then the
sites whose basis is a technical contract, and those whose basis is not
settled.

    python -m labkit.tools.rules_map [--check]

Writes `docs/rules-map.md` of the checkout labkit is installed from, or with
`--check` compares the file with what it would write and exits 1 on a
difference. The page adds nothing to its sources:

  - the source, scanned now (`check_inventory.finding_sites`): each site's
    function, file, grade, evidence kind, recorded rule assignment, outcome
    and message; the places that name an open assignment for a site to
    receive (`check_inventory.open_causes`); the gate stations whose own
    code or called functions hold the site (`gate_stations.stations_told`,
    the part "at this station", not the static estimate "further down")
  - the ledger's active rules and the shipped texts and code strings that
    cite each (`check_inventory.rule_uses`)
  - `docs/chain.md`: the sections whose **Where:** line names a site's
    function
  - `docs/checks-reach.tsv`: per site the tests that reached it in the last
    traced run of the suite
  - `docs/rule-gaps.tsv`: the known gaps between a rule's text and the code
    that records the rule, one row each — the one hand-written source; a
    row is refused when its rule is no active rule, its quotation does not
    stand in the rule's text, or its function records no site with that
    rule (where the task is kept is not checked)

What the page claims, and what not, as it repeats: an assignment says the
rule concerns the case the site holds, not that the code holds all of the
rule's text. A rule no site records is listed as such: nothing follows
about an agent audit checking it or a tool ruling it out; a shipped text
citing the rule is named, not what it asks. Line numbers are left out, so
the page changes when a site, its message or its reach changes, not when
code above it moves (`python -m labkit.tools.check_inventory` prints them).
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console
from labkit.formats.gate import NEW_CLASS, OPEN_ASSIGNMENT, TECHNICAL_CONTRACT
from labkit.formats.rules import LEDGER_NAME, load_ledger, rule_text
from labkit.tools import test_inventory
from labkit.tools.check_inventory import (
    NOT_RECORDED,
    RULE_ID,
    VARIABLE,
    FindingSite,
    OpenCause,
    RuleUse,
    active_rules,
    call_graph,
    finding_sites,
    open_causes,
    read_modules,
    rule_names,
    rule_uses,
    shipped_texts,
)
from labkit.tools.check_overview import REACH, write_or_compare
from labkit.tools.gate_stations import (
    Gate,
    StationSites,
    station_label,
    stations_told,
)

USAGE = "usage: python -m labkit.tools.rules_map [--check]"
#: the page and its two sources beside the reach file, relative to the checkout
RULES_MAP = Path("docs") / "rules-map.md"
CHAIN = Path("docs") / "chain.md"
GAPS = Path("docs") / "rule-gaps.tsv"
#: the columns of the gaps file, in order
GAP_COLUMNS = ("rule", "function", "the rule's text", "the code", "recorded")
#: how a station that reaches a site only further down the call graph is marked
FURTHER = "(further down)"
#: the most test files a row names; more are counted and left to the checks overview
MAX_FILES = 6
#: what the page says of a rule no finding site records
NO_SITE = "no finding site records it — no mechanical check evidenced"
#: a section of the chain and the line that names its functions
CHAIN_SECTION = re.compile(r"^## (.+)$")
CHAIN_WHERE = re.compile(r"^- \*\*Where:\*\* (.+)$")
CODE_SPAN = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class RuleGap:
    """One known gap between a rule's text and the code that records it
    (a row of `docs/rule-gaps.tsv`): RULE its id, FUNCTION the site's unit
    without `labkit.`, TEXT what the rule's text asks, CODE what the code
    does, RECORDED where the gap is kept as a task."""

    rule: str
    function: str
    text: str
    code: str
    recorded: str


def quoted_in(quote: str, rule: str) -> bool:
    """Does QUOTE, a quotation in double quotes with `…` for what it
    leaves out, stand in RULE's text — each part, in order, whitespace
    taken as one space? Pure."""
    flat = " ".join(rule.split())
    at = 0
    for part in quote.strip().strip('"').split("…"):
        part = " ".join(part.split())
        found = flat.find(part, at)
        if found < 0:
            return False
        at = found + len(part)
    return True


def read_gaps(
    text: str, name: str, sites: list[FindingSite], rule_texts: dict[str, str]
) -> list[RuleGap]:
    """The rows of a gaps file's TEXT (called NAME in an error), tab
    separated, with the header GAP_COLUMNS. RULE_TEXTS maps each active
    rule to its text in the standard. Raises ValueError on another header,
    a row of another width, an empty cell, a rule that is not active, a
    quotation that does not stand in that rule's text (`quoted_in`), or a
    function that records no site of SITES with that rule — the row would
    describe code or text that is not there. Where the task is kept
    (`recorded`) is not checked."""
    # a cell is taken as written: quotes in it are the rule's own quotation
    rows = list(csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE))
    if not rows or tuple(rows[0]) != GAP_COLUMNS:
        raise ValueError(f"{name}: the header must be {', '.join(GAP_COLUMNS)}")
    recorded = {(s.unit.removeprefix("labkit."), s.assignment) for s in sites}
    out = []
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != len(GAP_COLUMNS) or not all(c.strip() for c in row):
            raise ValueError(
                f"{name}:{n}: {len(GAP_COLUMNS)} non-empty cells expected, got {row!r}"
            )
        gap = RuleGap(*row)
        if gap.rule not in rule_texts:
            raise ValueError(f"{name}:{n}: {gap.rule} is no active rule")
        if not quoted_in(gap.text, rule_texts[gap.rule]):
            raise ValueError(
                f"{name}:{n}: {gap.text} does not stand in {gap.rule}'s text"
            )
        if (gap.function, gap.rule) not in recorded:
            raise ValueError(
                f"{name}:{n}: no finding site in {gap.function} records "
                f"{gap.rule} — remove the row, or name the function that does"
            )
        out.append(gap)
    return out


def chain_sections(text: str) -> dict[str, tuple[str, ...]]:
    """Each section heading of `docs/chain.md`'s TEXT → the names in its
    **Where:** line, in their order (a section without one names none).
    Pure."""
    out: dict[str, tuple[str, ...]] = {}
    heading = None
    for line in text.splitlines():
        if m := CHAIN_SECTION.match(line):
            heading = m.group(1)
            out[heading] = ()
        elif heading is not None and (m := CHAIN_WHERE.match(line)):
            out[heading] = tuple(CODE_SPAN.findall(m.group(1)))
    return out


def chain_headings(units: set[str], sections: dict[str, tuple[str, ...]]) -> list[str]:
    """The headings of SECTIONS whose **Where:** line names one of UNITS —
    a name matches a unit it ends (`code_check.promise_block_findings`
    matches `labkit.checks.code_check.promise_block_findings`). Pure."""
    return [
        heading
        for heading, names in sections.items()
        if any(u == n or u.endswith(f".{n}") for u in units for n in names)
    ]


def site_stations(
    found: list[Gate], told: dict[tuple[str, int], StationSites]
) -> dict[tuple[str, int, str], list[str]]:
    """(path, line, channel) of a site → the stations (`station_label`)
    that can tell it, in the gates' order: a station whose own code or
    called functions hold the site by its label, one that reaches it
    further down the call graph — a static estimate — by its label and
    FURTHER. FOUND and TOLD as `gate_stations.stations_told` returns them.
    Pure."""
    out: dict[tuple[str, int, str], list[str]] = defaultdict(list)
    for g in found:
        for st in g.stations:
            t = told[(g.unit, st.line)]
            label = station_label(g, st)
            here = {(s.path, s.line, s.channel) for s in (*t.own, *t.called_sites)}
            for s in (*t.own, *t.called_sites, *t.further):
                key = (s.path, s.line, s.channel)
                shown = label if key in here else f"{label} {FURTHER}"
                if label not in out[key] and shown not in out[key]:
                    out[key].append(shown)
    return out


def _cell(text: str) -> str:
    """TEXT for a table cell, its pipes escaped; `—` for an empty one."""
    return text.replace("|", "\\|") if text else "—"


def _function(s: FindingSite) -> str:
    """The site's unit without the package and layer."""
    return s.unit.removeprefix("labkit.").split(".", 1)[-1]


@dataclass(frozen=True)
class PageInputs:
    """What the page is rendered from, each as its source gives it.

    Attributes:
        uses: Every active rule with the sites and texts citing it
            (`rule_uses`).
        sites: Every finding site (`finding_sites`).
        stations: A site's (path, line, channel) → its stations
            (`site_stations`).
        reach: The last traced run's reach (`test_inventory.read_reach`).
        chain: `docs/chain.md`'s sections (`chain_sections`).
        gaps: The known gaps (`read_gaps`).
        causes: The places naming an open assignment a site receives
            (`open_causes`).
        names: Rule id → its name (`rule_names`).
    """

    uses: list[RuleUse]
    sites: list[FindingSite]
    stations: dict[tuple[str, int, str], list[str]]
    reach: test_inventory.TracedReach
    chain: dict[str, tuple[str, ...]]
    gaps: list[RuleGap]
    causes: list[OpenCause]
    names: dict[str, str]


SITE_HEADER = [
    "| Function | File | Grade | Evidence kind | Outcome | Stations (static estimate) | Tests that reached it | Tells |",  # noqa: E501 one table header line
    "|---|---|---|---|---|---|---|---|",
]


def _site_rows(sites: list[FindingSite], inputs: PageInputs) -> list[str]:
    """The table of SITES, by file and line: function, file, grade,
    evidence kind, outcome, stations, the tests that reached it, message."""
    keys = test_inventory.site_keys(inputs.sites)
    out = list(SITE_HEADER)
    for s in sorted(sites, key=lambda s: (s.path, s.line, s.channel)):
        found = inputs.reach.by_site.get(keys[(s.path, s.line, s.channel)])
        if s.channel == "printed":
            tests = "not traced (printed line)"
        elif found is None:
            tests = "not in the last trace"
        else:
            files = (
                ", ".join(f"`{f}`" for f in found.files)
                if len(found.files) <= MAX_FILES
                else f"{len(found.files)} files, [checks overview](checks-overview.md)"
            )
            tests = f"{found.tests} ({found.rule_tests} marked rule)" + (
                f": {files}" if found.files else ""
            )
        stations = ", ".join(inputs.stations.get((s.path, s.line, s.channel), []))
        out.append(
            f"| `{_function(s)}` | `{s.path}` | {s.grade} | {s.evidence_kind} | "
            f"{s.outcome} | {_cell(stations)} | {tests} | {_cell(s.wording)} |"
        )
    return out


def _written_down(
    use: RuleUse, units: set[str], chain: dict[str, tuple[str, ...]]
) -> list[str]:
    """Where USE's rule is written down beside the standard: the chain's
    sections naming one of UNITS, the shipped texts and the code strings
    citing it — each a bullet, `—` where there is none."""
    headings = chain_headings(units, chain)
    return [
        "- The rule: `labkit/docs/standard.md`.",
        "- The chain (`docs/chain.md`), sections naming a function of its sites: "
        + (", ".join(f"*{h}*" for h in headings) or "—")
        + ".",
        "- Shipped texts citing it: "
        + (", ".join(f"`labkit/{t}`" for t in use.shipped_texts) or "—")
        + ".",
        "- Other code strings citing it: "
        + (", ".join(f"`{m}`" for m in use.code_modules) or "—")
        + ".",
    ]


def render_rules_map(inputs: PageInputs) -> str:
    """The page as markdown: the head with its counts and limits, the rules
    with a recording site one section each, the rules no site records, the
    sites of another recorded rule, the technical contracts, and what is
    not settled — open assignments, a rule the cause passes in, the places
    naming an open assignment, the sites recording none. Pure."""
    sites = inputs.sites
    by_assignment: dict[str, list[FindingSite]] = defaultdict(list)
    for s in sites:
        by_assignment[s.assignment].append(s)
    active = {u.rule.split(" ", 1)[0] for u in inputs.uses}
    with_site = [u for u in inputs.uses if u.sites]
    without = [u for u in inputs.uses if not u.sites]
    other_rules = sorted(
        a for a in by_assignment if RULE_ID.fullmatch(a) and a not in active
    )
    gaps_of: dict[str, list[RuleGap]] = defaultdict(list)
    for g in inputs.gaps:
        gaps_of[g.rule].append(g)
    recorded_rule = sum(len(u.sites) for u in with_site) + sum(
        len(by_assignment[a]) for a in other_rules
    )
    out = [
        "# Rules map — each rule of the standard, the code that holds it, and what is not settled",
        "",
        "Generated, do not edit: `python -m labkit.tools.rules_map` writes this "
        "page from the source, the ledger, the shipped texts, `docs/chain.md`, "
        "`docs/checks-reach.tsv` and `docs/rule-gaps.tsv`, and "
        "`tests/test_map_of_rules.py` holds it equal to what the command writes. "
        "After a change to a finding site run the command again (`just overview`).",
        "",
        f"{len(inputs.uses)} active rules of the lab standard; "
        f"{len(with_site)} are recorded by a finding site, {len(without)} by none. "
        f"{len(sites)} finding sites: {recorded_rule} record a rule of a standard, "
        f"{len(by_assignment[TECHNICAL_CONTRACT])} a technical contract, "
        f"{len(by_assignment[OPEN_ASSIGNMENT])} an open assignment, "
        f"{len(by_assignment[NEW_CLASS])} a new class, "
        f"{len(by_assignment[VARIABLE])} a rule the cause passes in, "
        f"{len(by_assignment[NOT_RECORDED])} none (exits and printed lines). "
        f"{len(inputs.causes)} more places name an open assignment that a site "
        f"receives. {len(inputs.gaps)} known gap(s) between a rule's text and "
        "its code.",
        "",
        "How to read it. A site's *Rule* is the assignment its finding records "
        "as data. It says that the rule concerns the case the site holds — not "
        "that the code holds all of the rule's text: where the two are known to "
        "differ, the rule's section says so (from `docs/rule-gaps.tsv`). What "
        "the code does when the condition holds: *Grade* — BLOCKER refuses the "
        "step, WARNING tells and lets it pass, `exit` ends the command; "
        "*Evidence kind* — `guaranteed` is an exact check, `static evidence` a "
        "suspicion read from text or names; *Outcome* — what the finding states "
        "(`violated`, `deviation` where the rule is not decided, `suspected`, "
        "`not executable` for a check that could not run, `computed` or "
        "`variable` where the code decides at run time). *Stations* are the "
        "numbered gate stations that can tell the site "
        "([gate stations](gate-stations.md)): in their own code or a function "
        f"they call, or `{FURTHER}` the call graph — a static estimate that "
        "may name a station the site is not reached from at run time; `—` "
        "where no numbered station reaches it (a gate without numbered "
        "stations, such as `protocol-check`, or an area's script). *Tests that "
        "reached it* counts the tests of the last traced run that reached the "
        "site, how many carry the mark `rule`, and their files; reaching is "
        "not asserting. *Tells* is the constant text of the message, every "
        "value as `{…}`.",
        "",
        "Its limits. A rule no site records is listed as such: nothing follows "
        "from that about an agent audit checking it or a tool ruling it out — "
        "only what a source says stands here; a shipped text citing the rule "
        "is named, not what it asks. The chain's sections are matched by the "
        "functions their **Where:** line names. The stations are a static "
        "reading of the call graph (its limits: [gate stations](gate-stations.md)). "
        "Line numbers are left out: `python -m labkit.tools.check_inventory` "
        "prints them.",
        "",
        "## Rules recorded by a finding site",
    ]
    for use in with_site:
        rid = use.rule.split(" ", 1)[0]
        out += ["", f"### {use.rule}", ""]
        out += _written_down(use, {s.unit for s in use.sites}, inputs.chain)
        for g in gaps_of.get(rid, []):
            out += [
                "",
                f"**Known gap between text and code** "
                f"(`{g.function.split('.', 1)[-1]}`): the rule's text above "
                f"asks {g.text}; the code {g.code}. Kept as a task: "
                f"{g.recorded}.",
            ]
        out += ["", *_site_rows(list(use.sites), inputs)]
    out += [
        "",
        "## Rules no finding site records",
        "",
        f"For each: {NO_SITE}. Where a shipped text or a code string cites the "
        "rule, it is named; that is a citation, not a check.",
        "",
        "| Rule | Shipped texts citing it | Code strings citing it |",
        "|---|---|---|",
    ]
    for use in without:
        texts = ", ".join(f"`labkit/{t}`" for t in use.shipped_texts)
        code = ", ".join(f"`{m}`" for m in use.code_modules)
        out.append(f"| {use.rule} | {_cell(texts)} | {_cell(code)} |")
    if other_rules:
        out += [
            "",
            "## Other recorded rules",
            "",
            "Rules the sites record that are not active rules of the lab "
            "standard: the code standard's (`docs/coding-style.md`), or a rule "
            "the ledger retired.",
        ]
        for rid in other_rules:
            name = inputs.names.get(rid, "")
            out += ["", f"### {rid} {name}".rstrip(), ""]
            out += _site_rows(by_assignment[rid], inputs)
    out += [
        "",
        "## Technical contracts",
        "",
        "A condition a format or a check needs before it can answer — a file "
        "that reads, a reference that leads somewhere, a field written once, "
        "a format convention the stamp or the template writes. No rule of the "
        "standard is broken by it; the finding says the check could not "
        "answer, or the input is not what the format promises.",
        "",
        *_site_rows(by_assignment[TECHNICAL_CONTRACT], inputs),
        "",
        "## Not settled",
        "",
        "### Open assignments",
        "",
        "The site records that its rule is not decided: no sentence of the "
        "standard states its case, or the sentence reaches less far than the "
        "check. Why each is open: "
        "[the open assignments](notes/2026-11-11-open-assignments.md).",
        "",
        *_site_rows(by_assignment[OPEN_ASSIGNMENT], inputs),
    ]
    if by_assignment[NEW_CLASS]:
        out += [
            "",
            "### A new class",
            "",
            *_site_rows(by_assignment[NEW_CLASS], inputs),
        ]
    out += [
        "",
        "### The cause passes the rule in",
        "",
        "The site takes its assignment from the cause it reports, so the "
        "scan cannot read it; which cause carries which rule stands at the "
        "cause (the open ones are listed below).",
        "",
        *_site_rows(by_assignment[VARIABLE], inputs),
        "",
        "### Places that name an open assignment a site receives",
        "",
        "| Place | Function |",
        "|---|---|",
        *(
            f"| `{c.path}` | `{c.unit.removeprefix('labkit.')}` |"
            for c in sorted(inputs.causes, key=lambda c: (c.path, c.line))
        ),
        "",
        "### Sites that record no assignment",
        "",
        "An exit (`raise SystemExit(<message>)`) and a printed `WARNING:` or "
        "`BLOCKER:` line carry no rule as data.",
        "",
        *_site_rows(by_assignment[NOT_RECORDED], inputs),
    ]
    return "\n".join(out) + "\n"


def rules_map(
    package_dir: Path,
    reach_text: str,
    chain_text: str,
    gaps_text: str,
) -> str:
    """The page for the package at PACKAGE_DIR from its sources, its
    ledger, its shipped texts, the `pyproject.toml` and the code standard
    beside it, and the texts of the reach file, the chain and the gaps
    file.

    Raises:
        ValueError: The reach file or the gaps file does not read
            (`test_inventory.read_reach`, `read_gaps`).
    """
    modules = read_modules(package_dir)
    sites = finding_sites(modules)
    ledger = active_rules(package_dir)
    standard = (package_dir / "docs" / "standard.md").read_text(encoding="utf-8")
    rows = load_ledger(package_dir / LEDGER_NAME)
    texts = {rid: rule_text(rid, standard, rows) for rid, _ in ledger}
    found, told = stations_told(modules, package_dir.parent, sites, call_graph(modules))
    return render_rules_map(
        PageInputs(
            uses=rule_uses(ledger, sites, modules, shipped_texts(package_dir)),
            sites=sites,
            stations=site_stations(found, told),
            reach=test_inventory.read_reach(reach_text, str(REACH)),
            chain=chain_sections(chain_text),
            gaps=read_gaps(gaps_text, str(GAPS), sites, texts),
            causes=open_causes(modules),
            names=rule_names(package_dir),
        )
    )


def main(argv: list[str]) -> int:
    """Write the page, or with `--check` compare it: 0, or 1 when the page
    on disk is not what would be written.

    Side effects:
        Without `--check`, creates or overwrites `docs/rules-map.md` of the
        checkout.
    """
    if argv in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    if argv not in ([], ["--check"]):
        raise console.Refused("rules_map", USAGE)
    repo = PACKAGE_DIR.parent
    texts = {}
    for source in (REACH, CHAIN, GAPS):
        if not (repo / source).is_file():
            raise console.Refused(
                "rules_map",
                f"{repo / source}: not there — labkit's own checkout holds it",
            )
        texts[source] = (repo / source).read_text(encoding="utf-8")
    try:
        text = rules_map(PACKAGE_DIR, texts[REACH], texts[CHAIN], texts[GAPS])
    except ValueError as exc:
        raise console.Refused("rules_map", str(exc)) from exc
    return write_or_compare(
        "rules_map",
        RULES_MAP,
        text,
        check=argv == ["--check"],
        sources=f"the source, {REACH}, {CHAIN} and {GAPS} give",
    )


def cli() -> None:
    """Console entry: `main` with the process's arguments."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
