"""Every supported skeleton, end to end on the real chain: stamp, fill, run,
check, adopt — the count at low repeat cost, the prompt skeleton at low repeat cost with the
model faked, the estimator at high repeat cost through the freeze. Each step is the
command an agent runs (`labkit-init exp`, `protocol-fill`, the area's own
scripts under the interpreter, `finalize`, `protocol-fill --from-run`, the
stop hook, the pre-commit's `report-check --if-reported --staged`), and
what every station holds is the contract's answer (`standard_contract`).

Four findings are pinned here on the real chain, not on fixtures, numbered
as the tests cite them: the gate asks only for a check script the skeleton
stamps (1), a script changed under a reported number is held by both hooks
(2), the pre-commit reads the index the commit holds, not the tree (3), and
a refused adoption leaves no unchecked declaration standing (4).
"""

from __future__ import annotations

import pytest

import contextlib
import importlib.util
import io
import json
from datetime import datetime, timezone
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from labkit.tools import report_command
from labkit.formats.area_state import state_of
from labkit.gates import (
    audit,
    agent_hooks,
    finalize,
    hook_post_change,
    preflight,
    registration_hold,
    report_check,
    report_context,
)
from labkit.tools import protocol_fill, scaffold
from labkit.run import runlog, start_check
from labkit.formats import (
    answering_run,
    run_index,
    run_starts,
    findings,
    promises,
    protocol_block,
    protocol_check,
    runs,
    scope_sha,
    standard_contract as sc,
)
from protocol_fixture import (
    decide_words,
    fill_known_case,
    protocol_id_of,
    registration_of,
    shown_sha,
)  # noqa: E402
from labkit.formats.runs import RUN_ID_TIME  # noqa: E402

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

#: the second of a run id, as `time.strftime(RUN_ID_TIME)` writes it
_SECOND = time.strftime(RUN_ID_TIME, time.gmtime(0))


def _replace(path: Path, pairs: list[tuple[str, str]]) -> None:
    """Fill a stamped file's TODOs: every OLD once, by exact text."""
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if text.count(old) != 1:
            raise AssertionError(f"{path.name}: {old!r} stands {text.count(old)}×")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


class Lab:
    """A stamped lab repo under git, and the commands an agent runs in it."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        # the session's transcript, its first record dated as the lab is made:
        # the stop dates the session's commits by it
        self.transcript = Path(self.tmp.name) / "session.jsonl"
        when = datetime.now(timezone.utc)
        self.transcript.write_text(
            json.dumps(
                {"type": "user", "timestamp": when.isoformat(timespec="milliseconds")}
            )
            + "\n",
            encoding="utf-8",
        )
        self.root = Path(self.tmp.name) / "lab"
        self.root.mkdir()
        scaffold.stamp_lab(self.root, "lab")
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(self.root),
            "LABKIT_DETACHED": "1",  # a full run at high repeat cost starts detached
        }

    def close(self) -> None:
        self.tmp.cleanup()

    def git(self, *args: str) -> str:
        r = subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=True
        )
        return r.stdout

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def exp(self, name: str, **kw) -> tuple[Path, Path]:
        """`labkit-init exp NAME …`: the area and its protocol."""
        area, _ = scaffold.stamp_area(self.root, name, **kw)
        return area, next(area.glob("PROTOCOL-*.md"))

    def fill(self, protocol: Path, *pairs: str) -> None:
        """`protocol-fill PROTOCOL "label=value" …`, must succeed."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = protocol_fill.main([str(protocol), *pairs])
        if rc != 0:
            raise AssertionError(f"protocol-fill: {out.getvalue()}")

    def conclude(
        self, protocol: Path, answer: str = "The documents hold about two lines each."
    ) -> None:
        """Write PROTOCOL's Conclusion, which an adoption owes."""
        self.fill(protocol, f"Conclusion={answer}")

    def concluded(self, protocol: Path) -> None:
        """PROTOCOL's Conclusion written (`conclude`) when it is still open."""
        text = protocol.read_text(encoding="utf-8")
        if protocol_check.written_line(text, protocol_check.CONCLUSION_LABEL) is None:
            self.conclude(protocol)

    def fill_open(self, protocol: Path, **named: str) -> None:
        """Fill every open field with a sentence, NAMED ones with their value
        — the full form's many prose fields need text, not a particular text."""
        text = protocol.read_text(encoding="utf-8")
        from labkit.formats.protocol_check import FIELDS, fields

        after = {f.label.casefold() for f in FIELDS if f.level == "after"}
        pairs = []
        for f in fields(text):
            if f.placeholder and f.name not in after:  # --from-run writes the rest
                pairs.append(
                    f"{f.label}={named.get(f.label, f'written for the end-to-end test: {f.label}')}"
                )
        if pairs:
            self.fill(protocol, *pairs)

    def script(self, area: Path, name: str, *args: str, env: dict | None = None) -> str:
        """The area's script under the interpreter, from the repo root, as
        an agent runs it; raises with the output on a nonzero exit."""
        r = subprocess.run(
            [sys.executable, str(area / "scripts" / name), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env or self.env,
        )
        if r.returncode != 0:
            raise AssertionError(
                f"{name} {' '.join(args)} exits {r.returncode}:\n{r.stdout}\n{r.stderr}"
            )
        return r.stdout

    @staticmethod
    def run_id_of(output: str) -> str:
        m = re.search(r"run: (\S+)", output)
        if m is None:
            raise AssertionError(f"no run id in:\n{output}")
        return m.group(1)

    def record(
        self, area: Path, protocol: Path, mode: str, run_id: str | None = None
    ) -> str:
        """A decided audit record of the area as it is now: `labkit-audit`'s
        file without its model call. Returns the scope sha it saw."""
        sha = scope_sha.area_stamp(area)[0]
        findings.write(
            area,
            mode,
            "test",
            sha,
            promises.block_stamp(protocol.read_text(encoding="utf-8")),
            (0, 0, 0),
            [],
            run_id=run_id,
            shown_sha=(
                shown_sha(area, area / "runs" / run_id) if run_id is not None else None
            ),
            registration=registration_of(area),
            protocol_id=protocol_id_of(area),
        )
        return sha

    def finalize(self, area: Path) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = finalize.main([str(area)])
        return rc, out.getvalue()

    def adopt(self, protocol: Path, run_id: str) -> tuple[int, str]:
        """`protocol-fill PROTOCOL --from-run RUN_ID`, the Conclusion written
        first where it is open (`concluded`), as the author does: the
        adoption owes it. Its refusal without one: tests/test_adopt.py."""
        self.concluded(protocol)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = protocol_fill.main([str(protocol), "--from-run", run_id])
        return rc, out.getvalue()

    def adopt_forced(self, protocol: Path, run_id: str) -> tuple[int, str]:
        """`protocol-fill PROTOCOL --from-run RUN_ID --force`: (exit, what it
        printed, a refusal included), the Conclusion written first where it
        is open (`concluded`)."""
        self.concluded(protocol)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = protocol_fill.main([str(protocol), "--from-run", run_id, "--force"])
        return rc, out.getvalue()

    def stop_hook(self) -> tuple[int, str]:
        """`claude-hook stop` over everything git sees as changed."""
        err = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root)}),
            contextlib.redirect_stderr(err),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            rc = agent_hooks.stop(
                {
                    "cwd": str(self.root),
                    "session_id": "e2e",
                    "transcript_path": str(self.transcript),
                }
            )
        return rc, err.getvalue()

    def pre_commit(self, *paths: Path) -> tuple[int, str]:
        """The pre-commit's `report-check --if-reported --staged PATHS`."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = report_check.hold_reported(list(paths), self.root, staged=True).exit
        return rc, out.getvalue()


def assert_draws(
    test: unittest.TestCase, lab: "Lab", area: Path, run_id: str, key: str, other: str
) -> None:
    """`02_analyze.py --draws` on the kept run prints its criterion value
    under the measure skeleton's key (`CRITERION_VALUE_KEY`): the value metrics.json
    holds, never the other skeleton's key. The analysis skeleton is shared,
    so it must not read the model's key for every skeleton."""
    metrics = json.loads((area / "runs" / run_id / "metrics.json").read_text())
    out = lab.script(area, "02_analyze.py", "--draws")
    test.assertIn(f"draw 1  {run_id}  {key} {metrics[key]}  criterion_1_pass True", out)
    test.assertNotIn(other, out)


def stamp_count(
    lab: "Lab", deliverables: tuple[str, ...] = (), report_file: str | None = None
) -> tuple[Path, Path]:
    """The counting skeleton at low repeat cost in LAB, filled and committed:
    lines per document over three documents (1, 2, 6 lines — mean 3.0).
    With DELIVERABLES (stamped into the script) each is one row of the mean
    under the kept key (`[kept] key = "lines_mean"`, filled through
    protocol-fill); REPORT_FILE registers a report. Returns (area, protocol)."""
    root = lab.root
    docs = root / "data" / "raw" / "docs"
    docs.mkdir(parents=True)
    for name, lines in (("a.txt", 1), ("b.txt", 2), ("c.txt", 6)):
        (docs / name).write_text("x\n" * lines, encoding="utf-8")
    area, protocol = lab.exp(
        "lines",
        repeat_cost="low",
        kind="compute",
        deliverables=deliverables,
        report_file=report_file,
    )
    _replace(
        area / "scripts" / "01_measure.py",
        [
            *(
                [
                    (
                        '    raise NotImplementedError(f"deliverable_rows(): the rows of {path} from items and metrics")',
                        '    return [{"lines_mean": metrics["lines_mean"]}]',
                    )
                ]
                if deliverables
                else []
            ),
            (
                'SOURCE = REPO / "data" / "TODO"',
                'SOURCE = REPO / "data" / "raw" / "docs"\nCOUNT_FIELD = "lines"',
            ),
            (
                '    raise NotImplementedError("expected_ids(): the ids SOURCE lists")',
                "    return [p.name for p in visible(SOURCE)]",
            ),
            (
                '    raise NotImplementedError("rows(): one dict per id, fail loud on a missing one")',
                '    return [{"id": i, COUNT_FIELD: len((SOURCE / i).read_text(encoding="utf-8").splitlines())} for i in ids]',
            ),
            (
                '    raise NotImplementedError("evaluate_rows(): compute the number(s) from items")',
                '    return {"lines_mean": sum(r[COUNT_FIELD] for r in items) / len(ids)}',
            ),
        ],
    )
    fill_known_case(area, KNOWN_IDS, KNOWN_ROWS, KNOWN_METRICS)
    lab.fill(
        protocol,
        "type=exploratory",
        "kept.key=lines_mean",
        "kept.unit=lines",
        "Terms of this protocol=n/a — no coinage",
        "Question / hypothesis=How many lines does a document of data/raw/docs hold on average?",
        "Data / scope=data/raw/docs, 3 documents, read directly",
        "Exclusions / filters=hidden entries and nested directories (visible())",
        "Unit=one document of data/raw/docs",
    )
    lab.commit("the count, registered")
    return area, protocol


#: the counting areas' hand-checked case for their stamped test: two documents of 1 and 3
#: lines give a mean of 2.0
KNOWN_IDS = '["a", "b"]'
KNOWN_ROWS = '[{"id": "a", "lines": 1}, {"id": "b", "lines": 3}]'
KNOWN_METRICS = '{"lines_mean": 2.0}'


