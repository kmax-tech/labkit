"""agent_transcript reads what an agent did from its session transcript —
the measurement the self-reported probe log could not be (re-measure
2026-10-07: a read through `inspect.signature` never reached the log)."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from labkit.probes import agent_transcript as at

ROOT = Path("/probe/count-1")
SOURCE = re.compile(r"labkit/\w+\.py|labkit/docs/standard|arbeitsstandard", re.I)
HOOK_TEXT = 'echo "pre-commit: must fields missing (see above)"\n'


def transcript(calls: list[tuple[float, str, dict, float, str]]) -> Path:
    """(start second, tool, input, seconds until the result, output) per call."""
    records = [{"type": "user", "timestamp": "2026-10-07T14:00:00Z", "message": {}}]
    for n, (t0, tool, inp, dur, output) in enumerate(calls):
        records.append(
            {
                "type": "assistant",
                "timestamp": f"2026-10-07T14:00:{t0:06.3f}Z",
                "message": {
                    "content": [
                        {"type": "tool_use", "id": f"u{n}", "name": tool, "input": inp}
                    ],
                    # what the call cost: the context grows by 1000 per call
                    "usage": {
                        "input_tokens": 3,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 1000 * n,
                        "cache_creation_input_tokens": 1000,
                    },
                },
            }
        )
        records.append(
            {
                "type": "user",
                "timestamp": f"2026-10-07T14:00:{t0 + dur:06.3f}Z",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": f"u{n}",
                            "content": output,
                        }
                    ]
                },
            }
        )
    d = tempfile.mkdtemp()
    path = Path(d) / "agent.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n\n", encoding="utf-8"
    )
    return path


def bash(cmd: str) -> dict:
    return {"command": f"cd {ROOT} && L={ROOT}.log.md && echo x >> $L && {cmd}"}


CALLS = [
    (2.0, "Bash", bash("cat TASK.md && wc -l CLAUDE.md"), 1.0, "..."),
    (5.0, "Read", {"file_path": f"{ROOT}/experiments/01-x/PROTOCOL-x.md"}, 0.5, "..."),
    (
        8.0,
        "Bash",
        bash(
            ".venv/bin/python - <<'EOF'\nfrom labkit.checks import recheck\nimport inspect\n"
            "print(inspect.signature(recheck.holds))\nEOF"
        ),
        1.0,
        "(run_dir)",
    ),
    (12.0, "Bash", bash("cat > scripts/m.py <<'EOF'\nprint(1)\nEOF"), 0.5, ""),
    (15.0, "Bash", bash("cat .githooks/pre-commit | head -40"), 0.5, HOOK_TEXT),
    (
        20.0,
        "Bash",
        bash("git commit -m x 2>&1 | tail -5"),
        2.0,
        "x\npre-commit: must fields missing (see above)\n",
    ),
    (
        25.0,
        "Bash",
        bash(".venv/bin/protocol-check --contract; .venv/bin/finalize ."),
        3.0,
        "",
    ),
]


class Measured(unittest.TestCase):
    def setUp(self):
        self.t = at.trace(transcript(CALLS), ROOT, SOURCE)

    def test_wall_clock_runs_from_first_to_last_record(self):
        self.assertEqual(self.t.wall_seconds, 28)

    def test_tool_time_is_the_sum_of_call_to_result(self):
        self.assertEqual(self.t.tool_seconds, round(1 + 0.5 + 1 + 0.5 + 0.5 + 2 + 3))
        self.assertEqual(self.t.calls, 7)

    def test_commands_count_by_position_not_inside_a_heredoc(self):
        self.assertEqual(self.t.commands, {"protocol-check": 1, "finalize": 1})

    def test_tokens_sum_the_usage_blocks_and_keep_the_largest_context(self):
        n = len(CALLS)
        self.assertEqual(
            self.t.tokens,
            at.Tokens(
                calls=n,
                input=3 * n,
                output=50 * n,
                cache_read=1000 * sum(range(n)),
                cache_creation=1000 * n,
                context_max=3 + 1000 * (n - 1) + 1000,
            ),
        )

    def test_a_count_that_is_not_an_integer_names_its_line(self):
        path = transcript(CALLS[:1])
        text = path.read_text(encoding="utf-8").replace(
            '"output_tokens": 50', '"output_tokens": "50"'
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(at.TranscriptError) as cm:
            at.tokens(path)
        self.assertIn("agent.jsonl:2: usage.output_tokens", str(cm.exception))

    def test_a_transcript_without_usage_counts_no_calls(self):
        path = transcript(CALLS[:1])
        records = [
            json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln
        ]
        for r in records:
            r.get("message", {}).pop("usage", None)
        path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        self.assertEqual(at.tokens(path).calls, 0)
        self.assertEqual(at.describe_tokens(at.tokens(path)), "no usage recorded")


class Heuristic(unittest.TestCase):
    def setUp(self):
        self.t = at.trace(transcript(CALLS), ROOT, SOURCE)

    def test_reads_are_the_read_verbs_arguments_and_file_tools(self):
        self.assertEqual(
            self.t.files_read,
            [
                "TASK.md",
                "CLAUDE.md",
                "experiments/01-x/PROTOCOL-x.md",
                ".githooks/pre-commit",
            ],
        )

    def test_writing_with_cat_is_no_read(self):
        self.assertNotIn("scripts/m.py", self.t.files_read)

    def test_an_introspection_call_is_a_source_read(self):
        self.assertEqual(self.t.source_reads, ["inspect.signature(recheck.holds)"])

    def test_a_refusal_is_the_hook_speaking_not_its_script_shown(self):
        self.assertEqual(self.t.refusals, 1)


class Refusals(unittest.TestCase):
    def test_a_transcript_of_another_probe_is_refused(self):
        with self.assertRaises(at.TranscriptError) as cm:
            at.trace(transcript(CALLS), Path("/probe/other"), SOURCE)
        self.assertIn("not this probe's transcript", str(cm.exception))

    def test_a_broken_line_names_its_number(self):
        path = transcript(CALLS)
        path.write_text(path.read_text() + "{not json\n", encoding="utf-8")
        with self.assertRaises(at.TranscriptError) as cm:
            at.read_calls(path)
        self.assertIn(":17:", str(cm.exception))


class Gzipped(unittest.TestCase):
    def test_an_archived_transcript_reads_like_the_original(self):
        import gzip

        plain = transcript(CALLS)
        packed = plain.with_suffix(".jsonl.gz")
        packed.write_bytes(gzip.compress(plain.read_bytes(), mtime=0))
        self.assertEqual(at.timeline(packed), at.timeline(plain))


class Timeline(unittest.TestCase):
    def test_bookkeeping_and_heredoc_bodies_are_cut(self):
        lines = at.timeline(transcript(CALLS))
        self.assertTrue(
            lines[0].startswith(" 0:02   1.0s Bash   cat TASK.md && wc -l CLAUDE.md"),
            lines[0],
        )
        self.assertNotIn("from labkit", lines[2])
        self.assertTrue(lines[5].endswith("REFUSED"), lines[5])
        self.assertFalse(lines[4].endswith("REFUSED"), lines[4])
        self.assertTrue(
            lines[-1].startswith("tokens: 7 calls · output 350 · context max "),
            lines[-1],
        )


class Commands(unittest.TestCase):
    def test_every_installed_command_counts_and_no_other(self):
        """The hand list missed labkit-params and labkit-audit and named a
        `recheck` labkit never installed (audit 2026-10-18)."""
        line = "labkit-params experiments/01-x && recheck x; labkit-audit 01 --mode preflight"
        self.assertEqual(at.labkit_commands(line), ["labkit-params", "labkit-audit"])


class OutsidePaths(unittest.TestCase):
    """Paths the agent used outside its probe: judge-2 of 2026-10-20 named
    its audit output `/tmp/j2_audit.out` as an earlier probe had, and read
    that probe's file first. The score lists such paths for the operator —
    static evidence, a shared store the isolation did not cover."""

    def test_a_shared_store_is_listed_the_probe_its_log_and_null_are_not(self):
        calls = [
            (
                2.0,
                "Bash",
                bash("labkit-audit x --mode analysis > /tmp/j2_audit.out 2>/dev/null"),
                1.0,
                "",
            ),
            (
                4.0,
                "Bash",
                bash(f"cat /tmp/j2_audit.out; ls {ROOT}/experiments"),
                1.0,
                "",
            ),
            (6.0, "Read", {"file_path": "/Users/someone/other-probe/RUNS.md"}, 0.5, ""),
            (
                8.0,
                "Bash",
                bash(f"cat {ROOT}.log.md; sed -n 's/a/b/' x; /usr/bin/env true"),
                1.0,
                "",
            ),
            # an unexpanded `"$D"/x` and `/` alone are no store
            (9.0, "Bash", bash('git diff > "$D"/x.patch; ls / >/dev/null'), 1.0, ""),
        ]
        got = at.trace(transcript(calls), ROOT, SOURCE).outside_paths
        self.assertEqual(
            got, ["/tmp/j2_audit.out", "/Users/someone/other-probe/RUNS.md"]
        )

    def test_a_probe_inside_its_dir_lists_none(self):
        self.assertEqual(at.trace(transcript(CALLS), ROOT, SOURCE).outside_paths, [])


class RecordsWithoutTimestamp(unittest.TestCase):
    """Claude Code 2.1.285 writes session bookkeeping without a timestamp
    (`atis-latch`, `last-prompt`, `cost-state`; the sandbox probe of
    2026-10-21). Those carry no call and are skipped; a message record
    without one is still refused."""

    def with_record(self, record: dict) -> Path:
        path = transcript(CALLS)
        lines = path.read_text(encoding="utf-8").splitlines()
        lines.insert(2, json.dumps(record))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_bookkeeping_without_a_timestamp_is_skipped(self):
        for kind in ("atis-latch", "last-prompt", "cost-state"):
            with self.subTest(kind=kind):
                path = self.with_record({"type": kind, "sessionId": "s"})
                self.assertEqual(
                    at.trace(path, ROOT, SOURCE).calls,
                    at.trace(transcript(CALLS), ROOT, SOURCE).calls,
                )

    def test_a_message_without_a_timestamp_is_refused(self):
        path = self.with_record(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "x"}]},
            }
        )
        with self.assertRaisesRegex(at.TranscriptError, "without a timestamp"):
            at.trace(path, ROOT, SOURCE)


if __name__ == "__main__":
    unittest.main()
