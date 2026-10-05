"""claude-hook — the two Claude Code hooks a lab repo installs.

    claude-hook pre-run       PreToolUse  (matcher: Bash)
    claude-hook post-change   PostToolUse (matcher: Bash|Write|Edit)

Both read the hook's JSON event on stdin and answer the way Claude Code
expects: `pre-run` blocks with exit 2 (the stderr text goes back to the
agent), everything else is `additionalContext` on stdout and exit 0.

Why these exist (2026-10-05): the rules that matter — "preflight before a
full run", "protocol-check after writing a protocol" — lived in the skill
text, in the agent's memory. The write hooks that did exist matched only
the Write and Edit tools; a protocol written through a Bash heredoc got no
check at all, and no hook at all stood between the agent and
`python 01_measure.py`. A rule the agent has to remember is the weak layer;
this is the layer that does not depend on remembering.

pre-run
    The command is a run start when it names a .py file that opens a run
    (`runlog.run(` / `runlog.Run(`) and is not one of the throwaway stages
    (`--show`, `--probe`, `--eval-only`). For that script's area (the
    nearest directory above it with a PROTOCOL-*.md) `preflight` runs:
      · protocol frozen (`Frozen before run: yes`) + blockers  → exit 2, blocked
      · protocol unfrozen (a pilot by declaration) + blockers  → context only
      · clean                                                   → one line
    `LABKIT_PREFLIGHT=skip` in the command string skips the gate; it is
    visible in the transcript, like `--no-verify` on a commit.

post-change
    Every file the repo now reports as changed (git status, untracked
    included) plus the tool's own file_path, filtered to PROTOCOL-*.md and
    notes/messung/*.md (not 00-*), is checked with protocol-check or
    notes-check. A per-session cache of content hashes keeps a file that was
    already checked at this content from being reported after every later
    command.

Exit codes: pre-run 0 or 2 (block); post-change 0; usage errors and
unexpected failures 1, loud on stderr, never swallowed.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from labkit import notes_check, preflight, protocol_check

# The template's throwaway stages: none of them opens a run, and the probe
# is what comes BEFORE preflight, so gating it would invert the order.
THROWAWAY_FLAGS = re.compile(r"(^|\s)--(show|probe|eval-only)\b")
PY_TOKEN = re.compile(r"[\w./~-]+\.py\b")
OPENS_RUN = re.compile(r"runlog\.(run|Run)\(")
PROTOCOL_IN_SCRIPT = re.compile(r"PROTOCOL-[\w.-]+\.md")
SKIP_TOKEN = "LABKIT_PREFLIGHT=skip"
PROTOCOL_NAME = re.compile(r"^PROTOCOL-.*\.md$")


def _read_event() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _context(event_name: str, text: str) -> None:
    """Hand text back to the agent as additionalContext."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event_name, "additionalContext": text}},
        ensure_ascii=False))


def _capture(fn, *args) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue().rstrip()


# ---------------------------------------------------------------- pre-run

def find_area(script: Path, stop: Path | None = None) -> Path | None:
    """The nearest directory above `script` holding a PROTOCOL-*.md."""
    for d in script.resolve().parents:
        if any(d.glob("PROTOCOL-*.md")):
            return d
        if stop is not None and d == stop.resolve():
            return None
    return None


def run_scripts(command: str, cwd: Path) -> list[Path]:
    """The .py files in the command that open a run — resolved and existing."""
    out = []
    for tok in PY_TOKEN.findall(command):
        p = Path(os.path.expanduser(tok))
        if not p.is_absolute():
            p = cwd / p
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if OPENS_RUN.search(text):
            out.append(p.resolve())
    return out


def protocol_named_in(script: Path, area: Path) -> Path | None:
    """The single PROTOCOL-*.md the script names, if it names exactly one
    and it exists in the area — the series case where preflight would
    otherwise refuse to pick."""
    names = sorted(set(PROTOCOL_IN_SCRIPT.findall(
        script.read_text(encoding="utf-8"))))
    if len(names) != 1:
        return None
    p = area / names[0]
    return p if p.is_file() else None


