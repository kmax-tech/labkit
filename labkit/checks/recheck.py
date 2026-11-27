"""recheck — hold a kept number to its own output.

    from labkit.checks import recheck
    recheck.holds(area=AREA, out=OUT, recompute=evaluate, note=PROTOCOL)
    recheck.holds_outputs(area=AREA, outs={"generated": GEN, "judged": JUDGED},
                          recompute=evaluate_both, note=PROTOCOL)

Three mechanics every area's `--check` needs, held here once:

1. **pin** — `out` is the file the chosen run recorded in `outputs.json`
   (runlog keeps a `runs.RECORD_SHA_CHARS`-hex sha256 prefix; the comparison
   is `startswith`, not equality — a full digest never matches a prefix).
   A number computed from several output files — a stage that generates
   and one that judges — names each by a key (`holds_outputs`): every one
   is pinned before `recompute` sees the rows of all of them, by key.
2. **agree** — `recompute(rows)` equals `metrics.json`: intent keys
   (`criterion_1_…`, `quality_check_1_…`, `interpretation_1_…`) present on both sides or neither,
   nothing the run reported vanishes (runlog's own keys excepted), every
   shared value identical. Keys the recomputation gained are a derived
   run, reported, not a failure (LAB-041 Generate numbers, don't retype them).
3. **cited** — the note carries every reported number (decimal comma and
   U+2212 minus normalised first) and the run_id.

Before the numbers are compared, the code is (`require_run_code`): a run
whose script or imported modules changed since it ran is refused — equal
numbers from other code would not be a recalculation of that run —, and
where nothing shows that the code here is the code the run ran, the run is
not verifiable (`NotVerifiable`): a missing proof, no failed comparison,
and no number is compared with today's code in its place. The release that
owes the recalculation waits on it — the area's `--check` holds the run
the protocol answers with, and report-check reads the clause
`NOT_VERIFIABLE` off that check's output; a recheck of any other run only
says so.

An area's `--check` names the protocol it holds (`protocol_named`; an
area of several protocols owes the name) and recomputes that protocol's
run with the script the run ran (`script_module`): a second protocol with
a script of its own is held by its own evaluation, and by nothing of the
other protocol's.

A run that computes from other runs' outputs (a comparison over its
source runs) is held by `holds_from_inputs`: inputs → scopes → code →
block → agree → cited. The inputs step comes first and stands apart from the
recomputation: every input the run recorded is still the bytes it read —
an input with an origin run still that run's registered output
(`inputs_pinned`, the same condition as finalize's input-origins
station) —, and only then does the computing run's own evaluation over
those inputs have to give the numbers its metrics.json holds (`require_agreement`).
The source runs are not run again.

An older run is checked apart from the answering one
(`holds_as_measured`, an area's `--check --run <run_id>`): under the
protocol text it started under, with its rows as it recorded them — the
file as it stands, or, where a later run overwrote it, the bytes a commit
holds with the recorded sha256, read into a temporary directory
(`output_as_recorded`). Where no bytes with that sha256 are left, the run
is not verifiable; the file as it stands is never read in their place.
That check holds no note, changes no adoption and releases nothing.

Every output compared is a row file: one JSON object per line, a leading
`_meta` header skipped (`jsonl.data_rows_of`) — what `runlog` areas write
and `batch.Store` appends. A pipeline's own outputs are not that: stagekit
writes each stage artifact as one indented JSON document
(`stage_outputs/<stage>/<key>.json`). The area writes the rows its number
reads from them into a row file of its own inside the run and registers
it (`Run.output`); handed a file that is no row file, the recheck refuses
it, naming the output, and reads nothing in its place.

The recomputation (`recompute`) is the area's own evaluation, and the
check assumes of it what it cannot enforce of a Python function: that it
reads the rows it is handed and writes nothing — no file, no run, no
metrics. It is called before the last reads of the check (the `[kept]`
key of the run's own text, `kept_keys`), so a check refused at that read
has already called it.

Any disagreement is a SystemExit with a sentence — the area's `--check`
calls this with no main of labkit's around it (the rule by caller stands
at `console.Refused`); the verdict names what was compared. Rules of the
lab standard: LAB-041 Generate numbers, don't retype them,
LAB-043 Runs go through `runlog`.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import re
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from labkit.formats import (
    digests,
    jsonl,
    promises,
    protocol_block,
    runs,
)
from labkit.formats.area_state import AreaState, state_of
from labkit.formats.protocol_then import as_measured, bound_protocol_file
from labkit.formats.repo import (
    ProtocolChoiceError,
    blob_bytes,
    blobs_in_history,
    file_text,
    git_root,
    path_kind,
    the_protocol,
)
from labkit.formats.commands import adopt_command
from labkit.checks import run_code_check, run_record_check
from labkit.checks.origin_check import origin_gap, origin_now

#: keys labkit writes into metrics.json itself — not evaluate()'s to
#: reproduce: runlog's duration, llm's retry counter (the stamped evaluate()
#: records it)
LABKIT_KEYS = frozenset({"duration_s", "llm_retries"})


@dataclass(frozen=True)
class Verdict:
    """What a recheck held: the run, the keys compared, what grew, the numbers the note was held to."""

    run_id: str
    # the output files pinned, by the key the caller named each with; empty:
    # no output file compared, the run was recomputed from its inputs
    # (`holds_from_inputs`)
    outs: Mapping[str, Path]
    keys_compared: int
    grown: list[str]  # keys the recomputation has and the run did not
    numbers: list[str]  # what the note was held to


#: the clause every `NotVerifiable` refusal carries, written here only
#: (`require_run_code`). report-check looks for it as a substring of what
#: an area's `--check` printed — the one channel a script's exit leaves —
#: to tell a missing proof from a failed comparison
NOT_VERIFIABLE = (
    "is not verifiable — nothing shows that the code here now is the code it ran"
)


class NotVerifiable(SystemExit):
    """A recalculation that could not be made: nothing shows that the code
    here now is the code the run ran (`require_run_code`, the sentence
    carries the clause `NOT_VERIFIABLE`), or the rows an older run
    recorded are nowhere left (`output_as_recorded`). A missing proof, not
    a failed comparison — no number was compared. A SystemExit like every
    refusal of this module, so an area's `--check` ends nonzero with the
    sentence; a caller that looks into a run no release waits on catches
    this class and reports it."""


def chosen_run(
    area: Path,
    protocol_text: str,
    run_id: str | None = None,
    *,
    state: AreaState | None = None,
) -> Path:
    """The run a protocol is held to — and the run `--from-run` writes back.

    The choice is `answering_run.bound_answering_run` for the protocol's stamped id,
    the same one finalize and intent-check make; RUN_ID names a run instead,
    which must be completed and bound to that id. Never a repeat draw, named
    or not. STATE is the area's state when the caller built it already
    (`holds`: one build per check); None builds it here, and only when the
    choice is asked (no RUN_ID).
    """
    try:
        pid = protocol_block.head(protocol_text).id
    except protocol_block.BlockError as exc:
        raise SystemExit(f"recheck: {exc}") from exc
    if pid is None:
        raise SystemExit(
            "recheck: the protocol carries no stamped id ([protocol] id) — no run "
            "binds to it; `labkit-init exp` stamps it"
        )
    if run_id is not None:
        return _named_run(runs.run_path(area, run_id), pid)
    held = state if state is not None else state_of(area)
    choice, blocker, lines = held.measured_of(pid).told(protocol_text)
    if blocker or choice.run_dir is None:
        why = blocker.message if blocker else "no run answers"
        raise SystemExit(f"recheck: {why}" + "".join(f"\n  {ln}" for ln in lines))
    return choice.run_dir


def _named_run(d: Path, pid: str) -> Path:
    """RUN_ID as the explicit choice: completed, no repeat, bound to PID."""
    try:
        state = runs.completion_state(d) if path_kind(d) == "dir" else "missing"
        if state != runs.COMPLETED:
            raise SystemExit(f"recheck: {d} is not a completed run ({state})")
        cfg = runs.read_run_config(d)
        parent = cfg.repeat_of if cfg else None
    except runs.RunConfigError as exc:
        raise SystemExit(f"recheck: {exc}") from exc
    if parent is not None:
        # no --force past this: a repeat never answers, named or not
        raise SystemExit(
            f"recheck: {d.name} is a repeat of {parent} — supporting "
            f"evidence, never the answer; `02_analyze.py --draws` shows it"
        )
    bound = cfg.protocol.id if cfg else None
    if bound != pid:
        raise SystemExit(
            f"recheck: {d.name} is bound to {bound or 'no protocol'}, not to "
            f"{pid} — it answers another question"
        )
    return d


def run_dir(
    area: Path,
    protocol: Path,
    run_id: str | None = None,
    *,
    state: AreaState | None = None,
) -> Path:
    """`chosen_run` for a protocol the area's state holds — STATE, or the
    state built here once for the protocol's text and the choice."""
    held = state if state is not None else state_of(area)
    return chosen_run(area, held.text_of(protocol), run_id, state=held)


