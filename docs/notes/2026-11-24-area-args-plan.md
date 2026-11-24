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

Two homes in `labkit/formats/repo.py`, one for each kind of parser, and nothing else that resolves or refuses an area:

1. **`existing_area(tool, given) -> Path`** — the one resolution: a bare name through `area_path`, a name several areas carry refused, a path that is no directory refused with `no_such_area`; raises `console.Refused(tool, …)`. argparse commands call it right after `parse_args`; `area_args` calls it too.
2. **`area_args(tool, argv, usage, *, options=(), positionals=(), protocol=True) -> AreaArgs | int`** — the reader for commands without argparse. An `Option` is a frozen dataclass `(flag, takes_value)`; `AreaArgs` gains `options: dict[str, str | bool]` and `positionals: tuple[str, ...]`. Refused by name: a flag without its value ("--run needs a value"), a flag given twice, a wrong number of positionals, an unknown word.

Left as they are, deliberately: commands that take a protocol file (intent-check, protocol-fill, protocol-check); labkit-audit's argparse (twelve flags, two-value `--decide`, mutual exclusion); the runlog subcommands' argparse (the `--` split of `runlog start`); report-check's `--if-reported PATH …` form for the hooks. These keep argparse and gain only `existing_area`.

## Steps, one commit each

1. `existing_area` in `repo`, with rule tests (bare name, ambiguous name, no directory, a path as written); `area_args` uses it. No command changes.
2. The argparse commands call `existing_area` after `parse_args` instead of their own check: labkit-audit, labkit-next, labkit-adopt, report-check, runlog, runlog reindex (`labkit/gates/audit.py:441`, `labkit/tools/adopt.py:136`, `labkit/tools/next_command.py:92`, `labkit/tools/report_command.py:54`, `labkit/run/runlog_command.py:560`, `:636`). Output unchanged; the existing tests hold.
3. `runlog start` resolves its area through `existing_area`: `runlog start x -- …` then finds `experiments/x` as `runlog x` does, and refuses with the shared sentence. A fix (it accepts more, refuses the same), named in CHANGELOG.
4. `area_args` gains `options`, `positionals` and `protocol`, the named refusals, and tests for each refusal and its valid twin — the first tests of "unexpected argument".
5. labkit-params (`--run`) and code-check (`--bundle`) move to `area_args`; their loops go. labkit-run-diff moves with `positionals=("OLD_RUN", "NEW_RUN")`, `protocol=False`.
6. scope-sha: its positional and `--area` go through `existing_area`, so a bare name is the area. Its loop stays (alias `--area`, default `.`, free FILE list, `--globs`); moving it would cost as much spec as it saves.
7. Docs: `docs/architecture.md` ("one home per question": the area argument), README command lines where a refusal sentence is quoted, CHANGELOG.

Steps 1–3 stand on their own and fix what a user meets; 4–6 remove the copies.

## What changes for a user

- A bare area name works in every area command, scope-sha and runlog start included.
- Every refusal of an area reads the same: `no such area: … — name it relative to …`.
- A flag without its value, a flag given twice and a word too many are named as such instead of "unexpected argument".
- Nothing a command accepted today is refused, except a repeated flag in the loops that now say so (a stricter refusal: a fix, not a break), and labkit-run-diff with `--protocol` (it never read one).

## Acceptance

- `grep "no_such_area("` outside `repo.py` finds no gate, tool or check (the audit prompt's own sentence aside).
- No loop of its own in params, code-check or run-diff (`tests/test_one_home.py` gains the pattern of the copied loop, with the home `repo`).
- For each command line: the bare-name case, the ambiguous name and the missing area tested once at the rule layer (`existing_area`, `area_args`), and once per command that the command reaches it (`tests/test_no_such_area.py` already holds most commands; scope-sha and runlog start join).
- The whole suite green; `just guard` green before each commit.
- An independent reader (`code-clarity`) on the final diff.

## Decisions for the author

1. **scope-sha `--area`:** keep it as an alias beside the positional area (step 6 as planned), or drop it in a Breaking release so scope-sha reads its area like every other command — dropping it simplifies the loop but breaks scripts that pass `--area`.
2. **AREA first:** keep "AREA comes first" in `area_args` (what the next-step commands print, `labkit/formats/commands.py:462`, `:478`), or accept flags before the area as argparse does — the second is friendlier, the first is what every printed command already does.

## Side finding, not part of this plan

`intent-check PROTOCOL --metrics FILE extra` ignores `extra`: `_named` reads `argv[1:3]` and never looks at what follows (`labkit/checks/intent_check.py:197`). A step of its own.
