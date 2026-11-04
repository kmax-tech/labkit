# Liveness and wait: who asks whether a writer still runs

2026-11-04. Step 6 of the [repair plan](2026-11-03-maintainability-repair-plan.md),
rows N1 and N2 of the [shared-rules review](2026-11-03-shared-rules-review.md).
Reviewed against `f1ff7723`.

## Consumers

Every reader of process liveness in the package (`grep is_alive open_runs
os.kill pid`):

| Consumer | Reads | Decides | Protects |
|---|---|---|---|
| `labkit-next` (`next_step.next_step`) | `runlog.open_runs`: run records in state running or unknown (`runs.is_alive`: pid exists and its command line runs the recorded script; None when that cannot be read) and without failure.json | the "wait" step before any other | advice never sends a second measurement beside a run still going (reference pilot task 15) |
| `runlog --wait` (`runlog_command._wait`) | `runlog.active` (every state not in FAILED_STATES, failure.json not read) and `detached.starts` still running (lock held, exit null) that no open run names by its pid | return 0 idle, 2 failed, 3 still running | a result is not read before its writer ended; "idle" is not said early (area 15, t21) |
| twin refusal (`runlog._require_no_open_twin`) | `open_runs` of the same script in another process | refuse a measurement's start | two processes of one script writing the same rows |
| output lock (`batch.Store.__enter__`, `lock_holder_words`) | ownership: the lock file created with `O_EXCL`; advice: the lock line's pid, `os.kill(pid, 0)` only | ownership refuses a second writer; the advice says "stale, delete it" or "still writing, wait, never delete" | one writer per output file |
| `runlog AREA` (`_print_status`) | as `--wait` | "treat it as running, never delete its lock" for an unknown run | the same as the lock advice |
| endpoint lease (`endpoint_lease._live_records`) | `is_alive` is False → the lease is dropped; True or None keep it | which leases count against an endpoint | endpoint capacity; None counts as alive |
| detached start record (`detached.starts`) | the record's `flock`, never a pid | running or ended | the start's own existence until its command ends |

`_failed_starts` binds a start to a run by pid and start time (a reused pid
of an older run binds nothing); `agent_hooks._end_descendants` kills the
stop's own descendants and reads no liveness of a run. Both stay outside
this comparison.

## Answers per case, before repair (claims to reproduce)

| Case | `labkit-next` | `--wait` | twin refusal | output-lock advice |
|---|---|---|---|---|
| A detached start, run record not yet written | not open → the next step (e.g. measure) | waits for the start (exit 3 at the limit) | no twin → a second measurement starts | (no lock yet) |
| B real writer | open → wait | waits | refused | "alive, still writing — wait" |
| C dead writer | not open | exit 2 at once (crashed) | passes | "gone, stale — delete" |
| D pid reused by another live process | not open | exit 2 at once (crashed) | passes | "alive, still writing — wait, never delete" |
| E process inspection unavailable (no `ps`), live writer | open (unknown) → wait | waits | refused | "alive" from pid existence |
| E′ no `ps`, pid reused | open (unknown) → wait | waits to the limit, every time | refused | "alive" from pid existence |
| F run broke off (failure.json), its process lives on | not open | waits (state running) | passes | — |

Claims, to be shown with real processes before any change:

1. **N1 (case A):** `labkit-next` says measure while `--wait` waits for the
   detached start. Unsafe as advice: following it measures a second time.
2. **N2 (case D):** the lock advice says "still writing, wait, never delete"
   while `--wait` ends at once: the advice cannot be followed to an end.
   It claims a writer from pid existence alone.
3. **F:** `labkit-next` and the twin refusal call the area free while
   `--wait` waits for the same run.
4. **E′:** with no `ps` and a reused pid every consumer says wait and the
   wait never ends; the lock's claim again comes from pid existence alone.
5. Not a claim of the plan, found on the way: a writer started as
   `python -m pkg.mod` records `mod.py` as its script, which its command
   line does not name; `is_alive` would call it dead while it writes.

## What the probes showed

Two probes against `f1ff7723`, real processes throughout; only an
unavailable `ps` is mocked (`runs._command_of` returning None). They ran
from the session's scratch directory, not committed; the inputs below make
them reconstructible.

- **Case A, reproduced (claim 1).** The counting skeleton (`stamp_count`
  of the end-to-end test) committed, then `runlog start <area>
  --max-seconds 0.5 -- sh -c 'sleep 6; exec python <area>/scripts/01_measure.py'`:
  exit 3, "pid … is still starting", `runs/` empty. `labkit-next` said
  "measure: `.venv/bin/python …/01_measure.py` opens a run"; `runlog
  --wait --max-seconds 1` exit 3 "pid=… (detached, no run record yet)".
  Following `labkit-next` measured in the foreground (exit 0); six seconds
  later the detached command measured too: two runs, two runs.tsv rows.
  The twin refusal stopped neither, since neither was open when the
  other opened.
- **Case B (real writer: `runlog.run` + `batch.Store`, sleeping).** All
  agree: `is_alive` True, open, `open_twins` names it, `--wait` exit 3,
  lock "pid … is alive: that run is still writing".
- **Case C (the writer killed with SIGKILL, lock left).** All agree:
  crashed, not open, `--wait` exit 2 at once, lock "pid … is gone … the
  lock is stale". With `ps` mocked away the same (`os.kill` decides).
