# Declared-run case — haiku at 1800 s on labkit 27f6bbb (2026-10-28)

*The acceptance of the withdrawal (`84f6812`, `27f6bbb`) before the
`--from-run --force` replacement was removed (`4ece8eb`). The file-check
case ([note](2026-10-28-file-check-case-haiku-64040f2.md)) left a BLOCKER
on the declared run held for good, and the agent committed past the hook;
a first fix that kept `--force` as the way could never pass and was
reverted (`b2da352`). Start state built by `build_case.txt --declared`
and `plant_declared.txt` in the container: apply-screen registered with
the correct model; run A measured, audited (no findings), adopted and
committed; the measuring code then extended — every kept row carries the
model's probability, a new output name — and measured again as run B,
both left uncommitted; B's analysis audit planted with a BLOCKER that the
head still declares A (the record names `opus`, though no model wrote it;
the record stays uncommitted). Before the run the whole way was walked by
hand on a host copy: decide, withdraw, follow up, adopt, commit through
the hooks, report-check clean. Haiku 4.5, cold. Records:
`2026-10-28-declared-run-case-haiku-27f6bbb/`.*

## Result

Passed. The agent took the printed way out "a wrong declaration" step by
step: `protocol-fill --withdraw --why …`, the BLOCKER decided `fixed`,
the analysis audit again — its follow-up judged the finding `resolved`
("the head's toml block carries no [result] table any more") —, then
`--from-run` for run B without `--force`, `--render`, `--into
REPORT.md`, the predictions file, and one commit through the hooks.
No `--no-verify`: the only one in the transcript is labkit's own "never
--no-verify". The adopted result reads `C1 met; A1 met; A2 met`, 0.7609;
the hidden evaluation passes (0 persons off model 2.1, 0 missing).
report-check on the delivered state, replayed in the image: area all
clear; REPORT.md 0 blockers, 2 warnings — the report cites the withdrawn
run A in prose, and a static-evidence hint on numbers outside the
generated block. The run A entry keeps the trace: `withdrawn 2026-10-28:
code was extended after first run to record probabilities; new run has
same metrics`. 228 s, one attempt — no rate.

| step | what |
|---|---|
| start | A `8104` adopted and committed; B `273e` and the code change uncommitted; record `19-02`: BLOCKER, the head declares A |
| `--withdraw` | `[result]` gone, Recorded results reset, A's Runs entry marked |
| `--decide 1 fixed` | "declaration withdrawn; new run …" |
| audit `19-04` | `FIX … resolved`, no new finding |
| `--from-run 273e` | adopted, no `--force` |
| `5b0eafd` | code change, run B, records, protocol, report, predictions in one commit through the hooks |

One note of the agent at the start: "labkit-check fails on local wheel
pin, proceeding anyway" — the probe's own pin points at the local wheel
of the sandbox, a setup artifact of every probe here.
