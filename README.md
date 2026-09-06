# labkit — shared lab helpers

The four building blocks every experiment repo imports, in **one** place:
run ledger (`runlog`), LLM backend (`llm`), resumable output file (`batch`)
and the protocol checker (`protocol_check`, installed as `protocol-check`).

They used to live as copies in every repo — up to three versions per file
(`experiments/`, `resources/templates/`, `~/.claude/resources/`). On
2026-09-01 an active repo's `experiments/llm.py` was 379 lines behind the
master while the drift check reported "in sync": it compared the snapshot,
not the imported file.

## Use

```bash
pip install ~/projects/labkit      # in repos: pinned via requirements.txt/.lock
```

```python
from labkit import runlog, llm, batch
```

Two **console commands** come with the installation (both answer `--help`):

```bash
protocol-check <PROTOCOL-*.md>...   # mandatory-field check (must/should contract)
runlog [<area>]                     # open runs: run_id, running/crashed, script
```

**Pin the version, never `pip install -e` in an experiment repo.** A run
records its environment; if the helpers could change under a finished run,
that record is a claim about an environment that no longer exists. Editable
installs belong here, where the tests are.

**New code imports the package directly** — `from labkit import runlog` —
and never creates shims; the scaffolder stamps repos in this style, and a
guard test (`test_shared_helpers_come_from_labkit.py`) fires if a file ever
shadows the package.

**Shims are the documented LEGACY bridge only:** repos whose frozen run
snapshots say `import runlog` (hundreds of files that must not be touched)
keep a module handover per name — never `import *`, which drops private
helpers and makes monkeypatching land on a copy:

```python
# lib/runlog.py  (legacy repos only)
import sys
from labkit import runlog as _mod
sys.modules[__name__] = _mod
```

`lib init <repo> --sync check` recognises exactly this form as a shim
("nothing to sync").

## Language

Code, messages, docstrings and this README are English — the kit is meant
to be handed to students as-is. The protocol checker's *contract* stays
bilingual on purpose: its keyword patterns accept German and English field
content, because grown protocols are German-filled.

## Develop

```bash
python3 -m unittest discover -s tests -v
```

Change → test → bump `version` in `pyproject.toml` → tag. The experiment
repos catch up via their pin, each at its own time; a running experiment is
never surprised by a bugfix.

## Boundary

Only what **more than one repo** uses lives here. Project-local helpers
stay in the project (`lib/`) — a module moves here when it is needed for
the second time.

Not here: templates meant to be filled in (`~/.claude/resources/`, they are
supposed to diverge) and prose references like the style guide (read, not
imported).
