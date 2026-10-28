Lesebericht zu den vier Situationen (S1, S2, S4, S5). Gelesen wurden nur instructions.md und cases.md. Zeilenangaben beziehen sich auf /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-stuck-reading/instructions.md (kurz "Anl.") bzw. cases.md (kurz "Fälle"). Die Lesart der Regeln und die Befehle unten sind meine Ableitung aus dem Text, nicht geprüft am Werkzeug.

## S1: compute-hrv, repeat_cost low, kind compute

**(a) Probleme**
1. Die Verfeinerung in scripts/01_measure.py:113/:123 kürzt die Peak-Positionen auf das 10-ms-Raster (ganzzahliger dtype). Dadurch entsteht künstlicher Jitter; rmssd_ms 26.94 ist Artefakt (BLOCKER, Fälle Z. 40).
2. Der Protokollkopf und [result] zeigen auf Lauf 8b74 mit rmssd_ms 26.053. Der aktuelle Code liefert aber 26.94 bzw. anderes; drei Schlüssel fehlen im Protokoll (Fälle Z. 41, 39).
3. Der Analyse-Audit deckt den aktuellen Code nicht ab (Fälle Z. 42).
4. Die Ausgabe pred_results/hrv.csv stammt aus dem überholten Lauf 8b74 und ist damit falsch.
5. 02_analyze.py --check schlägt fehl, Recorded results und Limit-Zeilen sind veraltet (Fälle Z. 43–46).
6. Audit-Befund 22-38#2 steht auf accepted und wurde nie nachverfolgt (Fälle Z. 47).

**(b) Offene Optionen**
- fixed, für BLOCKER 1 (Anl. Z. 262–263: Implementierungsfehler → Code reparieren, neu messen, neuen Lauf prüfen). Hilft, aber fixed braucht die geforderte Diagnose (refined_peak_fraction_nonint, Fälle Z. 40).
- accepted mit --effect stands (Fälle Z. 19). Hilft hier nicht: der Fehler verfälscht die Zahl selbst; die Erklärung "Verdikt hält" wäre falsch.
- accepted mit --effect "<ID> not assessable" (Anl. Z. 269–271). Passt nur für unjudged promise; hier gibt es keine Kriterien mit compute, also nicht einschlägig.
- deferred / dismissed (Fälle Z. 28–29). Hilft nicht; reicht nicht, weil der Befund behoben werden kann.
- Handover: protocol-fill ... --handover (Anl. Z. 30, 289–301). Nur Ausweg, wenn der Fix nicht gelingt.
- Neues Protokoll mit [replaces] (Anl. Z. 272–285). Hilft nicht; Registrierung ist nicht ungültig, der Fehler liegt im Code.
- protocol-fill --from-run 4268 --force (Fälle Z. 39). Nur, wenn der Lauf 4268 den Fehler sicher nicht enthält; das ist aus den Ausgaben nicht klar.

**(c) Vorgehen, in dieser Reihenfolge**
```
rm experiments/01-compute-hrv/pred_results/hrv.csv   # Pfad: die Aufgabe nennt pred_results/hrv.csv; Datei löschen, weil BLOCKER offen (Anl. Z. 40–45)
git add experiments/01-compute-hrv/scripts/01_measure.py <Testdatei>   # nur eigene Pfade
git commit -m "01-compute-hrv: keep sub-sample peak positions as floats"
.venv/bin/python -m pytest -q
code-check experiments/01-compute-hrv
.venv/bin/python experiments/01-compute-hrv/scripts/01_measure.py      # low: Vordergrund
finalize experiments/01-compute-hrv
labkit-audit experiments/01-compute-hrv --mode analysis
labkit-audit experiments/01-compute-hrv --findings                    # dann jede Entscheidung mit dem ausgegebenen --decide-Befehl
protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --from-run <neue_run_id>
protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md "Conclusion=<Satz>"
protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --render
protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --into REPORT.md
.venv/bin/python experiments/01-compute-hrv/scripts/02_analyze.py --check
report-check experiments/01-compute-hrv
cp <Ausgabedatei von <neue_run_id>> pred_results/hrv.csv              # Datei des Laufs kopieren, nicht abtippen
```
Hinweis: "--force" nur, wenn --from-run ohne sie abgelehnt wird (Anl. Z. 193). Bei Ablehnung des Befunds mit fixed den Befehl lesen, nicht erraten.

