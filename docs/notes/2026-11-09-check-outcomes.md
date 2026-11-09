# What a check reports — 2026-11-09

*Design target · decided 2026-11-09 · not built; the inventory that led to it: [rule-per-finding proposal](2026-11-09-rule-per-finding-proposal.md)*

A check answers one question about one state and reports one of four outcomes: **not applicable** (the question does not arise here — before the first measurement a result file may be absent), **satisfied**, **violated** (a finding), **not executable** (the question arises and cannot be answered here). Applicability and preconditions are two questions: whether a file is required is the check's to decide, whether it can be read is the reader's to say.

## The reader says why, the check says what it means

A shared reader distinguishes its failures — the file is missing, access is refused, the format is invalid — and hands the cause on; it does not decide what the failure means. The check that called it decides: a missing `metrics.json` is a finding where the run is reported, and not applicable before any run. Today the causes are mixed at the source: `runs._json_of` turns `OSError` and `JSONDecodeError` into one `ArtefactError` (`labkit/formats/runs.py:350`), `scope_sha.read_source` and its parser turn a gone file, a non-UTF-8 file and a syntax error into one `SourceError` (`labkit/formats/scope_sha.py:85`). That is why 27 finding sites of the inventory cannot tell a defect from a check not executed. A distinguishable cause does not need one error class per cause; a cause carried with the error and kept until the message is enough.

## One finding, one statement, an explicit assignment

A finding states one concrete fact. It may concern one rule, several, or only labkit's technical contract; the assignment is written with it, and a count follows the assignment. Reality is not cut into several findings so that each names one rule. A finding that a check is left open names the finding that left it open, so one cause stays one finding:

```
shared reader: metrics.json missing
  → precondition: this reported run requires it
      → one finding: a required run file is missing
          → report ↔ stored number: open, because of that finding
          → recomputation ↔ stored number: open, because of the same finding
```

A rule can be checked by several checks, and a check can serve several rules. All mechanical checks passing covers the part of a rule they test, nothing more.

## What is decided, what waits

Decided: distinguishable failure causes, carried from the reader to the message — worth doing with or without a check register. Waiting for a shown need: shared precondition checks with declared dependencies, the full structure above in code. `not applicable` exists today as a gate's note (`n/a — …`, `labkit/gates/finalize.py:459`); it is told, not counted.
