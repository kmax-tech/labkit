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

The earlier letters K, S, W and N are not read (labkit 0.48 broke with
them; protocols that carry them are read with labkit 0.47). They do not map
one-to-one onto C/A/B, so nothing translates them.

Letters chosen against collision with metric names: F (`f1`), P (`p1`),
R (`r1`), Q (`q1`), H (`h1`) are standard metric or hypothesis names and
are never ids.

**The promise block** — promises as data instead of prose. The protocol's
one fenced ```toml block (`protocol_block.py`; its `[protocol]` table is the
head) may carry `[[promise]]` tables:

    [[promise]]
    id = "C1"
    key = "c1_pass"
    sentence = "macro-F1 of the judge >= min_f1 on the test split"
    scope = ["scripts/01_measure.py:evaluate", "lib/text.py"]
    constants = { min_f1 = 0.70 }

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
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import protocol_block, runs, scope_sha

#: the letters of the promise block, and what each one is
KINDS = {"C": "criterion", "A": "admissibility", "B": "branch"}
#: A constant is named like the config key it is recorded under — lowercase
#: snake_case, so the name IS the mapping between protocol and run record
#: (2026-10-08: `min_f1` in the block against `min_f1` in the record would
#: need a second table nobody checks).
CONSTANT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_LETTERS = "".join(KINDS)
#: an id anywhere in protocol prose: `[C1]`, `[k2]`
ID_IN_PROTOCOL = re.compile(rf"\[([{_LETTERS}]\d+)\]", re.I)


def registers_ids(text: str) -> bool:
    """Does the protocol's prose name any promise id? A count at seconds
    names none and owes no [[promise]] table (0.87.1)."""
    return ID_IN_PROTOCOL.search(text) is not None


#: an id in the letters labkit 0.47 read — detected, never read: a protocol
#: carrying them would otherwise pass every id check with nothing checked
EARLIER_ID = re.compile(r"\[([KSWN]\d+)\]")
#: a metrics key in the id namespace: bare `c1` or `c1_<suffix>`
ID_KEY = re.compile(rf"^([{_LETTERS.lower()}]\d+)(?:_.*)?$")
#: a metrics key that is unmistakably an intent key (suffix required)
INTENT_KEY = re.compile(rf"^[{_LETTERS.lower()}]\d+_")
#: an id as a string literal in source: `"c1_pass"`, `'s1'`
ID_LITERAL = re.compile(rf"""['"]([{_LETTERS.lower()}]\d+)(_[a-z0-9_]*)?['"]""")

#: a criterion's denominator key: `c1_n` — the count a criterion was
#: computed over, held by `finalize` to the recorded inputs
CRITERION_N_KEY = re.compile(r"^c\d+_n$")

_BLOCK_ID = re.compile(rf"^[{''.join(KINDS)}]\d+$")
_ALLOWED_FIELDS = {"id", "key", "sentence", "scope", "constants"}

#: what `block_sha` is a digest of — recorded with it, so a run from an
#: earlier format is told apart instead of reported as changed promises
DIGEST_FORMAT = "promises-normalized-json"
#: what an audit record names as the promise block of a protocol that
#: declares no [[promise]] tables (a count at seconds)
NO_BLOCK = "none"


def block_stamp(text: str) -> str:
    """The protocol's promise block as an audit record names it: the digest
    of its [[promise]] tables (`PromiseTables.sha`), or NO_BLOCK when it
    declares none. Raises PromiseError on a malformed block, like
    `parse_block` — an audit of promises nobody can read binds nothing."""
    block = parse_block(text)
    return NO_BLOCK if block is None else block.sha


class PromiseError(ValueError):
    """The promise block is malformed; the message names the field."""


@dataclass(frozen=True)
class Promise:
    """One promise of a protocol to the code: its id, the metrics key that reports it, its sentence, scope and constants."""

    id: str  # "C1"
    kind: str  # "criterion" | "admissibility" | "branch"
    key: str  # metrics key that reports it
    sentence: str  # the promise in one sentence
    scope: tuple[str, ...]  # declared implementation region
    constants: dict[str, int | float | str | bool]


@dataclass(frozen=True)
class PromiseTables:
    """A protocol's `[[promise]]` tables, parsed, with their digest."""

    promises: tuple[Promise, ...]
    sha: str  # digest of the [[promise]] tables (canonical JSON), not the head

    def by_id(self) -> dict[str, Promise]:
        """The promises keyed by their id."""
        return {p.id: p for p in self.promises}


def ids_in_prose(text: str) -> set[str]:
    """Ids written anywhere in the protocol prose (`[C1]`), lowercased — the
    prose side; the data side is the [[promise]] tables (`PromiseTables`).
    `reported_ids` is the metrics side."""
    return {m.group(1).lower() for m in ID_IN_PROTOCOL.finditer(text)}


def earlier_ids(text: str) -> list[str]:
    """Ids in the earlier letters K/S/W/N, as written — each one a promise
    no check reads. Callers refuse them; nothing translates them (the
    letters do not map one-to-one onto C/A/B)."""
    return sorted(set(EARLIER_ID.findall(text)))


EARLIER_IDS_HELP = (
    "the letters K/S/W/N are not read since labkit 0.48 — "
    "re-register the promises as [C]/[A]/[B] by the separation "
    "rule (docs/promise-block.md), or check this protocol with labkit 0.47"
)


def key_kind(key: str) -> str | None:
    """The kind a metrics key belongs to by its letter — "criterion",
    "admissibility", "branch" — or None outside the id namespace. The one
    way to ask "is this an [A] key": two tools re-spelled the letters
    (`^a\\d+_`, `[ca]`) and would have gone silent on the next change of the
    alphabet, as 0.48.0 was (audit 2026-10-15)."""
    m = ID_KEY.match(key)
    return KINDS[m.group(1)[0].upper()] if m else None


def reported_ids(metrics: Mapping[str, object]) -> set[str]:
    """Ids a metrics dict reports (bare id or id_suffix keys), lowercased."""
    out: set[str] = set()
    for key in metrics:
        m = ID_KEY.match(str(key))
        if m:
            out.add(m.group(1))
    return out


def is_block_id(name: str) -> bool:
    """Is NAME a promise id as a [[promise]] table spells it (`C1`, `A2`)?"""
    return bool(_BLOCK_ID.match(name))


def parse_block(text: str) -> PromiseTables | None:  # noqa: C901 complexity baseline 2026-10-08
    """The protocol's promises, or None if its block declares none.

    Raises PromiseError on anything malformed: invalid TOML, an unknown
    field, an unknown letter, a key outside its id's namespace, a duplicate
    id, an empty scope, a non-scalar constant. The digest covers the
    promises only, not the head: freezing or stamping the audit line must
    not read as a changed promise.
    """
    try:
        data = protocol_block.parse_toml_block(text)
    except protocol_block.BlockError as exc:
        raise PromiseError(str(exc)) from exc
    if "promise" not in data:
        return None
    entries = data["promise"]
    if not isinstance(entries, list):
        raise PromiseError("`promise` must be an array of tables: [[promise]]")

    out: list[Promise] = []
    seen: set[str] = set()
    constant_home: dict[str, str] = {}  # constant name -> the promise that declares it
    for n, e in enumerate(entries, 1):
        where = f"[[promise]] #{n}"
        if not isinstance(e, dict):
            raise PromiseError(
                f"{where}: {e!r} is not a table — each promise is a "
                f"[[promise]] table with id, key, sentence, scope"
            )
        unknown = set(e) - _ALLOWED_FIELDS
        if unknown:
            raise PromiseError(
                f"{where}: unknown field(s) {sorted(unknown)}; "
                f"allowed: {sorted(_ALLOWED_FIELDS)}"
            )
        for field in ("id", "key", "sentence", "scope"):
            if field not in e:
                raise PromiseError(f"{where}: missing `{field}`")
        pid = e["id"]
        if not isinstance(pid, str) or not _BLOCK_ID.match(pid):
            raise PromiseError(f"{where}: id {pid!r} is not C<n>, A<n> or B<n>")
        where = f"[[promise]] {pid}"
        if pid in seen:
            raise PromiseError(f"{where}: duplicate id")
        seen.add(pid)
        key = e["key"]
        if not isinstance(key, str) or (
            key != pid.lower() and not key.startswith(pid.lower() + "_")
        ):
            raise PromiseError(
                f"{where}: key {key!r} is outside the id's "
                f"namespace — expected '{pid.lower()}' or "
                f"'{pid.lower()}_<suffix>'"
            )
        sentence = e["sentence"]
        if not isinstance(sentence, str) or not sentence.strip():
            raise PromiseError(f"{where}: `sentence` is empty")
        scope = e["scope"]
        if (
            not isinstance(scope, list)
            or not scope
            or not all(isinstance(s, str) and s.strip() for s in scope)
        ):
            raise PromiseError(
                f"{where}: `scope` must be a non-empty list of "
                f"'file' or 'file:function' strings"
            )
        absolute = [s for s in scope if Path(s.partition(":")[0]).is_absolute()]
        if absolute:
            raise PromiseError(
                f"{where}: scope {absolute} is absolute — scopes are "
                f"relative to the protocol's directory, so the "
                f"declaration travels with the repo"
            )
        constants = e.get("constants", {})
        if not isinstance(constants, dict):
            raise PromiseError(f"{where}: `constants` must be a table")
        for name, value in constants.items():
            if not isinstance(value, (int, float, str, bool)):
                raise PromiseError(
                    f"{where}: constant {name} is {type(value).__name__} — only scalars"
                )
            if not CONSTANT_NAME.match(name):
                raise PromiseError(
                    f"{where}: constant {name!r} — a constant is named like the "
                    f"config key it is recorded under: lowercase snake_case "
                    f"(`margin`, `max_empty`)"
                )
            if name in constant_home:
                raise PromiseError(
                    f"{where}: constant {name} already stands in [[promise]] "
                    f"{constant_home[name]} — a constant has one home"
                )
            constant_home[name] = pid
        out.append(
            Promise(
                id=pid,
                kind=KINDS[pid[0]],
                key=key,
                sentence=sentence.strip(),
                scope=tuple(scope),
                constants=dict(constants),
            )
        )
    # over the promises as read, not as spelled: a stripped sentence, a
    # sorted scope and a missing `constants` mean the same promise
    canonical = json.dumps(
        [
            {
                "id": q.id,
                "key": q.key,
                "sentence": q.sentence,
                "scope": sorted(q.scope),
                "constants": q.constants,
            }
            for q in out
        ],
        sort_keys=True,
        ensure_ascii=False,
    )
    return PromiseTables(
        promises=tuple(out), sha=scope_sha.digest(canonical.encode("utf-8"))
    )


def prose_mismatch(text: str, block: PromiseTables) -> tuple[list[str], list[str]]:
    """(new-letter ids in prose but not in the block, block ids not in prose)."""
    prose = {i.upper() for i in ids_in_prose(text)}
    ids = {p.id for p in block.promises}
    return sorted(prose - ids), sorted(ids - prose)


def load(protocol: Path) -> PromiseTables:
    """The promise block of `protocol`; raises if it has none.

    For scripts: `promises.load(PROTOCOL).by_id()["C1"].constants["min_f1"]`
    reads the threshold from the frozen protocol instead of a second copy
    in the code.
    """
    block = parse_block(protocol.read_text(encoding="utf-8"))
    if block is None:
        raise PromiseError(f"{protocol}: no [[promise]] tables in its ```toml block")
    return block


