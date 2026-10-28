
<!-- labkit discussed
protocol = "experiments/01-apply-screen/PROTOCOL-apply-screen.md"
run = "2026-10-28T16-41-45_a802"
why = "Measurement unable to complete formal adoption due to technical blockers in analysis audit and check script."
-->
Run 2026-10-28T16-41-45_a802 — discussed, not reported: Measurement unable to complete formal adoption due to technical blockers in analysis audit and check script.
<!-- /labkit discussed -->

## Investigation Summary

An analysis audit identified that ScreeningModel.probability() at line 196 was computing standardisation as `(v - mu) / sd**2` when the registration required `(v - mu) / sd`. The code was corrected.

Multiple measurement iterations with the fixed code were conducted. Technical blockers in the analysis audit completion and check script configuration prevented formal adoption of the result. The experiment remains open without a reported conclusion.