**(d) Nicht tun**
- Keine Zahl (26.05, 26.94) abtippen oder in Report/Protokoll übernehmen (Anl. Z. 37–45; Fälle Z. 42–46).
- Kein --effect stands auf BLOCKER 1.
- Kein --force auf 4268 ohne Prüfung; kein --no-verify (Anl. Z. 308).
- Audit-, Lauf- und Protokoll-Evidenz nicht von Hand ändern (Fälle Z. 16).
- Kein Commit der Ausgabedatei in diesem Zustand.

**(e) Ausgabedatei**
Jetzt entfernen (Ergebnis gilt nicht mehr, BLOCKER offen; Anl. Z. 40–45). Nach dem neuen Lauf aus dessen eigener Ausgabedatei neu kopieren. Im Report sagen, was geschah und warum.

**Unsicher / Widersprüche**
- Anl. Z. 147 sagt "through runlog", Low sagt "in the foreground": ich habe Low als direkten Aufruf gelesen.
- --force steht in Anl. Z. 193 nur für das Ändern der Conclusion; report-check schlägt es aber für --from-run vor (Fälle Z. 39).
- Ob die Verfeinerung eine Änderung der Registrierung ist, sagt der Text nicht.
- Ob Lauf 4268 den Fehler enthält, ist aus den Ausgaben nicht klar.

## S2: fit-assay, repeat_cost low, kind fit

**(a) Probleme**
1. Nach dem Lauf wurden Text und Konstante von 0.15 auf 0.25 geändert; der Promise-Block wechselte (d37c134869ce → f571a17d2fc6). Die Registrierung wurde nach der Messung verändert (Fälle Z. 87, 93). Das Ergebnis beantwortet damit keine registrierte Frage.
2. Die Registrierung war intern widersprüchlich: Text 0.15, Konstante 0.25.
3. WARNING 139: die Registrierung beschreibt Tuning, der Code tut keines (Fälle Z. 72).
4. WARNING 2: die Änderung der Margin ist ein Zeugnis derselben Sache (Fälle Z. 75, 89–90).
5. 02_analyze.py --check schlägt fehl (Fälle Z. 88).
6. Der nächste Commit wird abgelehnt, weil der Stand selbst der Fehler ist.

**(b) Optionen**
- Text und Konstante zurück auf den ersten Commit: hilft nicht allein; der Widerspruch bleibt, die Registrierung ist dann ungültig.
- Neues Protokoll mit [replaces]: ist der vorgesehene Weg, wenn "die Frage nicht als geschrieben beantwortbar ist, z. B. widersprüchliche Definitionen" (Anl. Z. 272–285). Hilft am meisten.
- Missed criterion / Ergebnis als Miss berichten: nicht passend, weil der Lauf unter anderer Schwelle lief als registriert.
- accepted mit --effect stands auf WARNING 1/2: nicht geeignet, bevor die Review den Stand bestätigt (Fälle Z. 89–90); Review kann man mit --review anfordern.
- deferred oder dismissed: schließt nichts, solange die Review nicht hält (Fälle Z. 89).
- Handover: Ausweg, wenn kein neues Protokoll gelingt (Anl. Z. 286–301).

