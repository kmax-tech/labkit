"""start_check — what refuses a run before its directory exists, in order.

Two phases of `runlog.Run`'s start live here: the preparation
(`prepare`: the protocol binding, the promise snapshot, the config
frozen; it refuses what cannot be read) and the checks the constructor
sequences — the seconds registration (`registration_refusal`), the
detach gate (`foreground_refusal`, with `foreground_timeout`), and for a
full run the freeze gate (`freeze_gate`: undecided blockers, the freeze
or the registration, the acknowledgement over a failed audit). Each
refusal raises with the sentence a person acts on; nothing here writes.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from labkit.formats.runs import RunKind, parse_run_kind

from labkit.formats import findings, promises, protocol_block, repo
from labkit.formats.standard_contract import PREFLIGHT_AUDIT, lane
from labkit.formats.scope_sha import area_stamp
from labkit.formats.runs import (
    COMPLETED,
    RunConfigError,
    completion_state,
    read_run_config,
    repeat_parent,
)


@dataclass(frozen=True)
class _Bound:
    """The bound protocol, read once at binding: `binding` is the record
    config.json carries ({"id": ..., "path": ...}, both None when unbound),
    `text` and `head` the protocol as read then (None when unbound). The
    freeze gate and the registration check take it instead of reading the
    file again (three reads and three parses before, audit 2026-10-13)."""

    binding: dict
    text: str | None
    head: "protocol_block.Head | None"

    @property
    def name(self) -> str:
        """The protocol's file name, `(unbound)` without one."""
        path = self.binding.get("path")
        return Path(path).name if isinstance(path, str) and path else "(unbound)"


def protocol_binding(base_dir: Path, protocol: str | Path | None) -> _Bound:
    """Which protocol this run belongs to, with its text and head.

    The record's shape never varies — `id` and `path` always exist, only
    the values change. A reader never has to tell an absent key from null
    from an object (2026-09-26).

    `id` is the binding; `path` is relative to the area, for lookup and
    diagnosis, and may go stale. An explicit protocol must lie inside the
    area and be one of the PROTOCOL-*.md found there, or the run would bind
    to a file nobody checked. Omitted: one protocol binds, several are a
    hard error (guessing is what this whole mechanism exists to stop), none
    is unbound with a warning.
    """
    found = repo.area_protocols(base_dir)
    if protocol is not None:
        path = Path(protocol)
        if not path.is_absolute():
            path = base_dir / path
        path = path.resolve()
        if path not in [f.resolve() for f in found]:
            raise SystemExit(
                f"runlog: protocol={protocol!r} is not one of the "
                f"PROTOCOL-*.md in the run's area ({base_dir}):\n  "
                + "\n  ".join(f.name for f in found or [Path("(none)")])
            )
    elif len(found) == 1:
        path = found[0].resolve()
    elif not found:
        print(
            f"runlog: WARNING — no PROTOCOL-*.md in {base_dir}; this run "
            f"is recorded as unbound. A kept number needs a protocol "
            f"(LAB-003 No run without an intent paragraph)."
        )
        return _Bound({"id": None, "path": None}, None, None)
    else:
        raise SystemExit(
            f"runlog: {len(found)} protocols in {base_dir} — nothing would "
            f"say which one this run belongs to. Name it:\n"
            f"  runlog.run(..., protocol=PROTOCOL)\n  "
            + "\n  ".join(f.name for f in found)
        )

    try:
        rel = str(path.relative_to(base_dir.resolve()))
    except ValueError:
        rel = str(path)
    text = path.read_text(encoding="utf-8")
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        raise SystemExit(f"runlog: {rel}: {exc}") from exc
    if head.id is None:
        print(
            f"runlog: WARNING — {rel} carries no stamped id (`id` in its "
            f"[protocol] table); this run is recorded as unbound."
        )
    return _Bound({"id": head.id, "path": rel}, text, head)