def answering_run_dir(area: Path, protocol: Path) -> Path:
    """The run directory PROTOCOL of AREA answers with — the run an area's
    own analysis reads: the adopted run (`[result] run`), else the newest
    completed run bound to the protocol's id — the newest that reports an
    intent key where one does —; never a repeat draw. A choice whose run
    reports no intent key while the protocol registers ids is refused. The
    choice `--check`, finalize and intent-check make (`run_dir`,
    `chosen_run`), no rule of its own: a newer run does not replace an
    adopted one. It guarantees that choice, not that the run is fit to
    answer the question — that is what finalize, the audits and
    report-check hold. Raises SystemExit with the reason where no run
    answers, or the protocol carries no stamped id."""
    return run_dir(area, protocol)


def protocol_named(area: Path, name: str | None) -> Path:
    """The protocol an area's `--check` holds: the one NAME names — a file
    name inside AREA, or a path —, else the area's only one
    (`repo.the_protocol`, the choice every command makes). Raises
    SystemExit where the area has no protocol, where the named one is not
    there, and — listing the candidates — where it has several and none
    is named: the check never takes the first."""
    try:
        return the_protocol(area, Path(name) if name is not None else None)
    except ProtocolChoiceError as exc:
        raise SystemExit(f"recheck: {exc}") from exc


