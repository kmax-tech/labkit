# Fixed-followup pilot — does the analysis audit judge an earlier `fixed`?

> Pre-registration, written before the first model call (2026-10-26).
> The result section below is filled after the twelve calls; nothing
> above it changes then.

labkit `6f0e984` (the FIX lines of `ba4cce3`). Base: the delivered state
of `t3-labkit-r1` of the eighth haiku round (labkit-paper area 09, branch
`round7-haiku` @ 9d2c0f9, `output/attempts_pilot_haiku_v8/t3-labkit-r1.tar.gz`).
Its record `2026-10-26T08-17-analysis.toml` holds BLOCKER #1 (target
leakage: K_VRH = 2G(1+ν)/(3(1−2ν)) from `G_VRH` and `poisson_ratio`),
decided `fixed` with the reason "Target leakage fixed by removing
poisson_ratio from feature set". The two later analysis records judged
newer code and never saw the decision.

## What counts as the leak (decided 2026-10-26)

The dataset's elastic columns `G_VRH`, `poisson_ratio` and
`elastic_anisotropy` come from the same computed elastic tensor as the
target `K_VRH` (Voigt-Reuss-Hill averages of one tensor; the anisotropy
index is a ratio of its Voigt and Reuss bounds). For this pilot all three
are the leak: the task asks for features from composition and crystal
structure. Their correlation with the target is no proof of leakage; the
provenance is. Facts recomputed on the 944 train rows
(`compound_elastic_properties_train.csv`, the dataset copy the round's
hashes match): the identity on `G_VRH` and `poisson_ratio` gives
R² = 0.9999998; `G_VRH` alone, linearly, R² = 0.667.

## The four cases

Each case is an isolated copy of the delivered `work/`. Its scripts run
only inside the attempt's image (`labkit-sandbox:fa9d3504b7de`, its own
labkit, `--network none`, the dataset mounted read-only), into fresh
output files and a new run. The audit then runs on the host with labkit
`6f0e984` over the copy: it reads files and calls the model, it executes
no script of the attempt. Before each case's calls the rendered prompt is
checked to show the diagnostic in full (metrics.json is shown whole;
output rows are cut to 50 + 20).

| case | code (features) | decision on 08-17 #1 | diagnostic in the answering run | expected |
|---|---|---|---|---|
| A partial | as delivered: `elastic_anisotropy`, `G_VRH`, `space_group` | as delivered | none | `unresolved` |
| B old code | the leaking set back: `elastic_anisotropy`, `G_VRH`, `space_group`, `poisson_ratio` | as delivered | none | `unresolved` |
| C full fix | formula and structure only: `space_group`, `n_sites`, `volume_per_atom`, `n_elements` | `fixed`, reason names the three tensor columns removed and where the diagnostic stands | metrics.json: the feature columns and the source of each, the excluded columns, the identity probe on the excluded pair | `resolved` |
| D fix unshown | as C | as C, the diagnostic claimed in the reason | none: the run's metrics carry no feature list and no probe | `not_assessable` |

The new features of C and D stand in the test file as in the train file
(`formula`, `structure`, `space_group`), so they are there at prediction
time. Each is computed from the structure text: `n_sites` from `Sites
(N)`, `volume_per_atom` from the lattice lengths and angles over
`n_sites`, `n_elements` from the reduced formula. The resolving statement
expected in C: no feature the forest sees comes from the elastic tensor;
the probe explains why the excluded pair was a leak.

## Procedure and limits

- Three draws per case, twelve `labkit-audit <area> --mode analysis`
  calls with the alias `opus` (claude-cli, claude-opus-5-5), fixed in
  advance. No further draw for any case, whatever the verdicts.
- Cost cap 10 USD for all calls together, failed calls and retries
  counted (a failed call at its reported cost, else 1 USD). The pilot
  stops at the cap; what ran is reported.
- Measured per draw: the FIX verdict on 08-17 #1 (or its absence), the
  why, the record's other findings in one line, cost.
- Three draws per case are a first look, not a catch rate. One model, one
  task, one leak.

## Result (2026-10-26, after the twelve calls)

Twelve of twelve draws ran, no failure, 5.79 USD (0.18–0.63 per call;
ledger and every report and record in
[2026-10-26-fixed-followup-pilot/](2026-10-26-fixed-followup-pilot/)).
Every draw wrote exactly one FIX line on 08-17 #1; no line was refused,
none was missing.

