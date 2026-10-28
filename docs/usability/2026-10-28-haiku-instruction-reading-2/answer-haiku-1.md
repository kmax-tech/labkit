Bericht des Lesers zu instructions.md (315 Zeilen) und cases.txt (18 Zeilen). Gelesen wurden nur diese beiden Dateien. Zeilenangaben beziehen sich auf instructions.md. Abkürzungen: C = Kriterium, A = Zulassungsbedingung (Admissibility), B = registrierter Zweig, BLOCKER = schwerer Audit-Befund, WARNING = leichterer Befund, Freeze = Einfrieren des Protokolls (`frozen = true`), Preflight-Audit = Prüfung vor dem Einfrieren, Analysis-Audit = Prüfung nach dem Lauf.

1. Kind: `fit` (Z. 56-59: "Choose fit, even if the deliverable is predictions without gold labels"; "A RandomForest fitted in seconds is fit"). Repeat cost: `low` (Z. 59). Type: `confirmatory` (Z. 53, Frage und Kriterium vor den Ergebnissen festgelegt).
- Kriterium, Zulassungsbedingung und Nullbedingung sind Pflicht (Z. 96-97). Analysis-Audit ist Pflicht, bei jedem Kosten-Stufe (Z. 61, Z. 159-160). Preflight-Audit und Freeze entfallen bei `low` (Z. 144).
- Nächste Schritte: `labkit-init exp <name> --repeat-cost low --kind fit`; `protocol-fill <PROTOCOL> --list` und `protocol-check <PROTOCOL> --contract` (Z. 91-92); Vor-Lauf-Felder füllen; committen (Z. 146); im Vordergrund `.venv/bin/python <area>/scripts/01_measure.py` (Z. 147-148); `finalize <area>`; `labkit-audit <area> --mode analysis` (Z. 159-160).
- Lücke: Das Kriterium wird nur an gelabelten Held-out-Zeilen beurteilt (Z. 57-58). Die Instruktionen sagen nicht, wie dieser Split zu wählen ist. `--show 2` gilt für Estimator-Skelette vor dem Lauf (Z. 115-117). Ob das RandomForest-Skelett darunter fällt, ist Auslegung.

2. Kind: `compute` (Z. 51: "calculate a quantity without judging predictions"). Ein Zählwert hat keine Vorhersage-Kriterien (Z. 78).
- Repeat cost: `high`. Z. 52: "a repeat needs protection by a preflight audit and freeze". Die Dauer allein entscheidet das nicht (Z. 52, "not the audit's or the whole task's duration"). Dass man nicht leichtfertig wiederholt, ist die Begründung.
- Type: nicht aus dem Fall ableitbar, nach der Frage zu wählen (Z. 53).
- Pflicht: `--show` entfällt (Z. 116-117, "compute has no --show"). `--probe` entfällt (Z. 133-134). Preflight: `preflight <area>` (Z. 138-139). Preflight-Audit: `labkit-audit <area> --mode preflight`, Befunde wie in Schritt 4 entscheiden (Z. 139-141). Freeze: `frozen = true` nach `--report` (Z. 141-142). Analysis-Audit ist ebenfalls Pflicht (Z. 159-160). Die Rechnung selbst testen (Z. 133-134), `code-check` nach Codeänderungen (Z. 118).
- Lücke: Wie die Zahl ins Protokoll kommt (Z. 228-230: Eingangszahlen aus `kept rows` in `metrics.json`) ist nur grob beschrieben.

