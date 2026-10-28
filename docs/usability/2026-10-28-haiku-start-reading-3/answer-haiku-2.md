Gelesen: instructions.md (333 Zeilen) und cases.md vollständig. Keine weitere Datei, kein Befehl.

## Situation T1: Berechnungsbereich hrv (RMSSD), gestempelt mit --repeat-cost low --kind compute

**(a) Was die Ausgabe verlangt**
RMSSD (Wurzel aus dem Mittel der quadrierten Abstände aufeinanderfolgender Herzschläge, ein HRV-Maß) aus data/ecg.csv berechnen und nach pred_results/hrv.csv schreiben. Vorher die Art prüfen (fit, apply oder compute). Dann Protokoll-Felder und Code füllen, committen, die erste volle Messung im Vordergrund laufen lassen (sie ist zugleich Instrumentenprüfung). Danach finalize, Analyse-Audit mit Entscheidungen, Schlusssatz (Conclusion) und Übernahme des Laufs per `--from-run`. Erst aus diesem übernommenen Lauf entsteht die CSV.
Die Art ist compute: RMSSD ist eine Berechnung, kein trainiertes oder gewähltes Modell, und sie urteilt keine Vorhersage (instructions.md:56-62). Kein `--change-kind`.

**(b) Was vor dem ersten Commit zu schreiben oder zu entscheiden ist**

| Feld / Einstellung | Wert | Wer entscheidet |
|---|---|---|
| kind | compute | gesetzt bei labkit-init, Prüfung oben |
| repeat_cost | low | gesetzt bei labkit-init |
| type (Kopf) | confirmatory oder exploratory; Vorschlag confirmatory, weil Definition und Ausschlüsse vor dem Ergebnis stehen. Der Typ ist eine Aussage über die Wissenschaft, kein Gütesiegel | ich |
| Terms of this protocol | RMSSD-Formel, Einheit, Umgang mit Artefakten | ich |
| Question / hypothesis | RMSSD von data/ecg.csv | ich |
| Data / scope | welche Aufzeichnung oder welche Segmente | ich |
| Exclusions / filters | Artefakt- und Ausreißerregel | ich |
| Unit | Einheit der CSV (vermutlich ms; die Quellen nennen keine) | ich |
| criterion, admissibility, null condition, Model/tool, Promise-Tabelle, Data profile, Prompt, Raw output | entfallen: Berechnungen haben keine Schwelle (cases.md:44, 47) | Werkzeug |
| Recorded results | nach dem Lauf, vom Werkzeug | Werkzeug |
| Conclusion | höchstens zwei Sätze, vor der Übernahme; beschreibt den Wert, ist keine Erfolgsbehauptung | ich |
| scripts/01_measure.py: expected_ids(), rows(), evaluate_rows(); tests/test_01_hrv.py | Implementierung und Testfälle | ich |
| Format von pred_results/hrv.csv (Spalten, Kopfzeile) | keine Quelle nennt es | Aufgabe (offen, siehe unten) |

