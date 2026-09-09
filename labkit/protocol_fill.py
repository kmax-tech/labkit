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

# Same shape protocol_check.PLACEHOLDER parses, split into groups we keep:
# prefix (bullet + emphasis), label, separator (colon + emphasis), value.
FIELD_LINE = re.compile(r"^(\s*[-*]?\s*\*{0,2})([^*<>:]{2,60}?)"
                        r"(\*{0,2}\s*:\*{0,2}\s*)(.*)$")


def _norm(label: str) -> str:
    return label.replace("†", "").strip().lower()


def _placeholder_span(lines: list[str], i: int, value: str) -> int | None:
    """End index (inclusive) of the placeholder starting at line i, or None
    if the value is not a placeholder. `<...>` on one line ends at i; an
    unclosed `<...` runs until the first line containing `>`."""
    v = value.strip()
    if not v.startswith("<"):
        return None
    if ">" in v:
        return i if v.endswith(">") else None
    for j in range(i + 1, len(lines)):
        if ">" in lines[j]:
            return j
    return None


def fill(text: str, field: str, value: str, line_no: int | None = None,
         force: bool = False) -> str:
    """Return the protocol text with `field`'s placeholder replaced by `value`.

    Raises ValueError with a human-readable reason (unknown label, ambiguous
    label, already filled without force) — the CLI prints it verbatim.
    """
    lines = text.splitlines()
    hits: list[tuple[int, re.Match]] = []
    for i, line in enumerate(lines):
        m = FIELD_LINE.match(line)
        if m and _norm(m.group(2)) == _norm(field):
            if line_no is None or i + 1 == line_no:
                hits.append((i, m))
    if not hits:
        labels = sorted({lbl for _, lbl in open_fields(text)})
        raise ValueError(
            f"no field labelled {field!r}"
            + (f" at line {line_no}" if line_no else "")
            + (". Open placeholder fields: " + " · ".join(labels)
               if labels else ". No placeholder fields left."))
    if len(hits) > 1:
        where = ", ".join(str(i + 1) for i, _ in hits)
        raise ValueError(f"label {field!r} matches lines {where} — "
                         f"disambiguate with --line <n>.")
    i, m = hits[0]
    end = _placeholder_span(lines, i, m.group(4))
    if end is None:
        if not force:
            raise ValueError(
                f"line {i + 1} ({m.group(2).strip()!r}) is already filled: "
                f"{m.group(4).strip()[:80]!r}. Overwrite with --force.")
        end = i
    new_line = m.group(1) + m.group(2) + m.group(3) + value
    lines[i:end + 1] = [new_line]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def open_fields(text: str) -> list[tuple[int, str]]:
    """(line number, label) of every field whose value is still a placeholder."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = FIELD_LINE.match(line)
        if m and _placeholder_span(lines, i, m.group(4)) is not None:
            out.append((i + 1, m.group(2).strip()))
    return out


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="protocol-fill",
        description="Fill one stamped placeholder field in a PROTOCOL-*.md, "
                    "matched by its label (never by quoting the placeholder "
                    "text). --list shows what is still open.")
    ap.add_argument("protocol", type=Path)
    ap.add_argument("field", nargs="?", help="field label († optional)")
    ap.add_argument("value", nargs="*", help="the field's new value")
    ap.add_argument("--list", action="store_true",
                    help="list open placeholder fields and exit")
    ap.add_argument("--line", type=int, default=None,
                    help="line number, when the label is ambiguous")
    ap.add_argument("--force", action="store_true",
                    help="overwrite a field that is already filled")
    args = ap.parse_args(argv)
    if not args.protocol.is_file():
        print(f"protocol-fill: no such file: {args.protocol}")
        return 2
    text = args.protocol.read_text(encoding="utf-8")
    if args.list:
        fields = open_fields(text)
        if not fields:
            print("no placeholder fields left")
        for n, label in fields:
            print(f"{n:4d}  {label}")
        return 0
    if not args.field or not args.value:
        ap.error("need FIELD and VALUE (or --list)")
    try:
        new = fill(text, args.field, " ".join(args.value),
                   line_no=args.line, force=args.force)
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
