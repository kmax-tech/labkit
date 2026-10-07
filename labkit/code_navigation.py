"""code_navigation — how fast a newcomer finds their way in a repo's code, measured.

The protocol probes measure whether a person can read what a run found; this
one measures whether a person can find where the code does a thing. A cold
agent gets the repo and a few questions that describe a behaviour, never a
name ("where is decided which of the repeated answers counts?"), and answers
each with `path:line`. Two measures:

- **found** (guaranteed): the answer's file and line fall inside the symbol
  that is the truth — a function, a class or a module-level name, resolved
  from the source with `ast`, so a truth that no longer exists refuses to
  score instead of scoring wrong;
- **effort** (from the agent's transcript, `agent_transcript`): tool calls,
  files opened, searches, seconds.

Questions and truth live in a TOML file:

    [[question]]
    id = "majority"
    question = "When a model step asks the same question several times, ..."
    truth = ["src/agent/model/call.py:majority"]   # any of them counts

A truth names a symbol, or — for logic that has no name of its own — a line
range, `path:L120-L135`; a range is only as good as the commit it was read
on, so a question file with ranges belongs to that commit. A flow question
asks for the steps of an entry point in order and is scored by how many of
its registered steps the answer names in the right order:

    [[flow]]
    id = "finalize_steps"
    question = "List, in order, the checks ..."
    steps = [["completion", "complet"], ["intent ids", "intent|promis"]]
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from labkit import agent_transcript


class NavigationError(ValueError):
    """A question file or a truth that cannot be used; the message names it."""


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    truth: tuple[str, ...]  # "path:symbol", path relative to the repo


def load_questions(path: Path) -> list[Question]:
    """The questions of a TOML file. Raises NavigationError naming the entry."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out = []
    for n, q in enumerate(data.get("question", []), 1):
        missing = [k for k in ("id", "question", "truth") if k not in q]
        if missing:
            raise NavigationError(f"{path.name}: question {n} lacks {missing}")
        if not q["truth"]:
            raise NavigationError(f"{path.name}: question {q['id']} has no truth")
        out.append(Question(q["id"], q["question"], tuple(q["truth"])))
    if not out:
        raise NavigationError(f"{path.name}: no [[question]] entries")
    return out


def symbol_span(repo: Path, truth: str) -> tuple[str, int, int]:
    """(path, first line, last line) of `path:symbol` — a function, class or
    module-level assignment; `Class.method` for a method. Raises
    NavigationError when the file or the symbol is not there."""
    path, _, symbol = truth.partition(":")
    source = repo / path
    if not source.is_file():
        raise NavigationError(f"truth {truth}: no file {source}")
    lines = re.fullmatch(r"L(\d+)-L(\d+)", symbol)
    if lines:
        return path, int(lines.group(1)), int(lines.group(2))
    if not symbol:
        return path, 1, len(source.read_text(encoding="utf-8").splitlines())
    nodes: list[ast.stmt] = ast.parse(source.read_text(encoding="utf-8")).body
    node: ast.stmt | None = None
    for part in symbol.split("."):
        node = next((n for n in nodes if _names(n) and part in _names(n)), None)
        if node is None:
            raise NavigationError(f"truth {truth}: no {part!r} in {path}")
        nodes = node.body if isinstance(node, ast.ClassDef) else []
    assert node is not None
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return path, first, node.end_lineno or node.lineno


