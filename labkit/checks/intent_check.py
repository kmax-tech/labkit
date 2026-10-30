"""intent-check — do the metrics report every promise the protocol made?

The most frequent blocker class of the first audits (2026-09-08, areas
62-65) was "registered without implementation": a fork with no branch in
the code, a quality check printed but never compared to its threshold, a
three-conjunct criterion implemented as one conjunct, gate metrics written
next to the content numbers the gate was meant to suppress. Reading catches
this late; a set comparison catches it mechanically.

The contract (LAB-004 Identifiers make the intent addressable): every registration that promises the
code something — a verdict, a branch, an abort, a control — carries an id
in the protocol text (`[criterion-1]` criterion, `[quality-check-1]` quality check,
`[branch-1]` branch; the alphabet is `promises`), and every id
reappears as a lowercase key in the reportable run's metrics.json
(`criterion_1_pass`, `quality_check_1_pass`, `branch_1_outcome`, or the bare id). This command checks the two sets
against each other, in both directions:

- an id with no metrics key: the promise has no implementation evidence;
- a metrics key in the id namespace with no registration: something was
  built that nobody registered.

Letters that are metric names (F, P, R, Q, H) are never ids: in the F
namespace an `f1_score` in the metrics would "satisfy" a registered promise
that has no implementation at all.

Existence, not correctness: a key `quality_check_1_pass` proves the stage reports, not
that it computes the right thing — the semantic half stays with the
preflight audit (LAB-015 Preflight audit before freezing), which works the same ids.

The alphabet lives in `promises`: the kinds criterion, quality-check and
branch, and the promise block that makes them data. With a block, four more checks run here — text and block
name the same ids, every declared key is reported exactly, the run
recorded this very block, and a branch's key records one of the
registered outcome values (`unregistered_outcomes`).

A protocol without ids exits 0 with a note: nothing is promised.

WHICH run answers is decided by the binding, not by the directory: the
protocol's head carries an id and a run records the id it belongs to, so
only completed runs with that id take part in the automatic choice
(`docs/protocol-run-binding.md`). `protocol.path` never selects — it goes
stale by design. A protocol without a stamped id binds nothing; then the
run is named with --metrics.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.gate import AREA_SLOT
from labkit.formats.runs import metrics_path
from labkit.formats import console, promises, protocol_block
from labkit.formats.gate import EXIT_CONTRACT, GateFinding, blocker, with_way_out
from labkit.formats.runs import COMPLETED, read_metrics, read_run_config
from labkit.formats.answering_run import bound_answering_run, run_facts
from labkit.formats.repo import layout_root, shown
from labkit.formats.scope_sha import area_files, imported_repo_helpers

# The alphabet lives in `promises`; these names stay importable from here
# because code_check and tools outside labkit (befundregister) use them.
ID_IN_PROTOCOL = promises.ID_IN_PROTOCOL
ID_KEY = promises.ID_KEY
ids_in_prose = promises.ids_in_prose
reported_intent_ids = promises.reported_ids


def protocol_id_of(text: str) -> str | None:
    """The stamped id of the protocol's head, None while it is unstamped.
    A missing or malformed head raises protocol_block.BlockError."""
    return protocol_block.head(text).id


#: the way out of a finding where protocol and run do not name the same
#: promises — what intent-check's sentences leave to the author
INTENT_FIX = (
    "make the protocol's ids, its promise block and the run's metrics.json name "
    "the same promises: fix the code and measure again; after the first "
    "measurement a changed registration is registered anew"
)


@dataclass(frozen=True)
class Held:
    """What intent-check found for one protocol. NOTES say which run was
    chosen and on what proof — told, held against nobody; FINDINGS are the
    guaranteed-tier mismatches, each one a blocker with its way out; SUMMARY
    is the one line of a clean check (empty beside findings). `hold` builds
    it, `main` prints it, `finalize` collects it as data (audit follow-up
    2026-10-23, F4: parsed from stdout, every note became a blocker)."""

    notes: list[str]
    findings: list[GateFinding]
    summary: str


class NoRunChosen(console.Refused):
    """No metrics.json chosen for the protocol: no stamped id, or no bound
    run that may answer. The command line adds `METRICS_HINT`; finalize,
    which has no `--metrics`, shows the reason alone (audit 2026-10-27,
    third, I12: it passed the hint on)."""


#: the way out only intent-check's own command line offers
METRICS_HINT = "Name one explicitly with --metrics FILE if you know it belongs here."


def main(argv: list[str]) -> int:
    """intent-check: every registered promise id reports as a key of the
    answering run's metrics.json. Exit 0 all keys present, 1 findings (a key
    missing or extra), 2 no check (no bound run, unreadable artefact, no
    stamped id). `finalize` calls `hold` and holds 2 and 1 alike as a
    blocker."""
    try:
        return _main(argv)
    except NoRunChosen as exc:
        console.refuse(exc.tool, f"{exc.why}\n  {METRICS_HINT}")
        return 2
    except console.Refused as exc:
        console.refuse(exc.tool, exc.why)
        return 2


def _prose_block_mismatch(
    protocol: Path, text: str, block: promises.PromiseTables | None
) -> list[str]:
    """The ids the prose and the promise block do not share, one sentence
    each (`promises.prose_mismatch`); [] when they agree or there is no block."""
    if block is None:
        return []
    only_prose, only_block = promises.prose_mismatch(text, block)
    return [
        f"{protocol}: [{i}] appears in the text but not in the "
        f"promise block — a promise must be data to be held."
        for i in only_prose
    ] + [
        f"{protocol}: [{i}] is in the promise block but never "
        f"named in the text — say what it promises where the "
        f"reader looks."
        for i in only_block
    ]


def _metrics_file(
    protocol: Path, text: str, pid: str | None, metrics_arg: Path | None
) -> tuple[Path, list[str]]:
    """The metrics.json to hold the protocol to, and the notes of its
    choice: the named one, else the answering run's; raises
    `console.Refused` while the id is unstamped and nothing is named."""
    if metrics_arg is not None:
        return choose_explicit(protocol, metrics_arg, pid)
    if pid is not None:
        return choose_bound(protocol, pid, promises.registers_ids(text))
    raise NoRunChosen(
        "intent-check",
        f"{protocol.name} has no stamped id ([protocol] id) — no run is bound to it.",
    )


def _key_mismatch(
    protocol: Path, mpath: Path, reg: set[str], metrics: dict
) -> list[str]:
    """Registered ids without a key, keys without a registered id."""
    led = reported_intent_ids(metrics)
    return [
        f"{protocol}: [{i}] registered, but {mpath.name} has no "
        f"'{promises.key_stem(i)}'/'{promises.key_stem(i)}_*' key — the promise has no implementation "
        f"evidence in the metrics."
        for i in sorted(reg - led)
    ] + [
        f"{mpath}: key '{promises.key_stem(i)}'/'{promises.key_stem(i)}_*' is in the intent-id namespace, but "
        f"the protocol registers no [{i}] — built without a "
        f"registration."
        for i in sorted(led - reg)
    ]


def _named(argv: list[str]) -> tuple[Path, Path | None]:
    """(protocol, --metrics FILE or None) of ARGV; raises `console.Refused`
    for anything else on the line and for a protocol that is not a file."""
    protocol = Path(argv[0])
    metrics_arg = None
    if len(argv) >= 3 and argv[1] == "--metrics":
        metrics_arg = Path(argv[2])
    elif len(argv) > 1:
        raise console.Refused("intent-check", f"unexpected argument {argv[1]!r}")
    if not protocol.is_file():
        raise console.Refused("intent-check", f"no such protocol: {protocol}")
    return protocol, metrics_arg


def _read(protocol: Path) -> tuple[str, str | None, promises.PromiseTables | None]:
    """(text, stamped id or None, promise block or None) of PROTOCOL; a head
    or a block that does not read is a `console.Refused`."""
    text = protocol.read_text(encoding="utf-8")
    try:
        pid = protocol_id_of(text)
    except protocol_block.BlockError as exc:
        raise console.Refused("intent-check", f"{protocol}: {exc}") from exc
    try:
        block = promises.parse_block(text)
    except promises.PromiseError as exc:
        raise console.Refused(
            "intent-check", f"{protocol}: promise block: {exc}"
        ) from exc
    return text, pid, block


def _main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        lines = [
            (__doc__ or "").strip().splitlines()[0],
            "usage: intent-check <PROTOCOL-*.md> [--metrics FILE]",
            "  --metrics FILE  metrics.json to check against. Default: "
            "the newest COMPLETED run bound to this protocol's id that "
            "reports intent keys; required while the protocol's id is "
            "unstamped.",
            EXIT_CONTRACT,
        ]
        return console.usage("intent-check", "\n".join(lines), asked=bool(argv))

    protocol, metrics_arg = _named(argv)
    held = hold(protocol, metrics_arg)
    for line in held.notes:
        print(line)
    for finding in held.findings:
        print(finding.message)
    if held.findings:
        return 1
    print(held.summary)
    return 0


def hold(protocol: Path, metrics_arg: Path | None) -> Held:
    """Hold PROTOCOL's registered ids to a metrics.json: METRICS_ARG when
    named, else the newest completed run bound to the stamped id. Reads
    only. The prose and the promise block disagreeing is the first finding
    and the last; an unregistered protocol is a clean check with its reason
    as summary. Raises `console.Refused` when nothing can be held: no
    protocol or head or block that reads, earlier-form ids, no stamped id
    and no file named, no run that may answer, an unreadable metrics.json
    or run record."""
    text, pid, block = _read(protocol)
    earlier = promises.earlier_ids(text)
    if earlier:
        raise console.Refused(
            "intent-check",
            f"{protocol}: intent ids {', '.join(earlier)} — {promises.EARLIER_IDS_HELP}",
        )
    mismatch = _prose_block_mismatch(protocol, text, block)
    if mismatch:
        return Held([], [blocker(m, fix=INTENT_FIX) for m in mismatch], "")

    reg = ids_in_prose(text)
    if not reg:
        return Held(
            [],
            [],
            "intent-check: no intent ids registered ([criterion-1]/[quality-check-1]/[branch-1] — "
            "LAB-004 Identifiers make the intent addressable); nothing to hold the metrics against.",
        )

    try:
        mpath, notes = _metrics_file(protocol, text, pid, metrics_arg)
        metrics = read_metrics(mpath)
    except ValueError as exc:  # MetricsError, RunConfigError
        raise console.Refused("intent-check", str(exc)) from exc
    found = [
        blocker(m, fix=INTENT_FIX)
        for m in _key_mismatch(protocol, mpath, reg, metrics)
        + (check_block_against_run(block, mpath, metrics) if block is not None else [])
    ] + (
        unregistered_outcomes(block, metrics, mpath.parent.name)
        if block is not None
        else []
    )
    if found:
        return Held(notes, found, "")
    summary = (
        f"intent-check: {len(reg)} id(s) registered, all report in {mpath.name}."
        + (
            f" Promise block {block.sha} is the one the run recorded."
            if block is not None
            else ""
        )
    )
    return Held(notes, [], summary)


def check_block_against_run(
    block: "promises.PromiseTables", mpath: Path, metrics: dict
) -> list[str]:
    """Guaranteed-tier findings for a protocol WITH a promise block.

    Two things the prose check cannot see: every declared key is reported
    exactly (a `criterion_1_pass` promise is not answered by `criterion_1_debug`), and the
    run recorded THIS block — same constants, same scopes, same keys. A
    block edited after the run would otherwise hold today's thresholds
    against yesterday's number.
    """
    out = []
    for p in block.promises:
        if p.key not in metrics:
            out.append(
                f"{mpath}: [{p.id}] declares key '{p.key}', which the "
                f"run does not report."
            )
    cfg = read_run_config(mpath.parent)
    drift = promises.block_drift(cfg.promises if cfg else None, block)
    if drift:
        out.append(f"{mpath.parent.name}: {drift}.")
    out += promised_constant_mismatches(
        block, cfg.config if cfg else {}, mpath.parent.name
    )
    return out


def unregistered_outcomes(
    block: promises.PromiseTables, metrics: dict, run_name: str
) -> list[GateFinding]:
    """Guaranteed tier: every branch of BLOCK whose key METRICS
    records with a value that is none of its outcomes' names
    (`promises.parse_outcomes`) — a blocker naming them. An outcome
    the protocol never registered is a conclusion chosen after the run;
    the reader of the run finds no outcome for it. A key the run does not
    report is `check_block_against_run`'s finding, and a sentence still the
    stamp's placeholder registers no outcomes (`promise_tables_owed` holds
    it), so neither is one here. RUN_NAME names the run in the sentence.
    Pure."""
    out = []
    for p in block.promises:
        outcomes = p.outcome_names()
        if not outcomes or p.key not in metrics:
            continue
        value = metrics[p.key]
        if isinstance(value, str) and value in outcomes:
            continue
        out.append(
            blocker(
                f"{run_name}: [{p.id}] records {p.key} = {value!r}, which is "
                f"none of its outcomes' names",
                fix=f"record one of {', '.join(outcomes)} — the name of the "
                f"outcome whose condition holds, as [[promise]] {p.id} writes it: "
                f"fix the code, then `.venv/bin/python {AREA_SLOT}/scripts/01_measure.py`",
            )
        )
    return out


def promised_constant_mismatches(
    block: promises.PromiseTables, run_config: dict, run_name: str
) -> list[str]:
    """The constants the protocol promised (a margin, a threshold) whose value
    differs from the one the run recorded under the same name, or is absent.

    The script is meant to read its thresholds from the block
    (`promises.constants`). One that keeps its own copy — `min_f1 = 0.5`
    against 0.6 in the protocol — judged by a threshold nobody registered
    (Durchstich 2026-10-06). Exact, but only as far as the script records
    the value in its run config; a copy it never records stays invisible
    here (0.70.0). Since 0.71.0 a missing constant is a finding too: runlog
    refuses such a run before mkdir, so a record without it is an old run
    or a hand-written one.
    """
    out = []
    for r in promises.constant_records(block, run_config):
        if r.state == "different":
            out.append(
                f"{run_name}: [{r.promise_id}] declares {r.name} = {r.promised!r}, "
                f"the run used {r.name} = {r.recorded!r} — read "
                f"it with promises.all_constants(), not a second copy."
            )
        elif r.state == "missing":
            out.append(
                f"{run_name}: [{r.promise_id}] declares {r.name} = {r.promised!r}, "
                f"the run recorded no constant of that name — a run under "
                f"labkit 0.71 or later cannot start without it; an older run is "
                f"held and reproduced with its pinned version (0.70.0 was the "
                f"last that let it pass)."
            )
    return out


# --- which metrics file answers: named explicitly, or chosen by binding -----
#
# Each returns the chosen metrics.json or raises console.Refused with the
# reason. `_main` only dispatches, then checks.


def choose_explicit(
    protocol: Path, metrics_arg: Path, pid: str | None
) -> tuple[Path, list[str]]:
    """`--metrics FILE`: the named file, if it may answer for this protocol,
    and the warning told when nothing proves it belongs here. Raises
    console.Refused when it may not."""
    if not metrics_arg.is_file():
        raise console.Refused("intent-check", f"no such metrics file: {metrics_arg}")
    # An explicit file still has to be a file that MAY answer for this
    # protocol. Naming one was always a seatbelt, never a proof of
    # belonging — where the run records a binding, that proof now
    # exists and is held (2026-09-26).
    facts = run_facts(metrics_arg.parent)
    # A run that did not complete has numbers on disk and no finish —
    # "nothing may report it" (protocol-run-binding.md); naming the file
    # must not be a loophole around completion.
    if facts is None or facts.state != COMPLETED:
        state = facts.state if facts else "no config.json"
        why = (facts.why if facts else None) or (
            "an incomplete run's numbers may not be reported, even when named explicitly"
        )
        raise console.Refused(
            "intent-check",
            f"{metrics_arg.parent.name} is not completed ({state}) — {why}.",
        )
    bound_to = facts.binding.id
    notes: list[str] = []
    if bound_to:
        if pid and bound_to != pid:
            raise console.Refused(
                "intent-check",
                f"{metrics_arg} belongs to protocol "
                f"{bound_to}, this protocol is {pid} — "
                f"holding one protocol's promises against another "
                f"protocol's run answers nothing.",
            )
        if pid is None:
            notes.append(
                f"intent-check: WARNING — {metrics_arg} is bound to "
                f"{bound_to}, but {protocol.name} carries no "
                f"stamped id to hold it against. Checking anyway, unverified."
            )
    else:
        notes.append(
            f"intent-check: WARNING — {metrics_arg} records no binding "
            f"(unbound run); nothing proves it belongs to {protocol.name}. "
            f"Checking anyway, unverified."
        )
    return metrics_arg, notes


def choose_bound(
    protocol: Path, pid: str, ids_registered: bool
) -> tuple[Path, list[str]]:
    """The newest completed run bound to `pid` — `answering_run.bound_answering_run` —
    and the lines of its choice to tell the operator (`AnsweringRun.explain`). Raises
    console.Refused when no choice stands, a probe or producer run among
    them when the protocol registers ids (until 0.96.0 a warning, and every
    promise then read as unimplemented)."""
    choice = bound_answering_run(protocol.parent, pid)
    blocker, lines = choice.explain(ids_registered)
    if blocker:
        why = [
            with_way_out(
                f"{blocker.text} ({protocol.name}) — nothing to hold the promises "
                f"against",
                blocker.fix,
            )
        ]
        if lines:
            why.append(f"  {len(lines)} other run(s) in {protocol.parent}:")
            why += [f"    {line}" for line in lines]
        elif choice.run_dir is None:
            why.append(f"  no runs in {protocol.parent} yet.")
        raise NoRunChosen("intent-check", "\n".join(why))
    assert choice.run_dir is not None, (
        "explain() names a blocker whenever no run stands"
    )
    return metrics_path(choice.run_dir), [
        f"intent-check: using {choice.run_dir.name}/metrics.json ({line})."
        for line in lines
    ]


def cli() -> None:
    """Entry point for the installed `intent-check` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()


