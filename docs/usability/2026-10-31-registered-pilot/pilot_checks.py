"""Fail before a pilot starts when its installed sandbox differs from its pin.

Rationale: docs/notes/2026-10-31-pilot-environment.md.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


def validate_sandbox_commit(requirements: str, direct_url: str | None) -> str:
    """Return the installed Git commit when it equals the full requirements pin.

    Raises ValueError for a missing/ambiguous pin, malformed metadata, a
    directory/editable install, or a commit different from the pin. Package
    versions cannot distinguish the sandbox revisions used by this pilot.
    """
    pins = re.findall(
        r"^agentsandbox\s*@\s*git\+\S+@([0-9a-fA-F]{40})\s*$",
        requirements,
        re.M,
    )
    declarations = re.findall(r"^agentsandbox(?:\s|@|=).*$", requirements, re.M)
    if len(pins) != 1 or len(declarations) != 1:
        raise ValueError(
            "requirements.txt: agentsandbox needs exactly one full Git commit pin"
        )
    if direct_url is None:
        raise ValueError("agentsandbox direct_url.json: missing Git commit provenance")
    try:
        info = json.loads(direct_url)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"agentsandbox direct_url.json: malformed JSON: {exc}"
        ) from exc
    if not isinstance(info, dict):
        raise ValueError("agentsandbox direct_url.json: expected an object")
    vcs = info.get("vcs_info")
    if "dir_info" in info or not isinstance(vcs, dict) or vcs.get("vcs") != "git":
        raise ValueError(
            "agentsandbox direct_url.json: install from pinned Git, not a directory or editable checkout"
        )
    commit = vcs.get("commit_id")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError(
            "agentsandbox direct_url.json: commit_id must be a full Git commit"
        )
    if commit.lower() != pins[0].lower():
        raise ValueError(
            f"agentsandbox commit_id {commit} differs from requirements.txt pin {pins[0]}"
        )
    return commit.lower()


def read_environment(repo: Path) -> dict[str, str]:
    """Read and validate this interpreter's agentsandbox against REPO's pin.

    Returns interpreter, package version and commit for store provenance.
    Raises ValueError on mismatches, PackageNotFoundError when absent, and
    OSError when requirements.txt cannot be read. Changes no environment.
    """
    dist = importlib.metadata.distribution("agentsandbox")
    commit = validate_sandbox_commit(
        (repo / "requirements.txt").read_text(encoding="utf-8"),
        dist.read_text("direct_url.json"),
    )
    return {
        "python": sys.executable,
        "agentsandbox_version": dist.version,
        "agentsandbox_commit": commit,
    }


def docker_output(args: list[str], stdin: bytes | None = None) -> str:
    """Run Docker and return stdout; raise with stderr on failure or timeout.

    Commands may create/copy/start/remove disposable check containers. Each
    call is bounded to 120 seconds; no shell or inherited model secret is used.
    """
    result = subprocess.run(
        ["docker", *args], input=stdin, capture_output=True, timeout=120
    )
    if result.returncode:
        raise RuntimeError(
            f"docker {args[0]} failed ({result.returncode}): "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout.decode("utf-8")


def check_setup(image: str, archive: bytes, env: dict[str, str], script: str) -> str:
    """Run SCRIPT on a disposable copy of an attempt tree, with no network.

    ARCHIVE is the same owned tar form the real attempt copies into `/`;
    ENV is the agent's placeholder-only environment. Returns setup output.
    Creates a container, copies the tree, starts only the setup and removes
    the container even on failure. Raises RuntimeError on a failed Docker
    step and TimeoutExpired after 120 seconds. Never runs the agent command.
    """
    name = f"pilot-check-{uuid.uuid4().hex}"
    flags = [item for key, value in env.items() for item in ("-e", f"{key}={value}")]
    docker_output(
        [
            "create",
            "--name",
            name,
            "--network",
            "none",
            *flags,
            image,
            "sh",
            "-c",
            script,
        ]
    )
    try:
        docker_output(["cp", "-a", "-", f"{name}:/"], archive)
        output = docker_output(["start", "-a", name])
        status = json.loads(
            docker_output(["inspect", "--format", "{{json .State}}", name])
        )
        if status["ExitCode"] != 0 or status["OOMKilled"]:
            raise RuntimeError(
                f"setup exited {status['ExitCode']} (OOMKilled={status['OOMKilled']}): {output}"
            )
        return output
    finally:
        docker_output(["rm", "-f", name])


#: a power-management event in `pmset -g log`: its timestamp and kind, the kind
#: padded with spaces up to a tab ("Wake Requests" is no Wake)
_PM_EVENT = re.compile(
    r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}) (Sleep|Wake|DarkWake) *\t", re.M
)


def sleep_intervals(pmset_log: str) -> list[tuple[float, float]]:
    """The host's sleeps in PMSET_LOG (`pmset -g log` text) as (start, end)
    epoch seconds: from a Sleep event to the next Wake or DarkWake; a sleep
    the log does not end stays open (end = inf). Pure; reads nothing else.
    A laptop shut on battery sleeps whatever caffeinate asserts (part 0's
    repetition lost twenty of its forty minutes to 'Clamshell Sleep')."""
    out: list[tuple[float, float]] = []
    start: float | None = None
    for stamp, kind in _PM_EVENT.findall(pmset_log):
        t = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S %z").timestamp()
        if kind == "Sleep":
            if start is None:
                start = t
        elif start is not None:
            out.append((start, t))
            start = None
    if start is not None:
        out.append((start, float("inf")))
    return out


def slept_seconds(
    intervals: list[tuple[float, float]], start: float, end: float
) -> float:
    """Seconds of INTERVALS inside [START, END]: how long the host slept
    during one attempt. Raises ValueError when END precedes START."""
    if end < start:
        raise ValueError(f"attempt window ends before it starts: {start} > {end}")
    return sum(max(0.0, min(b, end) - max(a, start)) for a, b in intervals)


def read_pmset_log() -> str:
    """The host's power-management log (`pmset -g log`, macOS). Raises
    RuntimeError when pmset fails — a sleep that cannot be read is not
    assumed absent."""
    result = subprocess.run(
        ["pmset", "-g", "log"], capture_output=True, text=True, timeout=120
    )
    if result.returncode:
        raise RuntimeError(
            f"pmset -g log failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout
