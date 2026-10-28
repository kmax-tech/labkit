#!/usr/bin/env python3
"""code-check — the mechanical half of the preflight, before the model looks.

The preflight audit (LAB-015 Preflight audit before freezing) used to do three jobs in one
pass: mechanics, compliance, judgement. The mechanics are the cheap half and
they do not need a model — an id that no script mentions, a field the
analysis reads and no producer writes, a protocol still full of placeholders
are all decidable from the source. Deciding them here leaves the model the
one question worth its cost: does the code MEAN what the registration says.

The automated checks, in the order `code_findings` runs them; each finding
carries its evidence kind as data (`gate.GateFinding.evidence_kind`:
GUARANTEED, or STATIC EVIDENCE — a warning, never a blocker). The rest is
extracted as facts into the bundle (``--bundle``) for an agent the lab
runs on it — labkit ships no agent for the bundle; its agent audit of the
code is `labkit-audit <AREA> --mode preflight` — not verified by this
command:

  1. **the promise block against the code** (LAB-004 Identifiers make the
     intent addressable, GUARANTEED), when the protocol has one: the block
     parses (else one blocker), every declared scope resolves, every
     declared key appears as a literal in a script. Then, block or not,
     every id registered in the prose appears as a key literal, and every
     key in the intent-id namespace has a registered id (a WARNING).
     Report time has `intent-check` for the metrics; before the run the same
     promise goes unchecked exactly when repairing it is still cheap.
  1a. **[A] keys decide something** (STATIC EVIDENCE, 2026-10-14; with a
     promise block only). An admissibility key the code writes and never
     tests (`if`, `and`, `all()`, …) permits nothing: the C verdict is
     reported either way. A test is not proof of a branch, so each finding
     is a WARNING. In the same pass, **constant copies** (STATIC EVIDENCE):
     a script that sets a registered constant's value itself instead of
     reading it from the protocol judges by an unregistered value once the
     two drift.
  1b. **parser fixtures** (GUARANTEED, 2026-10-05). Every `parse_*` function in
     the area's scripts is called by a test file under the repo's tests/ (a
     call, not a mention; the assertion is not checked) — five
     audit findings in three repos were "this parser has no fixture test on
     real raw answers", and a parser fails silently into a wrong number.
  1c. **prompt drift** (GUARANTEED, 2026-10-05). The protocol's prompt block
     is the `PROMPT` constant, not a transcript of it: every line of the
     constant without a `{placeholder}` must appear in the block. The most
     frequent provenance blocker in the audit corpus.
  1d. **stamp coverage** (STATIC EVIDENCE, 2026-10-12). The audit stamp
     follows `import` statements into `lib/` and `src/` (`scope_sha`); it
     cannot follow a `sys.path` edit, `importlib`/`runpy`/`exec`, or an
     import that resolves to a repo file outside those roots — another
     area's script, `tools/`. Each is a WARNING naming the line: code that
     determines the number and that no stamp sees (LAB-019 The stamp covers
     everything that determines the number). Five audits in uniagent
     (areas 15, 16, 17, 22, 23) found this by reading; the agent should
     not have to.

The following are extracted into the audit bundle but NOT checked by this
command — an agent reading the bundle judges them:

  2. **schema contract** (LAB-015 Preflight audit before freezing, preflight scope). Every field the analysis
     READS must be written somewhere — in the materialized data if it exists,
     otherwise as a write site in the producer's source.
  3. **gate labels** (LAB-038 What the prompt demands). String comparisons in evaluation code — both
     resolved literals and named constants — extracted as facts for the agent.

Protocol placeholders are neither checked nor extracted here: `protocol-check`
owns the template contract, and the bundle carries the protocol whole.

Where each lives: 1 and 1a here (`promise_block_findings`,
`admissibility_reads`, `constant_copies`); 1b and 1c in `prompt_check`; 1d
in `import_check`; the facts 2 and 3 from `code_scan` and
`gate_label_scan`. This module runs them all (`code_findings`, which
preflight's code station reads too) and writes the bundle.

Reads and writes are told apart with `ast`, not with a regex: `row["x"]` in
a Load context is a read, in a Store context it is a write, and no pattern
over text gets that right reliably.

Usage:
    code-check <AREA>                    # run the mechanical checks
    code-check <AREA> --bundle FILE      # additionally write the audit bundle
                                         # (protocol + scripts + imported
                                         #  repo-local lib modules) for an
                                         #  agent to read in one go

Exit code 1 with a blocker, 0 with warnings only or all clear — the gate
contract, told by `gate.Findings.report` like every gate's (until the
2026-10-23 audit the closing line was code-check's own and counted the
kinds by hand): a warning is to read, never a stop. Until 0.97.1
code-check exited 1 on a warning too, against its own contract (audit
2026-10-18). 2 on usage errors.
"""

