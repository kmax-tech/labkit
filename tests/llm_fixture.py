"""Typed backend specs for tests that fake a call: `spec_of` turns the
record-shaped dict a test writes (`endpoint` singular, as runs record it)
into the spec `llm.spec` hands every call, through `parse_spec` — so a
fixture is held to the same shape as models.toml."""

from __future__ import annotations

import dataclasses
import json
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


def cli_reply(
    model: str = "m", result: str = "Yes", without: str = "", **fields: object
) -> str:
    """A `claude -p --output-format json` reply as the CLI writes one when
    MODEL answers whole: one turn, no safety stop, MODEL alone in
    `modelUsage` (fields observed on CLI 2.1.304, 2026-10-22). FIELDS
    replace or add keys; WITHOUT names one to drop."""
    body: dict[str, object] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result,
        "num_turns": 1,
        "safety_stops": 0,
        "modelUsage": {model: {"inputTokens": 2, "outputTokens": 4}},
    }
    body.update(fields)
    body.pop(without, None)
    return json.dumps(body) + "\n"
