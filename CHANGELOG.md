# Changelog

labkit does not carry legacy paths: a format or API change is a break,
announced here with the last version that still has the old behaviour.
Reproduce an old run with the repo's own commit and the labkit version it
pins (`requirements.txt` / `requirements.lock`).

## Unreleased (since v0.45.0)

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
