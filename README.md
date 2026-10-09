# labkit — shared lab helpers

The modules every experiment repo imports, in **one** place: writing a
run (`runlog`), reading one (`runs`), the promise block (`promises`), the
protocol checker (`protocol_check`), the checks (`intent_check`,
`code_check`, `recheck`, `scope_sha`, `notes_check`), model calls (`llm`,
`endpoint_lease`), resumable output (`batch`) and repo layout (`repo`).
Two orchestrating commands — `preflight` (before a full run, and before
freezing a protocol that freezes) and `finalize` (after the run, before a
number is reported) — sequence the checks at the two decision points. Layers,
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

Fifteen **console commands** come with the installation, `runlog` with three
sub-commands (all answer `--help`):

```bash
protocol-check <PROTOCOL-*.md>...   # mandatory-field check (must/should contract)
protocol-check --contract           # the head, the fields by exact label, the budgets — read before writing
runlog [<area>]                     # the area's runs: open ones with state and pid, then the finished ones (what each is, committed or not, its command)
runlog reindex <area>               # append rows for completed runs it missed
intent-check <PROTOCOL-*.md>        # registered promise ids vs. metrics keys
code-check <AREA>                   # intent-id check + audit bundle for the agent
scope-sha [--area DIR]              # audit stamp over the code that determines a number
protocol-fill <PROTOCOL> FIELD VAL  # fill one stamped placeholder field by label
notes-check <repo | dir | note.md>  # kind declaration gate for notes/messung
preflight <AREA>                    # the mechanical pre-freeze gate: protocol + code + scope + dirty check + area tests (not the agent audit)
finalize <AREA>                     # post-run gate: completion + intent-check + open fields
finalize --if-reported <PROTOCOL>.. # the commit gate: finalize every protocol whose answer cites a run
claude-hook pre-run|post-change|stop  # the Claude Code hooks a lab repo installs (stdin: event JSON)
claude-hook sessions [--run RUN_ID]  # the session log the stop hook keeps (.git/labkit-sessions.jsonl): session, transcript, runs
labkit-hooks install|check [REPO]   # install this labkit's hooks (pre-commit, core.hooksPath, claude-hook); rerun after a pin raise
usability stage|score|trace <DIR>  # cold-agent probe: stage a probe lab repo, score the agent's trace (time, steps, number), read a trace
labkit-audit <AREA> --mode preflight|analysis   # the AGENT audit (experiment-preflight) through any models.toml alias — not the `preflight` gate; exit 1 on a blocker OR a warning
labkit-audit <AREA> --mode clarity              # a newcomer's reading of README, protocol and measure script (code-clarity); exit 1 on findings, never a gate
labkit-params <AREA> [--run ID]     # the values the answering run ran with: home, meaning, tier (guaranteed / static evidence)
labkit-calltree <COMMAND> [-- ARGS]  # what one run of a command called, cut to its package: path:line per call path (reading aid, not a check)
```

## Usability trace — what the whole chain costs for one kept number

The doctrine grew by scars and every scar added a gate; nobody measured
what the chain costs in the simplest case. On 2026-10-05 a deterministic
seven-second run (uniagent area 01) took four days, three freezes and
three agent audits. `usability` makes that measurable and repeatable:

```bash
usability stage /tmp/probe --venv .venv   # fresh lab repo, area stamped as the route does (seconds cut + counting skeleton), fixture, TASK.md
usability stage /tmp/probe --venv .venv --task judge   # seconds cut + measure skeleton, a model in the loop (--model is the judge default)
usability stage /tmp/probe --venv .venv --cost unset   # the full form; the agent declares the tier
#   hand <probe>.prompt.md (CLAUDE.md as a session loads it + the TASK.md pointer) to a COLD agent; it logs one line per step
usability score /tmp/probe                # number == truth? bound? tier? wall-clock, steps per tag → probe.score.json
usability score /tmp/probe --transcript agent.jsonl   # plus measured: wall-clock, tool time, labkit commands, refusals, files and source reads
usability trace agent.jsonl              # the agent's timeline: elapsed, duration, command (bookkeeping cut), REFUSED
usability score /tmp/probe --transcript agent.jsonl --archive DIR   # keep transcript (gzip), timeline and score
```

The fixture is twelve cases with a known number of input files each
(mean 3.5); the truth sits next to the repo, not in it. The log contract
is `HH:MM:SS · read|run|edit|unsure|gate · step`; `score` counts per tag,
takes the wall-clock from the stamps, and records the labkit version, so
two versions can be compared on the same task. Target line: one kept
number under five minutes.

## Enforcement — five layers; the first and the last cannot be forgotten

A rule the agent has to remember is the weak layer: it lives in the skill
text and dies with a long session. The layers that do not depend on
remembering (2026-10-05) — `runlog.Run` holds because every run passes
through it, the git pre-commit hook because every commit does; the three
Claude hooks hold only in a Claude Code session:

