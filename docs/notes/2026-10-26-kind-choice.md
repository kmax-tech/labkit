# Choosing the kind: training comes first

*2026-10-26, ninth haiku round of labkit-paper area 09 (labkit `85c54fd`),
t3-labkit. Code: `labkit/tools/scaffold.py` (`KIND_QUESTIONS`, `next_steps`),
`labkit/templates/AGENTS.md.template` (lane `low`, step 1).*

## What happened

The task said "Train a random forest model … save the test set predictions".
The agent had the stamped AGENTS.md in context, with the two kind questions
and RandomForest named as the example of a fit. It wrote "This is a low-cost
computation (model training and prediction), so I'll use the low repeat cost
lane" and ran `labkit-init exp … --repeat-cost low --kind compute`. The next
steps then said "no criterion … a computation has no bar to clear"; the
protocol never got a criterion or an admissibility condition.

## Reading

Two things met:

- The lane text described `low` as "a computation, a handful of model calls",
  so the word of the kind stood in the definition of the cost.
- The questions began with "does the number judge how well a model
  predicts?". With unlabelled test rows the deliverable is a predictions
  file, not a score, so the agent could answer "no".

Rewriting the criterion sentence alone would have left the wrong kind in
place. The fix moves the decision ahead of the cost.

## Now

- The questions ask first whether the area trains, adjusts or selects a
  model, and say that predictions on unlabelled rows are still a fit whose
  kept number is the held-out score. Help, the refusal without `--kind` and
  a computation's next steps print one text.
- A computation's next steps open with that check and the restamp command.
- The lane text no longer uses "computation" for the cost, and says that
  the cost does not decide the kind.

Whether this is enough is open until a cold agent meets it (the repair case
after the ninth round).
