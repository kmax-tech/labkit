"""promises — the one home of the promise alphabet and the promise block.

A promise is one checked registration of a protocol: a criterion that
judges, a quality check that releases or withholds the verdict, an
interpretation that says what follows from it. Its id is its kind and a
number, in the protocol text (`[criterion-1]`); its key in the run's
metrics is the id with underscores and a suffix (`criterion_1_pass`).

    criterion       constrains the reported outcome: which value of which
                    metric counts as support for the hypothesis
    quality-check   determines whether any criterion's verdict may be
                    issued, conditional on an outcome-neutral check
                    (control, anchor, yield, coverage, resolution) passing
                    in the same run
    interpretation  binds a pre-specified condition on the results to the
                    reading or follow-up analysis it licenses

An interpretation's sentence is written arm by arm, `<condition> →
<reading>`, arms separated by `;` (`parse_arms`); the run records one of
its readings under the promise's key, and intent-check holds it there.

The kind is spelled out so that a person reading a protocol, a report or a
run's metrics.json needs no legend. The earlier letters (C/A/B, and before
them K/S/W/N) are not read: a protocol that carries them is refused with a
sentence (`earlier_ids`) and read with labkit 0.103.0 (C/A/B) or 0.47
(K/S/W/N). Nothing translates them.

**The promise block** — promises as data instead of prose. The protocol's
one fenced ```toml block (`protocol_block.py`; its `[protocol]` table is the
head) may carry `[[promise]]` tables:

    [[promise]]
    id = "criterion-1"
    key = "criterion_1_pass"
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

from labkit.formats import files, protocol_block, runs, scope_sha

#: the kinds of promise — each one an id's stem: `criterion-1`
KINDS = ("criterion", "quality-check", "interpretation")
#: A constant is named like the config key it is recorded under — lowercase
#: snake_case, so the name IS the mapping between protocol and run record
#: (2026-10-08: `min_f1` in the block against `min_f1` in the record would
#: need a second table nobody checks).
CONSTANT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_KIND = "|".join(re.escape(k) for k in KINDS)
#: the kinds as a metrics key spells them: `quality_check`
_KEY_KIND = "|".join(k.replace("-", "_") for k in KINDS)
#: an id anywhere in protocol prose: `[criterion-1]`
ID_IN_PROTOCOL = re.compile(rf"\[((?:{_KIND})-\d+)\]")
#: an id the stamp writes before a field's placeholder: `[criterion-1] <…>`
ID_PREFIX = re.compile(rf"^\[(?:{_KIND})-\d+\]\s*")


def key_stem(pid: str) -> str:
    """The metrics-key namespace of the id PID: `quality-check-2` →
    `quality_check_2` (its key is that stem or `<stem>_<suffix>`)."""
    return pid.replace("-", "_")


def id_of_stem(stem: str) -> str:
    """The id whose key stem is STEM (`key_stem` reversed): a kind holds
    hyphens only, so `quality_check_2` → `quality-check-2`."""
    return stem.replace("_", "-")


def kind_of(pid: str) -> str:
    """The kind of the id PID: `quality-check-2` → `quality-check`."""
    return pid.rpartition("-")[0]


def registers_ids(text: str) -> bool:
    """Does the protocol's prose name any promise id? A computation at low repeat cost
    names none and owes no [[promise]] table (0.87.1)."""
    return ID_IN_PROTOCOL.search(text) is not None


#: an id in the letters earlier labkits read (C/A/B up to 0.103.0, K/S/W/N
#: up to 0.47) — detected, never read: a protocol carrying them would
#: otherwise pass every id check with nothing checked
EARLIER_ID = re.compile(r"\[([CABKSWN]\d+)\]")
#: a metrics key in the id namespace: the bare stem `criterion_1` or
#: `criterion_1_<suffix>`; group 1 is the stem
ID_KEY = re.compile(rf"^((?:{_KEY_KIND})_\d+)(?:_.*)?$")
#: a metrics key that is unmistakably an intent key (suffix required)
INTENT_KEY = re.compile(rf"^(?:{_KEY_KIND})_\d+_")
#: a key stem as a string literal in source: `"criterion_1_pass"`
ID_LITERAL = re.compile(rf"""['"]((?:{_KEY_KIND})_\d+)(_[a-z0-9_]*)?['"]""")

#: a criterion's denominator key: `criterion_1_n` — the count a criterion
#: was computed over, held by `finalize` to the recorded inputs
CRITERION_N_KEY = re.compile(r"^criterion_\d+_n$")

_BLOCK_ID = re.compile(rf"^(?:{_KIND})-\d+$")

