"""labkit-hooks — install the hooks that make a lab repo use its own tools.

    labkit-hooks install [REPO]    write them (idempotent; other hooks kept)
    labkit-hooks check [REPO]      exit 1 when one is missing or from another labkit

The hooks come with the pinned labkit, so raising the pin and running
`install` again brings hooks that match the commands they call (2026-10-07;
before, the scaffolder in the house dotfiles wrote its own copy once, and
existing repos never got a newer one).

    .githooks/pre-commit     protocol-check on staged protocols; the area
                             numbers in the index (labkit-init numbers
                             --staged) when a staged path lies under
                             experiments/; report-check
                             --if-reported on every staged path — a
                             written-back answer in an area it touches (the
                             whole release check, finalize among its
                             stations); claude-hook undecided on the staged
                             paths; the
                             guard test where a repo has it; then the
                             repo's own .githooks/pre-commit.local, if any
                             (the repo owns it, labkit-hooks never writes it)
    .githooks/pre-merge-commit
                             runs .githooks/pre-commit on the merge's index:
                             git runs this hook, never pre-commit, for a
                             merge it completes on its own, and a merge
                             without a text conflict can still bring a
                             reported number and a changed analysis together
    git core.hooksPath       set to .githooks (it used to be a manual step
                             per clone, and the hook silently did nothing)
    .claude/settings.json    claude-hook pre-run · post-change · stop

Each hook names the labkit version that wrote it; `check` compares.
"""

from __future__ import annotations

import json
import re

from labkit.formats import console
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from labkit.formats.repo import git_root, git_run

MARK = "# installed by labkit-hooks"


def labkit_version() -> str:
    """The installed labkit's version, or "unknown" outside an installed package."""
    try:
        return version("labkit")
    except PackageNotFoundError:
        return "unknown"


def pre_commit() -> str:
    """The pre-commit script of this labkit version."""
    return f"""#!/bin/sh
{MARK} {labkit_version()} — reinstall: .venv/bin/labkit-hooks install
# Escape hatch for a deliberate exception: git commit --no-verify

fail=0
staged_protocols=$(git diff --cached --name-only --diff-filter=ACMR | grep -E '(^|/)PROTOCOL-[^/]*\\.md$')

# 1. Mandatory fields on every staged protocol.
if [ -n "$staged_protocols" ]; then
    if [ ! -x .venv/bin/protocol-check ]; then
        echo "pre-commit: .venv/bin/protocol-check missing — install labkit into .venv"
        echo "(.venv/bin/pip install -r requirements.txt)."
        fail=1
    # shellcheck disable=SC2086 # word-splitting over the file list is intended
    elif ! .venv/bin/protocol-check $staged_protocols; then
        echo ""
        echo "pre-commit: must fields missing (see above) — fill them, or justify as"
        echo "'<field>: n/a — <why>'."
        fail=1
    fi
fi

# 1b. One number per area: two branches that each stamped their next area
#     carry one number twice. Only when a staged path lies under
#     experiments/: nothing else can give two areas one number.
staged_areas=$(git diff --cached --name-only -- experiments)
if [ -n "$staged_areas" ]; then
    if [ ! -x .venv/bin/labkit-init ]; then
        echo "pre-commit: .venv/bin/labkit-init missing — the area numbers cannot be"
        echo "checked; install labkit into .venv (.venv/bin/pip install -r requirements.txt)."
        fail=1
    else
        out=$(.venv/bin/labkit-init numbers --staged 2>&1) || {{
            echo "$out"
            echo ""
            echo "pre-commit: two areas carry one number (see above)."
            fail=1
        }}
    fi
fi

# 2. A number written back: every protocol of an area a staged file touches
#    whose head declares a result ([result] run) goes through report-check —
#    the whole release check at every repeat cost (finalize clean, a full run,
#    a decided analysis audit, the numbers recomputed); a protocol declaring
#    none owes nothing here. Every staged path, not only a protocol: a script changed
#    under a reported number reopens it. --staged: the answer as the index
#    holds it, and the area's tree must equal the index — the commit holds
#    the index, the check reads the tree (audit 2026-10-19).
#    A deletion counts: a script or result removed under a reported number
#    reopens it as an edit does (--no-renames: a move is its old path
#    deleted and its new one added).
staged=$(git diff --cached --name-only --no-renames)
for tool in report-check claude-hook; do
    if [ -n "$staged" ] && [ ! -x .venv/bin/$tool ]; then
        echo "pre-commit: .venv/bin/$tool missing — the gates on the staged files"
        echo "cannot run; install labkit into .venv (.venv/bin/pip install -r requirements.txt)."
        fail=1
    fi
done
if [ -n "$staged" ] && [ -x .venv/bin/report-check ]; then
    # shellcheck disable=SC2086
    if ! .venv/bin/report-check --if-reported --staged $staged; then
        echo ""
        echo "pre-commit: report-check reports blockers for a written-back number (see above)."
        fail=1
    fi
fi

# 2b. An undecided audit BLOCKER in an area a staged file touches: the
#     stop hook's rule at the commit (third haiku round on 0.99.0: audited,
#     read, left open, measured with run_kind='probe', reported).
if [ -n "$staged" ] && [ -x .venv/bin/claude-hook ]; then
    # shellcheck disable=SC2086
    if ! .venv/bin/claude-hook undecided $staged; then
        echo ""
        echo "pre-commit: an audit BLOCKER nobody decided, or audit evidence gone or unreadable (see above) — labkit-audit <AREA> --findings prints the --decide and handover commands."
        fail=1
    fi
fi

# 3. Guard test, where a repo has it: the shared helpers resolve to labkit.
if [ -f tests/test_shared_helpers_come_from_labkit.py ] && [ -x .venv/bin/python ]; then
    out=$(.venv/bin/python -m unittest discover -s tests -p "test_shared_helpers_come_from_labkit.py" 2>&1) || {{
        echo "$out"
        echo ""
        echo "pre-commit: guard test fails (does something shadow the labkit package?)."
        fail=1
    }}
fi

# 4. The repo's own checks: .githooks/pre-commit.local belongs to the repo
#    and is never written by labkit-hooks (uniagent, 2026-10-07: a replay
#    test of its runs lived in the hook and an install would have erased it).
if [ -x .githooks/pre-commit.local ]; then
    .githooks/pre-commit.local || fail=1
fi

exit $fail
"""


