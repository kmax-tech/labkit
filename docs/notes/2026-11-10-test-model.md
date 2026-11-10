# A test model for labkit — the inventory and the plan (2026-11-10)

> Decided by the author on 2026-11-10: the test model and the restructuring of the checks come before the next usage round. labkit is to be maintainable, and what the round finds would have to be carried into the new structure anyway (TODO.md, task 6c).

## The question

The suite has grown to 3 233 tests in 187 files, 65 700 lines. The 13 end-to-end scenario files (12 900 lines) take about 80 % of its time: 383 s for the whole suite, 81 s without them, on 11 cores. What is unclear is what each test checks and on which layer. Is a rule's check tested on its own, or only inside a scenario that runs whole commands? How many tests check the same thing?

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

## The model

Four layers of tests, each asking one kind of question. A fifth group stands apart: the repository's own rules (`test_architecture`, `test_one_home`, the rules ledger).

| layer    | asks                                                                                                                                                       | builds                                                                   | never                                                   |
|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|---------------------------------------------------------|
| reader   | does a file read as its object, or refuse with its cause (`files.ReadError`); does a writer's output read back                                             | one file in a temporary folder                                           | a gate, git, a command                                  |
| rule     | for one finding site: the violation is found, the twin passes, the check that cannot run says so (`not executable`)                                        | the check's input as data — an `AreaState`, records, a text in memory    | files where the file is not the subject, git, a command |
| gate     | the order of the stations at one entry, one cause one blocker, a withdrawal first, the file state read (index or tree)                                     | a state in memory; a repository only where the file state is the subject | a whole command                                         |
| scenario | one walk through the real commands per assurance — registration, provenance, completeness, audit coverage, report — and per repair path that crosses gates | a lab repository, real commands; marked `slow`                           | a single rule's variants                                |

The rule layer is where a check's variants belong. A rule is tested once, with its twin, at the narrowest layer that can show it; a scenario only shows that the pieces fit. The precondition was built in task 5: the gates are functions of `AreaState` and `AreaEvidence`, which can be built as data.

## Targets — the inventory measures each

1. **No unreached site.** Each of the 30 gets a rule test, or is removed when the branch cannot happen.
2. **No site reached only through commands.** Each of the 19 gets a rule test.
3. **Every gate-finding site is reached at the rule layer** (check or format) by a test with its twin. Today that holds for 54 of 194.
4. **Every site names its rule** in the code. A message citing a rule can carry it, or a field can, as audit findings now do (`findings.Finding.rule`). Then the per-rule table counts something.
5. **The slow tier shrinks to the scenarios that are walks**: a scenario test whose every site is also reached at a narrower layer is redundant, unless it is the one walk of an assurance. Target: the slow tier under 2 minutes, from 5. The fast tier stays under 90 s.

## The plan, each step its own commit and measured by the inventory

1. **A state builder for tests** (`tests/state_fixture.py`): an `AreaState`, `AreaEvidence` and `Checked` from data, without a repository — the enabler of the rule and gate layers.
2. **The rule of each site as data**, so the inventory counts per rule (target 4), in the shape the restructuring of the checks gives a check (rule, check, gate). This is where the restructuring and the test model meet: a check that becomes a pure function of the state gets its rule test in the same commit.
3. **Close the 30 unreached and the 19 command-only sites** (targets 1 and 2), gate by gate: finalize, report-check, preflight, the report holds.
4. **Move the variants out of the scenario files** (target 5): the inventory gains a column naming the scenario tests whose sites are all reached lower; those that are no walk go.
5. **Measure again**: the inventory's tables and the suite's time, before the usage round.