def _freeze_findings(base_dir: Path, bound: _Bound) -> list[str]:
    """Why a FULL run may not start on this protocol — empty means it may."""
    from labkit.formats.protocol_check import seconds_registration_missing

    text, head = bound.text, bound.head
    if text is None or head is None:
        return [
            "the run is unbound (no protocol) — a full run needs a "
            "registered protocol (LAB-003 No run without an intent paragraph)"
        ]
    path = Path(bound.name)
    if bound.binding.get("id") is None:
        # a full run's number must be bound; an unstamped id binds nothing,
        # and finalize would only say so after the number exists (review 2026-10-07)
        return [
            f"{path.name}: the [protocol] id is not stamped — a full run "
            f"needs a bound protocol (`labkit-init exp` stamps it)"
        ]
    # the freeze or the registration: the lane's answer (`standard_contract`)
    if lane(head.cost).registration:
        missing = seconds_registration_missing(text)
        if not missing:
            return []
        return [
            f'{path.name}: `cost = "{head.cost}"`, but the registration is not '
            f"written: {', '.join(missing)} still empty or a placeholder — at "
            f"seconds the gate is the question (with a model also criterion · "
            f"admissibility condition), not the freeze (LAB-003 No run without an intent paragraph, LAB-017 The number of audits follows the cost tier)"
        ]
    out = []
    if not head.frozen:
        out.append(f"{path.name}: not `frozen = true`")
    out += _audit_line_findings(base_dir, path, head.preflight_audit, text)
    return out


def _undecided_findings(base_dir: Path) -> tuple[list[str], list[str]]:
    """(blockers, warnings): every finding still `open` in a preflight audit
    record of the area, each as `<file>: <text>`. A record of any stamp
    counts — a finding nobody decided is an ignored finding, not an old one
    (LAB-015 Preflight audit before freezing: every finding is decided).
    Raises SystemExit on a record nobody can read."""
    try:
        records = findings.area_records(base_dir)
    except findings.FindingsError as exc:
        raise SystemExit(f"runlog: {exc}") from exc
    blockers, warnings = [], []
    for rec in records:
        if rec.mode != "preflight":
            continue
        for f in rec.open:
            (blockers if f.grade == "BLOCKER" else warnings).append(
                f"{rec.path.name}: {f.text}"
            )
    return blockers, warnings


def _audit_unavailable(base_dir: Path, bound: _Bound) -> "findings.Failed | None":
    """The failed audit attempt an acknowledged full run rests on, or
    None at `cost = "seconds"`, where no audit is owed before the run. Raises
    SystemExit when none fits: the hatch is for an audit the backend refused,
    not for one nobody started. The attempt must name the code as it stamps
    now and, under a protocol, the promise block as it reads now, and its
    call must have had the default timeout at least (`findings.ATTEMPT_TIMEOUT_S`)."""
    if bound.head is not None and PREFLIGHT_AUDIT not in lane(bound.head.cost).audits:
        return None
    try:
        sha = area_stamp(base_dir)[0]
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(
            f"runlog: LABKIT_UNFROZEN=1 — the area cannot be stamped ({exc}), so no "
            f"failed audit attempt can be held to its code"
        ) from exc
    block_sha = None
    if bound.text is not None:
        try:
            block_sha = promises.block_stamp(bound.text)
        except promises.PromiseError as exc:
            raise SystemExit(f"runlog: promise block: {exc}") from exc
    try:
        failed = findings.audit_unavailable(base_dir, sha, "preflight", block_sha)
    except findings.FindingsError as exc:
        raise SystemExit(f"runlog: {exc}") from exc
    if failed is None:
        tried = findings.failed_attempts(base_dir)
        seen = (
            "; ".join(
                f"{f.path.name} (code {f.scope_sha}, promises {f.block_sha}, "
                f"{f.timeout_s} s)"
                for f in tried
            )
            or "none"
        )
        raise SystemExit(
            "runlog: this run declares run_kind='measurement' (a full run) on a protocol not "
            "ready for one, and LABKIT_UNFROZEN=1 acknowledges an audit that "
            "could not run — not one nobody ran. No failed preflight attempt of "
            f"the code as it is now (code {sha}, promises {block_sha or 'no protocol'}, at least "
            f"{findings.ATTEMPT_TIMEOUT_S} s) is recorded; attempts: {seen}.\n"
            f"Run the audit: `labkit-audit {shown_area(base_dir)} --mode "
            "preflight`; when the backend does not answer, it writes "
            f"audits/<date>-preflight{findings.FAILED_SUFFIX}, and this "
            "acknowledgement rests on that file — and its number cannot be "
            "reported either (report-check refuses it)."
        )
    return failed


