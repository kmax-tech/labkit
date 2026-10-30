"""A protocol head for test fixtures: the ```toml block with its [protocol] table.

One home for the shape, so a fixture states only what it varies:
`head(repeat_cost="low", frozen=True)`.
"""

from __future__ import annotations

from labkit.formats.runs import RunKind

import json
import subprocess
from pathlib import Path

from labkit.formats import promises, runs, scope_sha

PID = "p-0123456789abcdef"

#: The tables a frozen fixture carries unless it says otherwise — the stamp's
#: shape (0.71.0: frozen = true owes a promise block); the scope is the
#: script `scope_file` writes.
DEFAULT_BLOCK = """\
[[promise]]
id = "criterion-1"
key = "criterion_1_pass"
sentence = "the criterion holds"
scope = ["scripts/01_measure.py"]

[[promise]]
id = "quality-check-1"
key = "quality_check_1_pass"
sentence = "the yield suffices"
scope = ["scripts/01_measure.py"]

[[promise]]
id = "quality-check-2"
key = "quality_check_2_pass"
sentence = "the null lane sits at chance"
scope = ["scripts/01_measure.py"]
"""
#: one criterion and the prose that names it — a protocol whose run
#: reports `criterion_1_pass` alone; a block id the prose does not name, or a
#: metrics key a block id lacks, fails intent-check
C1_BLOCK = DEFAULT_BLOCK.split("\n\n")[0] + "\n"
C1_PROSE = "- **Success / failure criterion:** [criterion-1] the criterion holds\n"


def registration_of(area: Path) -> dict[str, str]:
    """The registration a record a test writes judged: that of AREA's
    `PROTOCOL-x.md` (else its one protocol) as it stands now
    (`protocol_check.registration_stamp`) — a record written right after the
    protocol covers it, as one `labkit-audit` writes would. With no protocol
    in AREA, or a head that does not read, the kind alone, unset: the record
    covers no protocol."""
    from labkit.formats import protocol_block, protocol_check

    named = area / "PROTOCOL-x.md"
    found = [named] if named.is_file() else sorted(area.glob("PROTOCOL-*.md"))
    if len(found) == 1:
        try:
            return protocol_check.registration_stamp(
                found[0].read_text(encoding="utf-8")
            )
        except protocol_block.BlockError:
            pass
    return {protocol_check.REGISTRATION_KIND: protocol_check.REGISTRATION_ABSENT}


def protocol_text_of(area: Path) -> str:
    """AREA's `PROTOCOL-x.md` (else its one protocol) as it stands now, ""
    without one — the text a record a test writes was audited on."""
    named = area / "PROTOCOL-x.md"
    found = [named] if named.is_file() else sorted(area.glob("PROTOCOL-*.md"))
    return found[0].read_text(encoding="utf-8") if len(found) == 1 else ""


def shown_sha(area: Path, run_dir: Path | None) -> str:
    """What a record a test writes binds as `shown_sha`: what MODE analysis
    shows of RUN_DIR under AREA's protocol as it stands now
    (`audit_binding.run_shown`) — the one home of that digest in the tests,
    so a record written right after the protocol covers it, as one
    `labkit-audit` writes would."""
    from labkit.checks import audit_binding

    return audit_binding.run_shown(area, run_dir, "", protocol_text_of(area)).sha


def scope_file(area: Path) -> Path:
    """The script the default block's scopes name, written if absent."""
    script = area / "scripts" / "01_measure.py"
    if not script.is_file():
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            'def evaluate_rows(rows):\n    return {"criterion_1_pass": True, "quality_check_1_pass": True, "quality_check_2_pass": True}\n',
            encoding="utf-8",
        )
    return script


def script_sha_of(script: Path) -> str:
    """The `script_sha` a run of SCRIPT records (`provenance.snapshot_script`):
    a fixture run that names the script it ran, so the code-since-run check
    (finalize station 3) finds it unchanged."""
    return scope_sha.file_digest(script)[: scope_sha.DIGEST_CHARS]


