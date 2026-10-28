# When the agent is stuck: AGENTS.md and the tool's own options, read by Haiku (2026-10-28)

*What does an agent do when a gate refuses it? It has two sources: AGENTS.md
and what the tools print — `labkit-audit <area> --findings` (no model call;
open findings with ready `--decide` and handover commands) and
`report-check`. Four real stuck states from the SAB-like probes, the tools
of labkit main 9ff3e71 run on them, three cold Haiku 4.5 readers. Reading
only, not task success.*

## Setup

- States: delivered repositories of the SAB-like draws (sab-like-cases,
  sab-cases-on-main), replayed by labkit main in a venv with the task
  packages (a first replay without numpy produced false blockers and was
  discarded). S3 of the draft set was dropped as a noisier twin of S4.
- [Cases](2026-10-28-haiku-stuck-reading/cases.md): per state a short
  situation from the records plus the verbatim `--findings` and
  `report-check` output; questions (a) what is wrong, (b) which options
  remain and which helps, (c) the next commands, (d) what not to do, (e) the
  task's output file. [Contract](2026-10-28-haiku-stuck-reading/assessment-contract.txt)
  and cases committed (ad5f4bd) before any answer. The S2 expectation was
  checked on a copy first: restoring the promise block as it stood at the
  run clears both promise blockers (a first guess, reverting the constant,
  was wrong — the run had used 0.25).
- Answers [1](2026-10-28-haiku-stuck-reading/answer-haiku-1.md),
  [2](2026-10-28-haiku-stuck-reading/answer-haiku-2.md),
  [3](2026-10-28-haiku-stuck-reading/answer-haiku-3.md), verbatim.

## Result

| Situation | What the readers chose | Against the contract |
|---|---|---|
| S1 code changed after adoption | 3 of 3 the fix path: correct the code, test, commit, measure again, finalize, new audit, decide, adopt the new run, render, report; output file from the new run | supported; 2 of 3 write the Conclusion only after `--from-run` |
| S2 promise text changed after the run | 2 register anew with `[replaces]`, 1 restores the text as at the run and hands over | supported (both paths are in the contract) |
| S4 registration after three measurements, no audit | 3 of 3 register anew (own null against permuted gold) or hand over; none adopts an old run | supported |
| S5 deferral of a carried BLOCKER rejected | 3 of 3 refuse a new deferral or another review draw, remove the output file; all three fix the detector in the same protocol and say they cannot tell whether the incomplete first registration forces a new one | supported, with the gap the contract foresaw |

No reader edits a record, uses `--no-verify`, widens a band or keeps a
number an audit rejected.

## Where the tool output misled them

1. **report-check prints an adoption command that cannot help.** S1:
   "`protocol-fill … --from-run 2026-10-27T22-46-40_4268 --force` declares
   the run the checks hold" — that run carries the open BLOCKER and no audit
   covers it; all three readers rejected the line, two called it a
   contradiction with AGENTS.md (which names `--force` only for a Conclusion
   after adoption). S4 and S5 print "`--from-run <run>` writes it" beside
   blockers that say no run of the protocol can answer.
2. **An incomplete registration at the first measurement has no named
   remedy.** S5's blocker says what the commit held, not what to do; the
   replacement path in AGENTS.md is worded for a registration that "cannot
   be answered as written". 3 of 3 readers asked.
3. **Re-adoption is not described.** AGENTS.md says the Conclusion comes
   before adoption and `--force` changes it afterwards, but not that a new
   answering run is adopted with `--from-run <run> --force` — 2 of 3 put the
   Conclusion after the adoption.
4. **When to remove the output file.** "if there is none, remove the output
   file" read as now or after the rerun (2 of 3 asked).

Named once: whether `--effect "<ID> not assessable"` applies to a
computation without promises; the audit's own "new class" label beside the
four classes `--findings` lists.

What the readers did not stumble over: `--findings` shows no current
decision per finding (S5 lists two `deferred` findings as "to decide") and
does not show report-check's blockers (S2, S4). The readers read
report-check beside it and went by that; the gap stays an observation.

## Next

- report-check: print the adoption command only when adoption can follow
  (no open BLOCKER on the run, a covering audit, a registration that
  answers); otherwise name the step that comes first.
- report-check and AGENTS.md: a registration missing or incomplete at the
  first measurement cannot be completed afterwards — register anew with
  `[replaces]` or hand over.
- AGENTS.md: re-adoption after a fix — Conclusion for the new run, then
  `--from-run <new run> --force`; remove the stale output file now and write
  it again from the new answering run.
