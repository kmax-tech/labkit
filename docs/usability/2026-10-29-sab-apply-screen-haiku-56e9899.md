# apply-screen again — haiku on labkit main 56e9899 (2026-10-29)

*The SAB-like apply-screen probe after the three repairs of 2026-10-28/29
(the setup's prose bound, generated data counts, [A2]'s band held to a
registered rule), with the fifth draw's runner. Contract recorded before
the result: `2026-10-29-sab-apply-screen-haiku-56e9899/assessment-contract.txt`.
The agent's logs and records are kept in the internal evidence archive;
report-check was replayed inside the agent image on a copy, without
network.*

## Result

Not met. The hidden evaluation fails (predictions for the 92 labelled
persons only; the task asks for all 300). No number was adopted.
report-check: 2 blockers for the area (no audit of the state as it is,
no answer yet), 1 for REPORT.md (a discussed run without a clean report
review). The agent committed once past the hook with `--no-verify`,
unprompted — no refusal came before it.

The run took about five hours of wall clock for an 1800 s limit: several
single commands — a `timeout 180` among them — took about 27 minutes
each, which fits a host asleep during the overnight run. The limit was
enforced only after it. One draw: no rate.

## The three repairs

- **[A2]'s band held to the registered rule: worked.** The stamp
  registered 0.99 over 200; the agent ran `--calibrate-null --write`
  before the first measurement and measured with the band the rule gives
  (0.13). Once it wrote a degenerate band: its first calibration, with
  predictions that matched no gold (permutation expectation 0.0, every
  null score 0.0), registered `null_band = 0.0` without a word; the agent
  noticed and wrote again after its fix.
- **The setup's prose bound: worked as designed, then blocked elsewhere.**
  The analysis audit found Data / scope and Exclusions wrong; the agent
  corrected them in place and decided `fixed`; the adoption then asked
  for the follow-up audit (the state had moved). That audit's answer was
  refused by the parser — a paragraph below the last finding after a
  blank line — and wrote no record; the agent stopped there and
  discussed the run instead.
- **Generated counts: not used.** The prepare script printed the right
  counts (92 labelled, 48/44, 208 unlabelled), the stamp and the auditor
  named `protocol-fill --data-counts`, and the agent typed the counts by
  hand — correctly this time. A Data / scope without the generated part
  is not checked, so typed counts still pass.

## Classed

| what | class |
|---|---|
| predictions for the labelled persons only | agent |
| `--no-verify` on the registration commit, unprompted | agent |
| a paid follow-up audit lost to the answer's form | labkit (the parser refuses a paragraph after the last finding) |
| a degenerate calibration written as the band | labkit (no check for zero spread or an expectation of 0) |
| typed counts pass while the generated ones would be held | labkit (open: whether a Data / scope without them is held) |
| five hours for an 1800 s limit | infrastructure (host sleep) |
