"""Every supported skeleton, end to end on the real chain: stamp, fill, run,
check, adopt — the count at seconds, the prompt skeleton at seconds with the
model faked, the estimator at minutes through the freeze. Each step is the
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
    findings,
    promises,
    protocol_block,
    scope_sha,
    standard_contract as sc,
)


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
        self.root = Path(self.tmp.name) / "lab"
        self.root.mkdir()
        scaffold.stamp_lab(self.root, "lab")
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(self.root),
            "LABKIT_DETACHED": "1",  # a full run at minutes starts detached
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
            rc = claude_hooks.stop({"cwd": str(self.root), "session_id": "e2e"})
        return rc, err.getvalue()

    def pre_commit(self, *paths: Path) -> tuple[int, str]:
        """The pre-commit's `report-check --if-reported --staged PATHS`."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = report_check.if_reported(list(paths), self.root, staged=True)
        return rc, out.getvalue()


class Count(unittest.TestCase):
    """The counting skeleton at seconds: lines per document, three documents."""

    run_id = ""  # the kept run, from the step that runs it

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        root = cls.lab.root
        docs = root / "data" / "raw" / "docs"
        docs.mkdir(parents=True)
        for name, lines in (("a.txt", 1), ("b.txt", 2), ("c.txt", 6)):
            (docs / name).write_text("x\n" * lines, encoding="utf-8")
        cls.area, cls.protocol = cls.lab.exp("lines", cost="seconds")
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
        sk = sc.skeleton("seconds", False)
        self.assertIs(sk, sc.COUNT)
        self.assertEqual(
            sorted(p.name for p in (self.area / "scripts").iterdir()),
            sorted(dest for _, dest in sk.scripts),
        )
        self.assertTrue((self.area / sc.CHECK_SCRIPT).is_file())

    def test_02_run_finalize_audit_adopt(self):
        lab = type(self).lab
        out = lab.script(self.area, "01_measure.py")
        run_id = lab.run_id_of(out)
        type(self).run_id = run_id
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
        # finding (1): station 4 ran the count's own check script
        self.assertIn("read from the proposed protocol", out)
        self.assertIn("finalized, audited, checked", out)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(f"- **Recorded results:** lines_mean = 3.0 (run {run_id})", text)
        self.assertIn(f"- {run_id} — the kept run", text)

    def test_03_the_stop_hook_and_the_commit_hold_the_adopted_number(self):
        lab = type(self).lab
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

    def test_04_a_script_changed_under_the_reported_number_reopens_it(self):
        """Finding (2): the protocol untouched, the formula changed — the
        stop hook holds the area, not the protocol alone."""
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
        lab = type(self).lab
        text = self.protocol.read_text(encoding="utf-8")
        reopened = re.sub(r'\n\[result\]\nrun = "[^"]+"\n', "", text)
        self.assertNotEqual(reopened, text)
        self.protocol.write_text(reopened, encoding="utf-8")
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 1, out)
        self.assertIn("the working tree differs from the index", out)
        self.assertIn(f"its head declares {self.run_id}", out)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("report-check", out)
        lab.git("checkout", "HEAD", "--", str(self.protocol))

    def test_06_without_the_check_script_the_gap_names_the_template(self):
        """Finding (1), the other way round: an area stamped before the count
        had its own check script is told which template to stamp."""
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


