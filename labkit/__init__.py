"""labkit — the shared helpers every experiment repo imports.

Four modules, stdlib only:

- `runlog`         one run = one directory + one ledger row (id, config, env, status)
                   (installed as the `runlog` command: `runlog <area>` lists open runs)
- `llm`            LLM backends behind one call; aliases resolved via models.toml
- `batch`          resumable output file (lock + resume-by-id + status)
- `protocol_check` the checker the experiment protocol contracts with
                   (installed as the `protocol-check` command)

    from labkit import runlog, llm, batch

**Pin the version, never install editable in an experiment repo.** A run
records its environment; if the helpers can change under a finished run, that
record is a claim about an environment that no longer exists. Editable installs
belong here, in this repo, where the tests are.

Older repos import the modules flat (`import runlog`, via a path entry). A
shim keeps them working while there is still only one truth — hand over the
module object itself, never `import *` (star imports drop the private helpers
and make monkeypatching land on a copy):

    # lib/runlog.py
    import sys
    from labkit import runlog as _mod
    sys.modules[__name__] = _mod
"""

__version__ = "0.2.1"

# The submodules are deliberately NOT imported here: `import labkit` must stay
# free of side effects (llm reads models.toml when it is used, not when the
# package is loaded). `from labkit import runlog` works regardless.
