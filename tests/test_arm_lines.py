"""Arm lines in `Model / tool` (0.73.1): a protocol that compares two
profiles names each with file, fingerprint and model alias; finalize holds
the line to the answering run and warns on what the run did not record.

    .venv/bin/python -m pytest tests/test_arm_lines.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit.checks import run_record_check

SHA_B, SHA_A = "bcec0c37236d", "1d4c79af596a"
TEXT = (
    "- **Model / tool:** alias `gpt-oss-20b-leguin`\n"
    f"  Arm `before`: register/profiles/b.toml @ {SHA_B}, model=gpt-oss-20b-leguin\n"
    f"  Arm `after`: register/profiles/a.toml @ {SHA_A}, model=gpt-oss-20b-leguin\n"
)


def _repo(
    d: str, *, profiles: tuple[str, ...], fingerprints: dict
) -> tuple[Path, Path]:
    root = Path(d)
    (root / ".git").mkdir()
    for p in profiles:
        (root / "register" / "profiles").mkdir(parents=True, exist_ok=True)
        (root / "register" / "profiles" / p).write_text("x = 1\n", encoding="utf-8")
    area = root / "experiments" / "01-x"
    run = area / "runs" / "2026-10-09T10-00-00_aaaa"
    run.mkdir(parents=True)
    (run / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "config": {
                    "judge": {"alias": "gpt-oss-20b-leguin", "model": "gpt-oss:20b"},
                    "fingerprints": fingerprints,
                },
            }
        ),
        encoding="utf-8",
    )
    return area, run


class ArmLines(unittest.TestCase):
    def test_twin_named_arms_the_run_recorded_are_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area, run = _repo(
                d,
                profiles=("a.toml", "b.toml"),
                fingerprints={"before": SHA_B, "after": SHA_A},
            )
            self.assertEqual(run_record_check.arm_findings(TEXT, area, run), [])

    def test_a_fingerprint_the_run_did_not_record_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area, run = _repo(
                d,
                profiles=("a.toml", "b.toml"),
                fingerprints={"before": SHA_B, "after": "0000deadbeef"},
            )
            got = run_record_check.arm_findings(TEXT, area, run)
            self.assertEqual(len(got), 1)
            self.assertIn(
                f"arm `after`: the protocol names fingerprint {SHA_A}", got[0]
            )

    def test_a_missing_profile_and_an_unrecorded_alias_are_named(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area, run = _repo(
                d, profiles=("b.toml",), fingerprints={"before": SHA_B, "after": SHA_A}
            )
            text = TEXT.replace("model=gpt-oss-20b-leguin\n", "model=haiku\n", 1)
            got = run_record_check.arm_findings(text, area, run)
            self.assertTrue(
                any("names register/profiles/a.toml, no such file" in g for g in got),
                got,
            )
            self.assertTrue(
                any("arm `before`: the protocol names model=haiku" in g for g in got),
                got,
            )

    def test_no_arm_line_claims_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area, run = _repo(d, profiles=(), fingerprints={})
            self.assertEqual(
                run_record_check.arm_findings(
                    "- **Model / tool:** alias `haiku`\n", area, run
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
