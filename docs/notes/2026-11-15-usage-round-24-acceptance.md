# Usage round 24: acceptance of the repairs and balance per finding

2026-11-15. Step 5 of the plan under task 7 in `TODO.md`: the cases replayed on [2026-11-13](2026-11-13-usage-round-24-replays.md) and [2026-11-15](2026-11-15-agent-guidance-replays.md) rerun through the same entry points at labkit `d5f4e2b7`, the printed way out followed to its end, the twin kept free; an independent code review of each repair commit that had none; the full checks at that state. The registered round's result stays "not shown"; nothing here measures whether agents now act differently.

## Replay

Real commands on fresh count-task labs; the model calls are stand-ins with a fixed answer. Script, logs and outputs stay internal (labkit-evidence, `usability/2026-11-15-usage-round-24-acceptance/`): 44 checks as expected, 4 gaps the repairs left open. The patterns of the old readings were confirmed present by the 2026-11-13 script, which at `d5f4e2b7` reports them gone (4 of its 15 checks now MISMATCH, as intended).

| Case                                                    | Old reading gone | Printed way closes the hold                         | Twin free | Gap left open                                                                                                                                                         |
|---------------------------------------------------------|------------------|-----------------------------------------------------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 run and adoption in the tree, only the report staged  | yes              | yes (`git add -- <area>`, then the commit passes)   | yes       | report-check's block line still offers "adopt a run in the protocol", which the tree has done                                                                         |
| 2 rejected `stands` on a WARNING                        | yes              | yes (decide again, review upholds, render, commit)  | —         | `labkit-next` says "nothing holds it — the number may be reported" and names neither the open warning nor deciding again                                              |
| 3 handed-over predecessor and successor share REPORT.md | yes              | yes (both reviews clean, staged, the commit passes) | yes       | —                                                                                                                                                                     |
| 4 hints before the first measurement                    | yes              | —                                                   | yes       | —                                                                                                                                                                     |
| 5 two first measurements saw different question texts   | yes              | only by a detour                                    | yes       | the printed `labkit-audit <area> --findings` says "no audit record yet — nothing to decide"; the printed handover omits `--into REPORT`, which protocol-fill requires |

The per-run permitted null deviation (`usability/2026-11-14-band-second-run/repro_per_run.py 4 10`) gives at `d5f4e2b7` the same output as on 2026-11-14, run ids and paths aside.

## Independent review

Four reviewers, each given the commits, not the conclusion; full reports kept with the replay. Every listed finding was checked against the code here before it went into this list.

| Commit(s)                                      | Verdict                      | Confirmed findings                                                                                                                                                                                                                                                                                                                                    |
|------------------------------------------------|------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `c43c842e`, `6b1bac53`                         | core holds, no false blocker | the CHANGELOG says reports without another protocol's block keep their review fingerprint; the brief is part of it (`audit_prompt.py:127`), so every earlier report review is owed again — behaviour as documented, the sentence is wrong; the adoption-only branch (`report_hold.py:179`) has no test                                                |
| `cde6124c`, `f590406e`, `77af00ea`             | contract holds               | after `insufficient` the gate's way out is `--review` (`report_decisions.py:273`), which the review command refuses; the review's "nothing is held" while report-check exits 1 on a stale Limitation line until `--render`; an `--again` draw reads "not confirmed by a second auditor" in the inlined protocol; no test of the changed rule citation |
| `4b6a076f`, `96711518`                         | no correctness bug           | a malformed `failure.json` on a stopped first run ends finalize in a traceback (`runs.stopped_without_number` raises, `registration_hold.stopped_note` does not catch)                                                                                                                                                                                |
| `eb939a4e`, `0e33157c`, `7c7b25be`, `05cd9826` | core holds                   | a successor's report renders the predecessor with no reviews (`result_render.py:360`), so a rejected "not assessable" still shows; after `insufficient` the second `--review` is refused with the rejection's advice (the same gap as above); exact r2 takes about 3 minutes per evaluation at 5 000 items and 200 permutations                       |

Plausible, not confirmed: the staging step also for an untracked run that answers nothing; a running first run labelled "stopped without a number"; a field decided `fixed` skipping the split hold; an outcome claim moved into a discussion block's reason passing the reviewer.

## Full checks

At `d5f4e2b7`: ruff, ruff format, pyright and the whole suite green (3613 passed, 1 skipped), each exit 0; log in labkit-evidence, `test-runs/2026-11-15-full-checks-d5f4e2b7.log`.

## Balance per finding

The findings of [the trace readings](2026-11-13-usage-round-24-findings.md), by group.

| Finding                                                                                                  | Replayed            | Repaired                                         | Accepted here         | Open                                            |
|----------------------------------------------------------------------------------------------------------|---------------------|--------------------------------------------------|-----------------------|-------------------------------------------------|
| 1 an unstaged run read as "measure"                                                                      | yes                 | `c43c842e`                                       | yes                   | gap of case 1                                   |
| 1 the successor check asking opposite entries; contradicting hold sections; stop hook against pre-commit | no                  | —                                                | —                     | not confirmed                                   |
| 2 a crashed first run anchoring the registration                                                         | yes (assay b2 copy) | `4b6a076f`; binding kept by decision             | yes, with a detour    | gap of case 5; traceback on a malformed failure |
| 3 the report review striking demanded numbers                                                            | at the code         | `96711518` (the discussion block named)          | gate tests only       | effect on models not measured                   |
| 3 the predecessor's review blind to the successor                                                        | yes                 | `6b1bac53`                                       | yes                   | CHANGELOG sentence                              |
| 4 no null comparison in the apply template                                                               | yes                 | offered, `ee2af670` ff.; band per run `5d8cabfd` | band replay unchanged | r2 run time                                     |
| 4 `--not-assessable` locking the criterion                                                               | at the code         | `eb939a4e`, standard 0.29                        | gate tests only       | predecessor rendering; way after `insufficient` |
| 4 the rejected limitation "held" beside "nothing holds it"                                               | yes                 | `cde6124c`, `f590406e`                           | yes                   | gap of case 2; stale-line and `--again` wording |
| 4 hard labels for ROC-AUC; the second draft's audit missing the first's finding                          | no                  | —                                                | —                     | audit tier, not a gate question                 |
| 5 stated values, hand-checked case, unregistered report                                                  | yes                 | `6458354b`, `d5f4e2b7`                           | yes                   | effect on agents not measured                   |
| 5 detector by closeness; deleted runs, `reset --hard`, `--no-verify`                                     | read                | —                                                | —                     | audit tier; index-against-tree group            |
| 6 API errors, git identity, pin form                                                                     | read                | —                                                | —                     | labkit-paper's sandbox; no product fault        |
