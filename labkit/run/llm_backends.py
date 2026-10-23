"""llm_backends — the wire calls behind `llm.complete`, one per backend.

The Claude CLI (an isolated, cwd-pinned subprocess and its JSON result),
Ollama (raw generate and chat, its options, usage and the prompt-fit
check that refuses a prompt the context would cut), and an
OpenAI-compatible endpoint; the endpoint chosen round-robin across the
configured ones, the auth headers, the per-thread call state
(`CALL_STATE`: endpoint, usage, thinking of the last call) and the
types a call raises or returns (`BackendError`, `PromptTruncated`,
`Usage`). The specs a call is made with are `llm_specs`'. `llm`
resolves the alias, retries and records; it calls these.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import sys
import threading
import urllib.error
import urllib.request
from typing import Any, NamedTuple, cast

from labkit.formats.runs import JsonObject
from labkit.run.llm_specs import ClaudeCliSpec, OllamaSpec, OpenAISpec, ServedSpec


def auth_headers(spec: ServedSpec) -> dict[str, str]:
    """Authorization header for a served endpoint, or nothing.

    `api_key_env` names the environment variable that holds the key: the
    spec (and with it every run config) records the NAME, the key itself
    never leaves the process. A literal `api_key` still works for servers
    behind a VPN where the key is not a secret — but it is recorded verbatim.
    A named variable that is not set fails loud: a run must not start
    unauthenticated and die after the first 401, or worse, fall back to an
    unauthenticated endpoint nobody chose.
    """
    env = spec.api_key_env
    if env:
        key = os.environ.get(env)
        if not key:
            raise ValueError(
                f"alias '{spec.alias}': api_key_env = {env!r}, but "
                f"{env} is not set in the environment"
            )
        return {"Authorization": f"Bearer {key}"}
    if spec.api_key:
        return {"Authorization": f"Bearer {spec.api_key}"}
    return {}


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


class UnprovenAnswer(BackendError):
    """A reply that does not show the requested model as the whole answer's
    writer — another model in it, a safety stop, more than one turn. Not
    retried (`llm.complete`): the request carries it, and each try of an
    audit costs minutes and a dollar; in two probe rounds the second try was
    stopped again."""


class ReplyError(BackendError):
    """A server's reply that is not the shape its API defines — not JSON, cut
    off mid-object, a field missing or of another type — named with the
    backend and the field. Retryable like any BackendError: an HTML error
    page or a reply cut in transit can be gone on the next try; a server
    that always answers so fails after the retries, by name. Before, the
    same replies surfaced as KeyError, AttributeError, TypeError or a
    JSONDecodeError (a ValueError, which labkit-audit read as an area it
    could not stamp) far from the reply (review 2026-10-20)."""


def json_reply(raw: str | bytes, where: str) -> JsonObject:
    """The JSON object a server replied with, or ReplyError naming WHERE
    (the backend and route) and what came instead."""
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        raise ReplyError(
            f"{where}: the reply is not JSON ({exc}): {text.strip()[:200]!r}"
        ) from exc
    if not isinstance(body, dict):
        raise ReplyError(
            f"{where}: the reply is a JSON {type(body).__name__}, not an object"
        )
    return cast(JsonObject, body)


def reply_field(
    body: JsonObject,
    key: str,
    kind: type | tuple[type, ...],
    where: str,
    *,
    required: bool = False,
) -> Any:
    """BODY[KEY] when it is of KIND; None when absent or null and not
    REQUIRED; else ReplyError naming WHERE.KEY and what it holds. A bool is
    no int here: a count of `true` is a broken reply."""
    value = body.get(key)
    if value is None:
        if required:
            raise ReplyError(f"{where}: the reply has no `{key}`")
        return None
    kinds = kind if isinstance(kind, tuple) else (kind,)
    if not isinstance(value, kinds) or (isinstance(value, bool) and bool not in kinds):
        names = " or ".join(k.__name__ for k in kinds)
        raise ReplyError(f"{where}: `{key}` = {value!r:.80}, not {names}")
    return value


def _count(body: JsonObject, key: str, where: str) -> int | None:
    """A token count of the reply: a non-negative integer, or None when the
    server reported none."""
    value = reply_field(body, key, int, where)
    if value is not None and value < 0:
        raise ReplyError(f"{where}: `{key}` = {value}, not a count")
    return value


class PromptTruncated(RuntimeError):
    """The server read less of the prompt than was sent — not retryable.

    ollama fits a prompt longer than its context window by dropping tokens
    and answers anyway; the reply looks like any other. A retry reads the
    same cut prompt, so this error stays out of _TRANSIENT.
    """


# Round-robin state per alias, and the endpoint of the most recent attempt.
# Two endpoints are two instrument instances (batch invariance) — callers that
# want per-row provenance read last_endpoint() right after a successful call.
# The endpoint is THREAD-local: under parallel.run each worker sees its own
# call's endpoint, never a neighbour's (the writer thread stamps via the
# record's _prov, prepared in the worker — see parallel._stamped).
_RR: dict[str, int] = {}


_RR_LOCK = threading.Lock()


CALL_STATE = threading.local()


class Usage(NamedTuple):
    """The token counts of one completion, as the backend reported them;
    None where it reported nothing. `prompt_tokens` is the whole prompt the
    model read, cache hits included (claude-cli: input + cache creation +
    cache read; ollama: `prompt_eval_count`; OpenAI-style: `prompt_tokens`);
    `cached_tokens` is the part served from a prompt cache (claude-cli:
    cache read; OpenAI-style: `prompt_tokens_details.cached_tokens`; ollama
    says nothing); `cost_usd` only where the backend prices the call
    (claude-cli `total_cost_usd`)."""

    prompt_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    cost_usd: float | None

    def describe(self) -> str:
        """One line for a log: `prompt 61,234 (8,671 cached) · output 1,902 · 0.41 USD`."""

        def n(v: int | None) -> str:
            return "n/a" if v is None else f"{v:,}"

        cached = (
            "" if self.cached_tokens is None else f" ({n(self.cached_tokens)} cached)"
        )
        cost = "" if self.cost_usd is None else f" · {self.cost_usd:.2f} USD"
        return f"prompt {n(self.prompt_tokens)}{cached} · output {n(self.output_tokens)}{cost}"


NO_USAGE = Usage(None, None, None, None)


# `claude -p` is an agent harness, not an inference API: by default every
# call inherits the operator's ~/.claude/settings.json AND both CLAUDE.md
# files (user + project) into its system prompt. An empty setting-sources
# list drops all of them while OAuth keeps working (verified CLI 2.1.267;
# `--system-prompt` does NOT drop CLAUDE.md, an empty CLAUDE_CONFIG_DIR
# drops the login). 2026-09-23: `language: German` in the operator's
# settings had 45/432 English scenario prompts answered in German.
# No tools either: a judgement is an inference, not an agent session. With
# its read-only tools left on, a long prompt that says "read <file>" can send
# the CLI off to its cwd instead of answering from the inlined text, and the
# answer then depends on what lies there (preflight audit of labkit-paper
# area 03, 2026-10-06). `--tools ""` disables the whole built-in set.
CLI_ISOLATION = ["--setting-sources", "", "--tools", ""]


#: `claude -p` runs from a neutral directory, never from the repo: the CLI
#: is a harness and reads its cwd (project files, git state) into the
#: conversation. A cold agent observed answers mentioning "labkit" and
#: "Python code" for a one-word judgement when called from the repo root,
#: 3 of 5 times, clean from /tmp (2026-10-05, not reproduced in 7 tries —
#: a sketch, but the cwd is not part of the instrument either way).
_CLI_CWD = tempfile.gettempdir()


def _cli_run(
    cmd: list[str], timeout: float | None, stdin: str | None = None
) -> subprocess.CompletedProcess:
    """The one place `claude -p` is spawned: isolated flags, neutral cwd, the
    prompt on STDIN. As an argument it hit Linux's 128 kB cap per argv entry
    (`OSError: Argument list too long`) — an audit prompt is 200 kB, and
    only macOS let it through (audit 2026-10-15)."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=_CLI_CWD, input=stdin
    )


