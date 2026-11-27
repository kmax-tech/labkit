---------------------------- MODULE AreaLifecycle ----------------------------
(***************************************************************************)
(* One experiment area under labkit: one protocol at repeat cost LANE      *)
(* ("low" or "high"), its registered report, and the git commits that hold *)
(* them.                                                                   *)
(*                                                                         *)
(* Each action is a command the author runs. Its guard is what the command *)
(* checks, read from the gate's stations (docs/gate-stations.md) and code. *)
(* The INVARIANTs are the workflow's promises (docs/workflow.md), stated   *)
(* on the last commit where the commit hook is what promises them.         *)
(*                                                                         *)
(* A model, not the code: a broken rule here is a path to replay against   *)
(* the real commands before it counts as a finding.                        *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS Lane, MaxRuns, MaxEdits

ASSUME Lane \in {"low", "high"}

VARIABLES
    reg,            \* "open" | "written": the registration fields
    regVer,         \* version of the registration text
    preflight,      \* "none" | "findings" | "decided": the preflight audit (high)
    frozen,         \* the protocol's `frozen = true` (high)
    code,           \* version of the measurement code (area scripts, lib/ helpers)
    data,           \* version of a data input outside the area, not in a promise's scope
    areaData,       \* version of a data input inside the area (data/prepared/)
    runs,           \* number of runs started; the newest is the answering run
    run,            \* "none" | "running" | "completed" | "crashed": the newest run
    runAt,          \* what the newest run was started under
    audit,          \* "none" | "findings" | "decided": the analysis audit
    auditAt,        \* what the audit record is bound to: [run, code]
    reviewOwed,     \* a decision released a BLOCKER (limitation/false-positive)
    reviewed,       \* the decision review upheld it
    adopted,        \* 0, or the run the protocol declares as its result
    report,         \* "none" | "progress" | "result" | "handover": the registered report
    reportReviewed, \* the report review of its final text named no claim
    cm              \* the last commit: a snapshot of the above

work == <<reg, regVer, preflight, frozen, code, data, areaData, runs, run, runAt, audit,
          auditAt, reviewOwed, reviewed, adopted, report, reportReviewed>>
vars == <<work, cm>>

Snap == [reg |-> reg, regVer |-> regVer, preflight |-> preflight,
         frozen |-> frozen, code |-> code, data |-> data, areaData |-> areaData,
         runs |-> runs,
         run |-> run, runAt |-> runAt, audit |-> audit, auditAt |-> auditAt,
         reviewOwed |-> reviewOwed, reviewed |-> reviewed, adopted |-> adopted,
         report |-> report, reportReviewed |-> reportReviewed]

NoRun == [kind |-> "none", code |-> 0, data |-> 0, areaData |-> 0, reg |-> 0,
          frozen |-> FALSE, regCommitted |-> FALSE, preflightDecided |-> FALSE]

Init ==
    /\ reg = "open" /\ regVer = 0 /\ preflight = "none" /\ frozen = FALSE
    /\ code = 0 /\ data = 0 /\ areaData = 0
    /\ runs = 0 /\ run = "none" /\ runAt = NoRun
    /\ audit = "none" /\ auditAt = [run |-> 0, code |-> 0]
    /\ reviewOwed = FALSE /\ reviewed = FALSE
    /\ adopted = 0 /\ report = "none" /\ reportReviewed = FALSE
    /\ cm = Snap

(***************************************************************************)
(* The gates as predicates: checks are pure, they write nothing.           *)
(***************************************************************************)

\* the registration as the last commit holds it (start_check._committed_registration)
RegCommitted == cm.reg = "written" /\ cm.regVer = regVer

\* start_check.freeze_gate for run_kind = "measurement": an undecided
\* preflight BLOCKER refuses first; then the lane's gaps (_freeze_findings):
\* the committed registration at low, the freeze at high
MeasurementMayStart ==
    /\ preflight /= "findings"
    /\ IF Lane = "low" THEN reg = "written" /\ RegCommitted ELSE frozen

\* finalize.finalize_area (labkit/gates/finalize.py)
FinalizeClean ==
    /\ run = "completed"          \* 1. answering run
    /\ runAt.reg = regVer         \* 2. the registration as the first measurement recorded it
    /\ runAt.code = code          \* 4. the run's code and the declared scopes
    /\ (Lane = "low" => runAt.data = data /\ runAt.areaData = areaData)
                                  \* 6. provenance, at low only (finalize.py:1338)

\* report_check.chain_gaps for a declared run D (labkit/gates/report_check.py)
ChainClean(D, withReport) ==
    /\ D = runs                   \* 1. declaration: the declared run is the answering run
    /\ IF Lane = "high"           \* 2. the freeze where the lane owes it,
       THEN frozen                \*    else the registration committed at the first measurement
       ELSE runAt.regCommitted
    /\ FinalizeClean              \* 3. finalize
    /\ runAt.kind = "measurement" \* 4. full run (runs.unreportable)
    /\ audit /= "none"            \* 5. analysis: an audit bound to this run and code
    /\ auditAt = [run |-> runs, code |-> code]
    /\ audit = "decided"          \* 7. decisions, and the review a released BLOCKER owes
    /\ (reviewOwed => reviewed)
    /\ (withReport => report = "result" /\ reportReviewed)   \* 8. report, with its review

\* report_check.hold_changed_paths: the stop and the commit. It runs only for
\* areas the changed paths reach (scope_sha.areas_touched): files in the
\* area, a promise's scope, bound validation, lib/ or src/ modules the code
\* imports, and a report that registers or cites the protocol.
AreaTouched == [cm EXCEPT !.data = data] /= Snap

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
    /\ UNCHANGED <<preflight, frozen, code, data, areaData, runs, run, runAt, audit,
                   auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

\* labkit-audit AREA --mode preflight (high): the audit before the freeze
PreflightAudit ==
    /\ Lane = "high" /\ reg = "written" /\ ~frozen /\ preflight = "none"
    /\ preflight' = "findings"
    /\ UNCHANGED <<reg, regVer, frozen, code, data, areaData, runs, run, runAt, audit,
                   auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

\* labkit-audit AREA --decide N STATUS on the preflight record
DecidePreflight ==
    /\ preflight = "findings"
    /\ preflight' = "decided"
    /\ UNCHANGED <<reg, regVer, frozen, code, data, areaData, runs, run, runAt, audit,
                   auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

\* protocol-fill PROTOCOL --freeze RECORD: preflight clean, its audit decided
Freeze ==
    /\ Lane = "high" /\ reg = "written" /\ preflight = "decided" /\ ~frozen
    /\ frozen' = TRUE
    /\ UNCHANGED <<reg, regVer, preflight, code, data, areaData, runs, run, runAt, audit,
                   auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

\* an edit of an area script or of a lib/ helper it imports
EditCode ==
    /\ code < MaxEdits
    /\ code' = code + 1
    /\ UNCHANGED <<reg, regVer, preflight, frozen, data, areaData, runs, run, runAt,
                   audit, auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

\* a data file outside the area that the run reads, not declared in scope
EditOutsideData ==
    /\ data < MaxEdits
    /\ data' = data + 1
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, areaData, runs, run, runAt,
                   audit, auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

\* a data file inside the area that the run reads (write-protected, lifted on purpose)
EditAreaData ==
    /\ areaData < MaxEdits
    /\ areaData' = areaData + 1
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, runs, run, runAt,
                   audit, auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

StartAs(kind) ==
    /\ run /= "running"
    /\ runs < MaxRuns
    /\ runs' = runs + 1
    /\ run' = "running"
    /\ runAt' = [kind |-> kind, code |-> code, data |-> data,
                 areaData |-> areaData, reg |-> regVer,
                 frozen |-> frozen, regCommitted |-> RegCommitted,
                 preflightDecided |-> preflight = "decided"]
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, audit, auditAt,
                   reviewOwed, reviewed, adopted, report, reportReviewed, cm>>

\* the measuring script with run_kind = "measurement"; runlog's start check
StartMeasurement == MeasurementMayStart /\ StartAs("measurement")

\* the same script with run_kind = "probe": no freeze, no registration owed
StartProbe == StartAs("probe")

RunCompletes ==
    /\ run = "running" /\ run' = "completed"
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, runAt,
                   audit, auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

RunCrashes ==
    /\ run = "running" /\ run' = "crashed"
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, runAt,
                   audit, auditAt, reviewOwed, reviewed, adopted, report,
                   reportReviewed, cm>>

\* labkit-audit AREA --mode analysis: earlier undecided findings first
AnalysisAudit ==
    /\ run = "completed"
    /\ audit /= "findings"
    /\ audit' = "findings"
    /\ auditAt' = [run |-> runs, code |-> code]
    /\ reviewOwed' = FALSE /\ reviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, adopted, report, reportReviewed, cm>>

\* labkit-audit AREA --decide N STATUS; a released BLOCKER owes a review
Decide ==
    /\ audit = "findings"
    /\ audit' = "decided"
    /\ reviewOwed' \in BOOLEAN
    /\ reviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, auditAt, adopted, report, reportReviewed, cm>>

\* labkit-audit AREA --review
DecisionReview ==
    /\ reviewOwed /\ ~reviewed
    /\ reviewed' = TRUE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, audit, auditAt, reviewOwed, adopted, report,
                   reportReviewed, cm>>

\* labkit-adopt AREA: step 1 keeps the proposal only when report-check passes
\* on it without the report station; step 2 writes the result block
Adopt ==
    /\ adopted /= runs
    /\ ChainClean(runs, FALSE)
    /\ adopted' = runs
    /\ report' = "result"
    /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, audit, auditAt, reviewOwed, reviewed, cm>>

\* labkit-audit AREA --report-review REPORT
ReportReview ==
    /\ report = "result" /\ ~reportReviewed
    /\ reportReviewed' = TRUE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, audit, auditAt, reviewOwed, reviewed, adopted,
                   report, cm>>

\* protocol-fill PROTOCOL --discuss RUN --into REPORT: the progress account
ProgressAccount ==
    /\ runs > 0 /\ adopted = 0 /\ report /= "progress"
    /\ report' = "progress" /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, audit, auditAt, reviewOwed, reviewed, adopted, cm>>

\* protocol-fill PROTOCOL --withdraw --into REPORT
Withdraw ==
    /\ adopted /= 0
    /\ adopted' = 0 /\ report' = "none" /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, audit, auditAt, reviewOwed, reviewed, cm>>

\* protocol-fill PROTOCOL --handover --into REPORT
Handover ==
    /\ runs > 0 /\ adopted = 0 /\ report /= "handover"
    /\ report' = "handover" /\ reportReviewed' = FALSE
    /\ UNCHANGED <<reg, regVer, preflight, frozen, code, data, areaData, runs, run,
                   runAt, audit, auditAt, reviewOwed, reviewed, adopted, cm>>

\* git commit of every change; the pre-commit hook holds
Commit ==
    /\ Snap /= cm
    /\ Hold
    /\ cm' = Snap
    /\ UNCHANGED work

Next ==
    \/ WriteRegistration \/ PreflightAudit \/ DecidePreflight \/ Freeze
    \/ EditCode \/ EditOutsideData \/ EditAreaData
    \/ StartMeasurement \/ StartProbe \/ RunCompletes \/ RunCrashes
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

\* "A measurement is a full run, not a probe or preparation."
CommittedNumberFromMeasurement ==
    cm.adopted /= 0 => cm.runAt.kind = "measurement"

\* step 4: "a real implementation repair needs a new run"
CommittedNumberFromCodeAsRun ==
    cm.adopted /= 0 => cm.runAt.code = cm.code

\* the requirement, at every repeat cost: an adopted number stays bound to the
\* inputs it was measured on (the protection, step 4's provenance, is low only)
CommittedNumberFromDataAsRun ==
    cm.adopted /= 0 => cm.runAt.data = cm.data

CommittedNumberFromAreaDataAsRun ==
    cm.adopted /= 0 => cm.runAt.areaData = cm.areaData

\* "A confirmatory protocol is held to the registration of its first measurement."
CommittedNumberUnderItsRegistration ==
    cm.adopted /= 0 => cm.runAt.reg = cm.regVer

\* step 2, low: "the required registration stands in the commit of the first measurement"
CommittedNumberOnCommittedRegistration ==
    (Lane = "low" /\ cm.adopted /= 0) => cm.runAt.regCommitted

\* step 2, high: "pass preflight, decide its audit ... and freeze the protocol"
\* before the measurement
CommittedNumberMeasuredFrozen ==
    (Lane = "high" /\ cm.adopted /= 0) =>
        cm.frozen /\ cm.runAt.frozen /\ cm.runAt.preflightDecided

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

\* step 2: "no measurement starts while it [the type] is a placeholder"
NoMeasurementWithoutRegistration ==
    runAt.kind = "measurement" => reg = "written"

=============================================================================
