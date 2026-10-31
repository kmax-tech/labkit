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
.venv/bin/labkit-init exp document-count --repeat-cost low --kind compute
```

In a fresh repo this creates `experiments/01-document-count/` and its test
under `tests/`. The command prints the paths. Choose the repeat cost by how
cheaply you can repeat the measurement:

| Repeat cost | Before the full run | Before reporting a result |
|---|---|---|
| `low` | Write and commit the registration, implement/test the measurement; no freeze or preflight audit. | Finalize, decide the analysis audit, adopt the result through `report-check` (which holds the registration to the commit of the first measurement). |
| `high` | Also probe the instrument where the skeleton has a probe (a computation's run is its own instrument check), pass preflight, decide the preflight audit, complete the report fields and freeze the protocol. | Finalize, decide the analysis audit, adopt the result through `report-check`. |

`--kind` says what the kept number asserts, and the skeleton and the
registration follow it: `compute` judges no prediction (the compute
skeleton; question, scope, exclusions, unit); `fit` judges a model trained
or adjusted in the experiment (the estimator skeleton; also criterion,
quality check, null condition); `apply` judges a model used
unchanged (with `--model <alias>` the prompt skeleton, else the unchanged
predictor's `predict(X)`, never trained; its null lane scores the same
predictions against labels permuted with the seed, or a fixed null
predictor the protocol registers). Declare every loaded model file in
`PREDICTOR_FILES` so its content is bound to the run, resumed output and
repeat configuration. Add `--model <alias>` when the model answers through `models.toml`;
configure that alias there. Audits also use an alias; the default
`opus` uses the Claude CLI and needs its authentication. `--model` on
`labkit-audit` selects another configured backend.

### A cheap measurement, from question to result

The following paths assume the fresh area above. All commands run from the
repo root.

1. **Register the question.** Fill the protocol's open fields. For a computation,
   describe the data, unit and exclusions; the stamped form lists what is
   owed. A fit or an apply also registers its criterion, quality
   check and null condition; with a model named, the prompt and the
   judged data profile follow (the prompt skeleton's `00_prepare.py --audit`
   prints an aid; read before the run).

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

   Decide each finding with the command `labkit-audit
   experiments/01-document-count --findings` prints for it (`--decide N
   STATUS --why "REASON"`): `fixed`, `limitation` or `false-positive` — a
   BLOCKER nobody can settle stays `open`, and the handover records it;
   all but `fixed` owe a reason (`--why`); a `limitation` that leaves a promise unjudged names it with `--not-assessable`.
   The record is never edited by hand. Fixes can invalidate the audit's
   binding; rerun the affected measurement or audit when the checks
   require it.

5. **Adopt the result.** Replace `<run-id>` with the recorded run ID:

   ```bash
   .venv/bin/labkit-adopt experiments/01-document-count <run-id>
   ```

   This writes the answer and run reference from `metrics.json`, runs
   `report-check`, and restores the protocol if a check blocks adoption.
   Commit the resulting protocol and artifacts. Later, rerun
   `report-check experiments/01-document-count` to check the reported result.

Scripts declare `run_kind="measurement"`; a separate `run_kind="probe"`
is only allowed at high repeat cost. Data preparation uses
`run_kind="preparation"` and keeps its own provenance record. At low repeat cost, repeat the full measurement
to check or correct the instrument.

An exploration may leave the answer open and end without a reported result.
A probe (`run_kind="probe"`) or an acknowledged unfrozen run cannot supply a
reportable number. A report (`REPORT.md`, a results note) that cites the
area's answering run while its protocol has adopted no result is held at the
stop and the commit: that is the number leaving the area without the
adoption. A run the report looks at without reporting it stands in a
discussion block, `protocol-fill <PROTOCOL> --discuss <run_id> --why "<what
refused the adoption, what you found>" --into REPORT.md`: its head holds
the protocol, the run and the why as TOML, its line
(`Run <run_id> — discussed, not reported: <why>`) is written from them.
Which block a report gets: the number a protocol has adopted → `--into`; a
run looked at but not reported → `--discuss`; a protocol that ends
without a result → `--handover` (below).

### When a check stops you

