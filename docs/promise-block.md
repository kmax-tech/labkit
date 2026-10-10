# Promise block

What a protocol promises the code, as data instead of prose, and what the
checks built on it may claim. Code: `labkit/promises.py`; tests:
`tests/test_promises.py`. Terms (`protocol`, `run`, `metrics`, `intent id`)
are coined in the README.

## Claim and check tiers

labkit's claim: **it detects violations of explicitly encoded scientific
intent across implementation, execution and reporting.** The chain:

    scientific intent → explicit promise → code realization → execution → reported result

Every check belongs to exactly one tier and its message says which:

| Tier | Claims | Examples |
|---|---|---|
| **guaranteed** | exact and mechanical; silent on a correct input | block parses, prose and block name the same ids, the declared key is reported exactly, the run recorded this block, the declared scope is unchanged |
| **static evidence** | an indication; warns, never blocks | a key is written but never read; a scope function calls repo code outside the declared scope |
| **agent audit** | semantic agreement of intent and code | `labkit-audit` (the experiment-preflight instructions, one model call), the `code-check` agent on a `code-check --bundle` |

A static check is never presented as proof of semantics. Everything in
`promises.py` is the guaranteed tier.

## Three kinds of promise

| Letter | Kind | One sentence |
|---|---|---|
| `C` | criterion | constrains the reported outcome: which value of which metric counts as support for the hypothesis |
| `A` | admissibility | determines whether any C verdict may be issued, conditional on an outcome-neutral check (control, anchor, yield, coverage, resolution) passing in the same run |
| `B` | branch | binds a pre-specified condition on the results to the conclusion or follow-up analysis it licenses |

**Separation rule: C judges, A releases the judgement, B says what follows
from it.** Whether something is A: does it depend on the outcome of the
hypothesis? No → A (an outcome-neutral condition in the sense of Registered
Reports); yes → C. A comparator without a target value (a baseline the
traces are read against) is no promise; it belongs in the text of the C it
serves.

Two refinements (review 2026-10-08). An A names *why* its failure makes the
measurement uninterpretable — the instrument's yield, an anchor, a control
at its expected value — never a value the hypothesis needs: that threshold
is a C, and filed as an A it would turn a clean negative result into "no
verdict". A failed A withholds the verdict, not the data: descriptive
readings may follow, labelled as such. A B is decided on its own
condition, not on the verdict: a stop rule fires during the run or on an
inadmissible one too (`verdict()` sets the C keys to None, never the B).
"n/a — only one outcome" is the honest B when the answer to "and if [C…]
fails?" is not known before the run; a decision taken afterwards is
reported as taken afterwards.

**Earlier letters.** `K` (criterion), `S` (stop rule), `W` (fork) and `N`
(null condition) are not read since labkit 0.48. They did not map
one-to-one onto C/A/B: tested against 16 earlier protocols, the separation
rule assigned six ids differently from their letter — anchor and
completeness checks filed as criteria are A, a stop rule that selects the
next study is B, and an S/N pair describing one check becomes one A. Frozen
protocols are registrations and are not rewritten; they are read with
labkit 0.47.

**Not a kind:** a descriptive quantity reported in every branch, without a
criterion. It is a report line, not a promise — until a second case shows
it needs its own kind.

Letters excluded against collision with metric names: F (`f1`), P (`p1`),
R (`r1`), Q (`q1`), H (`h1`).

## The block

The protocol's one fenced TOML block holds the head (`[protocol]`, see
`labkit/protocol_block.py` and `docs/protocol-run-binding.md`) and the
`[[promise]]` tables:

```toml
[protocol]
standard = "0.19"
id = "p-9e2341c0390948dc"
type = "confirmatory"
cost = "minutes"
frozen = true
preflight_audit = "2026-10-07 · scope sha 3f9a1c2b7e04 · 2 findings (2 fixed)"

[[promise]]
id = "C1"
key = "c1_pass"
sentence = "macro-F1 of the judge >= min_f1 on the test split"
scope = ["scripts/01_measure.py:evaluate", "scripts/01_measure.py:filter_items"]
constants = { min_f1 = 0.70 }
```

