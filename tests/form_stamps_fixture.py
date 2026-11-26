"""The protocol forms the stamp writes today, kept as files for comparison.

`tests/form_stamps/` holds one file per form: `stamp-<cost>-<kind>-<model>-<form>.txt`
(`scaffold.protocol_stamp`, form `short` or `report`) and
`report-high-<kind>-<model>.txt` (an area stamped at high repeat cost, then
`labkit-init exp NAME --report`). The protocol id is written as `FIXED_ID`.
A deliberate change of a form rewrites the files:

    .venv/bin/python tests/form_stamps_fixture.py --write

and the diff is read before the commit. Analysis and plan:
docs/notes/2026-11-13-protocol-field-selection-plan.md.
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

from labkit.formats.protocol_block import PROTOCOL_KINDS
from labkit.formats.runs import REPEAT_COSTS
from labkit.tools import scaffold

FORM_STAMPS = Path(__file__).parent / "form_stamps"
MODELS: tuple[bool | str, ...] = (False, "haiku")
FIXED_ID = "p-0000000000000000"
PROTOCOL_ID = re.compile(r"p-[0-9a-f]{16}")


def model_word(model: bool | str) -> str:
    """`model` or `nomodel`, as the file names spell MODEL."""
    return "model" if model else "nomodel"


def stamp_cases() -> Iterator[tuple[str, str, bool | str, bool]]:
    """Every (cost, kind, model, report) the stamp is compared for: 24."""
    for cost in REPEAT_COSTS:
        for kind in PROTOCOL_KINDS:
            for model in MODELS:
                for report in (False, True):
                    yield cost, kind, model, report


def stamp_file(cost: str, kind: str, model: bool | str, report: bool) -> Path:
    """The kept form of `protocol_stamp` for these answers."""
    form = "report" if report else "short"
    return FORM_STAMPS / f"stamp-{cost}-{kind}-{model_word(model)}-{form}.txt"


def report_file(kind: str, model: bool | str) -> Path:
    """The kept protocol of a high area after `--report`."""
    return FORM_STAMPS / f"report-high-{kind}-{model_word(model)}.txt"


def quiet(f, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201 - passes F's own types through
    """F called with its printing swallowed."""
    with contextlib.redirect_stdout(io.StringIO()):
        return f(*args, **kwargs)


def lab(tmp: str) -> Path:
    """A fresh lab repo under TMP (`labkit-init lab`)."""
    root = Path(tmp) / "lab"
    quiet(scaffold.stamp_lab, root, "lab")
    return root


def fixed_id(text: str) -> str:
    """TEXT with every protocol id written as FIXED_ID."""
    return PROTOCOL_ID.sub(FIXED_ID, text)


def stamped(root: Path, cost: str, kind: str, model: bool | str, report: bool) -> str:
    """`protocol_stamp` for these answers under FIXED_ID."""
    return scaffold.protocol_stamp(root, "x", cost, kind, model, report, pid=FIXED_ID)


def reported(root: Path, cost: str, kind: str, model: bool | str) -> tuple[str, str]:
    """(protocol after the stamp, protocol after `--report`) of a new area
    `x` under ROOT, ids as FIXED_ID. Writes the area."""
    area, _ = quiet(
        scaffold.stamp_area, root, "x", repeat_cost=cost, kind=kind, model=model
    )
    protocol = area / "PROTOCOL-x.md"
    before = protocol.read_text(encoding="utf-8")
    quiet(scaffold.stamp_area, root, "x", report=True)
    return fixed_id(before), fixed_id(protocol.read_text(encoding="utf-8"))


def write_form_stamps() -> None:
    """Rewrite every file under FORM_STAMPS from today's code."""
    FORM_STAMPS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = lab(tmp)
        for cost, kind, model, report in stamp_cases():
            text = stamped(root, cost, kind, model, report)
            stamp_file(cost, kind, model, report).write_text(text, encoding="utf-8")
    for kind in PROTOCOL_KINDS:
        for model in MODELS:
            with tempfile.TemporaryDirectory() as tmp:
                _, after = reported(lab(tmp), "high", kind, model)
            report_file(kind, model).write_text(after, encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] != ["--write"]:
        sys.exit("usage: form_stamps_fixture.py --write")
    write_form_stamps()
