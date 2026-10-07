"""intent-check — do the metrics report every promise the protocol made?

The most frequent blocker class of the first audits (2026-09-08, areas
62-65) was "registered without implementation": a fork with no branch in
the code, an admissibility condition printed but never compared to its threshold, a
three-conjunct criterion implemented as one conjunct, gate metrics written
next to the content numbers the gate was meant to suppress. Reading catches
this late; a set comparison catches it mechanically.

The contract (Arbeitsstandard AS-004 Kennungen machen den Intent adressierbar): every registration that promises the
code something — a verdict, a branch, an abort, a control — carries an id
in the protocol text (`[C1]` criterion, `[A1]` admissibility condition,
`[B1]` registered branch; the alphabet is `promises`), and every id
reappears as a lowercase key in the reportable run's metrics.json
(`c1_pass`, `a1_pass`, `b1_branch`, or the bare id). This command checks the two sets
against each other, in both directions:

- an id with no metrics key: the promise has no implementation evidence;
- a metrics key in the id namespace with no registration: something was
  built that nobody registered.

Letters that are metric names (F, P, R, Q, H) are never ids: in the F
namespace an `f1_score` in the metrics would "satisfy" a registered promise
that has no implementation at all.

Existence, not correctness: a key `a1_pass` proves the stage reports, not
that it computes the right thing — the semantic half stays with the
preflight audit (AS-015 Preflight-Audit vor dem Einfrieren), which works the same ids.

Since 2026-10-06 the alphabet lives in `promises`: the letters C
(criterion), A (admissibility), B (branch), and the promise block that
makes them data. With a block, three more checks run here — text and block
name the same ids, every declared key is reported exactly, and the run
recorded this very block.

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
import json
import sys
from pathlib import Path

from labkit import promises, protocol_block
from labkit.runs import RunConfigError, read_run_config, run_state

# The alphabet lives in `promises`; these names stay importable from here
# because code_check and tools outside labkit (befundregister) use them.
ID_IN_PROTOCOL = promises.ID_IN_PROTOCOL
ID_KEY = promises.ID_KEY
registered_ids = promises.registered_ids
reported_intent_ids = promises.reported_ids


def protocol_id_of(text: str) -> str | None:
    """The stamped id of the protocol's head, None while it is unstamped.
    A missing or malformed head raises protocol_block.BlockError."""
    return protocol_block.head(text).id


def read_metrics(path: Path) -> dict:
    """A run's metrics.json; unreadable raises ValueError naming the file.

    Skipping an unreadable metrics file chose the next older run as if the
    newer had reported no intent keys — the damage stayed invisible
    (review 2026-10-06).
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"{path}: unreadable metrics ({exc}) — repair the "
            f"run or name another with --metrics"
        ) from exc


def run_facts(run_dir: Path) -> dict | None:
    """What a run directory says about itself: state and binding.

    `None` for a directory without config.json — not a run. An unreadable
    config.json is a run in state `corrupt` with the reason in `why`: it
    stays in the listing the operator reads instead of vanishing, and it is
    never chosen (review 2026-10-06).
    """
    try:
        cfg = read_run_config(run_dir)
    except RunConfigError as exc:
        return {
            "dir": run_dir,
            "metrics": run_dir / "metrics.json",
            "state": "corrupt",
            "protocol_id": None,
            "why": str(exc),
        }
    if cfg is None:
        return None
    binding = cfg.get("protocol") or {}
    return {
        "dir": run_dir,
        "metrics": run_dir / "metrics.json",
        "state": run_state(run_dir, cfg, alive=False),
        "protocol_id": binding.get("id"),
    }


def bound_runs(area: Path, pid: str) -> tuple[list[dict], list[dict]]:
    """(runs bound to `pid` and completed, everything else), oldest first.

    Only the first list may feed an automatic choice. The second carries
    the reason it was left out, for the operator who has to look. The
    binding is the id and nothing else — `protocol.path` is a hint for
    humans, never a selection criterion: it goes stale by design.
    """
    taken, left = [], []
    for d in sorted((area / "runs").glob("*")):
        facts = run_facts(d)
        if facts is None:
            continue
        if facts["state"] != "completed":
            facts.setdefault("why", facts["state"])
        elif facts["protocol_id"] == pid:
            taken.append(facts)
            continue
        elif facts["protocol_id"]:
            facts["why"] = f"bound to {facts['protocol_id']}"
        else:
            facts["why"] = "unbound (no protocol id at run time)"
        left.append(facts)
    return taken, left


