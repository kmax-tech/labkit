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
