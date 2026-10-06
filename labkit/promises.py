"""promises — the one home of the promise alphabet and the promise block.

A promise is one checked registration of a protocol: a criterion that
judges, an admissibility condition that releases or withholds the verdict,
a branch that says what follows from it. Each has an id in the protocol
text (`[C1]`) and a key in the run's metrics (`c1_pass`).

    C  criterion      constrains the reported outcome: which value of which
                      metric counts as support for the hypothesis
    A  admissibility  determines whether any C verdict may be issued,
                      conditional on an outcome-neutral check (control,
                      anchor, yield, coverage, resolution) passing in the
                      same run
    B  branch         binds a pre-specified condition on the results to the
                      conclusion or follow-up analysis it licenses

The legacy letters K (criterion), S (stop rule), W (fork) and N (null
condition) stay readable in prose; they do not map one-to-one onto C/A/B
(see the thread note `versprechen-kategorien-c-a-b`), so nothing here
translates them. The promise block takes only the new letters.

Letters chosen against collision with metric names: F (`f1`), P (`p1`),
R (`r1`), Q (`q1`), H (`h1`) are standard metric or hypothesis names and
are never ids.

**The promise block** — promises as data instead of prose. A protocol may
carry exactly one fenced ```toml block with `[[promise]]` tables:

    [[promise]]
    id = "C1"
    key = "c1_pass"
    sentence = "macro-F1 of the judge >= MIN_F1 on the test split"
    scope = ["scripts/01_measure.py:evaluate", "lib/text.py"]
    constants = { MIN_F1 = 0.70 }

`scope` is DECLARED, not derived: the author names the implementation
region the promise rests on (a file, or `file:function` for one top-level
function), paths relative to the protocol's directory. The declared-scope
hash (`declared_scope_sha`; not the area audit stamp `scope-sha`)
states exactly this and no more: **the implementation region declared for
this promise was byte-identical in the run that produced the number.** It
does not state that this region is all the code the number depends on, and
nothing here states that the code implements the promise correctly — that
is static evidence and agent audit (thread note `scope-hash-aussage`).

Everything in this module is the "guaranteed" tier: exact, mechanical,
silent on a correct input, loud on a malformed one.
"""

from __future__ import annotations

import ast
import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: the letters of the promise block, and what each one is
KINDS = {"C": "criterion", "A": "admissibility", "B": "branch"}
#: pre-2026-10 letters, still recognised in prose and metrics keys
LEGACY_KINDS = {"K": "criterion", "S": "stop rule", "W": "fork",
                "N": "null condition"}

_LETTERS = "".join(KINDS) + "".join(LEGACY_KINDS)
#: an id anywhere in protocol prose: `[C1]`, `[k2]`
ID_IN_PROTOCOL = re.compile(rf"\[([{_LETTERS}]\d+)\]", re.I)
#: a metrics key in the id namespace: bare `c1` or `c1_<suffix>`
ID_KEY = re.compile(rf"^([{_LETTERS.lower()}]\d+)(?:_.*)?$")
#: a metrics key that is unmistakably an intent key (suffix required)
INTENT_KEY = re.compile(rf"^[{_LETTERS.lower()}]\d+_")
#: an id as a string literal in source: `"c1_pass"`, `'s1'`
ID_LITERAL = re.compile(rf"""['"]([{_LETTERS.lower()}]\d+)(_[a-z0-9_]*)?['"]""")

#: a criterion's denominator key: `c1_n`, legacy `k1_n` — the count a
#: criterion was computed over, held by `finalize` to the recorded inputs
CRITERION_N_KEY = re.compile(r"^[ck]\d+_n$")

