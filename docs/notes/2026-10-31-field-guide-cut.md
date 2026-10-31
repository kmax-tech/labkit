# The field guide cut (2026-10-31)

`labkit/docs/protocol-field-guide.md` went from 6,555 to about 3,800
words before the cold round 21/60, so that "after" measures the short
surface: the guide is what `protocol-check --guide` names when a field's
one-line help in the template is not enough. Each sentence went through
the self-check of the SimpleEnglish skill (`~/projects/SimpleEnglish`,
document register); a field whose entry only repeated the template's help
lost its entry (the guide says so at its top); `labkit-adopt` is named as
the adoption. The example of a generated Recorded results line, which a
test reads, stands as it was.

## Where the removed sentences came from

The evidence behind the guide's rules, kept here so the guide carries only
the rule:

- **One job per field** (rule 8): 2026-10-07, a frozen, audited protocol
  was sound and read "far too dense" — bare cross-references, one case
  spelled two ways, every field retelling the result.
- **`repeat_cost`**: until 0.103.0 it read `seconds | minutes | hours`; two
  cold agents declared `minutes` for 16 calls and waited 15 minutes of
  audits for a 64-second run (2026-10-05).
- **`standard`**: the version history (0.23 renamed `cost` to
  `repeat_cost`, 0.22 brought `kind`, 0.21 the Conclusion and Recorded
  results labels, 0.19 / labkit 0.72 made the promise tables owed) is the
  CHANGELOG's.
- **Conclusion**: round 10 — four readers of the first ten lines took the
  number and its limit, not whether the criterion was met.
- **Question †**: round 15 (2026-10-08) — a person restated the question
  and did not read the Conclusion as its answer.
- **Terms of this protocol**: rounds 15–16, areas 18 and 19
  (2026-10-09) — four cold readers lost the thread; until 2026-10-09 the
  field stood under Context, and older protocols keep it there.
- **Inference criterion**: uniagent area 17 (a threshold as prose in a
  docstring) and round 15 (2026-10-08, a person found no way from the
  sentence to the threshold).
- **Quality check**: review 2026-10-08 — a threshold the hypothesis needs,
  written as a quality check, turns a clean negative into "no verdict".
- **Registered branch**: round 15 — "extremely technical, I have to look
  that up first".
- **Recorded results**: phase 5 (2026-10-21) — since then report-check
  holds the field exactly to its rendering.
- **Analysis audit**: 2026-10-07 — readers stumbled over an open
  placeholder.
- **`[result] run`**: phase 3 of the 1.0 line (2026-10-21) — before, the
  old Answer line and an `Answering run` field carried the id; round 15
  (2026-10-08): a person named the fresh run instead of the derived one.
- **Model / tool and `[gate] labels`**: phase 4 (2026-10-21) — until
  0.100.0 the prose line decided by matching "n/a", "none" or dashes, and
  the gate labels were a prose field.
- **Model arms**: introduced 2026-10-09.
- **Null condition**: usability probe 2026-10-07 — a placebo whose answer
  varied per item followed the gold label and left its band.
- **Noise ceiling**: Sonnet v3 t3 and t5 (2026-10-16) wrote what they saw
  under Randomness controls, where nobody looks.