class Count(unittest.TestCase):
    """The counting skeleton at low repeat cost: lines per document, three documents."""

    run_id = ""  # the kept run, from `_adopted`
    committed = False  # `_committed`: the adopted number is in HEAD

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = stamp_count(cls.lab)
        cls.measure = cls.area / "scripts" / "01_measure.py"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def test_01_the_stamp_is_the_contracts_skeleton(self):
        sk = sc.skeleton("low", "compute", False)
        self.assertIs(sk, sc.COMPUTE)
        self.assertEqual(
            sorted(p.name for p in (self.area / "scripts").iterdir()),
            sorted(dest for _, dest in sk.scripts),
        )
        self.assertTrue((self.area / sc.CHECK_SCRIPT).is_file())

    def _adopted(self) -> str:
        """Run, finalize, record, adopt — once per class. Every later test
        rests on this state and calls it first, so each test runs alone and
        in any order, under any `--dist`."""
        cls = type(self)
        if cls.run_id:
            return cls.run_id
        lab = cls.lab
        out = lab.script(self.area, "01_measure.py")
        run_id = lab.run_id_of(out)
        cls.run_id = run_id
        self.assertIn('"lines_mean": 3.0', out)
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        # finding (4): a refused adoption leaves the protocol as it was —
        # no analysis record yet, so the release refuses
        lab.concluded(self.protocol)  # the answer written first, as owed
        before = self.protocol.read_text(encoding="utf-8")
        rc, out = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)
        self.assertEqual(self.protocol.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.area.glob(".PROTOCOL-*")), [])
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        # finding (1): recomputation ran the count's own check script
        self.assertIn("read from the proposed protocol", out)
        self.assertIn("finalized, audited, checked", out)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            f"- **Recorded results:** kept number: lines_mean = 3.0 lines (run {run_id})",
            text,
        )
        self.assertIn(f"- {run_id} — the kept run", text)
        return run_id

    def _committed(self) -> str:
        """The adopted number committed through the hooks — once per class,
        on `_adopted`; the stop hook and the pre-commit are held on the way."""
        run_id = self._adopted()
        cls = type(self)
        if cls.committed:
            return run_id
        lab = cls.lab
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)
        # nothing staged: the commit would carry no declaration, nothing is owed
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual((rc, out), (0, ""))
        # the protocol staged alone: the commit would declare the result while
        # output/ and runs/ stay outside it — the tree is not the index
        lab.git("add", str(self.protocol))
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 1, out)
        self.assertIn("the working tree differs from the index", out)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol, self.measure)
        self.assertEqual(rc, 0, out)
        self.assertIn("read from the index", out)
        lab.commit("the number, adopted")
        cls.committed = True
        return run_id

    def test_02_run_finalize_audit_adopt(self):
        self._adopted()

    def test_03_the_stop_hook_and_the_commit_hold_the_adopted_number(self):
        self._committed()

    def test_04_a_script_changed_under_the_reported_number_reopens_it(self):
        """Finding (2): the protocol untouched, the formula changed — the
        stop hook holds the area, not the protocol alone."""
        self._committed()
        lab = type(self).lab
        _replace(
            self.measure,
            [
                (
                    '    return {"lines_mean": sum(r[COUNT_FIELD] for r in items) / len(ids)}',
                    '    return {"lines_mean": sum(r[COUNT_FIELD] for r in items) / len(ids) + 1}',
                ),
            ],
        )
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 2, err)
        self.assertIn("no analysis audit saw the area as it is now", err)
        self.assertIn("02_analyze.py --check exits 1", err)
        rc, out = lab.pre_commit(self.measure)
        self.assertEqual(rc, 1, out)
        lab.git("checkout", "--", str(self.measure))
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)

    def test_05_the_commit_holds_the_index_not_the_tree(self):
        """Finding (3): the answer reopened in the tree, the index still
        citing the run — the commit would carry the declaration, so the
        pre-commit holds it; staged, the open answer owes nothing."""
        run_id = self._committed()
        lab = type(self).lab
        text = self.protocol.read_text(encoding="utf-8")
        reopened = re.sub(r'\n\[result\]\nrun = "[^"]+"\n', "", text)
        self.assertNotEqual(reopened, text)
        self.protocol.write_text(reopened, encoding="utf-8")
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 1, out)
        self.assertIn("the working tree differs from the index", out)
        self.assertIn(f"its head has adopted {run_id}", out)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("report-check", out)
        lab.git("checkout", "HEAD", "--", str(self.protocol))


def _strip_promise_placeholders(protocol: Path) -> None:
    """The stamp's `<…>` promise sentences, written as the sentences they
    propose (an agent rewords them; the checks want them without `<…>`)."""
    text = protocol.read_text(encoding="utf-8")
    text = re.sub(r'sentence = "<([^"]*)>"', r'sentence = "\1"', text)
    protocol.write_text(text, encoding="utf-8")


def _load(measure: Path, name: str):
    """The area's measure script as a module, by path, as its test does."""
    spec = importlib.util.spec_from_file_location(name, measure)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


#: the judge's sentences: one causal claim and its plain counterpart
JUDGE_GOLD = {
    "causal": "Rain causes the street to be wet.",
    "not_causal": "The street is wet.",
}


def judge_area(lab: Lab, name: str) -> tuple[Path, Path]:
    """A judge area NAME of LAB as `Judge` registers it — stamped at low
    repeat cost, its prompt filled, its protocol filled, its prepare script
    run; not committed. (area, protocol)."""
    root = lab.root
    raw = root / "data" / "raw" / "sentences.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(
        "".join(
            json.dumps(
                {"id": f"s{i}", "text": f"{i}: {JUDGE_GOLD[gold]}", "gold": gold}
            )
            + "\n"
            for i, gold in enumerate(["causal", "not_causal"] * 6)
        ),
        encoding="utf-8",
    )
    area, protocol = lab.exp(name, repeat_cost="low", kind="apply", model="haiku")
    scripts = area / "scripts"
    _replace(
        scripts / "00_prepare.py",
        [
            (
                'SOURCE = REPO / "data" / "TODO"',
                'SOURCE = REPO / "data" / "raw" / "sentences.jsonl"',
            ),
            (
                'OUT = AREA / "data" / "prepared" / "TODO_v1.jsonl"',
                'OUT = AREA / "data" / "prepared" / "sentences_v1.jsonl"',
            ),
            (
                'ABOUT = "TODO: one sentence — what one row is and what this dataset is for."',
                'ABOUT = "one sentence, labelled causal or not"',
            ),
            (
                '"gold": "TODO: every gold value spelled out, e.g. causal | not_causal",',
                '"gold": "causal | not_causal",',
            ),
        ],
    )
    measure = scripts / "01_measure.py"
    _replace(
        measure,
        [
            (
                'ITEMS = AREA / "data" / "prepared" / "TODO_v1.jsonl"',
                'ITEMS = AREA / "data" / "prepared" / "sentences_v1.jsonl"',
            ),
            (
                'ANSWERS = {"Yes": "TODO-positive-gold", "No": "TODO-negative-gold"}',
                'ANSWERS = {"Yes": "causal", "No": "not_causal"}',
            ),
            (
                'PROMPT = ("TODO: the question about this text.\\n\\n"',
                'PROMPT = ("Does the text state that one thing causes another?\\n\\n"',
            ),
            (
                'PROMPT_NULL = ("TODO: a question about this text that has nothing to do with the gold label.\\n\\n"',
                'PROMPT_NULL = ("Is this text written in English?\\n\\n"',
            ),
        ],
    )
    _strip_promise_placeholders(protocol)
    lab.fill(
        protocol,
        "type=exploratory",
        "Terms of this protocol=n/a — no coinage",
        "Question / hypothesis=Does the model read a causal claim off one sentence?",
        "Inference criterion=[criterion-1] registered accuracy at least the null lane's plus margin",
        "Quality check=[quality-check-1] at most max_empty empty answers; [quality-check-2] the null lane at chance within null_band_items",
        "Data / scope=data/prepared/sentences_v1.jsonl, 12 sentences, 00_prepare.py",
        "Data profile=6 and 6 sentences, the marker 'because' in both classes",
        "Model / tool=haiku",
        "Null condition / anchors (in the same run)=[quality-check-2] the placebo question (English?) answers Yes for every item: expected accuracy 6 of 12",
        "Exclusions / filters=none",
        "Unit=one sentence",
    )
    lab.fill(protocol, "--prompts")
    lab.script(area, "00_prepare.py")
    return area, protocol


class CountCommands(unittest.TestCase):
    """The commands an agent runs on a fresh count area (`stamp_count`):
    measure, labkit-audit with the model's answer given, --decide,
    --withdraw, the adoption. A base without tests of its own."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab)
        rel = self.area.relative_to(self.lab.root).as_posix()
        self.clean = (
            "verdict: 0 blockers, 0 warnings, 0 notes\nscope:\n"
            f"{rel}/scripts/01_measure.py"
        )

    # -- the commands, as an agent runs them
    def measure(self) -> str:
        """Run the measuring script, in a later second than every run the
        area holds: run ids carry the second, and two in one second leave
        the answering run's choice blocked (`answering_run.same_second_rival`)
        — a history no lab writes by hand. Waits for the clock, not for a
        guessed time."""
        runs = self.area / "runs"
        held = runs.iterdir() if runs.is_dir() else ()
        newest = max((d.name[: len(_SECOND)] for d in held), default="")
        while time.strftime(RUN_ID_TIME) <= newest:
            time.sleep(0.02)
        return self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))

    def records(self) -> set[Path]:
        return set((self.area / "audits").glob("*-analysis*.toml"))

    def analysis(
        self, answer: str, protocol: Path | None = None
    ) -> tuple[int, str, str]:
        """`labkit-audit AREA --mode analysis`, the model's answer ANSWER:
        (exit, output, the prompt sent); the record it wrote is `self.record`
        — by the set of records, not by name order (`…-analysis-2.toml`
        sorts before `…-analysis.toml`). PROTOCOL is named with `--protocol`,
        which an area of several protocols owes."""
        before = self.records()
        sent: list[str] = []

        def fake(alias, prompt, **kw):
            sent.append(prompt)
            return answer

        out = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", fake),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            rc = audit.main(
                [
                    str(self.area),
                    "--mode",
                    "analysis",
                    *(["--protocol", str(protocol)] if protocol else []),
                ]
            )
        written = self.records() - before
        self.record = written.pop() if len(written) == 1 else None
        return rc, out.getvalue(), sent[0] if sent else ""

    def decide(
        self,
        record: Path,
        n: int,
        status: str,
        reason: str,
        protocol: Path | None = None,
    ) -> str:
        """`labkit-audit AREA --decide N`: its output, the decision's line.
        PROTOCOL is named with `--protocol`, as the decide line is printed
        in an area of several protocols."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = audit.main(
                [
                    str(self.area),
                    "--decide",
                    str(n),
                    *decide_words(status, reason),
                    "--record",
                    str(record),
                    *(["--protocol", str(protocol)] if protocol else []),
                ]
            )
        self.assertEqual(rc, 0, out.getvalue())
        return out.getvalue()

    def withdraw(self, why: str, *more: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = protocol_fill.main(
                [str(self.protocol), "--withdraw", "--why", why, *more]
            )
        return rc, out.getvalue() + err.getvalue()

    def declared(self) -> str | None:
        return protocol_block.declared_run(self.protocol.read_text(encoding="utf-8"))

    def adopted_a(self) -> str:
        """Run A measured, finalized, audited without findings, adopted and
        committed — the state a later change starts from."""
        run_a = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)
        self.lab.commit(f"adopt {run_a}")
        return run_a

    def change_code(self) -> None:
        """The measuring code extended: each kept row also carries its size."""
        _replace(
            self.area / "scripts" / "01_measure.py",
            [
                (
                    'COUNT_FIELD: len((SOURCE / i).read_text(encoding="utf-8").splitlines())}',
                    'COUNT_FIELD: len((SOURCE / i).read_text(encoding="utf-8").splitlines()), '
                    '"bytes": (SOURCE / i).stat().st_size}',
                )
            ],
        )


class MeasuredRunsKeepTheirSecond(CountCommands):
    def test_two_measurements_back_to_back_carry_different_seconds(self):
        """The fixture's `measure` never writes two runs of one second:
        two would block the answering run's choice in the correction tests'
        hooks."""
        a, b = self.measure(), self.measure()
        self.assertNotEqual(a[: len(_SECOND)], b[: len(_SECOND)])


