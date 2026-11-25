"""Every run of a protocol shown to its analysis audit (`protocol_runs`),
on real commands in a stamped count lab: the runs with their state,
result, step, registration and code then; a cut diff marked unread and the
full one printed by `labkit-run-diff`; a new run of the protocol staling the
audit. For a computation run C, the runs of each source protocol beside its
own (the plan's example A0/A1, docs/notes/2026-11-14-exploratory-workflow-plan.md,
"The other runs shown to the auditor"): A1 measured after C's audit stales
it; a run of a protocol C draws nothing from does not.
"""

from __future__ import annotations

import contextlib
import io
import re
import unittest
from pathlib import Path
from unittest import mock

import pytest

import test_end_to_end as e2e
from test_origin_scenario import _pointed

from labkit.checks import protocol_runs
from labkit.formats import protocol_block, runs
from labkit.gates import report_check
from labkit.tools import run_diff

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

FILTER = "Exclusions / filters=hidden entries, nested directories and empty documents"
WHY = "A counted empty documents as zero-line rows"
STALE = "no analysis audit saw the area as it is now"


def piece(prompt: str, label: str) -> str:
    """The text of the prompt's piece LABEL (its `===== LABEL` line), up to
    the next piece."""
    start = prompt.index(f"===== {label}") + len("===== ")
    end = re.search(r"\n===== ", prompt[start + len(label) :])
    return prompt[start : start + len(label) + end.start()] if end else prompt[start:]


def stale_lines(out: str) -> list[str]:
    """The BLOCKER lines of report-check output that name a stale analysis audit."""
    return [ln for ln in out.splitlines() if "BLOCKER" in ln and STALE in ln]


