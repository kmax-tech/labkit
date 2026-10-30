"""protocol_block — the one TOML block of a protocol, and its head.

A protocol carries exactly one fenced ```toml block. Its `[protocol]` table
holds the fields a machine reads — the head — and its optional
`[[promise]]` tables hold the promises (`promises.py`); a computation may
carry a `[reference]` table, the stated value its number is compared with
(`reference`):

    [protocol]
    standard = "0.23"
    id = "p-0123456789abcdef"       # stamped by `labkit-init exp`, never typed
    type = "exploratory"            # exploratory | confirmatory
    repeat_cost = "low"         # low | high — the price of a repeat
    kind = "compute"                # compute | fit | apply — what the kept number asserts
    frozen = false
    preflight_audit = ""            # high repeat cost: the decided preflight record, audits/<minute>-preflight.toml
    report = "REPORT.md"            # optional: the report file, repo-relative, that owes this protocol's result

One parser (`tomllib`), exact keys, typed values: a typo is a loud error
naming the field, never a silent "not found" — `Cost: second` used to read
as an undeclared tier and so as `high` (TODO 8). The prose fields a human
writes and reads stay Markdown; `protocol_check` holds them by their exact
template label.

A value still in angle brackets (`"<low | high>"`) is a
placeholder: the head reads it as None, and the checker reports it as an
unfilled field instead of a malformed one.
"""

from __future__ import annotations

import json
import math
import posixpath
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from labkit.formats.repo import (
    PROTOCOL_NAME,
    REPORT_SUFFIX,
    git_root,
    repo_protocols,
)
from labkit.formats.runs import RUN_ID

#: the head format this labkit reads; a protocol of another standard is
#: read with the labkit release it was written for
STANDARD = "0.23"
#: what a reader of the previous standard changes to read a protocol here —
#: said in the refusal, so the migration is a sentence, not a legacy path
MIGRATION = (
    'from 0.22: set standard = "0.23" and replace `cost = "seconds" | "minutes" | '
    '"hours"` with `repeat_cost = "low" | "high"` — the price of a repeat, as the '
    "gates read it: seconds is low, minutes and hours are high (`protocol-fill "
    "<PROTOCOL> repeat_cost=…` after renaming the key)"
)
TYPES = ("exploratory", "confirmatory")
REPEAT_COSTS = ("low", "high")
#: what the kept number asserts (standard 0.22): a computation judges no
#: prediction; a fit judges a model trained or adjusted in this experiment;
#: an apply judges a model used unchanged — the obligations follow
#: (`standard_contract.registration_fields`), never the model technology
KINDS = ("compute", "fit", "apply")
#: `p-` plus 16 lowercase hex: not derived from name or path, so renaming
#: and moving a protocol leave its identity intact
ID_SHAPE = re.compile(r"^p-[0-9a-f]{16}$")

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+-]*)")
_TOP_LEVEL = {"protocol", "promise", "result", "model", "gate", "replaces", "reference"}
#: the settings every protocol carries in its ```toml head (the block at the
#: end of the protocol), in the template's order — not the run's config.json,
#: which runlog writes per run
PROTOCOL_HEAD_KEYS = (
    "standard",
    "id",
    "type",
    "repeat_cost",
    "kind",
    "frozen",
    "preflight_audit",
)
#: the head fields a protocol may carry: `report`, the file (a path
#: relative to the repository root) assigned as this protocol's report —
#: once it exists, it owes the protocol's result block or its handover
#: block (`report_hold.report_owed`); absent, no file is owed anything
OPTIONAL_HEAD_KEYS = ("report",)


class BlockError(ValueError):
    """The protocol's TOML block is missing or malformed; the message names the field."""


@dataclass(frozen=True)
class Head:
    """The `[protocol]` table. None marks a field still holding its placeholder."""

    standard: str
    id: str | None
    type: str | None
    repeat_cost: str | None
    kind: str | None  # one of KINDS; None while the stamp's placeholder stands
    frozen: bool
    preflight_audit: (
        str  # "" until the decided preflight record is named (its file name)
    )
    report: str | None = None  # the registered report file, repo-relative; None: none

    @property
    def placeholders(self) -> list[str]:
        """The head fields still holding a template placeholder."""
        return [
            f for f in ("id", "type", "repeat_cost", "kind") if getattr(self, f) is None
        ]