def pre_merge_commit() -> str:
    """The pre-merge-commit script of this labkit version: the commit's
    checks (`.githooks/pre-commit`) on the merge's index. git runs it,
    never pre-commit, for a merge it completes on its own; a merge without
    a text conflict can still bring a number reported on one branch and
    its analysis changed on the other together (probed 2026-10-28 on the
    count walkthrough: the merge went through, report-check on its state
    exits 1). A merge with conflicts is committed through pre-commit."""
    return f"""#!/bin/sh
{MARK} {labkit_version()} — reinstall: .venv/bin/labkit-hooks install
# Escape hatch for a deliberate exception: git merge --no-verify

if [ ! -x .githooks/pre-commit ]; then
    echo "pre-merge-commit: .githooks/pre-commit missing — the merge's checks cannot"
    echo "run; reinstall: .venv/bin/labkit-hooks install"
    exit 1
fi
.githooks/pre-commit && exit 0
echo ""
echo "pre-merge-commit: the commit's checks above hold this merge; it stays"
echo "uncommitted — fix what they name, then git commit; or git merge --abort."
exit 1
"""


def git_hooks() -> dict[str, str]:
    """The git hooks an install writes under `.githooks/`, by file name."""
    return {"pre-commit": pre_commit(), "pre-merge-commit": pre_merge_commit()}


def _hook(name: str, timeout: int, message: str) -> dict:
    return {
        "type": "command",
        "command": f'"${{CLAUDE_PROJECT_DIR:-.}}/.venv/bin/claude-hook" {name}',
        "timeout": timeout,
        "statusMessage": f"claude-hook {name}: {message}",
    }


#: the seconds Claude Code gives the stop hook; past them it cancels the
#: hook, and a cancelled stop holds nothing (`claude_hooks.STOP_BUDGET_S`
#: ends the checks before)
STOP_TIMEOUT_S = 120

