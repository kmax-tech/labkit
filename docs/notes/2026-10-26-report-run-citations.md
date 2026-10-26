# Note 2026-10-26 — a discussed run as a block, not a prose marker

> **Status 2026-10-26: built** (`report_blocks.discussions`,
> `report_blocks.discussion_gaps`, `report_check.discussion_sources`,
> `protocol_fill.discuss_into`; CHANGELOG Unreleased). Step 1 of the order
> after the eighth haiku round (TODO.md, contract V1). The report review
> becoming owed (V2, V3) is step 5 and reads the blocks this note defines.

## The case

Eighth haiku round on 48cd001 (`docs/usability/2026-10-26-sandbox-48cd001.md`,
t3). The adoption was refused, and the agent took the way out the gate
named: it cited the run as not reported. It wrote
``Run `2026-10-26T08-18-33_7392` (not reported: …)``. The closing backtick
stood between the id and the parenthesis, and `report_blocks._NOT_REPORTED`
wanted `<run>\s*(not reported`. The gate read no marker and held the
citation as an unadopted run twice. The agent's next commit was
`git commit --no-verify`.

The data the gate needs here — which run, of which protocol, and why it
is not reported — was encoded in a prose pattern. Markdown that means the
same (a code span, emphasis, a line break) was a different machine state.
The direction TODO.md already holds for 1.0 says machine contracts are
structured, and the explanation is prose. The marker was the last binding
state read out of prose in a report.

## The form

```
<!-- labkit discussed
protocol = "experiments/01-x/PROTOCOL-x.md"
run = "2026-10-26T08-18-33_7392"
why = "adoption refused — target leakage through G_VRH"
-->
Run 2026-10-26T08-18-33_7392 — discussed, not reported: adoption refused — target leakage through G_VRH
<!-- /labkit discussed -->
```

- **One block, one source.** The head is TOML inside the opening comment.
  It holds exactly `protocol` (relative to the report, as the result
  block names it), `run` and `why`, all strings. `tomllib` reads it, so
  quoting, missing and unknown keys get plain sentences. The visible line
  is written from the head (`discussion_body`). The author keeps one
  thing, not a declaration and its rendering side by side.
- **Written by the tool.** `protocol-fill <PROTOCOL> --discuss RUN --why
  "…" --into REPORT` replaces the block of the same protocol and run in
  place, or appends one; other discussions stay. Two blocks of the same
  protocol and run are refused by the writer and blocked by the gate. The
  writer refuses the protocol's declared run (that run is reported:
  `--into` without `--discuss`) and a run its area lacks. The why is one
  line without `-->`.
- **Held by the gate.** A block without its why, a line that differs from
  its head, a repeated block, a run its protocol's area lacks, and a
  discussed run some protocol declares are blockers (guaranteed). The
  undiscussed citation of a protocol's answering run that declares no
  result stays the promotion blocker; its sentence names the `--discuss`
  command. Numbers in and beside a block are a hint (static evidence).
- **The word.** "discussed", the counterpart of "reported": the report
  talks about the run, and its numbers are not the result. `lib term`
  found no coinage in the house; "not reported" already named the probe's
  number in the README.

## What it does not do

The block makes the statement "this run is discussed, not reported"
unambiguous. It does not make it true. Beside a correct block a report
can still say "the method meets every criterion" of a run nobody adopted
— t3 and t18 in rounds seven and eight did. That contradiction is
semantics, and the report review reads it (`labkit-audit --report-review`).
Step 5 makes that review owed for a report with a discussion block.

## Rejected

- **Widening the regex** (accept a code span around the id). One line,
  and the next variation (emphasis, a line break, `run:`) is the next
  miss. Decided against it in the plan review on 2026-10-26: the format
  break comes right away, so the intermediate repair would be built and
  removed in the same series. The t3 text is a regression test instead
  (`test_the_prose_marker_is_not_read_eighth_round_t3`).
- **A TOML head for the whole report** (`[[runs]]` at the top). It is a
  second place beside the visible citation. The block keeps the
  declaration where the reader sees it.
- **A new key syntax in the comment line** (`run … why="…"`). It would be a
  parser of its own for quoting and escapes; TOML has one.
