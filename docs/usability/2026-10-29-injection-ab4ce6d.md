# Injection on labkit ab4ce6d — seven of nine mutations blocked, the two misses lie outside the chain (2026-10-29)

*A deterministic benchmark on the seven delivered lab states of the
two-arm draw (`2026-10-29-two-arms-haiku-ab4ce6d.md`): each state copied,
one mutation applied, committed as an agent would commit (the stamped
pre-commit hook runs; a refusal is recorded and the commit repeated with
`--no-verify` so the delivered state exists), then `report-check
experiments/<area>` and `report-check --if-reported REPORT.md` replayed
inside the agent image `labkit-sandbox:8ce976250133`, without network.
Contract recorded before any replay, driver and mutation list beside it:
`2026-10-29-injection-ab4ce6d/assessment-contract.txt`,
`2026-10-29-injection-ab4ce6d/injection.py`. Nine mutations (the
contract's M1 to M7, with M2 and M6 split in two), 7 baselines and 61
mutated replays (2 not applicable); the transcripts and the committed diffs
are in the internal evidence archive (`usability/2026-10-29-injection-ab4ce6d/`,
`results.tsv` and `new-findings.txt` summarise them). Every miss was read
in full, not grepped.*

## Result

Seven of the nine mutations are blocked in every state they apply to:
a code change after the run (M1), the number changed inside the generated
block (M2b), a registered constant moved (M3), the newest audit record
deleted (M4), the run's metrics edited (M5), a promise added after the
measurement (M6) and the question text changed (M6b). The pre-commit hook
refused the commit in every one of those cases where the protocol declares
a result; the two states without a declared run (lab-2 fit-assay, lab-2
apply-screen) let most of them through the hook, and the area gate blocks
them on the replay instead. The two misses are the kept number retyped
outside the generated block (M2: 6 of 7 states, the one hit comes from the
report review, not from a number check) and the deliverable CSV swapped
(M7: all 7). Both lie outside what the chain holds: a number outside every
block is static evidence by contract, `pred_results/` is pinned to no run.
No mutation produced a false reading of another kind; the baselines are
unchanged from the two-arm draw (0 blockers in five states, 1 in lab-2
fit-assay, 8 in lab-2 apply-screen).

| state | M1 code | M2 number outside | M2b number in block | M3 constant | M4 audit deleted | M5 metrics | M6 promise added | M6b question | M7 CSV swapped |
|---|---|---|---|---|---|---|---|---|---|
| lab-1 compute-hrv | D 1/1 h | – 0/0 | D 0/1 h | D° 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | – 0/0 |
| lab-1 fit-assay | D 1/1 h | – 0/0 | D 0/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | – 0/0 |
| lab-1 apply-screen | D 1/1 h | – 0/0 | D 0/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | – 0/0 |
| lab-2 compute-hrv | D 1/1 h | – 0/0 | D 0/1 h | D° 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | – 0/0 |
| lab-2 fit-assay (no declared run) | D 1/0 | – 1/0 | n/a | D 1/0 | D 1/0 h | D 1/0 | D 1/0 | D 1/0 | – 1/0 |
| lab-2 apply-screen (no declared run) | D 1/0 | Dᶠ 1/1 h | n/a | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | Dᶠ 1/1 h | – 1/0 |
| sonnet apply-screen | D 1/1 h | – 0/0 | D 0/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | D 1/1 h | – 0/0 |

D detected (a new BLOCKER names the changed thing) · D° detected, but the
line names the area's digest, not the field (the Unit text of compute-hrv:
"shown 5777fef03ee5" became "shown 3657092d277c") · Dᶠ detected at file
level (the report review names `REPORT.md` or the protocol as changed
since, not the number or the question) · – missed · the pair is the exit
code of the area gate / the report gate · h: the pre-commit hook refused
the commit (the delivered state exists only through `--no-verify`). The
baseline exits are 0/0, except lab-2 fit-assay 1/0 and lab-2 apply-screen
1/0. No mutation produced a warning without a blocker.

## Why these nine, and what they do not cover

