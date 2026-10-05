#!/usr/bin/env python3
"""Check experiment protocols for mandatory fields (structure-free).

The protocol template (`experiment-protocol.md.template`) is a checklist of
mandatory fields, not a copy-form: protocols may be structured freely, but
every field must occur — an explicit "n/a — <why>" counts, silence does not.
A field counts as present as soon as its concept keywords appear anywhere in
the file, so a protocol must at least *mention* the concepts that hurt when
omitted (scar 2026-08-13: two freely written protocols omitted "Type" and
"Model I/O"; each omission caused a bad run).

The checks, each stated as its current rule (the change history lives in the
commits, Arbeitsstandard §3):

  * **Placeholder detection.** A field whose value is a bare `<...>` is not
    filled; severity follows the field (MUST -> failure, SHOULD -> warning).
    Keyword presence alone once passed 28 protocols of which not one
    contained an actual model input/output (2026-08-17).
  * **Template-line detection.** Any line still identical to a line of the
    template is instruction, not content. Needs `--template PATH` (or the
    template sitting next to this script).
  * **Verbatim-block check.** A protocol that mentions a prompt but contains
    no fenced code block almost certainly paraphrases it — a MUST failure:
    the verbatim prompt and one real example with the model's output are the
    one thing a protocol exists for. Protocols that never mention a prompt
    (no model involved) are untouched; the example itself is the "Raw
    output" MUST field — a link into output/ or an "n/a — <why>" satisfies
    it, silence does not.
  * **Two tiers, one template.** MUST is the pilot minimum (question,
    success, stop rule, type, prompt/IO, null condition); SHOULD is what a
    REPORTABLE run owes on top (rivals, scope, prognosis, yield, knobs,
    result). The graduation gate is mechanical: **`Frozen before run: yes`
    escalates every SHOULD field to MUST.** Claiming confirmatory status is
    claiming the full protocol; an unfrozen pilot's numbers stay pilot
    numbers — "Pilot leicht, Bericht schwer" without a second template that
    would drift (2026-08-18).
  * **Terms are a MUST field.** The template asks for them twice — "Terms of
    this protocol" in the opening block, "Clarified terms" after the dry run
    — and one keyword entry covers both. What the check enforces is the
    *moment of naming*: the definition notes existed, the declaration in the
    protocol was the one thing nothing forced (2026-08-19). Terms sit first
    in MUST because they precede the question they are asked in (CLAUDE.md
    6: Begriff vor Gebrauch).
  * **A measure run demands a written result.** A documented run_id that
    is not a prepare/probe line makes empty `Answer to the question` / `Raw
    output` fields (or a missing Result section) a MUST failure — pilot
    suppression does not apply, because the context that explains the
    numbers dies with the session (2026-08-24).
  * **Change-history prose is a warning.** The current rule belongs in the
    text, the change and its why in the commit message (Arbeitsstandard §3).
    Warning only — load-bearing translation tables (old names still in
    runs.tsv) are legitimate (2026-08-24).

Usage:
    protocol-check PROTOCOL-foo.md [more files or directories ...]
    protocol-check --template experiment-protocol.md.template <files>

Directories are searched recursively for PROTOCOL-*.md. Exit code 1 if any
MUST field is missing or unfilled in any file; SHOULD fields only warn.

Forward-looking: apply to new protocols, do not retrofit old ones (same policy
as runlog).
"""

import re
import subprocess
import sys
from pathlib import Path

