# Adopting a documented analysis correction on unchanged answers

Task, 2026-11-24, for a separate labkit session. Not built yet. First question: does labkit already support this through a separate analysis run? Only if it does not: a concrete extension proposal with tests, presented to the author before it is built.

## The case

argmining27, experiment 14 (`experiments/14-fixed-scenario-cross-rating`), labkit `v0.115.0`.

| Run                        | Kind                                   | Code      | What it did                                                                       |
|----------------------------|----------------------------------------|-----------|-----------------------------------------------------------------------------------|
| `2026-11-24T12-28-53_aa0a` | `measurement`                          | `1d3d170` | 6 144 model answers into `output/fixed-scenario-cross-rating.jsonl`, then metrics |
| `2026-11-24T14-22-02_2b96` | `measurement`, `derived_from` = `aa0a` | `bf0bfc7` | the same answers evaluated again, no model call                                   |

The analysis audit `audits/2026-11-24T13-33-analysis.toml` found two implementation faults in the evaluation, not in the measurement:

1. `paired_draw_interval` read the lower bootstrap bound one rank too high (`int(0.025 * n)` instead of the nearest rank `ceil(0.025 * n) - 1`).
2. The inputs were not held to the digests the protocol registers.

Both were repaired in `scripts/01_measure.py` (commit `bf0bfc7`), declared as a protocol step (`--builds-on aa0a --step-id audit-repair-reevaluate --occasion repair`), and the answers were evaluated again in the derived run `2b96`. Result: of 64 interval bounds one changed in the fifth decimal, no reading changed, the kept number stayed 10.

`finalize` blocks `2b96`: `scripts/01_measure.py changed since 2026-11-24T12-28-53_aa0a ran it — its number came from other code (LAB-041)`, and its only way out is to measure anew. `02_analyze.py --check` refuses likewise. A new measurement would mean 6 144 paid calls only to clear a fault in the arithmetic, and it would replace the answers the audit looked at.

## What the person requires

- The original answers and the original run record stay unchanged.
- Old and new evaluation code can both be traced (which commit computed which number).
- A change to the prompts, to the rule that reads an answer (for example `parse_letter`), and to the metrics is told apart explicitly. Only the last may pass on unchanged answers; the first two change what was measured and keep needing a new measurement.
- No blanket release of changed measurement scripts.

## Questions for the investigation

1. Does a supported path exist today? Candidates to check: `derived_from` with the evaluation moved into a script of its own (so the measuring script stays byte-identical to the parent's), `--reported-through` / an analysis run that names the measurement as its input, `02_analyze.py --check --run`, `labkit-adopt` on a derived run. For each: what `finalize`, `report-check` and `labkit-adopt` say, and whether the number would be adopted. Show it on a copy of the experiment 14 area or a small fixture, never on the live area.
2. If none fits: which check refuses, and on what evidence? (`finalize` and `recheck` compare the parent's script to the current one; find the lines.)
3. How can labkit tell "only the evaluation changed" from "the measurement changed" without trusting the author's word? Options to weigh: a declared split of the script into a measuring part (prompts, answer reading, model calls) and an evaluating part, each with its own digest; a recorded digest of the answer file plus a proof that the derived run read exactly those bytes; a diff restricted to named functions. Say what each option costs a lab and which faults it would let through.
4. How is the correction shown in the result? The adopted run, its parent, both code commits, the audit finding it repairs, and the numbers that changed.

## Acceptance for a proposal

- A test where only the evaluation changes: the derived run is adopted, the parent's record and answer file stay byte-identical, and the adopted result names both commits and the finding.
- A test where the prompt changes: refused, with the way out "measure anew".
- A test where the answer-reading rule changes (for example `parse_letter`): refused, with the same way out.
- A test where the answer file changed after the parent run: refused.
- The existing tests stay green; no change to standards or rule texts without the author's decision.

## Not in this task

- No change in argmining27 and no model call. Experiment 14 waits for the result; it is neither adopted nor handed over in the meantime.
- No change to the global release rule (separate decided task in `TODO.md`).
