# Protocol–run binding

Which protocol does a run belong to? The contract below answers that. Terms
(`area`, `protocol`, `run`, `run index`, `metrics`, `documented runs`) are
coined in the README and not repeated here.

## Identity

A protocol carries its own id in the `[protocol]` table of its ```toml
block (the head, `labkit/protocol_block.py`):

```toml
[protocol]
standard = "0.19"
id = "p-9e2341c0390948dc"
```

- **Shape:** `p-` plus 16 lowercase hex digits (64 bit).
- **Origin:** stamped by `labkit-init exp <name>` at creation, never typed. Not
  derived from name or path, so renaming a protocol or moving an area leaves
  the identity intact.
- **Due:** in every protocol. A protocol with a prose head (Standard
  0.16/0.17) is read with labkit 0.47.
- **Unique:** in practice, not by proof. 64 bit make a collision a
  non-event; the stamp additionally scans the repository, and
  `protocol-check` reports the same id in two files as an error — the real
  source of duplicates is a protocol copied as the start of the next one.
- **Immutable** by rule. `protocol-check` compares against `git show
  HEAD:<path>` and warns when the working tree differs. The check is skipped
  for a file that is new, outside git, or unreadable by git, and it is not a
  proof: after the next commit the changed id is the state.

## Binding

A run records the protocol it belongs to. The binding lives in exactly one
place, `runs/<run_id>/config.json`, written before any work and never
rewritten:

```json
"protocol": {
  "id": "p-9e2341c0390948dc",
  "path": "PROTOCOL-s13-kette-headroom.md"
}
```

- `id` is the binding. `path` is relative to the run's `base_dir` (the area),
  serves lookup and diagnosis only, and may go stale (protocol renamed or
  moved). It is **not** refreshed — config.json is write-once. There is no
  alias register.
- The script names its protocol: `runlog.run(..., protocol=PROTOCOL)`. The
  path must lie inside `base_dir` and be one of the `PROTOCOL-*.md` found
  there.
- Omitted: exactly one protocol in the area binds to it, several are a hard
  error, none is `unbound` plus a warning.
- A protocol whose id is not yet stamped yields `"id": null` with the path
  filled — unbound, with a hint where to look; a full run (`long=True`) on
  it is refused. A protocol without a readable head refuses the run.
- The key always has the same shape. Missing protocol, missing id and found
  protocol differ in their VALUES, never in whether the key or the fields
  exist: no reader has to tell absent from null from object.

`protocol` follows `long` in `runlog.run(...)`, and `derived_from` follows
`protocol`, so no existing positional call shifts.

The file is named `config.json` and carries the provenance too. Renaming it
would break every reader of every finished run, so the term moves and the
file stays: **run metadata** means `runs/<run_id>/config.json`.

## Run completion

A run directory says for itself whether it finished: complete when
`metrics.json` AND `completion.json` exist. A run whose `config.json`
carries no `schema_version` was written before labkit 0.21 (when
`metrics.json` alone marked a finish); its state is `legacy`, it is never
`completed` here, and it is read with labkit 0.47.

`schema_version` is stamped into `config.json` at run START, which is what
makes the distinction decidable: at the moment a reader has to judge a run,
`completion.json` may be exactly the file that is missing.

`completion.json`, written atomically (temp file in the same directory, then
rename) so it is either absent or whole:

```json
{
  "schema_version": 2,
  "finished": "2026-09-26T21:14:02",
  "git": "a1b2c3d-dirty",
  "git_full": "a1b2c3d4e5f6...",
  "note": "swap held, 4 anchors out of band"
}
```

`git`/`git_full` are the state at the END of the run — the same state the
index column has always carried, so the column's meaning does not change.
The state at the start stays in `config.json`; the two remain
distinguishable, which they were not before.

Write order in `_finalize`, and the reason for it:

1. `outputs.json`, `metrics.json` — the results.
2. `completion.json` — atomically.
3. the index row.

That makes two failures tell themselves apart instead of looking alike:

- **`metrics.json` without `completion.json`** (v2): finalization broke
  off. The numbers may be there, the run is not finished, nothing may
  report it — `unfinalized`.
- **`completion.json` without `metrics.json`**: a completion record over
  results that are gone — `corrupt`. A completion marker must never cover
  for missing results, which is why both files are required.
- **Both, but no index row**: a complete run the index missed. Fully
  reconstructible — this is what `reindex` repairs.

## How the tools read the markers

- **`active()`** — unchanged for the first state, one state added. A
  directory is open when `config.json` exists and the run is not complete by
  its own marker. The recorded pid decides between `running` and the two
  dead states, so each entry carries `state`: `running` · `unknown` ·
  `crashed` · `unfinalized` · `corrupt`. `completed` and `legacy` runs are
  not open and are not listed. `alive` stays as it is.
- **`--wait`** — exit codes keep their meaning: 0 nothing open · 2 a run
  failed · 3 still running at `--max-seconds`. `unfinalized` and `corrupt`
  are failures and exit 2, each with its own message: a machine only needs
  "did not finish cleanly", a human tells them apart by state and message.
- **`reindex`** — appends rows that are missing, and only those. It never
  rewrites an existing row, refuses an index with other columns, never
  appends a `run_id` the index already lists, reports an existing duplicate
  `run_id` as an error, indexes only completed runs, and reports legacy and
  incomplete runs instead of inventing rows for them.

## Index columns

`runs.tsv` carries `protocol_id` as the LAST column. `_check_run_index`
refuses to append to an index whose header does not match — appending would
shift columns silently. An index from before labkit 0.21 is migrated with
labkit 0.47 (`runlog migrate-index`).

Every writer of `runs.tsv` — the finishing run's append, `reindex`, header
creation and the duplicate scan — takes one exclusive `flock` on
`.runs.tsv.lock` in the area, so a killed process leaves no stale lock.

## Unbound runs

A run without a `protocol` key is `unbound`. Nothing is derived for it — not
from the area, not from the documented runs, not from timestamps. Unbound
runs take part in no automatic selection; they are chosen explicitly or not
at all.

## Selection

`intent-check` resolves a protocol to a run by the id and nothing else.
`protocol.path` never selects: it may be stale, and it may be wrong.

1. **Protocol with a stamped id.** Eligible are COMPLETED runs recording
   this id — no others. An unbound run, a run bound elsewhere, an
   `unfinalized` and a `corrupt` run never enter the automatic choice.
   Among the eligible, the rule from 2026-09-09 holds unchanged: the
   newest reporting any intent key, so a probe run does not shadow the
   gate run.
2. **No eligible run.** Exit code 2, with every other run in the area and
   the reason it was left out. "Nothing to check yet" is not a pass when
   the check was called as proof.
3. **Id not yet stamped.** No run is bound to it: exit 2, the run is
   named with `--metrics FILE`.

`--metrics FILE` names the file to read; where the run records a binding
it is also verified. Same id passes. A different id is a hard abort —
holding one protocol's promises against another protocol's run answers
nothing. An unbound run is allowed as an explicit choice, with a warning
that says so; a run that is not completed (legacy included) never.

## Index derivation

The run index (`runs.tsv`) carries `protocol_id` as a column. Currently,
tools that search by protocol (`intent-check`, `bound_runs`) open every
run directory rather than reading the index; the column exists for future
use and for human filtering. The index stays a derived view: the run
directory is authoritative, and where the index holds something the run
directory does not, that is a gap to close, not a source to trust.

The documented runs in a protocol's `## Runs` section are **not yet
checked** against the runs bound to it; `protocol-check` recognises the
section and counts its lines, but does not verify the run ids.

## State

Built: identity (0.20.0); the binding in `config.json`, `schema_version`,
`completion.json`, `runlog reindex`, the `protocol_id` column and the index
lock (0.21.0); selection by id in `intent-check` (0.22.0); the id in the
TOML head, legacy paths removed (0.48.0). `code-check` still resolves
by area and refuses when several protocols are present — it runs before
any run exists, so it has nothing to bind to.

Selection by id followed in 0.22.0. The binding is complete: a protocol
has an identity, a run records it, and every check that pairs the two
goes through the id.

## A resumed file (0.72.3)

Resume is the same command again; `batch.Store` skips the ids already in
the file. The second start is a run of its own, so its record names what
it took over: each JSONL output in `outputs.json` carries `rows_from`
(run_id → rows, from the rows' `_prov.run`) and `continues` (the runs
whose rows the file already held); `completion.json` carries `continues`
too. `finalize` holds the rows to the run — its own, the ones it
continues, or its derived_from lineage; anything else is a file of two
measurements and a blocker.