# (field label, regex over the whole file)
# Keywords match German AND English: the template's field labels are English
# (2026-08-20), pre-existing protocols name their concepts in German, and
# either language may fill a field — the checker accepts both.
MUST = [
    ("Terms (every label with a half-sentence gloss)",
     r"begriff|terminolog|glossar|terms of"),
    ("Question / hypothesis", r"hypothese|frage|question|hypothesis"),
    ("Success criterion", r"erfolg|success"),
    ("Stop rule", r"abbruch|kill|stop.?rule"),
    ("Type (exploratory / confirmatory)",
     r"explorativ|konfirmatorisch|explorator|confirmator"),
    ("Model I/O / prompt (verbatim)", r"modell-i/o|model i/o|prompt"),
    ("Null condition / anchor / control",
     r"nullbedingung|null.?condition|anker|anchor|placebo|swap|kontroll"),
    # The one thing a protocol exists for: a real example with the model's
    # actual output (embedded or linked). A metric without one is a number
    # nobody can interpret later — the mechanism shows in the single case.
    ("Raw output (one real example + model output)",
     r"roh-output|roh-beispiel|roh-antwort|i/o-beispiel|raw.?output"),
]
MUST_MEASUREMENT = [
    ("Question", r"question|frage"),
    ("Data / scope", r"data\b|scope|daten|skopus|quelle"),
    ("Prior computation", r"prior computation|vorherige berechnung|vorberechnung"),
    ("Method", r"method|methode|skript"),
    ("Exclusions / filters", r"exclusion|filter|ausschluss|ausschl[üu]sse"),
    ("Result", r"result|ergebnis"),
    ("Terms", r"begriff|terminolog|glossar|terms[\s:]"),
]

SHOULD = [
    # Missing in all five freely written protocols of Aug 2026, and the result
    # section was systematically never written back — hence the two nudges.
    ("Frozen before run (ja/yes | nein/no)", r"frozen|eingefroren"),
    ("Result / outcome (write back after the run)",
     r"ergebnis|ausgang|resultat|result|outcome"),
    ("Meaning of the gold label", r"gold"),
    ("Yield per stage", r"ausbeute|yield"),
    ("Rival explanations / confounds", r"rival|konfund|confound"),
    ("Error direction per confound",
     r"fehlerrichtung|error.?direction|richtung der hypothese|zugunsten der hypothese"),
    ("Scope (what is NOT measured)", r"skopus|nicht gemessen|out of scope"),
    ("Free knobs + sensitivity", r"freie[nr]? kn|free knob|sensitivit|sweep"),
    ("Prediction for the follow-up run", r"prognose|vorhersage|prediction"),
    ("Instrument check (dry run before the pilot)",
     r"instrumentenprobe|trockenlauf|rauchtest|instrument check|dry.?run"),
    ("Context (self-contained)",
     r"einordnung|vorgeschichte|selbsttragend|self.?contained"),
]

MUST_V015 = [
    ("Exclusions / filters (what is dropped and why)",
     r"exclusion|filter|ausschluss|ausschl[üu]sse"),
]

# Due from Standard 0.16 on, for experiments AND measurements: the protocol's
# own identity. Nothing in a run said which protocol it belonged to, so in a
# series area (PROTOCOL-s1-* ... PROTOCOL-s13-*) every automatic pairing of
# protocol and run was a guess. The id is what a run binds to; the path is
# only where it was found. Contract: docs/protocol-run-binding.md.
MUST_V016 = [
    ("Protocol id (stamped by `lib exp`, never typed)",
     r"protocol id|protocol_id"),
]

# Due from Standard 0.17 on, measurements only: the counted unit (2026-10-05).
# The one audit question no machine answers — `.DS_Store` counted as a
# document moved a mean by a whole document while test and --check stayed
# green. Said once, in words, in the protocol.
MUST_MEASUREMENT_V017 = [
    ("Unit (what one counted thing is, and what is not)", r"\bunit\b|einheit"),
]

# The shape the stamp produces: `p-` + 16 lowercase hex (64 bit). Not derived
# from name or path, so renaming and moving leave it intact.
PROTOCOL_ID = re.compile(r"protocol[ _]id[^:\n]*:\**\s*\**\s*(\S+)", re.I)
PROTOCOL_ID_SHAPE = re.compile(r"^p-[0-9a-f]{16}$")

