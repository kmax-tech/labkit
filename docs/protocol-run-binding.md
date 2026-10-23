# Protocol–run binding

Which protocol does a run belong to, and which run answers for a protocol?
The contract below answers both. Terms (`area`, `protocol`, `run`, `run
index`, `metrics`, `protocol run list`) are coined in the README and not
repeated here. How the contract was built: [history](notes/2026-10-20-protocol-run-binding-history.md).

## Identity

A protocol carries its own id in the `[protocol]` table of its ```toml
block (the head, `labkit/formats/protocol_block.py`):

```toml
[protocol]
standard = "0.22"
id = "p-9e2341c0390948dc"
```

- **Shape:** `p-` plus 16 lowercase hex digits (64 bit).
- **Origin:** stamped by `labkit-init exp <name>` at creation, never typed. Not
  derived from name or path, so renaming a protocol or moving an area leaves
  the identity intact.
- **Due:** in every protocol. A protocol with a prose head is read with
  labkit 0.47.
- **Unique:** in practice, not by proof. 64 bit make a collision a
  non-event; the stamp scans the repository, and `protocol-check` reports
  the same id in two files as a blocker — the real source of duplicates is
  a protocol copied as the start of the next one.
- **Immutable** by rule. `protocol-check` compares against `git show
  HEAD:<path>` and warns when the working tree differs. The check is skipped
  for a file that is new, outside git, or unreadable by git, and it is not a
  proof: after the next commit the changed id is the state.

## Binding

A run records the protocol it belongs to. The binding lives in exactly one
place, `runs/<run_id>/config.json` (the **run metadata**; the file name
stays, the term is what readers use), written before any work and never
rewritten:

```json
"protocol": {
  "id": "p-9e2341c0390948dc",
  "path": "PROTOCOL-s13-kette-headroom.md"
}
```

- `id` is the binding. `path` is relative to the run's `base_dir` (the area),
  serves lookup and diagnosis only, and may go stale (protocol renamed or
  moved). It is never refreshed — config.json is write-once. There is no
  alias register.
- The script names its protocol: `runlog.run(..., protocol=PROTOCOL)`. The
  path must lie inside `base_dir` and be one of the `PROTOCOL-*.md` found
  there.
- Omitted: exactly one protocol in the area binds to it, several are a hard
  error, none is `unbound` plus a warning.
- A protocol whose id is not yet stamped yields `"id": null` with the path
  filled — unbound, with a hint where to look; a measurement on it is
  refused. A protocol without a readable head refuses the run.
- The key always has the same shape. Missing protocol, missing id and found
  protocol differ in their VALUES, never in whether the key or the fields
  exist: no reader has to tell absent from null from object.

`run_kind` states the run's purpose, one of three strings: `"probe"` checks
the instrument, `"measurement"` measures the registered question,
`"preparation"` records data preparation before measurement. The API
default is `"probe"`; measurement scripts declare their kind. At seconds a
separate probe is refused before a run directory exists; at minutes and
hours a probe may run before the freeze, and a measurement owes the full
start checks. A missing or unknown `run_kind` makes the record unreadable.
The kind does not enter the choice of the answering run (below); whether
its number may be reported is report-check's question (`runs.unreportable`:
only a measurement without an unfrozen acknowledgement, and then still
after the audit and the recomputation).

## Run completion

A run directory says for itself whether it finished: complete when
`metrics.json` AND `completion.json` exist. A run whose `config.json` is not
schema 3 or lacks a valid `run_kind` is `unreadable`: listed with a reason,
never chosen or indexed. Schema 2 records are read with labkit 0.99.0;
reproduce them with their original repo commit and pinned package.

`schema_version` is stamped into `config.json` at run START: when a reader
has to judge a run, `completion.json` may be exactly the file that is
missing.

`completion.json`, written whole or not at all (`files.write_atomic`):

```json
{
  "schema_version": 3,
  "finished": "2026-09-26T21:14:02",
  "git": "a1b2c3d+dirty",
  "git_full": "a1b2c3d4e5f6...",
  "note": "swap held, 4 anchors out of band",
  "continues": []
}
```

`git`/`git_full` are the state at the END of the run, as the index column
carries it; the state at the start stays in `config.json`. `continues`
names the runs whose rows a resumed output already held (below).

The run writes, in this order: `outputs.json` and `metrics.json` (the
results), `completion.json`, the index row. A failure therefore says which
step it hit:

- **`metrics.json` without `completion.json`**: finalization broke off. The
  numbers may be there, the run is not finished, nothing may report it —
  `unfinalized`.
- **`completion.json` without `metrics.json`**: a completion record over
  results that are gone — `corrupt`. A completion marker never covers for
  missing results, which is why both files are required.
- **Both, but no index row**: a complete run the index missed, fully
  reconstructible — `runlog reindex` repairs it.

## How the tools read the markers

- **`runlog [AREA]`** lists every run that is not complete by its own
  marker, each with its `state`: `running` · `unknown` · `crashed` ·
  `unfinalized` · `corrupt` · `unreadable`. The recorded pid decides between
  `running` and the dead states. `completed` runs are not listed.
- **`runlog <area> --wait`** exits 0 when nothing is open, 2 when a run failed
  (`unfinalized` and `corrupt` count as failed, each with its own message),
  3 when a run is still running at `--max-seconds`.
- **`runlog reindex`** appends the rows that are missing, and only those. It
  never rewrites an existing row, refuses an index with other columns, never
  appends a `run_id` the index already lists, reports an existing duplicate
  `run_id` as an error, indexes only completed runs, and reports unreadable
  (exit 2) and incomplete runs instead of inventing rows for them.

## The run index

`runs.tsv` has the columns `run_id`, `git`, `script`, `data`, `config`,
`metrics`, `note`, `protocol_id`. The run writer refuses to append to an
index whose header differs — appending would shift columns silently; an
index from before labkit 0.21 is migrated with labkit 0.47 (`runlog
migrate-index`). Every writer — the finishing run's append, `reindex`,
header creation and the duplicate scan — takes one exclusive `flock` on
`.runs.tsv.lock` in the area, so a killed process leaves no stale lock.

The index is a local view, not a record: the versioned run directories
under `runs/<run_id>/` are the truth, `runs.tsv` is git-ignored by the lab
stamp, and `runlog reindex AREA` writes it back from them — the same rows;
two runs started in the same second may come back in the other order,
since no record holds a finer start time. No gate reads the index.

The index is a derived view: the run directories are authoritative. The
tools that search by protocol read the run directories, not the index; the
`protocol_id` column serves people filtering by hand.

## Unbound runs

A run without a bound id is `unbound`. Nothing is derived for it — not from
the area, not from the protocol run list, not from timestamps. Unbound runs
take part in no automatic choice; they are named explicitly or not at all.

## The answering run

Every reader that holds a protocol to a run — `intent-check`, `finalize`,
`report-check`, `recheck`, `labkit-params`, `labkit-audit` in analysis mode,
the usability scorer — asks one function for the run
(`answering_run.bound_answering_run`). It resolves by the id and nothing
else; `protocol.path` never selects.

1. **Eligible** are the COMPLETED runs that record this id. Left out, each
   with its reason for the operator: unbound runs, runs bound to another
   id, `unfinalized`, `corrupt` and `unreadable` runs, and **repeats**
   (`repeat_of`): a repeat draws a kept run again to show the spread of its
   number — supporting evidence, never the answer.
2. **The choice** among the eligible is the newest that reports any intent
   key, so a probe or producer run without the keys does not shadow the run
   that answers. When the protocol registers ids and no eligible run reports
   a key, there is no answer.
3. **Refused, though a run was found:**
   - a **newer unreadable** run — its config.json cannot be read, so it may
     be the one that answers;
   - a **rival in the same second** — another eligible run of the same
     standing whose run id carries the same start second: the order of the
     two is chance.
4. **No answer** (nothing eligible, or a refusal) is exit 2 in
   `intent-check`, a blocker in `finalize`, with every other run of the
   area and the reason it was left out. "Nothing to check yet" is not a pass
   when the check was called as proof.
5. **Id not yet stamped:** no run is bound to it; the run is named with
   `--metrics FILE`.

`intent-check --metrics FILE` names the file to read; where the run records
a binding it is also verified. The same id passes. Another id is a hard
abort — holding one protocol's promises against another protocol's run
answers nothing. An unbound run is allowed as an explicit choice, with a
warning that says so; a run that is not completed never.

## The declared run

The protocol declares the run it reports in its TOML head:

```toml
[result]
run = "2026-10-21T13-40-06_ad5f"
```

Written by `protocol-fill --from-run` after a clean `finalize`, never typed
(`protocol_block.declared_run`; until 0.100.0 the declaration was a run id
in the former prose Answer line, and the `Answering run` field a second projection
of it). It is a projection of the answering run, never a second binding:
`finalize` and `report-check` hold it to `bound_answering_run`'s choice — a
table naming another run blocks, one naming no run of the area blocks, one
that does not read (a typed `…_final`, a stray key) blocks where it stands,
and a protocol without the table is an exploration that reports nothing.
The Recorded results line is generated from the declared run's `metrics.json`.

## Protocol run list

The protocol's `## Runs` section lists run entries: a run id and one
sentence describing that run. `protocol-fill --from-run` adds the declared
run's entry. Listing a run does not select it as the answering run or
declare its result reported; selection and declaration are defined above.
The other run entries are not checked against the runs bound to the protocol.

`code-check` runs before any run exists and has nothing to bind to: it
resolves by area, or takes `--protocol FILE` once the area holds several.

## A resumed file

Resume is the same command again; `batch.Store` skips the ids already in
the file. The second start is a run of its own, so its record names what
it took over: each JSONL output in `outputs.json` carries `rows_from`
(run_id → rows, from the rows' `_prov.run`) and `continues` (the runs
whose rows the file already held); `completion.json` carries `continues`
too. `finalize` holds the rows to the run — its own, the ones it
continues, or its `derived_from` lineage; anything else is a file of two
measurements and a blocker.
