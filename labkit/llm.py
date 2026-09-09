"""llm — project LLM-backend scaffold (stdlib-only).

Experiments never hardcode endpoints or model ids: cluster addresses change,
and every run must record exactly which model answered. `models.toml` at the
repo root is the single place where backends live.

    import llm
    text = llm.complete("haiku", "Say OK")
    spec = llm.resolve("gpt-oss")     # dict -> put into runlog config, so
                                      # runs.tsv records model+backend+endpoint
                                      # + controls_temperature (see below)

Sampling control differs per backend: 'ollama' accepts a temperature,
'claude-cli' cannot (the CLI exposes no such flag) and REFUSES the argument
rather than ignoring it. resolve() therefore reports 'controls_temperature',
which lands in the run config — so a run is never recorded as deterministic
when the backend never made it so.

models.toml:
    [endpoints]                       # URLs live ONCE, under a name; a srun
    gamma1 = "http://gammaweb07.medien.uni-weimar.de:11490"   # reallocation
    # gamma2 = "http://gammawebNN.medien.uni-weimar.de:11491" # edits HERE only

    [models.haiku]
    backend = "claude-cli"            # subprocess `claude -p` (CLI auth, headless-safe)
    model = "claude-haiku-4-5-20251001"

    [models.gpt-oss]
    backend = "ollama"
    model = "gpt-oss:latest"
    endpoints = ["gamma1"]            # a name from [endpoints] or a literal URL;
                                      # legacy `endpoint = "<url>"` keeps working

    [models.gpt-oss-vllm]
    backend = "openai"                # any OpenAI-compatible server: vLLM, sglang
    model = "openai/gpt-oss-20b"      # the SERVED model id (vllm serve <id>)
    endpoint = "gamma2"               # api_key = "..." if the server requires one
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

For specialized calls (logprobs, raw payloads): use resolve(alias) for
endpoint/model and do your own HTTP — never a literal URL in the experiment.
"""
from __future__ import annotations

import http.client
import json
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

try:
    from labkit import endpoint_lease
except ImportError:                      # vendored flat copy (student repos)
    import endpoint_lease


def _find_models_toml() -> Path:
    seeds = [Path(sys.argv[0]).resolve().parent if sys.argv[0] else Path.cwd(), Path.cwd()]
    for seed in seeds:
        for d in [seed, *seed.parents]:
            p = d / "models.toml"
            if p.exists():
                return p
    raise FileNotFoundError("models.toml not found (searched upward from script dir and cwd)")


_FROZEN: dict[str, dict] = {}      # alias -> spec, fixed at first use per process


def resolve(alias: str) -> dict:
    """Alias -> full backend spec (put this into runlog's config).

    The spec is FROZEN per process at first use. `models.toml` is shared state:
    a cluster host changes with every allocation, and an experiment running in
    parallel must not have its backend swapped mid-run by whoever edits the
    file — the swap would be silent, and the run's config.json would keep
    naming the model that answered the first half. A new process picks up the
    edit; a running one keeps what it started with.
    """
    if alias in _FROZEN:
        return dict(_FROZEN[alias])
    cfg = tomllib.loads(_find_models_toml().read_text(encoding="utf-8"))
    try:
        spec = dict(cfg["models"][alias])
    except KeyError:
        known = ", ".join(cfg.get("models", {}))
        raise KeyError(f"model alias '{alias}' not in models.toml (known: {known})")
    spec["alias"] = alias
    # Endpoint names resolve against [endpoints]; literal URLs pass through.
    # `endpoints = [...]` (list) and legacy `endpoint = "..."` (string) both
    # normalize to spec["endpoints"] (list) + spec["endpoint"] (first entry,
    # for direct-HTTP callers). Frozen with the rest of the spec: an edit to
    # models.toml never reaches a running process.
    table = cfg.get("endpoints", {})
    raw_eps = spec.pop("endpoints", None) or \
        ([spec["endpoint"]] if spec.get("endpoint") else [])
    eps = []
    for e in raw_eps:
        if "://" in e:
            eps.append(e)
        elif e in table:
            eps.append(table[e])
        else:
            known = ", ".join(table) or "none defined"
            raise KeyError(f"endpoint name '{e}' for alias '{alias}' not in "
                           f"[endpoints] (known: {known})")
    if eps:
        spec["endpoints"] = eps
        spec["endpoint"] = eps[0]
    # Recorded in every runlog config, so a run never *looks* deterministic
    # when the backend cannot control sampling at all.
    spec["controls_temperature"] = spec["backend"] in ("ollama", "openai")
    # Camera-ready gap closed 2026-08-18: the model NAME is not the model.
    # "qwen2.5:7b" can mean different weights in three months; the digest
    # pins what actually answered. Best-effort — a run must not die because
    # the tags endpoint hiccups; "unavailable" is honest and visible.
    # With several endpoints, all are probed: serving DIFFERENT weights under
    # the same alias would silently mix two models into one run — that is a
    # defect, and the config says so loudly instead of picking one digest.
    if spec["backend"] == "ollama":
        spec["model_digest"] = _aggregate_digests(
            {ep: _ollama_digest(ep, spec["model"]) for ep in eps} or
            {"": _ollama_digest("", spec["model"])})
    _FROZEN[alias] = dict(spec)
    return spec


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
            return str(m.get("digest", ""))[:12] or "unavailable"
    return "unavailable"


