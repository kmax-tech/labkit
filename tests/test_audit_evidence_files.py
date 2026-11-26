"""Tests for the files a protocol declares in `[[evidence_file]]`: a data or
output file the audit reads in full, with the sha256 recorded when it was
declared.

Why this exists: the audit prompt showed the protocol, the code and the
declared promise scopes, never a data file the person rests a repair on
(a classification JSON, an output Markdown), so a finding about it stayed
"not assessable". A promise `scope` would change the registration. The
declaration lives beside the promises, not in them: the prompt shows each
declared file under `EVIDENCE FILE: <path> (sha256 …)`, the area stamp binds its
bytes, and a file changed since its declaration, missing or too large is
refused before any model call.
"""

import contextlib
import hashlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks.audit_binding import AuditError  # noqa: E402
from labkit.formats import (  # noqa: E402
    audit_gaps,
    findings,
    promises,
    protocol_block,
    protocol_check,
    scope_sha,
)
from labkit.gates import audit, audit_prompt  # noqa: E402
from labkit.tools import protocol_fill  # noqa: E402
from protocol_fixture import head, protocol_id_of, registration_of  # noqa: E402
from repo_fixture import init_repo  # noqa: E402

CLASSIFICATION = '{"case-1": "compatible", "case-2": "incompatible"}\n'
#: a file of the area the protocol mentions and does not declare
UNDECLARED = "output/wordcheck.md"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_table(path: str, digest: str) -> str:
    return f'[[evidence_file]]\npath = "{path}"\nsha256 = "{digest}"\n'


class _Area(unittest.TestCase):
    """A repository with one area `experiments/01`: a script, a protocol
    that declares `data/raw/classification.json` as an evidence file with
    its sha256, and an output file it does not declare."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        init_repo(self.repo)
        self.area = self.repo / "experiments" / "01"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "scripts" / "m.py").write_text("x = 1\n", encoding="utf-8")
        self.json = self.area / "data" / "raw" / "classification.json"
        self.json.parent.mkdir(parents=True)
        self.json.write_text(CLASSIFICATION, encoding="utf-8")
        undeclared = self.area / UNDECLARED
        undeclared.parent.mkdir(parents=True)
        undeclared.write_text("UNDECLARED-WORDCHECK-MARK\n", encoding="utf-8")
        self.protocol = self.area / "PROTOCOL-x.md"
        self.declare(
            evidence_table("data/raw/classification.json", sha256(CLASSIFICATION))
        )

    def declare(self, tables: str) -> str:
        """Write the protocol with TABLES in its block; its text."""
        text = "# x\n\nThe repair rests on output/wordcheck.md.\n\n" + head(
            promises=tables
        )
        self.protocol.write_text(text, encoding="utf-8")
        return text

    def prompt(self) -> str:
        reading = audit_prompt.gather(self.area, None)
        return audit_prompt.bound_prompt("preflight", self.area, reading).prompt

    def _record(self) -> str:
        text = self.protocol.read_text(encoding="utf-8")
        return findings.write(
            self.area,
            "preflight",
            "opus",
            scope_sha.area_stamp(self.area)[0],
            promises.block_stamp(text),
            (0, 0, 0),
            [],
            registration=registration_of(self.area, preflight=True),
            protocol_id=protocol_id_of(self.area),
        ).name

    def _gap(self, name: str) -> str | None:
        text = self.protocol.read_text(encoding="utf-8")
        gap = audit_gaps.audit_record_gap(self.area, name, text)
        return gap.why if gap else None

    def refusal(self) -> str:
        with self.assertRaises(AuditError) as cm:
            self.prompt()
        return str(cm.exception)


class Parse(unittest.TestCase):
    """The table reads exactly or is refused naming the field; it is no
    part of the promise block or the registration."""

    def test_a_declaration_reads_path_and_digest(self) -> None:
        text = head(promises=evidence_table("data/a.json", "a" * 64))
        self.assertEqual(
            protocol_block.evidence_files(text),
            (protocol_block.EvidenceFile("data/a.json", "a" * 64),),
        )

    def test_the_twin_no_table_is_no_declaration(self) -> None:
        self.assertEqual(protocol_block.evidence_files(head()), ())

    def test_each_malformed_field_is_named(self) -> None:
        cases = {
            "absolute": (evidence_table("/etc/a.json", "a" * 64), "path"),
            "upward": (evidence_table("../b/a.json", "a" * 64), "path"),
            "short digest": (evidence_table("a.json", "abc"), "sha256"),
            "upper hex": (evidence_table("a.json", "A" * 64), "sha256"),
            "unknown key": (
                evidence_table("a.json", "a" * 64) + 'why = "x"\n',
                "unknown field",
            ),
            "twice": (
                evidence_table("a.json", "a" * 64)
                + "\n"
                + evidence_table("a.json", "b" * 64),
                "declared twice",
            ),
            "twice, spelled apart": (
                evidence_table("a.json", "a" * 64)
                + "\n"
                + evidence_table("./a.json", "b" * 64),
                "declared twice",
            ),
        }
        for what, (tables, needle) in cases.items():
            with self.subTest(what=what):
                with self.assertRaises(protocol_block.BlockError) as cm:
                    protocol_block.evidence_files(head(promises=tables))
                self.assertIn("[[evidence_file]] #", str(cm.exception))
                self.assertIn(needle, str(cm.exception))

    def test_a_declaration_moves_neither_promises_nor_registration(self) -> None:
        """Declared after the first measurement, it changes nothing the
        registration hold or a record's `block_sha` compares."""
        block = (
            '[[promise]]\nid = "criterion-1"\nkey = "criterion_1_pass"\n'
            'sentence = "s"\nscope = ["scripts/m.py"]\n'
        )
        before = head(promises=block)
        after = head(promises=block + "\n" + evidence_table("a.json", "a" * 64))
        self.assertEqual(promises.block_stamp(before), promises.block_stamp(after))
        for audited in (True, False):
            with self.subTest(audited=audited):
                self.assertEqual(
                    protocol_check.registration_stamp(before, audited=audited),
                    protocol_check.registration_stamp(after, audited=audited),
                )