**(c) Vorgehen**
```
labkit-init exp fit-assay-m025 --kind fit --repeat-cost low
protocol-check experiments/fit-assay-m025/PROTOCOL-fit-assay-m025.md --contract
protocol-fill experiments/fit-assay-m025/PROTOCOL-fit-assay-m025.md --list
# Im Kopf: type = "exploratory", [replaces] protocol = "<id von 01-fit-assay>",
# je Änderung ein [[replaces.change]] (what, from, to, why); Konflikt im Text erklären
protocol-fill experiments/fit-assay-m025/PROTOCOL-fit-assay-m025.md "type=exploratory" "<Felder laut --list>"
git add experiments/fit-assay-m025/
git commit -m "fit-assay-m025: register anew, replacing 01-fit-assay (margin text and constant conflicted)"
.venv/bin/python experiments/fit-assay-m025/scripts/01_measure.py
finalize experiments/fit-assay-m025
labkit-audit experiments/fit-assay-m025 --mode analysis
labkit-audit experiments/fit-assay-m025 --findings
labkit-audit experiments/01-fit-assay --decide <N> deferred "<Grund: ersetzt durch fit-assay-m025>" --record audits/2026-10-27T23-21-analysis.toml
protocol-fill experiments/fit-assay-m025/PROTOCOL-fit-assay-m025.md --from-run <run_id>
protocol-fill experiments/fit-assay-m025/PROTOCOL-fit-assay-m025.md --into REPORT.md
report-check experiments/fit-assay-m025
```
Das alte Protokoll bleibt unangetastet; sein Ergebnis wird nicht als Antwort berichtet.

**(d) Nicht tun**
- Text oder Konstante nicht noch einmal ändern, um sie anzugleichen.
- Keinen --force, kein --no-verify, kein --effect stands ohne Review.
- Den Lauf 23-11-56_d0c0 nicht als Beleg für die Frage melden.
- Audit- und Lauf-Dateien nicht von Hand bearbeiten.

**(e) Ausgabedatei**
Die Aufgabe nennt keine (Fälle Z. 98). Falls ein Ergebnisfile aus d0c0 existiert, entfernen (Anl. Z. 42–45); nur aus dem Lauf des neuen Protokolls neu schreiben.

**Unsicher / Widersprüche**
- Ob der Fall "ungültige Registrierung" oder "Miss" ist, ist nicht eindeutig.
- Wie die BLOCKER von report-check auf einem ersetzten Protokoll geschlossen werden, steht nicht im Text.
- Anl. Z. 209 sagt, Konklusion-Änderungen brauchen keine erneute Messung; hier geht es aber um die Registrierung.

## S4: apply-screen, kind apply, repeat_cost low

**(a) Probleme**
1. Die Registrierung im ersten Mess-Commit fehlt (Frage, Kriterium, Zulässigkeit, Nullbedingung, repeat_cost) (Fälle Z. 116). Gemessen wurde ohne Intent (Anl. Z. 92–94).
2. Drei Läufe liefen unter drei verschiedenen Registrierungen (Blöcke 0bad…, 35ae…, 2777…); margin wurde zwischen den Läufen auf 0 gesetzt. Welche Registrierung galt, ist nicht feststellbar (Fälle Z. 117).
3. Der Nulllauf ist identisch mit dem registrierten Lauf: kein Rauschboden (Fälle Z. 118). Anl. Z. 97–98 verlangt die Nullbedingung im selben Lauf.
4. Kein Analyse-Audit (Fälle Z. 119).
5. Keine Antwort im Protokoll; 02_analyze.py --check schlägt fehl (Fälle Z. 120).
6. pred_results/screen_pred.csv fehlt.

**(b) Optionen**
- Neues Protokoll mit [replaces] (Anl. Z. 272–285; Fälle Z. 117): passt, weil die Frage in keiner Fassung als geschrieben beantwortbar ist. Hilft am meisten.
- Handover (Anl. Z. 286–301; Fälle Z. 117): ehrlicher Ausweg, wenn kein neues Protokoll gelingt.
- --findings: nutzlos, da kein Audit-Record existiert (exit 2, Fälle Z. 107).
- Null-Lauf reparieren: nötig im neuen Protokoll, löst aber die Registrierungsfrage nicht.
- protocol-fill --from-run 19-55-33 (Fälle Z. 120): Falle; der Lauf hat keine gültige Registrierung.