class OwnProtocol(e2e.CountCommands):
    """Run A measured; step B on A filters empty documents, declared, and
    B's code carries one more field in the working tree (its
    uncommitted.patch). B is the answering run the audit reads."""

    def setUp(self) -> None:
        super().setUp()
        self.run_a = self.measure()
        self.lab.fill(self.protocol, "--force", FILTER)
        self.lab.fill(
            self.protocol,
            "--builds-on",
            self.run_a,
            "--step-id",
            "filter",
            "--occasion",
            "observation",
            "--why",
            WHY,
        )
        self.lab.commit("step B on A")
        self.change_code()
        self.run_b = self.measure()
        self.pid = protocol_block.head(self.protocol.read_text(encoding="utf-8")).id
        self.label = f"{protocol_runs.OWN_LABEL}{self.pid}"

    def audited_prompt(self) -> str:
        rc, out, prompt = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        return prompt

    def test_every_run_is_shown_with_its_step_text_and_code(self):
        prompt = self.audited_prompt()
        shown = piece(prompt, self.label)
        self.assertIn(
            f"- {self.run_a}: completed, measurement, first measurement", shown
        )
        self.assertIn(
            f"- {self.run_b}: completed, measurement, the run compared", shown
        )
        self.assertIn(f'Step "filter" on run {self.run_a} (observation): {WHY}', shown)
        self.assertIn("declared change: Exclusions / filters", shown)
        # A, compared with B: its text lacks the filter, its code the field
        a_lines = shown.split(f"- {self.run_a}:")[1].split("\n- ")[0]
        self.assertIn("differs — Exclusions / filters", a_lines)
        diff_label = f"{protocol_runs.DIFF_LABEL}{self.run_b} → {self.run_a}"
        self.assertIn(f"the whole diff: under {diff_label}", a_lines)
        self.assertIn('"bytes"', piece(prompt, diff_label))
        self.assertIn("with its uncommitted.patch", shown)  # B's code then

    def test_a_run_that_did_not_complete_is_listed_with_its_result(self):
        late = self.measure()
        (self.area / "runs" / late / runs.COMPLETION_FILE).unlink()
        shown = piece(self.audited_prompt(), self.label)
        lines = shown.split(f"- {late}:")[1].split("\n- ")[0]
        self.assertIn("unfinalized", lines)
        self.assertIn("result: {", lines)
        self.assertIn("code: not compared — the run did not complete", lines)

    def test_a_diff_past_the_budget_is_marked_and_the_command_prints_all(self):
        with (
            mock.patch.object(protocol_runs, "DIFF_BUDGET", 10),
            mock.patch.object(protocol_runs, "DIFF_SHOW_LINES", 3),
        ):
            prompt = self.audited_prompt()
        shown = piece(prompt, self.label)
        self.assertIn("[not shown in full:", shown)
        self.assertIn("3 of", shown)
        self.assertIn("the rest unread — a judgement that needs it stays open", shown)
        self.assertNotIn(f"===== {protocol_runs.DIFF_LABEL}{self.run_b}", prompt)
        command = f"labkit-run-diff {self.area.relative_to(self.lab.root).as_posix()}"
        self.assertIn(f"`{command} {self.run_b} {self.run_a}` prints all", shown)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = run_diff.main([str(self.area), self.run_b, self.run_a])
        self.assertEqual(rc, 0)
        self.assertIn('"bytes"', out.getvalue())
        self.assertGreater(len(out.getvalue().splitlines()), 3 + 2)

    def test_runs_of_one_step_stand_under_one_heading(self):
        """Case 23: a further run of the step reuses the step's reason."""
        again = self.measure()
        shown = piece(self.audited_prompt(), self.label)
        self.assertEqual(shown.count('Step "filter"'), 1, shown)
        step = shown.split('Step "filter"')[1]
        self.assertIn(f"- {self.run_b}:", step)
        self.assertIn(f"- {again}:", step)

    def test_a_new_run_beside_the_adopted_one_stales_its_audit(self):
        """B adopted stays the answering run; D measured beside it widens
        what B was chosen from, so B's audit is owed again."""
        self.audited_prompt()
        rc, out = self.lab.adopt(self.protocol, self.run_b)
        self.assertEqual(rc, 0, out)
        self.assertEqual(stale_lines(_verdict(self.area, self.protocol)[1]), [])
        # D, same code, writes the file B wrote; B's bytes are put back, so
        # neither the code nor B's rows move and only the list of runs grew
        (out,) = runs.read_outputs(self.area / "runs" / self.run_b) or []
        rows_b = (self.lab.root / out.path).read_bytes()
        self.measure()
        (self.lab.root / out.path).write_bytes(rows_b)
        rc, out = _verdict(self.area, self.protocol)
        self.assertNotEqual(stale_lines(out), [], out)
        self.assertIn(f"run {self.run_b}", stale_lines(out)[0])
        self.audited_prompt()
        self.assertEqual(stale_lines(_verdict(self.area, self.protocol)[1]), [])


#: a helper table the code grows by, ahead of the decisive change, so that
#: change stands past the excerpt's lines in the diff
PADDING = "\n".join(
    ["SIZES = ("] + [f"    {n},  # size class {n}" for n in range(120)] + [")"]
)
#: the decisive change: documents of one line are dropped, the mean rises
KEEP_ALL = "    return [p.name for p in visible(SOURCE)]"
DROP_SHORT = (
    "    return [p.name for p in visible(SOURCE) "
    'if (SOURCE / p.name).read_text(encoding="utf-8").count("\\n") > 1]'
)


