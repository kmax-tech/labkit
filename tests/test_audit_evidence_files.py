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


if __name__ == "__main__":
    unittest.main()
