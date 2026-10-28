# Committed evidence stays as written

*2026-10-28. Sources: TODO.md Phase 2 point 5 ("Belegintegrität") and
the Phase-2 remainders 7 and 10, the standard way out
([note](2026-10-27-standard-way-out.md)), the handover contract
([note](2026-10-27-handover-recovery.md)), `labkit/formats/evidence.py`,
`tests/test_evidence.py`.*

## Why

Before this, labkit noticed evidence that went *missing*: a record or an
answer an ended attempt names, a file under `audits/` HEAD holds, a
journal cut against HEAD or against its copy in the git directory
(`attempts.gaps`, `copy_gaps`). Evidence *rewritten* in place was seen
only where a rewrite broke the record's format: the ninth Haiku round's
t5 rewrote records field by field, and a committed run's `metrics.json`
could change under its run id with no gate saying so. The lab notebook's
rule is the same for both: a record is never erased or written over; a
correction is added beside it.

The direction for labkit is a well-meaning agent (decided 2026-10-28): a
slip or a shortcut is to be caught, exactly and with its way out; an agent
that also rewrites git's own records is out of reach of a local check and
is measured in the experiments through the sandbox's proxy log, which the
agent cannot reach.

## Contract

What committed evidence may become (`evidence`, module docstring):

| path | may change |
|---|---|
| `audits/<record>.toml` | its findings' decision lines (`status`, `reason`, `effect`), as `--decide` writes them (`findings.without_decisions`) |
| `audits/attempts.jsonl` | appended to; `attempts` holds it, not this module |
| any other file under `audits/` | never |
| `runs/<run_id>/**` of a run committed closed (`completion.json` or `failure.json`) | never; a run still open is runlog's to write |

A version back as labkit first committed it is no change (`original`):
otherwise restoring a record that a commit past the pre-commit rewrote
would itself read as a change against HEAD, and the way out would hold.

Witnesses, all git's:

1. **The state against HEAD** (`changes`): the working tree at the stop,
   the post-change hook and `--findings`, the index at the commit. A file
   the index dropped (`git rm --cached`) is judged by its bytes on disk.
2. **The session's commits** (`commit_changes`, the stop only): each commit
   since the commit the session's commits come after, against its first
   parent — what the pre-commit would have refused, committed past it
   (`--no-verify`). A path the tree has since restored drops out: the
   commit stays in the history, so its repair is the restored file,
   committed or not.
3. **HEAD's reflog** (`orphaned_runs`, the stop only): a closed run in a
   commit HEAD held since the session began and no longer holds — a reset,
   an amend or a rebase left it behind — whose files the tree lacks or
   holds otherwise.
4. **Ignored evidence** (`ignored`): a file labkit writes under `audits/`
   (by suffix) or a run's record file that `.gitignore`, `.git/info/exclude`
   or the global excludes file hide from every commit. A raw output and an
   editor's litter are left to the lab.

Every change found is undone from git, and its line names the commit to
restore from. So a handover does not acknowledge it: the handover binds
`audits/` as it stands (`handovers.mismatch`), not what it lost against a
commit, and it does not bind `runs/` at all.

## Rejected

- **A ledger of the trees the pre-commit checked** (Phase-2 remainder 10).
  It would name a commit that bypassed the hook, but it holds provenance,
  not content: a pull from a co-author, a rebase and a fresh clone bring
  trees this clone's hook never saw, and each would read as a bypass. The
  session's commits against their parents (witness 2) give the guarantee
  that matters here — what a bypassing commit did to evidence — and stay
  silent on a correct one.
- **The whole history against each file's first version.** Records an
  older labkit wrote or a person corrected long ago would hold every stop
  of an area as soon as it is touched; the checks keep to the state against
  HEAD and to the session's own commits.
- **A copy of each closed run's blob ids in the git directory**, like the
  journal's. It would see a run changed or deleted before its first
  commit. Left open: such a loss cannot be restored, so it needs a way out
  a handover can bind — and the handover does not bind `runs/` today.

## Limits

- A record or a run no commit ever held has no witness here (the attempt
  journal's copy covers the audit attempts).
- The session's witnesses end where git's do: a reflog expired or switched
  off, a commit made outside a session (another harness, a terminal), a
  history rewritten before the session began.
- An open run (neither `completion.json` nor `failure.json`) is never
  held, also when runlog was killed and will never close it.
