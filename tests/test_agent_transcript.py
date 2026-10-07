"""agent_transcript reads what an agent did from its session transcript —
the measurement the self-reported probe log could not be (re-measure
2026-10-07: a read through `inspect.signature` never reached the log)."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from labkit import agent_transcript as at

ROOT = Path("/probe/count-1")
SOURCE = re.compile(r"labkit/\w+\.py|arbeitsstandard", re.I)
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
                    ]
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
            ".venv/bin/python - <<'EOF'\nfrom labkit import recheck\nimport inspect\n"
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


if __name__ == "__main__":
    unittest.main()