class FirstMeasurementLost(CountCommands):
    """A measured, never committed, its directory deleted: only the run
    index names it. The next start is not held to HEAD as a first
    measurement and says what is missing; finalize holds the number as a
    check not executable, and with the record back from a copy the
    comparison with A runs again
    (docs/notes/2026-11-18-lost-first-measurement.md)."""

    OLD = "How many lines does a document of data/raw/docs hold on average?"
    NEW = "How many lines does the longest document of data/raw/docs hold?"

    def lose_a(self) -> tuple[str, Path]:
        """Measure A and delete its directory: (its id, a copy kept
        outside the lab)."""
        run_a = self.measure()
        kept = Path(tempfile.mkdtemp()) / run_a
        self.addCleanup(shutil.rmtree, kept.parent)
        shutil.move(str(self.area / "runs" / run_a), str(kept))
        return run_a, kept

    def start_b(self, run_a: str) -> tuple[str, str]:
        """Start B in a later second than A: (its id, what the start printed)."""
        while time.strftime(RUN_ID_TIME) <= run_a[: len(_SECOND)]:
            time.sleep(0.02)
        out = self.lab.script(self.area, "01_measure.py")
        return self.lab.run_id_of(out), out

    def test_the_start_warns_and_finalize_holds_until_the_record_is_back(self):
        run_a, kept = self.lose_a()
        _replace(self.protocol, [(self.OLD, self.NEW)])
        self.lab.commit("the question, rewritten after A")
        run_b, out = self.start_b(run_a)
        self.assertIn(
            "PROTOCOL-lines.md: this run is not held to HEAD as its first measurement",
            out,
        )
        self.assertIn(f"run {run_a} is gone", out)
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn("BLOCKER (check not executable): what the number is about", out)
        self.assertIn(f"run {run_a} is gone", out)
        # the start files hold both starts, A's first: nothing is unknown
        self.assertNotIn("is unknown", out)
        self.assertNotIn("are the ones the first measurement registered", out)
        for way in ("a copy that holds it", "register anew", "--handover"):
            self.assertIn(way, out)
        # the twin: A back from the copy, and the comparison with it runs
        shutil.move(str(kept), str(self.area / "runs" / run_a))
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertNotIn("check not executable", out)
        self.assertIn(
            f"what the number is about changed after the first measurement {run_a}",
            out,
        )
        self.assertIn(f"as the answering run {run_b} saw the protocol", out)

    def test_the_twin_a_later_run_lost_is_named_and_holds_nothing(self):
        """A stands and reads; a second measurement is deleted before a
        commit. The start files put its start after A's, so the
        registration station compares as before and warns of the lost run.
        What needs the lost run's own evidence is held by its own check:
        the output file holds the lost run's rows, and the row provenance
        station (`run_record_check.row_provenance_findings`) blocks A's
        number over them."""
        run_a = self.measure()
        later = self.measure()
        shutil.rmtree(self.area / "runs" / later)
        rc, out = self.lab.finalize(self.area)
        self.assertIn("are the ones the first measurement registered", out)
        self.assertIn(f"WARNING: run {later} is gone", out)
        self.assertIn("the comparison with the first measurement runs", out)
        self.assertIn("which labkit does not check", out)
        self.assertNotIn("what the number is about cannot be compared", out)
        self.assertNotIn(f"run {run_a} is gone", out)
        self.assertEqual(rc, 1, out)
        self.assertIn(
            f"row(s) from {later} — a run this run neither is, continues nor "
            f"derives from",
            out,
        )

    def break_off(self) -> str:
        """A measurement that starts and breaks off in the measuring
        script; the script as committed again afterwards. Its id."""
        measure = self.area / "scripts" / "01_measure.py"
        ok = '    return {"lines_mean": sum(r[COUNT_FIELD] for r in items) / len(ids)}'
        _replace(measure, [(ok, '    raise RuntimeError("broke off")')])
        r = subprocess.run(
            [sys.executable, str(measure)],
            cwd=self.lab.root,
            capture_output=True,
            text=True,
            env=self.lab.env,
        )
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.lab.git("checkout", "--", str(measure))
        (broke_off,) = [d.name for d in (self.area / "runs").iterdir()]
        return broke_off

    def test_a_measurement_that_broke_off_and_was_deleted_keeps_counting(self):
        """A starts and breaks off: no index row, and its directory is
        deleted. Its start file is all that is left — through a reindex
        too. The next start says so and starts; finalize holds
        the number of the run that followed."""
        broke_off = self.break_off()
        starts = run_starts.start_path(self.area, broke_off)
        self.assertIn(f'"run_id": "{broke_off}"', starts.read_text(encoding="utf-8"))
        index = self.area / "runs.tsv"
        indexed = index.read_text(encoding="utf-8") if index.is_file() else ""
        self.assertNotIn(broke_off, indexed)
        shutil.rmtree(self.area / "runs" / broke_off)
        kept = starts.read_text(encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            runlog.reindex(self.area)
        self.assertEqual(starts.read_text(encoding="utf-8"), kept)
        _, out = self.start_b(broke_off)
        self.assertIn(
            "PROTOCOL-lines.md: this run is not held to HEAD as its first measurement",
            out,
        )
        self.assertIn(
            f"run {broke_off} is gone (its start file lists it as a measurement "
            f"that started",
            out,
        )
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn("BLOCKER (check not executable): what the number is about", out)
        self.assertIn(f"run {broke_off} is gone (its start file lists it", out)
        self.assertIn("may have been the first", out)
        self.assertNotIn("are the ones the first measurement registered", out)

    def test_a_committed_deletion_of_the_start_file_leaves_the_run_known(self):
        """A breaks off; its start file is committed, its directory never
        is. Then the directory and the start file are deleted and the
        deletion is committed. The run is still known from the commit that
        held its start file: the next start warns, finalize holds B's
        number, and the hook names the checkout that restores the file."""
        broke_off = self.break_off()
        start = run_starts.start_path(self.area, broke_off)
        self.lab.git("add", str(start))
        self.lab.git("commit", "-qm", "the start of a run that broke off")
        held = self.lab.git("rev-parse", "HEAD").strip()
        shutil.rmtree(self.area / "runs" / broke_off)
        start.unlink()
        self.lab.git("add", "-A")
        self.lab.git("commit", "-qm", "the start file, deleted")
        state = state_of(self.area)
        self.assertEqual(state.deleted_starts, {broke_off: held})
        self.assertEqual(state.started_only, {broke_off: protocol_id_of(self.area)})
        (line,) = [
            ln
            for ln in hook_post_change.index_problems(state)
            if "start file is gone" in ln
        ]
        self.assertIn(f"git checkout {held} -- ", line)
        self.assertIn(f"{broke_off}.json", line)
        _, out = self.start_b(broke_off)
        self.assertIn(
            f"run {broke_off} is gone (its start file lists it as a measurement "
            f"that started",
            out,
        )
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn("BLOCKER (check not executable): what the number is about", out)
        self.assertIn("may have been the first", out)
        # the twin: the file back from that commit, and nothing is told as deleted
        self.lab.git("checkout", held, "--", str(start))
        self.assertEqual(state_of(self.area).deleted_starts, {})

    def test_a_start_file_that_does_not_read_refuses_nothing(self):
        """A measured and adoptable; then its start file is damaged. The
        area's checks still run: finalize warns of the incomplete start,
        names no hand repair, and holds nothing for it."""
        run_a = self.measure()
        run_starts.start_path(self.area, run_a).write_text(
            "{not json", encoding="utf-8"
        )
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn(
            f"WARNING (check not executable): the start file of run {run_a} does "
            f"not read",
            out,
        )
        self.assertIn("no value is written into a start file by hand", out)
        self.assertIn("are the ones the first measurement registered", out)

    def test_a_record_of_unknown_protocol_holds_nothing_and_establishes_nothing(
        self,
    ):
        """One protocol in the area, and a record that does not read and
        that no index row names: the protocol count assigns it to nobody.
        finalize holds nothing for it, warns that its binding is unknown,
        and does not say the first measurement's registration is
        established."""
        self.measure()
        unknown = self.area / "runs" / "2026-01-01T10-00-00_0bad"
        unknown.mkdir()
        (unknown / "config.json").write_text("{not json", encoding="utf-8")
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn(
            f"WARNING (check not executable): the record of run {unknown.name} "
            f"does not read",
            out,
        )
        self.assertIn("which protocol it belongs to cannot be determined", out)
        self.assertIn("nor that none came before", out)
        self.assertIn(
            "are the ones the first measurement that reads registered — an earlier "
            "measurement is not excluded",
            out,
        )
        self.assertNotIn("the ones the first measurement registered", out)

    def test_a_later_start_is_not_held_to_head_as_the_first(self):
        """With the protocol out of HEAD a first measurement is refused as
        not committed (`test_start_gate_unread`); after a lost one the start
        check names no gap, as after one whose record reads."""
        self.lose_a()
        rel = self.protocol.relative_to(self.lab.root).as_posix()
        self.lab.git("rm", "-q", "--cached", rel)
        self.lab.git("commit", "-qm", "the protocol out of the index")
        bound = start_check.protocol_binding(self.area, self.protocol.name)
        state = state_of(self.area)
        self.assertEqual(
            start_check._freeze_findings(self.area, bound, state),  # noqa: SLF001
            [],
        )


#: what one process of `ParallelStarts` runs: wait for the common signal,
#: then start and finish its runs in the area, printing each run id
_STARTER = """
import contextlib, io, sys, time
from pathlib import Path
from labkit.run import runlog

area, go, runs_each = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
while not go.exists():
    time.sleep(0.001)
for n in range(runs_each):
    with contextlib.redirect_stdout(io.StringIO()):
        with runlog.run("x", {"n": n}, area, run_kind="preparation") as run:
            run.metrics(n=n)
    print(run.run_id)
"""


class ParallelStarts(unittest.TestCase):
    """Processes of their own, not threads on one handle, start runs in one
    area at the same moment: every run gets an id of its own and one
    start file, whole — each created in one step and never written into by
    another start (`run_starts.write_start`) —, and the run index, appended
    under its lock, lists the same runs."""

    PROCESSES = 8
    RUNS_EACH = 5
    REPETITIONS = 3

    def one_round(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        area, go = tmp / "area", tmp / "go"
        area.mkdir()
        started = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    _STARTER,
                    str(area),
                    str(go),
                    str(self.RUNS_EACH),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(self.PROCESSES)
        ]
        go.touch()
        ids: list[str] = []
        for proc in started:
            out, err = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0, err)
            ids += out.split()
        total = self.PROCESSES * self.RUNS_EACH
        self.assertEqual(len(set(ids)), total)
        # one start file per run, each whole (a torn one would not read),
        # and nothing else in their directory: no temporary file
        starts = run_starts.read_starts(area)
        self.assertEqual(sorted(starts), sorted(ids))
        files = sorted(p.name for p in (area / run_starts.START_FILES_DIR).iterdir())
        self.assertEqual(files, sorted(f"{r}.json" for r in ids))
        self.assertEqual({s.run_kind for s in starts.values()}, {"preparation"})
        self.assertEqual(sorted(run_index.indexed_bindings(area)), sorted(ids))

    def test_every_start_has_its_own_id_and_one_whole_start_file(self):
        for n in range(self.REPETITIONS):
            with self.subTest(round=n):
                self.one_round()


