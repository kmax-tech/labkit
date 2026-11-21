"""Every console command prints its usage for `-h`/`--help` — also after a
subcommand or an area — exits 0 and writes nothing: no file in the repo
or the home directory, no git config. `labkit-hooks install --help`
once installed the hooks (2026-11-21).

The test proves no write, not that nothing else ran: a command that ran
a read-only check and then printed a usage would pass. The lines after
a subcommand or an area are listed by hand (`LATER_HELP`); a new
subcommand is covered once it is added there."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from labkit.formats import console

pytestmark = pytest.mark.slow

BIN = Path(sys.executable).parent

#: the words before `--help` on lines that run a subcommand or name an
#: area; labkit-calltree is left out after its TARGET, since it hands
#: those words to the target it runs
LATER_HELP = [
    ["labkit-hooks", "install"],
    ["labkit-hooks", "install", "."],
    ["labkit-hooks", "check"],
    *(
        ["claude-hook", event]
        for event in ("sessions", "pre-commit", "pre-run", "post-change", "stop")
    ),
    *(["codex-hook", event] for event in ("pre-run", "post-change", "stop")),
    *(["labkit-init", sub] for sub in ("lab", "exp", "numbers")),
    *(
        ["usability", sub]
        for sub in (
            "stage",
            "log",
            "score",
            "trace",
            "reader",
            "read-score",
            "glance",
            "glance-score",
            "terms",
            "nav",
            "nav-score",
            "human",
        )
    ),
    ["protocol-check", "PROTOCOL-x.md"],
    ["protocol-check", "--template"],
    ["scope-sha", "area"],
    ["intent-check", "PROTOCOL-x.md"],
    ["code-check", "area"],
    ["notes-check", "notes"],
    ["preflight", "area"],
    ["finalize", "area"],
    ["labkit-params", "area"],
    ["labkit-run-diff", "area"],
    ["runlog", "area"],
    ["labkit-audit", "area"],
    ["labkit-next", "area"],
    ["labkit-adopt", "area"],
    ["report-check", "area"],
]

CALLS = [
    *(
        [name, flag]
        for name in sorted(console.command_names())
        for flag in ("--help", "-h")
    ),
    *([*words, "--help"] for words in LATER_HELP),
]


def _state(root: Path) -> dict[str, tuple[float, int]]:
    """Every path under ROOT with its mtime and size."""
    return {
        str(p.relative_to(root)): (p.lstat().st_mtime, p.lstat().st_size)
        for p in root.rglob("*")
    }


@pytest.mark.parametrize("argv", CALLS, ids=" ".join)
def test_help_prints_the_usage_and_writes_nothing(argv: list[str]) -> None:
    script = BIN / argv[0]
    assert script.is_file(), f"{script} is not installed: pip install -e '.[dev]'"
    with tempfile.TemporaryDirectory() as d:
        repo, home = Path(d) / "repo", Path(d) / "home"
        home.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        before = _state(Path(d))
        r = subprocess.run(
            [str(script), *argv[1:]],
            cwd=repo,
            env=dict(os.environ, HOME=str(home)),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "usage" in r.stdout.lower(), r.stdout + r.stderr
        assert _state(Path(d)) == before
