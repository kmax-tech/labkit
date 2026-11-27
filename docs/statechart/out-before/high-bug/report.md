# AreaLifecycle

TLC reached more states than the chart budget of 5000, so the chart draws only the bug paths: 12 states and 10 arrows.
The chart does not draw 2 steps that stay in one chart state.

## CommittedNumberFromDataAsRun breaks
The shortest path has 12 steps:
0. Work Registration open, Last commit Commit: nothing registered
1. protocol-fill writes the registration: Work Registered, nothing measured, Last commit Commit: nothing registered
2. labkit-audit --mode preflight: Work Preflight findings undecided, Last commit Commit: nothing registered
3. labkit-audit --decide (preflight): Work Preflight decided, not frozen, Last commit Commit: nothing registered
4. protocol-fill --freeze: Work Frozen, nothing measured, Last commit Commit: nothing registered
5. you start a measurement: Work Measurement in progress, Last commit Commit: nothing registered
6. you change a data file outside the area: Work Measurement in progress, Last commit Commit: nothing registered
7. the run completes: Work Measured, not audited, Last commit Commit: nothing registered
8. labkit-audit --mode analysis: Work Audit findings undecided, Last commit Commit: nothing registered
9. labkit-audit --decide: Work Ready to adopt, Last commit Commit: nothing registered
10. labkit-adopt: Work Adopted, input changed since the run, Last commit Commit: nothing registered
11. labkit-audit --report-review: Work Adopted, input changed since the run, Last commit Commit: nothing registered
12. git commit (hook passes): Work Adopted, input changed since the run, Last commit Commit: number on changed input

## Rules not checked
CommittedNumberFromCompletedNewestRun, CommittedNumberFromMeasurement, CommittedNumberFromCodeAsRun, CommittedNumberFromAreaDataAsRun, CommittedNumberUnderItsRegistration, CommittedNumberOnCommittedRegistration, CommittedNumberMeasuredFrozen, CommittedNumberAudited, CommittedReleasedBlockerReviewed, CommittedReportNumberAdopted, CommittedResultReportReviewed, CommittedMeasurementHasReport, NoMeasurementWithoutRegistration
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked these rules in every state.
