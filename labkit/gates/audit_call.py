"""audit_call — a model call of the audit's family as an attempt: the
token room a report is given (`report_room`), the errors the audit and
both reviewers refuse with a sentence (`REFUSAL_ERRORS`), and a reviewer's
call journaled from start to answer (`journaled_answer`). `audit`, the
decision review and the report review import it; it imports none of them.
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from pathlib import Path

from labkit.formats import attempts, console
from labkit.run import llm

REPORT_TOKENS = 4096  # room for a report of many findings, where a backend caps


def report_room(alias: str) -> int | None:
    """The token cap an audit report is given: REPORT_TOKENS where the
    backend takes a cap, none where it has none (claude-cli: it sends the
    model's own output cap; an answer past it comes back cut and resumed —
    `llm_backends.UnprovenAnswer`)."""
    return REPORT_TOKENS if llm.takes_max_tokens(alias) else None


#: what the audit and both reviewers refuse with exit 2 and a sentence
#: instead of a traceback: their own errors (AuditError, BackendError,
#: PromptTruncated are RuntimeErrors; FindingsError, ReviewError,
#: ReportReviewError, AttemptError, ProtocolChoiceError, PromiseError are
#: ValueErrors), git failing (RuntimeError), an alias models.toml does not
#: know (KeyError), a file gone. One list for all three, so none refuses
#: less than the others.
REFUSAL_ERRORS = (ValueError, RuntimeError, KeyError, FileNotFoundError)


@contextlib.contextmanager
def journaled_answer(
    area: Path, mode: str, model: str, fingerprint: str, prompt: str, timeout: int
) -> Generator[tuple[attempts.Running, str]]:
    """A reviewer's model call as an attempt of MODE on AREA started on
    FINGERPRINT (`attempts.attempt`): the alias resolved first (an unknown
    one is a usage error, not an attempt), the attempt's notes told, the
    answer kept before anything reads it, its tokens told. The block reads
    and records the answer and ends the attempt (`Running.end`); a block
    that raises ends it `none`. The decision and the report review use it;
    the audit ends its attempt across two steps itself
    (`_answer_or_record`)."""
    room = report_room(model)
    with attempts.attempt(area, mode, model, fingerprint) as running:
        for note in running.notes:
            console.progress("labkit-audit", note)
        answer = llm.complete(model, prompt, timeout=timeout, max_tokens=room)
        running.keep_answer(answer)
        console.progress("labkit-audit", f"tokens · {llm.last_usage().describe()}")
        yield running, answer
