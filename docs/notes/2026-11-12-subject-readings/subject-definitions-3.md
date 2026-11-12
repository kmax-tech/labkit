Ask two questions of a cause: which thing does the finding call wrong, and against what is it held? The subject names the thing called wrong.

| Subject | The finding says … | Belongs here too | Does not belong here |
|---|---|---|---|
| protocol text or head | the protocol file as it stands is wrong | a field, a table of the head, the promise block's form; two parts of the protocol that contradict each other; a protocol changed after a run was measured under it; a head or table that does not read | a run that did not deliver what the protocol asks |
| run record in itself | a run's own record is missing, incomplete or does not read | its kind, lineage, draws, sources, outputs, models, the commit it recorded; no run that may answer, or two | a record that is complete and differs from the protocol or from the files |
| run record against the registration | a run did not deliver what the protocol, unchanged since, registers | a registered key the run did not report, a constant recorded with another value, a missing verdict or kept number | a protocol changed after the run |
| run record against the state | the files are no longer what a run recorded | code, a declared scope, a source or an output changed, moved or gone since the run | an audit that no longer covers the code |
| audit coverage | an audit or a review does not cover what the number rests on | no audit or review record for the state as it is; code, protocol or evidence changed after the audit; the run an audit read is gone; code the audit's stamp cannot follow (an import outside the covered roots, code loaded at run time, another area's file) | an audit finding nobody decided |
| records among themselves | audit findings, their decisions, follow-ups and handovers do not fit each other | an undecided finding, a follow-up that does not fit; an audit, review or handover record that does not read | whether an audit covers the present state |
| generated line or block | a line or block labkit writes between its markers into the protocol or the report is missing, malformed or differs from its source | the result block, the Recorded results line, a discussion block, the handover and progress blocks of a report | the report's sentences outside such a block |
| report prose | a sentence of the report outside any labkit block names a run id or a number without a source | | a block labkit wrote |
| code against the registration | the area's code lacks what the protocol registers | a key literal, a registered constant copied into the code, the prompt | code the audit does not cover |
| area tests | the area's tests are missing, did not run or failed | a test run that could not start, whatever the reason (also a missing pytest); a parser no test calls | |
| text beside the protocol | a note or the area's README is wrong | a note's meta line, the README's route; a note that cannot be read | |
| repository or installation state | the repository or the installation is not in the state a check needs | uncommitted or untracked files, hooks, no git repository; a commit, tree or past version git cannot give back; a code file that cannot be read or parsed | |

Seven rules for a doubt:

1. **What does not read.** The subject is that of the thing that does not read: a protocol, a run's record, an audit record, a note. A code file, and anything git is asked for and cannot give back (a commit, a tree, a past version of any file), is "repository or installation state".
2. **Two things compared.** The one changed later is called wrong; the other is the fixed side. A run's record is fixed when the run ends: a protocol that differs from it was changed after the run.
3. **Not the fix, not the teller.** The subject follows what the finding calls wrong — not the file the way out edits, and not the function or gate that tells it.
4. **None.** A cause that calls no such thing wrong is not assigned.
5. **A field that names something absent.** A protocol field that names a file or a run that is not there: the field is wrong — "protocol text or head". Where the thing named is an audit or review record, the question is whether an audit covers the state — "audit coverage".
6. **A sentence that wraps another cause.** "X cannot be held to Y: <why>" takes the subject of the why it names, not of X. Where one item bundles several whys of different subjects, take the first named and mark the item unclear.
7. **A check that could not run.** A cause that says only that a check could not be done (and shows nothing wrong) takes the subject of what the check would have looked at.

Do not force an answer. Where the definitions and rules do not decide, give your best subject and set "unclear": true.
