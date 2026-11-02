# Plan to simplify the labkit workflow

2026-11-02. Requested by Max. This is the work plan; current rules belong
in the standard and [workflow](../workflow.md). Proposals below do not
change those rules. B and repair A1 are implemented; C is undecided.

## Goal and evidence

Correct work should reach a useful report with fewer repeated steps,
without weakening the scientific standard.

In area 17, six of 18 labkit attempts reached the 2400-second limit;
none of 18 controls did. Five of the six left no report. However, four
shared a proxy outage and lost about 16 minutes each to retries. No control
ran during that window. The timeout contrast is confounded and must not be
presented as the effect of labkit alone.

The two t34 attempts had no such outage. Seven follow-up audits after prose
edits cost about 20 minutes together. The unchanged numbers do not show
that these audits were useless: one found a missing reference. Finding the
successor-registration route cost about 18 minutes across those attempts.
Repeated calculations took seconds; no expensive acquisition was repeated.
Sources and limits are in the appendix.

## Work packages

| Package | Change | Status and next action |
|---|---|---|
| **B — report before adoption** | Save a readable intermediate report before the audit loop. Replace its discussion block on adoption. | Implemented. Joint verification with A1 passes; see acceptance cases below. An agent comparison is needed before claiming time saved. |
| **A — consistent repair guidance** | Make the decision hint, next action and release gate agree about changed evidence. | A1 implemented in `200c6ebb`, with example helpers in `4dbf203c`. The correction route is described below. No general relaxation of code binding. |
| **C — review the second-review duty** | Remove or narrow the general second-auditor duty for a BLOCKER accepted as a limitation with `stands`. | A concrete removal hypothesis, requiring a separate policy decision and protection comparison. B keeps today's rule. |

B's prerequisites are implemented: shared measurement check (`7c70615f`),
report setter (`410507cc`), historical reader (`82a372a5`) and report binding
(`c413182d`). Block replacement is in `c68e0b0b`, next-step and commit handling
in `4a664163`, workflow additions in `82dfa297`.

Field-address guidance is implemented in `e0837d48`: malformed addresses name the
existing command syntax; no new input format was added. Its evidence is in
the appendix. The remaining proposals below are separate work, not extra
prerequisites for B. The evaluation order remains area 17, then area 18;
this plan authorizes no new agent round.

## B: agreed behaviour

### Register the report before measuring

Registration is one step for `compute`, `fit` and `apply`. Choose the kind
by what the number asserts. Use
[`standard_contract.registration_fields(kind, model)` and `skeleton(...)`](../../labkit/formats/standard_contract.py)
as the existing source, displayed by `protocol-check PROTOCOL --contract`.
Do not copy its field lists into another contract.

`compute` calculates a quantity; `fit` evaluates a predictor trained or
adjusted in the experiment; `apply` evaluates an unchanged predictor. Lack
of a requested threshold does not automatically make prediction evaluation
a computation. Task 60's fixed-predictor comparison remains an unresolved
boundary; redesigning it is not scheduled before B.

When a task requires a report, create the area with `--report-file REPORT.md`,
or use `protocol-fill PROTOCOL report=REPORT.md` before the first measurement.
The option already existed; agent guidance now points to it. None of the
18 area-17 protocols registered a report, so B would not apply to those
historical states without this setup change.

Before measurement, replacing the path requires `--force` (E2). At `low`,
the first measurement requires it to be committed. Removing or redirecting
the bound path then blocks: restore it, or hand over and explicitly register
a successor protocol (E1). Earlier evidence remains. New registration is
not the normal repair for faulty code.

Scope: report registered before measurement, `low`, bound through the
committed first measurement. `high` and late registration remain outside
this change. Moving a protocol to `high` leaves this binding and requires
freeze and preflight audit; no broader protection is claimed here.

Known count-skeleton and absolute/relative-threshold defects follow the
existing template repair order. Test B on a valid baseline; do not attribute
a template failure to B or require a general template redesign first.

### Save progress, then continue the checks

After a completed measurement and before the audit blockers, `labkit-next`
asks for an intermediate report using the existing command:

```sh
protocol-fill PROTOCOL --discuss RUN --why "what was measured; what remains open" --into REPORT.md
```

The report should explain the question, method, completed work and open
issues. Its discussion block names the current answering run. It explicitly
releases no result. Once it exists, `labkit-next` names the remaining work;
it does not return `nothing` because progress was saved.

The commit accepts this intermediate form. The stop reminds once to adopt
or hand over. Other applicable blockers remain: the account does not waive
an undecided audit BLOCKER, changed run evidence or malformed references.

No additional model review is required before the audit loop. For this
registered report, final review remains due after its result or handover
block exists. Progress prose can therefore be wrong and is unreviewed.
The final review reads the final report, including any remaining prose;
it does not read previous Git versions automatically.

Adoption replaces the matching discussion block in place with the result
block. Other protocols' blocks, other runs' discussions and surrounding
prose remain. The final report is held until its required review passes.
A valid negative result follows the same path.