from __future__ import annotations

import ast
from pathlib import Path

from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.formats import console, promises, protocol_block, rules, standard_contract
from labkit.formats.gate import (
    EXIT_CONTRACT,
    BLOCKER,
    WARNING,
    Findings,
    GateFinding,
    coded,
)
from labkit.checks.intent_check import ID_IN_PROTOCOL, code_ids, code_keys
from labkit.formats.repo import (
    AmbiguousArea,
    area_path,
    choose_protocol,
    layout_root,
    no_such_area,
    shown,
)
from labkit.formats.scope_sha import (
    SourceError,
    area_files,
    imported_repo_helpers,
    parse_source,
)
from labkit.checks.code_scan import (
    FIELDISH,
    name_of,
    string_constants,
    data_keys,
    scan,
    split_stages,
    unreadable_source,
)
from labkit.checks.gate_label_scan import gate_labels
from labkit.checks.import_check import stamp_coverage_findings
from labkit.checks.prompt_check import check_parser_fixtures, check_prompt_drift


# --- source analysis ------------------------------------------------------


#: the rule every intent-id finding cites
ID_RULE = "LAB-004 Identifiers make the intent addressable"


# --- gate-label extraction ------------------------------------------------


def check_intent_ids(area: Path, protocol: Path) -> list[GateFinding]:
    """Registered promises against the code, before any run exists.

    `intent-check` asks the same question of the metrics at report time, when
    the tokens are already spent. Here the answer is still cheap. A file in
    the scope that does not parse is one blocker, not a traceback.
    """
    try:
        return _intent_id_findings(area, protocol)
    except SourceError as exc:
        return [unreadable_source(exc)]


def code_findings(area: Path, protocol: Path, repo: Path) -> list[GateFinding]:
    """The automated checks 1–1d, in order, as finding lines: the promise
    block and the intent ids (with the [A]-key reads and constant copies),
    parser fixtures, prompt drift, stamp coverage. The one list both
    `code-check` and preflight's code station report, each finding with its
    grade and evidence kind as data."""
    return (
        check_intent_ids(area, protocol)
        + check_parser_fixtures(area, repo)
        + check_prompt_drift(area, protocol)
        + stamp_coverage_findings(area, repo)
    )


def _intent_id_findings(area: Path, protocol: Path) -> list[GateFinding]:
    text = protocol.read_text(encoding="utf-8")
    findings = promise_block_findings(area, protocol, text)
    registered = {m.group(1).lower() for m in ID_IN_PROTOCOL.finditer(text)}
    if not registered:
        return findings
    in_code = code_ids(area)
    unmistakable = code_ids(area, suffixed_only=True)
    for i in sorted(registered - set(in_code)):
        findings.append(
            coded(
                BLOCKER,
                protocol.name,
                f"[{i.upper()}] is registered, but no script mentions a "
                f"'{i}'/'{i}_*' key · the run reports nothing for this promise "
                f"and the metrics check fails after the tokens are spent",
                rule=ID_RULE,
                fix="implement the key or drop the id",
                evidence_kind=GUARANTEED,
            )
        )
    for i in sorted(set(unmistakable) - registered):
        findings.append(
            coded(
                WARNING,
                unmistakable[i][0],
                f"key '{i}_*' is in the intent-id namespace, but the protocol "
                f"registers no [{i.upper()}] · a number gets reported that "
                f"nobody registered",
                rule=ID_RULE,
                fix="register it or rename the key",
                evidence_kind=GUARANTEED,
            )
        )
    return findings