#: an interpretation's reading — the value its run records under the key
READING = re.compile(r"^[a-z0-9][a-z0-9-]*$")
#: the arrow between an arm's condition and its reading (U+2192), the one
#: spelling: `->` is refused, not read as a second form of the same arm
ARROW = "→"
#: what separates an interpretation's arms
ARM_SEPARATOR = ";"
#: the condition of a last arm, taken when no earlier arm's condition holds
OTHERWISE = "otherwise"
#: the form, as every refusal of an interpretation's sentence shows it
ARMS_FORM = (
    "an interpretation is written arm by arm, `<condition> → <reading>`, arms "
    "separated by `;`, a reading in lowercase letters, digits and hyphens: "
    '"criterion-1 met and quality-check-1 met → generalises; quality-check-1 '
    'not met → noisy; otherwise → no-verdict"'
)
_ALLOWED_FIELDS = {"id", "key", "sentence", "scope", "constants"}

#: what `block_sha` is a digest of — recorded with it, so a run from an
#: earlier format is told apart instead of reported as changed promises
DIGEST_FORMAT = "promises-normalized-json"
#: what an audit record names as the promise block of a protocol that
#: declares no [[promise]] tables (a computation at low repeat cost)
NO_BLOCK = "none"


def snapshot_changes(was: dict, now: dict) -> list[str]:
    """What differs between two promise snapshots runs recorded (`snapshot`):
    one phrase per change of the registration — an id added or dropped, its
    key, a constant (`[quality-check-2] null_band 0.1 → 0.15`), its declared
    scope. Not
    the declared-scope digests: changed code under an unchanged declaration
    is a repair, no change of the registration. [] for the same block
    (`block_sha`); a block that differs in nothing the snapshot holds
    differs in a sentence, which the snapshot does not keep in clear text:
    `a promise's sentence`. Pure."""
    if was.get("block_sha") == now.get("block_sha"):
        return []
    old, new = was.get("ids") or {}, now.get("ids") or {}
    out = [f"[{i}] added" for i in sorted(set(new) - set(old))]
    out += [f"[{i}] dropped" for i in sorted(set(old) - set(new))]
    for i in sorted(set(old) & set(new)):
        a, b = old[i], new[i]
        if a.get("key") != b.get("key"):
            out.append(f"[{i}] key {a.get('key')} → {b.get('key')}")
        ca, cb = a.get("constants") or {}, b.get("constants") or {}
        for name in sorted(set(ca) | set(cb)):
            if ca.get(name) != cb.get(name):
                out.append(
                    f"[{i}] {name} {ca.get(name, '(none)')} → {cb.get(name, '(none)')}"
                )
        if sorted(a.get("scope") or []) != sorted(b.get("scope") or []):
            out.append(f"[{i}] scope {a.get('scope')} → {b.get('scope')}")
    return out or ["a promise's sentence"]


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
class InterpretationArm:
    """One arm of an interpretation: a condition on the results and the
    reading it licenses — the value the run records under the promise's key
    when the condition holds."""

    condition: str  # "quality-check-1 not met", or OTHERWISE on the last arm
    reading: str  # "noisy" — READING


def parse_arms(sentence: str) -> tuple[InterpretationArm, ...]:
    """The arms of an interpretation's SENTENCE, in order.

    The form: arms separated by `;`, each `<condition> → <reading>`. The
    arrow is `→` alone — `->` is refused with a sentence, not read as a
    second spelling. The condition is non-empty; `otherwise` stands as the
    condition of the last arm only. The reading matches READING and is
    unique in the sentence: it is the value a run records. At least two
    arms — one outcome licenses nothing to choose between. Pure; raises
    PromiseError naming the arm and what is wrong, with ARMS_FORM.
    """
    parts = [part.strip() for part in sentence.split(ARM_SEPARATOR)]
    arms: list[InterpretationArm] = []
    for n, part in enumerate(parts, 1):
        if not part:
            raise PromiseError(f"arm {n} is empty — {ARMS_FORM}")
        if part.count(ARROW) != 1:
            ascii_arrow = (
                " (the arrow is `→`, not `->`)"
                if not part.count(ARROW) and "->" in part
                else ""
            )
            raise PromiseError(
                f"arm {n} {part!r} holds {part.count(ARROW)} `→`, not one"
                f"{ascii_arrow} — {ARMS_FORM}"
            )
        condition, _, reading = (side.strip() for side in part.partition(ARROW))
        if not condition:
            raise PromiseError(f"arm {n} {part!r} has no condition — {ARMS_FORM}")
        if condition == OTHERWISE and n != len(parts):
            raise PromiseError(
                f"arm {n} {part!r} is `otherwise` but not the last arm — the "
                f"arms after it would never be taken; {ARMS_FORM}"
            )
        if not READING.match(reading):
            raise PromiseError(
                f"arm {n} {part!r}: reading {reading!r} is not lowercase "
                f"letters, digits and hyphens — {ARMS_FORM}"
            )
        if reading in {a.reading for a in arms}:
            raise PromiseError(
                f"arm {n} {part!r}: reading {reading!r} stands in an earlier "
                f"arm too — a recorded reading must name one arm"
            )
        arms.append(InterpretationArm(condition, reading))
    if len(arms) < 2:
        raise PromiseError(
            f"one arm — an interpretation chooses between at least two "
            f"readings; with one outcome, register none; {ARMS_FORM}"
        )
    return tuple(arms)


