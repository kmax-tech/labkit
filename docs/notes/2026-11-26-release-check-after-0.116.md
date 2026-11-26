# What the unreleased breaks hit in the lab repos — a count before the next release

2026-11-26. Read and measured only; nothing was released, and no lab repo was changed. State of labkit: `b7c4fa75` (92 commits after `v0.116.0`). The question: which runs and which lab code do the entries under "Breaking" in `CHANGELOG.md` ("Unreleased") reach, and does a lab on 0.116.0 read the same after the move?

## Result

For the one lab pinned to 0.116.0, `finalize` tells the same before and after the move; its other gates were not run. In the labs on an older pin, the new reader does not accept 690 of the 697 patches with changes. The files stay as they are; the runs they belong to are checked and reproduced with the labkit version their lab pins, not with the new one. A move to the new version is therefore a decision per lab, not a general upgrade. Two labs call a name that moved out of `labkit.formats.findings`.

## What was counted

26 repositories under `~/projects` hold run records (`experiments/*/runs/*/config.json`), 1 204 runs in all: 707 with changes in `uncommitted.patch`, 480 with an empty patch, 17 without one.

| Break                                                     | Runs or places hit                                | Where                                                              |
|-----------------------------------------------------------|---------------------------------------------------|--------------------------------------------------------------------|
| Changes in a patch beside a record of a clean tree        | 0 of 1 204 runs                                   | —                                                                  |
| A changed tree whose patch is gone                        | 14 runs                                           | `counterfactual-worlds`, `experiments/11-hong-repair` (pin 0.85.0) |
| A patch is read only as a run writes it today             | 690 of 697 patches in the older labs do not apply | table below                                                        |
| Names moved out of `labkit.formats.findings`              | 2 labs                                            | `twostage-argument-demo`, `labkit-paper` (and its two copies)      |
| Names removed (`verdict_counts`, the `intent_check` ones) | 0 places                                          | —                                                                  |

The patches were read with the reader of this state (`repo.tree_then`, the run's recorded commit and its patch), per lab:

| Lab                     | Pin     | Patches with changes | Read | Do not apply |
|-------------------------|---------|----------------------|------|--------------|
| `argmining27`           | 0.116.0 | 10                   | 10   | 0            |
| `fallacy-detection`     | 0.25.0  | 3                    | 3    | 0            |
| `counterfactual-worlds` | 0.85.0  | 358                  | 4    | 354          |
| `labkit-paper`          | 0.85.0  | 86                   | 0    | 86           |
| `uniagent`              | 0.88.8  | 60                   | 0    | 60           |
| `fallacy-datasets`      | 0.25.0  | 33                   | 0    | 33           |

The remaining labs, read the same way: `labkit-paper-main` 58 of 58, `labkit-paper-usage` 86 of 86 (both are copies of `labkit-paper` at other states, so their runs largely repeat its), the probe repositories, `fallacy-dataset-generation` and `paper-organization` together 13 of 13 — none reads. In all: 707 patches with changes, 17 read (10 in `argmining27`, 3 in `fallacy-detection`, 4 in `counterfactual-worlds`), 690 do not.

Every failure is git's `corrupt patch at line N`: the patch was written stripped by labkit 0.103.0 or earlier, which the entry in the changelog names. No patch file is changed or removed by the new version; it refuses to rebuild the run's start from it.

The two labs that call a moved name:

- `twostage-argument-demo`, `tests/test_argue_rank_scenario.py:245`: `findings.write`, copied from `docs/examples/standin-audit.py`; it is `audit_records.write` now. The lab is pinned to 0.114.0.
- `labkit-paper`, `lib/sandboxlab/standard_check.py:76`: its check of a delivered state takes `area_records` and `audit_coverage` from the module it calls `findings`; they stand in `audit_records` and `audit_gaps`. The file already chooses its module paths by labkit version and needs a third case for the version that carries this move.

## One lab through the real gate

A copy of `argmining27` (working tree as it stood, its own `.venv` linked) ran `finalize` on each of its 15 areas twice: with labkit 0.116.0 from the lab's venv and with this state. The two outputs are byte for byte the same in all 15, exit status included: four areas clear, four with blockers (the same blockers), seven refused because their protocols carry standard 0.26, which neither version reads.

What this shows: for this lab none of the breaks changes a verdict of `finalize`, and no audit record is orphaned by the move. What it does not show: `report-check`, `preflight`, `labkit-audit` and the hooks were not run, and no other lab was put through a gate.

## For the release

1. The entry "A run's patch is read as a run writes it" said such patches "may no longer apply"; it now carries the count, and that the files stay and the runs keep their lab's pin. "In short" of the release entry should repeat that sentence.
2. `twostage-argument-demo` needs its one import changed when it moves; `docs/stagekit-areas.md` points labs to the script it copied.
3. `labkit-paper` needs the third case in its standard check before an image carries the new labkit.
4. `counterfactual-worlds` holds 14 runs whose patch is gone; they were refused by two of three readers before and are refused by all three now.