def promise_block_findings(area: Path, protocol: Path, text: str) -> list[GateFinding]:
    """The promise block against the code, before any run (guaranteed tier).

    Three things a run would otherwise discover after the tokens are spent:
    the block does not parse, a declared scope names code that is not there
    (runlog refuses the run), a declared key appears nowhere in the code
    (intent-check fails after the run). Exact key, not id: `"c1_passed"`
    does not answer a promise declaring `c1_pass` (Durchstich 2026-10-06).
    """
    try:
        block = promises.parse_block(text)
    except promises.PromiseError as exc:
        return [
            coded(
                BLOCKER,
                protocol.name,
                f"promise block: {exc}",
                rule=ID_RULE,
                fix="fix the block",
                evidence_kind=GUARANTEED,
            )
        ]
    if block is None:
        return []
    out: list[GateFinding] = []
    keys = code_keys(area)
    out += admissibility_reads(area, protocol, block, keys)
    for p in block.promises:
        try:
            promises.declared_scope_sha(area, p.scope)
        except promises.PromiseError as exc:
            out.append(
                coded(
                    BLOCKER,
                    protocol.name,
                    f"[{p.id}] declared scope: {exc} · runlog refuses the run",
                    fix="fix the scope",
                    evidence_kind=GUARANTEED,
                )
            )
        out += constant_copies(area, protocol, p)
        if p.key not in keys:
            near = sorted(k for k in keys if k.startswith(p.id.lower()))
            hint = f" (the code has {', '.join(near)})" if near else ""
            out.append(
                coded(
                    BLOCKER,
                    protocol.name,
                    f"[{p.id}] declares key '{p.key}', which no script "
                    f"mentions{hint} · intent-check fails after the run",
                    fix="report the declared key or fix the block",
                    evidence_kind=GUARANTEED,
                )
            )
    return out


_DECIDING_CALLS = frozenset({"all", "any"})


def _decides(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """Does NODE sit where a decision is taken: the test of an `if`, `while`,
    `assert` or conditional expression, an operand of `and`/`or`/`not`, or
    an argument of `all()`/`any()`? Climbs to the enclosing statement."""
    child, here = node, parents.get(id(node))
    while here is not None and not isinstance(child, ast.stmt):
        if isinstance(here, (ast.If, ast.While, ast.Assert, ast.IfExp)):
            if child is here.test:
                return True
        elif isinstance(here, ast.BoolOp) or (
            isinstance(here, ast.UnaryOp) and isinstance(here.op, ast.Not)
        ):
            return True
        elif isinstance(here, ast.Call) and name_of(here.func) in _DECIDING_CALLS:
            return True
        child, here = here, parents.get(id(here))
    return False


def _loop_keys(
    name: str, node: ast.AST, parents: dict[int, ast.AST], tuples: dict[str, list[str]]
) -> list[str]:
    """The string literals the loop variable NAME runs over, for the nearest
    enclosing `for` or comprehension that binds it: an inline tuple, list or
    set, or a name this file binds to one (`ADMISSIBILITY = ("a1_pass", …)`)."""
    here = parents.get(id(node))
    while here is not None:
        loops = (
            here.generators
            if isinstance(
                here, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)
            )
            else [here]
            if isinstance(here, (ast.For, ast.AsyncFor))
            else []
        )
        for loop in loops:
            if name_of(loop.target) == name:
                it = loop.iter
                if isinstance(it, (ast.Tuple, ast.List, ast.Set)):
                    return string_constants(it.elts)
                return tuples.get(name_of(it) or "", [])
        here = parents.get(id(here))
    return []