#: event -> (matcher or None, hook)
CLAUDE_HOOKS = {
    "PreToolUse": ("Bash", _hook("pre-run", 120, "preflight before a run")),
    "PostToolUse": ("Bash|Write|Edit", _hook("post-change", 60, "check what changed")),
    "Stop": (None, _hook("stop", STOP_TIMEOUT_S, "finalize a written-back number")),
}


#: a hook command that calls one of these was written by a labkit install —
#: this version's or an earlier one (uniagent 2026-10-10: a jq one-liner
#: running `protocol-check` on every PROTOCOL write survived three installs
#: and doubled every report beside `claude-hook post-change`). Not every
#: labkit command (`console.command_names`): a foreign hook that calls
#: `runlog` is not one an install wrote, and an install must not erase it.
HOOK_COMMANDS = ("claude-hook", "protocol-check", "notes-check")
#: one of labkit's commands as a word of the hook's command line — at the
#: start, after a space, a `/` or a quote, and not inside a longer name: a
#: foreign `./bin/my-protocol-checker` was taken for ours and erased by an
#: install (audit 2026-10-15)
_LABKIT_COMMAND = re.compile(
    r"""(?:^|[\s/"'])(?:""" + "|".join(HOOK_COMMANDS) + r""")(?=$|[\s"'])"""
)


def _ours(hook: dict) -> bool:
    """Whether one hook command was written by a labkit install."""
    return _LABKIT_COMMAND.search(hook.get("command", "")) is not None


def stale_entries(current: dict) -> list[str]:
    """Every hook in `current` a labkit install wrote that is not this
    version's — one line per hook: event and the command's first 70 chars."""
    wanted = {json.dumps(hook, sort_keys=True) for _, hook in CLAUDE_HOOKS.values()}
    out = []
    for event, entries in (current.get("hooks") or {}).items():
        for entry in entries:
            for h in entry.get("hooks", []):
                if _ours(h) and json.dumps(h, sort_keys=True) not in wanted:
                    out.append(f"{event}: {h.get('command', '')[:70]}")
    return out


def merged_settings(current: dict) -> dict:
    """`current` with labkit's hooks — this version's and any earlier
    install's (`HOOK_COMMANDS`) — replaced by this version's; every other
    key and every foreign hook kept, also one that shares an entry (and its
    matcher) with a labkit hook: the filter takes single commands, and an
    entry left without any is dropped."""
    out = dict(current)
    hooks = {
        event: [
            {**e, "hooks": kept}
            for e in entries
            if (kept := [h for h in e.get("hooks", []) if not _ours(h)])
        ]
        for event, entries in (out.get("hooks") or {}).items()
    }
    hooks = {event: entries for event, entries in hooks.items() if entries}
    for event, (matcher, hook) in CLAUDE_HOOKS.items():
        entry: dict = {"hooks": [hook]}
        if matcher:
            entry = {"matcher": matcher, **entry}
        hooks[event] = hooks.get(event, []) + [entry]
    out["hooks"] = hooks
    return out


def _settings(repo: Path) -> tuple[Path, dict]:
    path = repo / ".claude" / "settings.json"
    if not path.is_file():
        return path, {}
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"labkit-hooks: {path} is not valid JSON ({exc}) — repair it first"
        )


#: where a Claude Code session must start for the hooks to load: Claude Code
#: reads a project's hooks from `.claude/` of the directory it starts in,
#: with no fallback to a parent (docs/notes/2026-10-19-hooks-and-report-check.md)
START_IN_ROOT = (
    "start Claude Code in the repository root ({root}) — a session started "
    "in a directory below it loads none of the claude-hook entries of "
    "{root}/.claude/settings.json; the pre-commit holds a commit either way"
)


#: where the versioned hooks live, and what `core.hooksPath` points at
HOOKS_DIR = ".githooks"


def point_hooks_at(repo: Path) -> None:
    """`git config core.hooksPath .githooks` in REPO: the hook runs only
    where that setting points at it (2026-10-05). The one place it is set
    — `labkit-hooks install` and `labkit-init` both call it (audit
    2026-10-27, third, S9). Raises RuntimeError naming git's refusal."""
    r = git_run(["config", "core.hooksPath", HOOKS_DIR], repo)
    if r.returncode != 0:
        raise RuntimeError(
            f"git config core.hooksPath failed in {repo}: {r.stderr.strip()}"
        )


