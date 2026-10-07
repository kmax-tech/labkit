"""labkit-audit — the experiment-preflight audit, through any llm backend.

    labkit-audit <AREA> --mode preflight|analysis [--protocol FILE] [--model ALIAS]
                 [--timeout S] [--out FILE]

The agent audit of §2.A12 (preflight, before freezing) and §2.D11
(analysis, before a number leaves) as a command instead of a Claude
subagent: the instructions ship with the package
(`experiment-preflight.agent.md`), the files the agent is told to read are
gathered here and inlined — the area's protocol, `scripts/*.py`,
`analysis/*.py`, the repo-local `lib/` modules they import, and the repo's
`docs/arbeitsstandard.md` — and one call goes through `labkit.llm` to the
alias the lab's `models.toml` names. `claude -p` runs without tools, so the
inlined text is all the auditor sees. Synchronous, with a timeout: on
expiry the command fails, it never waits on in the background.

Exit codes are the contract:
    0  no blocker and no warning
    1  findings to decide — a blocker OR a warning (labkit-paper benchmark,
       2026-10-06: the table-led audit found the positional-join fault only
       as a WARNING; an audit that passed on warnings would have let it by)
    2  no audit: a missing file, an unreadable report, a backend failure

The report is printed (and written to --out); deciding the findings and
stamping the protocol field stays with the human (§2.A12). The command
prints the stamp's facts — date, scope sha, counts — to copy from.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from labkit import llm
from labkit.repo import area_protocols, layout_root
from labkit.scope_sha import area_stamp, imported_lib

AGENT = Path(__file__).with_name("experiment-preflight.agent.md")
DEFAULT_MODEL = "opus"            # the agent's model; any alias of models.toml works
DEFAULT_TIMEOUT_S = 900           # one call reads the standard (~100 kB) plus the area
MODES = ("preflight", "analysis")

FINDING = re.compile(r"^[\s>*`-]*\**(BLOCKER|WARNING|NOTE)\**\s*·", re.M)
VERDICT = re.compile(r"verdict:\s*(\d+)\s*blockers?(?:\(s\))?,\s*(\d+)\s*warnings?(?:\(s\))?"
                     r"(?:,\s*(\d+)\s*notes?(?:\(s\))?)?", re.I)
INLINE_NOTE = ("The files you are told to read are inlined below instead of read with "
               "tools; each starts with a `===== FILE: <path> =====` line. Nothing else "
               "is in scope.")


class AuditError(RuntimeError):
    """No audit could be made — the cause is in the message."""


def instructions() -> str:
    """The agent's instructions as shipped, without the provenance comment."""
    return re.sub(r"^<!--.*?-->\n", "", AGENT.read_text(encoding="utf-8"), count=1, flags=re.S)


def gather(area: Path, protocol: Path | None) -> tuple[Path, list[Path], Path]:
    """(protocol, code files, standard) the agent reads; refuses what is missing."""
    if not area.is_dir():
        raise AuditError(f"no such area: {area}")
    protocols = area_protocols(area)
    if protocol is not None:
        chosen = protocol
    elif len(protocols) == 1:
        chosen = protocols[0]
    else:
        raise AuditError(f"{len(protocols)} protocols in {area} — name one with --protocol: "
                         + ", ".join(p.name for p in protocols))
    if not chosen.is_file():
        raise AuditError(f"no such protocol: {chosen}")
    repo = layout_root(area)
    code = sorted(area.glob("scripts/*.py")) + sorted(area.glob("analysis/*.py"))
    if not code:
        raise AuditError(f"{area}: no scripts/*.py or analysis/*.py — nothing to audit")
    code += imported_lib(area, repo)
    standard = repo / "docs" / "arbeitsstandard.md"
    if not standard.is_file():
        raise AuditError(f"{standard} is missing — the audit reads the repo's standard "
                         f"(scar table, severity legend); stamp it with `lib init`")
    return chosen, code, standard


def render(mode: str, area: Path, protocol: Path, code: list[Path], standard: Path) -> str:
    """The one prompt: instructions, MODE line, then every file verbatim."""
    repo = layout_root(area)

    def rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(repo.resolve()))
        except ValueError:
            return str(p)
    files = "".join(f"===== FILE: {rel(p)} =====\n{p.read_text(encoding='utf-8')}\n"
                    for p in [protocol, *code, standard])
    return (f"{instructions()}\n\nMODE: {mode} · AREA: {rel(area)}\n\n"
            f"{INLINE_NOTE}\n\n{files}")


