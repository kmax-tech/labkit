# labkit — shared lab helpers

The modules every experiment repo imports, in **one** place: writing a
run (`runlog`), reading one (`runs`), the promise block (`promises`), the
protocol checker (`protocol_check`), the checks (`intent_check`,
`code_check`, `recheck`, `scope_sha`, `notes_check`), model calls (`llm`,
`endpoint_lease`), resumable output (`batch`) and repo layout (`repo`).
Two orchestrating commands — `preflight` (before freezing) and `finalize`
(after the run) — sequence the checks at the two decision points. Layers,
the chain from promise to number, and the one home of each recurring
question: `docs/architecture.md`.

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
from labkit import runlog, llm, batch, recheck
```

`recheck.holds(area, out, recompute, note)` is the `--check` of an
analysis script in one call: the output file pinned to the run's recorded
sha prefix, `metrics.json` against the recomputation (intent keys exact,
nothing vanished, grown keys reported as a derived run), the note holding
every reported number as a token and the run_id. Two areas re-implemented
it and got two of three parts wrong (2026-10-05).

Ten **console commands** come with the installation, `runlog` with three
sub-commands (all answer `--help`):

```bash
protocol-check <PROTOCOL-*.md>...   # mandatory-field check (must/should contract)
protocol-check --contract           # budgets and the words each field is recognised by — read before writing
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
claude-hook pre-run|post-change     # the two Claude Code hooks a lab repo installs (stdin: event JSON)
usability stage|score <DIR>        # probe lab repo for a cold agent; score its trace (time, steps, number)
labkit-audit <AREA> --mode preflight|analysis   # experiment-preflight audit through any models.toml alias; exit 1 on a blocker OR a warning
```

## Usability trace — what the whole chain costs for one kept number

The doctrine grew by scars and every scar added a gate; nobody measured
what the chain costs in the simplest case. On 2026-10-05 a deterministic
seven-second run (uniagent area 01) took four days, three freezes and
three agent audits. `usability` makes that measurable and repeatable:

```bash
usability stage /tmp/probe --venv .venv   # fresh lab repo, stamped area, fixture with a known answer, TASK.md
usability stage /tmp/probe --venv .venv --cost seconds   # the seconds cut + counting skeleton (lib exp --cost seconds)
usability stage /tmp/probe --venv .venv --task judge --cost seconds --model   # seconds cut + measure skeleton, a model in the loop
#   hand TASK.md to a COLD agent (fresh context); it logs one line per step
usability score /tmp/probe                # number == truth? bound? tier? wall-clock, steps per tag → probe.score.json
```

The fixture is twelve cases with a known number of input files each
(mean 3.5); the truth sits next to the repo, not in it. The log contract
is `HH:MM:SS · read|run|edit|unsure|gate · step`; `score` counts per tag,
takes the wall-clock from the stamps, and records the labkit version, so
two versions can be compared on the same task. Target line: one kept
number under five minutes.

## Enforcement — four layers, two of them cannot be forgotten

A rule the agent has to remember is the weak layer: it lives in the skill
text and dies with a long session. The layers that do not depend on
remembering (2026-10-05):

| Layer                | Where                                                      | Holds when                                            |
|----------------------|------------------------------------------------------------|-------------------------------------------------------|
| code refuses         | `runlog.Run` — leak, index header, detach, **freeze gate** | always: every run passes through it                   |
| Claude hook blocks   | `claude-hook pre-run` (PreToolUse Bash, exit 2)            | a frozen protocol's area has preflight blockers; not at `Cost: seconds` |
| Claude hook reports  | `claude-hook post-change` (PostToolUse Bash\|Write\|Edit)  | a protocol or messung note changed, whatever wrote it |
| git pre-commit fails | `.githooks/pre-commit`                                     | a staged protocol misses must fields                  |

**Freeze gate.** `long=True` is the script's declaration of a full run.
`runlog` refuses it before `mkdir` unless the bound protocol says
`Frozen before run: yes` and its `Preflight audit:` field is filled (a
protocol that never had the field is not a gap; a stamped placeholder is).
A long *pilot* acknowledges with `LABKIT_UNFROZEN=1`; the acknowledgement
is written to `config.json` as `unfrozen_ack`, so the number carries it.
The gate follows the cost tier (`Cost:` in the protocol, §2.A14): at
`seconds` a rerun costs nothing, so the gate is the **written success
criterion**, not the freeze — an instrument change after it is a commit
and a rerun, never a second freeze. `minutes`, `hours` and an undeclared
tier keep the freeze. The tier is written to `config.json` as `cost_tier`.

**pre-run.** The hook sees every Bash command. One that names a `.py` file
which opens a run (`runlog.run(`) and is not a throwaway stage (`--show`,
`--probe`, `--eval-only`) triggers `preflight` on the script's area. Frozen
protocol + blockers → the command is blocked and the agent reads why.
Unfrozen (a pilot by declaration) + blockers → reported, not blocked.
`LABKIT_PREFLIGHT=skip` in the command skips the gate, visibly.

**post-change.** Matches on what changed (`git status`, untracked
included), not on which tool wrote it — a protocol written through a
heredoc gets the same `protocol-check` as one written with Edit. A
per-session content hash keeps a file from being reported again after
every later command.

Install (what `arbeitsstandard-init.py` stamps into `.claude/settings.json`):

```json
{"hooks": {
  "PreToolUse":  [{"matcher": "Bash",
                   "hooks": [{"type": "command", "timeout": 120,
                              "command": "\"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/claude-hook\" pre-run"}]}],
  "PostToolUse": [{"matcher": "Bash|Write|Edit",
                   "hooks": [{"type": "command", "timeout": 30,
                              "command": "\"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/claude-hook\" post-change"}]}]}}
```

## Terms

One word, one thing. Everything below occurs in more than one module, so it
is coined here and explained nowhere else; the per-field explanations live in
`protocol-field-guide.md`.

| Term                | Means                                                                                               |
|---------------------|-----------------------------------------------------------------------------------------------------|
| **area**            | the directory grouping protocols and their runs                                                     |
| **protocol**        | the specification of one experiment (`PROTOCOL-*.md`)                                               |
| **protocol id**     | a protocol's stable, path-independent identity (`p-` + 16 hex)                                      |
| **run**             | one execution of a protocol                                                                         |
| **run metadata**    | a run's own record (`config.json` + `completion.json`)                                              |
| **run index**       | the searchable overview of runs (`runs.tsv`)                                                        |
| **metrics**         | what a run measured and reported (`metrics.json`)                                                   |
| **documented runs** | the runs listed by hand in a protocol's `## Runs` section                                           |
| **intent id**       | the stable id of one checked promise (`[C1]`, `[A1]`, `[B1]`; kinds in `docs/promise-block.md`)   |
| **bundle**          | the current protocol + scripts + extracted facts, packed for an audit agent (`code-check --bundle`) |
| **frozen**          | unchangeable past a declared point (`Frozen before run: yes`)                                       |
| **scope hash**      | the hash over the input scope a run's number rests on (`scope_sha`)                                 |

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

Not here: templates meant to be filled in (`~/.claude/resources/*.template`,
they are supposed to diverge) and prose references that are read, not
imported — the two style guides, `coding-style.md` (every line of code) and
`writing-style-guide.md` (prose and LaTeX). Their masters live in
`~/.claude/resources/`; every lab repo carries a stamped copy under `docs/`
(`docs/coding-style.md`, `docs/writing-style-guide.md`), kept in step by
`lib sync`.