| Layer                | Where                                                      | Holds when                                            |
|----------------------|------------------------------------------------------------|-------------------------------------------------------|
| code refuses         | `runlog.Run` — leak, index header, detach, **freeze gate** | always: every run passes through it                   |
| Claude hook blocks   | `claude-hook pre-run` (PreToolUse Bash, exit 2)            | a frozen protocol's area has preflight blockers; not at `cost = "seconds"` |
| Claude hook reports  | `claude-hook post-change` (PostToolUse Bash\|Write\|Edit)  | a protocol or messung note changed, whatever wrote it |
| Claude hook sends back | `claude-hook stop` (Stop, exit 2)                        | a protocol changed in this session cites a run and `finalize` has blockers — once per stop |
| git pre-commit fails | `.githooks/pre-commit`                                     | a staged protocol misses must fields; a written-back answer fails `finalize --if-reported` |

All of them are installed by `labkit-hooks install` from the pinned labkit, and
`preflight` warns when they are missing or from another labkit version.

**Freeze gate.** `long=True` is the script's declaration of a full run.
`runlog` refuses it before `mkdir` unless the bound protocol's head says
`frozen = true` and its `preflight_audit` names the `scope sha` the code
has now (or says `n/a — <reason>`): a hand-written line is checked, not
trusted.
A long *pilot* acknowledges with `LABKIT_UNFROZEN=1`; the acknowledgement
is written to `config.json` as `unfrozen_ack`, so the number carries it.
The gate follows the cost tier (`cost` in the protocol head, AS-017 Die Zahl der Audits folgt der Kostenstufe): at
`seconds` a rerun costs nothing, so the gate is the **written success
criterion**, not the freeze — an instrument change after it is a commit
and a rerun, never a second freeze. `minutes`, `hours` and an unfilled
cost keep the freeze. The tier is written to `config.json` as `cost_tier`.

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

One word, one thing. This table is the home of the **tool's** words (the
method's live in the lab standard's vocabulary table, a lab's own in its
`notes/theorie/begriffe.md`, a protocol's in its Terms field). Everything
below occurs in more than one module, so it is coined here; the promise kinds and the block are specified in
`docs/promise-block.md`, which run answers in `docs/protocol-run-binding.md`,
and the per-field explanations live in `protocol-field-guide.md`.

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
| **frozen**          | unchangeable past a declared point (`frozen = true` in the protocol head); *freezing* is setting it, after `preflight` and the audits |
| **promise**         | one checked commitment of the protocol: an intent id with a metrics key, a sentence, a scope and constants (`[[promise]]` table) |
| **criterion**       | the promises of kind C — success or failure, decided after the run                                 |
| **admissibility**   | the promises of kind A — what must hold before a criterion may be read; one fails, every C key is None |
| **branch**          | a promise of kind B — the registered sentence per outcome (`b1_branch`)                            |
| **binding**         | a run's record of the protocol id it ran under (`config.json`); the choice of a run is a filter on it |
| **answering run**   | the newest completed run bound to the protocol that reports an intent key — the one every check holds the protocol to (`runs.bound_answering_run`) |
| **derived run**     | a run that re-evaluates another run's rows (`derived_from`); it makes no model call and records no model |
| **scope hash**      | per promise: the hash over its declared scope (`declared_scope_sha`), recorded by the run, held by `finalize` |
| **stamp**           | per area: the hash over every file that determines a number (`scope-sha`), written into an audit field, held by `runlog` at the start of a full run |

**"Ledger" is not used:** it named three different things — the run
index, a run's metrics, and the hand-written `## Runs` section.

Which protocol a run belongs to — identity, binding, selection —
is specified in `docs/protocol-run-binding.md`.

The hierarchy the vocabulary is meant to make visible:

    config.json      start state, and the binding of run to protocol
    metrics.json     result data
    completion.json  confirmed completion (note, end-of-run git state)
    runs.tsv         run index — derived, never a source
    ## Runs          manual documentation, never a source

A protocol has **one template, cut by cost**: `cost = "seconds"` (a count,
or a handful of model calls — rerunnable at will) owes a short cut and never
freezes — but the `[[promise]]` tables like every full run (standard 0.19); `minutes` and `hours` have **two modes**: `frozen = false` is the
light pilot (MUST fields only), `frozen = true` the heavy report mode —
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
   once `frozen = true`).
2. Before freezing, **`preflight <area>`** runs the pre-freeze gate:
   `protocol-check` (mandatory fields) → `code-check` (intent ids against
   the code) → `scope-sha` (audit stamp) → dirty-tree warning. The
   individual commands remain available for targeted use; `code-check
   --bundle` additionally extracts schema facts and gate labels into a
   bundle for the audit agent's judgement pass.
3. The run goes through `runlog` (frozen config, env fingerprint, script
   snapshot, split-leakage check); `runlog <area>` monitors it and lists the finished runs (what each is, committed or not, its command), `runlog
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
to be handed to students as-is. Field labels are English and held exactly
(`protocol_check.FIELDS`); field content may be German or English.

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
