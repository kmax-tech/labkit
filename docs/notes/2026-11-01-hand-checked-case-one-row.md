# 2026-11-01 — the compute skeleton's hand-checked case asks for one row

**Problem.** The quick test template (`labkit/templates/test-quick.py.template`)
asked for a hand-checked case of two rows at least: `KNOWN_ROWS` had to hold
two or more, so that dropping one in
`test_a_lost_row_is_a_refusal_not_a_smaller_denominator` still left a row to
evaluate. A task whose number is about one unit has one row. In the
registered pilot and the reference pilot, tasks 21 and 34 were such tasks;
their agents met the two-row demand by inventing a second row, copied from
the run's own output. The hand-checked case then held a value nobody had
checked by hand, and it was the run's value, so the test could not disagree
with the run.

**Solution.** One row is enough (0.106.0, `ea428e7c`). The lost-row test
drops the last row and expects a refusal: with one row the items are empty
while the ids still name one, and `evaluate_rows()` refuses the silent loss
just as it does for a larger case. The template comment states the rule only;
this note keeps why.

**Notes.** The case is worked out by hand, never by calling the code (the
template's TODO). A second row is welcome when the task has two units; it is
never made up to satisfy the test.
