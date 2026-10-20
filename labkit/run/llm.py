"""llm — project LLM-backend scaffold (stdlib-only).

Experiments never hardcode endpoints or model ids: cluster addresses change,
and every run must record exactly which model answered. `models.toml` at the
repo root is the single place where backends live.

    import llm
    text = llm.complete("haiku", "Say OK")
    spec = llm.resolve("gpt-oss")     # dict -> put into runlog config, so
                                      # runs.tsv records model+backend+endpoint
                                      # + controls_temperature (see below)
    typed = llm.spec("gpt-oss")       # the immutable OllamaSpec every call
                                      # is made with (llm_specs)

Sampling control differs per backend: 'ollama' and 'openai' send a
temperature, 'claude-cli' cannot (the CLI exposes no such flag) and REFUSES
the argument rather than ignoring it. resolve() therefore reports 'controls_temperature',
which lands in the run config — so a run is never recorded as deterministic
when the backend never made it so.

'claude-cli' runs with an empty setting-sources list: the operator's
settings and CLAUDE.md files stay out of the call, and provenance() stamps
CLI version + isolation flags (see CLI_ISOLATION).

models.toml (each backend reads only its own keys — `llm_specs.OPTIONS`;
any other key, and a served backend without endpoints, is refused when the
alias is first resolved):
    [endpoints]                       # URLs live ONCE, under a name; a srun
    gamma1 = "http://gammaweb07.medien.uni-weimar.de:11490"   # reallocation
    # gamma2 = "http://gammawebNN.medien.uni-weimar.de:11491" # edits HERE only

    [models.haiku]
    backend = "claude-cli"            # subprocess `claude -p` (CLI auth, headless-safe)
    model = "claude-haiku-4-5-20251001"

    [models.gpt-oss]
    backend = "ollama"
    model = "gpt-oss:latest"
    endpoints = ["gamma1"]            # names from [endpoints] or literal URLs
    num_ctx = 32768                   # context window ollama allots; without it
                                      # the server's default applies, and a
                                      # longer prompt is CUT, not refused —
                                      # see _check_prompt_fit

    [models.gpt-oss-vllm]
    backend = "openai"                # any OpenAI-compatible server: vLLM, sglang
    model = "openai/gpt-oss-20b"      # the SERVED model id (vllm serve <id>)
    endpoints = ["gamma2"]            # api_key_env = "MY_KEY_VAR" if the server
                                      # requires a key: the NAME of an environment
                                      # variable, never the key — the spec lands in
                                      # every run config. A literal `api_key` is
                                      # honoured but recorded verbatim there.
    reasoning = true                  # model thinks before answering: the server
                                      # must run --reasoning-parser so the trace
                                      # arrives in its own field; an answer whose
                                      # content carries no trace field fails loud

Two servers, SAME model: list both names — completions round-robin across
them and fail over when one drops. Model identity and serving endpoint are
different knobs: the model is a measurement parameter, the endpoint is
operations. But two servers are two INSTRUMENT INSTANCES (batch invariance:
the same item can answer differently depending on server state), so record
per row which endpoint answered — `llm.last_endpoint()` after each call —
and report results split by endpoint; the split must sit under the noise
ceiling. A DIFFERENT model on the second server is simply another alias
pointing at the other endpoint name.

What a call cost: `llm.last_usage()` right after `complete` returns — the
token counts the backend reported (`Usage`: prompt, output, cached, USD where
priced), per thread like `last_endpoint()`. A run that records them per row
or per batch can say what it cost; labkit-audit prints them beside the
prompt size.

For specialized calls (logprobs, raw payloads): use resolve(alias) for
endpoint/model and do your own HTTP — never a literal URL in the experiment.
"""

from __future__ import annotations

import dataclasses
import http.client
import json
import shlex
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from labkit.run import endpoint_lease
from labkit.formats.repo import lab_root
from labkit.formats.runs import JsonObject
from labkit.run.llm_specs import (
    BackendSpec,
    ClaudeCliSpec,
    OllamaSpec,
    parse_spec,
    record,
)
from labkit.run.llm_backends import (
    BackendError,
    NO_USAGE,
    Usage,
    CLI_ISOLATION,
    CALL_STATE,
    auth_headers,
    cli_version,
    complete_claude_cli,
    complete_ollama_chat,
    complete_ollama_raw,
    complete_openai,
)