**(c) Befehle in Reihenfolge bis zur ersten vollen Messung**
1. `.venv/bin/protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list` (instructions.md:93; `.venv/bin/`-Präfix, falls nicht im PATH)
2. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract` (instructions.md:93)
3. `protocol-fill` für type, Terms, Question, Data/scope, Exclusions und Unit (Syntax siehe offener Punkt 1)
4. Code schreiben; nach jeder Änderung `code-check experiments/01-hrv` (instructions.md:120)
5. Testlauf auf handgeprüften Fällen: `.venv/bin/python -m pytest -q` (instructions.md:322) bzw. tests/test_01_hrv.py
6. `git add <nur die eigenen Pfade>` (Protokoll, Skripte, Test, Eingaben), dann `git commit`; der Hook prüft die Pflichtfelder
7. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund (cases.md:32; instructions.md:148-150)

Danach folgen finalize, `labkit-audit experiments/01-hrv --mode analysis`, die Entscheidungen, die Conclusion, `protocol-fill ... --from-run <run_id>` und erst dann die CSV aus diesem Lauf.

**(d) Was ich nicht tue, und warum**
- Kein `--change-kind`, weil die Art compute ist.
- Kein `--show` und kein `--probe`: compute hat beides nicht; bei low ist die volle Messung die Instrumentenprüfung (instructions.md:118-119, 135-136).
- Kein Freeze, kein Preflight-Audit, kein `frozen = true`: bei low entfällt das (instructions.md:146).
- Keine Schwelle, keine Versprechen-Tabelle, keine Nullbedingung erfinden: eine Berechnung hat keine Schwelle (instructions.md:97-98).
- Keine Messung vor dem Commit (instructions.md:147-149).
- Die CSV nicht von Hand schreiben und nicht aus einem anderen Rechenweg füllen, nur aus dem übernommenen Lauf (instructions.md:36-46).
- Keine Zahl berichten, bevor der Analyse-Audit entschieden ist (instructions.md:161-162).
- Kein `--force` (nur nötig, wenn die Conclusion nach der Übernahme geändert wird), kein `--no-verify`, keine Eingriffe in Lauf- oder Audit-Protokolle (instructions.md:311-316).
- Kein `git add -A`.

**Offen oder widersprüchlich in T1**
1. Syntax von `protocol-fill`: instructions.md:107 und 189 nutzen ein Argument `"<Label>=<value>"`; cases.md:41 nutzt zwei Argumente `"<label>" "<value>"`. Ich würde die Form aus instructions.md:107 nehmen und die Abweichung klären.
2. `type`: cases.md:29 nennt es „in the head“; instructions.md:107 setzt es mit `protocol-fill "type=…"`. Die Quellen sagen nicht, ob von Hand oder per Befehl. instructions.md:26-27 erlaubt Handedits nur für die Freeze-Felder am Kopf, nicht ausdrücklich für type.
3. Eingabedaten: instructions.md:327 macht „prepared data“ read-only; die Quellen sagen nicht, ob data/ecg.csv Rohdaten oder vorbereitete Daten sind. Die Herkunftsprüfung verlangt, dass die Quelle im Lauf eingefroren und in git verfolgt ist (cases.md:46). Ob data/ecg.csv dazu schon in git liegt, ist unklar.
4. Pfad des Tests: Die Ausgabe nennt tests/test_01_hrv.py ohne Bereichspräfix; relativ zu welchem Verzeichnis, sagt sie nicht.
5. Format von pred_results/hrv.csv: keine Quelle nennt Spalten oder Kopfzeile. Die Aufgabe muss ich selbst gegen ihre Vorgaben prüfen (instructions.md:256-257).
6. REPORT.md: instructions.md:234-240 erzeugt Ergebnisblock und Bericht, die Aufgabe nennt nur die CSV. Ob ein Bericht geschuldet ist, ist offen.

## Situation T4: Messung abgewiesen, Registrierung nicht geschrieben

**(a) Was die Ausgabe verlangt**
Die Messung wurde abgewiesen (Exit 1). Im Protokoll fehlt die Registrierung: Question / hypothesis, und der Commit verlangt außerdem die weiteren Felder, die `protocol-check --contract` nennt. Bei low gibt es keinen Freeze. Also: Registrierung schreiben und committen, dann denselben Lauf erneut starten. Probe-Läufe und Läufe mit `LABKIT_UNFROZEN=1` liefern keine berichtbaren Zahlen (cases.md:57-59).
Vorher ist mir selbst ein Fehler unterlaufen: Ich habe den Lauf vor dem Commit gestartet. instructions.md:147-149 verlangt Commit, dann Messung. Die Abweisung hat das abgefangen; es entstand keine Zahl.

**(b) Was vor dem Commit zu schreiben oder zu entscheiden ist**
Dieselben Felder wie in T1 (type, Terms, Question, Data/scope, Exclusions, Unit), alle meine Entscheidung. Ebenfalls meine Entscheidung: Code, Test und Eingaben, die zusammen mit der Registrierung committet werden. Vom Werkzeug kommt, welche Felder der Commit verlangt (cases.md:41, 45). Schlusssatz und Recorded results entstehen erst nach dem Lauf.

**(c) Befehle in Reihenfolge bis zur ersten vollen Messung**
1. `.venv/bin/protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list`, um die offenen Felder zu sehen
2. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract`, um die Feldliste zu bestätigen
3. `protocol-fill` für type, Terms, Question, Data/scope, Exclusions, Unit; danach wieder `--list`
4. `code-check experiments/01-hrv` und `.venv/bin/python -m pytest -q`, falls der Code nach dem letzten Lauf geändert wurde (instructions.md:117-121)
5. `git add <nur die eigenen Pfade>`, dann `git commit`
6. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund, dieselbe Messung wie zuvor

**(d) Was ich nicht tue, und warum**
- Keine Probe (run_kind='probe') und kein `LABKIT_UNFROZEN=1`: beides wird als solches erfasst, und report-check verweigert seine Zahlen (cases.md:59).
- Kein Freeze, kein `frozen = true`, kein Preflight-Audit: bei low nicht geschuldet (instructions.md:146).
- Keine Messung vor dem Commit, auch nicht „zum Testen“; der frühere Versuch wird nicht wiederholt.
- Keine Zahl aus dem abgewiesenen Lauf in pred_results/hrv.csv oder in einen Bericht.
- Den abgewiesenen Versuch nicht löschen oder umschreiben; Belege bleiben (instructions.md:311-316).
- Kein `--no-verify`.
- Keine andere Art wählen und keine Schwelle nachtragen, um die Abweisung zu umgehen.

**Offen oder widersprüchlich in T4**
1. Die Abweisung sagt „the commit also owes the other fields“, nennt sie aber nicht. Die Liste kommt nur aus `protocol-check --contract` (cases.md:41-47) und stimmt mit instructions.md:97 überein.
2. Die Quellen sagen nicht, ob ein abgewiesener Lauf Spuren in runs/ hinterlässt und ob er aufbewahrt werden muss. instructions.md:311-316 verlangt, Belege zu erhalten; ob das für abgewiesene Läufe auch gilt, steht dort nicht ausdrücklich.

Quellen: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading-3/instructions.md und /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading-3/cases.md. Keine Datei geschrieben.
