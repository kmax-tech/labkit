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
from pathlib import Path

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


# --- the glance: what a reader takes away before stopping -------------------
#
# A reader who saw the whole protocol cannot report what it knew at line ten
# (round 9: a reader claimed the result from lines that held the legend).
# The glance reader gets only the first lines of the file, as they are: when
# the head or form text uses them up, that is the finding. Lines are unfair
# between writers — one field per long line holds three times the text of a
# wrapped one — so the excerpt's characters are reported beside it, and
# which Summary fields it holds is checked mechanically (guaranteed: the
# field parser, no judgement).

GLANCE_LINES = 10
SUMMARY_FIELDS = ("result", "limits", "next step")

GLANCE_QUESTIONS = (
    (
        "question",
        "What was investigated? One sentence, or null if these lines do not say.",
    ),
    ("result", "What came out? One sentence, or null."),
    (
        "number",
        "The one number the result rests on, as written (digits only), or null.",
    ),
    (
        "criterion_held",
        "Did the success criterion hold — true, false, or null if these lines do not say?",
    ),
    ("how_sure", "How sure or how limited is the result? One sentence, or null."),
    (
        "what_follows",
        "What follows from it — a decision or a next step? One sentence, or null.",
    ),
    (
        "unclear",
        "Every term, abbreviation, code or file name a newcomer would have to look up — a list, [] if none.",
    ),
)


@dataclass(frozen=True)
class Glance:
    """The first lines of a protocol and which Summary fields they hold."""

    excerpt: str
    lines: int
    chars: int
    summary_fields: tuple[
        str, ...
    ]  # of SUMMARY_FIELDS, those whose label is in the excerpt


def glance(text: str, lines: int = GLANCE_LINES) -> Glance:
    """The first `lines` lines of the file as they are, and which of the
    Summary's fields begin inside them."""
    head = text.splitlines()[:lines]
    inside = tuple(
        name
        for name in SUMMARY_FIELDS
        if any(f.name == name and f.line <= lines for f in fields(text))
    )
    excerpt = "\n".join(head)
    return Glance(excerpt, len(head), len(excerpt), inside)


def glance_prompt(excerpt: str, answer_path: str) -> str:
    """The prompt for a reader who sees only the first lines."""
    asks = "\n".join(f'- "{k}": {q}' for k, q in GLANCE_QUESTIONS)
    return (
        "You are a new student who knows basic statistics, but not this "
        "lab, its tools or its words. Below are the FIRST LINES of an "
        "experiment protocol, nothing more — a reader who stops here. Answer "
        "only from these lines; where they do not say, answer null. No files, "
        "no tools except writing your answer.\n\n"
        "Answer with one JSON object with exactly these keys:\n"
        f"{asks}\n\n"
        f"Write the JSON to {answer_path} (a single Bash `cat > … <<'EOF'`), "
        "then reply with the same JSON.\n\n"
        "----- FIRST LINES -----\n"
        f"{excerpt}\n"
        "----- (the protocol continues; you stopped here) -----\n"
    )


@dataclass(frozen=True)
class GlanceScore:
    number_ok: bool | None  # None: the run has no number
    criterion_ok: bool | None  # None: the run reports no criterion
    answered: tuple[
        str, ...
    ]  # of question/result/how_sure/what_follows, those not null
    unclear: list[str]


def score_glance(answer_text: str, truth: Truth, tol: float = 0.006) -> GlanceScore:
    """Hold the glance answer to the run. A null where the run has a value
    counts as not taken away, the same as a wrong one. Raises ValueError
    when the answer is not the asked-for JSON."""
    try:
        data = json.loads(answer_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"glance answer is not JSON: {exc.msg}") from exc
    missing = [k for k, _ in GLANCE_QUESTIONS if k not in data]
    if missing:
        raise ValueError(f"glance answer lacks {missing}")
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
    crit = (
        None
        if truth.criterion_held is None
        else data["criterion_held"] is truth.criterion_held
    )
    answered = tuple(
        k for k in ("question", "result", "how_sure", "what_follows") if data[k]
    )
    unclear = (
        [str(u) for u in data["unclear"]] if isinstance(data["unclear"], list) else []
    )
    return GlanceScore(number_ok, crit, answered, unclear)


