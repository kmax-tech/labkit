# How the English standard was translated

`labkit/docs/standard.md` began as a machine translation of the German lab
standard. This page records how it was made, so that a reader can trace a
sentence of the English standard back to the German decision behind it. The
raw model outputs are not kept in the repo: they are not the origin of the
edited text, and git history would keep them forever.

## Source

| What | Value |
|---|---|
| Rule inventory (`docs/standard-cut.tsv`) | dotfiles blob `0888ec5` of `arbeitsstandard.md.template`, 102 ids, 95 package / 7 house |
| Translated text (`docs/standard-blocks.tsv`) | dotfiles blob `a28df38`, the same file after dotfiles `4405df7` moved the dated incidents into the evidence file |
| Blocks | 143 in all: 126 package (124 translated, 2 separators copied), 16 house, 1 generated register |
| Fixed terms | `docs/standard-terms.tsv` at labkit `4b8011b` (46 terms) |

## Method

1. **Rule names first.** One call translated all 102 rule titles, so that
   every block call received the same English name for each rule it cites.
2. **One call per block** (Sonnet, `claude-sonnet-5-5` via `claude -p`
   2.1.285, no tools, no settings) under a fixed contract (sha `556cc1485a83`
   at the final round):
   - keep normative strength (must / should / may / must not / never);
   - keep ids, code, paths and data verbatim; translate placeholders;
   - use the fixed terms;
   - add, drop or improve nothing.

   The chapter heading and the previous block were sent as context.
3. **Mechanical check per block.** Compared German and English for rule ids,
   alias marks, code spans, headings, table rows, fences and rule heads. Also
   caught model meta-text and German left in the prose.
4. **Review.** Opus (`claude-opus-5-5`) read every German block next to its
   English translation, with the terms and both manifests. It reported
   omissions, additions, meaning shifts, changes in normative strength,
   terminology drift and contradictions, and rewrote nothing.
5. **Repair, not rerun.** After round 2, only the blocks with findings went
   back to Sonnet, together with their German source, the earlier English and
   the findings. A full rerun only redraws the defects, because `claude -p`
   has no temperature control.

## Rounds

| Round | What ran | Findings (high / medium / low) |
|---|---|---|
| 1 | all blocks | 0 / 3 / 23 — mostly terminology drift from terms the list did not fix |
| 2 | all blocks again, 11 more fixed terms | 1 / 10 / 24 — model meta-text in one block, untranslated headings, "Stufe" overcorrected to "stage" |
| 3 | repair of 28 blocks, 8 more terms | 1 / 2 / 9 |
| 4 | repair of 12 blocks | 0 / 1 / 6 |
| 5 | repair of 6 blocks | 0 / 0 / 6 |

Of the final blocks, 87 come from round 2 and 37 from the repairs. The six
low findings that remain are terminology drift: "stage" for a level that
is not a pipeline step, "mandatory field" next to "required field", and
"Check" for the instrument check. The human review resolved all six.

## Human review

On 2026-10-09, all 124 German/English block pairs were read in order. The
review corrected the six remaining terminology findings and translation
problems that were individually faithful but unclear or unidiomatic in the
assembled standard. It did not rewrite blocks marked `adapt` or `house-refs`.
The fixed rendering of *stanzen* was relaxed from "generate from the template"
to the context-dependent "generate or create"; `stamp` remains reserved for
the scope-sha stamp.

## Still to do before this is the package standard

- **Rewrite flagged blocks.** Blocks flagged `adapt` in
  `docs/standard-blocks.tsv` (front matter, the id rules, the coinage table)
  and `house-refs` (house paths and labs) get rewritten for the package. That
  is a separate, reviewed edit, not part of the translation.
- **Define the coinages** — area, promise, scar table, free knobs — where the
  coinage table marks them.
