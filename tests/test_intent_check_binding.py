"""Tests for intent-check's choice BY BINDING (protocol head id).

Why this exists: the choice used to be made by directory — newest run in
the area with intent keys. In a series area (`PROTOCOL-s1-*` ...
`PROTOCOL-s13-*`) that pairs a protocol with whatever ran last, and the
check comes back green about promises nobody made here.

The decisive fixture is two protocols registering THE SAME intent ids. If
the choice were driven by the set of ids — or by `protocol.path`, or by
recency — such a test would pass while the mechanism is broken. Only the
binding tells them apart.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks import intent_check  # noqa: E402
from labkit.formats import answering_run, runs  # noqa: E402
from protocol_fixture import run_record, head  # noqa: E402

A_ID = "p-aaaaaaaaaaaaaaaa"
B_ID = "p-bbbbbbbbbbbbbbbb"
#: Both protocols promise exactly this — only the binding can separate them.
SAME_IDS = (
    "- **Inference criterion:** [criterion-1] holds and [criterion-2] holds\n"
    "- **Quality check:** [quality-check-1] yield above 90%\n"
)
#: Every promise of SAME_IDS reported.
FULL = {
    "criterion_1_pass": True,
    "criterion_2_pass": True,
    "quality_check_1_pass": True,
}


def _protocol(area: Path, name: str, pid: str | None, body=SAME_IDS) -> Path:
    """`pid=None` writes an unstamped head (the `<protocol-id>` placeholder)."""
    p = area / name
    p.write_text(head(id=pid or "<protocol-id>") + body, encoding="utf-8")
    return p


def _run(
    area: Path,
    name: str,
    *,
    pid: str | None,
    metrics: dict,
    schema: int | None = runs.RUN_SCHEMA,
    completion=True,
    with_metrics=True,
) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    cfg: dict = {"script": "01_measure.py", "pid": 1}
    if schema is not None:
        cfg["schema_version"] = schema
        cfg["run_kind"] = "measurement"
        cfg["protocol"] = {"id": pid, "path": "whatever.md"}
    (d / "config.json").write_text(
        json.dumps(
            run_record(
                cfg, drop=() if schema is not None else ("schema_version", "run_kind")
            )
        ),
        encoding="utf-8",
    )
    if with_metrics:
        (d / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    if completion:
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
    return d


def _check(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = intent_check.main([str(a) for a in argv])
    return code, buf.getvalue()


class TestTwoProtocolsSameIntentIds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.area = Path(self.tmp.name)
        self.a = _protocol(self.area, "PROTOCOL-s1-a.md", A_ID)
        self.b = _protocol(self.area, "PROTOCOL-s2-b.md", B_ID)

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_protocol_reads_its_own_run(self):
        """A's run satisfies all promises, B's is missing c2. Same ids in
        both protocols, so only the binding can produce both verdicts."""
        _run(self.area, "2026-01-01T00-00-00_aaaa", pid=A_ID, metrics=FULL)
        _run(
            self.area,
            "2026-01-01T00-00-01_bbbb",
            pid=B_ID,
            metrics={"criterion_1_pass": True, "quality_check_1_pass": True},
        )

        code_a, out_a = _check([self.a])
        self.assertEqual(code_a, 0, out_a)
        self.assertIn("all report", out_a)

        code_b, out_b = _check([self.b])
        self.assertEqual(code_b, 1, out_b)
        self.assertIn("[criterion-2] registered", out_b)

    def test_a_newer_run_of_the_other_protocol_does_not_shadow(self):
        """Recency must not beat the binding: B's run is newer and would win
        under the old area-wide rule."""
        _run(self.area, "2026-01-01T00-00-00_aaaa", pid=A_ID, metrics=FULL)
        _run(
            self.area,
            "2026-01-01T09-00-00_bbbb",
            pid=B_ID,
            metrics={"nothing": 1, "criterion_1_pass": True},
        )
        # B's run reports neither c2 nor a1, so picking it would fail the
        # check — exit 0 is itself the proof that A's run was used.
        code, out = _check([self.a])
        self.assertEqual(code, 0, out)
        cands, _ = answering_run.bound_runs(self.area, A_ID)
        self.assertEqual([c.dir.name for c in cands], ["2026-01-01T00-00-00_aaaa"])

    def test_no_bound_run_exits_2_and_says_why_each_was_left_out(self):
        _run(self.area, "2026-01-01T00-00-00_bbbb", pid=B_ID, metrics=FULL)
        _run(
            self.area,
            "2026-01-01T00-00-01_unfi",
            pid=A_ID,
            metrics={"criterion_1_pass": True},
            completion=False,
        )
        _run(
            self.area,
            "2026-01-01T00-00-02_corr",
            pid=A_ID,
            metrics={},
            with_metrics=False,
        )
        _run(
            self.area,
            "2026-01-01T00-00-03_unbd",
            pid=None,
            metrics={"criterion_1_pass": True},
        )
        code, out = _check([self.a])
        self.assertEqual(code, 2, out)
        self.assertIn(f"no completed run bound to {A_ID}", out)
        self.assertIn(f"bound to {B_ID}", out)
        self.assertIn("unfinalized", out)
        self.assertIn("corrupt", out)
        self.assertIn("unbound", out)

    def test_unfinalized_and_corrupt_never_enter_the_choice(self):
        """Both carry this protocol's id and full metrics — only their
        state keeps them out."""
        _run(
            self.area,
            "2026-01-01T00-00-01_unfi",
            pid=A_ID,
            metrics=FULL,
            completion=False,
        )
        code, out = _check([self.a])
        self.assertEqual(code, 2, out)
        self.assertIn("unfinalized", out)

    def test_probe_run_does_not_shadow_the_gate_run_among_bound_runs(self):
        """The 2026-09-09 rule, now inside the bound set."""
        _run(self.area, "2026-01-01T00-00-00_gate", pid=A_ID, metrics=FULL)
        _run(self.area, "2026-01-01T00-00-01_prob", pid=A_ID, metrics={"calls": 12})
        code, out = _check([self.a])
        self.assertEqual(code, 0, out)
        self.assertIn("skipped 1 newer bound run(s)", out)

    def test_path_is_never_the_criterion(self):
        """protocol.path may be stale or plain wrong; the id decides."""
        d = _run(self.area, "2026-01-01T00-00-00_aaaa", pid=A_ID, metrics=FULL)
        cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
        cfg["protocol"]["path"] = "PROTOCOL-s2-b.md"  # points at B
        (d / "config.json").write_text(json.dumps(run_record(cfg)), encoding="utf-8")
        code, out = _check([self.a])
        self.assertEqual(code, 0, out)
        code_b, out_b = _check([self.b])
        self.assertEqual(code_b, 2, out_b)


class TestExplicitMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.area = Path(self.tmp.name)
        self.a = _protocol(self.area, "PROTOCOL-s1-a.md", A_ID)

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_id_is_allowed(self):
        d = _run(self.area, "r1", pid=A_ID, metrics=FULL)
        code, out = _check([self.a, "--metrics", d / "metrics.json"])
        self.assertEqual(code, 0, out)
        self.assertNotIn("WARNING", out)

    def test_another_id_is_a_hard_abort(self):
        d = _run(self.area, "r1", pid=B_ID, metrics=FULL)
        code, out = _check([self.a, "--metrics", d / "metrics.json"])
        self.assertEqual(code, 2, out)
        self.assertIn(f"belongs to protocol {B_ID}", out)

    def test_unbound_v2_run_is_allowed_with_a_warning(self):
        d = _run(self.area, "r1", pid=None, metrics=FULL)
        code, out = _check([self.a, "--metrics", d / "metrics.json"])
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING", out)
        self.assertIn("unbound", out)

    def test_the_warning_is_a_note_not_a_finding(self):
        """`hold` keeps the choice's lines apart from the findings: finalize
        made every printed line a blocker, the unbound warning among them
        (audit follow-up 2026-10-23, F4)."""
        d = _run(self.area, "r1", pid=None, metrics={"criterion_1_pass": True})
        held = intent_check.hold(self.a, d / "metrics.json")
        self.assertEqual(len(held.notes), 1, held)
        self.assertIn("unbound", held.notes[0])
        self.assertTrue(held.findings, held)
        self.assertTrue(all("registered" in f.text for f in held.findings), held)
        self.assertEqual(held.summary, "")

    def test_pre_schema_run_is_rejected(self):
        """A run without `schema_version >= 2` is read with labkit 0.47;
        here its metadata is unreadable, so naming it explicitly is no loophole."""
        d = _run(self.area, "r1", pid=None, schema=None, completion=False, metrics=FULL)
        code, out = _check([self.a, "--metrics", d / "metrics.json"])
        self.assertEqual(code, 2, out)
        self.assertIn("not completed (unreadable)", out)
        self.assertIn("labkit 0.47", out)

    def test_incomplete_v2_run_is_rejected_even_when_named_explicitly(self):
        """A v2 run with metrics.json but no completion.json must fail.

        Before the fix, the explicit --metrics path skipped the state check,
        so naming the file was a loophole around the completion gate.
        """
        d = _run(self.area, "r1", pid=A_ID, completion=False, metrics=FULL)
        code, out = _check([self.a, "--metrics", d / "metrics.json"])
        self.assertEqual(code, 2, out)
        self.assertIn("not completed", out)


class TestUnstampedAndProseHead(unittest.TestCase):
    """No id, no binding: the run is named, never guessed. A prose head
    (`- **Standard:** 0.16`) is no head at all and is refused loudly."""

    def test_unstamped_id_needs_explicit_metrics(self):
        with tempfile.TemporaryDirectory() as t:
            area = Path(t)
            proto = _protocol(area, "PROTOCOL-new.md", None)
            _run(area, "2026-01-01T00-00-00_aaaa", pid=None, metrics=FULL)
            code, out = _check([proto])
        self.assertEqual(code, 2, out)
        self.assertIn("no stamped id", out)
        self.assertIn("--metrics", out)

    def test_unstamped_id_with_explicit_metrics_checks(self):
        with tempfile.TemporaryDirectory() as t:
            area = Path(t)
            proto = _protocol(area, "PROTOCOL-new.md", None)
            d = _run(area, "r1", pid=None, metrics=FULL)
            code, out = _check([proto, "--metrics", d / "metrics.json"])
        self.assertEqual(code, 0, out)
        self.assertIn("all report", out)

    def test_prose_head_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            area = Path(t)
            proto = area / "PROTOCOL-old.md"
            proto.write_text(
                f"- **Standard:** 0.16\n- **Protocol id:** {A_ID}\n" + SAME_IDS,
                encoding="utf-8",
            )
            _run(area, "2026-01-01T00-00-00_aaaa", pid=A_ID, metrics=FULL)
            code, out = _check([proto])
        self.assertEqual(code, 2, out)
        self.assertIn("no [protocol] table", out)


if __name__ == "__main__":
    unittest.main()
