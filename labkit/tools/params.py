"""labkit-params — the values a run ran with, each with its home and what the line proves.

    labkit-params <AREA> [--run RUN_ID] [--protocol PROTOCOL-*.md]

"Which value held in this run, and where was it decided?" otherwise takes
four files (the script's constants, its design object, the run's
config.json, models.toml). This is the one view, a
projection of the canonical sources, never a source itself: the first line
names the run and the protocol it reads; every row says where the value
has its home and which tier the claim belongs to.

What a row claims — and no more:

  recorded            the run recorded this key with this value          guaranteed
  registered constant the constant the run's own promise snapshot
                      registered and the recorded value are equal /
                      differ                                              guaranteed
                      the record carries no key of that name: its absence
                      is certain, reading it as a fault is                static evidence
  model               the model that answered these rows, from the
                      `models_resolved` of the run that recorded it —
                      a derived run records none, so the walk along
                      `derived_from` names the ancestor (`answering_run.
                      model_provenance_run`); a chain without one says so  guaranteed
  module constant     an UPPER_CASE constant in the script as the run
                      kept it (its script-source.py) with no key of its
                      name in the record — whether it moves the number is
                      not claimed                                         static evidence

Whether the record is COMPLETE is not a claim this view can make: an old
run and a new one carry the same schema, and only the area's own test (the
record held to the config object's fields) proves completeness. The model
is read from the run's record, never resolved against today's models.toml,
and so are the registered constants and the script's literals: a named
older run shows what it ran with, not today's protocol or script. A run
that kept no script copy shows its literals as not available.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.formats.runs import run_path, runs_path, script_copy_path
from labkit.formats import console, promises, protocol_block
from labkit.formats.repo import (
    AmbiguousArea,
    area_path,
    choose_protocol,
    no_such_area,
)
from labkit.formats.runs import read_run_config
from labkit.formats.scope_sha import parse_source
from labkit.formats.area_state import state_of
from labkit.formats.runs import lineage, model_provenance_run


@dataclass(frozen=True)
class ParamRow:
    """One line of the table: a value, where it lives, what the line proves.

    Attributes:
        name: The parameter (a config key, a promise constant, an alias).
        value: The value as the home states it.
        home: The authoritative source — the run's record, the protocol's
            promise, the ancestor's `models_resolved`, the script line.
        meaning: What the value is to the measurement (registered constant,
            recorded parameter, the answering model, an unrecorded constant).
        in_run: The value the run recorded under that name, or "—".
        evidence_kind: `gate.GUARANTEED` or `gate.STATIC_EVIDENCE`, nothing
            else — what carries the line. A registered constant the record
            lacks is static evidence: its absence is certain, the fault it
            suggests is not; `in_run` says "not recorded".
    """

    name: str
    value: str
    home: str
    meaning: str
    in_run: str
    evidence_kind: str


def _shown(value: object, width: int = 38) -> str:
    """A value as one short cell."""
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return text if len(text) <= width else text[: width - 1] + "…"


def _looks_like_model_spec(value: object) -> bool:
    """A dict shaped like `llm.resolve`'s spec (alias/model/endpoint) — a
    resolved model recorded under a key runlog does not read."""
    return (
        isinstance(value, dict)
        and "model" in value
        and ("alias" in value or "endpoint" in value)
    )


def recorded_rows(run_config: dict, run_name: str) -> list[ParamRow]:
    """Every key the run recorded under `config`: certain, and nothing more.
    A resolved model spec under a key other than `model`/`*_model` is
    marked: the run recorded it, but it is not provenance labkit holds
    (runlog resolves `model` keys into `models_resolved`; a `judge` key,
    for one, is not resolved)."""
    rows = []
    for key, value in sorted(run_config.items()):
        spec = _looks_like_model_spec(value) and not (
            key == "model" or key.endswith("_model")
        )
        rows.append(
            ParamRow(
                name=key,
                value=_shown(value),
                home=f"{run_name}/config.json: config.{key}",
                meaning=(
                    "looks like a resolved model spec under a key runlog does not read "
                    "(`model`, `*_model`) — recorded, not provenance labkit holds"
                    if spec
                    else "recorded parameter of this run"
                ),
                in_run=_shown(value),
                evidence_kind=STATIC_EVIDENCE if spec else GUARANTEED,
            )
        )
    return rows


def constant_rows(
    registered: list[tuple[str, dict]],
    run_config: dict,
    run_name: str,
    copies: dict[str, tuple[object, int]],
    script: str,
) -> list[ParamRow]:
    """The constants the run's promise snapshot registered (REGISTERED,
    `promises.snapshot_constants`) against the record: equal, different,
    or missing — the state is certain; a missing one is a fault only as
    evidence, and the strongest evidence is a literal of the same name in
    SCRIPT, the script the literals were read from, in either case
    (`copies`: name -> (value, line); `min_f1` is copied as `MIN_F1`)."""
    rows = []
    for rec in promises.constant_records_of(registered, run_config):
        if rec.state == "missing":
            copy_name = next(
                (n for n in (rec.name, rec.name.upper()) if n in copies), None
            )
            held = (
                f"; {script}:{copies[copy_name][1]} holds "
                f"{copy_name} = {copies[copy_name][0]!r}"
                if copy_name
                else ""
            )
            in_run = f"— (not recorded{held})"
            kind = STATIC_EVIDENCE
        else:
            in_run = _shown(rec.recorded) + (
                "" if rec.state == "equal" else "  ≠ DIFFERS"
            )
            kind = GUARANTEED
        rows.append(
            ParamRow(
                name=rec.name,
                value=_shown(rec.promised),
                home=f"{run_name}/config.json: promises [{rec.promise_id}] constants",
                meaning="registered constant",
                in_run=in_run,
                evidence_kind=kind,
            )
        )
    return rows


def model_rows(run_dir: Path) -> list[ParamRow]:
    """The model that answered the rows, from the record that holds it.

    Raises:
        ValueError: From `runs.lineage` — a broken `derived_from`
            chain, wherever in it.
    """
    found = model_provenance_run(run_dir)
    chain = [run.name for run in lineage(run_dir)]
    if found is None:
        return [
            ParamRow(
                name="model",
                value="—",
                home="no run in the lineage recorded models_resolved",
                meaning="model provenance: not recorded in models_resolved along lineage "
                + " → ".join(chain),
                in_run="—",
                evidence_kind=GUARANTEED,
            )
        ]
    found_cfg = read_run_config(found)
    resolved = found_cfg.models_resolved if found_cfg else {}
    via = chain[: chain.index(found.name)]
    home = f"models_resolved of {found.name}" + (
        f", inherited through {' → '.join(via)}" if via else ""
    )
    rows = []
    for alias, spec in sorted(resolved.items()):
        model = spec.get("model", "?") if isinstance(spec, dict) else "?"
        endpoint = spec.get("endpoint") if isinstance(spec, dict) else None
        rows.append(
            ParamRow(
                name=f"model {alias}",
                value=f"{alias} → {model}" + (f" @ {endpoint}" if endpoint else ""),
                home=home,
                meaning="the model that answered these rows",
                in_run="recorded"
                if found == run_dir
                else f"inherited from {found.name}",
                evidence_kind=GUARANTEED,
            )
        )
    return rows


def script_literals(script: Path) -> dict[str, tuple[object, int]]:
    """Names assigned a literal at module level of SCRIPT: name -> (value,
    line). Empty without the script. A registered constant's copy is
    looked up here under its own name; the evidence rows take the
    UPPER_CASE ones. Raises SourceError (a ValueError) naming the script
    when it does not parse."""
    if not script.is_file():
        return {}
    out: dict[str, tuple[object, int]] = {}
    for node in parse_source(script).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target, value = node.targets[0], node.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant):
            out[target.id] = (value.value, node.lineno)
    return out


def script_constant_rows(
    literals: dict[str, tuple[object, int]],
    run_config: dict,
    registered: set[str],
    script: str,
) -> list[ParamRow]:
    """Module constants with no key of their name (either case) in the record
    and no registered row of their own (either case: `MIN_F1` is the copy of
    the registered `min_f1` and stands in its row) — evidence of a value the run may
    have used without recording it, not a proof."""
    return [
        ParamRow(
            name=name,
            value=_shown(value),
            home=f"{script}:{line}",
            meaning="module constant not in the record — whether it moves the number is not claimed",
            in_run="—",
            evidence_kind=STATIC_EVIDENCE,
        )
        for name, (value, line) in literals.items()
        if name.isupper()
        and name not in run_config
        and name.lower() not in run_config
        and name not in registered
        and name.lower() not in registered
    ]


def ran_script(run_dir: Path) -> Path | None:
    """The copy of the measuring script RUN_DIR kept as it ran
    (`runs.script_copy_path`), None when it kept none: today's script is
    never read in its place, since its values are not the run's."""
    copy = script_copy_path(run_dir, ".py")
    return copy if copy.is_file() else None


