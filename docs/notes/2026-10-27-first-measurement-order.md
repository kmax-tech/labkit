# Which measurement is first: git's history, not the clock

*2026-10-27, decided (plan step 2.2, audit row A11). Sources: the audit
register (`docs/audit-2026-10-27.md`, A11), the reproduction below, the
code as cited.*

## The fault

At the low lane report-check holds the registration to the commit of the
first measurement. Until this change the first measurement was the
oldest run by name, and a run id is the local start time
(`runs.RUN_ID_TIME`). A run started under `TZ=Etc/GMT+12` sorts twelve
hours earlier. Reproduced on a staged count lab: R0 measured at a commit
without the registration (the tree held it), the registration was
committed, R1 started under `TZ=Etc/GMT+12`:

    first_measurement: experiments/01-docs-per-case/runs/2026-10-26T23-02-15_b752

R1, whose commit holds the registration, was first, and report-check
named no registration gap. Started under the local zone instead, R0 was
first and report-check held it (`BLOCKER: the registration as committed at
the first measurement 2026-10-27T12-02-28_3e2f (7c78dc6) lacks Question /
hypothesis`).

## The rule

`answering_run.first_measurements` orders the measurements by the commit
each record names (`runs.recorded_commit`, the full sha `git_full`): one
precedes another when its commit is an ancestor of the other's
(`repo.earliest_commits`). The run id orders only runs at one commit;
those share their verdict, so which of them is named changes nothing.

Git's history is a partial order. Every measurement no other one
provably preceded is first, and the registration is held at each:

- diverged history (a rebase, an amend, a side branch): one per branch.
  After an amend both the run's commit and its replacement usually hold
  the registration, so this blocks only a branch that lacked it;
- a run whose commit cannot be placed — none recorded, or one the clone
  does not hold (pruned after a rewrite, a shallow clone): nothing shows
  another measurement came before it. The exit is to fetch the commit.

## Rejected

- Recording the UTC offset and ordering by UTC (the audit's proposal): a
  new field, a schema break, and the clock is still the run's own claim.
- Refusing to name a first measurement on diverged history: a dead end
  after every `git commit --amend` behind a run, with no admissible step.
- Skipping a run whose commit is unknown: the run that started before the
  registration could be exactly that one.

## Limits

- A run started after checking out an older commit counts as earlier.
  That is the stricter reading: it measured on a state that may lack the
  registration, and the commit it names is what held then.
- The commit is what the record says. A record edited by hand (another
  `git_full`) is the integrity question of plan step 2.5, not this order.
- A run whose config.json cannot be read is not among the measurements,
  as before; its binding is unknowable.
- The clock still orders other things: the answering run (newest by name)
  and the stop hook's session runs (`claude_hooks`, by the time in the id).
