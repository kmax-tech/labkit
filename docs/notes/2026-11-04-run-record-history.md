# The run record format — the incidents behind its rules

2026-11-04. The rules stand in `labkit/formats/runs.py` as the current
contract; this note keeps what happened, dated, so the docstrings do not
(the repo rule: the current rule first, the history in a note). One
entry per rule, in the module's order. The dates are the day the incident
was seen or reviewed; "review" is a code review of that day, "audit" a
repo audit, "round" a usability round.

| Rule (where) | Incident | Consequence |
|---|---|---|
| A run is alive only when the PID exists *and* its command line runs the recorded script; undecidable is None (`is_alive`) | 2026-08-15: `runlog` reported a run from August 13 as running — the OS had recycled its PID to a macOS service (`RemoteManagement`). Anyone following "look, don't ask" got a wrong answer and would not have restarted a run long dead. | the script-name check; None over a false True |
| The script name is matched as a word or a path's last component, never as a substring (`runs_script`) | review 2026-10-14: `not_01_measure.py` held a dead run "running" while a substring decided it | the bounded match |
| One spelling each for an audit file's name minute and its `date` minute (`NAME_MINUTE`, `DATE_MINUTE`) | audit 2026-10-27 (third): nine writers spelled them by hand | the two constants |
| A crashed run writes why (`FAILURE_FILE`) | 2026-10-23: a claude-cli answer another model wrote ended a run loudly, and the reason stood on stderr alone | `failure.json` |
| One spelling of the runs folder and the metrics file (`RUNS_DIR`, `METRICS_FILE`) | audit 2026-10-23: about twenty call sites spelled `area / "runs" / id` and `run / "metrics.json"` by hand | the constants |
| One spelling of the record's other files (`CONFIG_FILE`, `COMPLETION_FILE`, `OUTPUTS_FILE`) | audit 2026-10-27 (third, S6) | the constants |
| A token shaped like a run id with any suffix reads as a citation (`RUN_ID_LIKE`) | labkit-paper area 08, 2026-10-21: an agent typed `…T12-48-00_final` into the Answer; a gate that saw only `RUN_ID` saw no citation and let it through | the wider pattern for prose |
| Unreadable is not absent: a damaged config.json raises (`read_run_config`) | review 2026-10-06: skipping it silently made a broken newer run vanish, and an older one was chosen or reported in its place | `RunConfigError`; listings show `corrupt`, choices refuse |
| Recorded paths are repo-relative where the file lies in the repo (`recorded_path`) | 2026-10-14: a cloud run recorded `/home/user/...`; `02_analyze.py --check` and finalize's source check broke on every other machine, and a relative `data=` path was kept relative to the working directory of the moment | relative to the layout root, absolute only outside it |
| Stored values are equal only as texts (`as_stored`) | review 2026-10-20: a checker built on `==` took `True == 1` and `1 == 1.0`, and passed a recomputation of another type | `json.dumps` with sorted keys as the one equality |
| metrics.json must be a JSON object; unreadable raises (`read_metrics`) | review 2026-10-08: a list such as `["criterion_1_pass"]` read as metrics satisfied the guaranteed intent check; review 2026-10-06: skipping an unreadable file chose the next older run as if the newer had reported no intent keys | `MetricsError` naming the file |
| labkit's tables in config.json are held on read (`RECORD_TABLES`) | review 2026-10-20: a damaged table read as empty let a repeat with an empty config pass as comparable | the shape check |
| `derived_from` names a run id, never a path (`_derived_shape_problem`) | review 2026-10-20: `./<own run>` looped the walk forever, `../../<elsewhere>` left the area | the id-only rule |
| `repeat_of` and `draw` are held to their shape (`_repeat_shape_problem`) | review 2026-10-15: a damaged value read as "no repeat" put a repeat back into the answering choice | loud instead |
| A run's state is asked of its record, never of metrics.json alone (`state_of`) | review 2026-10-06: an unfinalized v2 run (metrics, no completion record) was rechecked as a kept number and accepted as a parent | the one state question |
| `RunSummary` states what a run is | code-navigation round 11, 2026-10-08: a person with an assistant got 1 of 8 such questions right from config.json keys and the patch file | the summary record |
| A record carries every field; a missing one is no null and no default (`_FIELDS`) | review 2026-10-20: dropping `"unfrozen_ack": true` made an acknowledged run reportable | the complete-record rule |
| One walk of `runs/` returns data; the caller decides what an unreadable run means (`read_run_dirs`) | audit 2026-10-13: listing, index, choice and completion walked `runs/` six times and each decided for itself | the one walk |
| One answering-run choice for intent-check, finalize and labkit-params | 2026-10-08: the choice stood in intent_check and finalize alike; a third copy for the parameter view was the line | one home |