class Shown(_Area):
    def test_a_declared_json_file_is_shown_in_full_with_its_sha256(self) -> None:
        prompt = self.prompt()
        self.assertIn(
            "===== EVIDENCE FILE: experiments/01/data/raw/classification.json "
            f"(sha256 {sha256(CLASSIFICATION)}) =====",
            prompt,
        )
        self.assertIn(CLASSIFICATION.strip(), prompt)

    def test_an_undeclared_file_is_not_shown(self) -> None:
        prompt = self.prompt()
        self.assertNotIn("UNDECLARED-WORDCHECK-MARK", prompt)
        self.assertNotIn(f"EVIDENCE FILE: experiments/01/{UNDECLARED}", prompt)

    def test_the_twin_the_same_file_declared_is_shown(self) -> None:
        """The known positive of the test above: the mark it looks for does
        reach the prompt once the file is declared."""
        mark = (self.area / UNDECLARED).read_text(encoding="utf-8")
        self.declare(
            evidence_table("data/raw/classification.json", sha256(CLASSIFICATION))
            + "\n"
            + evidence_table(UNDECLARED, sha256(mark))
        )
        self.assertIn("UNDECLARED-WORDCHECK-MARK", self.prompt())

    def test_the_twin_without_a_declaration_shows_no_evidence_file(self) -> None:
        self.declare("")
        prompt = self.prompt()
        self.assertNotIn("EVIDENCE FILE: experiments/01/", prompt)
        self.assertNotIn('"case-1"', prompt)