def _ollama_digest(endpoint: str, model: str) -> str:
    try:
        with urllib.request.urlopen(f"{endpoint.rstrip('/')}/api/tags",
                                    timeout=10) as r:
            return _digest_from_tags(json.loads(r.read().decode("utf-8")), model)
    except Exception:
        return "unavailable"


# A dropped connection is not an experiment result. Retrying transport errors
# belongs in the FAST lane too: a pilot loses just as much work as a scaled run
# when the cluster hiccups (2026-08-12: a socket timeout killed a scoring run at
# 49 of 96 items). Retries are COUNTED, never silent — put `llm.retries()` into
# your run metrics, so a run that limped is distinguishable from one that flew.
class BackendError(RuntimeError):
    """A backend refused a call without a diagnosable reason — retryable.

    The claude CLI can exit non-zero with an EMPTY stderr (seen 2026-08-12:
    two CLI-heavy runs in parallel killed both after hundreds of successful
    calls). That is a hiccup, not a misconfiguration, and it belongs in the
    retry set. A real misconfiguration still fails — just three times, fast.
    """


_TRANSIENT = (TimeoutError, ConnectionError, urllib.error.URLError,
              http.client.HTTPException, subprocess.TimeoutExpired,
              BackendError)
_RETRIES = {"n": 0}
_BACKOFF = (10, 45, 120)   # network hiccup, model reload, queue


def retries() -> int:
    """How many transport retries this process has made (for run metrics)."""
    return _RETRIES["n"]


# Round-robin state per alias, and the endpoint of the most recent attempt.
# Two endpoints are two instrument instances (batch invariance) — callers that
# want per-row provenance read last_endpoint() right after a successful call.
# The endpoint is THREAD-local: under parallel.run each worker sees its own
# call's endpoint, never a neighbour's (the writer thread stamps via the
# record's _prov, prepared in the worker — see parallel._stamped).
_RR: dict[str, int] = {}
_RR_LOCK = threading.Lock()
_TLS = threading.local()


def last_endpoint() -> str:
    """URL that served (or was tried by) this thread's most recent attempt."""
    return getattr(_TLS, "endpoint", "")


def provenance(alias: str) -> dict:
    """Per-row provenance stamp for `batch.Store(prov=...)`.

    The facts that die when an output file loses its runs.tsv join: which
    model (name@digest) and which serving instance. `endpoint` is passed as a
    CALLABLE — Store evaluates it per append, because with a multi-endpoint
    alias the answering server differs from row to row. Add the run pointer
    yourself: `{**llm.provenance(alias), "run": run.run_id}`.
    """
    spec = resolve(alias)
    model = spec["model"]
    if spec.get("model_digest"):
        model += "@" + spec["model_digest"]
    return {"model": model, "endpoint": last_endpoint}


def _pick_endpoint(spec: dict) -> str:
    """Next endpoint for this call: round-robin over spec['endpoints'].

    A single endpoint behaves exactly as before. With several, each call
    advances the counter — and because `complete()` re-enters here on retry,
    a dropped server naturally fails over to the next one.
    """
    eps = spec.get("endpoints") or [spec["endpoint"]]
    if len(eps) == 1:
        url = eps[0]
    else:
        key = spec.get("alias", spec.get("model", ""))
        with _RR_LOCK:
            i = _RR.get(key, 0)
            _RR[key] = i + 1
        url = eps[i % len(eps)]
    _TLS.endpoint = url
    return url