def script_module(area: Path, run: Path) -> ModuleType:
    """The script RUN ran, imported from where it stands in AREA now
    (`run_code_check.script_of`): its evaluation is the one a
    recalculation of RUN owes, whichever protocol of the area RUN answers.
    Whether that file is still the code the run ran is `require_run_code`'s
    question, asked inside `holds`. Raises SystemExit when RUN's record
    does not read, and `NotVerifiable` when no record says which script
    ran, or that script is gone or cannot be told apart from another of
    its name. Side effect: runs the script's module level — also of a
    script changed since the run, which `holds` refuses only afterwards."""
    try:
        cfg = runs.read_run_config(run)
    except runs.RunConfigError as exc:
        raise SystemExit(f"recheck: {exc}") from exc
    # a sentence in place of the file: gone, or several of its name
    script = (
        "it has no record of the script it ran"
        if cfg is None
        else run_code_check.script_of(area, cfg)
    )
    if isinstance(script, str):
        raise NotVerifiable(
            f"recheck: run {run.name} {NOT_VERIFIABLE}: {script}. Its number is "
            f"recomputed with the script it ran, never with another: restore "
            f"that script and the run's record, or measure anew and hold that run"
        )
    # unique per area and script: two areas' `01_measure.py` in one process
    # must not share a module
    name = re.sub(r"\W", "_", f"script_{area.name}_{script.stem}")
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise SystemExit(f"recheck: run {run.name}: {script} does not import")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # a dataclass in it looks its module up here
    spec.loader.exec_module(module)
    return module


def registered_output(run: Path, out: Path) -> runs.OutputEntry:
    """The entry RUN registered for the file OUT (its outputs.json).

    Raises:
        SystemExit: RUN did not register OUT as an output.
    """
    outputs = runs.read_outputs(run) or []
    recorded = next((o for o in outputs if o.path.resolve() == out.resolve()), None)
    if recorded is None:
        raise SystemExit(
            f"recheck: run {run.name} did not register {out.name} as an output"
        )
    return recorded


def pin(run: Path, out: Path) -> None:
    """Refuse rows the chosen run did not write: OUT must be an output RUN
    registered (`registered_output`) and still the file it recorded."""
    recorded = registered_output(run, out)
    drift = run_record_check.output_drift(runs.output_now(recorded))
    if drift is not None:
        raise SystemExit(
            f"recheck: {out.name} is not the file run {run.name} recorded — "
            f"{drift.why}; rerun the script or name that run"
        )


@dataclass(frozen=True)
class RecordedOutput:
    """An output of a run as the run recorded it (`output_as_recorded`).

    Attributes:
        path: Where those bytes read: the output's own path, or a copy in
            a temporary directory.
        commit: The commit whose blob the copy is; None for the file as it
            stands in the tree.
    """

    path: Path
    commit: str | None

    @property
    def source(self) -> str:
        """Where the bytes came from, as a check's line says it."""
        if self.commit is None:
            return "the file as it stands"
        return f"commit {self.commit[:12]}, which holds the file as the run recorded it"


@contextlib.contextmanager
def output_as_recorded(run: Path, out: Path, area: Path) -> Iterator[RecordedOutput]:
    """The output OUT of RUN (a run of AREA) with exactly the bytes RUN
    recorded — their sha256 starts with the digest outputs.json holds: the
    file as it stands where it still is that file, else the newest commit
    any ref reaches that holds OUT with those bytes
    (`repo.blobs_in_history`), written to a temporary directory that is
    removed when the block ends. The working tree, OUT included, is not
    touched. Raises SystemExit when RUN did not register OUT
    (`registered_output`), and
    `NotVerifiable` when the record holds no sha256 for it or no bytes
    with that sha256 are left — the file as it stands is never read in
    their place. Raises RuntimeError when git fails."""
    recorded = registered_output(run, out)
    now = runs.output_now(recorded)
    drift = run_record_check.output_drift(now)
    if drift is None:
        yield RecordedOutput(out, None)
        return
    missing = (
        f"recheck: run {run.name} is not verifiable — {out.name} as it stands is "
        f"not the file that run recorded ({drift.why})"
    )
    way = (
        "A missing proof, not a failed comparison: no number was compared, and "
        "the file as it stands is never read in its place. Commit a run's output "
        "before a later run overwrites it, or let each run write a file of its own"
    )
    sha = recorded.sha256
    root = git_root(area)
    if sha is None or root is None:
        raise NotVerifiable(f"{missing}. {way}")
    versions = blobs_in_history(root, out.resolve())
    for commit, blob in versions:
        data = blob_bytes(root, blob)
        if digests.digest(data, None).startswith(sha):
            with tempfile.TemporaryDirectory(prefix="labkit-recheck-") as tmp:
                copy = Path(tmp) / out.name
                copy.write_bytes(data)
                yield RecordedOutput(copy, commit)
            return
    raise NotVerifiable(
        f"{missing}, and none of the {len(versions)} version(s) of it the commits "
        f"of this repository hold has the recorded sha256 {sha}. {way}"
    )


