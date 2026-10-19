"""prompt_check — the prompt as the protocol states it and as the code sends it.

Every `parse_*` function of an area's scripts is exercised by a test
(`check_parser_fixtures`: a parser fails silently into a wrong number);
every line of a `PROMPT` constant without a `{placeholder}` appears in
the protocol's prompt block (`check_prompt_drift`), read through
`prompt_constants` and `prompt_blocks`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from labkit.formats import protocol_block
from labkit.formats.protocol_check import fields


PARSE_DEF = re.compile(r"^\s*def (parse_\w+)\s*\(", re.M)


PROMPT_NAME = re.compile(r"^PROMPT(_[A-Z0-9_]+)?$")


PLACEHOLDER_IN_PROMPT = re.compile(r"\{[^{}]*\}")


def check_parser_fixtures(area: Path, repo: Path) -> list[str]:
    """Every `parse_*` in the area's scripts is named in some test file."""
    scripts = (
        sorted((area / "scripts").glob("*.py")) if (area / "scripts").is_dir() else []
    )
    parsers: dict[str, Path] = {}
    for sp in scripts:
        for m in PARSE_DEF.finditer(sp.read_text(encoding="utf-8")):
            parsers.setdefault(m.group(1), sp)
    if not parsers:
        return []
    tests_dir = repo / "tests"
    test_text = (
        "\n".join(
            t.read_text(encoding="utf-8") for t in sorted(tests_dir.glob("test_*.py"))
        )
        if tests_dir.is_dir()
        else ""
    )
    findings = []
    for name, sp in sorted(parsers.items()):
        if not re.search(rf"\b{re.escape(name)}\b", test_text):
            findings.append(
                f"BLOCKER · {sp.name} · {name}() has no test under {tests_dir.name}/ · "
                f"a parser fails silently into a wrong number · give it a fixture "
                f"with real raw answers (LAB-016 Resolution check before freezing, 2026-10-05)"
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
    made every stamped prompt unreadable, so the drift check never ran
    (re-measure 2026-10-07, three of three judge agents)."""
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
    scripts, as the scripts compute them (`_value_of`)."""
    return _prompts(area)[0]


def _prompts(area: Path) -> tuple[dict[str, str], list[str]]:
    out: dict[str, str] = {}
    unreadable: list[str] = []
    scripts = (
        sorted((area / "scripts").glob("*.py")) if (area / "scripts").is_dir() else []
    )
    for sp in scripts:
        try:
            found, bad = _script_prompts(sp.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        out.update(found)
        unreadable += [f"{sp.name}:{n}" for n in bad]
    return out, unreadable


def prompt_blocks(protocol: Path) -> list[str]:
    """Every fenced block under a `Prompt` field, up to the next field at the
    same depth or the next heading — one block per variant is a written
    form, and reading only the first made a null prompt in a second block
    look missing (re-measure 2026-10-07: five false blockers in twelve
    protocols once the check ran). The field is the one label parser's
    (`protocol_check.fields`), the blocks the one fence walker's
    (`protocol_block.fence_spans`): until 0.96.0 a second label grammar
    and a backtick-only fence stood here (audit 2026-10-15)."""
    text = protocol.read_text(encoding="utf-8")
    lines = text.splitlines()
    found = fields(text)
    blocks: list[str] = []
    for n, f in enumerate(found):
        if f.name != "prompt":
            continue
        indent = len(lines[f.line - 1]) - len(lines[f.line - 1].lstrip())
        end = len(lines)
        for g in found[n + 1 :]:
            deeper = len(lines[g.line - 1]) - len(lines[g.line - 1].lstrip()) > indent
            if not deeper:
                end = g.line - 1
                break
        for j in range(f.line, end):
            if lines[j].startswith("#"):
                end = j
                break
        region = lines[f.line : end]
        blocks += [
            "\n".join(region[s:e]) for _, s, e in protocol_block.fence_spans(region)
        ]
    return blocks


def check_prompt_drift(area: Path, protocol: Path) -> list[str]:
    """The protocol's prompt block against the PROMPT constant(s).

    Compared line by line: every non-empty line of the constant that carries
    no `{placeholder}` must appear, stripped, in some prompt block. A block
    rendered with real data passes; a transcript that drifted does not."""
    consts, unreadable = _prompts(area)
    # A prompt this reader cannot compute is unchecked — said aloud, never a
    # silent pass (re-measure 2026-10-07: the stamped skeleton's were).
    warnings = [
        f"WARNING · {name} is not statically readable (a call or a format "
        f"spec this check does not compute) · prompt drift unchecked for it"
        for name in unreadable
    ]
    # a block that only holds a `<placeholder>` is the template's, not a prompt
    blocks = [b for b in prompt_blocks(protocol) if not b.strip().startswith("<")]
    if not consts or not blocks:
        return warnings
    have = {ln.strip() for b in blocks for ln in b.splitlines() if ln.strip()}
    findings = []
    for name, text in sorted(consts.items()):
        fixed = [
            ln.strip()
            for ln in text.splitlines()
            if ln.strip() and not PLACEHOLDER_IN_PROMPT.search(ln)
        ]
        missing = [ln for ln in fixed if ln not in have]
        if fixed and missing:
            findings.append(
                f"BLOCKER · {protocol.name} · prompt block drifted from {name}: "
                f"{len(missing)} of {len(fixed)} fixed line(s) missing, e.g. "
                f"{missing[0][:60]!r} · paste the rendered `--show` output, not a "
                f"transcript (LAB-007 Render check before the instrument check, 2026-10-05)"
            )
    return warnings + findings
