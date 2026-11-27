# Protocol–run binding

Which protocol does a run belong to, and which run answers for a protocol? The contract below answers both. Terms (`area`, `protocol`, `run`, `run index`, `metrics`, `protocol run list`) are coined in the README and not repeated here. How the contract was built: [history](notes/2026-10-20-protocol-run-binding-history.md).

## Identity

A protocol carries its own id in the `[protocol]` table of its ```toml block (the head, `labkit/formats/protocol_block.py`):

```toml
[protocol]
standard = "0.33"
id = "p-9e2341c0390948dc"
```

- **Shape:** `p-` plus 16 lowercase hex digits (64 bit).
- **Origin:** stamped by `labkit-init exp <name>` at creation, never typed. Not derived from name or path, so renaming a protocol or moving an area leaves the identity intact.
- **Due:** in every protocol. A protocol with a prose head is read with labkit 0.47.
- **Unique:** in practice, not by proof. 64 bit make a collision a non-event; the stamp scans the repository, and `protocol-check` reports the same id in two files as a blocker — the real source of duplicates is a protocol copied as the start of the next one.
- **Immutable** by rule. `protocol-check` compares against `git show HEAD:<path>` and warns when the working tree differs. The check is skipped for a file that is new, outside git, or unreadable by git, and it is not a proof: after the next commit the changed id is the state.

## Binding

A run records the protocol it belongs to. The binding lives in exactly one place, `runs/<run_id>/config.json` (the **run metadata**; the file name stays, the term is what readers use), written before any work and never rewritten:

```json
"protocol": {
  "id": "p-9e2341c0390948dc",
  "path": "PROTOCOL-s13-kette-headroom.md"
}
```

- `id` is the binding. `path` is relative to the run's `base_dir` (the area), serves lookup and diagnosis only, and may go stale (protocol renamed or moved). It is never refreshed — config.json is write-once. There is no alias register.
- The script names its protocol: `runlog.run(..., protocol=PROTOCOL)`. The path must lie inside `base_dir` and be one of the `PROTOCOL-*.md` found there.
- Omitted: exactly one protocol in the area binds to it, several are a hard error, none is `unbound` plus a warning.
- A protocol whose id is not yet stamped yields `"id": null` with the path filled — unbound, with a hint where to look; a measurement on it is refused. A protocol without a readable head refuses the run.
- The key always has the same shape. Missing protocol, missing id and found protocol differ in their VALUES, never in whether the key or the fields exist: no reader has to tell absent from null from object.

`run_kind` states the run's purpose, one of three strings: `"probe"` checks the instrument, `"measurement"` measures the registered question, `"preparation"` records data preparation before measurement. The API default is `"probe"`; measurement scripts declare their kind. At low repeat cost a separate probe is refused before a run directory exists; at high repeat cost a probe may run before the freeze, and a measurement owes the full start checks. A missing or unknown `run_kind` makes the record unreadable. The kind does not enter the choice of the answering run (below); whether its number may be reported is report-check's question (`runs.unreportable`: only a measurement without an unfrozen acknowledgement, and then still after the audit and the recomputation).

## Run completion

A run directory says for itself whether it finished: complete when `metrics.json` AND `completion.json` exist. A run whose `config.json` is not schema 5 or lacks a valid `run_kind` is `unreadable`: listed with a reason, never chosen or indexed. Schema 2 records are read with labkit 0.99.0, schema 3 (`cost_tier` instead of `repeat_cost`) with 0.103.0, schema 4 (inputs without their origin run) with 0.113.0; reproduce them with their original repo commit and pinned package.

`schema_version` is stamped into `config.json` at run START: when a reader has to judge a run, `completion.json` may be exactly the file that is missing.

`completion.json`, written whole or not at all (`files.write_atomic`):

```json
{
  "schema_version": 5,
  "finished": "2026-09-26T21:14:02",
  "git": "a1b2c3d+dirty",
  "git_full": "a1b2c3d4e5f6...",
  "note": "swap held, 4 anchors out of band",
  "continues": [],
  "served_instruments": {
    "judge": {"start_digest": "3f2a9c01b7de", "first_vllm_version": "0.11.0",
              "digest": "3f2a9c01b7de", "tool": "start-swap.sh=fe51baa6c6a4,swap_proxy.py=b3a2afc3cd05",
              "vllm_version": "0.11.0"}
  }
}
```

`git`/`git_full` are the state at the END of the run, as the index column carries it; the state at the start stays in `config.json`. `continues` names the runs whose rows a resumed output already held (below). `served_instruments` holds, per `openai` alias served through a [vllm-swap](https://github.com/kmax-tech/vllm-swap) proxy, what its `GET /health` said: the configuration digest at resolution (`start_digest`, also in `config.json` as the alias's `served_digest`), the vLLM version right after the first answer, and digest, proxy files and vLLM version at the end; `{}` when the run used no such alias. A field the proxy did not report says `not reported`; the vLLM version is reported only while the alias is loaded. What is built and what is not: the server's state is recorded and compared; the digest names the configuration (served model id and launch command), not the weights — a model served without `--revision` can change its weights under the same digest; and the cache key and the resume check (`llm.identity`) do not include the digest yet, so a cached answer or a resumed row of another configuration is not refused.

The run writes, in this order: `outputs.json` and `metrics.json` (the results), the comparison of the served instruments, `completion.json`, the index row. A failure therefore says which step it hit:

- **`metrics.json` without `completion.json`**: finalization broke off. The numbers may be there, the run is not finished, nothing may report it — `unfinalized`. One cause is labkit's own: when an `openai` alias's proxy reports another configuration digest at the end than at resolution, none at the end, or another vLLM version than after the first answer, the run writes `failure.json` (`ServedInstrumentChanged`) and stops here, because its answers may come from two instruments. A swap to another alias and back between the readings is not seen.
- **`completion.json` without `metrics.json`**: a completion record over results that are gone — `corrupt`. A completion marker never covers for missing results, which is why both files are required.
- **Both, but no index row**: a complete run the index missed, fully reconstructible — `runlog reindex` repairs it.

## How the tools read the markers

- **`runlog [AREA]`** lists every run that is not complete by its own marker, each with its `state`: `running` · `unknown` · `crashed` · `unfinalized` · `corrupt` · `unreadable`, and `broke off` for a run that wrote failure.json while its process lives on. The recorded pid decides between `running` and the dead states. Then the `completed` runs, oldest first, each with what it is (a fresh run, or derived from which), whether its code was committed and the command that started it.
- **`runlog <area> --wait`** exits 0 when nothing is open, 2 when a run failed (`unfinalized`, `corrupt` and `broke off` count as failed, each with its own message), 3 when a run is still running at `--max-seconds`.
- **`runlog reindex`** appends the rows that are missing, and only those. It never rewrites an existing row, refuses an index with other columns, never appends a `run_id` the index already lists, reports an existing duplicate `run_id` as an error, indexes only completed runs, and reports unreadable (exit 2) and incomplete runs instead of inventing rows for them.

## The run index

`runs.tsv` has the columns `run_id`, `git`, `script`, `data`, `config`, `metrics`, `note`, `protocol_id`. The run writer refuses to append to an index whose header differs — appending would shift columns silently; an index from before labkit 0.21 is migrated with labkit 0.47 (`runlog migrate-index`). Every writer — the finishing run's append, `reindex`, header creation and the duplicate scan — takes one exclusive `flock` on `.runs.tsv.lock` in the area, so a killed process leaves no stale lock.

The index is a local, derived view, not a record: the versioned run directories under `runs/<run_id>/` are authoritative, `runs.tsv` is git-ignored by the lab stamp, and `runlog reindex AREA` writes it back from them — the same rows; two runs started in the same second may come back in the other order, since no record holds a finer start time. One thing only the index knows: a run that finished and was deleted before any commit held it. The area state every gate builds reads the index for exactly that (`area_state.AreaState.lost`, through `run_index.indexed_bindings`): the gates name such a run as lost and never invent its record. Such a run keeps counting as a measurement of the protocol its row names ([note](notes/2026-11-18-lost-first-measurement.md)). Which runs belong to a protocol, and everything else about a run, the gates take from the run directories; the `protocol_id` column otherwise serves people filtering by hand.

## The start file

`run-starts/<run_id>.json` in the area, outside the run's directory and outside `runs/`, answers what the index cannot: which run started with which protocol, when and as what. It is a JSON object of exactly the keys `run_id`, `protocol_id`, `started_utc` and `run_kind`, one file per run of every kind — a probe can produce numbers too —, written whole and synced to disk as the last step of the run's start, before the script's block runs (`run_starts.write_start`, `runlog.Run._write_start_file`). A start whose file cannot be written is refused and leaves no run directory; a start refused for another reason writes none. An existing start file is never overwritten: different run ids are different files, and the same run id started twice is refused, loudly. The end of a run adds nothing to it: completion stays the index's. `runlog reindex` neither reads nor writes start files, so one survives its run directory, and a run from before start files has none.

A start file is tracked, not ignored. Commit it with the run: a clone has exactly the start files a commit holds, and before the commit there is no such safeguard — the file exists on the machine that started the run and nowhere else. Until it is committed git reports the tree as changed, and the next run records that (`+dirty`); this is the state as it is, and labkit does not hide it. Once a commit holds a start file it never changes or goes: a change or a deletion is a blocker at report-check, the stop and the commit, with the restore from that commit as its way out (`evidence.start_file_changes`), against HEAD or by a commit of the session. A start file whose deletion was committed earlier is read back from the last commit that held it and keeps being used for assignment and order (`area_state.committed_starts`); the post-change hook names the deletion with the checkout that restores the file, and its existence alone blocks no release. A run of the format with start files needs its start file staged or committed: where the commit is checked the start files are the index's, and a start file that stands in the working tree while the index holds the run's record — staged now or committed earlier — holds the commit, with `git add` of the file as the way out (`evidence.unstaged_start_files`). Which runs that are is told by the start mark in the run's directory (below); for a run without it no start-file duty is evidenced, and none is asked. Where a run's directory contains the mark and no start file is found — not in the working tree, the index or a commit — that is evidence lost, and it holds the release of the protocol the run is assigned to by its record or the index: a blocker of a check not executable in `finalize` (`registration_hold.missing_start_hold`), with the start file back from a commit, a clone or a copy as the way out — never written anew from memory —, else a new registration or the handover. It does not hold the area: another protocol is not touched, and a run nothing assigns is warned of and held against none. When a run's directory and its only start file both vanish before a commit holds either, labkit has no evidence of the run and sees nothing — a different situation from a kept mark, an index row or a commit, each of which keeps the run. Only the commit secures a start file. A start file that does not read is its run's incomplete start, never a refusal of the area: its protocol, time and kind are unknown, nothing is written into it by hand, the run stays the protocol's its record or its index row names with an order that is unknown, and a run nothing else names is held against no protocol (`area_state.unread_start_warning`). Design and the rejected alternatives: [note](notes/2026-11-18-run-start-record.md).

The two files a start writes, in the order it writes them, after `config.json` and before the script's block runs:

| File                                                           | Holds                                                                                                            | Shows                                                                                                                                                               | Does not show                                                                                                                                                                          |
|----------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| start mark, `runs/<run_id>/start-file`, in the run's directory | the path of the run's start file, one line                                                                       | that a start file was written for this run: the evidence of a start-file duty, read from the file state or from the commit that holds it (`area_state.marked_runs`) | anything about the start itself; and its absence proves nothing — no duty is evidenced then, which is the case of every run started before start files and of a run that lost its mark |
| start file, `run-starts/<run_id>.json`, outside `runs/`        | a JSON object of exactly `run_id`, `protocol_id` ("" unbound), `started_utc` (UTC, to the second) and `run_kind` | which protocol the run was bound to at its start, when it started by the starting machine's clock, and as what kind — also when the run's directory is gone         | that the run completed (the index and `completion.json` say that), that the clock was right, or anything of a run whose start file is not there                                        |

Both are written once by `runlog` (`run_starts.write_start_mark`, `write_start`) and never again: a failure of either refuses the start and leaves no run directory, `runlog reindex` writes neither, and neither is edited by hand.

What the gates read from the start files and the index, in this order ([note](notes/2026-11-18-lost-first-measurement.md)):

1. **Which protocol.** A run whose record reads is bound by its record. A record that does not read belongs to the protocol its start file or its index row names (`area_state.assigned_to`), for every check alike; one neither names is assigned to no protocol, whatever the number of protocols in the area, holds none and is warned of. Where a run's record, its start file and its index row name different protocols, no file wins: each protocol named is held by a blocker of its own (`registration_hold.binding_conflict_hold`).
2. **Whether it measured.** A start file says that a run started, and its `run_kind` says as what. Where a record is gone or does not read, a run its start file lists as a probe or a preparation counts as a measurement for no check (`Measured.may_have_measured`); one without a start file counts, since the index names no kind and nothing says what it was.
3. **Whether it may have been the first measurement.** A run without a record — only the index or only a start file names it, or its record does not read — keeps counting for its protocol: the next run is not held to HEAD as a first measurement (runlog warns and starts). Its order against the measurements of the protocol that read is told only where a start file holds a UTC start for both. Started before all of them, or with none that reads, it may have been the first, and `finalize` holds the protocol's numbers as a check not executable until the record is back (`registration_hold.lost_record_hold`). Started after one of them, it is named in a warning and holds nothing. With a start missing — a run from before start files — the order is unknown, said as such, and held like the first; it is never guessed from a run id, a row's position or a commit. A time never assigns a run to a protocol.

A UTC start removes the time zone from the comparison, not the clock: that the machines' clocks were right when the runs started is assumed, stated in every message that takes a run as the later one, and not checked.

## Unbound runs

A run without a bound id is `unbound`. Nothing is derived for it — not from the area, not from the protocol run list, not from timestamps. Unbound runs take part in no automatic choice; they are named explicitly or not at all.

## The answering run

Every reader that holds a protocol to a run — `intent-check`, `finalize`, `report-check`, `recheck`, `labkit-params`, `labkit-audit` in analysis mode — asks one function for the run (`answering_run.bound_answering_run`). It resolves by the id and nothing else; `protocol.path` never selects. The usability scorer holds no protocol to a run: it reads the newest completed run, bound or not (`usability_score.latest_run`), since an unbound run is a finding of the probe.

Once the protocol has adopted a run (`[result] run`, below), that run answers — not the newest. It must be eligible (point 1); else no run answers, and the blocker names why it cannot and the withdrawal. Eligible runs whose ids sort after it are a static-evidence warning in `finalize`, never a blocker. Before the adoption the choice is points 1 to 3, and `labkit-next` proposes its run for the adoption.

1. **Eligible** are the COMPLETED runs that record this id. Left out, each with its reason for the operator: unbound runs, runs bound to another id, `unfinalized`, `corrupt` and `unreadable` runs, and **repeats** (`repeat_of`): a repeat draws a kept run again to show the spread of its number — supporting evidence, never the answer.
2. **The choice** among the eligible is the newest that reports any intent key, so a probe or producer run without the keys does not shadow the run that answers. When the protocol registers ids and no eligible run reports a key, there is no answer.
3. **Refused, though a run was found:**
   - a **newer unreadable** run — its config.json cannot be read, so it may
     be the one that answers;
   - a **rival in the same second** — another eligible run of the same
     standing whose run id carries the same start second: the order of the
     two is chance.
   The order is the run ids', and a run id is local time without a zone (`runlog`): a run measured on a machine in another zone sorts by its own clock, a cluster run in UTC two hours "before" a Mac run in CEST measured earlier. Until the id carries its zone, every machine that measures for one area runs in the same zone — containers with `TZ=UTC`.
4. **No answer** (nothing eligible, or a refusal) is exit 2 in `intent-check`, a blocker in `finalize`, with every other run of the area and the reason it was left out. "Nothing to check yet" is not a pass when the check was called as proof.
5. **Id not yet stamped:** no run is bound to it; the run is named with `--metrics FILE`.

`intent-check --metrics FILE` names the file to read; where the run records a binding it is also verified. The same id passes. Another id is a hard abort — holding one protocol's promises against another protocol's run answers nothing. An unbound run is allowed as an explicit choice, with a warning that says so; a run that is not completed never.

## The declared run

The protocol declares the run it reports in its TOML head:

```toml
[result]
run = "2026-10-21T13-40-06_ad5f"
```

Written by `protocol-fill --from-run` after a clean `finalize`, never typed (`protocol_block.declared_run`; until 0.100.0 the declaration was a run id in the former prose Answer line, and the `Answering run` field a second projection of it). Once written, it is the answering run (`bound_answering_run` takes it): a table naming a run that cannot answer — none of the area, an unfinalized one, one bound elsewhere — blocks with the withdrawal, one that does not read (a typed `…_final`, a stray key) blocks where it stands, and a protocol without the table is an exploration that reports nothing. The Recorded results line is generated from the declared run's `metrics.json`.

## Protocol run list

The protocol's `## Runs` section lists run entries: a run id and one sentence describing that run. `protocol-fill --from-run` adds the declared run's entry. Listing a run does not select it as the answering run or declare its result reported; selection and declaration are defined above. The other run entries are not checked against the runs bound to the protocol.

`code-check` runs before any run exists and has nothing to bind to: it resolves by area, or takes `--protocol FILE` once the area holds several.

## A resumed file

Resume is the same command again; `batch.Store` skips the ids already in the file. The second start is a run of its own, so its record names what it took over: each JSONL output in `outputs.json` carries `rows_from` (run_id → rows, from the rows' `_prov.run`) and `continues` (the runs whose rows the file already held); `completion.json` carries `continues` too. `finalize` holds the rows to the run — its own, the ones it continues, or its `derived_from` lineage; anything else is a file of two measurements and a blocker.