def pre_run(event: dict) -> int:
    if event.get("tool_name", "Bash") != "Bash":
        return 0
    command = (event.get("tool_input") or {}).get("command") or ""
    if not command or THROWAWAY_FLAGS.search(command):
        return 0
    cwd = Path(event.get("cwd") or os.getcwd())
    scripts = run_scripts(command, cwd)
    if not scripts:
        return 0
    if SKIP_TOKEN in command:
        _context("PreToolUse", f"claude-hook pre-run: {SKIP_TOKEN} — preflight "
                 f"gate skipped on request; the transcript carries it.")
        return 0

    project = os.environ.get("CLAUDE_PROJECT_DIR")
    stop = Path(project) if project else None
    blocked: list[str] = []
    notes: list[str] = []
    for script in scripts:
        area = find_area(script, stop)
        if area is None:
            notes.append(f"{script.name}: opens a run, but no PROTOCOL-*.md "
                         f"above it — unbound runs keep no number (§2.A1).")
            continue
        protocol = protocol_named_in(script, area)
        rc, out = _capture(preflight.run, area, protocol)
        texts = [p.read_text(encoding="utf-8")
                 for p in ([protocol] if protocol else sorted(area.glob("PROTOCOL-*.md")))]
        frozen = any(protocol_check.FROZEN_YES.search(t) for t in texts)
        head = f"preflight {area.name}" + (f" --protocol {protocol.name}" if protocol else "")
        if rc == 1 and frozen:
            blocked.append(f"{head}: BLOCKED — the protocol is frozen and "
                           f"preflight reports blockers:\n{out}")
        elif rc == 1:
            notes.append(f"{head}: blockers, protocol not frozen (pilot) — "
                         f"the full run will not start until they are fixed:\n{out}")
        elif rc == 2:
            notes.append(f"{head}: could not run preflight:\n{out}")
        else:
            notes.append(f"{head}: " + (out.splitlines()[-1] if out else "ok"))
    if blocked:
        sys.stderr.write("\n\n".join(blocked) + "\n")
        if notes:
            sys.stderr.write("\n" + "\n".join(notes) + "\n")
        return 2
    if notes:
        _context("PreToolUse", "\n\n".join(notes))
    return 0


# ------------------------------------------------------------ post-change

def _git_changed(repo: Path) -> list[Path]:
    r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                       cwd=repo, capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        raise RuntimeError(f"git status failed in {repo}: {r.stderr.strip()}")
    out = []
    for line in r.stdout.splitlines():
        if len(line) < 4 or line[1] == "D" or line[0] == "D":
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(repo / path)
    return out


def wants_check(path: Path) -> str | None:
    """Which checker a path belongs to: 'protocol', 'note' or None."""
    if PROTOCOL_NAME.match(path.name):
        return "protocol"
    parts = path.as_posix().split("/")
    if ("notes" in parts and "messung" in parts
            and parts.index("messung") == parts.index("notes") + 1
            and path.suffix == ".md" and not path.name.startswith("00-")):
        return "note"
    return None


def _cache_path(session_id: str | None) -> Path | None:
    if not session_id:
        return None
    d = Path(tempfile.gettempdir()) / "labkit-claude-hook"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session_id}.json"


def _load_cache(p: Path | None) -> dict:
    if p is None or not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def post_change(event: dict) -> int:
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    repo = Path(project) if project else Path(event.get("cwd") or os.getcwd())
    candidates: list[Path] = []
    if (repo / ".git").exists():
        candidates.extend(_git_changed(repo))
    fp = (event.get("tool_input") or {}).get("file_path")
    if fp:
        candidates.append(Path(fp))
    seen: set[Path] = set()
    targets: list[tuple[str, Path]] = []
    for c in candidates:
        c = c.resolve()
        if c in seen or not c.is_file():
            continue
        seen.add(c)
        kind = wants_check(c)
        if kind:
            targets.append((kind, c))
    if not targets:
        return 0

    cache_file = _cache_path(event.get("session_id"))
    cache = _load_cache(cache_file)
    reports = []
    for kind, path in targets:
        digest = _sha(path)
        if cache.get(str(path)) == digest:
            continue
        cache[str(path)] = digest
        fn = protocol_check.main if kind == "protocol" else notes_check.main
        _, out = _capture(fn, [str(path)])
        # The checker gets the absolute path (the hook's cwd is wherever the
        # agent stood); the report shows it repo-relative, as pfad:zeile.
        try:
            out = out.replace(str(path), str(path.relative_to(repo.resolve())))
        except ValueError:
            pass
        if out:
            reports.append(out)
    if cache_file is not None:
        cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    if reports:
        _context("PostToolUse", "\n".join(reports))
    return 0


# -------------------------------------------------------------------- cli

def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: claude-hook pre-run | post-change   (hook event JSON on stdin)")
        return 0 if argv else 1
    event = _read_event()
    if argv[0] == "pre-run":
        return pre_run(event)
    if argv[0] == "post-change":
        return post_change(event)
    print(f"claude-hook: unknown event {argv[0]!r}", file=sys.stderr)
    return 1


def cli() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
