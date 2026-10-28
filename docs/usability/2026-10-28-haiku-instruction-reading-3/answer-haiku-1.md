Antworten zu den Fällen 13, 14 und 15. Quellen sind `instructions.md` (Zeilen wie dort nummeriert) und `cases.txt`. Ich habe nur diese beiden Dateien gelesen. Kennzeichnung: **[explizit]** steht so in der Anleitung, **[Urteil]** ist meine Schlussfolgerung.

## Fall 13: Alter Bereich mit `standard = "0.21"`, neue Frage

**Was tun**

1. Alter Bereich, Analyse heute reproduzieren:
   - **[explizit]** Das Protokoll nicht umschreiben, um die Gates zu bestehen (Z. 70–71: „Preserve historical protocols and runs with their original commit and package pin; do not convert them"). Stattdessen am Commit reproduzieren, an dem der Lauf entstand, mit einer venv aus dessen eigener `requirements.lock` (Z. 71–73: „a checkout of that commit with a venv built from its own `requirements.lock`").
   - **[Urteil]** Die Anleitung nennt keinen Befehl für den Checkout (kein `git worktree`, kein `git checkout`). Das ist Ihre Wahl. Ob `protocol-check` im alten Checkout durchläuft, sagt die Anleitung nicht.
2. Neue Frage:
   - **[explizit]** Neuer Bereich unter dem aktuellen Pin: `labkit-init exp <name> --repeat-cost <cost> --kind <kind>` (Z. 84–85), danach `protocol-fill <PROTOCOL> --list` und `protocol-check <PROTOCOL> --contract` (Z. 92–93). `--model <alias>` nur, wenn Modellaufrufe über `models.toml` laufen (Z. 85–86).
   - **[explizit]** Neuer Bereich statt Umbau des alten: „stamp a fresh area for new work" (Z. 73).

**Welche labkit-Version gilt**

- **[explizit]** Die Pin-Zeile steht in `requirements.lock`, sonst in `requirements.txt` (Z. 65–66). Sie gilt für das ganze Repository. `labkit-check` zeigt sie neben der installierten Version (Z. 66).
- **[explizit]** `standard = "…"` im Protokollkopf benennt das Protokollformat, nicht die Paketversion (Z. 67–68).

**Deckt ein früheres Audit noch einen Bereich?**

- **[explizit]** Ein Anheben des Pins ändert das Stamp jedes Bereichs, daher deckt danach kein früheres Audit mehr einen Bereich (Z. 68–69).
- **Offene Lücke:** Der Lauf `2026-10-26T08-18-33_7392` und das Protokoll `2026-10-26T08-28-analysis.toml` sind nach dem Pin-Anheben entstanden. Die Anleitung sagt nicht, ob dieses Audit unter dem neuen Pin noch gilt, obwohl der Kopf `standard = "0.21"` abgelehnt wird. Dieser Widerspruch ist nicht aufgelöst. Die Anleitung erklärt auch nicht, warum `protocol-check` den Kopf ablehnt.

**Erlaubte Aussage heute:** Nur die Reproduktion am alten Commit mit altem Pin. Die neue Frage ist noch nicht gemessen.

## Fall 14: Protokoll A (fit) verfehlt C1, neue Modellfamilie auf denselben Daten

**Ist es eine Ersetzung von A?** **[explizit]** Nein. Ersetzung ist nur für eine Registrierung, die „cannot be answered as written" (Z. 271–273). Ein Versuch nach einem gültigen Ergebnis, „a miss included, such as another model on the same data", ist ein eigenes Protokoll ohne `[replaces]` (Z. 274–276).

**Welche Registrierung**

- **[explizit]** Eigenes Protokoll, eigener Name: `labkit-init exp <neuer-name> --repeat-cost <cost> --kind fit` (Z. 84–85). `kind = fit`, weil ein Modell trainiert oder ausgewählt wird (Z. 55–57). Ist es ein Sprachmodell über `models.toml`, zusätzlich `--model <alias>` (Z. 85–86).
- **[explizit]** Typ `exploratory`: „when it builds on what an earlier protocol showed, its Question / hypothesis names that protocol and what it showed, and its type is `exploratory`" (Z. 276–278). Die Frage/Hypothese nennt also A und was A zeigte.
- **[explizit]** Die Wahl von `exploratory` entfernt keine Kriterien und Audits: „Neither `low` nor `exploratory` removes a fit/apply's criterion or audits" (Z. 61). Kriterium, Zulassungsbedingung und Nullbedingung sind also trotzdem nötig (Z. 97–99).
- **[explizit]** Vor der ersten vollen Messung die Registrierung committen. Kriterien und Konstanten vor dem Ergebnis setzen (Z. 110–112).

