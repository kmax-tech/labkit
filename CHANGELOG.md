# Changelog

labkit does not carry legacy paths: a format or API change is a break,
announced here with the last version that still has the old behaviour.
Reproduce an old run with the repo's own commit and the labkit version it
pins (`requirements.txt` / `requirements.lock`).

## 0.48.0 — 2026-10-07

### Breaking

Last version that reads the old formats: **v0.47.0**. A repo with frozen
protocols in the old head, runs without `schema_version` or an old run
index stays on its pin until new work starts there.

- **The protocol head is data** (TODO 8). `Standard`, `Protocol id`, `Type`,
  `Cost`, `Frozen before run` and `Preflight audit` moved from prose lines
  into the `[protocol]` table of the protocol's one ```toml block (Standard
  0.18), read by the new `labkit.protocol_block` — `tomllib`, exact keys,
  typed values. A typo is an error naming the field: `Cost: second` used to
  read as undeclared and so as `hours`. A protocol without the table is
  refused by every command.
- **Prose fields by exact template label.** `protocol-check` holds each
  field by its label (`protocol_check.FIELDS`), not by keywords searched in
  the whole file: a word anywhere satisfied a field (`prompt` in a sentence
  covered "Model I/O"), a narrow word failed a filled one (`**Terms:**`). A
  test binds `FIELDS` to the template and the seconds cut to its markers.
  "Answer to the question", "Raw output" and "Analysis audit" are owed after
  the run (the run-unreported check), no longer before it. Removed:
  `check_text`, `graduate`, `severity_of`, `cost_tier_of`, `FROZEN_YES`,
  `TYPE_MEASUREMENT`, `protocol_identity`, `protocol_id_of`,
  `criterion_present`; new: `check_fields`, `fields`, `owed`.
- **The promise digest covers the `[[promise]]` tables only** (canonical
  JSON), not the block text: freezing or stamping the audit line in the
  head must not read as a changed promise. Runs recorded under 0.46/0.47
  carry the old digest; `recheck` against them reports a changed block.
- **Legacy paths removed:** the intent letters K/S/W/N (only C/A/B are
  ids); protocols below Standard 0.16 and the area-based run choice
  (`choose_legacy`, `gate_metrics`, `latest_metrics`, `runs_by_intent_keys`);
  runs without `schema_version` (state `legacy`, never `completed`);
  `runlog migrate-index`; the measurement short form (`Type: measurement`
  — the seconds cut replaced it); the old admissibility words (`stop
  rule`, `kill`, `Abbruch`); `intent_check.ledger_ids`.
- An unstamped protocol id binds nothing: `intent-check` needs `--metrics`,
  `finalize` reports a blocker.

## 0.47.0 — 2026-10-07

### Changed

- **Template and field guide speak C/A/B** (TODO 7): the protocol template
  stamps `[C]` criterion, `[A]` admissibility condition, `[B]` registered
  branch, with keys `c1_pass`, `a1_pass`, `b1_branch`. The field "Stop rule"
  is now "Admissibility condition", "Registered fork" is "Registered
  branch"; null conditions and anchors carry `[A]` ids. `protocol-check`
  accepts the new label; the old labels (`stop rule`, `kill`, `Abbruch`) and
  the letters K/S/W/N are still read and go with the legacy release (TODO 8).

### Added

- `labkit-audit <AREA> --mode preflight|analysis`: the experiment-preflight
  audit as a command through `labkit.llm` (any `models.toml` alias, default
  `opus`), synchronous with a timeout; the instructions ship with the
  package (`experiment-preflight.agent.md`). Exit 1 on a blocker OR a
  warning, 2 when no audit could be made.

## 0.46.0 — 2026-10-06

### Breaking

Last version with the old names: **v0.45.0**.

- **Run read side moved to `labkit.runs`.** `is_alive`, `run_state`,
  `read_run_config`, `RunConfigError`, `completion_state`,
  `completed_runs`, `FAILED_STATES` are no longer in `labkit.runlog`.
  `runlog._is_alive` and `runlog.is_alive` are one name: `runs.is_alive`.
- **`promises.scope_sha` is `promises.declared_scope_sha`.** Runs record
  `config.json → promises.ids.<id>.declared_scope_sha` (was `scope_sha`).
  The area audit stamp `scope-sha` is unchanged.
- **`code_check.find_protocols` / `find_repo` are `repo.area_protocols` /
  `repo.layout_root`.**

### Stricter (correct inputs pass as before; these now fail loud)

- A v2 run with `metrics.json` but no `completion.json` is no longer
  chosen or accepted by `recheck`, `runlog.Run(derived_from=…)`,
  intent-check's choice for protocols without an id, or `usability score`.
- An unreadable `config.json` shows as `corrupt` in `runlog`, makes
  `runlog --wait` and `runlog reindex` exit 2, and is listed, never chosen,
  by intent-check. An unreadable `metrics.json` ends intent-check with exit
  2 instead of falling back to an older run.
- A git failure inside a repository raises `repo.GitError`; it used to read
  as an empty answer ("clean tree").
- `runlog` no longer swallows an unreadable protocol and names a malformed
  `Protocol id:` in its warning.
- Promise block (protocols that carry one):
  - `code-check` / `preflight` block a malformed block, a declared scope that
    does not resolve, and a declared key that appears nowhere in the code.
  - `finalize` blocks a declared scope changed since the run.
  - `recheck` refuses a note whose promise block or declared scope changed
    since the run.
  - `intent-check` / `finalize` report a block constant the run recorded
    under the same name with another value.
- `finalize` holds `c<i>_n` to the recorded inputs like `k<i>_n`.
- `llm` calls `claude -p` with `--tools ""`: a judgement runs without the
  CLI's built-in tools, so a prompt that says "read <file>" cannot send the
  model to its working directory instead of the inlined text.

### Added

- `labkit.promises`: the promise block — one fenced TOML block of
  `[[promise]]` entries (id `C`/`A`/`B`, key, sentence, declared scope,
  constants); `runlog` records its digest and a hash per declared scope.
  Contract: `docs/promise-block.md`.
- `labkit.runs` (read a run), `labkit.repo` (area protocols, repo root,
  git), `protocol_check.protocol_identity` (one reading of `Protocol id:`).
- `code-check` reads intent keys passed as keyword arguments
  (`r.metrics(c1_pass=…)` drew a false blocker before).
- `endpoint_lease`: atomic record writes under a directory `flock`; an
  unreadable record counts as busy for `UNREADABLE_GRACE_S`, then is
  removed with a message.
- `AGENTS.md` (with `CLAUDE.md` as a symlink), `docs/architecture.md`,
  `docs/coding-style.md` (vendored), `pip install -e '.[dev]'` for tests.

### Unchanged behaviour, new structure

- `intent_check._main` dispatches to `choose_explicit` / `choose_bound` /
  `choose_legacy`; `llm._complete_once` dispatches to one adapter per
  backend.