class LosingTheStartFile(CountCommands):
    """Does losing a start file ease a release? The same scenario twice —
    with the start file, and after deleting it while no commit holds it —
    through every check that reads the start: finalize's registration
    station, report-check, the run's start check and the post-change hook.

    Two cases, kept apart. An evidenced loss holds: something else still
    names the run — its index row, its record with the start mark —, and
    no check that held with the file passes without it. A complete loss of
    every trace is the detection limit: with the run directory and the
    only start file gone before a commit held either, labkit has no
    evidence and sees nothing; only the commit secures a start file
    (docs/notes/2026-11-18-run-start-record.md).

    For the start, "holds" means that its warning names the run: the start
    refuses nothing, and a new run starts while the number waits."""

    def checks(self, run: str) -> dict[str, bool]:
        """Per check: does it hold the protocol's number, or name RUN, now?"""
        ctx = report_context.checked(self.area, self.protocol)
        held = registration_hold.registration_changes(
            ctx.area, ctx.protocol, ctx.head.id, ctx.run, ctx.area_state, ctx.evidence
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            report_command.main([str(self.area)])
        state = state_of(self.area)
        bound = start_check.protocol_binding(self.area, self.protocol.name)
        note = start_check.earlier_measurement_note(bound, state) or ""
        return {
            "registration station": any(f.grade == "BLOCKER" for f in held),
            "report-check": "BLOCKER (check not executable): finalize: "
            in out.getvalue(),
            "start check": run in note,
            "post-change hook": any(
                run in line for line in hook_post_change.index_problems(state)
            ),
        }

    def with_and_without(self, run: str) -> tuple[dict[str, bool], dict[str, bool]]:
        """(the checks with RUN's start file, the checks after deleting it)."""
        before = self.checks(run)
        run_starts.start_path(self.area, run).unlink()
        return before, self.checks(run)

    ALL = {
        "registration station": True,
        "report-check": True,
        "start check": True,
        "post-change hook": True,
    }
    NONE = dict.fromkeys(ALL, False)

    def break_off(self) -> str:
        """A measurement that starts and breaks off; its id."""
        measure = self.area / "scripts" / "01_measure.py"
        ok = '    return {"lines_mean": sum(r[COUNT_FIELD] for r in items) / len(ids)}'
        _replace(measure, [(ok, '    raise RuntimeError("broke off")')])
        subprocess.run(
            [sys.executable, str(measure)],
            cwd=self.lab.root,
            capture_output=True,
            text=True,
            env=self.lab.env,
        )
        self.lab.git("checkout", "--", str(measure))
        (run,) = [d.name for d in (self.area / "runs").iterdir()]
        return run

    def test_the_counter_case_an_intact_start_file_holds_nothing(self):
        run = self.measure()
        self.assertEqual(self.checks(run), self.NONE)

    def test_evidenced_a_finished_run_deleted_keeps_holding(self):
        """A finished — the index lists it — and its directory was deleted;
        B measured. The index row keeps A whatever becomes of its start
        file."""
        run_a = self.measure()
        shutil.rmtree(self.area / "runs" / run_a)
        self.measure()
        self.assertEqual(self.with_and_without(run_a), (self.ALL, self.ALL))

    def test_evidenced_a_run_whose_record_names_the_start_file_holds(self):
        """A stands, and its record carries the start mark. With its start
        file nothing holds; without it the loss is evidenced, and the
        release is held."""
        run_a = self.measure()
        self.assertEqual(self.with_and_without(run_a), (self.NONE, self.ALL))

    def test_the_start_refuses_nothing_while_the_release_is_held(self):
        """A's start file is lost and the release is held. A new run of the
        same protocol still starts and completes: only the number waits."""
        run_a = self.measure()
        run_starts.start_path(self.area, run_a).unlink()
        run_b = self.measure()
        self.assertNotEqual(run_b, run_a)
        self.assertTrue((self.area / "runs" / run_b / "completion.json").is_file())
        self.assertTrue(self.checks(run_a)["registration station"])

    def test_evidenced_a_contradicting_start_file_deleted_still_holds(self):
        """A stands; its start file names another protocol, which holds the
        release. Deleting the file does not lift the hold: the record still
        names a start file, and none is found."""
        run_a = self.measure()
        path = run_starts.start_path(self.area, run_a)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["protocol_id"] = "p-0000000000000000"
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        before, after = self.with_and_without(run_a)
        self.assertEqual(before, {**self.ALL, "post-change hook": False})
        self.assertEqual(after, self.ALL)

    def test_the_limit_a_run_gone_with_its_only_start_file_is_not_seen(self):
        """A LIMIT, NOT A GUARANTEE. A broke off — no index row — and its
        directory was deleted, the start mark with it; its start file is
        its only trace, and no commit holds it. With the file every check
        holds or names A; with the file deleted too, labkit has no evidence
        of A and sees nothing. This asserts what is, so that a change is
        seen: it does not say the state is acceptable. Only a commit
        secures a start file."""
        run_a = self.break_off()
        shutil.rmtree(self.area / "runs" / run_a)
        self.measure()
        self.assertEqual(self.with_and_without(run_a), (self.ALL, self.NONE))


class Withdraw(CountCommands):
    """Replacing a declared result goes through the real commands: withdraw
    the declaration (`protocol-fill --withdraw`), audit the run that
    answers, adopt it (`--from-run`). While a run stands adopted, every
    check and the analysis audit hold that run, not the newest by name
    (`answering_run.bound_answering_run`), so a withdrawal moves the state
    and the next audit follows earlier findings up. No test here writes a
    protocol head by hand."""

    # -- the repair case
    def test_a_wrong_declaration_is_withdrawn_followed_up_and_replaced(self):
        run_a = self.adopted_a()
        self.change_code()
        run_b = self.measure()
        # finalize holds the adopted run, not the newest by name: its code
        # changed, and the withdrawal comes first
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"changed since {run_a} ran it", out)
        self.assertIn("withdraw the adoption first", out)
        self.assertIn(f"{run_a}: completed (adopted in [result]", out)
        self.assertIn(
            f"WARNING (suspected, static evidence): {run_b}: bound to this protocol "
            "and newer by name",
            out,
        )
        wrong = (
            f"BLOCKER · PROTOCOL-lines.md:1 · statement · the head has adopted run {run_a}, "
            f"which the current code no longer measures; run {run_b} answers · "
            f"the reported mean · LAB-050 Analysis audit before reporting · "
            f"declare the run the current code measured\n"
            f"verdict: 1 blockers, 0 warnings, 0 notes"
        )
        rc, out, prompt = self.analysis(wrong)
        self.assertEqual(rc, 1, out)
        # the audit reads the adopted run, so no other run is declared
        self.assertNotIn("the protocol's [result] names", prompt)
        # the ways out by cause are the auditor's (the prompt) and the guide's;
        # the decision list names where they stand and `labkit-next`
        self.assertIn("a wrong adoption", prompt)
        self.assertIn("--withdraw", prompt)
        self.assertIn("stand in `labkit-next --guide`", out)
        record = self.record
        assert record is not None
        self.decide(record, 1, "fixed", "the wrong declaration withdrawn")
        # a declaration is never replaced, --force or not: it is withdrawn
        rc, out = self.lab.adopt_forced(self.protocol, run_b)
        self.assertEqual(rc, 2, out)
        self.assertIn("an adoption is not replaced: withdraw it", out)
        self.assertEqual(self.declared(), run_a)
        rc, out = self.withdraw("the measuring code changed after the adoption")
        self.assertEqual(rc, 0, out)
        self.assertIsNone(self.declared())
        # the steps in the order of the way out — decide, audit, adopt — each a
        # command that runs (two words, not one quoted token)
        steps = [
            out.index(s)
            for s in (
                "  1. a BLOCKER that named",
                " --findings`",
                "  2. `labkit-audit ",
                " --mode analysis`",
                "  3. `labkit-adopt ",
            )
        ]
        self.assertEqual(steps, sorted(steps))
        text = self.protocol.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            rf"- {run_a} — .* · withdrawn \d{{4}}-\d{{2}}-\d{{2}}: the measuring code changed after the adoption",
        )
        # withdrawn alone, nothing is released: the fixed BLOCKER owes its
        # follow-up, which the missing analysis audit names once
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 1, out)
        self.assertEqual(
            out.count("BLOCKER: analysis audit: no analysis audit saw"), 1, out
        )
        self.assertNotIn("never followed up", out)
        rc, out, prompt = self.analysis(
            f"FIX · {record.name}#1 · resolved · the head has adopted no run now\n\n{self.clean}"
        )
        self.assertEqual(rc, 0, out)
        self.assertNotIn("the protocol's [result] names", prompt)
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), run_b)
        self.assertIn(
            " · withdrawn ", self.protocol.read_text(encoding="utf-8")
        )  # the trace stays

    # -- the usual path: change the code, measure B, audit B, adopt B
    def test_change_measure_audit_adopt_after_a_withdrawal(self):
        run_a = self.adopted_a()
        rc, out = self.withdraw("the measuring code changes: each row carries its size")
        self.assertEqual(rc, 0, out)
        self.lab.commit("withdraw")
        self.change_code()
        self.lab.commit("the measuring code extended")
        run_b = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        rc, out, prompt = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("the protocol's [result] names", prompt)
        rc, out = self.lab.adopt(self.protocol, run_b)  # no --force
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), run_b)
        self.assertNotEqual(run_a, run_b)

    def test_an_audit_made_while_another_run_was_declared_is_owed_again(self):
        """The twin of the usual path in the other order: audited while A is
        still adopted, the audit reads A; after the withdrawal it does not
        cover B, and one audit more does."""
        run_a = self.adopted_a()
        self.change_code()
        run_b = self.measure()
        rc, out, prompt = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        # while A stands adopted, the audit reads A, not B
        self.assertIn(f"runs/{run_a}", prompt)
        self.assertNotIn(f"runs/{run_b}", prompt)
        self.assertEqual(self.withdraw("code changed")[0], 0)
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 0, out)

    def test_a_first_adoption_of_the_run_audited_keeps_its_audit(self):
        """The usual order — audit, then adopt — moves no state: adopting
        the run audited needs no audit more."""
        run_a = self.measure()
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        records = self.records()
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.records(), records)

    # -- no adoption stands: the refusal does not tell to withdraw one
    def test_adopting_a_run_whose_code_changed_names_no_withdrawal(self):
        """The adoption's own check sees its proposal declare the run; with
        that run's code changed and no adoption standing, it does not tell
        the agent to "withdraw the adoption first": there is nothing to
        withdraw. The twin is the test below: a standing adoption is told to
        withdraw first."""
        run_a = self.measure()
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        self.change_code()
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"changed since {run_a}", out)
        self.assertNotIn("withdraw the adoption first", out)
        self.assertIsNone(self.declared())

    # -- after an adoption, a code change is told to withdraw first
    def test_a_code_change_after_the_adoption_is_told_to_withdraw_first(self):
        """The commit of a fix after an adoption is held (the hook holds the
        code to the declared run). Each hold names the withdrawal before its
        own way out, so the agent does not spend an audit under the old
        declaration. The
        twin: once withdrawn, the same commit passes."""
        run_a = self.adopted_a()
        self.change_code()
        measure = self.area / "scripts" / "01_measure.py"
        self.lab.git("add", str(measure))
        rc, out = self.lab.pre_commit(measure)
        self.assertEqual(rc, 1, out)
        holds = [ln for ln in out.splitlines() if ln.startswith("  BLOCKER: ")]
        self.assertGreaterEqual(len(holds), 2, out)
        for hold in holds:
            self.assertIn(". Next: withdraw the adoption first (`", hold)
        self.assertIn(f"changed since {run_a}", out)
        self.assertEqual(self.withdraw("the measuring code changes")[0], 0)
        self.lab.git("add", str(self.protocol))
        rc, out = self.lab.pre_commit(measure, self.protocol)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("withdraw the adoption first", out)

    # -- a dismissed BLOCKER owes a second auditor; a dismissed WARNING does not
    def review(self, record: Path, verdict: str) -> tuple[int, str]:
        """`labkit-audit AREA --review --record RECORD`, the model faked to
        VERDICT the one decision under review."""
        answer = (
            f"DECISION #1 · {verdict} · visible() skips dotfiles at :12\n"
            f"verdict: {int(verdict == 'upheld')} upheld, "
            f"{int(verdict == 'rejected')} rejected, 0 insufficient\n"
        )
        out = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", lambda *a, **k: answer),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            rc = audit.main([str(self.area), "--review", "--record", str(record)])
        return rc, out.getvalue()

    def test_a_false_positive_blocker_is_held_until_a_second_auditor_upholds_it(self):
        """The deciding agent's own `dismissed` does not release a blocking
        finding, its first dismissal too. The twin: a review that
        upholds it releases the adoption."""
        run_a = self.measure()
        rc, out, _ = self.analysis(
            "BLOCKER · scripts/01_measure.py:1 · statement · hidden files are counted · the mean "
            "· LAB-050 Analysis audit before reporting · skip them\n"
            "verdict: 1 blockers, 0 warnings, 0 notes"
        )
        self.assertEqual(rc, 1, out)
        record = self.record
        assert record is not None
        self.decide(record, 1, "false-positive", "visible() skips hidden files at :12")
        self.lab.fill(
            self.protocol, "Conclusion=Three documents hold 3.0 lines on average."
        )
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{record.stem} #1: `false-positive` on a BLOCKER", out)
        self.assertIn("--review", out)
        rc, out = self.review(record, "upheld")
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)

    def test_a_dismissed_warning_owes_no_review(self):
        run_a = self.measure()
        rc, out, _ = self.analysis(
            "WARNING · scripts/01_measure.py:1 · statement · hidden files might be counted · the "
            "mean · LAB-050 Analysis audit before reporting · check visible()\n"
            "verdict: 0 blockers, 1 warnings, 0 notes"
        )
        record = self.record
        assert record is not None
        self.decide(record, 1, "false-positive", "visible() skips hidden files at :12")
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)

    # -- a withdrawal releases nothing
    def test_a_withdrawal_releases_nothing(self):
        run_a = self.measure()
        rc, out = self.withdraw("nothing declared yet")
        self.assertEqual(rc, 2, out)  # nothing to withdraw
        self.assertIn("has adopted no result", out)
        rc, out, _ = self.analysis(self.clean)
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)
        # a later audit finds a fault; its BLOCKER stays open
        rc, out, _ = self.analysis(
            "BLOCKER · scripts/01_measure.py:1 · statement · hidden files are counted · the mean "
            "· LAB-050 Analysis audit before reporting · skip them\n"
            "verdict: 1 blockers, 0 warnings, 0 notes"
        )
        self.assertEqual(rc, 1, out)
        blocking = self.record
        assert blocking is not None
        audits = {
            p: p.read_bytes() for p in (self.area / "audits").rglob("*") if p.is_file()
        }
        report = self.lab.root / "REPORT.md"
        report.write_text("# Report\n", encoding="utf-8")
        out_into = io.StringIO()
        with contextlib.redirect_stdout(out_into):
            protocol_fill.main([str(self.protocol), "--into", str(report)])
        self.assertIn(run_a, report.read_text(encoding="utf-8"))
        rc, out = self.withdraw(
            "a fault found after the adoption", "--into", str(report)
        )
        self.assertEqual(rc, 0, out)
        self.assertNotIn(
            run_a, report.read_text(encoding="utf-8")
        )  # its block withdrawn
        # the withdrawal touched no audit evidence, and decided nothing
        after = {
            p: p.read_bytes() for p in (self.area / "audits").rglob("*") if p.is_file()
        }
        self.assertEqual(after, audits)
        self.assertEqual([f.status for f in findings.read(blocking).findings], ["open"])
        # and it opens no way to a result: the open BLOCKER still holds the adoption
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn("still `open`", out)
        self.assertIsNone(self.declared())


