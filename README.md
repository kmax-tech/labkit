# labkit

labkit helps research labs keep an experiment's question, implementation,
execution and reported result connected. It detects violations of
**explicitly encoded scientific intent across implementation, execution
and reporting**.

You write a protocol, make its checkable promises explicit, and run your
measurement through labkit. The result keeps a record of its code, inputs,
configuration and model. Before you report a number, labkit checks that it
belongs to that protocol and agrees with the recorded run.

For example, a protocol can require a minimum number of usable answers
before an accuracy is meaningful. labkit checks the declared keys and
recorded values; an agent audit reviews whether the code implements the
requirement's meaning.

It provides script templates, a Python package and command-line checks.
It requires **Python 3.12+**, has no runtime dependencies, and keeps its
records as files in your experiment repo.

## Start a lab repo

Choose a published release tag and replace `<release-tag>` below. Run these
commands from the new repo's root:

```bash
mkdir my-lab
cd my-lab
git init
python3 -m venv .venv
.venv/bin/pip install "labkit @ git+https://github.com/kmax-tech/labkit.git@<release-tag>"
.venv/bin/labkit-init lab .
.venv/bin/pip install -r requirements.txt
.venv/bin/labkit-hooks install
.venv/bin/pip freeze > requirements.lock
```

This creates the lab layout, `AGENTS.md`, a pinned `requirements.txt`,
`models.toml` and the shared-helper test. The standard and templates come
with the package. Templates are starting points to fill in, not completed
experiments.