def is_placeholder(sentence: str) -> bool:
    """Is SENTENCE still the stamp's placeholder — the whole value one `<…>`,
    as `labkit-init exp` writes it?"""
    return sentence.startswith("<") and sentence.endswith(">")


@dataclass(frozen=True)
class Promise:
    """One promise of a protocol to the code: its id, the metrics key that reports it, its sentence, scope and constants."""

    id: str  # "criterion-1"
    kind: str  # one of KINDS: "criterion" | "quality-check" | "interpretation"
    key: str  # metrics key that reports it
    sentence: str  # the promise in one sentence
    scope: tuple[str, ...]  # declared implementation region
    constants: dict[str, int | float | str | bool]
    # an interpretation's arms (`parse_arms`); () for a criterion, a
    # quality check, and a sentence still the stamp's placeholder
    arms: tuple[InterpretationArm, ...]

    def readings(self) -> tuple[str, ...]:
        """The readings the promise registers, in arm order: the values its
        run may record under `key` (none for a criterion or quality check)."""
        return tuple(a.reading for a in self.arms)


@dataclass(frozen=True)
class PromiseTables:
    """A protocol's `[[promise]]` tables, parsed, with their digest."""

    promises: tuple[Promise, ...]
    sha: str  # digest of the [[promise]] tables (canonical JSON), not the head

    def by_id(self) -> dict[str, Promise]:
        """The promises keyed by their id."""
        return {p.id: p for p in self.promises}


def ids_in_prose(text: str) -> set[str]:
    """Ids written anywhere in the protocol prose (`[criterion-1]`) — the
    prose side; the data side is the [[promise]] tables (`PromiseTables`).
    `reported_ids` is the metrics side."""
    return {m.group(1) for m in ID_IN_PROTOCOL.finditer(text)}


def earlier_ids(text: str) -> list[str]:
    """Ids in the earlier letters (C/A/B, K/S/W/N), as written — each one a
    promise no check reads. Callers refuse them; nothing translates them."""
    return sorted(set(EARLIER_ID.findall(text)))


EARLIER_IDS_HELP = (
    "promise ids are written as their kind and a number since labkit "
    "0.104.0 — [criterion-1], [quality-check-1], [interpretation-1] "
    "(docs/promise-block.md); re-register the promises so, or check this "
    "protocol with labkit 0.103.0 (C/A/B) or 0.47 (K/S/W/N)"
)


def key_kind(key: str) -> str | None:
    """The kind a metrics key belongs to — one of KINDS — or None outside
    the id namespace. The one way to ask "is this a quality-check key":
    two tools once re-spelled the alphabet and would have gone silent on its
    next change."""
    m = ID_KEY.match(key)
    return kind_of(id_of_stem(m.group(1))) if m else None


def reported_ids(metrics: Mapping[str, object]) -> set[str]:
    """Ids a metrics dict reports (a bare stem or `<stem>_<suffix>` key), as
    ids (`criterion_1_pass` → `criterion-1`)."""
    out: set[str] = set()
    for key in metrics:
        m = ID_KEY.match(str(key))
        if m:
            out.add(id_of_stem(m.group(1)))
    return out


def is_block_id(name: str) -> bool:
    """Is NAME a promise id as a [[promise]] table spells it
    (`criterion-1`, `quality-check-2`)?"""
    return bool(_BLOCK_ID.match(name))


