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
from labkit.tools import protocol_fill, scaffold
from labkit.formats import (
    answering_run,
    findings,
    promises,
    protocol_block,
    scope_sha,
    standard_contract as sc,
)
from protocol_fixture import registration_of, shown_sha  # noqa: E402


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
                shown_sha(area, area / "runs" / run_id) if run_id is not None else None
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
        """`protocol-fill PROTOCOL --from-run RUN_ID --force`: (exit, what it
        printed, a refusal included)."""
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


def stamp_count(lab: "Lab") -> tuple[Path, Path]:
    """The counting skeleton at low repeat cost in LAB, filled and committed:
    lines per document over three documents (1, 2, 6 lines — mean 3.0).
    Returns (area, protocol)."""
    root = lab.root
    docs = root / "data" / "raw" / "docs"
    docs.mkdir(parents=True)
    for name, lines in (("a.txt", 1), ("b.txt", 2), ("c.txt", 6)):
        (docs / name).write_text("x\n" * lines, encoding="utf-8")
    area, protocol = lab.exp("lines", repeat_cost="low", kind="compute")
    _replace(
        area / "scripts" / "01_measure.py",
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
    lab.fill(
        protocol,
        "type=exploratory",
        "Terms of this protocol=n/a — no coinage",
        "Question / hypothesis=How many lines does a document of data/raw/docs hold on average?",
        "Data / scope=data/raw/docs, 3 documents, read directly",
        "Exclusions / filters=hidden entries and nested directories (visible())",
        "Unit=one document of data/raw/docs",
    )
    lab.commit("the count, registered")
    return area, protocol


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
        return self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))

    def records(self) -> set[Path]:
        return set((self.area / "audits").glob("*-analysis*.toml"))

    def analysis(self, answer: str) -> tuple[int, str, str]:
        """`labkit-audit AREA --mode analysis`, the model's answer ANSWER:
        (exit, output, the prompt sent); the record it wrote is `self.record`
        — by the set of records, not by name order (`…-analysis-2.toml`
        sorts before `…-analysis.toml`)."""
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
            rc = audit.main([str(self.area), "--mode", "analysis"])
        written = self.records() - before
        self.record = written.pop() if len(written) == 1 else None
        return rc, out.getvalue(), sent[0] if sent else ""

    def decide(self, record: Path, n: int, status: str, reason: str) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = audit.main(
                [
                    str(self.area),
                    "--decide",
                    str(n),
                    status,
                    reason,
                    "--record",
                    str(record),
                ]
            )
        self.assertEqual(rc, 0, out.getvalue())

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


