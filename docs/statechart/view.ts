// The reader's words for the AreaLifecycle model: one region for the work in
// the tree, one for what the last commit holds.

type V = { [k: string]: any };

const before = (v: V): string => {
  if (v.reg === "open") return "Registration open";
  if (v.preflight === "findings") return "Preflight findings undecided";
  if (v.frozen) return "Frozen, nothing measured";
  if (v.preflight === "decided") return "Preflight decided, not frozen";
  return "Registered, nothing measured";
};

const work = (v: V): string => {
  if (v.runs === 0) return before(v);
  if (v.run === "running")
    return v.runAt.kind === "probe" ? "Probe in progress" : "Measurement in progress";
  if (v.run === "crashed") return "Newest run crashed";
  if (v.adopted !== 0) {
    if (v.runAt.code !== v.code) return "Adopted, code changed since the run";
    if (v.runAt.data !== v.data) return "Adopted, input changed since the run";
    if (v.runAt.reg !== v.regVer) return "Adopted, registration changed";
    return v.reportReviewed ? "Adopted, report reviewed" : "Adopted, report review owed";
  }
  if (v.runAt.kind === "probe") return "Probe completed";
  const current = v.auditAt.run === v.runs && v.auditAt.code === v.code;
  if (!current || v.audit === "none") return "Measured, not audited";
  if (v.audit === "findings") return "Audit findings undecided";
  if (v.reviewOwed && !v.reviewed) return "Decision review owed";
  return "Ready to adopt";
};

const commit = (c: V): string => {
  if (c.runs === 0) return c.reg === "written" ? "Commit: registration" : "Commit: nothing registered";
  if (c.adopted !== 0) {
    if (c.runAt.code !== c.code) return "Commit: number on changed code";
    if (c.runAt.data !== c.data) return "Commit: number on changed input";
    return "Commit: adopted number, reviewed";
  }
  if (c.report === "progress") return "Commit: progress account";
  if (c.report === "handover") return "Commit: handover";
  return "Commit: run, no report";
};

export const state = (v: V) => ({ Work: work(v), "Last commit": commit(v.cm) });

const LABELS: { [action: string]: string } = {
  WriteRegistration: "protocol-fill writes the registration",
  PreflightAudit: "labkit-audit --mode preflight",
  DecidePreflight: "labkit-audit --decide (preflight)",
  Freeze: "protocol-fill --freeze",
  EditCode: "you change the code",
  EditOutsideData: "you change a data file outside the area",
  StartMeasurement: "you start a measurement",
  StartProbe: "you start a probe",
  RunCompletes: "the run completes",
  RunCrashes: "the run crashes",
  AnalysisAudit: "labkit-audit --mode analysis",
  Decide: "labkit-audit --decide",
  DecisionReview: "labkit-audit --review",
  Adopt: "labkit-adopt",
  ReportReview: "labkit-audit --report-review",
  ProgressAccount: "protocol-fill --discuss",
  Withdraw: "protocol-fill --withdraw",
  Handover: "protocol-fill --handover",
  Commit: "git commit (hook passes)",
};

// TLC names both starts by their shared operator StartAs; the run's kind tells them apart
export const step = (action: string, _from: V, to: V) =>
  action === "StartAs"
    ? to.runAt.kind === "probe" ? LABELS.StartProbe : LABELS.StartMeasurement
    : LABELS[action] ?? action;

export const title = "One labkit area: commands, gates, last commit";
