# Count and judge at `seconds` — cold Sonnet agents on db1695d (2026-10-20)

*Three cold runs of each task on one pinned commit, one after another, to
measure the current templates and gates before further architecture work.
All seven numbers (three count, four judge) came out bound; the count
equals its truth every time. Five of six valid runs stayed under the
five-minute target. The friction is in the tools around the number:
eight agent-reported faults hold against the code, two of them in every
probe or nearly every one. Scores: `2026-10-20-sonnet-<probe>.score.json`.*

## Setup

- **Code:** `git archive db1695d225658a3f3baf31cc4b2f7a03e3cb7cd3`,
  installed non-editable (`pip install <archive>`, Python 3.12.7), not the
  working checkout. `usability stage <dir> --task <count|judge> --venv
  <env>` from that install, default tier `seconds`; every probe carries the
  same scaffold sha `d1de7d60240f` and records `labkit @ file://…/src`.
- **Environments:** count-1 linked the shared env `env/`; its agent
  installed pytest into it. From count-2 on each probe got its own env
  built the same way (`env-<probe>`), and `pip freeze` of each equals the
  frozen list after its run, except `env-count-3`, where that probe's agent
  installed pytest. This is the one operator intervention during the
  series; no probe saw another probe's change.
- **Agents:** Sonnet as a subagent of the operator's Claude Code session,
  started without history and handed only `<probe>.prompt.md` verbatim
  (the probe's AGENTS.md plus the TASK.md pointer; the prompts differ only
  by path). As a subagent it runs outside a session started in the probe:
  the probe's Claude hooks did not fire; the git pre-commit hook and
  `runlog` did.
- **Model in the loop (judge):** `haiku` through `claude -p`, 24 calls a
  run.
- **Order:** count-1, count-2, count-3, judge-1, judge-2, judge-3,
  judge-4, each scored and traced before the next started.

## Result

| probe | number | right · bound | log span | transcript | calls | gate lines | refusals | source reads |
|---|---|---|---|---|---|---|---|---|
| count-1 | 3.5 | yes · yes | 2m44s | 3m38s | 26 | 3 | 0 | 0 |
| count-2 | 3.5 | yes · yes | **6m42s** | 7m31s | 24 | 2 | 0 | 0 |
| count-3 | 3.5 | yes · yes | 2m29s | 3m15s | 24 | 3 | 0 | 0 |
| judge-1 | 0.8333 | — · yes | *28m41s (slept)* | *29m04s* | 34 | 5 | 0 | 1 |
| judge-2 | 0.75 | — · yes | 4m10s | 4m53s | 25 | 0 | 0 | 0 |
| judge-3 | 0.8333 | — · yes | 3m50s | 4m21s | 24 | 1 | 1 | 0 |
| judge-4 | 0.9167 | — · yes | **5m18s** | 5m43s | 28 | 1 | 0 | 0 |

The judge has no fixed truth; its number is accuracy against the
twelve gold labels, one draw of `haiku`. All judge runs passed [C1]
(threshold 0.75) and both admissibility conditions; the null lane scored
0.5 in every run.

- **Medians over valid runs:** count 2m44s (target met 2 of 3), judge
  4m10s over judge-2..4 (met 2 of 3).
- **judge-1 does not count for time.** The laptop slept 21:17:09–21:38:39
  (`pmset -g log`: Maintenance Sleep from 21:21:23 for 904 s). The score
  shows a log gap of 1064 s; the agent read it as a hung `claude -p` call
  and killed it, leaving a crashed run (`2026-10-20T21-19-06_20b7`). Its
  number and steps stand; its time, the hang and its draw spread do not.
  On the owner's decision judge-4 repeated it on the same stamp.
- **Spread of the judge:** 0.75, 0.8333, 0.9167 across three valid
  probes; judge-2's 0.75 sits exactly on the bar. judge-4's repeat draw
  gave the same 0.9167.
- **Confound found by every judge audit:** each causal item carries an
  explicit connective (because, so, due to, …), no not_causal item does;
  a keyword rule scores 12/12. The agents accepted the finding; it is a
  property of the probe's twelve items, not of labkit.

## Costs

| probe | subagent tokens | subagent wall | analysis audit (agent-reported) | haiku calls |
|---|---|---|---|---|
| count-1 | 69,371 | 3m39s | 0.23 USD | — |
| count-2 | 71,517 | 7m32s | unknown | — |
| count-3 | 70,434 | 3m16s | unknown | — |
| judge-1 | 89,677 | 29m04s | ≈ 0.49 USD | unknown |
| judge-2 | 83,137 | 4m54s | 0.51 USD | unknown |
| judge-3 | 84,224 | 4m21s | 0.48 USD | unknown |
| judge-4 | 86,827 | 5m44s | 0.48 USD (repeated attempts: unknown) | unknown |

The subagents' own dollar cost is not reported by the harness: unknown.
The audit figures are the agents' reading of `labkit-audit`'s stderr, not
checked against a bill. The analysis audit is the largest single wait in
every run (about 1–3.5 minutes).

## Findings, each checked against the code at db1695d

