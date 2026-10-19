# labkit's commands to copy and run: `just` lists them, `just <name> ARGS` runs one.
# Install once: brew install just. The same in VS Code: .vscode/launch.json.

venv := ".venv/bin"

# list the recipes
default:
    @just --list

# the commit gate: ruff, format, pyright, pytest (the hook itself, one home)
check:
    .githooks/pre-commit

# the suite, or the tests matching NAME
test name="":
    {{venv}}/pytest -q {{ if name != "" { "-k " + quote(name) } else { "" } }}

# stop at the first line of the tests matching NAME (pdb)
test-start name:
    {{venv}}/pytest -q -k {{quote(name)}} --trace

# run the tests matching NAME, open pdb where one fails
test-fail name:
    {{venv}}/pytest -q -k {{quote(name)}} --pdb

# a labkit module under pdb from its entry point, named with its layer package:
# just debug gates.audit AREA --mode preflight
debug module *args:
    {{venv}}/python -m pdb -m labkit.{{module}} {{args}}

# what one run of a command called, cut to labkit: just calltree protocol-check --contract
calltree command *args:
    {{venv}}/labkit-calltree {{command}} -- {{args}}

# runs the module FILE, not -m: with -m, --include_files keeps nothing (viztracer 1.1.1);
# the leading - opens the timeline even when the command exits non-zero

# the run as a timeline in the browser: just timeline formats.protocol_check --contract
timeline module *args:
    -{{venv}}/viztracer --quiet --include_files ./labkit -o /tmp/labkit-timeline.json -- labkit/{{replace(module, ".", "/")}}.py {{args}}
    {{venv}}/vizviewer /tmp/labkit-timeline.json

# A release is one step in the one order the tag test allows: the CHANGELOG entry
# `## X.Y.Z — date` is written (the only change in the tree), the recipe sets the
# version in pyproject.toml, reinstalls the editable labkit (its metadata must
# carry the new version before the hook's suite stamps), commits both through
# the hook, then tags that commit.
# The push stays with you; the recipe prints it. Why: on 2026-10-13 the tag
# v0.88.5 was set before the version commit, the tag test went red, the commit
# went in past the hook with --no-verify, and the tag stayed on the old commit.

# cut a release: changelog entry written → version set, committed, tagged: just release 0.88.6
release version:
    #!/usr/bin/env python3
    import re, subprocess, sys
    from pathlib import Path

    v = "{{version}}"
    tag = f"v{v}"

    def die(msg):
        sys.exit(f"release: {msg}")

    def git(*args, check=True):
        r = subprocess.run(["git", *args], capture_output=True, text=True)
        if check and r.returncode != 0:
            die(f"git {' '.join(args)} failed:\n{r.stderr.strip() or r.stdout.strip()}")
        return r

    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        die(f"VERSION must be X.Y.Z, got {v!r}")
    if git("rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False).returncode == 0:
        at = git("rev-parse", "--short", tag).stdout.strip()
        die(f"tag {tag} exists already, on {at}")
    version_re = re.compile(r'^version = "(\d+\.\d+\.\d+)"$', re.M)
    head = version_re.search(git("show", "HEAD:pyproject.toml").stdout)
    if head is None:
        die("HEAD:pyproject.toml has no version line")
    if head.group(1) == v:
        die(f"HEAD already declares {v} — tag it by hand if that commit is the release")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (\S+) — (\d{4}-\d{2}-\d{2})$", changelog, re.M)
    if not heads:
        die("CHANGELOG.md has no `## X.Y.Z — YYYY-MM-DD` heading")
    if heads[0][0] != v:
        die(f"the top CHANGELOG.md entry is {heads[0][0]}, not {v} — write the entry first")
    dirty = [ln for ln in git("status", "--porcelain", "--untracked-files=no").stdout.splitlines()
             if ln[3:] not in ("CHANGELOG.md", "pyproject.toml")]
    if dirty:
        die("the tree carries more than the release — commit or stash first:\n" + "\n".join(dirty))

    pyproject = Path("pyproject.toml")
    text = pyproject.read_text(encoding="utf-8")
    if version_re.search(text) is None:
        die("pyproject.toml has no version line")
    pyproject.write_text(version_re.sub(f'version = "{v}"', text, count=1), encoding="utf-8")
    # before the commit, not after the tag: the hook's suite stamps, and the
    # stamper refuses while the editable metadata lag the version just set
    # (the first 0.88.8 release attempt: 21 red tests, 2026-10-13)
    r = subprocess.run([".venv/bin/pip", "install", "-q", "-e", ".[dev]"])
    if r.returncode != 0:
        die(f"pyproject.toml says {v}, but reinstalling labkit failed — run .venv/bin/pip install -e '.[dev]', then run again")

    entry = changelog.split(f"## {v} — ", 1)[1].split("\n## ", 1)[0]
    subhead = re.search(r"^### (.+)$", entry, re.M)
    title = f"{v}: {subhead.group(1)}" if subhead else v
    git("add", "CHANGELOG.md", "pyproject.toml")
    r = subprocess.run(["git", "commit", "-q", "-m", title, "-m", f"Entry: CHANGELOG.md `## {v}`."])
    if r.returncode != 0:
        die(f"the commit was refused (hook above) — pyproject.toml already says {v}; fix, then run again")
    git("tag", tag)
    sha = git("rev-parse", "--short", "HEAD").stdout.strip()
    print(f"release: {sha} {title}\nrelease: tag {tag} on it, labkit reinstalled — push with:\n  git push origin main {tag}")