When a check stops you, `labkit-audit <area> --findings` shows readable
open findings, evidence problems and complete recovery commands without a
model call. For a failed audit call — a `-failed.toml` (the backend did
not answer) or an attempt the journal ended without a record (the answer
did not read, kept under `audits/answers/`) — it names the call, its
error and its kept answer and offers the handover without inventing
findings; it exits 2 then. A later completed audit of the same mode and
the same protocol with the same promise block supersedes the call, also
after a code change (the journal's order; an earlier audit, another
protocol or promise block supersede nothing; a protocol is named by its
file name, so one renamed since counts as another): it is then shown as
superseded by that record, informational, never as open. The old call and its kept answer stay as they are; superseding confirms neither the call's content nor the repair of any finding, and a recorded BLOCKER stays under the follow-up rule. A historical call —
its start written by labkit 0.103.0 or earlier without a promise block
and protocol, or a `-failed.toml` no journal attempt names — is named as
such with the command that supersedes it: the audit of its mode run
again now (`labkit-audit <area> --mode <mode>`), of any protocol of the
area, since the old start names none. Decide unresolved readable BLOCKERs explicitly before using
the printed `protocol-fill ... --handover --why ... --tried ... --into
REPORT.md` command. It withdraws the protocol's result, keeps an
immutable handover record of the remaining evidence, losses, the
findings left open and the run the protocol stands at — none measured,
measured without a number, held by checks, or adoptable, with the
reasons — and writes the record's handover block (the state, no run id)
into the report — one block per protocol, replaced in place. It withdraws
that protocol's result blocks in the chosen report and keeps other text
and other protocols' blocks. Citations in prose and other reports still
need to be removed or explicitly discussed; the handover names each such
report with its `--discuss` command — after a loss of audit evidence the
restore or the removal instead, since labkit-audit starts no review while
evidence is gone. It permits no result or audit approval. Stage the
protocol, report, handover record and remaining evidence together.

### Longer measurements

At `high`, follow the additional before-run steps in the common workflow
in the repo's `AGENTS.md`:
where the skeleton has them, render real prompts and run the instrument
probe (a computation has neither), complete the area tests, run
`preflight`, then `labkit-audit --mode preflight`.
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
run. **`report-check` checks release of the result at every repeat cost**,
including a decided analysis audit and the area's recomputation check.
`labkit-audit` performs the model review; running `preflight` alone does not
perform that review.

The run writer and git hooks enforce checks independently of an agent.
Claude Code and Codex live hooks add feedback during a session. Install the pinned
hooks with `labkit-hooks install`, and repeat that after raising the pin.
Start Claude Code in the repository root: a session started in a directory
below it loads none of the hooks the root's `.claude/settings.json` holds
(the pre-commit still holds every commit).
Codex uses `.codex/hooks.json`: trust the project and review the installed
hooks with `/hooks` before they run. Reinstall after moving the repository,
since its Codex commands name the repo venv by absolute path.
See [Codex hooks](docs/codex-hooks.md) for the event contract and limits.

## Command reference

The **console commands** are installed with the package. Use
`.venv/bin/<command>` from the repo root; each supports `--help`.

