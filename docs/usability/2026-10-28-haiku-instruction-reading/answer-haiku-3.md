Verständnisprobe 2026-10-28. Gelesen nur instructions.md und cases.txt (/Users/max/projects/labkit-sab-cases-main/docs/usability/2026-10-28-haiku-instruction-reading/). Keine Befehle ausgeführt, nichts geschrieben.

Legende: [Doku] = steht so im Text, [Urteil] = meine Schlussfolgerung. Zeilen = Zeilen in instructions.md.

**Fall 1 (RandomForest, fünf Sekunden)**
- kind: fit. [Doku] "A RandomForest fitted in seconds is fit, usually at low repeat cost" (Z. 57). Auch bei unlabelled Testzeilen gilt fit, Bewertung auf gelabelten Held-out-Zeilen (Z. 54–56).
- repeat_cost: low. [Doku] (Z. 57)
- type: confirmatory, weil Frage und Regel vor den Ergebnissen festlagen. [Doku Definition Z. 51; Zuordnung Urteil]
- Kriterium: ja, mit Zulässigkeits- und Nullbedingung im selben Lauf. [Doku Z. 88–90]
- Analysis-Audit: ja, "at either cost" (Z. 151). Preflight-Audit und Freeze: nicht geschuldet bei low (Z. 136).
- Schritte/Befehle: labkit-init exp <name> --repeat-cost low --kind fit (Z. 75); protocol-fill <PROTOCOL> --list und protocol-check <PROTOCOL> --contract (Z. 83–84); Vorher-Felder füllen (Z. 84–85, 97–99); committen (Z. 101); 01_measure.py --show 2 (Z. 107–108, nur bei Schablonen für Schätzer/Prompts); code-check <area> (Z. 110); Messung im Vordergrund (Z. 138–140); finalize, dann labkit-audit <area> --mode analysis (Z. 151).
- Zulässige Aussage: vor Finalize und Audit keine. Vorhersagen sind Beschreibung, keine Erfolgsaussage (Z. 174–175).
- Lücke: Das Dokument sagt nicht, wie die gelabelten Held-out-Zeilen zu den unlabelled Testzeilen stehen. Ob die Testvorhersagen als externe Ausgabe gelten (Z. 35–37), ist im Fall nicht gesagt.

**Fall 2 (Zählung lokaler Dokumente, sechs Stunden)**
- kind: compute. [Doku] "calculate a quantity without judging predictions" (Z. 49).
- repeat_cost: high. [Urteil aus "nicht casually wiederholen"; Doku Z. 50: "a repeat needs protection by a preflight audit and freeze"; Z. 50 sagt, die Messkosten zählen, nicht die Gesamtdauer.]
- type: im Fall nicht angegeben. Wahl nach Z. 51 (vorab festgelegte Frage: confirmatory, sonst exploratory). [Urteil]
- Geschuldet: kein --show (Z. 108–109, "compute has no --show"); kein --probe (Z. 124–125), stattdessen die Berechnung testen (Z. 125–126); preflight (Z. 130); labkit-audit <area> --mode preflight (Z. 130–131); Freeze mit frozen = true (Z. 133–134); committen, dann runlog start/--wait (Z. 138, 141–144); Analysis-Audit (Z. 151). Kein Kriterium, weil compute keine Vorhersage bewertet (Z. 70).
- Lücke: Welche Felder der Freeze-Vertrag für compute verlangt, steht nur in protocol-check <PROTOCOL> --contract (Z. 61–63), dessen Ausgabe ich nicht kenne.