3. Kind: `apply` (Z. 60, "An unchanged LLM judged against labels is apply"). Repeat cost: `high`, weil mehrstündige Wiederholung Schutz durch Preflight-Audit und Freeze braucht (Z. 52). Die Einstufung über die Dauer ist meine Auslegung.
- Vorher-Sequenz bei `high`: (a) `labkit-init exp <name> --repeat-cost high --kind apply --model <alias>`, weil Aufrufe über `models.toml` laufen (Z. 83-85). (b) Vor-Lauf-Felder: Frage, Daten/Umfang, Ausschlüsse, Einheit (Z. 95); Kriterium, Zulassungsbedingung, Nullbedingung (Z. 96-97); Datenprofil und `protocol-fill <PROTOCOL> --prompts` (Z. 99-100); Zusagen C/A/B (Z. 102-103); Registrierung committen vor der ersten vollen Messung (Z. 110). (c) Code implementieren, `code-check <area>`, Bereichstest (Z. 115-120); `01_measure.py --show 2` lesen (Z. 115-117). (d) Datenprofil: Oberflächenmerkmale prüfen und Urteil festhalten (Z. 122-123). (e) `01_measure.py --probe` mit Rohbeispielen; Auswertung an synthetischen Extremen testen (Z. 129-131). (f) `preflight <area>`, `labkit-audit <area> --mode preflight`, `preflight_audit` im Kopf, `--report`, `frozen = true` (Z. 138-143). (g) Committen, dann `.venv/bin/runlog start <area> -- .venv/bin/python <area>/scripts/01_measure.py` und `.venv/bin/runlog <area> --wait` (Z. 146-153). (h) `finalize <area>`, `labkit-audit <area> --mode analysis` (Z. 159-160).
- Bei `low` (gleiche Messung, beliebig wiederholbar): Probe, Preflight-Audit und Freeze entfallen (Z. 133-134, 144). `--show`, Datenprofil, Commit, `finalize` und Analysis-Audit bleiben (Z. 76-77, Z. 115-117, Z. 159-160). Die Messung läuft im Vordergrund (Z. 147-148).
- Ausführen des Datenprofil-Helfers reicht nicht: Das Urteil muss in Datenprofil stehen, die Zählungen von `00_prepare.py --audit` sind nur Hinweise (Z. 124-125).
- Lücke: Das Skelett-Verhalten für LLM-Aufrufe ist nicht vollständig beschrieben. Die Dauer-Schwelle für `high` ist nicht festgelegt.

4. Restfolge: (a) `protocol-fill <PROTOCOL> "Conclusion=…"` vor der Übernahme, höchstens zwei schlichte Sätze (Z. 187-188). Weitere Nach-Lauf-Felder füllen; mit Modell je ein echtes Prompt-Antwort-Paar aus der Rohausgabe (Z. 188-191). (b) `protocol-fill <PROTOCOL> --from-run <run_id>` (Z. 213-216); die Übernahme prüft Analysis-Audit und `02_analyze.py --check`. (c) `protocol-fill <PROTOCOL> --into REPORT.md` (Z. 224-225). (d) Erklärung im Bericht selbst schreiben, konsistent mit Conclusion (Z. 226-228). (e) Ausgabepfade der externen Aufgabe prüfen, staging (Z. 240-244).
- Generiert: `[result] run`, Recorded results, Run-Eintrag (Z. 214-215, 221-222); Ergebnisblock und Grenzen im REPORT.md (Z. 224-225, "Never retype those values").
- Von Hand: Conclusion (Z. 187), Erklärung im Bericht (Z. 226-228), übrige Nach-Lauf-Felder, Rohausgabe-Paar (Z. 190-191), Eingangszahlen in `metrics.json` (Z. 228-230).
- Lücke: Die Liste der Nach-Lauf-Felder ist nicht vollständig. Die Reihenfolge Conclusion/Übernahme ist nur über Z. 187 ("before adoption") festgelegt.

5. Zuerst: den zweiten Leak im Code entfernen, nicht im Ausschluss-Regelwerk (Z. 255-257). Dann testen (Z. 115-120), committen, neu messen, `finalize`, Analysis-Audit (Z. 169-170). Die verlangte Diagnose laufen lassen und bewerten (Z. 166-167). Erst dann `labkit-audit <area> --decide <N> fixed "<REASON>" --record <record>` (Z. 164-167). Die Regel: "fixed" heißt, dass die ganze genannte Störung behoben und die Diagnose gelaufen und bewertet ist; der Status ist Entscheidung, kein Beweis (Z. 166-168).
- Das Ändern des Ausschlussregelwerks repariert den Fehler nicht (Z. 256-257). Codeänderung allein repariert den alten Lauf nicht (Z. 171-172). Die Kopfbedingung ist also: neuer Lauf unter unveränderter Registrierung (Z. 254-255).
- Lücke: Wie die Diagnose bewertet wird, ist nicht beschrieben.