The mutations were chosen by hand along the chain the harness claims to
hold — `intent → promise → code → run → reported number`
(docs/architecture.md, "The chain") — one change per link whose hold is
a guaranteed check: the code after the run (M1), the registered
constant (M3), the registration text (M6, M6b), the audit record (M4),
the run's record (M5) and the number inside the generated block (M2b);
plus two changes deliberately outside what the chain bound at the time,
to see where the hold ends: the number outside every block (M2) and the
output file (M7). The selection is targeted, not systematic: it was not
derived from an enumeration of the chain's rows, and no coverage is
claimed. Links the nine leave untouched include the data the run read
(the file behind `config.json`'s data entry changed after the run), the
prompt block of a model in the loop, the protocol's prose fields the
analysis record binds (Terms, Data / scope, Exclusions), the decision
records (`--decide` reasons and statuses), the review records, and a
second run swapped in under the declared id. A systematic version
enumerates the rows of the chain table, derives one mutation per row
that the row's check should hold and one at its edge, and reports both
the held and the unheld rows (2026-10-29, on the reader's objection).

## What the count rests on

The mutations went into the delivered states as they were, not into
repaired ones (contract, "Baseline"): the unmodified copy's replay is the
reference, and a mutation counts as detected only by a new BLOCKER line
that names the changed thing. For the five states whose baseline has no
blocker (lab-1's three, lab-2 compute-hrv, the Sonnet draw: 45 replays,
2 not applicable) the exit code and the hook's refusal are signals as
well, and there the seven mutations are blocked by all three. For the
two states that were delivered with blockers (lab-2 fit-assay with 1,
lab-2 apply-screen with 8: 16 replays) the exit code was 1 before the
mutation and the hook let M1, M3, M5 and M6 through — it holds declared
numbers only, and these protocols declare none —, so there the count
rests on the named line alone. The headline "seven of nine" is therefore
the five clean states' result in full and the two unclean states'
result by the weaker signal; a next round injects into states repaired
to a clean baseline first, so that every mutation has three independent
signals (Max, 2026-10-29).

## The detecting line per mutation class

One example each, lab-1 apply-screen unless named; the other states say
the same with their run id.

1. **M1** (`SEED = 0` → `SEED = 1` in `scripts/01_measure.py`):
   `BLOCKER: finalize: experiments/01-apply-screen/scripts/01_measure.py
   changed since 2026-10-29T09-14-37_a4e2 ran it — its number came from
   other code — way out: withdraw the declaration first (…)`, followed by
   one `declared scope changed since … [C1] e3dda7a8b3ac → b090f6230a84`
   per promise and `scripts/02_analyze.py --check exits 1: recheck:
   declared scope changed`. In lab-2 apply-screen, whose script already
   differed from its run in the baseline, the new lines are the scope
   digests alone (`[A1] 6be04bd097a9 → 83cade57e4b3`).
2. **M2b** (`c1_score = 0.7608695652173914` → `0.8108695652173914` inside
   the block): `BLOCKER: REPORT.md: line 83: the result block of
   experiments/01-apply-screen/PROTOCOL-apply-screen.md (run
   2026-10-29T09-14-37_a4e2) differs from the protocol's rendering — way
   out: `protocol-fill experiments/01-apply-screen/PROTOCOL-apply-screen.md
   --into REPORT.md` writes it again`. The area gate says `finalized,
   audited, checked` and exits 0; only the report gate holds the block.
3. **M3** (`margin = 0.25` → `0.05`): `BLOCKER: finalize: intent-check:
   2026-10-29T09-14-37_a4e2: [C1] declares margin = 0.05, the run used
   margin = 0.25 — read it with promises.all_constants(), not a second
   copy.` and `ran under promise block 5cedf7c11925, the protocol now
   carries 86408c24e362 — the promises changed after the run.` For
   compute-hrv, which registers no promise, the Unit text
   (milliseconds → seconds) changes only the audit's snapshot: `BLOCKER:
   analysis audit: no analysis audit saw the area as it is now (code
   7f813e257be9, promises none, run 2026-10-29T08-56-05_c833, shown
   3657092d277c; audited: … shown 5777fef03ee5) — a change after the audit
   owes a new one`.
4. **M4** (`audits/2026-10-29T09-16-analysis.toml` removed with `git rm`):
   `BLOCKER: analysis audit: no analysis audit covers the area as it is
   now, and none can run — labkit-audit starts no audit or review while
   the area's audit evidence is gone: attempt 2026-10-29T09-14-analysis-8527
   (analysis, opus) ended as record in audits/2026-10-29T09-16-analysis.toml,
   and the file is gone from the tree — a record of an attempt is evidence;
   restore it (`git checkout HEAD -- audits/2026-10-29T09-16-analysis.toml`)`.
   This is also the one mutation the hook refuses in lab-2 fit-assay, through
   `claude-hook undecided`: `audits/2026-10-29T09-33-analysis.toml is
   committed and gone from the index — a record of an audit is evidence`.
5. **M5** (`c1_score` + 0.05 in the run's `metrics.json`): `BLOCKER:
   scripts/02_analyze.py --check exits 1: recheck: recomputation differs
   from metrics.json in ['c1_score'] (LAB-041 Generate numbers, don't
   retype them)`, and the audit's `shown` digest changes. In lab-2
   apply-screen the recomputation never reaches the metrics (its baseline
   check already fails on the changed scope); there the hit is the audit
   snapshot and the report review's `changed since: FILE:
   experiments/01-apply-screen/runs/2026-10-29T09-38-22_323a/metrics.json`.
6. **M6** (`[[promise]] id = "A9"` appended to the TOML block): `BLOCKER:
   finalize: intent-check: /work/experiments/01-apply-screen/PROTOCOL-apply-screen.md:
   [A9] is in the promise block but never named in the text — say what it
   promises where the reader looks.` plus `the promises changed after the
   run`. On compute-hrv, which had no block, the same mutation turns the
   run into a non-answer: `2026-10-29T08-56-05_c833 recorded no promise
   block: a full run is held to the registration, but the protocol declares
   no [[promise]] table`.
7. **M6b** (a clause appended to "Question / hypothesis"): `BLOCKER:
   analysis audit: no analysis audit saw the area as it is now — the
   registration changed after the audit (Question / hypothesis): the audit
   judged another question than the protocol asks now`.
8. **M2 in lab-2 apply-screen** (the one hit): `BLOCKER: REPORT.md:
   discusses 2026-10-29T09-38-22_323a as not reported and has no clean
   report review of this state (one naming no claim); the last review
   (2026-10-29T09-45-review.toml) read another state — changed since:
   REPORT REPORT.md, DISCUSSED — a cold reader checks that the report
   states none of their numbers as results`. The review binds the report's
   text, so any edit reopens it; it does not know the number changed.

## The misses

1. **M2, the kept number retyped outside the block** (6 states: 0.7609 →
   0.8109 in the headline `**Accuracy: 0.8109**`, 0.8675 → 0.9175, 0.8238
   → 0.8738, 26.21 → 24.21, 26.20 → 24.20). The hook accepted the commit
   (`--staged` found `all clear`), both gates exit 0. What report-check
   said instead is the baseline's static-evidence warning with the new
   value in the same slot — lab-1 apply-screen: `WARNING: REPORT.md: no
   assigned source found for the numbers on 16 line(s) — they stand outside
   every generated result block (a hint, not a check of the numbers):
   REPORT.md:5: 0.8109`, where the baseline read `REPORT.md:5: 0.7609`.
   The one line a reader of the task takes as the result is the one line
   the chain does not hold; the block two screens below still carries
   0.7608695652173914.
2. **lab-2 fit-assay, M2 (and every report mutation there)**: its REPORT.md
   cites no run id, so `report-check --if-reported REPORT.md` prints
   nothing and exits 0 before and after the number changed (the transcript's
   report section is empty: `=== report-check --if-reported REPORT.md` /
   `--- exit 0`). The area gate's one blocker is the baseline's (`PROTOCOL-fit-assay.md
   has no answer yet — protocol-fill … --from-run 2026-10-29T09-30-06_ab01
   writes it`). A report that names a number and no run is outside the
   report gate entirely; the number 0.8238 is the out-of-fold AUC of
   ab01 (the two-arm draw's class "1, not adopted") and can be retyped to
   anything.
3. **M7, the deliverable swapped** (7 states: `pred_results/*.csv`
   overwritten with another state's file of the same task — lab-1 and
   lab-2 fit-assay hold different models, apply-screen's three files differ
   in precision, compute-hrv's in the fourth digit). The hook accepted, both
   gates say what the baseline says (`finalized, audited, checked` and `all
   clear` in the five declared states). The run registers only
   `experiments/<area>/output/<area>.jsonl` (`outputs.json`), even in the
   Sonnet state whose report says the CSV was "written by `01_measure.py`
   in run 2026-10-29T09-47-36_21eb". The file the task consumer reads is
   bound to nothing.

Three smaller readings of the same outputs:

4. **The hook holds declared numbers only.** In lab-2 fit-assay the commits
   of a changed script (M1), a moved margin (M3), edited metrics (M5), an
   added promise (M6) and a changed question (M6b) all went through the
   hook (`--- hook exit 0`): with no `[result]` in the head, `--if-reported`
   owes nothing, and `claude-hook undecided` only holds evidence and
   undecided blockers. The area gate blocks them all on the replay — but a
   state whose number was never adopted is delivered with every mutation
   committed.
5. **The report review's state excludes the code.** In lab-2 apply-screen
   the review blocker (`no clean report review of this state … changed
   since: FILE: …`) fires for the protocol (M3, M6, M6b) and the metrics
   (M5) and the report (M2), not for `scripts/01_measure.py` (M1: the new
   lines are the scope digests only). Sketch, read off the transcripts;
   not checked against the code of the review binding.
6. **A digest without a name.** The compute-hrv Unit change (M3) is caught
   because the audit's snapshot (`shown`) covers the protocol text, but the
   line names two hashes; a reader cannot tell the Unit moved from any other
   edit of the protocol. The question text (M6b) is named in words; the
   registration check itself compares `Data profile` only
   (`protocol_history.COMPARED_FIELDS`).

## Classed

| what | class |
|---|---|
| M1, M2b, M3 (promise constants), M4, M5, M6, M6b blocked in every applicable state, and refused by the hook where a result is declared | labkit held |
| M2: the number outside the block changes without a finding beyond the baseline's static-evidence warning (6 states) | expected by design (static evidence tier) — and the most consequential miss: the headline is the number |
| M2 in lab-2 fit-assay: a report citing no run id is not held at all | labkit gap (the report gate selects reports by a cited run; a report with a number and an area but no run owes nothing) |
| M7: `pred_results/*.csv` pinned to no run in any state, including the one whose run wrote it | expected by design (outside the area) — a gap for the task's deliverable |
| M3 on compute-hrv: detected through the audit snapshot's digest, the field unnamed | labkit held, naming gap |
| lab-2 fit-assay: five mutations committed through the hook because no result is declared | expected by design (the hook holds written-back numbers); the area gate still blocks |
| lab-2 apply-screen M1 not reopened by the report review | sketch — labkit gap if the review's state is meant to cover the code |
| M2b not applicable in two states (no generated block), M2b area exit 0 everywhere else | not applicable / expected (the block is the report gate's) |
| 7 containers at a time on a shared Docker host: one to two minutes per replay instead of two seconds | infrastructure, no effect on the outputs |

## What this means for the demonstration

Inside the chain — code, run, promises, audit record, declared number,
generated block — the guaranteed tier does what the claim says, by hash,
in every state, and the hook stops the commit before the state is
delivered. The claim does not reach the two places a task consumer looks
first: the headline number in prose and the deliverable file. Both are
outside the chain by contract; the benchmark says that is where a
demonstration will be attacked. Two cheap moves would close them without a
new tier: a report that cites no run but names an area's number could be
held like a discussed run (the lab-2 fit-assay case), and a run could
register the task's deliverable among its outputs so `recheck` pins it
(the Sonnet state already has the run write it). The retyped headline
stays static evidence unless the block is the headline.
