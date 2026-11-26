"""audit_files — the files under an area's audits/: their names by kind, how
one is created without overwriting, and their order as written.

A written file is named `<minute>-<word>[-<n>].toml`: the word is a record's
mode, or a review's word (`REVIEW_WORD`, `CLAIM_REVIEW_WORD`); a failed
attempt ends in `FAILED_SUFFIX`. `create_file` creates one exclusively and
numbers a second file of the minute; `written_order` sorts the files as
written and raises `findings.FindingsError` for a name of no such shape.
`is_record_name` and `names_preflight_record` tell a record of findings by
its name. The journal and the answers folder are named here, written
elsewhere (`attempts`).
"""

from __future__ import annotations

import re
from pathlib import Path

from labkit.formats.repo import EVIDENCE_DIR
from labkit.formats.runs import NAME_MINUTE
from labkit.formats.standard_contract import PREFLIGHT_AUDIT
from labkit.formats.findings import FindingsError, MODES


DIR = EVIDENCE_DIR
#: the attempt journal under DIR (`attempts`)
JOURNAL = "attempts.jsonl"
#: the folder under DIR that keeps each answer, named by its attempt
ANSWERS = "answers"
#: the suffix of a failed attempt's file, never of a record of findings
FAILED_SUFFIX = "-failed.toml"
#: the word a review's file name holds where a record's holds its mode
#: (`<minute>-<word>[-<n>].toml`) — a decision review's and a report
#: review's, then a claim review's. The writers of a name and its readers
#: (`name_ending`, `_WRITTEN_NAME`) take the word from here
REVIEW_WORD = "review"
CLAIM_REVIEW_WORD = "claim-review"


def name_ending(word: str) -> re.Pattern[str]:
    """How the name of a file ends that `create_file` wrote as
    `<minute>-WORD` with the suffix `.toml`: `-WORD[-<n>].toml`
    (`create_file` numbers a second file of the minute before the suffix)."""
    return re.compile(rf"-{re.escape(word)}(?:-\d+)?\.toml$")


#: the name of a decision review (`reviews`), written beside the records
#: and never read as one: `<minute>-review[-<n>].toml`. A claim review's
#: name ends the same way (`report_reviews.CLAIM_REVIEW_NAME` tells it)
REVIEW_NAME = name_ending(REVIEW_WORD)


def create_file(folder: Path, name: str, suffix: str, text: str) -> Path:
    """Write TEXT to `FOLDER/<name><suffix>`, else `<name>-2<suffix>`, … —
    the first name no file holds, taken by exclusive create, so two audits
    finishing in one minute get two files: a check for a free name before
    a plain write would let both take the same one. Creates FOLDER."""
    folder.mkdir(exist_ok=True)
    n = 1
    while True:
        path = folder / f"{name}{'' if n == 1 else f'-{n}'}{suffix}"
        try:
            with path.open("x", encoding="utf-8") as f:
                f.write(text)
        except FileExistsError:
            n += 1
            continue
        return path


#: the minute as `runs.name_minute` writes it, read off its format: four
#: digits for the year, two for every other field
_NAME_MINUTE_SHAPE = re.sub(
    r"%[YmdHM]",
    lambda field: r"\d{4}" if field.group() == "%Y" else r"\d{2}",
    re.escape(NAME_MINUTE),
)
#: the words of the mode's place, the longer first: `claim-review` ends in
#: `review`
_WRITTEN_WORDS = "|".join(
    re.escape(word) for word in (*MODES, CLAIM_REVIEW_WORD, REVIEW_WORD)
)
#: the name `create_file` gives a record, a failed attempt or a review (a
#: decision review, a report review, a claim review under `report-reviews/`):
#: `<minute>-<mode>[-<n>]` and its suffix, n counting the files of one minute
_WRITTEN_NAME = re.compile(
    rf"^({_NAME_MINUTE_SHAPE})-(?P<mode>{_WRITTEN_WORDS})(?:-(?P<n>\d+))?"
    rf"(?P<failed>{re.escape(FAILED_SUFFIX)})?(?(failed)|\.toml)$"
)


def written_order(path: Path) -> tuple[str, int, str]:
    """The sort key of a file `create_file` wrote, oldest first: its minute, then
    its number within the minute as a number — by name, `-2` and `-3`
    would sort before the minute's first file. Raises FindingsError for a name of
    another shape: its age cannot be told."""
    m = _WRITTEN_NAME.match(path.name)
    if m is None:
        raise FindingsError(
            f"{path}: not a name labkit-audit writes (<minute>-<mode>[-<n>].toml) "
            f"— its place among the records cannot be told; rename or move it"
        )
    return (m.group(1), int(m.group("n") or 1), path.name)


def is_record_name(name: str) -> bool:
    """Whether a file directly in `audits/` named NAME is a record of
    findings: TOML, neither a failed attempt nor a decision review."""
    return (
        name.endswith(".toml")
        and not name.endswith(FAILED_SUFFIX)
        and not REVIEW_NAME.search(name)
    )


def names_preflight_record(name: str) -> bool:
    """Does NAME read as a preflight record's file name — the name
    `create_file` gave it under audits/ (`<minute>-preflight[-n].toml`),
    not a failed attempt's?"""
    m = _WRITTEN_NAME.match(name)
    return (
        m is not None and m.group("mode") == PREFLIGHT_AUDIT and not m.group("failed")
    )
