"""labkit — the shared helpers every experiment repo imports.

Ten modules, stdlib only:

- `runlog`         one run = one directory + one run-index row (id, config, env, status)
                   (installed as the `runlog` command: `runlog <area>` lists open runs)
- `llm`            LLM backends behind one call; aliases resolved via models.toml
- `endpoint_lease` one alias at a time per serving endpoint (a slot is not a
                   service); `llm.complete` takes it implicitly
- `batch`          resumable output file (lock + resume-by-id + status)
- `intent_check`   registered intent ids vs. the run's metrics keys
                   (installed as the `intent-check` command)
- `protocol_check` the checker the experiment protocol contracts with
                   (installed as the `protocol-check` command)
- `protocol_fill`  fill one stamped placeholder field by label
                   (installed as the `protocol-fill` command)
- `code_check`     mechanical preflight: intent ids, schema, gate labels
                   (installed as the `code-check` command)
- `scope_sha`      audit stamp over the code that determines a number
                   (installed as the `scope-sha` command)
- `notes_check`    kind declaration gate for notes/messung
                   (installed as the `notes-check` command)

    from labkit import runlog, llm, batch

**Pin the version, never install editable in an experiment repo.** A run
records its environment; if the helpers can change under a finished run, that
record is a claim about an environment that no longer exists. Editable installs
belong here, in this repo, where the tests are.

New code imports the package directly (`from labkit import runlog`) and
creates no shims. Shims are the documented legacy bridge for repos whose
frozen run snapshots import the modules flat (`import runlog`, via a path
entry) — hand over the module object itself, never `import *` (star imports
drop the private helpers and make monkeypatching land on a copy):

    # lib/runlog.py  (legacy repos only)
    import sys
    from labkit import runlog as _mod
    sys.modules[__name__] = _mod
"""

__version__ = "0.22.0"   # keep in step with pyproject.toml

# The submodules are deliberately NOT imported here: `import labkit` must stay
# free of side effects (llm reads models.toml when it is used, not when the
# package is loaded). `from labkit import runlog` works regardless.
