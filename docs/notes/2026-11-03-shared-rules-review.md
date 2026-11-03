# Shared rules, duplicate comparisons, special cases

2026-11-03. Code inspected: `e5fdf363`; the package is unchanged up to
`424aed0e`, so every `path:line` below holds there too. A second, separate
pass beside the [maintainability review](2026-11-03-maintainability-review.md)
of the same day; both follow the
[workflow simplification](2026-11-02-workflow-simplification.md) plan's
"Review maintainability after the simplification". No production code was
changed. Overlap: V3 here is that review's M1, V5 its M2.

## Result

21 findings, no case for a rebuild. The main pattern: one fact is checked
in two places with their own logic — 14 of 21. Three already disagree today,
reproduced by running the functions (`.venv`, synthetic protocol texts):

- A prompt that starts with `<` counts as the template placeholder at run
  start and runs without the drift check (R1).
- A field label with a gloss, e.g. `Unit (per judged item)`, escapes the
  hold after the first measurement (V1).
- A Data profile that was only re-wrapped counts as a changed registration (V2).

Six findings (N1–N6) are places where `labkit-next` or another tool advises
differently from what the gate then decides. Removable special cases are
rare: two reading paths for old formats (S1, S2).

## Method

Three questions: (1) the same rule in more than one home; (2) two places
comparing the same fact with their own logic; (3) branches for names, forms
or old versions that a general rule already covers. First a mechanical
search (functions defined in several modules, identical bodies, regex
literals, module constants) — nothing duplicated. Then three readers each
took one part (`gates/`, `formats/` + `checks/`, `tools/` + `run/`); every
finding was re-read at its location, R1, V1 and V2 also run. "Status"
says how far.

## Same rule in more than one home

| No. | Rule | Locations | Consequence | Smallest change |
|---|---|---|---|---|
| R1 | "this Prompt block is only the template's placeholder" | right: `labkit/formats/protocol_check.py:259` (`is_stamp_placeholder_block`); wrong: `labkit/checks/prompt_check.py:216`, `labkit/run/lanes.py:366` (`startswith("<")`) | **Run.** A real prompt opening with `<instructions>` counts as placeholder: `lanes` says "no registered Prompt block" and starts the paid run without drift check; `check_prompt_drift` stays silent. | Both call `is_stamp_placeholder_block`. |
| R2 | "the value is one `<…>`" | `labkit/formats/protocol_block.py:286`, `labkit/formats/promises.py:287`, `labkit/formats/protocol_check.py:334`, `labkit/checks/data_counts.py:101` | `--data-counts` appends counts to a placeholder with an id prefix while protocol-check reports the field empty. Output text only. | One function in `protocol_block`. |
| R3 | "which run does the head declare; unreadable means none" | `labkit/formats/answering_run.py:647` (`adopted_run`) and `labkit/formats/protocol_check.py:1059` (`result_due`), same body; inline copies `protocol_check.py:959`, `:1030` | Same today; the docstrings justify the `None` differently. | Drop `result_due`, use `adopted_run`. |
| R4 | "measured, even if the run was deleted since" | `labkit/gates/report_hold.py:470` (`has_measured`), `labkit/gates/report_check.py:767` (`adoption_state`), `labkit/gates/agent_hooks.py:533` (`gone_runs`) | Same today. The stop hint scans only `experiments/*`. | One pure `measurements(area, pid)`. |
| R5 | two text pieces | "withdraw the adoption first": `labkit/gates/audit_decisions.py:905` beside `labkit/gates/ways_out.py:237`; report place: `labkit/gates/report_hold.py:251` rebuilds `held_place` (`:141`) | Drifts at the next rewording. | Use the constant / call `held_place`. |

## Duplicate comparisons

| No. | Fact | Locations | Divergence | Status | Smallest change |
|---|---|---|---|---|---|
| V1 | value of a registration field | `labkit/formats/protocol_history.py:414`, `:465` look up the label as written; `labkit/formats/protocol_check.py:179`, `:899` by `field_name` | With `**Unit (per judged item):**` `scope_differences` returns `[]` for a changed value, `audited_texts` sees it. A field written twice: stamp takes the first, hold the last. | run | One `field_values(text)` in `protocol_check` for all four. |
| V2 | Data profile changed? | `labkit/formats/protocol_history.py:468` raw; `:391` and `labkit/formats/protocol_check.py:916` whitespace-folded | A re-wrapped paragraph is a changed registration a successor must declare, though the audit stamp sees none. | run | `scope_value` for `COMPARED_FIELDS` too. |
| V3 | declared run's code changed? (= M1) | `labkit/gates/report_check.py:888` searches "changed since <run>" in finalize's texts; finalize decides at `labkit/gates/finalize.py:999` | Messages about predecessor runs or a deleted script name another id; report-check's stages then lack "withdraw the adoption first". | read | finalize returns `held_by`. |
| V4 | does a report block belong to this protocol? | as written: `labkit/gates/report_hold.py:367`, `:374`, `:457`; resolved: `:914` (comment on the pilot bug), `labkit/gates/report_review.py:147` | `./PROTOCOL-x.md` or another spelling: missing in one place, present in the other. The 2026-11-01 pilot bug is fixed in one place only. | read | Compare `block_protocol(report, b)` everywhere. |
| V5 | what changed since the first measurement? (≈ M2) | `labkit/gates/audit_decisions.py:1013` (`_departure`) without release step; `labkit/gates/finalize.py:644` (`scope_now`) with `released_fields` | After a released in-place correction, `--decide fixed` can say "finalize refuses it" for a field finalize already released. | in the code, flow not reproduced | `_departure` reads `scope_now(…).held`. |
| V6 | does the preflight audit cover this state? | `labkit/formats/audit_gaps.py:239`–`275` field by field; `labkit/formats/findings.py:504` `AuditedState` as the one match | Same today; a new `AuditedState` field would not be compared by preflight. | read | Compare `AuditedState` first, fields only for wording. |
| V7 | registration changed after the first measurement? | `labkit/gates/finalize.py:343`; `labkit/checks/result_render.py:295` (`_unregistered`) | Same for the promise block; finalize also holds scope changes, the successor rendering does not and still shows a verdict. | read | One pure function for both. |
| V8 | registration ready for the full run? | `labkit/gates/agent_hooks.py:344` says "registration written" (working tree); `labkit/run/start_check.py:146` requires it committed | Hook says ready, runlog refuses "not committed" — one round lost. | read | Hook calls the start check or names "committed". |

