# apply-screen with Sonnet — the same setting on labkit main 56e9899 (2026-10-29)

*The Haiku apply-screen run of the same day
(`2026-10-29-sab-apply-screen-haiku-56e9899.md`), repeated with Claude
Sonnet 5.5 as the agent: same labkit wheel, probe, runner and 1800 s
limit. The runner rebuilt the agent image (labkit-sandbox:8ce976250133
instead of c5e9959d714c); labkit inside the probe is the same wheel.
Contract recorded before the result:
`2026-10-29-sab-apply-screen-sonnet-56e9899/assessment-contract.txt`.
Logs and records are kept in the internal evidence archive; report-check
was replayed in the agent image on a copy, without network.*

## Result

Contract met, with no confirmed claim. The hidden evaluation passes: all
300 persons are predicted by the unchanged model. One number is adopted
in 278 s and 25 turns ($0.63). report-check reports the area as all clear
and REPORT.md with 0 blockers and one static-evidence warning. No commit
went past the hook and no record was edited by hand.

[C1] stays not assessable. The agent wrote "margin 0.2" in the criterion,
the sentence and the Terms, but left the constant at the stamp's example
value 0.25. The first measurement then bound both values. The analysis
audit found this as a BLOCKER. The agent accepted it as its own invalid
registration, with the effect "C1 not assessable". It reported the
accuracy (70/92) as a description only and named a successor protocol as
the next step. The pass under either bar rests on one person.

## The three repairs

- **[A2]'s band held to the registered rule: worked.** The agent ran
  `--calibrate-null --write` once before the commit and measured with the
  band the rule gives (0.13, the same value as Haiku's).
- **Generated counts: used.** The agent ran `protocol-fill --data-counts`
  after the preparation run. Data / scope carries the agent's own source
  description followed by the generated counts.
- **The setup's prose bound: not exercised.** No finding asked for a
  correction of the setup.

## Classed

| what | class |
|---|---|
| margin 0.2 in the prose, 0.25 in the constant | agent; mechanically detectable, nothing checks it before the first measurement |
| the first analysis audit lost to the answer's form (a paragraph below the last finding) | labkit; second run in a row, Sonnet repeated the call |
| a constant-copy warning on the untouched stamp (`null_band_quantile = None`) | labkit, from 56e9899; fixed in 78bc969 |

One draw per model: the pair is no comparison of rates.
