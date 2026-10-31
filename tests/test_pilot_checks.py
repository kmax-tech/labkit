"""The pilot must fail before spending money on the wrong sandbox revision."""

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

PILOT = (
    Path(__file__).resolve().parents[1] / "docs/usability/2026-10-31-registered-pilot"
)
COMMIT = "d" * 40
PIN = f"agentsandbox @ git+file:///sandbox@{COMMIT}\n"


@pytest.fixture
def checks(monkeypatch):
    monkeypatch.syspath_prepend(str(PILOT))
    return importlib.import_module("pilot_checks")


def vcs(commit=COMMIT):
    return json.dumps({"vcs_info": {"vcs": "git", "commit_id": commit}})


@pytest.mark.parametrize(
    "metadata, message",
    [
        (None, "missing"),
        ("{}", "directory"),
        ('{"dir_info": {"editable": true}}', "directory"),
        ('{"vcs_info": {"vcs": "git"}}', "commit_id"),
        (vcs("e" * 40), "differs"),
        ("[]", "object"),
        ("{", "property name"),
    ],
)
def test_commit_refuses_missing_directory_and_wrong_revision(checks, metadata, message):
    # Both real installations said 0.1.0; the pilot install had only dir_info.
    with pytest.raises(ValueError, match=message):
        checks.validate_sandbox_commit(PIN, metadata)


def test_correct_commit_passes_and_version_is_not_the_proof(
    checks, monkeypatch, tmp_path
):
    (tmp_path / "requirements.txt").write_text(PIN)
    distribution = SimpleNamespace(version="0.1.0", read_text=lambda name: vcs())
    monkeypatch.setattr(
        checks.importlib.metadata, "distribution", lambda name: distribution
    )
    assert checks.read_environment(tmp_path)["agentsandbox_commit"] == COMMIT
    assert checks.validate_sandbox_commit(PIN, vcs(COMMIT.upper())) == COMMIT


@pytest.mark.parametrize("pin", ["", PIN + PIN, PIN.replace(COMMIT, "main")])
def test_pin_must_be_unique_and_immutable(checks, pin):
    with pytest.raises(ValueError, match="exactly one full Git commit"):
        checks.validate_sandbox_commit(pin, vcs())


@pytest.mark.parametrize("failure", ["copy", "start", "timeout", "setup", None])
def test_setup_checks_exit_and_always_removes_its_container(
    checks, monkeypatch, failure
):
    calls = []

    def docker(args, stdin=None):
        calls.append((args, stdin))
        if args[0] == "cp" and failure == "copy":
            raise RuntimeError("copy failed")
        if args[0] == "start" and failure == "start":
            raise RuntimeError("start failed")
        if args[0] == "start" and failure == "timeout":
            raise subprocess.TimeoutExpired("docker", 120)
        if args[0] == "inspect":
            # A CLI returning zero must not conceal a failing setup in the image.
            return json.dumps(
                {"ExitCode": 1 if failure == "setup" else 0, "OOMKilled": False}
            )
        return "one labkit: 0.104.3\n" if args[0] == "start" else ""

    monkeypatch.setattr(checks, "docker_output", docker)
    if failure:
        with pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
            checks.check_setup("image", b"tar", {"PATH": "/work/.venv/bin"}, "setup")
    else:
        assert "one labkit:" in checks.check_setup(
            "image", b"tar", {"PATH": "/work/.venv/bin"}, "setup"
        )
    assert calls[-1][0][:2] == ["rm", "-f"]
    assert calls[0][0][3:5] == ["--network", "none"]
    assert calls[1][1] == b"tar"
    assert all("claude -p" not in str(call) for call in calls)


@pytest.fixture
def runner(checks, monkeypatch):
    for name in (
        "agentsandbox",
        "agentsandbox.config",
        "agentsandbox.agents",
        "agentsandbox.attempt",
        "sandboxlab",
        "sandboxlab.batch",
        "sandboxlab.benches",
        "labkit",
    ):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    spec = importlib.util.spec_from_file_location(
        "pilot_under_test", PILOT / "run_pilot.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ARMS_ONLY", ())
    return module


