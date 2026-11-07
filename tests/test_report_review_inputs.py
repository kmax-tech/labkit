"""The report review's bundle: every run of the area in one line each
(`runs_text`), so a search the report keeps silent about is visible to the
reviewer — the adopted run's metrics alone show none of it."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit.checks import report_review_inputs
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
        text = report_review_inputs.runs_text(area, PID, b.name, set(), {a.name})
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
        lines = report_review_inputs.runs_text(area, PID, b.name, set(), set()).split(
            "\n"
        )
        self.assertIn("random_state=absent", lines[0])
        self.assertIn("random_state=null", lines[1])

    def test_an_unreadable_run_and_a_missing_metrics_file_stay_in_the_list(self):
        area = self._area()
        bad = completed_run(area, "2026-01-01T00-00-01_bad", metrics=None)
        (bad / "config.json").write_text("{not json", encoding="utf-8")
        none = completed_run(area, "2026-01-01T00-00-02_n", metrics=None)
        text = report_review_inputs.runs_text(area, PID, None, set(), set())
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
            report_review_inputs.runs_text(area, PID, None, set(), set()), "no runs"
        )

    def test_the_bundle_carries_the_runs_before_the_audits(self):
        area = self._area()
        completed_run(area, "2026-01-01T00-00-01_a", metrics={"score": 0.84})
        report = area.parent.parent / "REPORT.md"
        report.write_text("# Report\n", encoding="utf-8")
        proto = area / "PROTOCOL-x.md"
        pieces = report_review_inputs.review_pieces(
            area, report, "# Report\n", proto, proto.read_text(encoding="utf-8"), []
        )
        labels = [label for label, _ in pieces]
        self.assertEqual(labels[-2:], ["RUNS", "AUDITS"], labels)
        self.assertIn("2026-01-01T00-00-01_a · completed", dict(pieces)["RUNS"])


if __name__ == "__main__":
    unittest.main()
