# AreaLifecycle

TLC reached more states than the chart budget of 5000, so the chart draws only the bug paths: 13 states and 11 arrows.

## CommittedNumberFromDataAsRun breaks
The shortest path has 11 steps:
0. Work Registration open, Last commit Commit: nothing registered
1. protocol-fill writes the registration: Work Registered, nothing measured, Last commit Commit: nothing registered
2. git commit (hook passes): Work Registered, nothing measured, Last commit Commit: registration
3. you start a measurement: Work Measurement in progress, Last commit Commit: registration
4. the run completes: Work Measured, not audited, Last commit Commit: registration
5. labkit-audit --mode analysis: Work Audit findings undecided, Last commit Commit: registration
6. labkit-audit --decide: Work Ready to adopt, Last commit Commit: registration
7. labkit-adopt: Work Adopted, report review owed, Last commit Commit: registration
8. labkit-audit --report-review: Work Adopted, report reviewed, Last commit Commit: registration
9. git commit (hook passes): Work Adopted, report reviewed, Last commit Commit: adopted number, reviewed
10. you change a data file outside the area: Work Adopted, input changed since the run, Last commit Commit: adopted number, reviewed
11. git commit (hook passes): Work Adopted, input changed since the run, Last commit Commit: number on changed input

## Rules not checked
CommittedNumberFromCompletedNewestRun, CommittedNumberFromMeasurement, CommittedNumberFromCodeAsRun, CommittedNumberFromAreaDataAsRun, CommittedNumberUnderItsRegistration, CommittedNumberOnCommittedRegistration, CommittedNumberMeasuredFrozen, CommittedNumberAudited, CommittedReleasedBlockerReviewed, CommittedReportNumberAdopted, CommittedResultReportReviewed, CommittedMeasurementHasReport, NoMeasurementWithoutRegistration
After the first break, each TLC run stops at 100,000 distinct states. A run reached that bound before it checked these rules in every state.
