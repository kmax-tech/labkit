# Simplify checks and tests — implementation plan (2026-11-10)

> Decided by the author on 2026-11-10: the test model and the restructuring of the checks come before the next usage round. This note owns the implementation steps and their acceptance; [TODO task 6c](../../TODO.md#6c-ein-klares-testmodell-und-der-umbau-der-checks--vor-der-nutzungsrunde-entschieden-2026-11-10) owns their place in the work order.

## Outcome and current status

A check states which rule it holds and tests that rule against data in memory. A gate composes checks; a scenario verifies the hand-over between real commands. This puts each assurance in one place and makes changes possible without rebuilding a repository for every variant. Doing this before the usage round avoids carrying its findings into a second structure later.

The current inventory is built; its extensions and the implementation steps below are pending. **Next: step 1, the state builder for tests, including the decision how an answering run's files reach a check as data.** Implementation has not started. Only steps 1 and 2a precede the finalize pilot; the remaining tool work (2b) follows the checkpoint.

The baseline is the green suite measured on 2026-11-10: 3 233 tests in 187 files, about 65 700 lines; 383 s in total and 81 s without the 13 scenario files (about 12 900 lines), on 11 cores. Of 194 gate-finding sites, 30 are unreached, 19 are reached only through commands and 54 are reached through a check or format function. These reach counts cover only the gate channel. All 226 currently inventoried sites are in scope, including 26 `exit` and 6 `printed` sites; the inventory itself also misses some refusals, as documented below. The detailed baseline and its limits are preserved below.

## Decisions and dependencies

1. **Agreed:** four test layers; a rule field on each finding, with an explicit value for an assignment still open; acceptance by an asserted finding and a passing valid twin; scenario removal only after every assertion has a named replacement.
2. **Still open:** individual rule assignments in the [assignment proposal](2026-11-09-rule-per-finding-proposal.md). Recording an open assignment must not approve it. A technical contract without a standard rule must not be assigned an invented rule merely to fill the field.
3. **Dependencies by site:** steps 1 and 2a and the finalize pilot can start independently of the six author decisions on second review. The rule value can carry an open assignment without settling it. In step 3, defer the checks in `labkit/gates/report_decisions.py` whose assignment or meaning depends on LAB-015 Preflight audit before freezing until those decisions are made. The dependent [report-claim decision contract](2026-11-10-report-claim-decisions.md) waits as well. Task 6b's remaining adoption acceptance for two protocols remains a prerequisite for the usage round, not for building a test fixture. Their status stays in [TODO task 6b](../../TODO.md#6b-die-einzelprüfung-der-blocker-umsetzen--entschieden-2026-11-10).
4. **Boundary:** preserve the checks' current meaning while restructuring them. A change to the scientific rule is a separate author decision. Release, rollout and the usage experiment remain separate tasks.

## The plan

Follow the steps in order, with the mandatory checkpoint after the first gate in step 3. Step 2 is split around that checkpoint: before the finalize pilot only what finalize needs (2a), the rest after the checkpoint and before the next gate (2b), so that the checkpoint measures migration work rather than mostly tool building. Step 3 repeats in small commits by gate; extracting a check and giving it its rule test belong in the same commit. The 226 sites are the starting inventory, not a claim that the scanner finds every refusal.

| Step | Work                                      | Complete when                                                                                                                                                        | Status  |
|------|-------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|
| 1    | Build test state from data                | A rule test runs without a repository, from `AreaState` and `AreaEvidence` or from an answering run's files given as data                                            | Next    |
| 2a   | Rule value and site list for the pilot    | The rule value is defined and validated; finalize's sites stand in the site account at the pilot's start commit                                                      | Pending |
| 2b   | Rule data and baseline for the rest       | The rule value reaches every constructor and the audit records; all channels and recovered refusals are in the baseline; every remaining site is in the site account | Pending |
| 3    | Restructure and test checks, gate by gate | All sites map to tested conditions or composition behavior; first-gate checkpoint passed                                                                             | Pending |
| 4    | Reduce scenario variants                  | Each removed assertion has a named test that keeps it; command hand-overs remain covered                                                                             | Pending |
| 5    | Measure and review the result             | Acceptance and timing are recorded, with any remaining gaps explicit                                                                                                 | Pending |

### 1. Build test state from data

Add `tests/state_fixture.py` to construct `AreaState` and `AreaEvidence` directly from data. `Checked` (`labkit/gates/report_context.py`) is report-check's gate-layer object, which no check receives; add it to the builder only when report-check's gate tests need it. Keep the inputs relevant to the tested condition explicit; use existing state types rather than a second representation of an area. Build only what the first migrated check needs, then extend with subsequent checks. Construct explicit, minimal data without hidden scientific defaults, derived-field synchronization, automatic repairs or special cases that make an invalid state valid. Tests must be able to supply inconsistent states deliberately. Reuse production data types, not production normalization that could erase the condition under test. Defaults may shorten irrelevant boilerplate only when documented and independent of the tested condition.

**The answering run's files as data.** About half of finalize's stations do not read the area state: they take the answering run's directory and read its files themselves — `check_run_code`, `check_declared_scopes`, `check_provenance`, `check_null_lane`, `check_registered_outputs`, `check_criterion_n` in `labkit/gates/finalize.py` (code and scope hashes, `outputs.json`, `metrics.json`, the recorded inputs, git tracking). `AreaState` holds none of these. Before the pilot reaches them, decide which typed value carries what these checks read of one run — its records as read, each read failure as data (`gate.outcome_of_failed_read` decides its outcome) — and which reader builds it. Prefer the records `labkit/formats/runs.py` already returns (`read_outputs`, `read_metrics`, the run record); the checks behind these stations live in `labkit/checks/run_record_check.py` and take the run's directory today; a new type is justified only where no existing one carries the input, and it describes a run, not a second representation of an area. Record the decision with the reference implementation. `check_area_tests` runs the area's tests as a subprocess and stays a named boundary (`preflight.area_tests`), not a pure check.

**Acceptance:** migrate a first rule test with its violation and valid twin. Both run without a repository, file reads or commands where the file itself is not the subject. The test asserts the cause of the finding and the existing rule field where assigned. Record the first migrated function and its gate caller here as the reference implementation, using the contract below, before migrating more checks. Step 2a then normalizes the rule value. Demonstrate that the builder preserves a deliberately inconsistent input unchanged, and add the rule-test boundary guard described below with this first example.

### 2. Unify rule data and prepare measurement

Step 2 is split around the checkpoint. 2a supplies what the finalize pilot needs; 2b, the rest, comes after the checkpoint and before the next gate is migrated.

#### 2a. Rule value and site list for the pilot

**Rule representation.** `GateFinding.rule` already exists (`labkit/formats/gate.py`, class `GateFinding`); its documented value is `LAB-nnn Name`, whereas `findings.Finding.rule` carries `LAB-nnn` or `new class`. Normalize the machine value to the rule id in both forms, using one validator and the rules ledger for the display title. Add an explicit value for an assignment still open. Keep that distinct from an audit's `new class` (no existing rule names the fault) and a technical contract without a standard rule. Represent these cases with one validated, tagged value: a known-rule case carries the rule id, an open-assignment case carries no invented id, and a technical-contract case is explicit. Preserve the separate audit `new class` case. Define the English tags once and reject contradictory tag/payload combinations. Do not use arbitrary strings or a fallback that turns an invalid id into an open assignment; keep the representation small, without a new registry. Do not introduce a parallel rule field. Before the pilot, fill the existing `GateFinding.rule` at finalize's sites and in the constructors finalize uses; the rest follows in 2b.

**The site account.** Open a site account: one row per site in a TSV file beside this note, holding the site as it stands at a named commit (channel, qualified function, normalized message template, `file:line` at that commit), its category, the condition or forwarding behavior it maps to, its rule value and the tests that hold it — or its removal, merge or extraction exception with the reason. A site is identified by its row, not by its line: the line is a display location at the row's commit. For the pilot, enter finalize's sites in all three channels at the pilot's start commit, and check `labkit/gates/finalize.py` for refusals the scanner misses (a `SystemExit` whose argument is a call, see 2b).

**Acceptance:** the rule value rejects an invalid id and a contradictory tag/payload combination, with a passing valid twin; the first migrated rule test asserts the normalized field; finalize's sites stand in the site account with the pilot's start commit.

#### 2b. Rule data and baseline for the rest

**Rule data everywhere.** Fill the rule value at every migrated site and extend the constructors that currently cannot receive it, including the audit records' `findings.Finding.rule` — a record format on disk, so check the public API and record-format obligations first and follow the repository's transition and Breaking policies where applicable. Read the inventory's rule counts from these data, not from message text.

**Inventory coverage.** List all `exit` and `printed` sites alongside gate findings, with their test-evidence status. The scanner currently excludes `SystemExit` arguments that are calls (`check_inventory._refusal_message`); this hides `runlog` refusals wrapped in `with_way_out`, including `_repeat_parent` and `_require_no_open_twin`. Review this omission and other scanner boundaries before freezing the comparison baseline. A known wrapped refusal and a known direct refusal must both appear; command exit-code forwarding must not become a spurious finding. New sites discovered here increase the denominator explicitly.

**Comparison through the site account.** The site account is the old-to-new mapping; there is no second, automatic matcher. Compare the inventory at the baseline commit with the current one by channel, qualified function and normalized message template — no line numbers, so inserting lines changes nothing. Every difference (moved into a check, renamed, reworded, split, merged, removed, added) must be explained by a row of the site account. A key that occurs more than once on one side is resolved in the account by hand, never by line order. Enter every remaining site in the account before its gate is migrated.

**Acceptance:** rule data survive forwarding and display; the inventory distinguishes assigned, open and technical-contract cases. All current channels and newly found refusals are accounted for. The comparison lists every difference no row explains, and nothing for a mere line insertion. Preserve the dated 194-site trace as a partial baseline; do not infer reach for untraced channels. Use direct test assertions as evidence for those until tracing exists. The cross-test candidate report required by step 4 is a separate tool deliverable there.

### 3. Restructure and test checks, gate by gate

Start with finalize and stop at the checkpoint below. If continued, work through report-check, preflight and the report holds, then the remaining readers and run-time refusals outside those gates. At each gate, start with its unreached and command-only sites, then cover the sites reached only through a gate or tool. Review existing check and format tests against the same acceptance. Closing just the 30 unreached and 19 command-only sites does not finish this step: the target covers all retained sites across `finding`, `exit` and `printed`, plus refusals recovered from scanner omissions. Assign the 32 non-gate sites to their owning module in the site account; none is implicitly exempt.

**Sites account for the implementation; conditions define the tests.** Classify each site as a scientific rule condition, a technical contract condition, or composition/forwarding. Several sites may share one condition and its violation/valid-twin tests when their meaning and inputs are the same. Map each such site to that condition and its named tests; test only additional context or wiring at the caller. Forwarding a finding does not create a new rule condition. Do not extract a function or duplicate a twin test merely to improve a site count.

For each site:

1. Identify its category, underlying condition or forwarding behavior, current rule assignment and existing assertions. Preserve a proposed assignment as open.
2. Put the condition in its single pure check function where it can be tested from data. Keep file reading in the reader and station order at the gate entry.
3. For each distinct scientific or technical condition, assert the finding's grade, rule field and cause and provide the valid twin; reuse these tests for sites sharing that condition. Where the check can be `not executable`, assert that result separately from a violation.
4. Keep gate tests for composition, ordering, withdrawal and index-versus-tree selection. Those assertions are different from a rule's variants.
5. For an `exit` or `printed` site, test the underlying condition as data (reusing its twin tests where shared) and retain a boundary assertion for the exit status or printed warning. Test forwarding as forwarding, including correct handling of a passing result, rather than inventing a separate scientific twin. The boundary keeps its current outward behavior. If extraction does not help (for example a command usage error), record a per-site exclusion with its reason and the test that still holds it. Exclusion from extraction is not exclusion from accounting.
6. Remove an unreachable branch only with evidence that it cannot occur. Record the removed site's reason so a smaller denominator cannot masquerade as better coverage.

**Acceptance per gate or module:** every retained site maps to a tested scientific condition, tested technical condition, tested composition/forwarding behavior, or a justified extraction exception. Every distinct condition has a violation and valid twin; composition tests assert the extra behavior they own. Report site reach and condition acceptance separately: more tests per site are not a success criterion. The inventory confirms where execution entered; reading the assertions establishes what is tested. If the outermost-call tracer still classifies a migrated test as `gate`, explain or correct the test entry rather than treating reach as acceptance.

### Check contract and first-gate checkpoint

**Reference form to establish in step 1:** put an extracted area-state check in the owning subject module under `labkit/checks/`; reuse an existing module where it owns that condition. Its reference signature is `check_<condition>(state: AreaState, *, evidence: AreaEvidence) -> list[GateFinding]`. A check needing only smaller data takes explicitly typed domain arguments instead; record those inputs with the first example. A run-level check takes the answering run's records as decided in step 1 ("The answering run's files as data"), not the run's directory. Do not pass a mutable collector or the gate-layer `Checked` object into a check. A passing check returns `[]`; a failure returns findings with grade, rule, cause, evidence kind, check outcome and the required way out. A check neither reads files nor prints, writes, raises `SystemExit` or changes its input. Malformed caller data still raises a named validation error; it must not silently become success.

The gate chooses whether and when to call the check, then passes its returned list to the existing `Findings.take_all`. The reader supplies file contents or a typed read failure as data. For run-time refusals, the boundary translates the result to the existing exception or printed channel. Record the actual first function's signature, location, return values and caller in this note; use it as the template for later migrations. Keep genuine differences in input types explicit rather than introducing a check registry or new universal wrapper.

**Architecture guards, built alongside the first migrations.** Extend existing tests rather than creating a second architecture checker. `tests/test_architecture.py::NoFileAccessInGates` already scans gates and checks for direct file, git and subprocess calls with named exceptions. Keep that guard and add only the missing boundaries:

1. In step 1, identify rule tests explicitly with an existing pytest mechanism, such as a marker. A shared fixture for these tests rejects process creation, command-entry calls and repository construction, including when reached through a helper. Reader tests and gate tests that verify index/tree behavior remain outside this restriction.
2. With the first extracted check, exercise it under a guard that rejects file access, repository access and subprocess creation through helpers as well as direct calls. Keep named boundary exceptions out of pure checks. This supplements the existing source scan; it does not claim to prove purity for every possible execution.
3. In step 2b, extend the tests of the existing finding forwarding operations to assert that the rule assignment, evidence kind and check outcome survive unchanged except where an explicit transformation is intended.

For each guard, include a small deliberately forbidden example and an allowed example so a green architecture test shows that the guard itself works. Reuse those guards for later migrations. They enforce observable technical boundaries; review still judges whether a test asserts the intended scientific condition.

**Mandatory stop after finalize, before another gate is migrated.** Before starting the pilot, record its commit, the selected sites, suite timings and the time spent on shared infrastructure separately. Track implementation and verification time during the pilot. At the checkpoint report sites accounted for, distinct conditions completed, implementation/verification time per condition and per site, code and test line changes, fast/slow suite time changes, and a remaining-effort range based on the observed work and the still-unclassified sites. Scenario time may not improve before step 4; report zero or unmeasured improvement honestly rather than crediting an anticipated saving.

A reliable estimate and an overall time cap do not exist yet. At this checkpoint the author chooses whether to continue unchanged, narrow the work with a time cap, or defer the rest. Do not continue the broad migration automatically. A usage round with a partial refactor requires an explicit change to the earlier decision: list completed modules, deferred sites, remaining risks and unmet targets. Preserve the checks and tests for deferred sites. This checkpoint prevents the complete migration from becoming an unbounded prerequisite while leaving the research decision with the author.

### 4. Reduce scenario variants

**Tool work first:** extend the inventory to emit per-scenario test node id, its reached site identities, and the lower-layer test ids reaching each site. This cross-test candidate list does not exist in the current renderer, which reports mostly per site and file. Test the report with a scenario whose sites all have lower-layer witnesses and one with a command-only site. Flag tests with no traced sites, untraced channels or missing subprocess events as unknown; never call them redundant.

Use that report to find candidates whose sites are reached lower. For each candidate, list every assertion and name the test that will keep it. Include command hand-overs, stored state read by the next command, and repairs across gates. Move single-rule variants to the narrowest layer; retain scenarios for each assurance and repair path that only real commands demonstrate.

**Acceptance:** every removed assertion has a named replacement. A site reached by another test is insufficient evidence. Retained scenario tests keep the `slow` mark. Timing pressure does not justify losing an assurance.

### 5. Measure and review the result

Run the extended inventory and compare its tables with the baseline through the site account from step 2b under comparable conditions. Resolve unmatched sites before claiming coverage gains. Record the whole suite, fast-tier and slow-tier times, worker count, and the added or removed sites. Use the full-suite run required for this measurement; while migrating checks, use the touched tests and the repository's normal commit checks.

**Acceptance:** evaluate all [targets](#targets), name the condition and composition tests supporting the site account, and record any open assignments or missed timing targets. Retained assurances and passing architecture guards take priority over timing. Target times remain under 90 s for the fast tier and under 2 min for the slow tier; missing a timing target is reported separately and never justifies removing a unique assurance. The next usage round is a separate research task and starts only after the work order's prerequisites are satisfied.

## Maintaining this plan

After each implementation commit, update the step's status here and record the gate or sites completed, the tests establishing acceptance, and the commit. Keep TODO task 6c as a short pointer and current next action; keep detailed counts and the implementation record in this note, the per-site rows in the site account (step 2a). Keep the baseline below dated and add the final comparison rather than overwriting the starting measurements.

## The model

Four layers of tests, each asking one kind of question. A fifth group stands apart: the repository's own rules (`test_architecture`, `test_one_home`, the rules ledger).

| layer    | asks                                                                                                                                                       | builds                                                                   | never                                                   |
|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|---------------------------------------------------------|
| reader   | does a file read as its object, or refuse with its cause (`files.ReadError`); does a writer's output read back                                             | one file in a temporary folder                                           | a gate, git, a command                                  |
| rule     | for one distinct scientific or technical condition: the violation is found, the twin passes, a check that cannot run says so (`not executable`)            | the check's input as data — an `AreaState`, records, a text in memory    | files where the file is not the subject, git, a command |
| gate     | the order of the stations at one entry, one cause one blocker, a withdrawal first, the file state read (index or tree)                                     | a state in memory; a repository only where the file state is the subject | a whole command                                         |
| scenario | one walk through the real commands per assurance — registration, provenance, completeness, audit coverage, report — and per repair path that crosses gates | a lab repository, real commands; marked `slow`                           | a single rule's variants                                |

The rule layer is where a condition's variants belong. Each distinct condition is tested with its twin at the narrowest layer that can show it; several conditions may belong to one standard rule, and several sites may share one condition; a scenario only shows that the pieces fit. The precondition was built in task 5: the gates are functions of `AreaState` and `AreaEvidence`, which can be built as data.

## Targets

Scope: all 226 currently inventoried sites, plus sites recovered by reviewing scanner omissions in step 2b. Extraction exceptions require a per-site reason and a named boundary test; untraced is a measurement status, not an exception.

The inventory measures reach: a site was executed. That is an intermediate target, not the acceptance. A condition counts as tested only when a test asserts its finding — the grade, rule assignment and cause — and its valid twin passes. A site is accounted for by mapping it, in its row of the site account, to those tests, to tests of its additional composition behavior, or to a justified boundary exception. This mapping is reviewed, not inferred from reach. It need not have a one-to-one relationship with tests.

1. **No unreached site.** Each of the 30 is linked to condition tests or composition tests, or removed with evidence that the branch cannot happen.
2. **No site reached only through commands.** Each of the 19 is linked to condition or composition tests below the command layer, with boundary assertions for any additional command behavior or a justified boundary-only exception.
3. **Every retained site has narrow-layer acceptance or a justified extraction exception.** For scientific and technical conditions, reach at the check or format layer is an intermediate measure: 54 of 194 sites in the original trace. Composition-only sites belong at the gate or boundary layer and are counted separately, not forced into a rule test. For the 26 `exit` and 6 `printed` sites, and newly found refusals, record asserted condition and boundary tests separately until their reach is traceable. Acceptance follows the condition/composition mapping above; report exceptions separately from completed migrations.
4. **Every migrated site names its rule as a field** of its finding; justified boundary-only exceptions keep their assignment in the site account. Gate and audit findings use the same rule-id representation; the message is for people, the field for tests and counts (decided 2026-11-10). Many assignments are still proposals (`docs/notes/2026-11-09-rule-per-finding-proposal.md`), and a required field must not make an open one look settled: the field takes an explicit value for an assignment still open, counted apart and distinct from an audit's `new class` and from a technical contract without a standard rule.
5. **The slow tier keeps what only a scenario shows.** A scenario test is not redundant because its sites are reached lower: it may check the hand-over between commands, a state one command stores and the next reads, or a repair path across gates. One goes only when each of its assertions is kept elsewhere, named per test. Timing goals: slow tier under 2 minutes; fast tier under 90 s. The fast baseline (81 s) already meets its goal; expected savings come mainly from removing redundant scenario variants. The roughly 302 s difference between the full and fast runs is not an independently measured slow-tier baseline. Measure that tier separately before comparing. Preserving assurances takes priority over both timing goals.
6. **Boundaries remain enforced.** The architecture guards introduced with steps 1 and 2b pass, reject their known forbidden examples and allow their valid examples. Scientific adequacy remains a review obligation.

## How it was measured

`python -m labkit.tools.test_inventory` runs the suite once and traces every gate finding a test builds: which finding site (`check_inventory.finding_sites`) built it, and through which layer the test entered labkit. A layer is either a whole `command` — a console script's `main` or `cli`, in or out of process — or else the package folder of the outermost labkit function the test called: `gate`, `check`, `format`, …

The limits:

- **Reaching a site is not asserting it.** A test may build a finding and check something else.
- **Only gate findings are traced**: 194 of the 226 finding sites. The remaining 26 `exit` and 6 `printed` sites are now explicit work in steps 2 and 3, not an exemption.
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