def scopes_unchanged(run: Path, area: Path) -> None:
    """Refuse a recomputation over code the run did not use, per promise.

    The run recorded a declared-scope hash per promise (config.json `promises`);
    if a declared region changed since, recomputing with today's code
    agrees or disagrees about a different instrument. A scope that gives
    no digest now (`promises.ScopeDrift.unread`) is refused as not
    compared, with its cause's step. Runs without a promise block — and
    run dirs without config.json — have nothing to compare and pass.
    """
    cfg = runs.read_run_config(run)
    drift = promises.scope_drift(cfg.promises if cfg else None, area)
    # a scope without a digest now is not compared: its cause and that
    # cause's step, no change claimed — a rerun is refused over it too
    unread = [d for d in drift if d.unread is not None]
    if unread:
        raise SystemExit(
            f"recheck: declared scope cannot be compared with what run "
            f"{run.name} recorded: "
            + "; ".join(
                f"{d.told} — {promises.scope_way_out(d.promise_id, d.unread)}"
                for d in unread
                if d.unread is not None
            )
            + ", or recheck from that run's commit"
        )
    if drift:
        raise SystemExit(
            f"recheck: declared scope changed since run {run.name}: "
            + "; ".join(d.told for d in drift)
            + " — rerun, or recheck from that run's commit"
        )


def require_run_code(run: Path, area: Path) -> None:
    """Refuse a recalculation of RUN unless the code here now is shown to
    be the code it ran. The code is the run's script and the modules it
    imports, for the run and each run it derives from
    (`run_code_check.code_since_run`, the comparison finalize makes).
    Where that found a difference, SystemExit: a recomputation with other
    code can agree by chance and would be read as a recalculation of that
    run. Where it could not compare — no script or commit recorded, a
    helper uncommitted then, a module in another repository —
    `NotVerifiable` with each reason and the two ways out: the proof is
    missing, and agreeing with today's code would not supply it. Declared
    scopes are `scopes_unchanged`'s, before this. Reads files and git."""
    blockers, warnings = run_code_check.code_since_run(area, run)
    changed = [b.text for b in blockers if b.changed_since is not None]
    if changed:
        raise SystemExit(
            f"recheck: the code that computed run {run.name} is not the code "
            f"here now: {'; '.join(changed)} — recomputing with today's code is "
            f"no recalculation of that run; recheck from that run's commit, or "
            f"compute anew as a run of its own and hold that one"
        )
    unknown = [b.text for b in blockers] + warnings
    if unknown:
        raise NotVerifiable(
            f"recheck: run {run.name} {NOT_VERIFIABLE}: {'; '.join(unknown)}. A "
            f"missing proof, not a failed comparison: no number was compared, "
            f"and agreeing with today's code would be no recalculation of that "
            f"run. Restore the code as the run ran it and what records it (its "
            f"commit, its uncommitted.patch, its script copy), or measure anew "
            f"— a run whose code is recorded in full — and hold that one"
        )


def protocol_as_run_saw(run: Path, area: Path) -> str | None:
    """The text of the protocol RUN is bound to as RUN saw it when it
    started — its commit with its uncommitted.patch, held to the promise
    block it recorded (`protocol_then.as_measured`) —, not as the
    protocol reads now; None for an unbound run. This module's reading of
    `as_measured`, as a refusal. A run that recorded no promise block is
    read from its commit and patch alone: there is no recorded block to
    hold that text to. Raises SystemExit, with
    why and what brings the text back, when it cannot be read back: the
    protocol as it reads now is never read in its place. Reads files and
    git."""
    rd = runs.read_run_dir(run)
    if rd.error is not None:
        raise SystemExit(f"recheck: run {run.name}: {rd.error}")
    if rd.config is None or rd.config.protocol.id is None:
        return None
    binding = rd.config.protocol
    assert binding.id is not None
    protocol = bound_protocol_file(area, binding.id, binding.path)
    text, where = as_measured(protocol, rd, git_root(area), role="run")
    if text is None:
        raise SystemExit(
            f"recheck: the protocol run {run.name} was measured under cannot be "
            f"read back: {where} — what it registered then (its `[kept]` key) is "
            f"not taken from the protocol as it reads now; restore what the "
            f"sentence names, or measure anew and hold that run"
        )
    return text


def kept_keys(run: Path, area: Path) -> frozenset[str]:
    """The `[kept]` key RUN's protocol named when the run started
    (`protocol_as_run_saw`, not the protocol as it reads now) — the number
    it reports, compared exactly by `require_agreement` —, empty for an unbound run or
    a text without the table. Raises SystemExit when that text cannot be
    read back or its head does not read."""
    text = protocol_as_run_saw(run, area)
    if text is None:
        return frozenset()
    try:
        table = protocol_block.kept(text)
    except protocol_block.BlockError as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    return frozenset({table.key}) if table is not None and table.key else frozenset()


def block_unchanged(run: Path, area: Path, *, state: AreaState | None = None) -> None:
    """Refuse to hold a note whose promises changed after the run.

    A lowered threshold can leave the verdict unchanged by chance — the
    recomputation then agrees and the note looks held, against promises
    nobody registered before the number. The bound
    protocol's block as it reads now must be the one the run recorded.
    The step of a run the protocol answers with; an older run named for a
    recheck is held under its own text instead (`holds`). The protocol's
    text is read off STATE, the area's state (built here when None, for a
    bound run only).
    """
    cfg = runs.read_run_config(run)
    if cfg is None or cfg.protocol.id is None:
        return  # unbound: nothing to hold
    pid = cfg.protocol.id
    try:
        protocol = protocol_block.find_by_id(area, pid)  # by id; the path goes stale
        held = state if state is not None else state_of(area)
        block = promises.parse_block(held.text_of(protocol))
    except (protocol_block.BlockError, promises.PromiseError) as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    drift = promises.block_drift(cfg.promises, block)
    if drift:
        raise SystemExit(f"recheck: run {run.name} {drift.why}")


