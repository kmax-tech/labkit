"""Stamp WHICH code an audit looked at — the scope hash of §2.A12 / §2.D11.

The audit fields in a protocol claim "this code was audited". A stamp that
covers less than the code determining the number is worse than none: it makes
a stale audit look current. So the scope is everything whose content moves a
reported number — the measure scripts, the analysis scripts, the repo-local
`lib/` files they import (shared anchors and thresholds live there), and the
labkit pin.

Why a command and not a shell one-liner: the one-liner in the first draft of
§2.A12 was
    { cat "$S"; xargs -a "$S" shasum -a 256; ...; } | shasum -a 256
which on macOS hashed NO file content at all — BSD xargs has no `-a`, and
under zsh's noclobber the `>` that built the list was refused too. It printed
a stable-looking 12-hex stamp while a changed anchor file left it untouched
(2026-09-08). A stamp that cannot go wrong quietly has to be tested code.

The hash covers each file's PATH and its content digest, plus the pin line, so
adding, removing, renaming or editing a scope file all change the stamp.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

DIGEST_CHARS = 12  # enough to spot a mismatch, short enough for a protocol line
AREA_GLOBS = ("scripts/*.py", "analysis/*.py")


def area_files(area: Path) -> list[Path]:
    """The area's own code, in a stable order."""
    out: list[Path] = []
    for pat in AREA_GLOBS:
        out.extend(area.glob(pat))
    return out


def find_pin(start: Path, name: str = "labkit==") -> tuple[str, str] | None:
    """(file, line) of the labkit pin, searched upwards from the area."""
    for d in [start, *start.parents]:
        for fn in ("requirements.lock", "requirements.txt"):
            p = d / fn
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith(name) or s.startswith("labkit @"):
                    return str(p), s
    return None


def scope_sha(files: list[Path], pin: str | None) -> str:
    """Digest over (path, content digest) per file plus the pin line."""
    h = hashlib.sha256()
    for f in sorted({str(f) for f in files}):
        h.update(f.encode("utf-8") + b"\n")
        h.update(hashlib.sha256(Path(f).read_bytes()).hexdigest().encode() + b"\n")
    if pin:
        h.update(pin.encode("utf-8") + b"\n")
    return h.hexdigest()[:DIGEST_CHARS]


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__.strip().splitlines()[0])
        print("usage: scope-sha [--area DIR] [--no-pin] [FILE ...]")
        print("  --area DIR  area whose scripts/*.py + analysis/*.py count "
              "(default: cwd)")
        print("  FILE ...    extra files that determine the number — the "
              "repo-local lib/ files the scripts import (from the audit's "
              "`scope:` list)")
        print("  --no-pin    do not include the labkit pin line")
        return 0

    area = Path(".")
    use_pin = True
    extra: list[Path] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--area":
            if i + 1 >= len(argv):
                print("--area needs a directory")
                return 2
            area = Path(argv[i + 1])
            i += 2
            continue
        if a == "--no-pin":
            use_pin = False
            i += 1
            continue
        extra.append(Path(a))
        i += 1
    if not area.is_dir():
        print(f"scope-sha: no such area: {area}")
        return 2

    files = area_files(area) + extra
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        for m in missing:
            print(f"scope-sha: missing {m}")
        return 2
    if not files:
        print(f"scope-sha: no scope files under {area} (scripts/*.py, "
              f"analysis/*.py) and none named")
        return 2

    pin_found = find_pin(area.resolve()) if use_pin else None
    sha = scope_sha(files, pin_found[1] if pin_found else None)

    for f in sorted({str(f) for f in files}):
        print(f)
    if pin_found:
        print(f"{pin_found[1]}   ({pin_found[0]})")
    elif use_pin:
        print("(no labkit pin found — stamp does not cover the shared helpers)")
    print(f"scope sha {sha}")
    return 0


def cli() -> None:
    """Entry point for the installed `scope-sha` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
