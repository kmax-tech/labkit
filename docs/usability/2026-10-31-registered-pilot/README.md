# Registered pilot: an analysis plan given, the agent implements (draft, 2026-10-31)

Round 2's lab attempts often failed at their own registration: an agent narrowed
or sharpened the task when it wrote the protocol (Rondônia "clipped to the state
boundary" with no boundary in the data) and was then held to it. labkit holds an
implementation to explicitly encoded intent; it does not write the intent.

This pilot gives every attempt a registration and asks: **can the agent
implement a given analysis plan correctly, with labkit and without?** The
registration is the task text plus the researcher's analysis plan. Methods,
null conditions, margins, the projection and tie rules are the researcher's
decisions, not the task's; each is marked "researcher's choice" or
"researcher's precision" where it stands. A missed criterion is a valid
result.

- `protocols/<task>.md` — the lab arm's protocol (the stage replaces
  `{protocol_id}` with the stamped id) for five tasks of round 1: 21, 34, 60
  (compute), 15 (fit), pubmedqa50 (apply with a model). Each carries the task
  verbatim in its own section, so the audit, which reads the protocol first,
  sees the full deliverable spec. Each passes `protocol-check` — that shows
  the form, not that the plan is sound.
- `plans/<task>.md` — the same content for the control arm as `PLAN.md`,
  without labkit's terms, written by `make_plans.py`; the two arms differ in
  labkit, not in what they are told about the task.
- `excluded/71.md` — not in this pilot: the estimator skeleton scores one
  value per item, and 71's target is 3,400 values per image. Supporting it
  is an extension of the skeleton; the pilot would measure implementation,
  usability and new framework function at once.

## The researcher's choices

1. 21: all supplied roads, the buffer not clipped at a state boundary; that
   every feature lies inside Rondônia is not checked. Areas in EPSG:32720
   (UTM 20S), chosen for its fit to the layers' extent.
2. 34: neurokit2 0.2.12 (the image's), `ecg_peaks` default method without
   artifact correction, `hrv()` at 100 Hz. An empty column only for an index
   `hrv()` returns no value for, with its reason in the report; a missing
   package or an exception is a failed run.
3. 60: registered as `compute` (fixed predictions, nothing of ours is judged).
   The MFA tie goes to the first response in CCOBRA's order and the rule
   application is spelled out — both precisions of the task's wording.
4. 15: Morgan fingerprints (radius 2, 2,048 bits) and
   `RandomForestClassifier(n_estimators=500, random_state=0)`, 3 folds and 2
   permuted-label refits per fold from the skeleton's plan, nothing tuned.
   Margin 0.25 without a source; null band 0.1 a generous plausibility limit.
5. pubmedqa50: the model template's lanes as stamped — a placebo null lane
   ("Is this passage written in English?") whose chance the template
   computes from its own answers (since the template repair of 2026-10-31;
   before, it sat at half the items, right for two balanced labels only),
   band 3 items, margin 0.25, the template's first-word parser in any case.

## Preparation evidence (not part of the registration)

- 21, the projection's effect, computed in the runtime image
  (`labkit-sandbox:286f86bb93f8`, geopandas 1.1.4) with the reference
  computation of buffer, dissolve and overlay: EPSG:32720 0.47491,
  EPSG:32723 0.47930, EPSG:5880 0.47546 — under 1 % apart; the benchmark's
  tolerance is 5 % relative. The extent of the roads: 60.1–66.8° W,
  8.0–13.7° S.
- 15, counted in the supplied files: train 5,093 rows (2,654 positive), val
  728 (450 positive).
- pubmedqa50, counted in train.json: yes 22, no 21, maybe 7.
- pubmedqa50, the model route, tried once apart from any attempt: labkit's
  `haiku` alias (backend `claude-cli`) called from inside the agent image
  through the proxy on the API key — one request
  (`req_011CgarZ4rjdELjRRdaiXhuv`), reply `yes` to the placebo, 0.008 USD;
  about 6,200 input tokens per call are the CLI's own system prompt. Script
  and output in the evidence archive (`labkit-evidence`, same folder name).

## The round

`assessment-contract.txt` registers it: part 0, a technical trial run (lab arm, 21 and pubmedqa50,
one attempt each, not counted), then part 1, five tasks × two arms × three attempts.
`run_pilot.py` runs both (copy it with pilot_checks.py, protocols/, plans/ and a models.toml into a run directory).
Open before part 0: the release with the template repair, and `sandbox/labkit.pin` set to its
commit hash.

## Runner checks (points 2 and 3 of the environment repair)

Every mode verifies the interpreter's installed `agentsandbox` commit from
`direct_url.json` against the full Git commit in
`labkit-paper-main/requirements.txt`, before building images. Missing metadata,
a directory or editable installation, and a mismatching commit stop the runner.
The package version alone is insufficient: the incompatible installations both
reported 0.1.0. A real pilot stores the checked commit, version and interpreter
in its batch provenance as `runner_environment`.

From the copied run directory, use the **same interpreter and settings** for
check and pilot; `--check` honors `--only`, `ARMS_ONLY` and `REPS` just as `--pilot` does:

```sh
ID_PREFIX=rpt ARMS_ONLY=labkit ~/projects/labkit-paper-main/.venv/bin/python run_pilot.py --check --only 21 pubmedqa50
```

`--check` builds the images, stages the selected task/arm repositories and
constructs every attempt, including its adapter command and environment. For
each distinct snapshot it copies the repository and inputs into a disposable
container and runs the actual setup line, then `protocol-check` for the lab
arm. These containers have no network. Setup Docker calls have a separate
120-second timeout; the attempt budgets are constructed and recorded, while
the setup containers use no attempt CPU or memory limits. The check starts no agent or proxy,
reads no API key and writes no attempt store. A setup or protocol failure
stops the check. The proxy image is inspected; proxy forwarding and model
responses still require the registered technical trial run.

After all checks pass, `check-<prefix>.json` and `check-<prefix>.txt` record the
installed commit, image tags and immutable IDs, CLI version, model, budgets,
constructed attempt IDs, tree digests and observed setup output (including
`one labkit`). The text is the evidence for the next addendum; the historical
contract is not rewritten automatically. Failed checks do not produce a new
success report; existing reports describe earlier checks only.

**Environment:** labkit-paper-main's `.venv` is its own (no longer a link to
labkit-paper's), built from `requirements.lock`, with agentsandbox pinned to
`db9b20c` (labkit-paper 6f8e27e); it passes the commit check. `.venv-pilot`, a
directory installation, is refused as intended. Part 0's first two attempts
ran from `.venv-pilot` on the same code (`db9b20c`, the directory's contents
then), recorded in the contract's addendum 3.