def rows_of(out: Path) -> list[dict]:
    """The data rows of the row file OUT, in order: one JSON object per
    non-empty line, every `_meta` header line left out
    (`jsonl.data_rows_of`). Public API (`docs/architecture.md`): the
    stamped analysis script calls it. Raises OSError when OUT cannot be
    read; ValueError for a line that is not JSON or no object, naming the
    file and the line, and for bytes that are not UTF-8."""
    return jsonl.data_rows_of(out)


def output_rows(run: Path, outs: Mapping[str, Path]) -> dict[str, list[dict]]:
    """The rows of every output of OUTS, by its key (`rows_of`) — what a
    recomputation over several output files is handed. Raises SystemExit,
    naming RUN, the key and the file, for a file that is no row file (a
    JSON document, such as a stagekit stage output, is one): nothing is
    read in its place."""
    rows: dict[str, list[dict]] = {}
    for key, out in outs.items():
        try:
            rows[key] = rows_of(out)
        except ValueError as exc:
            raise SystemExit(
                f"recheck: run {run.name}: output {key!r} ({out.name}) is no row "
                f"file — {exc}. The recomputation reads row files: write the rows "
                f"the number reads into one inside the run and register it"
            ) from exc
    return rows


def _named_outputs(outs: Mapping[str, Path]) -> None:
    """Refuse an OUTS that names no output file: a recomputation over
    nothing compares nothing. Raises ValueError."""
    if not outs:
        raise ValueError(
            "recheck: OUTS names no output file — pass each file the number "
            "is computed from under a key of its own"
        )


def require_agreement(
    metrics: dict,
    recomputed: dict,
    ignore: frozenset[str] = LABKIT_KEYS,
    kept: frozenset[str] = frozenset(),
) -> list[str]:
    """metrics.json against the recomputation: SystemExit where they
    disagree, else the keys that grew.
    As LAB-041 Generate numbers, don't retype them states it: the
    registered identifiers (`promises.INTENT_KEY`) are compared exactly —
    on one side only, or with another value, the check fails —, and so are
    the KEPT
    keys (the protocol's `[kept]` key, `kept_keys`: the number it
    reports), on one side only failing as well; absent from both, this
    check passes it — finalize blocks a metrics.json that does not hold it
    as a finite number (`kept_number_gaps`). Of the other
    descriptive keys none may disappear, and a value that differs or a key
    that grew is no failure. Compared as JSON, the way the run recorded it
    (`runs.as_stored`): a tuple from evaluate() is the list in metrics.json,
    not a difference, and `1` is not `true`."""
    recomputed = json.loads(json.dumps(recomputed))
    intent = {k for k in set(metrics) | set(recomputed) if promises.INTENT_KEY.match(k)}
    kept_one_sided = {
        k: [
            side
            for side, d in ((runs.METRICS_FILE, metrics), ("recomputation", recomputed))
            if k not in d
        ]
        for k in sorted(kept)
        if (k in metrics) != (k in recomputed)
    }
    if kept_one_sided:
        raise SystemExit(
            f"recheck: the kept number is missing — {kept_one_sided}: the number the "
            f"protocol reports must stand in metrics.json and come out of the "
            f"recomputation"
        )
    one_sided = sorted(k for k in intent if (k in metrics) != (k in recomputed))
    vanished = sorted(set(metrics) - set(recomputed) - ignore)
    if one_sided or vanished:
        beside = (
            f" — {vanished} stand in metrics.json, but the evaluation of the kept "
            f"rows does not produce them: compute each in `evaluate_rows()` from "
            f"what the rows carry (a required check too), never beside it"
            if vanished
            else ""
        )
        raise SystemExit(
            f"recheck: metrics.json and the recomputation disagree — "
            f"intent keys on one side only {one_sided}, vanished {vanished}{beside}"
        )
    differing = sorted(
        k
        for k in intent | kept
        if k in metrics and runs.as_stored(recomputed[k]) != runs.as_stored(metrics[k])
    )
    if differing:
        raise SystemExit(
            f"recheck: recomputation differs from metrics.json in the "
            f"identifiers or the kept number {differing}"
        )
    return sorted(set(recomputed) - set(metrics))


def plain_numbers(metrics: dict) -> list[str]:
    """Default: every top-level number, written the way Python prints it —
    `nan`, `inf` and `-inf` for a value that is not finite, as
    `result_render.recorded_results_line` writes it into the protocol."""
    return [
        str(v)
        for v in metrics.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]


#: one number as the note writes it: a sign only where it cannot be a
#: hyphen (`3-5` is 3 and 5, `x=-0.5` is -0.5), a decimal part, an exponent
_NUMBER_TOKEN = re.compile(
    r"(?<![\d.])(?:(?<![A-Za-z0-9_)\]])[-+])?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?!\d)"
)


#: a value no digit writes — NaN and the infinities as `plain_numbers`
#: gives them, with a sign, in any case: a whole word of the note, so `nan`
#: is not in `nanometre` and `inf` not in `info`; a dot may follow (the
#: note's commas are dots by the time it is read)
_NONFINITE_TOKEN = re.compile(r"(?<![\w.])-?(?i:nan|inf)(?!\w)")