def cli_version() -> str:
    """The installed Claude CLI's version, or "unknown" when it does not answer."""
    try:
        r = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=30
        )
        return r.stdout.strip().split()[0] if r.returncode == 0 else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def pick_endpoint(spec: ServedSpec) -> str:
    """Next endpoint for this call: round-robin over spec['endpoints'].

    A single endpoint behaves exactly as before. With several, each call
    advances the counter — and because `complete()` re-enters here on retry,
    a dropped server naturally fails over to the next one.
    """
    eps = spec.endpoints
    if len(eps) == 1:
        url = eps[0]
    else:
        with _RR_LOCK:
            i = _RR.get(spec.alias, 0)
            _RR[spec.alias] = i + 1
        url = eps[i % len(eps)]
    CALL_STATE.endpoint = url
    return url


def _chat_messages(system: str | None, prompt: str) -> list[dict]:
    """The chat message list: optional system turn, then the user prompt."""
    return ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]


def _post_json(spec: ServedSpec, path: str, payload: dict, timeout: int) -> dict:
    """POST `payload` to the alias' endpoint + `path`; the decoded answer."""
    req = urllib.request.Request(
        pick_endpoint(spec).rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **auth_headers(spec)},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json_reply(resp.read(), f"{spec.alias} {path}")


def complete_claude_cli(
    spec: ClaudeCliSpec,
    prompt: str,
    *,
    system: str | None,
    temperature: float | None,
    timeout: int,
    raw: bool,
    stop: list[str] | None,
    max_tokens: int | None = None,
) -> str:
    """`claude -p`, isolated from the operator's settings (CLI_ISOLATION).
    Refuses what the CLI cannot honour — a temperature, an untemplated
    prompt, a stop sequence, a token cap — instead of dropping it: the CLI
    has no flag for any of them, and a run must not be documented with a
    setting nothing applied."""
    alias = spec.alias
    if max_tokens is not None:
        raise ValueError(
            f"alias '{alias}' uses backend 'claude-cli', which has no token cap "
            f"— it cannot honour max_tokens={max_tokens}. Pass none (the CLI's "
            f"own limit holds), or use an ollama or openai alias."
        )
    if raw or stop:
        raise ValueError(
            f"alias '{alias}' uses backend 'claude-cli', which has no "
            f"{'untemplated route (raw=True)' if raw else 'stop sequences'} — "
            f"it would be dropped without a word; use an ollama or openai alias"
        )
    if temperature is not None:
        raise ValueError(
            f"alias '{alias}' uses backend 'claude-cli', which has no "
            f"temperature flag — it cannot honour temperature="
            f"{temperature}. Pass temperature=None and document the run "
            f"as backend-default sampling, or use an ollama or openai alias."
        )
    cmd = [
        "claude",
        "-p",  # the prompt comes on stdin (_cli_run)
        "--model",
        spec.model,
        "--output-format",
        "json",
        *CLI_ISOLATION,
    ]
    if system:
        cmd += ["--append-system-prompt", system]
    r = _cli_run(cmd, timeout, stdin=prompt)
    if r.returncode != 0:
        detail = r.stderr.strip() or r.stdout.strip() or "no output on stderr or stdout"
        raise BackendError(f"claude-cli exit {r.returncode}: {detail[:300]}")
    return _cli_result(r.stdout, spec.model)