# Fields that are only DUE once the template stamps them (2026-09-08). The two
# audit gates — code vs. intent before freezing (§2.A12) and the evaluation
# against the frozen criterion before a number is reported (§2.D11) — are
# enforced through the placeholder mechanism alone: a stamped-but-unfilled
# field is a should-gap, and the graduation gate below turns it into a MUST
# failure at "frozen: yes". They are deliberately NOT in SHOULD, because
# check_text() would then fail every protocol written before the gates
# existed — retrofitting a closed registration buys nothing.
SHOULD_IF_PRESENT = [
    ("Preflight audit (code vs. intent, before freezing)",
     r"preflight|producer-audit|code.?audit"),
    ("Analysis audit (evaluation vs. frozen criterion)",
     r"analysis.?audit|auswertungs-audit"),
    # The resolution check (§2.A13, 2026-09-09): the registered criterion run
    # over synthetic extremes — perfect effect must fire, null effect must
    # stay silent — by the REAL evaluate(), before freezing. Third repeat of
    # the same scar (63 anchor gate, 65 compliance floor, 66 permutation
    # floor: 8 hits on 8 draws p=0.0002, the same 8 on 4 draws p=0.0769).
    # Pattern deliberately narrow: the template's "Answer form + resolution"
    # field must NOT be caught by it.
    ("Resolution check (criterion at synthetic extremes)",
     r"resolution.?check|aufl(ö|oe)sungsprobe"),
    ("Gate labels (expected)",
     r"gate.?label|gate.?etikett"),
    ("Randomness controls",
     r"randomness|zufall|seeds?\b.*\b(run|temperature|temp)|temperature.*(seed|run)"),
    # The cost tier (2026-10-05): seconds | minutes | hours. It decides how
    # much audit a run gets (§2.A12); a stamped-but-unfilled tier is a gap,
    # a protocol from before the field is not.
    ("Cost tier (seconds / minutes / hours)",
     r"\bcost\b|kostenstufe"),
]

#: The three tiers of `Cost:`; anything else in the field is a placeholder
#: or a typo, and `cost_tier_of` returns None for both.
COST_TIERS = ("seconds", "minutes", "hours")
COST_TIER = re.compile(r"\bcost\b[^:\n]*:\**\s*\**\s*(seconds|minutes|hours)\b", re.I)

# "Frozen before run: yes" without a single rendered example is a frozen
# registration on an unchecked instrument — it freezes the error in. On
# 2026-08-17 a 12-call dry run found the prompt asking for ENTAILMENT while
# the gold label means DEGREE OF SUPPORT; a 9-call dry run saved 440 calls.
# Neither would have happened in a "frozen" protocol without an I/O example.
FROZEN_YES = re.compile(r"frozen before run[^:\n]*:\**\s*\**\s*(ja|yes)\b", re.I)

STANDARD_VERSION = re.compile(r"standard[^:\n]*:\**\s*\**\s*(\d+\.\d+)\b", re.I)
DEFAULT_STANDARD = "0.13"

# The highest `Standard: <x.y>` these gates implement. A protocol declaring a
# newer standard was written against gates this code does not know — checking
# it anyway produces false findings, not fewer findings (2026-09-14: a
# pre-0.15 checker flagged the 0.15 template's own stamped preamble as
# "verbatim template text" all session long). Too old to judge is a hard
# failure that says so, never a best effort.
SUPPORTED_STANDARD = "0.17"


def _std(standard: str) -> tuple[int, ...]:
    """Standard version as a comparable tuple — string comparison would put
    "0.9" above "0.15" and misapply every versioned gate."""
    return tuple(int(p) for p in standard.split("."))

TYPE_MEASUREMENT = re.compile(
    r"^\s*[-*]?\s*\*{0,2}typ[e]?[^:\n]*:\*{0,2}\s*\*{0,2}\s*measurement\s*$|"
    r"^\s*[-*]?\s*\*{0,2}typ[^:\n]*:\*{0,2}\s*\*{0,2}\s*messung\s*$", re.I | re.M)

# The mirror image of the graduation gate: a protocol that explicitly declares
# `Frozen before run: nein` is a pilot BY DECLARATION. Its missing SHOULD
# fields are not gaps but fields that are not yet due — listing them one by
# one trains the reader to ignore the checker. One summary line instead.
FROZEN_NO = re.compile(r"frozen before run[^:\n]*:\**\s*\**\s*(nein|no)\b", re.I)

# runlog run ids as they appear in the run index: 2026-08-23T20-37-21_afbe. A
# line carrying one that is NOT data preparation or a throwaway probe is a
# measure run — from then on an empty Result is a MUST gap, pilot or not.
RUN_ID = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_[0-9a-f]{2,12}\b")
SETUP_RUN = re.compile(r"prepare|probe|wegwerf|trockenlauf|dry.?run", re.I)
# A labelled Result field whose value is nothing but (em-)dashes. A bare
# "Label:" at end of line is NOT empty — multi-line values start on the next
# line (the 25er protocol writes them that way; first version false-alarmed).
EMPTY_ANSWER = re.compile(
    r"(?im)^\s*[-*]?\s*\*{0,2}(answer to the question|antwort auf die frage)"
    r"[^:\n]*:\**\s*[—–-]+\s*$")
