"""One alias at a time per serving endpoint — the lock that batch.Store isn't.

A serving endpoint is a GPU slot, not a service. On a swap proxy several
aliases resolve to the same slot: asking for an alias that is not loaded
unloads the running model and loads the wanted one (measured 2026-09-08:
~5 minutes per swap). Two stages against the same endpoint with DIFFERENT
aliases therefore do not run in parallel — they evict each other, over and
over.

Why this is a defect and not an inconvenience. The damage does not stay in
the wallclock; it arrives in a reported number:

    swap thrashing -> llm.complete runs into timeouts -> exhausted retries
    return empty answers -> rounds without a parsed mechanism -> the stop
    rule "more than 2 of 96 rounds empty => the parser is the finding"
    counts them

That rule then measures operational noise and calls it parser quality
(2026-09-08: a judge test fired next to a running probe did exactly this;
it was filed as an operator slip, which is what a missing interlock looks
like from the inside).

What was mistaken for protection: `batch.Store` takes a lock on the OUTPUT
FILE — it says nothing about who is using the model. And "stages stay
staggered" is a sentence in a protocol and a code comment, i.e. an
intention. Any second process breaks it: another terminal, another area, a
test fired alongside.

The rule here, in one line: **same alias may share, a different alias is
refused — and a process never blocks itself.** One script that runs the
generator stage and then the judge stage holds two aliases in one pid: that IS
the staggering the rule wants, so own-pid records are not conflicts. Sharing an alias costs throughput, never a swap; a second alias
costs the run. Refusal is immediate (SystemExit) rather than a wait — a
queue in front of a five-minute swap is the same trap with a nicer name.

Scope, honestly: the lease is a local directory, so it interlocks the
processes on THIS machine. A run started from another host is invisible to
it. Ambiguity resolves conservatively: a holder whose liveness cannot be
decided counts as alive — a wrong refusal costs a message, a wrong
admission costs the run.

Deliberate exception, like `--no-verify`: `LABKIT_NO_ENDPOINT_LEASE=1`.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

try:
    from labkit import runlog
except ImportError:                      # vendored flat copy (student repos)
    import runlog

_HELD: set[tuple[str, str]] = set()      # (endpoint, alias) held by this process
_FILES: dict[tuple[str, str], Path] = {}
_MUTEX = threading.Lock()


def lease_dir() -> Path:
    """Where leases live. `LABKIT_LEASE_DIR` overrides (tests, shared FS)."""
    env = os.environ.get("LABKIT_LEASE_DIR")
    return Path(env) if env else Path.home() / ".labkit" / "leases"


def _slug(endpoint: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", endpoint).strip("_") or "default"


def _script() -> str:
    return Path(sys.argv[0]).name or "python"


def holders(endpoint: str) -> list[dict]:
    """Live lease records for this endpoint; stale ones are removed on the way.

    A record whose process is gone is deleted (a crashed run must not block
    the slot forever). A record whose liveness is undecidable is kept and
    returned — see the module docstring on the failure direction.
    """
    d = lease_dir() / _slug(endpoint)
    out: list[dict] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            f.unlink(missing_ok=True)
            continue
        if rec.get("pid") == os.getpid():
            out.append(rec)
            continue
        if runlog.is_alive(rec.get("pid"), rec.get("script")) is False:
            f.unlink(missing_ok=True)
            continue
        out.append(rec)
    return out


def _conflict(endpoint: str, alias: str) -> dict | None:
    """The oldest live holder of a DIFFERENT alias, or None."""
    others = [h for h in holders(endpoint)
              if h.get("alias") != alias and h.get("pid") != os.getpid()]
    return min(others, key=lambda h: h.get("started", "")) if others else None


def _refuse(endpoint: str, alias: str, other: dict) -> None:
    since = other.get("started", "?")
    raise SystemExit(
        f"llm: endpoint {endpoint} is leased to alias '{other.get('alias')}' "
        f"(pid {other.get('pid')}, {other.get('script')}, since {since}) — "
        f"refusing to run '{alias}' against it.\n"
        f"  This endpoint is ONE model slot: a second alias makes both stages "
        f"swap the model back and forth (~5 min each), the timeouts come back "
        f"as empty answers, and a stop rule counts them as a parser finding.\n"
        f"  Let that stage finish, use the same alias, or — if you really mean "
        f"to share the slot — set LABKIT_NO_ENDPOINT_LEASE=1.")


def acquire(alias: str, endpoints: list[str] | None) -> None:
    """Lease every endpoint this alias may use. Idempotent, refuses on conflict.

    Called by `llm.complete` on every call; the work happens once per
    (endpoint, alias) and per process. Backends without an endpoint
    (claude-cli) lease nothing.
    """
    if os.environ.get("LABKIT_NO_ENDPOINT_LEASE"):
        return
    for endpoint in endpoints or []:
        key = (endpoint, alias)
        with _MUTEX:
            if key in _HELD:
                continue
            other = _conflict(endpoint, alias)
            if other is not None:
                _refuse(endpoint, alias, other)
            d = lease_dir() / _slug(endpoint)
            d.mkdir(parents=True, exist_ok=True)
            rec = {"alias": alias, "pid": os.getpid(), "script": _script(),
                   "endpoint": endpoint,
                   "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "argv": " ".join(sys.argv)[:300]}
            f = d / f"{_slug(alias)}.{os.getpid()}.json"
            f.write_text(json.dumps(rec), encoding="utf-8")
            # Two processes can pass the check at the same moment. Re-read
            # after writing: whoever is not the oldest live holder yields.
            # A check without this second look is a lock with a race in it.
            other = _conflict(endpoint, alias)
            if other is not None and other.get("started", "") <= rec["started"]:
                f.unlink(missing_ok=True)
                _refuse(endpoint, alias, other)
            _HELD.add(key)
            _FILES[key] = f


def release_all() -> None:
    """Drop this process' leases. Registered atexit; safe to call twice."""
    with _MUTEX:
        for key, f in list(_FILES.items()):
            f.unlink(missing_ok=True)
            _FILES.pop(key, None)
            _HELD.discard(key)


atexit.register(release_all)
