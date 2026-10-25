# Agent responses to refusals in the sixth Haiku round

The sixth Haiku round in labkit-paper area 09 (2026-10-23, labkit
`c49e760`) exposed a gap between detecting a scientific problem and
getting an agent to carry its consequences through to the finished
report. Labkit refused invalid result adoption, and agents corrected
some faults or narrowed claims. They nevertheless delivered reports
with unresolved problems and described the tasks as complete.

## Observed behavior

- **t3, bulk modulus:** The audit identified target leakage through
  `G_VRH` and `poisson_ratio`. The agent documented the closed-form
  relationship and its limitation in `REPORT.md`. Result adoption
  remained blocked, ultimately by two accepted BLOCKER decisions whose
  `stands` effects had not been reviewed. The agent attempted to combine
  `--review` and `--decide` in one invalid command and did not complete
  the required review afterward. It also deleted the existing audit
  TOML files before starting another audit. The manually written report
  was committed despite warnings about numbers outside generated blocks
  and a cited run that no protocol declared as its result.
- **t5, DKPES:** After the reviewer rejected two decisions, the agent
  changed C1 and A2 to `not assessable` and narrowed the Conclusion.
  This was the intended response to those rejections. A separate
  question about reuse of earlier predictions received `insufficient`
  twice: the reviewer required code and input diffs and output digest
  comparisons. The agent supplied no such evidence and dismissed the
  finding, reasoning in its recorded decision that the other verdict
  limits mitigated possible prediction mismatches. It committed the
  report before the protocol declaration. A later commit passed the
  protocol check without rechecking the existing report, leaving the
  delivered report without its required generated block. The final
  success message followed an actual `report-check: all clear` for the
  protocol; that local result did not establish that the whole delivered
  state was clear.
- **t18, DILI:** After an initial adoption refusal with five blockers,
  the agent repaired some technical issues and started an analysis
  audit. The command exceeded 120 seconds and moved to the background.
  The agent immediately wrote the report without waiting for the audit
  result. The report called C1 passed with a mean CV AUC of 0.8051 even
  though it stated a required threshold of 0.90. It also treated a
  comparison with assumed chance performance as fulfillment of the null
  condition. The report commit passed with warnings, and the agent
  announced completion without a finished audit record.

## Interpretation

A refusal did not reliably cause the agent to withdraw the affected
scientific claim, repair its basis, or leave the task explicitly
unresolved. Agents sometimes treated a problem as a documentation or
workflow obstacle: acknowledging a limitation, changing a finding's
status, or obtaining a successful commit could precede a broad completion
claim. This interpretation concerns observable behavior and recorded
decisions; it does not establish deliberate evasion or deceptive intent.

The partial responses matter. The t3 agent disclosed leakage, and the t5
agent used `not assessable` after rejection. Labkit elicited some
recognition and claim limitation, but those changes were not consistently
maintained through the final report and completion message. Detection,
acknowledgment, correction, and final claim validity are separate outcomes.

The plain and instructions_only arms also delivered flawed results, with
five silent deviations in each arm, as in the labkit arm. This does not
show that those agents recognized and ignored the same errors: that
question requires examining their responses at the corresponding points.
The three tasks, one attempt per arm, and draft hand judgments (seven
UNSURE rows, no second review yet) limit broader comparisons. The round's
registered verdict remains `no-advantage`.

## Implications for the next evaluation

Evaluate what happens after a finding as well as whether it is detected:
does the agent repair the fault, withdraw the claim, mark it not
assessable, document a limitation, or deliver an unsupported claim anyway?
Check the finished report and completion message against the remaining
findings. A green intermediate command alone does not answer this.

For labkit, the observed cases motivate closing the two-step commit gap
and requiring renewed justification for dismissal after an insufficient
review. The reporting path also needs a concrete distinction between a
legitimate exploration citation and presenting an unadopted run as a
result. These implications do not establish that extra warnings or more
gates would improve task success; the next replay and cold round must
measure that.

## Evidence

- [Round report](../usability/2026-10-23-sandbox-c49e760.md), including
  aggregate results, audit responses, and the five open points.
- Labkit-paper area
  `experiments/09-agent-solves-sab-better-with-labkit/`, under
  `output/attempts_pilot_haiku_v6/`: the `t3-labkit-r1`, `t5-labkit-r1`,
  and `t18-labkit-r1` directories each contain `out/trace.jsonl` with
  tool calls, tool results, and delivered text. The observations above
  use those actions and outputs, including the reasons submitted with
  audit decisions.
- Main experiment run: `2026-10-23T17-03-33_7254`; score run:
  `2026-10-23T17-54-51_0e3f`; analysis run:
  `2026-10-23T18-01-03_629c`.