def _find_models_toml() -> Path:
    """The lab's `models.toml`: `repo.lab_root` from the script's directory,
    else from the working directory."""
    seeds = [
        Path(sys.argv[0]).resolve().parent if sys.argv[0] else Path.cwd(),
        Path.cwd(),
    ]
    for seed in seeds:
        root = lab_root(seed)
        if root is not None:
            return root / "models.toml"
    raise FileNotFoundError(
        "models.toml not found (searched upward from script dir and cwd)"
    )


_FROZEN: dict[str, BackendSpec] = {}  # alias -> spec, fixed at first use per process
_FROZEN_LOCK = threading.Lock()


def spec(alias: str) -> BackendSpec:
    """Alias -> its typed backend spec (`ClaudeCliSpec`, `OllamaSpec`,
    `OpenAISpec`), what every call is made with.

    The spec is FROZEN per process at first use. `models.toml` is shared state:
    a cluster host changes with every allocation, and an experiment running in
    parallel must not have its backend swapped mid-run by whoever edits the
    file — the swap would be silent, and the run's config.json would keep
    naming the model that answered the first half. A new process picks up the
    edit; a running one keeps what it started with. The spec and every value
    in it are immutable (endpoints a tuple), so no caller can edit it. The
    first resolution of an alias holds a lock: two threads starting together
    get the same spec, not two readings of a file edited between them.

    Raises KeyError for an alias or endpoint name models.toml lacks,
    ValueError for a table its backend cannot hold (`parse_spec`).
    """
    with _FROZEN_LOCK:
        if alias not in _FROZEN:
            _FROZEN[alias] = _load_spec(alias)
        return _FROZEN[alias]


def resolve(alias: str) -> JsonObject:
    """Alias -> the spec as a run records it (`llm_backends.record`): put
    this into runlog's config. A new dict every call, from the frozen spec
    (`spec`)."""
    return record(spec(alias))


def _load_spec(alias: str) -> BackendSpec:
    """The spec of ALIAS as `models.toml` states it now — what `spec`
    freezes. For ollama the weights' digest is probed on every endpoint."""
    cfg = tomllib.loads(_find_models_toml().read_text(encoding="utf-8"))
    models = cfg.get("models", {})
    if alias not in models:
        known = ", ".join(models)
        raise KeyError(f"model alias '{alias}' not in models.toml (known: {known})")
    parsed = parse_spec(alias, models[alias], cfg.get("endpoints", {}))
    # Camera-ready gap closed 2026-08-18: the model NAME is not the model.
    # "qwen2.5:7b" can mean different weights in three months; the digest
    # pins what actually answered. Best-effort — a run must not die because
    # the tags endpoint hiccups; "unavailable" is honest and visible.
    # With several endpoints, all are probed: serving DIFFERENT weights under
    # the same alias would silently mix two models into one run — that is a
    # defect, and the config says so loudly instead of picking one digest.
    if isinstance(parsed, OllamaSpec):
        auth = auth_headers(parsed)
        digest = _aggregate_digests(
            {ep: _ollama_digest(ep, parsed.model, auth) for ep in parsed.endpoints}
        )
        parsed = dataclasses.replace(parsed, model_digest=digest)
    return parsed


def _aggregate_digests(per_endpoint: dict[str, str]) -> str:
    """One digest value for the run config, from per-endpoint probes.

    All reachable endpoints agree -> that digest. None reachable ->
    "unavailable". Disagreement -> "MISMATCH:..." — visible in every
    config.json, because a mixed-weights run must not look clean.
    """
    seen = sorted({d for d in per_endpoint.values() if d != "unavailable"})
    if not seen:
        return "unavailable"
    if len(seen) == 1:
        return seen[0]
    return "MISMATCH:" + ",".join(seen)


def _digest_from_tags(tags: dict, model: str) -> str:
    """Pure lookup: /api/tags payload -> short digest for `model`.

    Bare names match their :latest entry ("gpt-oss" -> "gpt-oss:latest").
    Unknown model -> "unavailable" rather than a guess.
    """
    want = {model, model if ":" in model else f"{model}:latest"}
    for m in tags.get("models", []):
        if m.get("name") in want or m.get("model") in want:
            # A proxy (KubeAI's ollama route) prefixes the digest with its
            # algorithm — "sha256:f8ceb…" — where ollama itself sends bare hex.
            # Cutting twelve characters off the prefixed form left FIVE hex
            # digits of pin (seen 2026-10-03 against llm.srv.webis.de).
            digest = str(m.get("digest", "")).removeprefix("sha256:")
            return digest[:12] or "unavailable"
    return "unavailable"


