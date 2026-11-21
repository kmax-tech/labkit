# Audit 2026-10-27 (second) — the error path and the handover

*Scope: what an agent or person is told to do when a gate stops them, the
new terminal handover (`protocol-fill --handover`, `labkit-audit
--findings` as recovery entry — uncommitted work on top of `c7b1f8d`), how
it overlaps with `--decide` and `--discuss`, drift, single homes and
configuration. The whole-repo register of the same day is
[audit-2026-10-27.md](audit-2026-10-27.md); its rows are not repeated
here. Method: ground truth first; three readers in parallel (clarity on
the handover diff, drift, homes); every row below re-opened, the marked
ones re-run in scratch repos built with the test fixtures
(`e2e.Lab`, `judge_area`). Evidence: **V** verified here (lines opened or
scenario run), **RR** the reader ran it, **R** the reader read it. The
rows describe the state audited; what was done with each stands under
"State" at the end.*

## Ground truth

- HEAD `c7b1f8d` in a fresh clone, its own labkit on `PYTHONPATH`, empty
  `HOME`: 2060 passed, 1 skipped (`test_runlog_env`, no lock), exit 0.
  A `git archive` copy run with the repo's venv imports the working
  tree's labkit through the editable install — not a HEAD check.
- Working tree (handover work uncommitted; a second session committed
  `ec3026e` during the audit): ruff, format, pyright clean.
- `python -m labkit.formats.rules check` and `refs`: 0 problems (RR).

## A. Error path with effect

| id | Finding | Ev. |
|---|---|---|
| H1 | `--findings` offers the terminal handover in every state. Clean area: `findings: … — no findings to decide`, then `unresolved exit (no model call): protocol-fill … --handover …`, exit 0. Area with no audit yet: the handover line, then the refusal "no findings record — follow protocol-check --contract", exit 2. The lines are printed whenever the area has a protocol (`labkit/gates/audit.py:1593-1599`), before the no-record refusal (`:1600-1604`). The note (`notes/2026-10-27-handover-recovery.md:18-19`) and the template's working loop say it directs to the workflow. | V |
| H2 | A handover that no longer matches is silent. `handovers.valid` drops every failed condition with `continue` (`labkit/formats/handovers.py:270-301`); its docstring says "normal checks report the errors" (`:253`) — none reports an edited report, a changed protocol hash or a newly declared result. Run: one sentence appended to the generated `REPORT.md` → stop exit 2 with the original loss plus "recorded evidence loss — restore it or hand over unresolved" (`:242`); no word that a handover exists. The hook texts name only restoring (`labkit/gates/claude_hooks.py:887-893`, `:990-998`); the pre-commit echo calls every `undecided` failure "an audit BLOCKER nobody decided" (`labkit/gates/install_hooks.py:108`). | V |
| H3 | The handover report is frozen byte for byte (`handovers.py:293`) and every printed command names the same file (`repo.handover_command`, default `REPORT.md`, `labkit/formats/repo.py:120`). `--into` and `--discuss` write blocks into that file in place (`protocol_fill.discuss_into`, `labkit/tools/protocol_fill.py:863`). So (a) a second area handed over into `REPORT.md` with `--force` voids the first area's acknowledgement; (b) a discussion or result block added later voids it; (c) the report cannot name the open findings: `report_text` writes protocol, why, tried and a link (`handovers.py:185-198`), and any added line voids it. The plan wanted the handover block to name the findings by record and number; the previous template asked the report to say "which findings remain". | V (edit voids, text); R (a, b) |
| H4 | A staged handover record that is not UTF-8 crashes the pre-commit: `missing_evidence` calls `text_at` outside the decode guard (`handovers.py:238`), `attempts.area_gaps` converts only `HandoverError` (`labkit/formats/attempts.py:451-455`), `undecided_blockers` catches only `AttemptError`. Run: tree → a sentence naming the file; index → `UnicodeDecodeError` traceback. A staged non-UTF-8 findings record yields an error without its path (`labkit/formats/findings.py:1259`, `:1267`). | V; RR (findings) |
| H5 | `finalize` prints `protocol-fill --from-run <run> --force` without the protocol (`labkit/gates/finalize.py:142`); argparse refuses it (`the following arguments are required: protocol`). `tests/test_one_home.py:52` misses it (its regex needs `{…}` between the command and the flag). Not handover work. | V; RR (test) |
| H6 | README step 4 says "Resolve the findings in the written `audits/*.toml`: each needs a status … and a reason" (`README.md:132-135`) — a hand edit, against `--decide` everywhere else (`findings.py:27-31`, `:587-588`, `audit.py:1387-1388`, the template, `claude_hooks.py:892`). `fixed` owes no reason (`findings.py:141`); the stop and pre-commit texts say "with reason" for all four. | V |
| H7 | Two instructions for the same exit. report-check's holds print `audit.HANDOVER` (`labkit/gates/report_check.py:341`, `:483`): a hand-written report, no command. WAYS_OUT, README, workflow and the template now go through `labkit-audit --findings` → `--decide … deferred` → `protocol-fill --handover`. The comment above it still calls HANDOVER "the one sentence" both print (`audit.py:1328-1333`). | V |
| H8 | The template's working loop says `protocol-check <PROTOCOL> --contract` "names what it owes" (`labkit/templates/AGENTS.md.template:16-17`); `--contract` ignores the protocol (`labkit/formats/protocol_report.py:691-693`): the output with and without it is identical (same md5), five fixed lane rows, none for high-cost compute. The `--findings` refusal points there too (`audit.py:1602`). | V |
| H9 | `README.md:242`: `--review --again` "the exit code is this draw's, not the state's"; the help (`audit.py:1111`), `docs/workflow.md:173-174` and the code (`gates/decision_review.py:366-369`) exit by state. | V |