def newest_with_intent_keys(cands: list[dict]) -> tuple[Path | None, int]:
    """Among already-eligible runs: the newest reporting any intent key,
    plus how many newer ones were skipped for reporting none.

    The rule from 2026-09-09 (area 71) unchanged, only its input narrowed:
    a producer or probe run writes a metrics.json too, and holding the
    promises against THAT file reports every promise as unimplemented.
    """
    skipped = 0
    for facts in reversed(cands):
        if reported_intent_ids(read_metrics(facts["metrics"])):
            return facts["metrics"], skipped
        skipped += 1
    return (cands[-1]["metrics"], 0) if cands else (None, 0)


def main(argv: list[str]) -> int:
    """intent-check; an unreadable run artefact ends it with a sentence."""
    try:
        return _main(argv)
    except ValueError as exc:  # read_metrics / RunConfigError
        print(f"intent-check: {exc}")
        return 2


def _main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: intent-check <PROTOCOL-*.md> [--metrics FILE]")
        print(
            "  --metrics FILE  metrics.json to check against. Default: "
            "the newest COMPLETED run bound to this protocol's id that "
            "reports intent keys; required while the protocol's id is "
            "unstamped."
        )
        return 0 if argv else 2

    protocol = Path(argv[0])
    metrics_arg = None
    if len(argv) >= 3 and argv[1] == "--metrics":
        metrics_arg = Path(argv[2])
    elif len(argv) > 1:
        print(f"intent-check: unexpected argument {argv[1]!r}")
        return 2

    if not protocol.is_file():
        print(f"intent-check: no such protocol: {protocol}")
        return 2
    text = protocol.read_text(encoding="utf-8")
    try:
        pid = protocol_id_of(text)
    except protocol_block.BlockError as exc:
        print(f"{protocol}: {exc}")
        return 2
    try:
        block = promises.parse_block(text)
    except promises.PromiseError as exc:
        print(f"{protocol}: promise block: {exc}")
        return 2
    if block is not None:
        only_prose, only_block = promises.prose_mismatch(text, block)
        for i in only_prose:
            print(
                f"{protocol}: [{i}] appears in the text but not in the "
                f"promise block — a promise must be data to be checked."
            )
        for i in only_block:
            print(
                f"{protocol}: [{i}] is in the promise block but never "
                f"named in the text — say what it promises where the "
                f"reader looks."
            )
        if only_prose or only_block:
            return 1

    earlier = promises.earlier_ids(text)
    if earlier:
        print(
            f"{protocol}: intent ids {', '.join(earlier)} — {promises.EARLIER_IDS_HELP}"
        )
        return 2
    reg = registered_ids(text)
    if not reg:
        print(
            "intent-check: no intent ids registered ([C1]/[A1]/[B1] — "
            "AS-004 Kennungen machen den Intent adressierbar); nothing to hold the metrics against."
        )
        return 0

    if metrics_arg is not None:
        chosen = choose_explicit(protocol, metrics_arg, pid)
    elif pid is not None:
        chosen = choose_bound(protocol, pid)
    else:
        print(
            f"intent-check: {protocol.name} has no stamped id ([protocol] "
            f"id) — no run is bound to it; name the run with --metrics FILE."
        )
        return 2
    if isinstance(chosen, int):
        return chosen
    mpath = chosen
    try:
        metrics = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"intent-check: cannot read {mpath}: {exc}")
        return 2
    led = reported_intent_ids(metrics)

    missing = sorted(reg - led)
    unregistered = sorted(led - reg)
    for i in missing:
        print(
            f"{protocol}: [{i.upper()}] registered, but {mpath.name} has no "
            f"'{i}'/'{i}_*' key — the promise has no implementation "
            f"evidence in the metrics."
        )
    for i in unregistered:
        print(
            f"{mpath}: key '{i}'/'{i}_*' is in the intent-id namespace, but "
            f"the protocol registers no [{i.upper()}] — built without a "
            f"registration."
        )
    block_findings = (
        check_block_against_run(block, mpath, metrics) if block is not None else []
    )
    for f in block_findings:
        print(f)
    if missing or unregistered or block_findings:
        return 1
    print(
        f"intent-check: {len(reg)} id(s) registered, all report in "
        f"{mpath.name}."
        + (
            f" Promise block {block.sha} is the one the run recorded."
            if block is not None
            else ""
        )
    )
    return 0


