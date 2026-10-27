# Note 2026-10-19 — why the Claude hooks and report-check hold what they hold

The history behind `labkit/gates/claude_hooks.py` and
`labkit/gates/report_check.py`, kept here so their docstrings can state the
rule that holds today. Each section names the code it belongs to.

## `claude_hooks`: the layer that does not depend on remembering

**Trigger (2026-10-05).** The rules that matter — "preflight before a full
run", "protocol-check after writing a protocol" — lived in the skill text,
in the agent's memory. The write hooks that did exist matched only the
Write and Edit tools; a protocol written through a Bash heredoc got no
check at all, and no hook stood between the agent and
`python 01_measure.py`.

**Stop runs report-check, not finalize.** Until 0.99.0 the stop hook ran
finalize only, and report-check, which refuses a probe's number, was never
called by any agent of the haiku rounds (TODO 2, 2026-10-19). The number
is checked in the session that still knows why it is there, not at the
next commit (2026-10-07).

**The whole area, not the protocol alone.** A script edited under a
reported number passed both hooks while the protocol stayed untouched
(audit 2026-10-19).

**Undecided blockers stop the turn.** Third haiku round on 0.99.0
(labkit-paper area 09, t5): the agent ran the audit, read its four
BLOCKERs, left all twelve findings `open`, measured with `long=False` and
reported — report-check would have refused the number, but nothing made the
agent call it. A gate the agent must call is no gate; the stop and the
commit are the two it cannot choose.

**The session log (2026-10-07).** Claude Code deletes transcripts after
`cleanupPeriodDays`; the log keeps the link from a run to the session it
came from.