6. Sofortiger Weg: den Fehlschlag als Ergebnis berichten (Z. 258-259, "that is the result: report the miss first"). Ein Fehlschlag unter gültiger Zulassungsbedingung ist ein berichtbarer Fehlschlag (Z. 221-222). Das Absenken der Schwelle ist keine Reparatur (Z. 259-260). Ein Rand-Band nach Sicht der Ergebnisse ist verboten: Kriterien und Konstanten müssen vor den Ergebnissen stehen, sonst beantworten sie die ursprüngliche Frage nicht (Z. 109-111).
- Eine neue Area, die die Ursprungsfrage als beantwortet ausgibt, ist ausgeschlossen: "a new approach never turns an earlier miss into a pass" (Z. 271-272).
- Spätere Untersuchungen sind nicht verboten. Eine andere Frage bekommt ein eigenes Protokoll ohne `[replaces]`; baut sie auf A auf, nennt Question, was A gezeigt hat, und der Typ ist `exploratory` (Z. 273-275). Eine Exploration darf ohne Übernahme enden (Z. 245-246).
- Lücke: Ob ein Rand-Band eine neue Frage ist oder dieselbe, ist Auslegung.

7. Die Zusage C1 ist nicht als Erfolg berichtbar. Eine nicht beurteilbare Zulassungsbedingung macht jedes Kriterium nicht beurteilbar (Z. 180-181, "leaves every criterion not assessable"). Der Bericht zeigt also nicht bestanden; `c1_pass=True` und die gemessenen Werte bleiben Beschreibung (Z. 182-183). Die Verdikt-Ableitung erfolgt in Recorded results; die Rohmetriken bleiben unverändert (Z. 221-222). `metrics.json` nicht editieren, um das Verdikt zu ändern (Z. 221-222, Z. 293-294).
- Decision-Review: Pflicht nur bei einem BLOCKER, der mit `stands` angenommen wurde (Z. 197-198). "not assessable does not itself require a decision review" (Z. 208-209). Ob der Befund ein BLOCKER war, steht nicht im Fall; das bleibt offen.

8. Stale: die Decision-Review (Z. 193-194, Z. 205-206). Die Erklärung im Bericht muss weiter passen (Z. 194-195) und ist von mir neu zu schreiben (Z. 227-228). Das adoptierte Ergebnis und der REPORT-Block bleiben gültig (Z. 192-194). Keine neue Messung (Z. 207). Befehl: `protocol-fill <PROTOCOL> "Conclusion=…" --force` (Z. 191-193). Nachzuholen: Review, falls Pflicht, `labkit-audit <area> --review --record <record>` (Z. 197-198).
- `--again` ersetzt keine fehlende Zustimmung und hebt keine frühere Ablehnung auf (Z. 208-209). Ein sauberer Lauf am unveränderten Stand löst nichts (Z. 237-238). Ein früherer Ablehnungsfall bleibt offen.
- Lücke: Was `--again` genau tut, steht nicht im Text.

