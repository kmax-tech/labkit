# Simplify checks and tests — implementation plan (2026-11-10)

> Decided by the author on 2026-11-10: restructure the checks and tests before the next usage round. This note owns the implementation plan; [TODO task 6c](../../TODO.md#6c-ein-klares-testmodell-und-der-umbau-der-checks--vor-der-nutzungsrunde-entschieden-2026-11-10) owns its place in the work order.

## Start here

**Goal:** each scientific or technical condition has one implementation and direct tests; gates compose checks, and scenarios verify hand-overs between real commands. Preserve those assurances first; reduce test time second.

**Status:** the inventory exists; implementation has not started. **Next:** step 1 — build minimal test inputs and migrate one check as the reference. This includes deciding how the answering run's files reach a check as data.

**Execution order:** 1 → 2a → finalize pilot → stop for the author's decision → 2b → remaining gates → 4 → 5. The pilot has no time cap (author decision, 2026-11-10). Do not build the full measurement tooling before it.

## The plan

Extracting a check and testing its condition belong in the same commit. Repeat step 3 in small commits by gate. Use touched tests while working and the repository's required commit checks; run the full suite when measurement requires it.

| Step       | Deliverable                                                            | Acceptance                                                                                                                        |
|------------|------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| 1          | Minimal state builder, run-input decision and first migrated check     | Violation and valid twin run from data; inconsistent test inputs remain unchanged; reference and boundary guards are recorded     |
| 2a         | Shared rule value in `GateFinding` and finalize site account           | Invalid rule values are refused; every `GateFinding.rule` uses the value; finalize's sites are listed at the pilot's start commit |
| 3, pilot   | Migrate finalize                                                       | Its conditions, composition and boundary exceptions meet the contracts below; stop at the checkpoint                              |
| Checkpoint | Pilot cost, clarity, abstraction balance and remaining-effort estimate | Author chooses continuation, a narrower scope/time cap, or deferral                                                               |
| 2b         | Rule data throughout, inventory coverage and comparison                | Remaining sites and recovered refusals are accounted for; changes are explained through the site account                          |
| 3, rest    | Migrate remaining gates and run-time checks                            | Every site maps to condition/composition tests or a justified exception                                                           |
| 4          | Candidate report and fewer scenario variants                           | Every removed assertion has a named replacement; unique hand-overs remain covered                                                 |
| 5          | Final inventory, review and timing                                     | Report all targets, open assignments, exceptions and timing results                                                               |

### 1. Establish the reference check

Build `tests/state_fixture.py` using existing `AreaState` and `AreaEvidence` types. Keep relevant inputs explicit and minimal. No hidden scientific defaults, synchronization of derived fields, automatic repair or normalization of inconsistent states. Defaults may shorten irrelevant boilerplate only when documented and independent of the tested condition. Add gate-layer `Checked` only when report-check's gate tests need it; checks never receive it.

**Resolve the missing run inputs before migrating their checks.** About half of finalize's stations take a run directory and read data absent from `AreaState`: code/scope hashes, outputs, metrics, recorded inputs and Git tracking. This affects `check_run_code`, `check_declared_scopes`, `check_provenance`, `check_null_lane`, `check_registered_outputs` and `check_criterion_n`; their checks in `labkit/checks/run_record_check.py` currently take a directory too. Reuse the records returned by `labkit/formats/runs.py` where possible. Decide which typed value carries the remaining inputs and read failures, and which reader builds it. A new type must describe a run, not duplicate the area model. `gate.outcome_of_failed_read` remains the outcome classifier. `check_area_tests` remains an execution boundary through `preflight.area_tests`.

Migrate one condition with its violation and valid twin under the [check contract](#check-contract). Record its actual signature, location, gate caller and run-input decision here as the template for later migrations. Demonstrate that the builder preserves a deliberately inconsistent input. Introduce the rule-test and pure-check guards with this example.

### 2a. Prepare only what finalize needs

Define and validate the [shared rule value](#rule-assignment) and switch `GateFinding.rule` to it at once, at every site that sets it — about 15 `rule=` uses in 7 modules on 2026-11-10, none in finalize — so the field never accepts the old string and the new value side by side. Then populate it at finalize's sites. The first migrated test asserts the normalized value.

Open the [site account](#site-account) for finalize at the pilot's start commit, covering all three channels. Check the source for refusals the scanner misses. The audit records' `findings.Finding.rule`, constructors that cannot yet receive a rule, and inventory tooling wait for 2b.

### 3. Migrate by gate, stopping after finalize

At each gate, start with unreached and command-only sites; then review the remaining conditions and existing tests. Apply the [test model](#the-model) and [check contract](#check-contract). Classify every site and link it to the tests of its condition or forwarding behavior in the account. Do not create a function or duplicate a twin test merely to improve a site count.

Keep gate tests for ordering, withdrawal, one cause/one blocker and index-versus-tree selection. For `exit` and `printed` sites, retain assertions for the outward exception/status or warning. A boundary that gains nothing from extraction, such as a usage error, needs an explicit exception reason and its boundary test. Remove an unreachable branch only with evidence that it cannot occur.

After finalize, follow the checkpoint below. If continued, complete 2b before report-check, preflight and report holds; then cover the remaining readers and run-time refusals outside those gates. The 32 non-gate sites are included, not implicitly exempt.

### Checkpoint after finalize

Record the pilot's start commit, selected sites and baseline timings before migration; track infrastructure time separately from migration and verification. At the stop, report:

1. Sites accounted for and distinct conditions tested.
2. Implementation and verification time per condition/site, plus shared infrastructure cost.
3. Code/test line changes and measured fast/slow timing changes. Report no gain or unmeasured gain honestly; scenario savings may come only in step 4.
4. A remaining-effort range, including still-unclassified sites.
5. A before/after example from the pilot: how a further condition and its twin were added, which files and helpers were needed, and whether the reader can follow input → condition → finding → gate caller. Ask the author to judge clarity at this checkpoint; passing tests alone do not establish that the design is easier to use.
6. An abstraction balance: new types, wrappers, fixture options and indirections versus removed duplication and special cases. Name the purpose of each addition and what it replaces. Line counts alone do not decide simplicity; remove or simplify additions whose maintenance cost has no demonstrated benefit before proposing broader migration.

**Stop before another gate.** The author chooses continuation, a narrower scope with a time cap, or deferral based on correctness, clarity, added complexity and cost. Meeting coverage and timing targets alone is insufficient to continue. A usage round with a partial refactor requires an explicit change to the earlier decision, listing deferred sites, risks and unmet targets. Keep their existing checks and tests. No reliable overall estimate or time cap exists before this checkpoint.

### 2b. Complete rule data and measurement

Extend the audit records (`findings.Finding.rule`) and the constructors that cannot yet receive a rule to the shared rule value. Check public API and on-disk format obligations before changing accepted values; follow the repository's transition and Breaking policies. Inventory rule counts read the data field, not message text. Extend forwarding tests as specified below.

Complete the site account and repair the scanner's known omission: `check_inventory._refusal_message` excludes a `SystemExit` argument that is a call, hiding `runlog` messages wrapped in `with_way_out`. A known wrapped refusal and a direct refusal must both appear; command exit-code forwarding must not become a finding. Review other scanner boundaries and add discovered sites explicitly to the denominator.

Compare baseline and current inventories through the account. Channel, qualified function and normalized message template form the comparison key; line numbers only locate source. Explain moves, rewordings, renames, splits, merges, removals and additions in the account. Resolve duplicate keys there by hand, never by line order. The comparison must list unexplained differences and ignore mere line insertion; do not build a second automatic matcher. Enter each remaining site before migrating its gate.

### 4. Reduce scenario variants

First extend the inventory with a per-scenario candidate report: test node id, reached sites and lower-layer test ids witnessing each site. The current renderer lacks this cross-test list. Verify it with one candidate whose sites all have lower-layer witnesses and one with a command-only site. No traced sites, untraced channels or missing subprocess events mean **unknown**, not redundant.

Then review every candidate's assertions. Name the replacement test for each assertion before removing it. Preserve command hand-overs, stored state read by the next command and repairs across gates. Reach alone never establishes replacement. Retained scenarios keep the `slow` mark.

### 5. Measure and review

Compare inventories through the account and resolve unexplained changes before claiming gains. Under comparable conditions, record full-suite, fast-tier and slow-tier times, worker count, and added/removed sites. Evaluate the [targets](#targets), keeping open assignments and extraction exceptions visible, and close the temporary site account as specified below. The usage round remains a separate research task subject to its prerequisites.

## Contracts used throughout

### The model

A finding site is where a result is built or told; it is an accounting unit. A condition is what the check decides; it is a testing unit. Several conditions can belong to one standard rule, and several sites can share one condition and its twin tests. Classify sites as scientific conditions, technical contract conditions, or composition/forwarding. Test only additional context at each caller.

| Layer    | What it establishes                                                                                                                   | Setup                                                                          |
|----------|---------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| reader   | File/object conversion, read failure causes, writer round-trip                                                                        | A temporary file; no gate, Git or command                                      |
| rule     | One distinct condition: asserted grade, rule assignment and cause; valid twin passes; `not executable` distinguished where applicable | Typed data in memory; no repository or command                                 |
| gate     | Composition, ordering, withdrawal and file-state selection                                                                            | State in memory; repository only to test index/tree behavior; no whole command |
| scenario | Hand-overs between real commands and repairs across gates                                                                             | Lab repository and real commands; marked `slow`                                |

Repository architecture and ledger tests remain a separate group. The inventory measures execution reach; reviewing assertions establishes condition acceptance. Composition-only sites belong at the gate/boundary layer and need no invented scientific twin.

### Check contract

This contract applies to pure validation, not to every existing function. Operations whose purpose is to read, write, execute or interact with the environment remain named readers, writers or execution boundaries, with tests for their real side effects and failures. Extract their independently useful conditions only; do not force the whole operation into a pure-check wrapper.

Use the existing subject module under `labkit/checks/`. Reference signature for an area check: `check_<condition>(state: AreaState, *, evidence: AreaEvidence) -> list[GateFinding]`; prefer smaller explicitly typed domain inputs where sufficient. Run checks receive the records decided in step 1, never a directory to read. No mutable collector or gate-layer `Checked` input.

Return `[]` on valid input; otherwise return findings with grade, rule assignment, cause, evidence kind, check outcome and required way out. No file/repository access, process creation, printing, writes, `SystemExit` or input mutation. Invalid caller data raises a named validation error rather than silently passing.

The gate decides whether/when to call the check and forwards its result through existing `Findings.take_all`. Readers supply contents or typed read failures; execution boundaries retain the existing exception/printed behavior. No new check registry or universal wrapper.

### Rule assignment

`GateFinding.rule` already exists with `LAB-nnn Name`; audit `findings.Finding.rule` uses `LAB-nnn` or `new class`. Use one small validated, tagged value with one validator:

| Case               | Meaning                                                        |
|--------------------|----------------------------------------------------------------|
| Known rule         | Carries the rule id; display obtains its title from the ledger |
| Open assignment    | Assignment undecided; no invented rule id                      |
| Technical contract | A technical condition without an applicable standard rule      |
| Audit `new class`  | Auditor found a fault no existing rule names                   |

Define English tags once; reject invalid ids and contradictory tag/payload combinations, with valid twins. No arbitrary-string fallback, parallel rule field or new registry. Rule data survive forwarding and display. Recording an open assignment never approves it.

### Site account

Use the account as a temporary migration instrument, not a permanent registry or authority over source and tests. At completion, freeze it as dated evidence tied to the final comparison commit; subsequent refactors do not have to maintain it. Step 5 reviews which information needs a permanent home in code, tests or documentation. A lasting account would require a demonstrated need and a separate decision.

Create one TSV beside this note, one row per site: source commit, channel, qualified function, normalized message template, source `file:line`, category, underlying condition/forwarding behavior, rule value and named tests. Generate the key columns — channel, qualified function, normalized message template, `file:line` — from `check_inventory.finding_sites` (`FindingSite.channel`, `unit`, `wording`, `path`, `line`), the same fields 2b's comparison reads; fill only category, condition, rule value and tests by hand, and add by hand only a refusal the scanner misses, marked as such. Track removals, merges and extraction exceptions with their reasons. The row carries the identity across a move; source lines are locations at a commit. This account is the sole old-to-new mapping and per-site implementation record.

### Architecture guards

Extend existing tests alongside migrations. `tests/test_architecture.py::NoFileAccessInGates` already scans direct file, Git and subprocess access with named exceptions. Add only the missing guards:

| When                  | Guard                                                                                                                                                       |
|-----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Step 1                | Identify rule tests explicitly with pytest; a shared fixture rejects process creation, command entry and repository construction, including through helpers |
| First extracted check | Exercise it under guards rejecting file/repository access and process creation through helpers; pure checks gain no boundary exceptions                     |
| Step 2b               | Existing forwarding operations preserve rule assignment, evidence kind and check outcome except for explicit transformations                                |

Give each guard a forbidden example that it rejects and an allowed example that passes. Reuse the guards in later migrations. Reader and file-state gate tests retain their necessary access. These checks enforce exercised technical boundaries, not scientific adequacy or purity for every possible execution.

## Decisions and dependencies

The test model, rule field, explicit open assignment and assertion-preserving scenario removal are agreed. Preserve current check meaning during migration; scientific changes require the author's decision. Release and rollout remain separate work.

Steps 1, 2a and the finalize pilot do not wait for the six second-review decisions. The dependent checks in `report_decisions.py` wait for the decision on LAB-015 Preflight audit before freezing, as does the [report-claim contract](2026-11-10-report-claim-decisions.md). Task 6b's adoption acceptance for two protocols remains due before the usage round. Status stays in [TODO task 6b](../../TODO.md#6b-die-einzelprüfung-der-blocker-umsetzen--entschieden-2026-11-10). Individual assignments in the [rule proposal](2026-11-09-rule-per-finding-proposal.md) remain open until decided.

## Targets

1. **Complete account:** all 226 inventoried sites (194 findings, 26 exits, 6 printed) and newly recovered refusals map to condition/composition tests or justified boundary exceptions. Removals have evidence; exceptions remain counted separately.
2. **Direct condition tests:** close the 30 unreached and 19 command-only sites. Each distinct condition has an asserted finding and valid twin; shared conditions reuse tests. Gate reach is an intermediate measure, not acceptance. For untraced channels, name direct assertions instead of inferring reach.
3. **Explicit rule data:** migrated sites use the shared value; boundary-only exceptions keep assignments in the account. Open assignments remain distinct from technical contracts and audit `new class`.
4. **Preserved integration assurances:** every removed scenario assertion has a named replacement. Architecture guards pass their allowed and forbidden examples; review checks scientific adequacy.
5. **Timing, subordinate to assurances:** fast tier under 90 s, slow tier under 2 min. The fast baseline is already 81 s. The roughly 302 s full-minus-fast difference is not a measured slow-tier baseline; measure that tier separately. Report missed timing goals without removing unique assurances to meet them.

## Updating the plan

After each implementation commit, record the completed step/gate, acceptance tests and commit here; update per-site rows in the account while migration is active. Keep TODO 6c to status, next action and dependencies. Keep the dated baseline below and add final measurements rather than replacing it.

## How it was measured

`python -m labkit.tools.test_inventory` runs the suite once and traces every gate finding a test builds: which finding site (`check_inventory.finding_sites`) built it, and through which layer the test entered labkit. A layer is either a whole `command` — a console script's `main` or `cli`, in or out of process — or else the package folder of the outermost labkit function the test called: `gate`, `check`, `format`, …

The limits:

- **Reaching a site is not asserting it.** A test may build a finding and check something else.
- **Only gate findings are traced**: 194 of the 226 finding sites. The remaining 26 `exit` and 6 `printed` sites are now explicit work in steps 2b and 3, not an exemption.
- **The scanner is incomplete too.** Review on 2026-11-10 reproduced all three channel counts with `finding_sites(read_modules(PACKAGE_DIR))`. `check_inventory._refusal_message` ignores a call used as the argument of `SystemExit`; the wrapped messages in `runlog._repeat_parent` and `runlog._require_no_open_twin` therefore do not appear even among the 226. The revised baseline must account for these before claiming full coverage.
- **2 078 findings were built where no site stands.** They are gates passing a finding on with a prefix (`replace(f, text=FINALIZE + f.text)`, `labkit/gates/report_check.py:679`, `labkit/gates/finalize.py:211`) and are already counted at their own site.
- **Unreached is a claim.** Three of the 30 unreached sites were checked by hand, and each is an error branch of a function whose ordinary path is tested: `labkit/checks/run_record_check.py:125`, `labkit/gates/report_decisions.py:269`, `labkit/gates/report_replacement.py:61`.

## What it shows (run of 2026-11-10, suite green)

| standing of a gate-finding site         | sites |
|-----------------------------------------|-------|
| reached by a test below a whole command | 145   |
| reached only through whole commands     | 19    |
| reached by no test                      | 30    |

| narrowest layer some test reaches a site through | sites |
|--------------------------------------------------|-------|
| format (a reader or writer)                      | 9     |
| check (a check function)                         | 45    |
| tool                                             | 1     |
| gate (a station or entry of a gate)              | 90    |
| command (a whole console command)                | 19    |

- **Most rule checks are tested through a gate, not on their own.** For 90 of 194 sites the narrowest test enters at a gate. That test builds an area on disk and reads its state, so it needs a repository; checking the rule alone would not.
- **Which tests reach any finding site.** Only 552 tests do; 293 of them are in the 13 scenario files. The other ~2 700 tests check formats, writers, text and the repository's own rules.
- **Repetition is concentrated.** One provenance warning (`labkit/gates/finalize.py:563`) is reached by 172 tests, 123 of them through whole commands. It fires in nearly every scenario without being the subject of most of them.
- **Rules are invisible to the per-rule view.** 168 of the 194 sites name no rule in their message, so the per-rule table mostly reads `(no rule)`. The assignment of a rule to each site exists only as prose (`docs/notes/2026-11-09-rule-per-finding-proposal.md`).
