"""intent-check — does the ledger report every promise the protocol made?

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

- an id with no ledger key: the promise has no implementation evidence;
- a ledger key in the id namespace with no registration: something was
  built that nobody registered.

W (not F) for forks, deliberately: `f1`/`f1_score` is a standard metric
name, and in the F namespace an f1_score in the ledger would have
"satisfied" a registered fork that has no branch at all.

Existence, not correctness: a key `s1_hit` proves the stage reports, not
that it computes the right thing — the semantic half stays with the
preflight audit (§2.A12), which works the same ids.

Opt-in by presence: a protocol without ids (everything before 2026-09-09)
exits 0 with a note. No retrofitting of closed runs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ID_IN_PROTOCOL = re.compile(r"\[([KSWN]\d+)\]", re.I)
ID_KEY = re.compile(r"^([kswn]\d+)(?:_.*)?$")


def registered_ids(text: str) -> set[str]:
    """Ids promised anywhere in the protocol (structure free, fields duty)."""
    return {m.group(1).lower() for m in ID_IN_PROTOCOL.finditer(text)}


def ledger_ids(metrics: dict) -> set[str]:
    """Ids the metrics file reports (bare id or id_suffix keys)."""
    out = set()
    for key in metrics:
        m = ID_KEY.match(str(key))
        if m:
            out.add(m.group(1))
    return out


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
            if ledger_ids(json.loads(p.read_text(encoding="utf-8"))):
                return p, skipped
        except (OSError, json.JSONDecodeError):
            pass
        skipped += 1
    return (runs[-1], 0) if runs else (None, 0)


def latest_metrics(area: Path) -> Path | None:
    """The gate run's metrics.json (see gate_metrics). Name and signature
    kept stable: tools outside labkit build on it (befundregister)."""
    return gate_metrics(area)[0]


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: intent-check <PROTOCOL-*.md> [--metrics FILE]")
        print("  --metrics FILE  metrics.json to check against "
              "(default: the newest runs/*/metrics.json beside the protocol)")
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
    reg = registered_ids(protocol.read_text(encoding="utf-8"))
    if not reg:
        print("intent-check: no intent ids registered ([K1]/[S1]/[W1]/[N1] "
              "— §2.A1); nothing to hold the ledger against.")
        return 0

    if metrics_arg is not None:
        if not metrics_arg.is_file():
            print(f"intent-check: no such metrics file: {metrics_arg}")
            return 2
        mpath = metrics_arg
    else:
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

    try:
        metrics = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"intent-check: cannot read {mpath}: {exc}")
        return 2
    led = ledger_ids(metrics)

    missing = sorted(reg - led)
    unregistered = sorted(led - reg)
    for i in missing:
        print(f"{protocol}: [{i.upper()}] registered, but {mpath.name} has no "
              f"'{i}'/'{i}_*' key — the promise has no implementation "
              f"evidence in the ledger.")
    for i in unregistered:
        print(f"{mpath}: key '{i}'/'{i}_*' is in the intent-id namespace, but "
              f"the protocol registers no [{i.upper()}] — built without a "
              f"registration.")
    if missing or unregistered:
        return 1
    print(f"intent-check: {len(reg)} id(s) registered, all report in "
          f"{mpath.name}.")
    return 0


def cli() -> None:
    """Entry point for the installed `intent-check` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()


# --- preflight half: ids against the CODE, before any run exists ----------
#
# main() above answers the report-time question (does the LEDGER report every
# promise?) and needs a runs/*/metrics.json. Before the run that file does not
# exist, so the same promise goes unchecked exactly when checking it is still
# cheap. code_ids() answers the earlier question from the source: does the code
# even MENTION the key it is supposed to report? An id that appears nowhere in
# the scripts cannot report at run time — that is mechanical, not a judgement.

ID_LITERAL = re.compile(r"""['"]([kswn]\d+)(_[a-z0-9_]*)?['"]""")


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