def _names(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def prompt(
    repo: Path,
    questions: list[Question],
    answer_path: str,
    flows: tuple[Flow, ...] = (),
) -> str:
    """The prompt for a cold agent in `repo`."""
    asks = "\n".join(f'- "{q.id}": {q.question}' for q in questions)
    if flows:
        asks += "\n" + "\n".join(
            f'- "{f.id}" (a list of short strings, one per step, in order): {f.question}'
            for f in flows
        )
    return (
        f"You are new to the code repository at {repo}. Find where the code "
        "does each of the things below. Look around the repository as you "
        "normally would — read, search, list — but change nothing and run "
        "nothing that writes or runs the code.\n\n"
        "Answer with one JSON object: for each key below, the place as "
        '"path:line" (path relative to the repository root, the line where '
        "the code doing it starts), or null if you could not find it.\n"
        f"{asks}\n\n"
        f"Write the JSON to {answer_path} (a single Bash `cat > … <<'EOF'`), "
        "then reply with the same JSON.\n"
    )


_PLACE = re.compile(r"^\s*`?(?:\./)?([^\s:`]+):(\d+)")


@dataclass(frozen=True)
class Found:
    id: str
    answer: str | None
    file_right: bool
    found: bool  # file right and the line inside the truth's span
    truth: str  # the truth spans, "path:first-last"


def score(answer_text: str, questions: list[Question], repo: Path) -> list[Found]:
    """Hold each answer to its truth. Raises ValueError when the answer is
    not the asked-for JSON, NavigationError when a truth no longer exists."""
    try:
        data = json.loads(answer_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"navigation answer is not JSON: {exc.msg}") from exc
    missing = [q.id for q in questions if q.id not in data]
    if missing:
        raise ValueError(f"navigation answer lacks {missing}")
    out = []
    for q in questions:
        spans = [symbol_span(repo, t) for t in q.truth]
        raw = data[q.id]
        m = _PLACE.match(str(raw)) if raw else None
        path, line = (m.group(1), int(m.group(2))) if m else (None, None)
        file_right = any(path == p for p, _, _ in spans)
        found = any(
            path == p and line is not None and a <= line <= b for p, a, b in spans
        )
        out.append(
            Found(
                q.id,
                raw,
                file_right,
                found,
                ", ".join(f"{p}:{a}-{b}" for p, a, b in spans),
            )
        )
    return out


@dataclass(frozen=True)
class Flow:
    id: str
    question: str
    steps: tuple[tuple[str, str], ...]  # (name, regex a mention of the step matches)


def load_flows(path: Path) -> list[Flow]:
    """The flow questions of a TOML file (none is fine)."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in data.get("flow", []):
        missing = [k for k in ("id", "question", "steps") if k not in f]
        if missing:
            raise NavigationError(f"{path.name}: a flow lacks {missing}")
        out.append(Flow(f["id"], f["question"], tuple((n, r) for n, r in f["steps"])))
    return out


def flow_in_order(answer: list[str], flow: Flow) -> int:
    """How many registered steps the answer names in the registered order —
    the longest run of steps whose first mentions rise through the answer."""
    first: list[int] = []
    for _, pattern in flow.steps:
        hit = next(
            (i for i, item in enumerate(answer) if re.search(pattern, item, re.I)),
            None,
        )
        if hit is not None:
            first.append(hit)
    best: list[int] = []  # longest strictly increasing subsequence of `first`
    for x in first:
        i = next((k for k, v in enumerate(best) if v >= x), len(best))
        best[i : i + 1] = [x]
    return len(best)


@dataclass(frozen=True)
class Effort:
    seconds: int
    calls: int
    by_tool: dict[str, int] = field(default_factory=dict)
    files_opened: list[str] = field(default_factory=list)  # Read calls, no repeats


def effort(transcript: Path, repo: Path) -> Effort:
    """What the agent did to find its answers, from its transcript."""
    calls, first, last = agent_transcript.read_calls(transcript)
    by_tool: dict[str, int] = {}
    opened: list[str] = []
    for c in calls:
        by_tool[c.tool] = by_tool.get(c.tool, 0) + 1
        reads = (
            [c.text]
            if c.tool == "Read"
            else agent_transcript.shell_reads(c.text)
            if c.tool == "Bash"
            else []
        )
        for f in reads:
            rel = f.removeprefix(str(repo) + "/").removeprefix("./")
            if rel not in opened:
                opened.append(rel)
    return Effort(round(last - first), len(calls), by_tool, opened)
