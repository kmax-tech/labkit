# AreaLifecycle

TLC reached more states than the chart budget of 500, so the chart draws only the bug paths: 12 states and 10 arrows.

## CommittedNumberFromDataAsRun breaks
The shortest path has 10 steps:
0. Work Registration open, Last commit Commit: nothing measured
1. protocol-fill writes the registration: Work Registered, nothing measured, Last commit Commit: nothing measured
2. you start the run: Work Run in progress, Last commit Commit: nothing measured
3. the run completes: Work Measured, not audited, Last commit Commit: nothing measured
4. labkit-audit --mode analysis: Work Audit findings undecided, Last commit Commit: nothing measured
5. labkit-audit --decide: Work Ready to adopt, Last commit Commit: nothing measured
6. labkit-adopt: Work Adopted, report review owed, Last commit Commit: nothing measured
7. labkit-audit --report-review: Work Adopted, report reviewed, Last commit Commit: nothing measured
8. git commit (hook passes): Work Adopted, report reviewed, Last commit Commit: adopted number, reviewed
9. you change a data file outside the area: Work Adopted, input changed since the run, Last commit Commit: adopted number, reviewed
10. git commit (hook passes): Work Adopted, input changed since the run, Last commit Commit: number on changed input

## Rules not checked
CommittedNumberFromCompletedNewestRun, CommittedNumberFromCodeAsRun, CommittedNumberUnderItsRegistration, CommittedNumberAudited, CommittedReleasedBlockerReviewed, CommittedReportNumberAdopted, CommittedResultReportReviewed, CommittedMeasurementHasReport, NoRunWithoutRegistration
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked these rules in every state.
