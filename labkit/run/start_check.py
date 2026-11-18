"""start_check — what refuses a run before its directory exists, in order.

Two phases of `runlog.Run`'s start live here: the preparation
(`prepare`: the protocol binding, the promise snapshot, the config
frozen — a reseeded repeat's seed is set later, under runlog's lock; it
refuses what cannot be read) and the checks the constructor
sequences — the low registration (`require_registration`), a reseed's
conditions (`require_valid_reseed`), the
detach gate (`require_detached`, with `foreground_timeout`), and for a
full run the freeze gate (`freeze_gate`: undecided blockers, the freeze
or the registration, the acknowledgement over a failed audit). Each
`require_*` raises SystemExit with the sentence a person acts on, and so
does every other refusal here — a measure script reaches it with no main
of labkit's around it (the rule by caller stands at `console.Refused`); a `*_refusal` (`_constants_refusal`)
returns the sentence for its caller to raise. Nothing here writes.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from labkit.formats.area_state import (
    CLOCKS_ASSUMED,
    UNASSIGNED_LEAVES_OPEN,
    AreaState,
    measurements_without_record,
    state_of,
)
from labkit.formats import evidence
from labkit.formats.commands import checkout_command, contract_command, fill_command
from labkit.formats import commands
from labkit.formats.runs import run_path, runs_path
from labkit.formats.runs import PROBE, RunKind, parse_run_kind

from labkit.formats import findings, promises, protocol_block, protocol_check, repo
from labkit.formats import audit_gaps
from labkit.formats import failed_attempts
from labkit.formats.answering_run import REPEAT_SEED_KEY, is_measurement
from labkit.formats.gate import BLOCKER, with_rule, with_way_out
from labkit.formats.standard_contract import (
    PREFLIGHT_AUDIT,
    first_measurement_hint,
    lane,
)
from labkit.formats.scope_sha import area_stamp
from labkit.formats.runs import (
    COMPLETED,
    RUN_ID,
    RunConfig,
    RunConfigError,
    completion_state,
    read_run_config,
)


@dataclass(frozen=True)
class _Bound:
    """The bound protocol, read once at binding: `binding` is the record
    config.json carries ({"id": ..., "path": ...}, both None when unbound),
    `text` and `head` the protocol as read then (None when unbound). The
    freeze gate and the registration check take it instead of reading the
    file again."""

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
    from an object.

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
                with_way_out(
                    f"runlog: protocol={protocol!r} is not one of the "
                    f"PROTOCOL-*.md in the run's area ({base_dir}):\n  "
                    + "\n  ".join(f.name for f in found or [Path("(none)")]),
                    "name one of these: `runlog.run(..., protocol=PROTOCOL)`",
                )
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
            with_way_out(
                f"runlog: {len(found)} protocols in {base_dir} — nothing would "
                f"say which one this run belongs to:\n  "
                + "\n  ".join(f.name for f in found),
                "name it: `runlog.run(..., protocol=PROTOCOL)`",
            )
        )

    rel = repo.shown(path, base_dir)
    text = path.read_text(encoding="utf-8")
    try:
        head = protocol_block.head(text)
    except protocol_block.BlockError as exc:
        raise SystemExit(
            with_way_out(
                f"runlog: {rel}: {exc}",
                f"repair the head as the sentence says "
                f"(`{contract_command(path)}` shows its fields)",
            )
        ) from exc
    if head.id is None:
        print(
            f"runlog: WARNING — {rel} carries no stamped id (`id` in its "
            f"[protocol] table); this run is recorded as unbound."
        )
    return _Bound({"id": head.id, "path": rel}, text, head)


def _committed_registration(
    base_dir: Path, bound: _Bound, state: AreaState
) -> list[str]:
    """Refuse a first measurement whose report differs from HEAD, on both
    lanes. Low also requires the scientific registration committed; high
    retains its separate freeze checks. Later measurements use the first
    one's binding: once the area measured the protocol — a measurement of
    it whose record reads, or a run without a record that the run index
    binds to it (`area_state.measurements_without_record`) — no run is held
    to HEAD as the first, and HEAD is not named as what binds; where the
    earlier run may have been the first, `earlier_measurement_note` says so
    at the start and the registration station holds the number
    (`registration_hold.lost_record_hold`). A record that does not read and
    that no index row names counts for no protocol: the run is held to HEAD
    as before. A HEAD git cannot read is refused as such, before either. No
    commitment check outside Git or for an unbound protocol. Reads HEAD,
    the run index and what the area measured; writes nothing.
    """
    from labkit.formats.protocol_history import registration_in_commit

    head, rel = bound.head, bound.binding.get("path")
    root = repo.git_root(base_dir)
    if root is None or head is None or head.id is None or not isinstance(rel, str):
        return []
    measured = state.measured_of(head.id)
    # STATE is the working tree's, so its lost runs are lost in the tree
    without = measurements_without_record(measured, measured.lost)
    reads = any(rd.config is not None and is_measurement(rd) for rd in measured.runs)
    if reads or without.of_protocol:
        return []
    protocol = (base_dir / rel).resolve()
    committed = repo.text_at(root, protocol, "HEAD")
    unread = repo.unreadable_at(root, protocol, "HEAD") if committed is None else ""
    if unread:
        # None from `text_at` is "not committed" and "git failed" alike; a
        # HEAD git cannot read is neither uncommitted nor without a report
        return [
            f"{protocol.name} cannot be read at HEAD: {unread} — what the first "
            f"measurement would be held to cannot be told; restore the repository's "
            f"missing objects (`git fsck` names them, a clone that holds them "
            f"`git fetch`es them), then start the run (LAB-003 No run without an "
            f"intent paragraph)"
        ]
    if lane(head.repeat_cost).registration:
        missing = registration_in_commit(protocol, "HEAD", head.kind)
        if missing is None:
            return [
                f"{protocol.name} is not committed — the first measurement is held to "
                f"the registration its commit holds; commit the protocol (`git add` + "
                f"`git commit`), then start the run (LAB-003 No run without an intent "
                f"paragraph)"
            ]
        if missing:
            return [
                f"{protocol.name}: the registration as committed (HEAD) lacks "
                f"{', '.join(missing)} — the first measurement is held to what its "
                f"commit holds; commit the written registration, then start the run "
                f"(LAB-003 No run without an intent paragraph)"
            ]
    # the report duty starts from what the first measurement's commit holds
    # (`registered_report.report_duty`): uncommitted, the entry binds nothing
    then = protocol_block.head(committed).report if committed is not None else None
    if head.report != then:
        return [
            f"{protocol.name} registers {head.report or 'no report'} as its report, "
            f"and HEAD registers {then or 'none'} — the report the first measurement "
            f"stands under is what its commit holds; commit the protocol, then start "
            f"the run"
        ]
    return []


def earlier_measurement_note(bound: _Bound, state: AreaState) -> str | None:
    """The warning a measurement starts with about runs without a record
    (`area_state.measurements_without_record` over STATE, the working
    tree's), one sentence per case:

    - a run of the protocol that may have been its first measurement —
      also where the run ids do not tell its order against a measurement
      that reads, which its clause says: this run is not held to HEAD as
      the first, what stood registered then cannot be read from
      here, and the registration station holds every number of the protocol
      until the record is back or the protocol is registered anew or handed
      over;
    - a run of the protocol whose id lies more than 26 hours after that
      of a measurement that reads: named, with the assumption that takes
      it as the later one (`area_state.CLOCKS_ASSUMED`); nothing is held
      for it;
    - a record that does not read and that no index row names: its
      protocol cannot be determined, in an area of one protocol too, and
      the sentence says what that leaves open
      (`area_state.UNASSIGNED_LEAVES_OPEN`).

    A warning, never a refusal: a started investigation may go on, and only
    a result that needs the missing record is held
    (docs/notes/2026-11-18-lost-first-measurement.md). None when every
    measurement has its record, and for an unbound protocol. Pure."""
    head = bound.head
    if head is None or head.id is None:
        return None
    measured = state.measured_of(head.id)
    # STATE is the working tree's, so its lost runs are lost in the tree
    without = measurements_without_record(measured, measured.lost)
    told: list[str] = []
    if without.held:
        told.append(
            f"this run is not held to HEAD as its first measurement — a run that "
            f"may have been the first left no record that reads: "
            f"{'; '.join(without.held)}. What stood registered "
            f"then cannot be read from here, and the protocol as committed now "
            f"does not stand in for it. The run starts; `finalize` and "
            f"`report-check` hold every number of this protocol until the record "
            f"is back, or the protocol is registered anew or handed over "
            f"(finalize names each way)."
        )
    if without.later:
        told.append(
            f"{'; '.join(without.later)} — by the run ids more than 26 hours "
            f"after a measurement of this protocol that reads started, and taken "
            f"as the later one, {CLOCKS_ASSUMED}; so nothing is held for it; a "
            f"result that needs its "
            f"rows is held where that result is checked."
        )
    if without.unassigned:
        told.append(
            f"the record of run {', '.join(without.unassigned)} does not read, "
            f"and the run index does not list it: which protocol it belongs to "
            f"cannot be determined — {UNASSIGNED_LEAVES_OPEN}; restore "
            f"its config.json from a commit or a copy that holds it."
        )
    if not told:
        return None
    return f"runlog: WARNING — {bound.name}: " + " Also: ".join(told)


def _first_step(base_dir: Path, bound: _Bound, state: AreaState) -> str:
    """The next action before a full run: low's registration, or high's
    report commitment when missing, otherwise its freeze. Reads the first
    measurement and HEAD at high cost through the shared commitment check;
    writes nothing. While the area has not measured the protocol
    (`area_state.Measured.has_measured`, the question `labkit-next` asks)
    each step ends with what only the task can say
    (`standard_contract.first_measurement_hint`): runlog is the last stop
    before that run, and an agent that never ran labkit-next sees only this
    line.
    """
    head = bound.head
    hint = ""
    rel = bound.binding.get("path")
    if (
        bound.text is not None
        and head is not None
        and head.id is not None
        and isinstance(rel, str)
        and not state.measured_of(head.id).has_measured
    ):
        hint = first_measurement_hint(base_dir / rel, bound.text)
    if bound.text is not None and protocol_check.repeated_fields(bound.text):
        # at high cost the deletion changes what the preflight audit bound
        after = (
            "commit the protocol, then start the run again"
            if head is None or lane(head.repeat_cost).registration
            else "then `preflight <AREA>` clean, the preflight audit run anew on "
            "the changed registration, and `protocol-fill <PROTOCOL> --freeze` again"
        )
        step = (
            f"For each field named above: {protocol_check.REPEATED_WAY_OUT}; " + after
        )
    elif head is not None and lane(head.repeat_cost).registration:
        step = (
            f'At repeat_cost = "{head.repeat_cost}" nothing freezes: write and commit '
            "the registration the kind owes (`protocol-check --contract` names it), "
            "then start the run again"
        )
    elif _committed_registration(base_dir, bound, state):
        step = (
            "Commit the registered report path as named above, then start the run again"
        )
    else:
        step = (
            "Freeze first: `preflight <AREA>` clean, the preflight audit decided, then "
            "`protocol-fill <PROTOCOL> --freeze`"
        )
    return step + hint + "."


def _freeze_findings(base_dir: Path, bound: _Bound, state: AreaState) -> list[str]:
    """Why a FULL run may not start on this protocol — empty means it may."""
    from labkit.formats.protocol_check import low_registration_missing

    text, head = bound.text, bound.head
    if text is None or head is None:
        return [
            "the run is unbound (no protocol) — a full run needs a "
            "registered protocol (LAB-003 No run without an intent paragraph)"
        ]
    path = Path(bound.name)
    if bound.binding.get("id") is None:
        # a full run's number must be bound; an unstamped id binds nothing,
        # and finalize would only say so after the number exists
        return [
            f"{path.name}: the [protocol] id is not stamped — a full run "
            f"needs a bound protocol (`labkit-init exp` stamps it)"
        ]
    # a field written twice is no registration on either lane: which copy
    # binds cannot be told (`protocol_check.repeated_fields`)
    twice = [f"{path.name}: {r}" for r in protocol_check.repeated_findings(text)]
    # the freeze or the registration: the lane's answer (`standard_contract`)
    if lane(head.repeat_cost).registration:
        missing = low_registration_missing(text)
        if not missing:
            # the committed registration names the same copies again; the
            # tree's repair comes first, its commit is the next step
            return twice or _committed_registration(base_dir, bound, state)
        return twice + [
            f'{path.name}: `repeat_cost = "{head.repeat_cost}"`, but the registration is not '
            f"written: {', '.join(missing)} (the commit also owes the other fields "
            f"`protocol-check --contract` names) — at low repeat cost the gate is the "
            f"registration the kind owes (a computation its question; a fit or an apply "
            f"also criterion · quality check · null condition; with a "
            f"model the data profile), not the freeze (LAB-003 No run without an "
            f"intent paragraph, LAB-017 The number of audits follows the cost tier)"
        ]
    out = twice + _committed_registration(base_dir, bound, state)
    if head.kind is None:
        # what the number asserts is decided before it exists
        out.append(
            f"{path.name}: [protocol] kind is still a placeholder — compute, fit or "
            f"apply (`{fill_command(path, 'kind=…')}`)"
        )
    if not head.frozen:
        out.append(f"{path.name}: not `frozen = true`")
    out += _audit_line_findings(base_dir, path, head.preflight_audit, text)
    return out


def measurement_refusal(base_dir: Path, protocol: Path) -> tuple[list[str], str]:
    """What `freeze_gate` refuses a measurement bound to PROTOCOL in BASE_DIR
    with, as the area stands now: the gaps (`_freeze_findings`; empty when
    the run would start) and the first step its refusal names
    (`_first_step`). The undecided preflight BLOCKERs, which refuse before
    the gaps, are not read here. Raises SystemExit as `protocol_binding`
    does; prints its warning for a protocol without a stamped id."""
    bound = protocol_binding(base_dir, protocol.resolve())
    state = state_of(base_dir)
    return _freeze_findings(base_dir, bound, state), _first_step(base_dir, bound, state)


def _undecided_findings(
    base_dir: Path, held: evidence.AreaEvidence
) -> tuple[list[str], list[str]]:
    """(blockers, lesser): every finding still `open` in a preflight audit
    record of the area, each as `<file>: <text>`, BLOCKERs apart from the
    WARNINGs and NOTEs. A record of any stamp counts — a finding nobody
    decided is an ignored finding, not an old one (LAB-015 Preflight audit
    before freezing: every finding is decided). Preflight records only, by
    intent (`findings.open_findings` has the table): the run rests on the
    preflight audit; an analysis record judges a run and is finalize's.
    The blockers refuse (`freeze_gate`); the lesser ones are told only with
    the run acknowledged — on a clean start the named record is decided
    whole (`audit_record_gap`), and an older record's open WARNING does not
    hold a run. HELD is the area's audit evidence (`evidence.AreaEvidence`).
    Raises SystemExit on a record nobody can read."""
    if held.unreadable:
        raise SystemExit(
            with_way_out(f"runlog: {held.unreadable[0]}", findings.record_way(base_dir))
        )
    records = held.records
    blockers, lesser = [], []
    for u in findings.open_findings(records, mode=PREFLIGHT_AUDIT):
        (blockers if u.grade == BLOCKER else lesser).append(u.line)
    return blockers, lesser


def _audit_unavailable(
    base_dir: Path, bound: _Bound
) -> "failed_attempts.Failed | None":
    """The failed audit attempt an acknowledged full run rests on, or
    None at `repeat_cost = "low"`, where no audit is owed before the run. Raises
    SystemExit when none fits: the hatch is for an audit the backend refused,
    not for one nobody started. The attempt must name the code as it stamps
    now and, under a protocol, the promise block as it reads now, and its
    call must have had the default timeout at least (`failed_attempts.ATTEMPT_TIMEOUT_S`)."""
    if (
        bound.head is not None
        and PREFLIGHT_AUDIT not in lane(bound.head.repeat_cost).audits
    ):
        return None
    try:
        sha = area_stamp(base_dir)[0]
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(
            with_way_out(
                f"runlog: LABKIT_UNFROZEN=1 — the area cannot be stamped ({exc}), "
                f"so no failed audit attempt can be held to its code",
                "repair what the sentence names, then start the run again",
            )
        ) from exc
    block_sha = None
    if bound.text is not None:
        try:
            block_sha = promises.block_stamp(bound.text)
        except promises.PromiseError as exc:
            raise SystemExit(
                with_way_out(f"runlog: promise block: {exc}", PROMISE_BLOCK_WAY)
            ) from exc
    try:
        failed = failed_attempts.audit_unavailable(
            base_dir, sha, "preflight", block_sha
        )
    except findings.FindingsError as exc:
        raise SystemExit(
            with_way_out(f"runlog: {exc}", findings.record_way(base_dir))
        ) from exc
    if failed is None:
        tried = failed_attempts.failed_attempts(base_dir)
        seen = (
            "; ".join(
                f"{f.path.name} (code {f.scope_sha}, promises {f.block_sha}, "
                f"{f.timeout_s} s)"
                for f in tried
            )
            or "none"
        )
        raise SystemExit(
            with_way_out(
                "runlog: this run declares run_kind='measurement' (a full run) on a "
                "protocol not ready for one, and LABKIT_UNFROZEN=1 acknowledges an "
                "audit that could not run — not one nobody ran. No failed preflight "
                f"attempt of the code as it is now (code {sha}, promises "
                f"{block_sha or 'no protocol'}, at least "
                f"{failed_attempts.ATTEMPT_TIMEOUT_S} s) is recorded; attempts: {seen}",
                f"run the audit: `{commands.audit_command(base_dir, '--mode', 'preflight', protocol=base_dir / bound.name if bound.head is not None else None)}`; "
                "when the backend does not answer, it writes "
                f"audits/<date>-preflight{findings.FAILED_SUFFIX}, and this "
                "acknowledgement rests on that file — and its number cannot be "
                "reported either (report-check refuses it)",
            )
        )
    return failed


def _audit_line_findings(base_dir: Path, path: Path, line: str, text: str) -> list[str]:
    """Why the head's `preflight_audit` does not cover a full run: empty, or
    what `audit_gaps.audit_record_gap` says of the record it names — none
    named (`n/a` is none), no such record, one of other code
    or another promise block than the area carries now, a finding open —
    each with its way out (`RecordGap.fix`)."""
    if not line:
        return [
            f"{path.name}: `preflight_audit` is empty — run `preflight`, then the "
            f"preflight audit (`labkit-audit <area> --mode preflight`), decide its "
            f"findings and name its record here (LAB-015 Preflight audit before freezing)"
        ]
    gap = audit_gaps.audit_record_gap(base_dir, line, text)
    if gap is None:
        return []
    why = with_rule(f"{path.name}: preflight_audit: {gap.why}", gap.rule)
    return [with_way_out(why, gap.fix)]


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
        raise SystemExit(
            with_way_out(f"runlog: promise block: {exc}", PROMISE_BLOCK_WAY)
        ) from exc


#: the way out of a promise block that does not read or names code that is
#: not there
PROMISE_BLOCK_WAY = (
    "repair the [[promise]] tables as the sentence says (`protocol-check "
    "<PROTOCOL> --contract` shows the block's form); after the first "
    "measurement a changed registration is registered anew"
)


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
    `CLAUDE_CODE_FOREGROUND_S`.

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
                with_way_out(
                    f"runlog: {FOREGROUND_TIMEOUT_ENV}={raw!r} is not a number of "
                    f"seconds >= 0",
                    f"set {FOREGROUND_TIMEOUT_ENV} to the shell's limit in seconds "
                    f"(0: the shell has no limit)",
                )
            )
        return (limit, FOREGROUND_TIMEOUT_ENV) if limit > 0 else None
    if os.environ.get("CLAUDECODE"):
        return CLAUDE_CODE_FOREGROUND_S, "CLAUDECODE: Claude Code"
    return None


def require_valid_reseed(
    prepared: Prepared, repeat_of: str | None, reseed: bool
) -> None:
    """Refuse a run whose seed is drawn anew (RESEED) against the rules: a
    reseed goes with REPEAT_OF; the config must hold an integer
    REPEAT_SEED_KEY; and a seed the protocol registers as a constant is
    not drawn — a repeat may not change a registered value. Before any
    lock: the derivation itself needs the draw (`runlog._repeat_draw`).
    Raises SystemExit with the reason."""
    if not reseed:
        return
    if repeat_of is None:
        raise SystemExit(
            with_way_out(
                "runlog: reseed draws a repeat's seed anew — it goes with repeat_of",
                "pass `repeat_of=<the primary run>` with `reseed=True`, or drop reseed",
            )
        )
    seed = prepared.config.get(REPEAT_SEED_KEY)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise SystemExit(
            with_way_out(
                f"runlog: reseed: the config holds no integer `{REPEAT_SEED_KEY}` "
                f"to draw anew ({seed!r})",
                f"give the config an integer `{REPEAT_SEED_KEY}`",
            )
        )
    registered = promises.all_constants(prepared.block) if prepared.block else {}
    if REPEAT_SEED_KEY in registered:
        raise SystemExit(
            with_way_out(
                f"runlog: reseed: the protocol registers `{REPEAT_SEED_KEY}` = "
                f"{registered[REPEAT_SEED_KEY]!r} — a spread over "
                f"seeds needs a seed the protocol does not fix, and a repeat may "
                f"not change a registered value",
                "repeat without reseed, or register a spread over seeds in a "
                "protocol of its own",
            )
        )


def require_registration(
    bound: _Bound,
    block: "promises.PromiseTables | None",
    config: dict,
    full_run: bool,
) -> None:
    """Refuse a run that breaks the registration's contract, before any
    gate that can be acknowledged and before mkdir: a
    frozen protocol and every full run carry the promises as data
    (`promises.promise_tables_owed`), and a run under a block records every
    registered constant unchanged — otherwise the number is held to a
    threshold nobody registered. FULL_RUN means the
    script declares a measurement. An unbound run passes here (the freeze
    gate refuses an unbound full run on its own). Raises SystemExit with
    the reason."""
    name, head = bound.name, bound.head
    if head is None or bound.text is None:
        return
    owed = promises.promise_tables_owed(
        block,
        frozen=head.frozen,
        full_run=full_run,
        registers=protocol_check.kind_registers(head.kind, bound.text),
    )
    if owed:
        raise SystemExit(
            with_way_out(
                f"runlog: {name}: {owed}",
                "write the [[promise]] tables in the protocol and commit them "
                "before the run (`protocol-check <PROTOCOL> --contract` names "
                "what the kind owes)",
            )
        )
    if block is not None:
        refusal = _constants_refusal(block, config)
        if refusal:
            raise SystemExit(
                with_way_out(
                    f"runlog: {name}: {refusal}",
                    "read them with promises.all_constants(), not a second copy",
                )
            )


def _constants_refusal(block: "promises.PromiseTables", config: dict) -> str | None:
    """Why this config may not run under `block`: a registered constant the
    config lacks or carries with another value (type-strict). The guarantee
    behind the record: a run under a block recorded every registered
    constant unchanged."""
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
    )


def completed_parent(base_dir: Path, key: str, run_id: str, why: str = "") -> RunConfig:
    """The config of RUN_ID, the parent a new run names under KEY
    (`repeat_of`, `derived_from`), or a refusal naming KEY: no completed
    run of this area, or a config that does not read; WHY ends the "no
    completed run" sentence. The one reading of a parent run for both keys;
    each caller adds its own check that the
    parent is no repeat."""
    parent = run_path(base_dir, run_id)
    try:
        state = completion_state(parent) if parent.is_dir() else "missing"
        pcfg = read_run_config(parent) if state == COMPLETED else None
    except RunConfigError as exc:
        raise SystemExit(
            with_way_out(
                f"runlog: {key}={run_id!r}: {exc}",
                "restore the run record the sentence names as runlog wrote it "
                f"(`{checkout_command('<path>')}` where git holds it)",
            )
        ) from exc
    if pcfg is None:
        raise SystemExit(
            with_way_out(
                f"runlog: {key}={run_id!r} names no completed run under "
                f"{runs_path(base_dir)} ({state}){why}",
                f"name a completed run of this area by its id (its folder under "
                f"{runs_path(base_dir)} holds a completion.json)",
            )
        )
    return pcfg


def _derived_parent(base_dir: Path, derived_from: str | None) -> str | None:
    """DERIVED_FROM as config.json records it, or a refusal: the parent must
    be a completed run of this area and no repeat."""
    if derived_from is None:
        return None
    if RUN_ID.fullmatch(derived_from) is None:
        raise SystemExit(
            with_way_out(
                f"runlog: derived_from={derived_from!r} is not a run id",
                f"name a run of {runs_path(base_dir)} by its id, never a path",
            )
        )
    drawn_from = completed_parent(
        base_dir,
        "derived_from",
        derived_from,
        " — a derived run needs a finished parent",
    ).repeat_of
    # a derived run is no repeat and may answer: from a repeat, the
    # best of several draws would answer through it
    if drawn_from is not None:
        raise SystemExit(
            with_way_out(
                f"runlog: derived_from={derived_from!r} is a repeat of "
                f"{drawn_from} — supporting evidence, never the answer",
                f"derive from {drawn_from}",
            )
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
        repeat_cost: The head's repeat cost, None when unbound or unfilled.
        block: The parsed promise block, None without tables.
        promises: The snapshot of the block the record carries (`promises.snapshot`).
        config: The run's config, frozen now — what the checks hold is what
            config.json records, but for a reseeded repeat's seed, which
            runlog derives under its lock (`require_valid_reseed` holds the
            conditions first).
        run_kind: Data preparation, an instrument probe, or a measurement.
    """

    derived_from: str | None
    bound: _Bound
    repeat_cost: str | None
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
    the registration check holds is what config.json records, but for a
    reseeded repeat's seed, which runlog derives under its lock (its
    conditions: `require_valid_reseed`)."""
    run_kind = parse_run_kind(run_kind)
    derived = _derived_parent(base_dir, derived_from)
    bound = protocol_binding(base_dir, protocol)
    repeat_cost = bound.head.repeat_cost if bound.head is not None else None
    # Seconds uses the complete measurement as its instrument check.
    # Rationale: docs/notes/2026-10-20-run-kinds.md.
    if run_kind == PROBE and not lane(repeat_cost).probe_allowed:
        raise SystemExit(
            with_way_out(
                "runlog: run_kind='probe' is not allowed at repeat_cost='low' — "
                "this repeat cost has no separate probe stage",
                "run the full measurement with run_kind='measurement'",
            )
        )
    block, snapshot = _promise_snapshot(base_dir, bound.text)
    return Prepared(
        derived_from=derived,
        bound=bound,
        repeat_cost=repeat_cost,
        block=block,
        promises=snapshot,
        config=dict(config),
        run_kind=run_kind,
    )


def require_detached(base_dir: Path, limit: tuple[float, str]) -> None:
    """Refuse a foreground start under the harness LIMIT, before mkdir.

    The caller decides whether detachment is owed and missing. The harness
    kills the process group at its limit, including the run and its lock.
    Why: docs/notes/2026-10-19-gates-and-run-start.md.
    """
    raise SystemExit(
        with_way_out(
            f"runlog: this run declares run_kind='measurement' and sits in a "
            f"foreground shell an agent harness kills after {limit[0]:g} s "
            f"({limit[1]}) — the kill takes the process group mid-run",
            # the area as `shown_area` names it, the command a slot —
            # home: no builder in commands
            f"start it detached: `runlog start {shown_area(base_dir)} -- <the same "
            f"command>`; or, if the caller already detached it (run_in_background, "
            f"nohup+setsid), acknowledge with LABKIT_DETACHED=1",
        )
    )


def freeze_gate(base_dir: Path, prepared: Prepared) -> tuple[bool, str | None]:
    """The freeze gate for a full run, before mkdir: a full run on a protocol
    not ready for one is a refusal, not a run with a warning. Returns
    (unfrozen_ack, audit_failed): whether `LABKIT_UNFROZEN=1` took the run
    past its gaps, and the failed audit attempt that rests on.

    In order: an undecided BLOCKER of a preflight audit refuses, with or
    without the acknowledgement — a finding nobody read is not an unfrozen
    protocol. Then the warning for an earlier measurement without a record
    that reads (`earlier_measurement_note`; it refuses nothing). Then the
    gaps (`_freeze_findings`: the freeze at
    high repeat cost, the registration at low repeat cost): none, and the run starts
    plain; gaps and `LABKIT_UNFROZEN=1`, and the run starts acknowledged —
    at high repeat cost only over an audit that could NOT run
    (`_audit_unavailable`, SystemExit without one), recorded and told, its
    number unreportable; gaps alone refuse. The refusals name the
    consequence and offer no way round, and they say "probe", never
    "pilot" — agents take the way a message offers. Why each rule:
    docs/notes/2026-10-19-gates-and-run-start.md."""
    declares = "this run declares run_kind='measurement'"
    blockers, open_lesser = _undecided_findings(
        base_dir, evidence.read_evidence(base_dir, staged=False)
    )
    state = state_of(base_dir)
    if blockers:
        raise SystemExit(
            with_way_out(
                f"runlog: {declares}, and a "
                "preflight audit found BLOCKER(s) nobody decided — not an "
                "unfrozen protocol, an ignored finding; LABKIT_UNFROZEN=1 does not "
                "pass it:\n  " + "\n  ".join(blockers),
                f"decide each ({findings.DECIDED_LIST}) with the command "
                f"`{commands.audit_command(base_dir, '--findings')}` prints per finding",
            )
        )
    gaps = _freeze_findings(base_dir, prepared.bound, state)
    # told whether the run starts or not: it holds for the next start too
    note = earlier_measurement_note(prepared.bound, state)
    if note is not None:
        print(note)
    if not gaps:
        return False, None
    if os.environ.get("LABKIT_UNFROZEN") != "1":  # "0" is no acknowledgement
        raise SystemExit(
            with_way_out(
                f"runlog: {declares}, but its "
                "protocol is not ready for one:\n  " + "\n  ".join(gaps),
                f"{_first_step(base_dir, prepared.bound, state)} "
                "No other run yields a reported number: a probe (run_kind='probe') "
                "and a run acknowledged with LABKIT_UNFROZEN=1 (at "
                "high repeat cost only over an audit the backend refused, "
                f"audits/*{findings.FAILED_SUFFIX} written by labkit-audit) are "
                "recorded as such, and report-check refuses their numbers.",
            )
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
            "\n  undecided WARNING(s) / NOTE(s) of the preflight audits:\n  "
            + "\n  ".join(open_lesser)
            if open_lesser
            else ""
        )
    )
    return True, failed.path.name if failed is not None else None


def shown_area(area: Path) -> str:
    """AREA as a person types it from here: relative to the working directory
    when it lies below it, else absolute."""
    return repo.shown(area, Path.cwd())