For an **existing lab repo**, install its pin instead:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/labkit-hooks install
```

Commit the requirements and lock file. Keep the package pinned in an
experiment repo; editable installs belong in labkit development.
[Updating a pin](docs/student-repos.md#moving-to-a-newer-version) is a
separate, deliberate step; check [breaking changes](CHANGELOG.md) first.

## Run an experiment

An **area** is a directory for one question, its protocol, scripts, outputs
and runs. Create one from the repo root:

```bash
.venv/bin/labkit-init exp document-count --cost seconds
```

In a fresh repo this creates `experiments/01-document-count/` and its test
under `tests/`. The command prints the paths. Choose the cost tier by how
cheaply you can repeat the measurement:

| Tier | Before the full run | Before reporting a result |
|---|---|---|
| `seconds` | Write the registration and implement/test the measurement; no freeze or preflight audit. | Finalize, decide the analysis audit, adopt the result through `report-check`. |
| `minutes` / `hours` | Also probe the instrument, pass preflight, decide the preflight audit, complete the report fields and freeze the protocol. | Finalize, decide the analysis audit, adopt the result through `report-check`. |

Without `--model`, seconds creates a counting skeleton; minutes/hours
creates an estimator skeleton. Add `--model <alias>` for an LLM measurement.
Configure that alias in `models.toml`. Audits also use an alias; the default
`opus` uses the Claude CLI and needs its authentication. `--model` on
`labkit-audit` selects another configured backend.

### A cheap measurement, from question to result

The following paths assume the fresh area above. All commands run from the
repo root.

1. **Register the question.** Fill the protocol's open fields. For a count,
   describe the data, unit and exclusions; the stamped form lists what is
   owed. A model measurement also needs its criterion, admissibility
   condition, prompt, null condition and the judged data profile
   (`00_prepare.py --audit`, read before the run).

   ```bash
   .venv/bin/protocol-fill experiments/01-document-count/PROTOCOL-document-count.md --list
   .venv/bin/protocol-check experiments/01-document-count/PROTOCOL-document-count.md --contract
   ```

   Use `protocol-fill PROTOCOL "LABEL=VALUE" ...` to fill several fields.
   The [field guide](labkit/docs/protocol-field-guide.md) explains them.

2. **Implement and test.** Fill the script and area-test TODOs, including
   the source, expected items and calculation. The scripts already use
   `runlog` to keep the measurement's record.

   ```bash
   .venv/bin/pytest -q
   .venv/bin/code-check experiments/01-document-count
   ```

3. **Commit the code and inputs, then run.**

   ```bash
   .venv/bin/python experiments/01-document-count/scripts/01_measure.py
   .venv/bin/runlog experiments/01-document-count
   ```

   Keep the printed run ID. Commit the recorded inputs, outputs and run
   artifacts as required by the checks.

4. **Check the result and audit its interpretation.**

   ```bash
   .venv/bin/finalize experiments/01-document-count
   .venv/bin/labkit-audit experiments/01-document-count --mode analysis
   ```

   Resolve the findings in the written `audits/*.toml`: each needs a status
   (`fixed`, `accepted`, `deferred` or `dismissed`) and a reason. Fixes can
   invalidate the audit's binding; rerun the affected measurement or audit
   when the checks require it.

5. **Adopt the result.** Replace `<run-id>` with the recorded run ID:

   ```bash
   .venv/bin/protocol-fill experiments/01-document-count/PROTOCOL-document-count.md --from-run <run-id>
   ```

   This writes the answer and run reference from `metrics.json`, runs
   `report-check`, and restores the protocol if a check blocks adoption.
   Commit the resulting protocol and artifacts. Later, rerun
   `report-check experiments/01-document-count` to check the reported result.

Scripts declare `run_kind="measurement"`; a separate `run_kind="probe"`
is only allowed at minutes/hours. Data preparation uses
`run_kind="preparation"` and keeps its own provenance record. At seconds, repeat the full measurement
to check or correct the instrument.

An exploration may leave the answer open and end without a reported result.
A probe (`run_kind="probe"`) or an acknowledged unfrozen run cannot supply a
reportable number.

### Longer measurements

At `minutes`/`hours`, follow the longer lane in the repo's `AGENTS.md`:
render real prompts where applicable, run the instrument probe, complete
the area tests, run `preflight`, then `labkit-audit --mode preflight`.
Decide the findings and fill the protocol's audit field with the matching
stamp. Add report fields with `labkit-init exp <name> --report`, complete
them, set `frozen = true`, and commit before the full run.

When your agent's shell has a foreground time limit, start the run detached
and wait for its recorded state:

```bash
.venv/bin/runlog start experiments/01-document-count -- .venv/bin/python experiments/01-document-count/scripts/01_measure.py
.venv/bin/runlog experiments/01-document-count --wait
```

Use your actual area's path. Follow the same post-run steps as above:
finalize, analysis audit, decisions, adoption. Internal checks and timeout
configuration are described in [architecture](docs/architecture.md#run-and-hook-enforcement).

## What the checks establish

| Tier | What it tells you |
|---|---|
| **Guaranteed** | An exact encoded condition holds: for example, the run is bound to the protocol or a cited number matches its record. Silent on correct input. |
| **Static evidence** | A code pattern deserves review. It warns and never blocks; it does not prove the code's meaning. |
| **Agent audit** | A model reviews the implementation or analysis against the scientific intent. Findings need a decision; this is semantic review, not a guarantee. |

`preflight` checks readiness before freezing; `finalize` checks the completed
run. **`report-check` checks release of the result at every cost tier**,
including a decided analysis audit and the area's recomputation check.
`labkit-audit` performs the model review; running `preflight` alone does not
perform that review.

The run writer and git hooks enforce checks independently of an agent.
Claude Code's live hooks add feedback during a session. Install the pinned
hooks with `labkit-hooks install`, and repeat that after raising the pin.

## Command reference

The **console commands** are installed with the package. Use
`.venv/bin/<command>` from the repo root; each supports `--help`.

```bash
labkit-init lab [DIR]               # create a lab repo
labkit-init exp NAME [--cost T] [--model ALIAS] [--report] [--explore]
protocol-check PROTOCOL             # check required fields and promise tables
protocol-check --contract | --guide # field contract or field-guide path
protocol-fill PROTOCOL "LABEL=VALUE" ... # fill fields
protocol-fill PROTOCOL --list | --prompts | --render | --from-run [RUN]
protocol-fill PROTOCOL --into REPORT.md # the declared result as a generated block in a report
code-check AREA [--protocol FILE] [--bundle FILE] # code checks; audit bundle
intent-check PROTOCOL [--metrics FILE] # promises against recorded metrics
scope-sha AREA                     # code stamp used by an audit
preflight AREA                     # readiness before freezing
finalize AREA                      # checks after the run
labkit-audit AREA --mode preflight|analysis|clarity [--model ALIAS]
labkit-audit AREA --decide N STATUS REASON [--effect E] [--record FILE] # store your decision on a finding (an accepted BLOCKER owes --effect)
labkit-audit AREA --findings [--record FILE]               # show what there is to decide, no audit
report-check AREA                  # release check before reporting
report-check --if-reported [--staged] PATH... # check affected reported areas and citing reports
runlog [AREA] [--wait | --follow]    # inspect or monitor runs
runlog start AREA -- COMMAND       # start a detached run
runlog reindex AREA                # recover missing index rows
labkit-params AREA [--run ID]       # values and provenance of a run
labkit-hooks install|check [REPO]   # install or check hooks
claude-hook pre-run|post-change|stop # live Claude Code hook adapter
claude-hook undecided PATH...      # unresolved audit blockers in touched areas
claude-hook sessions [--run RUN_ID] # session records
labkit-check [REPO] [--offline]     # report pin, installation and hook drift
notes-check PATH                   # check measurement-note declarations
labkit-calltree [--depth N] [--out FILE] COMMAND [-- ARGS] # inspect calls
usability stage|log|score|trace     # prepare and measure an agent's workflow
usability reader|read-score|glance|glance-score|terms # protocol reading probes
usability nav|nav-score|human       # code navigation probes
```

Mechanical gates return failure when they have blockers; warnings alone
pass. `labkit-audit` exits 1 for either blockers or warnings, and 2 on an
execution error. `--mode clarity` reviews readability and is never a gate.

## Terms

This is the home of labkit's tool vocabulary. Method terms live in the
[standard](labkit/docs/standard.md); terms local to an experiment belong in
its protocol. The [promise format](docs/promise-block.md) and
[protocol/run binding](docs/protocol-run-binding.md) specify the contracts.

| Term | Meaning |
|---|---|
| **area** | Directory grouping an experiment's protocols, scripts and runs. |
| **protocol** | Experiment specification in `PROTOCOL-*.md`. |
| **protocol id** | Stable, path-independent identity: `p-` followed by 16 hex characters. |
| **run** | One execution recorded under a protocol. |
| **preparation** | Recorded data preparation, before the measurement; cannot supply a reported result. |
| **probe** | Instrument check before a measurement at minutes/hours; its number is not reported. |
| **measurement** | Run of the registered question, eligible for result release after the required checks. |
| **run metadata** | Start and completion records: `config.json` and `completion.json`. |
| **run index** | Searchable overview in `runs.tsv`. |
| **metrics** | Measured values recorded in `metrics.json`. |
| **documented runs** | Entries in a protocol's `## Runs` section. |
| **intent id** | Identifier of a checked promise: `[C1]`, `[A1]`, `[B1]`, etc. |
| **bundle** | Protocol, code and extracted facts packed for an audit agent. |
| **frozen** | Protocol committed to its declared specification, with `frozen = true`. |
| **promise** | Checkable commitment: id, metrics key, sentence, code scope and constants in a `[[promise]]` table. |
| **criterion** | Kind C promise: success or failure decided from the run. |
| **admissibility** | Kind A promise: prerequisite for reading a criterion; failure withholds all C verdicts. |
| **branch** | Kind B promise: the registered interpretation for an outcome, recorded as `b1_branch`, etc. |
| **binding** | Run's record of the protocol id it ran under. |
| **answering run** | Completed run selected to answer a particular protocol; repeat draws are excluded. Selection rules: [protocol/run binding](docs/protocol-run-binding.md). |
| **derived run** | Re-evaluation of a completed non-repeat run's rows through `derived_from`, with no new model calls. |
| **scope hash** | Per-promise hash of its declared code scope, recorded with the run and checked by finalize. |
| **stamp** | Area audit fingerprint of selected source files, declared scopes and the package pin. |
| **estimator** | Instrument fitted to data; the stamped estimator skeleton compares true-label and permuted-label lanes. |

The run index and a protocol's `## Runs` section are views of the run
records; they are not the source of truth. Python scripts import helpers
from their package directly:

```python
from labkit.run import runlog, llm, batch
from labkit.checks import recheck
```

Use the stamped scripts as integration examples. `recheck.holds` connects
an analysis script's `--check` to recorded outputs, recomputed metrics and
the cited result.

## Develop labkit

In a checkout of this repo:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

`just check` runs lint, formatting, type checking and the suite.
[AGENTS.md](AGENTS.md) holds the contribution rules;
[architecture](docs/architecture.md) explains layers, records and enforcement;
[TODO](TODO.md) holds open work. Historical audits and usability measurements
live under `docs/` and `docs/usability/`.

A release starts with its CHANGELOG entry; `just release X.Y.Z` sets the
version, commits through the checks and tags that commit. The author pushes
the tag. Experiment repos adopt it by changing their pin.