9. Der dokumentierte Weg: `protocol-fill <PROTOCOL> --discuss <run_id> --why "<was die Übernahme verhindert hat, was du gefunden hast>" --into REPORT.md` (Z. 232-234). Die Frage bleibt offen; Diskussion ist kein Erfolgsnachweis (Z. 235). Pflicht danach: `labkit-audit <area> --report-review REPORT.md` (Z. 236). Vom Gutachter genannte Aussagen korrigieren und den geänderten Stand prüfen lassen (Z. 236-238). Unübernommene Zahlen dürfen nicht als Antwort stehen (Z. 245-246).
- Evidenz: Bericht, Protokoll, Ausgaben, Läufe und Audit-Belege zusammen stagen, einschließlich `audits/attempts.jsonl` und Review-Belege (Z. 241-243). Fehlgeschlagene Audits behalten (Z. 296-297). `--no-verify` ist verboten (Z. 297-298).
- Alternative, wenn es nicht abschließbar ist: Handover mit `protocol-fill <PROTOCOL> --handover --why "…" --tried "…" --into REPORT.md` (Z. 276-283). Ein ehrlicher Abschluss ohne Ergebnis ist zulässig (Z. 250-251).
- Ob Prosa allein reicht: Die Instruktionen verlangen den `--discuss`-Weg mit Report-Review (Z. 232-238). Für Prosa allein gibt es keine Regel. Für die Zeitnot gibt es keinen Ausweg.
- Lücke: Ob der Handover-Text für diesen Fall gilt, ist unklar.

10. Ersatzweg: Den Widerspruch vor der neuen Registrierung erklären (Z. 265-267). Dann `labkit-init exp <new-name> --kind …`, Typ `exploratory`, `[replaces] protocol = "<id>"`, je Änderung ein `[[replaces.change]]` mit what/from/to/why, offene BLOCKER des Vorgängers `deferred` (Z. 267-269).
- Frühere Befunde und Ergebnisse bleiben erhalten (Z. 293-297). Das Verdikt des Vorgängers wird zuerst gerendert; ein neues Vorgehen macht daraus keinen Erfolg (Z. 270-272).
- Nicht jede spätere Frage ersetzt: "Only a new attempt at the same question is a replacement". Andere Fragen sind eigene Protokolle ohne `[replaces]` (Z. 270-271).
- Lücke: Wo die Erklärung des Widerspruchs stehen soll, steht nicht.

11. Die Aufgabe ist nicht erledigt. Der Pfad wird vom Gate nicht geprüft: "a green gate proves only its encoded checks" (Z. 240-241). Ausgabe muss dort liegen, wo die Aufgabe sie verlangt (Z. 35-38). Erlaubt ist, die Ausgabedatei des antwortenden Laufs zu kopieren, nicht neu zu schreiben (Z. 37-39). Also die Datei des Laufs an den Wurzelpfad kopieren, Pfad und Format selbst prüfen, mit Bericht und Protokoll stagen (Z. 240-244).
- Lücke: Ob das Kopieren in den Wurzelpfad mit dem Layout des Repos vereinbar ist, sagen die Instruktionen nicht. Ebenso nicht, wie man den "antwortenden Lauf" im Wurzelpfad kennzeichnet.

12. Beides ist erlaubt. `--decide` (Z. 164, Z. 293-295 "Change decisions with --decide"). Neuer Berichtsblock: nach geänderten Entscheidungen `protocol-fill <PROTOCOL> --render`, dann Berichtsblock neu erzeugen (Z. 225-226; Z. 294-295 "generate result updates with protocol-fill"). Die Schlusssätze widersprechen sich nicht: "These permitted updates do not erase or rewrite the earlier measurements" (Z. 295-296).
- Intakt bleiben: Laufbelege, Audit-Antworten, frühere Befunde, Historie (Z. 293-294), fehlgeschlagene Audits (Z. 296-297), keine Löschungen, keine Änderung an Aufzeichnungen, keine Ignore-Regeln (Z. 297-298).
- Maßgebende Version: Für eine festgesetzte Area gilt die Labkit-Version des Originalcommits und der Originalpin; nicht umschreiben, sondern dort reproduzieren (Z. 70-72). Der Pin ist die `labkit`-Zeile in `requirements.lock`, sonst `requirements.txt` (Z. 63-66).
- Lücke: Ob `--decide` und `--render` mit einem alten Pin funktionieren, sagt der Text nicht.

