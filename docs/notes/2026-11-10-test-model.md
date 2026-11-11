# Simplify checks and tests — implementation plan (2026-11-10)

> Decided by the author on 2026-11-10: restructure the checks and tests before the next usage round. This note owns the implementation plan; [TODO task 6c](../../TODO.md#6c-ein-klares-testmodell-und-der-umbau-der-checks--vor-der-nutzungsrunde-entschieden-2026-11-10) owns its place in the work order.

## Start here

**Problem:** labkit's tests reach most check logic only from the outside, or not at all. Of the 194 places that build a gate finding, 90 are reached no closer than through a gate, 19 only through whole console commands, and 30 by no test at all. One provenance warning is reached by 172 tests without being the subject of most of them. 168 of the 194 places name no rule in their message. The fast tier takes 81 s; the full suite takes roughly 302 s longer ([What it shows](#what-it-shows-run-of-2026-11-10-suite-green)).

**Goal:** each scientific or technical condition has one implementation and tests of its own. Gates combine checks; scenario tests verify only what one command passes to the next. The plan keeps what today's tests establish first and reduces test time second.

**Status:** steps 1 to 5 are done ([step 5](#5-measure-and-review)). The full suite runs 13–14 % faster than at the baseline with 100 tests more; the timing targets are missed, by the author's decision, and three sites still wait for the second-review decision. **Target 4:** the independent review found a missing gate assertion for a field edited after the answering run ([review](2026-11-11-test-model-review.md)); that assertion is restored in `29290169` (the review, "Correction"). The second call of the same comparison has its test since `cd615bb5`. A measurement over the callers of the pure checks (the review, "The callers of every pure check") found one more unheld caller, finalize's null-lane station, now tested (`NullLaneStation`). The author closed target 4 on 2026-11-11.

**Execution order:** 1 → 2a → finalize pilot → stop for the author's decision → 2b → remaining gates → 4 → 5. The pilot is the migration of the finalize gate alone; it has no time cap (author decision, 2026-11-10). Do not build the full measurement tooling of step 2b before the author's decision at the checkpoint.

### Terms used in this note

The words below are local to this plan unless a source is named. Where the [README terms](../../README.md#terms) use the same word in another sense, the entry says so.

- **Finding site:** a place in the source that builds a finding or ends a command with a message (`check_inventory.finding_sites`). It is the unit the plan counts.
- **Channel:** how a site tells its result. `finding` builds a gate finding (`GateFinding`); `exit` raises `SystemExit(<message>)`; `printed` prints its own `WARNING:` or `BLOCKER:` line.
- **Refusal:** the message of an `exit` site. A *missed* refusal is one the scanner does not see (step 2b).
- **Condition:** what one check decides; it is the unit the plan tests. Several sites can share one condition. Not the README's *condition*, which selects the outcome of a registered branch.
- **Valid twin:** the test beside a violation test whose input satisfies the condition and therefore yields no finding.
- **Station:** one named step inside a gate; finalize runs its stations in order.
- **Scenario test:** a test that runs real console commands in a lab repository; 13 scenario files hold them, and they carry the `slow` mark.
- **Fast tier, slow tier:** the tests without and with the `slow` mark.
- **Inventory:** the two tool outputs the plan measures with. `python -m labkit.tools.check_inventory` lists the sites from the source; `python -m labkit.tools.test_inventory` records which test reaches which site.
- **Reach:** a test reaches a site when the site builds a finding while the test runs. Reach is not an assertion.
- **Unreached site:** a site no test reaches. **Command-only site:** a site that tests reach only through whole console commands.
- **Site account:** the temporary table that tracks every site through the migration ([Site account](#site-account)).
- **Extraction exception:** a site that deliberately stays outside a pure check, with its reason recorded in the site account.
- **Gate finding** (`GateFinding`) and **audit finding** (`findings.Finding`) are two different records. The README's *finding* is the audit finding.

## The plan

Extracting a check and testing its condition belong in the same commit. Repeat step 3 in small commits, one gate at a time. While working, run the tests of the changed modules and the repository's required commit checks; run the full suite when a measurement requires it.

| Step       | Deliverable                                                                      | Acceptance                                                                                                                                    |
|------------|----------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| 1          | Minimal state builder, decision on run inputs, and the first migrated check      | Violation test and valid twin run from data; an inconsistent test input stays unchanged; the rule-test guard and the pure-check guard exist   |
| 2a         | Shared rule value in `GateFinding`, and the site account opened for finalize     | Invalid rule values are refused; every `GateFinding.rule` uses the value; the site account lists finalize's sites at the pilot's start commit |
| 3, pilot   | Migrate finalize                                                                 | Its conditions, its composition and its extraction exceptions meet the [contracts](#contracts-used-throughout); work stops at the checkpoint  |
| Checkpoint | Pilot cost, clarity, abstraction balance and an estimate of the remaining effort | The author chooses to continue, to continue with a narrower scope and a time cap, or to defer                                                 |
| 2b         | Rule data in all records, complete site account, and the inventory comparison    | All remaining sites and missed refusals are in the site account; every difference between the inventories is explained there                  |
| 3, rest    | Migrate the remaining gates and the checks that run during a measurement         | Every site maps to a rule test, a gate test, or a justified extraction exception                                                              |
| 4          | Report of scenario tests that could be removed, and fewer scenario variants      | Every removed assertion has a named replacement; each state that one command passes to the next stays covered                                 |
| 5          | Final inventory, review and timing                                               | Report on all targets, the open rule assignments, the extraction exceptions and the timing results                                            |

### 1. Establish the reference check

Build `tests/state_fixture.py` on the existing `AreaState` and `AreaEvidence` types. Keep the inputs that matter for a test explicit and minimal. The builder adds no hidden scientific defaults, does not synchronize derived fields, and does not repair or normalize inconsistent states. A default may shorten boilerplate that does not matter for the test, but only when it is documented and independent of the tested condition. Add the gate-layer `Checked` value only when report-check's gate tests need it; checks never receive it.

**Resolve the missing run inputs before migrating the checks that need them.** About half of finalize's stations take a run directory and read data that `AreaState` does not hold: code and scope hashes, outputs, metrics, recorded inputs and Git tracking. The affected stations are `check_run_code`, `check_declared_scopes`, `check_provenance`, `check_null_lane`, `check_registered_outputs` and `check_criterion_n`. The checks they call in `labkit/checks/run_record_check.py` also take a directory today. Reuse the records that `labkit/formats/runs.py` returns where possible. Decide which typed value carries the remaining inputs and their read failures, and which reader builds that value. A new type must describe a run and must not duplicate the area model. `gate.outcome_of_failed_read` stays the classifier for failed reads. `check_area_tests` stays an execution boundary through `preflight.area_tests`.

Migrate one condition with its violation test and valid twin under the [check contract](#check-contract). Record here its actual signature, location, gate caller and the decision on run inputs; later migrations copy this template. Show with a test that the builder keeps a deliberately inconsistent input unchanged. Introduce the rule-test guard and the pure-check guard with this example ([Architecture guards](#architecture-guards)).

**Built 2026-11-10 (`e3789158`).** The reference condition: an analysis audit record names a run the area no longer holds (LAB-043 Runs go through `runlog`). Before, the site `labkit/gates/finalize.py:355` was reached only through whole commands, by 2 tests (inventory of 2026-11-10 at `524b93ce`).

| Part          | As built                                                                                                                                                                                                             |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Check         | `check_audited_runs_kept(state: AreaState, *, evidence: AreaEvidence) -> list[GateFinding]` in `labkit/checks/audit_binding.py`; its way out `gone_run_way(state, run_id)` moved there from finalize                 |
| Gate caller   | `finalize.check_open_audit_findings` (station 9): `findings.take_all(check_audited_runs_kept(state, evidence=held))`; unreadable records first and the open findings stay the station's                              |
| Rule test     | `tests/test_rules_audit_binding.py`: the violation (grade, evidence kind, outcome, text, way out, step), the way out from the commit that holds the run, and the valid twin (a kept run, no run, a preflight record) |
| State builder | `tests/state_fixture.py`: `area_state`, `area_evidence` take every field as given, empty otherwise; `run_dir`, `audit_record` fill named placeholders that bear on no run or record condition                        |
| Guards        | `tests/check_guards.py`: the mark `rule` (registered in `tests/conftest.py`) forbids processes and console commands for the whole test; `pure_call` forbids file and process access around one check call            |
| Guard tests   | `tests/test_check_guards.py`: forbidden and allowed example of each guard, the mark switches the guard on, every `tests/test_rules_*.py` carries the mark, the builder keeps an inconsistent state unchanged         |

The template for every later migration: the pure check in its subject module under `labkit/checks/`, with the smallest typed inputs that suffice; the station calls it and forwards with `take_all`; the rule tests in `tests/test_rules_<module>.py` with `pytestmark = pytest.mark.rule`, each check call through `pure_call`, inputs from `state_fixture`. The rule value is still absent; step 2a adds it and the rule test then asserts it.

A limit of `pure_call`: `Path.resolve` passes, because a way out names paths as the working directory reaches them (`repo.shown`). A check's way out therefore depends on the working directory and resolves paths; everything else that touches the file system is refused.

**Decision on run inputs.** No aggregate run type. A run station calls the readers of `labkit/formats/runs.py` — `read_run_config` (`RunConfig`), `read_metrics` (a dict), `read_outputs` (`OutputEntry`), `read_data` (`DataEntry`) —, turns their typed failure (`ArtefactError`, a `files.ReadError`) into `run_file_unread` as today, and hands the check the typed records. One value read up front would let an unreadable `outputs.json` reach stations that never read it and change which blockers appear; the migration keeps each check's meaning. What the record files do not hold — the bytes of a recorded output or source as the tree holds them now, the rows of a kept JSONL output — comes from a reader beside the record readers in `runs.py` that returns a small frozen value per recorded file; it describes the run's files, never the area, and `AreaState` stays the one area model. Each value is built when its station migrates (registered outputs, null lane, criterion n, provenance). The git half of `check_provenance` (tracked, ignored), `check_run_code` (git history, the run's script copies) and `check_declared_scopes` (scope hashes now) read the repository: at their migration their pure conditions are extracted and the reading stays a reader or an extraction exception with its reason. `check_area_tests` stays an execution boundary through `preflight.area_tests`.

### 2a. Prepare only what finalize needs

Define and validate the [shared rule value](#rule-assignment). Switch `GateFinding.rule` to it at once, at every site that sets the field. On 2026-11-10 these are about 15 `rule=` uses in 7 modules, none of them in finalize. After the switch the field never accepts the old string and the new value side by side. Then set the new value at finalize's sites. The first migrated test asserts the normalized value.

Open the [site account](#site-account) for finalize at the pilot's start commit, covering all three channels. Read the source for refusals the scanner misses. Three things wait for step 2b: the audit records' `findings.Finding.rule`, the constructors that cannot yet receive a rule, and the inventory tooling.

**Built 2026-11-10 (`b4fdf56d`).** `gate.RuleAssignment` holds the kind (`KNOWN_RULE`, `OPEN_ASSIGNMENT`, `TECHNICAL_CONTRACT`, `NEW_CLASS`) and, for a known rule, its id and name; `cited_rule("LAB-nnn Name")` builds a known rule, and `OPEN_RULE`, `TECHNICAL_RULE` and `NEW_CLASS_RULE` stand for the others. A wrong kind, a malformed id, a known rule without its name, an id beside another kind and a plain string in `GateFinding.rule` are refused, each beside a valid twin (`tests/test_gate.py::ARuleAssignmentIsData`). Every site that set the field — in `audit`, `code_check`, `import_check` and `prompt_check` — now passes the value; `blocker`, `Findings.block` and `Findings.warn` take an optional `rule`; the lines told are unchanged. `findings.NEW_CLASS` comes from `gate`. `None` stays allowed and means a site the migration has not visited; `OPEN_RULE` means visited and not decided.

Two departures from the text above. First, the display does not read the title from the ledger: `gate` is core, and the ledger module `rules` is doctrine (`docs/architecture.md`, "Core and doctrine"), so the value carries the name as cited, and the existing source reference check (`rules.check_refs`, `tests/test_rules.py`) holds id and name to the ledger's active rule. Second, the rule values at finalize's other sites are set during the pilot, at each site as it is migrated, not here: 2a's acceptance does not need them, and each site would otherwise be touched twice.

The site account is open: `docs/notes/2026-11-10-site-account.tsv`, 73 rows at `b4fdf56d` (71 `finding`, 2 `exit`, 0 `printed`). Its rows are the sites whose function `finalize_area` reaches through `check_inventory.call_graph` — a static estimate in both directions; the two `exit` sites in `labkit/run/batch.py` are reached only through a shared name and are to be confirmed or removed with their reason. The source review found no refusal the scanner misses in finalize's reach: the `console.Refused` of intent-check (exit 2, no finding by the inventory's definition) is caught by finalize's station and becomes the counted site of `check_intent_keys_in_metrics`. The key columns were generated with a one-off script over `finding_sites`; the reference site's hand columns are filled.

### 3. Migrate by gate, stopping after finalize

At each gate, start with the unreached and command-only sites; then review the remaining conditions and their existing tests. Apply the [test model](#the-model) and the [check contract](#check-contract). Classify every site in the site account and link it to the tests of its condition or of its forwarding. Do not create a function or a duplicate twin test only to improve a site count.

Keep the gate tests for ordering, withdrawal, the rule that one cause yields one blocker, and the choice between the Git index and the working tree. For `exit` and `printed` sites, keep the assertions on the exception, the exit status or the printed warning. A boundary that gains nothing from extraction, such as a usage error, needs a recorded reason for its extraction exception and a test at the boundary. Remove an unreachable branch only with evidence that it cannot occur.

After finalize, stop at the checkpoint below. If the author decides to continue, complete step 2b before report-check, preflight and report holds; then cover the remaining readers and the refusals raised during a measurement outside those gates. The plan includes the 32 sites outside the `finding` channel; they are not implicitly exempt.

### Checkpoint after finalize

Before the migration, record the pilot's start commit, the selected sites and the baseline timings. Track the time for shared infrastructure separately from the time for migration and verification. At the stop, report:

1. The sites accounted for and the distinct conditions tested.
2. Implementation and verification time per condition and per site, plus the cost of shared infrastructure.
3. Changed code and test lines, and the measured change of the fast-tier and slow-tier times. Report no gain or an unmeasured gain as such; savings from scenario tests can only come in step 4.
4. A range for the remaining effort, including the sites not yet classified.
5. A before-and-after example from the pilot: how a further condition and its twin were added, which files and helpers this needed, and whether a reader can follow input → condition → finding → gate caller. Ask the author to judge clarity at this checkpoint; passing tests alone do not show that the design is easier to use.
6. An abstraction balance: the new types, wrappers, fixture options and indirections against the removed duplication and special cases. Name the purpose of each addition and what it replaces. Line counts alone do not decide simplicity. Before proposing a broader migration, remove or simplify each addition whose maintenance cost has no demonstrated benefit.

**Pilot baseline, recorded 2026-11-10.** Start commit `b4fdf56d`. Selected sites: the 73 rows of the [site account](2026-11-10-site-account.tsv). Times at that commit on 11 cores (`pytest -q -p no:warnings -n auto`): fast tier (`-m "not slow"`) 80 s, 2 768 passed; slow tier (`-m slow`) 280 s, 485 passed; both green. Shared infrastructure (steps 1 and 2a) and the migration are told apart by their commits: everything up to `b4fdf56d` is infrastructure, every `finalize pilot` commit after it is migration and verification.

### Pilot progress

Each commit below moved or tested sites and filled their rows in the [site account](2026-11-10-site-account.tsv); the rows hold category, condition, rule value and tests.

| Commit     | Station              | Sites | How                                                                                                                                         |
|------------|----------------------|-------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `e3789158` | 9, audited runs kept | 1     | pure check `audit_binding.check_audited_runs_kept`, rule test (step 1)                                                                      |
| `f7a0234b` | 9, audit records     | 3     | pure checks `check_audit_records_read`, `check_audit_findings_decided`; the station composes, an undecided NOTE stays a told line           |
| `67cdcdbb` | 8, criterion n       | 1     | `criterion_n_input_mismatches` takes the records (`criterion_ns`, `DataEntry`, `OutputEntry`); the station reads them, as decided in step 1 |
| `057deec4` | 8, reference head    | 2     | forwarding of conditions tested where they live; one gate test each and a twin                                                              |
| `a95e4d4d` | 0, protocol and head | 2     | composition of the early end in a passed collector; gate tests and a twin                                                                   |
| `4b093d3b` | 1, run choice        | 2     | the missing protocol id from a state built in memory; the newer-by-name warning keeps its test                                              |

What the first stations show for the remaining ones: where a condition already lives in a pure function with its own tests (`reference.comparison_gaps`, `protocol_check.reference_gap`), the site is forwarding and needs a gate test only; where a check takes a run directory (`run_record_check`: code since the run, provenance, outputs, null lane, row provenance, arms, model provenance), the work is the run-input decision of step 1 — the station reads with the `runs` readers, and the lineage of a run can come from the configs `AreaState.runs` already holds instead of reading each run's `config.json` again. The two `exit` rows in `labkit/run/batch.py` are still to be confirmed as reachable from finalize or removed with their reason.

### Checkpoint report (2026-11-10, at `602f794f`)

**1. Sites and conditions.** The site account holds 73 rows at `b4fdf56d`. Three are not in finalize's reach — the static call graph counts every method of a named class (two `exit` sites in `labkit/run/batch.py`) and finds a caller `evidence.change_blockers` does not have — and are marked removed with that reason. The other 70 are classified:

| How a site is held now                                                          | Sites | Examples                                                                                          |
|---------------------------------------------------------------------------------|-------|---------------------------------------------------------------------------------------------------|
| pure check, rule tests from data under `pure_call` (7 checks)                   | 10    | `check_audited_runs_kept`, `check_audit_findings_decided`, `null_lane_findings`, `source_finding` |
| already pure where it lives, tested from data there                             | 10    | `reference.comparison_gaps`, `kept_number_gaps`, `AnsweringRun.explain`, `declared_run_gaps`      |
| composition, forwarding, reader or technical, tested at the gate                | 30    | step 0, the run choice, open fields, data counts, area tests, run files that do not read          |
| boundary against git and the run's kept files, tested against real repositories | 20    | `code_since_run` (11, an extraction exception), row provenance (4), registration (5)              |

Of the 24 sites in finalize's reach that the baseline inventory found unreached (13) or reached only through whole commands (11), 23 now have a test below a whole command, nearly all of them added in the pilot; the exception is a `data=` entry that does not read (`labkit/checks/run_record_check.py:543` at `b4fdf56d`), still reached only through finalize's command. The inventory itself is run again in step 2b, through the site account. 66 sites record their rule as an open assignment, 4 a known rule (LAB-015 twice, LAB-034, LAB-043): the pilot made the assignment data and decided none.

**2. Time.** Agent wall-clock from the commits, author review not included. Shared infrastructure (steps 1 and 2a, with reading the code): about 30 minutes. Migration and verification of the 70 sites: about 60 minutes in 19 commits, so under a minute per site on average — a site that only needed its rule value and a gate test took one to three minutes, each of the seven extracted checks with its reader and rule tests three to six. The cold reading of the whole pilot found six points; three were real (an output hashed although nothing was recorded to compare with, a rule value set over a whole function, station numbers one behind) and are fixed in `602f794f`.

**3. Lines and test time.** Infrastructure: package +210 −70, tests +596 −10. Pilot: package +450 −176, tests +772 −122. Test time, the start commit and `602f794f` run alternately on the same machine at 18:5x (`-n auto`, 11 cores): fast tier 105 and 102 s against 92 and 91 s; slow tier at `d449701a` 261 s against the 280 s of the baseline run at 17:00. The pilot made the suite no slower; it made it no faster either — the start commit ran from another directory, and the earlier 80 s baseline shows how much the machine's load moves the number. A gain can only come from step 4, which removes scenario tests.

**4. Remaining effort, a range with low confidence.** Step 3 for the other gates: about 156 sites plus the refusals the scanner misses, at the pilot's pace three to five hours, more where report-check's conditions are less pure than finalize's. Step 2b's tooling: one to two hours. Step 4, the review of 293 scenario tests' assertions with a named replacement for each removed one: four to eight hours, the least known part. Step 5: about an hour. In all nine to sixteen hours of agent time, plus the author's review.

**5. A before and after: criterion n.** Before, `criterion_n_input_mismatches(answering_run)` opened metrics.json, config.json and outputs.json itself, and its test wrote three files into a temporary run. After, the station reads with the `runs` readers and calls `criterion_n_input_mismatches(ns, inputs, outputs)` with `criterion_ns(metrics)` and the typed `DataEntry` and `OutputEntry` records; the rule test builds two records in memory (`tests/test_rules_run_record_check.py`). A reader follows input (`metrics`, the records) → condition (`criterion_ns`, `criterion_n_input_mismatches`) → finding (a static-evidence WARNING, rule open) → gate caller (`finalize.check_criterion_n`, `take_all`). Adding a further condition needs one function in the check's module and one test class; no helper beyond `pure_call` and the records. Whether this reads more clearly is the author's judgement.

**6. Abstraction balance.** Added, each with its purpose: `tests/state_fixture.py` (four builders: a state and evidence without files), `tests/check_guards.py` (the `rule` mark and `pure_call`), `gate.RuleAssignment` with `cited_rule` and three constants (the rule as data instead of a string), three run readers with their values (`KeptRows`, `OutputNow`, `SourceNow` — what a check judges, read once by the station), `criterion_ns`, three pure checks in `audit_binding` and the constant `UNDECIDED`. Removed: the file-writing tests of criterion n and the null lane, a directory parameter from four checks, and the duplicate wording of the undecided line. No registry, no wrapper type, no new module in the package. `SourceNow` is the heaviest addition: eight fields, because the decision it feeds has six outcomes in a fixed order. Nothing here was added only for a site count, and nothing is proposed for removal; the author may judge `SourceNow` worth its size.

**Decided by the author on 2026-11-10: continue** — the remaining gates, step 2b first, then step 3 for report-check, preflight and the report holds, step 4 and step 5; no time cap. The other open points below stay open.

Open for the author: the 66 open rule assignments (the [rule proposal](2026-11-09-rule-per-finding-proposal.md)); whether row provenance and registration stay boundaries or are split into facts and decisions like provenance; and the choice below.

**Stop before another gate.** The author chooses to continue, to continue with a narrower scope and a time cap, or to defer. The choice rests on correctness, clarity, added complexity and cost; meeting the coverage and timing targets alone does not justify continuing. A usage round with a partial refactor requires an explicit change to the earlier decision that lists the deferred sites, the risks and the unmet targets. The deferred sites keep their existing checks and tests. No reliable overall estimate or time cap exists before this checkpoint.

### 2b. Complete rule data and measurement

Extend the audit records (`findings.Finding.rule`) and the constructors that cannot yet receive a rule to the shared rule value. Check the obligations of the public API and of the on-disk format before changing accepted values; follow the repository's transition and Breaking policies. Inventory rule counts read the data field, not the message text. Extend the forwarding tests as the forwarding guard in [Architecture guards](#architecture-guards) specifies.

Complete the site account and repair the scanner's known omission. `check_inventory._refusal_message` skips a `SystemExit` whose argument is a call, so it does not see the `runlog` messages wrapped in `with_way_out`. After the repair, a known wrapped refusal and a direct refusal both appear, and forwarding a command's exit code does not become a finding. Review the scanner's other limits and add each site found that way explicitly to the site count.

Compare the baseline inventory with the current one through the site account. The comparison key is the channel, the qualified function and the normalized message template; line numbers only locate the source. Explain moves, rewordings, renames, splits, merges, removals and additions in the site account. Resolve duplicate keys there by hand, never by line order. The comparison lists the differences the site account does not explain and ignores lines that only moved because others were inserted; do not build a second automatic matcher. Enter each remaining site before migrating its gate.

**Built 2026-11-10 (`95639c56`…`6e5783c0`).** The audit records' `findings.Finding.rule` is the gate's `RuleAssignment`; the record stores the same text as before (`recorded_rule`, `stored_rule`), so the on-disk format did not change. The scanner sees a refusal wrapped in `with_way_out`: 30 refusals of `runlog` and the run start check were missing, and the 226 inventoried sites are 256 (194 `finding`, 56 `exit`, 6 `printed`); no other missed form was found. Both inventories count rules by the data field (`FindingSite.assignment`) and keep the cited ids beside it. The forwarding guard is `tests/test_architecture.py::ForwardingKeepsWhatAFindingIs`. The site account holds all 256 sites at `6e5783c0`: finalize's 73 rows kept their hand columns, the five sites the pilot moved name their old place in the condition, and the rows of two `batch` refusals and `evidence.change_blockers` are no longer marked removed — they are live sites of other gates. `python -m labkit.tools.check_inventory --account docs/notes/2026-11-10-site-account.tsv` compares by key and count and reports no difference; ten keys are shared by two sites each, told apart by hand.

### Step 3 for the other gates, as built (2026-11-10)

Every one of the 256 sites of the [site account](2026-11-10-site-account.tsv) is classified: 98 scientific, 28 technical, 31 composition, 2 forwarding, 8 reader, 23 boundary, 56 refusals and printed lines, and 10 sites of `report_decisions.py` that wait for the decision on the second review. Every gate finding site records its rule as data (`253b82a`; 179 open assignments, 15 known rules). The sites the inventory of `6e5783c0` found unreached or reached only through whole commands got tests below the command: report-check, the report holds, the replacement gate, the registered report, preflight, code-check, notes-check, the protocol history, the audit's tier warning and a `data=` entry (`tests/test_*_stations.py`, `tests/test_check_stations.py`); `state_fixture.checked` builds report-check's context for its gate tests. The exit sites are named by the tests that reach them, traced through `with_way_out` in one run of the suite, or by the tests whose source holds their wording; recheck's and the run start's untested refusals got tests (`tests/test_recheck_refusals.py`, `tests/test_run_start_refusals.py`).

Outside finalize no further check was extracted: their conditions are tested at the check layer already (59 sites) or are composition and boundaries of their gates; the pilot's extractions show the pattern where a condition read files itself.

Open from step 3, for the author — points 1 and 2 closed on 2026-11-10:

1. ~~`report_check.analysis_audit_gap` did not catch a refused access~~ — fixed in `b8968d4e`: a `PermissionError` is the station's blocker, told as a check not executable, with the way out to make the file readable (CHANGELOG, Fixed); the gate test covers missing, malformed and refused.
2. ~~Seven sites no test named~~ — closed: six got a targeted test or name the test that asserts their sentence (`runlog.py:315`, `detached.py:292`, `recheck.py:164`, `protocol_report.py:745` and `:838`, `protocol_fill.py:763`); `usability.py:565` is an extraction exception — the probe's progress line during `usability stage`, which builds a venv, its condition `labkit_spec_problem` tested in `tests/test_usability.py`. Every site of the account names a test or a reason; three sites of `report_decisions.py` reach no test and wait with the others of that module (point 3).
3. The ten sites of `report_decisions.py` wait for the six decisions on the second review.

### 4. Reduce scenario variants

First extend the inventory with a report per scenario test: its pytest node id, the sites it reaches, and for each site the lower-layer tests that also reach it. The current renderer lacks this list across tests. Verify the report with one scenario test whose sites all have lower-layer tests and one that reaches a command-only site. A scenario test with no traced sites, with sites in untraced channels or with missing subprocess events counts as **unknown**, not as redundant.

Then review the assertions of every scenario test in the report. Name the replacement test for each assertion before removing it. Keep the tests of state that one command passes to the next, of stored state that the next command reads, and of repairs across gates. Reach alone never establishes a replacement. Scenario tests that stay keep the `slow` mark.

**The report, built 2026-11-10 (`03b53d3b`).** `test_inventory` lists each scenario test with the gate finding sites it reaches and those no faster test reaches below a whole command (`scenario_tests`). On the trace of `6e5783c0`: of the 485 scenario tests, 293 reached a traced site — 132 `covered` (a faster test reaches each of their sites), 161 `holds a site` — and 192 reached none and are `unknown`. Verified on two cases: `tests/test_adopt.py::Adopt::test_a_refused_adoption_leaves_no_kept_copy` is covered (its two sites have faster tests); `tests/test_handovers.py::HandoverRecovery::test_a_bad_record_name_does_not_hide_its_readable_blocker` held `labkit/gates/report_check.py:438`, reached otherwise only through whole commands — since step 3 a gate test reaches it too. Reach is no assertion: `covered` says where to review, never what to remove.

**Where the slow tier's time lies (2026-11-10, `20e99f59`).** 485 scenario tests, 2 487 test-seconds, 273 s on 11 cores. Four files hold 1 690 s of it, two thirds: `tests/test_repair_paths.py` 618 s (46 tests), `tests/test_end_to_end.py` 565 s (63), `tests/test_handovers.py` 308 s (36), `tests/test_next_step.py` 200 s (28); then `tests/test_counter_cases.py` 137 s and `tests/test_registration_committed.py` 113 s. The 120 s target asks for about half of the test-seconds to go. The assertion review starts with these files, `covered` tests first; a test that keeps state one command passes to the next stays whatever its reach.

**The review of the four files (2026-11-10, at `68bea87f`).** One row per test in the [scenario review](2026-11-10-scenario-review.tsv): its standing on the trace of `68bea87f`, its seconds, the verdict, and the replacement or the reason it stays. Of the 163 tests the four files collect, 144 stay, 12 move to the fast tier and 7 go:

- **Removed, each with its replacement:** four tests of `RepairPaths` that `RegisteredReportRepairs` inherited and ran a second time — its exclusion list named tests renamed since; the helpers now live in a base without tests (`StagedLab`), so no test is inherited. The same-second refusal (`tests/test_answering_run.py`, `tests/test_answering_run_exhaustive.py`), the missing check script (`tests/test_report_check.py`, station 4) and a count typed over the written counts (`tests/test_data_counts.py`, `tests/test_finalize_steps.py::DataCountsStation`).
- **Moved, unchanged:** eight `labkit-next` tests that build no lab (`tests/test_next_step_before_the_chain.py`) and four handover tests (`tests/test_handover_scope.py`). They now run in the commit's fast tier.
- **Kept:** every other test asserts state one command passes to the next, stored records the next command reads, or a repair across gates. Of the 60 `covered` tests, three had faster tests for their assertions (the last three removed above); for the others the faster tests reach the same sites with other inputs, never the sequence.

Timing, four workers on an otherwise idle machine: the four files take 786 test-seconds; the removed and moved tests took 19 of them (2 %). Where the rest lies: `RegisteredReportRepairs` 262 s (subprocesses through the real hooks), `HandoverRecovery` 141 s, the two correction classes of `tests/test_end_to_end.py` 113 s. The 2 487 test-seconds above came from the full suite on eleven workers, where every test starts further processes (the measuring script, git, the area's tests inside finalize) and the load reached about 54 on 11 cores; the two measurements are not comparable test-second for test-second.

The finding that decides what follows: the review keeps the assertions, so it cannot reach the 120 s target. Ten tests of `CorrectedDescription` and nine of `CorrectionThenNewRun` are the only tests of `labkit/gates/registration_hold.py:358` and `:304` (the site account files both as a boundary that reads the protocol texts each run saw); their variants (another field, a place given as a line number, a text edited after the verdict) are conditions of `resolved_corrections`, `released_fields` and `awaiting_followup` that no rule test holds. Fewer of them needs those conditions extracted and tested on data first — step 3 for this gate — and is the one lever in these files with a measurable share (113 of 786 s).

**The correction conditions as rule tests (2026-11-10, `77f2e89e`, `7693b910`).** Decided by the author: extract the conditions first, then remove only variants whose assertions are fully replaced. What a follow-up's `resolved` releases (`followup.released_corrections`), which correction a follow-up would judge (`followup.awaited_corrections`), which field stays held (`registration_hold.split_released`, `waiting_refs`) and the way each scope hold names first (`seen_hold`, `now_hold`) are computed from typed data; `scope_changes` still reads the records, the texts and git. `tests/test_rules_registration_hold.py` holds each condition with its release and its refusals; four mutants each turn the test meant for them red, rerun 2026-11-11 — the decision digest ignored: `AResolvedCorrectionReleasesItsField::test_the_refusals_release_nothing` [the verdict bound to an earlier decision]; a moved field ignored: `TheRefsAHoldLeadsWith::test_a_ref_per_difference_none_for_a_field_without_or_moved`; the measuring code ignored: `TheHoldAsTheProtocolStands::test_a_code_change_beside_it_measures_again_first`; the covering record ignored: `AFollowUpJudgesTheDecidedCorrection::test_the_twins_are_awaited_not` [its record covers the state now] — and the variants passed unchanged against the refactor before any was removed. Then 20 of the 25 variants went, each row of the [scenario review](2026-11-10-scenario-review.tsv) naming the replacement of every assertion; three assertions no faster test held got one first — a reflowed field is no change, an unresolved correction of another grade is not carried, the question's decision line offers no route. Five stay: the correction released, the new run released, the verdict on A held at the text B saw (the one route through finalize to `seen_hold`), an adopted run withdrawn and replaced, and a finding decided `fixed` in the state audited (another gate).

**The other nine scenario files (2026-11-10, `806842b0`, `f52d8c73`).** 322 tests: 254 kept, 54 moved, 14 removed. Removed: 14 of the 19 cases `CodexStop` inherited from `test_agent_hooks.Stop` and ran through Codex JSON — `codex-hook stop` hands `agent_hooks.stop` the same event with `project_dir` and `hook_command` added, which a new test asserts (`CodexStopPassesTheSharedStop`), together with the project being the event's cwd and never an inherited `CLAUDE_PROJECT_DIR`, which no test held before; the five cases that use what the Codex entry adds stay, as an explicit list. Moved unchanged to the fast tier: report-check on areas without a repository (`tests/test_report_check_areas.py`), a report's blocks as text (`tests/test_report_blocks_text.py`), the decision line's branch (`tests/test_repair_hint.py`). Kept: the hooks' own logic in a repository, the registration held through git history, the adoption's steps, the whole counter cases. One reduction was declined: seven tests of `HighReportRegisteredBeforeTheFirstMeasurement` call only `report_binding_gap`, which reads no lane, but no test holds that it does not, so they stay. In the table, the seconds of the first 163 rows come from four workers on an idle machine, those of the nine files from the full slow tier at `c79b139e`.

**Before and after, measured alternately (2026-11-10).** Three states, each tier twice, the order reversed in the second round, from git worktrees of the same venv (`PYTHONPATH` set to the worktree, so tests and their subprocesses load its labkit), the machine kept awake (`caffeinate -i`), load 25–45 at every start:

| state                             | fast tier wall | slow tier wall  | slow tier test-seconds | tests fast / slow |
|-----------------------------------|----------------|-----------------|------------------------|-------------------|
| before the extraction, `c79b139e` | 93.4 / 91.8 s  | 251.1 / 251.7 s | 2 363 / 2 346          | 2 874 / 466       |
| after the 20 variants, `7693b910` | 91.9 / 98.4 s  | 243.3 / 246.8 s | 2 167 / 2 204          | 2 900 / 446       |
| after the nine files, `f52d8c73`  | 90.5 / 94.9 s  | 217.9 / 221.3 s | 2 204 / 2 238          | 2 954 / 380       |

The slow tier lost 12 % of its wall time (251 → 220 s) and 6–7 % of its test-seconds. The wall time does not follow the removed test-seconds, and why is not known: in the same runs the 20 variants took 184–189 test-seconds at `c79b139e` and their removal cut 6 s of wall time, while the nine files' changes took 50 test-seconds out and cut 25 s. A guess, not checked: the order in which the workers take the longest tests changed (the longest, `RegisteredReportRepairs::test_a_correction_then_a_code_repair_is_measured_judged_and_reported`, runs 51–68 s at every state); two runs per state may also not separate 6 s from 25 s. So no share of the gain is attributed to either change; the fast tier, now 80 tests larger, is unchanged within the spread of its runs (about 92 s). Two earlier measurements were set aside: one sequential pair, between whose halves the machine's state changed (both tiers slower after, with fewer tests), and an alternating pair with a run of 2 196 s wall for 140 s of tests, the machine asleep between. The targets are missed: the fast tier stands at about 92 s against 90 s, the slow tier at about 220 s against 120 s; by the author's decision no further assertion is given up for them. Step 4 is complete.

### 5. Measure and review

Compare the inventories through the site account and resolve unexplained changes before claiming gains. Under comparable conditions, record the times of the full suite, the fast tier and the slow tier, the worker count, and the added and removed sites. Evaluate the [targets](#targets); keep the open rule assignments and the extraction exceptions visible. Close the temporary site account as [Site account](#site-account) specifies. The usage round stays a separate research task with its own prerequisites.

**Step 5, done 2026-11-11.** The final comparison, its targets and the site account closed.

- **The inventories agree.** `check_inventory --account` explains every site once the two hold sites that moved into `seen_hold` and `now_hold` are recorded. Read by today's scanner, the baseline `524b93ce` and the end of step 4 both hold 256 sites: none added, none removed, eight moved into pure checks (four of finalize's station 9, two of `run_record_check`, the two holds). The baseline's 226 counted with the scanner of its day, which missed 30 refusals (step 2b).
- **Reach (`test_inventory` at `b5235238`).** Reached by no test: 5 sites (30 at the baseline); only through whole commands: 1 (19). Two of the five were real gaps the account had misnamed — the softer lines of a note (`notes_check.check_notes`, the named test reached only the unreadable branch) and the arm lines forwarded by finalize's station 1 — and got gate tests with twins, each turned red by removing its forwarding (`tests/test_check_stations.py::TheSofterLinesOfANoteWarn`, `tests/test_finalize_steps.py::Steps::test_station_1_forwards_the_arms_lines_as_guaranteed_warnings`). The other three are sites of `report_decisions.py` that wait for the second-review decision. The one command-only site stands in `code_check.main` itself, so every test that reaches it enters through the command.
- **Timing, measured alternately** (the baseline and `b5235238` from worktrees, as in step 4; 11 cores, `-n auto`, load 3–22 at every start, two rounds, the order reversed in the second):

| tier       | baseline `524b93ce`           | `b5235238`                    |
|------------|-------------------------------|-------------------------------|
| full suite | 521.6 / 481.2 s (3 234 tests) | 447.8 / 414.3 s (3 334 tests) |
| fast tier  | 102.0 / 95.6 s                | 99.9 / 104.9 s                |
| slow tier  | 258.7 / 290.0 s               | 243.8 / 241.3 s               |

The full suite runs 13–14 % faster with 100 tests more; the fast tier, 134 tests larger, is unchanged within the spread of its runs; the slow tier is 6–17 % faster, its second baseline run an outlier the load does not explain. The machine runs slower than yesterday (the slow tier measured 220 s then), so only comparisons within one measurement hold.

The targets:

1. **Complete site account — met but for the ten sites that wait.** All 256 sites map to rule tests, gate tests or a stated reason; the ten sites of `report_decisions.py` wait for the six decisions on the second review (TODO 6b), three of them reached by no test.
2. **Rule tests per condition — met but for the same ten.** Unreached 30 → 3, command-only 19 → 1 (above). Reach is measured; that each condition's twin passes is asserted by the tests the account names, not measured.
3. **Explicit rule data — met.** Every gate finding site records its rule as `RuleAssignment`; 14 name a known rule, one passes on the rule it is given, 179 stay open assignments, distinct from the technical contract and from the audit's new class. Recording an assignment approved none of them.
4. **Preserved integration guarantees — met, closed by the author on 2026-11-11 after the independent review.** Every removed scenario assertion names its replacement (the [scenario review](2026-11-10-scenario-review.tsv)); the architecture guards pass their allowed and forbidden examples. The [independent review](2026-11-11-test-model-review.md) reproduced one insufficient replacement: a field edited after the answering run is tested only with a supplied set of changed fields, so an error in the caller's comparison remains undetected. Restored in `29290169`: `TheReleaseReadsWhichFieldTheRunSawOtherwise` passes two protocol texts through `released_fields` and fails when the comparison is suppressed. The second call of the comparison (the way out a hold names first) is tested since `cd615bb5`. With the answer of 17 functions replaced for the package's callers (16 of the 17 pure checks and the comparison `moved_fields`), one suite run each, 15 were caught by a test; the two that were not — this comparison and finalize's null-lane station — have gate tests now. The measurement replaces answers, not inputs: a caller that computes a wrong input is seen only where the computing function was replaced.
5. **Timing — missed.** The fast tier stands at about 100 s against 90 s, the slow tier at about 240 s against 120 s. By the author's decision no assertion goes for them.

**The site account, closed.** Frozen as evidence of the final comparison in the commit that carries this paragraph (its rows' source commits name where each site stood); later refactors need not maintain it. What it held that needs a home has one: the rule value in code (`GateFinding.rule`), each extraction exception's reason at its code (the docstring of `run_record_check.code_since_run`, a comment at `usability.stage`'s progress line), the sites that wait in TODO 6b, the open assignments in the [rule proposal](2026-11-09-rule-per-finding-proposal.md). The comparison itself, `check_inventory --account`, went with the account's closing (decided by the author, 2026-11-11): nothing maintains the account, so every later refactor would have shown as a difference nobody is to resolve. It stands last in `00aaeaad`, where the final comparison can be repeated.

## Contracts used throughout

> What holds today stands in [the architecture](../architecture.md#checks-and-their-tests), "Checks and their tests": the check contract, the rule assignment, the test layers and the guards. The sections below are the contracts as the plan agreed them, kept as its record; where the two differ, the architecture holds.

### The model

A site is a unit of accounting; a condition is a unit of testing ([Terms](#terms-used-in-this-note)). Several conditions can belong to one rule of the standard, and several sites can share one condition and its twin tests. Classify each site as a scientific condition, a technical contract condition, or composition and forwarding. At each caller, test only what the caller adds.

| Layer    | What its tests establish                                                                                                                  | Setup                                                                                               |
|----------|-------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| reader   | Conversion between file and object, causes of a failed read, round-trip with the writer                                                   | A temporary file; no gate, Git or command                                                           |
| rule     | One distinct condition: asserted grade, rule assignment and cause; the valid twin passes; `NOT_EXECUTABLE` distinguished where it applies | Typed data in memory; no repository or command                                                      |
| gate     | Composition, ordering, withdrawal and the choice of file state                                                                            | State in memory; a repository only to test the Git index against the working tree; no whole command |
| scenario | State that one command passes to the next, and repairs across gates                                                                       | Lab repository and real commands; marked `slow`                                                     |

The tests of the repository's architecture and of its ledgers stay a separate group. The inventory measures reach; only a review of the assertions establishes that a condition is tested. A site that only composes or forwards belongs at the gate or boundary layer and needs no invented scientific twin.

### Check contract

This contract applies to pure validation, not to every existing function. Operations whose purpose is to read, write, execute or act on the environment stay named readers, writers or execution boundaries; their tests cover their real side effects and failures. Extract only the conditions of such an operation that are useful on their own; do not force the whole operation into a pure-check wrapper.

Put each check in the existing subject module under `labkit/checks/`. The reference signature for an area check is `check_<condition>(state: AreaState, *, evidence: AreaEvidence) -> list[GateFinding]`; prefer smaller, explicitly typed inputs where they suffice. Run checks receive the records decided in step 1, never a directory to read. A check receives no mutable collector and no gate-layer `Checked` value.

A check returns `[]` on valid input. Otherwise it returns findings with grade, rule assignment, cause, `evidence_kind`, `check_outcome` and the required way out. A check does not access files or the repository, start processes, print, write, raise `SystemExit` or change its input. Invalid data from the caller raises a named validation error instead of passing silently.

The gate decides whether and when to call the check and forwards the result through the existing `Findings.take_all`. Readers supply contents or typed read failures; execution boundaries keep their existing behavior of raising or printing. No new check registry and no universal wrapper.

### Rule assignment

Today `GateFinding.rule` holds `LAB-nnn Name`, while the audit's `findings.Finding.rule` holds `LAB-nnn` or `new class`. Replace both with one small validated value that carries a tag, checked by one validator:

| Case               | Meaning                                                          |
|--------------------|------------------------------------------------------------------|
| Known rule         | Carries the rule id; the display reads the title from the ledger |
| Open assignment    | The rule is not decided yet; no invented rule id                 |
| Technical contract | A technical condition that no rule of the standard covers        |
| Audit `new class`  | The auditor found a fault that no existing rule names            |

Define the English tags once. Reject invalid ids and contradictory combinations of tag and payload, each with a valid twin. No fallback to an arbitrary string, no parallel rule field and no new registry. The rule data survive forwarding and display. Recording an open assignment never approves it.

### Site account

The site account is a temporary instrument of the migration. It is not a permanent registry and has no authority over source or tests. At completion, freeze it as dated evidence tied to the commit of the final comparison; later refactors need not maintain it. Step 5 reviews which of its information needs a permanent home in code, tests or documentation. A lasting site account would need a demonstrated need and a separate decision.

Create one TSV beside this note with one row per site. The columns are: source commit, channel, qualified function, normalized message template, source `file:line`, category, the condition or forwarding behind the site, rule value, and named tests.

Generate the key columns (channel, qualified function, normalized message template, `file:line`) from `check_inventory.finding_sites`, whose fields `FindingSite.channel`, `unit`, `wording`, `path` and `line` are the same ones the comparison in step 2b reads. Fill only category, condition, rule value and tests by hand. Add a row by hand only for a refusal the scanner misses, and mark it as such. Record removals, merges and extraction exceptions with their reasons. A row keeps a site's identity when the site moves; its source line is only the location at one commit. The site account is the only mapping from old to new sites and the only record of each site's implementation.

### Architecture guards

Extend the existing tests alongside the migrations. `tests/test_architecture.py::NoFileAccessInGates` already scans for direct file, Git and subprocess access, with named exceptions. Add only the missing guards:

| Guard            | When                  | What it enforces                                                                                                                                            |
|------------------|-----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Rule-test guard  | Step 1                | Rule tests are marked explicitly in pytest; a shared fixture rejects starting a process, entering a command and building a repository, also through helpers |
| Pure-check guard | First extracted check | The check runs under guards that reject file access, repository access and starting a process, also through helpers; pure checks get no guard exceptions    |
| Forwarding guard | Step 2b               | Existing forwarding keeps rule assignment, `evidence_kind` and `check_outcome`, except for explicit transformations                                         |

Give each guard a forbidden example that it rejects and an allowed example that passes. Later migrations reuse the guards. Reader tests and the gate tests of file state keep the file access they need. The guards enforce the technical boundaries that the tests exercise; they do not establish scientific adequacy, nor purity for every possible execution.

## Decisions and dependencies

The test model, the rule field, the explicit open assignment and the removal of scenario tests only with preserved assertions are agreed. The migration keeps the current meaning of each check; a scientific change requires the author's decision. Release and rollout stay separate work.

Steps 1, 2a and the finalize pilot do not wait for the six decisions of the second review. The dependent checks in `report_decisions.py` wait for the decision on LAB-015 Preflight audit before freezing, and so does the [report-claim contract](2026-11-10-report-claim-decisions.md). Task 6b's adoption acceptance for two protocols stays due before the usage round; its status stays in [TODO task 6b](../../TODO.md#6b-die-einzelprüfung-der-blocker-umsetzen--entschieden-2026-11-10). The individual assignments in the [rule proposal](2026-11-09-rule-per-finding-proposal.md) stay open until decided.

## Targets

1. **Complete site account:** all 226 inventoried sites (194 `finding`, 26 `exit`, 6 `printed`) and the missed refusals found later map to rule tests, gate tests or justified extraction exceptions. Each removal has evidence; extraction exceptions stay counted separately.
2. **Rule tests per condition:** close the 30 unreached and the 19 command-only sites. Each distinct condition has an asserted finding and a valid twin; sites that share a condition share its tests. Reach through a gate is an intermediate measure, not acceptance. For the untraced channels `exit` and `printed`, name the tests that assert each site instead of inferring reach.
3. **Explicit rule data:** migrated sites use the shared value; the site account keeps the rule assignments of extraction exceptions. Open assignments stay distinct from technical contracts and from the audit's `new class`.
4. **Preserved integration guarantees:** every removed scenario assertion has a named replacement. The architecture guards pass their allowed and forbidden examples; a review checks scientific adequacy.
5. **Timing, subordinate to the targets above:** fast tier under 90 s, slow tier under 120 s. The fast tier's baseline is already 81 s. The full suite takes roughly 302 s longer than the fast tier, but that difference is not a measured slow-tier baseline; measure the slow tier separately. Report missed timing goals rather than removing a test that alone guarantees something to meet them.

## Updating the plan

After each implementation commit, record here the completed step or gate, the acceptance tests and the commit. Update the site account's rows while the migration is active. TODO 6c keeps only status, next action and dependencies. Keep the dated baseline below and add the final measurements beside it instead of replacing it.

## How it was measured

`python -m labkit.tools.test_inventory` runs the suite once and traces every gate finding a test builds. For each finding it records which site (`check_inventory.finding_sites`) built it and through which layer the test entered labkit. The layer is `command` when the test ran a whole console command, meaning a console script's `main` or `cli`, in or out of process. Otherwise the layer is the package folder of the outermost labkit function the test called: `gate`, `check`, `format`, and so on.

The limits:

- **Reaching a site is not asserting it.** A test may build a finding and assert something else.
- **Only gate findings are traced**: 194 of the 226 sites. The other 26 `exit` and 6 `printed` sites are explicit work in steps 2b and 3, not an exemption.
- **The scanner is incomplete too.** A review on 2026-11-10 reproduced the counts of all three channels with `finding_sites(read_modules(PACKAGE_DIR))`. `check_inventory._refusal_message` ignores a call used as the argument of `SystemExit`. The wrapped messages in `runlog._repeat_parent` and `runlog._require_no_open_twin` are therefore missing from the 226. The revised baseline must count them before the plan claims full coverage.
- **2 078 traced findings come from no site.** A gate builds them when it passes a finding on with a prefix (`replace(f, text=FINALIZE + f.text)`, `labkit/gates/report_check.py:679`, `labkit/gates/finalize.py:211`). The original finding is already counted at its own site.
- **"Unreached" is a claim.** Three of the 30 unreached sites were checked by hand. Each is an error branch of a function whose ordinary path is tested: `labkit/checks/run_record_check.py:125`, `labkit/gates/report_decisions.py:269`, `labkit/gates/report_replacement.py:61`.

## What it shows (run of 2026-11-10, suite green)

| How tests reach a gate-finding site     | sites |
|-----------------------------------------|-------|
| reached by a test below a whole command | 145   |
| reached only through whole commands     | 19    |
| reached by no test                      | 30    |

| Narrowest layer through which a test reaches the site | sites |
|-------------------------------------------------------|-------|
| format (a reader or writer)                           | 9     |
| check (a check function)                              | 45    |
| tool (a module under `labkit/tools/`)                 | 1     |
| gate (a station or entry point of a gate)             | 90    |
| command (a whole console command)                     | 19    |

- **The largest group of sites is reached no closer than through a gate.** For 90 of the 194 sites, the narrowest test enters at a gate; only 45 are reached through a check function directly. A test through a gate builds an area on disk and reads its state, so it needs a repository; a test of the rule alone would not.
- **552 tests reach a finding site; 293 of them are in the 13 scenario files.** The other ~2 700 tests check formats, writers, text and the repository's own rules.
- **Reach is concentrated.** One provenance warning (`labkit/gates/finalize.py:563`) is reached by 172 tests, 123 of them through whole commands. It fires in nearly every scenario test without being the subject of most of them.
- **Most sites name no rule.** 168 of the 194 sites name no rule in their message, so the per-rule table of `test_inventory` mostly reads `(no rule)`. The assignment of a rule to each site exists only as prose (`docs/notes/2026-11-09-rule-per-finding-proposal.md`).