def _ollama_digest(
    endpoint: str, model: str, headers: dict[str, str] | None = None
) -> str:
    try:
        req = urllib.request.Request(
            f"{endpoint.rstrip('/')}/api/tags", headers=headers or {}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return _digest_from_tags(json.loads(r.read().decode("utf-8")), model)
    except Exception:
        return "unavailable"


_TRANSIENT = (
    TimeoutError,
    ConnectionError,
    urllib.error.URLError,
    http.client.HTTPException,
    subprocess.TimeoutExpired,
    BackendError,
)
_RETRIES = {"n": 0}
_RETRIES_LOCK = threading.Lock()
# network hiccup, model reload, queue, outage — 2026-09-24: two runs died
# after ~3 min of DNS/SSL failures with the old (10, 45, 120) ladder.
_BACKOFF = (10, 45, 120, 300, 300)


def retries() -> int:
    """How many transport retries this process has made (for run metrics)."""
    return _RETRIES["n"]


def last_endpoint() -> str:
    """URL that served (or was tried by) this thread's most recent attempt."""
    return getattr(CALL_STATE, "endpoint", "")


def last_usage() -> Usage:
    """The token counts of this thread's most recent completion — read right
    after `complete` returns, like `last_endpoint`. NO_USAGE before the first
    call and when the backend reported none. labkit-audit prints it beside
    the prompt size, so every stamp can carry what the audit cost
    (2026-10-11: 30 transcripts, 7 billion cache-read tokens, and no line
    anywhere said what one audit cost)."""
    return getattr(CALL_STATE, "usage", NO_USAGE)


def last_thinking() -> str:
    """The reasoning trace of this thread's most recent completion — what a
    reasoning model wrote before its answer (ollama `thinking`, OpenAI-style
    `reasoning_content`/`reasoning`); "" when the backend returns none. Read
    it right after `complete` returns, like `last_endpoint`: the answer alone
    says what the model decided, the trace says why (uniagent 2026-10-07: a
    false framework `yes` could not be explained because only the answer was
    kept)."""
    return getattr(CALL_STATE, "thinking", "")


def provenance(alias: str) -> dict:
    """Per-row provenance stamp for `batch.Store(prov=...)`.

    The facts that die when an output file loses its runs.tsv join: which
    model (name@digest) and which serving instance. `endpoint` is passed as a
    CALLABLE — Store evaluates it per append, because with a multi-endpoint
    alias the answering server differs from row to row. Add the run pointer
    yourself: `{**llm.provenance(alias), "run": run.run_id}`.

    For claude-cli the stamp also carries the CLI version and the isolation
    flags — the system prompt is the harness's own, and these two decide
    what else went into it.
    """
    used = spec(alias)
    model = used.model
    if isinstance(used, OllamaSpec):
        model += "@" + used.model_digest
    prov: dict[str, Any] = {"model": model, "endpoint": last_endpoint}
    if isinstance(used, ClaudeCliSpec):
        prov["cli_version"] = cli_version()
        prov["cli_flags"] = shlex.join(CLI_ISOLATION)
    return prov


def complete(
    alias: str,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float | None = None,
    timeout: int = 300,
    attempts: int = 6,
    raw: bool = False,
    stop: list[str] | None = None,
    max_tokens: int = 512,
) -> str:
    """One text completion, retrying transport failures (see _TRANSIENT).

    `attempts` counts total tries, not extra ones; backoff follows _BACKOFF
    (10 s … 300 s, ~13 min in all, so a short outage is survived). Errors
    that no retry can fix — an unknown alias, a temperature the backend cannot
    honour — are raised immediately. Pass attempts=1 to disable.
    """
    for attempt in range(1, attempts + 1):
        CALL_STATE.thinking = ""  # never a previous call's trace
        CALL_STATE.usage = NO_USAGE  # nor its token counts
        try:
            return _complete_once(
                alias,
                prompt,
                system=system,
                temperature=temperature,
                timeout=timeout,
                raw=raw,
                stop=stop,
                max_tokens=max_tokens,
            )
        except _TRANSIENT as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code < 500:
                # the server answered, and the answer is about the request:
                # a wrong model id (404), a missing key (401), a prompt the
                # server refuses (400) — no retry changes it, and HTTPError
                # is a URLError (six attempts, 13 min, audit 2026-10-15)
                raise BackendError(
                    f"{alias}: HTTP {exc.code} {exc.reason} — the server refused "
                    f"the request, not the connection; check the alias in "
                    f"models.toml (model id, api_key_env) and the prompt"
                ) from exc
            if attempt == attempts:
                # Exhausted retries ALWAYS raise BackendError, no matter what
                # the backend threw. Otherwise WHICH exception escapes depends
                # on the backend: claude-cli throws BackendError (a
                # RuntimeError), ollama throws URLError/TimeoutError — no
                # RuntimeErrors. A caller with "except RuntimeError" is then
                # correct on one backend and loses its whole batch on the
                # other (2026-08-14: a DNS hiccup killed a 145-item run after
                # the switch from haiku to the cluster). One documented type =
                # one thing to catch; the original exception stays attached
                # via "from exc".
                if isinstance(exc, BackendError):
                    raise
                raise BackendError(
                    f"{alias}: {type(exc).__name__} after {attempts} attempts: "
                    f"{str(exc)[:200]}"
                ) from exc
            with _RETRIES_LOCK:
                _RETRIES["n"] += 1
            # The backoff must outlive a MODEL LOAD, not just a network
            # hiccup: a 13 GB model takes ~90 s into VRAM, and 5/15 s pauses
            # all fizzle before that (a run died after 5 of 100).
            wait = _BACKOFF[min(attempt - 1, len(_BACKOFF) - 1)]
            print(
                f"llm: {type(exc).__name__} on attempt {attempt}/{attempts} "
                f"({str(exc)[:60]}) — retrying in {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise AssertionError("unreachable")


def complete_many(
    alias: str, prompts: list[str], *, workers: int = 4, **kw: Any
) -> list[str]:
    """complete() over many independent prompts, results in input order.

    A thread pool of `workers`; each worker calls complete() with the same
    keyword arguments, so retries and the retry counter behave as in the
    serial case. claude-cli spawns one process per call (~300 MB), which
    bounds `workers` by RAM, not by the API. Independent prompts only — a
    tournament's pairs, never a conversation.
    """
    if workers <= 1 or len(prompts) <= 1:
        return [complete(alias, p, **kw) for p in prompts]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda p: complete(alias, p, **kw), prompts))