def _cli_result(stdout: str, model: str) -> str:
    """The answer text of a `claude -p --output-format json` reply, written
    whole by MODEL; its `usage` and `total_cost_usd` go to `last_usage()`.
    Anything but that JSON object is a backend failure, named with what
    came instead; so is a reply that does not show MODEL as its only writer
    (`_cli_provenance`). Every failure names the reply's evidence fields
    (`_cli_evidence`)."""
    where = "claude-cli --output-format json"
    body = json_reply(stdout, where)
    seen = _cli_evidence(body)
    try:
        # the provenance before `is_error`: a stopped answer may come
        # flagged as an error, and an error is retried, a switch is not
        is_error = reply_field(body, "is_error", bool, where)
        _cli_provenance(body, model, where, is_error=bool(is_error))
        result = reply_field(body, "result", str, where, required=True)
    except UnprovenAnswer as exc:
        raise UnprovenAnswer(f"{exc} [{seen}]") from exc
    except ReplyError as exc:
        raise ReplyError(f"{exc} [{seen}]") from exc
    if is_error:
        raise BackendError(f"claude-cli: is_error — {result[:300]} [{seen}]")
    usage = reply_field(body, "usage", dict, where) or {}
    counted = [
        _count(usage, k, f"{where} usage")
        for k in (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
    ]
    CALL_STATE.usage = Usage(
        prompt_tokens=sum(v for v in counted if v is not None)
        if any(v is not None for v in counted)
        else None,
        output_tokens=_count(usage, "output_tokens", f"{where} usage"),
        cached_tokens=counted[2],
        cost_usd=reply_field(body, "total_cost_usd", (int, float), where),
    )
    return result.strip()


def _cli_evidence(body: JsonObject) -> str:
    """The reply's fields that say who answered and how it ended, as they
    came — for every claude-cli failure message, so a refusal shows what
    the CLI reported."""
    usage = body.get("modelUsage")
    models = sorted(usage) if isinstance(usage, dict) else usage
    return ", ".join(
        f"{k}={v!r}"
        for k, v in (
            ("subtype", body.get("subtype")),
            ("stop_reason", body.get("stop_reason")),
            ("is_error", body.get("is_error")),
            ("safety_stops", body.get("safety_stops")),
            ("num_turns", body.get("num_turns")),
            ("models", models),
        )
    )


def _cli_provenance(
    body: JsonObject, model: str, where: str, *, is_error: bool
) -> None:
    """Raises UnprovenAnswer unless the reply shows no model but MODEL and —
    for an answer, not an error — MODEL used in one turn (`modelUsage`,
    `num_turns`, both required: a missing one is a ReplyError — no proof,
    no answer), and no safety stop where the CLI counts them
    (`safety_stops`, absent before CLI 2.1.304), and no reply that ended in a
    refusal (`stop_reason`). A safety classifier can
    stop the requested model mid-answer; the CLI then lets another model
    continue and `result` holds only the continuation — the requested
    model's id stays on the record for text another model wrote, and a part
    reads as the whole. CLI 2.1.285 reported such a reply as
    `subtype = "success"`, `is_error = false`, `num_turns = 2`, both models
    in `modelUsage`, no `safety_stops` (fit probe on 97e6470). An error
    (IS_ERROR) without a stop or another model is left to the caller: an
    overloaded server is retried."""
    used = sorted(reply_field(body, "modelUsage", dict, where, required=True))
    if reply_field(body, "stop_reason", str, where) == "refusal":
        # a stop nothing continued: one turn, one model, and no answer —
        # not yet seen; a guard, the field's value there is unverified
        raise UnprovenAnswer(
            f"claude-cli: {model}'s answer ended in a refusal (`stop_reason`) "
            f"— no answer of {model}"
        )
    stops = reply_field(body, "safety_stops", int, where)
    if stops:
        raise UnprovenAnswer(
            f"claude-cli: {stops} safety stop(s) in the answer of {model} "
            f"(models used: {', '.join(used) or 'none'}) — the text may be a "
            f"continuation by another model, not {model}'s whole answer"
        )
    if set(used) - {model}:
        raise UnprovenAnswer(
            f"claude-cli: requested {model}, the reply was written by "
            f"{', '.join(used)} — not an answer of {model}"
        )
    if is_error:
        return
    if used != [model]:
        raise UnprovenAnswer(
            f"claude-cli: requested {model}, the reply names no model that "
            f"wrote it — not an answer of {model}"
        )
    turns = reply_field(body, "num_turns", int, where, required=True)
    if turns != 1:
        raise UnprovenAnswer(
            f"claude-cli: {turns} turns where one answer takes one (no tools) "
            f"— `result` holds only the last"
        )


#: how long ollama keeps the model loaded after a call. Without it ollama
#: evicts the model between two calls (default 5 min) and every call pays a
#: reload — ~13 GB for gpt-oss; that once drove a run into the timeout after
#: 5 of 100 items. No caller ever set another value (audit 2026-10-13).
OLLAMA_KEEP_ALIVE = "10m"


def _ollama_options(
    spec: OllamaSpec, temperature: float | None, stop: list[str] | None, max_tokens: int
) -> dict[str, object]:
    """The `options` of an ollama request, for /api/generate and /api/chat
    alike. `num_predict` is never left out: a completion has no natural end
    and without a token budget it writes until the context is full (a pilot
    stalled 12 min on one call; until 2026-08-19 the chat path — the one
    every experiment takes — set only `temperature`, and a server log showed
    `n_gen = 3520` at a nominal 2048, the request aborted after almost three
    minutes, which looked like an overloaded cluster)."""
    options: dict[str, object] = {"num_predict": max_tokens}
    if temperature is not None:
        options["temperature"] = temperature
    if stop:
        options["stop"] = stop
    if spec.num_ctx is not None:
        options["num_ctx"] = spec.num_ctx
    return options


def _warn_empty(alias: str, detail: str) -> None:
    """Said aloud, decided by the caller: a reasoning model that put its
    trace in its own field and nothing in `content` thought and said
    nothing — a MISSING measurement that would come back as an empty string
    and look like a model answer to the parser. Silently lost items are the
    most expensive error type."""
    print(
        f"llm: {alias} returned EMPTY content ({detail}) — count as unreadable, "
        f"not as an answer",
        file=sys.stderr,
    )


def complete_ollama_raw(
    spec: OllamaSpec,
    prompt: str,
    *,
    system: str | None,
    temperature: float | None,
    timeout: int,
    stop: list[str] | None,
    max_tokens: int,
) -> str:
    """ollama /api/generate with raw=true: the prompt goes untemplated."""
    # /api/generate with raw=true sends the prompt UNTEMPLATED — the
    # model sees exactly our text, the way a paper's own
    # "### Instruction/### Response" scaffold assumes. Through /api/chat
    # ollama would wrap that scaffold in the model's chat template on
    # top, and the model answers in chat register (preambles, meta
    # commentary). A completion needs a stop sequence, or it writes the
    # next instruction itself.
    if system:
        raise ValueError(
            "raw=True sends one untemplated prompt; fold "
            "any system text into the prompt itself"
        )
    payload: dict[str, object] = {
        "model": spec.model,
        "prompt": prompt,
        "raw": True,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": _ollama_options(spec, temperature, stop, max_tokens),
    }
    body = _post_json(spec, "/api/generate", payload, timeout)
    where = f"{spec.alias} /api/generate"
    CALL_STATE.usage = _ollama_usage(body, where)
    _check_prompt_fit(spec, len(prompt), CALL_STATE.usage)
    return reply_field(body, "response", str, where, required=True).strip()


def _ollama_usage(body: JsonObject, where: str) -> Usage:
    """ollama counts `prompt_eval_count` and `eval_count`; it omits the
    first when the whole prompt came from its cache, hence None."""
    return Usage(
        prompt_tokens=_count(body, "prompt_eval_count", where),
        output_tokens=_count(body, "eval_count", where),
        cached_tokens=None,
        cost_usd=None,
    )


#: characters per prompt token above which a prompt counts as cut. Tokenizers
#: average 3-6 characters per token on English and code (repetitive English
#: read 5.2 on gpt-oss:20b, leguin, 2026-10-11); a ratio of 10 means
#: more than half the prompt never reached the model. Floor, not estimate:
#: a prompt cut by a third passes — the exact check needs `num_ctx`.
TRUNCATION_CHARS_PER_TOKEN = 10


#: prompts shorter than this are not checked by ratio: a short prompt fits
#: every context window, and chat-template tokens skew its ratio
TRUNCATION_MIN_CHARS = 4000


def _check_prompt_fit(spec: OllamaSpec, prompt_chars: int, usage: Usage) -> None:
    """Raise PromptTruncated when ollama read less than the whole prompt.

    ollama cuts a prompt longer than its context window and answers what is
    left; nothing in the reply but `prompt_eval_count` shows it. Two tests:
    with `num_ctx` set, a count that reaches the window is a cut (ollama
    0.23.1 trims to exactly the window and answers with HTTP 200: a
    25,272-character prompt at num_ctx 2048 read 2,048, leguin, 2026-10-11); without it, a count far below the prompt's
    length (TRUNCATION_CHARS_PER_TOKEN). A reply without the count (whole
    prompt from cache) cannot be judged and passes.
    """
    read = usage.prompt_tokens
    if read is None or read <= 0:
        return
    alias = spec.alias
    window = spec.num_ctx
    if window is not None and read >= window:
        raise PromptTruncated(
            f"{alias}: ollama read {read:,} prompt tokens, the whole num_ctx "
            f"window of {window:,} — the prompt was cut to fit, and nothing is "
            f"left to answer with. Raise num_ctx in models.toml or shorten the prompt."
        )
    if (
        prompt_chars >= TRUNCATION_MIN_CHARS
        and prompt_chars / read > TRUNCATION_CHARS_PER_TOKEN
    ):
        hint = (
            f"num_ctx is {window:,}"
            if window is not None
            else "no num_ctx is set, so the server default applies"
        )
        raise PromptTruncated(
            f"{alias}: ollama read {read:,} prompt tokens of a {prompt_chars:,}-"
            f"character prompt ({prompt_chars / read:.0f} characters per token; "
            f"a whole prompt reads at 3-6) — the server cut it to its context "
            f"window, and {hint}. Set num_ctx in models.toml."
        )


def complete_ollama_chat(
    spec: OllamaSpec,
    prompt: str,
    *,
    system: str | None,
    temperature: float | None,
    timeout: int,
    stop: list[str] | None,
    max_tokens: int,
) -> str:
    """ollama /api/chat — the path every templated experiment takes."""
    alias = spec.alias
    payload: dict[str, object] = {
        "model": spec.model,
        "messages": _chat_messages(system, prompt),
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": _ollama_options(spec, temperature, stop, max_tokens),
    }
    body = _post_json(spec, "/api/chat", payload, timeout)
    where = f"{alias} /api/chat"
    CALL_STATE.usage = _ollama_usage(body, where)
    _check_prompt_fit(spec, len(system or "") + len(prompt), CALL_STATE.usage)
    message = reply_field(body, "message", dict, where, required=True)
    content = (reply_field(message, "content", str, f"{where} message") or "").strip()
    thinking = reply_field(message, "thinking", str, f"{where} message") or ""
    CALL_STATE.thinking = thinking.strip()
    if not content:
        _warn_empty(
            alias,
            f"done_reason={body.get('done_reason')!r}, "
            f"eval_count={CALL_STATE.usage.output_tokens}, "
            f"thinking={len(CALL_STATE.thinking)} chars",
        )
    return content


def complete_openai(
    spec: OpenAISpec,
    prompt: str,
    *,
    system: str | None,
    temperature: float | None,
    timeout: int,
    raw: bool,
    stop: list[str] | None,
    max_tokens: int,
) -> str:
    """Any OpenAI-compatible server (vLLM, sglang, …) via /v1/chat/completions."""
    # Any OpenAI-compatible server: vLLM, sglang, ... Same completion
    # semantics as the ollama chat path. `keep_alive` does not apply (the
    # server owns model residency); `raw` has no untemplated route here.
    # Model pinning: /v1 exposes no weights digest — the served model id
    # plus the server launch command (revision, quantization) are the pin,
    # both belong in the run config.
    alias = spec.alias
    if raw:
        raise ValueError(
            "raw=True needs ollama's /api/generate — the "
            "OpenAI-compatible API has no untemplated path"
        )
    payload: dict[str, object] = {
        "model": spec.model,
        "messages": _chat_messages(system, prompt),
        "max_tokens": max_tokens,
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if stop:
        payload["stop"] = stop
    body = _post_json(spec, "/v1/chat/completions", payload, timeout)
    where = f"{alias} /v1/chat/completions"
    usage = reply_field(body, "usage", dict, where) or {}
    details = reply_field(usage, "prompt_tokens_details", dict, f"{where} usage") or {}
    CALL_STATE.usage = Usage(
        prompt_tokens=_count(usage, "prompt_tokens", f"{where} usage"),
        output_tokens=_count(usage, "completion_tokens", f"{where} usage"),
        cached_tokens=_count(details, "cached_tokens", f"{where} usage"),
        cost_usd=None,
    )
    choices = reply_field(body, "choices", list, where, required=True)
    if not choices or not isinstance(choices[0], dict):
        raise ReplyError(f"{where}: `choices` = {choices!r:.80}, not a list of objects")
    first = cast(JsonObject, choices[0])
    message = reply_field(first, "message", dict, f"{where} choices[0]", required=True)
    at = f"{where} message"
    content = (reply_field(message, "content", str, at) or "").strip()
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
    reasoning = (
        reply_field(message, "reasoning_content", str, at)
        or reply_field(message, "reasoning", str, at)
        or ""
    ).strip()
    CALL_STATE.thinking = reasoning
    if spec.reasoning and content and not reasoning:
        raise ValueError(
            f"{alias}: reasoning = true, but the answer carries content "
            f"without reasoning_content/reasoning — the server runs "
            f"without --reasoning-parser and mixes the thinking trace "
            f"into the answer. Fix the server cmd (swap-models.toml), or "
            f"set reasoning = false if this model truly writes no trace."
        )
    if not content:
        _warn_empty(
            alias,
            f"finish_reason={first.get('finish_reason')!r}, reasoning={len(reasoning)} chars",
        )
    return content
