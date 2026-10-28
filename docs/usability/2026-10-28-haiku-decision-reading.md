# Decisions, withdrawal and handover, read by Haiku (2026-10-28)

*Do the day's guidance changes (the status table, the withdrawal named first, the stop rule, the one-line ways out) lead a reader to the right next step
at the moments where agents went wrong in today's sandbox cases? A
reading probe, not task success. Contract and the stamped AGENTS.md the
readers had: `2026-10-28-haiku-decision-reading/`. The cases with their
verbatim tool outputs and the readers' answers are kept in the internal
evidence archive, outside this repository.*

## Setup

Four moments, each bound to an observation from the logs of the
file-check case and the declared-run case:

| case | what the logs showed | change under test |
|---|---|---|
| D1 a code change after an adoption, the commit refused | the withdrawal met only after a refused adoption and a spent audit; then a commit past the hook | the withdrawal named first |
| D2 an audit BLOCKER on the declared run | the BLOCKER decided `fixed` before its repair | the status table: `fixed` only after the repair |
| D3 four findings, four statuses | no log evidence for confusing `dismissed` and `deferred` | the status table |
| D4 refused: hand over or go on? | a commit past the hook instead of the named step | hand over only for a named missing prerequisite |

The tool outputs were produced by labkit `698ed6f` on copies of the
declared-run start state. Three fresh Claude Haiku 4.5 readers had the
stamped AGENTS.md and the cases only. The contract was committed before
any answer (`6291157`).

## Result

At each of the four moments all three readers chose the step the
contract expected:
- the withdrawal before the next audit (D1);
- `fixed` only after the withdrawal, no new measurement (D2);
- the four statuses told apart (D3);
- a refusal followed by its named step, a handover only where the input
  file was gone (D4).
None used `--force` or `--no-verify`, restored the intended code or wrote
the predictions file from the withdrawn run.

One detail departed from the contract: all three said an accepted
WARNING needs no second auditor. That follows step 5 of AGENTS.md; the
new status table had said otherwise, and the contract copied the table.
The table was fixed the same day.

## Limits

Reading only: three readers, one reading each, no rate. A careful reader
had time for the whole output; whether a running agent finds the step
under time pressure is not shown. In D1 the withdrawal then stood in a
note below six holds whose own ways out said "measure anew"; it now
stands in every hold.
