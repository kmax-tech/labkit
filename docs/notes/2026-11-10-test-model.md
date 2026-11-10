# Simplify checks and tests — implementation plan (2026-11-10)

> Decided by the author on 2026-11-10: the test model and the restructuring of the checks come before the next usage round. This note owns the implementation steps and their acceptance; [TODO task 6c](../../TODO.md#6c-ein-klares-testmodell-und-der-umbau-der-checks--vor-der-nutzungsrunde-entschieden-2026-11-10) owns their place in the work order.

## Outcome and current status

A check states which rule it holds and tests that rule against data in memory. A gate composes checks; a scenario verifies the hand-over between real commands. This puts each assurance in one place and makes changes possible without rebuilding a repository for every variant. Doing this before the usage round avoids carrying its findings into a second structure later.

The inventory is built; the five implementation steps below are pending. **Next: step 1, the state builder for tests.** This is a documentation of the agreed work, not a record of its implementation.

The baseline is the green suite measured on 2026-11-10: 3 233 tests in 187 files, about 65 700 lines; 383 s in total and 81 s without the 13 scenario files (about 12 900 lines), on 11 cores. Of 194 gate-finding sites, 30 are unreached, 19 are reached only through commands and 54 are reached through a check or format function. The detailed counts and their limits are preserved below.

## Decisions and dependencies

1. **Agreed:** four test layers; a rule field on each finding, with an explicit value for an assignment still open; acceptance by an asserted finding and a passing valid twin; scenario removal only after every assertion has a named replacement.
2. **Still open:** individual rule assignments in the [assignment proposal](2026-11-09-rule-per-finding-proposal.md). Recording an open assignment must not approve it. A technical contract without a standard rule must not be assigned an invented rule merely to fill the field.
3. **Earlier in the work order:** task 6b's remaining adoption acceptance for two protocols, the six author decisions on second review, and the dependent [report-claim decision contract](2026-11-10-report-claim-decisions.md). Their status stays in [TODO task 6b](../../TODO.md#6b-die-einzelprüfung-der-blocker-umsetzen--entschieden-2026-11-10); this plan does not decide them. If one is still open, it stays visible rather than being silently resolved by a refactor.
4. **Boundary:** preserve the checks' current meaning while restructuring them. A change to the scientific rule is a separate author decision. Release, rollout and the usage experiment remain separate tasks.

## The plan

Follow the steps in order. Step 3 repeats in small commits by gate; extracting a check and giving it its rule test belong in the same commit. The counts are a baseline, not a fixed list of source line numbers: track moved and removed sites when comparing inventories.

| Step | Work                                      | Complete when                                                                                      | Status  |
|------|-------------------------------------------|----------------------------------------------------------------------------------------------------|---------|
| 1    | Build test state from data                | A rule test can use `AreaState`, `AreaEvidence` and `Checked` without a repository                 | Next    |
| 2    | Carry the rule as finding data            | The field and inventory distinguish assigned rules from open assignments                           | Pending |
| 3    | Restructure and test checks, gate by gate | Every retained gate-finding site has an asserted finding and a passing twin at the narrowest layer | Pending |
| 4    | Reduce scenario variants                  | Each removed assertion has a named test that keeps it; command hand-overs remain covered           | Pending |
| 5    | Measure and review the result             | Acceptance and timing are recorded, with any remaining gaps explicit                               | Pending |

### 1. Build test state from data

Add `tests/state_fixture.py` to construct `AreaState`, `AreaEvidence` and `Checked` directly from data. Keep the inputs relevant to the tested condition explicit; use existing state types rather than a second representation of an area. Build only what the first migrated check needs, then extend with subsequent checks.

**Acceptance:** migrate a first rule test with its violation and valid twin. Both run without a repository, file reads or commands where the file itself is not the subject. The test asserts the cause of the finding; the rule field is added in step 2. This first migration demonstrates that the builder enables the intended test layer.

### 2. Carry the rule as finding data

Add the rule field to gate findings and make the inventory read it. Audit findings already have `findings.Finding.rule`; use that as the existing reference. Keep the human message separate from the field used for assertions and counts. Assign only settled mappings; carry an explicit open value for the rest and count it separately. Keep technical contracts distinguishable from undecided standard-rule assignments.

**Acceptance:** a finding retains its rule through forwarding and display; the inventory counts a known assignment and an open assignment separately; the first migrated rule test asserts the field. Changing this representation must not change whether an input blocks or passes. This step supplies the representation; step 3 applies it across the retained sites.

### 3. Restructure and test checks, gate by gate

Work through finalize, report-check, preflight and the report holds. At each gate, start with its unreached and command-only sites, then cover the sites reached only through a gate or tool. Review existing check and format tests against the same acceptance. Closing just the 30 unreached and 19 command-only sites does not finish this step: the target covers all retained gate-finding sites.

For each site:

1. Identify its condition, current rule assignment and existing assertions. Preserve a proposed assignment as open.
2. Put the condition in its single pure check function where it can be tested from data. Keep file reading in the reader and station order at the gate entry.
3. Assert the finding's grade, rule field and cause; add the valid twin. Where the check can be `not executable`, assert that result separately from a violation.
4. Keep gate tests for composition, ordering, withdrawal and index-versus-tree selection. Those assertions are different from a rule's variants.
5. Remove an unreachable branch only with evidence that it cannot occur. Record the removed site's reason so a smaller denominator cannot masquerade as better coverage.

**Acceptance per gate:** name the tests that hold each retained site's finding and twin. The inventory confirms reach at the check or format layer; reading the assertions establishes what is tested. If the outermost-call tracer still classifies a migrated test as `gate`, explain or correct the test entry rather than treating reach as acceptance.

### 4. Reduce scenario variants

Use the inventory to find candidates whose sites are reached lower. For each candidate, list every assertion and name the test that will keep it. Include command hand-overs, stored state read by the next command, and repairs across gates. Move single-rule variants to the narrowest layer; retain scenarios for each assurance and repair path that only real commands demonstrate.

**Acceptance:** every removed assertion has a named replacement. A site reached by another test is insufficient evidence. Retained scenario tests keep the `slow` mark. Timing pressure does not justify losing an assurance.

### 5. Measure and review the result

Run the inventory and compare its tables with the dated baseline under comparable conditions. Record the whole suite, fast-tier and slow-tier times, worker count, and the added or removed sites. Use the full-suite run required for this measurement; while migrating checks, use the touched tests and the repository's normal commit checks.

**Acceptance:** evaluate all [targets](#targets), name the tests supporting the per-site acceptance, and record any open assignments or missed timing targets. Target times remain under 90 s for the fast tier and under 2 min for the slow tier. The next usage round is a separate research task and starts only after the work order's prerequisites are satisfied.

## Maintaining this plan

After each implementation commit, update the step's status here and record the gate or sites completed, the tests establishing acceptance, and the commit. Keep TODO task 6c as a short pointer and current next action; keep detailed counts and the implementation record in this note. Keep the baseline below dated and add the final comparison rather than overwriting the starting measurements.

## The model

Four layers of tests, each asking one kind of question. A fifth group stands apart: the repository's own rules (`test_architecture`, `test_one_home`, the rules ledger).

| layer    | asks                                                                                                                                                       | builds                                                                   | never                                                   |
|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|---------------------------------------------------------|
| reader   | does a file read as its object, or refuse with its cause (`files.ReadError`); does a writer's output read back                                             | one file in a temporary folder                                           | a gate, git, a command                                  |
| rule     | for one finding site: the violation is found, the twin passes, the check that cannot run says so (`not executable`)                                        | the check's input as data — an `AreaState`, records, a text in memory    | files where the file is not the subject, git, a command |
| gate     | the order of the stations at one entry, one cause one blocker, a withdrawal first, the file state read (index or tree)                                     | a state in memory; a repository only where the file state is the subject | a whole command                                         |
| scenario | one walk through the real commands per assurance — registration, provenance, completeness, audit coverage, report — and per repair path that crosses gates | a lab repository, real commands; marked `slow`                           | a single rule's variants                                |

The rule layer is where a check's variants belong. A rule is tested once, with its twin, at the narrowest layer that can show it; a scenario only shows that the pieces fit. The precondition was built in task 5: the gates are functions of `AreaState` and `AreaEvidence`, which can be built as data.

## Targets

The inventory measures reach: a site was executed. That is an intermediate target, not the acceptance. A site counts as tested only when a test asserts its finding — the grade, the rule, the sentence that names the cause — and its twin, the valid case, passes. That is read in the test, not traced.

1. **No unreached site.** Each of the 30 gets a rule test, or is removed when the branch cannot happen.
2. **No site reached only through commands.** Each of the 19 gets a rule test.
3. **Every gate-finding site is reached at the rule layer** (check or format): 54 of 194 today, the measured intermediate target. Accepted per site when that test asserts the finding and a twin passes.
4. **Every site names its rule as a field** of its finding, as audit findings do (`findings.Finding.rule`); the message is for people, the field for tests and counts (decided 2026-11-10). Many assignments are still proposals (`docs/notes/2026-11-09-rule-per-finding-proposal.md`), and a required field must not make an open one look settled: the field takes an explicit value for an assignment still open, counted apart, as an audit's `new class` is.
5. **The slow tier keeps what only a scenario shows.** A scenario test is not redundant because its sites are reached lower: it may check the hand-over between commands, a state one command stores and the next reads, or a repair path across gates. One goes only when each of its assertions is kept elsewhere, named per test. Target: the slow tier under 2 minutes, from 5; the fast tier stays under 90 s.

## How it was measured

`python -m labkit.tools.test_inventory` runs the suite once and traces every gate finding a test builds: which finding site (`check_inventory.finding_sites`) built it, and through which layer the test entered labkit. A layer is either a whole `command` — a console script's `main` or `cli`, in or out of process — or else the package folder of the outermost labkit function the test called: `gate`, `check`, `format`, …

The limits:

- **Reaching a site is not asserting it.** A test may build a finding and check something else.
- **Only gate findings are traced**: 194 of the 226 finding sites. The rest end in a `SystemExit` or a printed line.
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
