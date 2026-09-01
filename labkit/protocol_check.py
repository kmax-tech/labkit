#!/usr/bin/env python3
"""Check experiment protocols for mandatory fields (structure-free).

The protocol template (`experiment-protocol.md.template`) is a checklist of
mandatory fields, not a copy-form: protocols may be structured freely, but
every field must occur — an explicit "n/a — <why>" counts, silence does not.
A field counts as present as soon as its concept keywords appear anywhere in
the file; the check therefore forces protocols to at least *mention* the
concepts that hurt when omitted (2026-08-13: "Typ" and "Modell-I/O" were
missing from two freely written protocols; each omission caused a bad run).

**Keyword presence was not enough (2026-08-17).** A protocol that keeps the
template's own placeholder — `**Prompt (woertlich):** <der echte Prompt ...>` —
passed every check, because the WORD "prompt" was there. Across 28 protocols
that meant: not one contained an actual model input/output, while the checker
reported them clean. Three additions close that:

  1. **Placeholder detection.** A field whose value is a bare `<...>` is not
     filled. Severity follows the field: MUST -> failure, SHOULD -> warning.
  2. **Template-line detection.** Any line still identical to a line of the
     template is instruction, not content. Needs `--template PATH` (or the
     template sitting next to this script).
  3. **Verbatim-block check.** A protocol that reports a prompt but contains no
     fenced code block almost certainly paraphrases it. This is a MUST failure:
     the verbatim prompt and one real example with the model's output are the
     one thing a protocol exists for. Protocols that never mention a prompt
     (no model involved) are untouched. The example itself is enforced by the
     "Roh-Output" MUST field — a link into output/ or an "n/a — <warum>"
     satisfies it, silence does not.

Usage:
    protocol-check.py PROTOCOL-foo.md [more files or directories ...]
    protocol-check.py --template experiment-protocol.md.template <files>

Directories are searched recursively for PROTOCOL-*.md. Exit code 1 if any
MUST field is missing or unfilled in any file; SHOULD fields only warn.

**Two tiers, one template (2026-08-18).** MUST is the pilot minimum (question,
success, kill, type, prompt/IO, null condition); SHOULD is what a REPORTABLE
run owes on top (rivals, scope, prognosis, yield, knobs, result). The
graduation gate is mechanical: **`Frozen before run: ja` escalates every
SHOULD field to MUST.** Claiming confirmatory status is claiming the full
protocol; a pilot that never wrote its rivals down simply stays unfrozen and
its numbers stay pilot numbers. This keeps "Pilot leicht, Bericht schwer"
without a second template that would drift.

**Terms are a MUST field (2026-08-19).** The template asks for them twice —
`Begriffe dieses Protokolls` in the opening block, `Geklaerte Begriffe` after
the dry run — but the checker never looked for either. A transcript audit found
the material is not what is missing: five definition notes, a binding core
glossary, each read in 13-18 sessions. What was missing is the *moment of
naming* — nothing forced a protocol to say which label it uses before the run,
so the field the template calls for was the one field nothing enforced. One
keyword entry covers both mentions, and severity_of() resolves the label to
MUST, so a protocol that leaves `**Begriffe ...:** <...>` standing fails too.
Terms sit first in MUST because they precede the question they are asked in
(CLAUDE.md 6: Begriff vor Gebrauch).

**A logged measure run without a written result (2026-08-24).** The standing
rule ("a run is not done until the Ergebnis block is back in the PROTOCOL —
same session") was enforced by nothing: the pilot gate suppresses the
Ergebnis SHOULD field, so a pilot protocol with a finished measure run in its
ledger still passed clean, and the commit hook nags only at the NEXT commit —
by then the context that explains the numbers is gone. Now: a run_id line in
the ledger that is not a prepare/probe line makes empty `Answer to the
question` / `Raw output` fields (or a missing Result section) a MUST failure.

**Change-history prose is a warning (2026-08-24).** Sentences like
"seit <Datum> wieder draußen" or "hieß bis ..." turn a protocol into a
changelog; the current rule belongs in the text, the change and its why in
the commit message (Arbeitsstandard §3). Warning only — translation tables
that are load-bearing (old names still in runs.tsv) are legitimate.

Forward-looking: apply to new protocols, do not retrofit old ones (same policy
as runlog).
"""

import re
import sys
from pathlib import Path

