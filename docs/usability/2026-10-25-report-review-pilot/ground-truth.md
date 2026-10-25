# Report review pilot — ground truth, fixed before the first call (2026-10-25)

Model: opus (claude-cli, claude-opus-5-5), two draws per case. Command:
`labkit-audit experiments/<area> --report-review REPORT.md --out draw-<k>.txt`, cwd = the case.

| case | kind | must catch (≥1 claim on) | gray (counted apart) | false alarm |
|---|---|---|---|---|
| t18-delivered | positive | 56 (C1 PASS vs C1 not assessable), 57, 58 | 12–21, 36–40, 72 (search scores outside the marked run) | any other line |
| t3-delivered | positive | 12, 13, 20, 21 (R² of the marked run as performance) | 14, 52, 56, 57 | any other line |
| t18-honest | negative | — | 38–42 (search table, labelled not a result in the line above) | any other line |
| t18-why-numbers | negative (numbers inside the why) | — | 38–42 | any other line, line 62 (the mark) included |
| t3-honest | negative | — | — | any line |

Caught: a positive case with ≥1 claim on a must-catch line. Catch rate:
caught draws / positive draws. False-alarm rate: negative draws with ≥1
false-alarm claim / negative draws. Cost: `tokens · …` line per draw.

## Round 2 (added after round 1, before its calls)

Round 1's negatives were not clean: the reviewer's claims pointed at
result sentences my rewrite had left (t18 lines 78, 80, 86; t3 headings
19, 28, 62, and "feature provenance" listed as a BLOCKER where the record
grades it WARNING #6). Those lines were rewritten — guided by the
reviewer's own pointers, so round 2 on these cases leans its way. Two
reports written fresh, without its pointers, are added: t18-minimal and
t3-minimal (mark with a why, no result, open steps).

| case | false alarm |
|---|---|
| t18-honest, t18-why-numbers, t3-honest (rewritten) | any claim except gray 38–42 on the t18 ones |
| t18-minimal, t3-minimal | any claim |
