"""Two protocols of one area, each with its own earlier BLOCKER: repair,
follow-up and adoption run for each apart, through the real commands.

An audit record names the protocol it audited (`[audit] protocol`), and the
follow-up, the release and the adoption read the records of their own
protocol (`followup.protocol_records`). The conditions from data in memory:
tests/test_audit.py (the follow-up shown, the release held, the carry across
protocols refused; tests/test_rules_audit_binding.py: an undecided finding
holds its own protocol); here what the commands pass on — the adoption
(`labkit-adopt AREA RUN --protocol FILE`) of one protocol is neither
released nor held by the other's records, decided or not, while a change of
the area's shared code is held for each by its own audit coverage.

One coupling stays (TODO.md, 6b): `scripts/02_analyze.py --check` belongs to
the first protocol and finalize runs it for every protocol of the area, so
the second is adopted only after the first — the order every scenario here
keeps.
"""

from __future__ import annotations

import contextlib
import io
import re
import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import findings, protocol_block  # noqa: E402
from labkit.gates import audit  # noqa: E402
from labkit.tools import adopt  # noqa: E402
from test_end_to_end import CountCommands  # noqa: E402

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

RIGHT = "data/raw/docs, 3 documents, read directly"
WRONG = "data/raw/docs, 4 documents, read directly"