# --- terms: is an unclear term explained where the reader would look? -------
#
# Two layers (2026-10-07): a term in the Summary must be plain there — the
# Terms field cannot rescue it; a term in the technical part may be
# explained in Terms or in a glossary note it links. Whether a term OCCURS
# there is checked here — static evidence, never proof of an explanation;
# whether the entry explains it is a reader's judgement (`terms_judge_prompt`).
# Ids are matched as patterns: digit runs become NN, so an entry
# `beschaffungsantrag-NN` covers `beschaffungsantrag-09`.

_LINK = re.compile(r"\]\(([^)\s]+\.md)\)")
_DIGITS = re.compile(r"\d+")
_SPLIT = re.compile(r"\s*(?:/|\(|\)|,|;)\s*")


def normalize_term(term: str) -> str:
    """Casefolded, quotes and backticks gone, digit runs as `nn`."""
    t = term.strip().strip("`'\"“”„").casefold()
    return _DIGITS.sub("nn", t.replace("`", ""))


def _variants(term: str) -> list[str]:
    """The term and the parts a reader lists it by ("A / B (C)")."""
    parts = [term, *_SPLIT.split(term)]
    return [n for n in (normalize_term(p) for p in parts) if len(n) >= 3]


def _section_text(text: str, name: str) -> str:
    return normalize_term(_section(text, name))


def glossary_text(text: str, protocol_path: str | None) -> str:
    """The Terms field's value plus every note it links (read relative to the
    protocol). Raises FileNotFoundError naming a linked note that is gone."""
    terms = next((f for f in fields(text) if f.name.startswith("terms")), None)
    if terms is None:
        return ""
    out = [terms.value]
    if protocol_path is not None:
        base = Path(protocol_path).parent
        for target in _LINK.findall(terms.value):
            note = (base / target).resolve()
            if not note.is_file():
                raise FileNotFoundError(f"Terms links {target}, which is not at {note}")
            out.append(note.read_text(encoding="utf-8"))
    return "\n".join(out)


@dataclass(frozen=True)
class TermHit:
    term: str
    in_summary: bool  # the Summary uses it: Terms does not count there
    in_terms: bool  # it occurs in Terms or a linked glossary (static evidence)


def terms_coverage(
    text: str, unclear: list[str], protocol_path: str | None = None
) -> list[TermHit]:
    summary = _section_text(text, "Summary")
    glossary = normalize_term(glossary_text(text, protocol_path))
    hits = []
    for term in unclear:
        vs = _variants(term)
        hits.append(
            TermHit(
                term,
                in_summary=any(v in summary for v in vs),
                in_terms=any(v in glossary for v in vs),
            )
        )
    return hits


def terms_judge_prompt(pairs: list[tuple[str, str]], answer_path: str) -> str:
    """Ask a reader whether each entry explains its term (the semantics the
    occurrence check cannot see)."""
    body = "\n\n".join(f"TERM: {t}\nENTRY: {e}" for t, e in pairs)
    return (
        "You are a new student who knows basic statistics, but not this lab. "
        "For each term below you get the entry a protocol gives for it. Does "
        "the entry let you understand the term — what it is, in plain words? "
        "A mere mention, a code, or a pointer elsewhere is not an explanation.\n\n"
        "Answer with one JSON object mapping each term exactly as given to "
        "true (explained) or false (not explained).\n"
        f"Write the JSON to {answer_path} (a single Bash `cat > … <<'EOF'`), "
        "then reply with the same JSON. No files, no other tools.\n\n"
        f"{body}\n"
    )


def entry_for(term: str, glossary: str) -> str | None:
    """The glossary line that mentions the term (pattern-matched), or None."""
    vs = _variants(term)
    for line in glossary.splitlines():
        n = normalize_term(line)
        if any(v in n for v in vs):
            return line.strip()
    return None