**Was passiert mit A's Verfehlung**

- **[explizit]** Sie bleibt Ergebnis. „a missed criterion — that is the result: report the miss first" (Z. 260–262). Die Marge nicht senken: „Lowering the margin is not a repair" (Z. 262). Läufe und Audits von A bleiben erhalten (Z. 296–299).
- **[explizit]** Ein neuer Ansatz macht einen frühen Verfehlt nicht zu einem Bestanden (Z. 273–274).

**Offene Punkte**

- **[Urteil]** Die Anleitung sagt nicht, ob derselbe Datensatz mit denselben Kriterien dieselbe Marge erfordert. Das entscheidet Ihre Registrierung, bevor Sie die Ergebnisse sehen.
- **[Urteil]** Ob es sich um eine Modellfamilie mit `models.toml` handelt, bestimmt, ob `--model` nötig ist. Das ist aus dem Fall nicht ersichtlich.

## Fall 15: Analyse-Audit ohne Befunde, Lauf übernehmen?

**Kann man übernehmen?** **[explizit]** Ja, wenn das Audit den aktuellen Code, die Zusagen und den Lauf gesehen hat: „An analysis audit with no findings covers the run when it saw the current code, promises and run" (Z. 218–219). Übernommen wird mit `protocol-fill <PROTOCOL> --from-run <run_id>` (Z. 214–217). Vorher müssen Messung, das entschiedene deckende Analyse-Audit und `02_analyze.py --check` gelten (Z. 216–217).

**Ist etwas zu entscheiden?** **[explizit]** Nein: „there is nothing to decide" (Z. 219). Man trägt nichts in das Protokoll ein.

**Reihenfolge und Hinweise**

- **[explizit]** Vor der Übernahme das Fazit schreiben: `protocol-fill <PROTOCOL> "Conclusion=…"` (Z. 188–189).
- **[explizit]** Danach `protocol-fill <PROTOCOL> --into REPORT.md`, Werte nie abtippen (Z. 226–228).
- **[explizit]** Audit-Protokoll und Befunde lesen, auch ohne Befunde: „Read the audit's findings and diagnostics" (Z. 161–162).
- **[Urteil]** `02_analyze.py --check` steht im Text ohne Pfad. Vermutlich `<area>/scripts/02_analyze.py --check` nach dem Muster in Z. 117. Diesen Pfad bitte gegen die Bereichsstruktur prüfen.

**Was ändert ein früherer BLOCKER, der seitdem behoben wurde?**

- **[explizit]** Ein Eingriff in die Messung repariert den alten Lauf nicht: „Editing code does not repair an old run" (Z. 172–173). Nach einer Änderung am Messcode: testen, committen, neue Messung, `finalize`, Analyse-Audit (Z. 170–172). Die Neumessung ist nötig.
- **[explizit]** Das Audit prüft frühere entschiedene BLOCKERs selbst nach. Übernahme braucht, dass es die Behebung „in place" findet. Man ergänzt dafür nichts im Protokoll (Z. 219–221).
- **[explizit]** Wurde der BLOCKER mit `stands` akzeptiert, braucht er ein `labkit-audit <area> --review --record <record>` (Z. 198–199). Wird er auf `fixed`, `dismissed` oder `deferred` geändert und war ein Review abgelehnt, braucht die Änderung ein bestätigendes Review (Z. 199–203).
- **[explizit]** Bei `repeat_cost = high` zusätzlich `frozen = false` setzen, bevor der Reparaturzyklus startet (Z. 174–177).
- **Offene Lücke:** Die Anleitung behandelt nur Messcode-Fixes ausdrücklich (Z. 170). Bei einer Behebung außerhalb des Messcodes sagt sie nichts Klares. Ob der alte Lauf dann gilt, ist nicht festgelegt.

## Offene Punkte (Zusammenfassung)

1. Fall 13: Warum `protocol-check` den Kopf `standard = "0.21"` ablehnt und ob das Audit vom 26.10. unter dem neuen Pin noch deckt. Die Anleitung klärt das nicht.
2. Fall 13: Befehl für den Checkout des alten Commits und die venv daraus. Die Anleitung nennt keinen.
3. Fall 14: Ob dieselbe Marge für die neue Modellfamilie gilt. Das bestimmt die Registrierung.
4. Fall 15: `02_analyze.py --check` mit vollständigem Pfad.
5. Fall 15: Verhalten bei einer Behebung außerhalb des Messcodes. Die Anleitung deckt nur Messcode-Fixes ab.
