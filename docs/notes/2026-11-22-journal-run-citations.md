# A working note that names the current answering run (2026-11-22)

**Question.** A thesis journal names runs to record the week's state, without reporting their results. What does the pre-commit hook do with such a file?

**Finding.** A plain mention of the run a protocol currently answers with requires, even without any number, a generated result block or a model review of the text; after adoption the discussion route is refused. A run id in a Markdown file makes the file a report for `report-check` (`report_hold.report_files`, `labkit/gates/report_hold.py:268`). No change to labkit follows from this note; the open question is below.

## How it was reproduced

`docs/examples/count-walkthrough.sh` stamped a lab repo and walked the count task to adoption, with the editable labkit 0.114.0 at 6c1d0edc. One run (`2026-11-22T15-58-41_98ed`); commit `bdfa025` holds it unadopted, commit `5240fb9` adopted. For each state and case, a fresh `journal.md` at the repository root was staged and committed alone; the pre-commit hook judged it.

| `journal.md` names …                                       | before adoption                                                                                                | after adoption                                                             |
|------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| the run with a number ("mean 3.5 documents")               | blocked: the answering run cited while the protocol adopted no result (`promotions`)                           | blocked: an adopted result cited without its generated block               |
| the run without a number ("the inputs need a second look") | blocked, same reason                                                                                           | blocked, same reason                                                       |
| the run in a discussion block (`protocol-fill --discuss`)  | blocked: the discussed report owes a report review of its state (`labkit-audit --report-review`, a model call) | not writable: `protocol-fill --discuss` refuses an adopted result (exit 2) |
| an invented run id                                         | warnings only                                                                                                  | warnings only                                                              |
| numbers and no run id ("n=100 cases by week 49")           | nothing                                                                                                        | nothing                                                                    |

In the state after adoption every commit also met a second blocker: the area's own test failed (`test_01_docs_per_case.py`, 2 of 3). It is unrelated to the journal and its cause is not examined; the journal blocker stands beside it in the log.

Not covered: runs other than the current answering run. `promotions` exempts an older run, a probe and an acknowledged unfrozen run (`labkit/gates/report_hold.py:895`); those were not tried. Only `repeat_cost = "low"` and a computation were tried.

## What the code says

- An invented id in prose warns as static evidence; in a generated block it blocks (`report_blocks.cited_gaps`, `labkit/checks/report_blocks.py:439`).
- The numbers hint (`unsourced_numbers`) reports every number of the file once it counts as a report, a calendar week included.

## Consequence so far

The thesis starter in the author's dotfiles now asks the journal to point to an experiment by its area and protocol, not by a run id, and keeps result blocks out of the journal, where a newer adoption would make them stale (dotfiles 45f03cf). This avoids the limit; it does not settle it. Pointing to the protocol loses which run a meeting discussed: the commit keeps the protocol's state, but the answering run then and the run discussed can differ.

## Open question for labkit

Should a factual mention of a run, without a result claim, owe a result block or a model review? The mention is the search signal that lets `report-check` find a number in an unregistered note (LAB-104 A number leaves the area only through its adoption); narrowing it to registered reports would let an unregistered report pass. Candidates, none chosen: limit the numbers hint to numbers near a run id; a cheaper route for a working note that names a run. Collect further cases before deciding.
