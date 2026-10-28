Lesebericht: Start-Fälle T1 bis T5 (2026-10-28)

Gelesen: instructions.md und cases.md vollständig, sonst nichts. Begriffe: fit = das Modell oder Verfahren wird hier trainiert, angepasst oder ausgewählt; apply = ein unverändertes Modell wird an Labels bewertet; compute = eine Größe wird berechnet, ohne Vorhersagen zu bewerten. Die Befehle stehen ohne `.venv/bin/`-Präfix; wo nicht im PATH, ist es voranzustellen (instructions.md, Z. 5).

## T1: compute-Bereich (RMSSD aus data/ecg.csv)

(a) Der Output verlangt zuerst die Prüfung der Art. Trainiert oder wählt die Fläche ein Modell oder Verfahren? Nein, RMSSD ist eine feste Formel. Bewertet die Zahl eine Vorhersage gegen Labels? Nein. Also bleibt kind = compute. Danach: Registrierung im Low-Schnitt, Code und Test, Commit, Lauf im Vordergrund, finalize, Analyse-Audit, Conclusion, Adoption mit --from-run. Erst aus diesem Lauf wird pred_results/hrv.csv geschrieben.

(b) Vor dem nächsten Commit:
- kind = compute: meine Entscheidung (beim Stempeln gesetzt, geprüft).
- repeat_cost = low: meine Entscheidung (beim Stempeln).
- type in der Kopfzeile: meine Entscheidung. Das Werkzeug prüft nur, dass er gesetzt ist. Ich würde confirmatory wählen, weil die Methode vor dem Ergebnis feststeht, aber das ist meine Setzung.
- Terms, Question / hypothesis, Data / scope, Exclusions / filters, Unit: meine Texte, per protocol-fill.
- Kein Kriterium, keine Zulassungsbedingung, keine Promise-Tabelle: vom Werkzeug so vorgegeben, weil Compute keinen Maßstab hat.
- Feldnamen und Pflichtliste: Werkzeug (protocol-check --contract).
- Code in scripts/01_measure.py (expected_ids, rows, evaluate_rows) und tests/test_01_hrv.py: meine Implementierung.
- Commit-Message und Commit-Pfade: meine Entscheidung.
- Recorded results, Conclusion, run_id: erst nach dem Lauf, vom Werkzeug erzeugt.

(c) Reihenfolge bis zur ersten vollen Messung:
1. protocol-fill PROTOCOL-hrv.md --list und protocol-check PROTOCOL-hrv.md --contract
2. protocol-fill für type, Terms, Question, Data, Exclusions, Unit
3. protocol-check --contract erneut, bis keine Lücke bleibt
4. Code schreiben, dann code-check experiments/01-hrv
5. Test in tests/test_01_hrv.py mit handgeprüften Fällen (.venv/bin/python -m pytest -q)
6. Commit mit benannten Pfaden (Protokoll, Script, Test)
7. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund (zugleich Instrumentenprüfung)

(d) Nicht:
- kein --show und kein --probe: beides gibt es für Compute nicht (instructions.md, Z. 118-119, 134-135).
- kein --change-kind auf fit: es gibt keine Trainings- oder Auswahlstufe.
- kein erfundenes Kriterium: Compute hat keinen Bar.
- pred_results/hrv.csv nicht selbst rechnen oder abtippen, sondern erst aus dem adoptierten Lauf.
- kein finalize und keine Adoption vor dem Commit.
- kein --no-verify.

## T2: fit-Bereich (Klassifikator für assay)

(a) Ein Klassifikator wird auf gelabelten Assay-Verbindungen trainiert, die unbeschrifteten werden vorhergesagt, pred_results/assay_pred.csv ist die Ausgabe. Vor dem Lauf fülle ich Kriterium, Zulassungsbedingung, Null-Bedingung und die Promise-Konstanten, bereite die Daten vor, schreibe den Schätzer und committe. Erst dann läuft die Messung.

(b) Bereits gesetzt, und von wem:
- Werkzeug: standard, id, frozen = false, preflight_audit = "" (Kopf); die Promise-IDs C1, A1, A2 mit keys und scope; die Modell-Zeile "n/a — no model call" (vorgefüllt, nur prüfen, ob sie stimmt).
- Mein Aufruf: repeat_cost = low und kind = fit (beim Stempeln).
- Stempel-Beispiele: margin = 0.25, max_empty = 0, null_band = 0.1. Ich muss sie nach dem Satz setzen, nicht nach dem Beispiel.
- Meine Eingaben: type; Terms; Question; der C1-Satz mit margin; der A1-Satz mit max_empty; der A2-Satz (Null-Bedingung) mit null_band; Data / scope; Exclusions; Unit.
- Offen, nicht aus den Quellen bestimmbar: die Zahlen margin, null_band und max_empty. Das ist eine Forschungsentscheidung, sie muss vor dem Commit feststehen.
- Nach dem Lauf: Conclusion (meine Formulierung), Recorded results und run_id (Werkzeug).

(c) Reihenfolge bis zur ersten vollen Messung:
1. protocol-fill PROTOCOL-assay.md --list und protocol-check --contract
2. protocol-fill für type, Terms, Question, C1, A1, A2, Data, Exclusions, Unit; die Promise-Konstanten im TOML-Kopf von Hand setzen
3. protocol-check --contract erneut
4. .venv/bin/python experiments/01-assay/scripts/00_prepare.py (erzeugt data/prepared/, Gold null für den unbeschrifteten Split)
5. make_estimator(), SCORE, FEATURES_FIELD in 01_measure.py füllen
6. .venv/bin/python experiments/01-assay/scripts/01_measure.py --show 3 lesen, kein Aufruf des Modells
7. code-check experiments/01-assay nach Änderungen; Tests mit handgeprüften Fällen
8. Commit mit benannten Pfaden: Protokoll, Scripts, Tests, data/prepared
9. .venv/bin/python experiments/01-assay/scripts/01_measure.py im Vordergrund

