"""The report review's bundle: every run of the area in one line each
(`runs_text`), so a search the report keeps silent about is visible to the
reviewer — the adopted run's metrics alone show none of it."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit.formats.runs import run_dirs
from labkit.formats.evidence import read_evidence
from labkit.checks import report_review_inputs
from labkit.formats.area_state import state_of
from protocol_fixture import (
    C1_BLOCK,
    C1_PROSE,
    PID,
    completed_run,
    head,
    scope_file,
)


def _settings_of(run: Path, **config: object) -> None:
    cfg_file = run / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    cfg["config"] = config
    cfg_file.write_text(json.dumps(cfg), encoding="utf-8")


class RunsText(unittest.TestCase):
    def _area(self) -> Path:
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        area.mkdir(parents=True)
        scope_file(area)
        (area / "PROTOCOL-x.md").write_text(
            head(repeat_cost="low", promises=C1_BLOCK) + C1_PROSE, encoding="utf-8"
        )
        return area

    def test_every_run_is_a_line_with_its_settings_against_the_adopted(self):
        """Three measurements under one protocol, the best adopted: the
        reviewer sees the setting that varies across the protocol's runs on every line,
        the score, and a probe of another protocol as what it is."""
        area = self._area()
        a = completed_run(area, "2026-01-01T00-00-01_a", metrics={"score": 0.84})
        b = completed_run(area, "2026-01-01T00-00-02_b", metrics={"score": 0.86})
        c = completed_run(
            area, "2026-01-01T00-00-03_c", pid="p-other", run_kind="probe"
        )
        _settings_of(a, estimator="rf", seed=0)
        _settings_of(b, estimator="lr", seed=0)
        _settings_of(c, estimator="lr", seed=0)
        text = report_review_inputs.runs_text(
            run_dirs(area), PID, b.name, set(), {a.name}
        )
        lines = text.split("\n")
        self.assertEqual(len(lines), 3, text)
        self.assertIn(
            f"{a.name} · completed · measurement · this protocol · cited · git g · "
            f'01_measure.py · settings varying across this protocol\'s measurements: estimator="rf" · '
            "metrics: n=1, score=0.84",
            lines[0],
        )
        self.assertIn(
            'adopted · git g · 01_measure.py · settings varying across this protocol\'s measurements: estimator="lr"',
            lines[1],
        )
        self.assertIn(
            "probe · bound to p-other · not in the report · git g · 01_measure.py · no metrics.json",
            lines[2],
        )

    def test_an_absent_setting_is_not_one_set_to_null(self):
        """`{}` and `{"random_state": null}` read as different settings on
        the lines: compared as `c.get(k)`, both would read `null`, and the
        difference would vanish."""
        area = self._area()
        a = completed_run(area, "2026-01-01T00-00-01_a")
        b = completed_run(area, "2026-01-01T00-00-02_b")
        _settings_of(a)
        _settings_of(b, random_state=None)
        lines = report_review_inputs.runs_text(
            run_dirs(area), PID, b.name, set(), set()
        ).split("\n")
        self.assertIn("random_state=absent", lines[0])
        self.assertIn("random_state=null", lines[1])

    def test_an_unreadable_run_and_a_missing_metrics_file_stay_in_the_list(self):
        area = self._area()
        bad = completed_run(area, "2026-01-01T00-00-01_bad", metrics=None)
        (bad / "config.json").write_text("{not json", encoding="utf-8")
        none = completed_run(area, "2026-01-01T00-00-02_n", metrics=None)
        text = report_review_inputs.runs_text(run_dirs(area), PID, None, set(), set())
        lines = text.split("\n")
        self.assertTrue(lines[0].startswith(f"{bad.name} · unreadable · "), lines[0])
        self.assertIn(
            f"{none.name} · corrupt · measurement · this protocol · not in the report",
            lines[1],
        )
        self.assertIn(
            "settings varying across this protocol's measurements: none · no metrics.json",
            lines[1],
        )

    def test_no_runs_directory_is_said(self):
        area = self._area()
        self.assertEqual(
            report_review_inputs.runs_text(run_dirs(area), PID, None, set(), set()),
            "no runs",
        )

    def test_the_bundle_carries_the_runs_before_the_audits(self):
        area = self._area()
        completed_run(area, "2026-01-01T00-00-01_a", metrics={"score": 0.84})
        report = area.parent.parent / "REPORT.md"
        report.write_text("# Report\n", encoding="utf-8")
        proto = area / "PROTOCOL-x.md"
        pieces = report_review_inputs.review_pieces(
            area,
            report,
            "# Report\n",
            proto,
            proto.read_text(encoding="utf-8"),
            [],
            state_of(area),
            read_evidence(area, staged=False),
        )
        labels = [label for label, _ in pieces]
        self.assertEqual(labels[-2:], ["RUNS", "AUDITS"], labels)
        self.assertIn("2026-01-01T00-00-01_a · completed", dict(pieces)["RUNS"])

    def _pieces(self, area: Path, text: str) -> dict[str, str]:
        report = area.parent.parent / "REPORT.md"
        report.write_text(text, encoding="utf-8")
        proto = area / "PROTOCOL-x.md"
        return dict(
            report_review_inputs.review_pieces(
                area,
                report,
                text,
                proto,
                proto.read_text(encoding="utf-8"),
                [],
                state_of(area),
                read_evidence(area, staged=False),
            )
        )

    def test_another_protocols_result_block_is_named_as_its_result(self):
        """A report shared by a handed-over predecessor and its successor
        carries the successor's result block: the predecessor's reviewer is
        told whose result it is and that report-check holds it against that
        protocol, so it does not read the successor's number as one this
        protocol presents unadopted (usage round 24, replay case 3). Its own
        block is not listed there."""
        area = self._area()
        own = completed_run(area, "2026-01-01T00-00-01_a")
        other = "2026-01-01T00-00-09_z"
        text = (
            "# Report\n\n"
            f"<!-- labkit result: experiments/02-y/PROTOCOL-y.md run {other} "
            "(protocol-fill --into; edit the protocol, not this block) -->\n"
            "kept number: n = 3 documents\n"
            "<!-- /labkit result -->\n\n"
            f"<!-- labkit result: experiments/01-x/PROTOCOL-x.md run {own.name} "
            "(protocol-fill --into; edit the protocol, not this block) -->\n"
            "kept number: n = 1\n"
            "<!-- /labkit result -->\n"
        )
        other_results = self._pieces(area, text)["OTHER PROTOCOLS' RESULTS"]
        self.assertIn(
            f"lines 3–5: experiments/02-y/PROTOCOL-y.md, run {other}", other_results
        )
        self.assertNotIn(own.name, other_results)

    def test_the_twin_a_report_of_its_own_blocks_reads_as_before(self):
        """No block of another protocol: no piece is added, so the review's
        fingerprint of such a report is the one it had."""
        area = self._area()
        self.assertNotIn("OTHER PROTOCOLS' RESULTS", self._pieces(area, "# Report\n"))

    def _computed_from(self, area: Path, source: str) -> Path:
        """Run c of the protocol, adopted, whose one input SOURCE wrote."""
        c = completed_run(area, "2026-01-01T00-00-05_cc")
        cfg_file = c / "config.json"
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        cfg["data"] = {
            "items": {
                "path": "out.jsonl",
                "sha256": "ab" * 8,
                "rows": 1,
                "origin_run": source,
                "origin_chosen": False,
                "origin_unreadable_runs": [],
            }
        }
        cfg_file.write_text(json.dumps(cfg), encoding="utf-8")
        (area / "PROTOCOL-x.md").write_text(
            head(repeat_cost="low", promises=C1_BLOCK, result=c.name) + C1_PROSE,
            encoding="utf-8",
        )
        return c

    def test_a_source_of_the_adopted_run_is_named_as_its_input(self):
        """The adopted run computes from another run's output: the reviewer
        is told that run is an input of the adopted number, not a result,
        so a conclusion the report draws about it on its own is a claim."""
        area = self._area()
        a0 = completed_run(area, "2026-01-01T00-00-01_aa", pid="p-other")
        c = self._computed_from(area, a0.name)
        sources = self._pieces(area, "# Report\n")["SOURCES OF THE ADOPTED RUN"]
        self.assertIn(f"run {a0.name} (protocol p-other)", sources)
        self.assertIn(f"an input of adopted run {c.name}", sources)
        self.assertIn("not a result", sources)

    def test_the_twin_an_adopted_run_without_sources_reads_as_before(self):
        area = self._area()
        c = completed_run(area, "2026-01-01T00-00-05_cc")
        (area / "PROTOCOL-x.md").write_text(
            head(repeat_cost="low", promises=C1_BLOCK, result=c.name) + C1_PROSE,
            encoding="utf-8",
        )
        self.assertNotIn("SOURCES OF THE ADOPTED RUN", self._pieces(area, "# Report\n"))


if __name__ == "__main__":
    unittest.main()
