# Decision review replayed on the fifth haiku round — labkit 366d38c (2026-10-22)

*The first run of `labkit-audit --review` (`gates/decision_review`,
`formats/reviews`), on copies of the three labkit attempts of the fifth
haiku round in labkit-paper area 09 (`attempts_pilot_haiku_v5`, labkit
0.102.0 in the image): every accepted finding with effect `stands` of
their final analysis records, one call per record, reviewer `opus`
(`claude-cli`) through the host labkit. The copies stand in the session's
scratchpad (`r5/t3`, `r5/t5`, `r5/t18`); the protocol heads were set to
standard 0.21 so the host labkit reads them, nothing else was touched.
The code stamps of the copies equal the records' `scope_sha`, the runs
show what the records' `shown_sha` names, so every review was admitted.
The question the exploration answers (TODO, 2026-10-22): does a second
auditor with the finding, the reason, the reported claim and the evidence
separate a limit that holds from one that does not — before a gate blocks
on it.*

## Result

| attempt | record | decisions | upheld | rejected | insufficient | prompt tokens | USD |
|---|---|---|---|---|---|---|---|
| t3 (bulk modulus) | 09-10 | 1 BLOCKER | 1 | 0 | 0 | 17,130 | 0.15 |
| t5 (dkpes classifier) | 09-15 | 3 BLOCKER + 6 WARNING | 0 | 9 | 0 | 16,893 | 0.15 |
| t18 (dili RF) | 09-33 | 1 BLOCKER + 1 WARNING | 0 | 2 | 0 | 52,057 | 0.43 |
| t18 (dili RF) | 09-34 | 1 BLOCKER + 2 WARNING | 1 | 1 | 1 | 16,066 | 0.14 |

Four calls, 0.87 USD. Every report parsed (one `DECISION` line per
finding, the closing counts equal to the lines); four review files
written; `report-check` on the copies names each decision not upheld with
the reviewer's sentence (t5: nine warnings; t18: five, the upheld one
silent).

## What the reviewer separated

- **t3, upheld.** The one `stands`: `cv_rmse` is a training-split CV
  score, the 232 test predictions are scored by nothing. The reviewer:
  the Summary reports the number as exactly that, the Limit line says
  "not test set error", so neither the number nor the conclusion of
  limited predictive power rests on the unscored predictions. It notes
  that the reason's premise (no test ground truth) is unverified on the
  page, but the claim as written does not rest on it. A limit that holds.
- **t5, nine rejected.** The three BLOCKERs: the reason restates the
  finding ("in-sample fit rather than generalization") while the Summary
  still reports a classifier "successfully developed" for test compounds
  — the generalising use the in-sample cut does not support; "an
  exploratory count" does not bring a yes/no question under the count
  exemption, so with no criterion the verdict has nothing to be judged
  against; the registered Unit was never measured, so the promise is
  `not assessable`, not `stands`. The six "Finding noted" WARNINGs: each
  rejected for its own consequence (the unreconciled 10 vs 12 test
  samples, the unregistered `>=` median cut both numbers depend on, a
  field read as inhibition that holds a probability, a recheck that holds
  vacuously, no trivial comparator behind "successfully developed", one
  seed on 28 points). The reason copied across findings was judged
  against each.
- **t18, 09-33 both rejected.** The winner's-curse BLOCKER: the reason
  concedes the bias and offers nothing that makes 0.73 an honest estimate
  while Recorded results and Conclusion report it as "73% mean
  cross-validation accuracy" answering "accurately predict" — `not
  assessable`, not a limit. The baseline WARNING: the ~0.59 majority rate
  is restated from the finding's own arithmetic, and the "~14%
  improvement" is a lift over the same optimistic score.
- **t18, 09-34: one of each.** The same BLOCKER rejected again (the reason
  answers it with "predictions are still generated"). The baseline WARNING
  upheld here: the reviewer recomputed the majority rates from the class
  counts in the protocol's Setup and the rows' `n_train_samples`
  (227/400, 433/660, 490/923) and found the Summary reporting the gain as
  a margin over that baseline. The positional-selection WARNING
  **insufficient**: the reason says train.csv was "verified" as sorted
  into the four blocks, and that evidence is not on the page — the
  `vDILIConcern` values per row range are not inlined. This is the false
  "verified" of the round (TODO, 2026-10-22): the reviewer does not take
  the word for it and does not release.

## Reading

1. The check separates. On 15 decisions it upheld two, rejected twelve,
   held one open — and the two upheld are the two where the claim was
   written as what the number is (t3's CV RMSE, t18's margin over the
   baseline). The round's own judgement ("15 of 28 accepted without any
   action") is what the rejections say, decision by decision.
2. The cost is one audit call per record (0.14–0.43 USD here; the 09-33
   call carried 52k prompt tokens, the others 16–17k — the same files, so
   the difference is the CLI's own context, not the review's), not a
   second audit of the area.
3. `insufficient` earns its place: without it the t18 "verified" claim
   would have had to be upheld or rejected on no evidence. It does not
   release, and the sentence names what to inline.
4. Open before a gate blocks: (a) whether `rejected` should send the
   person to `--decide` again (the message says so) or to a new audit —
   both are allowed today; (b) the reviewer sees the protocol as it is
   *now*, not as it stood when the person decided — a Conclusion
   rewritten after the review reopens nothing, since the protocol prose
   has no digest (the same gap as for the analysis record, TODO
   "Protokollprosa"); (c) a second cold reviewer on the same decisions
   would show the verdicts' spread; one draw per record here.

## Second cold pass (labkit with the claim bound, same copies, same model)

After the review was bound to the judged claim (`claim_sha`: Conclusion,
Recorded results, Limit lines — a strengthened Conclusion makes a review
stale), the same four records were reviewed again, cold. 0.90 USD.

| record | decision | pass 1 | pass 2 |
|---|---|---|---|
| t3 09-10 | #1 BLOCKER, CV RMSE as measurement | upheld | upheld |
| t5 09-15 | #1–#9 | rejected ×9 | rejected ×9 |
| t18 09-33 | #1 BLOCKER, winner's curse | rejected | rejected |
| t18 09-33 | #2 WARNING, majority baseline | rejected | upheld |
| t18 09-34 | #1 BLOCKER, winner's curse | rejected | rejected |
| t18 09-34 | #2 WARNING, majority baseline | upheld | insufficient |
| t18 09-34 | #3 WARNING, positional selection "verified" | insufficient | insufficient |

13 of 15 verdicts agree. Both disagreements are the one decision at the
margin — the hand-computed majority baseline, the same reason in two
records — which over four draws came back rejected, upheld, upheld and
insufficient: the reviewer is undecided whether a baseline restated from
the finding's arithmetic, not computed in the run, lets the "~14%
improvement" stand. No clear decision moved: no rejected BLOCKER became
upheld, no upheld BLOCKER became rejected, the nine "Finding noted"
rejections held, and the "verified" claim stayed `insufficient` twice.
Reading: the spread sits where a person would hesitate too; a gate that
blocks on `not upheld` would, on this material, block the right things
and ask twice about the borderline one. What this is not: an independent
judgement of the twelve rejections — that reading is still owed before
the warning becomes a blocker.

Reports as the model wrote them: the first pass's review files in the
scratchpad's `pass1/` (written before `claim_sha`, no longer read), the
second pass's in the copies (`experiments/*/audits/2026-10-22T13-5{6,7}-review*.toml`),
the raw reports `review-*.md` (pass 1) and `review2-*.md` (pass 2).