### Advice and gate check differently

`labkit-next`, `labkit-adopt`, `protocol-fill` or `batch` derive a gate's
condition themselves instead of calling the gate — what work package A of
the plan set out to stop.

| No. | Question | Advice | Gate | Status | Smallest change |
|---|---|---|---|---|---|
| N1 | is a run still open? | `labkit/tools/next_step.py:128` asks `open_runs` (`labkit/run/runlog.py:881`): a detached start without a run record is not open, advice may be "measure" | `runlog --wait` (`labkit/run/runlog_command.py:245`) counts such starts; the twin gate (`runlog.py:893`) only the same script | read | One `busy(area)` for `next` and `--wait`. |
| N2 | is the lock holder still writing? | `labkit/run/batch.py:248` checks only that the pid exists and says "wait, never delete its lock" | `runs.is_alive` (`labkit/formats/runs.py:56`) also checks the script; after pid reuse `--wait` returns at once — the wait never ends | read | Call `runs.is_alive(pid, script)`. |
| N3 | which reports does the commit hold? | `reports_without_block` (`labkit/gates/report_hold.py:217`) scans every `.md`; `next_step.py:166` says "the commit and the stop hold" | the gate holds only touched and newly reached committed reports (`labkit/gates/report_check.py:963`) | read | Build candidates as the gate does, or soften the sentence. |
| N4 | may the report be registered after measuring? | `protocol_fill.report_bound` (`labkit/tools/protocol_fill.py:963`) refuses any change at every lane | `report_binding_gap` (`labkit/gates/report_hold.py:542`) holds only at `low` and only a registered report; a hand edit passes every gate | read | Decide the rule in one place (see below). |
| N5 | anything open after a handover? | `next_step.py:221` checks only `report_owed`, else "nothing" | `hold_registered` (`report_check.py:1046`) also checks `report_binding_gap` | reported, not re-read | Gap list as one pure function. |
| N6 | does the progress account suffice? | `next_step.py:332` accepts it even when another block does not read | `report_hold.py:393` does not (`why`) | reported, not re-read | One `account_owed` for both. |

Belongs to R1: the prompt-drift comparison itself is written twice,
`labkit/run/lanes.py:345` and `labkit/checks/prompt_check.py:216`. Same
today; pull it into one function with R1.

## Special cases

Most old-format branches detect and refuse, naming the version — allowed by
"Breaking changes, not legacy paths" (e.g. `labkit/formats/promises.py:867`).

| No. | Special case | Locations | Cost | Justified? | Smallest change |
|---|---|---|---|---|---|
| S1 | journal starts of labkit 0.103.0 or earlier are read, with their own supersession rule (any later audit of the mode supersedes, no protocol/block match) | `labkit/formats/attempts.py:247`, `:283` (`historical_call`), `:335`; `labkit/gates/audit_decisions.py:421` | a second branch in the supersession rule, for good | partly: the journal is append-only evidence; CHANGELOG 0.104.0 announces the end | Refuse old starts in the next Breaking release; keep the "no attempt names this file" case. |
| S2 | `indexed_runs` reads any header the writer refuses as pre-0.21 and silently skips short rows | reader `labkit/run/runlog.py:929`; writer `:270` (`header_refusal`) | a truncated row drops a measured run: `has_measured` says not measured, `protocol-fill` allows a registration that should be bound — breaks fail loud | no | Call `header_refusal`, raise on a short row. |

## To decide

1. **Report after the first measurement (N4):** bound at every cost tier
   (the gate gets stricter) or only at `low` (`protocol-fill` stops
   refusing)? Today `protocol-fill` refuses, a hand edit passes every gate.
2. **Journal starts of labkit 0.103.0 and earlier (S1):** refuse them in
   the next Breaking release, or keep them as a justified exception?

## Open points

By risk. Each one is its own small commit with a twin test (today's wrong
case, the correct variant still passing). None needs a rebuild.

1. R1 + prompt drift.
2. V1 + V2: one `field_values(text)` by `field_name`, folded whitespace for Data profile.
3. N4, after the decision above.
4. S2.
5. N1, N2.
6. V3, V4, V5 (V3/V5 overlap M1/M2 of the other review; reproduce V5 first).
7. N3, N5, N6 (re-read N5, N6 first).
8. R2–R5, V6–V8: merge the copies while they still agree.
9. S1, after the decision above.

Not found: duplicated hash functions, regex literals or module constants,
layering violations, old-format reading in `tools/` and `run/` beyond S2.
No module split is proposed: no finding depends on module size.
