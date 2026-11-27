---------------------------- MODULE AreaLifecycle ----------------------------
(***************************************************************************)
(* One experiment area under labkit: one protocol at repeat cost low, its  *)
(* registered report, and the git commits that hold them.                  *)
(*                                                                         *)
(* Each action is a command the author runs. Its guard is what the command *)
(* checks, read from the gate's stations (docs/gate-stations.md) and code. *)
(* The INVARIANTs are the workflow's promises (docs/workflow.md), stated   *)
(* on the last commit: labkit promises them where the commit hook holds.   *)
(*                                                                         *)
(* A model, not the code: a broken rule here is a path to replay against   *)
(* the real commands before it counts as a finding.                        *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS MaxRuns, MaxEdits

VARIABLES
    reg,            \* "open" | "written": the registration fields
    regVer,         \* version of the registration text
    code,           \* version of the measurement code (area scripts, lib/ helpers)
    data,           \* version of a data input outside the area, not in a promise's scope
    runs,           \* number of runs started; the newest is the answering run
    run,            \* "none" | "running" | "completed" | "crashed": the newest run
    runAt,          \* what the newest run measured under: [code, data, reg]
    audit,          \* "none" | "findings" | "decided": the analysis audit
    auditAt,        \* what the audit record is bound to: [run, code]
    reviewOwed,     \* a decision released a BLOCKER (limitation/false-positive)
    reviewed,       \* the decision review upheld it
    adopted,        \* 0, or the run the protocol declares as its result
    report,         \* "none" | "progress" | "result" | "handover": the registered report
    reportReviewed, \* the report review of its final text named no claim
    cm              \* the last commit: a snapshot of the above

work == <<reg, regVer, code, data, runs, run, runAt, audit, auditAt,
          reviewOwed, reviewed, adopted, report, reportReviewed>>
vars == <<work, cm>>

Snap == [reg |-> reg, regVer |-> regVer, code |-> code, data |-> data,
         runs |-> runs, run |-> run, runAt |-> runAt, audit |-> audit,
         auditAt |-> auditAt, reviewOwed |-> reviewOwed, reviewed |-> reviewed,
         adopted |-> adopted, report |-> report, reportReviewed |-> reportReviewed]

Init ==
    /\ reg = "open" /\ regVer = 0 /\ code = 0 /\ data = 0
    /\ runs = 0 /\ run = "none" /\ runAt = [code |-> 0, data |-> 0, reg |-> 0]
    /\ audit = "none" /\ auditAt = [run |-> 0, code |-> 0]
    /\ reviewOwed = FALSE /\ reviewed = FALSE
    /\ adopted = 0 /\ report = "none" /\ reportReviewed = FALSE
    /\ cm = Snap

(***************************************************************************)
(* The gates as predicates: checks are pure, they write nothing.           *)
(***************************************************************************)

\* finalize.finalize_area (labkit/gates/finalize.py)
FinalizeClean ==
    /\ run = "completed"          \* 1. answering run
    /\ runAt.reg = regVer         \* 2. the registration as the first measurement recorded it
    /\ runAt.code = code          \* 4. the run's code and the declared scopes
    /\ runAt.data = data          \* 6. provenance: each data input against the recorded bytes

\* report_check.chain_gaps for a declared run D (labkit/gates/report_check.py)
ChainClean(D, withReport) ==
    /\ D = runs                   \* 1. declaration: the declared run is the answering run
    /\ reg = "written"            \* 2. registration
    /\ FinalizeClean              \* 3. finalize
    /\ audit /= "none"            \* 5. analysis: an audit bound to this run and code
    /\ auditAt = [run |-> runs, code |-> code]
    /\ audit = "decided"          \* 7. decisions, and the review a released BLOCKER owes
    /\ (reviewOwed => reviewed)
    /\ (withReport => report = "result" /\ reportReviewed)   \* 8. report, with its review

\* report_check.hold_changed_paths: the stop and the commit. It runs only for
\* areas the changed paths reach (scope_sha.areas_touched): files in the
\* area, a promise's scope, bound validation, lib/ or src/ modules the code
\* imports, and a report that registers or cites the protocol.
AreaTouched ==
    \/ reg /= cm.reg \/ regVer /= cm.regVer \/ code /= cm.code
    \/ runs /= cm.runs \/ run /= cm.run \/ audit /= cm.audit
    \/ auditAt /= cm.auditAt \/ reviewOwed /= cm.reviewOwed
    \/ reviewed /= cm.reviewed \/ adopted /= cm.adopted
    \/ report /= cm.report \/ reportReviewed /= cm.reportReviewed

\* hold_declared_result: a declared result is held to the whole chain; an
\* undeclared protocol only to its registered report (hold_registered_report)
Hold ==
    IF ~AreaTouched THEN TRUE
    ELSE IF adopted /= 0 THEN ChainClean(adopted, TRUE)
    ELSE runs > 0 => report \in {"progress", "handover"}

(***************************************************************************)
(* The commands.                                                           *)
(***************************************************************************)

\* protocol-fill PROTOCOL "field=..."; after a measurement it is a new version
WriteRegistration ==
    /\ IF runs = 0 THEN reg = "open" ELSE regVer < MaxEdits
    /\ reg' = "written"
    /\ regVer' = IF runs > 0 THEN regVer + 1 ELSE regVer
    /\ UNCHANGED <<code, data, runs, run, runAt, audit, auditAt, reviewOwed,
                   reviewed, adopted, report, reportReviewed, cm>>

\* an edit of an area script or of a lib/ helper it imports
EditCode ==
    /\ code < MaxEdits
    /\ code' = code + 1
    /\ UNCHANGED <<reg, regVer, data, runs, run, runAt, audit, auditAt,
                   reviewOwed, reviewed, adopted, report, reportReviewed, cm>>

\* a data file outside the area that the run reads, not declared in scope
EditOutsideData ==
    /\ data < MaxEdits
    /\ data' = data + 1
    /\ UNCHANGED <<reg, regVer, code, runs, run, runAt, audit, auditAt,
                   reviewOwed, reviewed, adopted, report, reportReviewed, cm>>

\* the measurement script; hook_pre_run.before_run and runlog's start check
\* refuse a full run while a low registration field is open
StartRun ==
    /\ reg = "written"
    /\ run /= "running"
    /\ runs < MaxRuns
    /\ runs' = runs + 1
    /\ run' = "running"
    /\ runAt' = [code |-> code, data |-> data, reg |-> regVer]
    /\ UNCHANGED <<reg, regVer, code, data, audit, auditAt, reviewOwed,
                   reviewed, adopted, report, reportReviewed, cm>>

RunCompletes ==
    /\ run = "running" /\ run' = "completed"
    /\ UNCHANGED <<reg, regVer, code, data, runs, runAt, audit, auditAt,
                   reviewOwed, reviewed, adopted, report, reportReviewed, cm>>

RunCrashes ==
    /\ run = "running" /\ run' = "crashed"
    /\ UNCHANGED <<reg, regVer, code, data, runs, runAt, audit, auditAt,
                   reviewOwed, reviewed, adopted, report, reportReviewed, cm>>

\* labkit-audit AREA --mode analysis: earlier undecided findings first
AnalysisAudit ==
    /\ run = "completed"
    /\ audit /= "findings"
    /\ audit' = "findings"
    /\ auditAt' = [run |-> runs, code |-> code]
    /\ reviewOwed' = FALSE /\ reviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, adopted,
                   report, reportReviewed, cm>>

\* labkit-audit AREA --decide N STATUS; a released BLOCKER owes a review
Decide ==
    /\ audit = "findings"
    /\ audit' = "decided"
    /\ reviewOwed' \in BOOLEAN
    /\ reviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, auditAt,
                   adopted, report, reportReviewed, cm>>

\* labkit-audit AREA --review
DecisionReview ==
    /\ reviewOwed /\ ~reviewed
    /\ reviewed' = TRUE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, audit, auditAt,
                   reviewOwed, adopted, report, reportReviewed, cm>>

\* labkit-adopt AREA: step 1 keeps the proposal only when report-check passes
\* on it without the report station; step 2 writes the result block
Adopt ==
    /\ adopted /= runs
    /\ ChainClean(runs, FALSE)
    /\ adopted' = runs
    /\ report' = "result"
    /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, audit, auditAt,
                   reviewOwed, reviewed, cm>>

\* labkit-audit AREA --report-review REPORT
ReportReview ==
    /\ report = "result" /\ ~reportReviewed
    /\ reportReviewed' = TRUE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, audit, auditAt,
                   reviewOwed, reviewed, adopted, report, cm>>

\* protocol-fill PROTOCOL --discuss RUN --into REPORT: the progress account
ProgressAccount ==
    /\ runs > 0 /\ adopted = 0 /\ report /= "progress"
    /\ report' = "progress" /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, audit, auditAt,
                   reviewOwed, reviewed, adopted, cm>>

\* protocol-fill PROTOCOL --withdraw --into REPORT
Withdraw ==
    /\ adopted /= 0
    /\ adopted' = 0 /\ report' = "none" /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, audit, auditAt,
                   reviewOwed, reviewed, cm>>

\* protocol-fill PROTOCOL --handover --into REPORT
Handover ==
    /\ runs > 0 /\ adopted = 0 /\ report /= "handover"
    /\ report' = "handover" /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, code, data, runs, run, runAt, audit, auditAt,
                   reviewOwed, reviewed, adopted, cm>>

\* git commit of every change; the pre-commit hook holds
Commit ==
    /\ Snap /= cm
    /\ Hold
    /\ cm' = Snap
    /\ UNCHANGED work

Next ==
    \/ WriteRegistration \/ EditCode \/ EditOutsideData
    \/ StartRun \/ RunCompletes \/ RunCrashes
    \/ AnalysisAudit \/ Decide \/ DecisionReview
    \/ Adopt \/ ReportReview \/ ProgressAccount \/ Withdraw \/ Handover
    \/ Commit

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* The promises (docs/workflow.md), on what the last commit holds.         *)
(***************************************************************************)

\* "The protocol's declared result must be its answering run."
CommittedNumberFromCompletedNewestRun ==
    cm.adopted /= 0 => cm.run = "completed" /\ cm.adopted = cm.runs

\* step 4: "a real implementation repair needs a new run"
CommittedNumberFromCodeAsRun ==
    cm.adopted /= 0 => cm.runAt.code = cm.code

\* step 4: provenance, "each data input against the bytes its run recorded"
CommittedNumberFromDataAsRun ==
    cm.adopted /= 0 => cm.runAt.data = cm.data

\* "A confirmatory protocol is held to the registration of its first measurement."
CommittedNumberUnderItsRegistration ==
    cm.adopted /= 0 => cm.runAt.reg = cm.regVer

\* step 5: "Both repeat costs require analysis review before release."
CommittedNumberAudited ==
    cm.adopted /= 0 =>
        /\ cm.audit = "decided"
        /\ cm.auditAt = [run |-> cm.adopted, code |-> cm.code]

\* step 6: a decision that releases a BLOCKER is upheld by a second reviewer
CommittedReleasedBlockerReviewed ==
    cm.adopted /= 0 /\ cm.reviewOwed => cm.reviewed

\* step 8: the report's number is the adopted one
CommittedReportNumberAdopted ==
    cm.report = "result" => cm.adopted /= 0

\* step 8: a registered report "still owes review of its final text"
CommittedResultReportReviewed ==
    cm.report = "result" => cm.reportReviewed

\* step 8: "A missing registered report after measurement holds the stop."
CommittedMeasurementHasReport ==
    cm.runs > 0 => cm.report /= "none"

\* step 2: no measurement starts while the registration is open
NoRunWithoutRegistration ==
    runs > 0 => reg = "written"

=============================================================================
