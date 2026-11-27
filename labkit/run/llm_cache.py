"""llm_cache — a lab's cache of raw model answers, across runs.

The cache keeps the model's raw answer (`llm_backends.Response`: text,
reasoning trace, finish reason, usage, endpoint, decoded reply) under a key
of everything that changes the answer. Parsing stays with the caller, so a
corrected parser applies to cached answers at once.

The key (`key_inputs`) is built from:
  * the answering model, `llm.identity` — backend and model, for ollama
    with the weights' digest; not the alias, which `models.toml` can point
    elsewhere, and not the endpoint, since a host can change while serving
    the same weights;
  * the spec fields that change the answer and `identity` leaves out:
    claude-cli `input`, openai `reasoning`, ollama `num_ctx`;
  * the system prompt and the prompt, `raw`, `stop`, the temperature and
    the token cap as sent (none given: `llm.DEFAULT_MAX_TOKENS` for a
    served backend);
  * `CACHE_VERSION`.
Not in it: the alias, endpoints, API keys, the parser. `llm.complete`
sends no seed, so none enters the key.

The lab allows the cache in its `models.toml` (`[llm_cache] enabled =
true`, `llm.cache_declared`; LAB-069 No LLM cache unless the lab declares
one): a cache hit repeats an answer, so a spread measured over cached
answers is 0. Without that declaration `Cache` refuses to open.

Three modes, fixed when a run opens the cache (`Cache`):

    normal   a hit is read; a miss asks the model and stores the answer
    replay   only reads; a miss raises `CacheMiss`, no model is asked — the
             processing runs again on the answers an earlier run got
    repeat   the run repeats another (`runlog.run(repeat_of=…)`): the
             cache is neither read nor written — the model is asked anew,
             and the answer an earlier run stored stays what a replay of
             that run gets

Not cacheable: an ollama model whose weights digest is unknown
(`unavailable`) or differs across endpoints (`MISMATCH:…`) — the key would
name no weights. Such a call goes to the model in normal and repeat mode
and says why on stderr; a replay refuses it.

Stand-in answers: `store_stand_in` writes a fixed answer, not a model's,
under the key a call with the same arguments gets — for a trial without a
model, replayed through `Cache`. Its entry says `stand_in: true`, a hit on
it says so in the call log, finalize names a run that read one
(`model_check.stand_in_findings`), and the generated result line of
a run resting on one opens with a stand-in label
(`result_render.stand_in_label`).

Where: `<lab root>/cache/llm/` unless given (the lab root holds
`models.toml`), one file per key, `<key[:2]>/<key>.json`, written once — the
first answer under a key is the one every later read gets
(`files.write_once`). The directory carries a `.gitignore` of `*`: the
answers live beside the experiment, not in git.

The run record: `llm-cache.json` (cache version, mode, directory), written
when the run opens the cache, and `llm-calls.jsonl`, one line per call —
key, alias, `hit`, for a hit its origin (the run that stored it, and when,
and whether it is a stand-in),
the usage (of the original call for a hit), and why a call was not cached.
`runs.read_model_calls` reads it back; `fresh_usage` sums the calls that asked the
model: a hit adds no cost.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from labkit.formats import console
from labkit.formats.files import write_atomic, write_once
from labkit.formats.repo import lab_root
from labkit.formats.digests import digest
from labkit.formats.runs import (
    LLM_CACHE_FILE,
    LLM_CALLS_FILE,
    JsonObject,
    now_stamp,
    read_model_calls,
)
from labkit.run import llm
from labkit.run.llm_backends import NO_USAGE, Response, Usage
from labkit.run.llm_specs import ClaudeCliSpec, OllamaSpec, OpenAISpec
from labkit.run.runlog import Run

#: the entry format and the key's construction; a change makes every
#: stored answer a miss, never a wrong hit
CACHE_VERSION = 1

Mode = Literal["normal", "replay", "repeat"]

#: an ollama weights digest that names weights (hex), unlike `unavailable`
#: or `MISMATCH:…`
_DIGEST = re.compile(r"[0-9a-f]+")


class CacheMiss(LookupError):
    """A replay asked for an answer the cache does not hold, or for a call
    it cannot cache; no model was asked."""


class CacheCorruptionError(ValueError):
    """A cache entry exists but is not one: not JSON, another version, or
    stored under another key. Raised instead of read as a miss — a miss
    would ask the model again beside an answer nobody looked at."""


@dataclass(frozen=True)
class Origin:
    """Where a cached answer came from: the run that stored it (None when
    it was stored outside a run), when, and whether it is a stand-in — a
    fixed answer `store_stand_in` wrote, not a model's (its run is None)."""

    run: str | None
    written: str
    stand_in: bool = False