def _present(number: str, text: str) -> bool:
    """The number as a whole token of the note, sign and exponent included,
    not as a digit run inside another number or a stamp: `3.5` is not in
    `13.57`, `12` is not in `12.7`, `0.5` is not in `-0.5`, `1` and `5`
    are not in `1e-5`, and `10` is not in the run id `…T10-22-33_ab12` or
    the date `2026-10-05` — the run id is mandatory in every note, so a
    count equal to one of its parts would otherwise pass as cited. A leading `+` is no sign. A value that is not
    finite (`nan`, `inf`, `-inf`) is a whole word of the note, in any
    case, its sign included: the write-back and this check share one
    spelling, so a NaN the run recorded can be cited and proven."""
    n = number.replace("−", "-").replace(",", ".").lstrip("+")
    text = runs.RUN_ID_OR_DATE.sub(" ", text.replace("−", "-").replace(",", "."))
    if _NONFINITE_TOKEN.fullmatch(n):
        return any(
            t.group().lower() == n.lower() for t in _NONFINITE_TOKEN.finditer(text)
        )
    return any(t.group().lstrip("+") == n for t in _NUMBER_TOKEN.finditer(text))


ANSWER_OPEN = re.compile(
    r"^\s*[-*]\s+\*\*Recorded results:\*\*\s*(<!--[^>]*-->\s*)?<", re.M
)


def cited(note: Path, numbers: list[str], run_id: str) -> None:
    """Refuse unless the note contains every reported number and cites the run.

    A Recorded results line still holding the stamp's placeholder is named as such —
    "numbers not in PROTOCOL" before the write-back would read as a failed
    check; the cure is one command."""
    found = file_text(note)
    if found is None:
        raise SystemExit(f"recheck: {note}: no such note")
    text = found.replace("−", "-").replace(",", ".")
    missing = sorted({n for n in numbers if not _present(n, text)})
    if missing and ANSWER_OPEN.search(text):
        raise SystemExit(
            f"recheck: {note.name} has no answer yet — "
            f"`{adopt_command(note, run_id)}` writes it once that run's "
            f"analysis audit is decided and report-check shows no other blocker"
        )
    if missing:
        raise SystemExit(f"recheck: numbers not in {note.name}: {missing}")
    if run_id not in text:
        raise SystemExit(f"recheck: {note.name} does not cite run {run_id}")


def verified_outputs(
    run: Path,
    area: Path,
    outs: Mapping[str, Path],
    recompute: Callable[[Mapping[str, list[dict]]], dict],
    ignore: frozenset[str] = LABKIT_KEYS,
    *,
    hold_block_now: bool = True,
    state: AreaState | None = None,
) -> tuple[dict, list[str]]:
    """pin → scopes → code → block (if HOLD_BLOCK_NOW) → agree for one run
    and the output files its number is computed from, no note: (its
    metrics, the keys the recomputation grew). Every file of OUTS is
    pinned first (`pin`: registered by RUN, its bytes the ones RUN
    recorded); only then is RECOMPUTE handed the rows of all of them by
    their key (`output_rows`) and compared with metrics.json (`require_agreement`). What
    `holds_outputs` checks before the note, and what `02_analyze.py
    --draws` checks for every draw — a draw shown unchecked lets an edited
    repeat file change the flipped items, an edited metrics.json the
    range. The block step holds the protocol as it reads now to the block
    the run recorded (`block_unchanged`) unless HOLD_BLOCK_NOW is False —
    an older run rechecked after the protocol moved on; the kept key is
    always the one of the run's own text (`kept_keys`). STATE is the
    area's state the caller built (`holds_outputs`); with None the block
    step builds it, for a run bound to a protocol only. Raises ValueError
    for an empty OUTS, SystemExit on the first disagreement,
    `NotVerifiable` where the code step finds no proof; a failed pin or
    code step leaves RECOMPUTE uncalled."""
    _named_outputs(outs)
    for out in outs.values():
        pin(run, out)
    scopes_unchanged(run, area)
    require_run_code(run, area)
    if hold_block_now:
        block_unchanged(run, area, state=state)
    metrics = runs.read_metrics(runs.metrics_path(run))
    grown = require_agreement(
        metrics,
        recompute(output_rows(run, outs)),
        ignore,
        kept=kept_keys(run, area),
    )
    return metrics, grown


def verified(
    run: Path,
    area: Path,
    out: Path,
    recompute: Callable[[list[dict]], dict],
    ignore: frozenset[str] = LABKIT_KEYS,
    *,
    hold_block_now: bool = True,
    state: AreaState | None = None,
) -> tuple[dict, list[str]]:
    """`verified_outputs` for a number computed from one output file OUT:
    RECOMPUTE takes its rows."""
    return verified_outputs(
        run,
        area,
        {out.name: out},
        lambda rows: recompute(rows[out.name]),
        ignore,
        hold_block_now=hold_block_now,
        state=state,
    )


