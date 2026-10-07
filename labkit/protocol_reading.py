"""protocol_reading — how well a person can read a protocol, measured two ways.

The checks hold a protocol to its registration; nothing measured whether a
person can read it. A reader's assessment of uniagent's protocols
(2026-10-07): strong in content, but about 65 lines of form before the
first sentence for a person, ids and keys in the summary, results as
`key value · key value · …` chains. Two measurements, both cheap:

- **form** (mechanical, static evidence — never proof of readability):
  prose lines before the first field, `·` chains of more than two items,
  the longest field, intent ids / metric keys / run_ids inside the Summary,
  whether the answer carries a table;
- **reader** (an agent that sees only the protocol): `reader_prompt` asks
  for the question, the result with its number, how far it holds and what
  comes next, as JSON; `score_answer` holds the number to the run's and
  keeps the terms the reader could not place. Time comes from the reader's
  transcript (agent_transcript).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from labkit.protocol_check import fields

#: what a reader of the Summary should not have to decode
SUMMARY_CODES = re.compile(
    r"\[[CAB]\d+\]|\b[cab]\d+_\w+|\b\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_[0-9a-f]+\b"
)
CHAIN = re.compile(r"·")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


@dataclass(frozen=True)
class Form:
    """Mechanical readability facts of one protocol (static evidence)."""

    lines: int
    prose_before_first_field: (
        int  # non-blank lines above the first field, the head block excluded
    )
    chains: int  # field values with more than two `·` items
    longest_field: int  # characters of the longest field value
    summary_codes: int  # ids, metric keys, run_ids inside the Summary section
    answer_has_table: bool


def _section(text: str, name: str) -> str:
    m = re.search(rf"^## {name}\b.*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def form(text: str) -> Form:
    lines = text.splitlines()
    found = fields(text)
    first = found[0].line if found else len(lines) + 1
    before, fence = 0, False
    for ln in lines[: first - 1]:
        if ln.strip().startswith("```"):
            fence = not fence
            continue
        if (
            not fence
            and ln.strip()
            and not ln.startswith("#")
            and not ln.strip().startswith("<!--")
        ):
            before += 1
    answer = next((f for f in found if f.name == "answer to the question"), None)
    answer_rows = lines[answer.line : answer.last + 6] if answer else []
    return Form(
        lines=len(lines),
        prose_before_first_field=before,
        chains=sum(1 for f in found if len(CHAIN.findall(f.value)) >= 2),
        longest_field=max((len(f.value) for f in found), default=0),
        summary_codes=len(SUMMARY_CODES.findall(_section(text, "Summary"))),
        answer_has_table=any(TABLE_ROW.match(r) for r in answer_rows),
    )


READER_QUESTIONS = (
    (
        "first_lines",
        "After the first 10 lines only: what had you understood? One sentence, or null.",
    ),
    (
        "question",
        "What did this experiment want to find out? One sentence, your words.",
    ),
    ("result", "What came out? One or two sentences, your words."),
    (
        "number",
        "The one number the result rests on, as written (digits only), or null.",
    ),
    (
        "criterion_held",
        "Did the success criterion registered before the run hold — true, false, or null if the protocol does not say?",
    ),
    (
        "admissible",
        "Did every admissibility condition (the checks that must pass before any verdict) hold — true, false, or null?",
    ),
    ("holds", "How far does the result hold — what limits it? One sentence."),
    ("next", "What happens next, according to the protocol? One sentence, or null."),
    (
        "unclear",
        "Every term, abbreviation, code or file name a newcomer would have to look up — a list, [] if none.",
    ),
    ("effort", "How hard was this protocol to read, 1 (easy) to 5 (very hard)?"),
)


def reader_prompt(protocol_text: str, answer_path: str) -> str:
    """The prompt for a cold reader: the protocol, the questions, the file.
    The reader is a newcomer, not a colleague — a colleague's patience hid
    jargon in rounds 7 and 8 (2026-10-07)."""
    asks = "\n".join(f'- "{k}": {q}' for k, q in READER_QUESTIONS)
    return (
        "You are a new student who knows basic statistics, but not this "
        "lab, its tools or its words. Below is one experiment protocol — read "
        "it to learn what was found, and nothing else: no files, no tools "
        "except writing your answer. Answer only from the protocol.\n\n"
        "Answer with one JSON object with exactly these keys:\n"
        f"{asks}\n\n"
        f"Write the JSON to {answer_path} (a single Bash `cat > … <<'EOF'`), "
        "then reply with the same JSON.\n\n"
        "----- PROTOCOL -----\n"
        f"{protocol_text}\n"
        "----- END -----\n"
    )


@dataclass(frozen=True)
class Truth:
    """What the run says, to hold a reader's answers to; None: it does not say."""

    number: float | None
    criterion_held: bool | None
    admissible: bool | None


def truth_from_metrics(metrics: dict, number_key: str | None) -> Truth:
    """`criterion_pass` when the run reports the whole criterion, else all
    `c<i>_pass`; every `a<i>_pass` for admissibility; the number under
    `number_key`."""

    def flags(prefix: str) -> list[bool]:
        return [
            v
            for k, v in metrics.items()
            if re.fullmatch(rf"{prefix}\d+_pass", k) and isinstance(v, bool)
        ]

    crit = metrics.get("criterion_pass")
    if not isinstance(crit, bool):
        cs = flags("c")
        crit = all(cs) if cs else None
    adm = flags("a")
    value = metrics.get(number_key) if number_key else None
    number = (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )
    return Truth(number, crit, all(adm) if adm else None)


@dataclass(frozen=True)
class ReaderScore:
    number_ok: bool | None  # None: the run has no number to hold it to
    number_read: float | None
    criterion_ok: bool | None = None
    admissible_ok: bool | None = None
    correct: int = 0  # checkable answers right
    checkable: int = 0  # answers the run could decide
    unclear: list[str] = field(default_factory=list)
    effort: int | None = None
    answers: dict = field(default_factory=dict)


def score_answer(answer_text: str, truth: Truth, tol: float = 0.006) -> ReaderScore:
    """Hold the reader's answer to the run. Raises ValueError with a sentence
    when the answer is not the asked-for JSON."""
    try:
        data = json.loads(answer_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"reader answer is not JSON: {exc.msg}") from exc
    missing = [k for k, _ in READER_QUESTIONS if k not in data]
    if missing:
        raise ValueError(f"reader answer lacks {missing}")
    raw = data["number"]
    try:
        read = float(str(raw).replace(",", ".")) if raw is not None else None
    except ValueError:
        read = None
    number_ok = (
        None
        if truth.number is None
        else (read is not None and abs(read - truth.number) <= tol)
    )

    def same(said: object, real: bool | None) -> bool | None:
        return None if real is None else (said is real)

    crit = same(data["criterion_held"], truth.criterion_held)
    adm = same(data["admissible"], truth.admissible)
    checks = [c for c in (number_ok, crit, adm) if c is not None]
    effort = data["effort"] if isinstance(data["effort"], int) else None
    unclear = (
        [str(u) for u in data["unclear"]] if isinstance(data["unclear"], list) else []
    )
    return ReaderScore(
        number_ok=number_ok,
        number_read=read,
        criterion_ok=crit,
        admissible_ok=adm,
        correct=sum(checks),
        checkable=len(checks),
        unclear=unclear,
        effort=effort,
        answers=data,
    )