def _audit_line_findings(base_dir: Path, path: Path, line: str, text: str) -> list[str]:
    """Why the head's `preflight_audit` line does not cover a full run: empty,
    or what `findings.audit_line_gap` says of it — it waives the audit (`n/a`,
    refused since 0.99.0), its `scope sha` is not the code's now, or no
    decided preflight record saw that code and the promise block TEXT
    carries now (the block since 0.98.0)."""
    if not line:
        return [
            f"{path.name}: `preflight_audit` is empty — run `preflight`, "
            f"then the experiment-preflight audit (LAB-015 Preflight audit before freezing), and stamp it"
        ]
    gap = findings.audit_line_gap(base_dir, line, text)
    return [f"{path.name}: preflight_audit: {gap}"] if gap else []


def _promise_snapshot(
    base_dir: Path, text: str | None
) -> tuple["promises.PromiseTables | None", dict | None]:
    """The bound protocol's promise block, parsed once, and the snapshot the
    run records of it — (None, None) without tables.

    Before mkdir, like every refusal here: a malformed block or a declared
    scope naming code that does not exist stops the run — a number bound
    to a promise whose scope cannot be hashed is bound to nothing
    (`promises.declared_scope_sha`).
    """
    if text is None:
        return None, None
    try:
        block = promises.parse_block(text)
        if block is None:
            return None, None
        return block, promises.snapshot(block, base_dir)
    except promises.PromiseError as exc:
        raise SystemExit(f"runlog: promise block: {exc}") from exc


#: the time limit, in seconds, an agent harness puts on one foreground shell
#: command — set in the environment the harness gives its shell (Codex,
#: Cursor, any agent); `0` says the shell has none
FOREGROUND_TIMEOUT_ENV = "LABKIT_FOREGROUND_TIMEOUT_S"


#: Claude Code's limit, the default when `CLAUDECODE` is set and the variable
#: is not: its Bash tool runs one command for at most 600 000 ms
CLAUDE_CODE_FOREGROUND_S = 600.0


def foreground_timeout() -> tuple[float, str] | None:
    """The foreground limit of the shell this process runs in, and who
    named it; None when no harness limits it.

    `LABKIT_FOREGROUND_TIMEOUT_S` names it for any agent, and wins; without
    it, Claude Code (`CLAUDECODE` in the environment) counts as
    `CLAUDE_CODE_FOREGROUND_S`. Until 2026-10-14 the detach gate asked only
    for `CLAUDECODE`, so a long run under another agent was not refused and
    died with that agent's timeout (TODO item 6).

    Raises:
        SystemExit: The variable is set but not a number >= 0.
    """
    raw = os.environ.get(FOREGROUND_TIMEOUT_ENV)
    if raw is not None and raw.strip():
        try:
            limit = float(raw)
        except ValueError:
            limit = -1.0
        if not limit >= 0:  # also NaN
            raise SystemExit(
                f"runlog: {FOREGROUND_TIMEOUT_ENV}={raw!r} is not a number of "
                f"seconds >= 0 (0: the shell has no limit)"
            )
        return (limit, FOREGROUND_TIMEOUT_ENV) if limit > 0 else None
    if os.environ.get("CLAUDECODE"):
        return CLAUDE_CODE_FOREGROUND_S, "CLAUDECODE: Claude Code"
    return None


def registration_refusal(
    bound: _Bound,
    block: "promises.PromiseTables | None",
    config: dict,
    full_run: bool,
) -> str | None:
    """The registration's contract, before any gate that can be acknowledged
    and before mkdir (standard 0.19): a frozen protocol and every full run
    carry the promises as data (`promises.promise_tables_owed`), and a run under a
    block records every registered constant unchanged — otherwise the
    number is held to a threshold nobody registered (Durchstich
    2026-10-06). FULL_RUN means the script declares a measurement. None
    when it holds, or when the run is unbound
    (the freeze gate refuses an unbound full run on its own)."""
    name, head = bound.name, bound.head
    if head is None or bound.text is None:
        return None
    owed = promises.promise_tables_owed(
        block,
        frozen=head.frozen,
        full_run=full_run,
        registers=promises.registers_ids(bound.text),
    )
    if owed:
        return f"{name}: {owed}"
    if block is not None:
        refusal = _constants_refusal(block, config)
        if refusal:
            return f"{name}: {refusal}"
    return None


