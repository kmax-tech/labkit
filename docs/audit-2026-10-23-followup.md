# Repo audit 2026-10-23, follow-up

Question: did the 28 commits that worked off the morning's register
(`docs/audit-2026-10-23.md`, state `b4cd032`) leave errors or drift, and
what is still worth improving. State at the audit: `main` at `e5f0438`,
tree clean, `.githooks/pre-commit` green (ruff, format, pyright, 1756
tests and 6328 subtests, 77 s). Three readers (clarity, drift, homes) ran
in parallel; every finding below was opened at its line before it was
listed. Line numbers are those of `e5f0438`.

## Summary

The register is worked off: every item D1–D6, B1, B2, C1–C8 and the
small list is fixed at the place it named, the seven doubled homes have
one home each, and `tests/test_one_home.py` holds five of them by grep.
What the 28 commits left is of one class: prose written for the new
homes that the code does not keep — a rule table whose row for runlog
does not match the code, three `--help`/docstring exit contracts that
disagree with the returns, two evidence-kind labels outside the
vocabulary the same docstring introduces, and six message sites that
still spell `runs/` by hand. No bug that changes a verdict; one
blocker text that labels non-findings as findings.

## Drift with effect

| # | Where | What happens |
|---|---|---|
| B1 | `tests/test_run_record_atomic.py:129-143` vs `labkit/run/runlog.py:327` | Flaky: the test fakes the uuid draws but not the clock. The run id is `strftime(...)_<hex>`; when the two `runlog.run` calls straddle a second boundary the second id differs in its time part, the repeated draw `aaaa` is free and kept, and the assertion on `_bbbb` fails. Seen once in the pre-commit hook under `-n auto` at 16:30:03 (1 failed, 1755 passed); five reruns alone passed. A flaky test in the hook refuses commits at random. Fix: patch `runlog.time.strftime` to a constant in the test. |
| F1 | `labkit/formats/findings.py:286-288` vs `labkit/run/start_check.py:167-168`, `:501-502`, `:530-533` | The gate table says a full run's undecided preflight WARNING "is told". The code prints the open warnings only on the acknowledged path (`LABKIT_UNFROZEN=1`); a clean full run returns at `:501` before them. A NOTE lands in the warnings list (`:168`) and is printed as "open WARNING(s)". The table is the one home of the rules and does not say this. |
| F2 | `labkit/formats/findings.py:277-296` vs `:1208`, `labkit/gates/preflight.py:372`, `:392`, `labkit/run/start_check.py:234`, `labkit/formats/protocol_report.py:448` | `audit_record_gap` grades "still open" on its own (`record.open`, any grade, the named record only) for three callers; none is a row of the table that calls itself the one home. preflight reports one undecided finding twice: "undecided in …" (`:374`) and "preflight_audit: … still `open`" (`:394`). |
| F3 | `labkit/gates/claude_hooks.py:73-74` vs `:488-489`, `:582-585`, `:611`, `:623-624` | Docstring: usage errors exit 1. Code: unknown event, `sessions --run` without id and `undecided` without paths return 2; a bare `claude-hook` returns 1. Exit 2 means "block" in pre-run, "keep working" in stop and "usage" in `undecided`. `claude-hook --help` (`:606-610`) prints no exit contract. |
| F4 | `labkit/gates/finalize.py:300-306` vs `labkit/checks/intent_check.py:331-341`, `:368` | On a nonzero intent-check, every stdout line becomes a BLOCKER — including "intent-check: using <run>/metrics.json (…)" and "WARNING — … Checking anyway". The reader sees `BLOCKER: intent-check: intent-check: using …` and reads a non-finding as a violated promise. intent-check holds its findings as data (`intent_check.py:211`); finalize parses text. |
| F5 | `labkit/gates/report_check.py:812-817` vs `:839-840`, `:852` | `hold_report`'s docstring puts "static evidence" on the undeclared-run warning; the code marks that GUARANTEED and the unsourced-numbers warning STATIC_EVIDENCE. |
| F6 | `labkit/checks/code_check.py:11-13` vs `:33`, `:38` | The head says each check carries GUARANTEED or STATIC EVIDENCE; checks 1b and 1c are labelled "AUTOMATED", which is no value of `gate.EVIDENCE_KINDS` (code gives GUARANTEED: `code_scan.py:212`, `prompt_check.py:61`). Left standing by `497ce10`. |
| F7 | `CHANGELOG.md:535` vs `:147`, `labkit/gates/report_check.py:26` | Unreleased calls report-check's registration "station 1"; the Fixed entry in the same section and the code say stage 2. |

## Doubled homes left or created