| Field | Rule |
|---|---|
| `id` | `C<n>`, `A<n>` or `B<n>`, unique; also named in the prose |
| `key` | the metrics key reporting it: the id itself or `<id>_<suffix>` |
| `sentence` | the promise in one sentence |
| `scope` | non-empty list of `file` or `file:function` (top-level function or class), relative to the protocol's directory |
| `constants` | scalars the code reads from here instead of a second copy in the script — `promises.all_constants(promises.load(PROTOCOL))` into the script's config object; a name is lowercase snake_case and stands in exactly one promise (0.71.0) |

TOML, not YAML: labkit is stdlib-only, and `tomllib` is in the standard
library.

## Constants: the name is the mapping

A registered constant is named like the config key it is recorded under
(`min_f1`, `margin`, `max_empty` — `^[a-z][a-z0-9_]*$`), and it stands in
exactly one `[[promise]]` table; `parse_block` refuses `MIN_F1` and a name
declared twice. The name is the whole mapping between protocol and run
record: no second table says which key answers which constant, and a
heuristic ("sounds alike") would be evidence, not a check. The script
builds its config from the block — `MeasureConfig(model=MODEL,
**promises.all_constants(promises.load(PROTOCOL)))` — and records that
object whole; `runlog` refuses, before the run directory exists, a config
that lacks a registered constant or carries it with another value
(type-strict: `True` is not `1`, `1` is not `1.0`). The guarantee behind
the record is therefore: *a run under a block recorded every registered
constant unchanged*. Whether `evaluate_rows` uses the value right is the
agent audit's question, not a mechanical one. A frozen protocol, and
every full run — at `cost = "seconds"` every run — owes the block
(`promises.promise_tables_owed`, standard 0.19): without tables, `protocol-check`
reports a MUST failure (frozen or seconds), `preflight` and `finalize`
block, and no full run starts under it; only an unfrozen pilot
(`long=False`) runs without one. The seconds cut IS the registration — in
prose and in tables, so the machine chain (block digest, scope hashes,
constants) holds for every reportable run, not only for frozen ones. Mechanically guaranteed is the one home of a
*name*; that two differently named constants mean the same threshold no
parser can see.

## What the declared-scope hash states

`declared_scope_sha` hashes one promise's declared scope. It is not the
area audit stamp `scope-sha` (README: *scope hash*), which covers a whole
area for an audit and binds to no promise.

> **The implementation region declared for this promise was byte-identical
> in the run that produced the reported number.**

It does **not** state that the region is all the code the number depends
on, nor that the code implements the promise correctly.

The counterexample that fixes this: `compute_score()` writes `c1_accuracy`
and calls `filter_items()`. An edit to `filter_items` (now dropping empty
answers instead of counting them wrong) moves the number.

| Version | Sees the edit? | Why |
|---|---|---|
| hash over the function that writes the key | no | `compute_score` itself is unchanged — a stamp that misses exactly the interesting change |
| declared scope, `filter_items` declared | yes (guaranteed) | region changed → hash changed |
| declared scope, `filter_items` not declared | no; a warning is planned (static evidence) | the scope calls repo code outside itself |
| area audit stamp (`scope-sha`) | yes, if in the area | but not per promise: any edit anywhere changes it |

Hence: **scope is declared, not derived.** The author says which region a
promise rests on; the hash makes that statement checkable. A call-closure
warning may help with declaring; it does not replace it.

Details: a `file:function` entry hashes the function's source segment
(decorators included), so edits to neighbouring functions leave the stamp
alone; each entry contributes its spelling and its content digest, so
adding, dropping or renaming an entry changes the stamp; a missing file or
function is an error, never an empty digest. Module-level constants
outside a declared function are not covered — read them from the block.

## Along the chain

| Link | Who | Refuses or reports |
|---|---|---|
| promise | `intent-check` | block malformed; prose and block name different ids |
| execution | `runlog` | malformed block, dangling scope, frozen without tables, or a config missing or contradicting a registered constant → refused before the run dir exists; otherwise `config.json` records `promises`: the digest of the promises as read (normalized JSON — neither the head nor the spelling of a table moves it) and its format, and per id key, constants, scope, `declared_scope_sha` |
| report | `intent-check` | declared key not reported exactly; run recorded no block, or a different one ("the promises changed after the run"); a run from labkit 0.46/0.47 is told apart by its digest format, not reported as changed |
| recomputation | `recheck.holds` | a declared scope changed since the run, per promise |

A protocol without `[[promise]]` tables has no promise checks; its head is still read.