def holds_outputs(
    area: Path,
    outs: Mapping[str, Path],
    recompute: Callable[[Mapping[str, list[dict]]], dict],
    note: Path,
    run_id: str | None = None,
    numbers: Callable[[dict], list[str]] | None = None,
    ignore: frozenset[str] | None = None,
    protocol: Path | None = None,
) -> Verdict:
    """pin → scopes → code → block → agree → cited, for the run that answers the
    protocol (`chosen_run`; or `run_id`) and every output file of OUTS
    (`verified_outputs`; RECOMPUTE takes their rows by key). The protocol
    is `note` unless `protocol` names it — a results note under notes/
    carries no head. The answering run (no RUN_ID) also holds the protocol
    as it reads now to the block it recorded; a run named by RUN_ID is
    rechecked under its own text — the block it recorded and the `[kept]`
    key of the protocol as it started under it —, whatever the protocol
    registers now. The code step (`require_run_code`) refuses a run whose
    script or imported modules changed since it ran, and raises
    `NotVerifiable` for a run whose code cannot be compared with the code
    here.

    `numbers(metrics)` formats what the note must carry — pass your own when
    the note rounds; None is `plain_numbers`. IGNORE names the metrics keys
    not compared; None is the keys labkit writes itself (`LABKIT_KEYS`:
    `duration_s`, `llm_retries`). The area's state is built once, here, and the run
    choice and the block step read that build. Raises ValueError for an
    empty OUTS, SystemExit on the first disagreement, `NotVerifiable` where
    the code step finds no proof."""
    _named_outputs(outs)
    numbers = plain_numbers if numbers is None else numbers
    ignore = LABKIT_KEYS if ignore is None else ignore
    state = state_of(area)
    run = run_dir(area, protocol or note, run_id, state=state)
    answering = run_id is None  # no run named: the one the protocol answers with
    metrics, grown = verified_outputs(
        run, area, outs, recompute, ignore, hold_block_now=answering, state=state
    )
    return _cited_verdict(run, outs, metrics, grown, note, numbers, ignore)


def holds(
    area: Path,
    out: Path,
    recompute: Callable[[list[dict]], dict],
    note: Path,
    run_id: str | None = None,
    numbers: Callable[[dict], list[str]] = plain_numbers,
    ignore: frozenset[str] = LABKIT_KEYS,
    protocol: Path | None = None,
) -> Verdict:
    """`holds_outputs` for a number computed from one output file OUT:
    RECOMPUTE takes its rows."""
    return holds_outputs(
        area,
        {out.name: out},
        lambda rows: recompute(rows[out.name]),
        note,
        run_id,
        numbers,
        ignore,
        protocol,
    )


@dataclass(frozen=True)
class AsMeasured:
    """What the separate check of an older run held (`holds_as_measured`).

    Attributes:
        run_id: The run.
        sources: Where the rows of each output were read, by its key
            (`RecordedOutput.source`).
        keys_compared: The keys of its metrics.json compared.
        grown: Keys the recomputation has and the run did not.
    """

    run_id: str
    sources: Mapping[str, str]
    keys_compared: int
    grown: list[str]

    @property
    def source(self) -> str:
        """Where the rows were read, as a check's line says it: the one
        output's source, or each output's by its key."""
        if len(self.sources) == 1:
            return next(iter(self.sources.values()))
        return "; ".join(f"{key} from {where}" for key, where in self.sources.items())


def holds_as_measured_outputs(
    area: Path,
    outs: Mapping[str, Path],
    recompute: Callable[[Mapping[str, list[dict]]], dict],
    run_id: str,
    protocol: Path,
    ignore: frozenset[str] = LABKIT_KEYS,
) -> AsMeasured:
    """The separate check of an older run RUN_ID of PROTOCOL over every
    output file of OUTS: rows → scopes → code → agree, under the text the
    run started under. The rows of each output are the bytes the run
    recorded (`output_as_recorded`: the file as it stands, else a commit's
    copy in a temporary directory), handed to RECOMPUTE by key; the
    `[kept]` key compared exactly is the one of its own text
    (`kept_keys`), and the protocol as it reads now is not held to the
    block the run recorded. No note is read: the check changes no adoption
    and releases nothing — the protocol's number is held by
    `holds_outputs` alone. RUN_ID must be a completed measurement bound to
    PROTOCOL, no repeat (`chosen_run`). Raises ValueError for an empty
    OUTS, SystemExit on the first disagreement, `NotVerifiable` where the
    recorded rows of any output are nowhere left or the code step finds no
    proof."""
    _named_outputs(outs)
    run = run_dir(area, protocol, run_id)
    with contextlib.ExitStack() as stack:
        kept_outputs = {
            key: stack.enter_context(output_as_recorded(run, out, area))
            for key, out in outs.items()
        }
        scopes_unchanged(run, area)
        require_run_code(run, area)
        metrics = runs.read_metrics(runs.metrics_path(run))
        grown = require_agreement(
            metrics,
            recompute(output_rows(run, {k: r.path for k, r in kept_outputs.items()})),
            ignore,
            kept=kept_keys(run, area),
        )
        return AsMeasured(
            run.name,
            {k: r.source for k, r in kept_outputs.items()},
            len(set(metrics) - ignore),
            grown,
        )


def holds_as_measured(
    area: Path,
    out: Path,
    recompute: Callable[[list[dict]], dict],
    run_id: str,
    protocol: Path,
    ignore: frozenset[str] = LABKIT_KEYS,
) -> AsMeasured:
    """`holds_as_measured_outputs` for a number computed from one output
    file OUT: RECOMPUTE takes its rows."""
    return holds_as_measured_outputs(
        area,
        {out.name: out},
        lambda rows: recompute(rows[out.name]),
        run_id,
        protocol,
        ignore,
    )