def parse_block(text: str) -> PromiseTables | None:  # noqa: C901 complexity baseline 2026-10-08
    """The protocol's promises, or None if its block declares none.

    Raises PromiseError on anything malformed: invalid TOML, an unknown
    field, an unknown kind, a key outside its id's namespace, a duplicate
    id, an empty scope, a non-scalar constant, an interpretation whose
    sentence is not arms (`parse_arms`; the stamp's `<…>` placeholder
    passes — `promise_tables_owed` holds it). The digest covers the
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
            hint = (
                f" — {EARLIER_IDS_HELP}"
                if isinstance(pid, str) and EARLIER_ID.match(f"[{pid}]")
                else ""
            )
            raise PromiseError(
                f"{where}: id {pid!r} is not criterion-<n>, quality-check-<n> "
                f"or interpretation-<n>{hint}"
            )
        where = f"[[promise]] {pid}"
        if pid in seen:
            raise PromiseError(f"{where}: duplicate id")
        seen.add(pid)
        key = e["key"]
        stem = key_stem(pid)
        if not isinstance(key, str) or (key != stem and not key.startswith(stem + "_")):
            raise PromiseError(
                f"{where}: key {key!r} is outside the id's "
                f"namespace — expected '{stem}' or '{stem}_<suffix>'"
            )
        sentence = e["sentence"]
        if not isinstance(sentence, str) or not sentence.strip():
            raise PromiseError(f"{where}: `sentence` is empty")
        sentence = sentence.strip()
        arms: tuple[InterpretationArm, ...] = ()
        if kind_of(pid) == "interpretation" and not is_placeholder(sentence):
            try:
                arms = parse_arms(sentence)
            except PromiseError as exc:
                raise PromiseError(f"{where}: `sentence`: {exc}") from exc
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
                kind=kind_of(pid),
                key=key,
                sentence=sentence,
                scope=tuple(scope),
                constants=dict(constants),
                arms=arms,
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
    """(ids in prose but not in the block, block ids not in prose)."""
    prose = ids_in_prose(text)
    ids = {p.id for p in block.promises}
    return sorted(prose - ids), sorted(ids - prose)


def registered_ids(text: str) -> set[str]:
    """Ids the protocol registers: named in the prose (`[criterion-1]`)
    or declared as a [[promise]] table. A table the prose does not name
    still registers its id — `prose_mismatch` reports that; it is no reason
    to check nothing. Raises PromiseError on a malformed block."""
    block = parse_block(text)
    declared = {p.id for p in block.promises} if block is not None else set()
    return ids_in_prose(text) | declared


def table_ids(text: str) -> set[str]:
    """The ids the protocol's [[promise]] tables declare (`criterion-1`):
    the ids an audit decision's effect may leave not assessable
    (`labkit-audit --decide N limit --not-assessable <ID>`). Empty for a
    protocol without tables — a computation registers none. Unlike
    `registered_ids`, an id named only in the prose does not count. Raises
    PromiseError on a malformed block."""
    block = parse_block(text)
    return set(block.by_id()) if block is not None else set()


def load(protocol: Path) -> PromiseTables:
    """The promise block of `protocol`; raises if it has none.

    For scripts:
    `promises.load(PROTOCOL).by_id()["criterion-1"].constants["min_f1"]`
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


def with_constant(text: str, name: str, value: float) -> str:
    """TEXT with the registered constant NAME set to VALUE in the one
    `constants = { … }` line of the TOML block that holds it — every other
    byte kept, the block read back and holding exactly VALUE. Raises
    PromiseError when the block does not read, no table or more than one
    line holds NAME, or the read-back differs."""
    span = protocol_block.toml_block_span(text)
    if span is None:
        raise PromiseError("no ```toml block to set a constant in")
    lines = text.split("\n")
    pattern = re.compile(
        rf"(\bconstants\s*=\s*\{{[^}}]*\b{re.escape(name)}\s*=\s*)[-+0-9.eE]+"
    )
    hits = [i for i in range(*span) if pattern.search(lines[i])]
    if len(hits) != 1:
        raise PromiseError(
            f"{len(hits)} constants lines hold {name!r} — one table registers a constant"
        )
    lines[hits[0]] = pattern.sub(
        lambda m: m.group(1) + repr(value), lines[hits[0]], count=1
    )
    new = "\n".join(lines)
    block = parse_block(new)
    if block is None or all_constants(block).get(name) != value:
        raise PromiseError(f"{name} did not read back as {value!r}")
    return new


def write_constant(protocol: Path, name: str, value: float) -> None:
    """PROTOCOL with the registered constant NAME set to VALUE
    (`with_constant`), written in place. Raises PromiseError as it does."""
    text = protocol.read_text(encoding="utf-8")
    files.write_atomic(protocol, with_constant(text, name, value))


def placeholder_sentences(block: PromiseTables) -> list[str]:
    """The ids whose `sentence` is still a stamp placeholder: the whole value
    one `<…>`, as `labkit-init exp` writes it."""
    return [p.id for p in block.promises if is_placeholder(p.sentence)]


def promise_tables_owed(
    block: PromiseTables | None, *, frozen: bool, full_run: bool, registers: bool = True
) -> str | None:
    """Why a protocol owes its [[promise]] tables, or None — the one home of
    the rule (standard 0.19) for protocol-check, preflight, runlog and
    finalize. The table:

        registers = False (the prose names no promise id — a
            computation, 0.87.1) → not owed, frozen or not: it judges no
            prediction, and its stamp carries no table (`protocol_cuts.bar_cut`)
        frozen = true            → owed (the freeze is the registration)
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
    if not registers:
        # a computation, frozen or a full run: nothing registered, nothing to
        # hold — its high-cost freeze asked for tables its own stamp removes
        return None
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
        promise_id: The promise that declares it ("criterion-1").
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
    """`[criterion-1] old → new` for every promise whose declared scope changed since
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
