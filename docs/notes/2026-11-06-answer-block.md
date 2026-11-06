# Answer block: the report states the question and the protocol's answer

2026-11-06. Draft for task 4 of `TODO.md` ("Einen ausdrücklichen Antwortblock im Bericht entwerfen"), with a review of the same day worked in (one validation for writer and check, "generated" as carried over, the narrower reach); no code changed. Built after the pin route and the finding's kind; the next usage round judges the three as one package — what this part contributed stays open by design.

## Problem

Six of the seven failed attempts of labkit-paper area 23 delivered a report without the number or without the verdict ([One explainer](2026-11-04-one-explainer-plan.md), "Reading of the repeated usage round"): three sts512 handovers ("no result is reported"), task 34 r1 (two columns and the RMSSD statement missing) and r3 (the demand never answered), assay r2 (0.8665 < 0.90 called "cannot be assessed").

What a report carries today, for a protocol that declares a result (`report_blocks`):

- the **result block**, written by `protocol-fill <PROTOCOL> --into <FILE>`: the protocol's Recorded results line — the reportable verdict of every registered promise, the kept number, the run id — and one line per Limitation (`block_body`), held exactly to the protocol (`block_gaps`, guaranteed);
- prose of the author's around it, which no gate reads for an answer.

So the number and the verdict on each promise are already in the report whenever a result is declared. What no gate requires is the **answer to the question**: the protocol's Conclusion ("the answer in at most two plain sentences: whether the bar set before the run was met, or why no verdict was possible", template Summary) stays in the protocol, and the report may never say it.

