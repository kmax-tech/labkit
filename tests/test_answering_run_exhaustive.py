"""`runs.bound_answering_run` over every area of up to three runs drawn from
nine kinds, held to an oracle that restates the rule from its docstrings.

The worst faults the audit of 2026-10-15 found were in this choice (the
wrong run's number written into the protocol), and the case tests in
tests/test_answering_run.py each cover one arrangement. Here every
arrangement up to three runs is checked (820 areas, once on different days
and once in one second): the oracle is written from the rule, not from
the code, so a disagreement is a finding on one side or the other.

    .venv/bin/python -m pytest tests/test_answering_run_exhaustive.py
"""

from __future__ import annotations

import contextlib
import io
import itertools
import json
import re
import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from protocol_fixture import head

from labkit import audit, finalize, intent_check, params, recheck, runs
from labkit.gate import Findings

PID = "p-aaaaaaaaaaaaaaaa"
OTHER = "p-bbbbbbbbbbbbbbbb"
PARENT = "2026-09-01T00-00-00_0000"


@dataclass(frozen=True)
class Kind:
    """One kind of run directory and what the rule says about it."""

    name: str
    pid: str | None = PID
    metrics: dict | None = None  # None: no metrics.json
    completion: bool = True
    repeat: bool = False
    unreadable: bool = False
    #: the reason bound_runs gives for leaving it out; None if it is taken
    why: str | None = None
    keys: bool = True


KEYS = {"c1_pass": True}
KINDS = (
    Kind("answer", metrics=KEYS),
    Kind("probe", metrics={"n_rows": 3}, keys=False),
    Kind("unfinalized", metrics=KEYS, completion=False, why="unfinalized"),
    Kind("corrupt", why="corrupt"),
    Kind("crashed", completion=False, why="crashed"),
    Kind("other", pid=OTHER, metrics=KEYS, why=f"bound to {OTHER}"),
    Kind("unbound", pid=None, metrics=KEYS, why="unbound (no protocol id at run time)"),
    Kind(
        "repeat",
        metrics=KEYS,
        repeat=True,
        why=f"a repeat of {PARENT} — supporting evidence, never the answer",
    ),
    Kind("unreadable", unreadable=True, why="<unreadable>"),
)


def _write(area: Path, name: str, kind: Kind) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    if kind.unreadable:
        (d / "config.json").write_text("{not json", encoding="utf-8")
        return d
    cfg: dict = {
        "schema_version": 2,
        "script": "01_measure.py",
        "pid": 1,
        "protocol": {"id": kind.pid, "path": "x.md"},
        "derived_from": None,
        "models_resolved": {},
        "config": {},
    }
    if kind.repeat:
        cfg["repeat_of"] = PARENT
        cfg["draw"] = 2
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if kind.metrics is not None:
        (d / "metrics.json").write_text(json.dumps(kind.metrics), encoding="utf-8")
    if kind.completion:
        (d / "completion.json").write_text(
            json.dumps({"schema_version": 2, "finished": "x", "git": "g"}),
            encoding="utf-8",
        )
    return d


@dataclass(frozen=True)
class Expected:
    run_dir: Path | None
    skipped_newer: int
    reports_intent_keys: bool
    blocked_by: str | None  # "none-bound", "newer-unreadable", "same-second" or None
    exclusions: dict[str, str]


def oracle(placed: list[tuple[Path, Kind]]) -> Expected:
    """The rule, restated: of the completed runs bound to the protocol that
    are not repeats, the newest reporting an intent key answers (newer
    probes are skipped and counted); if none reports one, the newest bound
    run is returned and says so. No bound run is a blocker; an unreadable
    run that may have started after the choice (newer, or the same second)
    is a blocker; so is another bound run of the same standing started in
    the same second. Every other run is excluded with its reason. `placed`
    is in name order."""
    exclusions = {d.name: k.why for d, k in placed if k.why is not None}
    taken = [(d, k) for d, k in placed if k.why is None]
    if not taken:
        return Expected(None, 0, True, "none-bound", exclusions)
    with_keys = [i for i, (_, k) in enumerate(taken) if k.keys]
    if with_keys:
        i = with_keys[-1]
        chosen, skipped, has_keys = taken[i][0], len(taken) - 1 - i, True
    else:
        chosen, skipped, has_keys = taken[-1][0], 0, False

    def second(d: Path) -> str:
        return d.name.split("_")[0]

    if any(
        k.unreadable
        and (d.name > chosen.name or (d != chosen and second(d) == second(chosen)))
        for d, k in placed
    ):
        return Expected(None, skipped, has_keys, "newer-unreadable", exclusions)
    if any(
        d != chosen and second(d) == second(chosen) and (k.keys or not has_keys)
        for d, k in taken
    ):
        return Expected(None, skipped, has_keys, "same-second", exclusions)
    return Expected(chosen, skipped, has_keys, None, exclusions)