**Fall 3 (unveränderter LLM gegen Gold, viele Stunden)**
- kind: apply. [Doku] "An unchanged LLM judged against labels is apply" (Z. 58).
- repeat_cost: high. [Urteil; Doku Z. 50 Messkosten]
- Vorlauf (high), in dieser Reihenfolge:
  1. labkit-init exp <name> --repeat-cost high --kind apply, ggf. --model <alias> (Z. 75–77).
  2. protocol-fill <PROTOCOL> --list, protocol-check <PROTOCOL> --contract; Frage, Daten, Ausschlüsse, Einheit; Kriterium, Zulässigkeit, Nullbedingung; Datenprofil; PROMPT-Konstanten mit protocol-fill <PROTOCOL> --prompts (Z. 83–93, 94–95 für C/A/B).
  3. Registrierung committen (Z. 101).
  4. --show 2 (Z. 107–108); code-check <area> (Z. 110); Test auf Hand-Fällen (Z. 110–111).
  5. Oberflächenmerkmale beurteilen, im Datenprofil festhalten (Z. 114–116).
  6. 01_measure.py --probe (Z. 120–123); Auswertung an synthetischen Extremen prüfen (Z. 122–123).
  7. Code und Inputs committen; preflight <area>; labkit-audit <area> --mode preflight; Befunde entscheiden; preflight_audit im Protokollkopf; labkit-init exp <name> --report; frozen = true (Z. 130–135).
  8. Committen, dann runlog start <area> -- .venv/bin/python <area>/scripts/01_measure.py und runlog <area> --wait (Z. 141–144).
- Bei wiederholbar (low): Probe entfällt, der volle Lauf prüft das Instrument (Z. 125–126); kein Freeze, kein Preflight-Audit (Z. 136); Lauf im Vordergrund (Z. 138–140). Show, code-check, Datenprofil, Kriterium und Analysis-Audit bleiben (Z. 59, 151).
- Datenprofil-Helfer allein reicht nicht: "counts are hints, not the judgement" (Z. 116–117); das Urteil selbst ist zu schreiben (Z. 114–115).
- Lücke: Ob der Fall über models.toml läuft, ist nicht gesagt (Z. 75–77).

**Fall 4 (low-cost fit, Finalize ok, Audit ohne Befunde, Conclusion leer)**
- Schritte: (a) protocol-fill <PROTOCOL> "Conclusion=…", höchstens zwei Sätze, vor der Adoption (Z. 179–180); (b) übrige Nachlauf-Felder füllen, bei Modell Roh-Paare je Befund (Z. 180–183); (c) keine Befunde, also keine Entscheidung und kein Review (Z. 185–192); (d) protocol-fill <PROTOCOL> --from-run <run_id> (Z. 201–204); Vorbedingungen: Messung, Analysis-Audit, 02_analyze.py --check (Z. 203–204); (e) protocol-fill <PROTOCOL> --into REPORT.md (Z. 209–210); (f) Erklärung im Report selbst schreiben, konsistent zur Conclusion (Z. 212–213); zählbare Größen in metrics.json (Z. 213–215); (g) Vorgaben der externen Aufgabe prüfen (Z. 225–226); (h) Report, Protokoll, Outputs, Runs, Audit-Belege gemeinsam stagen, inkl. audits/attempts.jsonl (Z. 226–228).
- Generiert: [result]-Block, Recorded results, Verdikte, Run-Eintrag, Ergebnisblock und Grenzen (Z. 202–210). Verfasst: Conclusion (Z. 179), Report-Erklärung (Z. 212–213), Roh-Paare bei Modell (Z. 182–183), metrics.json als Eingabe (Z. 213–215).
- Lücke: Die run_id ist im Fall nicht genannt. Die bekannte Ausgangslage (2026-10-26T08-18-33_7392, Analyse-Record 2026-10-26T08-28-analysis.toml) passt nur, wenn es derselbe Lauf ist. Der Befehl für 02_analyze.py --check ist nicht ausgeschrieben (Z. 204).

**Fall 5 (Fit, zwei verbotene Merkmale, nur eins entfernt)**
- Nicht als fixed markieren. "fixed means the whole named fault was corrected and its requested diagnostic run and assessed" (Z. 159–160).
- Zuerst: das zweite Merkmal im Code entfernen; die angeforderte Diagnose laufen lassen und auswerten (Z. 159–160); Tests und code-check (Z. 110–111); committen; neu messen (Z. 138–140); finalize, Analysis-Audit; der neue Audit prüft die früheren BLOCKER nach (Z. 161–164); dann labkit-audit <area> --decide <N> fixed "<REASON>" --record <record> (Z. 156).
- Der alte Output: neu aus einem Lauf nach dem Fix schreiben, sonst entfernen (Z. 38–41). Alter Lauf bleibt als Beleg (Z. 276–279).
- Änderung der Ausschlussregel repariert nicht: "Remove it from the code, not from the exclusion rule" (Z. 241–242). Die Registrierung ändert sich nicht (Z. 101–103).
- Lücke: Ob die Diagnose-Anforderung eine eigene Ausgabe braucht, ist nicht gesagt.