def test_check_stops_on_wrong_environment_before_build_or_key(runner, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_pilot.py", "--check"])
    monkeypatch.setattr(
        runner, "read_environment", MagicMock(side_effect=ValueError("wrong commit"))
    )
    with pytest.raises(ValueError, match="wrong commit"):
        runner.main()
    runner.infra.build_images.assert_not_called()
    runner.run_batch.assert_not_called()


def test_check_uses_shared_preparation_and_never_runs_batch_or_reads_key(
    runner, monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "argv", ["run_pilot.py", "--check", "--only", "21"])
    monkeypatch.setattr(
        runner, "read_environment", lambda repo: {"agentsandbox_commit": COMMIT}
    )
    monkeypatch.setattr(runner, "LIMITS", SimpleNamespace(timeout_s=2400))
    runner.infra.build_images.return_value = {"agent": "image", "proxy": "proxy"}
    runner.infra.labkit_pin.return_value = COMMIT
    runner.llm.resolve = MagicMock(return_value={"model": "solver"})
    prepare = MagicMock(return_value=["constructed attempts"])
    monkeypatch.setattr(runner, "prepare_attempts", prepare)
    probe = MagicMock(return_value={"model_calls": 0, "snapshots": {}})
    monkeypatch.setattr(runner, "check_attempts", probe)
    monkeypatch.setattr(
        runner, "api_key", MagicMock(side_effect=AssertionError("read secret"))
    )
    monkeypatch.setattr(runner, "S", tmp_path)
    runner.main()
    prepare.assert_called_once_with(
        {"agent": "image", "proxy": "proxy"}, "solver", ["21"]
    )
    probe.assert_called_once()
    runner.run_batch.assert_not_called()
    runner.api_key.assert_not_called()
    assert json.loads((tmp_path / "check-rp.json").read_text())["model_calls"] == 0


def test_real_pilot_keeps_checked_commit_in_store_provenance(runner, monkeypatch):
    monkeypatch.setattr(runner, "registration", lambda task: ("protocol", "plan"))
    monkeypatch.setattr(runner, "LIMITS", SimpleNamespace(timeout_s=2400))
    monkeypatch.setattr(runner, "api_key", lambda: "test-key")
    environment = {"agentsandbox_commit": COMMIT}
    runner.pilot({"agent": "image"}, "solver", [], environment)
    assert (
        runner.run_batch.call_args.kwargs["prov"]["runner_environment"] == environment
    )


@pytest.mark.parametrize("selection", [["unknown"], ["21", "typo"]])
def test_check_cannot_pass_an_empty_selection_by_typo(runner, selection):
    with pytest.raises(ValueError, match="unknown tasks"):
        runner.validate_selection(selection)


def test_check_executes_setup_per_snapshot_with_inputs_and_protocol(
    runner, monkeypatch, tmp_path
):
    agent = SimpleNamespace(
        setup="real lab setup",
        model="solver",
        env=lambda url: {"PATH": "/work/.venv/bin", "ANTHROPIC_API_KEY": "placeholder"},
    )
    lab = SimpleNamespace(
        snapshot=tmp_path / "lab",
        inputs={"data": tmp_path / "inputs"},
        labels={"arm": "labkit", "task_id": "21"},
        agent=agent,
        attempt_id="lab-r1",
    )
    control = SimpleNamespace(
        snapshot=tmp_path / "control",
        inputs={},
        labels={"arm": "instructions_only", "task_id": "21"},
        agent=SimpleNamespace(setup=None, model="solver", env=lambda url: {}),
        attempt_id="control-r1",
    )
    runner.trees.tree_entries.return_value = [("work/example", b"data", 0o644, None)]
    runner.trees.digest.return_value = "tree-digest"
    runner.trees.tar_stream.return_value = b"owned-tree"
    setup = MagicMock(side_effect=["one labkit: 0.104.3\n", ""])
    monkeypatch.setattr(runner, "check_setup", setup)
    monkeypatch.setattr(runner, "LIMITS", SimpleNamespace(timeout_s=2400))
    report = runner.check_attempts(
        {"agent": "image", "proxy": "proxy"}, [lab, lab, control], {}
    )
    assert setup.call_count == 2
    script = setup.call_args_list[0].args[3]
    assert "real lab setup" in script
    assert "protocol-check experiments/01-task-21/PROTOCOL-task-21.md" in script
    assert setup.call_args_list[1].args[3] == "cd /work && (:)"
    assert runner.trees.tree_entries.call_count == 3  # two snapshots and one input
    assert len(report["snapshots"]) == 2
    assert report["model_calls"] == 0


def test_failed_check_does_not_write_success_report(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["run_pilot.py", "--check"])
    monkeypatch.setattr(runner, "read_environment", lambda repo: {})
    monkeypatch.setattr(runner, "LIMITS", SimpleNamespace(timeout_s=2400))
    monkeypatch.setattr(runner, "prepare_attempts", lambda *args: ["attempt"])
    runner.infra.build_images.return_value = {"agent": "image"}
    runner.infra.labkit_pin.return_value = COMMIT
    runner.llm.resolve = MagicMock(return_value={"model": "solver"})
    monkeypatch.setattr(
        runner, "check_attempts", MagicMock(side_effect=RuntimeError("setup failed"))
    )
    monkeypatch.setattr(runner, "S", tmp_path)
    with pytest.raises(RuntimeError, match="setup failed"):
        runner.main()
    assert not list(tmp_path.iterdir())
    runner.run_batch.assert_not_called()
