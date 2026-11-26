"""required_check — the check a finding requires for its repair — a metrics
key, a file, or evidence a follow-up audit shows — read from the finding's
closing field and worded as an order.

The field closes a finding line as `· check: <key>` (`check_of` reads it).
The key is a metrics key, `file:<path>`, or a request a follow-up audit
serves: `diff:` or `code:` (`evidence_request`). `check_order` words what
the check asks for. A malformed request raises ValueError naming the form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from labkit.formats.runs import RUN_ID


#: a finding line's closing field naming the diagnostic a repair must show:
#: `· check: <metrics key>` — the auditor's, fixed when the finding is written
CHECK_FIELD = re.compile(r"·\s*check\s*:")
#: the whole field: the key, then nothing, or a note in one of two forms
#: running to the end of the line — `(<note>)` or `— <note>`. Either may
#: end the line with a sentence's closing period: a dash note keeps it as
#: its last character, after the parenthesis it closes the line and is no
#: part of the note
_CHECK = re.compile(
    r"·\s*check\s*:\s*`?(?P<key>[a-z][a-z0-9_]*|(?:file|diff|code):[^\s`()]+)`?"
    r"(?:\s*\((?P<paren>.*\S.*)\)\.?|\s+[—–]\s+(?P<dash>\S.*))?\s*$"
)
CHECK_KEY = re.compile(r"^(?:[a-z][a-z0-9_]*|(?:file|diff|code):[^\s`()]+)$")
#: a check that asks for a file's content, not a computed value: the run
#: declares the file as a dependency, so the follow-up is shown it
FILE_CHECK = "file:"
#: a check that asks for evidence the audit was not shown for want of
#: room: the code difference of two runs, whole or one path's section of
#: it, or a line range of one file's side of it (`diff_request`) — nothing
#: to build or measure, the follow-up audit shows it
#: (`protocol_runs.requested_pieces`)
DIFF_CHECK = "diff:"
#: a check that asks for one file of a run's code as that run started from
#: it (commit plus uncommitted.patch), whole or a line range
#: (`code_request`) — evidence like DIFF_CHECK, served the same way
CODE_CHECK = "code:"
#: the checks that ask for evidence a follow-up audit shows, nothing a run
#: carries: `fixed` on one says only that the evidence is supplied
REQUEST_CHECKS = (DIFF_CHECK, CODE_CHECK)
CHECK_FORM = (
    "a closing `· check: <metrics key>` (lowercase snake_case), `· check: "
    "file:<repository path>`, `· check: diff:<run>..<run>[:<repository "
    "path>[:old|new:<from>-<to>]]` or `· check: code:<run>:<repository "
    "path>[:<from>-<to>]`, optionally followed by ` (<what it must show>)` "
    "or ` — <what it must show>` to the end of the line"
)
#: a line range closing a request's path: `<from>-<to>`, from 1, inclusive
_LINES = re.compile(r"^(?P<path>.*):(?P<a>[1-9]\d*)-(?P<b>[1-9]\d*)$")
#: the side a diff's line range counts on: the old run's file or the new's
DIFF_SIDES = ("old", "new")


@dataclass(frozen=True)
class DiffRequest:
    """A `diff:` check read (`diff_request`): the code difference of run
    NEW from run OLD, both of the audited area, and PATH, the repository
    path (a file or a folder) whose section of it is asked — None for the
    whole difference; for one file, SIDE (`old` or `new`) and LINES
    (from, to; inclusive) narrow it to the lines of that side's file in
    that range — None for the whole section."""

    old: str
    new: str
    path: str | None
    side: str | None = None
    lines: tuple[int, int] | None = None


@dataclass(frozen=True)
class CodeRequest:
    """A `code:` check read (`code_request`): PATH, a repository path, as
    run RUN started from it, whole or LINES (from, to; inclusive)."""

    run: str
    path: str
    lines: tuple[int, int] | None = None


def _repo_path(check: str, path: str, form: str) -> str:
    """PATH of CHECK when it is a repository path, relative and inside it;
    raises ValueError quoting CHECK and naming FORM otherwise."""
    if not path or path.startswith("/") or ".." in path.split("/") or ":" in path:
        raise ValueError(
            f"check {check!r}: the path is a repository path, relative, inside "
            f"it and without `:` — {form}"
        )
    return path


def _line_range(check: str, m: re.Match[str], form: str) -> tuple[int, int]:
    """The (from, to) M read from CHECK; raises ValueError when to < from."""
    a, b = int(m["a"]), int(m["b"])
    if b < a:
        raise ValueError(f"check {check!r}: line {b} before line {a} — {form}")
    return a, b


def diff_request(check: str) -> DiffRequest:
    """CHECK, `diff:<OLD>..<NEW>`, `diff:<OLD>..<NEW>:<path>` or
    `diff:<OLD>..<NEW>:<path>:<old|new>:<from>-<to>`, read. Raises
    ValueError, quoting it, when a run is no run id, the path is empty,
    absolute or climbs out of the repository, or a line range is not one
    of a side in order."""
    rest = check.removeprefix(DIFF_CHECK)
    pair, colon, path = rest.partition(":")
    old, dots, new = pair.partition("..")
    form = (
        f"`{DIFF_CHECK}<run>..<run>`, `{DIFF_CHECK}<run>..<run>:<repository "
        f"path>` or `{DIFF_CHECK}<run>..<run>:<file>:old|new:<from>-<to>`"
    )
    if not dots or not all(RUN_ID.fullmatch(r) for r in (old, new)):
        raise ValueError(f"check {check!r}: two run ids expected — {form}")
    if not colon:
        return DiffRequest(old, new, None)
    m = _LINES.match(path)
    if m is None:
        return DiffRequest(old, new, _repo_path(check, path, form))
    file, _, side = m["path"].rpartition(":")
    if side not in DIFF_SIDES:
        raise ValueError(
            f"check {check!r}: a line range names the side it counts on, old "
            f"or new — {form}"
        )
    lines = _line_range(check, m, form)
    return DiffRequest(old, new, _repo_path(check, file, form), side, lines)


def code_request(check: str) -> CodeRequest:
    """CHECK, `code:<RUN>:<path>` or `code:<RUN>:<path>:<from>-<to>`, read.
    Raises ValueError, quoting it, when RUN is no run id, the path is
    empty, absolute or climbs out of the repository, or the range is out
    of order."""
    rest = check.removeprefix(CODE_CHECK)
    run, colon, path = rest.partition(":")
    form = f"`{CODE_CHECK}<run>:<repository path>[:<from>-<to>]`"
    if not RUN_ID.fullmatch(run) or not colon:
        raise ValueError(f"check {check!r}: a run id and a path expected — {form}")
    m = _LINES.match(path)
    if m is None:
        return CodeRequest(run, _repo_path(check, path, form))
    return CodeRequest(
        run, _repo_path(check, m["path"], form), _line_range(check, m, form)
    )


def evidence_request(check: str) -> DiffRequest | CodeRequest:
    """A REQUEST_CHECKS check read (`diff_request`, `code_request`); raises
    what they raise, and ValueError on any other check."""
    if check.startswith(DIFF_CHECK):
        return diff_request(check)
    if check.startswith(CODE_CHECK):
        return code_request(check)
    raise ValueError(f"check {check!r} asks for no evidence")


def check_of(text: str) -> tuple[str, str]:
    """(key, note) of the diagnostic a finding line requires for its repair
    — its closing `· check: <key>` field, the note what the auditor wrote
    after the key in one of the two forms of CHECK_FORM (a period closing
    the line is part of a dash note and no part of a parenthesis note) —
    or ("", "") when it requires none. Only the key is machine-read; the note is kept whole.
    TEXT is the finding whole, all its lines searched: one check per
    finding, closing the line that holds it — the last line, or the first
    with the finding's bullets below it. Raises
    ValueError on a field that does not read and on two
    check fields in one finding, quoting the line that holds the last
    one: a requirement half-read, or one of two, would be one nobody can
    be held to."""
    if not CHECK_FIELD.search(text):
        return "", ""
    # the line that holds the last check field, as the refusals quote it
    held = next(x for x in reversed(text.splitlines()) if CHECK_FIELD.search(x))
    if len(CHECK_FIELD.findall(text)) > 1:
        raise ValueError(
            f"two check fields in one finding: {held.strip()[-160:]!r} — one "
            f"finding requires one diagnostic; {CHECK_FORM}"
        )
    m = _CHECK.search(held.rstrip())
    if m is None:
        raise ValueError(
            f"a check field that does not read: {held.strip()[-160:]!r} — the form "
            f"is {CHECK_FORM}"
        )
    if m["key"].startswith(REQUEST_CHECKS):
        evidence_request(m["key"])  # a request no follow-up could serve is refused here
    return m["key"], (m["paren"] or m["dash"] or "").strip()


def request_words(asked: DiffRequest | CodeRequest) -> str:
    """What ASKED names, in words: which runs, file, side and lines — the
    one wording of a request in the decision list and its piece's head."""
    lines = f", lines {asked.lines[0]}–{asked.lines[1]}" if asked.lines else ""
    if isinstance(asked, CodeRequest):
        return (
            f"`{asked.path}`{lines} as run {asked.run} started from it (its "
            f"commit with its uncommitted.patch)"
        )
    if asked.path is None:
        return f"the code difference of run {asked.new} from run {asked.old} whole"
    side = (
        f" of the {asked.side} file (run {asked.old if asked.side == 'old' else asked.new})"
        if asked.side
        else ""
    )
    return (
        f"the section of `{asked.path}`{lines}{side} of the code difference of "
        f"run {asked.new} from run {asked.old}"
    )


