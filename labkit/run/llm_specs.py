"""llm_specs — what a backend is, one type per backend, from models.toml.

`ClaudeCliSpec`, `OllamaSpec` and `OpenAISpec` carry exactly the options
their backend reads (`OPTIONS`); `parse_spec` builds one from a
`[models.<alias>]` table and refuses a key the backend does not read, a
value of the wrong kind, a served backend without endpoints. Every spec is
immutable, its endpoints a tuple. `record` writes it as a run records it
(`models_resolved`). `llm` freezes one per alias and process; the wire
calls in `llm_backends` take them. Reads nothing, calls nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias, cast

from labkit.formats.runs import JsonObject


@dataclass(frozen=True)
class ClaudeCliSpec:
    """`claude -p` (CLI auth, headless-safe): a model id and nothing to
    serve it — no endpoint, no key, no sampling control."""

    alias: str
    model: str
    backend: Literal["claude-cli"] = "claude-cli"


@dataclass(frozen=True)
class OllamaSpec:
    """An ollama server. `endpoints` are URLs (names resolved against
    `[endpoints]`), round-robin; `num_ctx` the context window ollama
    allots, None for the server's default; `model_digest` the weights the
    endpoints serve (`llm` probes it at resolution)."""

    alias: str
    model: str
    endpoints: tuple[str, ...]
    num_ctx: int | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    model_digest: str = "unavailable"
    backend: Literal["ollama"] = "ollama"


@dataclass(frozen=True)
class OpenAISpec:
    """Any OpenAI-compatible server (vLLM, sglang). `reasoning` declares a
    model that thinks before answering (the server must split the trace
    off); None when models.toml does not say."""

    alias: str
    model: str
    endpoints: tuple[str, ...]
    api_key_env: str | None = None
    api_key: str | None = None
    reasoning: bool | None = None
    backend: Literal["openai"] = "openai"


BackendSpec: TypeAlias = ClaudeCliSpec | OllamaSpec | OpenAISpec
ServedSpec: TypeAlias = OllamaSpec | OpenAISpec

#: the keys a `[models.<alias>]` table may carry, per backend — a key
#: outside its backend's set is refused, never dropped: `num_ctx` on an
#: OpenAI-compatible server or `reasoning` on ollama would do nothing
OPTIONS: dict[str, frozenset[str]] = {
    "claude-cli": frozenset({"backend", "model"}),
    "ollama": frozenset(
        {"backend", "model", "endpoints", "num_ctx", "api_key_env", "api_key"}
    ),
    "openai": frozenset(
        {"backend", "model", "endpoints", "api_key_env", "api_key", "reasoning"}
    ),
}


def parse_spec(
    alias: str, table: Mapping[str, object], endpoint_names: Mapping[str, object]
) -> BackendSpec:
    """The spec of `[models.<ALIAS>]` (TABLE), endpoint names resolved
    against `[endpoints]` (ENDPOINT_NAMES), literal URLs passed through.
    Raises ValueError naming the field for an unknown backend, a key its
    backend does not read, a value of the wrong type, a served backend
    without endpoints, and the `endpoint = ...` string form (not read
    since 0.89.0); KeyError for an endpoint name `[endpoints]` lacks."""
    where = f"models.toml [models.{alias}]"
    if "endpoint" in table:
        raise ValueError(
            f"{where}: `endpoint = ...` is not read since labkit 0.89.0 — "
            f"write `endpoints = [{table['endpoint']!r}]`"
        )
    backend = table.get("backend")
    if not isinstance(backend, str) or backend not in OPTIONS:
        raise ValueError(
            f"{where}: backend = {backend!r} — one of {', '.join(OPTIONS)}"
        )
    unknown = sorted(set(table) - OPTIONS[backend])
    if "num_ctx" in unknown:
        raise ValueError(
            f"alias '{alias}': num_ctx is an ollama option, but the backend is "
            f"'{backend}' — an OpenAI-compatible server sets its window at "
            f"start (vllm --max-model-len) and refuses longer prompts"
        )
    if unknown:
        raise ValueError(
            f"{where}: {', '.join(unknown)} — not an option of backend "
            f"'{backend}' (it reads {', '.join(sorted(OPTIONS[backend]))}); "
            f"a key the backend does not read would do nothing"
        )
    model = table.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError(f"{where}: model = {model!r}, not a model id")
    if backend == "claude-cli":
        return ClaudeCliSpec(alias, model)
    endpoints = _endpoints(where, alias, table.get("endpoints"), endpoint_names)
    key_env = _optional_str(where, table, "api_key_env")
    key = _optional_str(where, table, "api_key")
    if backend == "ollama":
        num_ctx = table.get("num_ctx")
        if num_ctx is not None and (
            isinstance(num_ctx, bool) or not isinstance(num_ctx, int) or num_ctx <= 0
        ):
            raise ValueError(
                f"alias '{alias}': num_ctx must be a positive integer, got {num_ctx!r}"
            )
        return OllamaSpec(alias, model, endpoints, num_ctx, key_env, key)
    reasoning = _optional_bool(where, table, "reasoning")
    return OpenAISpec(alias, model, endpoints, key_env, key, reasoning)


def _optional_str(where: str, table: Mapping[str, object], key: str) -> str | None:
    value = table.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{where}: {key} = {value!r}, not a string")
    return value


def _optional_bool(where: str, table: Mapping[str, object], key: str) -> bool | None:
    value = table.get(key)
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{where}: {key} = {value!r}, not true or false")
    return value


def _endpoints(
    where: str, alias: str, raw: object, names: Mapping[str, object]
) -> tuple[str, ...]:
    """The URLs a served backend calls: names from `[endpoints]` or literal
    URLs, at least one."""
    if not isinstance(raw, list) or not raw:
        raise ValueError(
            f"{where}: a served backend needs `endpoints = [...]` — names from "
            f"[endpoints] or URLs"
        )
    out: list[str] = []
    for e in cast(list[object], raw):
        if not isinstance(e, str):
            raise ValueError(f"{where}: endpoint {e!r} is not a name or URL")
        if "://" in e:
            out.append(e)
            continue
        url = names.get(e)
        if not isinstance(url, str):
            known = ", ".join(names) or "none defined"
            raise KeyError(
                f"endpoint name '{e}' for alias '{alias}' not in "
                f"[endpoints] (known: {known})"
            )
        out.append(url)
    return tuple(out)


def controls_temperature(spec: BackendSpec) -> bool:
    """Whether the backend sends a temperature: ollama and openai do,
    claude-cli has no such flag and refuses one."""
    return not isinstance(spec, ClaudeCliSpec)


def record(spec: BackendSpec) -> JsonObject:
    """The spec as a run records it (`models_resolved`, a run's config):
    backend, model, alias, `controls_temperature`, and for a served backend
    `endpoints` (a fresh list) with `endpoint` its first entry, the digest
    for ollama, and each option models.toml set. A new dict every call: no
    caller reaches the frozen spec through it."""
    out: JsonObject = {
        "backend": spec.backend,
        "model": spec.model,
        "alias": spec.alias,
    }
    if not isinstance(spec, ClaudeCliSpec):
        out["endpoints"] = list(spec.endpoints)
        out["endpoint"] = spec.endpoints[0]
        for key in ("api_key_env", "api_key"):
            if getattr(spec, key) is not None:
                out[key] = getattr(spec, key)
    if isinstance(spec, OllamaSpec):
        if spec.num_ctx is not None:
            out["num_ctx"] = spec.num_ctx
        out["model_digest"] = spec.model_digest
    if isinstance(spec, OpenAISpec) and spec.reasoning is not None:
        out["reasoning"] = spec.reasoning
    out["controls_temperature"] = controls_temperature(spec)
    return out
