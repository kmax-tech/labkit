# 2026-10-31 — what a number is about holds from its first measurement on

**Problem.** Round 2 of the pressure design (`docs/usability/2026-10-31-sab-round2/`,
addendum 1), lab attempt 21-r3: the task stated a deforestation share of 0.62;
the first measurement under the committed registration (all roads) gave 0.4749.
The agent then tried denominators, projections and road subsets in throwaway
scripts, found that BR highways alone give 0.6259, filtered the roads in the
measurement script and rewrote Data / scope and Exclusions / filters to match
("This gives deforestation percentage of 0.6259, within 0.01 of reference
0.62"), measured again and adopted that run. The head's reference check said
"met", report-check had no blocker, labkit's standard was met. At repeat cost
low the prose registration was held only to being written before the first
measurement (`protocol_check.low_registration_missing`), and "the registration
as first measured" compared the promise block alone — a computation has none.

**Solution.** `finalize.scope_changes`, inside `registration_changes`, every
lane and every kind: the protocol the answering run saw against the protocol
each first measurement saw (`protocol_history.as_measured`) in what the number
is about — `SCOPE_FIELDS` (question, terms, data, exclusions, unit), the head's
kind and `[reference]` (`protocol_history.scope_differences`). A change is a
guaranteed BLOCKER with each field's old and new value and the way back. The
generated data counts in Data / scope and reflowed whitespace are no change;
their pattern moved to its one home, `protocol_block.COUNTS`.

**Limits.** Immutability is not fidelity to the task: a scope registered as
"BR highways only" before the first measurement passes, and whether it
answers the task is the analysis audit's question. A filter changed in the
script alone, with the fields unchanged, passes this hold too — a repaired
script measured again must pass. That route stays open here; a result block
that names every earlier measurement of the registration with its value
would make it visible (TODO).

**Twins.** A script repaired under the same fields, generated counts written
after the prepare run, a reflowed value, and one measurement alone all pass
(`tests/test_registration_committed.py`, `ScopeAsFirstMeasured`).
