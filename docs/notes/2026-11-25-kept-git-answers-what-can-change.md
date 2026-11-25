# When HEAD, the index and the working tree can change within a command (2026-11-25)

An examination, nothing built. Since `aa3603b1` a command keeps git answers about an object named by its full hash ([measurement](2026-11-25-suite-runtime.md), last section). This note asks what would have to hold before an answer that depends on `HEAD`, the index or the working tree is kept too, and how much each kind would save.

## What is left, by what the answer depends on

The same logged run as in the measurement (`tests/test_repair_paths.py`, a correction then a code repair, run alone, after the change): 3303 git calls through `labkit/formats/repo.py`, 2391 of them repeat an earlier call of the same process word for word. The repeats are an upper bound of what keeping can save; the second run of the pair gave the same counts.

| The answer depends on                                                  | Calls | Repeats | Share of all calls | Mostly                                                                      |
|------------------------------------------------------------------------|-------|---------|--------------------|-----------------------------------------------------------------------------|
| `HEAD`, a branch, or the history read by name                          | 1615  | 1314    | 40 %               | `head_sha` (618), `area_state.last_committed`'s `git log` (566), `files_at` |
| the index                                                              | 530   | 342     | 10 %               | `git show :path` (`text_at`), `git ls-files --cached` and `--stage`         |
| where the repository is (`--git-dir`, `--git-common-dir`)              | 452   | 392     | 12 %               | `files_at`, `git_dir_path`, `evidence._repo_of`                             |
| the content of two objects named by full hashes — cannot change        | 168   | 128     | 4 %                | `tree_diff` (144), `git show <commit>:path` (24)                            |
| which history the clone holds: is one full hash an ancestor of another | 102   | 85      | 3 %                | `is_ancestor`                                                               |
| the working tree                                                       | 103   | 47      | 1 %                | `git status`, `git diff HEAD`, `git ls-files --others`                      |
| an object by its full hash, or a run's tree — kept since `aa3603b1`    | 333   | 83      | 3 %                | first builds; the repeats are in processes that are no command (see below)  |

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
- **The content of objects named by full hashes: can be kept under the rule that stands** — `tree_diff` of two tree ids, a file at a full commit hash. 128 repeats, 4 % of the calls.
- **The ancestor question is not of that kind**, though both hashes are full: its answer depends on how much history the clone holds. Tried in a shallow clone that held both commits: `git merge-base --is-ancestor A B` exits 1, after `git fetch --unshallow` it exits 0. It belongs with the history read by name. 85 repeats, 3 %.
- **Where the repository is: the answer belongs to the directory asked from, not to the repository.** Tried: from the root git answers `.git`, from a subdirectory the absolute path, from a linked worktree `…/.git/worktrees/NAME` with the main repository's `.git` as the common directory; a relative answer is read against the directory asked from (`repo.git_dir_path`). So the key is the resolved directory, per question (`--git-dir`, `--git-common-dir`). A worktree moved in mid-command (`git worktree move`) is a new directory and so a new key; its git directory keeps its name. With `GIT_DIR` in the environment, as inside a hook, git answers that directory from anywhere; labkit passes git only `GIT_INDEX_FILE`, so this holds for a whole process. The answer "no repository" is never kept (`labkit-init`, `usability stage` create one); two of the three asking sites read only that (`repo.files_at`, `evidence._repo_of`). Not tried: a worktree removed while a command runs in it, submodules. 392 repeats, 12 %.
- **`HEAD`, history and the index: no rule proposed yet.** Dropping every kept answer of this kind when the command starts a process other than git, calls a model or sleeps covers the five sites of items 3 and 4, and a test would have to hold that no other site starts a process. It does not cover a person or another session acting during a command that does neither. 1741 repeats with the ancestor question, 53 %.
- **Keeping from each question's first asking is no snapshot.** A command could keep `HEAD` = A, and after a commit from outside ask the history for the first time and keep it as of B: two states, held for the rest of the command. One state per command would need every such answer read at one moment, or derived from the one commit read first (the history of that hash, not of `HEAD`); the index has no such name. Which state a gate judges is the contract, so this stays an examination.

## A replacement changes what a full hash answers — a question before the keeping

Tried in a scratch repository with two commits, the second replaced by the first (`git replace C2 C1`), each reading once plain and once with `GIT_NO_REPLACE_OBJECTS=1`:

| Reading                                                 | Plain, the replacement honoured | Replacements excluded |
|---------------------------------------------------------|---------------------------------|-----------------------|
| `git rev-parse C2^{commit}`                             | C2                              | C2                    |
| `git rev-parse C2^{tree}`                               | the tree of C1                  | the tree of C2        |
| `git show C2:f`                                         | the content at C1               | the content at C2     |
| `git read-tree C2` in a temporary index, then the blobs | the blobs of C1                 | the blobs of C2       |
| `git cat-file blob B` after `git replace B OTHER`       | the other content               | the content of B      |
| `git merge-base --is-ancestor C1 C2`                    | no (exit 1)                     | yes (exit 0)          |
| `git log HEAD`                                          | one commit                      | two commits           |
| `git status` on a clean tree                            | `f` modified                    | clean                 |
| `git diff TREE1 TREE2`, `git hash-object f`             | the same                        | the same              |

A clone of that repository carries no replacement (`refs/replace` is not fetched by default).

So "a full hash" does not by itself make git's answer fixed, and the docstring of `repo._once_by_hash` is too narrow in naming only pruning. But the keeping is the smaller part. labkit passes git no setting on this, so every reading honours a replacement today, kept or fresh: in a clone that holds one, the tree a run "started from", a protocol at its registered commit and a blob by its recorded id are read as the replacement, while the record names the hash of the real object — and another clone of the same commit reads something else. What `aa3603b1` adds is one case: a replacement created or deleted while a command runs is not seen for the rest of that command, for the four kept readings.

The decision that stands before any wider keeping, and applies to kept and fresh readings alike:

- **Read the real objects**: every git labkit starts gets `GIT_NO_REPLACE_OBJECTS=1` (one place, `repo.git_run`, and `repo.blob_bytes`, which starts git itself). Then content by full hash is fixed while the object exists, and two clones of one commit read the same. A lab that uses replacements on purpose sees labkit disagree with its own `git log` and `git status`.
- **Honour replacements**, as today: then no answer about content is fixed by its hash, and what is kept would have to be dropped at the points where a process other than labkit's git may have run — the rule not yet found for `HEAD`.
- In between: refuse or warn when the repository holds a replacement (`refs/replace/`), and keep as today otherwise.

**Decided by the author and built (2026-11-25): the real objects.** Every git `labkit/formats/repo.py` starts runs with `GIT_NO_REPLACE_OBJECTS=1` (`repo.NO_REPLACE_ENV`); tests read a replaced blob and a replaced commit fresh, kept, and with the replacement made in mid-command, each after plain git showed the replacement in force (`tests/test_repo.py`, `ReplacedObjects`). This settles replacements only. It does not make two clones of one commit hold the same history: a shallow clone and grafts still change that.

Not tried: grafts (`.git/info/grafts`, deprecated), which change parents like a replacement does; `git gc --prune` in mid-command, the limit already named.

## The two open cases of "where the repository is"

Tried in scratch repositories.

- **A linked worktree removed while a command asks from it** (`git worktree remove --force`): the directory and the git directory it named (`.git/worktrees/NAME`) are gone. Asked again, git cannot start there (`FileNotFoundError`, today a `GitError`); made anew as a plain directory, git answers "no repository". A kept answer would name a git directory that no longer exists.
- **A submodule**: from inside it git answers the superproject's `.git/modules/NAME` for both the git directory and the common directory, and `.git` there is a file; the superproject's root answers `.git`. The answers differ per directory, as with a worktree, so the key by resolved directory holds. But for an old-style submodule with its own `.git` directory, `git submodule absorbgitdirs` changes the answer for the same directory from `.git` to `…/.git/modules/NAME`, and the kept relative answer then points at a file.

So the directory as key is right but not enough: in both cases the answer for one directory changes because another process restructured the repository during the command — the same kind of event as a replacement or a pruning. Unlike those it can be seen without starting a process: a kept git directory that is no longer a directory is dropped and asked again. That test is not enough to build on, though: a git directory that still exists need not still belong to the directory asked from. The `.git` file of a worktree or submodule can come to name another git directory while the old one stays, and the kept answer would then be a wrong place that exists. Telling that apart needs the identity of the link, a second mechanism for at most 12 % of the calls. Put back: first see how much waiting is left after the changes above.

Not examined: whether a check compares two readings of `HEAD` or the index within one command apart from item 5; the hooks an agent harness calls (`claude-hook`, `codex-hook`), which are single commands but run while an agent works; a repository with `reftable` or several worktrees, where a branch can move from another worktree. Counts and scripts: internal evidence repository, `2026-11-25-check-inventories/run6-kept-answers/` (`classes.py`, `repeats.py`).