def run_record(
    fields: dict | None = None, /, *, drop: tuple[str, ...] = (), **more: object
) -> dict:
    """A complete config.json as runlog writes it — schema 4, every field of
    `runs.RUN_CONFIG_KEYS`: a measurement, unbound, no parent, no repeat, no
    data, an empty config. FIELDS and MORE replace what a test varies; a
    test of a damaged record breaks a field explicitly: DROP leaves fields
    out (a record from before the schema), or it deletes one from the
    result (`del record["unfrozen_ack"]`). The one home for the record's shape in
    the tests: a fixture that wrote a part of it read, until 2026-10-20, as
    a record with defaults."""
    record: dict = {
        "schema_version": 4,
        "experiment": "x",
        "script": "01_measure.py",
        "protocol": {"id": None, "path": None},
        "derived_from": None,
        "repeat_of": None,
        "draw": None,
        "run_kind": "measurement",
        "unfrozen_ack": False,
        "audit_failed": None,
        "repeat_cost": None,
        "promises": None,
        "script_sha": "no-script",
        "untracked_sources": [],
        "pid": 1,
        "git": "g",
        "git_full": "g",
        "python": "3.12",
        "env": "unpinned",
        "models_resolved": {},
        "started": "2026-01-01T00:00:00",
        "command": [],
        "data": {},
        "config": {},
    }
    assert tuple(record) == runs.RUN_CONFIG_KEYS, "run_record lags runs.RUN_CONFIG_KEYS"
    out = {**record, **(fields or {}), **more}
    for key in drop:
        del out[key]
    return out


def completed_run(
    area: Path,
    name: str,
    *,
    pid: str = PID,
    metrics: dict | None = None,
    completion: bool = True,
    run_kind: RunKind = "measurement",
    unfrozen_ack: bool = False,
) -> Path:
    """A run directory as runlog leaves one: bound to PID, its promise
    snapshot taken from the area's PROTOCOL-x.md (0.71: a run under a frozen
    protocol recorded its block), a full run unless LONG says a probe, not
    acknowledged unless UNFROZEN_ACK (0.99.0: both recorded, `runs.unreportable`),
    METRICS written when given, finished when COMPLETION. The one home for the
    shape (finalize, report-check)."""
    d = area / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    script = scope_file(area)  # the block's scopes name the fixture's script
    block = promises.parse_block((area / "PROTOCOL-x.md").read_text(encoding="utf-8"))
    cfg = run_record(
        script_sha=script_sha_of(script),
        protocol={"id": pid, "path": "PROTOCOL-x.md"},
        run_kind=run_kind,
        unfrozen_ack=unfrozen_ack,
        promises=promises.snapshot(block, area) if block is not None else None,
    )
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if metrics is not None:
        (d / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 4,
                    "finished": "x",
                    "git": "g",
                    "git_full": "g",
                    "note": "",
                }
            ),
            encoding="utf-8",
        )
    return d


