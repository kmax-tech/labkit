# Reading probe of `docs/workflow.md` — the four acceptance questions (2026-10-22)

*The acceptance the TODO set for the workflow page ("Klarheit des
Ablaufs"): a reader who did not write the code follows the example and
answers four questions without help. Run as a cold subagent (fresh
context, general-purpose, no tools beyond reading) given exactly two
files — the page at commit `26513e9` and the output of
`docs/examples/count-walkthrough.sh` — and told to open nothing else,
answer the four questions with line citations, then list misreadings,
guesses and passages read twice. Three turns, about 60k tokens.*

## Result

All four answers were right and cited: the answering run is chosen once in
finalize's first station by `answering_run.bound_answering_run` and every
other gate holds that choice; a decision review is owed for an accepted
BLOCKER with `stands` and released only by `upheld`, bound to decision and
Conclusion; `--from-run` changes the protocol file alone; the block equals
its bound sources and the chain holds, the prose and the reading of the
number stay judgement.

What the reader stumbled on, and what was done about it on the page and
the walkthrough (committed after this probe):

| finding | kind | done |
|---|---|---|
| "reports an intent key" vs. a count that registers none — is the condition waived? | misreading | step 4 says it: for a count the answering run is the newest completed bound run |
| protocol-check's "all must and should fields filled" while the Conclusion is open | misreading | step 2 says the Conclusion is owed after the run and not among those fields |
| three names for what `--from-run` writes: the runlog hint ("Answer, Result and Runs"), the command, the page | misreading | the hint in the skeletons and the judge lanes now says "Recorded results, [result] run and the run entry"; step 7 quotes the command's words |
| the Conclusion written after the adoption in the walkthrough, before the review on the page | misreading | the walkthrough writes it before `--from-run`; step 7 says so |
| section 8 and the summary name different residues of judgement | misreading | section 8 names both (the reading of the number, whether a limit is enough) |
| full run, station, release, hint, declared vs. answering run — inferred, not defined | guesses | a "five words" paragraph at the top; the equality of declared and answering run stated in one sentence |
| "the declared run names it (or none yet), its rows come from it" | stumble | the station list rewritten with its nouns |
| "where `minutes`/`hours` owe more, it stands at its place" | stumble | rewritten |
| the second tamper in section 10 showed no `$` command | stumble | both tampers announce the edit and print the command |
| hook output after `git commit` without a label | stumble | the walkthrough says once that every commit runs the probe's pre-commit hook |

Two findings are the tools', not the page's, and sit in the module the
other session has open (`report_check`): the station-1 sentence that ends
in "… the analysis audit and the check are" (the reader reconstructed "are
owed"), and the prefix `analysis audit:` on the blocker for a retyped
Recorded results line, which made the reader look for an audit-record
problem. Both are one-line wording changes there.

Not changed: "lane" for the tier's obligations and "covering records" are
the README's and the architecture's words; the page now links the reader
to them through the five-words paragraph rather than coining again.