EMPTY_RAW = re.compile(
    r"(?im)^\s*[-*]?\s*\*{0,2}(raw output|roh-output)[^:\n]*:\**\s*[—–-]+\s*$")
# A follow-up registration appended to the SAME protocol — the pattern that
# grew one file to 649 lines out of three experiments ("Lauf B — ...
# (deklariert vor dem Lauf)", "Stufe 2 ..."): each such heading is a second
# question in a one-question file. The series rule (Arbeitsstandard §2.F)
# gives every follow-up its own PROTOCOL-s<N>-<slug>.md. Warning only.
SERIES_HEAD = re.compile(
    r"(?im)^##.*\((deklariert|registriert) vor dem( jeweils \w+)? "
    r"(lauf|vote|pilot)|declared before the run\)?")

# The documented runs are mandatory content (one line per run_id), not prose —
# counting it against the length budget taught people not to document runs
# (found 2026-09-06: 93 of a protocol's 409 lines were its run list).
# "ledger" stays in the pattern, not in the vocabulary: protocols written
# before 2026-09-26 head the section "## Runs (ledger — ...)".
DOCUMENTED_RUNS_HEAD = re.compile(r"(?i)^##\s.*(runs|ledger|l[\u00e4a]ufe)")

# Change-history prose — the doc should carry the current rule, the commit the
# change (Arbeitsstandard §3). Warning only.
CHANGELOG = re.compile(
    r"seit 20\d\d-\d\d|wieder drau[ßs]+en|wieder drin\b|hie[ßs]+ bis"
    r"|vorher (stand|galt)|fr[üu]her hie[ßs]+|umbenannt am", re.I)

# Line budget per section. The global 350 only bites once a protocol is
# already unreadable; the per-section budgets sit between the corpus median
# and its upper quartile, so they flag roughly the top third instead of
# everything (a warning that fires on every file is background noise).
# Calibration 2026-09-15, 94 protocols with an Intent section across
# ~/projects + ~/work: Intent median 25, Q3 38 — but confirmatory protocols
# (n=59) sit at median 30, because the [K/S/W/N] intent ids moved mandatory
# registrations INTO Intent; the disciplined confirmatory cluster tops out
# at 35 prose lines, so the budget sits at that ceiling and still flags the
# top quarter. Setup as before (median 42, top quartile above 54; only 556
# of 3344 Setup lines are code blocks — the length is prose, not evidence).
# Needs more room? That is a note, and here stands its [[wikilink]].
SECTION_BUDGET = [
    ("Summary", r"summary|zusammenfassung", 20),
    ("Context", r"context|einordnung", 20),
    ("Intent", r"intent|absicht|hypothese und kriterien|die eine frage", 35),
    ("Setup", r"setup|aufbau", 45),
]


def oversized_sections(text: str) -> list[tuple[str, int, int]]:
    """(label, prose lines, budget) for each section over budget.

    Counted like the global length check: code fences (rendered examples are
    mandatory raw output) and table rows do not count against the budget.
    """
    counts: dict[str, int] = {}
    cur, fence = None, False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fence = not fence
            continue
        if fence or stripped.startswith("|"):
            continue
        if stripped.startswith("## "):
            head = stripped[3:].lower()
            cur = next((lb for lb, pat, _ in SECTION_BUDGET
                        if re.search(pat, head)), None)
            continue
        if cur:
            counts[cur] = counts.get(cur, 0) + 1
    return [(lb, counts[lb], lim) for lb, _, lim in SECTION_BUDGET
            if counts.get(lb, 0) > lim]


# `- **Feld:** <noch nicht ausgefuellt>` — a label followed by a bare
# placeholder. `<offen ...>` and `<TODO ...>` count too: they are honest, but
# they are still not a filled field, and the point of the check is to make the
# gap visible rather than to reward the wording.
PLACEHOLDER = re.compile(r"^\s*[-*]?\s*\*{0,2}([^*<>:]{2,60}?)\*{0,2}\s*:\*{0,2}\s*<[^>]*>?\s*$")