```bash
labkit-init lab [DIR]               # create a lab repo
labkit-next AREA [--protocol FILE]    # where the area stands, the one next step, and what is held until it is taken
labkit-next --guide                   # the workflow in full (labkit/docs/agent-guide.md), which the stamped AGENTS.md keeps short
labkit-adopt AREA [RUN] [--protocol FILE]  # adopt the run: --from-run, the registered report's --into, report-check — stops at the first that does not pass
labkit-init exp NAME [--repeat-cost T] --kind compute|fit|apply [--model ALIAS] [--report] [--report-file PATH] [--explore]
labkit-init exp NAME --kind compute --reference KEY=VALUE[±TOL] [--relation within|at_least|at_most] [--reference-source TEXT] # a computation compared with a stated value: the head's [reference]
labkit-init exp NAME --kind KIND --change-kind # another kind before the first measurement, written fields kept
labkit-init numbers [--staged]      # one number per area (--staged: the index); the next free one over every branch and worktree
protocol-check PROTOCOL             # check required fields and promise tables
protocol-check [PROTOCOL] --contract | --guide # field contract (with PROTOCOL: the fields it owes and its row) or field-guide path
protocol-fill PROTOCOL "LABEL=VALUE" ... # fill fields
protocol-fill PROTOCOL --list | --prompts | --render | --from-run [RUN]
protocol-fill PROTOCOL --into REPORT.md # the adopted result as a generated block in a report
protocol-fill PROTOCOL --handover --why "…" --tried "…" --into REPORT.md # end without a result: [result] withdrawn, a handover record, its block in the report
protocol-fill PROTOCOL --discuss RUN_ID --why "…" --into REPORT.md # a run the report looks at without reporting it, as a discussion block
protocol-fill PROTOCOL --withdraw --why "…" [--into REPORT.md] # the adoption withdrawn, the run's Runs entry marked; audit, then --from-run adopts the run that answers
code-check AREA [--protocol FILE] [--bundle FILE] # code checks; audit bundle
intent-check PROTOCOL [--metrics FILE] # promises against recorded metrics
scope-sha AREA                     # code stamp used by an audit
preflight AREA                     # readiness before freezing
finalize AREA                      # checks after the run
labkit-audit AREA --mode preflight|analysis|clarity [--model ALIAS]
labkit-audit AREA --decide N STATUS --why REASON [--not-assessable IDS] [--record FILE] # store your decision on a finding (fixed, limitation, false-positive)
labkit-audit AREA --findings [--record FILE]               # show what there is to decide, no audit
labkit-audit AREA --review [--record FILE] [--again]       # a second auditor on the `stands` decisions, and on a finding closed after a review did not uphold it: does the reported claim stand within each limit? (--again: one more draw on a judged state — its verdicts count, it lifts no hold; the exit is the state's, as without --again)
labkit-audit AREA --report-review REPORT                   # a cold reader on a report that discusses a run (a discussion block): does it state that run's numbers as results, or what the audits contradict? recorded in audits/report-reviews/; report-check holds the report until a review of its state names no claim; exit 0 only when the state is released, 2 on a claimed state without --again [--again: one more draw on a judged state — its claims hold, it releases nothing]
report-check AREA                  # release check before reporting
report-check --if-reported [--staged] PATH... # check affected reported areas, citing reports, and the report a protocol head registers (owed its result block or handover block once delivered)
runlog [AREA] [--wait | --follow]    # inspect or monitor runs
runlog start AREA -- COMMAND       # start a detached run; returns once its run directory exists (2: the command failed first, 3: still starting)
runlog reindex AREA                # recover missing index rows
labkit-params AREA [--run ID]       # values and provenance of a run
labkit-hooks install|check [REPO]   # install or check hooks
claude-hook pre-run|post-change|stop # live Claude Code hook adapter
codex-hook pre-run|post-change|stop  # live Codex hook adapter
claude-hook undecided PATH...      # unresolved audit blockers in touched areas
claude-hook sessions [--run RUN_ID] # session records
labkit-check [REPO] [--offline]     # report pin, installation and hook drift
notes-check PATH                   # check measurement-note declarations
labkit-calltree [--depth N] [--out FILE] COMMAND [-- ARGS] # inspect calls
usability stage|log|score|trace     # prepare and measure an agent's workflow (--task count|judge|fit|compute-hrv|fit-assay|apply-screen, fit with --data)
usability reader|read-score|glance|glance-score|terms # protocol reading probes
usability nav|nav-score|human       # code navigation probes
```

Mechanical gates return failure when they have blockers; warnings alone
pass. `labkit-audit` exits 1 for either blockers or warnings, and 2 on an
execution error; `--findings` exits 2 also when audit evidence is gone or
does not read, after listing what does. `--mode clarity` reviews
readability and is never a gate.

## Terms

This is the home of labkit's tool vocabulary. Method terms live in the
[standard](labkit/docs/standard.md); terms local to an experiment belong in
its protocol. The [promise format](docs/promise-block.md) and
[protocol/run binding](docs/protocol-run-binding.md) specify the contracts.

