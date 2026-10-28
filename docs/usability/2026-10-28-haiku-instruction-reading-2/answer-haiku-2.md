Lesehinweis: Alle Zeilenangaben „L." beziehen sich auf /Users/max/projects/labkit-agents-clarity/docs/usability/2026-10-28-haiku-instruction-reading-2/instructions.md. Mit [Text] markiere ich, was die Anleitung ausdrücklich sagt, mit [Urteil], was ich daraus schließe.

**Fall 1: RandomForest in fünf Sekunden, Vorhersage auf unbeschrifteten Testzeilen**
- Nächste Schritte: kind = fit [Text, L. 55–59: „A RandomForest fitted in seconds is `fit`, usually at `low` repeat cost“]. repeat_cost = low [Text, L. 59]. type = confirmatory [Urteil aus L. 53: Frage und Kriterium vor den Ergebnissen festgelegt].
- Kriterium owed: ja [Text, L. 96 und L. 61: „Neither `low` nor `exploratory` removes a fit/apply's criterion or audits“]. Analysis-Audit owed: ja [Text, L. 159–160: „at either cost“]. Preflight-Audit und Freeze: nicht owed [Text, L. 144].
- Erlaubte Aussage: noch keine. Erst nach Auswertung des Kriteriums und des Analysis-Audits.
- Lücke: L. 56–57 verlangt die Auswertung auf „held-out labelled rows“. Unbeschriftete Testzeilen tragen das Kriterium nicht. Die Anleitung sagt nicht, wie die Auswertung dann aussehen soll [Urteil].

**Fall 2: Lokale Dokumente zählen, sechs Stunden, nicht leichtfertig wiederholen**
- Nächste Schritte: kind = compute [Text, L. 51 und L. 57–58: weder Fit noch Apply]. repeat_cost = high [Urteil aus L. 52: „a repeat needs protection by a preflight audit and freeze“; die Anleitung nennt keine Stundenschwelle]. type nach Frage [Urteil, L. 53].
- Owed: `--show` nicht [Text, L. 116–117: „compute has no `--show`“]. `--probe` nicht [Text, L. 133: „Compute has no `--probe`; test its calculation“]. Stattdessen Test der Berechnung an handgeprüften Fällen [Text, L. 119, 133]. `preflight <area>` ja, `labkit-audit <area> --mode preflight` ja, Befunde entscheiden, `preflight_audit` in den Protokollkopf, `labkit-init exp <name> --report`, `frozen = true` [Text, L. 138–142]. Analysis-Audit ja [Text, L. 159].
- Lücke: Ab wann ein Lauf als „high“ gilt, sagt die Anleitung nicht; die Wahl ist Urteil.

**Fall 3: Unveränderter LLM gegen Gold-Labels, viele Stunden pro Messung**
- Nächste Schritte bei high (Reihenfolge):
  1. `labkit-init exp <name> --repeat-cost high --kind apply --model <alias>` [Text, L. 83–87].
  2. `protocol-check <PROTOCOL> --contract` und `protocol-fill <PROTOCOL> --list` [Text, L. 91–92].
  3. Vor dem Lauf ausfüllen: Frage, Daten/Scope, Ausschlüsse, Einheit; Kriterium, Zulassungsbedingung, Nullbedingung [Text, L. 95–97]; Datenprofil und `protocol-fill <PROTOCOL> --prompts` [Text, L. 99–100]; Zusagen C/A/B [Text, L. 102–103].
  4. Datenprofil: Urteil, ob Oberflächenmerkmale die Frage ohne die gemeinte Fähigkeit beantworten könnten, im Datenprofil festhalten [Text, L. 122–123].
  5. `01_measure.py --show 2` lesen, `code-check <area>`, Bereichstest [Text, L. 116–119].
  6. `01_measure.py --probe`, Auswertung an synthetischen Extremen testen [Text, L. 128–131].
  7. Committen, `preflight <area>`, `labkit-audit <area> --mode preflight`, Befunde entscheiden, Freeze [Text, L. 138–143].
  8. Committen, dann `.venv/bin/runlog start <area> -- .venv/bin/python <area>/scripts/01_measure.py`, überwachen mit `.venv/bin/runlog <area> --wait` [Text, L. 146–155].
  9. `finalize <area>`, dann `labkit-audit <area> --mode analysis` [Text, L. 159–160].
- Wenn der Lauf `low` wäre: kein `--probe` [Text, L. 133–134], kein Preflight und kein Freeze [Text, L. 144], Vordergrundlauf [Text, L. 147–148]. `--show`, Datenprofil, Code-Check und Analysis-Audit bleiben [Urteil aus L. 116–123 und L. 159, die dort nicht auf high beschränkt sind].
- Ein Datenhelfer genügt nicht. `00_prepare.py --audit` liefert „hints, not the judgement“ [Text, L. 124–125]. Das Urteil muss im Datenprofil stehen [Text, L. 122–123].
- Lücke: Wie der Hintergrund-Audit konkret laufen soll, sagt die Anleitung nur als „your harness's background-task mechanism“ [Text, L. 153–155].

**Fall 4: Low-Fit committet, finalize besteht, Analysis-Audit ohne Befunde, Conclusion leer**
- Nächste Schritte: (a) `protocol-fill <PROTOCOL> "Conclusion=<...>"`, höchstens zwei schlichte Sätze, vor der Adoption [Text, L. 187–188]. (b) Übrige Felder nach dem Lauf füllen [Text, L. 189]. (c) Kein Entscheidungs-Review, da kein BLOCKER [Text, L. 197–198]. (d) `protocol-fill <PROTOCOL> --from-run <run_id>` [Text, L. 213–216]. (e) `protocol-fill <PROTOCOL> --into REPORT.md` [Text, L. 224–225]. (f) Erklärung im Bericht selbst schreiben, passend zur Conclusion [Text, L. 226–227]. (g) Berechnete Zahlen in `metrics.json` aus den Zeilen [Text, L. 228–230]. (h) Staging: Bericht, Protokoll, Outputs, Runs, Audit-Nachweise zusammen; `runs.tsv` nicht stagen, es ist eine ignorierte Sicht [Text, L. 240–244].
- Generiert: Ergebnisblock, Recorded results, Laufeintrag, Grenzen [Text, L. 213–214, 220–222, 224–225]. Verfasst: Conclusion [Text, L. 187], Berichtserklärung [Text, L. 227], Eingabewerte in `metrics.json` [Text, L. 228–230].
- Lücke: Welche „übrigen Felder“ gemeint sind, steht nicht da [Urteil].

**Fall 5: Low-Fit, Audit nennt zwei verbotene Leak-Merkmale und eine Diagnose; nur eins entfernt, nicht neu gemessen, „fixed“ setzen?**
- Nicht zuerst. `fixed` heißt: die ganze benannte Störung korrigiert und die angeforderte Diagnose gelaufen und bewertet [Text, L. 166–168]. Ein Merkmal von zwei reicht nicht [Urteil].
- Nächste Schritte: beide Merkmale im Code entfernen, nicht in der Ausschlussregel [Text, L. 254–257]. Test, `code-check` [Text, L. 118–119], committen, neue Messung unter unveränderter Registrierung [Text, L. 169–171], `finalize`, Analysis-Audit [Text, L. 159–160], Diagnose laufen lassen und bewerten, dann `labkit-audit <area> --decide <N> fixed "<REASON>" --record <record>` [Text, L. 164–168].
- Ohne Freeze und Preflight, Vordergrundlauf [Text, L. 144, 147–148].
- Ausschlussregel ändern repariert den Fehler nicht [Text, L. 256–257]. Code-Änderung repariert auch den alten Lauf nicht [Text, L. 172]. Ein Output, der das Leak-Ergebnis trägt, ist neu aus einem Lauf nach dem Fix zu schreiben oder zu entfernen [Text, L. 40–43].
- Lücke: Was die „requested diagnostic run“ konkret ist, steht nicht da.

**Fall 6: Gültiger Low-Fit verfehlt C1; breitere Nullbedingung und niedrigere Schwelle im selben Protokoll, oder neue Area, die die Frage als beantwortet behauptet?**
- Richtiger Weg: den Fehlschlag als Ergebnis berichten [Text, L. 258–259: „that is the result: report the miss first“]. Die Adoption verbucht ihn als berichtbaren Fehlschlag [Text, L. 220–222].
- Verboten: Schwelle senken ist keine Reparatur [Text, L. 259–260]. Kriterien und Konstanten nach Ergebnissen ändern beantwortet die ursprüngliche Frage nicht [Text, L. 109–111]. Eine neue Area als Ersatz setzt eine ungültige Registrierung voraus [Text, L. 264–269]. Ein neuer Ansatz macht einen Fehlschlag nicht zum Erfolg [Text, L. 270–271].
- Erlaubt: spätere Untersuchung als eigenes Protokoll, ohne `[replaces]`, `type = "exploratory"`, Frage/Hypothese nennt A und was A zeigte [Text, L. 272–275].
- Lücke: Ob eine fehlerhafte Nullbedingung als „ungültige Registrierung“ zählt, ist Urteil. Das Beispiel im Text sind unvereinbare Definitionen des Kriteriums [Text, L. 264–266].

**Fall 7: Metriken c1_pass=True und a3_pass=True; Audit-Befund akzeptiert mit `A3 not assessable`**
- Bericht zeigt: C1 und die übrigen Kriterien als nicht bewertbar, nicht als bestanden. Eine nicht bewertbare Zulassungsbedingung lässt jedes Kriterium nicht bewertbar [Text, L. 180–182]. Gemessene Werte bleiben Beschreibung [Text, L. 182–183] und sind mit „nicht bewertbar, nicht bestanden“ zu berichten [Text, L. 261–263].
- `metrics.json` nicht editieren. Die Verdikte erzeugt `protocol-fill`, Rohmetriken bleiben unverändert [Text, L. 220–222, 224–225].
- Entscheidungs-Review: nicht ausdrücklich nötig. Der Text verlangt ein Review nur bei `stands` [Text, L. 197–198]; „not assessable does not itself require a decision review“ [Text, L. 208].
- Lücke: Bei einem BLOCKER mit anderem Effekt als `stands` sagt der Text nichts [Urteil].

**Fall 8: BLOCKER mit `stands` bestätigt, adoptiert und in REPORT.md gerendert; nur die Conclusion verstärken**
- Befehl: `protocol-fill <PROTOCOL> "Conclusion=<...>" --force` [Text, L. 191–192].
- Bleibt gültig: adoptiertes Ergebnis und Berichtsblock, da aus dem Lauf gerendert, nicht aus der Conclusion [Text, L. 192–193].
- Veraltet: alle Entscheidungs-Reviews [Text, L. 193–194; L. 205–206]. Das Review des BLOCKERs `stands` ist neu zu holen [Text, L. 197–198]. Die Berichtserklärung muss passen und wird neu geschrieben [Text, L. 194–195, 227].
- Keine neue Messung [Text, L. 207].
- `--again` settled die alte Ablehnung nicht: „never supplies missing approval or overrules an earlier rejection“ [Text, L. 208–209].
- Lücke: Die Anleitung nennt `--again` nur an dieser Stelle und erklärt nicht, welches Kommando genau gemeint ist [Urteil].

**Fall 9: Analysis-Audit fehlgeschlagen, Adoption verweigert, Metriken gut, Bericht fällig**
- Weg: `protocol-fill <PROTOCOL> --discuss <run_id> --why "<was die Adoption verhinderte, was du fandest>" --into REPORT.md` [Text, L. 232–234]. Der Bericht sagt, dass die Frage offen bleibt; Diskussion ist keine Erfolgsaussage [Text, L. 234–235].
- Pflichten: `labkit-audit <area> --report-review REPORT.md` für den fertigen Bericht [Text, L. 235–236]. Eine vom Reviewer benannte Behauptung korrigieren und den geänderten Stand reviewen; ein sauberer Befund am unveränderten Stand gibt nichts frei [Text, L. 236–238].
- Metriken gut heißt nichts: „do not present its unadopted numbers as the answer in REPORT.md“ [Text, L. 245–246]. Zitate in Prosa brauchen Entfernung oder ausdrückliche Diskussion [Text, L. 286–287].
- Reicht Prosa „nicht berichtet“? Nach dem Text nein [Urteil aus L. 245–246 und L. 286–287].
- Wenn der Stand nicht lösbar ist: Abbruch über `protocol-fill <PROTOCOL> --handover --why "<...>" --tried "<...>" --into REPORT.md` [Text, L. 276–281]. Keine Run-IDs in Grund und Versuchen [Text, L. 288]. Das ist die einzige Verbuchung ohne Zahl oder Freigabe [Text, L. 289–290].
- Lücke: Welcher der Wege bei knapper Zeit passt, entscheidet der Text nicht [Urteil].

**Fall 10: Registrierung mit unvereinbaren Definitionen; Ersatzweg, Folgen für Ergebnisse, Typ, Pflicht zur Ersetzung jeder späteren Frage**
- Weg: Konflikt erklären, dann `labkit-init exp <new-name> --kind …`, `type = "exploratory"`, `[replaces] protocol = "<id>"`, je Änderung ein `[[replaces.change]]` (what, from, to, why), offene BLOCKER des Vorgängers `deferred` [Text, L. 264–269].
- Frühere Befunde und Ergebnisse bleiben erhalten [Text, L. 293–295]. Der neue Lauf zeigt sein eigenes Urteil zuerst; ein neuer Ansatz macht eine frühere Verfehlung nicht zum Erfolg [Text, L. 270–271].
- Nicht jede spätere Frage ersetzt. Nur ein neuer Versuch derselben Frage ist Ersatz; andere spätere Fragen sind eigene Protokolle ohne `[replaces]` [Text, L. 271–275].

**Fall 11: `finalize` besteht, aber die externe Aufgabe verlangt `pred_results/predictions.csv` im Repo-Wurzelverzeichnis; die Datei liegt nur im Area-Output**
- Nicht erledigt. Die Datei ist das Ergebnis; sie muss unter dem verlangten Pfad liegen, aus dem beantwortenden Lauf, nicht neu geschrieben [Text, L. 35–40]. Pfade, Formate und Inhalt selbst prüfen [Text, L. 240–241].
- Nächster Schritt: die Ausgabedatei des beantwortenden Laufs an den verlangten Pfad kopieren und mit dem Bericht und Protokoll stagen [Text, L. 39, 242–243].
- Was das Gate garantiert: nur seine eigenen Prüfungen. „a green gate proves only its encoded checks“ [Text, L. 240–241].
- Lücke: Ob der Pfad außerhalb der Area zusätzlich in den Lauf-Nachweis muss, steht nicht da [Urteil].

**Fall 12: `--decide` setzen und neuen Berichtsblock erzeugen, dazu „evidence is preserved“; erlaubt? Welche Version gilt?**
- Erlaubt: `--decide` ist der dokumentierte Weg für Befunde [Text, L. 164–165]; `protocol-fill --into` und `--render` erzeugen den Block [Text, L. 224–226]. „These permitted updates do not erase or rewrite the earlier measurements“ [Text, L. 293–296].
- Intakt bleiben: Laufnachweise, Audit-Antworten, frühere Befunde, Historie; erfolglose Audits bleiben [Text, L. 293–296]. Nicht umgehen mit `--no-verify`, nicht Records editieren, nicht löschen, keine Ignore-Regeln [Text, L. 297–298].
- Welche Version: die Pin-Zeile des `labkit`-Pakets in `requirements.lock` (sonst `requirements.txt`), für das ganze Repo [Text, L. 65–67]. Historische Protokolle mit ihrem Commit und ihrem Pin reproduzieren [Text, L. 70–72]. Die Pflichten nicht aus einer älteren Lab-Anleitung nehmen, sondern aus `protocol-check <PROTOCOL> --contract` [Text, L. 63–64].
- Lücke: Ob nach einer geänderten Entscheidung ein Review fällig ist, folgt aus L. 205–206 [Urteil].

**Fall 13: Labkit-Pin wurde angehoben; alter Bereich mit `standard = "0.21"` wird abgelehnt; Analyse heute reproduzieren, zusätzlich neue Frage**
- Alter Bereich: nicht umschreiben; am ursprünglichen Commit mit dem ursprünglichen Pin reproduzieren [Text, L. 70–72]. Den Protokollkopf nicht an den aktuellen Gate anpassen [Text, L. 70–71].
- Neue Frage: frischer Bereich mit `labkit-init exp <name> --repeat-cost <cost> --kind <kind>` [Text, L. 72, 83–84].
- Welche labkit-Version gilt: die Pin-Zeile in `requirements.lock` (sonst `requirements.txt`); `labkit-check` zeigt sie neben der installierten Version [Text, L. 65–67]. `standard = "…"` nennt das Protokollformat, nicht die Paketversion [Text, L. 67–68].
- Frühere Audits: keiner deckt einen Bereich nach der Anhebung ab [Text, L. 68–69].
- Lücke: Wie man am alten Commit mit altem Pin arbeitet, ist nicht beschrieben [Urteil].

**Fall 14: Protokoll A (Fit) verfehlte C1, Verfehlung berichtet; nun andere Modellfamilie auf denselben Daten**
- Kein Ersatz über `[replaces]`. Der Ersatzweg gilt für ungültige Registrierung, nicht für eine verfehlte Verfehlung [Text, L. 258–259, 264–266]. Ob es derselben Frage gilt, ist Urteil; ein anderes Modell auf denselben Daten ist hier eher eine neue Frage [Urteil].
- Registrierung: neues Protokoll B mit `labkit-init exp <name> --kind fit` (ein Modell wird trainiert) [Text, L. 55–56, 83–84]. `type = "exploratory"`, denn B baut auf dem auf, was A zeigte [Text, L. 272–275]. Frage/Hypothese nennt A und die Verfehlung von C1 [Text, L. 273–274].
- Verfehlung von A bleibt, wie sie ist [Text, L. 270–271, 293–295].

**Fall 15: Analysis-Audit ohne Befunde, Code, Zusagen und Lauf geprüft; adoptieren? Was, wenn ein früherer BLOCKER behoben wurde?**
- Ja, adoptierbar, wenn Messung, Audit und `02_analyze.py --check` gelten [Text, L. 215–219]. Nichts zu entscheiden [Text, L. 218].
- Früherer BLOCKER: Die Behebung muss in diesem Datensatz bestätigt werden [Text, L. 218–219]. Der neue Audit führt frühere entschiedene BLOCKER weiter; ungeklärte werden übernommen und dort entschieden [Text, L. 170–172]. Eine Code-Änderung verlangt eine neue Messung, Finalisierung und neuen Audit [Text, L. 169–171].
- Lücke: Wie die Bestätigung eines früheren BLOCKERs ohne Befund im neuen Datensatz verbucht wird, steht nicht da; das einzige dokumentierte Kommando ist `--decide` für Befunde [Text, L. 164–165] [Urteil].

**Fall 16: Nach Adoption und Rendern ist die Conclusion zu stark; abschwächen**
- Befehl: `protocol-fill <PROTOCOL> "Conclusion=<...>" --force` [Text, L. 191–192].
- Bleibt gültig: Adoption und Berichtsblock [Text, L. 192–193].
- Veraltet: alle Entscheidungs-Reviews; wo einer gefordert ist, neu holen [Text, L. 193–194, 205–206]. Die Berichtserklärung ist anzupassen [Text, L. 194–195, 227].
- Keine neue Messung [Text, L. 207].
- Lücke: Ob die Abschwächung ein eigenes Begründungsfeld verlangt, sagt die Anleitung nicht [Urteil].

**Offene Lücken über alle Fälle hinweg**
1. `--again` wird nur in L. 209 erwähnt, ohne Kommando-Beschreibung.
2. Die Stundenschwelle zwischen low und high fehlt (Fälle 2, 3).
3. Der konkrete Hintergrundlauf für Audits fehlt (Fall 3).
4. Die Bestätigung eines früheren BLOCKERs in einem Datensatz ohne Befund ist nicht als Kommando beschrieben (Fall 15).
5. Welche übrigen Felder nach dem Lauf zu füllen sind, ist nicht aufgelistet (Fall 4).