def _complete_once(
    alias: str,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float | None = None,
    timeout: int = 300,
    raw: bool = False,
    stop: list[str] | None = None,
    max_tokens: int = 512,
) -> str:
    """One text completion via the alias' backend. Returns the answer text.

    temperature: the 'ollama' and 'openai' backends send it; 'claude-cli'
    has no such flag. Passing a value to a backend that cannot honour it
    raises instead of silently ignoring it —
    a run must not be documented as "temperature 0" when nothing set it.

    Dispatches to one adapter per backend; each adapter owns its protocol
    (CLI flags, ollama /api/generate or /api/chat, OpenAI /v1).
    """
    used = spec(alias)
    # A serving endpoint is ONE model slot: a second alias against it makes
    # both stages swap the model back and forth, and the timeouts come back as
    # empty answers that an admissibility condition counts as a parser finding. The lease sits
    # HERE and not in the calling script on purpose — a rule a script has to
    # remember is an intention (endpoint_lease's docstring carries the chain).
    endpoint_lease.acquire(
        alias, None if isinstance(used, ClaudeCliSpec) else list(used.endpoints)
    )
    if isinstance(used, ClaudeCliSpec):
        return complete_claude_cli(
            used,
            prompt,
            system=system,
            temperature=temperature,
            timeout=timeout,
            raw=raw,
            stop=stop,
        )
    if isinstance(used, OllamaSpec):
        call = complete_ollama_raw if raw else complete_ollama_chat
        return call(
            used,
            prompt,
            system=system,
            temperature=temperature,
            timeout=timeout,
            stop=stop,
            max_tokens=max_tokens,
        )
    return complete_openai(
        used,
        prompt,
        system=system,
        temperature=temperature,
        timeout=timeout,
        raw=raw,
        stop=stop,
        max_tokens=max_tokens,
    )
