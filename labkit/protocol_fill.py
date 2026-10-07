"""protocol-fill — fill one stamped placeholder field, matched by its label.

Filling protocol fields by full-text replacement fails in rounds: the quoted
placeholder block never matches exactly (2026-09-09, twice in one day on the
same protocol — three attempts each until a regex sat). The template stamps
every field as `- **Label †:** <placeholder>`, so the LABEL is the stable
handle; this tool matches it, replaces the `<...>` value (multi-line
placeholders included) and leaves everything else byte-identical.

    protocol-fill PROTOCOL-x.md --list
    protocol-fill PROTOCOL-x.md "Meaning of the gold label" "positive = ..."
    protocol-fill PROTOCOL-x.md --line 27 Question "does Y move X?"

A field that is already filled is refused without --force — overwriting an
answer silently is how two truths happen. Labels are matched with the †
marker and case ignored; an ambiguous label (same label in Summary and a
section) is refused with the line numbers, disambiguate with --line.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from labkit.protocol_check import field_name, fields, placeholder_fields

# Bullet and indentation of a label line, kept when the line is rewritten.
_LEAD = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+)?")


def fill(
    text: str, field: str, value: str, line_no: int | None = None, force: bool = False
) -> str:
    """Return the protocol text with `field`'s placeholder replaced by `value`.

    Fields are read by `protocol_check.fields` — the one parser of labels
    and placeholders; a second one here mis-read a wrapped label as
    `extremes)` (usability probe 2026-10-07). The label line and its
    continuation lines become one line; everything else stays byte-identical.

    Raises ValueError with a human-readable reason (unknown label, ambiguous
    label, already filled without force) — the CLI prints it verbatim.
    """
    want = field_name(field)
    hits = [
        f
        for f in fields(text)
        if f.name == want and (line_no is None or f.line == line_no)
    ]
    if not hits:
        labels = sorted({lbl for _, lbl in placeholder_fields(text)})
        raise ValueError(
            f"no field labelled {field!r}"
            + (f" at line {line_no}" if line_no else "")
            + (
                ". Open placeholder fields: " + " · ".join(labels)
                if labels
                else ". No placeholder fields left."
            )
        )
    if len(hits) > 1:
        where = ", ".join(str(f.line) for f in hits)
        raise ValueError(
            f"label {field!r} matches lines {where} — disambiguate with --line <n>."
        )
    (f,) = hits
    if not f.placeholder and not force:
        raise ValueError(
            f"line {f.line} ({f.label!r}) is already filled: "
            f"{f.value[:80]!r}. Overwrite with --force."
        )
    lines = text.splitlines()
    lead = _LEAD.match(lines[f.line - 1])
    assert lead is not None, "the pattern matches the empty prefix"
    lines[f.line - 1 : f.last] = [f"{lead.group(0)}**{f.label}:** {value}"]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="protocol-fill",
        description="Fill one stamped placeholder field in a PROTOCOL-*.md, "
        "matched by its label (never by quoting the placeholder "
        "text). --list shows what is still open.",
    )
    ap.add_argument("protocol", type=Path)
    ap.add_argument("field", nargs="?", help="field label († optional)")
    ap.add_argument("value", nargs="*", help="the field's new value")
    ap.add_argument(
        "--list", action="store_true", help="list open placeholder fields and exit"
    )
    ap.add_argument(
        "--line",
        type=int,
        default=None,
        help="line number, when the label is ambiguous",
    )
    ap.add_argument(
        "--force", action="store_true", help="overwrite a field that is already filled"
    )
    args = ap.parse_args(argv)
    if not args.protocol.is_file():
        print(f"protocol-fill: no such file: {args.protocol}")
        return 2
    text = args.protocol.read_text(encoding="utf-8")
    if args.list:
        holes = placeholder_fields(text)
        if not holes:
            print("no placeholder fields left")
        for n, label in holes:
            print(f"{n:4d}  {label}")
        return 0
    if not args.field or not args.value:
        ap.error("need FIELD and VALUE (or --list)")
    try:
        new = fill(
            text, args.field, " ".join(args.value), line_no=args.line, force=args.force
        )
    except ValueError as exc:
        print(f"protocol-fill: {exc}")
        return 1
    args.protocol.write_text(new, encoding="utf-8")
    print(f"filled: {args.field}")
    return 0


def cli() -> None:
    """Entry point for the installed `protocol-fill` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