def install(repo: Path) -> list[str]:
    """Write the hooks; returns what was done."""
    done = []
    (repo / HOOKS_DIR).mkdir(exist_ok=True)
    for name, text in git_hooks().items():
        hook = repo / HOOKS_DIR / name
        if hook.is_file() and MARK not in hook.read_text(encoding="utf-8"):
            # A hook labkit did not write may carry the repo's own checks:
            # kept beside, never erased in silence.
            kept = hook.with_name(f"{name}.before-labkit")
            if kept.exists():
                raise SystemExit(
                    f"labkit-hooks: {hook} was not written by labkit-hooks and "
                    f"{kept.name} exists already — move the repo's own steps to "
                    f"{HOOKS_DIR}/{name}.local, remove {kept.name}, run install again"
                )
            hook.rename(kept)
            done.append(
                f"kept the previous hook as {kept.relative_to(repo)} — move its "
                f"repo-specific steps to {HOOKS_DIR}/{name}.local (executable)"
            )
        if not hook.is_file() or hook.read_text(encoding="utf-8") != text:
            hook.write_text(text, encoding="utf-8")
            done.append(f"wrote {hook.relative_to(repo)}")
        hook.chmod(hook.stat().st_mode | 0o755)
    try:
        point_hooks_at(repo)
    except RuntimeError as exc:
        raise SystemExit(f"labkit-hooks: {exc}") from exc
    done.append("git core.hooksPath = .githooks")
    path, current = _settings(repo)
    wanted = merged_settings(current)
    if wanted != current:
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(wanted, indent=2) + "\n", encoding="utf-8")
        done.append(
            f"wrote {path.relative_to(repo)} (claude-hook pre-run · post-change · stop)"
        )
    return done


def check(repo: Path) -> list[str]:
    """What is missing or from another labkit version; empty means installed."""
    out = []
    for name, text in git_hooks().items():
        hook = repo / ".githooks" / name
        if not hook.is_file():
            out.append(f".githooks/{name} is missing")
        elif hook.read_text(encoding="utf-8") != text:
            first = next(
                (
                    ln
                    for ln in hook.read_text(encoding="utf-8").splitlines()
                    if ln.startswith(MARK)
                ),
                "",
            )
            was = first.removeprefix(MARK).split("—")[0].strip()
            out.append(
                f".githooks/{name} is from labkit {was}, this labkit is {labkit_version()}"
                if was
                else f".githooks/{name} was not written by labkit-hooks"
            )
    r = git_run(["config", "--get", "core.hooksPath"], repo)
    if r.stdout.strip() != ".githooks":
        out.append(
            "git core.hooksPath is not .githooks — the pre-commit hook never runs"
        )
    _, current = _settings(repo)
    stale = stale_entries(current)
    for line in stale:
        out.append(f".claude/settings.json: a hook from an earlier labkit — {line}")
    if not stale and merged_settings(current) != current:
        out.append(".claude/settings.json lacks this labkit's claude-hook entries")
    return out


def main(argv: list[str]) -> int:
    """Command line of `labkit-hooks`: install or check a repo's git hooks."""
    if not argv or argv[0] in ("-h", "--help"):
        lines = [
            (__doc__ or "").strip().splitlines()[0],
            "usage: labkit-hooks install [REPO] | check [REPO]",
        ]
        return console.usage("labkit-hooks", "\n".join(lines), asked=bool(argv))
    cmd, where = argv[0], Path(argv[1]) if len(argv) > 1 else Path(".")
    repo = git_root(where)
    if repo is None:
        console.refuse("labkit-hooks", f"{where} is not inside a git repo")
        return 2
    if cmd == "install":
        for line in install(repo):
            print(f"labkit-hooks: {line}")
        print(f"labkit-hooks: {START_IN_ROOT.format(root=repo)}")
        return 0
    if cmd == "check":
        gaps = check(repo)
        for g in gaps:
            print(f"labkit-hooks: {g}")
        if gaps:
            print("labkit-hooks: fix with  .venv/bin/labkit-hooks install")
        return 1 if gaps else 0
    console.refuse("labkit-hooks", f"unknown command {cmd!r}")
    return 2


def cli() -> None:
    """Entry point for the installed `labkit-hooks` command."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
