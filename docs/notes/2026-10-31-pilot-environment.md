# Pilot environment identity before a paid run

## 2026-10-31 — Equal versions, different sandbox adapters

**Problem:** labkit-paper-main's `.venv` pointed at another checkout. Both
sandbox installations reported version 0.1.0, but only the directory install
in `.venv-pilot` supported the pilot's API-key adapter. Images and a contract
addendum were prepared before constructing the first attempt.

**Solution:** the registered pilot runner checks `direct_url.json`'s Git
commit against requirements.txt before building images, and records the
commit in store provenance. `--check` uses the same attempt construction as
`--pilot`, runs setup on disposable offline copies, and emits observed
image/setup evidence for an addendum only after every selected check passes.

**Notes:** a directory install cannot prove its commit and is refused.
Changing the pin and installing the intended Git revision is a separate
step; this change does not repair the existing environment. The actual
rejection and the setup path on freshly staged task 21 and pubmedqa50 lab
arms were verified separately: both setups printed `one labkit: 0.104.3`,
both protocol checks passed, and no model was called. This does not establish
proxy forwarding or a successful complete `--check` in the current environment.