1. **`usability log` with TASK.md's argument order crashes.** TASK.md
   writes `usability log <tag> "<step>" --log <file> -- <cmd>`; the parser
   takes `cmd_words` as `argparse.REMAINDER` right after `text`
   (`labkit/probes/usability_command.py:75`), so `--log <file> -- <cmd>`
   lands in the command: the line goes to `./log.md`, then `--log` is
   executed — a `FileNotFoundError` traceback. Reproduced. Hit by all
   three count probes; it lost early log lines and left stray `log.md`
   files. Probe tooling, not the lab path — but it falsifies the log the
   score reads.
2. **`labkit-audit` and `report-check` refuse the bare area name.**
   `repo.area_path` resolves `01-<name>` for `code-check`, `finalize`,
   `preflight`, `runlog` and `params`; `labkit/gates/audit.py` and
   `labkit/gates/report_check.py` take the argument as a plain `Path`.
   The refusal (`repo.no_such_area`) even suggests the name form that
   fails. Hit in four of seven probes; cost reruns, and in judge-4 a paid
   audit twice.
3. **`protocol-fill --list` omits the promise sentences.** The judge
   stamp holds three `sentence = "<…>"` lines in the TOML head (lines 67,
   74, 81 of a fresh stamp); `--list` names the eleven fields and not
   these. Every judge agent found them only by reading the file.
4. **`code-check` reads as an exemption the pre-commit does not grant.**
   At `seconds` it prints "schema, gate labels, placeholders: not checked
   — not owed at cost seconds" (`labkit/checks/code_check.py:571`); the
   pre-commit then refuses the open `<…>` promise sentence. judge-3 lost a
   commit to it. The line means "this check is not run here", and reads as
   "these are not owed".
5. **The printed `--from-run` command names the protocol by file name
   only** (`labkit/formats/protocol_report.py:550`, `f.name`). From the
   repo root, where the agents work, it fails "no such file" (count-3).
6. **Audit findings are decided by hand in TOML.** `labkit-audit` says
   "set status (fixed / accepted / deferred / dismissed)"
   (`audit.py:740`); there is no command for it. count-3 wrote an
   unescaped quote, and the next `--from-run` refused the file as "not
   TOML".
7. **The stamped skeleton is mostly reading.** The judge agents read about
   650 lines (`01_measure.py` 435, `00_prepare.py` 132, the test) to
   change about eight; the count agents name `INPUTS`, `METRIC_KEY` and
   the reader as derivable from the data. This meets the trigger of the
   TODO row "Zählvorlage aus Task-Feldern" (a Sonnet probe names the stubs
   as the obstacle).
8. **The `--from-run` Result line is a key dump**, which two agents
   reworded by hand. Already allowed by the lane text; noted, not a fault.

Not labkit's:

- **pytest missing in the venv** (all seven): an artefact of this setup.
  The stamped `requirements.txt` lists pytest, but it pins labkit at
  `v0.99.0` from GitHub, not `db1695d`, so the operator built the envs
  from the archive and linked them with `--venv`. `finalize` warned; the
  area tests ran only where an agent installed pytest itself.
- **zsh `noclobber`** cost judge-1 and count-3 an attempt each (`>` onto
  an existing file).
- **judge-1's "hang"** is the laptop's sleep (above).

## Consequence

- Findings 1–6 are small and local; they are the next fixes, each with a
  reproduction first. Finding 2 and 3 cost the most across probes.
- Finding 7 is the case for a data-derived stamp; it stays behind its TODO
  row's acceptance line (do not cut the template to the weakest model).
- The analysis audit dominates time and the only dollar cost at
  `seconds`. Whether that is too much is a decision of the standard
  (LAB-017 The number of audits follows the cost tier), not a fault; the
  numbers here are its evidence.
- No architecture change is indicated by these runs.

## After the series

The same day, after this report, findings 1–5 were fixed and finding 6
got an aid (CHANGELOG, Unreleased; commits `4a4a130`..`80d2ff0`):

| finding | state |
|---|---|
| 1 `usability log` argument order | fixed: the command is what follows the first `--` |
| 2 area name at `labkit-audit`, `report-check` | fixed: both resolve it through `repo.area_path` |
| 3 promise sentences not listed | fixed: `--list` names them, `"C1 sentence=…"` fills them as a TOML string |
| 4 "not owed" at `seconds` | fixed: the line separates the review (not owed) from the open fields (owed) |
| 5 bare file name in the adopt line | fixed: `repo.adopt_command` names the path from the working directory |
| 6 hand-written audit decisions | **aid, not fixed**: file head and refusal name the TOML string forms; invalid TOML stays possible |

- **An independent review of these fixes** (same day) found eleven
  more problems in them — among them valid id spellings dropped from
  `--list`, characters that broke a written TOML string, two adopt hints
  still without a protocol. All but one pre-existing one are fixed
  (CHANGELOG, Unreleased); the remaining one is in TODO.md.
- **Areas stamped before keep their stamped scripts.** The adopt line of
  finding 5 lives in the measure-script templates; an area stamped before
  the fix prints the bare file name until it is stamped again. The probes
  above are such areas.
- **The next series** uses freshly stamped areas on one pinned commit,
  with environments prepared in full (pytest included), after an
  independent review of the fixes. Its main measure is operating friction
  — wrong calls, repairs, manual interventions, correct binding of the
  result; wall-clock alongside, since six runs show no reliable speed-up.