class ChosenRun(e2e.CountCommands):
    """The selection the audit controls: run A counts every document; run
    B's code, changed without a step, grows by a helper table and drops the
    one-line documents — the change that moves the number stands past line
    DIFF_SHOW_LINES of the diff. B is the run the agent adopts. Whether a
    model would judge the choice is not tested; that the evidence reaches it is.
    Its auditor is shown A's result beside B's and the whole diff, the
    decisive line in it; past the budget, the twin shows that line absent and
    the diff marked not shown in full."""

    def setUp(self) -> None:
        super().setUp()
        self.run_a = self.measure()
        script = self.area / "scripts" / "01_measure.py"
        e2e._replace(
            script,
            [
                ('COUNT_FIELD = "lines"', f'COUNT_FIELD = "lines"\n{PADDING}'),
                (KEEP_ALL, DROP_SHORT),
            ],
        )
        self.lab.commit("count only documents of more than one line")
        self.run_b = self.measure()
        # as the diff from B's code to A's shows it: B's line taken out
        self.decisive = f"-{DROP_SHORT}"

    def test_the_decisive_change_past_the_excerpt_reaches_the_auditor(self):
        rc, out, prompt = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        label = f"{protocol_runs.DIFF_LABEL}{self.run_b} → {self.run_a}"
        diff = piece(prompt, label)
        rows = diff.splitlines()
        (at,) = [n for n, row in enumerate(rows) if self.decisive in row]
        self.assertGreater(at, protocol_runs.DIFF_SHOW_LINES)
        pid = protocol_block.head(self.protocol.read_text(encoding="utf-8")).id
        listed = piece(prompt, f"{protocol_runs.OWN_LABEL}{pid}")
        a_lines = listed.split(f"- {self.run_a}:")[1].split("\n- ")[0]
        self.assertIn('"lines_mean"', a_lines)  # the result B was preferred to
        self.assertIn(f"the whole diff: under {label}", a_lines)
        # the agent adopts the run it chose; the audit that saw both stands
        rc, out = self.lab.adopt(self.protocol, self.run_b)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), self.run_b)

    def test_past_the_budget_the_decisive_change_is_named_unread(self):
        with mock.patch.object(protocol_runs, "DIFF_BUDGET", 100):
            rc, out, prompt = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        self.assertNotIn(self.decisive, prompt)
        self.assertIn("[not shown in full:", prompt)
        self.assertIn("a judgement that needs it stays open", prompt)


#: a shared table the code of run B adds beside the decisive change: it
#: makes the whole diff larger than the patched budget, the script's
#: section alone smaller
LARGE_TABLE = "\n".join(
    ["WEIGHTS = ("] + [f"    {n},  # weight class {n}" for n in range(2000)] + [")"]
)
#: the patched budget for diffs: between the script's section and the whole
REQUEST_BUDGET = 20_000