#: a `[[promise]]` table header line, spaces and a comment allowed — where
#: an editor of the block finds a promise table
PROMISE_HEADER = re.compile(r"^\s*\[\[\s*promise\s*\]\]\s*(?:#.*)?$")
#: any table header line (`[protocol]`, `[[promise]]`, `[promise.constants]`)
TABLE_HEADER = re.compile(r"^\s*\[")


#: characters json leaves raw that a one-line TOML string cannot hold raw:
#: DEL (TOML forbids it unescaped) and the line breaks `str.splitlines` cuts
#: beyond those json escapes — the fence walker would split the string
_TOML_RAW_UNSAFE = str.maketrans(
    {"\x7f": "\\u007f", "\x85": "\\u0085", " ": "\\u2028", " ": "\\u2029"}
)


def toml_string(value: str) -> str:
    """VALUE as a one-line TOML basic string, the one writer of a TOML
    string labkit writes (findings and review files, a promise sentence,
    the head of a report's discussion block). json's
    escaping is TOML's for the quote, the backslash and every control
    character below U+0020; DEL, U+0085, U+2028 and U+2029 are escaped on
    top. Raises
    ValueError on a lone surrogate, which no TOML string can hold."""
    bad = next((c for c in value if 0xD800 <= ord(c) <= 0xDFFF), None)
    if bad is not None:
        raise ValueError(
            f"a lone surrogate U+{ord(bad):04X} is no character a TOML string "
            f"can hold — the text was not decoded as UTF-8"
        )
    return json.dumps(value, ensure_ascii=False).translate(_TOML_RAW_UNSAFE)


def fence_spans(lines: list[str]) -> list[tuple[str, int, int]]:
    """(info string, first body line, line after the body) of every
    top-level fenced block, as 0-based indexes into LINES — the one fence
    walker; `fenced_blocks` is its text form, and the readers that need a
    place (the head's line, the Prompt block to replace) use the spans.
    A fence inside another fence is body, not a block: a verbatim prompt
    that asks the model for ```toml output is no second head (review
    2026-10-07). A fence closes with the same character, at least as long,
    and nothing after it; an unclosed fence runs to the end."""
    out: list[tuple[str, int, int]] = []
    i = 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        marker, info = m.group(2), m.group(3).lower()
        start = i + 1
        i = start
        while i < len(lines) and not closes(lines[i], marker):
            i += 1
        out.append((info, start, i))
        i += 1
    return out


def section_starts(lines: list[str]) -> list[int]:
    """The 0-based indexes of the `## ` headings of a protocol — outside
    every fence (`fenced_lines`), in order. The one cut into sections: the
    prose count, the Runs list, the low cut and the stamp's blank-line
    pass each found the headings themselves, two of them inside fences too
    (audit 2026-10-23)."""
    fenced = fenced_lines(lines)
    return [
        i
        for i, line in enumerate(lines)
        if i not in fenced and line.lstrip().startswith("## ")
    ]


def section_end(lines: list[str], start: int) -> int:
    """The index of the first line after the section opening at START: the
    next heading's, or `len(lines)`."""
    return next((i for i in section_starts(lines) if i > start), len(lines))


def fenced_lines(lines: list[str]) -> set[int]:
    """The 0-based indexes of every line a fence takes — its markers and its
    body, by `fence_spans`. For a reader that walks lines and must skip the
    fenced ones (a prose count, a label search, a rule scan): until the
    audit of 2026-10-18 seven readers toggled a flag on ``` by hand, so a
    `~~~` fence or a ``` nested in a fence turned prose into code and code
    into prose for them, while the protocol parser read it right."""
    out: set[int] = set()
    for _, start, end in fence_spans(lines):
        out.update(range(start - 1, min(end + 1, len(lines))))
    return out


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """(info string, body) of every top-level fenced block (`fence_spans`)."""
    lines = text.splitlines()
    return [
        (info, "\n".join(lines[start:end]) + "\n")
        for info, start, end in fence_spans(lines)
    ]


def toml_block_span(text: str) -> tuple[int, int] | None:
    """(first body line, line after the body) of the protocol's one TOML
    block, 0-based, or None without one; raises BlockError when there are
    two — where a writer edits the head in place."""
    spans = [(s, e) for info, s, e in fence_spans(text.splitlines()) if info == "toml"]
    if len(spans) > 1:
        raise BlockError(
            f"{len(spans)} ```toml blocks — a protocol has exactly "
            f"one, holding [protocol] and its [[promise]] tables"
        )
    return spans[0] if spans else None