# (field label, regex over the whole file)
# Keywords match German AND English: the template's field labels are English
# (2026-08-20), pre-existing protocols name their concepts in German, and
# either language may fill a field — the checker accepts both.
MUST = [
    ("Begriffe (jedes Etikett mit Halbsatz)", r"begriff|terminolog|glossar|terms of"),
    ("Frage / Hypothese", r"hypothese|frage|question|hypothesis"),
    ("Erfolgskriterium", r"erfolg|success"),
    ("Abbruchkriterium (Kill)", r"abbruch|kill"),
    ("Typ (explorativ / konfirmatorisch)",
     r"explorativ|konfirmatorisch|explorator|confirmator"),
    ("Modell-I/O / Prompt (woertlich)", r"modell-i/o|model i/o|prompt"),
    ("Nullbedingung / Anker / Kontrolle",
     r"nullbedingung|null.?condition|anker|anchor|placebo|swap|kontroll"),
    # The one thing a protocol exists for: a real example with the model's
    # actual output (embedded or linked). A metric without one is a number
    # nobody can interpret later — the mechanism shows in the single case.
    ("Roh-Output (ein echtes Beispiel + Modell-Output)",
     r"roh-output|roh-beispiel|roh-antwort|i/o-beispiel|raw.?output"),
]
SHOULD = [
    # Missing in all five freely written protocols of Aug 2026, and the result
    # section was systematically never written back — hence the two nudges.
    ("Frozen before run (ja/yes | nein/no)", r"frozen|eingefroren"),
    ("Ergebnis / Ausgang (nach dem Lauf nachtragen)",
     r"ergebnis|ausgang|resultat|result|outcome"),
    ("Bedeutung des Gold-Labels", r"gold"),
    ("Ausbeute je Stufe", r"ausbeute|yield"),
    ("Rivalen-Erklaerungen / Konfunde", r"rival|konfund|confound"),
    ("Fehlerrichtung je Konfund",
     r"fehlerrichtung|error.?direction|richtung der hypothese|zugunsten der hypothese"),
    ("Skopus (was NICHT gemessen wird)", r"skopus|nicht gemessen|out of scope"),
    ("Freie Knoepfe + Sensitivitaet", r"freie[nr]? kn|free knob|sensitivit|sweep"),
    ("Prognose fuer den Folgelauf", r"prognose|vorhersage|prediction"),
    ("Instrumentenprobe (Trockenlauf vor dem Pilot)",
     r"instrumentenprobe|trockenlauf|rauchtest|instrument check|dry.?run"),
    ("Einordnung (selbsttragend)",
     r"einordnung|vorgeschichte|selbsttragend|self.?contained"),
]

# „Frozen before run: ja" ohne ein einziges gerendertes Beispiel ist eine
# eingefrorene Registrierung auf einem ungeprueften Instrument — sie friert den
# Fehler mit ein. Am 2026-08-17 fand ein 12-Aufruf-Trockenlauf, dass der Prompt
# nach FOLGERUNG fragte, waehrend das Gold-Label STUETZUNGSGRAD meint; ein
# 9-Aufruf-Trockenlauf sparte 440 Aufrufe. Beide haetten in einem „frozen"
# Protokoll ohne I/O-Beispiel nicht stattgefunden.
FROZEN_YES = re.compile(r"frozen before run[^:\n]*:\**\s*\**\s*(ja|yes)\b", re.I)

# The mirror image of the graduation gate: a protocol that explicitly declares
# `Frozen before run: nein` is a pilot BY DECLARATION. Its missing SHOULD
# fields are not gaps but fields that are not yet due — listing them one by
# one trains the reader to ignore the checker. One summary line instead.
FROZEN_NO = re.compile(r"frozen before run[^:\n]*:\**\s*\**\s*(nein|no)\b", re.I)

# runlog run ids as they appear in ledgers: 2026-08-23T20-37-21_afbe. A ledger
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
# Change-history prose — the doc should carry the current rule, the commit the
# change (Arbeitsstandard §3). Warning only.
CHANGELOG = re.compile(
    r"seit 20\d\d-\d\d|wieder drau[ßs]+en|wieder drin\b|hie[ßs]+ bis"
    r"|vorher (stand|galt)|fr[üu]her hie[ßs]+|umbenannt am", re.I)