**Reach of this change, narrower than the problem:** it secures the visible answer in a report of an adopted result. Of the seven failures it can reach task 34 r3 (the demand never answered) and the form of assay r2 (an answer line the review can hold against the verdict); it does not reach the three sts512 handovers, which end without an adopted result (the pin route and the finding's kind are aimed there), nor task 34 r1's missing columns, a demand of the task sheet, not of the protocol. "Six of seven" motivates the package, not this part of it.

## Proposal

The result block's body gains two lines above its Recorded results line, rendered from the protocol like the rest of the body:

```
<!-- labkit result: experiments/01-x/PROTOCOL-x.md run 2026-10-22T09-13-08_0dc3 (protocol-fill --into; edit the protocol, not this block) -->
Question: <the protocol's registered question, verbatim>
Answer: <the protocol's Conclusion, verbatim>
auc = 0.69, n = 12 (run 2026-10-22T09-13-08_0dc3)
<!-- /labkit result -->
```

- **No new block.** The result block already has a writer (`--into`), an exact check (`block_gaps`), a duty (`blocks_owed`: a report citing a declared run carries its block) and a stale rule (a protocol change makes the block stale, `--into` rewrites it). Two more rendered lines inherit all four. A separate answer block would be a second opener, parser, writer and check for the same protocol and run.
- **Guaranteed tier:** a report showing a declared result shows, verbatim, the question it answers and the protocol's answer; a changed Conclusion makes the block stale. An empty or placeholder Conclusion has no rendering: the one function that renders the block refuses it, so `--into` refuses to write the block and `block_gaps` holds a block already in the report — a hand-written block with an empty Answer line passes neither. One validation, read by the writer and the check.
- **"Generated" means carried over, not confirmed.** The Answer line is the author's statement, copied from the protocol so the report cannot drop or retype it; it is no recorded verdict. The report review reads it as a claim of the author's — a `contradiction` when the recorded verdict below says otherwise (assay r2's pattern) —, and the brief says so in words; the decision review already binds the Conclusion (`protocol_check.reported_claim`).
- **Not guaranteed:** that the answer is right, or that it agrees with the verdict line below it.
- **A handover owes no answer.** Its block states why no result is reported (`handovers`); that is the honest end without an answer, unchanged.

## Readers and writers

| Place                                                               | Change                                                                                                                                                                                                                                                                                                                       |
|---------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `labkit/checks/report_blocks.py` `block_body`                       | renders the two lines from the protocol text; module docstring's block example                                                                                                                                                                                                                                               |
| `labkit/checks/result_render.py`                                    | the Rendering carries the question and the Conclusion, or `block_body` reads them from the protocol text — one reader, `protocol_check.field_values`                                                                                                                                                                         |
| `labkit/tools/protocol_fill.py` (`--into`)                          | tells the renderer's refusal of an empty or placeholder Conclusion, naming the field; no validation of its own                                                                                                                                                                                                               |
| `labkit/agents/report-review.agent.md`                              | says in words that the Answer line is carried over from the protocol, the author's statement, not a recorded verdict — a claim to check against the verdict line ("Not a claim" names the recorded numbers and verdicts only); changing the brief stales every review once (the fingerprint), so it goes in the same release |
| `labkit/docs/agent-guide.md`, `labkit/docs/protocol-field-guide.md` | the Conclusion is what the report's block shows                                                                                                                                                                                                                                                                              |
| `docs/workflow.md`, `docs/examples/count-walkthrough.sh`            | step 8 shows the two lines; the walkthrough (`tests/test_workflow_example.py`) writes a Conclusion before `--into`                                                                                                                                                                                                           |
| `tests/test_report_blocks.py`, `tests/test_protocol_fill.py`        | twins below                                                                                                                                                                                                                                                                                                                  |
| `CHANGELOG.md`                                                      | Breaking: every result block written before is stale once (`--into` rewrites it), and every report review with it                                                                                                                                                                                                            |

Budget: package about +40 lines (two rendered lines, one refusal, docs strings), tests about +60. More than +80 package lines stops the build for a look.

## Tests

Twins, each seen red on the old code where it changes behaviour:

- a block with the question and the Conclusion passes; the same block with the Answer line retyped blocks (exact, as today for the Recorded results line);
- a Conclusion changed in the protocol after `--into` makes the block stale; `--into` again passes;
- `--into` with the Conclusion a placeholder is refused naming the field; filled, it writes;
- a hand-written block whose Answer line is empty, beside a protocol whose Conclusion is empty, blocks at `report-check` — the same refusal as `--into`, from the same function;
- a handover owes no answer line;
- the walkthrough ends as `docs/workflow.md` says, with the two lines in REPORT.md.

Review case (the semantic side, a fixed reply in the suite tests only the routing): a block correct in every generated line whose Answer says "cannot be assessed" while the verdict line says "not met" — the brief's wording must lead the reviewer to a `contradiction` on the Answer line. It goes into the repair-path probe with a real reviewer; the suite holds that the bundle hands the reviewer the Answer line outside the "recorded verdict" exemption.

## Check before building

1. **Which question.** Two fields can carry it: `Question / hypothesis` is registered before the run and anchored at the first measurement (`protocol_history.UNCORRECTABLE_FIELDS`); `Question †` is the Summary's plain rewording, written after the run. See open decision 1.
2. **When the Conclusion is owed — checked at the code (2026-11-06): after the adoption, not by it.** The Conclusion is a field of level `after` (`labkit/formats/protocol_check.py:137`). `protocol_check.owed` — what `labkit-next` names before `labkit-adopt` and what the adoption refuses on (`adopting=True`) — returns the levels must, should and report only, so an adoption does not owe it. It becomes owed once the head declares a result: `protocol_report.unreported` lists every `after` field still empty, and protocol-check prints it as a must ("the head has adopted run … but Conclusion empty", `labkit/checks/protocol_report.py:796`); the pre-commit holds the changed protocol on it. The agent guide asks for it earlier, as advice: "Write the Conclusion before the adoption" (`labkit/docs/agent-guide.md:252`). Consequence for this draft: `labkit-adopt` writes the registered report's block itself (`docs/workflow.md`, step 7), so with the renderer refusing an empty Conclusion an adoption could stop half-way, the protocol adopted and the block unwritten. See open decision 3.

## Open decisions

1. **Which question the block shows.** (a) The registered `Question / hypothesis`, verbatim — what the number was measured to answer, unchangeable after the first measurement; it may be technical and carry the expectation. (b) The Summary's `Question †` — plain words for a reader, but written after the run and free to drift from the registered one. Recommended: (a); the block's point is that the report answers the question that was registered, and a reader-friendly wording stays in the report's prose.
2. **Separate block or two lines in the result block.** Recommended: the two lines, for the reasons above; a separate block only if a report should show an answer without a declared result, which the handover already covers.
3. **The Conclusion's place in the order.** (a) The adoption owes it: `owed(adopting=True)` adds the Conclusion, so `labkit-next` names it before `labkit-adopt`, the adoption refuses without it, and the guide's advice becomes the rule — the block can then always render, and adopt never stops half-way. (b) It stays owed after the adoption, and the block renders until then with a visible "Answer: not yet written" that `block_gaps` holds as a blocker — two states of the block instead of one. Recommended: (a); the number the Conclusion answers exists once the run is measured, and one rule for next, adopt and the block is simpler than a second block state.