def closes(line: str, marker: str) -> bool:
    """Does `line` close a fence opened with `marker`?"""
    s = line.strip()
    return bool(s) and set(s) == {marker[0]} and len(s) >= len(marker)


def block_text(text: str) -> str | None:
    """The raw text of the protocol's TOML block, None if it has none.

    Raises BlockError when there are two: a protocol has exactly one."""
    blocks = [body for info, body in fenced_blocks(text) if info == "toml"]
    if len(blocks) > 1:
        raise BlockError(
            f"{len(blocks)} ```toml blocks — a protocol has exactly "
            f"one, holding [protocol] and its [[promise]] tables"
        )
    return blocks[0] if blocks else None


def parse_toml_block(text: str) -> dict:
    """The parsed TOML block; an empty dict when the protocol has none."""
    raw = block_text(text)
    if raw is None:
        return {}
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise BlockError(
            f"the protocol's ```toml block is not valid TOML: {exc}"
        ) from exc
    extra = set(data) - _TOP_LEVEL
    if extra:
        raise BlockError(
            f"top-level keys {sorted(extra)} in the ```toml block — "
            f"only [protocol] and [[promise]] belong there"
        )
    return data


def _placeholder(value: object) -> bool:
    """The template's `"<…>"`; a value merely starting with `<` is content."""
    return (
        isinstance(value, str)
        and value.strip().startswith("<")
        and value.strip().endswith(">")
    )


#: the keys of the `[result]` table: the one declaration that a number is reported
RESULT_KEYS = ("run",)
#: the `[model]` table — a model is in the loop — and its arms, one table each
MODEL_KEYS = ("alias", "arms", "number_describes", "annotation_validity")
ARM_KEYS = ("profile", "fingerprint", "alias")
FINGERPRINT = re.compile(r"^[0-9a-f]{8,64}$")
#: what a computed number over a model's outputs describes (`[model]
#: number_describes`, only with kind = "compute"): the outputs themselves
#: ("the model marked 30 % as causal") or a property of the data, the model
#: as annotator ("30 % of the texts are causal") — the latter owes
#: `annotation_validity`
NUMBER_DESCRIBES = ("model_outputs", "target_property")
MODEL_OUTPUTS, TARGET_PROPERTY = NUMBER_DESCRIBES
#: the claim keys of `[model]`: they say what a computation over the model's
#: outputs claims, so they belong to kind = "compute" alone
CLAIM_KEYS = ("number_describes", "annotation_validity")
#: the evidence that the model suits as annotator (`[model]
#: annotation_validity`), one key: an apply protocol of this repo (bound by
#: `protocol_history.check_annotation_validity`) or a DOI (its form only)
VALIDITY_KEYS = ("protocol", "doi")
DOI_SHAPE = re.compile(r"^10\.\d{4,9}/\S+$")
#: the `[gate]` table: the labels the gate accepts, declared for the code check
GATE_KEYS = ("labels",)


@dataclass(frozen=True)
class Arm:
    """One compared arm: its profile file, the fingerprint the run must record, its alias."""

    profile: str  # register/profiles/x.toml, relative to the repo
    fingerprint: str  # 8–64 hex digits, recorded somewhere in the run's config
    alias: str | None  # the model alias behind it, when it differs


@dataclass(frozen=True)
class Validity:
    """The evidence that the model suits as annotator (`[model] annotation_validity`)."""

    key: str  # "protocol" or "doi" (VALIDITY_KEYS)
    value: str  # a protocol id (ID_SHAPE) or a DOI (DOI_SHAPE)


@dataclass(frozen=True)
class Model:
    """The model in the loop, as the head declares it (`[model]`)."""

    alias: str | None  # None while the stamp's `"<…>"` stands
    arms: dict[str, Arm]  # {} when the protocol compares no arms
    number_describes: str | None  # NUMBER_DESCRIBES; None while absent or `"<…>"`
    annotation_validity: Validity | None  # None while absent
    claim_keys: frozenset[str]  # the CLAIM_KEYS the table carries, stamped or filled


def _table(data: dict, name: str) -> dict | None:
    """DATA's top-level table NAME, None when absent; BlockError when it is no table."""
    if name not in data:
        return None
    table = data[name]
    if not isinstance(table, dict):
        raise BlockError(f"`{name}` must be a table: [{name}]")
    return table


