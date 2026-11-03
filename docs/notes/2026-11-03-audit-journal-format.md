# Audit journals require bound audit starts

2026-11-03. S1 of the [combined maintainability plan](2026-11-03-maintainability-repair-plan.md).
Max decided to remove the old journal reader now, keeping as little
legacy handling as possible. This supersedes the plan's recommendation
to wait for another deliberate break. No scientific standard changes.

**Problem.** Audit starts written by 0.103.0 or earlier name neither
the protocol nor the promise block. Reading them required a separate
supersession rule: a later audit of the same mode could settle the call
regardless of its protocol. Current starts already record both bindings.

**Current contract.** The reader and writer share one binding validator.
An analysis/preflight start requires non-empty text for `block_sha` and
`protocol`; missing, empty or non-text values raise `AttemptError` naming
the file, line (when read), field and last compatible release, 0.107.0.
The writer refuses an invalid binding before creating locks or journal
lines. A real no-promise block uses `promises.NO_BLOCK`, a recorded value;
it is not an absent binding.

Decision and report reviews bind different inputs and continue to need
neither audit field. Old journal contents and answers are never rewritten,
deleted or supplied with guessed bindings. Reproduce their areas with the
pinned version. The append-only and evidence-loss checks remain in force.

**Distinct case retained.** A failed file no journal attempt names is
still evidence with unknown order/protocol. It is shown and can be settled
by a completed journaled audit of its mode; no start is invented for it.
This is evidence-loss handling, not a reader for the removed start format.
For a journaled failed audit, supersession always requires a later record
of the same mode, protocol and promise block.

**Verification.** Tests cover rejected old/partial audit starts, both
current audit modes, both review modes, refusal before writing, unchanged
kept evidence and refusal before model calls. Existing supersession tests
cover current failed calls and the unjournaled-file counterpart. Model
answers are fixed test replies; no real model calls are required.
