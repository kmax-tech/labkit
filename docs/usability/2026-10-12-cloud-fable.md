# Cloud probes — a cold Fable agent, the count task, ten draws (2026-10-12)

*Usability trace of the kept-number chain in a claude.ai/code cloud session:
no house directory, no skills, only the pinned package and the stamped probe
repo. Model: Fable 5.1 (the strongest available — times are a lower bound,
see the caveat). Score files: `2026-10-12-cloud-fable-count-N.score.json`.*

## Setup

- Probe repo `kmax-tech/labkit-probe` (public: pip clones labkit only
  anonymously, so labkit went public too), stamped with `usability stage
  --task count` and two edits for the cloud: the step log is `log.md` in the
  repo (git-ignored, `git add -f` at the end) and the work leaves on branch
  `probe-count`.
- Environment: setup script (`cd "$CLAUDE_PROJECT_DIR"`, fresh venv,
  `pip install --no-cache-dir -r requirements.txt`, `labkit-hooks install`,
  `labkit-check` as a guard), network "Trusted", no secrets.
- **The cloud reuses the previous session's container and skips the setup
  script unless the environment was edited** (draws 3, 5, 7 ran on the
  previous tag's venv; seen in the sessions' "Initialized session" step).
  Since draw 8 a SessionStart hook in the probe's `.claude/settings.json`
  rebuilds the venv when `labkit-check` says the install lags the pin.
- Scoring: fetch the branch as `probe-count-N`, copy `log.md` beside the
  dir, `usability score` (log-based time; no transcript from the cloud).

## The draws

| Draw | labkit | log span | read · run · edit · unsure · gate | number right, bound |
|---|---|---|---|---|
| 1 | 0.85.0 | 4m27s | 3 · 17 · 7 · 3 · 3 | yes |
| 2 | 0.86.0 | 2m28s | 4 · 10 · 7 · 2 · 2 | yes |
| 3 | 0.86.1 (venv 0.86.0) | 2m26s | 3 · 13 · 6 · 0 · 2 | yes |
| 4 | 0.86.1 | 2m09s | 4 · 9 · 6 · 0 · 1 | yes |
| 5 | 0.86.2 (venv 0.86.1) | 2m39s | 4 · 10 · 6 · 1 · 2 | yes |
| 6 | 0.87.0 | 3m36s | 10 · 15 · 7 · 1 · 3 | yes |
| 7 | 0.87.1 (venv 0.87.0) | 4m23s | 8 · 13 · 6 · 1 · 3 | yes |
| 8 | 0.87.1 | 2m20s | 6 · 14 · 6 · 1 · 0 | yes |
| 9 | 0.87.1 | 2m06s | 4 · 11 · 4 · 0 · 1 | yes |
| 10 | 0.87.1 | 3m42s | 5 · 13 · 6 · 1 · 0 | yes |
| 11 | 0.88.0 | 3m11s | 5 · 13 · 6 · 0 · 1 | yes |
| 12 | 0.88.0 | 1m34s | 5 · 9 · 4 · 0 · 0 | yes |
| H2 | 0.88.1 (Haiku 5.5) | 1m13s | 13 · 16 · 9 · 1 · 2 | yes |
| H3 | 0.88.1 (Haiku 5.5) | 2m30s | 11 · 21 · 8 · 1 · 1 | yes |
| H4 | 0.88.1 (Haiku 5.5) | 1m47s | 17 · 20 · 10 · 2 · 1 | yes |
| H5 | 0.88.5 (Haiku 5.5) | 0m54s | 11 · 13 · 3 · 0 · 1 | yes |

Three clean draws on 0.87.1 (8–10): median 2m20s, 0 or 1 gate line, 0 reads
of labkit source. Before the fixes (draw 1, 0.85.0): 4m27s, 3 unsure, 3 gate.

Draw 11 (0.88.0, 2026-10-13) is the check for `protocol-fill --from-run`: the
log carries one write-back line (`protocol-fill --from-run <run_id>`) and no
edit of the Answer, Result or run line by hand; the agent left the generated
Result line unchanged because `--check` holds the key verbatim. The one gate
line is the README contract placeholder again (decision below).

