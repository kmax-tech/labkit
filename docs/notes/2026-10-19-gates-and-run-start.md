# Note 2026-10-19 — the gates' findings as data, the run's start in phases

The history behind three pieces of code, kept here so the code can state
the rule that holds today and no more. Each section names the code it
belongs to; the code links back with `docs/notes/2026-10-19-…`.

## `gate.Findings`: one collector, one channel

**Trigger.** Until 0.96.0 five gates (preflight, finalize, report-check,
code-check, notes-check) spelled "what I found" five ways: a dataclass,
two counters with inline prints, graded strings counted by `startswith` —
and preflight counted code-check's strings a second time. Three spellings
of the grade stood in the output (audit 2026-10-15). `gate.Findings` became
the one collector: `block`, `warn`, `add` for a line graded by its own word,
`report`.

**Why the summary repeats every blocker.** Inside a commit hook the
sections run to 20 lines and the one blocker drowned in the middle
(usability probe 2026-10-07).

**Why the channel.** `Findings` printed as it collected. report-check runs
finalize as one of its stations and wanted finalize's blockers as data,
not its output; until 0.100.0 it redirected stdout into a buffer it threw
away and read the blockers from the collector afterwards. The channel
(`tell`: `print`, or `None`) makes the data the primary thing and the
console one way to show it; headers and notes go through the same channel
(`note`, `header`), so a silent gate is silent whole. Rejected: a second
findings model next to `Findings` (two spellings would come back), and
stations that return findings while the entry point prints them (every
station's "ok" line would have moved to the entry point).

## `preflight_area`: the stations

**Trigger.** The entry point was 180 lines with stations `2`, `2b`, `3` and
every skip condition inside the station (audit 2026-10-18, step 4 of its
list; CODE-017 for the pattern, measured on finalize in the code-navigation
rounds of 2026-10-08). It became the flow — eight stations, each a named
function, every skip condition literal in the body.

**Where the rules of single stations came from.**

- The audit line's coverage: until 0.95.0 preflight never compared the
  line's `scope sha` with the code's stamp and passed the state runlog's
  freeze gate refuses (audit 2026-10-15); until 0.99.0 both took `n/a` as
  a decision (third haiku round on 0.99.0, t18). `findings.audit_line_gap`
  is the one answer for both.
- Deferred findings elsewhere in the repo are told, never counted: one
  deferred in area 16 bit in area 17 (uniagent 2026-10-08).
- Code-check's lines are counted once by their own word (until 0.96.0
  preflight counted them a second time).
- A missing area test is a blocker once `frozen = true`: until 2026-10-07
  it only warned, and a protocol could freeze without any test.

## `runlog.Run.__init__`: three phases

**Trigger.** The constructor ran 115 lines of refusals, with the repeat
check and the record reading half-set attributes of `self`
(audit 2026-10-18). It became `_prepare` → `_admit` → creation, with the
refusals in their old order.

**Where the rules came from.**

- Every refusal before mkdir: a refusal used to leave an empty run dir
  (2026-09-26); a failure between mkdir and the record left a directory
  without `config.json` that the listings read as a legacy run
  (2026-10-09). Hence the provenance is read before mkdir and a failure
  while writing the record removes the directory (0.74.0).
- The detach gate: a long run started in an agent's foreground shell died
  with the harness's tool timeout, which killed the whole process group,
  run and lock with it (2026-08-13, twice in one evening). Which lane may
  start in the foreground is the contract's answer since 2026-10-05.
- The freeze gate (2026-10-05): a full run on an unfrozen protocol
  produced a number nobody registered for, and the rule lived only in the
  skill text a long session forgets. An undecided BLOCKER of a preflight
  audit refuses even with the acknowledgement since 0.97.1 (labkit-paper
  area 09, haiku round: the record lay in `audits/` before the first run).
  The acknowledgement needs a failed audit attempt since 0.99.0 (second
  haiku round on 0.98.0: no agent started an audit, and the hatch passed).
  The messages say "probe" and "acknowledged run", never "pilot": the
  agents of the benchmark rounds took the way the message offered and
  called their run a pilot (review 2026-10-18). At `cost = "seconds"` the
  run is rerunnable at will, so a freeze would protect nothing: what a
  full run needs there is the registration, written before the number
  (LAB-003 No run without an intent paragraph, LAB-017 The number of
  audits follows the cost tier); an instrument change after it is a commit and a
  rerun, not a second freeze.
- A derived run resolves no model anew (2026-10-08): its rows were
  answered by the model of the run it derives from; today's `models.toml`
  would record a provenance the rows never had. `runs.model_provenance_run`
  walks `derived_from` to the run that did.
- A repeat's draw is counted and its record written under one lock:
  counted outside it, two parallel starts took the same number, and a
  file named before the record could disagree with it (review 2026-10-15).
- `long` is recorded since 0.99.0, so `runs.unreportable` can tell a probe
  from a full run.


## Review follow-up: visible start conditions and complete channel routing

**Problem.** The first extraction put the full-run condition in `_admit`
and the detach exceptions in `_foreground_refusal`, so the constructor
still hid when those checks ran. Protocol selection in finalize also used
the console form of the reader, bypassing a supplied silent channel.

**Solution.** The constructor now sequences the start checks and shows the
detach and full-run conditions; the refusal helper only formats and raises
the selected refusal. The intermediate admission helper and result type
are unnecessary. Finalize uses `repo.the_protocol`, routing its error to
the supplied collector or, for the standalone command, to stderr.

**Notes.** Check order, refusal cleanup and the repeat's index lock remain
unchanged. Silence is checked on both stdout and stderr, including missing
and ambiguous protocols.