**Fall 6 (Fit verfehlt C1)**
- Sofortiger Weg: die Verfehlung berichten. "a missed criterion — that is the result: report the miss first" (Z. 243–244). Verdikt: nicht erfüllt, unter gültiger Zulassung eine berichtbare Verfehlung (Z. 206–207). Ablauf: Conclusion, from-run, --into REPORT.md (Z. 179–210).
- Verboten: Null-Band und Schwelle nachträglich ändern. "Lowering the margin is not a repair" (Z. 244–245); "later changes do not answer the original registered question" (Z. 101–103). Eine neue Area, die die Frage als beantwortet ausgibt, verboten: "a new approach never turns an earlier miss into a pass" (Z. 254–255).
- Spätere Untersuchung: nicht verboten. Eine eigene, veränderte Folgefrage ist erlaubt, muss aber offenlegen, was schon beobachtet wurde (Z. 256–258); exploratory denkbar (Z. 51).
- Lücke: Wo und wie die Offenlegung zu stehen hat, ist nicht geregelt. Ob eine Folgefrage [replaces] braucht, steht nur für ungültige Registrierungen (Z. 252–253).

**Fall 7 (c1_pass=True, a3_pass=True, A3 nicht assessable akzeptiert)**
- Verdikt: C1 ist "not assessable", nicht pass. "An unassessable … admissibility condition leaves every criterion not assessable" (Z. 173–174). Metrikwerte bleiben Beschreibung (Z. 174–175). a3_pass=True ist wegen fehlender Zulassung kein Beleg.
- metrics.json nicht editieren: raw metrics bleiben unverändert (Z. 206–207); keine Änderung früherer Messungen (Z. 277–279).
- Decision-Review: nicht geschuldet. Review gilt nur bei BLOCKER mit "stands" (Z. 185–186); "not assessable" braucht keines (Z. 196–197). Bei WARNING bleibt es Warnung (Z. 191–192).
- Lücke: Ob das Finding BLOCKER oder WARNING war, ist nicht gesagt; die Status-Bezeichnung "accepted" steht nicht wörtlich im Text (Z. 170–171).

**Fall 8 (BLOCKER stands, Conclusion geändert)**
- Veraltet: das Review; "Changing the Conclusion or decision invalidates its review" (Z. 193–194). Auch der Report-Text muss zur neuen Conclusion passen (Z. 212–213).
- Wiederholen: labkit-audit <area> --review --record <record> (Z. 185–186); protocol-fill <PROTOCOL> "Conclusion=…" (Z. 179). Keine neue Messung (Z. 195).
- --again: "never supplies missing approval or overrules an earlier rejection" (Z. 196–197). Eine unveränderte --again-Runde erledigt eine frühere Ablehnung nicht.
- Lücke: Ob --render und die Neuerzeugung des Blocks nötig sind, steht nur nach geänderten Audit-Entscheidungen (Z. 210–211); hier ändert sich nur die Conclusion.

**Fall 9 (Analysis-Audit gescheitert, Adoption verweigert, Termin)**
- Zuerst: labkit-audit <area> --findings (Z. 19–24, 259–260). Ist es ein gescheiterter Aufruf ohne abdeckendes Audit, nennt es den Handover-Weg mit Exit 2 (Z. 21–24).
- Weg Diskussion: protocol-fill <PROTOCOL> --discuss <run_id> --why "<was die Adoption verweigerte, was du fandest>" --into REPORT.md (Z. 217–219). Im Text muss stehen, dass die Frage offen bleibt; Diskussion ist kein Erfolg (Z. 219–220).
- Pflichten: labkit-audit <area> --report-review REPORT.md (Z. 220–221); Korrekturen des Reviewers, dann neues Review; ein sauberer Befund auf unverändertem Stand gibt nichts frei (Z. 221–223). Belege stagen (Z. 226–228). Ungeadoptete Zahlen nicht als Antwort in REPORT.md (Z. 230–231).
- Alternative, wenn die Zeit nicht reicht: Handover. Offene BLOCKER entscheiden oder mit deferred und Grund übergeben, dann protocol-fill <PROTOCOL> --handover --why "…" --tried "…" --into REPORT.md (Z. 259–274). "An honest handover without a result is an admissible end" (Z. 235–236).
- Prosa allein reicht nicht [Urteil]: Die Dokumentation verlangt die genannten Befehle, die Blöcke schreiben.
- Lücke: Die run_id ist nicht genannt.

