# Semantic review of the chain rewrite (2026-11-26)

The rewrite in `bc989729` preserves the detailed conditions in all 17 changed sections as far as this independent comparison found. Two new lead sentences overgeneralize those conditions. These are documentation findings, not observed changes to gate behaviour. No change to `docs/chain.md` is made by this review.

## Scope and method

An independent reader, `chain_semantic_review`, compared `bc989729^:docs/chain.md` with `bc989729:docs/chain.md`, section by section, including the decisions section that had already been read. The reader did not write the rewrite, edit files or run tests. The coordinating reviewer checked both findings against the current documentation and the named implementation. This is a comparison of meaning, not a complete audit of whether every pre-existing statement matches the code.

A structural comparison confirmed identical headings, 17 changed sections and 27 unchanged sections. Structure and preserved identifiers alone do not establish preserved meaning.

## Findings

1. **Low — the decisions lead implies a review of every decision.** `docs/chain.md:90` says: “a second, cold auditor judges each decision: only `upheld` releases.” The preceding paragraph did not introduce this unrestricted summary. The detailed bullets retain conditions selecting the decisions that need review. `labkit/gates/decision_review.py:183` (`reviewable`) likewise selects specific cases; it does not select every decision. A reader relying on the lead could infer an unnecessary audit requirement. Suggested replacement: “A limit states its effect. The cases below specify which decisions require a second, cold auditor and when an `upheld` review releases them.”
2. **Low — the recomputation lead names only output files.** `docs/chain.md:534` says: “The reported number is recomputed from output files pinned to the run, with the code the run ran.” The same section explicitly supports recomputation from recorded inputs (`docs/chain.md:543`, `labkit/checks/recheck.py:1046`, `holds_from_inputs`). The old paragraph included that alternative without imposing this new introductory restriction. Suggested replacement: “The reported number is recomputed with the code the run ran, from its recorded output files or recorded inputs, as specified below.”

Neither finding removes the correct conditions from the detailed bullets. Both make the introductory sentence less accurate than those bullets. The proposed replacements have not been applied.

## Coverage

All changed sections were compared:

- `run → report (meaning)`
- `run → report (the decisions)`
- `run → report (the follow-up)`
- `run → report (a discussed run, the registered report)`
- `run → report (model)`
- `run → report (input origins)`
- `run → report (the report a protocol owes)`
- `run → report (what the number is about, as first measured)`
- `run → report (a declared replacement)`
- `run → report (the end)`
- `run → report (the declaration)`
- `run → report (a report outside the protocol)`
- `run → report (the gates that run unasked: the stop sends back once, the commit holds)`
- `audit → evidence (the attempts)`
- `report → number`
- `kind → kept number`
- `compute → reference comparison`

The four history fragments in `docs/notes/2026-11-26-chain-history.md` preserve the original wording. The `meaning` lead retains “pilot, no gate yet”; whether that older qualifier still describes current behaviour was not established by this review.

## Retained ambiguities and limits

The six passages deliberately left ambiguous remain at current `docs/chain.md` lines 80, 145, 332, 498, 514 and 570. They concern diagnostic syntax, the report state at commit, an orphaned reporting duty, changed committed evidence, the branch journal copy and which kinds reject a reference comparison. Preserving them avoids choosing a new interpretation, but does not resolve their meaning. They remain separate documentation work, not six newly introduced defects.

No runtime code, schema, prompt or reviewed chain text changed. No model call or experiment ran. Tests were not rerun for the comparison; the earlier full-suite result reported for the rewrite is not evidence for this semantic review.