| Term | Meaning |
|---|---|
| **area** | Directory grouping an experiment's protocols, scripts and runs. |
| **core / doctrine** | Core: what every lab must answer the same way — which run made a number, from which code, data and model. Doctrine: what another lab could decide differently — the standard, the templates, the gates' order. Definition and strike test: [architecture](docs/architecture.md#core-and-doctrine). |
| **protocol** | Experiment specification in `PROTOCOL-*.md`. |
| **protocol id** | Stable, path-independent identity: `p-` followed by 16 hex characters. |
| **run** | One execution recorded under a protocol. |
| **preparation** | Recorded data preparation, before the measurement; cannot supply a reported result. |
| **repeat cost** | `repeat_cost` in the protocol head, `low` or `high`: the price of repeating the run. It selects the lane — what the area owes before and after the run (the table above, `standard_contract.lane`). |
| **probe** | Instrument check before a measurement at high repeat cost; its number is not reported. |
| **measurement** | Run of the registered question, eligible for result release after the required checks. |
| **handover** | A protocol's end without a result: `protocol-fill <PROTOCOL> --handover` withdraws `[result]`, keeps a handover record under `audits/handovers/` (the remaining evidence, its losses, the findings left open, the run it stands at and what held its adoption) and writes its handover block into the report. The stop and the commit then accept the loss and the open findings it records; audits and adoption stay refused until the evidence is restored, and a measurement after the handover ends it. |
| **run metadata** | Start and completion records: `config.json` and `completion.json`. |
| **run index** | Searchable overview in `runs.tsv`. |
| **metrics** | Measured values recorded in `metrics.json`. |
| **protocol run list** | The protocol's `## Runs` section: references to runs; listing a run does not select or release its result. |
| **run entry** | One reference in the protocol run list: a run id and a sentence describing the run. |
| **intent id** | Identifier of a checked promise: `[criterion-1]`, `[quality-check-1]`, `[branch-1]`, etc. |
| **bundle** | Protocol, code and extracted facts packed by `code-check --bundle` for an agent the lab runs on it; labkit ships none. |
| **frozen** | Protocol committed to its declared specification, with `frozen = true`. |
| **kind** | What the kept number asserts, in the head (`kind`): `compute` judges no prediction, `fit` judges a model trained or adjusted in the experiment, `apply` judges a model used unchanged. The registration and the skeleton follow it; a run that only produces predictions declares no result and needs none. |
| **number_describes** | `[model]` key of a `compute` with a model in the loop: `model_outputs` (the number describes what the model marked) or `target_property` (a property of the data, the model as annotator). |
| **annotation validity** | Evidence that a model suits as annotator, owed with `target_property` (`[model] annotation_validity`): an apply protocol of the repo with an adopted result, bound by protocol-check and preflight, or a DOI, checked for its form only; whether it carries the annotation stays the audit's. |
| **promise** | An explicitly registered requirement that the implementation and the run are checked against: id, metrics key, sentence, code scope and constants in a `[[promise]]` table. |
| **inference criterion** | Promise kind `criterion` (`[criterion-1]`, protocol field `Inference criterion`): the registered condition on the result that decides which conclusion the run supports; a missed criterion is a valid result (OSF preregistration: *inference criteria*). |
| **quality check** | Promise kind `quality-check` (`[quality-check-1]`): assesses whether the measurement can support the intended inference, rather than whether the result supports the hypothesis; its condition is specified before the result is known. If any quality check is not met or cannot be assessed, no inference criterion receives a verdict; measured values may still be reported descriptively (Registered Reports: *outcome-neutral conditions*). |
| **registered branch** | Promise kind `branch` (`[branch-1]`): a pre-specified mapping from conditions on the results to named outcomes and their consequences, written `<condition> → <outcome>: <consequence>; …` (COS: decision tree of IF-THEN rules). |
| **condition** | A condition on the results that selects an outcome; the first that holds selects, a final `otherwise` covers the cases no earlier condition matched. |
| **outcome** | A named possible result of a registered branch; the run records the name its condition selected (`branch_1_outcome`) (PCI RR: *interpretation given different outcomes*; not CONSORT's outcome measure). |
| **consequence** | What the selected outcome permits: an interpretation, an action, or an explicitly justified non-action. |
| **binding** | Run's record of the protocol id it ran under. |
| **answering run** | Completed run selected to answer a particular protocol; repeat draws are excluded. Selection rules: [protocol/run binding](docs/protocol-run-binding.md). |
| **adopted run** | Run named by `[result].run` as the reported result, written by the adoption (`labkit-adopt`, through `protocol-fill --from-run`) and removed by `--withdraw`; the gates require it to equal the answering run. |
| **conclusion** | Author's interpretation answering the question, in at most two plain sentences in the Summary's `Conclusion` field. |
| **recorded results** | Generated verdicts of the registered promises (a quality check not assessable or not met leaves each criterion not assessable), the other metrics, run id and limits note in the protocol's `Recorded results` field; checked against the declared run and covering audit records. |
| **report result block** | Generated section in a separate report containing the recorded results and full Limitation lines; written by `protocol-fill --into` and checked against the same sources. |
| **discussion block** | Generated section in a separate report for a run it looks at without reporting it: protocol, run and why as TOML in the head, the line `Run <id> — discussed, not reported: <why>` written from them; written by `protocol-fill --discuss … --into`. |
| **derived run** | Re-evaluation of a completed non-repeat run's rows through `derived_from`, with no new model calls. |
| **scope hash** | Per-promise hash of its declared code scope, recorded with the run and checked by finalize. |
| **stamp** | Area audit fingerprint of selected source files, declared scopes and the package pin. |
| **estimator** | The instrument of the estimator skeleton: at `fit` trained on the data, at a local `apply` the unchanged predictor; both compare a registered lane with a null lane on permuted labels. |

The protocol's recorded results and a report result block present the
same bound sources. The report block includes the full Limitation lines so its
reader can see the restrictions alongside the numbers. The conclusion is
the author's interpretation of those results within their limits.

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
[architecture](docs/architecture.md) explains layers, [core and doctrine](docs/architecture.md#core-and-doctrine), records and enforcement;
[TODO](TODO.md) holds open work. Historical audits and usability measurements
live under `docs/` and `docs/usability/`.

A release starts with its CHANGELOG entry; `just release X.Y.Z` sets the
version, commits through the checks and tags that commit. The author pushes
the tag. Experiment repos adopt it by changing their pin.