def _only_keys(table: dict, where: str, allowed: tuple[str, ...]) -> None:
    unknown = set(table) - set(allowed)
    if unknown:
        raise BlockError(
            f"{where}: unknown field(s) {sorted(unknown)}; allowed: {', '.join(allowed)}"
        )


def _arm(name: str, raw: object) -> Arm:
    where = f"[model.arms.{name}]"
    if not isinstance(raw, dict):
        raise BlockError(f"{where} must be a table with profile and fingerprint")
    _only_keys(raw, where, ARM_KEYS)
    for key in ("profile", "fingerprint"):
        if key not in raw:
            raise BlockError(f"{where}: missing `{key}`")
    profile, fingerprint, alias = raw["profile"], raw["fingerprint"], raw.get("alias")
    if not isinstance(profile, str) or not profile.endswith(".toml"):
        raise BlockError(
            f"{where} profile = {profile!r} — a `.toml` path under the repo"
        )
    if not isinstance(fingerprint, str) or not FINGERPRINT.match(fingerprint):
        raise BlockError(f"{where} fingerprint = {fingerprint!r} — 8 to 64 hex digits")
    if alias is not None and (not isinstance(alias, str) or not alias.strip()):
        raise BlockError(f"{where} alias = {alias!r} — a non-empty string")
    return Arm(profile, fingerprint, alias)


def _validity(raw: object) -> Validity:
    where = "[model] annotation_validity"
    if not isinstance(raw, dict) or len(raw) != 1:
        raise BlockError(
            f'{where} = {raw!r} — one key: {{ protocol = "p-…" }} or {{ doi = "10.…" }}'
        )
    _only_keys(raw, where, VALIDITY_KEYS)
    ((key, value),) = raw.items()
    shape = ID_SHAPE if key == "protocol" else DOI_SHAPE
    if not isinstance(value, str) or not shape.match(value):
        raise BlockError(
            f"{where} {key} = {value!r} — "
            + (
                "p- and 16 hex digits"
                if key == "protocol"
                else "a DOI, 10.<registrant>/<suffix>"
            )
        )
    return Validity(key, value)


def model(text: str) -> Model | None:
    """The model the protocol declares in its loop — `[model] alias = "<alias
    from models.toml>"`, stamped by `labkit-init exp --model`, with the
    compared arms as `[model.arms.<arm>]` tables (profile, fingerprint,
    alias) finalize holds to the run — or None without the table: no model,
    a computation or an estimator. The one answer to "is a model named" for the
    low cut, the registration and `--report` (until 0.100.0 the prose
    `Model / tool` line, read with a pattern for "n/a", "none" and dashes).
    `alias` is None while it is still the stamp's placeholder, so is
    `number_describes`. Whether the claim keys fit the kind is
    `protocol_check.kind_gap`'s answer. Raises BlockError on a non-table, an
    unknown key, an alias that is no string, an arm without profile and hex
    fingerprint, a `number_describes` outside NUMBER_DESCRIBES, or an
    `annotation_validity` that is not one protocol id or one DOI."""
    table = _table(parse_toml_block(text), "model")
    if table is None:
        return None
    _only_keys(table, "[model]", MODEL_KEYS)
    if "alias" not in table:
        raise BlockError("[model]: missing `alias` — the alias from models.toml")
    alias = table["alias"]
    if not isinstance(alias, str) or not alias.strip():
        raise BlockError(f"[model] alias = {alias!r} — a non-empty string")
    arms_raw = table.get("arms", {})
    if not isinstance(arms_raw, dict):
        raise BlockError("[model] arms — one table per arm: [model.arms.<arm>]")
    arms = {name: _arm(name, raw) for name, raw in arms_raw.items()}
    describes = table.get("number_describes")
    if describes is not None and not _placeholder(describes):
        if describes not in NUMBER_DESCRIBES:
            raise BlockError(
                f"[model] number_describes = {describes!r} — one of "
                f"{', '.join(NUMBER_DESCRIBES)}"
            )
    else:
        describes = None
    validity = table.get("annotation_validity")
    return Model(
        None if _placeholder(alias) else alias,
        arms,
        describes,
        None if validity is None else _validity(validity),
        frozenset(k for k in CLAIM_KEYS if k in table),
    )