@dataclass(frozen=True)
class Answer:
    """One call through the cache: the model's raw `response` — for a hit
    the stored one, its usage the original call's — and the `origin` of a
    hit, None when the model was asked."""

    response: Response
    origin: Origin | None


def uncacheable(alias: str) -> str | None:
    """Why ALIAS's answers cannot be cached, or None: an ollama model whose
    weights digest is unknown or differs across endpoints."""
    used = llm.spec(alias)
    if isinstance(used, OllamaSpec) and not _DIGEST.fullmatch(used.model_digest):
        return (
            f"{alias}: ollama reports no single weights digest "
            f"({used.model_digest}) — a key would name no weights"
        )
    return None


def key_inputs(
    alias: str,
    prompt: str,
    *,
    system: str | None,
    temperature: float | None,
    max_tokens: int | None,
    raw: bool,
    stop: list[str] | None,
) -> JsonObject:
    """What the key of this call is built from (module docstring): the
    answering model, the spec fields that change the answer, the prompts
    and the sampling values as sent, and `CACHE_VERSION`."""
    used = llm.spec(alias)
    if isinstance(used, ClaudeCliSpec):
        answer_changing: JsonObject = {"input": used.input}
    elif isinstance(used, OpenAISpec):
        answer_changing = {"reasoning": used.reasoning}
    else:
        answer_changing = {"num_ctx": used.num_ctx}
    if max_tokens is None and not isinstance(used, ClaudeCliSpec):
        max_tokens = llm.DEFAULT_MAX_TOKENS
    return {
        "cache_version": CACHE_VERSION,
        "model": llm.identity(alias),
        "spec": answer_changing,
        "system": system,
        "prompt": prompt,
        "raw": raw,
        "stop": stop,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def cache_key(inputs: JsonObject) -> str:
    """The sha256 of INPUTS (`key_inputs`) in canonical JSON."""
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return digest(canonical.encode("utf-8"), chars=None)


def entry_path(root: Path, key: str) -> Path:
    """Where the entry under KEY lies in the cache directory ROOT:
    `<key[:2]>/<key>.json`."""
    return root / key[:2] / f"{key}.json"


def _require_declared() -> None:
    """Ends with SystemExit and the sentence when the lab has not declared
    the cache (`llm.cache_declared`) — before anything is written."""
    if not llm.cache_declared():
        raise SystemExit(
            "llm_cache: the lab has not declared a cache — a cached answer "
            "repeats instead of measuring; set [llm_cache] enabled = true in "
            "models.toml to allow it (LAB-069 No LLM cache unless the lab "
            "declares one)"
        )


def _make_root(root: Path) -> None:
    """Create the cache directory ROOT with its `.gitignore` of `*`, so its
    entries stay out of git, unless they are there."""
    root.mkdir(parents=True, exist_ok=True)
    ignore = root / ".gitignore"
    if not ignore.exists():
        write_atomic(ignore, "*\n")


def default_root(start: Path) -> Path:
    """`cache/llm/` under the lab root of START (the directory holding
    `models.toml`). Raises FileNotFoundError when no lab root is above."""
    root = lab_root(start)
    if root is None:
        raise FileNotFoundError(
            f"no models.toml above {start} — the cache lives in the lab repo; "
            f"pass Cache(..., root=DIR)"
        )
    return root / "cache" / "llm"


class Cache:
    """The cache as one run uses it (module docstring): its mode, its
    directory, and the run's `llm-calls.jsonl`.

    Opening it writes `llm-cache.json` into RUN's directory. The mode is
    `repeat` when RUN repeats another (`Run.draw` is set), else `replay`
    with REPLAY, else `normal`. ROOT defaults to `default_root` of the
    run's area. Ends with SystemExit and the sentence when the lab has not
    declared the cache (`llm.cache_declared`) — a measure script's loud end,
    before anything is written. Raises ValueError for a malformed
    `[llm_cache]` table, a replay asked of a repeat, and a second opening
    in the same run with another mode or directory."""

    def __init__(
        self, run: Run, *, replay: bool = False, root: Path | None = None
    ) -> None:
        _require_declared()
        if run.draw is not None and replay:
            raise ValueError(
                f"run {run.run_id} repeats another run: a repeat asks the model "
                f"anew and cannot replay stored answers"
            )
        self.mode: Mode = (
            "repeat" if run.draw is not None else "replay" if replay else "normal"
        )
        self.root = (root or default_root(run.base)).resolve()
        self.run_id = run.run_id
        self._calls = run.dir / LLM_CALLS_FILE
        self._lock = threading.Lock()
        record = {
            "cache_version": CACHE_VERSION,
            "mode": self.mode,
            "root": str(self.root),
        }
        path = run.dir / LLM_CACHE_FILE
        if path.exists():
            opened = json.loads(path.read_text(encoding="utf-8"))
            if opened != record:
                raise ValueError(
                    f"run {run.run_id} opened the cache as {opened}; a second "
                    f"opening as {record} would mix two caches in one record"
                )
        else:
            write_atomic(path, json.dumps(record, ensure_ascii=False, indent=2))
        _make_root(self.root)

    def complete(
        self,
        alias: str,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        timeout: int = 300,
        attempts: int = 6,
        raw: bool = False,
        stop: list[str] | None = None,
        max_tokens: int | None = None,
    ) -> Answer:
        """One completion through the cache, as the mode says; arguments,
        retries and errors as `llm.complete`'s. Raises CacheMiss in a replay
        for an answer the cache lacks or cannot hold, CacheCorruptionError
        for an entry that is not one. Appends the call's line to the run's
        `llm-calls.jsonl`."""
        why_not = uncacheable(alias)
        if why_not is not None:
            if self.mode == "replay":
                raise CacheMiss(f"{why_not}; a replay asks no model")
            console.progress("llm_cache", f"not cached — {why_not}")
        inputs = key_inputs(
            alias,
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            raw=raw,
            stop=stop,
        )
        key = cache_key(inputs)
        path = entry_path(self.root, key)
        if why_not is None and self.mode != "repeat":
            stored = read_entry(path, key)
            if stored is not None:
                self._log(key, alias, stored)
                return stored
            if self.mode == "replay":
                raise CacheMiss(
                    f"{alias}: no stored answer under key {key[:16]}… in {self.root} "
                    f"— a replay asks no model; run normally to fill the cache"
                )
        response = llm.complete_response(
            alias,
            prompt,
            system=system,
            temperature=temperature,
            timeout=timeout,
            attempts=attempts,
            raw=raw,
            stop=stop,
            max_tokens=max_tokens,
        )
        if why_not is None and self.mode == "normal":
            path.parent.mkdir(parents=True, exist_ok=True)
            write_once(
                path, entry_text(key, inputs, response, self.run_id, stand_in=False)
            )
        answer = Answer(response, None)
        self._log(key, alias, answer, why_not)
        return answer

    def _log(
        self, key: str, alias: str, answer: Answer, uncached: str | None = None
    ) -> None:
        """One line of the run's `llm-calls.jsonl` for this call."""
        origin = answer.origin
        line = {
            "key": key,
            "alias": alias,
            "hit": origin is not None,
            "origin": None
            if origin is None
            else {
                "run": origin.run,
                "written": origin.written,
                "stand_in": origin.stand_in,
            },
            "usage": answer.response.usage._asdict(),
            "uncached": uncached,
        }
        with self._lock, self._calls.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def store_stand_in(
    root: Path,
    alias: str,
    prompt: str,
    answer: str,
    *,
    system: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    raw: bool = False,
    stop: list[str] | None = None,
) -> Path:
    """Store ANSWER as a stand-in for what ALIAS would answer to PROMPT, in
    the cache directory ROOT (`default_root` of the lab), so that a replay
    (`Cache(run, replay=True)`) answers that call from it — a trial of a
    pipeline without a model. Returns the entry's path.

    The key comes from `key_inputs` and `cache_key`, the functions
    `Cache.complete` builds its key with, given the same arguments with
    the same defaults; no second construction of the key exists. The
    arguments are the call as the caller declares it will be made. Where
    the real call sends anything else — another prompt, one more line
    ending, another temperature, a system prompt — its key differs, and
    the replay raises `CacheMiss`: a mismatch is a miss, never a silent hit.

    The entry is marked as a stand-in (`stand_in: true`, no run): it holds
    no model's answer, so its response has no finish reason, no usage, no
    endpoint and no reply body. A hit on it carries `Origin.stand_in`, and
    the run's call log says so; finalize names a run that read stand-ins
    (`model_check.stand_in_findings`), and the generated result line
    labels a result resting on them (`result_render.stand_in_label`).

    Side effects: creates ROOT with its `.gitignore` of `*`, as `Cache`
    does, and writes the entry once (`files.write_once`). A stand-in with
    the same answer already under the key is left as it is.

    Raises:
        SystemExit: The lab has not declared the cache (`llm.cache_declared`),
            before anything is written; a replay would refuse to open.
        ValueError: ALIAS cannot be cached (`uncacheable`), or another
            entry stands under the key — a model's answer, or a stand-in
            with another answer; the cache keeps the first answer under a
            key, so that entry must be moved aside first.
        CacheCorruptionError: The entry under the key is not one.
    """
    _require_declared()
    why_not = uncacheable(alias)
    if why_not is not None:
        raise ValueError(f"{why_not}; a replay could not answer from a stand-in")
    inputs = key_inputs(
        alias,
        prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        raw=raw,
        stop=stop,
    )
    key = cache_key(inputs)
    root = root.resolve()
    _make_root(root)
    path = entry_path(root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    response = Response(
        text=answer,
        thinking="",
        finish_reason=None,
        usage=NO_USAGE,
        endpoint="",
        body=None,
    )
    if write_once(path, entry_text(key, inputs, response, None, stand_in=True)):
        return path
    stored = read_entry(path, key)
    assert stored is not None and stored.origin is not None, "write_once found a file"
    if stored.origin.stand_in and stored.response.text == answer:
        return path
    held = (
        "a stand-in with another answer"
        if stored.origin.stand_in
        else f"a model's answer stored by run {stored.origin.run}"
        if stored.origin.run is not None
        else "an answer stored outside any run, not marked as a stand-in"
    )
    raise ValueError(
        f"{path}: {held} stands under this key — the cache keeps the first "
        f"answer under a key; move that file aside to store this stand-in"
    )


def entry_text(
    key: str,
    inputs: JsonObject,
    response: Response,
    run: str | None,
    *,
    stand_in: bool,
) -> str:
    """The stored entry of one answer: version, key, the key's inputs, the
    raw response, the run that stored it, with the time, and whether it is
    a stand-in (`store_stand_in`) rather than a model's answer."""
    return json.dumps(
        {
            "cache_version": CACHE_VERSION,
            "key": key,
            "inputs": inputs,
            "response": {
                "text": response.text,
                "thinking": response.thinking,
                "finish_reason": response.finish_reason,
                "usage": response.usage._asdict(),
                "endpoint": response.endpoint,
                "body": response.body,
            },
            "run": run,
            "written": now_stamp(),
            "stand_in": stand_in,
        },
        ensure_ascii=False,
        indent=2,
    )


def read_entry(path: Path, key: str) -> Answer | None:
    """The answer stored at PATH under KEY as a hit, None when PATH does
    not exist. An entry without `stand_in` (written before 0.115.0, or by
    hand) is not marked as a stand-in — which shows no model gave it
    either. Raises CacheCorruptionError naming the file for anything
    else than an entry of `CACHE_VERSION` under KEY, and for a stand-in
    that names a run."""
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry["cache_version"] != CACHE_VERSION or entry["key"] != key:
            raise ValueError(
                f"version {entry['cache_version']}, key {str(entry['key'])[:16]}…"
            )
        stored = entry["response"]
        response = Response(
            text=stored["text"],
            thinking=stored["thinking"],
            finish_reason=stored["finish_reason"],
            usage=Usage(**stored["usage"]),
            endpoint=stored["endpoint"],
            body=stored["body"],
        )
        stand_in = entry.get("stand_in", False)
        if not isinstance(stand_in, bool):
            raise ValueError("`stand_in` is not true or false")
        if stand_in and entry["run"] is not None:
            raise ValueError(f"a stand-in names run {entry['run']}")
        return Answer(response, Origin(entry["run"], entry["written"], stand_in))
    except (ValueError, KeyError, TypeError) as exc:
        raise CacheCorruptionError(
            f"{path}: not a cache entry of version {CACHE_VERSION} under its key "
            f"({exc}) — move it aside and run again; it is never read as a miss"
        ) from exc


def fresh_usage(run_dir: Path) -> Usage:
    """The usage of RUN_DIR's calls that asked the model — its
    `llm-calls.jsonl` (`runs.read_model_calls`) without the hits, summed per
    field; a field no such call reported stays None. NO_USAGE-shaped (all
    None) without calls. Raises ValueError as `read_model_calls` does."""
    totals: dict[str, int | float | None] = dict.fromkeys(Usage._fields)
    for call in read_model_calls(run_dir):
        if call.hit:
            continue
        for name, value in call.usage.items():
            if value is not None:
                totals[name] = (totals[name] or 0) + value
    return Usage(**totals)  # type: ignore[arg-type]  # each field keeps its type
