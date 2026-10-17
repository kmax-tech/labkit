"""skeletons — which shipped templates an instrument gets, and the contract
tests they stamp (standard 0.20).

One home for two readers: the scaffolder writes an area from these
templates (`scaffold.stamp_scripts`), and the stamp check holds a stamped
area to them (`stamp_check`). The measure skeleton of a model asks its
model through `labkit.llm`; an estimator's and a count's never do. The
stamped test file carries the resolution check as named test functions,
and a stamped area keeps every one of them (plan II, the stamp check,
2026-10-17).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
TEMPLATES = PACKAGE / "templates"
PROTOCOL_TEMPLATE = PACKAGE / "experiment-protocol.md.template"
#: the script every instrument stamps — the one the stamp check reads
MEASURE_SCRIPT = "scripts/01_measure.py"
#: a test function a template stamps: `def test_…(` at column 0
CONTRACT_TEST = re.compile(r"^def (test_\w+)\(", re.M)


@dataclass(frozen=True)
class Skeleton:
    """The templates an instrument's area is stamped from."""

    scripts: tuple[tuple[str, str], ...]  # (template name, file under scripts/)
    test: str  # the area test's template, stamped as tests/test_<NN>_<name>.py
    asks_a_model: bool  # the measure script imports and calls labkit.llm
    #: the row shape the measure script reads, (field, its legend) — stamped
    #: into 00_prepare.py's FIELDS; a count prepares nothing
    row_fields: tuple[tuple[str, str], ...]


PREPARE = ("prepare-script.py.template", "00_prepare.py")
ANALYZE = ("analyze-script.py.template", "02_analyze.py")
#: the marker line of 00_prepare.py's FIELDS body — replaced by the row shape
ROW_FIELDS_MARK = "<row-fields>"
ID_FIELD = ("id", "unique per row")
SKELETONS: dict[str, Skeleton] = {
    "model": Skeleton(
        scripts=(PREPARE, ("measure-script.py.template", "01_measure.py"), ANALYZE),
        test="test-area.py.template",
        asks_a_model=True,
        row_fields=(
            ID_FIELD,
            ("text", "the item the model reads"),
            ("gold", "TODO: every gold value spelled out, e.g. causal | not_causal"),
        ),
    ),
    "estimator": Skeleton(
        scripts=(
            PREPARE,
            ("measure-estimator-script.py.template", "01_measure.py"),
            ANALYZE,
        ),
        test="test-estimator.py.template",
        asks_a_model=False,
        row_fields=(
            ID_FIELD,
            (
                "features",
                "the numeric features of the item, one list in a fixed order — "
                "computed here, read by the estimator",
            ),
            (
                "gold",
                "TODO: the label or value spelled out; null for the unlabelled "
                "split — a withheld label is no label",
            ),
            ("split", "train | test — train carries gold, test carries null"),
        ),
    ),
    "count": Skeleton(
        scripts=(("measure-quick-script.py.template", "01_measure.py"),),
        test="test-quick.py.template",
        asks_a_model=False,
        row_fields=(),
    ),
}


def row_fields_text(instrument: str) -> str:
    """The FIELDS body of 00_prepare.py for INSTRUMENT, one `"field": "legend",`
    line per field, as the template's marker line is replaced."""
    return "\n".join(
        f"    {field!r}: {legend!r},".replace("'", '"')
        for field, legend in SKELETONS[instrument].row_fields
    )


def template(name: str) -> str:
    """The text of a shipped template; a missing one is a broken install, said so."""
    path = PROTOCOL_TEMPLATE if name == PROTOCOL_TEMPLATE.name else TEMPLATES / name
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} is missing — labkit was installed without its templates"
        )
    return path.read_text(encoding="utf-8")


def contract_tests(instrument: str) -> tuple[str, ...]:
    """The test functions the instrument's test template stamps, in order —
    the resolution check in its permanent form; a stamped area keeps every
    one of them. Raises when the template stamps none: an empty contract
    would hold nothing and say so nowhere."""
    names = tuple(CONTRACT_TEST.findall(template(SKELETONS[instrument].test)))
    if not names:
        raise ValueError(
            f"{SKELETONS[instrument].test} stamps no test function — the contract is empty"
        )
    return names