def declared_labels(text: str) -> tuple[str, ...] | None:
    """The labels the gate accepts, declared as `[gate] labels = ["…", …]` —
    the registered set an agent reading `code-check --bundle` holds the
    code's string comparisons against (LAB-038 What the prompt demands); the
    judgement stays the agent's, no gate compares them. None without the table.
    Raises BlockError on a non-table, an unknown key, or labels that are
    not a non-empty list of non-empty strings."""
    table = _table(parse_toml_block(text), "gate")
    if table is None:
        return None
    _only_keys(table, "[gate]", GATE_KEYS)
    if "labels" not in table:
        raise BlockError("[gate]: missing `labels` — the labels the gate accepts")
    labels = table["labels"]
    if (
        not isinstance(labels, list)
        or not labels
        or any(not isinstance(x, str) or not x.strip() for x in labels)
    ):
        raise BlockError(
            f"[gate] labels = {labels!r} — a non-empty list of non-empty strings"
        )
    return tuple(labels)


#: the `[reference]` table of a computation: the stated value its kept
#: number is compared with, and how (docs/notes/2026-10-29-reference-comparison.md)
REFERENCE_KEYS = ("key", "value", "tolerance", "relative", "relation", "source")
#: how the measured value is held to the reference: `within` a tolerance of
#: it (`|measured - value| <= tolerance`), `at_least` it, `at_most` it — the
#: last two carry no tolerance
RELATIONS = ("within", "at_least", "at_most")
WITHIN, AT_LEAST, AT_MOST = RELATIONS


@dataclass(frozen=True)
class Reference:
    """The stated value a computation's kept number is compared with, as
    the head's `[reference]` registers it. The verdict is
    `reference.reference_verdict`'s; whether the head's kind may carry the
    table is `protocol_check.reference_gap`'s answer."""

    key: str  # the metrics key the comparison reads
    value: float  # the stated value, in the key's unit (an int as written)
    tolerance: (
        float | None
    )  # `within` only: absolute, or a fraction of `value` when `relative`
    relative: bool  # `tolerance` is a fraction of `value`
    relation: str  # one of RELATIONS
    source: str | None  # who states the value; None while not written

    @property
    def absolute_tolerance(self) -> float | None:
        """The tolerance in the key's unit: `tolerance` itself, or
        `|value| * tolerance` when relative; None without one."""
        if self.tolerance is None:
            return None
        return abs(self.value) * self.tolerance if self.relative else self.tolerance