**(c) Vorgehen**
```
labkit-init exp apply-screen-2 --repeat-cost low --kind apply
protocol-check experiments/apply-screen-2/PROTOCOL-apply-screen-2.md --contract
protocol-fill experiments/apply-screen-2/PROTOCOL-apply-screen-2.md --list
# Im Kopf: type = "exploratory", [replaces] protocol = "p-6a698091085d4ac7",
# je Abweichung gegen b782, 24d7 und a71c ein [[replaces.change]]; Null: Vorhersagen gegen permutierte Gold-Labels (LAB-034 Null condition in the same run)
protocol-fill experiments/apply-screen-2/PROTOCOL-apply-screen-2.md "type=exploratory" "<Felder laut --list>"
git add experiments/apply-screen-2/
git commit -m "apply-screen-2: register anew, replacing apply-screen (three conflicting registrations, null lane identical)"
.venv/bin/python experiments/apply-screen-2/scripts/01_measure.py
finalize experiments/apply-screen-2
labkit-audit experiments/apply-screen-2 --mode analysis
labkit-audit experiments/apply-screen-2 --findings
protocol-fill experiments/apply-screen-2/PROTOCOL-apply-screen-2.md --from-run <run_id>
protocol-fill experiments/apply-screen-2/PROTOCOL-apply-screen-2.md --into REPORT.md
report-check experiments/apply-screen-2
```

**(d) Nicht tun**
- Keinen der drei Läufe als Ergebnis wählen; keine Run-IDs im Report als Zahlen (Anl. Z. 292–293).
- Die alte Registrierung nicht ändern.
- Kein --from-run auf den alten Protokoll.
- Kein --no-verify; kein Audit "bestehen lassen".

**(e) Ausgabedatei**
pred_results/screen_pred.csv nicht aus einem der alten Läufe erzeugen. Erst aus der Ausgabedatei des Laufs des neuen Protokolls kopieren; bei Handover bleibt sie fehlen und der Report sagt es (Anl. Z. 252–254).

**Unsicher / Widersprüche**
- Fälle Z. 117 und 123 empfehlen beide --from-run als Option zur Adoption, doch die Registrierung ist ungültig; der Text trennt das nicht sauber.
- Welche Änderungen genau in [[replaces.change]] gehören, geht aus den Fällen nicht hervor (nur margin ist sicher).
- Ob type "exploratory" für eine Apply-Registrierung zulässig ist, prüft laut Anl. Z. 285 niemand; das bleibt meine Verantwortung.

## S5: compute-hrv, repeat_cost low, kind compute

