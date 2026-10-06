"""intent-check — do the metrics report every promise the protocol made?

The most frequent blocker class of the first audits (2026-09-08, areas
62-65) was "registered without implementation": a fork with no branch in
the code, a stop rule printed but never compared to its threshold, a
three-conjunct criterion implemented as one conjunct, gate metrics written
next to the content numbers the gate was meant to suppress. Reading catches
this late; a set comparison catches it mechanically.

The contract (Arbeitsstandard §2.A1): every registration that promises the
code something — a verdict, a branch, an abort, a control — carries an id
in the protocol text (`[K1]` criterion conjunct, `[S1]` stop rule, `[W1]`
registered fork, `[N1]` null condition / gate), and every id reappears as a
lowercase key in the reportable run's metrics.json (`k1_pass`, `s1_hit`,
`w1_branch`, `n1_pass`, or the bare id). This command checks the two sets
against each other, in both directions:

- an id with no metrics key: the promise has no implementation evidence;
- a metrics key in the id namespace with no registration: something was
  built that nobody registered.

W (not F) for forks, deliberately: `f1`/`f1_score` is a standard metric
name, and in the F namespace an f1_score in the metrics would have
"satisfied" a registered fork that has no branch at all.

Existence, not correctness: a key `s1_hit` proves the stage reports, not
that it computes the right thing — the semantic half stays with the
preflight audit (§2.A12), which works the same ids.

Since 2026-10-06 the alphabet lives in `promises`: the letters C
(criterion), A (admissibility), B (branch), and the promise block that
makes them data. With a block, three more checks run here — text and block
name the same ids, every declared key is reported exactly, and the run
recorded this very block. The legacy letters above stay valid in prose.

Opt-in by presence: a protocol without ids (everything before 2026-09-09)
exits 0 with a note. No retrofitting of closed runs.

WHICH run answers is decided by the binding, not by the directory: from
Standard 0.16 a protocol carries an id and a run records the id it belongs
to, so only completed runs with that id take part in the automatic choice
(`docs/protocol-run-binding.md`). `protocol.path` never selects — it goes
stale by design. Below 0.16 nothing binds, and the check refuses to guess
in an area with several protocols.
"""

from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

try:
    from labkit import promises
except ImportError:                       # vendored flat copies (student repos)
    import promises  # type: ignore

# The alphabet lives in `promises`; these names stay importable from here
# because code_check and tools outside labkit (befundregister) use them.
ID_IN_PROTOCOL = promises.ID_IN_PROTOCOL
ID_KEY = promises.ID_KEY
registered_ids = promises.registered_ids
reported_intent_ids = promises.reported_ids


def ledger_ids(metrics: dict) -> set[str]:
    """Deprecated alias of `reported_intent_ids` (renamed 2026-09-26).

    "Ledger" named three different things in this package — runs.tsv, a
    run's metrics.json, and the hand-written `## Runs` section of a
    protocol — and the discussion that fixed the vocabulary kept tripping
    over which one was meant. The name is gone from the package; the symbol
    stays for one cycle because it is imported from outside
    (counterfactual-worlds/tools/befundregister.py).
    """
    warnings.warn("ledger_ids() is deprecated; use reported_intent_ids()",
                  DeprecationWarning, stacklevel=2)
    return reported_intent_ids(metrics)


try:
    from labkit.runlog import run_state
except ImportError:                       # vendored flat copies (student repos)
    def run_state(run_dir: Path, cfg: dict, alive: bool | None) -> str:
        """Fallback for a runlog too old to know completion markers: then
        every run in reach is a legacy run, and metrics.json is its marker."""
        return "completed" if (run_dir / "metrics.json").is_file() else "crashed"


PROTOCOL_ID_IN_FILE = re.compile(r"protocol[ _]id[^:\n]*:\**\s*\**\s*(\S+)", re.I)
PROTOCOL_ID_SHAPE = re.compile(r"^p-[0-9a-f]{16}$")


def protocol_id_of(text: str) -> str | None:
    """The protocol's own id, or None below Standard 0.16."""
    m = PROTOCOL_ID_IN_FILE.search(text)
    if not m:
        return None
    pid = m.group(1).strip().strip("`*")
    return pid if PROTOCOL_ID_SHAPE.match(pid) else None


