"""finalize's provenance station: at repeat_cost = "low" the run must have
frozen its sources, each source's bytes must be the ones the record names,
and each must be tracked in git or ignored by a rule; the outputs tracked.
Elsewhere the station is n/a."""

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

from labkit.formats import digests, runs
from labkit import PACKAGE_DIR  # noqa: E402
from labkit.checks import run_record_check  # noqa: E402
from labkit.gates import finalize  # noqa: E402
from labkit.formats import promises  # noqa: E402
from labkit.formats.runs import RECORD_SHA_CHARS  # noqa: E402
from labkit.run import provenance  # noqa: E402
from protocol_fixture import run_record, PID, head, scope_file, script_sha_of  # noqa: E402

BODY = """
- **Question / hypothesis:** how many documents per case?
- **Recorded results:** 3.5, run r1
"""
SHORT = (
    "# Experiment protocol: x\n\n"
    + head(repeat_cost="low", promises=None, kept=("mean", "1"))
    + BODY
)
HIGH = (
    "# Experiment protocol: x\n\n"
    + head(repeat_cost="high", frozen=True, promises=None, kept=("mean", "1"))
    + BODY
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _recorded(path: Path) -> str:
    """The sha256 prefix outputs.json records for PATH as it is now — the
    registered-outputs station holds the file to it."""
    return digests.file_digest(path)[:RECORD_SHA_CHARS]


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
        # the run starts at a commit that holds its protocol, as a run in a
        # repository does: finalize reads the registration back from it
        _git(self.repo, "add", str(self.area / "PROTOCOL-x.md"))
        _git(self.repo, "commit", "-qm", "registration")
        started = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        d = self.area / "runs" / "2026-10-05T19-00-00_ab12"
        d.mkdir(parents=True)
        cfg = {
            "script": "01_measure.py",
            "script_sha": script_sha_of(scope_file(self.area)),
            "pid": 1,
            "schema_version": 4,
            "run_kind": "measurement",
            "git": started[:7],
            "git_full": started,
            "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
            "data": data or {},
            # a frozen protocol's run records its block
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
                    "git": started[:7],
                    "git_full": started,
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
        """The run's `data=` record of the source as it is now, as runlog
        writes it."""
        return {"cases": self._entry(self.src)}

    @staticmethod
    def _entry(source: Path) -> dict:
        return {
            "path": str(source),
            "rows": 1,
            "sha256": provenance.source_digest(source)[:RECORD_SHA_CHARS],
        }

    def test_frozen_and_tracked_is_clean(self):
        self._run(SHORT, self._frozen(), commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn(
            "source frozen in the run; source tracked in git; output tracked in git",
            out,
        )
        self.assertIn("each source's bytes as the run recorded them", out)

    def test_a_tracked_source_changed_since_the_run_blocks(self):
        """The record is the one integrity evidence for every source: a
        tracked file regenerated after the run is not what the number came
        from."""
        self._run(SHORT, self._frozen(), commit=True)
        self.src.write_text('{"id": 2}\n', encoding="utf-8")
        _git(self.repo, "commit", "-qam", "regenerated")
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        self.assertIn(f"source {self.src} is not the bytes the run read", out)
        self.assertIn("restore the bytes the run read (from git where it tracks", out)

    def test_no_data_is_a_blocker(self):
        self._run(SHORT, None, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        self.assertIn("source not frozen", out)

    def test_a_run_declaring_no_input_file_passes_and_says_so(self):
        """data=runlog.NO_INPUTS: the author's declaration, told apart from a
        data= left out — it passes, named as the author's word."""
        self._run(SHORT, {runs.NO_INPUTS_KEY: runs.NO_INPUTS_DECLARED}, commit=True)
        rc, out = self._finalize()
        self.assertNotIn("source not frozen", out)
        self.assertIn("declares it reads no input file", out)

    def test_the_twin_an_empty_record_is_no_declaration(self):
        """An old record's empty data= gains no release: only the key says it."""
        self._run(SHORT, {}, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        self.assertIn("data=runlog.NO_INPUTS", out)

    def test_a_source_the_record_holds_no_checksum_of_blocks(self):
        data = self._frozen()
        del data["cases"]["sha256"]
        self._run(SHORT, data, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        self.assertIn("the run recorded no sha256 for it", out)
        self.assertIn("pass every source in `data=`", out)

    def test_a_data_entry_naming_no_path_blocks(self):
        data = self._frozen()
        data["broken"] = {"rows": 1, "sha256": "ab"}
        self._run(SHORT, data, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        self.assertIn("data['broken'] in the run's record names no path", out)

    def test_outside_a_repository_the_bytes_are_still_held(self):
        """git's half needs a repository, the record's does not."""
        with tempfile.TemporaryDirectory() as tmp:
            area = Path(tmp) / "experiments" / "01-x"
            run = area / "runs" / "2026-10-05T19-00-00_ab12"
            run.mkdir(parents=True)
            src = Path(tmp) / "cases.jsonl"
            src.write_text('{"id": 1}\n', encoding="utf-8")
            record = run_record({"data": {"cases": self._entry(src)}})
            (run / "config.json").write_text(json.dumps(record), encoding="utf-8")
            (run / "outputs.json").write_text("[]", encoding="utf-8")
            b, w, _ = run_record_check.provenance_findings(area, run)
            self.assertEqual(b, [])  # the twin: the bytes as recorded
            self.assertIn("not a git repository", w[0])
            src.write_text('{"id": 2}\n', encoding="utf-8")
            b, _, _ = run_record_check.provenance_findings(area, run)
            self.assertEqual(len(b), 1)
            self.assertIn("is not the bytes the run read", b[0].text)

    def test_untracked_source_is_a_blocker(self):
        self._run(SHORT, self._frozen(), commit=False)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        self.assertIn("neither tracked in git nor ignored by a rule", out)

    def test_untracked_source_way_out_names_both_documented_routes(self):
        # the standard's Fixed inputs: small shareable inputs are committed,
        # large or protected data are kept outside git on purpose, with
        # source or access route and version in Data / scope: the way out
        # names both
        self._run(SHORT, self._frozen(), commit=False)
        line = self._blocker_line()
        self.assertIn("Next: if it is small and may legally be shared", line)
        self.assertIn(f"`git add {self.src}`", line)
        self.assertIn("large or protected data stay out of git on purpose", line)
        self.assertIn("an ignore rule for it", line)
        self.assertIn("route and version in the protocol's Data / scope", line)
        sha = self._frozen()["cases"]["sha256"]
        self.assertIn(f"the checksum this run recorded, `sha256 {sha}`", line)

    def test_an_untracked_source_blocks_though_data_scope_names_its_checksum(self):
        """git status is the hygiene rule beside the record: matching bytes
        do not settle whether the data belong to the project, and a
        checksum in Data / scope pins nothing."""
        sha = self._frozen()["cases"]["sha256"]
        protocol = SHORT + f"- **Data / scope:** cases.jsonl, release 3, sha256 {sha}\n"
        self._run(protocol, self._frozen(), commit=False)
        _git(self.repo, "add", "experiments")
        _git(self.repo, "commit", "-qm", "x")
        line = self._blocker_line()
        self.assertIn("neither tracked in git nor ignored by a rule", line)

    def test_an_ignored_source_with_the_recorded_bytes_passes(self):
        """A model directory excluded from git on purpose, holding the bytes
        the record names, passes, the rule named."""
        (self.repo / ".git" / "info" / "exclude").write_text("data/raw/\n")
        self._run(SHORT, self._frozen(), commit=True)  # `git add -A` skips it
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn(
            f"source {self.src} is kept outside git by an ignore rule "
            "(.git/info/exclude:1:data/raw/), pinned by the checksum the run "
            "recorded",
            out,
        )
        self.assertIn(
            "source tracked in git or kept outside it; output tracked in git",
            out,
        )

    def test_the_twin_an_ignored_source_with_one_byte_changed_blocks(self):
        (self.repo / ".git" / "info" / "exclude").write_text("data/raw/\n")
        self._run(SHORT, self._frozen(), commit=True)
        self.src.write_text('{"id": 2}\n', encoding="utf-8")
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        self.assertIn(f"source {self.src} is not the bytes the run read", out)
        self.assertIn("else from the source or access route Data / scope names", out)

    def held_outside(self, reached_by_link: bool) -> None:
        """A model file on scratch, recorded as itself or through a link in
        the repository: finalize passes it with the note."""
        with tempfile.TemporaryDirectory() as scratch:
            model = Path(scratch) / "model.bin"
            model.write_bytes(b"weights")
            source = model
            if reached_by_link:
                source = self.repo / "data" / "model.bin"
                source.symlink_to(model)
            self._run(SHORT, {"model": self._entry(source)}, commit=True)
            rc, out = self._finalize()
            self.assertEqual(rc, 0, out)
            self.assertIn(
                f"source {source} lies outside the repository "
                f"({model.resolve()}), pinned by the checksum the run recorded",
                out,
            )
            self.assertIn("access route and version belong in Data / scope", out)

    def test_a_source_outside_the_repository_is_held_by_its_checksum(self):
        """A source that lies outside the repository (a model directory on
        scratch) git can neither track nor ignore. Held by the checksum the run
        recorded, it passes with a note naming where it lies and what Data /
        scope owes."""
        self.held_outside(reached_by_link=False)

    def test_a_link_in_the_repository_to_bytes_outside_it_is_the_same(self):
        self.held_outside(reached_by_link=True)

    def test_the_twin_a_source_outside_the_repository_changed_blocks(self):
        with tempfile.TemporaryDirectory() as scratch:
            model = Path(scratch) / "model.bin"
            model.write_bytes(b"weights")
            self._run(SHORT, {"model": self._entry(model)}, commit=True)
            model.write_bytes(b"weights, retrained")
            rc, out = self._finalize()
            self.assertEqual(rc, 1, out)
            self.assertIn(f"source {model} is not the bytes the run read", out)
            self.assertNotIn("neither tracked in git nor ignored", out)

    def test_an_ignored_source_that_is_gone_names_the_route(self):
        (self.repo / ".git" / "info" / "exclude").write_text("data/raw/\n")
        self._run(SHORT, self._frozen(), commit=True)
        self.src.unlink()
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{self.src} is not at its recorded path on this machine", out)
        self.assertIn("get it again from the source or access route Data / scope", out)

    def test_a_source_a_negated_rule_keeps_in_is_named_without_a_rule(self):
        # `check-ignore -v` prints the `!` pattern that un-ignores a path too;
        # that path is not ignored, so it must be committed or ignored
        (self.repo / ".gitignore").write_text("data/raw/*\n!data/raw/cases.jsonl\n")
        self._run(SHORT, self._frozen(), commit=False)
        line = self._blocker_line()
        self.assertIn(f"commit it (`git add {self.src}`)", line)

    def test_a_manifest_beside_an_untracked_source_pins_nothing(self):
        """`MANIFEST.sha256` is no route; it is not read."""
        self._run(SHORT, self._frozen(), commit=False)
        manifest = self.repo / "data" / "MANIFEST.sha256"
        manifest.write_text(
            f"{digests.file_digest(self.src)}  data/raw/cases.jsonl\n",
            encoding="utf-8",
        )
        _git(self.repo, "add", "experiments", str(manifest))
        _git(self.repo, "commit", "-qm", "x")
        line = self._blocker_line()
        self.assertIn("neither tracked in git nor ignored by a rule", line)

    def _directory_source(self) -> tuple[Path, dict]:
        """A source directory the run read: a note and two data files."""
        geo = self.repo / "data" / "raw" / "geo"
        geo.mkdir(parents=True)
        (geo / "SOURCE.md").write_text("where the files come from\n")
        (geo / "roads.geojson").write_text("{}\n")
        (geo / "area.geojson").write_text("{}\n")
        entry = self._entry(geo)
        entry["rows"] = 3
        return geo, {"geo": entry}

    def _blocker_line(self) -> str:
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        return next(
            x for x in out.splitlines() if "neither tracked in git nor ignored" in x
        )

    def test_an_ignored_directory_with_one_file_tracked_passes(self):
        # data/raw/ excluded, only SOURCE.md committed (with -f);
        # the other files are ignored on purpose and the digest holds them
        (self.repo / ".git" / "info" / "exclude").write_text("data/raw/\n")
        geo, data = self._directory_source()
        self._run(SHORT, data, commit=True)  # `git add -A` skips data/raw/
        _git(self.repo, "add", "-f", str(geo / "SOURCE.md"))
        _git(self.repo, "commit", "-qm", "the note")
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn(f"source {geo} is kept outside git by an ignore rule", out)
        (geo / "README.md").write_text("added after the run\n")  # the twin
        rc, out = self._finalize()
        self.assertEqual(rc, 1, out)
        self.assertIn(f"source {geo} is not the bytes the run read", out)

    def test_an_untracked_directory_is_committed_file_by_file(self):
        geo, data = self._directory_source()
        self._run(SHORT, data, commit=True)
        _git(self.repo, "rm", "-q", "--cached", str(geo / "roads.geojson"))
        _git(self.repo, "commit", "-qm", "one file out")
        line = self._blocker_line()
        self.assertIn("1 file(s) under it (roads.geojson)", line)
        self.assertIn(
            f"commit it (`git add -- {(geo / 'roads.geojson').resolve()}`)", line
        )
        command = line.split("commit it (`", 1)[1].split("`", 1)[0]
        subprocess.run(command.split(), cwd=self.repo, check=True)
        _git(self.repo, "commit", "-qm", "the file")
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)

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