def check_block_against_run(
    block: "promises.PromiseBlock", mpath: Path, metrics: dict
) -> list[str]:
    """Guaranteed-tier findings for a protocol WITH a promise block.

    Two things the prose check cannot see: every declared key is reported
    exactly (a `c1_pass` promise is not answered by `c1_debug`), and the
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
    cfg = read_run_config(mpath.parent) or {}
    recorded = cfg.get("promises")
    drift = promises.block_drift(recorded, block)
    if drift:
        out.append(f"{mpath.parent.name}: {drift}.")
    out += constant_findings(block, cfg.get("config") or {}, mpath.parent.name)
    return out


def constant_findings(
    block: "promises.PromiseBlock", run_config: dict, run_name: str
) -> list[str]:
    """A block constant the run recorded under the same name with another value.

    The script is meant to read its thresholds from the block
    (`promises.constants`). One that keeps its own copy — `MIN_F1 = 0.5`
    against 0.6 in the protocol — judged by a threshold nobody registered
    (Durchstich 2026-10-06). Exact, but only as far as the script records
    the value in its run config; a copy it never records stays invisible
    here and is a static-evidence question.
    """
    out = []
    for p in block.promises:
        for name, value in p.constants.items():
            if name in run_config and run_config[name] != value:
                out.append(
                    f"{run_name}: [{p.id}] declares {name} = {value!r}, "
                    f"the run used {name} = {run_config[name]!r} — read "
                    f"it with promises.constants(), not a second copy."
                )
    return out


# --- which metrics file answers: named explicitly, or chosen by binding -----
#
# Each returns the chosen metrics.json, or an int: the exit code, with the
# reason already printed. `_main` only dispatches, then checks.


def choose_explicit(protocol: Path, metrics_arg: Path, pid: str | None) -> Path | int:
    """`--metrics FILE`: the named file, if it may answer for this protocol."""
    if not metrics_arg.is_file():
        print(f"intent-check: no such metrics file: {metrics_arg}")
        return 2
    # An explicit file still has to be a file that MAY answer for this
    # protocol. Naming one was always a seatbelt, never a proof of
    # belonging — where the run records a binding, that proof now
    # exists and is checked (2026-09-26).
    facts = run_facts(metrics_arg.parent)
    # A run that did not complete has numbers on disk and no finish —
    # "nothing may report it" (protocol-run-binding.md); naming the file
    # must not be a loophole around completion.
    if facts is None or facts["state"] != "completed":
        state = facts["state"] if facts else "no config.json"
        why = (
            "written before labkit 0.21 — read it with labkit 0.47"
            if state == "legacy"
            else "an incomplete run's numbers may not be reported, even when "
            "named explicitly"
        )
        print(
            f"intent-check: {metrics_arg.parent.name} is not completed ({state}) — {why}."
        )
        return 2
    if facts["protocol_id"]:
        if pid and facts["protocol_id"] != pid:
            print(
                f"intent-check: {metrics_arg} belongs to protocol "
                f"{facts['protocol_id']}, this protocol is {pid} — "
                f"holding one protocol's promises against another "
                f"protocol's run answers nothing."
            )
            return 2
        if pid is None:
            print(
                f"intent-check: WARNING — {metrics_arg} is bound to "
                f"{facts['protocol_id']}, but {protocol.name} carries no "
                f"stamped id to hold it against. Checking anyway, unverified."
            )
    else:
        print(
            f"intent-check: WARNING — {metrics_arg} records no binding "
            f"(unbound run); nothing proves it belongs to {protocol.name}. "
            f"Checking anyway, unverified."
        )
    return metrics_arg


def choose_bound(protocol: Path, pid: str) -> Path | int:
    """The newest completed run bound to `pid`."""
    # The run says which protocol it belongs to, so the choice is a filter, not a guess. Only COMPLETED runs with
    # this id take part — an unfinalized or corrupt run has numbers on
    # disk and no finish, and a run bound elsewhere answers for another
    # question entirely.
    cands, rest = bound_runs(protocol.parent, pid)
    if not cands:
        print(
            f"intent-check: no completed run bound to {pid} "
            f"({protocol.name}) — nothing to hold the promises "
            f"against."
        )
        if rest:
            print(f"  {len(rest)} other run(s) in {protocol.parent}:")
            for f in rest:
                print(f"    {f['dir'].name}: {f['why']}")
        else:
            print(f"  no runs in {protocol.parent} yet.")
        print("  Name one explicitly with --metrics FILE if you know it belongs here.")
        return 2
    mpath, skipped = newest_with_intent_keys(cands)
    assert mpath is not None, "cands is non-empty, so a metrics file exists"
    blocking = newer_unreadable(mpath.parent, rest)
    if blocking:
        print(f"intent-check: {blocking}")
        return 2
    if skipped:
        print(
            f"intent-check: using {mpath.parent.name}/metrics.json "
            f"(newest bound run with intent keys; skipped {skipped} "
            f"newer bound run(s) without any)."
        )
    return mpath


def newer_unreadable(chosen: Path, rest: list[dict]) -> str | None:
    """Why the choice must not stand: a run NEWER than the chosen one whose
    config.json cannot be read. Its binding is unknowable, so it may be the
    run that answers — choosing an older one past it is what
    `runs.read_run_config` says must not happen (review 2026-10-07)."""
    bad = [
        f
        for f in rest
        if f["state"] == "corrupt"
        and f["protocol_id"] is None
        and f["dir"].name > chosen.name
    ]
    if not bad:
        return None
    return (
        f"{len(bad)} newer run(s) cannot say which protocol they belong to — "
        + "; ".join(f["why"] for f in bad)
        + f". Repair or move them aside before {chosen.name} may answer."
    )


def cli() -> None:
    """Entry point for the installed `intent-check` command."""
    sys.exit(main(sys.argv[1:]))


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
    metrics.json as `"c1_pass"` however it is assembled, and a literal is
    what every assembly path has in common.

    `suffixed_only` keeps `"a1_pass"` and drops a bare `"a65"`. A bare id in
    the namespace is ambiguous — area 72 named its source sessions `"s65"`,
    `"s68"`, `"s69"` after the areas they came from, and reading those as
    unregistered promises produced three findings and no defect (2026-09-10).
    For "registered but absent from the code" every literal counts; for the
    reverse direction only an unmistakable metric key does.

    Keyword arguments count too: `r.metrics(c1_pass=acc >= MIN)` reaches
    metrics.json as `"c1_pass"` without ever being a string literal, and
    reading literals only reported a correct script as "no script mentions
    'c1'" — a blocker against correct code (2026-10-06, found in the first
    promise-block run). Only
    keyword names in CALLS count, not assignments: a local `c1_pass = …`
    is not yet a reported key. A file that does not parse keeps its literal
    hits and loses only the keyword half.
    """
    hits: dict[str, list[str]] = {}
    for key, where in code_keys(area).items():
        if suffixed_only and "_" not in key:
            continue
        m = ID_KEY.match(key)
        assert m is not None, f"code_keys returned a non-id key {key!r}"
        hits.setdefault(m.group(1), []).extend(where)
    for locs in hits.values():
        locs.sort()
    return hits


def code_keys(area: Path) -> dict[str, list[str]]:
    """Full intent keys the area's source mentions, key -> ["file:line", ...].

    The same scan as `code_ids` (string literals, keyword arguments in
    calls), but keeping the whole key: a promise block declares `c1_pass`,
    and `"c1_passed"` in the code answers the id, not the key. Preflight
    holds the block's keys to this, before any run (Durchstich 2026-10-06:
    a renamed key surfaced only after the run).
    """
    hits: dict[str, list[str]] = {}
    for path in sorted(area.glob("scripts/*.py")) + sorted(area.glob("analysis/*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(source.splitlines(), 1):
            for m in ID_LITERAL.finditer(line):
                key = (m.group(1) + (m.group(2) or "")).lower()
                hits.setdefault(key, []).append(f"{path.name}:{lineno}")
        for name, lineno in _keyword_names(source, path):
            if ID_KEY.match(name.lower()):
                hits.setdefault(name.lower(), []).append(f"{path.name}:{lineno}")
    return hits


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