def constants(protocol: Path, promise_id: str) -> dict[str, int | float | str | bool]:
    """The constants one promise declares, read from the protocol."""
    by_id = load(protocol).by_id()
    if promise_id not in by_id:
        raise PromiseError(
            f"{protocol}: no promise {promise_id!r}; declared: {sorted(by_id)}"
        )
    return dict(by_id[promise_id].constants)


def all_constants(block: PromiseTables) -> dict[str, int | float | str | bool]:
    """Every constant the block declares, as one dict — collision-free by the
    parser's guarantee (a name stands in one promise). What a script passes
    to its config object: `MeasureConfig(model=MODEL, **all_constants(load(PROTOCOL)))`."""
    out: dict[str, int | float | str | bool] = {}
    for p in block.promises:
        out.update(p.constants)
    return out


def placeholder_sentences(block: PromiseTables) -> list[str]:
    """The ids whose `sentence` is still a stamp placeholder: the whole value
    one `<…>`, as `labkit-init exp` writes it."""
    return [
        p.id
        for p in block.promises
        if p.sentence.startswith("<") and p.sentence.endswith(">")
    ]


def promise_tables_owed(
    block: PromiseTables | None, *, frozen: bool, full_run: bool, registers: bool = True
) -> str | None:
    """Why a protocol owes its [[promise]] tables, or None — the one home of
    the rule (standard 0.19) for protocol-check, preflight, runlog and
    finalize. The table:

        frozen = true            → owed (the freeze is the registration)
        registers = False and not frozen (the prose names no [C]/[A]/[B]
            id — a plain count at seconds, 0.87.1) → not owed: nothing to hold
        full_run (runlog run_kind='measurement') → owed
        otherwise (an unfrozen pilot) → not owed

    Where the tables are owed, a sentence still holding the stamp's `<…>`
    placeholder is a table not yet written (`placeholder_sentences`): frozen,
    it registered nothing (cloud judge probe, 2026-10-14: three placeholder
    sentences frozen, hashed into the run's block digest, passed every gate).
    An unfrozen pilot may carry them.

    "Block" elsewhere (`protocol_block.block_text`, `parse_toml_block`)
    means the whole ```toml block, [protocol] head included; this function
    and `PromiseTables` mean the [[promise]] tables alone."""
    if not (frozen or full_run):
        return None
    if block is not None:
        open_ids = placeholder_sentences(block)
        if not open_ids:
            return None
        because = (
            "frozen = true" if frozen else "a full run is held to the registration"
        )
        return (
            f"{because}, but [[promise]] {', '.join(open_ids)} still carries the "
            f"stamp's `<…>` sentence — state each promise explicitly in one "
            f"sentence in its table"
        )
    if not registers and not frozen:
        return None  # a full run of a count: nothing registered, nothing to hold
    because = "frozen = true" if frozen else "a full run is held to the registration"
    return (
        f"{because}, but the protocol declares no [[promise]] table — the "
        f"registration a run is held to is data, not prose (standard 0.19: "
        f"no run starts under it; `labkit-init exp` stamps the tables)"
    )


