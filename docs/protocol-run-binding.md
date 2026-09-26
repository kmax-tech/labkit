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
- A protocol without an id (standard below 0.16) yields `{"id": null,
  "path": ...}` — unbound, with a hint where to look.

The file is named `config.json` and carries the provenance too. Renaming it
would break every reader of every finished run, so the term moves and the
file stays: **run metadata** means `runs/<run_id>/config.json`.

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

Identity is built (labkit 0.20.0). Binding, legacy handling, selection and
index derivation are decided and specified here, not yet implemented; the
run index still has no `protocol_id` column, and `note` and the run's
authoritative git state exist only in `runs.tsv`, so a lossless rebuild is
not possible yet.