_BLOCK_ID = re.compile(rf"^[{''.join(KINDS)}]\d+$")
_FENCED_TOML = re.compile(r"^```toml[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_ALLOWED_FIELDS = {"id", "key", "sentence", "scope", "constants"}

#: same width as the area audit stamp (`scope_sha.DIGEST_CHARS`)
DIGEST_CHARS = 12


class PromiseError(ValueError):
    """The promise block is malformed; the message names the field."""


@dataclass(frozen=True)
class Promise:
    id: str                         # "C1"
    kind: str                       # "criterion" | "admissibility" | "branch"
    key: str                        # metrics key that reports it
    sentence: str                   # the promise in one sentence
    scope: tuple[str, ...]          # declared implementation region
    constants: dict[str, int | float | str | bool]


@dataclass(frozen=True)
class PromiseBlock:
    promises: tuple[Promise, ...]
    sha: str                        # digest of the block text as written

    def by_id(self) -> dict[str, Promise]:
        return {p.id: p for p in self.promises}


def registered_ids(text: str) -> set[str]:
    """Ids promised anywhere in the protocol prose, lowercased."""
    return {m.group(1).lower() for m in ID_IN_PROTOCOL.finditer(text)}


def reported_ids(metrics: dict) -> set[str]:
    """Ids a metrics dict reports (bare id or id_suffix keys), lowercased."""
    out = set()
    for key in metrics:
        m = ID_KEY.match(str(key))
        if m:
            out.add(m.group(1))
    return out


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:DIGEST_CHARS]


def parse_block(text: str) -> PromiseBlock | None:
    """The protocol's promise block, or None if it has none.

    Raises PromiseError on anything malformed: two blocks, invalid TOML,
    an unknown field, a legacy or unknown letter, a key outside its id's
    namespace, a duplicate id, an empty scope, a non-scalar constant.
    """
    blocks = [m.group(1) for m in _FENCED_TOML.finditer(text)
              if re.search(r"^\[\[promise\]\]", m.group(1), re.M)]
    if not blocks:
        return None
    if len(blocks) > 1:
        raise PromiseError(f"{len(blocks)} ```toml blocks with [[promise]] — "
                           f"a protocol has exactly one promise block")
    raw = blocks[0]
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise PromiseError(f"promise block is not valid TOML: {exc}") from exc
    extra = set(data) - {"promise"}
    if extra:
        raise PromiseError(f"promise block has top-level keys {sorted(extra)} "
                           f"— only [[promise]] tables belong there")
    entries = data["promise"]
    if not isinstance(entries, list):
        raise PromiseError("`promise` must be an array of tables: [[promise]]")

    out: list[Promise] = []
    seen: set[str] = set()
    for n, e in enumerate(entries, 1):
        where = f"[[promise]] #{n}"
        unknown = set(e) - _ALLOWED_FIELDS
        if unknown:
            raise PromiseError(f"{where}: unknown field(s) {sorted(unknown)}; "
                               f"allowed: {sorted(_ALLOWED_FIELDS)}")
        for field in ("id", "key", "sentence", "scope"):
            if field not in e:
                raise PromiseError(f"{where}: missing `{field}`")
        pid = e["id"]
        if not isinstance(pid, str) or not _BLOCK_ID.match(pid):
            raise PromiseError(
                f"{where}: id {pid!r} is not C<n>, A<n> or B<n> — the block "
                f"takes only the new letters (legacy K/S/W/N stay in prose)")
        where = f"[[promise]] {pid}"
        if pid in seen:
            raise PromiseError(f"{where}: duplicate id")
        seen.add(pid)
        key = e["key"]
        if not isinstance(key, str) or (key != pid.lower()
                                         and not key.startswith(pid.lower() + "_")):
            raise PromiseError(f"{where}: key {key!r} is outside the id's "
                               f"namespace — expected '{pid.lower()}' or "
                               f"'{pid.lower()}_<suffix>'")
        sentence = e["sentence"]
        if not isinstance(sentence, str) or not sentence.strip():
            raise PromiseError(f"{where}: `sentence` is empty")
        scope = e["scope"]
        if (not isinstance(scope, list) or not scope
                or not all(isinstance(s, str) and s.strip() for s in scope)):
            raise PromiseError(f"{where}: `scope` must be a non-empty list of "
                               f"'file' or 'file:function' strings")
        constants = e.get("constants", {})
        if not isinstance(constants, dict):
            raise PromiseError(f"{where}: `constants` must be a table")
        for name, value in constants.items():
            if not isinstance(value, (int, float, str, bool)):
                raise PromiseError(f"{where}: constant {name} is "
                                   f"{type(value).__name__} — only scalars")
        out.append(Promise(id=pid, kind=KINDS[pid[0]], key=key,
                           sentence=sentence.strip(), scope=tuple(scope),
                           constants=dict(constants)))
    return PromiseBlock(promises=tuple(out), sha=_digest(raw.encode("utf-8")))