**(a) Probleme**
1. Der übernommene BLOCKER 2 (R-Peak-Detektor erkennt Fehlschläge; rr_outlier_fraction 0.12, Soll ≈0) wurde deferred, die Review hat es abgelehnt (Fälle Z. 165–166). Ein abgelehnter Befund wird durch Schließen nicht erledigt.
2. Die Conclusion nennt 98.09 bpm und 186.78 ms, obwohl die eigene Diagnose den Fehler zeigt (Fälle Z. 165).
3. WARNING 1 (Abtastrate 100 literal, nicht geprüft) wurde deferred mit dem Grund "100 Hz" – Review hat das als Beleg abgelehnt (Fälle Z. 164).
4. Die erste Registrierung (6a83) hat keine Frage und kein repeat_cost (Fälle Z. 162).
5. report-check meldet "no answer yet": Die Zahlen sind nicht per protocol-fill adoptiert, also getippt (Fälle Z. 163; Anl. Z. 214–215, LAB-041 Generate numbers, don't retype them).
6. Die Zahl in pred_results/hrv.csv steht ebenfalls auf dem getippten Wert.

**(b) Optionen**
- fixed für BLOCKER 2 nach Fehlerbehebung (Anl. Z. 262–263, Implementierungsfehler). Hilft; braucht die Diagnose nach dem Lauf.
- accepted mit --effect "<ID> not assessable" (Fälle Z. 144–145). Hilft als Fallback, falls nicht reparierbar; dann Zahlen nur als Beschreibung.
- accepted mit --effect stands: abgelehnt; hilft nicht.
- deferred / dismissed erneut: hilft nicht, Review-Ablehnung bleibt.
- --review (Fälle Z. 164–165): fragt einen zweiten Auditor; hilft nur, wenn der Grund neu ist. Begründung ist laut Review nicht neu.
- Neues Protokoll (Anl. Z. 272–285): nur, wenn die Frage als geschrieben nicht beantwortbar ist; fehlende Frage im Erstcommit ist dafür nicht eindeutig genug.
- Handover (Anl. Z. 286–301): ehrlicher Ausweg, wenn der Detektor nicht korrigiert werden kann.

**(c) Vorgehen**
```
rm pred_results/hrv.csv                       # Ergebnis gilt nicht mehr; BLOCKER offen (Anl. Z. 40–45)
# Conclusion mit 98.09 / 186.78 zurückziehen
# Detektor korrigieren; Test: rr_outlier_fraction ≈ 0; Abtastrate aus den Zeitstempeln prüfen statt 100 hart zu setzen
git add experiments/01-compute-hrv/scripts/01_measure.py <Testdatei>
git commit -m "01-compute-hrv: fix R-peak detector spurious beats; check sampling rate from timestamps"
.venv/bin/python -m pytest -q
code-check experiments/01-compute-hrv
.venv/bin/python experiments/01-compute-hrv/scripts/01_measure.py
finalize experiments/01-compute-hrv
labkit-audit experiments/01-compute-hrv --mode analysis
labkit-audit experiments/01-compute-hrv --findings
labkit-audit experiments/01-compute-hrv --decide <N> fixed "<Änderung und Diagnose>" --record <neues_record>
protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --from-run <run_id>
protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md "Conclusion=<Satz>"
protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --into REPORT.md
report-check experiments/01-compute-hrv
```
Falls der Detektor nicht korrigierbar ist: `protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --handover --why "<Blocker>" --tried "<Versuche>" --into REPORT.md`.

**(d) Nicht tun**
- Die Zahlen 98.09 und 186.78 nicht berichten, nicht im Commit, nicht in pred_results.
- Kein erneutes deferred ohne neue Evidenz; kein --effect stands.
- Keine Begründung wie "100 Hz" ohne Zeitstempel-Beleg (Review hat das abgelehnt).
- Nichts von Hand am Audit-Record ändern; kein --no-verify.

**(e) Ausgabedatei**
pred_results/hrv.csv jetzt entfernen (BLOCKER nicht behoben; Anl. Z. 40–45). Nach einem fixierten Lauf aus dessen Ausgabe neu kopieren; sonst fehlt sie und der Report sagt es.

**Unsicher / Widersprüche**
- Ob die Zahlen aus Lauf 4fb9 stammen, ist unklar; Fälle Z. 160 sagt "no answer yet".
- Anl. Z. 201–202 verlangt bei abgelehnter Review "Entscheidung, Evidenz oder Aussage korrigieren", nicht erneut zu zeichnen; der Befehl zum Review ist laut Z. 165 nur eine Frage an einen zweiten Auditor.
- Ob fehlende Frage im Erstcommit zur ungültigen Registrierung zählt, ist nicht festgelegt.

Hinweis zum Protokoll allgemein: Anl. Z. 258 verlangt, zuerst die Ursache zu benennen, bevor etwas geändert wird; das habe ich bei jeder Situation vorangestellt.