| Logic | Occurrences | State |
|---|---|---|
| `runs/` spelled by hand in messages | `labkit/tools/params.py:339`, `labkit/run/start_check.py:363`, `:375`, `labkit/run/runlog.py:282`, `labkit/gates/decision_review.py:203`, `labkit/tools/protocol_fill.py:699` | six left; the guard (`tests/test_one_home.py:83`) matches `"runs"` double-quoted only. tests/ spell it 145 times and build runs by hand in eight fixtures; the guard reads `labkit/` only |
| progress line beside `console.progress` | `labkit/gates/audit.py:1119-1123`, `labkit/gates/decision_review.py:320-324` (multi-line `print(…, file=sys.stderr)`); guard `:102-106` matches one line | created by `86df3ec` |
| protocol `## ` section cut | `labkit/probes/protocol_reading.py:74` (regex, not fence-aware) beside `protocol_block.section_starts`; guard `:98` matches `startswith` only | one left |
| refusal outside `console.refuse` | `labkit/gates/claude_hooks.py:582-585` (stderr, exit 2, by hand), `labkit/formats/rules.py:439-440` (stderr, exit 1), `labkit/gates/claude_hooks.py:508-509` (stdout, exit 1) | three left |
| `evidence_kind` vocabulary | `labkit/formats/gate.py:50-56` validated; `labkit/tools/params.py:83`, `:155` free string "guaranteed: absent; as a fault static evidence" | same field name, two vocabularies |
| home table in `docs/architecture.md` | names `runs.run_dirs`, `files.write_atomic`, `jsonl.record_lines`, `findings.open_findings`; not `runs.run_path`/`metrics_path`, `jsonl.objects`/`data_rows`, `scope_sha.area_files`, `llm.model_entry`, `protocol_block.section_starts`, `console.refuse`/`progress` | six new homes without a row |
| guards | `runs.run_dirs` and `llm.model_entry` have no grep guard; no test names `model_entry` | — |

Merged and clean: `runs.run_dirs` (one walk), `scope_sha.area_files`,
`llm.model_entry` (the copy in `repo` is deleted, not redirected),
`jsonl.objects` (three streamed peeks with a `home:` note, `batch` a
named second home), `findings.open_findings` (no `.open` loop left),
`files.write_atomic` (the index append is the documented exception),
`gate.EXIT_CONTRACT` (one constant, `AUDIT_EXIT_CONTRACT` deliberately
apart), launch.json (test-held).

## Clarity

| # | Where | Finding |
|---|---|---|
| K1 | `labkit/formats/findings.py:890-891` | `audit_coverage` docstring claims "`preflight` for the freeze (runlog, preflight)"; its only caller is report-check in mode analysis (`report_check.py:355`). Runlog and preflight use `audit_record_gap`. |
| K2 | `labkit/gates/report_check.py:582`, `labkit/gates/audit.py:479` | `findings = Findings()` shadows the imported module `findings` (`report_check.py:100`), used in other functions of the same file; finalize and preflight import it as `audit_findings`. No bug (different functions), one name for two things. |
| K3 | `labkit/run/provenance.py:337`, `labkit/run/runlog.py:526-531` | `source_digest` digests run outputs and data files too; "source" means code everywhere else (`script-source`, `untracked_sources`). Its directory branch suggests directory outputs; `output()` (`:481`) takes any path, `_finalize` opens it as a file first (`IsADirectoryError`, loud but late). |
| K4 | `labkit/formats/runs.py:185`, `labkit/checks/recheck.py:114` | `runs.run_path` vs `runs.runs_path` differ by one letter; `recheck.run_dir()` is a function that chooses a run while `run_dir` is the signature name for a run's directory. |
| K5 | `labkit/gates/audit.py` `--help` | Ends with the audit exit contract; `--review` has another (`decision_review.py:34`: 0 upheld, 1 not upheld, 2 no review), which the help does not name. |
| K6 | `labkit/formats/findings.py:311` | `limit_line(record, n, finding)` ignores `record` and `n`; one caller (`result_render.py:59`). |
| K7 | `labkit/formats/scope_sha.py:425-429` | `area_snapshot(globs=…)` narrows the listed files; the import closure starts from `area_files(area)` with the default globs, so `scope-sha --globs` does not narrow what is followed. |

## Small

- `docs/notes/2026-10-23-documentation-navigation.md` — linked from nowhere; the other four notes of the day are linked from their code.
- `labkit/run/batch.py:538`, `labkit/docs/standard.md:585` — name `answers.read_jsonl`; no module `answers`, the function is `lanes.read_jsonl` (`lanes.py:88`). Pre-existing.
- `pyproject.toml:19` — comment says `just timeline audit ARGS`; the recipe takes the layered path (`just timeline gates.audit …`). Pre-existing.
- `labkit/__pycache__/` holds 35 `.pyc` of modules that moved into the layer packages (ignored, harmless; `find labkit -name __pycache__ -exec rm -r {} +`).

## Verified, no drift

Renames of `e1b2f67` (ledger, trace, `source_digest`): no old name in
code, docs, templates or tests. The five dated notes: four linked, each
"current contract is in X" true. Shortened docstrings of `e5f0438`
(console, decision_review, llm, provenance) match the code below them.
Counts ("three tiers", "nine are static evidence") hold. Every
`` `module.name` `` in README, AGENTS.md, docs/, the standard, the
templates and the agent files resolves to a definition at HEAD.