def complete(alias: str, prompt: str, *, system: str | None = None,
             temperature: float | None = None, timeout: int = 300,
             attempts: int = 4, raw: bool = False,
             stop: list[str] | None = None, max_tokens: int = 512,
             keep_alive: str = "10m") -> str:
    """One text completion, retrying transport failures (see _TRANSIENT).

    `attempts` counts total tries, not extra ones; backoff is 5 s, 15 s. Errors
    that no retry can fix — an unknown alias, a temperature the backend cannot
    honour — are raised immediately. Pass attempts=1 to disable.
    """
    for attempt in range(1, attempts + 1):
        try:
            return _complete_once(alias, prompt, system=system,
                                  temperature=temperature, timeout=timeout,
                                  raw=raw, stop=stop, max_tokens=max_tokens,
                                  keep_alive=keep_alive)
        except _TRANSIENT as exc:
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
                    f"{str(exc)[:200]}") from exc
            _RETRIES["n"] += 1
            # The backoff must outlive a MODEL LOAD, not just a network
            # hiccup: a 13 GB model takes ~90 s into VRAM, and 5/15 s pauses
            # all fizzle before that (a run died after 5 of 100).
            wait = _BACKOFF[min(attempt - 1, len(_BACKOFF) - 1)]
            print(f"llm: {type(exc).__name__} on attempt {attempt}/{attempts} "
                  f"({str(exc)[:60]}) — retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _complete_once(alias: str, prompt: str, *, system: str | None = None,
                   temperature: float | None = None, timeout: int = 300,
                   raw: bool = False, stop: list[str] | None = None,
                   max_tokens: int = 512, keep_alive: str = "10m") -> str:
    """One text completion via the alias' backend. Returns the answer text.

    temperature: only the 'ollama' backend can set it. Passing a value to a
    backend that cannot honour it raises instead of silently ignoring it —
    a run must not be documented as "temperature 0" when nothing set it.
    """
    spec = resolve(alias)
    # A serving endpoint is ONE model slot: a second alias against it makes
    # both stages swap the model back and forth, and the timeouts come back as
    # empty answers that a stop rule counts as a parser finding. The lease sits
    # HERE and not in the calling script on purpose — a rule a script has to
    # remember is an intention (endpoint_lease's docstring carries the chain).
    endpoint_lease.acquire(alias, spec.get("endpoints"))
    backend = spec["backend"]

    if backend == "claude-cli":
        if temperature is not None:
            raise ValueError(
                f"alias '{alias}' uses backend 'claude-cli', which has no "
                f"temperature flag — it cannot honour temperature="
                f"{temperature}. Pass temperature=None and document the run "
                f"as backend-default sampling, or use an ollama alias.")
        cmd = ["claude", "-p", prompt, "--model", spec["model"]]
        if system:
            cmd += ["--append-system-prompt", system]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            detail = (r.stderr.strip() or r.stdout.strip() or
                      "no output on stderr or stdout")
            raise BackendError(f"claude-cli exit {r.returncode}: {detail[:300]}")
        return r.stdout.strip()

    if backend == "ollama":
        if raw:
            # /api/generate with raw=true sends the prompt UNTEMPLATED — the
            # model sees exactly our text, the way a paper's own
            # "### Instruction/### Response" scaffold assumes. Through /api/chat
            # ollama would wrap that scaffold in the model's chat template on
            # top, and the model answers in chat register (preambles, meta
            # commentary). A completion needs a stop sequence, or it writes the
            # next instruction itself.
            if system:
                raise ValueError("raw=True sends one untemplated prompt; fold "
                                 "any system text into the prompt itself")
            payload = {"model": spec["model"], "prompt": prompt,
                       "raw": True, "stream": False, "keep_alive": keep_alive}
            # A completion has no natural end: without a token budget it keeps
            # writing until the context is full (a pilot stalled 12 min on one
            # call). CASA bounds theirs at max_length=512.
            options: dict[str, object] = {"num_predict": max_tokens}
            if temperature is not None:
                options["temperature"] = temperature
            if stop:
                options["stop"] = stop
            if options:
                payload["options"] = options
            req = urllib.request.Request(
                _pick_endpoint(spec).rstrip("/") + "/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())["response"].strip()

        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": prompt}]
        # keep_alive: without it ollama evicts the model between two calls
        # (default 5 min) and every call pays a reload — ~13 GB for gpt-oss.
        # That once drove a run into the timeout after 5 of 100 items.
        payload = {"model": spec["model"], "messages": messages,
                   "stream": False, "keep_alive": keep_alive}
        # `num_predict` belongs here TOO. Until 2026-08-19 this branch set
        # only `temperature` and silently dropped `max_tokens` — the
        # /api/generate branch above has always warned about this ("without a
        # token budget it keeps writing until the context is full"), but the
        # very path all experiments take had no cap. It surfaced in a server
        # log: `n_gen = 3520` at a nominal 2048, gpt-oss at ~19 t/s still not
        # done, request aborted after almost three minutes. No caller could
        # set the cap, so every heavy prompt ran into the timeout — and that
        # looked like an overloaded cluster.
        options: dict[str, object] = {"num_predict": max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        if stop:
            options["stop"] = stop
        payload["options"] = options
        req = urllib.request.Request(
            _pick_endpoint(spec).rstrip("/") + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
        message = body.get("message") or {}
        content = (message.get("content") or "").strip()
        # Reasoning models put their thinking trace in its own field. If
        # `content` stays empty while `thinking` is filled, the model thought
        # and said nothing — a MISSING measurement that would come back as an
        # empty string and look like a model answer to the parser. Do not
        # decide here (the caller knows its gold classes), but make it
        # visible: silently lost items are the most expensive error type.
        if not content:
            think = (message.get("thinking") or "").strip()
            print(f"llm: {alias} returned EMPTY content "
                  f"(done_reason={body.get('done_reason')!r}, "
                  f"eval_count={body.get('eval_count')}, "
                  f"thinking={len(think)} chars) — count as unreadable, "
                  f"not as an answer", file=sys.stderr)
        return content

    if backend == "openai":
        # Any OpenAI-compatible server: vLLM, sglang, ... Same completion
        # semantics as the ollama chat path. `keep_alive` does not apply (the
        # server owns model residency); `raw` has no untemplated route here.
        # Model pinning: /v1 exposes no weights digest — the served model id
        # plus the server launch command (revision, quantization) are the pin,
        # both belong in the run config.
        if raw:
            raise ValueError("raw=True needs ollama's /api/generate — the "
                             "OpenAI-compatible API has no untemplated path")
        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": prompt}]
        payload: dict[str, object] = {"model": spec["model"], "messages": messages,
                                      "max_tokens": max_tokens, "stream": False}
        if temperature is not None:
            payload["temperature"] = temperature
        if stop:
            payload["stop"] = stop
        headers = {"Content-Type": "application/json"}
        if spec.get("api_key"):
            headers["Authorization"] = f"Bearer {spec['api_key']}"
        req = urllib.request.Request(
            _pick_endpoint(spec).rstrip("/") + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
        first = (body.get("choices") or [{}])[0]
        message = first.get("message") or {}
        content = (message.get("content") or "").strip()
        # Reasoning models: with a server-side --reasoning-parser the
        # thinking trace sits in its own field (reasoning_content; newer
        # vLLM: reasoning) and content is the bare answer — the same split
        # ollama delivers as "thinking". WITHOUT the flag the trace lands IN
        # content; marker parsers appear to survive that, but parse_letter
        # then reads the first free-standing A/B of the DELIBERATION instead
        # of the answer. models.toml therefore declares `reasoning = true`;
        # content without a trace field is the signature of a server missing
        # the parser flag — fail immediately, no retry changes a server
        # config.
        reasoning = (message.get("reasoning_content")
                     or message.get("reasoning") or "").strip()
        if spec.get("reasoning") and content and not reasoning:
            raise ValueError(
                f"{alias}: reasoning = true, but the answer carries content "
                f"without reasoning_content/reasoning — the server runs "
                f"without --reasoning-parser and mixes the thinking trace "
                f"into the answer. Fix the server cmd (swap-models.toml), or "
                f"set reasoning = false if this model truly writes no trace.")
        if not content:
            print(f"llm: {alias} returned EMPTY content "
                  f"(finish_reason={first.get('finish_reason')!r}, "
                  f"reasoning={len(reasoning)} chars) — count as "
                  f"unreadable, not as an answer", file=sys.stderr)
        return content

    raise ValueError(f"unknown backend '{backend}' for alias '{alias}'")
