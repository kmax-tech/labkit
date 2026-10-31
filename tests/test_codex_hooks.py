"""Codex wire events exercise the same gates as Claude Code."""

import contextlib
import io
import json
import os
import unittest
from unittest import mock

from labkit.gates import codex_hooks
import test_agent_hooks as shared_tests
from test_agent_hooks import _repo, _transcript


def invoke(action, event):
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch("sys.stdin", io.StringIO(json.dumps(event))),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        rc = codex_hooks.main([action])
    return rc, out.getvalue(), err.getvalue()


def wire_event(root, event_name, **fields):
    return {
        "hook_event_name": event_name,
        "session_id": "codex-session",
        "turn_id": "codex-turn",
        "cwd": str(root),
        "transcript_path": str(_transcript()),
        **fields,
    }


class CodexAdapter(unittest.TestCase):
    def test_explicit_cd_locates_the_script_missing_from_the_session_directory(self):
        """Codex 0.165 drops exec_command.workdir from canonical hook input.

        Missing script context must refuse with a retry, rather than pass.
        """
        root = _repo(True)
        event = wire_event(
            root,
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "python 01_measure.py"},
        )
        rc, _, err = invoke("pre-run", event)
        self.assertEqual(rc, 2, err)
        self.assertIn("exec_command.workdir", err)
        self.assertIn("Next:", err)
        for command in (
            "./01_measure.py",
            "SETTING=value ./01_measure.py",
            "LABKIT_PREFLIGHT=skip python 01_measure.py",
        ):
            with self.subTest(command=command):
                event["tool_input"]["command"] = command
                self.assertEqual(invoke("pre-run", event)[0], 2)
        event["tool_input"]["command"] = (
            "cd experiments/01-x/scripts && python 01_measure.py"
        )
        rc, _, err = invoke("pre-run", event)
        self.assertEqual(rc, 2, err)
        self.assertIn("preflight", err)

    def test_resolved_non_measurement_and_explicit_probe_pass(self) -> None:
        root = _repo(True)
        helper = root / "helper.py"
        helper.write_text("print('ok')\n")
        for command in (
            "python helper.py",
            "./helper.py",
            "SETTING=value ./helper.py",
            f"python {helper}",
            f"cd {root} && python helper.py",
            "python 01_measure.py --probe 3",
            "sed -n 1,5p missing.py",
            "sed -n 1,5p ./missing.py",
            "cat ./missing.py",
            "rg runlog ./missing.py",
            "python -c 'print(1)'",
        ):
            with self.subTest(command=command):
                event = wire_event(
                    root,
                    "PreToolUse",
                    tool_name="Bash",
                    tool_input={"command": command},
                )
                self.assertEqual(invoke("pre-run", event)[0], 0)

    def test_probe_in_another_segment_does_not_free_unresolved_script(self) -> None:
        root = _repo(True)
        event = wire_event(
            root,
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "python missing.py --probe 3; python 01_measure.py"},
        )
        rc, _, err = invoke("pre-run", event)
        self.assertEqual(rc, 2, err)
        self.assertIn("01_measure.py", err)

    def test_frozen_run_blocks_and_probe_passes_even_with_a_claude_directory(self):
        root = _repo(True)
        scripts = root / "experiments/01-x/scripts"
        event = wire_event(
            scripts,
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "python 01_measure.py"},
        )
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": "/no-such-repo"}):
            rc, _, err = invoke("pre-run", event)
            self.assertEqual(rc, 2, err)
            event["tool_input"]["command"] += " --probe 3"
            self.assertEqual(invoke("pre-run", event)[0], 0)

    def test_patch_checks_the_changed_protocol_and_caches_the_context(self):
        root = _repo(False)
        protocol = root / "experiments/01-x/PROTOCOL-x.md"
        protocol.write_text("# broken protocol\n")
        event = wire_event(
            root,
            "PostToolUse",
            tool_name="apply_patch",
            tool_input={"command": "*** Begin Patch\n*** End Patch"},
        )
        rc, out, err = invoke("post-change", event)
        self.assertEqual(rc, 0, err)
        context = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(context["hookEventName"], "PostToolUse")
        self.assertIn("PROTOCOL-x.md", context["additionalContext"])
        self.assertEqual(invoke("post-change", event), (0, "", ""))

    def test_invalid_wire_fields_are_named_and_block(self):
        root = _repo(False)
        event = wire_event(root, "Stop", stop_hook_active=False)
        for field, bad in (
            ("session_id", None),
            ("cwd", "relative"),
            ("stop_hook_active", "false"),
            ("transcript_path", []),
            ("hook_event_name", "SessionEnd"),
        ):
            with self.subTest(field=field):
                rc, _, err = invoke("stop", {**event, field: bad})
                self.assertEqual(rc, 2)
                self.assertIn(field, err)
        self.assertEqual(invoke("stop", [event])[0], 2)
        event = wire_event(
            root, "PreToolUse", tool_name="Bash", tool_input={"cmd": "ls"}
        )
        rc, _, err = invoke("pre-run", event)
        self.assertEqual(rc, 2)
        self.assertIn("tool_input.command", err)

    def test_unknown_action_and_help_do_not_read_stdin(self):
        with (
            mock.patch("sys.stdin") as stdin,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(codex_hooks.main(["missing"]), 2)
            stdin.read.assert_not_called()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(codex_hooks.main(["--help"]), 0)


class CodexStop(shared_tests.Stop):
    """Run the shared stop contract, including clean twins, through Codex JSON."""

    def _stop(self, active=False):
        return invoke(
            "stop",
            {
                "hook_event_name": "Stop",
                "session_id": "s1",
                "cwd": str(self.root),
                "transcript_path": str(self.transcript),
                "stop_hook_active": active,
            },
        )

    def _command(self, command="ls"):
        return invoke(
            "pre-run",
            {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "cwd": str(self.root),
                "transcript_path": str(self.transcript),
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
        )
