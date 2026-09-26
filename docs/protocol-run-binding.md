# Protocol–run binding

Which protocol does a run belong to? The contract below answers that. Terms
(`area`, `protocol`, `run`, `run index`, `metrics`, `documented runs`) are
coined in the README and not repeated here.

## Identity

A protocol carries its own id in a header field, beside the standard version:

```markdown
- **Standard:** 0.16
- **Protocol id:** p-9e2341c0390948dc
```

- **Shape:** `p-` plus 16 lowercase hex digits (64 bit).
- **Origin:** stamped by `lib exp <name>` at creation, never typed. Not
  derived from name or path, so renaming a protocol or moving an area leaves
  the identity intact.
- **Due:** from `Standard: 0.16` on, for experiment and measurement
  protocols alike. Older protocols keep their standard and need no id.
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
  serves lookup and diagnosis only, and may go stale; it is refreshed on the
  next successful lookup. There is no alias register.
- The script names its protocol: `runlog.run(..., protocol=PROTOCOL)`. The
  path must lie inside `base_dir` and be one of the `PROTOCOL-*.md` found
  there.
- Omitted: exactly one protocol in the area binds to it, several are a hard
  error, none is `unbound` plus a warning.
- A protocol without an id (standard below 0.16) yields `"id": null` with
  the path filled — unbound, with a hint where to look.
- The key always has the same shape. Missing protocol, missing id and found
  protocol differ in their VALUES, never in whether the key or the fields
  exist: no reader has to tell absent from null from object.

`protocol` is the last parameter of `runlog.run(...)`, after `long`, so no
existing positional call shifts.

The file is named `config.json` and carries the provenance too. Renaming it
would break every reader of every finished run, so the term moves and the
file stays: **run metadata** means `runs/<run_id>/config.json`.

## Run completion

A run directory says for itself whether it finished. Two markers, because
runs written before this contract cannot be changed:

| `config.json` says  | complete when                        | state                   |
|---------------------|--------------------------------------|-------------------------|
| no `schema_version` | `metrics.json` exists                | legacy run              |
| `schema_version: 2` | `metrics.json` AND `completion.json` | run under this contract |

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
  dead states, so each entry carries `state`: `completed` · `running` ·
  `crashed` · `unfinalized` · `corrupt`. `alive` stays as it is.
- **`--wait`** — exit codes keep their meaning: 0 nothing open · 2 a run
  failed · 3 still running at `--max-seconds`. `unfinalized` and `corrupt`
  are failures and exit 2, each with its own message: a machine only needs
  "did not finish cleanly", a human tells them apart by state and message.
- **`reindex`** — appends rows that are missing, and only those. It never
  rewrites an existing row: for a legacy run the `note` and the end-of-run
  git state exist nowhere but in the index, so a rebuild would be a quiet
  loss. It refuses an unmigrated index, never appends a `run_id` the index
  already lists, reports an existing duplicate `run_id` as an error,
  rebuilds only completed v2 runs, and reports legacy runs and incomplete
  runs instead of inventing rows for them.
- **Legacy runs** keep `metrics.json` as their marker forever. Nothing is
  backfilled into them, no `completion.json` is written after the fact.

## Index migration

`runs.tsv` gains `protocol_id` as the LAST column, so a reader that counts
columns positionally keeps the first seven where they were.

`_check_run_index` already refuses to append to an index whose header does
not match, and names the way out — that refusal stays, and now names
`runlog migrate-index`. The migration is explicit, never automatic: a column
that shifts by itself is the scar the check was built for.

Every writer of `runs.tsv` — the finishing run's append, `migrate-index`,
`reindex`, header creation and the duplicate scan — takes one exclusive
`flock` on `.runs.tsv.lock` in the area. Without it an atomic migration and
a finishing run race: the migration rewrites and renames while the run
appends to the file it just replaced, and that row is gone without a trace.
`flock` rather than a lock file, so a killed process leaves no stale lock.

It rewrites the file atomically (temp file, then rename), keeps every
existing row verbatim including `note`, and adds one empty field per row.
It fills nothing in: an existing row's `protocol_id` stays empty until a
`reindex` can prove it from a run directory.

## Legacy

A run without a `protocol` key is `unbound`. Nothing is derived for it — not
from the area, not from the documented runs, not from timestamps. Unbound
runs take part in no automatic selection; they are chosen explicitly or not
at all.

## Selection

`intent-check` and `code-check` resolve a protocol to a run like this:

1. Runs bound to this protocol's id — newest with intent keys among them
   (a probe run without intent keys must not shadow the gate run).
2. No bound run and one protocol in the area: the area's newest run with
   intent keys, as before — right by construction.
3. No bound run and several protocols in the area: refuse, and require
   `--metrics FILE`. Exit code 2 — "nothing to check yet" is not a pass.

## Index derivation

The run index (`runs.tsv`) carries `protocol_id` as a column, so a tool
searching by protocol does not open every run directory. It stays a derived
view: the run directory is authoritative, and where the index holds
something the run directory does not, that is a gap to close, not a source
to trust.

The documented runs in a protocol's `## Runs` section are checked against the
runs bound to it — never read as a source.

## State

Built: identity (0.20.0); the binding in `config.json`, `schema_version`,
`completion.json` and the five run states, `runlog migrate-index` and
`runlog reindex`, the `protocol_id` column and the index lock (0.21.0);
and the fail-closed refusals in `code-check` and `intent-check`.

Not built: selection by id — `intent-check` still picks by area and refuses
in a series area (step 2). That is the next step, and it is now the only
one that needs no new data.