def run_facts(run_dir: Path) -> dict | None:
    """What a run directory says about itself: state and binding.

    `None` for a directory with no readable config.json — not a run this
    check can judge.
    """
    cfg_file = run_dir / "config.json"
    if not cfg_file.is_file():
        return None
    try:
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    binding = cfg.get("protocol") or {}
    return {"dir": run_dir,
            "metrics": run_dir / "metrics.json",
            "state": run_state(run_dir, cfg, alive=False),
            "schema": cfg.get("schema_version", 0),
            "protocol_id": binding.get("id")}


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
            facts["why"] = facts["state"]
        elif facts["protocol_id"] == pid:
            taken.append(facts)
            continue
        elif facts["protocol_id"]:
            facts["why"] = f"bound to {facts['protocol_id']}"
        elif facts["schema"] >= 2:
            facts["why"] = "unbound (no protocol id at run time)"
        else:
            facts["why"] = "legacy run (no binding recorded)"
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
        try:
            if reported_intent_ids(json.loads(
                    facts["metrics"].read_text(encoding="utf-8"))):
                return facts["metrics"], skipped
        except (OSError, json.JSONDecodeError):
            pass
        skipped += 1
    return (cands[-1]["metrics"], 0) if cands else (None, 0)


def gate_metrics(area: Path) -> tuple[Path | None, int]:
    """The metrics.json to hold the protocol against, plus how many NEWER
    runs were skipped for lacking intent keys.

    Newest-with-intent-keys, not newest: a producer or probe run writes a
    metrics.json too, and holding the promises against THAT file reports
    every promise as unimplemented (2026-09-09, area 71 — the check ran
    against the producer's metrics and cried wolf). If no run reports any
    intent key, the newest file is the honest target: the promises really
    have no evidence yet. Run dirs are timestamp-named, so lexicographic
    order is temporal order.
    """
    runs = sorted(area.glob("runs/*/metrics.json"))
    skipped = 0
    for p in reversed(runs):
        try:
            if reported_intent_ids(json.loads(p.read_text(encoding="utf-8"))):
                return p, skipped
        except (OSError, json.JSONDecodeError):
            pass
        skipped += 1
    return (runs[-1], 0) if runs else (None, 0)


def latest_metrics(area: Path) -> Path | None:
    """The gate run's metrics.json (see gate_metrics). Name and signature
    kept stable: tools outside labkit build on it (befundregister)."""
    return gate_metrics(area)[0]