class Refused(_Area):
    """Each refusal comes from building the prompt, before any call."""

    def test_a_file_changed_after_its_declaration_is_refused(self) -> None:
        self.json.write_text('{"case-1": "incompatible"}\n', encoding="utf-8")
        why = self.refusal()
        self.assertIn("changed after their declaration", why)
        self.assertIn("experiments/01/data/raw/classification.json", why)
        self.assertIn(sha256(CLASSIFICATION), why)
        self.assertIn(sha256('{"case-1": "incompatible"}\n'), why)

    def test_a_declared_file_that_is_gone_is_refused(self) -> None:
        self.json.unlink()
        why = self.refusal()
        self.assertIn("not a file", why)
        self.assertIn("classification.json", why)

    def test_an_oversized_file_is_refused_naming_file_and_size(self) -> None:
        big = '"' + "x" * audit_prompt.EVIDENCE_FILE_MAX_BYTES + '"\n'
        self.json.write_text(big, encoding="utf-8")
        self.declare(evidence_table("data/raw/classification.json", sha256(big)))
        why = self.refusal()
        self.assertIn("operating limit", why)
        self.assertIn(
            f"experiments/01/data/raw/classification.json ({len(big)} bytes)", why
        )

    def test_files_over_the_total_limit_are_refused(self) -> None:
        part = "y" * (audit_prompt.EVIDENCE_FILES_MAX_BYTES // 3 + 1)
        tables = ""
        for i in range(3):
            f = self.area / "data" / f"part{i}.txt"
            f.write_text(part, encoding="utf-8")
            tables += evidence_table(f"data/part{i}.txt", sha256(part)) + "\n"
        self.declare(tables)
        why = self.refusal()
        self.assertIn(f"{3 * len(part)} bytes in all", why)
        self.assertIn(f"experiments/01/data/part2.txt {len(part)}", why)

    def test_a_file_that_is_not_text_is_refused(self) -> None:
        raw = b"\xff\xfe\x00binary"
        self.json.write_bytes(raw)
        self.declare(
            evidence_table(
                "data/raw/classification.json", hashlib.sha256(raw).hexdigest()
            )
        )
        self.assertIn("not UTF-8 text", self.refusal())

    def test_the_command_refuses_before_the_model_is_called(self) -> None:
        big = "z" * (audit_prompt.EVIDENCE_FILE_MAX_BYTES + 1)
        self.json.write_text(big, encoding="utf-8")
        self.declare(evidence_table("data/raw/classification.json", sha256(big)))
        err = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete") as call,
            contextlib.redirect_stderr(err),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = audit.main([str(self.area), "--mode", "preflight"])
        self.assertEqual(code, 2)
        call.assert_not_called()
        self.assertIn("classification.json", err.getvalue())
        self.assertIn(str(len(big)), err.getvalue())


class Bound(_Area):
    """The area stamp binds each declared file's bytes and its declared
    digest, so a record stops covering the area once one changes."""

    def test_the_record_covers_the_area_while_nothing_changed(self) -> None:
        self.assertIsNone(self._gap(self._record()))

    def test_a_record_no_longer_covers_once_an_evidence_file_changes(self) -> None:
        name = self._record()
        self.json.write_text('{"case-1": "incompatible"}\n', encoding="utf-8")
        self.assertIsNotNone(self._gap(name))

    def test_a_changed_declaration_moves_the_stamp(self) -> None:
        before = scope_sha.area_stamp(self.area)[0]
        self.declare(evidence_table("data/raw/classification.json", "0" * 64))
        self.assertNotEqual(scope_sha.area_stamp(self.area)[0], before)

    def test_the_twin_an_undeclared_file_leaves_the_stamp(self) -> None:
        before = scope_sha.area_stamp(self.area)[0]
        (self.area / UNDECLARED).write_text("changed\n", encoding="utf-8")
        self.assertEqual(scope_sha.area_stamp(self.area)[0], before)

    def test_another_protocols_file_is_stamped_and_not_shown(self) -> None:
        """The stamp covers every protocol's declarations, as it covers
        every protocol's scopes; the prompt shows the audited one's."""
        other = self.area / "data" / "other.json"
        other.write_text('{"other": 1}\n', encoding="utf-8")
        (self.area / "PROTOCOL-y.md").write_text(
            "# y\n"
            + head(
                id="p-1111111111111111",
                promises=evidence_table("data/other.json", sha256('{"other": 1}\n')),
            ),
            encoding="utf-8",
        )
        reading = audit_prompt.gather(self.area, self.protocol)
        prompt = audit_prompt.bound_prompt("preflight", self.area, reading).prompt
        self.assertIn("classification.json", prompt)
        self.assertNotIn('"other": 1', prompt)
        before = scope_sha.area_stamp(self.area)[0]
        other.write_text('{"other": 2}\n', encoding="utf-8")
        self.assertNotEqual(scope_sha.area_stamp(self.area)[0], before)

    def test_an_area_without_a_declaration_keeps_its_stamp(self) -> None:
        """The basis is appended only when declared: the stamp without a
        table is the one an older labkit computed."""
        self.declare("")
        self.assertEqual(scope_sha.evidence_file_basis(self.area), ([], {}))
        snap = scope_sha.area_snapshot(self.area)
        files = [
            (scope_sha._key(f, self.repo), snap.contents[f.resolve()])
            for f in snap.files
        ]
        from labkit.formats.digests import tree_digest

        self.assertEqual(snap.sha, tree_digest(sorted(files), trailer=[]))


class SplitCannotBypass(_Area):
    """The total limit is over every declared file: one file too large for
    the per-file limit is refused, and the same bytes split into files
    each within it are refused by the total."""

    def test_one_large_file_and_its_parts_are_both_refused(self) -> None:
        part = "s" * (audit_prompt.EVIDENCE_FILE_MAX_BYTES - 1)
        whole = part * 3
        big = self.area / "data" / "whole.txt"
        big.write_text(whole, encoding="utf-8")
        self.declare(evidence_table("data/whole.txt", sha256(whole)))
        self.assertIn(f"whole.txt ({len(whole)} bytes)", self.refusal())
        tables = ""
        for i in range(3):
            (self.area / "data" / f"split{i}.txt").write_text(part, encoding="utf-8")
            tables += evidence_table(f"data/split{i}.txt", sha256(part)) + "\n"
        self.declare(tables)
        why = self.refusal()
        self.assertIn(f"{len(whole)} bytes in all", why)
        self.assertNotIn(f"({len(part)} bytes)", why)  # no part over the per-file limit

    def test_the_twin_parts_within_the_total_are_shown(self) -> None:
        part = "s" * (audit_prompt.EVIDENCE_FILES_MAX_BYTES // 2)
        tables = ""
        for i in range(2):
            (self.area / "data" / f"split{i}.txt").write_text(part, encoding="utf-8")
            tables += evidence_table(f"data/split{i}.txt", sha256(part)) + "\n"
        self.declare(tables)
        self.assertIn("EVIDENCE FILE: experiments/01/data/split1.txt", self.prompt())


class _Filled(_Area):
    """The area with `protocol-fill` run on its protocol, and a link in it
    to another area's data."""

    def fill(self, *args: str) -> tuple[int, str, str]:
        """protocol-fill on the protocol with ARGS: (exit, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = protocol_fill.main([str(self.protocol), *args])
        return code, out.getvalue(), err.getvalue()

    def text(self) -> str:
        return self.protocol.read_text(encoding="utf-8")

    def write(self, rel: str, content: str) -> Path:
        f = self.area / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
        return f

    def linked_cases(self) -> None:
        """`linked/` in the area, a link to another area's data holding
        `cases.json`."""
        shared = self.repo / "experiments" / "00" / "data"
        shared.mkdir(parents=True)
        (shared / "cases.json").write_text("[]\n", encoding="utf-8")
        (self.area / "linked").symlink_to(Path("..") / "00" / "data")


class Fill(_Filled):
    """`protocol-fill --evidence-file PATH` writes the table the audit reads,
    with the sha256 computed and the audit's own checks run on the protocol
    as it would be; nothing declared is overwritten silently."""

    def test_a_new_file_is_declared_with_its_computed_sha256(self) -> None:
        f = self.write(UNDECLARED, "WORDCHECK\n")
        code, out, _ = self.fill("--evidence-file", str(f))
        self.assertEqual(code, 0)
        self.assertIn("added", out)
        self.assertEqual(
            protocol_block.evidence_files(self.text())[-1],
            protocol_block.EvidenceFile(UNDECLARED, sha256("WORDCHECK\n")),
        )
        self.assertIn(f"EVIDENCE FILE: experiments/01/{UNDECLARED}", self.prompt())

    def test_the_path_is_written_relative_to_the_protocol(self) -> None:
        """Given from another working directory, the table holds the path
        the audit resolves against the protocol's directory."""
        f = self.write("output/check.md", "x\n")
        cwd = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, cwd)
        code, _, err = self.fill("--evidence-file", "experiments/01/output/check.md")
        self.assertEqual(code, 0, err)
        paths = [e.path for e in protocol_block.evidence_files(self.text())]
        self.assertEqual(paths[-1], "output/check.md")
        self.assertTrue((self.protocol.parent / paths[-1]).samefile(f))

    def last_path(self) -> str:
        return protocol_block.evidence_files(self.text())[-1].path

    def test_a_path_through_a_symlink_stays_as_written(self) -> None:
        """A link to another area's data is declared by the link's path,
        as the stamp names it, not by where it leads."""
        self.linked_cases()
        code, _, err = self.fill(
            "--evidence-file", str(self.area / "linked" / "cases.json")
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last_path(), "linked/cases.json")

    def test_a_prefix_spelled_through_another_link_keeps_the_link_below(
        self,
    ) -> None:
        """The repository reached through a link of its own (as `/var` is
        `/private/var` on macOS): the part below the protocol's directory
        is still written as given, both ways round."""
        aliases = tempfile.TemporaryDirectory()
        self.addCleanup(aliases.cleanup)
        alias = Path(aliases.name) / "repo-alias"
        alias.symlink_to(self.repo.resolve(), target_is_directory=True)
        self.linked_cases()
        given = alias / "experiments" / "01" / "linked" / "cases.json"
        code, _, err = self.fill("--evidence-file", str(given))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last_path(), "linked/cases.json")
        other = self.write("output/b.md", "b\n")
        out, err2 = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err2):
            code = protocol_fill.main(
                [
                    str(alias / "experiments" / "01" / self.protocol.name),
                    "--evidence-file",
                    str(other.resolve()),
                ]
            )
        self.assertEqual(code, 0, err2.getvalue())
        self.assertEqual(self.last_path(), "output/b.md")

    def test_the_same_path_and_sha256_changes_nothing(self) -> None:
        before = self.protocol.read_bytes()
        code, out, _ = self.fill("--evidence-file", str(self.json))
        self.assertEqual(code, 0)
        self.assertIn("already declared with this sha256", out)
        self.assertEqual(self.protocol.read_bytes(), before)

    def test_another_sha256_for_a_declared_path_is_refused(self) -> None:
        before = self.protocol.read_bytes()
        self.json.write_text('{"case-1": "incompatible"}\n', encoding="utf-8")
        code, _, err = self.fill("--evidence-file", str(self.json))
        self.assertEqual(code, 2)
        self.assertIn(sha256(CLASSIFICATION), err)
        self.assertIn("--replace-evidence-file", err)
        self.assertEqual(self.protocol.read_bytes(), before)

    def test_the_twin_replace_writes_only_the_new_sha256(self) -> None:
        before = self.protocol.read_bytes()
        new = '{"case-1": "incompatible"}\n'
        self.json.write_text(new, encoding="utf-8")
        code, out, err = self.fill(
            "--evidence-file", str(self.json), "--replace-evidence-file"
        )
        self.assertEqual(code, 0, err)
        self.assertIn(f"was {sha256(CLASSIFICATION)}", out)
        self.assertEqual(
            self.protocol.read_bytes(),
            before.replace(sha256(CLASSIFICATION).encode(), sha256(new).encode()),
        )
        self.assertIn(new.strip(), self.prompt())

    def test_a_replaced_file_is_no_longer_covered_by_the_earlier_record(
        self,
    ) -> None:
        """An audit record made before the replacement does not cover the
        area after it: the stamp binds the new bytes and the new digest."""
        record = self._record()
        self.assertIsNone(Bound._gap(self, record))  # type: ignore[arg-type]
        self.json.write_text('{"case-1": "incompatible"}\n', encoding="utf-8")
        code, _, err = self.fill(
            "--evidence-file", str(self.json), "--replace-evidence-file"
        )
        self.assertEqual(code, 0, err)
        self.assertIsNotNone(Bound._gap(self, record))  # type: ignore[arg-type]

    def test_a_path_outside_the_protocols_directory_is_refused(self) -> None:
        f = self.repo / "elsewhere.json"
        f.write_text("{}\n", encoding="utf-8")
        before = self.protocol.read_bytes()
        code, _, err = self.fill("--evidence-file", str(f))
        self.assertEqual(code, 2)
        self.assertIn("not below", err)
        self.assertEqual(self.protocol.read_bytes(), before)

    def test_each_file_the_audit_would_refuse_is_refused_unwritten(self) -> None:
        """The audit's checks, on the protocol as it would be: no file, not
        text, over the per-file limit, and the total over every declared
        file once the new one is added."""
        third = audit_prompt.EVIDENCE_FILES_MAX_BYTES // 3
        self.write("data/a.txt", "a" * third)
        self.write("data/b.txt", "b" * third)
        self.declare(
            evidence_table("data/raw/classification.json", sha256(CLASSIFICATION))
            + "\n"
            + evidence_table("data/a.txt", sha256("a" * third))
            + "\n"
            + evidence_table("data/b.txt", sha256("b" * third))
        )
        (self.area / "data" / "raw.bin").write_bytes(b"\xff\xfe\x00")
        cases = {
            "no file": ("data/none.txt", None, "is not a file"),
            "not text": ("data/raw.bin", None, "not UTF-8 text"),
            "over the per-file limit": (
                "data/big.txt",
                "z" * (audit_prompt.EVIDENCE_FILE_MAX_BYTES + 1),
                f"({audit_prompt.EVIDENCE_FILE_MAX_BYTES + 1} bytes)",
            ),
            "over the total once added": (
                "data/c.txt",
                "c" * third,
                f"{3 * third + len(CLASSIFICATION)} bytes in all",
            ),
        }
        for what, (rel, content, needle) in cases.items():
            with self.subTest(what=what):
                if content is not None:
                    self.write(rel, content)
                before = self.protocol.read_bytes()
                code, _, err = self.fill("--evidence-file", str(self.area / rel))
                self.assertEqual(code, 2)
                self.assertIn(needle, err)
                self.assertEqual(self.protocol.read_bytes(), before)

    def test_the_twin_a_file_that_fits_the_total_is_added(self) -> None:
        third = audit_prompt.EVIDENCE_FILES_MAX_BYTES // 3
        self.write("data/a.txt", "a" * third)
        code, _, err = self.fill("--evidence-file", str(self.area / "data/a.txt"))
        self.assertEqual(code, 0, err)
        self.assertEqual(len(protocol_block.evidence_files(self.text())), 2)

    def test_a_stale_declaration_of_another_file_is_refused_too(self) -> None:
        """The checks run over every declared file, as the audit's do."""
        self.json.write_text('{"case-1": "incompatible"}\n', encoding="utf-8")
        f = self.write(UNDECLARED, "WORDCHECK\n")
        before = self.protocol.read_bytes()
        code, _, err = self.fill("--evidence-file", str(f))
        self.assertEqual(code, 2)
        self.assertIn("changed after their declaration", err)
        self.assertEqual(self.protocol.read_bytes(), before)

    def test_replace_goes_only_with_evidence_file(self) -> None:
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as cm,
        ):
            protocol_fill.main([str(self.protocol), "--replace-evidence-file"])
        self.assertEqual(cm.exception.code, 2)