def prose_mismatch(text: str, block: PromiseBlock) -> tuple[list[str], list[str]]:
    """(new-letter ids in prose but not in the block, block ids not in prose).

    Legacy letters are not compared: they have no place in the block.
    """
    prose = {i.upper() for i in registered_ids(text) if i[0].upper() in KINDS}
    ids = {p.id for p in block.promises}
    return sorted(prose - ids), sorted(ids - prose)


def load(protocol: Path) -> PromiseBlock:
    """The promise block of `protocol`; raises if it has none.

    For scripts: `promises.load(PROTOCOL).by_id()["C1"].constants["MIN_F1"]`
    reads the threshold from the frozen protocol instead of a second copy
    in the code.
    """
    block = parse_block(protocol.read_text(encoding="utf-8"))
    if block is None:
        raise PromiseError(f"{protocol}: no promise block (```toml with [[promise]])")
    return block


def constants(protocol: Path, promise_id: str) -> dict[str, int | float | str | bool]:
    """The constants one promise declares, read from the protocol."""
    by_id = load(protocol).by_id()
    if promise_id not in by_id:
        raise PromiseError(f"{protocol}: no promise {promise_id!r}; "
                           f"declared: {sorted(by_id)}")
    return dict(by_id[promise_id].constants)


def _function_source(path: Path, name: str) -> str:
    """Source text of the top-level function or class `name` in `path`."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in tree.body:
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name == name):
            segment = ast.get_source_segment(source, node)
            assert segment is not None, f"{path}:{name} has no source segment"
            return segment
    raise PromiseError(f"{path}: no top-level function or class {name!r} — the "
                       f"declared scope names code that does not exist")


def declared_scope_sha(base: Path, scope: tuple[str, ...]) -> str:
    """Digest over the declared scope, entries resolved against `base`.

    A `file` entry covers the file's bytes; a `file:function` entry covers
    only that function's source (decorators excluded), so an edit to a
    neighbouring function leaves the stamp alone. Each entry contributes
    its own spelling plus its content digest, so adding, dropping or
    renaming an entry changes the stamp too. A missing file or function is
    a PromiseError, never an empty digest.
    """
    h = hashlib.sha256()
    for entry in sorted(scope):
        file_part, _, func = entry.partition(":")
        path = base / file_part
        if not path.is_file():
            raise PromiseError(f"scope entry {entry!r}: no such file {path}")
        content = (_function_source(path, func).encode("utf-8") if func
                   else path.read_bytes())
        h.update(entry.encode("utf-8") + b"\n")
        h.update(hashlib.sha256(content).hexdigest().encode() + b"\n")
    return h.hexdigest()[:DIGEST_CHARS]


def scope_drift(recorded: dict | None, base: Path) -> list[str]:
    """`[C1] old → new` for every promise whose declared scope changed since
    the run. `recorded` is the run's config.json `promises` (None: the run
    predates the block — nothing to compare)."""
    if recorded is None:
        return []
    out = []
    for pid, rec in sorted(recorded["ids"].items()):
        now = declared_scope_sha(base, tuple(rec["scope"]))
        if now != rec["declared_scope_sha"]:
            out.append(f"[{pid}] {rec['declared_scope_sha']} → {now}")
    return out


def block_drift(recorded: dict | None, block: PromiseBlock | None) -> str | None:
    """Why the protocol's promise block (`block`, as parsed now) is not the
    one the run recorded, or None when it is (or neither side has one)."""
    if recorded is None:
        return (None if block is None else
                f"the run recorded no promise block — it ran before the block "
                f"existed or outside runlog; rerun so the number is bound to "
                f"the promises (block {block.sha})")
    if block is None:
        return (f"the run ran under promise block {recorded['block_sha']}, the "
                f"protocol now carries none — the promises were removed after "
                f"the run")
    if block.sha != recorded["block_sha"]:
        return (f"ran under promise block {recorded['block_sha']}, the protocol "
                f"now carries {block.sha} — the promises changed after the run")
    return None


def snapshot(block: PromiseBlock, base: Path) -> dict:
    """What a run records about its promises (config.json `promises`)."""
    return {"block_sha": block.sha,
            "ids": {p.id: {"key": p.key, "constants": p.constants,
                           "scope": list(p.scope),
                           "declared_scope_sha": declared_scope_sha(base, p.scope)}
                    for p in block.promises}}
