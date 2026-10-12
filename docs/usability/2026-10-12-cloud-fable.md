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

Three clean draws on 0.87.1 (8–10): median 2m20s, 0 or 1 gate line, 0 reads
of labkit source. Before the fixes (draw 1, 0.85.0): 4m27s, 3 unsure, 3 gate.

## What the draws changed in labkit

| Version | From | Fix |
|---|---|---|
| 0.86.0 | draw 1 | pytest in the stamped requirements; `evaluate_rows` in the counting skeleton; no A2 table at seconds without a model |
| 0.86.1 | draw 2 | rows carry `_prov` inside the run; the probe lock knows pytest; `--show`/`--probe` only with a model; `Raw output` only with a model; code-check says what seconds does not owe |
| 0.86.2 | draw 4 | a path example in a code span is not a README placeholder |
| 0.87.0 | draws 1–5, decisions | no promise tables and no criterion for a count; Summary at seconds = Result line; one-line placeholders |
| 0.87.1 | draw 6 | the gates agree with the stamp: a protocol that registers no id owes no table; the seconds gate is the question |

## What every agent still names (decisions, in TODO)

- `protocol-check --contract` prints the full form at seconds; only its first line counts.
- The README's contract paragraph is a placeholder only `finalize` reports, after the run.
- `finalize` always warns on the first pass (output not yet tracked) — a second pass is built in.
- The number is written back by hand; a `--write-back` or `protocol-fill --from-run` would replace three edits.
- Terms, Unit and Exclusions restate `visible()` in prose for a file count.

## Caveat

The agent is Fable 5.1. "0 reads of labkit source" and ~2 minutes say little
about Sonnet or a local model; what Fable finds as template defects holds
for every agent. The same series with a weaker agent is the next measurement.