@dataclass(frozen=True)
class ConstantRecord:
    """One registered constant held against a run's config.

    Attributes:
        promise_id: The promise that declares it ("C1").
        name: The constant's name — the config key of the same name.
        promised: The value the protocol registers.
        recorded: The value the run's config carries under that name, None if none.
        state: "equal", "different" or "missing". Equal is type-strict:
            `True` is not `1`, `1` is not `1.0` — a threshold's type is part
            of what was registered.
    """

    promise_id: str
    name: str
    promised: object
    recorded: object | None
    state: str


def constant_records(block: PromiseTables, run_config: dict) -> list[ConstantRecord]:
    """Every registered constant with its state against `run_config` — the one
    reading for runlog's refusal (before mkdir), intent-check's blocker and
    the `labkit-params` view."""
    out = []
    for p in block.promises:
        for name, value in p.constants.items():
            if name not in run_config:
                out.append(ConstantRecord(p.id, name, value, None, "missing"))
                continue
            got = run_config[name]
            same = runs.as_stored(got) == runs.as_stored(value)
            out.append(
                ConstantRecord(p.id, name, value, got, "equal" if same else "different")
            )
    return out


def _top_level_names(node: ast.stmt) -> set[str]:
    """The names a top-level statement binds: a `def` or `class`, a plain
    assignment's names, an import's aliases."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in node.names}
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    return {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}


def _function_source(path: Path, name: str) -> str:
    """Source text of the top-level function or class `name` in `path`.
    A name the module binds more than once at the top level (a second
    `def`, an assignment, an import) is refused: Python runs the last
    binding, and hashing the first `def` let the code that computes the
    number change under an unmoved stamp (review 2026-10-20)."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise PromiseError(
            f"{path}: cannot read {name!r} from it ({exc.__class__.__name__}: "
            f"{exc}) — the declared scope must be parseable code"
        ) from exc
    defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == name
    ]
    bound = [node.lineno for node in tree.body if name in _top_level_names(node)]
    if defs and len(bound) > 1:
        raise PromiseError(
            f"{path}: {name!r} is bound {len(bound)} times at the top level "
            f"(lines {', '.join(map(str, bound))}) — Python runs the last one; "
            f"the declared scope must name one definition, so remove or rename "
            f"the others"
        )
    if defs:
        node = defs[0]
        # decorators included: `@cache` → `@retry` can change what the
        # function does, so it must move the stamp (review 2026-10-07)
        first = min([d.lineno for d in node.decorator_list] + [node.lineno])
        assert node.end_lineno is not None, f"{path}:{name} has no end line"
        return "\n".join(source.splitlines()[first - 1 : node.end_lineno])
    raise PromiseError(
        f"{path}: no top-level function or class {name!r} — the "
        f"declared scope names code that does not exist"
    )