def _constants_refusal(block: "promises.PromiseTables", config: dict) -> str | None:
    """Why this config may not run under `block`: a registered constant the
    config lacks or carries with another value (type-strict). The guarantee
    behind the record: a run under a block recorded every registered
    constant unchanged (0.71.0)."""
    broken = [r for r in promises.constant_records(block, config) if r.state != "equal"]
    if not broken:
        return None
    lines = [
        f"[{r.promise_id}] {r.name} = {r.promised!r} is registered, the config "
        + ("carries no such key" if r.state == "missing" else f"says {r.recorded!r}")
        for r in broken
    ]
    return (
        "the registered constants are not in this run's config as registered:\n  "
        + "\n  ".join(lines)
        + "\n  read them with promises.all_constants(), not a second copy"
    )


def _derived_parent(base_dir: Path, derived_from: str | None) -> str | None:
    """DERIVED_FROM as config.json records it, or a refusal: the parent must
    be a completed run of this area and no repeat."""
    if derived_from is None:
        return None
    parent = base_dir / "runs" / derived_from
    try:
        state = completion_state(parent) if parent.is_dir() else "missing"
        drawn_from = (
            repeat_parent(read_run_config(parent) or {}) if state == COMPLETED else None
        )
    except RunConfigError as exc:
        raise SystemExit(f"runlog: derived_from={derived_from!r}: {exc}") from exc
    if state != COMPLETED:
        raise SystemExit(
            f"runlog: derived_from={derived_from!r} names no completed "
            f"run under {base_dir / 'runs'} ({state}) — a derived run "
            f"needs a finished parent"
        )
    # a derived run is no repeat and may answer: from a repeat, the
    # best of several draws would answer through it (2026-10-15)
    if drawn_from is not None:
        raise SystemExit(
            f"runlog: derived_from={derived_from!r} is a repeat of "
            f"{drawn_from} — supporting evidence, never the answer; "
            f"derive from {drawn_from}"
        )
    return derived_from


@dataclass(frozen=True)
class Prepared:
    """Phase 1 of a run's start, the preparation: what the run is held to,
    read once before any check — the parent it derives from, the bound
    protocol with its text and head, the promise block and the snapshot
    the record carries of it, the config frozen as it will be recorded, and
    its declared purpose.

    Attributes:
        derived_from: The completed parent run, as config.json records it.
        bound: The protocol binding (`protocol_binding`).
        cost_tier: The head's cost, None when unbound or unfilled.
        block: The parsed promise block, None without tables.
        promises: The snapshot of the block the record carries (`promises.snapshot`).
        config: The run's config, frozen now — what the checks hold is what
            config.json records.
        run_kind: Data preparation, an instrument probe, or a measurement.
    """

    derived_from: str | None
    bound: _Bound
    cost_tier: str | None
    block: "promises.PromiseTables | None"
    promises: dict | None
    config: dict
    run_kind: RunKind


def prepare(
    base_dir: Path,
    config: dict,
    run_kind: RunKind,
    protocol: str | Path | None,
    derived_from: str | None,
) -> Prepared:
    """Phase 1 — preparation. Reads what every check holds the run to,
    each once, and refuses what cannot be read, before any check and
    before mkdir: a parent that is no completed run (`_derived_parent`),
    a protocol that cannot be bound (`protocol_binding`), a promise block
    that does not parse or names code that does not exist
    (`_promise_snapshot`) — each a SystemExit. Freezes the config: what
    the registration check holds is what config.json records."""
    run_kind = parse_run_kind(run_kind)
    derived = _derived_parent(base_dir, derived_from)
    bound = protocol_binding(base_dir, protocol)
    cost = bound.head.cost if bound.head is not None else None
    # Seconds uses the complete measurement as its instrument check.
    # Rationale: docs/notes/2026-10-20-run-kinds.md.
    if run_kind == "probe" and not lane(cost).probe_allowed:
        raise SystemExit(
            "runlog: run_kind='probe' is not allowed at cost='seconds'; "
            "run the full measurement with run_kind='measurement' — "
            "this cost tier has no separate probe stage"
        )
    block, snapshot = _promise_snapshot(base_dir, bound.text)
    return Prepared(
        derived_from=derived,
        bound=bound,
        cost_tier=cost,
        block=block,
        promises=snapshot,
        config=dict(config),
        run_kind=run_kind,
    )


