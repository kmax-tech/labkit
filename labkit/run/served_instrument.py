"""served_instrument — what a vllm-swap proxy says serves a model, read from its GET /health.

The contract is vllm-swap's `/health` since v0.1.0 (https://github.com/kmax-tech/vllm-swap):

    {"tool": {"swap_proxy.py": "<12 hex>", "start-swap.sh": "<12 hex>"},
     "instruments": {"<alias>": {"served_model": …, "cmd": […], "digest": "<12 hex>"}},
     "running": null | {"alias": …, "cmd": […], "digest": …, "vllm_version": "<version>" | null}}

`instruments.<alias>.digest` names the configuration a model alias is served with (served model id and launch
command); it is known before anything is loaded. `running.vllm_version` is the version of the vLLM process that
runs now, so it is known only while that alias is loaded. `tool` names the proxy's own files.

A server without this `/health` — plain vLLM answers it with an empty body, sglang and other OpenAI-compatible
servers differently or not at all — reports nothing: every field is NOT_REPORTED, and a run goes on with that
recorded. What a reading may not do is stand for a check: the end of a run compares readings
(`instrument_changes`), and a reading that names nothing there blocks.

    read_health          GET /health of one endpoint, parsed, or None
    reading_from_health  what one /health says of one model alias
    agreed_value         one value from several endpoints' readings
    read_instrument      the reading of a model alias over all its endpoints
    instrument_changes   what differs between the start of a run and its end

A swap to another alias and back between two readings is not seen; the proxy reports no swap count.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

#: what a field holds when the server did not report it
NOT_REPORTED = "not reported"
#: the prefix of a field whose endpoints reported different values
MISMATCH = "MISMATCH:"
#: how long one GET /health may take; the proxy answers it without touching vLLM except for `/version`
HEALTH_TIMEOUT_S = 10


class ServedInstrumentChanged(RuntimeError):
    """The instrument at the end of a run is not the one at its start, or the end could not be read: the
    answers may come from two instruments. Raised by `runlog` before the run's completion is written."""


@dataclass(frozen=True)
class ServedReading:
    """What a vllm-swap proxy said of one model alias at one moment. Each field is a value, NOT_REPORTED, or
    MISMATCH followed by the values when several endpoints disagreed. NOT_REPORTED means no endpoint gave the
    field: no such /health, a field of another shape, an alias the proxy does not configure, and for
    `vllm_version` also an alias not loaded right now. Among several endpoints one that gives nothing does
    not count (`agreed_value`): the others' value stands.

    - `digest`: the configuration the alias is served with (`instruments.<alias>.digest`).
    - `tool`: the proxy's own files, `name=digest` pairs joined by commas, sorted.
    - `vllm_version`: the running vLLM; NOT_REPORTED also when the alias is not loaded right now."""

    digest: str
    tool: str
    vllm_version: str


NOTHING_REPORTED = ServedReading(NOT_REPORTED, NOT_REPORTED, NOT_REPORTED)


def read_health(endpoint: str, headers: Mapping[str, str]) -> dict[str, object] | None:
    """GET /health of ENDPOINT as a JSON object, or None when it gives none: no answer, an HTTP error, an
    empty or non-JSON body (plain vLLM answers 200 with no body), JSON that is no object. No model call.

    None is a recorded fact, not a skipped error: the caller records NOT_REPORTED, and a check that needs
    the value blocks on it (`instrument_changes`)."""
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/health", headers=dict(headers)
    )
    try:
        with urllib.request.urlopen(request, timeout=HEALTH_TIMEOUT_S) as reply:
            body = json.loads(reply.read().decode("utf-8"))
    except (
        OSError,
        ValueError,
    ):  # URLError and HTTPError are OSErrors; JSON and decode errors ValueErrors
        return None
    return body if isinstance(body, dict) else None


def reading_from_health(
    health: Mapping[str, object] | None, alias: str
) -> ServedReading:
    """What HEALTH, one parsed /health (None: none was given), says of the proxy's model alias ALIAS — the
    `model` of a labkit spec, which the proxy knows as its alias. A field of a shape other than the contract
    is NOT_REPORTED (`ServedReading`); an alias the proxy does not configure reports no digest."""
    if health is None:
        return NOTHING_REPORTED
    digest = NOT_REPORTED
    instruments = health.get("instruments")
    if isinstance(instruments, dict):
        entry = instruments.get(alias)
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("digest"), str)
            and entry["digest"]
        ):
            digest = entry["digest"]
    tool = NOT_REPORTED
    files = health.get("tool")
    if (
        isinstance(files, dict)
        and files
        and all(isinstance(v, str) for v in files.values())
    ):
        tool = ",".join(f"{name}={files[name]}" for name in sorted(files))
    version = NOT_REPORTED
    running = health.get("running")
    if isinstance(running, dict) and running.get("alias") == alias:
        if isinstance(running.get("vllm_version"), str) and running["vllm_version"]:
            version = running["vllm_version"]
    return ServedReading(digest, tool, version)


def agreed_value(values: Sequence[str], missing: str) -> str:
    """One value from the readings of several endpoints: the value all endpoints that reported one agree on;
    MISSING when none reported (each said MISSING); MISMATCH and the sorted values when they disagree — a run
    served by two instruments under one alias must not look clean. One rule for every served backend: the
    ollama weights digest (`llm._aggregate_digests`) and each field of a `ServedReading`."""
    seen = sorted({v for v in values if v != missing})
    if not seen:
        return missing
    if len(seen) == 1:
        return seen[0]
    return MISMATCH + ",".join(seen)


def read_instrument(
    endpoints: Sequence[str], alias: str, headers: Mapping[str, str]
) -> ServedReading:
    """The reading of the proxy's model alias ALIAS over all ENDPOINTS, each field agreed across them
    (`agreed_value`). Reads every endpoint's /health; makes no model call."""
    readings = [reading_from_health(read_health(e, headers), alias) for e in endpoints]
    return ServedReading(
        agreed_value([r.digest for r in readings], NOT_REPORTED),
        agreed_value([r.tool for r in readings], NOT_REPORTED),
        agreed_value([r.vllm_version for r in readings], NOT_REPORTED),
    )


def instrument_changes(
    start_digest: str, first_version: str, end: ServedReading
) -> list[str]:
    """What differs between a run's start and END, its reading at the end, as sentences; [] when nothing
    does. START_DIGEST is the digest read when the alias was resolved, FIRST_VERSION the vLLM version read
    right after its first answer (NOT_REPORTED when it gave none or no answer came).

    Asked only for an alias whose start digest was reported: a server that never reported one is recorded
    as such and has nothing to compare. A start digest that is a MISMATCH is compared like any value: the
    disagreement stands recorded in the run's `served_digest`, and only a pin refuses it. Then:

    - the end must report a digest, and it must be the start's — else the answers may come from two
      configurations, or from one nobody can name;
    - the vLLM version is compared when both readings name one; the end names none while the alias is not
      loaded (another alias of the same proxy ran last), and that is no change."""
    out: list[str] = []
    if end.digest == NOT_REPORTED:
        out.append(
            f"the end reports no digest (start: {start_digest}) — the proxy did not answer /health, "
            "or no longer serves the alias; which instrument answered last is not known"
        )
    elif end.digest != start_digest:
        out.append(
            f"the configuration digest changed from {start_digest} to {end.digest}"
        )
    if (
        NOT_REPORTED not in (first_version, end.vllm_version)
        and first_version != end.vllm_version
    ):
        out.append(
            f"the vLLM version changed from {first_version} to {end.vllm_version}"
        )
    return out
