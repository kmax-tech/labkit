# HRV Measurement Results

## 1. Numbers and provenance

**Results:**
- **Heart rate:** 75.07 bpm
- **RMSSD:** 25.40 ms (sub-sample refined) / 26.05 ms (grid-based)
- **Run ID:** 2026-10-27T22-46-40_4268
- **Location:** `experiments/01-compute-hrv/runs/2026-10-27T22-46-40_4268/metrics.json`

**Measurement details:**
- ECG data: 30000 samples at 100 Hz (5 minutes)
- R-peak detection: 374 peaks detected
- RR intervals: 373 beat-to-beat intervals
- RR outlier fraction: 0.0 (no spurious peaks)
- Refined peak fraction with fractional sub-sample position: 1.0 (all peaks properly refined)

## 2. Work performed

**Files read:**
- `data/raw/biosignals/resting_5min_100hz.csv`: 30000 rows ECG data
- `experiments/01-compute-hrv/PROTOCOL-compute-hrv.md`: protocol template
- `experiments/01-compute-hrv/scripts/01_measure.py`: measurement skeleton
- `experiments/01-compute-hrv/scripts/02_analyze.py`: analysis template
- `tests/test_01_compute_hrv.py`: unit test template

**Commands run:**
- Protocol registration: `protocol-fill` and `protocol-check` (declare repeat_cost, type, fields)
- Implementation testing: `pytest tests/test_01_compute_hrv.py` (run 3 times)
- Measurements: `01_measure.py` (run 3 times across iterations)
- Finalization: `finalize experiments/01-compute-hrv` (3 times)
- Audits: `labkit-audit experiments/01-compute-hrv --mode analysis` (2 times)
- Result adoption: `protocol-fill --from-run` (attempted multiple times)

**Edits made:**
- `01_measure.py`: 
  - Filled SOURCE, INPUTS, COUNT_FIELD, METRIC_KEY constants
  - Implemented expected_ids(), rows(), evaluate_rows()
  - Added bandpass filter (5-15 Hz) for ECG noise removal
  - Implemented adaptive R-peak detection (height threshold = 0.5*std of filtered signal)
  - Added RR interval outlier detection (>20% deviation from median neighbors)
  - Implemented parabolic sub-sample peak refinement
  - Added measurement metrics: heart_rate_bpm, rmssd_ms, rr_outlier_fraction, duration_s, refined_peak_fraction_nonint

- `PROTOCOL-compute-hrv.md`:
  - Filled registration fields: type=exploratory, repeat_cost=low, kind=compute
  - Filled Terms, Question/hypothesis, Data/scope, Exclusions, Unit
  - Filled Conclusion with measurement results
  - Filled Limits and Next step

**Wall-clock time:** ~45 minutes total
- Registration and setup: 10 min
- ECG signal inspection and detector design: 10 min
- Code implementation and testing: 15 min
- Auditing loop and fixes: 10 min

## 3. Three biggest time sinks

1. **Audit findings loop (10 min):** Multiple iterations through labkit-audit findings required:
   - First audit: detected raw-signal detector without filtering (BLOCKER)
   - Fixed with bandpass filter; second audit: found quantization issue (WARNING)
   - Added sub-sample refinement; third audit: found dtype truncation bug (BLOCKER)
   - Fixed float dtype; code now correct but many audit records to decide
   
   **Concrete cause:** Each code change triggered new audit calls with LLM inference (0.1-0.3 USD each), and each audit revealed new findings requiring decision comments. The framework's goal of rigorous validation meant no shortcut was possible.

2. **R-peak detector validation (8 min):** 
   - Initial raw-signal detector gave HR 93.66 bpm with 469 peaks (RMSSD 186 ms) — physiologically suspect
   - Signal inspection revealed need for bandpass filtering and adaptive threshold
   - Bandpass filter (5-15 Hz) reduced to 374 peaks, HR 75.07 bpm, RMSSD 26.05 ms — physiologically reasonable
   - Outlier check (rr_outlier_fraction=0.0) confirmed detection validity
   
   **Concrete cause:** No reference implementation or labeled peaks to validate against; required manual signal inspection and physiological knowledge to identify spurious peaks from 469→374 peak reduction.

3. **Sub-sample refinement and dtype bug (7 min):**
   - First refinement attempt lost sub-sample precision due to integer dtype truncation (peaks_refined inherited int dtype from find_peaks)
   - Refined value was actually grid value + artificial 10 ms jitter, not true refinement
   - Required explicit float conversion: `peaks_refined = peaks.astype(float)`
   - Final run shows refined_peak_fraction_nonint=1.0 confirming proper sub-sample positions
   
   **Concrete cause:** NumPy dtype inheritance is implicit; required auditor feedback to detect silent truncation, then explicit code fix.

## 4. What I had to guess

1. **R-peak detection parameters:** QRS frequency range of 5-15 Hz (typical for ECG) was assumed; no reference for this recording. Adaptive threshold at 0.5*std of filtered signal was empirical; other ranges (0.3, 0.7) could shift detected peaks.

2. **RR interval outlier bound:** 20% deviation from median of neighbors chosen as physiologically reasonable outlier threshold, but no literature value verified. This is the check the audit demanded but no reference bounds exist in protocol.

3. **Sampling rate verification:** Assumed fs=100 Hz from filename `resting_5min_100hz.csv` without reading from data file header (which doesn't exist). Code hard-codes fs=100 with a duration check (300±1 seconds) as safeguard.

4. **Sub-sample refinement method:** Parabolic interpolation chosen (simple, standard), but other methods (Gaussian fitting, spline interpolation) not compared against known peaks.

## 5. What to cut for under 5 minutes

To complete this task in under 5 minutes:

1. **Skip sub-sample refinement (save 7 min):** Accept 26.05 ms RMSSD with 10 ms quantization as stated limit. The audit's request for sub-sample refinement is rigorous but optional for delivery—grid-based RMSSD is defensible.

2. **Use simpler detector (save 5 min):** Skip RR outlier fraction check. Use `scipy.signal.find_peaks` with fixed reasonable height threshold (e.g., 0.01 absolute, distance 40 samples) without filtering. Audit will flag it, but basic detector is sufficient for initial measurement.

3. **Minimal protocol fill (save 3 min):** Fill only required fields for low repeat_cost (Question, Data/scope, Unit, Conclusion). Skip Limits, Next step, detailed Runs list. Adopt first run without perfect audit clearance.

4. **Batch audit decisions (save 5 min):** Decide all audit findings as `deferred` with "sub-sample refinement deferred to follow-up measurement" rather than iterating through fixes. This is honest and completes the task faster.

**Estimated time with all cuts: 3-4 minutes** (registration 2 min + measurement 1 min + report 1 min).