def _key_reads(path: Path) -> set[str]:
    """The keys this file reads where a decision is taken (`_decides`):
    `m["a1_pass"]`, `m.get("a1_pass")`, `m[k]` with `k` running over a
    collection of key literals, and a bare name `a1_pass`. A read anywhere
    else — a print, a copy into another dict — decides nothing.

    Raises:
        SourceError: The file does not parse — a read check over code it
            cannot read would report a missing branch that may be there.
    """
    tree = parse_source(path)
    parents = {id(c): n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    tuples = {
        t.id: string_constants(n.value.elts)
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and isinstance(n.value, (ast.Tuple, ast.List, ast.Set))
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    reads: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load):
            key = n.slice
        elif (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get"
            and n.args
        ):
            key = n.args[0]
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            if _decides(n, parents):
                reads.add(n.id)
            continue
        else:
            continue
        if not _decides(n, parents):
            continue
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            reads.add(key.value)
        elif (var := name_of(key)) is not None:
            reads.update(_loop_keys(var, n, parents, tuples))
    return reads


def admissibility_reads(
    area: Path, protocol: Path, block: "promises.PromiseTables", keys: dict
) -> list[GateFinding]:
    """Every [A] key the code writes must also be read (static evidence).

    An admissibility condition permits the C verdict — C judges, A permits
    the verdict (LAB-004 Identifiers make the intent addressable). A key
    that is computed and never read is a label without effect: the
    criterion is reported whether the condition held or not (Opus audit,
    probe 11: "[N1] was a label without effect"; class C, 24 findings over
    six repos). Only a read where a decision is taken counts (`_key_reads`),
    but a decision on the key is not proof that it withholds the verdict,
    and a decision in a form this reader does not follow is missed — so
    the finding is a WARNING, and silence means only "decided on
    somewhere". A key the code does not mention at all is the blocker
    `promise_block_findings` already reports.
    """
    owed = [p for p in block.promises if p.kind == "admissibility" and p.key in keys]
    if not owed:
        return []
    root = layout_root(area)
    files = area_files(area) + imported_repo_helpers(area, root)
    try:
        reads = set().union(*(_key_reads(f) for f in files))
    except ValueError as exc:
        return [
            coded(
                WARNING,
                protocol.name,
                f"[A] keys: read check not done — {exc}",
                fix="fix the file",
                evidence_kind=GUARANTEED,
            )
        ]
    return [
        coded(
            WARNING,
            keys[p.key][0],
            f"[{p.id}] key '{p.key}' is written but nothing decides on it · "
            f"the C verdict is reported whether [{p.id}] held or not",
            rule=ID_RULE,
            fix=f'withhold the verdict when it fails (`if not m["{p.key}"]: …`)',
            evidence_kind=STATIC_EVIDENCE,
        )
        for p in owed
        if p.key not in reads
    ]


def _literal(node: ast.expr) -> object:
    """The value of a literal (`0.7`, `-3`, `"x"`); a `_NOT_LITERAL` otherwise."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return _NOT_LITERAL


_NOT_LITERAL = object()


def constant_copies(
    area: Path, protocol: Path, p: "promises.Promise"
) -> list[GateFinding]:
    """A declared constant the scope's code sets itself, as a literal
    (static evidence — a warning, never a blocker).

    The script is meant to read its thresholds from the block
    (`promises.constants`); a literal copy judges by a value nobody
    registered as soon as the two drift, and intent-check sees it only if
    the run records the value (Durchstich 2026-10-07). A copy under another
    name, or a threshold written inline (`mean >= 1.5`), stays invisible
    here — that is the agent audit's question.
    """
    if not p.constants:
        return []
    out: list[GateFinding] = []
    for path in sorted({area / entry.partition(":")[0] for entry in p.scope}):
        if path.suffix != ".py" or not path.is_file():
            continue
        tree = parse_source(path)
        for node in ast.walk(tree):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign) and node.value
                else []
            )
            for target in targets:
                if not (isinstance(target, ast.Name) and target.id in p.constants):
                    continue
                assert (
                    isinstance(node, (ast.Assign, ast.AnnAssign))
                    and node.value is not None
                )
                value = _literal(node.value)
                if value is _NOT_LITERAL:
                    continue
                declared = p.constants[target.id]
                same = (
                    "the same value"
                    if value == declared
                    else f"the block says {declared!r}"
                )
                out.append(
                    coded(
                        WARNING,
                        protocol.name,
                        f"[{p.id}] {path.relative_to(area).as_posix()}:{node.lineno} "
                        f"sets {target.id} = {value!r} itself ({same}) · a copy "
                        f"judges by an unregistered value once they drift",
                        fix=f'read it with promises.constants(PROTOCOL, "{p.id}")'
                        f'["{target.id}"]',
                        evidence_kind=STATIC_EVIDENCE,
                    )
                )
    return out


def schema_facts(area: Path) -> str:
    """The field table — facts for the agent, not findings of our own.

    Three calibration rounds (2026-09-10, areas 60-73) failed to make this a
    checker. Every narrowing removed one false-blocker class and left the
    next: fields staged into files a later step writes, a `fan_v1.jsonl` that
    is simply not on disk any more, a consumer that reads across area
    boundaries (72 reads 71's prepared data). Deciding whether a read is
    satisfied needs the data FLOW, and that is exactly what a model reads
    well and a parser does not.

    So the mechanics stop at the facts: which fields the analysis reads, and
    which keys the area's data rows actually carry. The agent holds them
    against each other — with the lookup work already done, which is the part
    that used to cost it minutes of grepping.
    """
    producers, consumers = split_stages(area)
    known, files = data_keys(area)
    lines = [
        "## Schema facts (mechanically extracted — judge them, they are not findings)",
        "",
    ]
    lines.append(
        f"Data keys present in the area's own JSON(L) rows "
        f"({', '.join(files) if files else 'no data materialized yet'}):"
    )
    lines.append("  " + (", ".join(sorted(known)) if known else "—"))
    lines.append("")
    lines.append(
        "Fields read by the analysis stage, with the variable read "
        "from — a name absent from the list above is either staged "
        "by an earlier step, read from another area, or a defect:"
    )
    for c in consumers:
        v = scan(c)
        if v is None:
            lines.append(f"  {c.name}: DOES NOT PARSE")
            continue
        unexplained = sorted(
            f
            for f, (_, holder) in v.reads.items()
            if f not in known
            and f not in v.writes
            and FIELDISH.match(f)
            and holder
            and holder not in v.built
        )
        if unexplained:
            for f in unexplained:
                site, holder = v.reads[f]
                lines.append(
                    f"  {site}: '{f}' from `{holder}` — not in the area's data"
                )
        else:
            lines.append(f"  {c.name}: every read field is present in the area's data")
    return "\n".join(lines) + "\n"


# --- the bundle -----------------------------------------------------------


def severity_legend() -> str:
    """The severity legend of LAB-015 Preflight audit before freezing, quoted from the
    lab standard for the bundle: an agent reading the bundle reads only the bundle
    and cannot look the legend up, and it must grade by the same words as the
    preflight audit."""
    return (
        "## Severity legend (LAB-015 Preflight audit before freezing, labkit standard)\n\n"
        + rules.paragraph("LAB-015", "**Severity levels**")
        + "\n"
    )


def declared_labels_section(protocol: Path) -> str:
    """The labels the protocol's head declares (`[gate] labels`), for the
    agent to hold the extracted comparisons against — data, no judgement;
    a head that does not read says so instead."""
    try:
        labels = protocol_block.declared_labels(protocol.read_text(encoding="utf-8"))
    except (OSError, protocol_block.BlockError) as exc:
        return f"## Gate labels declared ([gate] labels)\n\nnot readable: {exc}\n"
    body = (
        "none declared — the protocol registers no label set"
        if labels is None
        else "\n".join(f"- {label}" for label in labels)
    )
    return f"## Gate labels declared ([gate] labels)\n\n{body}\n"


def write_bundle(
    area: Path, repo: Path, protocol: Path, out: Path
) -> tuple[int, list[str]]:
    """Write the audit bundle to OUT, for an agent the lab runs on it (labkit
    ships none): the severity legend, schema facts, gate labels, the labels
    the head declares, then the protocol, the area's files and the repo
    helpers they import, in one file. Returns (files read, the files that
    could not be read, as shown): an unreadable file stands in the bundle
    as `not readable: …`, never left out without a word."""
    parts = [
        f"# AUDIT BUNDLE · area {area.name}\n\n",
        severity_legend(),
        "\n",
        schema_facts(area),
        "\n",
        gate_labels(area),
        "\n",
        declared_labels_section(protocol),
        "\n",
    ]
    files = [protocol]
    files += area_files(area)
    files += imported_repo_helpers(area, repo)
    unreadable: list[str] = []
    for f in files:
        label = shown(f, repo)
        try:
            body = f.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            unreadable.append(label)
            body = f"not readable: {exc}"
        parts.append(f"\n===== FILE: {label} =====\n{body}")
    out.write_text("".join(parts), encoding="utf-8")
    return len(files) - len(unreadable), unreadable


# --- cli ------------------------------------------------------------------


def _cost_of(protocol: Path) -> str | None:
    """The protocol head's repeat cost, None when the head does not parse (the
    checker reports that; this is only for the summary's wording)."""
    try:
        return protocol_block.head(protocol.read_text(encoding="utf-8")).repeat_cost
    except protocol_block.BlockError:
        return None


def _arguments(argv: list[str]) -> tuple[Path, Path | None, Path | None]:
    """(area, --protocol, --bundle) of ARGV; raises `console.Refused` for an
    ambiguous or missing area and for anything else on the line."""
    try:
        area = area_path(argv[0])
    except AmbiguousArea as exc:
        raise console.Refused("code-check", str(exc)) from exc
    bundle_to = None
    protocol_arg = None
    rest = argv[1:]
    while rest:
        if rest[0] in ("--bundle", "--protocol") and len(rest) >= 2:
            if rest[0] == "--bundle":
                bundle_to = Path(rest[1])
            else:
                protocol_arg = Path(rest[1])
            rest = rest[2:]
            continue
        raise console.Refused("code-check", f"unexpected argument {rest[0]!r}")
    if not area.is_dir():
        raise console.Refused("code-check", no_such_area(area))
    return area, protocol_arg, bundle_to


def _not_checked(findings: Findings, protocol: Path, bundle_to: Path | None) -> None:
    """What this command did not check, told as a note before the gate's
    summary (the summary and the exit code are `Findings.report`'s, like
    every gate's — audit 2026-10-23, C4)."""
    if bundle_to is not None:
        findings.note(
            "schema facts + gate labels extracted into the bundle, for an agent "
            "you run on it (labkit ships none)"
        )
    elif standard_contract.lane(_cost_of(protocol)).registration:
        # only the agent's review is not owed here; the protocol's open
        # fields are, and the pre-commit holds them (judge probe, 2026-10-20)
        findings.note(
            "schema, gate labels: not checked — the agent's review is not owed "
            "at repeat cost low, the measurement checks the instrument (--bundle "
            "extracts them anyway, for an agent you run; labkit ships none); the "
            "protocol's open fields are owed: protocol-fill <PROTOCOL> --list"
        )
    else:
        findings.note(
            "schema, gate labels: not checked — the preflight audit "
            "(labkit-audit <AREA> --mode preflight) reads the code before the "
            "freeze; --bundle extracts them for an agent you run (labkit ships "
            "none); the protocol's open fields: protocol-check"
        )


def main(argv: list[str]) -> int:
    """Command line of `code-check`: check an area's code against its protocol, optionally write the bundle."""
    if not argv or argv[0] in ("-h", "--help"):
        lines = [
            (__doc__ or "").strip().splitlines()[0],
            "usage: code-check <AREA> [--protocol FILE] [--bundle FILE]",
            "  --protocol FILE  the PROTOCOL-*.md to check against "
            "(required once the area holds more than one)",
            "  --bundle FILE    pack sources + schema facts + gate labels "
            "for an agent you run on them (labkit ships none)",
            EXIT_CONTRACT,
        ]
        return console.usage("code-check", "\n".join(lines), asked=bool(argv))
    try:
        area, protocol_arg, bundle_to = _arguments(argv)
    except console.Refused as exc:
        console.refuse(exc.tool, exc.why)
        return 2
    protocol = choose_protocol(area, protocol_arg, "code-check")
    if protocol is None:
        return 2

    repo = layout_root(area)
    findings = Findings()
    for finding in code_findings(area, protocol, repo):
        findings.take(finding)
    if bundle_to is not None:
        n, unreadable = write_bundle(area, repo, protocol, bundle_to)
        print(
            f"bundle: {n} file(s) -> {bundle_to} "
            f"({bundle_to.stat().st_size // 1024} KB)"
        )
        for label in unreadable:
            findings.warn(
                f"bundle: {label} could not be read — the reader sees "
                f"`not readable` in its place",
                evidence_kind=GUARANTEED,
            )
    _not_checked(findings, protocol, bundle_to)
    return findings.report("code-check", "the run")


def cli() -> None:
    """Console entry point of `code-check`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
