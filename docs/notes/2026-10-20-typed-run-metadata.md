# Typed run metadata — 2026-10-20

Built the same day: `RunConfig` at the read boundary (`8d789b4`), then
`ActiveRun` (`e0c21e0`). The contract is in the docstrings of
`labkit/formats/runs.py` and `labkit/run/runlog.py`; this note keeps why,
what the draft proposed, and where the build departed from it.

## The problem as it stood

`runs/<run_id>/config.json` was held to its shape where it was read
(`read_run_config` → `_shape_problem`: schema, `run_kind`, binding, the
record tables, `derived_from`, the repeat fields), then handed on as a
dict. Thirteen modules read labkit's own fields by string key
(`cfg.get("run_kind")`, `cfg.get("derived_from")`, …); a validated field
was read again as `object` and narrowed by hand, and a misspelt key was a
silent `None`. `runlog.active` merged computed facts and the record into
one dict, `{"run_id", "dir", "alive", "state", **cfg}`: a record key named
like a computed one would overwrite it.

## What holds now

- `read_run_config` returns a frozen `RunConfig` built by
  `parse_run_config`, the one check of a record: the schema first (an
  older record names the version that reads it), then no top-level key
  outside `RUN_CONFIG_KEYS` (the keys `runlog.Run._write_record` writes),
  the run kind, the binding, each labkit field's type, `derived_from` and
  the repeat fields. The experiment's own settings, `config`, stay free
  JSON.
- Nested values (`config`, `data`, `promises`, `models_resolved`,
  `command`, `untracked_sources`) are stored as their JSON text and handed
  out as fresh copies; `as_record()` gives the whole record as stored.
- `models_resolved` and `promises` stay checked tables; their modules
  (`llm_specs`, `promises`) own their shape.
- `runlog.active()` returns `ActiveRun` — `run_id`, `dir`, `state`,
  `alive`, `config` (None for an unreadable record), `error` — and merges
  nothing.

Held by `tests/test_run_config.py` (wrong types and unknown keys refused by
name, the experiment config free, writer and reader holding the same keys
on a real run, nested values copies), `tests/test_run_completion.py`
(`ActiveRun`), and a rule in `tests/test_one_home.py` against reading the
record by key outside `runs`.

## The draft, and what changed

The draft of the morning proposed a `RunConfig` for labkit's fields, the
reader boundary returning it, and `ActiveRun`. It left three questions to
the owner, decided before the build:

1. `runlog.active` is public script API — break it to `ActiveRun`, or keep
   a dict for scripts beside a typed call. Decided: break, no dict beside
   it (the house rule: breaking changes, not legacy paths).
2. A config.json key labkit does not write — refuse the record, or keep
   the key in an `extra` mapping. Decided: refuse; an `extra` would carry
   unexplained fields on indefinitely.
3. Type `models_resolved` and `promises` here, or leave them as checked
   tables. Decided: tables, until a concrete invariant asks for types
   (TODO, "Run-Tabellen").

The owner added a fourth: `frozen=True` does not freeze a dict inside a
field. Decided in the build: store nested values as JSON text and hand out
copies. Read-only views (`MappingProxyType`) were rejected — `json.dumps`
cannot write them, and several readers print or compare the record.

Where the build departed from the draft:

- The draft planned the boundary in one commit and the thirteen readers in
  about five more. The return type broke every reader at once, and a
  `.get()` on `RunConfig` to bridge them would have been a legacy path, so
  boundary and readers moved in one commit, pyright naming each reader.
- `run_state` lost its `cfg` argument, which it never read; `repeat_parent`
  went, replaced by the field `repeat_of`; `repeat_mismatch` compares the
  parent's `repeat_basis()` with the new run's keys.
- A parent run can no longer tell a table absent from one recorded as
  null (both read None). The writer writes every key, so only hand-made
  fixtures had the absent form; the new run's side keeps the distinction.

## After the review: a complete record

An independent review found that missing keys passed while unknown ones
were refused: a record without `"unfrozen_ack": true` read as a plain
measurement, its number reportable. Two answers were weighed — require
the fields a gate decides on, or all of them. Decided: all of them. A
list of gate fields would have to stay complete forever (`run_kind`,
`repeat_of`, `derived_from` decide too), and a `RunConfig` is meant to be
the whole record. `parse_run_config` now refuses a missing field, and
null is a value only where the writer writes one; the field table
(`_FIELDS`) states type and nullability once. The 3304 tests this broke
had fixtures writing parts of a record; they now build one through
`tests/protocol_fixture.run_record`, and a test of a damaged record drops
or breaks its field explicitly. A missing table and a null one no longer
meet in a valid record.

No record format changed: schema 3 stays; only the in-memory shape and
the reader's strictness did.