## B. Overlap: `--decide`, `--discuss`, `--handover`

- **Order is consistent and enforced.** `--handover` refuses open readable
  BLOCKERs (`protocol_fill.py:1003-1012`); README, workflow, template and
  WAYS_OUT all say decide first; `deferred` owes a reason and takes no
  `--effect` (`findings.py:141`, `:1092-1104`). (V)
- **The printed `deferred` command carries a fixed reason**
  (`"unresolved; handed over without a result"`, `audit.py:1582-1591`),
  labelled "if handing this unresolved finding over" and printed before the
  handover line — a copy-paste decision without the author's reason. (V)
- **`deferred` now has two meanings.** It meant "its own task, later"
  (`findings.py:72-79`); every later `preflight` of another area lists
  deferred findings as "deferred elsewhere" reminders
  (`gates/preflight.py:395-415`), handed-over BLOCKERs included. (R)
- **`--discuss` vs `--handover`** is a split by purpose (a run exists and
  is looked at / no result), written nowhere as "use X when"
  (`README.md:155-173` side by side). They share `--why`, whose help now
  says "what blocks" for both (`protocol_fill.py:1134`) while
  `report_blocks.discuss_command` and the README keep "what refused the
  adoption". (V)
- **One step, five names:** handover, handover record, terminal handover,
  unresolved report, unresolved exit (`audit.py:1595`). The README terms
  table, the home of coined terms, has none (`README.md:266ff`). (V)

## C. Doubled homes (handover work)

| Logic | Occurrences | Home |
|---|---|---|
| Open BLOCKERs of an area | `gates/claude_hooks.py:962-965`, `tools/protocol_fill.py:1004-1006`, `gates/audit.py:1554-1558`, `:1581` (written out beside `Record.open`), `gates/report_check.py:513-517` | `findings.open_blockers`; the `open_findings` gate table (`findings.py:393-418`) lists none of the new callers |
| Integrity problems of an area (record errors + `area_gaps`) | `claude_hooks.py:950-958` (catches `AttemptError`), `audit.py:1541-1546` (+`UnicodeError`), `protocol_fill.py:1024-1027` (+`expected_evidence`) | one function; the differing catches cause H4 |
| File text in the tree or the index | `report_check.state_text` (`report_check.py:1098`, copy `:1363`, layer 4), `handovers.py:238`, `:266-286`, `findings.py:1257-1266`, `attempts.py:428-439` | `repo`, with the decode guard |
| Any protocol of the area declares a result | `protocol_fill.py:1014-1022` (writer), `handovers.py:285-292` (validator), `report_check.py:1359-1370` | `handovers` |
| What a handover binds | built in the tool (`protocol_fill.py:1023-1039`), re-derived in `handovers.valid` | `handovers.build` |
| Printed commands by hand | `protocol_fill.py:1011` (`labkit-audit … --findings`, drops `--protocol`), `finalize.py:142` (H5); `--decide` three ways: `audit.py:1431-1432`, `:1582-1591`, `report_check.py:522-525` | `repo.*_command`; a `test_one_home` rule for `labkit-audit {` |
| Handover command spelling | `repo.py:123-124`, `AGENTS.md.template:244-245`, `docs/workflow.md:273-274`, `README.md:169` — `tests/test_ways_out.py:75` reads only a flag right after a backtick: `--handover`, `--why`, `--tried`, `--into`, `--findings` unchecked (all exist today) | the test reads every flag of a code span |

