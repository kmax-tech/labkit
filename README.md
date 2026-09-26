# labkit — shared lab helpers

Ten modules every experiment repo imports, in **one** place: run index
(`runlog`), LLM backend (`llm`), endpoint lease (`endpoint_lease`),
resumable output file (`batch`), intent-id check (`intent_check`),
protocol checker (`protocol_check`), protocol filler (`protocol_fill`),
mechanical preflight (`code_check`), audit stamp (`scope_sha`) and
notes-kind gate (`notes_check`).

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

Seven **console commands** come with the installation (all answer `--help`):

```bash
protocol-check <PROTOCOL-*.md>...   # mandatory-field check (must/should contract)
runlog [<area>]                     # open runs: run_id, running/crashed, script
intent-check <PROTOCOL-*.md>        # registered promise ids vs. metrics keys
code-check <AREA>                   # mechanical preflight (schema, gate labels)
scope-sha [--area DIR]              # audit stamp over the code that determines a number
protocol-fill <PROTOCOL> FIELD VAL  # fill one stamped placeholder field by label
notes-check <repo | dir | note.md>  # kind declaration gate for notes/messung
```

## Terms

One word, one thing. Everything below occurs in more than one module, so it
is coined here and explained nowhere else; the per-field explanations live in
`protocol-field-guide.md`.

| Term                | Means                                                                 |
|---------------------|-----------------------------------------------------------------------|
| **area**            | the directory grouping protocols and their runs                       |
| **protocol**        | the specification of one experiment (`PROTOCOL-*.md`)                 |
| **protocol id**     | a protocol's stable, path-independent identity — *not built yet*      |
| **run**             | one execution of a protocol                                           |
| **run metadata**    | the canonical record of a single run — *not built yet*                |
| **run index**       | the searchable overview of runs (`runs.tsv`)                          |
| **metrics**         | what a run measured and reported (`metrics.json`)                     |
| **documented runs** | the runs listed by hand in a protocol's `## Runs` section             |
| **intent id**       | the stable id of one checked promise (`[K1]`, `[S1]`, `[W1]`, `[N1]`) |
| **bundle**          | a run's frozen inputs, packed for an audit agent                      |
| **frozen**          | unchangeable past a declared point (`Frozen before run: yes`)         |
| **scope hash**      | the hash over the input scope a run's number rests on (`scope_sha`)   |

**"Ledger" is gone** (2026-09-26). It named three different things — the run
index, a run's metrics, and the hand-written `## Runs` section — and a word
that promises a complete and reliable book of record fits none of them —
least of all the hand-written one. `intent_check.ledger_ids` survives one cycle as
a deprecated alias of `reported_intent_ids`.

The hierarchy the vocabulary is meant to make visible:

    run metadata   canonical binding of run to protocol   (open, steps 3-5)
    runs.tsv       run index                              (data ownership open until then)
    metrics.json   result data
    ## Runs        manual documentation, never a source

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
the code, run, hold the run against the promises:

1. Write `PROTOCOL-<task>.md` from the packaged template; `protocol-check`
   enforces its fields from the first draft on (MUST for pilots, everything
   once `Frozen before run: yes`).
2. Before freezing, `code-check <area>` runs the mechanical preflight —
   registered intent ids vs. the code, schema facts, gate labels — and
   `--bundle` packs the sources for the audit agent's judgement pass.
3. The run goes through `runlog` (frozen config, env fingerprint, script
   snapshot, split-leakage check); `runlog <area>` monitors it, `runlog
   start -- <cmd>` detaches long runs.
4. After the run, `intent-check` holds the protocol's registered promises
   against the run's metrics; `scope-sha` stamps which code the audits saw;
   `protocol-fill` writes results back into the protocol without touching
   the rest.

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