(d) Nicht:
- keine Konstanten nach Sicht der Daten wählen oder aus Ergebnissen ableiten.
- kein --audit bei 00_prepare: das gibt es nur bei Prompt-Skeletten mit [model] (instructions.md, Z. 124-127).
- kein --probe: bei low gibt es keine eigene Probe (Z. 134-136); ein Probelauf erzeugt eine nicht berichtbare Zahl.
- data/prepared nicht nachträglich editieren, es ist read-only.
- frozen = true nicht setzen: bei low wird nichts eingefroren.
- das Kriterium nach dem Ergebnis nicht lockern.
- keine Zahl ins Protokoll, bevor die Adoption erfolgt ist.

## T3: der erste Commit nach dem Stempeln wird abgelehnt

(a) Der Hook verlangt, dass [protocol] type, Terms, Question, Data / scope, Exclusions und Unit gefüllt sind oder als "<Feld>: n/a — <Grund>" begründet werden. Die Zeile zu Runs ist nur ein Hinweis, kein Pflichtfeld: der Eintrag entsteht mit --from-run nach dem Lauf.

(b) Meine Entscheidung: type (exploratory oder confirmatory) und die fünf Texte, oder eine begründete n/a-Zeile. Ich würde n/a nur bei Exclusions verwenden, wenn wirklich nichts ausgeschlossen wird, und dann mit Grund. Werkzeug: die Liste der Pflichtfelder und die Zeilennummern. Die Runs-Zeile ist nicht meine.

(c) Reihenfolge:
1. protocol-fill PROTOCOL-hrv.md für type, Terms, Question, Data, Exclusions, Unit
2. protocol-check PROTOCOL-hrv.md --contract
3. Benannte Pfade stagen (Protokoll und die anderen Stempel-Dateien des Bereichs), dann committen. Der Hook prüft erneut.

(d) Nicht:
- kein --no-verify.
- kein git add -A: fremde oder nicht zu diesem Bereich gehörende Dateien bleiben draußen.
- den Runs-Eintrag nicht von Hand schreiben.
- kein n/a ohne Begründung.

## T4: Messung abgelehnt, Registrierung fehlt

(a) Der Lauf wird abgelehnt, weil bei repeat_cost = low die Registrierung fehlt. Für Compute ist das die Frage (Question / hypothesis). Ein Freeze spielt bei low keine Rolle. Ich soll die Registrierung schreiben, committen und dann neu starten. Die Wege über Probe-Läufe und LABKIT_UNFROZEN=1 sind dort als Nicht-Wege genannt.

(b) Meine Entscheidung: der Fragetext und der Commit. Ich fülle auch Terms, Data, Exclusions, Unit, weil protocol-check --contract sie auch für Low verlangt. Werkzeug: die Pflichtliste, die Ablehnung und die Schreibweise der Felder.

(c) Reihenfolge:
1. protocol-fill PROTOCOL-hrv.md "Question / hypothesis" und die übrigen fehlenden Felder
2. protocol-check --contract, bis es passt
3. code-check experiments/01-hrv und die Bereichstests
4. Commit von Protokoll und Script (Details in T5)
5. Lauf neu im Vordergrund

(d) Nicht:
- kein LABKIT_UNFROZEN=1: das ist nur bei high und nach einem fehlgeschlagenen Audit vorgesehen, und die Zahl würde von report-check abgelehnt.
- kein run_kind=probe, um an eine Zahl zu kommen.
- kein frozen = true bei low.
- die Frage nicht nach der Messung ändern.

Abweichung: T4 nennt nur die Frage als fehlend, T3 und protocol-check --contract nennen fünf Felder. Ich folge dem umfassenderen Stand.

## T5: Protokoll nicht committet

(a) Das Protokoll ist nicht committet, und die erste Messung ist an den Stand des Commits gebunden. Ich soll committen und dann den Lauf neu starten.

(b) Meine Entscheidung: die Commit-Pfade (Protokoll, scripts/01_measure.py, tests/test_01_hrv.py) und die Commit-Message auf Englisch. Werkzeug: die Pflicht, dass der Commit vor dem Lauf steht. Ab dem Commit gilt die Registrierung; spätere Änderungen an der Frage brauchen einen neuen Commit und einen neuen Lauf.

(c) Reihenfolge:
1. git status für experiments/01-hrv prüfen
2. git add mit benannten Pfaden, dann git commit
3. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund

(d) Nicht:
- kein LABKIT_UNFROZEN=1 und kein Probelauf als Ersatz.
- kein git add -A.
- kein --no-verify.
- das Protokoll nach dem Commit nicht stillschweigend ändern.

## Offene Punkte

1. T2: Zahlen margin, null_band und max_empty festlegen (Forschungsentscheidung).
2. T1: type festlegen (confirmatory oder exploratory).
3. T3 und T4: Die Pflichtlisten unterscheiden sich (nur Frage bei T4, fünf Felder bei T3). Ich folge dem umfassenderen Stand.
4. T3: Unklar, ob n/a für Question vom Hook akzeptiert würde; die Registrierung verlangt die Frage in jedem Fall.
5. T2: Die vorgefüllte Modell-Zeile "n/a" muss zum Protokoll passen; das prüfe ich, übernehme sie nicht blind.