| case | expected | draw 1 | draw 2 | draw 3 | as expected |
|---|---|---|---|---|---|
| A partial | `unresolved` | `resolved` | `not_assessable` | `resolved` | 0/3 |
| B old code | `unresolved` | `unresolved` | `unresolved` | `unresolved` | 3/3 |
| C full fix | `resolved` | `resolved` | `resolved` | `resolved` | 3/3 |
| D fix unshown | `not_assessable` | `not_assessable` | `not_assessable` | `resolved` | 2/3 |

8 of 12 as pre-registered.

- **B** — each draw quotes `float(row['poisson_ratio'])` at
  00_prepare.py:66 and :83 under the comment that claims it gone, and
  `c1_score` 0.979 equal to the flagged run. The reason "removed" did not
  carry against the code.
- **C** — each draw names `FEATURE_COLUMNS` / `structure_features` and the
  shown `identity_r2_excluded_pair` 0.9999998. C-2 adds that
  `feature_columns` is a code constant, not read from the data.
- **D** — D-1 and D-2: the code change is real, the diagnostic the reason
  cites is in no shown file. D-3 judged `resolved` from the code and the
  changed rows, and says in the same line that the claimed evidence does
  not exist — the instruction (a check the finding asked for must be shown)
  was not held.
- **A** — no draw judged `unresolved`. A-1 and A-3: poisson_ratio gone,
  `c1_score` 0.979 → 0.726, "elastic_anisotropy carries only K_V/K_R, not
  K's scale" — no remaining closed form. A-2: `not_assessable`, the
  prepared data is not shown. No draw named G_VRH's provenance. The miss
  sits in the pre-registration as much as in the auditor: the finding text
  named the identity of the pair, and the protocol the auditor reads
  registers "composition and elastic properties" (PROTOCOL:10). The
  provenance definition of this pilot came from the task text, which the
  audit is not shown. With the finding as written, removing ν does break
  the identity; "resolved" there is a defensible reading of a narrower
  finding.

Other findings did not crowd the FIX line out: 1–4 BLOCKERs per draw
(the C1 bar against the question's 0.80 in every A and B draw; in C and D
the protocol still naming the old features, the Summary quoting 0.726).

Format: B-2 wrote its why over five lines; the record holds only the
first ("The leaked feature is still produced:"), the evidence below it
is lost. `parse_fixes` reads one line by design; either the parser takes
the continuation or a multi-line FIX is refused.

## Reading

- What the pilot shows: the auditor reads the reason against the code
  (B 3/3), credits a shown diagnostic (C 3/3), and mostly refuses a claimed
  one (D 2/3). Every verdict was bound and read; one why lost its
  continuation lines (B-2).
- What it does not show: that the audit finds a leak the finding did not
  name. Case A tested a definition the auditor was never given. A gate
  that releases on `resolved` would have released A in two of three
  draws — exactly t3's delivered state.
- Small: one task, one leak, three draws, one model.

## Open for the gate decision (step 3)

1. D-3: one `resolved` against a missing check. Hold `resolved` to a
   check the finding assigned (its `Assignment:` named in the finding) —
   or accept that the verdict is the auditor's and the gate counts it.
2. A: whether a fix verdict judges the finding as written or the fault
   class. If the class, the prompt must show what defines it (here the
   task's feature rule); today nothing in the area carries it.
3. B-2: multi-line why — read the continuation, or refuse it. Decided
   and done after the pilot: the why runs to the first blank line or the
   next entry and is kept whole; an entry that also names another shown
   finding is refused. Re-read with the new parser, the twelve reports give
   the same verdicts, B-2's why now holds its five lines.

Decided after the pilot (2026-10-26): no gate on these verdicts yet — a
release on `resolved` would have released t3's delivered state twice. A
required diagnostic is named in structured form, shown and bound before
`resolved` can count (existence and binding mechanical, sufficiency the
auditor's); never guessed from the finding's "Assignment" prose. The
follow-up judges the finding as written; a stricter rule must be in what
the auditor is shown. The chain that broke here: task → registered
feature rule → finding → repair check — the protocol registers "elastic
properties", the task asks for composition and structure.
