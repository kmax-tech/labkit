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
3. **Decide with three outcomes, named by their consequence.**
   `labkit-audit <area> --decide N <outcome> --why "<reason>"`:
   `fixed` (the fault is repaired; a new measurement and a follow-up audit
   check it — the gate refuses the old run), `limit` (the finding is true
   and the number carries it as a Limit line in the report),
   `false-positive` (the auditor misread; a second auditor checks the
   reason). `deferred` goes: a fault the claim cannot be read within ends
   in a handover, not in a status. `--effect stands` goes: `limit` means
   it; the rare "these promises are not judged" becomes its own flag,
   `--not-assessable C1`. After every decision the consequence is printed
   in one sentence with the next command (partly built, 2026-10-29).

   Naming pass over the 57 decide calls of round 1 (the internal reading
   of the twelve lab-arm traces) — per word, whether the word or its
   description failed:

   | Today | How agents used it | Failed | Becomes |
   |---|---|---|---|
   | `fixed` | for any change that touched the finding: 15 decisions, one naming the change as the template asks; 3 before any repair, 2 of them by editing the registration in place | the description: the word holds (Bugzilla's RESOLVED FIXED, verified later), but the agent did not know a follow-up checks it | `fixed`, the consequence printed at once; refused while the declared scope is unchanged since the audit |
   | `accepted` | as "the result is fine as is": 11 of the 30 `stands` reasons dispute the finding, 6 `accepted` reasons describe a repair | the word: accepted what, the finding or the result? | `limit` (inherits the house's Limit line) |
   | `dismissed` | once, for a true finding the agent meant to handle later | the word: it names no direction | `false-positive` (the triage term of static analysis; the plan's `wrong` fails the context-free test, since the code could be what is wrong) |
   | `deferred` | three times as "later, by me" | the word: it claims a later the format does not have | gone, into the handover |
   | `--effect stands` | syntax guessed: 6 refusals in 4 cells, 8 findings left without effect | the shape: a missing positional REASON is reported by argparse as an unrecognized `stands` | gone; the reason as `--why` (the handover's flag), its absence refused with a sentence |
   | `--discuss` beside `--handover` | once run when the agent meant the handover | two exits with one purpose | one handover that carries the number or why there is none (step 5) |

   Kept: `--decide` (the act is the agent's), `labkit next`, `labkit
   adopt` (inherits adoption), handover. Only a word that fails the
   context-free or the lie test is renamed; `fixed` is not. The statuses
   are a record format (`findings.STATUSES`): the rename is an announced
   break in one release, no reader for the old values (decided
   2026-10-30). A `false-positive` on a BLOCKER needs a second auditor
   before the number leaves, as an accepted BLOCKER does today; on a
   WARNING the missing review warns (decided 2026-10-30).

   Replay on round 1 (the internal reading of the final audit records):
   of 67 decided findings, 64 map onto exactly one of `fixed`, `limit`,
   `false-positive` or the handover by what the reason says the agent
   meant; two straddle limit and dispute or repair, and one is a repair
   not yet made, which should have stayed open. Today's status matches
   the meaning in 38 of 67; the drift is `accepted` used to dispute (14)
   or to report a repair (6). The three words cover what the agents
   meant; whether an agent picks the right one, only the cold round shows.

   **Further terms on the agent's path** (naming pass over round 1's
   agent reasoning, candidates, not decided):

   | Term | What happened | Failed | Candidate |
   |---|---|---|---|
   | `type` beside `kind` | two head fields whose names are synonyms; agents set `confirmatory` because the task named a requirement, then flipped to `exploratory` after the number missed it (2 cells) | the neighbourhood test: the difference between the two fields is not in their names | `type` → `analysis` (`confirmatory` / `exploratory` analysis, the field's term); the flip after the first measurement refused, not only reported by the follow-up |
   | declare / adopt / withdraw | `protocol-fill --from-run` "declares" the run, the plan calls it adoption, `--withdraw` withdraws "the declaration"; agents unsure whether there was anything to withdraw | one act, two words | adoption only: `labkit adopt`, `--withdraw` withdraws the adoption; "declared run" leaves the agent's text |
   | admissibility condition | the distinction from the criterion had to be explained; the standard already maps it to the Registered Reports' outcome-neutral condition and quality check | a coinage where the field has a word | in agent-facing text "quality check (admissibility condition)" once, then quality check |
   | `C1`, `A1`, `A2` | used correctly as ids, but `A2` is the null condition — an ordinal name hides which A is which | the context-free test | ids stay (the id alphabet is a format); every message prints the id with its name, "A2 (null condition)" |
   | repeat cost `low` | twice read as a reason to skip the decision review | the description: the word is right, what `low` drops is not said where it matters | already hidden by step 1; the review line names that it holds at every repeat cost |
   | `--review --again` | an upheld redraw that "releases nothing" read as the release | the lie test: "again" promises a repeat of the real thing | off the agent's surface (a person's tool) |
   | carried (BLOCKER) | used as a label, no confusion seen | — | keep; the message says "unresolved since `<record>`" once |

   **Promise ids and kinds (decided 2026-10-30).** The letters go: an id
   is the kind word and a number — `criterion-1`, `quality-check-1`,
   `interpretation-1` — so it says its kind without a legend and asks
   nobody to coin a name; the metrics key derives from it in one place
   (`criterion_1_pass`). It passes the context-free test for the kind
   only, so every message puts the condition beside it: "criterion-1:
   ROC-AUC ≥ 0.90". `admissibility` becomes **quality check**: the
   standard already maps it so (Registered Reports' outcome-neutral
   condition), while "instrument check" is taken (the `--probe` field,
   `protocol_cuts.py`); the message says its consequence — "quality-check-1
   not met → criterion-1 gets no verdict" — since a quality check here
   decides whether the run can answer at all, not a warning. `branch`
   becomes **interpretation** (the Registered Reports' "interpretation
   given different outcomes"): a B entry holds conditions and readings in
   one sentence today, so each arm is written `<condition> → <reading>`,
   and the run's recorded value is one of the readings. The break ships
   in one release with the decision statuses, built as separate commits.
   Before the format changes, a reading probe tries the words in real
   messages (old against new, the next command as the measure).
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

Before: replay on the existing traces — of the decided findings, how many
map to one of the three outcomes without loss (done: 64 of 67, step 3);
of the twelve lab attempts of
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