class CorrectionCommands(CountCommands):
    """The count registered with a document count the data does not hold
    (Data / scope says 4, the run reads 3), run A measured: the commands of
    a correction in place. A base without tests of its own."""

    RIGHT = "data/raw/docs, 3 documents, read directly"
    WRONG = "data/raw/docs, 4 documents, read directly"
    HELD = "what the number is about changed after the first measurement"

    def setUp(self) -> None:
        super().setUp()
        # registered with a count the data does not hold, before any run
        self.lab.fill(self.protocol, "--force", f"Data / scope={self.WRONG}")
        self.lab.commit("the count, registered with a wrong document count")
        self.run_a = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)

    def audited(self, grade: str, place: str) -> Path:
        """The analysis audit of run A with one GRADE finding at PLACE."""
        n = (1, 0) if grade == "BLOCKER" else (0, 1)
        rc, out, _ = self.analysis(
            f"{grade} · PROTOCOL-lines.md:{place} · statement · Data / scope says 4 "
            f"documents, "
            f"the run read 3 · the mean's denominator as described · LAB-050 "
            f"Analysis audit before reporting · correct the description\n"
            f"verdict: {n[0]} blockers, {n[1]} warnings, 0 notes"
        )
        self.assertEqual(rc, 1, out)
        assert self.record is not None
        return self.record

    def describe(self, value: str) -> None:
        self.lab.fill(self.protocol, "--force", f"Data / scope={value}")

    def follow_up(self, record: Path, verdict: str, why: str) -> tuple[int, str, str]:
        return self.analysis(
            f"FIX · {record.name}#1 · {verdict} · {why}\n\n{self.clean}"
        )


class CorrectedDescription(CorrectionCommands):
    """A description in the protocol's setup that the data did not hold —
    the count in Data / scope — corrected in place: the finding names the
    field as its place, is decided `fixed`, and a follow-up audit judges the
    change (the field as registered against the field now). Only that
    `resolved`, in a record of exactly this state, releases the change from
    the hold of what the number is about (`registration_hold.resolved_corrections`);
    a fresh audit without it, a verdict on another field, a text edited
    after the verdict and a place given as a line number release nothing,
    at every grade (docs/notes/2026-11-02-registered-field-repair.md). Each
    of those conditions, its release and its refusals:
    tests/test_rules_registration_hold.py. Here the route through the real
    commands; no test writes a head by hand."""

    def test_the_corrected_description_is_followed_up_and_released(self):
        blocking = self.audited("BLOCKER", "Data / scope")
        self.describe(self.RIGHT)
        self.decide(blocking, 1, "fixed", "Data / scope now says 3 documents")
        # the correction moved the state: the finding owes its follow-up,
        # which the missing analysis audit names once
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)
        self.assertEqual(
            out.count("BLOCKER: analysis audit: no analysis audit saw"), 1, out
        )
        self.assertNotIn("never followed up", out)
        rc, out, prompt = self.follow_up(
            blocking, "resolved", "Data / scope says 3 documents, as the run read"
        )
        self.assertEqual(rc, 0, out)
        # the auditor judged the change: the field as registered and as it reads now
        self.assertIn(
            f"Data / scope registered (as its first measurement {self.run_a}", prompt
        )
        self.assertIn(f"Data / scope now: {self.RIGHT}", prompt)
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn(
            f"corrected in place after the first measurement {self.run_a}: Data / scope",
            out,
        )
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 0, out)

    def test_an_unchanged_description_stays_held_through_another_audit(self):
        blocking = self.audited("BLOCKER", "Data / scope")
        self.decide(blocking, 1, "fixed", "corrected")  # but nothing changed
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn("decided `fixed` in the state audited", out)
        self.assertIn("a description in the protocol's setup, corrected in place", out)
        rc, out, _ = self.analysis(self.clean)  # the same state audited again
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn("decided `fixed` in the state audited", out)


class CorrectionThenNewRun(CorrectionCommands):
    """A description corrected in place and released for run A, then a
    fault in the measuring code repaired and run B measured under the
    corrected text. A release belongs to the run it judged: B is released
    only by a follow-up on B whose `resolved` judges the correction again,
    with the field as B saw it, as it stands and as judged all one text;
    the earlier verdict on A releases nothing for B. Another field changed
    without a release of its own holds; several fields each released pass
    (docs/notes/2026-11-02-registered-field-repair.md, "Decided 2026-11-03").
    Those conditions: tests/test_rules_registration_hold.py; here the routes
    through the commands — B released, the verdict on A held at the text B
    saw, and an adopted A withdrawn and replaced."""

    CODE_FINDING = (
        "BLOCKER · scripts/01_measure.py:1 · statement · rows() keeps a size the protocol "
        "does not name · the rows as measured · LAB-050 Analysis audit before "
        "reporting · repair the code, measure again\n"
        "verdict: 1 blockers, 0 warnings, 0 notes"
    )

    def corrected_for_a(self) -> Path:
        """Data / scope corrected for run A and released by its follow-up;
        the correction's record."""
        blocking = self.audited("BLOCKER", "Data / scope")
        self.describe(self.RIGHT)
        self.decide(blocking, 1, "fixed", "Data / scope now says 3 documents")
        rc, out, _ = self.follow_up(blocking, "resolved", "3 documents, as A read")
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        return blocking

    def code_repaired(self) -> Path:
        """A later audit of A names a code fault, the code is changed and
        the finding decided `fixed`; the code finding's record."""
        rc, out, _ = self.analysis(self.CODE_FINDING)
        self.assertEqual(rc, 1, out)
        assert self.record is not None
        code = self.record
        self.change_code()
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            rc = audit.main(
                [
                    str(self.area),
                    "--decide",
                    "1",
                    *decide_words("fixed", "rows() keeps the count alone again"),
                    "--record",
                    str(code),
                ]
            )
        self.assertEqual(rc, 0, said.getvalue())
        self.said = said.getvalue()
        return code

    def judged(self, *verdicts: tuple[Path, str]) -> tuple[int, str, str]:
        """A follow-up on the newest run with one FIX line per (record, verdict)."""
        lines = "".join(
            f"FIX · {rec.name}#1 · {v} · judged on the run as it stands\n"
            for rec, v in verdicts
        )
        return self.analysis(f"{lines}\n{self.clean}")

    def held_as_b_saw(self, run_b: str, field: str) -> str:
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        holds = [ln for ln in out.splitlines() if self.HELD in ln and "BLOCKER" in ln]
        if not holds:
            # the whole finalize output and the runs it chose among, so a
            # missing hold shows what finalize saw, not a bare StopIteration
            runs = sorted(p.name for p in (self.area / "runs").iterdir())
            self.fail(f"no hold naming {field}; runs {runs}, B {run_b}:\n{out}")
        held = holds[0]
        self.assertIn(f"as the answering run {run_b} saw the protocol", held)
        self.assertIn(f"{field} ", held)
        return held

    def test_a_followup_on_the_new_run_that_judges_the_correction_releases_it(
        self,
    ):
        correction = self.corrected_for_a()
        code = self.code_repaired()
        run_b = self.measure()
        rc, out, prompt = self.judged((code, "resolved"), (correction, "resolved"))
        self.assertEqual(rc, 0, out)
        self.assertIn(f"{correction.name}#1", prompt)  # shown for B
        self.assertIn(f"Data / scope now: {self.RIGHT}", prompt)
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn(
            f"corrected in place after the first measurement {self.run_a}: Data / scope",
            out,
        )
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 0, out)

    def test_the_verdict_on_the_earlier_run_alone_releases_the_new_one_not(self):
        correction = self.corrected_for_a()
        code = self.code_repaired()
        run_b = self.measure()
        rc, out, prompt = self.judged((code, "resolved"))
        self.assertIn(f"{correction.name}#1", prompt)  # shown, not judged
        held = self.held_as_b_saw(run_b, "Data / scope")
        # the way out is the follow-up on B that judges the correction again
        self.assertIn(f"the follow-up analysis audit on {run_b}", held)
        self.assertIn(f"{correction.name}#1", held)
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 1, out)

    def test_an_adopted_corrected_run_is_withdrawn_measured_again_and_replaced(self):
        correction = self.corrected_for_a()
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 0, out)
        self.lab.commit(f"adopt {self.run_a}")
        code = self.code_repaired()
        run_b = self.measure()
        rc, out = self.lab.adopt_forced(self.protocol, run_b)  # not withdrawn
        self.assertNotEqual(rc, 0, out)
        self.assertIn("an adoption is not replaced: withdraw it", out)
        rc, out = self.withdraw("run A dropped no row but kept a size")
        self.assertEqual(rc, 0, out)
        rc, out, _ = self.judged((code, "resolved"), (correction, "resolved"))
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), run_b)


