# Checks have no switches — 2026-11-09

> `LABKIT_PREFLIGHT=skip` is not a switch in this note's sense: it leaves out the preflight the pre-run hook runs unasked and lifts no duty ([architecture](../architecture.md#rules-checks-and-gates)).

Decided 2026-11-09 by the author: no check of labkit can be switched off, not by a setting, not per area, not per line. During an experiment nothing of the harness can be changed by the agent that uses it. Whether a rule earns its place is a question about labkit, answered by measuring, and answered in labkit's code.

## Why

The agent that runs an experiment is the party the gates hold. A check it can switch off holds nothing: the switch is the cheapest way past every blocker, and a warning it can silence is a warning nobody reads. Linters work the other way (`select`, `ignore`, `# noqa`) because there the author and the checked party are the same person; in labkit they are not.

What varies by experiment already varies by a declared fact, not by a wish: the repeat cost picks the lane (`standard_contract.Lane`), and the lane says which duties a number owes. That stays the one way the checks differ between areas. A finding a person does not follow is decided, not silenced: an audit finding's decision (`findings.write_decision`) is a record with its reason, a gate's blocker has its way out. Neither turns a check off.

## How a rule leaves

A rule or a check is removed by a change to labkit, released as a version; an experiment pins its labkit, so the change never reaches a run in progress. The evidence for the change is a measurement:

1. The inventory says what exists: `python -m labkit.tools.check_inventory` lists every finding site with the rule it cites, its grade, its evidence kind and the commands that reach it, and every active rule with the places that cite it. Computed from the source at every call, committed nowhere.
2. A usage round counts what fired: per check, how often, a real fault or a false alarm, and which never fired (`TODO.md`, "Bei der nächsten Nutzung beobachten").
3. A rule that no check holds and no audit asks about, or whose checks never fired on a real fault, is a candidate. Removing it is a decision on that evidence, written into `CHANGELOG.md`.

## How a rule comes

The agent audit names the rule each finding holds, or `new class` when no rule of the standard fits (`findings.Finding.rule`, kept apart from the subject: one says where the fault lies, the other which rule it breaks). The `new class` findings are collected for the author (`check_inventory --records EXPERIMENTS`). A new rule, or a wider one, comes only from that review and with its grounds — what fault it names, where it occurred, why no rule holds it. A count of `new class` findings is a reason to look, not a rule.

## The state on 2026-11-09

The first inventory: 227 finding sites, 26 of which cite a rule; 10 of the 96 active rules are cited by a finding site, 8 more only by other code strings, 18 only by agent definitions, templates and guides, 60 nowhere outside the standard. "Nowhere" is about the citation, not the check: `LAB-010 Commit before the run` is cited nowhere, yet every run records its uncommitted code as `uncommitted.patch` and its untracked sources under `source-untracked/` (`run/provenance.py`), the safety net the rule names. Until each finding names the rule it holds, a usage round can count findings but not rules. So the next step towards the measurement is the mapping finding → rule, which is a decision about the doctrine and stays with the author.
