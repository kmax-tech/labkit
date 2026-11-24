# Plan: one home for reading an area from the command line

Plan, 2026-11-24, for the author's decision; nothing built. Follows the third audit of the same day ([note](2026-11-24-repo-audit-3.md), open point "argument parsing").

## The problem

Thirteen command lines in eleven console commands take an experiment area. The reading of that argument has no single home:

| How the area is read | Command lines | Commands                                                                                    |
|----------------------|---------------|---------------------------------------------------------------------------------------------|
| `repo.area_args`     | 2             | preflight, finalize                                                                         |
| a loop of its own    | 4             | code-check, labkit-params, labkit-run-diff, scope-sha                                       |
| argparse             | 7             | labkit-audit, labkit-next, labkit-adopt, report-check, runlog, runlog reindex, runlog start |

What they share is only `repo.area_path` (a bare name to its area) and `repo.no_such_area` (the refusal sentence). The step "not a directory, so refuse with that sentence" stands in eleven places. Consequences a user meets:

- `scope-sha x` from the repository root reads `x` as a scope file, not as the area `experiments/01-x`, and refuses with "scope file(s) missing: x" (`labkit/formats/scope_sha.py:965`: a positional is the area only if it is a directory as written). Its own comment says "like every other gate".
- `runlog start x -- …` does not resolve `x` either (`labkit/run/runlog_command.py:463`, `type=Path`) and refuses with a sentence of its own, while `runlog x` resolves the same name.
- labkit-params and code-check copy the loop of `area_args`, each with one extra flag (`--run`, `--bundle`).
- In every loop of its own, a flag without its value reads as "unexpected argument '--protocol'", a repeated `--protocol` is accepted and the last one wins, and AREA must come first. No test asserts the "unexpected argument" refusal.

Inventory with every command's refusals, help and tests: the survey of 2026-11-24 (kept by the session; its table is summarised here).

## Target

> Revised the same day after a second opinion: no second general argument parser beside argparse. The first draft extended `area_args` with options, positionals and named refusals — work argparse from the standard library already does.

One resolution, and argparse for reading the line:

1. **`repo.existing_area(tool, given) -> Path`** — the one resolution of an area argument: a bare name through `area_path`, a name several areas carry refused, a path that is no directory refused with `no_such_area`; raises `console.Refused(tool, …)`. Every area command calls it after reading its line, whatever reads the line; `scope-sha --area` and its positional area alike.
2. **argparse for the lines read by hand today** — preflight, finalize, labkit-params, code-check, labkit-run-diff — through one small builder in `repo`, `area_parser(tool, description, *, protocol=True) -> argparse.ArgumentParser`, which adds the `area` positional and, where the command reads one, `--protocol`; each command adds its own flags (`--run`, `--bundle`, the two run ids). `area_args` then becomes `area_parser` plus `existing_area`, or goes.
3. **Repeated options, decided per option:** a single-value option given twice is refused by name (`--protocol`, `--run`, `--bundle`, `--log`, `--max-seconds`) through one small `argparse.Action` in `repo`; options meant to repeat stay as they are (`protocol-fill --prompt-file`, scope-sha's FILE list). argparse already names a missing value ("expected one argument").
4. **Order:** the area comes first in every command labkit prints and documents (`labkit/formats/commands.py:462`, `:478`); argparse accepts flags before it too, and that stays — no new restriction without a reason.

Left as they are: commands that take a protocol file (intent-check, protocol-fill, protocol-check); scope-sha's own loop (alias `--area`, default `.`, free FILE list, `--globs`) — it only gains `existing_area`.

To check before step 4, since tests and agents read these texts: argparse writes its refusal as `usage: … / tool: error: …`, the hand loops as `console.refuse` (`tool: …`). Which tests assert the refusal and help text of preflight, finalize, params, code-check and run-diff (`tests/test_cli_help.py`, `tests/test_streams.py`, `tests/test_no_such_area.py`, `tests/test_preflight.py:326`, `tests/test_finalize.py:327`), and whether a refusal an agent meets keeps its way out (`tests/test_ways_out_data.py`). If the console form must stay, the builder sets `exit_on_error=False` and passes argparse's message to `console.refuse`.

Two limits hold for the whole plan:

- **`area_parser` stays small:** the shared setup of `area` and `--protocol`, and the one action that refuses a single-value option given twice — no parsing logic of its own beside argparse.
- **Changed messages are accepted on purpose, not only re-recorded in tests:** for a missing option value, an unknown or ambiguous area and a repeated option, each message read once as a person meets it — does it say what is wrong and what to type — with exit 2, and the agent-facing refusals keep their way out.

## Steps, one commit each

1. `existing_area` in `repo`, with rule tests (bare name, ambiguous name, no directory, a path as written); `area_args` uses it.
2. The argparse commands call it after `parse_args` instead of their own check: labkit-audit, labkit-next, labkit-adopt, report-check, runlog, runlog reindex (`labkit/gates/audit.py:441`, `labkit/tools/adopt.py:136`, `labkit/tools/next_command.py:92`, `labkit/tools/report_command.py:54`, `labkit/run/runlog_command.py:560`, `:636`). Output unchanged.
3. The two faults a user meets: `runlog start` and scope-sha (positional and `--area`) resolve their area through `existing_area`. A fix: they accept a bare name and refuse with the shared sentence. CHANGELOG.

Decision point after step 3: steps 1–3 fix what a user meets. Whether the hand-read lines move to argparse (steps 4–6) is decided then, with the text check above done.

4. `area_parser` and the repeat-refusing action in `repo`, with tests for the missing value, the repeated option and its valid twin, and the order.
5. preflight, finalize, labkit-params, code-check and labkit-run-diff read their lines through `area_parser`; their loops go, and `area_args` with them.
6. Docs: `docs/architecture.md` ("one home per question": the area argument), README where a refusal is quoted, CHANGELOG.

## What changes for a user

- After step 3: a bare area name works in every area command, scope-sha and runlog start included, and every refusal of an area reads the same.
- After step 5: a flag without its value and a single-value flag given twice are named as such; flags may stand before the area in the hand-read commands too.
- Nothing a command accepts today is refused, except a single-value flag given twice (a stricter refusal: a fix) and `labkit-run-diff --protocol`, which it never read.

## Acceptance

- `grep "no_such_area("` outside `repo.py` finds no gate, tool or check (the audit prompt's own sentence aside).
- After step 5, no hand loop for an area command (`tests/test_one_home.py` gains the pattern, home `repo`).
- `existing_area` tested at the rule layer; each command reaching it once (`tests/test_no_such_area.py`, scope-sha and runlog start join).
- The whole suite green; `just guard` before each commit; an independent reader (`code-clarity`) on the final diff.

## Decisions taken

1. `scope-sha --area` stays, beside the positional area; both go through `existing_area`.
2. The area comes first as labkit prints and documents it; an order argparse accepts today is not forbidden.
3. Repeated options are decided per option (Target, point 3), not refused wholesale.

## Side finding, not part of this plan

`intent-check PROTOCOL --metrics FILE extra` ignores `extra`: `_named` reads `argv[1:3]` and never looks at what follows (`labkit/checks/intent_check.py:197`). A step of its own.