### Where the existing workflow changes

| Step in [the workflow](../workflow.md#the-steps-at-a-glance) | Implemented B behaviour |
|---|---|
| 0–2: create and register | Guide a required report to its registration before measurement. |
| 3: measure | Write progress before entering the audit loop. |
| 4–6: check, audit, decide and review | Preserve release requirements. Describe pending work in the report. |
| 7–8: adopt and report | Replace the matching discussion in place; review the final text. |
| 9: stop and commit | Accept progress at commit, remind once at stop; release no result. |

Use existing writers, report checks and next-step logic. Each command checks
its conditions again; earlier advice is not permission or execution evidence.
A1 adds its correction route to steps 4–5 and recovery; C would change step 6
only after a separate decision.

## Acceptance and verification

| B case | Required outcome | Executable coverage |
|---|---|---|
| Save progress | Current-run discussion passes staged commit; stop reminds once; no adoption or extra model review. | `tests/test_next_step.py::ProgressAccount`, registered-report pairs in `tests/test_report_check.py`. |
| Survive interruption | Interrupted audit leaves a readable report and a valid next action, without a success claim. | `ProgressAccount` and `tests/test_attempts.py`. |
| Retain protection | Open blockers, altered evidence, stale references and malformed blocks retain their applicable holds. | `ProgressAccount`, `tests/test_report_check.py`, `tests/test_registration_committed.py`. |
| Finish cleanly | Matching discussion is replaced, unrelated content remains, final review is due; negative results work too. | `tests/test_report_blocks.py::AdoptionReplacesTheAccount`, `tests/test_report_review.py`, `tests/test_counter_cases.py::HonestMiss`. |

The combined local probe used a registered count protocol and real commands:
measure → save discussion → accept staged progress → correct a misdescribed
document count → decide `fixed` → refuse adoption after a fresh audit without
a verdict → obtain explicit `resolved` → adopt → review the final report →
pass the staged check. Progress remained during the refused adoption; adoption
replaced it and still owed report review. A separate registered-report
probe also completed this path with a missed prediction criterion: the
negative result remained a miss and passed final review and the staged gate.

Model responses were fixtures. This checks binding and command flow, not
scientific judgement. The focused regression selection covers next-step,
report-block, registration, repair-path, end-to-end, counter-case, executable
workflow and field-command tests. Required repository checks also run before
commit. The historical [injection benchmark](../usability/2026-10-29-injection-ab4ce6d.md)
remains the protection regression set; local tests are not a new replay of
that historical benchmark. A replay needs valid current baselines and a
finding about the intended fault, not just a nonzero exit.

- [x] Implement B's prerequisites, progress path and block replacement.
- [x] Map the four acceptance cases and exercise B together with A1.
- [x] Required repository checks passed on the combined code, including
  ruff, format, pyright and the full suite (`e0837d48`). The documentation
  commit repeats these checks through the hook.
- [ ] Before claiming work saved, compare agent behaviour under a controlled
  setup that distinguishes infrastructure failures from labkit costs.

## A: repair guidance

The probe on `82dfa297` found a real bypass: changing Unit or Terms and
re-auditing the first run allowed adoption, while measuring again reached
the registration hold. The decision hint recommended that unsuccessful
second path. A1 compares the current protocol as well as run snapshots
with the first registration and shares the comparison with repair guidance.

A setup description can be corrected in place only through a finding that
names the full field label, a `fixed` decision and the follow-up audit's
explicit `resolved` for this state. A fresh audit alone releases nothing,
including for WARNINGs. The binding is mechanical; whether it still describes
the same experiment is auditor judgement. No special exception by field name
is needed. The [A1 note](2026-11-02-registered-field-repair.md) owns the detailed
contract, limits and tests.

Keep the repair paths distinct:

- Faulty implementation: repair, repeat the affected measurement and checks,
  obtain the required follow-up evidence.
- Description of the same run: the field-bound correction route can release
  the unchanged run; measuring again under changed registration remains held.
- Conclusion alone: no new measurement or analysis audit solely for that edit;
  required decision and report reviews remain.
- Changed scientific choice: restore it or explicitly register a successor.
  The threshold probe found existing promise and registration checks already
  hold a moved bar; this is not a prose-correction exception.

`--withdraw` removes adoption and result blocks; it does not restore files
or delete runs. A commit is a checkpoint, not proof of repair. Do not decide
`limitation` automatically: the author must assess the remaining claim.
The six-timeout evidence supports no general relaxation of code comparison
or new derived-run feature; expensive remeasurement was not the cost there.

## C: a concrete removal hypothesis

An accepted BLOCKER limitation with `stands` need not always require a
second auditor. Compare removing that general duty with a narrower duty;
retain findings, reasons and declared limitations. The risk is accepting a
limitation that no longer supports the claim.

The replay's 13 of 15 stable judgements establish repeatability, not added
error detection. Test known faulty and correct decisions, including rejected
choices closed or redrawn until they pass, before deciding what protection
can be removed. C remains separate from B and A1.

## Follow-up work, not prerequisites

### Check the scientific coverage

Use the existing sources: standard for the obligation, architecture's
[chain table](../architecture.md#the-chain) for checks and tiers, workflow for
actions, tests for observable behaviour. Add only these decision fields to
the chain review: prevented error and evidence; cost on correct work; keep,
move, merge, warn or remove. Do not create a second check map.

For each applicable requirement, record what must hold, when it applies,
evidence read, exact scope and limits of the check, consequence, valid
recovery and faulty/correct/repaired cases. Checks about the same fact must
share the comparison; partial comparisons must not claim the whole state
is unchanged. Exercise the recommended recovery through the next gate.

| Scientific requirement | Evidence needed |
|---|---|
| Question and method fit | Scientific review. |
| Suitable data, splits and controls | Encodable checks plus suitability and leakage review. |
| Correct metrics, units and denominators | Hand-checked examples and meaningful faults. |
| Appropriate randomness and uncertainty | Task-dependent design and analysis checks. |
| Traceable results | Registration, code, input, run and report binding. |
| Supported conclusion | Scientific review of the claim and its limits. |

A justified standard requirement and a meaningful counterexample can warrant
protection before an observed incident. Not every task needs every check.
Mark mechanical coverage, semantic review, gaps and scope limits explicitly.
Questions such as which tasks need a null comparison are proposals for the
standard, not answers established by this note. This review adds no blocker.

### Keep technical choices in one place

Use the protocol's existing TOML block for machine-readable declarations
and prose for reasons and interpretation. Render readable statements from
the authoritative declaration; code and checks should read it too. No new
file format or workflow engine is required. For the observed threshold
mismatch, consider an explicit absolute-versus-relative choice, for example:

```toml
# Proposal only, not current syntax.
[criterion]
metric = "accuracy"
comparison = "absolute"
operator = "at_least"
threshold = 0.95
```

Fit any eventual schema to the existing promise contract, with the normal
format-break policy. This does not fix an unsuitable skeleton by itself.

### Defer a broader history and test reorganization

`labkit-next` should explain the missing evidence, permitted action and
command from shared rules. A progress view can use existing records and
protocol requirements. Missing records do not distinguish skipped from
unneeded work; advice is not evidence of execution.

A broader command history would distinguish recommendation, start, success,
refusal and interruption. Its storage and protection need a separate design.
Local files do not provide an immutable history against an agent that can
rewrite every copy. B requires neither a history service nor stored status.

Do not create a coded stage table without identifying actual duplicate logic:
next-step and hooks already share `report_gaps`. Test coverage overlap alone
does not make function, gate and hook tests redundant. Test reorganization
comes after the behaviour is stable, not before B.

## Evidence appendix

- **Area 17:** labkit-paper `scores_attempts_c17.jsonl`, commit `48c8a2d`,
  summary `96c7f69c`; [TODO context](../../TODO.md#werkzeuge-und-standard).
  All 18 attempts called labkit. None registered a report. The separate
  tsts512 attempt changed its null band after failure and passed with
  warnings, without audit/adoption; this is not proof about all timeouts.
- **Timeout assessment:** labkit-evidence `72bf1b01`,
  `usability/2026-11-02-c17-timeouts/{assessment.md,rounds.tsv,outage.tsv}`.
  Four timeouts overlapped 502 errors at 06:28–06:40 UTC. Fourteen audits
  completed: five initial, one voluntary preflight, one repair-confirming,
  seven after prose edits. Peak-correction and split-finding correctness
  remain unverified. Raw traces and excerpts stay in the evidence repo.
- **Registered-field probe:** that evidence directory's
  `probe-registered-field/`, archived labkit `82dfa297`, real commands and
  stand-in audit records; A1's public repair note links its consequences.
- **Round 2:** [assessment](../../TODO.md#wo-die-vollendung-stirbt--auswertung-der-48-laborversuche-der-runde-2-2026-10-31-nachts):
  12/48 adopted, seven compliant and five not. Six unfinished cases had stale
  audits after code edits; four had `fixed` without required measurement
  and audit. Causes overlap. All 39 transcript-counted attempts called labkit.
- **Field addresses:** `process_attempts_c17.json`: 175 `protocol-fill`
  calls, 18 exit 2: ten wrong fields, seven already filled, one freeze edit,
  no shell-quoting errors. Two suggestions confused `criterion-1 sentence`
  with `Inference criterion`. `field_address_hint` now names the existing
  syntax before fuzzy suggestions. CLI tests follow the advice and check
  refused input leaves files unchanged. File input remains deferred; these
  small errors are not an established timeout driver.
- **Second review:** [replay](../usability/2026-10-22-decision-review-replay-v5.md),
  13/15 stable judgements across two runs; added error detection unmeasured.