def foreground_refusal(base_dir: Path, limit: tuple[float, str]) -> None:
    """Refuse a foreground start under the harness LIMIT, before mkdir.

    The caller decides whether detachment is owed and missing. The harness
    kills the process group at its limit, including the run and its lock.
    History: docs/notes/2026-10-19-gates-and-run-start.md.
    """
    raise SystemExit(
        f"runlog: this run declares run_kind='measurement' and sits in a foreground "
        f"shell an agent harness kills after {limit[0]:g} s ({limit[1]}) "
        f"— the kill takes the process group mid-run (2026-08-13). "
        f"Start it detached:\n"
        f"  runlog start {shown_area(base_dir)} -- <the same command>\n"
        "or, if the caller already detached it (run_in_background, "
        "nohup+setsid), acknowledge with LABKIT_DETACHED=1."
    )


def freeze_gate(base_dir: Path, prepared: Prepared) -> tuple[bool, str | None]:
    """The freeze gate for a full run, before mkdir: a full run on a protocol
    not ready for one is a refusal, not a run with a warning. Returns
    (unfrozen_ack, audit_failed): whether `LABKIT_UNFROZEN=1` took the run
    past its gaps, and the failed audit attempt that rests on.

    In order: an undecided BLOCKER of a preflight audit refuses, with or
    without the acknowledgement — a finding nobody read is not an unfrozen
    protocol. Then the gaps (`_freeze_findings`: the freeze at
    minutes/hours, the registration at seconds): none, and the run starts
    plain; gaps and `LABKIT_UNFROZEN=1`, and the run starts acknowledged —
    at minutes/hours only over an audit that could NOT run
    (`_audit_unavailable`, SystemExit without one), recorded and told, its
    number unreportable; gaps alone refuse. The refusals name the
    consequence and offer no way round, and they say "probe", never
    "pilot" — agents take the way a message offers. Why each rule:
    docs/notes/2026-10-19-gates-and-run-start.md."""
    declares = "this run declares run_kind='measurement'"
    blockers, open_warnings = _undecided_findings(base_dir)
    if blockers:
        raise SystemExit(
            f"runlog: {declares}, and a "
            "preflight audit found BLOCKER(s) nobody decided — not an "
            "unfrozen protocol, an ignored finding; LABKIT_UNFROZEN=1 does not pass "
            "it. Decide each (fixed / accepted / deferred / dismissed) "
            "in the record:\n  " + "\n  ".join(blockers)
        )
    gaps = _freeze_findings(base_dir, prepared.bound)
    if not gaps:
        return False, None
    if os.environ.get("LABKIT_UNFROZEN") != "1":  # "0" is no acknowledgement
        raise SystemExit(
            f"runlog: {declares}, but its "
            "protocol is not ready for one:\n  "
            + "\n  ".join(gaps)
            + "\nFreeze first: `preflight <AREA>` clean, audit stamped, "
            "`frozen = true` "
            '(at cost = "seconds": the question written suffices, with a model also criterion and admissibility condition). '
            "No other run yields a reported number: a probe (run_kind='probe') "
            "and a run acknowledged with LABKIT_UNFROZEN=1 (at "
            "minutes/hours only over an audit the backend refused, "
            f"audits/*{findings.FAILED_SUFFIX} written by labkit-audit) are "
            "recorded as such, and report-check refuses their numbers."
        )
    failed = _audit_unavailable(base_dir, prepared.bound)  # SystemExit without one
    print(
        "runlog: WARNING — LABKIT_UNFROZEN=1: full run on an "
        "unfrozen protocol, acknowledged; recorded in config.json, and "
        "its number cannot be reported (report-check refuses it):\n  "
        + "\n  ".join(gaps)
        + (
            f"\n  rests on the audit that could not run: "
            f"{failed.path.name} ({failed.error})"
            if failed is not None
            else ""
        )
        + (
            "\n  open WARNING(s) of the preflight audit, undecided:\n  "
            + "\n  ".join(open_warnings)
            if open_warnings
            else ""
        )
    )
    return True, failed.path.name if failed is not None else None


def shown_area(area: Path) -> str:
    """AREA as a person types it from here: relative to the working directory
    when it lies below it, else absolute."""
    resolved = area.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(resolved)