def _cited_verdict(
    run: Path,
    outs: Mapping[str, Path],
    metrics: dict,
    grown: list[str],
    note: Path,
    numbers: Callable[[dict], list[str]],
    ignore: frozenset[str],
) -> Verdict:
    """The last step of `holds` and `holds_from_inputs`: NOTE carries every
    number of RUN's METRICS as NUMBERS formats them, and the run id
    (`cited`); the Verdict. Raises SystemExit as `cited` does."""
    wanted = numbers({k: v for k, v in metrics.items() if k not in ignore})
    cited(note, wanted, run.name)
    return Verdict(
        run_id=run.name,
        outs=outs,
        grown=grown,
        numbers=wanted,
        keys_compared=len(set(metrics) - ignore),
    )


def reads_another_run(run: Path) -> bool:
    """Does RUN compute from another run's output — does an input it
    recorded name an origin run? Such a run's number is owed the
    recalculation from its inputs (`verified_from_inputs`); a run over
    plain inputs is held by its own rows (`holds`). Raises SystemExit when
    the input record does not read."""
    try:
        entries = runs.read_data(run) or []
    except runs.ArtefactError as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    return any(e.origin_run is not None for e in entries)


def inputs_pinned(run: Path, area: Path) -> dict[str, Path]:
    """Every input RUN recorded (`data=`), by its key, each held to be the
    bytes the run read before anything is recomputed from it: an input
    whose record names an origin run is still that run's registered output
    with those bytes (`origin_check.origin_gap`, the condition finalize's
    input-origins station holds), a plain input still has the sha256 the
    run recorded (`run_record_check.source_drift`). The paths resolved
    against the area, as the run's start resolved them. Raises SystemExit
    naming the input and the part that fails, and for a record without
    inputs or one that does not read."""
    try:
        entries = runs.read_data(run)
    except runs.ArtefactError as exc:
        raise SystemExit(f"recheck: run {run.name}: {exc}") from exc
    if not entries:
        raise SystemExit(
            f"recheck: run {run.name} recorded no input file — nothing to "
            f"recompute from; hold its own output with `holds`"
        )
    pinned: dict[str, Path] = {}
    for entry in entries:
        path = runs.resolve_recorded(entry.recorded, area)
        if entry.origin_run is not None:
            gap = origin_gap(origin_now(area, entry))
            if gap is not None:
                raise SystemExit(
                    f"recheck: run {run.name}: {gap.told} — not recomputed "
                    f"from inputs that are not the ones it read"
                )
        else:
            drift = run_record_check.source_drift(path, entry.sha256)
            if drift is not None:
                raise SystemExit(
                    f"recheck: run {run.name}: data[{entry.key!r}] = "
                    f"{entry.recorded} is not the input it read: {drift}, the "
                    f"run recorded sha256 {entry.sha256}"
                )
        pinned[entry.key] = path
    return pinned


def verified_from_inputs(
    run: Path,
    area: Path,
    recompute: Callable[[Mapping[str, Path]], dict],
    ignore: frozenset[str] = LABKIT_KEYS,
    *,
    hold_block_now: bool = True,
) -> tuple[dict, list[str]]:
    """inputs → scopes → code → block (if HOLD_BLOCK_NOW) → agree for RUN, no note: (its metrics, the
    keys the recomputation grew). First every recorded input is the bytes
    the run read (`inputs_pinned`); only then RECOMPUTE — the run's own
    evaluation, given each input's path by its `data=` key — is compared
    with metrics.json as `verified` compares it, HOLD_BLOCK_NOW as there. The source runs are not
    run again. Raises SystemExit on the first disagreement, `NotVerifiable`
    where the code step finds no proof; a failed input or code step leaves
    RECOMPUTE uncalled."""
    pinned = inputs_pinned(run, area)
    scopes_unchanged(run, area)
    require_run_code(run, area)
    if hold_block_now:
        block_unchanged(run, area)
    metrics = runs.read_metrics(runs.metrics_path(run))
    grown = require_agreement(
        metrics, recompute(pinned), ignore, kept=kept_keys(run, area)
    )
    return metrics, grown


def holds_from_inputs(
    area: Path,
    recompute: Callable[[Mapping[str, Path]], dict],
    note: Path,
    run_id: str | None = None,
    numbers: Callable[[dict], list[str]] = plain_numbers,
    ignore: frozenset[str] = LABKIT_KEYS,
    protocol: Path | None = None,
) -> Verdict:
    """`holds` for a run that computes from its recorded inputs — a
    comparison over source runs' outputs: inputs → scopes → code → block →
    agree → cited (`verified_from_inputs`, `_cited_verdict`), for the run
    that answers the protocol (`chosen_run`; or RUN_ID). The code step is
    `holds`'s, and as there a run named by RUN_ID is rechecked under its
    own text, not held to the promise block as it reads now. Raises
    SystemExit on the first disagreement, `NotVerifiable` where the code
    step finds no proof."""
    run = run_dir(area, protocol or note, run_id)
    answering = run_id is None  # no run named: the one the protocol answers with
    metrics, grown = verified_from_inputs(
        run, area, recompute, ignore, hold_block_now=answering
    )
    return _cited_verdict(run, {}, metrics, grown, note, numbers, ignore)