def scope_sources(base: Path, scope: tuple[str, ...]) -> list[tuple[str, bytes]]:
    """(entry, content) of ONE promise's declared scope, entries resolved
    against `base` and sorted: a `file` entry is the file's bytes, a
    `file:function` entry that function's source, decorators included. A
    missing file or function is a PromiseError, never an empty entry. The
    one resolution `declared_scope_sha` and `unmentioned_constants` share."""
    entries: list[tuple[str, bytes]] = []
    for entry in sorted(scope):
        file_part, _, func = entry.partition(":")
        path = base / file_part
        if not path.is_file():
            raise PromiseError(f"scope entry {entry!r}: no such file {path}")
        try:
            content = (
                _function_source(path, func).encode("utf-8")
                if func
                else path.read_bytes()
            )
        except OSError as exc:
            raise PromiseError(f"scope entry {entry!r}: {exc}") from exc
        entries.append((entry, content))
    return entries


def unmentioned_constants(block: PromiseTables, base: Path) -> list[str]:
    """Static evidence (warns, never blocks): a registered constant that its
    promise's sentence does not name and no file of its declared scope reads
    as a word — a template leftover (`margin`, `max_empty`, `null_band_items`
    stood under three Haiku protocols whose sentences never used them,
    labkit-paper area 09, 2026-10-16) or a knob the promise does not state.
    runlog holds the constant to the run's config; this holds it to the
    sentence and the code. One line per constant, naming the promise.

    Raises:
        PromiseError: A scope entry cannot be resolved.
    """
    out = []
    for p in block.promises:
        if not p.constants:
            continue
        sources = [
            content.decode("utf-8", errors="replace")
            for _, content in scope_sources(base, p.scope)
        ]
        for name in p.constants:
            word = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
            if word.search(p.sentence) or any(word.search(s) for s in sources):
                continue
            out.append(
                f"{p.id}: constant `{name}` is named by no sentence and read by no "
                f"scope file ({', '.join(p.scope)}) — a template leftover, or a knob "
                f"the promise does not state (static evidence)"
            )
    return out


