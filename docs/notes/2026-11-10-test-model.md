# Simplify checks and tests — implementation plan (2026-11-10)

> Decided by the author on 2026-11-10: restructure the checks and tests before the next usage round. This note owns the implementation plan; [TODO task 6c](../../TODO.md#6c-ein-klares-testmodell-und-der-umbau-der-checks--vor-der-nutzungsrunde-entschieden-2026-11-10) owns its place in the work order.

## Start here

**Problem:** labkit's tests reach most check logic only from the outside, or not at all. Of the 194 places that build a gate finding, 90 are reached no closer than through a gate, 19 only through whole console commands, and 30 by no test at all. One provenance warning is reached by 172 tests without being the subject of most of them. 168 of the 194 places name no rule in their message. The fast tier takes 81 s; the full suite takes roughly 302 s longer ([What it shows](#what-it-shows-run-of-2026-11-10-suite-green)).

**Goal:** each scientific or technical condition has one implementation and tests of its own. Gates combine checks; scenario tests verify only what one command passes to the next. The plan keeps what today's tests establish first and reduces test time second.

**Status:** the inventory exists; implementation has not started. **Next:** step 1 — build minimal test inputs and migrate one check as the reference. Step 1 also decides how the files of the answering run reach a check as data.

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

### 2a. Prepare only what finalize needs

Define and validate the [shared rule value](#rule-assignment). Switch `GateFinding.rule` to it at once, at every site that sets the field. On 2026-11-10 these are about 15 `rule=` uses in 7 modules, none of them in finalize. After the switch the field never accepts the old string and the new value side by side. Then set the new value at finalize's sites. The first migrated test asserts the normalized value.

Open the [site account](#site-account) for finalize at the pilot's start commit, covering all three channels. Read the source for refusals the scanner misses. Three things wait for step 2b: the audit records' `findings.Finding.rule`, the constructors that cannot yet receive a rule, and the inventory tooling.

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

**Stop before another gate.** The author chooses to continue, to continue with a narrower scope and a time cap, or to defer. The choice rests on correctness, clarity, added complexity and cost; meeting the coverage and timing targets alone does not justify continuing. A usage round with a partial refactor requires an explicit change to the earlier decision that lists the deferred sites, the risks and the unmet targets. The deferred sites keep their existing checks and tests. No reliable overall estimate or time cap exists before this checkpoint.

### 2b. Complete rule data and measurement

Extend the audit records (`findings.Finding.rule`) and the constructors that cannot yet receive a rule to the shared rule value. Check the obligations of the public API and of the on-disk format before changing accepted values; follow the repository's transition and Breaking policies. Inventory rule counts read the data field, not the message text. Extend the forwarding tests as the forwarding guard in [Architecture guards](#architecture-guards) specifies.

Complete the site account and repair the scanner's known omission. `check_inventory._refusal_message` skips a `SystemExit` whose argument is a call, so it does not see the `runlog` messages wrapped in `with_way_out`. After the repair, a known wrapped refusal and a direct refusal both appear, and forwarding a command's exit code does not become a finding. Review the scanner's other limits and add each site found that way explicitly to the site count.

Compare the baseline inventory with the current one through the site account. The comparison key is the channel, the qualified function and the normalized message template; line numbers only locate the source. Explain moves, rewordings, renames, splits, merges, removals and additions in the site account. Resolve duplicate keys there by hand, never by line order. The comparison lists the differences the site account does not explain and ignores lines that only moved because others were inserted; do not build a second automatic matcher. Enter each remaining site before migrating its gate.

### 4. Reduce scenario variants

First extend the inventory with a report per scenario test: its pytest node id, the sites it reaches, and for each site the lower-layer tests that also reach it. The current renderer lacks this list across tests. Verify the report with one scenario test whose sites all have lower-layer tests and one that reaches a command-only site. A scenario test with no traced sites, with sites in untraced channels or with missing subprocess events counts as **unknown**, not as redundant.

Then review the assertions of every scenario test in the report. Name the replacement test for each assertion before removing it. Keep the tests of state that one command passes to the next, of stored state that the next command reads, and of repairs across gates. Reach alone never establishes a replacement. Scenario tests that stay keep the `slow` mark.

### 5. Measure and review

Compare the inventories through the site account and resolve unexplained changes before claiming gains. Under comparable conditions, record the times of the full suite, the fast tier and the slow tier, the worker count, and the added and removed sites. Evaluate the [targets](#targets); keep the open rule assignments and the extraction exceptions visible. Close the temporary site account as [Site account](#site-account) specifies. The usage round stays a separate research task with its own prerequisites.

## Contracts used throughout

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