def head(
    *,
    id: str = PID,
    type: str = "exploratory",
    repeat_cost: str = "high",
    kind: str | None = None,
    frozen: bool = False,
    preflight_audit: str = "",
    promises: str | None = "",
    result: str | None = None,
    model: str | None = None,
    claim: str = "",
    arms: dict[str, tuple[str, str, str | None]] | None = None,
    labels: tuple[str, ...] | None = None,
    report: str | None = None,
    reference: str | None = None,
) -> str:
    """The fenced TOML block; `promises` is appended inside it verbatim. A
    frozen or low head without an explicit block carries `DEFAULT_BLOCK`;
    `None` means no block even then (the mutant of standard 0.19's rule).
    RESULT is the run id a `[result]` table declares (phase 3, 2026-10-21);
    MODEL the alias of a `[model]` table, ARMS its `[model.arms.<arm>]`
    tables as {arm: (profile, fingerprint, alias)}, LABELS a `[gate]` table
    (phase 4). CLAIM is TOML written into `[model]` below the alias verbatim
    (`number_describes`, `annotation_validity`). KIND is the head's `kind` (standard 0.22); None derives it as
    the stamp would — `apply` with a model, else `compute` — so a fixture
    states only what it varies; a literal `kind="<compute | fit | apply>"`
    writes the placeholder. REPORT is the head's optional `report`, the
    registered report file (standard 0.23, 2026-10-29). REFERENCE is TOML
    written into a `[reference]` table verbatim — a computation's stated
    value (2026-10-29)."""
    if kind is None:
        kind = "apply" if model is not None else "compute"
    if promises == "" and (frozen or repeat_cost == "low"):
        promises = (
            DEFAULT_BLOCK  # frozen, or at low repeat cost every run is the full run
        )
    promises = promises or ""
    lines = [
        "```toml",
        "[protocol]",
        'standard = "0.23"',
        f'id = "{id}"',
        f'type = "{type}"',
        f'repeat_cost = "{repeat_cost}"',
        f'kind = "{kind}"',
        f"frozen = {'true' if frozen else 'false'}",
        f'preflight_audit = "{preflight_audit}"',
    ]
    if report is not None:
        lines.append(f'report = "{report}"')
    if result is not None:
        lines += ["", "[result]", f'run = "{result}"']
    if model is not None:
        lines += _model_tables(model, claim, arms)
    if reference is not None:
        lines += ["", "[reference]", *reference.strip().splitlines()]
    if labels is not None:
        lines += [
            "",
            "[gate]",
            "labels = [" + ", ".join(f'"{x}"' for x in labels) + "]",
        ]
    body = "\n".join(lines) + "\n"
    if promises:
        body += "\n" + promises.strip() + "\n"
    return body + "```\n"


def _model_tables(
    model: str, claim: str, arms: dict[str, tuple[str, str, str | None]] | None
) -> list[str]:
    """The `[model]` table and its arms, as `head` writes them."""
    lines = ["", "[model]", f'alias = "{model}"']
    lines += claim.strip().splitlines()
    for arm, (profile, fingerprint, alias) in (arms or {}).items():
        lines += [
            "",
            f"[model.arms.{arm}]",
            f'profile = "{profile}"',
            f'fingerprint = "{fingerprint}"',
        ]
        if alias is not None:
            lines.append(f'alias = "{alias}"')
    return lines


def head_commit(root: Path) -> dict[str, str]:
    """A run record's `git` and `git_full` for a run started at HEAD of the
    repository at ROOT with a clean tree — what runlog records
    (`provenance.record_provenance`): the short form and the full sha."""
    full = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {"git": full[:7], "git_full": full}


def started_at(run: Path, root: Path) -> None:
    """Record RUN as started at HEAD of ROOT (`head_commit`), as a run in a
    repository records it: report-check holds the low registration to the
    commit of the first measurement."""
    cfg = run / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data.update(head_commit(root))
    cfg.write_text(json.dumps(data), encoding="utf-8")


def decide_words(*words: str) -> list[str]:
    """WORDS after `--decide N` as the command takes them: `STATUS --why
    REASON`, a given `--effect stands` dropped (a limit writes it) and
    `--effect "<ids> not assessable"` as `--not-assessable <ids>`. Words
    already in that form, or a STATUS alone, pass unchanged — the one place
    the tests' older call shapes meet the command."""
    if not words:
        return []
    status, rest = words[0], list(words[1:])
    if rest and not rest[0].startswith("--"):
        rest = ["--why", rest[0], *rest[1:]]
    out: list[str] = [status]
    i = 0
    while i < len(rest):
        if rest[i] == "--effect" and i + 1 < len(rest):
            value = rest[i + 1]
            if value.endswith(" not assessable"):
                out += ["--not-assessable", value.removesuffix(" not assessable")]
            i += 2
            continue
        out.append(rest[i])
        i += 1
    return out