class NotRead(_Area):
    """A declared file that is gone, or does not read, is stamped under a
    name no content can take and refused by name, never a traceback."""

    def test_a_deleted_file_does_not_stamp_like_the_content_missing(self) -> None:
        """The content `<missing>` was once the marker of a deleted file:
        the record made over it no longer covers once the file is gone."""
        self.json.write_text("<missing>", encoding="utf-8")
        self.declare(
            evidence_table("data/raw/classification.json", sha256("<missing>"))
        )
        record = self._record()
        self.assertIsNone(self._gap(record))
        before = scope_sha.area_stamp(self.area)[0]
        self.json.unlink()
        self.assertNotEqual(scope_sha.area_stamp(self.area)[0], before)
        self.assertIsNotNone(self._gap(record))

    def test_the_twin_an_empty_file_does_not_stamp_like_a_deleted_one(self) -> None:
        self.json.write_text("", encoding="utf-8")
        self.declare(evidence_table("data/raw/classification.json", sha256("")))
        empty = scope_sha.area_stamp(self.area)[0]
        self.json.unlink()
        self.assertNotEqual(scope_sha.area_stamp(self.area)[0], empty)

    def unreadable(self, f: Path) -> None:
        """F's permissions taken away for the test, given back after."""
        if os.geteuid() == 0:
            self.skipTest("root reads a file without permissions")
        f.chmod(0)
        self.addCleanup(f.chmod, 0o644)

    def test_an_unreadable_file_is_refused_by_the_audit_before_the_call(self) -> None:
        self.unreadable(self.json)
        scope_sha.area_stamp(self.area)  # stamps, does not raise
        self.assertIn("cannot be read", self.refusal())
        err = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete") as call,
            contextlib.redirect_stderr(err),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = audit.main([str(self.area), "--mode", "preflight"])
        self.assertEqual(code, 2)
        call.assert_not_called()
        self.assertIn(
            "cannot be read: experiments/01/data/raw/classification.json",
            err.getvalue(),
        )

    def test_an_unreadable_file_is_refused_by_fill_unwritten(self) -> None:
        f = self.area / "output" / "locked.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x\n", encoding="utf-8")
        self.unreadable(f)
        before = self.protocol.read_bytes()
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = protocol_fill.main([str(self.protocol), "--evidence-file", str(f)])
        self.assertEqual(code, 2)
        self.assertIn("cannot be read: experiments/01/output/locked.md", err.getvalue())
        self.assertEqual(self.protocol.read_bytes(), before)