def _name(i: int, one_second: bool) -> str:
    """The i-th run id in name order: a day apart, or one second apart only
    by suffix."""
    if one_second:
        return f"2026-10-01T10-00-00_{'abc'[i] * 4}"
    return f"2026-10-0{i + 1}T10-00-00_aaaa"


class EveryArrangement(unittest.TestCase):
    def test_up_to_three_runs_of_nine_kinds(self) -> None:
        """Each arrangement twice: started on different days, and all in one
        second (the suffix then orders them by chance, 2026-10-15)."""
        checked = 0
        for one_second in (False, True):
            for n in range(4):
                for combo in itertools.product(KINDS, repeat=n):
                    with self.subTest(
                        kinds=[k.name for k in combo], one_second=one_second
                    ):
                        self._check(combo, one_second)
                    checked += 1
        self.assertEqual(checked, 2 * (1 + 9 + 81 + 729))

    def _check(self, combo: tuple[Kind, ...], one_second: bool) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            area = tmp / "area"
            (area / "runs").mkdir(parents=True)
            placed = [
                (_write(area, _name(i, one_second), k), k) for i, k in enumerate(combo)
            ]
            want = oracle(placed)
            got = runs.bound_answering_run(area, PID)
            self.assertEqual(got.run_dir, want.run_dir)
            self.assertEqual(got.skipped_newer, want.skipped_newer)
            self.assertEqual(got.reports_intent_keys, want.reports_intent_keys)
            if want.blocked_by is None:
                self.assertIsNone(got.blocker)
            elif want.blocked_by == "same-second":
                self.assertIn("started in the same second", got.blocker or "")
            elif want.blocked_by == "none-bound":
                self.assertIn(f"no completed run bound to {PID}", got.blocker or "")
            else:
                self.assertIn("cannot say which protocol", got.blocker or "")
            got_ex = {x.run_dir.name: x.why for x in got.exclusions}
            self.assertEqual(set(got_ex), set(want.exclusions))
            for name, why in want.exclusions.items():
                if why != "<unreadable>":
                    self.assertEqual(got_ex[name], why, name)
        finally:
            shutil.rmtree(tmp)


#: a protocol that registers an id, so a probe-only area is no answer
PROTOCOL_TEXT = "- **Answer to the question:** [C1] holds\n\n" + head(id=PID)
BLOCKED = "<blocked>"


def _chosen_by_every_check(area: Path, protocol: Path) -> dict[str, str]:
    """The run each check holds the protocol to, by name, or BLOCKED."""
    text = protocol.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    quiet = contextlib.redirect_stdout(io.StringIO())

    choice = runs.bound_answering_run(area, PID)
    blocker, _ = choice.explain(promises_registered := True)
    assert promises_registered
    out["bound_answering_run"] = (
        BLOCKED if blocker or choice.run_dir is None else choice.run_dir.name
    )

    found = Findings()
    with quiet:
        got = finalize.answering_run(found, area, PID, True)
    out["finalize"] = BLOCKED if found.blocked or got is None else got.name

    with contextlib.redirect_stdout(io.StringIO()):
        bound = intent_check.choose_bound(protocol, PID, True)
    out["intent-check"] = bound.parent.name if isinstance(bound, Path) else BLOCKED

    try:
        out["recheck"] = recheck.chosen_run(area, text).name
    except SystemExit:
        out["recheck"] = BLOCKED

    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        params.main([str(area)])
    m = re.search(r" · run (\S+) \(", printed.getvalue())
    out["params"] = m.group(1) if m else BLOCKED

    label = audit.run_rows(area, protocol)[0][0]
    out["audit"] = label.split("runs/", 1)[1] if "runs/" in label else BLOCKED
    return out


class EveryCheckChoosesTheSameRun(unittest.TestCase):
    """finalize, intent-check, recheck, params and the audit each call
    `bound_answering_run`, and each renders its outcome its own way (a
    blocker, exit 2, SystemExit, a printed line, a ROWS label) — the audit
    of 2026-10-15 found four renderings with four semantics. Here all five
    are held to the one choice on every arrangement above."""

    def test_every_check_names_the_run_bound_answering_run_names(self) -> None:
        for one_second in (False, True):
            for n in range(4):
                for combo in itertools.product(KINDS, repeat=n):
                    with self.subTest(
                        kinds=[k.name for k in combo], one_second=one_second
                    ):
                        self._check(combo, one_second)

    def _check(self, combo: tuple[Kind, ...], one_second: bool) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            area = tmp / "area"
            (area / "runs").mkdir(parents=True)
            protocol = area / "PROTOCOL-a.md"
            protocol.write_text(PROTOCOL_TEXT, encoding="utf-8")
            for i, k in enumerate(combo):
                _write(area, _name(i, one_second), k)
            chosen = _chosen_by_every_check(area, protocol)
            want = chosen.pop("bound_answering_run")
            self.assertEqual(chosen, dict.fromkeys(chosen, want))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