# --- preflight half: ids against the CODE, before any run exists ----------
#
# main() above answers the report-time question (do the METRICS report every
# promise?) and needs a runs/*/metrics.json. Before the run that file does not
# exist, so the same promise goes unchecked exactly when checking it is still
# cheap. code_ids() answers the earlier question from the source: does the code
# even MENTION the key it is supposed to report? An id that appears nowhere in
# the scripts cannot report at run time — that is mechanical, not a judgement.

ID_LITERAL = promises.ID_LITERAL


def code_ids(area: Path, suffixed_only: bool = False) -> dict[str, list[str]]:
    """Intent ids the area's source mentions, mapped id -> ["file:line", ...].

    Reads the string literals, not the syntax: a metric key reaches
    metrics.json as `"criterion_1_pass"` however it is assembled, and a literal is
    what every assembly path has in common.

    `suffixed_only` keeps `"quality_check_1_pass"` and drops a bare `"quality_check_65"`. A bare id in
    the namespace is ambiguous — area 72 named its source sessions `"s65"`,
    `"s68"`, `"s69"` after the areas they came from, and reading those as
    unregistered promises produced three findings and no defect (2026-09-10).
    For "registered but absent from the code" every literal counts; for the
    reverse direction only an unmistakable metric key does.

    Keyword arguments count too: `r.metrics(criterion_1_pass=acc >= MIN)` reaches
    metrics.json as `"criterion_1_pass"` without ever being a string literal, and
    reading literals only reported a correct script as "no script mentions
    'c1'" — a blocker against correct code (2026-10-06, found in the first
    promise-block run). Only
    keyword names in CALLS count, not assignments: a local `criterion_1_pass = …`
    is not yet a reported key. An area file that does not parse keeps its
    literal hits and loses only the keyword half; with a `lib/` or `src/` in
    the repo the import walk needs its syntax tree and raises
    `scope_sha.SourceError` naming it — code-check and preflight report
    that as one blocker (audit 2026-10-15).
    """
    hits: dict[str, list[str]] = {}
    for key, where in code_keys(area).items():
        if suffixed_only and not promises.INTENT_KEY.match(key):
            continue
        m = ID_KEY.match(key)
        assert m is not None, f"code_keys returned a non-id key {key!r}"
        hits.setdefault(promises.id_of_stem(m.group(1)), []).extend(where)
    for locs in hits.values():
        locs.sort()
    return hits