class Withdraw(CountCommands):
    """Replacing a declared result goes through the real commands: withdraw
    the declaration (`protocol-fill --withdraw`), audit the run that
    answers, adopt it (`--from-run`). An analysis record binds the run the
    head declared when it was another one (`audit_binding.declared_piece`),
    so a withdrawal moves the state and the next audit follows earlier
    findings up. File-check case, 2026-10-28: a BLOCKER on the declared run,
    fixed by re-adopting, stayed held, and the agent committed past the
    hook; a first fix bound the declaration but left `--from-run --force`
    as the way, which then could never pass. No test here writes a
    protocol head by hand."""

    # -- the repair case
    def test_a_wrong_declaration_is_withdrawn_followed_up_and_replaced(self):
        run_a = self.adopted_a()
        self.change_code()
        run_b = self.measure()
        # finalize names the mismatch, and the withdrawal as its way out
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(
            f"[result] declares {run_a}, but the run that answers is {run_b}", out
        )
        self.assertIn("--withdraw", out)
        wrong = (
            f"BLOCKER · PROTOCOL-lines.md:1 · the head declares run {run_a}, the rows "
            f"shown are run {run_b} · the reported mean · LAB-050 Analysis audit "
            f"before reporting · declare the run the current code measured\n"
            f"verdict: 1 blockers, 0 warnings, 0 notes"
        )
        rc, out, prompt = self.analysis(wrong)
        self.assertEqual(rc, 1, out)
        self.assertIn(
            f"the protocol's [result] declares {run_a}, not the run shown", prompt
        )
        self.assertIn("a wrong declaration", out)  # the way out, where it is decided
        self.assertIn("--withdraw", out)
        record = self.record
        assert record is not None
        self.decide(record, 1, "fixed", "the wrong declaration withdrawn")
        # a declaration is never replaced, --force or not: it is withdrawn
        rc, out = self.lab.adopt_forced(self.protocol, run_b)
        self.assertEqual(rc, 2, out)
        self.assertIn("a declaration is not replaced: withdraw it", out)
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
                "  3. `protocol-fill ",
                " --from-run ",
            )
        ]
        self.assertEqual(steps, sorted(steps))
        text = self.protocol.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            rf"- {run_a} — .* · withdrawn \d{{4}}-\d{{2}}-\d{{2}}: the measuring code changed after the adoption",
        )
        # withdrawn alone, nothing is released: the fixed BLOCKER owes its follow-up
        rc, out = self.lab.adopt(self.protocol, run_b)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{record.name}#1: decided `fixed`, never followed up", out)
        rc, out, prompt = self.analysis(
            f"FIX · {record.name}#1 · resolved · the head declares no run now\n\n{self.clean}"
        )
        self.assertEqual(rc, 0, out)
        self.assertNotIn("the protocol's [result] declares", prompt)
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
        self.assertNotIn("the protocol's [result] declares", prompt)
        rc, out = self.lab.adopt(self.protocol, run_b)  # no --force
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), run_b)
        self.assertNotEqual(run_a, run_b)

    def test_an_audit_made_while_another_run_was_declared_is_owed_again(self):
        """The twin of the usual path in the other order: B audited while A
        is still declared; after the withdrawal that audit does not cover,
        and one audit more does."""
        self.adopted_a()
        self.change_code()
        run_b = self.measure()
        rc, out, prompt = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        self.assertIn("the protocol's [result] declares", prompt)
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

    # -- after an adoption, a code change is told to withdraw first
    def test_a_code_change_after_the_adoption_is_told_to_withdraw_first(self):
        """The commit of a fix after an adoption is held (the hook holds the
        code to the declared run). Each hold names the withdrawal before its
        own way out — six holds that said "measure anew" led past a note
        below them (decision-reading probe, file-check case, 2026-10-28) —
        so the agent does not spend an audit under the old declaration. The
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
            self.assertIn("— way out: withdraw the declaration first (`", hold)
        self.assertIn(f"changed since {run_a}", out)
        self.assertEqual(self.withdraw("the measuring code changes")[0], 0)
        self.lab.git("add", str(self.protocol))
        rc, out = self.lab.pre_commit(measure, self.protocol)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("withdraw the declaration first", out)

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

    def test_a_dismissed_blocker_is_held_until_a_second_auditor_upholds_it(self):
        """The deciding agent's own `dismissed` does not release a blocking
        finding, its first dismissal too (decided 2026-10-28; until then it
        released the number on its reason alone). The twin: a review that
        upholds it releases the adoption."""
        run_a = self.measure()
        rc, out, _ = self.analysis(
            "BLOCKER · scripts/01_measure.py:1 · hidden files are counted · the mean "
            "· LAB-050 Analysis audit before reporting · skip them\n"
            "verdict: 1 blockers, 0 warnings, 0 notes"
        )
        self.assertEqual(rc, 1, out)
        record = self.record
        assert record is not None
        self.decide(record, 1, "dismissed", "visible() skips hidden files at :12")
        self.lab.fill(
            self.protocol, "Conclusion=Three documents hold 3.0 lines on average."
        )
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{record.stem} #1: `dismissed` on a BLOCKER", out)
        self.assertIn("--review", out)
        rc, out = self.review(record, "upheld")
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)

    def test_a_dismissed_warning_owes_no_review(self):
        run_a = self.measure()
        rc, out, _ = self.analysis(
            "WARNING · scripts/01_measure.py:1 · hidden files might be counted · the "
            "mean · LAB-050 Analysis audit before reporting · check visible()\n"
            "verdict: 0 blockers, 1 warnings, 0 notes"
        )
        record = self.record
        assert record is not None
        self.decide(record, 1, "dismissed", "visible() skips hidden files at :12")
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)

    # -- a withdrawal releases nothing
    def test_a_withdrawal_releases_nothing(self):
        run_a = self.measure()
        rc, out = self.withdraw("nothing declared yet")
        self.assertEqual(rc, 2, out)  # nothing to withdraw
        self.assertIn("declares no result", out)
        rc, out, _ = self.analysis(self.clean)
        rc, out = self.lab.adopt(self.protocol, run_a)
        self.assertEqual(rc, 0, out)
        # a later audit finds a fault; its BLOCKER stays open
        rc, out, _ = self.analysis(
            "BLOCKER · scripts/01_measure.py:1 · hidden files are counted · the mean "
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


class CorrectedDescription(CountCommands):
    """A description in the protocol's setup that the data did not hold —
    the count in Data / scope — corrected in place, is followed up like any
    repair: an analysis record binds the setup's prose
    (`protocol_check.audited_texts`), so the correction moves the state and
    the next audit judges the finding. Fifth SAB-like draw, 2026-10-28: a
    corrected count could never be followed up, the BLOCKER stayed held as
    fixed in the state audited. Both directions, through the real commands:
    the correction alone releases after the follow-up; an unchanged or an
    insufficient description releases nothing. No test writes a head by
    hand."""

    RIGHT = "data/raw/docs, 3 documents, read directly"

    def setUp(self) -> None:
        super().setUp()
        # registered with a count the data does not hold, before any run
        self.lab.fill(
            self.protocol,
            "--force",
            "Data / scope=data/raw/docs, 4 documents, read directly",
        )
        self.lab.commit("the count, registered with a wrong document count")
        self.run_a = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        line = next(
            n
            for n, ln in enumerate(self.protocol.read_text().splitlines(), 1)
            if "**Data / scope:**" in ln
        )
        rc, out, _ = self.analysis(
            f"BLOCKER · PROTOCOL-lines.md:{line} · Data / scope says 4 documents, the "
            f"run read 3 · the mean's denominator as described · LAB-050 Analysis "
            f"audit before reporting · correct the description\n"
            f"verdict: 1 blockers, 0 warnings, 0 notes"
        )
        self.assertEqual(rc, 1, out)
        assert self.record is not None
        self.blocking = self.record

    def describe(self, value: str) -> None:
        self.lab.fill(self.protocol, "--force", f"Data / scope={value}")

    def test_the_corrected_description_is_followed_up_and_released(self):
        self.describe(self.RIGHT)
        self.decide(self.blocking, 1, "fixed", "Data / scope now says 3 documents")
        # the correction moved the state: the finding owes its follow-up
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn(
            f"{self.blocking.name}#1: decided `fixed`, never followed up", out
        )
        rc, out, prompt = self.analysis(
            f"FIX · {self.blocking.name}#1 · resolved · Data / scope says 3 documents, "
            f"as the run read\n\n{self.clean}"
        )
        self.assertEqual(rc, 0, out)
        self.assertIn("3 documents", prompt)
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 0, out)

    def test_an_unchanged_description_stays_held_through_another_audit(self):
        self.decide(self.blocking, 1, "fixed", "corrected")  # but nothing changed
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn("decided `fixed` in the state audited", out)
        self.assertIn("a description in the protocol's setup, corrected in place", out)
        rc, out, _ = self.analysis(self.clean)  # the same state audited again
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)
        self.assertIn("decided `fixed` in the state audited", out)

    def test_an_insufficient_correction_is_judged_and_carried_open(self):
        self.describe("data/raw/docs, 5 documents, read directly")
        self.decide(self.blocking, 1, "fixed", "Data / scope corrected")
        rc, out, _ = self.analysis(
            f"FIX · {self.blocking.name}#1 · unresolved · Data / scope says 5 documents, "
            f"the run read 3\n\n{self.clean}"
        )
        assert self.record is not None
        carried = [
            f
            for f in findings.read(self.record).findings
            if f.carries == f"{self.blocking.name}#1"
        ]
        self.assertEqual([(f.grade, f.status) for f in carried], [("BLOCKER", "open")])
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertEqual(rc, 1, out)

    def test_writing_the_report_fields_leaves_the_audit_standing(self):
        """The twin of the binding: the Conclusion and the adoption's own
        lines are not bound, so the usual audit-then-adopt order holds."""
        self.describe(self.RIGHT)
        rc, out, _ = self.analysis(self.clean)
        self.lab.fill(
            self.protocol, "Conclusion=Three documents hold 3.0 lines on average."
        )
        records = self.records()
        rc, out = self.lab.adopt(self.protocol, self.run_a)
        self.assertNotIn("no analysis audit saw the area as it is now", out)
        self.assertEqual(self.records(), records)


class DataCounts(unittest.TestCase):
    """The counts of Data / scope come from the preparation run, through the
    real commands: the stamped 00_prepare.py records them, `protocol-fill
    --data-counts` writes them as the field's end, finalize holds that part
    to the run. Fifth SAB-like draw, 2026-10-28: two agents typed counts the
    data did not hold after a prepare script that printed the total alone.
    The twin: a count typed over the written part is held."""

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

    def test_a_count_typed_over_the_written_part_is_held(self):
        self.lab.fill(
            self.protocol, "Data / scope=data/raw/points.jsonl by 00_prepare.py"
        )
        self.assertEqual(self.counts()[0], 0)
        typed = self.data_scope().replace("12 labelled", "10 labelled")
        self.lab.fill(self.protocol, "--force", f"Data / scope={typed}")
        rc, out = self.finalized()
        self.assertEqual(rc, 1, out)
        self.assertIn("the counts differ from what prepare run", out)
        self.assertIn("--data-counts", out)
        self.assertEqual(self.counts()[0], 0)  # written again from the run
        rc, out = self.finalized()
        self.assertNotIn("the counts differ", out)

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
            shown_sha=shown_sha(self.area, self.area / "runs" / self.run_id), registration=registration_of(self.area),)  # fmt: skip

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
        # to this state, passes once a second auditor upholds the dismissal
        # (a dismissed BLOCKER owes a review, 2026-10-28)
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("decided `fixed` in the state audited", out)
        rc, out = self._decide(
            record, "dismissed", "the gold codes the prompt's three cases after all"
        )
        self.assertEqual(rc, 0, out)
        rc, out = self._report_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("`dismissed` on a BLOCKER not reviewed", out)
        rc, out = self._review(record)
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
            shown_sha=shown_sha(self.area, self.area / "runs" / self.run_id), registration=registration_of(self.area),)  # fmt: skip
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