def no_script_row(run_dir: Path) -> ParamRow:
    """The one row of a run that kept no script copy: its module literals
    are not available, and no row stands in for them."""
    return ParamRow(
        name="script literals",
        value="not available",
        home=f"{run_dir.name}/script-source.py is missing",
        meaning="the script's values as the run ran are not available; "
        "today's script is not shown in their place",
        in_run="—",
        evidence_kind=GUARANTEED,
    )


def params_table(run_dir: Path) -> list[ParamRow]:
    """Every row of the view for one run, registered constants first — each
    from the run itself: its record, its promise snapshot, its script copy
    (`ran_script`); without that copy the literals are not available
    (`no_script_row`).

    Raises:
        ValueError: An unreadable run config or promise snapshot, or a
            broken lineage.
    """
    cfg = read_run_config(run_dir)
    if cfg is None:
        raise ValueError(f"{run_dir}: no config.json")
    run_config = cfg.config  # an object, held where the config is read
    script = ran_script(run_dir)
    literals = script_literals(script) if script is not None else {}
    script_shown = f"{run_dir.name}/{script.name}" if script is not None else ""
    rows: list[ParamRow] = []
    if cfg.promises is not None:
        registered_then = promises.snapshot_constants(cfg.promises)
        rows += constant_rows(
            registered_then, run_config, run_dir.name, literals, script_shown
        )
    # a registered constant's home is the protocol; its recorded value stands
    # in that row, not again as a recorded parameter
    registered = {r.name for r in rows}
    rows += recorded_rows(
        {k: v for k, v in run_config.items() if k not in registered}, run_dir.name
    )
    rows += model_rows(run_dir)
    if script is None:
        rows.append(no_script_row(run_dir))
    else:
        rows += script_constant_rows(literals, run_config, registered, script_shown)
    return rows


