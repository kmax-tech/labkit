"""The executable count walkthrough (`docs/examples/count-walkthrough.sh`)
runs end to end on this labkit and ends where `docs/workflow.md` says it
ends: the number kept, declared, shown in the report, held by
report-check — and a retyped generated number refused twice. The script is
the workflow's example; a step it can no longer take is a drift of the
tools under the text (TODO "Klarheit des Ablaufs", 2026-10-22).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "examples" / "count-walkthrough.sh"
#: the venv this suite runs in (`sys.prefix`, not the interpreter's resolved
#: path, which is pyenv's): its `usability` is the labkit under test
VENV = Path(sys.prefix)


@unittest.skipUnless(
    (VENV / "bin" / "usability").is_file() and shutil.which("git"),
    "needs the suite's venv with labkit's commands, and git",
)
class CountWalkthrough(unittest.TestCase):
    def test_the_walk_ends_where_the_text_says(self):
        work = Path(tempfile.mkdtemp()) / "walk"
        # the walk's own commits are the reader's: in a home without a git
        # identity (a fresh clone) the test supplies one, as a reader would
        who = {"NAME": "walkthrough", "EMAIL": "walkthrough@labkit.invalid"}
        env = {
            **os.environ,
            **{
                f"GIT_{role}_{k}": v
                for role in ("AUTHOR", "COMMITTER")
                for k, v in who.items()
            },
        }
        p = subprocess.run(
            ["sh", str(SCRIPT), str(work), str(VENV)],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        out = p.stdout + p.stderr
        self.assertEqual(p.returncode, 0, out[-4000:])
        for said in (
            "== 1. a lab repo",
            "filled: SOURCE, INPUTS, COUNT_FIELD, METRIC_KEY",
            "== 5. finalize",
            "all clear",
            "- **Recorded results:** mean_docs_per_case = 3.5 (run ",
            "<!-- labkit result: experiments/01-docs-per-case/PROTOCOL-docs-per-case.md run ",
            "refused, as it must be: the block differs from what the protocol renders",
            "refused, as it must be: the Recorded results line differs",
            "== done — the number 3.5 is kept under ",
        ):
            self.assertIn(said, out, said)
        self.assertNotIn("UNEXPECTED", out)
        # the lab it left: the declared run, the record, the block
        lab = work / "lab"
        area = lab / "experiments" / "01-docs-per-case"
        self.assertEqual(len(list((area / "runs").iterdir())), 1)
        self.assertEqual(len(list((area / "audits").glob("*-analysis.toml"))), 1)
        self.assertIn("<!-- /labkit result -->", (lab / "REPORT.md").read_text())


if __name__ == "__main__":
    unittest.main()