def finite_number(value: object) -> bool:
    """VALUE is an int or a float that is finite — a bool is no number here, nor NaN or an infinity; the one reading of \"a number\" for the head and the verdict (`reference`)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def reference(text: str) -> Reference | None:
    """The stated value the protocol's `[reference]` table compares the
    kept number with — `key`, `value`, `relation`, with `within` a
    `tolerance` (absolute, or a fraction of `value` with `relative =
    true`), and `source`, who states the value — or None without the
    table: a pure computation. Raises BlockError on a non-table, an
    unknown key, a missing `key`, `value` or `relation`, a `value` or
    `tolerance` that is not a finite number (a bool is none), a negative
    tolerance, a `relation` outside RELATIONS, `within` without a
    tolerance, `at_least` or `at_most` with one (or with `relative`), a
    `relative` that is no bool, or an empty `source`."""
    table = _table(parse_toml_block(text), "reference")
    if table is None:
        return None
    _only_keys(table, "[reference]", REFERENCE_KEYS)
    for field in ("key", "value", "relation"):
        if field not in table:
            raise BlockError(
                f"[reference]: missing `{field}` — key (the metrics key compared), "
                f"value (the stated value) and relation ({', '.join(RELATIONS)})"
            )
    key = table["key"]
    if not isinstance(key, str) or not key.strip() or any(c.isspace() for c in key):
        raise BlockError(
            f"[reference] key = {key!r} — the metrics key the comparison reads, "
            f"one word (the compute skeleton's METRIC_KEY)"
        )
    value = table["value"]
    if not finite_number(value):
        raise BlockError(
            f"[reference] value = {value!r} — a finite number in the key's unit"
        )
    relation = table["relation"]
    if relation not in RELATIONS:
        raise BlockError(
            f"[reference] relation = {relation!r} — one of {', '.join(RELATIONS)}"
        )
    tolerance, relative = _reference_tolerance(table, relation)
    source = table.get("source")
    if source is not None and (not isinstance(source, str) or not source.strip()):
        raise BlockError(
            f"[reference] source = {source!r} — who states the value, a non-empty "
            f"string (the task text, a cited analysis), or no `source` line"
        )
    return Reference(
        key=key,
        value=value,
        tolerance=tolerance,
        relative=relative,
        relation=relation,
        source=source,
    )


def _reference_tolerance(table: dict, relation: str) -> tuple[float | None, bool]:
    """(tolerance, relative) of a `[reference]` TABLE under RELATION: owed
    with `within` (a finite number >= 0; `relative` a bool, false when
    absent), refused with `at_least` and `at_most` (`reference`)."""
    tolerance = table.get("tolerance")
    relative = table.get("relative", False)
    if not isinstance(relative, bool):
        raise BlockError(f"[reference] relative = {relative!r} — true or false")
    if relation != WITHIN:
        if tolerance is not None or "relative" in table:
            raise BlockError(
                f'[reference] relation = "{relation}" takes no tolerance (and no '
                f"relative): the measured value is held {relation.replace('_', ' ')} "
                f"the value itself; drop the key(s)"
            )
        return None, False
    if tolerance is None:
        raise BlockError(
            '[reference]: missing `tolerance` — relation = "within" holds '
            "|measured - value| <= tolerance; absolute, or a fraction of "
            "value with relative = true"
        )
    if not finite_number(tolerance) or tolerance < 0:
        raise BlockError(
            f"[reference] tolerance = {tolerance!r} — a finite number >= 0"
        )
    return tolerance, relative


def reference_toml(ref: Reference) -> str:
    """REF as the `[reference]` table `labkit-init exp --reference` stamps
    — the one writer of the table, and the form the registration stamp
    digests (`protocol_check.registration_stamp`). Reads back as REF."""
    lines = [
        "[reference]",
        f"key = {toml_string(ref.key)}",
        f"value = {ref.value!r}",
    ]
    if ref.tolerance is not None:
        lines.append(f"tolerance = {ref.tolerance!r}")
    if ref.relative:
        lines.append("relative = true")
    lines.append(f"relation = {toml_string(ref.relation)}")
    if ref.source is not None:
        lines.append(f"source = {toml_string(ref.source)}")
    return "\n".join(lines) + "\n"


def declared_run(text: str) -> str | None:
    """The run the protocol declares as its reported result — `[result]
    run = "<run_id>"` in the TOML block, written by `protocol-fill
    --from-run` and never typed; report-check holds the protocol to it at
    the stop and the commit. None without a `[result]` table: an
    exploration that reports nothing (until 0.100.0 the declaration was a
    run id in the former prose "Answer to the question" line, and a typed
    `…_final` there passed as a citation). Raises BlockError when the
    table is not a table, holds a key other than `run`, or `run` is not a
    string in the shape runlog writes (`runs.RUN_ID`)."""
    data = parse_toml_block(text)
    if "result" not in data:
        return None
    table = data["result"]
    if not isinstance(table, dict):
        raise BlockError("`result` must be a table: [result]")
    unknown = set(table) - set(RESULT_KEYS)
    if unknown:
        raise BlockError(
            f"[result]: unknown field(s) {sorted(unknown)}; allowed: {', '.join(RESULT_KEYS)}"
        )
    if "run" not in table:
        raise BlockError("[result]: missing `run` — the run id the result reports")
    run = table["run"]
    if not isinstance(run, str) or not RUN_ID.fullmatch(run):
        raise BlockError(
            f"[result] run = {run!r} — no run id runlog writes (<date>T<time>_<hex>); "
            f"a run id is runlog's, written by `protocol-fill <PROTOCOL> --from-run "
            f"<run_id>`, never typed"
        )
    return run


#: the fields of one declared change of a new registration
CHANGE_KEYS = ("what", "from", "to", "why")


@dataclass(frozen=True)
class Change:
    """One difference a replacing protocol declares against its predecessor:
    WHAT (`criterion-1 margin`, `criterion-1 sentence`, `kind`, `Data profile`, …), FROM and TO
    as the registrations read, and WHY — the reason, owed."""

    what: str
    from_: str
    to: str
    why: str


@dataclass(frozen=True)
class Replaces:
    """`[replaces]`: the protocol this one replaces and every change of the
    registration against it (K1, docs/notes/2026-10-27-new-registration-contracts.md)."""

    protocol: str
    changes: tuple[Change, ...]


def declared_run_shown(text: str) -> str | None:
    """What TEXT's `[result]` declares, as an audit shows and binds it: the
    run id (`declared_run`), or — for a table that does not read — the
    sentence naming why; None without a `[result]` table. Never raises on
    the table: the gates refuse a broken declaration (`declared_run`), and
    an audit that crashed on it could never see it repaired."""
    try:
        return declared_run(text)
    except BlockError as exc:
        return f"a [result] that does not read ({exc})"


def replaces(text: str) -> Replaces | None:
    """The protocol's `[replaces]` table — `protocol = "p-<id>"` and one
    `[[replaces.change]]` per declared difference (CHANGE_KEYS, `why` not
    empty) —, or None without one: a protocol that replaces nothing.
    Raises BlockError on a non-table, an unknown key, an id not in the
    shape labkit stamps, or a change missing a field or its reason."""
    data = parse_toml_block(text)
    if "replaces" not in data:
        return None
    table = data["replaces"]
    if not isinstance(table, dict):
        raise BlockError("`replaces` must be a table: [replaces]")
    _only_keys(table, "[replaces]", ("protocol", "change"))
    pid = table.get("protocol")
    if not isinstance(pid, str) or not ID_SHAPE.match(pid):
        raise BlockError(
            f"[replaces] protocol = {pid!r} — the id of the protocol this one "
            f"replaces (`p-` plus 16 lowercase hex digits)"
        )
    rows = table.get("change", [])
    if not isinstance(rows, list):
        raise BlockError("[replaces] change must be [[replaces.change]] tables")
    changes = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise BlockError(f"[[replaces.change]] #{i} is not a table")
        _only_keys(row, f"[[replaces.change]] #{i}", CHANGE_KEYS)
        values = {k: row.get(k) for k in CHANGE_KEYS}
        missing = [k for k, v in values.items() if not isinstance(v, str)]
        if missing:
            raise BlockError(
                f"[[replaces.change]] #{i}: {', '.join(missing)} missing or not a string"
            )
        what, from_, to, why = (str(values[k]) for k in CHANGE_KEYS)
        if not why.strip():
            raise BlockError(
                f"[[replaces.change]] #{i}: `why` is empty — a change owes its reason"
            )
        changes.append(Change(what, from_, to, why))
    return Replaces(pid, tuple(changes))


def _choice(table: dict, field: str, allowed: tuple[str, ...]) -> str | None:
    value = table[field]
    if _placeholder(value):
        return None
    if value not in allowed:
        raise BlockError(
            f"[protocol] {field} = {value!r} — one of {', '.join(allowed)}"
        )
    return value


def id_of(text: str) -> str | None:
    """The head's id; None when the head is missing, malformed or unstamped.
    For readers that index or count protocols — a broken head is reported
    where that protocol itself is checked, not by every scan that meets it."""
    try:
        return head(text).id
    except BlockError:
        return None


def repo_protocol_ids(start: Path) -> dict[str, list[Path]]:
    """Every protocol id in the repo, mapped to the files carrying it — read
    now, never cached: the caller holds the index for as long as it may
    trust it (`main`: one scan per repo per invocation). A module-level
    cache kept a duplicate made later in the same process invisible.

    Uniqueness cannot be settled at the stamp alone: copying a protocol or
    editing the id by hand makes a duplicate long after `labkit-init exp` ran, and
    two protocols with one id bind their runs to the same thing. Here, in the
    core, because the area stamp resolves an `annotation_validity` reference
    through it too (`scope_sha.validation_basis`).
    """
    root = git_root(start)
    if root is None:
        return {}
    index: dict[str, list[Path]] = {}
    for f in repo_protocols(root):
        try:
            pid = id_of(f.read_text(encoding="utf-8"))
        except OSError:
            continue
        if pid:
            index.setdefault(pid, []).append(f)
    return index


def head(text: str) -> Head:  # noqa: C901 complexity baseline 2026-10-08
    """The protocol's head. Raises BlockError when the block or the
    `[protocol]` table is missing, a field is missing or unknown, or a
    value has the wrong type or is outside its choices."""
    data = parse_toml_block(text)
    if "protocol" not in data:
        raise BlockError(
            f"no [protocol] table — the head ({', '.join(PROTOCOL_HEAD_KEYS)}) "
            f"lives in the ```toml block; protocols with a prose head "
            f"are read by labkit 0.47"
        )
    table = data["protocol"]
    if not isinstance(table, dict):
        raise BlockError("`protocol` must be a table: [protocol]")
    unknown = set(table) - set(PROTOCOL_HEAD_KEYS) - set(OPTIONAL_HEAD_KEYS)
    if unknown:
        raise BlockError(
            f"[protocol]: unknown field(s) {sorted(unknown)}; "
            f"allowed: {', '.join(PROTOCOL_HEAD_KEYS)}; optional: "
            f"{', '.join(OPTIONAL_HEAD_KEYS)}"
        )
    standard = table.get("standard")
    if not isinstance(standard, str):
        raise BlockError(f'[protocol] standard = {standard!r} — a string, "{STANDARD}"')
    if standard != STANDARD:
        # A protocol with runs is history: AGENTS.md keeps it at its commit and
        # pin and never converts it; only one not yet run may take the
        # migration (the refusal offered "update the protocol" to every
        # protocol alike, against AGENTS.md — review 2026-10-28).
        raise BlockError(
            f"[protocol] standard = {standard!r}, this labkit reads "
            f"{STANDARD!r} — a protocol with runs is reproduced with the "
            f"labkit release it was written for (a checkout of its commit "
            f"with a venv from its own requirements.lock), never converted; "
            f"new work gets a fresh area; only a protocol not yet run may "
            f"be updated ({MIGRATION})"
        )
    missing = [f for f in PROTOCOL_HEAD_KEYS if f not in table]
    if missing:
        raise BlockError(f"[protocol]: missing {', '.join(missing)}")
    pid = table["id"]
    if not isinstance(pid, str):
        raise BlockError(f"[protocol] id = {pid!r} — a string")
    if _placeholder(pid):
        pid = None
    elif not ID_SHAPE.match(pid):
        raise BlockError(
            f"[protocol] id = {pid!r} — expected `p-` plus 16 lowercase "
            f"hex digits, stamped by `labkit-init exp`"
        )
    frozen = table["frozen"]
    if not isinstance(frozen, bool):
        raise BlockError(f"[protocol] frozen = {frozen!r} — true or false")
    audit = table["preflight_audit"]
    if not isinstance(audit, str):
        raise BlockError(f"[protocol] preflight_audit = {audit!r} — a string")
    if _placeholder(audit):
        audit = ""
    return Head(
        standard=standard,
        id=pid,
        type=_choice(table, "type", TYPES),
        repeat_cost=_choice(table, "repeat_cost", REPEAT_COSTS),
        kind=_choice(table, "kind", KINDS),
        frozen=frozen,
        preflight_audit=audit.strip(),
        report=report_field(table.get("report")),
    )


def report_field(value: object) -> str | None:
    """The head's `report` as registered: None when the field is absent,
    else its path relative to the repository root, `/`-separated. Raises
    BlockError on a value that is not a string, is empty, names a path
    outside the repository (absolute, or leading above the root), a
    protocol file, or a file that is not Markdown (`repo.REPORT_SUFFIX`:
    only such a file takes a result or a handover block). Pure: whether
    the file exists is the gate's question, not the head's."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise BlockError(
            f"[protocol] report = {value!r} — the report file as a path relative "
            f'to the repository root, like "REPORT.md"'
        )
    clean = PurePosixPath(posixpath.normpath(value.strip()))
    if clean.is_absolute() or clean.parts[:1] == ("..",):
        raise BlockError(
            f"[protocol] report = {value!r} — a path inside the repository, "
            f"relative to its root"
        )
    if PROTOCOL_NAME.match(clean.name):
        raise BlockError(
            f"[protocol] report = {value!r} — a protocol is no report; the "
            f"report is the file that carries this protocol's result block"
        )
    if clean.suffix != REPORT_SUFFIX:
        raise BlockError(
            f"[protocol] report = {value!r} — a Markdown file ({REPORT_SUFFIX}); "
            f"only such a file takes a result or a handover block"
        )
    return clean.as_posix()


def find_by_id(area: Path, pid: str) -> Path:
    """The one protocol in `area` whose head carries `pid` — the binding a
    run recorded. A run's recorded path goes stale by design (renaming keeps
    the id); raises BlockError when no protocol or several carry it."""
    from labkit.formats.repo import (
        area_protocols,
    )  # layer 1 both; imported late, no cycle

    hits = []
    for p in area_protocols(area):
        try:
            if head(p.read_text(encoding="utf-8")).id == pid:
                hits.append(p)
        except BlockError:
            continue
    if len(hits) != 1:
        raise BlockError(
            f"{len(hits)} protocol(s) in {area} carry id {pid}"
            + (
                ": " + ", ".join(h.name for h in hits)
                if hits
                else " — renamed, moved or re-stamped since the run?"
            )
        )
    return hits[0]