class DataCounts(unittest.TestCase):
    """The counts of Data / scope come from the preparation run, through the
    real commands: the stamped 00_prepare.py records them, `protocol-fill
    --data-counts` writes them as the field's end, finalize holds that part
    to the run, so no count is typed that the data does not hold. A count
    typed over the written part is held: tests/test_data_counts.py (the
    condition) and tests/test_finalize_steps.py, DataCountsStation (finalize
    forwards it)."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = points_area(self.lab, "low", "fit")
        self.out = self.lab.script(self.area, "00_prepare.py")

    def data_scope(self) -> str:
        from labkit.formats.protocol_check import fields

        text = self.protocol.read_text(encoding="utf-8")
        return next(f.value for f in fields(text) if f.name == "data / scope")

    def counts(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = protocol_fill.main([str(self.protocol), "--data-counts", *args])
        return rc, out.getvalue()

    def finalized(self) -> tuple[int, str]:
        return self.lab.finalize(self.area)

    def test_the_prepare_run_records_and_the_field_carries_its_counts(self):
        self.assertIn("12 labelled", self.out)
        prepared = next(
            r
            for r in sorted((self.area / "runs").iterdir())
            if json.loads((r / "config.json").read_text())["run_kind"] == "preparation"
        )
        metrics = json.loads((prepared / "metrics.json").read_text())
        self.assertEqual(
            {
                k: metrics[k]
                for k in ("n_items", "n_labelled", "n_unlabelled", "gold_counts")
            },
            {
                "n_items": 16,
                "n_labelled": 12,
                "n_unlabelled": 4,
                "gold_counts": {"neg": 6, "pos": 6},
            },
        )
        self.lab.fill(
            self.protocol, "Data / scope=data/raw/points.jsonl by 00_prepare.py"
        )
        rc, out = self.counts()
        self.assertEqual(rc, 0, out)
        value = self.data_scope()
        self.assertTrue(
            value.startswith(
                "data/raw/points.jsonl by 00_prepare.py · counts (prepare run "
            ),
            value,
        )
        self.assertIn(
            "points.jsonl 16 lines; 16 items prepared — 12 labelled (neg 6, pos 6), 4 unlabelled",
            value,
        )
        rc, out = self.counts()  # again: replaced in place, not appended
        self.assertEqual(self.data_scope(), value)
        rc, out = self.finalized()
        self.assertNotIn("the counts differ", out)
        self.assertNotIn("names prepare run", out)

    def test_no_preparation_run_is_refused(self):
        other = Lab()
        self.addCleanup(other.close)
        area, protocol = stamp_count(other)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = protocol_fill.main([str(protocol), "--data-counts"])
        self.assertEqual(rc, 2, out.getvalue())
        self.assertIn("no completed preparation run", out.getvalue())


class Judge(unittest.TestCase):
    """The prompt skeleton at low repeat cost, the model faked: twelve texts, a
    registered question the text answers, a placebo for the null lane."""

    run_id = ""  # the kept run, adopted and committed by `_adopted`

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = judge_area(cls.lab, "judge")
        cls.measure = cls.area / "scripts" / "01_measure.py"
        cls.lab.commit("the judge, registered")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    @staticmethod
    def _model(alias: str, prompts: list[str], *, workers: int) -> list[str]:
        """The faked model: reads the causal claim off the text; answers the
        placebo with Yes for every item (null accuracy = the causal share)."""
        out = []
        for p in prompts:
            if p.startswith("Is this text written in English?"):
                out.append("Yes")
            else:
                out.append("Yes" if "Rain causes" in p else "No")
        return out

    def test_01_the_stamp_is_the_contracts_skeleton(self):
        self.assertIs(sc.skeleton("low", "apply", True), sc.MODEL)
        self.assertEqual(
            sorted(p.name for p in (self.area / "scripts").iterdir()),
            sorted(dest for _, dest in sc.MODEL.scripts),
        )

    def _measured(self) -> str:
        """The measuring script run in full with the faked model: what it
        printed, the run id in it (`Lab.run_id_of`)."""
        from labkit.run import llm

        out = io.StringIO()
        with (
            mock.patch.object(llm, "complete_many", self._model),
            mock.patch.object(
                llm,
                "provenance",
                lambda alias: {"model": "fake@e2e", "endpoint": "fake"},
            ),
            mock.patch.object(sys, "argv", [str(self.measure)]),
            mock.patch.dict(
                os.environ, {"CLAUDE_PROJECT_DIR": str(type(self).lab.root)}
            ),
            contextlib.redirect_stdout(out),
        ):
            _load(self.measure, "e2e_judge_measure").main()
        return out.getvalue()

    def _adopted(self) -> str:
        """Run, finalize, record, adopt, commit — once per class; every later
        test calls it first and so runs alone and in any order: after the
        test the lab returns to that commit (`_back_to_adopted`)."""
        cls = type(self)
        self.addCleanup(self._back_to_adopted)
        if cls.run_id:
            return cls.run_id
        lab = cls.lab
        listed = io.StringIO()
        with contextlib.redirect_stdout(listed):
            self.assertEqual(protocol_fill.main([str(self.protocol), "--list"]), 0)
        before, _, after = listed.getvalue().partition("after the run — yours")
        self.assertNotIn("Raw output", before)  # not owed before the run
        self.assertIn("Raw output", after)
        measured = self._measured()
        run_id = lab.run_id_of(measured)
        cls.run_id = run_id
        self.assertRegex(measured, r"criterion_1_pass +True")
        rc, out_text = lab.finalize(self.area)
        self.assertEqual(rc, 0, out_text)
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out_text = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out_text)
        self.assertIn("finalized, audited, checked", out_text)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            "- **Recorded results:** criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: ",
            text,
        )
        self.assertIn(f"(run {run_id})", text)
        assert_draws(
            self, lab, self.area, run_id, "criterion_1_accuracy", "criterion_1_score"
        )
        yours = out_text.partition("still yours")[2]
        self.assertIn("output/", yours)  # the run's rows, where the pair is read
        self.assertIn("Raw output", yours)
        lab.fill(self.protocol, "Raw output=one pair per finding, from the run")
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)
        lab.git("add", "-A")
        rc, out_text = lab.pre_commit(self.protocol, self.measure)
        self.assertEqual(rc, 0, out_text)
        lab.commit("the verdict, adopted")
        return run_id

    def _back_to_adopted(self) -> None:
        """The lab as the adoption committed it: the records, decisions and
        protocol edits a test leaves would otherwise reach the next test (an
        accepted limit's line with its record decided otherwise since)."""
        lab = type(self).lab
        lab.git("reset", "-q", "--hard")
        lab.git("clean", "-fdq")

    def test_02_run_finalize_audit_adopt(self):
        self._adopted()

    def test_03_seconds_refuses_the_templates_separate_probe(self):
        result = subprocess.run(
            [sys.executable, str(self.measure), "--probe", "2"],
            cwd=type(self).lab.root,
            capture_output=True,
            text=True,
            env=type(self).lab.env,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--probe is not available at repeat_cost='low'", result.stderr)

    def _blocker(self) -> Path:
        """A second analysis record of the kept run, holding one BLOCKER."""
        self._adopted()
        return findings.write(
            self.area,
            sc.ANALYSIS_AUDIT,
            "test",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(self.protocol.read_text(encoding="utf-8")),
            (1, 0, 0),
            [("BLOCKER", "BLOCKER · scripts/01_measure.py:1 · statement · LAB-015 Preflight audit before freezing · the prompt asks more than the gold scores")],
            run_id=self.run_id,
            shown_sha=shown_sha(self.area, self.area / "runs" / self.run_id), registration=registration_of(self.area), protocol_id=protocol_id_of(self.area),)  # fmt: skip

    def _decide(self, record: Path, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = audit.main(
                [
                    str(self.area),
                    "--decide",
                    "1",
                    *decide_words(*argv),
                    "--record",
                    str(record),
                ]
            )
        return rc, out.getvalue()

    def _report_check(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = report_command.main([str(self.area)])
        return rc, out.getvalue()

    def _review(self, record: Path, verdict: str = "upheld") -> tuple[int, str]:
        """The decision review, its model faked to VERDICT the one decision."""
        answer = (
            f"DECISION #1 · {verdict} · the Conclusion claims no more\n"
            f"verdict: {int(verdict == 'upheld')} upheld, "
            f"{int(verdict == 'rejected')} rejected, "
            f"{int(verdict == 'insufficient')} insufficient\n"
        )
        out = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", lambda *a, **k: answer),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            rc = audit.main([str(self.area), "--review", "--record", str(record)])
        return rc, out.getvalue()

    def test_04_an_accepted_blocker_reaches_the_protocol_as_its_limit(self):
        """An accepted BLOCKER may carry a
        number read within it, but an instrument unfit for criterion-1 leaves criterion-1
        unjudged — the decision says which, the protocol carries it as a
        Limitation line, report-check holds the two together."""
        self._adopted()
        lab = type(self).lab
        record = self._blocker()
        label = f"Limitation (audit {record.stem} #1)"
        reason = "real: the prompt says states or implies, the gold codes juxtaposition not causal"
        rc, out = self._decide(
            record, "limitation", reason, "--not-assessable", "criterion-9"
        )
        self.assertEqual(rc, 2, out)  # an id the protocol does not register
        self.assertIn("criterion-9", out)
        rc, out = self._decide(
            record, "limitation", reason, "--not-assessable", "criterion-1"
        )
        self.assertEqual(rc, 0, out)
        self.assertEqual(
            findings.read(record).findings[0].effect, "criterion-1 not assessable"
        )
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)  # the record says so, the protocol not yet
        self.assertIn(label, out)
        # the effect releases the BLOCKER: a second auditor confirms that the
        # fault prevents judging criterion-1, before the adoption
        self.assertIn("no decision review upholds that the fault prevents", out)
        rc, out = self._review(record)
        self.assertEqual(rc, 0, out)
        rc, out = lab.adopt_forced(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            f"- **{label}:** criterion-1 not assessable with this run — {reason}", text
        )
        # the verdict the Recorded results state: the criterion unjudged, no pass
        self.assertIn(
            f"- **Recorded results:** criterion-1 not assessable ({label})", text
        )
        self.assertIn(
            "criterion_1_accuracy = 1.0", text
        )  # the measurement stays reported
        rc, out = self._report_check()
        self.assertEqual(rc, 0, out)
        # a limit line taken out by hand is missed
        self.protocol.write_text(
            "\n".join(ln for ln in text.split("\n") if not ln.startswith(f"- **{label}"))
            , encoding="utf-8",
        )  # fmt: skip
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn(label, out)
        # the twin: the verdicts stand, the limit named beside them — and a
        # BLOCKER's `stands` owes a decision review before the number leaves
        rc, out = self._decide(record, "limitation", reason)
        self.assertEqual(rc, 0, out)
        rc, out = lab.adopt_forced(self.protocol, self.run_id)
        self.assertEqual(rc, 1, out)
        self.assertIn("`stands` on a BLOCKER decided limitation not reviewed", out)
        # the review judges the claim, the Conclusion — written already, since
        # the adoption owes it; here worded to the limit before the review
        lab.fill(
            self.protocol,
            "--force",
            "Conclusion=criterion-1 is met as one draw on twelve items; nothing more is claimed.",
        )
        rc, out = self._review(record)
        self.assertEqual(rc, 0, out)
        rc, out = lab.adopt_forced(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            f"- **{label}:** the verdicts stand, read within this limit — ", text
        )
        self.assertNotIn("not assessable with this run", text)
        self.assertIn(
            "; subject to 1 recorded limitation (the Limitation lines below)", text
        )
        rc, out = self._report_check()
        self.assertEqual(rc, 0, out)
        # fixed after all: no effect owed, and the line is the record's no longer
        rc, out = self._decide(record, "fixed", "")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("effect", record.read_text(encoding="utf-8"))
        # but `fixed` in the state audited: no follow-up has seen a repair, the
        # code is the audited code — report-check holds it; the twin, the
        # finding dismissed as not applying to this state, passes once a
        # second auditor upholds the dismissal (a dismissed BLOCKER owes a
        # review)
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("decided `fixed` in the state audited", out)
        rc, out = self._decide(
            record,
            "false-positive",
            "the gold codes the prompt's three cases after all",
        )
        self.assertEqual(rc, 0, out)
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("`false-positive` on a BLOCKER not reviewed", out)
        rc, out = self._review(record)
        self.assertEqual(rc, 0, out)

    def test_05_an_accepted_warning_that_names_its_effect_reaches_the_result(self):
        """A cue that limits how the number reads may be a WARNING,
        accepted, under an Answer of `criterion_1_pass = True` alone. A
        WARNING may name its effect; named, it reaches the result."""
        self._adopted()
        lab = type(self).lab
        record = findings.write(
            self.area,
            sc.ANALYSIS_AUDIT,
            "test",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(self.protocol.read_text(encoding="utf-8")),
            (0, 1, 0),
            [("WARNING", "WARNING · data/raw:1 · statement · LAB-015 Preflight audit before freezing · six connectives separate the classes")],
            run_id=self.run_id,
            shown_sha=shown_sha(self.area, self.area / "runs" / self.run_id), registration=registration_of(self.area), protocol_id=protocol_id_of(self.area),)  # fmt: skip
        label = f"Limitation (audit {record.stem} #1)"
        reason = "criterion-1 reached on these items; a keyword rule scores 12/12, so no causal understanding is shown"
        rc, out = self._decide(record, "limitation", reason)
        self.assertEqual(rc, 0, out)
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)  # named, the effect is owed in the result
        self.assertIn(label, out)
        rc, out = lab.adopt_forced(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            f"- **{label}:** the verdicts stand, read within this limit — {reason}",
            text,
        )
        self.assertIn(
            f"(run {self.run_id}); subject to 1 recorded limitation",
            text,
        )
        rc, out = self._report_check()
        self.assertEqual(rc, 0, out)
        # decided again as a false positive it is no limit — and the result
        # section must say so again: the rendering is exact, a Limit
        # line and a note the records no longer decide are blockers until
        # written back
        rc, out = self._decide(
            record, "false-positive", "data/raw:1 holds no connective at all"
        )
        self.assertEqual(rc, 0, out)
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("no covering record decides", out)
        rc, out = lab.adopt_forced(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertNotIn(label, text)
        self.assertNotIn("recorded limitation", text)
        rc, out = self._report_check()
        self.assertEqual(rc, 0, out)

    def test_06_a_declared_run_id_must_name_a_run_of_the_area(self):
        """The declaration is `[result] run`: an id typed there that does
        not read blocks where it stands, and one of the run-id shape must be
        a run of the area."""
        self._adopted()
        lab = type(self).lab
        text = self.protocol.read_text(encoding="utf-8")
        self.addCleanup(self.protocol.write_text, text, encoding="utf-8")
        for typed, says in (
            ("2026-10-21T12-48-00_final", "no run id runlog writes"),
            ("2026-10-21T12-48-00_a1b2", "no runs/2026-10-21T12-48-00_a1b2/"),
        ):
            with self.subTest(typed=typed):
                self.protocol.write_text(
                    text.replace(self.run_id, typed), encoding="utf-8"
                )
                rc, err = lab.stop_hook()
                self.assertNotEqual(rc, 0, err)  # declared, so held — not skipped
                rc, out = self._report_check()
                self.assertEqual(rc, 1, out)
                self.assertIn(says, out)
        self.protocol.write_text(text, encoding="utf-8")
        rc, out = self._report_check()
        self.assertEqual(rc, 0, out)  # the twin: the declared run exists


class AdoptedRunWithoutIntentKeys(unittest.TestCase):
    """An adopted run whose metrics report no intent key is no answer
    (`AnsweringRun.explain`); its way out, taken step by step on the judge
    area. What it shows is the order of the commands: the audit step is a
    decided record written in its place (`Lab.record`), not a run of
    `labkit-audit`, and the starting state is built, not reached by a
    command. A lab of its own: the scenario withdraws the adoption `Judge`'s
    tests share. It borrows `Judge`'s faked model, measurement and adoption,
    which read `lab`, `area`, `protocol`, `measure` and `run_id` off the
    class — set here as `Judge.setUpClass` sets them."""

    run_id = ""
    _model = staticmethod(Judge._model)
    _measured = Judge._measured
    _adopted = Judge._adopted
    _back_to_adopted = Judge._back_to_adopted

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = judge_area(cls.lab, "judge")
        cls.measure = cls.area / "scripts" / "01_measure.py"
        cls.lab.commit("the judge, registered")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def _measured_later(self, earlier: str) -> str:
        """A full run in a later second than the run EARLIER: its id. Run
        ids carry the second, and two bound runs of one second leave the
        answering run's choice blocked (`answering_run.same_second_rival`)."""
        while time.strftime(RUN_ID_TIME) <= earlier[: len(_SECOND)]:
            time.sleep(0.02)
        return self.lab.run_id_of(self._measured())

    def test_the_way_out_lifts_the_hold_and_a_full_run_alone_does_not(self):
        """The steps the hold prints, taken in the order it prints them —
        withdraw, measure, audit, adopt —, and finalize passes; the full run
        taken alone leaves the hold, since the adoption decides.
        The state is built by cutting the intent keys out of the adopted
        run's metrics: the adoption refuses such a run, so no command leads
        there."""
        lab = self.lab
        run_a = self._adopted()
        metrics = runs.metrics_path(runs.run_path(self.area, run_a))
        kept = {
            k: v
            for k, v in runs.read_metrics(metrics).items()
            if not promises.reported_ids({k: v})
        }
        metrics.write_text(json.dumps(kept), encoding="utf-8")
        # committed, so the cut record is the history's and no gate holds
        # the run for a record changed since HEAD
        lab.commit("the adopted run's metrics without intent keys")
        hold = (
            f"{run_a} is the adopted run ([result] run), and it reports no intent key"
        )
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(hold, out)
        # the printed way out: these four steps, in this order
        way_out = out.partition(hold)[2].splitlines()[0]
        steps = (
            "withdraw the adoption (`protocol-fill",
            "measure in full: `",
            "audit that run",
            "then adopt it",
        )
        at = [way_out.find(step) for step in steps]
        self.assertNotIn(-1, at, way_out)
        self.assertEqual(at, sorted(at), way_out)
        # the step the way out puts second, taken alone: the hold stays
        run_b = self._measured_later(run_a)
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(hold, out)
        # the four steps as printed
        told = io.StringIO()
        with contextlib.redirect_stdout(told), contextlib.redirect_stderr(told):
            rc = protocol_fill.main(
                [str(self.protocol), "--withdraw", "--why", "it reports no intent key"]
            )
        self.assertEqual(rc, 0, told.getvalue())
        run_c = self._measured_later(run_b)
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_c)
        rc, out = lab.adopt(self.protocol, run_c)  # no --force
        self.assertEqual(rc, 0, out)
        self.assertEqual(
            protocol_block.declared_run(self.protocol.read_text(encoding="utf-8")),
            run_c,
        )
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)


def points_area(lab: "Lab", repeat_cost: str, kind: str) -> tuple[Path, Path]:
    """A stamped estimator area in LAB over sixteen points — twelve labelled
    (pos 6, neg 6), four unlabelled — its 00_prepare.py filled to read them.
    Returns (area, protocol)."""
    raw = lab.root / "data" / "raw" / "points.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(16):
        gold = "pos" if i % 2 == 0 else "neg"
        x = 1.0 + i if gold == "pos" else -1.0 - i
        rows.append(
            {
                "id": f"p{i}",
                "text": f"point {i}",
                "gold": gold if i < 12 else None,
                "features": [x, 0.5],
            }
        )
    raw.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    area, protocol = lab.exp("threshold", repeat_cost=repeat_cost, kind=kind)
    _replace(
        area / "scripts" / "00_prepare.py",
        [
            (
                'SOURCE = REPO / "data" / "TODO"',
                'SOURCE = REPO / "data" / "raw" / "points.jsonl"',
            ),
            (
                'OUT = AREA / "data" / "prepared" / "TODO_v1.jsonl"',
                'OUT = AREA / "data" / "prepared" / "points_v1.jsonl"',
            ),
            (
                'ABOUT = "TODO: one sentence — what one row is and what this dataset is for."',
                'ABOUT = "one point with its features; gold null on the test split"',
            ),
            (
                '"gold": "TODO: every gold value spelled out, e.g. causal | not_causal",',
                '"gold": "pos | neg | null (test split)",\n    "features": "two floats",',
            ),
        ],
    )
    return area, protocol


class Estimator(unittest.TestCase):
    """The estimator skeleton at high repeat cost, through the freeze: a threshold on
    one feature, which the gold follows; the null lane permuted."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = points_area(cls.lab, "high", "fit")
        scripts = cls.area / "scripts"
        cls.measure = scripts / "01_measure.py"
        _replace(
            cls.measure,
            [
                (
                    'ITEMS = AREA / "data" / "prepared" / "TODO_v1.jsonl"',
                    'ITEMS = AREA / "data" / "prepared" / "points_v1.jsonl"',
                ),
                (
                    'ESTIMATOR = "TODO: e.g. RandomForestClassifier(n_estimators=500, random_state=seed)"',
                    'ESTIMATOR = "NearestNeighbour(feature 0)"',
                ),
                (
                    '    raise NotImplementedError(f"make_estimator(): {ESTIMATOR}")',
                    "    return NearestNeighbour()\n\n\n"
                    "class NearestNeighbour:\n"
                    '    """The label of the nearest fitted point on feature 0."""\n\n'
                    "    def fit(self, X, y):\n"
                    "        self.points = [(x[0], g) for x, g in zip(X, y)]\n"
                    "        return self\n\n"
                    "    def predict(self, X):\n"
                    "        return [min(self.points, key=lambda p: abs(p[0] - x[0]))[1] for x in X]",
                ),
            ],
        )
        _strip_promise_placeholders(cls.protocol)
        # the null band, derived for twelve items with the labels permuted
        _replace(
            cls.protocol,
            [("constants = { null_band = 0.1 }", "constants = { null_band = 0.25 }")],
        )
        cls.lab.fill(cls.protocol, "type=exploratory")
        cls.lab.fill_open(
            cls.protocol,
            **{
                "Terms of this protocol": "n/a — no coinage",
                "Question / hypothesis": "Does a threshold on feature 0 predict the label out of fold?",
                "Inference criterion": "[criterion-1] registered accuracy at least the null lane's plus margin",
                "Quality check": "[quality-check-1] at most max_empty items without a prediction; [quality-check-2] the null lane within null_band of chance",
                "Split touched": "train",
                "Timebox": "1h",
                "Data / scope": "data/prepared/points_v1.jsonl, 12 labelled and 4 test points, 00_prepare.py",
                "Exclusions / filters": "none",
                "Unit": "one point",
            },
        )
        cls.lab.script(cls.area, "00_prepare.py")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def test_01_the_stamp_is_the_contracts_skeleton(self):
        self.assertIs(sc.skeleton("high", "fit", False), sc.ESTIMATOR)
        self.assertEqual(
            sorted(p.name for p in (self.area / "scripts").iterdir()),
            sorted(dest for _, dest in sc.ESTIMATOR.scripts),
        )

    def test_02_probe_preflight_freeze_run_adopt(self):
        lab = type(self).lab
        out = lab.script(self.area, "01_measure.py", "--probe", "8")
        self.assertIn("probe: registered", out)
        lab.commit("the estimator, filled")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = preflight.main([str(self.area)])
        self.assertEqual(rc, 0, buf.getvalue())
        # the preflight audit, decided; the † fields (stamped with the full
        # form) filled; the freeze through its one writer, which names the
        # record and sets the flag once the proposed head passes the gate
        lab.record(self.area, self.protocol, sc.PREFLIGHT_AUDIT)
        (record,) = (self.area / "audits").glob("*-preflight.toml")
        lab.exp("threshold", repeat_cost="high", report=True)  # nothing to add
        lab.fill_open(self.protocol)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = protocol_fill.main([str(self.protocol), "--freeze"])
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn(f'preflight_audit = "{record.name}"', buf.getvalue())
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn("frozen = true", text)
        self.assertIn(f'preflight_audit = "{record.name}"', text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = preflight.main([str(self.area)])
        self.assertEqual(rc, 0, buf.getvalue())
        lab.commit("frozen")
        # the full run: detached (LABKIT_DETACHED=1 in the lab's env)
        out = lab.script(self.area, "01_measure.py")
        run_id = lab.run_id_of(out)
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        # no model: Raw output is not owed, and the stamp left it out
        self.assertNotIn("**Raw output", self.protocol.read_text(encoding="utf-8"))
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        self.assertIn("frozen, finalized, audited, checked", out)
        self.assertNotIn("Raw output", out)  # filled already: not named again
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            "- **Recorded results:** criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: ",
            text,
        )
        self.assertIn(f"(run {run_id})", text)
        self.assertEqual(protocol_block.declared_run(text), run_id)
        assert_draws(
            self, lab, self.area, run_id, "criterion_1_score", "criterion_1_accuracy"
        )
        self._a_repeat_draws_a_derived_seed_and_never_answers(run_id)
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol, self.measure)
        self.assertEqual(rc, 0, out)
        self.assertIn("read from the index", out)
        lab.commit("the verdict, adopted")
        self._the_class_counts_reach_the_report_block_and_are_held()

    def _a_repeat_draws_a_derived_seed_and_never_answers(self, run_id: str) -> None:
        """`01_measure.py --repeat-of`: the kept run
        drawn again with the seed labkit derives — a run of its own, never
        the answer; `--draws` shows it and the declared run still answers.
        A seed of the script's own beside it is refused."""
        lab = type(self).lab
        with self.assertRaises(AssertionError) as cm:
            lab.script(self.area, "01_measure.py", "--repeat-of", run_id, "--seed", "3")
        self.assertIn("drop --seed", str(cm.exception))
        out = lab.script(self.area, "01_measure.py", "--repeat-of", run_id)
        repeat = lab.run_id_of(out)
        self.assertIn(f"draw 2 of {run_id}", out)
        recorded = json.loads(
            (self.area / "runs" / repeat / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual((recorded["repeat_of"], recorded["draw"]), (run_id, 2))
        self.assertEqual(
            recorded["config"]["seed"], answering_run.repeat_seed(run_id, 2)
        )
        # measured with the recorded seed: every row of the draw's own file
        # carries it (a script that kept the parent's seed would show a spread
        # of 0)
        (draw_file,) = (self.area / "output").glob("*_draw2.jsonl")
        rows = [
            json.loads(x) for x in draw_file.read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(rows)
        self.assertEqual(
            {r["_instrument"]["seed"] for r in rows},
            {answering_run.repeat_seed(run_id, 2)},
        )
        out = lab.script(self.area, "02_analyze.py", "--draws")
        self.assertIn(f"draw 2  {repeat}  criterion_1_score", out)
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        pid = protocol_block.head(self.protocol.read_text(encoding="utf-8")).id
        assert pid is not None
        chosen = state_of(self.area).measured_of(pid).answering(None).run_dir
        self.assertEqual(chosen.name if chosen else None, run_id)  # still the answer

    def _the_class_counts_reach_the_report_block_and_are_held(self) -> None:
        """The input numbers come from the run: the scored rows' class counts
        stand in Recorded results and in the report's block, and a block
        whose count is typed over is held at the commit (twin: as written,
        it passes). The audit record is the artificial one of `Lab.record`."""
        lab = type(self).lab
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn("scored_class_counts = {'neg': 6, 'pos': 6}", text)
        report = lab.root / "REPORT.md"
        report.write_text("# Threshold\n\nThe result:\n\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = protocol_fill.main([str(self.protocol), "--into", str(report)])
        self.assertEqual(rc, 0, out.getvalue())
        written = report.read_text(encoding="utf-8")
        self.assertIn("scored_class_counts = {'neg': 6, 'pos': 6}", written)
        lab.git("add", "REPORT.md")
        rc, out = lab.pre_commit(report)
        self.assertEqual(rc, 0, out)
        report.write_text(written.replace("'neg': 6", "'neg': 7"), encoding="utf-8")
        lab.git("add", "REPORT.md")
        rc, out = lab.pre_commit(report)
        self.assertEqual(rc, 1, out)
        self.assertIn("REPORT.md: line 5: the result block of", out)
        self.assertIn("differs from the protocol's rendering", out)
        report.write_text(written, encoding="utf-8")
        lab.git("add", "REPORT.md")


class StatedBar(unittest.TestCase):
    """A bar the task states, end to end at low repeat cost: "accuracy at
    least 0.90" registered as `at_least`, an unchanged predictor right on
    10 of the 12 labelled points. Written as a margin over the null, such a
    bar would adopt a false pass; here the run records the registered bar,
    and the adoption renders the miss
    (docs/notes/2026-11-02-absolute-task-bar.md)."""

    def test_the_registered_bar_reaches_the_run_and_the_result(self):
        lab = Lab()
        self.addCleanup(lab.close)
        area, protocol = points_area(lab, "low", "apply")
        _replace(
            area / "scripts" / "01_measure.py",
            [
                (
                    'ITEMS = AREA / "data" / "prepared" / "TODO_v1.jsonl"',
                    'ITEMS = AREA / "data" / "prepared" / "points_v1.jsonl"',
                ),
                (
                    'ESTIMATOR = "TODO: e.g. RandomForestClassifier(n_estimators=500, random_state=seed)"',
                    'ESTIMATOR = "FixedThreshold(feature 0 > 4)"',
                ),
                (
                    '    raise NotImplementedError(f"make_estimator(): {ESTIMATOR}")',
                    "    return FixedThreshold()\n\n\n"
                    "class FixedThreshold:\n"
                    '    """pos above 4 on feature 0, never fitted."""\n\n'
                    "    def predict(self, X):\n"
                    '        return ["pos" if x[0] > 4 else "neg" for x in X]',
                ),
            ],
        )
        _replace(
            protocol,
            [("constants = { margin = 0.25 }", "constants = { at_least = 0.9 }")],
        )
        lab.fill(
            protocol,
            "type=exploratory",
            "criterion-1 sentence=registered accuracy is at least at_least = 0.90, "
            "the bar the task text states",
            "quality-check-1 sentence=at most max_empty labelled items without a prediction",
            "quality-check-2 sentence=the permuted-label lane within the permitted deviation of the "
            "permutation expectation, computed in each run by the rule null_band_quantile over "
            "null_permutations seeded by null_band_seed",
        )
        lab.fill_open(
            protocol,
            **{
                "Terms of this protocol": "n/a — no coinage",
                "Question / hypothesis": "Does the fixed threshold reach the accuracy the task asks for?",
                "Inference criterion": "[criterion-1] registered accuracy at least 0.90, the task's bar",
                "Quality check": "[quality-check-1] at most max_empty items without a prediction; "
                "[quality-check-2] the null lane within the permitted deviation of the permutation expectation",
                "Data / scope": "data/prepared/points_v1.jsonl, 12 labelled and 4 test points",
                "Exclusions / filters": "none",
                "Unit": "one point",
            },
        )
        lab.script(area, "00_prepare.py")
        lab.commit("registered: the task's bar as at_least")
        run_id = lab.run_id_of(lab.script(area, "01_measure.py"))
        metrics = json.loads(
            (area / "runs" / run_id / "metrics.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            (
                metrics["criterion_1_score"],
                metrics["criterion_1_threshold"],
                metrics["criterion_1_pass"],
                metrics["quality_check_2_pass"],
            ),
            (10 / 12, 0.9, False, True),
        )
        lab.commit("the run")
        rc, out = lab.finalize(area)
        self.assertEqual(rc, 0, out)
        lab.record(area, protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = lab.adopt(protocol, run_id)
        self.assertEqual(rc, 0, out)
        text = protocol.read_text(encoding="utf-8")
        self.assertIn("- **Recorded results:** criterion-1 missed;", text)
        self.assertIn("criterion_1_threshold = 0.9 ", text)


class StatedBarJudge(unittest.TestCase):
    """A bar the task states in the prompt skeleton, end to end at low repeat
    cost, the model faked: fixed answers test the arithmetic and the route
    from registration to adoption, not the quality of any judgement. The
    faked model misses three of the six causal sentences — accuracy 9/12 =
    0.75 — and answers the placebo Yes throughout (null 0.50, at chance).
    Registered `at_least = 0.75` meets the bar exactly; `at_least = 0.76`
    misses it. metrics.json, the run's printout and the Recorded results
    line carry the registered value (docs/notes/2026-11-02-absolute-task-bar.md)."""

    @staticmethod
    def _model(alias: str, prompts: list[str], *, workers: int) -> list[str]:
        out = []
        for p in prompts:
            if p.startswith("Is this text written in English?"):
                out.append("Yes")
            else:
                missed = any(f"Text: {i}: " in p for i in (0, 2, 4))
                out.append("No" if missed or "Rain causes" not in p else "Yes")
        return out

    def _run_to_adoption(self, name: str, bar: str) -> tuple[dict, str, str]:
        """Register `at_least = BAR` in a judge area NAME, run it with the
        faked model, finalize, record the analysis audit, adopt. Returns
        (metrics.json, the run's printout, the protocol as adopted)."""
        lab = Lab()
        self.addCleanup(lab.close)
        area, protocol = judge_area(lab, name)
        text = protocol.read_text(encoding="utf-8")
        self.assertEqual(text.count("constants = { margin = 0.25 }"), 1)
        text = text.replace(
            "constants = { margin = 0.25 }", f"constants = {{ at_least = {bar} }}"
        )
        text = re.sub(
            r'(id = "criterion-1"\nkey = "criterion_1_pass"\nsentence = )"[^"]*"',
            rf'\1"registered accuracy is at least at_least = {bar}, the bar the task text states"',
            text,
        )
        self.assertIn(f"at least at_least = {bar}, the bar the task text states", text)
        protocol.write_text(text, encoding="utf-8")
        lab.fill(
            protocol,
            "--force",
            f"Inference criterion=[criterion-1] registered accuracy at least {bar}, "
            "the bar the task text states",
        )
        lab.commit("the judge, registered with the task's bar")
        measure = area / "scripts" / "01_measure.py"
        from labkit.run import llm

        out = io.StringIO()
        with (
            mock.patch.object(llm, "complete_many", self._model),
            mock.patch.object(
                llm,
                "provenance",
                lambda alias: {"model": "fake@e2e", "endpoint": "fake"},
            ),
            mock.patch.object(sys, "argv", [str(measure)]),
            mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(lab.root)}),
            contextlib.redirect_stdout(out),
        ):
            _load(measure, f"e2e_stated_{name.replace('-', '_')}").main()
        run_id = lab.run_id_of(out.getvalue())
        metrics = json.loads(
            (area / "runs" / run_id / "metrics.json").read_text(encoding="utf-8")
        )
        lab.commit("the run")
        rc, out_text = lab.finalize(area)
        self.assertEqual(rc, 0, out_text)
        lab.record(area, protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out_text = lab.adopt(protocol, run_id)
        self.assertEqual(rc, 0, out_text)
        return metrics, out.getvalue(), protocol.read_text(encoding="utf-8")

    def test_a_lane_exactly_at_the_stated_bar_is_adopted_as_met(self):
        metrics, printed, text = self._run_to_adoption("judge-at-bar", "0.75")
        self.assertEqual(
            (
                metrics["criterion_1_accuracy"],
                metrics["criterion_1_threshold"],
                metrics["criterion_1_pass"],
                metrics["quality_check_2_accuracy"],
                metrics["quality_check_2_pass"],
            ),
            (0.75, 0.75, True, 0.5, True),
        )
        self.assertRegex(printed, r"criterion_1_threshold +0\.75\b")
        self.assertIn("- **Recorded results:** criterion-1 met;", text)
        self.assertIn("criterion_1_threshold = 0.75 ", text)

    def test_a_lane_just_below_the_stated_bar_is_adopted_as_missed(self):
        metrics, printed, text = self._run_to_adoption("judge-below-bar", "0.76")
        self.assertEqual(
            (
                metrics["criterion_1_accuracy"],
                metrics["criterion_1_threshold"],
                metrics["criterion_1_pass"],
            ),
            (0.75, 0.76, False),
        )
        self.assertRegex(printed, r"criterion_1_threshold +0\.76\b")
        self.assertIn("- **Recorded results:** criterion-1 missed;", text)
        self.assertIn("criterion_1_threshold = 0.76 ", text)


if __name__ == "__main__":
    unittest.main()
