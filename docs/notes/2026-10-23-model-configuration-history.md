# Note 2026-10-23 — model configuration history

The review of 2026-10-23 found that an alias alone did not protect resumed
outputs: editing `models.toml` could put model-b's answers beside model-a's
in the same file. `llm.identity` identifies the backend and model, with
the weights' digest for Ollama. Endpoint hosts are excluded because a new
cluster allocation can serve the same weights at another host.

The same audit found a second model-alias lookup in `repo` with its own
error text. `llm.model_entry` now uses `alias_tables`, the lookup used by
`_load_spec`. It supplies the audit's bound-validation evidence with the
current configuration; the validation run record supplies the settings
recorded when that run executed.

The current contracts are in `labkit/run/llm.py:identity` and `model_entry`.