13. Alte Area: Protokoll nicht umschreiben, um die Gates zu bestehen. Am ursprünglichen Commit und mit dem ursprünglichen Pin reproduzieren (Z. 70-73). Achtung: `standard = "0.21"` nennt das Protokollformat, nicht die Labkit-Version (Z. 66-67). Die Version liest man aus der `labkit`-Zeile von `requirements.lock` (sonst `requirements.txt`); `labkit-check` zeigt Pin und installierte Version (Z. 63-66).
- Frühere Audits decken die Area nach der Pin-Erhöhung nicht mehr (Z. 68-69).
- Neue Frage: frische Area mit `labkit-init exp <name> --repeat-cost … --kind …` unter dem aktuellen Pin (Z. 72-73, Z. 83-84).
- Lücke: Der Befehl, um am alten Commit zu reproduzieren, steht nicht im Text.

14. Ob das ein Ersatz von A ist, lässt sich nicht eindeutig aus dem Text ableiten. Die Ersatz-Route ist nur für ungültige Registrierung dokumentiert (Z. 265-270). "Only a new attempt at the same question is a replacement" steht dort. A ist aber nicht ungültig. Bleibt die Frage dieselbe (C1 auf denselben Daten), wäre es ein neuer Versuch derselben Frage, aber die Route dafür steht nicht da.
- Wahrscheinlicher Weg: eigenes Protokoll B, Typ `exploratory` (Z. 273-275), Question nennt A und was A gezeigt hat. Kriterien und Konstanten aus A übernehmen, vor den Ergebnissen von B festgelegt (Z. 109-111).
- Der Fehlschlag von A bleibt berichtet; ein neuer Ansatz macht ihn nicht zum Erfolg (Z. 271-272, Z. 293-297).
- Lücke: ob A ersetzt wird und ob `[replaces]` gesetzt wird.

15. Ja, übernehmen. Der Analysis-Audit ohne Befunde deckt den Lauf, wenn er aktuellen Code, Zusagen und Lauf sah. Es gibt nichts zu entscheiden (Z. 217-219). Übernahme: `protocol-fill <PROTOCOL> --from-run <run_id>` (Z. 213-216).
- Wurde ein früherer BLOCKER seither behoben, muss der neue Befund das im Protokoll bestätigen: "an earlier BLOCKER still needs its fix confirmed in that record" (Z. 218-219). Wer einen Codefehler behoben hat, muss neu messen und den Audit neu laufen lassen (Z. 169-170). Offene BLOCKER werden in den neuen Befund übernommen und dort entschieden (Z. 170-172).
- Lücke: Wie die Bestätigung im Befund festgehalten wird, steht nicht da. Wird ein früher abgelehnter BLOCKER jetzt `fixed`, ist eine Bestätigungs-Review nötig (Z. 201-203).

16. Befehl: `protocol-fill <PROTOCOL> "Conclusion=<schwächer>" --force` (Z. 191-193). Gültig bleiben: das adoptierte Ergebnis und der Ergebnisblock im REPORT.md (Z. 192-194). Veraltet: alle Decision-Reviews (Z. 193-194, Z. 205-206). Nachzuholen: Review, wo sie Pflicht ist (Z. 197-198), und die Erklärung im Bericht, die zur neuen Conclusion passen muss (Z. 194-195, Z. 227-228). Keine neue Messung (Z. 207). Die Conclusion bleibt bei höchstens zwei Sätzen (Z. 187-188).
- Lücke: Ob der Conclusion-Text auch an anderer Stelle im REPORT.md steht und von Hand ersetzt werden muss, ist nicht geregelt.

Gesamtlücken: (a) Wer schreibt `metrics.json` und wann (Z. 228-230). (b) Wie man am alten Commit reproduziert. (c) Was `--again` tut. (d) Wie eine Bestätigung im Befund festgehalten wird. (e) Typ bei `compute`, wenn die Frage offen ist. (f) Der Weg bei Zeitdruck ohne Übernahme.