**The repository from a subdirectory (audit 2026-10-27, C8).** Every hook
took the project directory for the repository and asked it for a `.git`
of its own. A session started below the root (Claude Code in
`experiments/`) skipped the stop and post-change's git status in silence,
the pre-run's walk to an area ended at the project directory, and the
pre-commit — git runs it at the root, with the session's
`CLAUDE_PROJECT_DIR` inherited — read the staged paths against the
subdirectory and found no area. Reproduced through the entry point
(`python -m labkit.gates.claude_hooks stop`, an open BLOCKER untracked):
`project=<tmp>/experiments rc=0 stderr='<empty>'`, where the root gave rc 2.
The hooks now hold the git root of the project directory, `undecided` that
of its current directory. Outside every repository the stop holds once per
turn and says why: a check that cannot run blocks (decided 2026-10-17).
The fix's reach: per the Claude Code docs (read 2026-10-27), hooks "load
from the current working directory's `.claude/` folder with no
parent-directory fallback" (https://code.claude.com/docs/en/permissions),
so a session started below the root runs none of the hooks
`labkit-hooks install` writes into the root's `.claude/settings.json`;
only `.claude/settings.local.json` loads from the git root. The fix holds
where a hook does fire there (local or user settings, the subdirectory's
own), and the pre-commit holds the commit either way. The stamped command
`"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/claude-hook"` also looks for the venv
under the project directory; what `CLAUDE_PROJECT_DIR` holds in a
subdirectory session the docs leave open ("the project root where the
session started").

**The commit's decisions from the index (audit 2026-10-27, C9).**
`undecided_blockers(staged=True)` read the attempt journal from the index
and the records with their decisions from the tree. A BLOCKER decided with
`--decide` and never staged passed the pre-commit while the commit carried
it `open`; reproduced through `python -m labkit.gates.claude_hooks
undecided` with the index holding `status = "open"`: `rc=0`. The reverse
held a commit falsely: a staged decision reopened only in the tree. The
commit now reads the records as the index holds them
(`findings.area_records(staged=True)`); the stop keeps reading the tree.

**The stop base moves only on a clean tree (audit 2026-10-27, C7).** The
stop's checks read the working tree. A commit past the pre-commit with
the wrong run declared, and the fix left uncommitted, passed the stop —
and the base moved to the bad commit, so dropping the fix afterwards was
never held. Reproduced through the entry point: `stop with the fix
uncommitted: rc=0`, `base ef07f648 -> 385993f7 (bad commit 385993f7)`,
`stop after the fix is dropped: rc=0`. The base now moves only past a
stop without a blocker on a tree equal to HEAD (git status empty). Not
done, deliberately: holding the turn until the fix is committed (a normal
session commits through the pre-commit and keeps editing — every stop
would ask for a commit), and checking HEAD itself (the stations read the
tree; HEAD would need a checkout of its own). `--no-verify` stays the
deliberate exception; the loop protection per turn stays as decided.

**Without a stop base, the commits since the transcript start (audit
2026-10-27, A12).** `rm -rf .git/labkit-stop-base` after a commit past the
pre-commit: `committed_in_session` returned no path and no word, and the
next Bash command kept a new base at the bad commit. Reproduced through the
entry point: `stop without a base: rc=0 stderr='<empty>'`, then `base kept
again at: 80764864 HEAD: 80764864`. Now the stop says the base is missing
and checks the commits on HEAD's first-parent line dated since the
transcript's first record (`repo.head_before`); pre-run keeps no base past
such a commit, and a clean stop on a clean tree keeps HEAD. Rejected:
checking every protocol of the repo (an old area's open BLOCKER would hold
every stop, decided 2026-10-17), and HEAD's reflog (`HEAD@{date}`, as easy
to delete as the base). The limits: a commit date is the commit's own word
(`GIT_COMMITTER_DATE`); and the sentence reaches the agent only when the
stop holds — "Claude never sees stderr from a hook that exits 0"
(https://code.claude.com/docs/en/hooks#exit-code-0, read 2026-10-27); a
clean fallback stop leaves it in the debug log.

**The stop's time budget (2.7).** Claude Code cancels the stop hook at its
timeout (120 s, `install_hooks.STOP_TIMEOUT_S`), "discarding the hook's
output, so on most events a timed-out hook renders no decision"
(https://code.claude.com/docs/en/hooks#timeouts, read 2026-10-27): a
cancelled stop holds nothing — while one area's tests and `--check` may
each take up to 300 s inside the gates. The checks now run under `STOP_BUDGET_S` (90 s, SIGALRM in
the hook's main thread; `subprocess.run` kills the child it waits on); past
it the stop holds once per turn and says so: a check that cannot run blocks
(2026-10-17). Measured on the Stop test fixture: 0.32 s for a clean stop;
a `--check` sleeping 30 s under a 3-s budget held after 3.01 s, the child
gone.

**A linked report at post-change (2026-10-27, after A10).** Since 2.8 the
stop and the commit test a report at its own path and refuse one that is a
symbolic link. post-change still resolved every path first, so a
`REPORT.md` linking into `data/` was read where it points — a skipped
directory — and told nothing (through the entry point: `post-change rc=0
context='<no context>'`). It now reads the reports as the repo names them
(`repo.own_path`) and gives a link the refusal and its way out
(`report_check.link_gap`), where the agent writes it.

## `report_check`: the gate after the last step

**Trigger.** `finalize` holds the run before the number is written back;
what follows it — the analysis audit, the result note, the note held to the
run by `02_analyze.py --check` — had no gate. In the cloud judge probe at
`minutes` (2026-10-14, draw 3) the agent skipped the check and the result
note, and finalize was green. finalize cannot be that gate: it comes before
the analysis audit.

**Where single stations came from.**

- Station 1 at `seconds`: until 0.99.0 the whole command exited 0 there,
  and a probe's number passed as a reported one (TODO 1, 2026-10-19).
- Station 2, the full run: second haiku round on 0.98.0 — t3 and t18
  reported a probe, t5 an acknowledged run (plan 2026-10-17, A3).
- Station 4, one command for every skeleton: until 0.99.0 the count carried
  its check inside `01_measure.py`, and the station asked for a file the
  skeleton never wrote (audit 2026-10-19).
- `--if-reported` holds the area: a script edited after the answer was
  written back passed both hooks with the protocol untouched (audit
  2026-10-19). An open answer owes nothing: in the third haiku round on
  0.99.0, t3 and t5 reported a probe's number and never called
  report-check.
- `--staged` reads the index: until 0.99.0 the hook read the tree, and a
  reported answer staged, then reopened in the tree, passed the commit
  (audit 2026-10-19).
- A changed declaration reaches the committed reports citing its run
  (`newly_declared`, `committed_reports`): sixth haiku round on c49e760
  (2026-10-23, t5, commits b47f915 and b629ddd) — REPORT.md citing the run
  was committed while the protocol with the declaration stayed unstaged
  (the index's protocol declared nothing: a warning), the next commit
  staged the protocol and held no report; the delivered state failed
  `report-check --if-reported` with a blocker neither commit saw. Only
  the paths given were held until then. The twin: a report whose block
  is already committed passes the declaring commit.
