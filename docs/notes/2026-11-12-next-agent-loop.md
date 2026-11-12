# The agent loop and report duties — 2026-11-12

## Problem

The shipped agent entry tells the agent to run `labkit-next`, take the named step and repeat. A measured protocol with a report registered before the measurement can still owe delivery after its file is deleted. `report-check` named that duty and required the old protocol to be restored. `labkit-next` instead ended before building the area state and instructed the agent to create a new protocol. The suggested action could not close the gate's finding.

The full agent guide, workflow and next-step hint also described the former rule that report targets could neither be added nor moved after measurement. The implemented narrow contract permits both and only keeps a lasting duty from the first measurement's committed registration.

## Correction

`next_step.next_step` builds the area state before its no-protocol branch. The branch asks `report_check.orphaned_duty_gaps` for the existing gate findings and prints the first finding's text and repair instruction. It creates no new report check and does not change release behavior. With no outstanding orphaned duty, it continues to suggest registration. Both paths judge the requested file state.

The independent clarity review also found that the command selected protocols from the working tree even with `--staged`. `repo.the_protocol` and its printing form now accept the index explicitly; the command lists candidates from that state as well. A protocol deleted only in the tree is still selected from the index, including when named by a bare file name. Symbolic links are checked in the selected state.

The guide and workflow now distinguish the lasting delivery duty from its movable target and from a target first entered after measurement. The pre-measurement hint encourages registering a required report without claiming that registration later is prohibited. The full guide states that `next` can run checks but does not execute its suggested action. The short entry distinguishes printing guidance from release; it remains within its tested 1,200-word limit.

## Verification

`tests/test_registration_committed.py`, `ReportOwedByADeletedProtocol`: the new next-step regression failed in both the working tree and index before the correction. It compares the printed action with the gate's own finding. The twin permits registration after deletion of a measured protocol that owed no report. The ordinary registration-to-adoption scenario in `tests/test_next_step.py` checks the updated hint and continues through the existing loop.

`tests/test_next_step.py`, `ProtocolInTheIndexOnly`: automatic selection, an explicit path and a bare file name all failed before the index-selection correction; afterwards they select the staged protocol and name the working-tree/index difference. `tests/test_repo.py`, `IndexProtocolChoice`, checks ambiguity, an untracked candidate, an indexed symbolic link replaced by a regular tree file, and the converse.

The generated instructions are tested as package templates; updating already stamped instructions in other repositories is separate rollout work. No real model was invoked.

The three next-step/registration files passed together before the index-selection correction: 137 tests and 20 subtests. After that correction, the focused repository, indexed-command, no-repository and orphaned-duty cases passed: 77 tests and 36 subtests, exit 0. The independent clarity reader's two findings (selection from the wrong state and the outside-repository error path) were corrected; its final verdict was zero findings. No full-suite result is claimed for this change.