def parse(text: str) -> dict:
    """{"verdict": (blockers, warnings, notes), "findings": [(grade, line)]} from
    the LAST verdict line (an auditor may correct itself), findings from the
    text before it. Raises AuditError when no verdict line is readable."""
    matches = list(VERDICT.finditer(text or ""))
    if not matches:
        raise AuditError("the report has no readable `verdict:` line — not an audit")
    m = matches[-1]
    body = (text or "")[:m.start()]
    findings = [(f.group(1), line.strip()) for line in body.splitlines()
                if (f := FINDING.match(line))]
    return {"verdict": (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)),
            "findings": findings, "scope": scope_list((text or "")[m.end():])}


def scope_list(tail: str) -> list[str]:
    """The auditor's closing `scope:` list — the files it says determine the
    number, one per line (also accepted on the `scope:` line itself)."""
    lines = tail.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("scope:"):
            first = line.strip().removeprefix("scope:").strip()
            rest = [ln.strip().lstrip("-*• ").strip("`") for ln in lines[i + 1:]]
            return [s for s in ([first.strip("`")] if first else []) + rest
                    if s and not s.startswith("```")]
    return []


def scope_mismatch(area: Path, listed: list[str]) -> list[str]:
    """Where the auditor's scope and the stamp disagree. The stamp is what a
    later check recomputes, so a file the auditor read as part of the number
    but the stamp misses can change unnoticed (review 2026-10-07: the list
    was asked for and then dropped)."""
    root = layout_root(area)
    _, files, _ = area_stamp(area)
    stamped = {f.resolve().relative_to(root.resolve()).as_posix()
               for f in files if f.resolve().is_relative_to(root.resolve())}
    named = set()
    for s in listed:
        q = Path(s)
        q = q if q.is_absolute() else root / q
        named.add(q.resolve().relative_to(root.resolve()).as_posix()
                  if q.resolve().is_relative_to(root.resolve()) else s)
    out = [f"the auditor read {n} as part of the number, the stamp does not cover it"
           for n in sorted(named - stamped)]
    out += [f"the stamp covers {s}, the auditor did not list it as read"
            for s in sorted(stamped - named)]
    return out


def stamp_facts(area: Path, verdict: tuple[int, int, int]) -> str:
    """The facts of the protocol's audit field — the human adds the decisions.
    The sha is `scope_sha.area_stamp`, the same a later `scope-sha` recomputes."""
    sha, _, _ = area_stamp(area)
    b, w, n = verdict
    return (f"{time.strftime('%Y-%m-%d')} · scope sha {sha} · {b + w + n} findings "
            f"({b} blockers, {w} warnings, {n} notes — decide each: fixed / accepted / dismissed)")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="labkit-audit", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("area", type=Path)
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--protocol", type=Path, help="the protocol, in an area holding several")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"models.toml alias (default {DEFAULT_MODEL})")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="seconds for the one call")
    ap.add_argument("--out", type=Path, help="also write the report here")
    args = ap.parse_args(argv)
    try:
        protocol, code, standard = gather(args.area, args.protocol)
        prompt = render(args.mode, args.area, protocol, code, standard)
        print(f"labkit-audit: {args.mode} · {protocol.name} · {len(code)} code file(s) · "
              f"{args.model} · {len(prompt) // 1000} kB", file=sys.stderr)
        report = llm.complete(args.model, prompt, timeout=args.timeout, max_tokens=4096)
        result = parse(report)
    except (AuditError, llm.BackendError) as exc:
        print(f"labkit-audit: {exc}", file=sys.stderr)
        return 2
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    b, w, _ = result["verdict"]
    print(f"\nstamp: {stamp_facts(args.area, result['verdict'])}", file=sys.stderr)
    for gap in scope_mismatch(args.area, result["scope"]):
        print(f"scope WARNING: {gap}", file=sys.stderr)
    return 1 if b or w else 0


def cli() -> None:
    """Entry point for the installed `labkit-audit` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