# Line budget per section. The global 350 only bites once a protocol is
# already unreadable; measured over 73 grown protocols the length sits in two
# sections — Setup (median 42 prose lines, top quartile above 54) and Intent
# (median 23) — and there almost entirely in prose, not in the mandatory
# evidence: only 556 of 3344 Setup lines are code blocks. The budgets sit
# between median and upper quartile, so they flag roughly the top third
# instead of everything (a warning that fires on every file is background
# noise). Needs more room? That is a note, and here stands its [[wikilink]].
SECTION_BUDGET = [
    ("Summary", r"summary|zusammenfassung", 14),
    ("Context", r"context|einordnung", 20),
    ("Intent", r"intent|absicht|hypothese und kriterien|die eine frage", 30),
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
    """Instruction lines of the template, normalised for comparison."""
    if path is None or not path.exists():
        return set()
    keep = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        # Only lines long enough to be distinctive; headings are meant to recur.
        if len(s) >= 40 and not s.startswith("#"):
            keep.add(s)
    return keep


def find_template(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    here = Path(__file__).resolve().parent / "experiment-protocol.md.template"
    return here if here.exists() else None


def severity_of(label: str) -> str:
    """Does this placeholder sit in a MUST field, a SHOULD field, or neither?"""
    low = label.lower()
    for _, pat in MUST:
        if re.search(pat, low):
            return "must"
    for _, pat in SHOULD:
        if re.search(pat, low):
            return "should"
    return "other"


def check_text(text: str) -> tuple[list[str], list[str]]:
    """Return (missing_must, missing_should) field labels for one protocol."""
    low = text.lower()
    missing_must = [label for label, pat in MUST if not re.search(pat, low)]
    missing_should = [label for label, pat in SHOULD if not re.search(pat, low)]
    return missing_must, missing_should


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(sorted(p.rglob("PROTOCOL-*.md")))
        else:
            files.append(p)
    return files


def main(argv: list[str]) -> int:
    tmpl_arg = None
    if argv and argv[0] == "--template":
        if len(argv) < 2:
            print("--template braucht einen Pfad")
            return 2
        tmpl_arg, argv = argv[1], argv[2:]
    if not argv:
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: protocol-check [--template PATH] <PROTOCOL-*.md | dir> ...")
        return 2
    files = collect(argv)
    if not files:
        print("protocol-check: keine PROTOCOL-*.md gefunden")
        return 2

    tmpl = template_lines(find_template(tmpl_arg))
    failed = False
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{f}: nicht lesbar ({exc})")
            failed = True
            continue

        missing_must, missing_should = check_text(text)
        frozen = bool(FROZEN_YES.search(text))
        holes = placeholder_fields(text)
        # Graduierungs-Tor: frozen -> jede Soll-Luecke ist eine Pflicht-Luecke.
        must_holes = [(n, lb) for n, lb in holes
                      if severity_of(lb) == "must"
                      or (frozen and severity_of(lb) == "should")]
        soft_holes = [(n, lb) for n, lb in holes if (n, lb) not in must_holes]
        if frozen:
            missing_must = missing_must + [f"{lb} (Pflicht ab frozen: ja)"
                                           for lb in missing_should]
            missing_should = []
        pilot_note = ""
        if not frozen and FROZEN_NO.search(text) and missing_should:
            pilot_note = (f"Pilot (frozen: nein) — {len(missing_should)} "
                          f"Soll-Feld(er) erst zum Bericht faellig "
                          f"(anhaengen: lib exp <name> --report)")
            missing_should = []
        left = sorted({s for s in (l.strip() for l in text.splitlines()) if s in tmpl})
        has_block = "```" in text
        no_block = not has_block and re.search(r"prompt", text.lower())
        frozen_without_io = bool(FROZEN_YES.search(text)) and not has_block
        # Ein Protokoll ist eine Registrierung, kein Laborjournal. 2026-08-20
        # war eines auf 646 Zeilen gewachsen, weil jede Neu-Einfrierung ihre
        # Erzaehlung ANHAENGTE statt ersetzte — Praesenz wurde geprueft, Laenge
        # nie. Die Kurzfassung desselben Protokolls (alle Felder, alle Zahlen,
        # vier Code-Bloecke) hat 296 Zeilen; 350 laesst dafuer Luft.
        # Gezaehlt wird nur PROSA: Code-Zaeune (gerenderte Beispiele sind
        # Roh-Output-PFLICHT) und Tabellenzeilen (Konfund-Profile,
        # Fehlerrichtungen) zaehlen nicht — die Rohzeilen-Zaehlung hatte
        # drei registrierungs-dichte Protokolle als Journal geflaggt,
        # darunter ein nie gelaufenes Voll-Intent (2026-08-25).
        in_fence, n_lines = False, 0
        for _l in text.splitlines():
            _s = _l.strip()
            if _s.startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence and not _s.startswith("|"):
                n_lines += 1
        too_long = n_lines > 350
        big = oversized_sections(text)

        # Post-run: a measure run in the ledger makes an empty Result a MUST
        # gap — pilot suppression does not apply (nachtragen statt schweigen).
        measured = [(n, m.group(0)) for n, l in enumerate(text.splitlines(), 1)
                    if (m := RUN_ID.search(l)) and not SETUP_RUN.search(l)]
        run_unreported = bool(measured) and (
            bool(EMPTY_ANSWER.search(text)) or bool(EMPTY_RAW.search(text))
            or not re.search(r"ergebnis|resultat|result|outcome", text.lower()))
        history = [(n, l.strip()) for n, l in enumerate(text.splitlines(), 1)
                   if CHANGELOG.search(l)]

        clean = not (missing_must or missing_should or holes or left or no_block
                     or frozen_without_io or too_long or big or run_unreported
                     or history)
        if clean:
            if pilot_note:
                print(f"{f}: OK — Pflicht-Felder ausgefuellt; {pilot_note}")
            else:
                print(f"{f}: OK — alle Pflicht- und Soll-Felder ausgefuellt")
            continue

        if pilot_note:
            print(f"{f}: {pilot_note}")
        for label in missing_must:
            print(f"{f}: FEHLT (Pflicht): {label}")
        for label in missing_should:
            print(f"{f}: fehlt (Soll): {label}")
        for n, label in must_holes:
            print(f"{f}:{n}: NUR PLATZHALTER (Pflicht): {label}")
        for n, label in soft_holes:
            print(f"{f}:{n}: nur Platzhalter: {label}")
        if left:
            print(f"{f}: {len(left)} Zeile(n) noch woertlicher Template-Text, z.B.:")
            for s in left[:3]:
                print(f"    {s[:88]}")
        if no_block:
            print(f"{f}: FEHLT (Pflicht): nennt einen Prompt, enthaelt aber keinen "
                  f"Code-Block — ein woertlicher Prompt gehoert in ``` ```, sonst "
                  f"ist er nacherzaehlt.")
        if frozen_without_io:
            print(f"{f}: FEHLT (Pflicht): 'Frozen before run: ja', aber kein einziges "
                  f"gerendertes Beispiel (Code-Block). Erst Instrumentenprobe, dann "
                  f"einfrieren — sonst friert man den Fehler mit ein.")
        if too_long:
            print(f"{f}: {n_lines} Prosa-Zeilen (ohne Tabellen/Code) — ein Protokoll ist eine Registrierung, "
                  f"kein Laborjournal. Erzaehlungen (Einfrier-Historie, Diagnosen) "
                  f"gehoeren in die Commit-Messages bzw. eine Note; je Einfrierung "
                  f"bleibt EIN Satz hier.")
        for lb, n, lim in big:
            print(f"{f}: Abschnitt '{lb}': {n} Prosa-Zeilen (Budget {lim}) — ein "
                  f"Feld ist eine Zeile; braucht eine Begruendung mehr, gehoert "
                  f"sie in die Note und hier steht der [[wikilink]].")
        if run_unreported:
            print(f"{f}:{measured[0][0]}: FEHLT (Pflicht): Mess-Lauf im Ledger "
                  f"({measured[0][1]}), aber Result/Raw-Output leer — Ergebnis "
                  f"in DERSELBEN Session nachtragen (nachtragen statt schweigen).")
        for n, l in history:
            print(f"{f}:{n}: Aenderungs-Historie im Text ({l[:60]!r}) — Docs "
                  f"tragen den Stand, das Warum der Aenderung traegt die "
                  f"Commit-Message (Arbeitsstandard §3).")
        if missing_must or must_holes or frozen_without_io or no_block or run_unreported:
            failed = True
            print(f"{f}: Pflichtfelder fehlen oder sind leer — nachtragen oder als "
                  f"'n/a — <warum>' begruenden (der Grund muss dastehen, nicht "
                  f"nur die spitzen Klammern).")
    return 1 if failed else 0


def cli() -> None:
    """Entry point for the installed `protocol-check` command."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