def runs_by_intent_keys(area: Path) -> tuple[list[Path], list[Path]]:
    """The area's run metrics, split into those reporting intent keys and
    those reporting none — the candidates and the rest, for the operator who
    has to name a run by hand."""
    keyed: list[Path] = []
    bare: list[Path] = []
    for p in sorted(area.glob("runs/*/metrics.json")):
        try:
            hit = bool(reported_intent_ids(json.loads(p.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            hit = False
        (keyed if hit else bare).append(p)
    return keyed, bare


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: intent-check <PROTOCOL-*.md> [--metrics FILE]")
        print("  --metrics FILE  metrics.json to check against. Default: "
              "the newest COMPLETED run bound to this protocol's id that "
              "reports intent keys. Below Standard 0.16 no run records a "
              "binding; then the area must hold exactly one protocol, or "
              "this flag is required.")
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
        block = promises.parse_block(text)
    except promises.PromiseError as exc:
        print(f"{protocol}: promise block: {exc}")
        return 2
    if block is not None:
        only_prose, only_block = promises.prose_mismatch(text, block)
        for i in only_prose:
            print(f"{protocol}: [{i}] appears in the text but not in the "
                  f"promise block — a promise must be data to be checked.")
        for i in only_block:
            print(f"{protocol}: [{i}] is in the promise block but never "
                  f"named in the text — say what it promises where the "
                  f"reader looks.")
        if only_prose or only_block:
            return 1

    reg = registered_ids(text)
    if not reg:
        print("intent-check: no intent ids registered ([C1]/[A1]/[B1], "
              "legacy [K1]/[S1]/[W1]/[N1] — §2.A1); nothing to hold the "
              "metrics against.")
        return 0

    pid = protocol_id_of(text)

    if metrics_arg is not None:
        if not metrics_arg.is_file():
            print(f"intent-check: no such metrics file: {metrics_arg}")
            return 2
        # An explicit file still has to be a file that MAY answer for this
        # protocol. Naming one was always a seatbelt, never a proof of
        # belonging — where the run records a binding, that proof now
        # exists and is checked (2026-09-26).
        facts = run_facts(metrics_arg.parent)
        # A v2 run that did not complete has numbers on disk and no finish —
        # "nothing may report it" (protocol-run-binding.md). The automatic
        # path already enforces this; the explicit path must do the same,
        # otherwise naming the file is a loophole around completion. Legacy
        # runs (schema < 2) predate completion markers, so they keep the old
        # behaviour (metrics.json IS their completion evidence).
        if facts and facts["schema"] >= 2 and facts["state"] != "completed":
            print(f"intent-check: {metrics_arg.parent.name} is not completed "
                  f"({facts['state']}) — an incomplete run's numbers may not "
                  f"be reported, even when named explicitly.")
            return 2
        if facts and facts["schema"] >= 2 and facts["protocol_id"]:
            if pid and facts["protocol_id"] != pid:
                print(f"intent-check: {metrics_arg} belongs to protocol "
                      f"{facts['protocol_id']}, this protocol is {pid} — "
                      f"holding one protocol's promises against another "
                      f"protocol's run answers nothing.")
                return 2
            if pid is None:
                print(f"intent-check: WARNING — {metrics_arg} is bound to "
                      f"{facts['protocol_id']}, but {protocol.name} carries "
                      f"no `Protocol id:` (Standard 0.16) to hold it "
                      f"against. Checking anyway, unverified.")
        elif facts and facts["schema"] >= 2:
            print(f"intent-check: WARNING — {metrics_arg} records no "
                  f"binding (unbound run); nothing proves it belongs to "
                  f"{protocol.name}. Explicit legacy choice, unverified.")
        else:
            print(f"intent-check: WARNING — {metrics_arg} predates run "
                  f"bindings; nothing proves it belongs to {protocol.name}. "
                  f"Explicit legacy choice, unverified.")
        mpath = metrics_arg
    elif pid is not None:
        # Standard 0.16 and up: the run says which protocol it belongs to,
        # so the choice is a filter, not a guess. Only COMPLETED runs with
        # this id take part — an unfinalized or corrupt run has numbers on
        # disk and no finish, and a run bound elsewhere answers for another
        # question entirely.
        cands, rest = bound_runs(protocol.parent, pid)
        if not cands:
            print(f"intent-check: no completed run bound to {pid} "
                  f"({protocol.name}) — nothing to hold the promises "
                  f"against.")
            if rest:
                print(f"  {len(rest)} other run(s) in {protocol.parent}:")
                for f in rest:
                    print(f"    {f['dir'].name}: {f['why']}")
            else:
                print(f"  no runs in {protocol.parent} yet.")
            print("  Name one explicitly with --metrics FILE if you know it "
                  "belongs here.")
            return 2
        mpath, skipped = newest_with_intent_keys(cands)
        assert mpath is not None, "cands is non-empty, so a metrics file exists"
        if skipped:
            print(f"intent-check: using {mpath.parent.name}/metrics.json "
                  f"(newest bound run with intent keys; skipped {skipped} "
                  f"newer bound run(s) without any).")
    else:
        # Below Standard 0.16 nothing in a run names its protocol. Fail
        # closed instead of guessing. `gate_metrics` picks by the area,
        # not by the protocol — it cannot tell an s13 run from an s1 run,
        # because nothing in a run says which protocol it belongs to. With
        # one protocol in the area the guess is right by construction; with
        # several it is a coin toss dressed as a check, so the caller names
        # the run. The real fix is a protocol id in the run metadata; until
        # then this flag is a seatbelt, not a proof of belonging (2026-09-26).
        siblings = sorted(protocol.parent.glob("PROTOCOL-*.md"))
        if len(siblings) > 1:
            print(f"intent-check: {len(siblings)} protocols in "
                  f"{protocol.parent} — nothing ties a run to one of them, "
                  f"so name the run with --metrics FILE:")
            for p in siblings:
                here = " <- checking this one" if p.name == protocol.name else ""
                print(f"  {p.name}{here}")
            keyed, bare = runs_by_intent_keys(protocol.parent)
            print(f"  candidate runs (intent keys reported): {len(keyed)}")
            for p in keyed:
                print(f"    {p}")
            if bare:
                print(f"  runs without intent keys ({len(bare)}): "
                      f"{', '.join(p.parent.name for p in bare)}")
            return 2

        mpath, skipped = gate_metrics(protocol.parent)
        if mpath is None:
            print(f"intent-check: {len(reg)} id(s) registered "
                  f"({', '.join(sorted(reg))}), no runs/*/metrics.json yet — "
                  f"the contract is due at report time.")
            return 0
        if skipped:
            print(f"intent-check: using {mpath.parent.name}/metrics.json "
                  f"(newest with intent keys; skipped {skipped} newer "
                  f"run(s) without any).")

    assert mpath is not None, "every branch above returns or sets mpath"
    try:
        metrics = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"intent-check: cannot read {mpath}: {exc}")
        return 2
    led = reported_intent_ids(metrics)

    missing = sorted(reg - led)
    unregistered = sorted(led - reg)
    for i in missing:
        print(f"{protocol}: [{i.upper()}] registered, but {mpath.name} has no "
              f"'{i}'/'{i}_*' key — the promise has no implementation "
              f"evidence in the metrics.")
    for i in unregistered:
        print(f"{mpath}: key '{i}'/'{i}_*' is in the intent-id namespace, but "
              f"the protocol registers no [{i.upper()}] — built without a "
              f"registration.")
    block_findings = (check_block_against_run(block, mpath, metrics)
                      if block is not None else [])
    for f in block_findings:
        print(f)
    if missing or unregistered or block_findings:
        return 1
    print(f"intent-check: {len(reg)} id(s) registered, all report in "
          f"{mpath.name}."
          + (f" Promise block {block.sha} is the one the run recorded."
             if block is not None else ""))
    return 0


def check_block_against_run(block: "promises.PromiseBlock", mpath: Path,
                            metrics: dict) -> list[str]:
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
            out.append(f"{mpath}: [{p.id}] declares key '{p.key}', which the "
                       f"run does not report.")
    cfg_file = mpath.parent / "config.json"
    recorded = None
    if cfg_file.is_file():
        recorded = json.loads(cfg_file.read_text(encoding="utf-8")).get("promises")
    if recorded is None:
        out.append(f"{mpath.parent.name}: the run recorded no promise block — "
                   f"it ran before the block existed or outside runlog; "
                   f"rerun so the number is bound to the promises "
                   f"(block {block.sha}).")
    elif recorded.get("block_sha") != block.sha:
        out.append(f"{mpath.parent.name}: ran under promise block "
                   f"{recorded.get('block_sha')}, the protocol now carries "
                   f"{block.sha} — the promises changed after the run.")
    return out


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
    metrics.json as `"k1_pass"` however it is assembled, and a literal is
    what every assembly path has in common.

    `suffixed_only` keeps `"s1_hit"` and drops a bare `"s65"`. A bare id in
    the namespace is ambiguous — area 72 names its source sessions `"s65"`,
    `"s68"`, `"s69"` after the areas they come from, and reading those as
    unregistered promises produced three findings and no defect (2026-09-10).
    For "registered but absent from the code" every literal counts; for the
    reverse direction only an unmistakable metric key does.

    """
    hits: dict[str, list[str]] = {}
    for path in sorted(area.glob("scripts/*.py")) + sorted(
            area.glob("analysis/*.py")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for m in ID_LITERAL.finditer(line):
                if suffixed_only and not m.group(2):
                    continue
                hits.setdefault(m.group(1).lower(), []).append(
                    f"{path.name}:{lineno}")
    return hits

