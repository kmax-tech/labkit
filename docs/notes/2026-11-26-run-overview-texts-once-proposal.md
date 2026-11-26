# Proposal: the run overview of an analysis audit shows each registration text once (2026-11-26)

> Status: a proposal. Nothing is built, and building it is not scheduled. The author asked for the proposal; whether and when to build is the author's decision (section "Decisions").

## The problem

An analysis audit shows the auditor every run of the protocol it audits (`labkit/checks/protocol_runs.py`). For each run the overview prints how the registration that run saw differs from the audited run's: one line per run, each changed field as `<field>: '<text of the audited run>' → '<text of this run>'`, both texts in full (`protocol_runs._registration`).

The text of the audited run is the same in every line. A protocol with four earlier runs therefore prints a changed field's text up to four times, and two runs that saw the same registration print the same line twice.

Measured on the analysis-audit prompt of one lab area with four earlier runs, built without a model call by labkit v0.116.0 (the script and the size table are kept outside this repository):

| What                                                  | Bytes   | Share of the prompt |
|-------------------------------------------------------|---------|---------------------|
| The whole prompt, 23 pieces                           | 815 570 | 100 %               |
| The run overview of the audited protocol              | 202 141 | 24.8 %              |
| Its four registration lines                           | 127 958 | 15.7 %              |
| The field texts in those lines                        | 127 567 | 15.6 %              |
| The same field texts, each distinct text counted once | 58 833  | 7.2 %               |
| Repeated field text (the difference)                  | 68 734  | 8.4 %               |

Six distinct texts of 3 276 to 7 358 characters are printed more than once. Two of the four lines are the same text character for character after the run id (33 868 characters each).

The prompt was not refused or cut by a model: the audit on it ran. The reason for the proposal is that this part of the prompt grows with every further run of a protocol, not that a call failed.

## What labkit does today for the neighbouring cases

- **Code of a run.** A run whose code is the same as a run listed before prints `the same as run <id>'s` (`protocol_runs._code_lines`, by the code's git tree). The registration has no such shortcut.
- **Diffs past a size.** All full diffs of one audit share 300 000 characters (`protocol_runs.DIFF_BUDGET`). A diff past it is named as not shown in full, with an excerpt, and the auditor asks for it with a `diff:` check.
- **Field texts in the follow-up piece.** The piece that shows earlier decided blockers prints each distinct field text once under `FIELD TEXTS`, with a number, the sha256 of its bytes and its size; the entries name the number (`audit_prompt.field_text_numbers`, `audit_prompt.field_texts_lines`). The layout applies only when a text of 500 bytes or more would be printed twice (`audit_prompt.FIELD_TEXT_ONCE_MIN`); otherwise every text stands at its entry.

## The proposal

Give the run overview the layout the follow-up piece already has.

1. When a field text of `FIELD_TEXT_ONCE_MIN` bytes or more would be printed twice in one overview piece, every field text of that piece moves into a section at the piece's end: each distinct text once, in full, under a number, with its field's name, the sha256 of its bytes and its size.
2. A run's registration line then names numbers instead of texts: `<field>: field text 3 → field text 5`. Two runs that saw the same registration print the same short line; no separate rule for that case is needed.
3. An overview in which no such text repeats keeps today's bytes.

Only texts that are equal character for character share a number. Two versions of a field that differ in one character are two texts with two numbers.

### What it changes for a lab

- **The auditor's prompt.** In the measured area the overview loses about 67 kB of 815 kB (68 734 bytes of repeated text, less the section's head and one head line per distinct text), 8 % of the prompt.
- **Existing audit records.** The digest an analysis record binds covers the overview's text (`audit_binding.run_shown`, through `protocol_runs_pieces`). In an area whose overview changes layout, the newest analysis record stops covering the state once the lab moves to the labkit version that carries this change, and one new analysis audit is owed. An area whose overview keeps its bytes (point 3) keeps its record. This is an announced break (`CHANGELOG.md`, "Breaking").

### Where the code would stand

`protocol_runs` is a check; the numbering lives in a gate (`audit_prompt`), and a check does not import a gate. The numbering and the section's lines would move to a home both can import, and the follow-up piece would use them from there: one home for the layout, not a second copy. Which module that is belongs to the building, not to this proposal.

## Not proposed

- **Equal sections across the run diffs.** Of 197 414 characters of diff sections in the four run diffs, 60 852 stand character for character in more than one diff. Showing a section once would break each diff into text and references, and a diff is read in order. The saving is the same size as this proposal's; the cost to the reader is higher. Left as it is.
- **Merging similar texts.** Two registration lines share 18 to 22 kB with another line without being equal. Anything short of equality needs a judgement about which difference matters, and that judgement is the auditor's.
- **Splitting an audit into several.** A record covers one whole state; partial audits would need their own rules for coverage, follow-up and counts, and none of them would see a finding that spans two parts.
- **Another base for the comparison** (each run against its predecessor instead of against the audited run). It changes what the auditor is asked to judge.
- **A check of the prompt's size before the call.** A separate open point (`TODO.md`).

## Acceptance criteria

Fixed before building. The first four come from a second opinion the author pasted; the last three are added here.

1. **Equal texts only.** A test with two field texts that differ in one character shows two numbers and both texts in full.
2. **Each run keeps what is its own.** For every run the piece still states its registration's source (the commit, with or without its patch), its code state and its changes; a test reads these back per run.
3. **Nothing is lost.** A test expands every number of a rendered piece into its text and compares the result, for every run, with the differences `protocol_history.registration_differences` returns: same fields, same old and new texts, same order.
4. **The saving is measured, not estimated.** The prompt of the measured area is built again without a model call. Predicted: the overview shrinks by 65 to 69 kB. If it shrinks by less than 50 kB, the change is not merged and the note says why the prediction failed.
5. **No change where nothing repeats.** The twin test: an overview without a repeated text of 500 bytes or more is byte for byte what it is today, and its digest is unchanged.
6. **The break is visible.** A test shows that the bound digest of an area with a repeated text differs before and after, and `CHANGELOG.md` names the consequence for existing records.
7. **One home.** The follow-up piece and the run overview use the same numbering and the same section lines; the follow-up piece's bytes do not change.

What these criteria do not show: whether an auditor reads the numbered layout as well as the texts in place. A comparison of content cannot answer that. The follow-up piece already uses the layout; no measurement of how auditors read either layout exists.

## Decisions

These are the author's.

1. **Build it, or wait for a prompt that a model refuses or cuts?** Building costs one announced break and, per affected area, one new analysis audit. Waiting costs 8 % of the prompt in an area with four runs, growing with each further run.
2. **If built: in its own release or together with another change that already makes records stop covering?** Together, an affected area pays one new audit for both changes.
