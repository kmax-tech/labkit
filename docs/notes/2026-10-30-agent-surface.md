# The agent-facing surface: fewer terms, one next step (plan, 2026-10-30)

**Problem.** labkit's guarantees hold (injection benchmark: seven of nine
mutations held in every state, the other two closed since), but too few
agents reach the point where they apply: in round 1 the lab arm bound a
number in three of fifteen attempts, all on the lightest task; nine attempts
ended in a handover or a discussion block without the task's number; the
`--decide` reading (57 calls) shows `fixed` read as "I changed something",
`accepted` used to dispute a finding, the syntax guessed, one closed loop in
nine cells. The gpt-oss and Qwen pilots add the entry side: three of five
weak agents never ran a labkit command although `AGENTS.md` was in every
request ("we skip"), two were led by the gate messages to a registered
measurement and stopped there. The gates work where they speak at the point
of use; the prose does not carry.

**What the agent is asked to hold today.** `AGENTS.md` (the staged template):
4,774 words, six workflow steps, seven "when you are stuck" cases, and these
coined terms before the first number: protocol, promise table, kind, repeat
cost, intent paragraph, registration, run, answering run, finalize, audit,
finding, decision (`fixed`, `accepted`, `deferred`, `dismissed`, the effect
`stands`), follow-up, adoption, result block, handover, discussion block,
report fields. The route after the measurement is three commands (`finalize`,
`labkit-audit --mode analysis` plus `--decide`, `protocol-fill --from-run`),
each with its own refusals.

**Principle.** At any moment the agent needs three things: where it stands,
the next command verbatim, and what the gate will refuse. Rules belong in
the gate message at the point of use (that is where agents follow them); the
prose shrinks to the loop and one table. Nothing of the guarantees changes;
the surface does.

## Changes, in order

1. **Six terms, the rest hidden.** The agent-facing vocabulary becomes:
   protocol (the registered question and bar), run (one measurement, with
   id), criterion (fit and apply only; a computation has a reference or
   nothing), audit (the check of code against protocol), decision (what the
   agent does with a finding), adoption (the run whose number is reported).
   The promise table stays as format and is never named in prose; "intent
   key / answering run" becomes "the run that answers the question";
   "repeat cost" becomes one question at creation ("can you repeat a
   measurement at will? yes → low") and is otherwise invisible; handover and
   discussion block become one thing, "a stop that still states the number
   or why there is none".
2. **One command for the next step: `labkit next <area>`.** A state machine
   over the area (no protocol → the fields to fill, with the command;
   fields unfilled → which; no run → run the script; run without audit →
   the audit command; findings open → the decide command for the first
   one; decided → adopt this run; adopted → the report line owed) prints
   exactly one next command and what will be refused if it is skipped.
   `AGENTS.md` says: when unsure, run `labkit next`. The six-step prose goes.
3. **Decide with three outcomes.** `fixed` (I changed code or protocol; a
   new measurement follows — the gate refuses the old run), `accepted` (the
   finding stands and is reported as a limitation — the gate writes the
   limit line), `wrong <reason>` (the finding is mistaken). `deferred` and
   `dismissed` fold into these; the effect `stands` is what `accepted`
   means. After every decision the consequence is printed in one sentence
   (partly built, 2026-10-29).
4. **Adoption as one step: `labkit adopt <area> <run>`.** Runs finalize, the
   fill from the run, the result block into the report and report-check in
   one command with one summary; the three commands stay for a person.
5. **An honest stop owes the number.** A handover or discussion block must
   carry the measured value or the line "not measurable because …";
   report-check holds a report without either. Saying nothing is no longer
   a clean exit.
6. **Gate messages in one pattern, before the prose is cut.** The
   refusals are the text agents follow, so they are rewritten first:
   `<what is refused>. <why, one clause>. Next: <command>` — the command
   verbatim, the condition before the command. All of them pass through
   `gate.with_way_out` (one home), so one test can hold every way out to
   ending in a command. Once a message carries a rule, the prose may drop
   it (step 7).
7. **`AGENTS.md` under 1,200 words.** The loop, the kinds table, the six
   terms, `labkit next`, the stop rule. Everything else is reference under
   `labkit/docs/`, reachable by `labkit explain <term>` and cited in the
   gate messages. The cut is a deletion, not a rewording; each sentence of
   today's 4,774 words goes through one filter:

   | The sentence … | Then |
   |---|---|
   | states a rule a gate already enforces, with a way out | delete; the message carries it |
   | says how labkit checks (hash, promise table, TOML fields, superseded calls) | move to `labkit/docs/`, for the person |
   | carries a date or an incident | move to a note under `docs/notes/` |
   | names an action no gate can check, and the agent acts differently for it | keep, as one instruction |

   Only the kept rest is then edited for style, in the procedural register
   of the SimpleEnglish skill (`~/projects/SimpleEnglish`,
   `references/use-cases.md`, "Instructions for AI agents"): one
   instruction per sentence, one word one meaning (the six terms), the
   condition before the command, "must" instead of "should". Its reply
   rules (no lists, no tables) do not apply — the kinds table stays. The
   skill is an authoring tool, not a dependency (stdlib only); what labkit
   holds lastingly is its own test: the template's word limit, no date in
   agent-facing text, every way out ending in a command.

Out of this plan, separate: the fit skeleton's budget (five folds with five
null refits do not finish in 60 minutes on 15 or 71), the hooks for Codex,
the SAB pressure design itself, and the prompts of the audit agents
(`labkit/agents/*.agent.md`, 5,657 words, the preflight alone 3,155 with
six dates). Their reader is a model labkit calls, not the working agent;
cut in the same round, a change in the cold round could not be told apart
from a change in the audits, and whether the guaranteed tier holds is the
injection benchmark's measure, not round 21/60's.

## How to know it helped, before and after building

Before: replay on the existing traces — of the 57 decide calls, how many
map to one of the three outcomes without loss; of the twelve lab attempts of
round 1, at which state `labkit next` would have named the step the agent
missed (handover without number: 5; no adoption after a run: 4; no run: 2).
After: a cold round on tasks 21 and 60 (the cheap ones), Haiku, three
attempts per arm, old `AGENTS.md` against new, same contract as round 1;
the counts are bound numbers per attempt, attempts that enter the route,
decisions that close a finding, and time to adoption. A gain on the entry
and on adoption without a loss on the overclaim count is the bar.

## Cost

Gate messages and their test 0.5; terms and the `AGENTS.md` cut one day; `labkit next` one day (it reads what
`finalize`, `report_check` and the audit already compute — one home, no new
check); decide 0.5; adopt 0.5; the stop rule 0.5. Core first; the rollout to
student repos and the house doctrine is a separate task (LAB-098).
