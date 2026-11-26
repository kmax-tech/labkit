"""prompt_check — the prompt as the protocol states it and as the code sends it.

Every `parse_*` function of an area's scripts is called by name in a test
file (`check_parser_fixtures`: a parser fails silently into a wrong
number) — a call in the syntax tree, not a mention in a comment or
string. Static evidence, a warning: a name match shows no coverage, and a
parser tested through its caller is not seen; whether a test asserts on
the result is not checked;
every line of a `PROMPT` constant without a `{placeholder}` appears in
the protocol's prompt block (`check_prompt_drift`), read through
`prompt_constants` and `protocol_check.registered_prompt_blocks`.

A pipeline that loads its templates from files (stagekit) is held at run
time instead: the area hands every template the run uses to
`require_registered_templates` before the first model call, which
refuses the start unless each stands verbatim in a Prompt block named
after it. The static check above does not see those files.
"""

from __future__ import annotations

from collections.abc import Mapping
import ast
import re
from pathlib import Path

from labkit.checks.code_scan import unreadable_source
from labkit.formats.repo import file_text, shown
from labkit.formats.commands import gate_command, pytest_command
from labkit.formats.gate import LAB_041, LAB_067
from labkit.formats.gate import TECHNICAL_RULE
from labkit.formats.gate import GUARANTEED, STATIC_EVIDENCE
from labkit.formats.scope_sha import (
    SCRIPT_GLOB,
    SourceError,
    area_files,
    parse_source,
    read_source,
    test_files,
)
from labkit.formats.gate import (
    BLOCKER,
    WARNING,
    NOT_EXECUTABLE,
    GateFinding,
    coded,
)
from labkit.formats.protocol_check import (
    named_prompt_blocks,
    registered_prompt_blocks,
    template_drift,
    unheld_prompt_lines,
    unread_prompt_field,
)


PARSE_DEF = re.compile(r"^\s*def (parse_\w+)\s*\(", re.M)


PROMPT_NAME = re.compile(r"^PROMPT(_[A-Z0-9_]+)?$")


def check_parser_fixtures(area: Path, repo: Path) -> list[GateFinding]:
    """Every `parse_*` in the area's scripts is called in some test file under
    the repo's tests/ (`parse_x(…)` or `module.parse_x(…)`). A name in a
    comment, a string or an import is no call.
    Whether the test asserts on the result is not checked. A test file that
    does not parse is a warning that this check could not run for it
    (`NOT_EXECUTABLE`): what it calls cannot be told, so no warning about a
    parser then means "not checked" for the calls that file holds. A script
    that does not read is one blocker (`unreadable_source`): which parsers
    it defines cannot be told."""
    scripts = area_files(area, (SCRIPT_GLOB,))
    parsers: dict[str, Path] = {}
    findings: list[GateFinding] = []
    for sp in scripts:
        try:
            source = read_source(sp)
        except SourceError as exc:
            findings.append(unreadable_source(exc))
            continue
        for m in PARSE_DEF.finditer(source):
            parsers.setdefault(m.group(1), sp)
    if not parsers:
        return findings
    tests = test_files(repo)
    called: set[str] = set()
    for t in tests:
        try:
            tree = parse_source(t)
        except SourceError as exc:
            # it hides only this check's indication, which never blocks: a
            # check not executed for that file, told as a warning
            findings.append(
                coded(
                    WARNING,
                    t.name,
                    f"cannot be parsed ({exc}) · which parsers it calls cannot be told",
                    fix=f"repair it until `{pytest_command(shown(t, Path.cwd()))}` "
                    f"collects it",
                    evidence_kind=GUARANTEED,
                    stated_outcome=NOT_EXECUTABLE,
                    rule=TECHNICAL_RULE,
                )
            )
            continue
        called |= {
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
        }
    for name, sp in sorted(parsers.items()):
        if name not in called:
            findings.append(
                # a name match is an indication, not coverage: a parser
                # tested through its caller has no call of its own
                coded(
                    WARNING,
                    sp.name,
                    f"{name}() is called by no test under tests/ · a parser "
                    f"fails silently into a wrong number",
                    rule=LAB_041,
                    fix=f"give it a test with real raw answers under tests/, "
                    f"then `{gate_command('code-check', area)}`",
                    evidence_kind=STATIC_EVIDENCE,
                )
            )
    return findings


