# AGENTS.md — labkit

Entry file for any coding agent working in this repo (Claude Code reads it
through the `CLAUDE.md` symlink). It holds only what an agent without the
author's machine needs; everything else is linked.

## What this is

labkit is the shared helper package of a research lab: run index, LLM
backend, protocol checks and the gates around a run. Its claim:

> labkit detects violations of explicitly encoded scientific intent across
> implementation, execution and reporting.

The chain is `intent → explicit promise → code → run → reported number`.
Every check belongs to one of three tiers — **guaranteed** (exact,
mechanical, silent on correct input), **static evidence** (warns, never
blocks), **agent audit** (semantics). Never present a static check as proof
of semantics. Contract and rationale: `docs/promise-block.md`.

## Read first

| File | For |
|---|---|
| `README.md` | modules, console commands, the coined terms (one word, one thing) |
| `TODO.md` | the work order and why (German); top section "Reihenfolge" decides what is next |
| `docs/promise-block.md` | promise kinds C/A/B, the TOML block, what the scope hash states |
| `docs/protocol-run-binding.md` | which run belongs to which protocol |
| `docs/coding-style.md` | binding for every line of code (vendored copy — do not edit here) |

## Setup and tests

```bash
pip install -e '.[dev]'
pytest -q
```

The suite is self-contained: it passes in a fresh clone with an empty home
directory (481 passed on 2026-10-06). One test skips everywhere for want of
a `requirements.lock` (`tests/test_runlog_env.py`). The `usability stage`
command itself reads the house templates under `~/.claude/resources` and
does not work outside the author's machine; its tests do not need them.

## Rules

- **stdlib only.** `dependencies = []` is deliberate; a lab helper that
  pulls packages in decides every experiment's environment. Dev tools go in
  the `dev` extra.
- **Fail loud.** No bare `except`, no silent skip. A malformed input raises
  with a sentence naming the field.
- **One home per logic.** The id alphabet lives in `labkit/promises.py`;
  other modules import it. A second use means moving code, not copying it.
- **Every number-producing function gets a test.** A gate that blocks gets
  a twin test: the correct variant must pass (no false blocker).
- **Language.** Code, identifiers, docstrings, docs in `docs/`, commit
  messages: English. Talk to the user, and write `TODO.md` entries, in
  German.
- **Backward compatibility.** Protocols without a promise block, the legacy
  letters K/S/W/N, and the flat-copy import fallbacks (`except ImportError`
  for vendored student repos) keep working.
- **Order before features.** Build what `TODO.md` puts next, nothing ahead
  of it: static-evidence checks wait for the benchmark pilot to show they
  are needed. Rollout to other repos, templates and the house doctrine is a
  separate task and out of reach here.
- **One commit per step**, the message says why. Do not push, tag or
  release; report what is ready to commit.

## Not in this repo

The research thread (literature, paper plan, benchmark case list) and the
house doctrine (`arbeitsstandard`) live on the author's machine. Where a
docstring cites `§2.A12` or a dated incident, that is the doctrine; the
code's own docstring states the rule it enforces.
