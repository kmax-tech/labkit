"""labkit-audit --mode clarity (2026-10-09): the code-clarity agent's area
mode as a command. The model call is faked; tested is what the reader gets
to read (README, protocol, measure script — no lib, no standard), the
verdict parsing and the exit-code contract: 1 on any finding, 0 on none,
2 on no reading.

    .venv/bin/python -m pytest tests/test_audit_clarity.py
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit import audit

PROTOCOL = "- **Protocol id:** p-0123456789abcdef\n## Summary\nQuestion †: q\n"
SCRIPT = '"""Does x?"""\nimport scoring\n\ndef evaluate_rows(rows):\n    return {}\n'
README = "# 01-x\n\nWas `evaluate_rows()` liefert: `margin` aus `MeasureConfig`.\n"
CLEAN = "verdict: 0 findings"
ONE = (
    "RULE 9 · experiments/01-x/README.md:3 · the README names `margin`, the "
    "script has none · rewrite from the [[promise]] sentences\n"
    "verdict: 1 findings (1 would be answered wrong)"
)


def area_with(readme: bool = True) -> Path:
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    area = repo / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "01_measure.py").write_text(SCRIPT, encoding="utf-8")
    (area / "PROTOCOL-x.md").write_text(PROTOCOL, encoding="utf-8")
    if readme:
        (area / "README.md").write_text(README, encoding="utf-8")
    (repo / "lib").mkdir()
    (repo / "lib" / "scoring.py").write_text("X = 0.7\n", encoding="utf-8")
    return area


def run(area: Path, answer: str) -> tuple[int, str, str, list[str]]:
    sent: list[str] = []

    def fake(alias, prompt, **kw):
        sent.append(prompt)
        return answer

    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch.object(audit.llm, "complete", fake),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        rc = audit.main([str(area), "--mode", "clarity"])
    return rc, out.getvalue(), err.getvalue(), sent


class Clarity(unittest.TestCase):
    def test_the_reader_gets_readme_protocol_and_script_only(self) -> None:
        rc, _, _, sent = run(area_with(), CLEAN)
        self.assertEqual(rc, 0)
        prompt = sent[0]
        self.assertIn("MODE: clarity", prompt)
        self.assertIn("# code-clarity", prompt)
        self.assertNotIn("<!--", prompt)  # the provenance comment is stripped
        files = [
            ln.removeprefix("===== FILE: ").removesuffix(" =====")
            for ln in prompt.splitlines()
            if ln.startswith("===== FILE: ")
        ]
        self.assertEqual(
            files,
            [
                "experiments/01-x/README.md",
                "experiments/01-x/PROTOCOL-x.md",
                "experiments/01-x/scripts/01_measure.py",
            ],
        )  # the reading order; no lib/scoring.py, no standard

    def test_a_finding_is_exit_1_and_counted(self) -> None:
        rc, out, err, _ = run(area_with(), ONE)
        self.assertEqual(rc, 1)
        self.assertIn("RULE 9", out)
        self.assertIn("1 finding(s), 1 would be answered wrong", err)
        self.assertNotIn("stamp:", err)  # a reading, not a stamp

    def test_no_readme_is_no_reading(self) -> None:
        rc, _, err, sent = run(area_with(readme=False), CLEAN)
        self.assertEqual(rc, 2)
        self.assertIn("no README.md", err)
        self.assertEqual(sent, [])

    def test_an_unknown_alias_is_no_reading_not_a_traceback(self) -> None:
        area = area_with()
        err = io.StringIO()
        with (
            mock.patch.object(
                audit.llm,
                "complete",
                mock.Mock(side_effect=KeyError("model alias 'x' not in models.toml")),
            ),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(err),
        ):
            rc = audit.main([str(area), "--mode", "clarity", "--model", "x"])
        self.assertEqual(rc, 2)
        self.assertIn("model alias 'x' not in models.toml", err.getvalue())

    def test_a_report_without_verdict_is_no_reading(self) -> None:
        rc, _, err, _ = run(area_with(), "looks fine")
        self.assertEqual(rc, 2)
        self.assertIn("no readable `verdict:`", err)

    def test_parse_reads_the_last_verdict_and_the_rule_lines(self) -> None:
        text = (
            "verdict: 3 findings (2 would be answered wrong)\n"
            "RULE 12 · a.py:1 · x · y\n"
            "- **RULE 14** · b.md:2 · x · y\n"
            "verdict: 2 findings (1 would be answered wrong)\n"
        )
        r = audit.parse_clarity(text)
        self.assertEqual((r["findings"], r["wrong"]), (2, 1))
        self.assertEqual([n for n, _ in r["lines"]], [12, 14])
        self.assertEqual(audit.parse_clarity("verdict: 0 findings")["wrong"], 0)


if __name__ == "__main__":
    unittest.main()