Draw 12 (0.88.0, 2026-10-13) repeats it in 1m34s with no gate line in the log
(finalize's README warning was handled inside one step); write-back again by
`--from-run`. The model is in every score file since 0.88.2 (`"agent"`).

Haiku 5.5 on 0.88.1 (draw H2, 2026-10-13): right and bound in 1m13s, 0 source
reads, no README line any more. Its one `unsure` was a real contradiction — the
seconds lane in AGENTS.md still asked for criterion and admissibility — and its
hand edit of the head's `type` was a gap in `protocol-fill --list`; both fixed
in 0.88.3. The two gate lines are its own notes (code-check not yet run; a late
entry), not a labkit refusal.

Haiku H3 (0.88.1 again, before 0.88.3 was stamped): the same head-`type`
round trip, and one new finding — the run index said `beae3bf+dirty` while
`uncommitted.patch` was empty, because the end state counted the run's own
untracked products (74 of 74 rows in uniagent carried the flag). Fixed in
0.88.4: the end state counts tracked files only.

Haiku H4 (0.88.1, the probe still not re-stamped): 1m47s, right and bound. Its
three sinks were all labkit's and are fixed in 0.88.5 — a BrokenPipe traceback
when `--contract` is piped to `head`, the flag read as a file name after the
path, and `--check` before the write-back saying "numbers not in PROTOCOL"
instead of "no answer yet, run `--from-run`". Its two `unsure` lines are the
cloud's own (the venv already built; the session's branch vs. `probe-count`).
Still open from its list: a skeleton for a directory-per-item source (n), the
run outputs committed by the tool (w).

Haiku H5 (0.88.5, the first draw with every fix since 0.88.1, the probe
re-stamped by `stage --restamp`): 0m54s, right and bound, 0 `unsure`, 0 source
reads, 3 edits — the shortest draw of the series. None of H4's three sinks
appears in its log or report. Its one `gate` line is the cloud's own (the
session's branch vs. `probe-count`). Its list: the counting skeleton's three
stubs made it read the script and the area test first (n/z); the
`Terms of this protocol` field is owed at a count with no coinage, and
`protocol-fill` takes one label per call (q, new); `log.md` git-ignored costs a
second commit (w); `data=` freezes the case list, not the document files the
number counts (t, new). Caveat on the span: the log was created after the
first reads, so the first two lines carry the log's own creation time.

## What the draws changed in labkit

| Version | From | Fix |
|---|---|---|
| 0.86.0 | draw 1 | pytest in the stamped requirements; `evaluate_rows` in the counting skeleton; no A2 table at seconds without a model |
| 0.86.1 | draw 2 | rows carry `_prov` inside the run; the probe lock knows pytest; `--show`/`--probe` only with a model; `Raw output` only with a model; code-check says what seconds does not owe |
| 0.86.2 | draw 4 | a path example in a code span is not a README placeholder |
| 0.87.0 | draws 1–5, decisions | no promise tables and no criterion for a count; Summary at seconds = Result line; one-line placeholders |
| 0.87.1 | draw 6 | the gates agree with the stamp: a protocol that registers no id owes no table; the seconds gate is the question |
| 0.88.0 | draws 1–10, Sonnet, Haiku | `protocol-fill --from-run` writes the Answer, Result and run lines from metrics.json; the skeletons print the command |

## What every agent still names (decisions, in TODO)

- `protocol-check --contract` prints the full form at seconds; only its first line counts.
- The README's contract paragraph is a placeholder only `finalize` reports, after the run.
- `finalize` always warns on the first pass (output not yet tracked) — a second pass is built in.
- ~~The number is written back by hand~~ — `protocol-fill --from-run` since 0.88.0, confirmed by draw 11.
- Draw 11 adds: the README duplicates the protocol at seconds (one question, contract, checkboxes); the measure script could run the write-back itself; the field names could be stamped from the task (TODO (n)); three commits for one 0.1 s count.
- Terms, Unit and Exclusions restate `visible()` in prose for a file count.

## Sonnet 5.5 and Haiku 5.5, same probe, one draw each

| Draw | labkit | log span | read · run · edit · unsure · gate | number right, bound |
|---|---|---|---|---|
| sonnet-1 | 0.87.1 | 0m42s | 4 · 7 · 4 · 0 · 0 | yes |

Right and bound, 0 reads of labkit source, finalize clear; the log was
started after the first two reads, so the span is a floor. The SessionStart
hook rebuilt the venv (the agent noted it). What Sonnet names: the same
five cuts as Fable — README placeholders only finalize asks for, the field
contract as a separate step, one protocol-fill per field, the two-pass
finalize — plus a worked example in the counting skeleton. One new
reading: "Result" was ambiguous between the Summary line and the Result
section.

| haiku-1 | 0.87.1 | 2m10s | 14 · 19 · 5 · 1 · 0 | yes |

Haiku: right and bound, finalize clear, 0 reads of labkit source, but
twice the reads and runs of Sonnet — it found every placeholder one round
trip at a time (script stubs, the head's `type`, the README) and typed the
number into three protocol lines by hand before `--check` passed, which it
names as the retyping LAB-041 forbids. Its cuts are the same list again,
with the write-back first.

## Caveat

The agent is Fable 5.1. "0 reads of labkit source" and ~2 minutes say little
about Sonnet or a local model; what Fable finds as template defects holds
for every agent. The same series with a weaker agent is the next measurement.
