# Precision of the unsourced-number hint, seventh haiku round (e9f088f)

> Verdict: 12 of 54 flagged lines hold a wrong number (22 %; 27 % of the
> 44 lines that carry a result). Every report has wrong lines and flagged
> correct ones alike, so the hint does not tell a wrong report from a
> right one; as a blocker it would hold 32 correct lines and 10 lines with
> no result. It stays a hint. Open point 5 of
> [the round's report](2026-10-25-sandbox-e9f088f.md).
>
> Counted by a subagent against the attempts' data and run files,
> read-only; t18's class counts re-checked by hand (174/226 and 434/226
> from `dili_v1.jsonl`, the report says 209/191 and 354/306).


Base: A = /Users/max/projects/labkit-paper-r7/experiments/09-agent-solves-sab-better-with-labkit/output/attempts_pilot_haiku_v7
Dataset copies checked against the attempts' frozen hashes (runs.tsv sha256 prefixes match):
/Users/max/projects/agentic-science-datasets/benchmark/datasets/{crystalline_compound,dkpes,dili}
(the attempts' own work/benchmark/datasets/ is empty after delivery).
Line categories: wrong = >=1 wrong number; correct = no wrong number, >=1 correct result; NaR-only = only "not a result".

## t3 (A/t3-labkit-r1/work/REPORT.md), E = .../work/experiments/01-bulk-modulus-prediction

| line | numbers | verdict | evidence |
|---|---|---|---|
| 12 | -0.064 | correct | E/runs/2026-10-25T20-18-03_3b26/metrics.json c1_score -0.06404 |
| 13 | -0.281 | correct | same file, a2_score -0.28136 |
| 14 | 232 | correct | same file, n_test 232; pred_results/compound_bulk_modulus.csv 232 data rows |
| 20 | -0.064 | correct | as line 12 |
| 21 | -0.281 | correct | as line 13 |
| 25 | 230 | not a result (space-group range 1-230, domain constant) | - |
| 56 | 944; 19,365 | 944 correct; 19,365 wrong (dataset has 944 records; 19,365 = physical lines minus header, and the task text does not mention it) | csv.DictReader count, scratchpad/t3_rows.py; wc -l train.csv = 19366 |
| 57 | 232; 4,680 | 232 correct; 4,680 wrong (232 records; 4,680 = lines minus header) | same; wc -l test.csv = 4681 |
| 58 | 944; 232 | correct | as above |

t3: 9 flagged; wrong 2; correct 6; NaR-only 1; unverifiable 0.
Uncertain: 19,365 / 4,680 could be read as "a count from the task text" -- but the instruction (A/t3-labkit-r1/instruction.md) has no such number, and they are not the record count. Judged wrong.

## t5 (A/t5-labkit-r1/work/REPORT.md), E = .../work/experiments/01-dkpes; data dir digest 40f740d57268bd9b matches runs.tsv

Facts recomputed (scratchpad/t5_check.py): train 44 rows, test 12; median 0.284, min 0.0, max 0.904; 24 numeric feature columns (excl. index, Signal-inhibition, ShapeQuery); all test labels -999. Code: E/scripts/01_measure.py:93 (median), :96 (class 1 = signal >= threshold), :100 (100 trees, random_state 42). Run 2026-10-25T20-35-40_50e8 metrics n_predictions 12.

| line | numbers | verdict | evidence |
|---|---|---|---|
| 5 | 29; 12 | 29 wrong (44); 12 correct | t5_check.py; metrics.json |
| 17 | 29; 12 | 29 wrong (44); 12 correct | same |
| 18 | 25 | wrong (24 features) | t5_check.py |
| 19 | 0.465 | wrong (0.284) | t5_check.py |
| 27 | 29; 0.24; 0.793 | all wrong (44; 0.0; 0.904) | t5_check.py |
| 29 | 0.465 | wrong (0.284) | t5_check.py |
| 30 | 12; -999 | 12 correct; -999 not a result (sentinel) | dataset test.csv |
| 31 | -999 | not a result | - |
| 37 | 100; 42 | not a result (parameters; match 01_measure.py:100) | - |
| 38 | 25 | wrong (24) | t5_check.py |
| 39 | 0.465; 0.465 | both wrong (0.284) | t5_check.py |
| 43 | 12 | correct | metrics.json n_predictions 12 |
| 49 | 12 | correct | pred_results/dkpes_test_pred.csv 12 rows |
| 53 | -999 | not a result | - |
| 56 | 12; 12 | correct | metrics.json |
| 64 | 12 | correct | csv |
| 68 | 12 | correct | csv |
| 76 | -999 | not a result | - |
| 77 | 12 | correct | metrics.json |
| 80 | 12 | correct | csv |

t5: 20 flagged; wrong 8; correct 8; NaR-only 4; unverifiable 0.
Not flagged but wrong: line 44-45 "6 / 6" (csv has 7 class 0, 5 class 1); lines 20-21 and 39 invert the class coding (code: class 1 = signal >= threshold).

## t18 (A/t18-labkit-r1/work/REPORT.md), E = .../work/experiments/01-dili; train/test sha prefixes 587b5127bb8cf5f5 / c0367d7d80dbcbeb match

Facts recomputed from E/data/prepared/dili_v1.jsonl (scratchpad/t18_check.py): groups by position MC 173, LC 260, NC 227, sider 263; MCNC 400 (174 DILI / 226 NoDILI), MCLCNC 660 (434 / 226), all 923 (434 / 489); test 55; fingerprint 2048 bits. Grid-search results exist only as printed stdout in A/t18-labkit-r1/out/trace.jsonl (lines 2412, 2839): MCNC 0.8214 {200, 30, 2, 1}, MCLCNC 0.7856 {200, 30, 2, 2}, all 0.7500 {200, 30, 5, 2}. Labkit run 2026-10-25T20-57-42_9ae7: c1_score 0.7795, c1_threshold 0.75, a2_score 0.4855, a2_chance 0.5, null_band 0.1, n_items 923, n_test 55.

| line | numbers | verdict | evidence |
|---|---|---|---|
| 11 | 173; 434; 660 | not a result (row ranges from the task text) | instruction.md |
| 12 | 400; 209; 191 | 400 correct; 209 wrong (174); 191 wrong (226) | t18_check.py |
| 13 | 0.8214 | correct | trace.jsonl:2412 |
| 15 | 174; 433 | not a result (task range) | instruction.md |
| 16 | 660; 354; 306 | 660 correct; 354 wrong (434); 306 wrong (226) | t18_check.py |
| 17 | 0.7856 | correct | trace.jsonl:2412 |
| 19 | 661; 923 | not a result (task range) | instruction.md |
| 20 | 923; 434; 489 | correct | t18_check.py |
| 21 | 0.7500 | correct | trace.jsonl:2412 |
| 27 | 50,100,200,10,20,30,10 | not a result (search grid; E/scripts/01_measure.py:341-344) | - |
| 30 | 55 | correct | metrics.json n_test 55 |
| 38 | 200; 30; 0.8214 | correct | trace.jsonl:2412 |
| 39 | 200; 30; 0.7856 | correct | trace.jsonl:2412 |
| 40 | 200; 30; 0.7500 | correct | trace.jsonl:2412 |
| 45 | 55 | correct | pred_results/MCNC_RF.csv 55 data rows |
| 46 | 55 | correct | MCLCNC_RF.csv 55 |
| 47 | 55 | correct | all_RF.csv 55 |
| 55 | 923 | correct | metrics.json n_items |
| 56 | 0.7795; 0.75 | 0.7795 correct; 0.75 not a result (criterion constant, = c1_threshold) | runs/2026-10-25T20-57-42_9ae7/metrics.json |
| 58 | 0.4855; 0.5; 0.1 | 0.4855 correct; 0.5, 0.1 not a result (chance, null_band) | same; runs.tsv config |
| 64 | 923 | correct | metrics.json |
| 68 | 2048 | not a result (fingerprint size; 00_prepare.py:86) | - |
| 72 | 0.8214 | correct | trace.jsonl:2412 |
| 76 | 200; 30 | correct (best params) | trace.jsonl:2412 |
| 78 | 55 | correct | csv |

t18: 25 flagged; wrong 2; correct 18; NaR-only 5; unverifiable 0.
Caveat: the grid-search numbers are verified against the attempt's printed stdout in the trace, not against a kept file, and were not recomputed.

## Totals

| attempt | flagged lines | >=1 wrong | correct | NaR-only | unverifiable |
|---|---|---|---|---|---|
| t3 | 9 | 2 | 6 | 1 | 0 |
| t5 | 20 | 8 | 8 | 4 | 0 |
| t18 | 25 | 2 | 18 | 5 | 0 |
| all | 54 | 12 | 32 | 10 | 0 |

Precision of the hint as "this line holds a wrong number": 12/54 = 22% of flagged lines; 12/44 = 27% of flagged lines that carry a result.
Wrong numbers (not lines): t3 2, t5 11, t18 4 = 17.