class EachProtocolAdoptsItsOwn(CountCommands):
    """The count area with a second protocol on the same question: its own
    stamped id, its own measuring script and output file. Both are
    registered with a document count the data does not hold (Data / scope
    says 4, the runs read 3), both measured, and each analysis audit names
    that field of its own protocol as a BLOCKER."""

    def setUp(self) -> None:
        super().setUp()
        self.first = self.protocol
        self.lab.fill(self.first, "--force", f"Data / scope={WRONG}")
        text = self.first.read_text(encoding="utf-8")
        pid = protocol_block.head(text).id
        assert pid is not None
        self.second = self.area / "PROTOCOL-second.md"
        self.second.write_text(
            text.replace(pid, "p-0123456789abcdef"), encoding="utf-8"
        )
        measure = (self.area / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        bound = f'"{self.first.name}"'
        assert bound in measure and '"lines.jsonl"' in measure
        (self.area / "scripts" / "03_measure_second.py").write_text(
            measure.replace(bound, f'"{self.second.name}"').replace(
                '"lines.jsonl"', '"lines_second.jsonl"'
            ),
            encoding="utf-8",
        )
        self.lab.commit("two protocols, each registered with a wrong document count")
        self.clean += f"\n{self.area.relative_to(self.lab.root).as_posix()}/scripts/03_measure_second.py"
        self.run_first = self.measure()
        self.run_second = self.lab.run_id_of(
            self.lab.script(self.area, "03_measure_second.py")
        )
        for protocol in (self.first, self.second):
            # the Conclusion line written: labkit-adopt refuses without it
            self.lab.conclude(protocol)

    def audited(self, protocol: Path) -> Path:
        """Run the analysis audit of PROTOCOL, the answer one BLOCKER at
        its Data / scope. Returns the record written (also `self.record`)."""
        rc, out, _ = self.analysis(
            f"BLOCKER · {protocol.name}:Data / scope · statement · Data / scope "
            f"says 4 documents, the run read 3 · the mean's denominator as "
            f"described · LAB-050 Analysis audit before reporting · correct the "
            f"description\nverdict: 1 blockers, 0 warnings, 0 notes",
            protocol,
        )
        self.assertEqual(rc, 1, out)
        assert self.record is not None
        return self.record

    def follow_up(self, protocol: Path, judged: Path) -> tuple[int, str, str]:
        """An analysis audit of PROTOCOL whose answer calls finding 1 of the
        record JUDGED resolved and names no new finding (`self.clean`, which
        lists both measuring scripts as read): (exit, output, prompt)."""
        return self.analysis(
            f"FIX · {judged.name}#1 · resolved · 3 documents, as the run read"
            f"\n\n{self.clean}",
            protocol,
        )

    def labkit_adopt(self, protocol: Path, run_id: str) -> tuple[int, str]:
        out = io.StringIO()
        with (
            contextlib.chdir(self.lab.root),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            rc = adopt.main([str(self.area), run_id, "--protocol", str(protocol)])
        return rc, out.getvalue()

    def declared_run(self, protocol: Path) -> str | None:
        return protocol_block.declared_run(protocol.read_text(encoding="utf-8"))

    def test_each_protocol_is_repaired_followed_up_and_adopted_apart(self):
        """The first protocol repaired and followed up: its follow-up shows
        its own BLOCKER alone, and its adoption passes while the second's
        repair is only claimed. That follow-up releases nothing of the
        second, which is held by its own BLOCKER until its own repair and
        follow-up; the second's records leave the first's adoption standing."""
        of_first = self.audited(self.first)
        of_second = self.audited(self.second)
        self.lab.fill(self.first, "--force", f"Data / scope={RIGHT}")
        self.decide(of_first, 1, "fixed", "Data / scope now says 3", self.first)
        # the second's repair is claimed only: decided `fixed`, its field unedited
        self.decide(of_second, 1, "fixed", "Data / scope now says 3", self.second)

        rc, out, prompt = self.follow_up(self.first, of_first)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"{of_first.name}#1", prompt)
        self.assertNotIn(of_second.name, prompt)
        rc, out = self.labkit_adopt(self.first, self.run_first)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared_run(self.first), self.run_first)

        # the first's follow-up released nothing of the second
        rc, out = self.labkit_adopt(self.second, self.run_second)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{of_second.name}#1: decided `fixed` in the state audited", out)
        self.assertNotIn(f"{of_first.name}#1", out)
        self.assertIsNone(self.declared_run(self.second))

        self.lab.fill(self.second, "--force", f"Data / scope={RIGHT}")
        rc, out, prompt = self.follow_up(self.second, of_second)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"{of_second.name}#1", prompt)
        self.assertNotIn(of_first.name, prompt)
        rc, out = self.labkit_adopt(self.second, self.run_second)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared_run(self.second), self.run_second)

        # the second's records moved nothing under the first's adoption
        rc, out = self.labkit_adopt(self.first, self.run_first)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"has adopted {self.run_first} already", out)

    def test_an_audit_of_one_protocol_judges_no_finding_of_the_other(self):
        """A follow-up on the second protocol that calls the first's BLOCKER
        resolved is refused and records nothing, and the first's adoption
        stays held by it. The twin: the first's own follow-up says the same,
        and the adoption passes."""
        of_first = self.audited(self.first)
        of_second = self.audited(self.second)
        self.lab.fill(self.first, "--force", f"Data / scope={RIGHT}")
        self.decide(of_first, 1, "fixed", "Data / scope now says 3", self.first)
        self.decide(of_second, 1, "fixed", "Data / scope now says 3", self.second)

        rc, out, _ = self.follow_up(self.second, of_first)
        # 2: the answer is refused — a verdict on a finding the prompt did not show
        self.assertEqual(rc, 2, out)
        self.assertIsNone(self.record)
        rc, out = self.labkit_adopt(self.first, self.run_first)
        # 1: the adoption is held by a blocker — the first's own, not followed up
        self.assertEqual(rc, 1, out)
        self.assertIsNone(self.declared_run(self.first))

        rc, out, _ = self.follow_up(self.first, of_first)
        self.assertEqual(rc, 0, out)
        rc, out = self.labkit_adopt(self.first, self.run_first)
        self.assertEqual(rc, 0, out)

    def test_an_undecided_finding_holds_its_own_protocol_alone(self):
        """The second protocol's BLOCKER left undecided: the first, repaired
        and followed up, is adopted all the same. The twin: the second's own
        adoption is held by it, and the decide line the hold prints names
        the protocol and runs as printed, its confirmation whole."""
        of_first = self.audited(self.first)
        of_second = self.audited(self.second)  # stays undecided
        self.lab.fill(self.first, "--force", f"Data / scope={RIGHT}")
        self.decide(of_first, 1, "fixed", "Data / scope now says 3", self.first)
        rc, out, _ = self.follow_up(self.first, of_first)
        self.assertEqual(rc, 0, out)
        rc, out = self.labkit_adopt(self.first, self.run_first)
        self.assertEqual(rc, 0, out)
        self.assertNotIn(of_second.name, out)

        rc, out = self.labkit_adopt(self.second, self.run_second)
        self.assertEqual(rc, 1, out)
        printed = re.search(
            rf"`(labkit-audit [^`]*--decide 1 STATUS [^`]*{re.escape(of_second.name)})`",
            out,
        )
        assert printed is not None, out
        self.assertIn(f"--protocol experiments/01-lines/{self.second.name}", printed[1])
        words = [
            {"STATUS": "fixed", "<why>": "Data / scope now says 3"}.get(w, w)
            for w in shlex.split(printed[1])[1:]
        ]
        said = io.StringIO()
        with (
            contextlib.chdir(self.lab.root),
            contextlib.redirect_stdout(said),
            contextlib.redirect_stderr(said),
        ):
            rc = audit.main(words)
        self.assertEqual(rc, 0, said.getvalue())
        # without the protocol the confirmation cannot say what `fixed` owes
        self.assertNotIn("could not be read", said.getvalue())
        self.assertEqual(findings.read(of_second).findings[0].status, "fixed")

    def test_a_change_of_the_shared_code_is_held_for_each_by_its_own_coverage(self):
        """Both protocols audited without a finding, the first adopted; then
        the first's measuring script changes — code the area's stamp covers
        for both. Each protocol is held by its own analysis coverage; a new
        audit of the first covers nothing of the second, the second's own
        audit does."""
        for protocol in (self.first, self.second):
            rc, out, _ = self.analysis(self.clean, protocol)
            self.assertEqual(rc, 0, out)
        rc, out = self.labkit_adopt(self.first, self.run_first)
        self.assertEqual(rc, 0, out)
        self.change_code()
        uncovered = "no analysis audit saw the area as it is now"

        rc, out = self.labkit_adopt(self.first, self.run_first)
        self.assertEqual(rc, 1, out)  # the adoption stands, its check holds
        rc, out = self.labkit_adopt(self.second, self.run_second)
        self.assertEqual(rc, 1, out)
        self.assertIn(uncovered, out)

        rc, out, _ = self.analysis(self.clean, self.first)
        self.assertEqual(rc, 0, out)
        rc, out = self.labkit_adopt(self.second, self.run_second)
        self.assertEqual(rc, 1, out)
        self.assertIn(uncovered, out)

        rc, out, _ = self.analysis(self.clean, self.second)
        self.assertEqual(rc, 0, out)
        rc, out = self.labkit_adopt(self.second, self.run_second)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared_run(self.second), self.run_second)
