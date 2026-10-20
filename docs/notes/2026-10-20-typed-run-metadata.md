# Typed run metadata — design, 2026-10-20

Status: decided 2026-10-20 (below) and built: `RunConfig` at the read
boundary, then `ActiveRun`.

## Problem

`runs/<run_id>/config.json` is held to its shape where it is read
(`runs.read_run_config` → `_shape_problem`: schema, `run_kind`, binding,
the record tables, `derived_from`, the repeat fields), but it is handed on
as a dict. Thirteen modules then read labkit's own fields by string key
(`cfg.get("run_kind")`, `cfg.get("derived_from")`, …): `intent_check`,
`recheck`, `run_record_check`, `answering_run`, `runs`, `standard_contract`,
`finalize`, `report_check`, `usability_score`, `runlog_command`, `runlog`,
`start_check`, `params`. A field the reader validated is read again as
`object` and narrowed by hand; a misspelt key is a silent `None`.

`runlog.active` makes it worse: it merges computed facts and the record
into one dict, `{"run_id", "dir", "alive", "state", **cfg}`. A record key
named like a computed one would overwrite it, and a reader cannot tell
which keys the run wrote and which `active` computed.

Already typed: `RunDir` (directory, config dict, error), `RunFacts` (state,
binding), `ProtocolBinding`, `RunSummary`, `OutputEntry`, `RunKind`.

## Proposal

1. **`RunConfig`**, a frozen dataclass in `labkit/formats/runs.py`, holds
   labkit's own fields — the keys `runlog.Run._write_record` writes:
   `schema_version`, `experiment`, `script`, `protocol` (`ProtocolBinding`),
   `derived_from`, `repeat_of`, `draw`, `run_kind`, `unfrozen_ack`,
   `audit_failed`, `cost_tier`, `promises`, `script_sha`,
   `untracked_sources`, `pid`, `git`, `git_full`, `python`, `env`,
   `models_resolved`, `started`, `command`, `data`, `config`.
   - `config` (the experiment's own settings) stays a free `JsonObject`:
     labkit types what it writes, never what an experiment chooses.
   - `_shape_problem` becomes the constructor's validation: one place
     decides what a readable record is, as today.
   - Writer and reader share the field list: a test holds every key
     `_write_record` writes to a `RunConfig` field and back.
2. **`read_run_config` returns `RunConfig | None`**; `RunDir.config` follows.
   Readers move from `cfg.get("x")` to `cfg.x`, one commit per reader
   group, each with the suite green; pyright then finds every reader left.
3. **`runlog.active` returns `ActiveRun`** — `run_id`, `dir`, `state`,
   `alive`, `error`, `config: RunConfig | None` — and merges nothing.

## Decisions

Taken 2026-10-20: (1) `runlog.active` breaks and returns `ActiveRun`, no
dict beside it; (2) an unknown top-level key is refused, the `config`
inside stays free; (3) `models_resolved` and `promises` stay checked
tables, their modules own their shape. Nested values are stored as their
JSON text and handed out as fresh copies — not stored as read-only views,
which `json.dumps` cannot write and every printing reader would trip on;
`tests/test_run_config.py` holds it. The boundary and its readers moved in
one commit, not per reader group: a changed return type breaks every
reader at once, and a `.get()` on `RunConfig` to bridge them would have
been a legacy path. The options as they were weighed:

1. **`runlog.active` is public script API.** Return `ActiveRun` (a
   Breaking change: a script reading `r["state"]` or a config key from it
   breaks, announced in the CHANGELOG with the last version that returns
   dicts), or keep a dict for scripts beside a typed internal call. The
   house rule says break, not legacy paths; the draft follows it unless
   a lab script is known to read `active`.
2. **Unknown keys in config.json.** A record carrying a key labkit does not
   write: refuse it as unreadable (strict, the writer is the only author),
   or keep it in an `extra` mapping. The draft proposes strict: config.json
   is write-once and written by labkit alone.
3. **`models_resolved` and `promises`** carry their own shapes
   (`llm_specs`, `promises`). Type them here too, or keep them as
   validated `JsonObject` tables in this step. The draft keeps them as
   tables: their own modules own their shape.

## Acceptance

- A config.json whose labkit field has the wrong type is unreadable,
  naming the field; the twin, any experiment `config`, passes untouched.
- Every key `_write_record` writes is a `RunConfig` field (writer–reader
  parity test).
- No module outside `runs` reads a labkit field by string key (a
  one-home rule in `tests/test_one_home.py`).
- `runlog <area>` prints what it prints today.

## Size

One commit for `RunConfig` and the reader boundary, then about five
commits moving the thirteen readers, then `active`. No record format
changes: schema 3 stays; only the in-memory shape does.
