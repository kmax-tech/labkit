# When HEAD, the index and the working tree can change within a command (2026-11-25)

An examination, nothing built. Since `aa3603b1` a command keeps git answers about an object named by its full hash ([measurement](2026-11-25-suite-runtime.md), last section). This note asks what would have to hold before an answer that depends on `HEAD`, the index or the working tree is kept too, and how much each kind would save.

## What is left, by what the answer depends on

The same logged run as in the measurement (`tests/test_repair_paths.py`, a correction then a code repair, run alone, after the change): 3303 git calls through `labkit/formats/repo.py`, 2391 of them repeat an earlier call of the same process word for word. The repeats are an upper bound of what keeping can save; the second run of the pair gave the same counts.

| The answer depends on                                               | Calls | Repeats | Share of all calls | Mostly                                                                      |
|---------------------------------------------------------------------|-------|---------|--------------------|-----------------------------------------------------------------------------|
| `HEAD`, a branch, or the history read by name                       | 1615  | 1314    | 40 %               | `head_sha` (618), `area_state.last_committed`'s `git log` (566), `files_at` |
| the index                                                           | 530   | 342     | 10 %               | `git show :path` (`text_at`), `git ls-files --cached` and `--stage`         |
| where the repository is (`--git-dir`, `--git-common-dir`)           | 452   | 392     | 12 %               | `files_at`, `git_dir_path`, `evidence._repo_of`                             |
| two objects named by full hashes, compared or read — cannot change  | 270   | 213     | 6 %                | `tree_diff` (144), `is_ancestor` (102), `git show <commit>:path` (24)       |
| the working tree                                                    | 103   | 47      | 1 %                | `git status`, `git diff HEAD`, `git ls-files --others`                      |
| an object by its full hash, or a run's tree — kept since `aa3603b1` | 333   | 83      | 3 %                | first builds; the repeats are in processes that are no command (see below)  |

The 83 repeats of the last row come from two kinds of process that keep nothing by design: the analysis script (22) and the test's stand-in for the auditor, which calls `audit.main` directly, without `console.exit_with` (61).

## What changes these within a command

Read in the code, each search checked on a hit known to be there (`git add` in `labkit/probes/usability.py`).

1. **labkit itself never moves `HEAD` and never writes the index of a lab repository.** No `git add`, `commit`, `checkout`, `reset`, `stash`, `update-index` or `update-ref` is run on it: the one staging command is printed for the person (`commands.py`), the tree a run saw is built in a temporary index (`repo._build_index_then`), and `labkit/probes/usability.py` stages and commits only in the probe repository it builds. `labkit-hooks install` writes `core.hooksPath`.
2. **labkit writes the working tree all the time**: a protocol (`protocol-fill`, `labkit-adopt`), audit records, run directories and the run index, stamped files.
3. **A command starts processes that can change all three**: the area's tests (`preflight.area_tests`), the analysis script with `--check` (`report_check.check_analysis_script`), any command after `usability log … --`, the detached measure script (`runlog start`), and the auditor's CLI (`llm_backends`). These run code labkit does not own.
4. **A command waits, and the person or another session acts meanwhile**: a model call of minutes in `labkit-audit`, and `runlog AREA --wait` and `--follow`, which poll until a run ends.
5. **One command reads again on purpose to see a change.** After the auditor answered, `labkit-audit` refuses to write a record when a shown decision changed while the auditor read (`audit_prompt.decisions_moved`, `audit.py`). A kept answer across that wait would make this check pass always. Only this one was found; the code was not read whole for others.
6. **Inside a commit's hook** `HEAD` moves only after the hook ended, and `git commit -- PATH` hands the hook an index of its own. Whether another process can stage into that index meanwhile was not tried.

## What follows for a rule

- **The working tree: never keep.** labkit writes it itself, and the reads are 1 % of the calls.
- **Comparisons of full hashes: can be kept under the rule that stands** — no new decision. 213 repeats, 6 % of the calls.
- **Where the repository is: changes only when a command creates a repository** (`labkit-init`, `usability stage`). Keeping the answer "here is the git dir" per directory, and never the answer "no repository", follows the pattern of a known commit. 392 repeats, 12 %.
- **`HEAD`, history and the index: the answer holds from the command's first question until the command next starts a process other than git, calls a model, or sleeps.** At those points every kept answer of this kind is dropped; the five sites of items 3 and 4 are the whole list today, and a test would have to hold that no other site starts a process (as `tests/test_one_home.py` holds that git runs only in `repo`). 1656 repeats, 50 %.
- **What this rule accepts:** a commit or `git add` by the person or another session during a command that neither waits nor starts a process is seen at the next command, not in this one. Today such a command reads `HEAD` up to 500 times and can see two states in one run; with the rule it judges one state, the one at its first question. The gap between a gate's last reading and its exit exists today as well.

Not examined: whether a check compares two readings of `HEAD` or the index within one command apart from item 5; the hooks an agent harness calls (`claude-hook`, `codex-hook`), which are single commands but run while an agent works; a repository with `reftable` or several worktrees, where a branch can move from another worktree. Counts and scripts: internal evidence repository, `2026-11-25-check-inventories/run6-kept-answers/` (`classes.py`, `repeats.py`).
