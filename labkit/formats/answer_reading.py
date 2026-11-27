"""answer_reading — a derived run's declaration of the module that reads an
answer: `runs/<run_id>/answer-reading.json`.

A derived run (`derived_from`) re-reads its parent's rows and makes no model
call. When it declares the module that turns a row's answer into what the
evaluation counts, the parent's code is compared only in that module and
the repo-local modules it imports, not in the whole script
(`run_code_check.code_since_run`): a fix to the evaluation after the
parent ran needs no new measurement, a change to the answer reading still
does. Whether all of the answer reading lies in that module is the
analysis audit's question, not this file's.

The declaration is a file of its own beside config.json, whose fields are
a closed set it leaves as it is. A labkit that does not know the file, and
every reader when the file is missing, compares the parent's whole script:
the way without it is the stricter one.

    {"module": "lib/scenario_rating.py", "labkit": "0.116.0"}

`module` is the file's path under the repository root, `labkit` the
version that started the run. runlog writes it once at the start
(`write_answer_reading`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from labkit.formats.files import read_cause, write_atomic
from labkit.formats.runs import ArtefactError

ANSWER_READING_FILE = "answer-reading.json"


@dataclass(frozen=True)
class AnswerReading:
    """What a derived run declared at its start (module docstring)."""

    module: str  # the module's path under the repository root, POSIX
    labkit: str  # the labkit version that started the run


def write_answer_reading(run_dir: Path, reading: AnswerReading) -> Path:
    """Write RUN_DIR/answer-reading.json from READING; return its path.
    Raises OSError when it cannot be written."""
    path = run_dir / ANSWER_READING_FILE
    write_atomic(
        path,
        json.dumps({"module": reading.module, "labkit": reading.labkit}, indent=1)
        + "\n",
    )
    return path


def read_answer_reading(run_dir: Path) -> AnswerReading | None:
    """The declaration RUN_DIR holds, or None when it holds none. Raises
    ArtefactError naming the file when it does not read, is no object of
    exactly the keys `module` and `labkit`, either is no non-empty string,
    or `module` is absolute or leaves the repository (`..`)."""
    path = run_dir / ANSWER_READING_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtefactError(
            f"{path}: unreadable answer-reading declaration ({exc})",
            cause=read_cause(exc),
        ) from exc
    if not isinstance(data, dict) or set(data) != {"module", "labkit"}:
        raise ArtefactError(
            f"{path}: {data!r} — not an object of the keys module and labkit"
        )
    module, labkit = data["module"], data["labkit"]
    if not isinstance(module, str) or not module:
        raise ArtefactError(f"{path}: module = {module!r}, not a path")
    if not isinstance(labkit, str) or not labkit:
        raise ArtefactError(f"{path}: labkit = {labkit!r}, not a version")
    pure = PurePosixPath(module)
    if pure.is_absolute() or ".." in pure.parts:
        raise ArtefactError(
            f"{path}: module = {module!r} — a path under the repository root"
        )
    return AnswerReading(module=module, labkit=labkit)
