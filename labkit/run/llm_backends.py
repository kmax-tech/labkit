"""llm_backends — the wire calls behind `llm.complete`, one per backend.

The Claude CLI (an isolated, cwd-pinned subprocess and its JSON result),
Ollama (raw generate and chat, its options, usage and the prompt-fit
check that refuses a prompt the context would cut), and an
OpenAI-compatible endpoint; the endpoint chosen round-robin across the
configured ones, the auth headers, the per-thread call state
(`CALL_STATE`: endpoint, usage, thinking of the last call) and the
types a call raises or returns (`BackendError`, `PromptTruncated`,
`Usage`). `llm` resolves the alias, retries and records; it calls these.
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
from typing import NamedTuple


def auth_headers(spec: dict) -> dict[str, str]:
    """Authorization header for a served endpoint, or nothing.

    `api_key_env` names the environment variable that holds the key: the
    spec (and with it every run config) records the NAME, the key itself
    never leaves the process. A literal `api_key` still works for servers
    behind a VPN where the key is not a secret — but it is recorded verbatim.
    A named variable that is not set fails loud: a run must not start
    unauthenticated and die after the first 401, or worse, fall back to an
    unauthenticated endpoint nobody chose.
    """
    env = spec.get("api_key_env")
    if env:
        key = os.environ.get(env)
        if not key:
            raise ValueError(
                f"alias '{spec.get('alias', '?')}': api_key_env = {env!r}, but "
                f"{env} is not set in the environment"
            )
        return {"Authorization": f"Bearer {key}"}
    if spec.get("api_key"):
        return {"Authorization": f"Bearer {spec['api_key']}"}
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


def pick_endpoint(spec: dict) -> str:
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
    CALL_STATE.endpoint = url
    return url


def _chat_messages(system: str | None, prompt: str) -> list[dict]:
    """The chat message list: optional system turn, then the user prompt."""
    return ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]


def _post_json(spec: dict, path: str, payload: dict, timeout: int) -> dict:
    """POST `payload` to the alias' endpoint + `path`; the decoded answer."""
    req = urllib.request.Request(
        pick_endpoint(spec).rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **auth_headers(spec)},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def complete_claude_cli(
    alias: str,
    spec: dict,
    prompt: str,
    *,
    system: str | None,
    temperature: float | None,
    timeout: int,
) -> str:
    """`claude -p`, isolated from the operator's settings (CLI_ISOLATION)."""
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
        spec["model"],
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
    return _cli_result(r.stdout)


def _cli_result(stdout: str) -> str:
    """The answer text of a `claude -p --output-format json` reply; its
    `usage` and `total_cost_usd` go to `last_usage()`. Anything but that JSON
    object is a backend failure, named with what came instead."""
    try:
        body = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise BackendError(
            f"claude-cli: stdout is not the JSON reply of --output-format json "
            f"({exc.msg}): {stdout.strip()[:200]!r}"
        ) from exc
    if not isinstance(body, dict) or "result" not in body:
        raise BackendError(
            f"claude-cli: JSON reply without a `result` field: {stdout.strip()[:200]!r}"
        )
    if body.get("is_error"):
        raise BackendError(f"claude-cli: is_error — {str(body['result'])[:300]}")
    usage = body.get("usage") or {}
    counted = [
        usage.get(k)
        for k in (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
    ]
    CALL_STATE.usage = Usage(
        prompt_tokens=sum(int(v) for v in counted if v is not None)
        if any(v is not None for v in counted)
        else None,
        output_tokens=usage.get("output_tokens"),
        cached_tokens=usage.get("cache_read_input_tokens"),
        cost_usd=body.get("total_cost_usd"),
    )
    return str(body["result"]).strip()


#: how long ollama keeps the model loaded after a call. Without it ollama
#: evicts the model between two calls (default 5 min) and every call pays a
#: reload — ~13 GB for gpt-oss; that once drove a run into the timeout after
#: 5 of 100 items. No caller ever set another value (audit 2026-10-13).
OLLAMA_KEEP_ALIVE = "10m"


def _ollama_options(
    spec: dict, temperature: float | None, stop: list[str] | None, max_tokens: int
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
    if "num_ctx" in spec:
        options["num_ctx"] = spec["num_ctx"]
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
    spec: dict,
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
        "model": spec["model"],
        "prompt": prompt,
        "raw": True,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": _ollama_options(spec, temperature, stop, max_tokens),
    }
    body = _post_json(spec, "/api/generate", payload, timeout)
    CALL_STATE.usage = _ollama_usage(body)
    _check_prompt_fit(spec, len(prompt), CALL_STATE.usage)
    return body["response"].strip()


def _ollama_usage(body: dict) -> Usage:
    """ollama counts `prompt_eval_count` and `eval_count`; it omits the
    first when the whole prompt came from its cache, hence None."""
    return Usage(
        prompt_tokens=body.get("prompt_eval_count"),
        output_tokens=body.get("eval_count"),
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


def _check_prompt_fit(spec: dict, prompt_chars: int, usage: Usage) -> None:
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
    alias = spec.get("alias", spec.get("model", "?"))
    window = spec.get("num_ctx")
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
    alias: str,
    spec: dict,
    prompt: str,
    *,
    system: str | None,
    temperature: float | None,
    timeout: int,
    stop: list[str] | None,
    max_tokens: int,
) -> str:
    """ollama /api/chat — the path every templated experiment takes."""
    payload: dict[str, object] = {
        "model": spec["model"],
        "messages": _chat_messages(system, prompt),
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": _ollama_options(spec, temperature, stop, max_tokens),
    }
    body = _post_json(spec, "/api/chat", payload, timeout)
    CALL_STATE.usage = _ollama_usage(body)
    _check_prompt_fit(spec, len(system or "") + len(prompt), CALL_STATE.usage)
    message = body.get("message") or {}
    content = (message.get("content") or "").strip()
    CALL_STATE.thinking = (message.get("thinking") or "").strip()
    if not content:
        _warn_empty(
            alias,
            f"done_reason={body.get('done_reason')!r}, "
            f"eval_count={body.get('eval_count')}, thinking={len(CALL_STATE.thinking)} chars",
        )
    return content


def complete_openai(
    alias: str,
    spec: dict,
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
    if raw:
        raise ValueError(
            "raw=True needs ollama's /api/generate — the "
            "OpenAI-compatible API has no untemplated path"
        )
    payload: dict[str, object] = {
        "model": spec["model"],
        "messages": _chat_messages(system, prompt),
        "max_tokens": max_tokens,
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if stop:
        payload["stop"] = stop
    body = _post_json(spec, "/v1/chat/completions", payload, timeout)
    usage = body.get("usage") or {}
    CALL_STATE.usage = Usage(
        prompt_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
        cost_usd=None,
    )
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
    reasoning = (
        message.get("reasoning_content") or message.get("reasoning") or ""
    ).strip()
    CALL_STATE.thinking = reasoning
    if spec.get("reasoning") and content and not reasoning:
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