def render_table(rows: list[ParamRow]) -> str:
    """The rows as one aligned table, a header line first."""
    header = ParamRow("parameter", "value", "home", "meaning", "in run", "evidence")
    cols = ("name", "value", "home", "meaning", "in_run", "evidence_kind")
    width = {c: max(len(getattr(r, c)) for r in (header, *rows)) for c in cols}
    lines = []
    for r in (header, *rows):
        lines.append("  ".join(getattr(r, c).ljust(width[c]) for c in cols).rstrip())
    return "\n".join(lines)


def main(argv: list[str]) -> int:  # noqa: C901 complexity baseline
    """Command line: the table for one area's answering run, or a named run.
    Without --run the run is the one that answers for the stamped protocol
    id (`Measured.told`), and a choice that carries a blocker is refused
    (exit 2) — unlike finalize, which tells the same blocker and goes on
    with the chosen run (`finalize.choose_answering_run`)."""
    if not argv or console.asks_help(argv):
        lines = [
            (__doc__ or "").strip().splitlines()[0],
            "usage: labkit-params <AREA> [--run RUN_ID] [--protocol PROTOCOL-*.md]",
        ]
        return console.usage("labkit-params", "\n".join(lines), asked=bool(argv))
    try:
        area = area_path(argv[0])
    except AmbiguousArea as exc:
        console.refuse("labkit-params", str(exc))
        return 2
    protocol_arg: Path | None = None
    run_arg: str | None = None
    rest = argv[1:]
    while rest:
        if rest[0] == "--protocol" and len(rest) >= 2:
            protocol_arg, rest = Path(rest[1]), rest[2:]
        elif rest[0] == "--run" and len(rest) >= 2:
            run_arg, rest = rest[1], rest[2:]
        else:
            console.refuse("labkit-params", f"unexpected argument {rest[0]!r}")
            return 2
    if not area.is_dir():
        console.refuse("labkit-params", no_such_area(area))
        return 2
    protocol = choose_protocol(area, protocol_arg, "labkit-params")
    if protocol is None:
        return 2
    text = protocol.read_text(encoding="utf-8")
    try:
        pid = protocol_block.head(text).id
    except protocol_block.BlockError as exc:
        console.refuse("labkit-params", f"{protocol.name}: {exc}")
        return 2
    if run_arg is not None:
        run_dir = run_path(area, run_arg)
        if not run_dir.is_dir():
            console.refuse("labkit-params", f"no run {run_arg} under {runs_path(area)}")
            return 2
        how = "named with --run"
    else:
        if pid is None:
            console.refuse(
                "labkit-params", f"{protocol.name} is unstamped — name a run with --run"
            )
            return 2
        choice, blocker, lines = state_of(area).measured_of(pid).told(text)
        if blocker or choice.run_dir is None:
            console.refuse(
                "labkit-params",
                "\n".join(
                    [
                        blocker.message if blocker else "no run answers",
                        *(f"    {ln}" for ln in lines),
                    ]
                ),
            )
            return 2
        run_dir = choice.run_dir
        how = f"the run that answers for {pid}" + "".join(f" ({ln})" for ln in lines)
    print(f"params: {area.name} · {protocol.name} · run {run_dir.name} ({how})")
    try:
        rows = params_table(run_dir)
    except ValueError as exc:
        console.refuse("labkit-params", str(exc))
        return 2
    print(render_table(rows))
    return 0


def cli() -> None:
    """Console entry point of `labkit-params`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