- **Case D, reproduced (claim 2).** The dead writer's record and lock
  rewritten to name the pid of a live `sleep 300` (pid reuse cannot be
  forced; an unrelated live process stands in). `is_alive` False (`ps`:
  `sleep 300`), crashed, not open, `--wait` exit 2 in 0.0 s — and the lock
  "pid … is alive: that run is still writing — wait for it (`runlog
  <area> --wait`), never delete its lock". The advice points at a wait
  that has already ended.
- **Case E (no `ps`, live writer).** All agree: unknown, open, refused,
  `--wait` exit 3; the lock says alive from pid existence alone, which
  happens to be true.
- **Case E′, reproduced (claim 4).** No `ps` and the reused pid of D:
  unknown, open, the twin refused, `--wait` exit 3 every time, the lock
  "alive". All consumers agree; none can end.
- **Case F, reproduced (claim 3).** A process opened a measurement,
  raised inside it (failure.json written), caught it and slept: state
  running, `open_runs` [] and `open_twins` [] — `--wait` exit 3 after its
  limit, waiting for the run.
- **Case G, reproduced (claim 5).** The writer of B started as `python
  -m probe_pkg.measure`: it records `measure.py`, its `ps` line reads
  `python -m probe_pkg.measure …`; `is_alive` False while it holds the
  lock and writes: crashed, `--wait` exit 2 at once, while the lock (pid
  existence) says alive. An `is_alive(pid, script)` check of the lock, the
  review's smallest change for N2, would here call a live writer's lock
  stale and invite a second writer.

## Repairs

- **F — one rule for "open".** `runlog.still_open` (OPEN_STATES and no
  failure.json) is read by `open_runs` — so by `labkit-next` and the twin
  refusal — and by `--wait` and `runlog AREA`, which show such a run as
  `broke off`. `--wait` ends with exit 2 naming the failure
  (`tests/test_runlog_wait.py`,
  `test_a_run_that_broke_off_while_its_process_lives_ends_the_wait`; its
  twin, a live run without failure.json, still waits:
  `test_running_run_exits_3_at_max_seconds`).
- **A (N1) — one answer for "is the area busy".** `runlog.busy` (pure
  core `busy_of`): the open runs and the detached starts still running
  that no open run names by its pid. `labkit-next` and `runlog --wait` /
  `runlog AREA` read it; `_unopened` in the command is gone. After the
  repair the probe's `labkit-next` says "pid … (started by runlog start)
  is still running … `runlog <area> --wait` waits for it", beside
  `--wait` exit 3. Test: `tests/test_next_step.py`,
  `ADetachedStartBeforeItsRecord` (fails on `f1ff7723`'s `next_step`;
  twin and recovery in the same test: once the command ended, the step is
  to measure again). The twin refusal keeps its own rule: it refuses a
  second writer of the same rows at the moment a run opens, and a start
  writes none before that. It therefore still lets a foreground run of
  the script pass beside a pending start; whichever opens second while the
  other is open is refused, and two runs one after the other remain
  possible for an agent that ignores `labkit-next` (open below).
- **D (N2) — the output lock answers by its flock.** The review's
  smallest change, `runs.is_alive(pid, script)` on the lock line, would
  have fixed D and broken G (a live `-m` writer's lock "stale") and given
  no answer in E′. Instead the Store keeps its lock file's `flock` while
  it writes and its line names it (`pid N · <time> · flock · <argv>`);
  the refusal asks the kernel (`files.lock_held`, the probe
  `detached.starts` already used, moved there). Held: "still writing,
  wait, never delete"; free: "stale, delete it, then start again". After
  the repair the probe's lock answers: B, E, G held; C, C′, D, E′ stale.
  Ownership stays with the lock: `O_EXCL` creation still decides who
  writes; liveness of the area's runs plays no part. A line without the
  marker (0.107.0 or earlier, or by hand) gets no answer and no deletion
  advice. Tests: `tests/test_batch.py`,
  `TestTheLockHolderIsToldByItsFlock` (the reused pid fails on
  `f1ff7723`'s `batch.py`, saying "is alive"; twins: a live writer with
  and without `ps`, a `-m` writer; recovery: the killed writer's lock
  deleted, the output resumes after its one row) and
  `test_a_lock_that_names_no_held_flock_advises_no_deletion`. `runlog
  AREA` beside an unknown run no longer says "never delete its lock"; it
  points to the lock's own answer.

## Open

1. **Run records still decide by pid and script (`runs.is_alive`).** D,
   E′ and G remain for runs: after pid reuse with `ps` missing (E′) every
   consumer says "wait" and `--wait` reaches its limit each time; a `-m`
   writer (G) reads as crashed, so `--wait` ends and the twin refusal
   lets a second start pass — its output lock then refuses it. A run
   could hold a flock on a file in its directory as the detached start
   and the output lock do; that is a run-record format change, not made
   here.
2. **Two measurements one after the other beside a pending start (A).**
   `labkit-next` now says wait, but the twin refusal does not see a
   detached start of the same script before its run opens; an agent that
   ignores the advice still measures twice. Refusing it would need the
   start's script compared with the starting one (`runs_script` on its
   command); not a contradiction between consumers, so not changed.
3. **A flock on a network file system** may hold only on one host. The
   lock line names its host (review of step 6): another host's lock that
   reads free here gets no deletion advice, as `attempts.alive_of` answers
   None for another host; creating the lock with `O_EXCL` still keeps a
   second writer out. Nothing in the lab writes from two hosts today
   (ferry copies).