def check_order(check: str, note: str = "") -> str:
    """What a finding's required CHECK asks of the measuring code — the one
    wording of the decision list, the follow-up's holds and the agent guide: the
    kept rows carry what the value needs, `evaluate_rows()` computes it from
    them and writes it to metrics.json under CHECK, where the recheck
    recomputes it; NOTE, what it must show. A `file:<path>`
    check asks for the file declared as the run's dependency instead; a
    `diff:` or `code:` check asks nothing of the code, the follow-up audit
    shows the evidence it names (`request_words`). A key alone shows
    nothing: the follow-up judges the computed value; with the check
    unwritten, every follow-up judges the repair not assessable."""
    shows = f" ({note})" if note else ""
    if check.startswith(REQUEST_CHECKS):
        # evidence the audit had no room for: nothing to build or measure
        return (
            f"nothing to build or measure — the follow-up analysis audit shows "
            f"{request_words(evidence_request(check))}{shows}, ahead of every "
            f"other diff, as long as it fits the audit's budget for diffs; "
            f"`fixed` says only: evidence supplied — it confirms neither the "
            f"code nor the claim, the follow-up judges the suspicion on it"
        )
    if check.startswith(FILE_CHECK):
        # a file's content, not a computed value: shown once the run declares
        # it, which no other audit piece shows
        path = check.removeprefix(FILE_CHECK)
        return (
            f"declare `{path}`{shows} among the files the run reads as a dependency "
            f"— in the estimator skeleton `PREDICTOR_FILES`, else runlog's `data=` "
            f"with `provenance.BinaryInput` — so that the run records its digest "
            f"and the analysis audit is shown its content"
        )
    # from the kept rows: the recheck recomputes every metrics key from them
    # and refuses one computed beside them
    return (
        f"extend the measuring script so that its kept rows carry what "
        f"`{check}`{shows} needs and `evaluate_rows()` computes it from them, "
        f"writing the value to metrics.json under that key — the check "
        f"(`02_analyze.py --check`) recomputes every metrics key from the kept "
        f"rows and refuses one computed beside them; a key written as a "
        f"constant shows nothing"
    )
