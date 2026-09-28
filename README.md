# labkit — shared lab helpers

Ten modules every experiment repo imports, in **one** place: run index
(`runlog`), LLM backend (`llm`), endpoint lease (`endpoint_lease`),
resumable output file (`batch`), intent-id check (`intent_check`),
protocol checker (`protocol_check`), protocol filler (`protocol_fill`),
mechanical preflight (`code_check`), audit stamp (`scope_sha`) and
notes-kind gate (`notes_check`). Two orchestrating commands —
`preflight` (before freezing) and `finalize` (after the run) — sequence
the checks at the two decision points.

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

Ten **console commands** come with the installation (all answer `--help`):

```bash
protocol-check <PROTOCOL-*.md>...   # mandatory-field check (must/should contract)
runlog [<area>]                     # open runs: run_id, state, script
runlog migrate-index <area>         # add missing run-index columns, rows kept
runlog reindex <area>               # append rows for completed runs it missed
intent-check <PROTOCOL-*.md>        # registered promise ids vs. metrics keys
code-check <AREA>                   # intent-id check + audit bundle for the agent
scope-sha [--area DIR]              # audit stamp over the code that determines a number
protocol-fill <PROTOCOL> FIELD VAL  # fill one stamped placeholder field by label
notes-check <repo | dir | note.md>  # kind declaration gate for notes/messung
preflight <AREA>                    # pre-freeze gate: protocol + code + scope + dirty check
finalize <AREA>                     # post-run gate: completion + intent-check + open fields
```

## Terms

One word, one thing. Everything below occurs in more than one module, so it
is coined here and explained nowhere else; the per-field explanations live in
`protocol-field-guide.md`.

| Term                | Means                                                                 |
|---------------------|-----------------------------------------------------------------------|
| **area**            | the directory grouping protocols and their runs                       |
| **protocol**        | the specification of one experiment (`PROTOCOL-*.md`)                 |
| **protocol id**     | a protocol's stable, path-independent identity (`p-` + 16 hex)        |
| **run**             | one execution of a protocol                                           |
| **run metadata**    | a run's own record (`config.json` + `completion.json`)                |
| **run index**       | the searchable overview of runs (`runs.tsv`)                          |
| **metrics**         | what a run measured and reported (`metrics.json`)                     |
| **documented runs** | the runs listed by hand in a protocol's `## Runs` section             |
| **intent id**       | the stable id of one checked promise (`[K1]`, `[S1]`, `[W1]`, `[N1]`) |
| **bundle**          | the current protocol + scripts + extracted facts, packed for an audit agent (`code-check --bundle`) |
| **frozen**          | unchangeable past a declared point (`Frozen before run: yes`)         |
| **scope hash**      | the hash over the input scope a run's number rests on (`scope_sha`)   |

**"Ledger" is gone** (2026-09-26). It named three different things — the run
index, a run's metrics, and the hand-written `## Runs` section — and a word
that promises a complete and reliable book of record fits none of them —
least of all the hand-written one. `intent_check.ledger_ids` survives one cycle as
a deprecated alias of `reported_intent_ids`.

Which protocol a run belongs to — identity, binding, legacy, selection —
is specified in `docs/protocol-run-binding.md`.

The hierarchy the vocabulary is meant to make visible:

    config.json      start state, and the binding of run to protocol
    metrics.json     result data
    completion.json  confirmed completion (note, end-of-run git state)
    runs.tsv         run index — derived, never a source
    ## Runs          manual documentation, never a source

labkit knows **two work types**: `measurement` for pure counting questions
("how many X are there?" — no model, no hypothesis, 7 fields, no freeze)
and `experiment` for everything hypothesis- or model-driven. An experiment
protocol has **two modes**: `Frozen before run: no` is the light pilot
(MUST fields only), `Frozen before run: yes` is the heavy report mode —
every SHOULD field becomes mandatory. The price sits on the claim, not the
activity: cheap tiers yield numbers that must not be reported. Every field's explanation — examples, rationale, the four questions to
ask a criterion — lives in `protocol-field-guide.md` (packaged alongside
the template; `protocol-check --guide` prints the path); thesis repos get
a copy at `templates/PROTOCOL-FIELD-GUIDE.md`.

The commands are stations of **one lifecycle** — write the protocol, audit
the code, run, hold the run against the promises. Two orchestrating
commands sequence the individual checks at the two decision points:

1. Write `PROTOCOL-<task>.md` from the packaged template; `protocol-check`
   enforces its fields from the first draft on (MUST for pilots, everything
   once `Frozen before run: yes`).
2. Before freezing, **`preflight <area>`** runs the pre-freeze gate:
   `protocol-check` (mandatory fields) → `code-check` (intent ids against
   the code) → `scope-sha` (audit stamp) → dirty-tree warning. The
   individual commands remain available for targeted use; `code-check
   --bundle` additionally extracts schema facts and gate labels into a
   bundle for the audit agent's judgement pass.
3. The run goes through `runlog` (frozen config, env fingerprint, script
   snapshot, split-leakage check); `runlog <area>` monitors it, `runlog
   start -- <cmd>` detaches long runs.
4. After the run, **`finalize <area>`** runs the post-run gate: completion
   check (newest bound run is `completed`) → `intent-check` (promises vs.
   metrics) → open-fields report (placeholders still to fill). The
   individual commands remain available; `protocol-fill` writes results
   back into the protocol without touching the rest.

`notes-check` sits beside the lifecycle: it gates the measurement notes the
results flow into.

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

Change → test → bump `version` in `pyproject.toml` → commit → tag
`v<version>`. The experiment repos catch up via their pin, each at its own
time; a running experiment is never surprised by a bugfix.

**One version, one identity, one label.** `pyproject.toml` carries the
version, the commit carries the identity, and the tag is a label over that
commit — checked by `tests/test_release_tags.py`, which holds every
`vX.Y.Z` against the version its commit declares. The package states no
`__version__`: a literal nobody read, kept in step by hand, is a second
truth waiting to drift. A forgotten tag is not fatal either — the
scaffolder's `labkit_pin()` falls back to the commit and prints the `git
tag` command it wants.

## Boundary

Only what **more than one repo** uses lives here. Project-local helpers
stay in the project (`lib/`) — a module moves here when it is needed for
the second time.

Not here: templates meant to be filled in (`~/.claude/resources/`, they are
supposed to diverge) and prose references like the style guide (read, not
imported).