def code_keys(area: Path) -> dict[str, list[str]]:
    """Full intent keys the area's source mentions, key -> ["file:line", ...].

    The same scan as `code_ids` (string literals, keyword arguments in
    calls), but keeping the whole key: a promise block declares `criterion_1_pass`,
    and `"criterion_1_passed"` in the code answers the id, not the key. Preflight
    holds the block's keys to this, before any run (Durchstich 2026-10-06:
    a renamed key surfaced only after the run).
    """
    hits: dict[str, list[str]] = {}
    # The imported repo-local code counts as the area's: a shared helper
    # under src/ or lib/ may write a registered key, and reading the area's
    # scripts alone made four promises "absent" (2026-10-07). The house rule
    # (CODE-016 The experiment area reconstructs itself) now wants every id
    # literal in the area script, because an id in shared code is counted
    # for every importing area; the scan stays transitive so a repo that
    # has not moved yet is held, not waved through.
    root = layout_root(area)
    own = area_files(area)
    for path in own + imported_repo_helpers(area, root):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(source.splitlines(), 1):
            for m in ID_LITERAL.finditer(line):
                key = (m.group(1) + (m.group(2) or "")).lower()
                hits.setdefault(key, []).append(f"{_where(path, area, root)}:{lineno}")
        for name, lineno in _keyword_names(source, path):
            if ID_KEY.match(name.lower()):
                hits.setdefault(name.lower(), []).append(
                    f"{_where(path, area, root)}:{lineno}"
                )
    return hits


def _where(path: Path, area: Path, root: Path) -> str:
    """An area file by its name, an imported one by its repo path."""
    if path.parent.parent == area:
        return path.name
    return shown(path, root)


def _keyword_names(source: str, path: Path) -> list[tuple[str, int]]:
    """(name, line) of every keyword argument in a call; [] if unparsable."""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    return [
        (kw.arg, kw.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg is not None
    ]
