Gelesen: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading-3/instructions.md (333 Zeilen) und /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading-3/cases.md. Verweise unten: "instructions Z. n" bzw. "cases Z. n" meinen diese beiden Dateien. Es wurde nichts geschrieben und kein anderes Werkzeug benutzt.

## T1: Computation-Area hrv ist gerade angelegt

**(a) Was die Ausgabe verlangt.** Zuerst die Art prüfen (kind): Ist es ein fit oder ein apply? Dann das Protokoll PROTOCOL-hrv.md für repeat_cost low und kind compute ausfüllen, ohne Kriterium und ohne Promise-Tabelle. Danach scripts/01_measure.py mit expected_ids(), rows() und evaluate_rows() schreiben und mit tests/test_01_hrv.py an handgeprüften Fällen testen. Dann committen und die Messung im Vordergrund starten; sie ist zugleich der Instrumententest. Nach dem Lauf: finalize, Analyse-Audit, Conclusion, und protocol-fill --from-run adoptiert die Zahl. Die Ausgabedatei pred_results/hrv.csv entsteht erst aus diesem adoptierten Lauf (T1-Ausgabe Schritt 6). Ein Freeze oder ein Audit vor dem Lauf ist bei low nicht verlangt (instructions Z. 146).

**(b) Was ich vor dem nächsten Commit festlege.** Quelle: "eigen" = meine Entscheidung, "Werkzeug" = vom Tool vorgegeben.

| Feld / Einstellung | Wert | eigen oder Werkzeug |
|---|---|---|
| kind | compute (bleibt, wie gestempelt) | eigen: ich beantworte die zwei Fragen der Ausgabe. Frage 1 (Modell oder Verfahren trainiert, angepasst oder gewählt?) ist nein, denn RMSSD ist eine feste Formel ohne gewählte Schwelle. Frage 2 (Vorhersagen gegen Gold-Labels bewertet?) ist nein. Also compute. |
| repeat_cost | low | eigen, gesetzt beim Anlegen mit `labkit-init` |
| type (Kopf) | confirmatory oder exploratory | eigen; Begriffe in instructions Z. 52–54, Wahl offen (siehe Unklarheit 1) |
| Terms of this protocol | RMSSD-Definition, RR-Intervall, Begriffe der Aufnahme | eigen (instructions Z. 109–110) |
| Question / hypothesis | Eine Frage zur RMSSD von data/ecg.csv | eigen, geprüft vom Werkzeug |
| Data / scope | data/ecg.csv, Zeitraum | eigen |
| Exclusions / filters | Umgang mit Artefakten | eigen |
| Unit | ms, falls RR in ms vorliegen | eigen |
| criterion, admissibility, null condition, promise table | nicht verlangt | Werkzeug (T1-Contract Z. 40–43) |
| Model, Prompt, Data profile, Raw output | nicht verlangt (kein [model]) | Werkzeug |
| Recorded results, Conclusion | erst nach dem Lauf | Werkzeug (instructions Z. 93–95) |
| expected_ids(), rows(), evaluate_rows() | meine Implementierung | eigen |
| tests/test_01_hrv.py | handgeprüfte Fälle | eigen |
| Commit-Inhalt | Protokoll, Skripte, Test, Eingabe; nur die Pfade der Area | eigen bei den Pfaden; Pflichtfelder: Werkzeug (Pre-commit-Hook) |
| run_kind, run_id | Lauf-Stempel | Werkzeug |

**(c) Befehle in Reihenfolge bis zur ersten vollen Messung.**
1. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract` (die Ausgabe ist schon gelesen) und `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list`, um die offenen Felder zu sehen (instructions Z. 93).
2. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md "type=…"`, dann Terms, Question, Data, Exclusions und Unit je über ihr Label mit `protocol-fill <PROTOCOL> "<Label>" "<Wert>"` (T1-Contract Z. 41).
3. `protocol-check … --contract` erneut, bis nichts mehr offen ist.
4. scripts/01_measure.py schreiben; nach jeder Änderung `code-check experiments/01-hrv` (instructions Z. 121).
5. `.venv/bin/python -m pytest -q` mit tests/test_01_hrv.py an den handgeprüften Fällen (instructions Z. 121–122, 322).
6. `git add` nur die Pfade der Area und die Eingabe, dann `git commit`; der Hook prüft die Pflichtfelder.
7. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund. Das ist die erste volle Messung.
Dazwischen kein `--show` und kein `--probe`, denn compute hat beides nicht (instructions Z. 118–119, 134–136).

**(d) Was ich nicht tue, und warum.**
- Kein `labkit-init … --change-kind`: die Frage 1 ist nein, also bleibt compute.
- Kein `--show`, kein `--probe`: compute hat sie nicht; bei low gibt es keine separate Probe (instructions Z. 134–136).
- Kein Preflight, kein `frozen = true`, kein Preflight-Audit: bei low nicht geschuldet (instructions Z. 146).
- Kein Analyse-Audit vor dem Lauf: er kommt nach `finalize` (instructions Z. 161–162).
- Keine Recorded results und keine Conclusion vor dem Lauf (instructions Z. 93–95).
- Keine Datei pred_results/hrv.csv aus eigener Rechnung. Sie wird erst aus dem adoptierten Lauf geschrieben (instructions Z. 35–44; T1-Ausgabe Schritt 6).
- Keine Zahl als Erfolg werten. Compute hat keine Schwelle; der Messwert ist Beschreibung (instructions Z. 185).
- Kein `--no-verify`, kein Editieren von Run- oder Audit-Records (instructions Z. 316).