**Fall 10 (Registrierung widersprüchlich)**
- Ersatzweg: Konflikt zuerst erklären; dann labkit-init exp <new-name> --kind …, type = "exploratory", [replaces] protocol = "<id>", je Änderung ein [[replaces.change]] mit what/from/to/why; offene BLOCKER des Vorgängers deferred (Z. 249–254). Das Verdikt des Vorgängers wird zuerst gerendert (Z. 254).
- Frühere Befunde und Ergebnisse bleiben: Historie und Läufe bleiben (Z. 63–64, 276–279).
- Nicht jede spätere unabhängige Frage ersetzt: "an independent question is not a replacement just because it comes later" (Z. 256–258).
- Lücke: Die Art, wie der Kind-Wechsel (--kind) gewählt wird, ist nur über Z. 53–58 erschließbar. --change-kind gilt nur vor der ersten Messung (Z. 79–80).

**Fall 11 (predictions.csv nur im Area-Ausgabeordner)**
- Nicht erledigt. Ausgaben der externen Aufgabe sind das Lieferobjekt, Metriken ersetzen sie nicht (Z. 35–37). Finalize garantiert nur die eigenen Prüfungen: "a green gate proves only its encoded checks" (Z. 225–226). Der Commit prüft nur den gestagten Stand (Z. 228–229).
- Schritt: pred_results/predictions.csv an der von der Aufgabe genannten Stelle aus der Messung schreiben (Z. 36–37), Format und Inhalt selbst prüfen (Z. 225–226), dann mit Report, Protokoll und Belegen stagen (Z. 226–228).
- Lücke: Ob ein Kopieren aus dem Ausgabeordner als "aus der Messung geschrieben" gilt, sagt der Text nicht [Urteil: Im Zweifel aus dem Lauf neu schreiben].

**Fall 12 (--decide plus neuer Report-Block)**
- Erlaubt: "Change decisions with --decide; generate result updates with protocol-fill" (Z. 276–277). Reihenfolge: labkit-audit … --decide <N> <STATUS> "<REASON>" --record <record> (Z. 156); bei geänderten Entscheidungen protocol-fill --render, dann den Block neu erzeugen (Z. 210–211); Review neu, wo die Entscheidung es verlangt (Z. 193–194).
- Unverändert bleiben: Run-Belege, Audit-Antworten, frühere Befunde, Historie; nicht erfolgreiche Audits bleiben (Z. 276–279). Kein --no-verify, keine Record-Änderung, kein Löschen, keine Ignore-Regeln (Z. 280–281).
- Maßgebende Version: die des Pins im Repo. "Use the lab standard shipped with this repository's pinned labkit" (Z. 3); historische Protokolle mit ihrem Commit und Pin erhalten, nicht an aktuelle Gates anpassen (Z. 63–64); Pflichten aus protocol-check --contract, nicht aus älteren Laborständen (Z. 61–63).
- Lücke: Wie der Pin einer konkreten Area festgestellt wird, steht nicht ausdrücklich im Text; "preserved" beschreibt nicht, wie eine frühere Entscheidung nach --decide sichtbar bleibt.

**Allgemeine offene Punkte**
1. Typ-Wahl (confirmatory/exploratory) ist in mehreren Fällen nicht vorgegeben.
2. Die Form des Protokolls für compute (Pflichtfelder) ist nur über protocol-check --contract zu erfahren.
3. Der Befehl für 02_analyze.py --check ist nicht ausgeschrieben.
4. Die Offenlegung einer Folgefrage ist nicht verortet.
