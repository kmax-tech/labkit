# Judge at `seconds` in the agentsandbox package — labkit 45bb0a2 (2026-10-21)

*Three cold judge probes on the stand that fixed the count
([report](2026-10-21-sandbox-count-45bb0a2.md)): same harness
(`agentsandbox` 1e0c557), image `labkit-probe:1d99e4d77a5c`, model
`claude-sonnet-5-5`, the judge's own model calls (`haiku`) through the same
proxy; labkit run and scorer 45bb0a2. All three numbers bound, no gate
refusal, no `no finding N` refusal — but in two runs the agent could not
see the numbered list `labkit-audit` prints, and one paid for a second
audit to get it. Scores and costs:
`2026-10-21-sandbox-45bb0a2-judge-<n>.{score,costs}.json`.*

| probe | number | log span | misuse | repairs | audits | decisions | source reads | total USD |
|---|---|---|---|---|---|---|---|---|
| judge-1 | 0.8333 | 4m56s | 4 (`--mode` with `--decide`) | 2 (the decide calls again; a second audit run only to list the findings) | 2 | 8 (4 per record) | 1 (`labkit/run/llm.py`) | 1.425 |
| judge-2 | 1.0 | 3m15s | 0 | 1 (`--help` and `ls audits/` to find the numbers) | 1 | 2 | 0 | 0.922 |
| judge-3 | 0.9167 | 2m54s | 0 | 0 | 1 | 2 | 0 | 0.793 |

Against the judge runs on 44db3ac: misuse 10 → 4, the refusal kind is a
different one; `--decide` named only recorded findings in all eight of
its successful calls. Costs rise with a second audit: judge-1's nested
sessions 1.08 USD against 0.54–0.61 in the others.

## Findings, checked against 45bb0a2

1. **The numbered list is hidden when the audit's output is piped.**
   `labkit-audit` prints the report on stdout and the decision list on
   stderr. In a pipe stdout is block-buffered and comes out at exit,
   stderr at once — so under `2>&1 | tail -30` (judge-2) the list stands
   *before* the report and the tail cuts it off. judge-2 then went
   looking with `--help` for a command to list the findings and guessed
   their numbers right; judge-1 re-ran the audit "just to list the
   findings", which wrote a second record with other numbers, and
   `report-check` refused until the first record's four were decided too
   (eight decisions, a second Opus call).
2. **No way to show an existing record's decision list without a new
   audit.** Both agents looked for one; `labkit-audit` has `--mode` (a new,
   paid audit) and `--decide`, nothing that reads.
3. **`--mode` and `--decide` together are refused** (judge-1, four calls):
   the agent kept `--mode analysis` in a shell variable and appended
   `--decide`. The refusal named the rule; one fix sufficed. Noted —
   finding 1 led to it.
4. **The auditor asks about `complete_many`'s order again** and judge-1
   read `labkit/run/llm.py` to dismiss it, as on 22483de and 44db3ac. The
   audit indexes the module by signature, so its documented contract
   ("results in input order") is not on the auditor's page. Noted.

Not seen again: the Raw output field left open by `--from-run`.

## Consequence

Proposed, to decide: print the decision list on stdout after the report
(the order a pipe keeps), and a read-only `labkit-audit AREA --findings
[--record FILE]` that shows the list of the newest record without a new
call.
