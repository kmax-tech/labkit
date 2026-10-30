"""finalize station 4 (2026-10-05): at repeat_cost = "low" the run must have frozen
its source and every source/output file must be tracked in git; elsewhere
the station is n/a."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import PACKAGE_DIR  # noqa: E402
from labkit.checks import run_record_check  # noqa: E402
from labkit.gates import finalize  # noqa: E402
from labkit.formats import promises, scope_sha  # noqa: E402
from labkit.formats.runs import RECORD_SHA_CHARS  # noqa: E402
from protocol_fixture import run_record, PID, head, scope_file, script_sha_of  # noqa: E402

BODY = """
- **Question / hypothesis:** how many documents per case?
- **Recorded results:** 3.5, run r1
"""
SHORT = "# Experiment protocol: x\n\n" + head(repeat_cost="low", promises=None) + BODY
HIGH = (
    "# Experiment protocol: x\n\n"
    + head(repeat_cost="high", frozen=True, promises=None)
    + BODY
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _recorded(path: Path) -> str:
    """The sha256 prefix outputs.json records for PATH as it is now — the
    registered-outputs station holds the file to it."""
    return scope_sha.file_digest(path)[:RECORD_SHA_CHARS]


def _snapshot(area: Path, protocol: str) -> dict | None:
    """What a run records of the protocol's block — the fixture's scopes name
    the script `scope_file` writes; None for a protocol without tables."""
    block = promises.parse_block(protocol)
    if block is None:
        return None
    scope_file(area)
    return promises.snapshot(block, area)


class Provenance(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q", ".")
        _git(self.repo, "config", "user.email", "t@t")
        _git(self.repo, "config", "user.name", "t")
        self.area = self.repo / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        self.src = self.repo / "data" / "raw" / "cases.jsonl"
        self.src.parent.mkdir(parents=True)
        self.src.write_text('{"id": 1}\n', encoding="utf-8")
        self.out = self.area / "output" / "x.jsonl"
        self.out.parent.mkdir()
        self.out.write_text('{"id": 1, "n": 4}\n', encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, protocol: str, data: dict | None, commit: bool) -> Path:
        (self.area / "PROTOCOL-x.md").write_text(protocol, encoding="utf-8")
        d = self.area / "runs" / "2026-10-05T19-00-00_ab12"
        d.mkdir(parents=True)
        cfg = {
            "script": "01_measure.py",
            "script_sha": script_sha_of(scope_file(self.area)),
            "pid": 1,
            "schema_version": 4,
            "run_kind": "measurement",
            "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
            "data": data or {},
            # a frozen protocol's run recorded its block (0.71)
            "promises": _snapshot(self.area, protocol),
        }
        (d / "config.json").write_text(json.dumps(run_record(cfg)), encoding="utf-8")
        (d / "metrics.json").write_text(json.dumps({"mean": 3.5}), encoding="utf-8")
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 4,
                    "run_kind": "measurement",
                    "finished": "x",
                    "git": "g",
                    "git_full": "g",
                    "note": "",
                }
            ),
            encoding="utf-8",
        )
        (d / "outputs.json").write_text(
            json.dumps([{"path": str(self.out), "sha256": _recorded(self.out)}]),
            encoding="utf-8",
        )
        if commit:
            _git(self.repo, "add", "-A")
            _git(self.repo, "commit", "-qm", "x")
        return d

    def _finalize(self) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = finalize.main([str(self.area)])
        return rc, buf.getvalue()

    def _frozen(self) -> dict:
        return {"cases": {"path": str(self.src), "rows": 1, "sha256": "ab"}}

    def test_frozen_and_tracked_is_clean(self):
        self._run(SHORT, self._frozen(), commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("source frozen in the run; source and output tracked", out)

    def test_no_data_is_a_blocker(self):
        self._run(SHORT, None, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        self.assertIn("source not frozen", out)

    def test_untracked_source_is_a_blocker(self):
        self._run(SHORT, self._frozen(), commit=False)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        self.assertIn("source", out)
        self.assertIn("not tracked in git", out)

    def test_untracked_source_way_out_names_both_documented_routes(self):
        # the standard's Fixed inputs: small shareable inputs are committed,
        # large or protected data are named by source or access route and
        # version beside the run's checksum (pilot t34: the blocker named
        # `git add` alone, and a committed DATA_SOURCE.md did not lift it)
        self._run(SHORT, self._frozen(), commit=False)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        line = next(x for x in out.splitlines() if "not tracked in git" in x)
        self.assertIn("Next: if it is small and may legally be shared", line)
        self.assertIn(f"`git add {self.src}`", line)
        self.assertIn(
            "large or protected data stay out, but finalize still blocks", line
        )
        self.assertIn("source or access route and version in the protocol's Data", line)
        self.assertIn("the checksum this run recorded (sha256 ab)", line)
        self.assertIn("protocol-fill <PROTOCOL> --handover --why", line)

    def test_an_ignored_source_names_the_rule_and_its_git_add_leads_out(self):
        # pilot t60: the sandbox's .git/info/exclude held `benchmark/`, and the
        # printed `git add` was refused for an ignored path
        (self.repo / ".git" / "info" / "exclude").write_text("data/raw/\n")
        self._run(SHORT, self._frozen(), commit=True)  # `git add -A` skips it
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        line = next(x for x in out.splitlines() if "not tracked in git" in x)
        self.assertIn("git ignores it (.git/info/exclude:1:data/raw/)", line)
        command = line.split("past the rule (`", 1)[1].split("`", 1)[0]
        self.assertEqual(command, f"git add -f {self.src}")
        subprocess.run(command.split(), cwd=self.repo, check=True)
        _git(self.repo, "commit", "-qm", "the source")
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("source frozen in the run; source and output tracked", out)

    def test_a_source_a_negated_rule_keeps_in_is_named_without_a_rule(self):
        # `check-ignore -v` prints the `!` pattern that un-ignores a path too;
        # git adds such a path without -f
        (self.repo / ".gitignore").write_text("data/raw/*\n!data/raw/cases.jsonl\n")
        self._run(SHORT, self._frozen(), commit=False)
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        line = next(x for x in out.splitlines() if "not tracked in git" in x)
        self.assertNotIn("git ignores", line)
        self.assertIn(f"commit it (`git add {self.src}`)", line)

    def _directory_source(self) -> tuple[Path, dict]:
        """A source directory the run read: a note and two data files."""
        geo = self.repo / "data" / "raw" / "geo"
        geo.mkdir(parents=True)
        (geo / "SOURCE.md").write_text("where the files come from\n")
        (geo / "roads.geojson").write_text("{}\n")
        (geo / "area.geojson").write_text("{}\n")
        return geo, {"geo": {"path": str(geo), "rows": 3, "sha256": "cd"}}

    def _blocker_line(self) -> str:
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        return next(x for x in out.splitlines() if "not tracked in git" in x)

    def test_a_directory_with_one_file_tracked_is_not_tracked(self):
        # pilot t21: benchmark/ excluded, only SOURCE.md committed (with -f),
        # and finalize said "source and output tracked in git … all clear"
        (self.repo / ".git" / "info" / "exclude").write_text("data/raw/\n")
        geo, data = self._directory_source()
        self._run(SHORT, data, commit=True)  # `git add -A` skips data/raw/
        _git(self.repo, "add", "-f", str(geo / "SOURCE.md"))
        _git(self.repo, "commit", "-qm", "the note")
        line = self._blocker_line()
        self.assertIn("2 file(s) under it are not (area.geojson, roads.geojson)", line)
        self.assertIn(
            "git ignores files under it (.git/info/exclude:1:data/raw/)", line
        )
        command = line.split("past the rule (`", 1)[1].split("`", 1)[0]
        self.assertEqual(
            command,
            f"git add -f -- {(geo / 'area.geojson').resolve()} "
            f"{(geo / 'roads.geojson').resolve()}",
        )
        subprocess.run(command.split(), cwd=self.repo, check=True)
        _git(self.repo, "commit", "-qm", "the data")
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("source frozen in the run; source and output tracked", out)

    def test_an_untracked_directory_is_committed_file_by_file(self):
        geo, data = self._directory_source()
        self._run(SHORT, data, commit=True)
        _git(self.repo, "rm", "-q", "--cached", str(geo / "roads.geojson"))
        _git(self.repo, "commit", "-qm", "one file out")
        line = self._blocker_line()
        self.assertIn("1 file(s) under it are not (roads.geojson)", line)
        self.assertNotIn("git ignores", line)
        self.assertIn(
            f"commit it (`git add -- {(geo / 'roads.geojson').resolve()}`)", line
        )

    def test_a_hidden_file_under_a_directory_source_is_none_it_read(self):
        geo, data = self._directory_source()
        self._run(SHORT, data, commit=True)
        (geo / ".DS_Store").write_text("x")  # outside the run's digest
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)

    def test_the_printed_handover_is_the_one_agents_md_gives(self):
        agents = (PACKAGE_DIR / "templates" / "AGENTS.md.template").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            " ".join(run_record_check.HANDOVER_COMMAND.split()),
            " ".join(agents.split()),
        )

    def test_untracked_output_after_the_run_is_a_warning_naming_git_add(self):
        d = self._run(SHORT, self._frozen(), commit=True)
        self.out.write_text(
            '{"id": 1, "n": 5}\n', encoding="utf-8"
        )  # rows born after the commit
        fresh = self.area / "output" / "fresh.jsonl"
        fresh.write_text("{}\n", encoding="utf-8")
        (d / "outputs.json").write_text(
            json.dumps([{"path": str(fresh), "sha256": _recorded(fresh)}])
        )
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("git add", out)

    def test_hours_is_not_the_stations_business(self):
        self._run(HIGH, None, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("n/a — protocol repeat cost is 'high'", out)


if __name__ == "__main__":
    unittest.main()