Solved well: `area_records` is a strict view over the tolerant
`record_status` (one reader, two views); writer and validator share
`handovers.report_text` and `report_destination`; `runs.RUN_ID_LIKE`
reused for "no run ids"; the commit gate has one home
(`.githooks/pre-commit` ← `just check` ← VS Code task); ruff and pyright
configured only in `pyproject.toml`; the rules ledger checks clean.

## D. Configuration

- `models.toml.template:14` `[models.opus]` must match
  `audit.DEFAULT_MODEL = "opus"` (`gates/audit.py:130`); no test ties
  them. (V)
- `vscode-settings.json.template` `search.exclude` is a declared hand copy
  of `pyrightconfig.json.template`'s `exclude`, equal today, untied. (R)
- `"runs"` is a literal in four skip sets (`repo.py:203`,
  `run_record_check.py:67`, `provenance.py:525`, `import_check.py:73`);
  the two "not code" sets differ only by `.git`. (R)
- pytest flags `-n auto -p no:warnings` live only in the hook;
  `just test` and the editor run plain `pytest -q`; no
  `[tool.pytest.ini_options]`. (R)

## E. Small drift (one line each)

- `--findings` help: "the newest record's findings" (`audit.py:1082`);
  it shows every record with an open BLOCKER plus the newest, the errors
  and handover commands; other records are left out without a line. (V)
- `--findings` exits 2 after a complete listing when any evidence error
  exists (`audit.py:1605`); not in the help epilog; `README.md:247-249`
  calls 2 an execution error. (V)
- A misnamed record sorts last through the `"9999"` fallback
  (`findings.py:1274-1279`): `--findings` treats it as newest,
  `_newest_record` refuses it. (R)
- `protocol-fill`: module usage (`protocol_fill.py:18-24`) and
  `_run_mode` docstring (`:937-938`) lack `--handover`; `--into` help says
  only "the declared result"; `--force` help says only "overwrite a
  field"; `--why` help omits the no-run-ids rule enforced on it
  (`handovers.py:137-144`). (V)
- `record_status` says "Normal gates use `area_records`"; the stop/commit
  gate now calls `record_status` (`claude_hooks.py:957`) and its docstring
  still names `area_records` (`:938`). (V)
- Comment above WAYS_OUT: a bar lowered after the first measurement "is
  not held yet (TODO)" (`audit.py:1315-1321`); held since `be0e539`. (V)
- `docs/architecture.md:238`: a lost file "blocks … the stop and the
  commit" — a valid handover lets both pass; no row for
  `audits/handovers/*.json` in "Where verdicts are recorded". (R)
- "Tier" names repeat cost (`README.md:70`) and evidence kind
  (`README.md:200`); `TODO.md:1263` records C5 of the 10-23 audit as
  closed. (V)

## State (2026-10-27, after the fixes)

The found handover work was committed as found (`fde983d`, the reading
probe's evidence apart in `da52a1d`); each point below is its own commit
on top, every new test red at its parent.

| Row | Done | Commit |
|---|---|---|
| H4, C: decode, integrity, open BLOCKERs | `repo.text_at`/`state_text` name the file; `attempts.area_integrity`, `findings.open_blockers`; one-home rule | `74fe852` |
| H3, C: report form, what a handover binds | the handover block, one per protocol, in place; `remaining` in the record; `handovers.build`, `declared_results`; `--force` refused | `87a450e` |
| H2 | each record that no longer counts says why (`handovers.mismatch`); one way-out sentence for stop and pre-commit | `2bcb43e` |
| H1, E (`--findings`) | refusal first; the handover only beside an open BLOCKER or an evidence problem, two steps, `<why>` placeholder; hidden records counted; help | `c4b4a15` |
| H5 | finalize names the protocol; one-home rule covers the form | `d2456dc` |
| H6–H9 | README step 4 and `--again`; `audit.HANDOVER` names the command; `--contract PROTOCOL` prints its own row | `8704a6b` |
| B, C (`--decide`) | one name "handover", README term, which block a report gets, `--why` per mode; `repo.decide_command` | `fdc22e6` |
| D, E | help texts, record order, docstrings, architecture rows, tier wording; `tests/test_template_ties.py` | `2fb62a1` |
| C (ways-out test) | every flag of a code span checked | `2bae48f` |
| C (protocol reader) | a protocol is a regular file: a link, valid or broken, refused per state; `repo_sources` reads through `repo.state_text` (Breaking) | `d0e02f7` |
| B (`deferred`) | preflight tells a deferred finding a handover lists ("handed over unresolved — no result released") from one set aside for later; bound by the record's `remaining`, no new status | `0393ffc` |

Left open, deliberately:
- `"runs"` in four skip sets and the two "not code" sets: read, not
  re-checked here (R).
- pytest's `-n auto -p no:warnings` stand in the commit hook only; `just
  test` runs plain on purpose (a debugger needs one process).
