"""Typed backend specs for tests that fake a call: `spec_of` turns the
record-shaped dict a test writes (`endpoint` singular, as runs record it)
into the spec `llm.spec` hands every call, through `parse_spec` — so a
fixture is held to the same shape as models.toml."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from labkit.run.llm_specs import BackendSpec, OllamaSpec, parse_spec

#: the keys a record carries that models.toml never states
_DERIVED = ("alias", "endpoint", "controls_temperature", "model_digest")


def spec_of(d: dict, alias: str = "x") -> BackendSpec:
    """The typed spec of D, a dict shaped like `llm.resolve`'s record."""
    table = {k: v for k, v in d.items() if k not in _DERIVED}
    if "endpoint" in d and "endpoints" not in d:
        table["endpoints"] = [d["endpoint"]]
    spec = parse_spec(d.get("alias", alias), table, {})
    if isinstance(spec, OllamaSpec) and "model_digest" in d:
        spec = dataclasses.replace(spec, model_digest=d["model_digest"])
    return spec


def typed(resolve: Callable[[str], dict]) -> Callable[[str], BackendSpec]:
    """A fake `llm.spec` from a fake that returns record-shaped dicts."""
    return lambda alias: spec_of(resolve(alias), alias)