class OutsideRepo(_Filled):
    """A declared path that leads out of the repository through a symlink
    is refused when declared and when read, never shown; a link that stays
    inside the repository is read as before."""

    #: what the file outside the repository holds, never to reach a prompt
    MARK = "OUTSIDE-REPOSITORY-MARK\n"

    def outside_dir(self) -> Path:
        """A folder beside the repository holding `secret.json`."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        outside = Path(tmp.name).resolve()
        (outside / "secret.json").write_text(self.MARK, encoding="utf-8")
        return outside

    def link_to_the_file(self) -> str:
        """`data/raw/out.json` in the area, a link to the file outside."""
        (self.area / "data" / "raw" / "out.json").symlink_to(
            self.outside_dir() / "secret.json"
        )
        return "data/raw/out.json"

    def link_to_its_folder(self) -> str:
        """`away/` in the area, a link to the folder outside: the declared
        path `away/secret.json` is itself no link."""
        (self.area / "away").symlink_to(self.outside_dir(), target_is_directory=True)
        return "away/secret.json"

    def declare_also(self, rel: str) -> None:
        """The protocol written by hand with REL declared beside the
        classification, its sha256 the outside file's own."""
        self.declare(
            evidence_table("data/raw/classification.json", sha256(CLASSIFICATION))
            + "\n"
            + evidence_table(rel, sha256(self.MARK))
        )

    def test_fill_refuses_a_link_out_of_the_repository_unwritten(self) -> None:
        for what, link in (
            ("the file is a link", self.link_to_the_file),
            ("a folder on the way is a link", self.link_to_its_folder),
        ):
            with self.subTest(what=what):
                rel = link()
                before = self.protocol.read_bytes()
                code, _, err = self.fill("--evidence-file", str(self.area / rel))
                self.assertEqual(code, 2)
                self.assertIn("lead out of the repository", err)
                self.assertIn(f"experiments/01/{rel}", err)
                self.assertEqual(self.protocol.read_bytes(), before)

    def test_the_audit_refuses_a_declared_link_out_of_the_repository(self) -> None:
        """Declared by hand with the matching sha256: refused when the
        prompt is built, the file's content in no message."""
        for what, link in (
            ("the file is a link", self.link_to_the_file),
            ("a folder on the way is a link", self.link_to_its_folder),
        ):
            with self.subTest(what=what):
                rel = link()
                self.declare_also(rel)
                why = self.refusal()
                self.assertIn("lead out of the repository", why)
                self.assertIn(f"experiments/01/{rel}", why)
                self.assertNotIn(self.MARK.strip(), why)

    def test_the_command_refuses_it_before_the_model_is_called(self) -> None:
        self.declare_also(self.link_to_the_file())
        err = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete") as call,
            contextlib.redirect_stderr(err),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = audit.main([str(self.area), "--mode", "preflight"])
        self.assertEqual(code, 2)
        call.assert_not_called()
        self.assertIn("lead out of the repository", err.getvalue())

    def test_the_twin_a_link_inside_the_repository_is_shown(self) -> None:
        """A link to another area's data stays allowed: declared through
        the command, its content stands in the prompt."""
        self.linked_cases()
        code, _, err = self.fill(
            "--evidence-file", str(self.area / "linked" / "cases.json")
        )
        self.assertEqual(code, 0, err)
        self.assertIn("EVIDENCE FILE: experiments/01/linked/cases.json", self.prompt())

    def test_the_stamp_does_not_take_the_outside_files_content(self) -> None:
        """The file outside is never read for the stamp: its content
        changing leaves the stamp, and the stamp is not the one of the
        same bytes held inside the repository."""
        for what, link in (
            ("a folder on the way is a link", self.link_to_its_folder),
            ("the file is a link", self.link_to_the_file),
        ):
            with self.subTest(what=what):
                rel = link()
                self.declare_also(rel)
                linked = scope_sha.area_stamp(self.area)[0]
                target = (self.area / rel).resolve()
                target.write_text("other content\n", encoding="utf-8")
                self.assertEqual(scope_sha.area_stamp(self.area)[0], linked)
        # the file link, declared last, replaced by a file of the repository
        (self.area / rel).unlink()
        (self.area / rel).write_text(self.MARK, encoding="utf-8")
        self.assertNotEqual(scope_sha.area_stamp(self.area)[0], linked)
        self.assertIn(f"EVIDENCE FILE: experiments/01/{rel}", self.prompt())


if __name__ == "__main__":
    unittest.main()