_Value = str | tuple[str, ...]


def _value_of(node: ast.AST, env: dict[str, _Value]) -> _Value | None:  # noqa: C901 complexity baseline 2026-10-08
    """A module-level constant as the script would compute it, or None.

    Read statically, never executed: string literals, names of earlier
    constants, `+`, f-strings over those, `"sep".join(<constant>)`, and the
    keys of a dict or the items of a list/tuple of strings. The stamped
    skeleton builds `PROMPT = "..." + ANSWER_LINE` with
    `ANSWER_LINE = f"... {' or '.join(ANSWERS)}."`; reading literals only
    would leave every stamped prompt unreadable and the drift check idle."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _value_of(node.left, env), _value_of(node.right, env)
        return a + b if isinstance(a, str) and isinstance(b, str) else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.FormattedValue):
                if v.conversion != -1 or v.format_spec is not None:
                    return None
                v = v.value
            part = _value_of(v, env)
            if not isinstance(part, str):
                return None
            parts.append(part)
        return "".join(parts)
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple)):
        items = node.keys if isinstance(node, ast.Dict) else node.elts
        out = []
        for item in items:
            if item is None:
                return None
            v = _value_of(item, env)
            if not isinstance(v, str):
                return None
            out.append(v)
        return tuple(out)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and len(node.args) == 1
        and not node.keywords
    ):
        sep, seq = _value_of(node.func.value, env), _value_of(node.args[0], env)
        if isinstance(sep, str) and isinstance(seq, tuple):
            return sep.join(seq)
    return None


def _script_prompts(source: str) -> tuple[dict[str, str], list[str]]:
    """(readable PROMPT constants, names of unreadable ones) of one script."""
    env: dict[str, _Value] = {}
    found: dict[str, str] = {}
    unreadable: list[str] = []
    for node in ast.parse(source).body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        name = node.targets[0].id
        value = _value_of(node.value, env)
        if value is not None:
            env[name] = value
        if PROMPT_NAME.match(name):
            if isinstance(value, str):
                found[name] = value
            else:
                unreadable.append(name)
    return found, unreadable


def prompt_constants(area: Path) -> dict[str, str]:
    """`PROMPT` / `PROMPT_<VARIANT>` string constants across the area's
    scripts, as the scripts compute them (`_value_of`); the ones it cannot
    compute are `unreadable_prompt_constants`."""
    return _prompts(area)[0]


def unreadable_prompt_constants(area: Path) -> list[str]:
    """`<script>:<NAME>` of every `PROMPT` / `PROMPT_<VARIANT>` constant in
    the area's scripts that `_value_of` does not compute to a string (a
    call other than `"sep".join`, a format spec, a tuple, list or dict) — the ones
    `prompt_constants` leaves out. A script that does not parse is read as
    having none."""
    return _prompts(area)[1]


def _prompts(area: Path) -> tuple[dict[str, str], list[str]]:
    out: dict[str, str] = {}
    unreadable: list[str] = []
    for sp in area_files(area, (SCRIPT_GLOB,)):
        try:
            found, bad = _script_prompts(read_source(sp))
        except (SyntaxError, SourceError):
            continue
        out.update(found)
        unreadable += [f"{sp.name}:{n}" for n in bad]
    return out, unreadable


def require_registered_templates(protocol: Path, templates: Mapping[str, str]) -> None:
    """Refuse the start of a run, before its first model call, unless every
    template it uses is registered verbatim in PROTOCOL: TEMPLATES maps
    each template's name — the one its pipeline registers it under — to
    its text as the pipeline holds it (for stagekit, from its registry).
    A template no Prompt block is named after is not covered and refuses
    the start like one whose text differs from its block; the comparison is
    exact up to line endings, the block's fence indentation and the
    template's one final line ending (`protocol_check.template_drift`, `named_prompt_blocks`).

    What it holds is the template text, not the prompts sent: how the
    placeholders are filled is the area's test's to show, up to the model
    call. Raises ValueError for an empty TEMPLATES, SystemExit naming each
    template that fails, and for a Prompt field that does not read."""
    if not templates:
        raise ValueError(
            "require_registered_templates: TEMPLATES is empty — pass every "
            "template the run uses, by name"
        )
    text = file_text(protocol)
    if text is None:
        raise SystemExit(f"{protocol}: no such protocol — no template is held to it")
    try:
        blocks = named_prompt_blocks(text)
    except ValueError as exc:
        raise SystemExit(unread_prompt_field(protocol.name, exc)) from exc
    drift = template_drift(templates, blocks)
    if drift:
        raise SystemExit(
            f"{protocol.name}: {len(drift)} of {len(templates)} template(s) the run "
            f"uses are not registered as they are — refused before any model "
            f"call:\n  "
            + "\n  ".join(drift)
            + "\nNext: register each template verbatim under its name "
            "(`protocol-fill PROTOCOL --prompts --prompt-file NAME=PATH`), or make "
            "the template the registered text; the Prompt block is the registration"
        )


def check_prompt_drift(area: Path, protocol: Path) -> list[GateFinding]:
    """The protocol's prompt block against the PROMPT constant(s).

    Compared line by line (`protocol_check.unheld_prompt_lines`): every
    non-empty line of the constant that carries no `{placeholder}` must
    appear, stripped, in some registered prompt block
    (`protocol_check.registered_prompt_blocks` — every fence under Prompt but
    the stamp's unfilled one). A block rendered with real data passes; a
    transcript that drifted does not. No registered block, or no readable
    constant: nothing to hold, only the unreadable-constant warnings — each
    a check that could not run for that constant (`NOT_EXECUTABLE`), not a
    breach by it. A Prompt field whose blocks do not read (a block that
    never closes) is one blocker instead, constants or not: the run start
    refuses that protocol with the same sentence (`unread_prompt_field`)."""
    try:
        blocks = registered_prompt_blocks(protocol)
    except ValueError as exc:
        return [
            coded(
                BLOCKER,
                protocol.name,
                unread_prompt_field(protocol.name, exc),
                rule=LAB_067,
                fix=f"close the block with a fence line like its opening one, "
                f"then `{gate_command('code-check', area)}`",
                evidence_kind=GUARANTEED,
            )
        ]
    consts, unreadable = _prompts(area)
    # A prompt this reader cannot compute is unchecked — said aloud, never a
    # silent pass.
    warnings = [
        coded(
            WARNING,
            None,
            f"{name} is not statically readable (a call or a format spec this "
            f"check does not compute) · prompt drift unchecked for it",
            evidence_kind=GUARANTEED,
            stated_outcome=NOT_EXECUTABLE,
            rule=TECHNICAL_RULE,
        )
        for name in unreadable
    ]
    if not consts or not blocks:
        return warnings
    findings: list[GateFinding] = []
    for name, text in sorted(consts.items()):
        fixed = unheld_prompt_lines(text, [])
        missing = unheld_prompt_lines(text, blocks)
        if missing:
            findings.append(
                coded(
                    BLOCKER,
                    protocol.name,
                    f"prompt block drifted from {name}: {len(missing)} of "
                    f"{len(fixed)} fixed line(s) missing, e.g. {missing[0][:60]!r}",
                    rule=LAB_067,
                    fix="paste the rendered `--show` output, not a transcript",
                    evidence_kind=GUARANTEED,
                )
            )
    return warnings + findings
