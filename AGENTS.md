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
| `docs/architecture.md` | layers, the chain from promise to number (module, command, tier), one home per question |
| `README.md` | console commands, the coined terms (one word, one thing) |
| `TODO.md` | the work order and why (German); top section "Reihenfolge" decides what is next |
| `docs/promise-block.md` | promise kinds C/A/B, the TOML block, what the declared-scope hash states |
| `docs/protocol-run-binding.md` | which run belongs to which protocol |
| `docs/student-repos.md` | how a student thesis repo gets labkit (pinned from GitHub) and moves to a newer one |
| `labkit/docs/standard.md`, `labkit/docs/rules.tsv` | the lab standard every gate cites (`AS-nnn Name`) and its ledger; `python -m labkit.rules show AS-nnn` prints one rule, `labkit/rules.py` checks heads, ledger and every reference |
| `docs/coding-style.md` | binding for every line of code (vendored copy — do not edit here) |

## Setup and tests

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

The editor's type checker reads the same `.venv` (`[tool.pyright]` in
`pyproject.toml`).
Reading and debugging recipes (a test under pdb, a command's call tree or
timeline): `justfile` (`just` lists them); in VS Code `.vscode/launch.json`.
Before a commit: `.venv/bin/ruff check . && .venv/bin/ruff format --check . &&
.venv/bin/pyright` — all three clean (docs/coding-style.md CS-008 Run the linter and the type checker),
and the suite green. The versioned hook `.githooks/pre-commit` runs all four
and refuses the commit otherwise; turn it on once per clone with
`git config core.hooksPath .githooks`.

The suite is self-contained: it passes in a fresh clone with an empty home
directory. One test skips everywhere for want of
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
- **Breaking changes, not legacy paths.** Build for the current format;
  keep code clear and modular. Do not add or extend code that reads old
  formats. A format change is an announced break (`CHANGELOG.md`,
  "Breaking", naming the last version that reads the old format); old runs
  are reproduced with the repo's commit and its pinned labkit version.
  Existing legacy paths are removed in one release with the template
  rollout (`TODO.md` item 8), not piecemeal.
- **Order before features.** Build what `TODO.md` puts next, nothing ahead
  of it: static-evidence checks wait for the benchmark pilot to show they
  are needed. Rollout to other repos, templates and the house doctrine is a
  separate task and out of reach here.
- **One commit per step**, the message says why. Do not push, tag or
  release; report what is ready to commit.

## Not in this repo

The research thread (literature, paper plan, benchmark case list), the
author's house rules (the German `arbeitsstandard`, seven rules on notes and
the thread) and the dated incidents behind every rule live on the author's
machine. The lab standard itself ships here (`labkit/docs/standard.md`, since
0.77.0). Where a docstring cites `AS-015 Preflight audit before freezing`,
that is a rule of this standard; where it cites a dated incident, that is
the evidence; the code's own docstring states the rule it enforces.
