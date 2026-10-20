# Protocol–run binding: how it was built — 2026-10-20

The contract itself is [protocol-run-binding](../protocol-run-binding.md);
this note keeps the history it no longer tells.

## Versions

- 0.20.0: the protocol id (`p-` plus 16 hex digits), stamped at creation.
- 0.21.0: the binding in `config.json`, `schema_version`, `completion.json`,
  `runlog reindex`, the `protocol_id` index column and the index lock.
- 0.22.0: `intent-check` selects by id. With it the binding was complete:
  a protocol has an identity, a run records it, every check that pairs the
  two goes through the id.
- 0.48.0: the id moved into the TOML head; the prose head and the legacy
  paths were removed. A protocol with a prose head (standard 0.16/0.17) is
  read with labkit 0.47.
- 0.72.3: a resumed output file records the runs it continues
  (`rows_from`, `continues`).
- after 0.99.0 (CHANGELOG, Unreleased): `run_kind` replaced the boolean
  `long`; schema 3. The details: [run kinds](2026-10-20-run-kinds.md).

## What changed in the readers

- Before 0.21, `metrics.json` alone marked a finished run. The completion
  record made a broken finalization (`unfinalized`) and results gone under
  a completion marker (`corrupt`) tell themselves apart.
- `runlog active` kept its first state and gained the ones the completion
  record makes possible (the contract said "unchanged for the first state,
  one state added"); a record that cannot be read is `unreadable`.
- `--wait` kept its exit codes when the new states came: both are failures
  (exit 2), told apart by their messages.
- `completion.json` carries the git state at the run's END, the state the
  index column always carried; the start state stays in `config.json`, so
  the two are distinguishable, which they were not before 0.21.
- The selection rule "newest run reporting any intent key" dates from
  2026-09-09: a probe run without intent keys must not shadow the gate run.
  The exclusion of repeats (2026-10-14), the refusal of a same-second rival
  (2026-10-15) and of a newer unreadable run (2026-10-06) came later.