## T4: Messung abgelehnt, Registrierung fehlt

**(a) Was die Ausgabe verlangt.** Der Lauf wurde verweigert, weil die Registrierung nicht geschrieben ist: Frage/Hypothese fehlt, und der Commit braucht laut Ausgabe weitere Felder. Bei low friert nichts ein. Ich schreibe und committe die Registrierung und starte den Lauf dann neu. Ein Probelauf (run_kind='probe') oder LABKIT_UNFROZEN=1 liefert keine berichtbare Zahl; report-check weist sie zurück.

**(b) Was ich vor dem nächsten Commit festlege.**

| Feld / Einstellung | Wert | eigen oder Werkzeug |
|---|---|---|
| Question / hypothesis | eigener Satz, die Frage zur RMSSD | eigen; das Werkzeug prüft nur, dass er da ist |
| Terms, Data / scope, Exclusions, Unit | eigene Angaben | eigen; Pflicht laut instructions Z. 97 und T1-Contract Z. 40, siehe Unklarheit 2 |
| type | confirmatory oder exploratory | eigen (siehe Unklarheit 1) |
| criterion, admissibility, null condition | nicht verlangt | Werkzeug (Ausgabe: "a computation its question") |
| Code und Skripte | eigene Implementierung, mitcommittet | eigen; Commit-Pflicht laut instructions Z. 148 und Quelle im Git laut T1-Contract |
| run_kind, LABKIT_UNFROZEN | nicht gesetzt | nicht meine Wahl; beides ist hier ausgeschlossen |

**(c) Befehle in Reihenfolge bis zur ersten vollen Messung.**
1. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract` und `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list`, um die offenen Felder zu sehen.
2. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md "Question / hypothesis" "<Wert>"`, dann Terms, Data / scope, Exclusions und Unit je über ihr Label, und `"type=…"`.
3. `protocol-check … --contract` erneut, bis nichts offen ist.
4. Falls der Code noch nicht committet ist: `code-check experiments/01-hrv` und `.venv/bin/python -m pytest -q`.
5. `git add` nur die Pfade der Area, dann `git commit`.
6. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund neu starten. Das ist dieselbe Mess-Kommando wie in T1; die erste volle Messung.

**(d) Was ich nicht tue, und warum.**
- Kein Probelauf und kein `LABKIT_UNFROZEN=1`, um die Sperre zu umgehen. Ihre Zahlen werden nicht berichtet (T4-Ausgabe Z. 59).
- Kein `--no-verify`, kein Editieren der Records (instructions Z. 316).
- Kein `frozen = true` und kein Preflight-Audit: bei low nicht geschuldet.
- Keine Datei pred_results/hrv.csv aus dem verweigerten Lauf. Falls er eine geschrieben hat, entferne ich sie; sie bleibt weg, bis ein Lauf adoptiert ist (instructions Z. 40–44).
- Keine After-run-Felder ausfüllen, bevor der Lauf da ist (instructions Z. 93–95).

## Unklarheiten und Widersprüche (offene Punkte, nummeriert)

1. **type bei einer Berechnung.** instructions Z. 52–54 definiert confirmatory als Prüfung einer vor den Ergebnissen festgelegten Frage und Kriteriums und exploratory als Erkundung. Eine Berechnung hat aber kein Kriterium (instructions Z. 80–81). Keiner der beiden Begriffe passt damit eindeutig. Das Tool gibt keinen Wert vor. Das ist eine Entscheidung, die du treffen musst.
2. **Welche Felder der Commit braucht.** T4-Ausgabe nennt für ein Computation nur "its question". T1-Contract Z. 40 und instructions Z. 97 verlangen zusätzlich Terms, Data, Exclusions und Unit. Ich fülle alle fünf vor dem Commit, weil die beiden Pässe sonst widersprüchlich sind.
3. **runlog oder direkter Aufruf.** instructions Z. 148–150 sagen beides: "measure with the stamped script through runlog" und bei low "run .venv/bin/python … in the foreground". T4-Ausgabe zeigt, dass das Skript selbst runlog nutzt. Ich rufe das Skript direkt auf. Das ist kein echter Widerspruch.
4. **Ort der Eingabe.** instructions Z. 148 verlangt, die Eingaben mitzucommitten. Z. 327 sagt nur, vorbereitete Daten seien read-only. Wo data/ecg.csv liegen soll, sagt keiner der beiden Texte.
5. **Ausgabe des verweigerten Laufs.** T4 sagt, du hast das Skript ausgeführt. Ob es schon eine Ergebnisdatei geschrieben hat, steht nicht da. instructions Z. 40–44 sagt nur, dass Ausgaben bis zur Adoption wegbleiben.