class Judge(unittest.TestCase):
    """The prompt skeleton at seconds, the model faked: twelve texts, a
    registered question the text answers, a placebo for the null lane."""

    run_id: str  # the kept run of test_02

    GOLD = {
        "causal": "Rain causes the street to be wet.",
        "not_causal": "The street is wet.",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        root = cls.lab.root
        raw = root / "data" / "raw" / "sentences.jsonl"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(
            "".join(
                json.dumps(
                    {"id": f"s{i}", "text": f"{i}: {cls.GOLD[gold]}", "gold": gold}
                )
                + "\n"
                for i, gold in enumerate(["causal", "not_causal"] * 6)
            ),
            encoding="utf-8",
        )
        cls.area, cls.protocol = cls.lab.exp("judge", cost="seconds", model="haiku")
        scripts = cls.area / "scripts"
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
        cls.measure = scripts / "01_measure.py"
        _replace(
            cls.measure,
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
        _strip_promise_placeholders(cls.protocol)
        cls.lab.fill(
            cls.protocol,
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
        cls.lab.fill(cls.protocol, "--prompts")
        cls.lab.script(cls.area, "00_prepare.py")
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
        self.assertIs(sc.skeleton("seconds", True), sc.MODEL)
        self.assertEqual(
            sorted(p.name for p in (self.area / "scripts").iterdir()),
            sorted(dest for _, dest in sc.MODEL.scripts),
        )

    def test_02_run_finalize_audit_adopt(self):
        lab = type(self).lab
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
        type(self).run_id = run_id  # test_04 reads the same kept run
        self.assertIn("c1_pass       True", out.getvalue())
        rc, out_text = lab.finalize(self.area)
        self.assertEqual(rc, 0, out_text)
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out_text = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out_text)
        self.assertIn("finalized, audited, checked", out_text)
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(f"c1_pass = True (run {run_id})", text)
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

    def test_03_seconds_refuses_the_templates_separate_probe(self):
        result = subprocess.run(
            [sys.executable, str(self.measure), "--probe", "2"],
            cwd=type(self).lab.root,
            capture_output=True,
            text=True,
            env=type(self).lab.env,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--probe is not available at cost='seconds'", result.stderr)

    def _blocker(self) -> Path:
        """A second analysis record of the kept run, holding one BLOCKER."""
        return findings.write(
            self.area,
            sc.ANALYSIS_AUDIT,
            "test",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(self.protocol.read_text(encoding="utf-8")),
            (1, 0, 0),
            [("BLOCKER", "BLOCKER · scripts/01_measure.py:1 · the prompt asks more than the gold scores")],
            run_id=self.run_id,
            shown_sha=audit_binding.run_shown(self.area, self.area / "runs" / self.run_id, "").sha,
        )  # fmt: skip

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

    def test_04_an_accepted_blocker_reaches_the_protocol_as_its_limit(self):
        """Review 2026-10-21 (judge-2): an accepted BLOCKER may carry a
        number read within it, but an instrument unfit for C1 leaves C1
        unjudged — the decision says which, the protocol carries it as a
        Limit line, report-check holds the two together."""
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
        self.assertIn(f"C1 not assessable with this run ({label})", text)  # the Answer
        self.assertIn("c1_pass = True", text)  # the number stays reported
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
        # the twin: the verdicts stand, the limit named beside them
        rc, out = self._decide(record, "accepted", reason, "--effect", "stands")
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

    def test_05_an_accepted_warning_that_names_its_effect_reaches_the_result(self):
        """Review 2026-10-21 (judge-2/3): the cue that limits how the number
        reads was a WARNING, accepted, and the Answer said `c1_pass = True`
        alone. A WARNING may name its effect; named, it reaches the result."""
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
            shown_sha=audit_binding.run_shown(self.area, self.area / "runs" / self.run_id, "").sha,
        )  # fmt: skip
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
            f"c1_pass = True (run {self.run_id}); subject to 1 recorded limitation",
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
    """The estimator skeleton at minutes, through the freeze: a threshold on
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
        cls.area, cls.protocol = cls.lab.exp("threshold", cost="minutes")
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
        self.assertIs(sc.skeleton("minutes", False), sc.ESTIMATOR)
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
        # the preflight audit, decided; its line into the head; the freeze
        sha = lab.record(self.area, self.protocol, sc.PREFLIGHT_AUDIT)
        _replace(
            self.protocol,
            [
                (
                    'preflight_audit = ""',
                    f'preflight_audit = "2026-10-19 · scope sha {sha[:12]} · 0 findings"',
                ),
                ("frozen = false", "frozen = true"),
            ],
        )
        # `labkit-init exp threshold --report`: the † fields, filled now
        lab.exp("threshold", cost="minutes", report=True)
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
        lab.fill(
            self.protocol,
            "Raw output=one registered row and one test row, from the probe",
        )
        lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        self.assertIn("frozen, finalized, audited, checked", out)
        self.assertNotIn("Raw output", out)  # filled already: not named again
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(f"c1_pass = True (run {run_id})", text)
        self.assertEqual(protocol_block.declared_run(text), run_id)
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol, self.measure)
        self.assertEqual(rc, 0, out)
        self.assertIn("read from the index", out)
        lab.commit("the verdict, adopted")


if __name__ == "__main__":
    unittest.main()
