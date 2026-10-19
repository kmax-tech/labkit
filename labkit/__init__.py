"""labkit — the shared helpers every experiment repo imports.

Stdlib only. Modules, layers and the one home of each question:
`docs/architecture.md`; console commands: README.

    from labkit.run import runlog, llm, batch

**Pin the version, never install editable in an experiment repo.** A run
records its environment; if the helpers can change under a finished run, that
record is a claim about an environment that no longer exists. Editable installs
belong here, in this repo, where the tests are.

Code imports the package directly (`from labkit.run import runlog`) and
creates no shims: a file named like a shared helper would be the second
truth all over again (the guard test `labkit-init` stamps fires on it). A
repo whose frozen run snapshots import the modules flat (`import runlog`)
is reproduced with its own commit and the labkit version it pins — labkit
carries no legacy bridge (CHANGELOG, "Breaking").
"""

from pathlib import Path

#: the package directory; the shipped assets — `templates/`, `agents/`,
#: `docs/` — are read relative to it, from whichever layer package
PACKAGE_DIR = Path(__file__).resolve().parent

# The submodules are deliberately NOT imported here: `import labkit` must stay
# free of side effects (llm reads models.toml when it is used, not when the
# package is loaded). `from labkit.run import runlog` works regardless.