class RequestedDiff(e2e.CountCommands):
    """The way to evidence past the budget, on real commands: run B's code
    adds a large table to `lib/` and, in the measuring script past the
    excerpt, drops the one-line documents. The first audit is shown the
    diff cut; its auditor asks for the script's section with a `diff:`
    check. Decided, the request stales that audit, the follow-up is shown
    the section whole as a REQUESTED DIFF piece bound in its digest, and
    its record covers the state. Twin: a section past the budget stays
    `not shown:`, and the follow-up's `resolved` is refused while
    `not_assessable` stands. Every command runs under one patched budget,
    report-check's recomputed digest among them."""

    def setUp(self) -> None:
        super().setUp()
        budget = mock.patch.object(protocol_runs, "DIFF_BUDGET", REQUEST_BUDGET)
        budget.start()
        self.addCleanup(budget.stop)
        self.run_a = self.measure()
        script = self.area / "scripts" / "01_measure.py"
        e2e._replace(
            script,
            [
                ('COUNT_FIELD = "lines"', f'COUNT_FIELD = "lines"\n{PADDING}'),
                (KEEP_ALL, DROP_SHORT),
            ],
        )
        table = self.lab.root / "lib" / "weights.py"
        table.parent.mkdir(exist_ok=True)
        table.write_text(LARGE_TABLE + "\n", encoding="utf-8")
        self.lab.commit("a shared weight table; count only longer documents")
        self.run_b = self.measure()
        self.rel = self.area.relative_to(self.lab.root).as_posix()
        self.path = f"{self.rel}/scripts/01_measure.py"
        self.check = f"diff:{self.run_b}..{self.run_a}:{self.path}"
        self.label = (
            f"{protocol_runs.REQUEST_LABEL}{self.run_b} → {self.run_a}, {self.path}"
        )
        self.decisive = f"-{DROP_SHORT}"

    def asked(self, check: str | None = None) -> Path:
        """The first audit, its BLOCKER asking with CHECK (the script's
        section when None); the record it wrote."""
        answer = (
            f"BLOCKER · {self.path}:1 · undetermined · B's code differs from "
            f"A's past the excerpt shown; the change that moves lines_mean may "
            f"stand there · lines_mean of B against A · new class · show the "
            f"omitted lines · check: {check or self.check} — confirms if a filter on the "
            f"documents stands there, clears if only the table does\n\n"
            f"{self.clean.replace('verdict: 0 blockers', 'verdict: 1 blockers')}"
        )
        _, out, prompt = self.analysis(answer)
        self.assertIsNotNone(self.record, out)
        self.assertIn("[not shown in full:", prompt)
        self.assertIn(f"check: diff:{self.run_b}..{self.run_a}[:<path>]", prompt)
        self.assertNotIn(self.decisive, prompt)
        self.assertNotIn(f"===== {self.label}", prompt)
        assert self.record is not None
        return self.record

    def test_the_section_asked_for_reaches_the_follow_up_and_binds_it(self):
        first = self.asked()
        # undecided, the request moves nothing: the audit that asked covers
        self.assertEqual(stale_lines(_verdict(self.area, self.protocol)[1]), [])
        said = self.decide(
            first, 1, "fixed", "the omitted section is asked of the follow-up"
        )
        self.assertIn("nothing to build or measure", said)
        # decided, the request enters the state: the follow-up is owed, no run
        _, out = _verdict(self.area, self.protocol)
        self.assertNotEqual(stale_lines(out), [], out)
        self.assertNotIn("then a new run", out)

        verdict = (
            f"FIX · {first.name}#1 · unresolved · implementation · the "
            f"requested diff shows B dropping the one-line documents\n\n{self.clean}"
        )
        _, out, prompt = self.analysis(verdict)
        self.assertIsNotNone(self.record, out)  # held by the carried finding
        section = piece(prompt, self.label)
        self.assertIn(self.decisive, section)
        self.assertNotIn("weight class", section)  # the section, not the table
        # the piece, not the instructions' mention of its label
        earlier = prompt.split(
            "===== EARLIER DECIDED BLOCKERS AND CORRECTIONS =====\n"
        )[-1]
        self.assertIn(f"required check `{self.check}`", earlier)
        self.assertIn(f"shown above under `{self.label}`", earlier)
        # the follow-up's record covers the state after its own verdict
        self.assertEqual(stale_lines(_verdict(self.area, self.protocol)[1]), [])
        # the carried finding asks nothing again
        self.assertNotIn(f"check: {self.check}", out)
        # judged, the section takes no more room: a later audit is shown the
        # verdict and the text's digest, not the text
        _, out, prompt = self.analysis(self.clean)
        judged = piece(prompt, self.label).split("\n", 1)[1]
        self.assertTrue(
            judged.startswith(f"judged: {first.name}#1 found `unresolved`"), judged
        )
        self.assertIn("is not shown again", judged)
        self.assertNotIn(self.decisive, judged)

    def test_a_section_judged_resolved_leaves_the_follow_up_covering(self):
        first = self.asked()
        self.decide(first, 1, "fixed", "the omitted section is asked of the follow-up")
        resolved = (
            f"FIX · {first.name}#1 · resolved · the section shows the filter is "
            f"the declared one\n\n{self.clean}"
        )
        rc, out, prompt = self.analysis(resolved)
        self.assertEqual(rc, 0, out)
        self.assertIn(self.decisive, piece(prompt, self.label))
        self.assertEqual(stale_lines(_verdict(self.area, self.protocol)[1]), [])

    def followed(self, first: Path, verdict: str) -> tuple[int, str, str]:
        """FIRST's request decided `fixed`, then the follow-up audit
        answering VERDICT on it: (exit, its output, its prompt)."""
        self.decide(first, 1, "fixed", "the evidence is asked of the follow-up")
        return self.analysis(f"FIX · {first.name}#1 · {verdict}\n\n{self.clean}")

    def test_a_line_range_serves_a_file_past_the_budget(self):
        """The script's section does not fit the budget; the lines of B's
        file around the decisive change do, under a label and a head that
        name the runs, their code then, the side and the lines."""
        script = (self.area / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        k = script.splitlines().index(DROP_SHORT) + 1
        check = f"{self.check}:old:{k}-{k}"
        label = f"{self.label}, old file, lines {k}–{k}"
        with mock.patch.object(protocol_runs, "DIFF_BUDGET", 1_500):
            first = self.asked(check)
            rc, out, prompt = self.followed(
                first, "unresolved · implementation · the lines show the filter"
            )
            self.assertIsNotNone(self.record, out)
            shown = piece(prompt, label)
            self.assertIn(self.decisive, shown)
            self.assertIn(f"+{KEEP_ALL}", shown)  # what A has in its place
            self.assertNotIn("size class", shown)
            self.assertIn(f"{self.run_b}: ", shown)
            self.assertIn(f"lines {k}–{k} of the old file (run {self.run_b})", shown)
            self.assertIn(protocol_runs.RANGE_ONLY, shown)
            self.assertEqual(stale_lines(_verdict(self.area, self.protocol)[1]), [])

    def test_a_run_s_file_as_it_started_reaches_the_follow_up(self):
        """A's script, unchanged by A, as A started from it: numbered, the
        lines asked only — B's later table is not in it."""
        check = f"code:{self.run_a}:{self.path}:1-5"
        label = f"{protocol_runs.CODE_LABEL}{self.run_a}, {self.path}, lines 1–5"
        first = self.asked(check)
        rc, out, prompt = self.followed(first, "resolved · A's head holds no filter")
        self.assertEqual(rc, 0, out)
        shown = piece(prompt, label)
        self.assertIn(f"as run {self.run_a} started from it, lines 1–5 of", shown)
        self.assertIn("\n1: ", shown)
        self.assertNotIn("\n6: ", shown)
        self.assertIn(protocol_runs.RANGE_ONLY, shown)
        self.assertEqual(stale_lines(_verdict(self.area, self.protocol)[1]), [])

    def test_a_run_s_file_whose_version_is_lost_is_never_today_s(self):
        """Run C started from a changed tree, its uncommitted.patch gone:
        its file then cannot be read back, and today's is not shown."""
        script = self.area / "scripts" / "01_measure.py"
        committed = script.read_text(encoding="utf-8")
        script.write_text(committed + "# TODAY_ONLY\n", encoding="utf-8")
        run_c = self.measure()
        (self.area / "runs" / run_c / "uncommitted.patch").unlink()
        script.write_text(committed, encoding="utf-8")
        answer = (
            f"BLOCKER · {self.path}:1 · undetermined · C's code may differ · "
            f"lines_mean of C · new class · show the file · check: "
            f"code:{run_c}:{self.path} — confirms if C's file differs\n\n"
            f"{self.clean.replace('verdict: 0 blockers', 'verdict: 1 blockers')}"
        )
        _, out, _ = self.analysis(answer)
        self.assertIsNotNone(self.record, out)
        assert self.record is not None
        first = self.record
        _, _, prompt = self.followed(first, "not_assessable · not shown")
        told = piece(prompt, f"{protocol_runs.CODE_LABEL}{run_c}, {self.path}")
        self.assertIn("not shown:", told)
        self.assertIn("uncommitted.patch is gone", told)
        self.assertNotIn("TODAY_ONLY", told)
        self.assertNotIn("SOURCE", told)

    def test_a_section_past_the_budget_leaves_the_judgement_open(self):
        first = self.asked()
        self.decide(first, 1, "fixed", "the omitted section is asked of the follow-up")
        with mock.patch.object(protocol_runs, "DIFF_BUDGET", 100):
            resolved = f"FIX · {first.name}#1 · resolved · only the table changed\n\n{self.clean}"
            rc, out, prompt = self.analysis(resolved)
            self.assertNotEqual(rc, 0, out)
            self.assertIsNone(self.record)
            told = piece(prompt, self.label).split("\n", 1)[1]
            self.assertTrue(told.startswith("not shown:"), told)
            # the narrower request it names: one file's lines
            self.assertIn(":<file>:old|new:<from>-<to>`; the files of this", told)
            self.assertIn(self.path, told)
            self.assertIn(f"required check `{self.check}`: not shown", prompt)
            self.assertNotIn(self.decisive, prompt)
            # the same answer but its verdict is recorded: the refusal above
            # was the verdict's, and the finding is carried open
            _, out, _ = self.analysis(resolved.replace("resolved", "not_assessable", 1))
            self.assertIsNotNone(self.record, out)
            self.assertIn(f"carried from {first.name}#1 (not_assessable)", out)


def _verdict(area: Path, protocol: Path) -> tuple[int, str]:
    """report-check on PROTOCOL: (exit, everything it told)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = report_check.protocol_verdict(area, protocol).exit
    return code, out.getvalue()


class SourceProtocol(e2e.CountCommands):
    """The plan's example: measurement protocol M with A0, computation
    protocol P whose run C reads A0's rows, a third protocol Q in the same
    area that C draws nothing from. C's audit is shown M's runs compared
    with A0; A1 in M stales it, a run of Q does not."""

    def run_script(self, script: str) -> str:
        """SCRIPT of the area run in a later second than every run it holds
        (`Lab.measure`); its run id."""
        return self.lab.measure(self.area, script)

    def setUp(self) -> None:
        super().setUp()
        text = self.protocol.read_text(encoding="utf-8")
        self.mid = protocol_block.head(text).id
        assert self.mid is not None
        self.computed = self.area / "PROTOCOL-compared.md"
        self.computed.write_text(
            text.replace(self.mid, "p-0123456789abcdef"), encoding="utf-8"
        )
        self.other = self.area / "PROTOCOL-other.md"
        self.other.write_text(text.replace(self.mid, "p-fedcba9876543210"), "utf-8")
        self.a0 = self.run_script("01_measure.py")
        (written,) = runs.read_outputs(self.area / "runs" / self.a0) or []
        measure = self.area / "scripts" / "01_measure.py"
        script = measure.read_text(encoding="utf-8")
        bound = f'"{self.protocol.name}"'
        (self.area / "scripts" / "03_compare.py").write_text(
            _pointed(script.replace(bound, f'"{self.computed.name}"'), written.path),
            encoding="utf-8",
        )
        (self.area / "scripts" / "04_other.py").write_text(
            script.replace(bound, f'"{self.other.name}"').replace(
                '"lines.jsonl"', '"lines-other.jsonl"'
            ),
            encoding="utf-8",
        )
        # A1 writes its own file: a rerun into A0's would change what C read
        measure.write_text(
            script.replace('"lines.jsonl"', '"lines-again.jsonl"'), encoding="utf-8"
        )
        self.lab.commit("the computation and a protocol C draws nothing from")
        self.c = self.run_script("03_compare.py")
        self.label = f"{protocol_runs.SOURCE_LABEL}{self.mid}"

    def stale(self) -> list[str]:
        return stale_lines(_verdict(self.area, self.computed)[1])

    def test_c_sees_the_source_protocols_runs_and_a1_stales_it(self):
        _, _, prompt = self.analysis(self.clean, self.computed)
        shown = piece(prompt, self.label)
        self.assertIn(f"compared with run {self.a0}", shown)
        self.assertIn(f"- {self.a0}: completed, measurement", shown)
        self.assertIn("a source of the run audited", shown)
        self.assertIn(f"{protocol_runs.OWN_LABEL}p-0123456789abcdef", prompt)
        self.assertNotIn("p-fedcba9876543210", prompt)
        self.assertEqual(self.stale(), [])

        a1 = self.run_script("01_measure.py")
        self.assertNotEqual(self.stale(), [])
        _, _, prompt = self.analysis(self.clean, self.computed)
        a1_lines = piece(prompt, self.label).split(f"- {a1}:")[1].split("\n- ")[0]
        self.assertIn("completed, measurement", a1_lines)
        # its code then, against A0's
        diff = piece(prompt, f"{protocol_runs.DIFF_LABEL}{self.a0} → {a1}")
        self.assertIn("lines-again.jsonl", diff)
        self.assertEqual(self.stale(), [])

    def test_a_run_of_a_protocol_c_draws_nothing_from_stales_nothing(self):
        self.analysis(self.clean, self.computed)
        self.assertEqual(self.stale(), [])
        self.run_script("04_other.py")
        self.assertEqual(self.stale(), [])


if __name__ == "__main__":
    unittest.main()
