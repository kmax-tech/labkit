"""Every supported skeleton, end to end on the real chain: stamp, fill, run,
check, adopt — the count at low repeat cost, the prompt skeleton at low repeat cost with the
model faked, the estimator at high repeat cost through the freeze. Each step is the
command an agent runs (`labkit-init exp`, `protocol-fill`, the area's own
scripts under the interpreter, `finalize`, `protocol-fill --from-run`, the
stop hook, the pre-commit's `report-check --if-reported --staged`), and
what every station holds is the contract's answer (`standard_contract`).

The four findings of the 2026-10-19 audit are pinned here on the real
chain, not on fixtures: the gate asked for a check script the skeleton
never stamped (1), a script changed under a reported number passed both
hooks (2), the pre-commit read the tree where the commit holds the index
(3), and a refused adoption left the unchecked declaration standing (4).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from datetime import datetime, timezone
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.gates import audit, claude_hooks, finalize, preflight, report_check
from labkit.checks import audit_binding  # noqa: E402
from labkit.tools import protocol_fill, scaffold
from labkit.formats import (
    answering_run,
    findings,
    promises,
    protocol_block,
    scope_sha,
    standard_contract as sc,
)
from protocol_fixture import registration_of  # noqa: E402


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
                audit_binding.run_shown(area, area / "runs" / run_id, "").sha
                if run_id is not None
                else None
            ),
            registration=registration_of(area),
        )
        return sha

    def finalize(self, area: Path) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = finalize.main([str(area)])
        return rc, out.getvalue()

    def adopt(self, protocol: Path, run_id: str) -> tuple[int, str]:
        """`protocol-fill PROTOCOL --from-run RUN_ID`."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = protocol_fill.main([str(protocol), "--from-run", run_id])
        return rc, out.getvalue()

    def adopt_forced(self, protocol: Path, run_id: str) -> tuple[int, str]:
        """`protocol-fill PROTOCOL --from-run RUN_ID --force`."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
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
            rc = claude_hooks.stop(
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
            rc = report_check.if_reported(list(paths), self.root, staged=True)
        return rc, out.getvalue()


def assert_draws(
    test: unittest.TestCase, lab: "Lab", area: Path, run_id: str, key: str, other: str
) -> None:
    """`02_analyze.py --draws` on the kept run prints its criterion value
    under the measure skeleton's key (`C1_VALUE_KEY`): the value metrics.json
    holds, never the other skeleton's key. The analysis skeleton is shared;
    it read the model's key for every skeleton and printed `c1_accuracy
    None` for a fit (2026-10-22)."""
    metrics = json.loads((area / "runs" / run_id / "metrics.json").read_text())
    out = lab.script(area, "02_analyze.py", "--draws")
    test.assertIn(f"draw 1  {run_id}  {key} {metrics[key]}  c1_pass True", out)
    test.assertNotIn(other, out)


class Count(unittest.TestCase):
    """The counting skeleton at low repeat cost: lines per document, three documents."""

    run_id = ""  # the kept run, from `_adopted`
    committed = False  # `_committed`: the adopted number is in HEAD

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        root = cls.lab.root
        docs = root / "data" / "raw" / "docs"
        docs.mkdir(parents=True)
        for name, lines in (("a.txt", 1), ("b.txt", 2), ("c.txt", 6)):
            (docs / name).write_text("x\n" * lines, encoding="utf-8")
        cls.area, cls.protocol = cls.lab.exp("lines", repeat_cost="low", kind="compute")
        cls.measure = cls.area / "scripts" / "01_measure.py"
        _replace(
            cls.measure,
            [
                (
                    'SOURCE = REPO / "data" / "TODO"',
                    'SOURCE = REPO / "data" / "raw" / "docs"',
                ),
                ('COUNT_FIELD = "TODO_count"', 'COUNT_FIELD = "lines"'),
                ('METRIC_KEY = "TODO_mean"', 'METRIC_KEY = "lines_mean"'),
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
                    "    return {METRIC_KEY: sum(r[COUNT_FIELD] for r in items) / len(ids)}",
                ),
            ],
        )
        cls.lab.fill(
            cls.protocol,
            "type=exploratory",
            "Terms of this protocol=n/a — no coinage",
            "Question / hypothesis=How many lines does a document of data/raw/docs hold on average?",
            "Data / scope=data/raw/docs, 3 documents, read directly",
            "Exclusions / filters=hidden entries and nested directories (visible())",
            "Unit=one document of data/raw/docs",
        )
        cls.lab.commit("the count, registered")

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
        in any order (audit 2026-10-18: test_04–06 read what test_02 left
        behind, and only `--dist loadscope` kept the suite green)."""
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
        self.assertIn(f"- **Recorded results:** lines_mean = 3.0 (run {run_id})", text)
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
                    "    return {METRIC_KEY: sum(r[COUNT_FIELD] for r in items) / len(ids)}",
                    "    return {METRIC_KEY: sum(r[COUNT_FIELD] for r in items) / len(ids) + 1}",
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
        self.assertIn(f"its head declares {run_id}", out)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("report-check", out)
        lab.git("checkout", "HEAD", "--", str(self.protocol))

    def test_06_without_the_check_script_the_gap_names_the_template(self):
        """Finding (1), the other way round: an area stamped before the count
        had its own check script is told which template to stamp."""
        self._committed()
        lab = type(self).lab
        check = self.area / sc.CHECK_SCRIPT
        check.unlink()
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = report_check.main([str(self.area)])
            self.assertEqual(rc, 1, out.getvalue())
            self.assertIn("no scripts/02_analyze.py", out.getvalue())
            self.assertIn("analyze-quick-script.py.template", out.getvalue())
        finally:
            lab.git("checkout", "--", ".")


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
        "Success / failure criterion=[C1] registered accuracy at least the null lane's plus margin",
        "Admissibility condition=[A1] at most max_empty empty answers; [A2] the null lane at chance within null_band_items",
        "Data / scope=data/prepared/sentences_v1.jsonl, 12 sentences, 00_prepare.py",
        "Data profile=6 and 6 sentences, the marker 'because' in both classes",
        "Model / tool=haiku",
        "Null condition / anchors (in the same run)=[A2] the placebo question (English?) answers Yes for every item: expected accuracy 6 of 12",
        "Exclusions / filters=none",
        "Unit=one sentence",
    )
    lab.fill(protocol, "--prompts")
    lab.script(area, "00_prepare.py")
    return area, protocol


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
    def _model(alias: str, prompts: list[str]) -> list[str]:
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

    def _adopted(self) -> str:
        """Run, finalize, record, adopt, commit — once per class; every later
        test calls it first and so runs alone and in any order (audit
        2026-10-18)."""
        cls = type(self)
        if cls.run_id:
            return cls.run_id
        lab = cls.lab
        from labkit.run import llm

        listed = io.StringIO()
        with contextlib.redirect_stdout(listed):
            self.assertEqual(protocol_fill.main([str(self.protocol), "--list"]), 0)
        before, _, after = listed.getvalue().partition("after the run — yours")
        self.assertNotIn("Raw output", before)  # not owed before the run
        self.assertIn("Raw output", after)
        out = io.StringIO()
        with (
            mock.patch.object(llm, "complete_many", self._model),
            mock.patch.object(
                llm,
                "provenance",
                lambda alias: {"model": "fake@e2e", "endpoint": "fake"},
            ),
            mock.patch.object(sys, "argv", [str(self.measure)]),
            mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(lab.root)}),
            contextlib.redirect_stdout(out),
        ):
            _load(self.measure, "e2e_judge_measure").main()
        run_id = lab.run_id_of(out.getvalue())
        cls.run_id = run_id
        self.assertIn("c1_pass       True", out.getvalue())
        rc, out_text = lab.finalize(self.area)
        self.assertEqual(rc, 0, out_text)
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out_text = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out_text)
        self.assertIn("finalized, audited, checked", out_text)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            "- **Recorded results:** C1 met; A1 met; A2 met · recorded: ", text
        )
        self.assertIn(f"(run {run_id})", text)
        assert_draws(self, lab, self.area, run_id, "c1_accuracy", "c1_score")
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
            [("BLOCKER", "BLOCKER · scripts/01_measure.py:1 · the prompt asks more than the gold scores")],
            run_id=self.run_id,
            shown_sha=audit_binding.run_shown(self.area, self.area / "runs" / self.run_id, "").sha, registration=registration_of(self.area),)  # fmt: skip

    def _decide(self, record: Path, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = audit.main(
                [str(self.area), "--decide", "1", *argv, "--record", str(record)]
            )
        return rc, out.getvalue()

    def _report_check(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = report_check.main([str(self.area)])
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
        """Review 2026-10-21 (judge-2): an accepted BLOCKER may carry a
        number read within it, but an instrument unfit for C1 leaves C1
        unjudged — the decision says which, the protocol carries it as a
        Limit line, report-check holds the two together."""
        self._adopted()
        lab = type(self).lab
        record = self._blocker()
        label = f"Limit (audit {record.stem} #1)"
        reason = "real: the prompt says states or implies, the gold codes juxtaposition not causal"
        rc, out = self._decide(record, "accepted", reason)
        self.assertEqual(rc, 2, out)  # the effect is owed
        self.assertIn("owes its effect", out)
        rc, out = self._decide(
            record, "accepted", reason, "--effect", "C9 not assessable"
        )
        self.assertEqual(rc, 2, out)  # an id the protocol does not register
        self.assertIn("C9", out)
        rc, out = self._decide(
            record, "accepted", reason, "--effect", "C1 not assessable"
        )
        self.assertEqual(rc, 0, out)
        self.assertEqual(findings.read(record).findings[0].effect, "C1 not assessable")
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)  # the record says so, the protocol not yet
        self.assertIn(label, out)
        rc, out = lab.adopt_forced(self.protocol, self.run_id)
        self.assertEqual(rc, 0, out)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            f"- **{label}:** C1 not assessable with this run — {reason}", text
        )
        # the verdict the Recorded results state: the criterion unjudged, no pass
        self.assertIn(f"- **Recorded results:** C1 not assessable ({label})", text)
        self.assertIn("c1_accuracy = 1.0", text)  # the measurement stays reported
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
        rc, out = self._decide(record, "accepted", reason, "--effect", "stands")
        self.assertEqual(rc, 0, out)
        rc, out = lab.adopt_forced(self.protocol, self.run_id)
        self.assertEqual(rc, 1, out)
        self.assertIn("`stands` on an accepted BLOCKER not reviewed", out)
        # the review judges the claim: the Conclusion comes first (judge-2
        # on 86e38bc reviewed a placeholder and paid a second review)
        rc, out = self._review(record)
        self.assertEqual(rc, 2, out)
        self.assertIn("the Conclusion is not written yet", out)
        lab.fill(
            self.protocol,
            "Conclusion=C1 is met as one draw on twelve items; nothing more is claimed.",
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
            "; subject to 1 recorded limitation (the Limit lines below)", text
        )
        rc, out = self._report_check()
        self.assertEqual(rc, 0, out)
        # fixed after all: no effect owed, and the line is the record's no longer
        rc, out = self._decide(record, "fixed", "")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("effect", record.read_text(encoding="utf-8"))
        # but `fixed` in the state audited: no follow-up has seen a repair, the
        # code is the audited code — report-check holds it (fixed-followup
        # pilots, 2026-10-26); the twin, the finding dismissed as not applying
        # to this state, passes
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("decided `fixed` in the state audited", out)
        rc, out = self._decide(
            record, "dismissed", "the gold codes the prompt's three cases after all"
        )
        self.assertEqual(rc, 0, out)

    def test_05_an_accepted_warning_that_names_its_effect_reaches_the_result(self):
        """Review 2026-10-21 (judge-2/3): the cue that limits how the number
        reads was a WARNING, accepted, and the Answer said `c1_pass = True`
        alone. A WARNING may name its effect; named, it reaches the result."""
        self._adopted()
        lab = type(self).lab
        record = findings.write(
            self.area,
            sc.ANALYSIS_AUDIT,
            "test",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(self.protocol.read_text(encoding="utf-8")),
            (0, 1, 0),
            [("WARNING", "WARNING · data/raw:1 · six connectives separate the classes")],
            run_id=self.run_id,
            shown_sha=audit_binding.run_shown(self.area, self.area / "runs" / self.run_id, "").sha, registration=registration_of(self.area),)  # fmt: skip
        label = f"Limit (audit {record.stem} #1)"
        reason = "C1 reached on these items; a keyword rule scores 12/12, so no causal understanding is shown"
        rc, out = self._decide(record, "accepted", reason, "--effect", "stands")
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
        # accepted without an effect it is no limit — and the result section
        # must say so again: the rendering is exact (phase 5), a Limit line
        # and a note the records no longer decide are blockers until written back
        rc, out = self._decide(record, "accepted", reason)
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
        """labkit-paper area 08, 2026-10-21: an agent typed `(run
        2026-10-21T12-48-00_final)` into Recorded results; the gates read only the
        exact id shape, saw no citation and let the commit through. Since
        phase 3 the declaration is `[result] run`: a typed id there does not
        read and blocks where it stands, a shaped one must be a run."""
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


class Estimator(unittest.TestCase):
    """The estimator skeleton at high repeat cost, through the freeze: a threshold on
    one feature, which the gold follows; the null lane permuted."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        root = cls.lab.root
        raw = root / "data" / "raw" / "points.jsonl"
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
        cls.area, cls.protocol = cls.lab.exp(
            "threshold", repeat_cost="high", kind="fit"
        )
        scripts = cls.area / "scripts"
        _replace(
            scripts / "00_prepare.py",
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
                "Success / failure criterion": "[C1] registered accuracy at least the null lane's plus margin",
                "Admissibility condition": "[A1] at most max_empty items without a prediction; [A2] the null lane within null_band of chance",
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
        # the preflight audit, decided; its record named in the head; the freeze
        lab.record(self.area, self.protocol, sc.PREFLIGHT_AUDIT)
        (record,) = (self.area / "audits").glob("*-preflight.toml")
        _replace(
            self.protocol,
            [
                ('preflight_audit = ""', f'preflight_audit = "{record.name}"'),
                ("frozen = false", "frozen = true"),
            ],
        )
        # `labkit-init exp threshold --report`: the † fields, filled now
        lab.exp("threshold", repeat_cost="high", report=True)
        lab.fill_open(self.protocol)
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
        # no model: Raw output is not owed, and the stamp left it out (I11)
        self.assertNotIn("**Raw output", self.protocol.read_text(encoding="utf-8"))
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        self.assertIn("frozen, finalized, audited, checked", out)
        self.assertNotIn("Raw output", out)  # filled already: not named again
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(
            "- **Recorded results:** C1 met; A1 met; A2 met · recorded: ", text
        )
        self.assertIn(f"(run {run_id})", text)
        self.assertEqual(protocol_block.declared_run(text), run_id)
        assert_draws(self, lab, self.area, run_id, "c1_score", "c1_accuracy")
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
        """`01_measure.py --repeat-of` (audit 2026-10-27, C1): the kept run
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
        # carries it (a script that kept the parent's seed showed a spread of 0)
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
        self.assertIn(f"draw 2  {repeat}  c1_score", out)
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        pid = protocol_block.head(self.protocol.read_text(encoding="utf-8")).id
        assert pid is not None
        chosen = answering_run.bound_answering_run(self.area, pid).run_dir
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


if __name__ == "__main__":
    unittest.main()