def placeholder_fields(text: str) -> list[tuple[int, str]]:
    """(line number, label) for every field whose value is still a placeholder."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        m = PLACEHOLDER.match(line)
        if m:
            out.append((n, m.group(1).strip()))
    return out


def template_lines(path: Path | None) -> set[str]:
    """Instruction lines of the template, normalised for comparison.

    The preamble — everything before the first `## ` section — is the
    stamped legend (field-id key, standard version, guide pointer). It is
    MEANT to survive filling, so it must not count as "still verbatim
    template text": counting it flagged every freshly stamped protocol
    forever and taught people to delete the legend (2026-09-14/15, two
    sessions of false positives on a correctly filled protocol).
    """
    if path is None or not path.exists():
        return set()
    keep = set()
    in_body = False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("## "):
            in_body = True
        # Only lines long enough to be distinctive; headings are meant to recur.
        if in_body and len(s) >= 40 and not s.startswith("#"):
            keep.add(s)
    return keep


def find_template(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    here = Path(__file__).resolve().parent / "experiment-protocol.md.template"
    return here if here.exists() else None


def find_field_guide() -> Path | None:
    here = Path(__file__).resolve().parent / "protocol-field-guide.md"
    return here if here.exists() else None


def severity_of(label: str) -> str:
    """Does this placeholder sit in a MUST field, a SHOULD field, or neither?"""
    low = label.lower()
    for _, pat in MUST + MUST_V015 + MUST_V016:
        if re.search(pat, low):
            return "must"
    for _, pat in SHOULD + SHOULD_IF_PRESENT:
        if re.search(pat, low):
            return "should"
    return "other"


def check_text(text: str, *, measurement: bool = False,
               standard: str = DEFAULT_STANDARD,
               ) -> tuple[list[str], list[str]]:
    """Return (missing_must, missing_should) field labels for one protocol."""
    low = text.lower()
    # Protocol id (Standard 0.16): the old regex check (`protocol id` found
    # anywhere in the text) was satisfiable by prose like "Protocol id will
    # be added later". The structural test — protocol_id_of() finding a
    # value in field syntax — is what the binding actually depends on.
    v016 = []
    if _std(standard) >= (0, 16) and protocol_id_of(text) is None:
        v016 = [label for label, _ in MUST_V016]
    if measurement:
        missing_must = [label for label, pat in MUST_MEASUREMENT
                        if not re.search(pat, low)]
        if _std(standard) >= (0, 17):
            missing_must += [label for label, pat in MUST_MEASUREMENT_V017
                             if not re.search(pat, low)]
        return missing_must + v016, []
    missing_must = [label for label, pat in MUST if not re.search(pat, low)]
    if _std(standard) >= (0, 15):
        missing_must += [label for label, pat in MUST_V015
                         if not re.search(pat, low)]
    missing_must += v016
    missing_should = [label for label, pat in SHOULD if not re.search(pat, low)]
    return missing_must, missing_should


def graduate(text: str, missing_must: list[str], missing_should: list[str],
             holes: list[tuple[int, str]],
             ) -> tuple[bool, list[str], list[str], list[tuple[int, str]],
                        list[tuple[int, str]]]:
    """The graduation gate, in ONE place: `Frozen before run: yes` turns
    every should-gap and should-placeholder into a must.

    Returns (frozen, missing_must, missing_should, must_holes, soft_holes).
    Until 2026-10-05 this lived inline in main(); preflight re-derived the
    severities without it and passed a frozen protocol with eleven should
    gaps that protocol-check failed — two homes, one of them blind to the
    freeze.
    """
    frozen = bool(FROZEN_YES.search(text))
    must_holes = [(n, lb) for n, lb in holes
                  if severity_of(lb) == "must"
                  or (frozen and severity_of(lb) == "should")]
    soft_holes = [(n, lb) for n, lb in holes if (n, lb) not in must_holes]
    if frozen:
        missing_must = missing_must + [f"{lb} (must once frozen: yes)"
                                       for lb in missing_should]
        missing_should = []
    return frozen, missing_must, missing_should, must_holes, soft_holes


def cost_tier_of(text: str) -> str | None:
    """The `Cost:` tier (`seconds` | `minutes` | `hours`), or None when the
    field is absent or still a placeholder — a pre-0.17 protocol has none."""
    m = COST_TIER.search(text)
    return m.group(1).lower() if m else None


#: A field line split into label and value — the value may be empty.
FIELD_LINE = re.compile(r"^\s*[-*]?\s*\*{0,2}([^*<>:]{2,60}?)\*{0,2}\s*:\*{0,2}\s*(.*?)\s*$")
SUCCESS_LABEL = re.compile(r"erfolg|success", re.I)


def criterion_present(text: str) -> bool:
    """True when the success/failure criterion is a written field: a line
    whose label names it and whose value is neither empty nor a `<…>`
    placeholder. At `Cost: seconds` this is what a full run needs instead
    of the freeze (§2.A12, 2026-10-05): the criterion is registered once,
    the instrument may change after it, the run is re-fired."""
    for line in text.splitlines():
        m = FIELD_LINE.match(line)
        if not m or not SUCCESS_LABEL.search(m.group(1)):
            continue
        value = m.group(2)
        if value and not value.startswith("<"):
            return True
    return False


def protocol_id_of(text: str) -> str | None:
    """The `Protocol id:` value, or None if the field is absent."""
    m = PROTOCOL_ID.search(text)
    return m.group(1).strip().strip("`*") if m else None


def _repo_root(start: Path) -> Path | None:
    base = start if start.is_dir() else start.parent
    for parent in [base.resolve(), *base.resolve().parents]:
        if (parent / ".git").exists():
            return parent
    return None


_ID_INDEX: dict[Path, dict[str, list[Path]]] = {}


def repo_protocol_ids(start: Path) -> dict[str, list[Path]]:
    """Every protocol id in the repo, mapped to the files carrying it.

    Uniqueness cannot be settled at the stamp alone: copying a protocol or
    editing the line by hand makes a duplicate long after `lib exp` ran, and
    two protocols with one id bind their runs to the same thing.
    """
    root = _repo_root(start)
    if root is None:
        return {}
    if root not in _ID_INDEX:
        index: dict[str, list[Path]] = {}
        for f in sorted(root.rglob("PROTOCOL-*.md")):
            try:
                pid = protocol_id_of(f.read_text(encoding="utf-8"))
            except OSError:
                continue
            if pid:
                index.setdefault(pid, []).append(f)
        _ID_INDEX[root] = index
    return _ID_INDEX[root]


def id_in_head(path: Path) -> str | None:
    """The id the committed version of this file carries — None when the file
    is new, git is absent, or the call fails. Never a proof of immutability:
    after the next commit a changed id IS the state. It catches the edit
    while it is still in the working tree."""
    root = _repo_root(path)
    if root is None:
        return None
    try:
        rel = path.resolve().relative_to(root)
        r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root,
                           capture_output=True, text=True, timeout=10)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return protocol_id_of(r.stdout) if r.returncode == 0 else None


def check_protocol_id(path: Path, text: str, standard: str) -> list[str]:
    """Shape, uniqueness and working-tree divergence of the protocol id.

    A missing field is not reported here — MUST_V016 already does that.
    """
    if _std(standard) < (0, 16):
        return []
    pid = protocol_id_of(text)
    if pid is None:
        return []
    if not PROTOCOL_ID_SHAPE.match(pid):
        return [f"{path}: MALFORMED protocol id {pid!r} — expected `p-` plus "
                f"16 lowercase hex digits, stamped by `lib exp`."]
    out = []
    others = [q for q in repo_protocol_ids(path).get(pid, [])
              if q.resolve() != path.resolve()]
    if others:
        out.append(f"{path}: DUPLICATE protocol id {pid} — also carried by "
                   + ", ".join(str(q) for q in others)
                   + ". An id binds runs to ONE protocol; re-stamp the copy.")
    was = id_in_head(path)
    if was and was != pid:
        out.append(f"{path}: WARNING: protocol id changed against HEAD "
                   f"({was} -> {pid}) — runs bound to the old id stop "
                   f"resolving.")
    return out


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(sorted(p.rglob("PROTOCOL-*.md")))
        else:
            files.append(p)
    return files


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: protocol-check [--template PATH] <PROTOCOL-*.md | dir> ...")
        print("  --template PATH  check against this template instead of the "
              "packaged one")
        print("  --guide          print the path to the protocol field guide")
        return 0
    if argv and argv[0] == "--guide":
        fg = find_field_guide()
        print(fg or "field guide not found")
        return 0 if fg else 1
    tmpl_arg = None
    if argv and argv[0] == "--template":
        if len(argv) < 2:
            print("--template needs a path")
            return 2
        tmpl_arg, argv = argv[1], argv[2:]
    if not argv:
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: protocol-check [--template PATH] <PROTOCOL-*.md | dir> ...")
        return 2
    files = collect(argv)
    if not files:
        print("protocol-check: no PROTOCOL-*.md found")
        return 2

    tmpl = template_lines(find_template(tmpl_arg))
    failed = False
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{f}: not readable ({exc})")
            failed = True
            continue

        std_m = STANDARD_VERSION.search(text)
        standard = std_m.group(1) if std_m else DEFAULT_STANDARD
        if _std(standard) > _std(SUPPORTED_STANDARD):
            print(f"{f}: CHECKER TOO OLD: protocol declares Standard: "
                  f"{standard}, this checker implements up to "
                  f"{SUPPORTED_STANDARD} — upgrade labkit. No other findings "
                  f"on this file: they would be noise, not judgement.")
            failed = True
            continue

        for finding in check_protocol_id(f, text, standard):
            print(finding)
            if "WARNING" not in finding:
                failed = True

        is_measurement = bool(TYPE_MEASUREMENT.search(text))
        missing_must, missing_should = check_text(
            text, measurement=is_measurement, standard=standard)
        # Mis-declaration: measurement + model prompt is a type error.
        has_block = "```" in text
        misdeclared = (is_measurement and has_block
                       and re.search(r"prompt", text.lower()))
        if misdeclared:
            missing_must.append(
                "MISDECLARED: protocol carries a model prompt but declares "
                "Type: measurement — change to exploratory/confirmatory")

        if is_measurement:
            holes = placeholder_fields(text)
            must_holes = [(n, lb) for n, lb in holes
                          if any(re.search(pat, lb.lower())
                                 for _, pat in MUST_MEASUREMENT)]
            clean = not (missing_must or must_holes)
            if clean:
                print(f"{f}: OK — measurement, all fields filled")
                continue
            for label in missing_must:
                print(f"{f}: MISSING (must): {label}")
            for n, label in must_holes:
                print(f"{f}:{n}: PLACEHOLDER ONLY (must): {label}")
            failed = True
            print(f"{f}: must fields missing or empty — fill them in, or "
                  f"justify as 'n/a — <why>'.")
            continue

        holes = placeholder_fields(text)
        frozen, missing_must, missing_should, must_holes, soft_holes = graduate(
            text, missing_must, missing_should, holes)
        budget_must = frozen and _std(standard) >= (0, 14)
        pilot_note = ""
        if not frozen and FROZEN_NO.search(text) and missing_should:
            pilot_note = (f"pilot (frozen: no) — {len(missing_should)} "
                          f"should-field(s) due only at report time "
                          f"(append them: lib exp <name> --report)")
            missing_should = []
        left = sorted({s for s in (ln.strip() for ln in text.splitlines()) if s in tmpl})
        no_block = not has_block and re.search(r"prompt", text.lower())
        frozen_without_io = bool(FROZEN_YES.search(text)) and not has_block
        # A protocol is a registration, not a lab journal. By 2026-08-20 one
        # had grown to 646 lines because every re-freeze APPENDED its
        # narrative instead of replacing it — presence was checked, length
        # never. The condensed version of that same protocol (all fields,
        # all numbers, four code blocks) has 296 lines; 350 leaves room.
        # Only PROSE counts: code fences (rendered examples are the raw-output
        # MUST) and table rows (confound profiles, error directions) do not —
        # raw-line counting had flagged three registration-dense protocols
        # as journals, one of which never even ran (2026-08-25).
        in_fence, in_runs, n_lines = False, False, 0
        for _l in text.splitlines():
            _s = _l.strip()
            if _s.startswith("```"):
                in_fence = not in_fence
                continue
            if _s.startswith("## "):
                in_runs = bool(DOCUMENTED_RUNS_HEAD.match(_s))
            if not in_fence and not in_runs and not _s.startswith("|"):
                n_lines += 1
        too_long = n_lines > 350
        big = oversized_sections(text)
        series = [(n, ln.strip()) for n, ln in enumerate(text.splitlines(), 1)
                  if SERIES_HEAD.match(ln)]

        # Post-run: a documented measure run makes an empty Result a MUST
        # gap — pilot suppression does not apply (write back, don't go quiet).
        measured = [(n, m.group(0)) for n, ln in enumerate(text.splitlines(), 1)
                    if (m := RUN_ID.search(ln)) and not SETUP_RUN.search(ln)]
        run_unreported = bool(measured) and (
            bool(EMPTY_ANSWER.search(text)) or bool(EMPTY_RAW.search(text))
            or not re.search(r"ergebnis|resultat|result|outcome", text.lower()))
        history = [(n, ln.strip()) for n, ln in enumerate(text.splitlines(), 1)
                   if CHANGELOG.search(ln)]

        clean = not (missing_must or missing_should or holes or left or no_block
                     or frozen_without_io or too_long or big or run_unreported
                     or history or series)
        if clean:
            if pilot_note:
                print(f"{f}: OK — must fields filled; {pilot_note}")
            else:
                print(f"{f}: OK — all must and should fields filled")
            continue

        if pilot_note:
            print(f"{f}: {pilot_note}")
        for label in missing_must:
            print(f"{f}: MISSING (must): {label}")
        for label in missing_should:
            print(f"{f}: missing (should): {label}")
        for n, label in must_holes:
            print(f"{f}:{n}: PLACEHOLDER ONLY (must): {label}")
        for n, label in soft_holes:
            print(f"{f}:{n}: placeholder only: {label}")
        if left:
            print(f"{f}: {len(left)} line(s) still verbatim template text, e.g.:")
            for s in left[:3]:
                print(f"    {s[:88]}")
        if no_block:
            print(f"{f}: MISSING (must): mentions a prompt but contains no code "
                  f"block — a verbatim prompt belongs in ``` ```, anything else "
                  f"is a paraphrase.")
        if frozen_without_io:
            print(f"{f}: MISSING (must): 'Frozen before run: yes', but not a "
                  f"single rendered example (code block). Instrument check "
                  f"first, then freeze — otherwise the error freezes in.")
        if too_long:
            sev = "OVERSIZED (must)" if budget_must else "oversized"
            print(f"{f}: {sev}: {n_lines} prose lines (tables/code excluded) "
                  f"— a protocol is a registration, not a lab journal. "
                  f"Narratives (freeze history, diagnoses) belong in commit "
                  f"messages or a note; ONE sentence per freeze stays here.")
        for lb, n, lim in big:
            sev = "OVERSIZED (must)" if budget_must else "oversized"
            print(f"{f}: {sev}: section '{lb}': {n} prose lines (budget "
                  f"{lim}) — one field is one line; if a justification needs "
                  f"more, it goes into a note and the [[wikilink]] stays "
                  f"here.")
        if run_unreported:
            print(f"{f}:{measured[0][0]}: MISSING (must): measure run in the "
                  f"run list ({measured[0][1]}) but Result/Raw output empty — "
                  f"write the result back in the SAME session.")
        for n, ln in series:
            print(f"{f}:{n}: follow-up registration in the same protocol "
                  f"({ln[:60]!r}) — one question per protocol: a declared "
                  f"follow-up gets its own PROTOCOL-s<N>-<slug>.md "
                  f"(series rule, Arbeitsstandard §2.F).")
        for n, ln in history:
            print(f"{f}:{n}: change history in the text ({ln[:60]!r}) — docs "
                  f"carry the current state, the why of the change goes in the "
                  f"commit message (Arbeitsstandard §3).")
        if (missing_must or must_holes or frozen_without_io or no_block
                or run_unreported or (budget_must and (too_long or big))):
            failed = True
            print(f"{f}: must fields missing or empty — fill them in, or "
                  f"justify as 'n/a — <why>' (the reason must be there, not "
                  f"just the angle brackets).")
    return 1 if failed else 0


def cli() -> None:
    """Entry point for the installed `protocol-check` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
