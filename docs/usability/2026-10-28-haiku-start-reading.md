# The start of an area, read by Haiku (2026-10-28)

*What does an agent make of labkit's first words — the next steps
`labkit-init exp` prints, `protocol-check --contract`, the pre-commit
hook's first refusal, runlog's refusals of a measurement? Five situations
on a fresh lab, the tools' output verbatim, three cold Haiku 4.5 readers
with AGENTS.md. Reading only, not task success.*

## Setup

- Outputs produced on a fresh lab (`labkit-init lab`, hooks installed),
  no model call: a compute area and a fit area at low repeat cost, the
  commit refused after stamping, the measurement refused while the
  registration is unwritten and while it is uncommitted.
- [Cases](2026-10-28-haiku-start-reading/cases.md) with questions (a) what
  the output asks, (b) what you write or decide before the next commit and
  whose decision each value is, (c) the commands up to the first full
  measurement, (d) what not to do.
  [Contract](2026-10-28-haiku-start-reading/assessment-contract.txt) and
  cases committed before any answer. Answers
  [1](2026-10-28-haiku-start-reading/answer-haiku-1.md),
  [2](2026-10-28-haiku-start-reading/answer-haiku-2.md),
  [3](2026-10-28-haiku-start-reading/answer-haiku-3.md), verbatim.

## Result

Every reader chose a sound path in every situation: the registration
written and committed before the run, no freeze, preflight or
`LABKIT_UNFROZEN` at low repeat cost, no `--no-verify`, all five must
fields filled including Terms, which the next steps did not name. The
doubts sat in the tools' own text:

| Doubt | Readers | Source |
|---|---|---|
| The stamped constants (`margin = 0.25`, `max_empty = 0`, `null_band = 0.1`): proposal or prescription? | 3 of 3 | numbers in the stamped `[[promise]]` tables, only the sentences marked `<…>` |
| `--show 2` (AGENTS.md) against `--show 3` (next steps) | 3 of 3 | AGENTS.md:118, `scaffold.py` low steps |
| How the task's output file comes about | 3 of 3 | the next steps never name it |
| runlog names Question / hypothesis alone, the hook five fields | 3 of 3 | each gate checks its own cut; all filled five |
| `00_prepare.py` in the fit area's contract, not in its steps | 2 of 3 | the low steps omitted it (the high steps name it) |
| "pilot subset first" in Data / scope, while low has no pilot | 2 of 3 | protocol template placeholder |
| "Freeze first: preflight … `frozen = true`" at low repeat cost | 2 of 3 called it a contradiction | runlog's refusal tail, corrected only in parentheses |
| Terms missing from the next steps | 1 of 3 named it, 3 of 3 filled it from the contract | `step_fields` |

The hypothesis of the contract — at most one reader names the constants
as its own decision — did not hold: all three did. But question (b) asked
for exactly that, so the probe shows what a reader sees when asked, not
what an agent notices unprompted. The unprompted case is on record: an
SAB-like fit agent wrote 0.15 in its criterion and sentence and kept the
stamped `margin = 0.25` (S2 of the [stuck probe](2026-10-28-haiku-stuck-reading.md)).

Named once: whether the area test belongs to the low steps; runlog against
"in the foreground"; "its reference" in the fit step; the Conclusion
missing from the adoption step.

## Changed (2457c3b)

- Next steps: "terms" beside question, unit, data, exclusions; a kind with
  a bar names its `[[promise]]` constants as the agent's to set; the low
  cut names `00_prepare.py` where the skeleton reads prepared rows, and
  the area test; the adoption step puts the Conclusion first and the
  task's output file after it.
- The stamped head says the constants are the stamp's examples, to be set
  to the value the sentence states.
- runlog's refusal names the freeze only where the repeat cost owes one.
- One `--show` count (3); "pilot subset first" out of the placeholder.

## Second round, after 2457c3b

Same five situations with the new output, three fresh readers, contract
before the answers (ade114d):
[cases](2026-10-28-haiku-start-reading-2/cases.md),
[contract](2026-10-28-haiku-start-reading-2/assessment-contract.txt), answers
[1](2026-10-28-haiku-start-reading-2/answer-haiku-1.md),
[2](2026-10-28-haiku-start-reading-2/answer-haiku-2.md),
[3](2026-10-28-haiku-start-reading-2/answer-haiku-3.md).

| Doubt of round one | Round one | Round two |
|---|---|---|
| the stamped constants | 3 of 3 asked whether they may stand | 0 asked; 3 of 3 set them as their own, one overcorrects to "do not take the stamp's values over" |
| `--show` count | 3 of 3 | 0 |
| the task's output file | 3 of 3 | 0; all write it from the adopted run |
| `00_prepare.py` | 2 of 3 | 0; all run it before the measurement |
| "pilot subset first" | 2 of 3 | 0 |
| "Freeze first" at low | 2 of 3 | 0 |
| runlog's one field against the hook's five | 3 of 3 (not changed) | 3 of 3, plus 2 of 3 on the contract's before-run line |

The one shared doubt left was changed in eb81522: the contract's
before-run line says runlog checks the registration fields and the
pre-commit hook every field of the first line; runlog's refusal says the
commit also owes the other fields the contract names.

## Third round, T1 and T4, after eb81522

Three fresh readers, contract before the answers (f4a8df1):
[cases](2026-10-28-haiku-start-reading-3/cases.md),
[contract](2026-10-28-haiku-start-reading-3/assessment-contract.txt), answers
[1](2026-10-28-haiku-start-reading-3/answer-haiku-1.md),
[2](2026-10-28-haiku-start-reading-3/answer-haiku-2.md),
[3](2026-10-28-haiku-start-reading-3/answer-haiku-3.md). Two readers state
the split correctly (runlog checks the question, the commit owes all
fields); one still files it under open points but fills all five. No
reader fills only the question. The shared doubts of the tools' text are
gone.

## What remains — questions about the standard, not about wording

Raised in more than one round, each by one or two readers; not changed,
because the answer is a decision about the standard:

1. **`type` of a computation.** AGENTS.md defines `confirmatory` as testing
   "a question and criterion specified before the relevant results"; a
   computation has no criterion (round three 2 of 3, round two 2 of 3).
2. **Where a computation ends and a fit begins.** "a threshold … chosen on
   performance data counts" — is a detection threshold tuned by looking at
   the signal, or against reference annotations, performance data? (rounds
   one to three, 1–2 readers each.)
3. **The input data.** AGENTS.md says to commit "code, registration and
   inputs"; readers ask whether `data/ecg.csv` is raw or prepared data and
   where it lives (round two 2 of 3, round three 2 of 3).

Named once and small: `protocol-fill` shown in two argument forms (both
work: `"<Label>=<value>"` and `"<label>" "<value>"`); `chance_of()` in the
stamped null sentence is not defined in either text; whether a refused run
leaves a trace (it does not: runlog refuses before a run directory exists).