def declared_scope_sha(base: Path, scope: tuple[str, ...]) -> str:
    """Digest over ONE promise's declared scope, entries resolved against `base`
    — not the area's audit stamp over its scripts and imported helpers
    (`scope_sha.area_stamp`, `scope_sha.imported_repo_helpers`).

    A `file` entry covers the file's bytes; a `file:function` entry covers
    only that function's source, decorators included, so an edit to a
    neighbouring function leaves the stamp alone. Each entry contributes
    its own spelling plus its content digest, so adding, dropping or
    renaming an entry changes the stamp too. A missing file or function is
    a PromiseError, never an empty digest.
    """
    return scope_sha.tree_digest(scope_sources(base, scope))


def scope_drift(recorded: dict | None, base: Path) -> list[str]:
    """`[C1] old → new` for every promise whose declared scope changed since
    the run. `recorded` is the run's config.json `promises` (None: the run
    predates the block — nothing to compare)."""
    if recorded is None:
        return []
    out = []
    for pid, rec in sorted(recorded["ids"].items()):
        try:
            now = declared_scope_sha(base, tuple(rec["scope"]))
        except PromiseError as exc:
            # gone or unparsable is a change, not a crash (review 2026-10-07)
            out.append(f"[{pid}] {rec['declared_scope_sha']} → unreadable now ({exc})")
            continue
        if now != rec["declared_scope_sha"]:
            out.append(f"[{pid}] {rec['declared_scope_sha']} → {now}")
    return out


def block_drift(recorded: dict | None, block: PromiseTables | None) -> str | None:
    """Why the protocol's promise block (`block`, as parsed now) is not the
    one the run recorded, or None when it is (or neither side has one)."""
    if recorded is None:
        return (
            None
            if block is None
            else f"the run recorded no promise block — it ran before the block "
            f"existed or outside runlog; rerun so the number is bound to "
            f"the promises (block {block.sha})"
        )
    if block is None:
        return (
            f"the run ran under promise block {recorded['block_sha']}, the "
            f"protocol now carries none — the promises were removed after "
            f"the run"
        )
    if recorded.get("digest") != DIGEST_FORMAT:
        return (
            "the run recorded its promises with labkit 0.46/0.47 (digest over "
            "the block text, not comparable) — compare with labkit 0.47 or rerun"
        )
    if block.sha != recorded["block_sha"]:
        return (
            f"ran under promise block {recorded['block_sha']}, the protocol "
            f"now carries {block.sha} — the promises changed after the run"
        )
    return None


def snapshot(block: PromiseTables, base: Path) -> dict:
    """What a run records about its promises (config.json `promises`)."""
    return {
        "block_sha": block.sha,
        "digest": DIGEST_FORMAT,
        "ids": {
            p.id: {
                "key": p.key,
                "constants": p.constants,
                "scope": list(p.scope),
                "declared_scope_sha": declared_scope_sha(base, p.scope),
            }
            for p in block.promises
        },
    }
