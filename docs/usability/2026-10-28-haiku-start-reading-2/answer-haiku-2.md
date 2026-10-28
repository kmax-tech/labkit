Gelesen: instructions.md vollständig, dann cases.md. Nur Read auf die beiden Dateien. Die Pfade stehen in der Aufgabe; Zeilenangaben beziehen sich auf instructions.md (kurz „Z.“) bzw. cases.md.

## T1 — computation-Bereich (RMSSD)

(a) Das Tool verlangt: Art prüfen (fit, apply oder compute), dann den Low-Schnitt des Protokolls füllen (type, Terms, Frage, Daten, Ausschlüsse, Unit), ohne Kriterium und ohne Promise-Tabelle. Dann den Code (expected_ids, rows, evaluate_rows) schreiben und testen, committen, das Skript im Vordergrund laufen lassen, danach finalize, Analyse-Audit, Conclusion und `protocol-fill --from-run`. Die Datei pred_results/hrv.csv entsteht erst aus dem adoptierten Lauf.

(b)
- kind = compute: mein Entscheid. RMSSD trainiert und wählt kein Modell. Wenn ich aber eine Schwelle (etwa für die R-Zacken-Erkennung) am Datensatz abstimme, ist das nach dem Tool-Text ein fit (siehe U7).
- repeat_cost = low: mein Entscheid, weil die Messung beliebig wiederholbar ist (Z. 53).
- type: mein Entscheid (exploratory oder confirmatory). Das Schreiben eines Typs begründet keine Gültigkeit (Z. 54).
- Terms, Question, Data/scope, Exclusions, Unit: mein Entscheid.
- Conclusion: mein Entscheid, vor der Adoption zu schreiben.
- Recorded results: Tool, durch `protocol-fill --from-run`.
- stamp, script, frozen = false, preflight_audit leer: Tool. Bei low gibt es kein Freeze und keinen Preflight-Audit.
- Kein Kriterium, keine Admissibility, keine Null-Bedingung, kein [model]: Vorgabe des Contracts (cases Z. 44).
- Code und Tests: mein Entscheid.

(c)
1. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract` und `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list`.
2. `protocol-fill` für type, Terms, Question, Data, Exclusions und Unit (Schreibweise siehe U1).
3. scripts/01_measure.py implementieren, dann `code-check experiments/01-hrv`, dann `.venv/bin/python -m pytest -q` mit tests/test_01_hrv.py auf Handfällen.
4. `git add <Pfade>` für Protokoll, Skript, Test und data/ecg.csv (siehe U10), dann `git commit`.
5. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund. Das ist die erste volle Messung und zugleich die Instrumentenprüfung.

(d) Ich tue nicht:
- kein Freeze, kein preflight_audit, kein `--probe`. Bei low entfällt beides (Z. 134–136, 145–146), `--probe` gibt es für compute nicht (Z. 135).
- kein `--show` (Z. 117–119, compute hat keines).
- kein `runlog start` bei low (Z. 149–150).
- keine Datei pred_results/hrv.csv vor dem adoptierten Lauf (Z. 40–46).
- keine Zahl abtippen, kein Analyse-Audit vor `finalize`.
- kein Kriterium und keine Promise-Tabelle erfinden (cases Z. 28–30).

## T2 — fit-Bereich (assay)

(a) Das Tool verlangt: Low-Schnitt mit Kriterium, Admissibility, Null-Bedingung und [[promise]]-Konstanten. Dann 00_prepare.py (Labels der unbeschrifteten Zeilen auf null), in 01_measure.py make_estimator(), SCORE und FEATURES_FIELD, `--show 3`, Code-Check, Test, Commit, Vordergrundlauf, finalize, Audit, Conclusion und Adoption.

(b)
- kind = fit: Befehl und mein Entscheid stimmen überein, weil ein Klassifikator trainiert wird (Z. 56–61).
- repeat_cost = low und type: mein Entscheid.
- Terms, Question, Data/scope, Exclusions, Unit: mein Entscheid.
- C1-Satz und Konstante margin: der Satz ist mein Entscheid. Der Wert 0.25 ist nur das Beispiel des Stamps und ich setze ihn selbst vor dem Commit (cases Z. 59, 132–137).
- A1-Satz und max_empty: der Satz ist mein Entscheid. Der Wert 0 ist ein Beispiel.
- A2-Satz und null_band: der Satz ist mein Entscheid. Der Wert 0.1 ist ein Beispiel. Die Formulierung „chance_of()“ ist unklar (U3).
- Promise-IDs C1, A1, A2 und die Schlüssel c1_pass, a1_pass, a2_pass: Vorgabe des Tools.
- make_estimator(), SCORE, FEATURES_FIELD: mein Entscheid.
- 00_prepare.py (Aufteilung, Nullung der Labels): mein Entscheid. Danach sind die Daten in data/prepared/ read-only.
- Data profile und Modellteil: nicht fällig, es gibt kein [model].
- Recorded results: Tool, bei `--from-run`.

(c)
1. `protocol-check experiments/01-assay/PROTOCOL-assay.md --contract` und `protocol-fill … --list`.
2. `protocol-fill` für type, Terms, Question, Data, Exclusions, Unit, Success/failure criterion (C1), Admissibility (A1) und Null-Bedingung (A2) (Schreibweise siehe U1).
3. Die Konstanten in den [[promise]]-Blöcken von Hand setzen, den Satz `sentence` ebenfalls (siehe U2).
4. scripts/00_prepare.py schreiben und ausführen (raw nach data/prepared/).
5. scripts/01_measure.py füllen: make_estimator(), SCORE, FEATURES_FIELD. Dann `.venv/bin/python experiments/01-assay/scripts/01_measure.py --show 3`.
6. `code-check experiments/01-assay` und `.venv/bin/python -m pytest -q` mit tests/test_01_assay.py.
7. `protocol-check … --contract` erneut.
8. `git add <Pfade>` für Protokoll, Skripte, Test, data/prepared und data/assay.csv, dann `git commit`.
9. `.venv/bin/python experiments/01-assay/scripts/01_measure.py` im Vordergrund. Das ist die erste volle Messung.

(d) Ich tue nicht:
- kein `--probe` (Z. 135–136), kein Freeze, kein Preflight-Audit.
- keine Änderung von margin, SCORE oder Features nach Sicht auf Ergebnisse (Z. 111–113). Ein verfehltes Kriterium wird berichtet, nicht durch Senken der Marge repariert (Z. 274–276).
- keine Stamp-Zahlen ungeprüft übernehmen.
- keine Labels in den Features und kein Ändern von data/prepared/.
- keine pred_results/assay_pred.csv vor der Adoption.
- kein `runlog start` bei low.

## T3 — erster Commit nach dem Stamp wird abgelehnt

(a) Der Hook verlangt, dass die Pflichtfelder type, Terms, Question, Data, Exclusions und Unit ausgefüllt oder mit „n/a — <Grund>“ begründet werden. Der Runs-Eintrag kommt erst über `--from-run`. Der Commit ist nicht zustande gekommen.

(b)
- type: mein Entscheid, gesetzt über `protocol-fill … "type=…"` (Z. 107).
- Terms, Question, Data, Exclusions, Unit: mein Entscheid. Ein „n/a — <Grund>“ nur bei einem echten Grund (U8).
- Runs-Eintrag: Tool, nicht von Hand.
- frozen und preflight_audit: Tool-Vorgabe, bleiben bei false beziehungsweise leer.
- Was im Commit steht: mein Entscheid. Das `git add -A` hat möglicherweise Fremdes gestaged (U9).

(c)
1. `git status` und prüfen, was `-A` gestaged hat. Fremdes nicht mitcommitten (kein Kommando dafür in den beiden Dateien, siehe U9).
2. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list`.
3. `protocol-fill` für type und die fünf Felder.
4. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract`.
5. `git add <Pfade>` für das Protokoll (und Skripte, falls geändert), dann `git commit`.

(d) Ich tue nicht:
- kein `--no-verify` (Z. 315–316).
- keinen Runs-Eintrag von Hand.
- keine Platzhalter committen und keinen pauschalen „n/a“, nur um den Hook zu passieren.
- keinen Lauf vor dem Commit.

## T4 — Messung abgelehnt: Registrierung fehlt

(a) runlog verweigert den Lauf, weil die Registrierung fehlt, hier Question / hypothesis. Bei low friert nichts ein. Ich schreibe und committe die Registrierung und starte den Lauf dann neu. Probe und `LABKIT_UNFROZEN=1` liefern keine meldbare Zahl; report-check verweigert sie.

(b)
- Question / hypothesis: mein Entscheid.
- Die übrigen Felder (type, Terms, Data, Exclusions, Unit): mein Entscheid. Ob sie hier fällig sind, ist unklar (U4).
- Commit-Inhalt: mein Entscheid.
- Neustart: dasselbe Messkommando (Z. 154).

(c)
1. `protocol-check … --contract` und `protocol-fill … --list`. Nicht nur das genannte Feld prüfen.
2. `protocol-fill` für Question / hypothesis und alle weiteren offenen Felder.
3. `protocol-check` erneut, bis es passt.
4. `code-check experiments/01-hrv` und `.venv/bin/python -m pytest -q`. Die Ausgabe nennt diesen Schritt nicht, er ist aber nach Code-Änderungen vorgeschrieben (Z. 121).
5. `git add <Pfade>`, dann `git commit`.
6. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund.

(d) Ich tue nicht:
- keinen Probe-Lauf (run_kind='probe') als Ersatz für die Zahl.
- kein `LABKIT_UNFROZEN=1`.
- keine Zahl aus dem abgelehnten Lauf übernehmen und keine Ausgabedatei schreiben.
- keinen Lauf vor dem Commit.
- keinen Art-Wechsel als Umweg.

## T5 — Messung abgelehnt: Protokoll nicht committet

(a) Protokoll und Skript sind nicht committet. Der erste Lauf wird an dem Stand gemessen, den sein Commit enthält. Also committen, dann Lauf.

(b)
- Commit-Inhalt und Commit-Nachricht: mein Entscheid. Dazu gehören Protokoll, scripts/01_measure.py, der Test und die Eingabe data/ecg.csv (U10).
- Die Registrierung ist mit dem Commit festgeschrieben: mein Entscheid, danach nicht mehr ändern (Z. 111–113).
- Das Gate des Laufs: Tool.

(c)
1. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract` (passt laut Ausgabe).
2. Falls der Code seit dem letzten Check geändert wurde: `code-check experiments/01-hrv` und `.venv/bin/python -m pytest -q`.
3. `git add <Pfade>` für Protokoll, Skript, Test und data/ecg.csv, dann `git commit`.
4. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund.

(d) Ich tue nicht:
- kein `LABKIT_UNFROZEN=1` und keinen Probe-Lauf.
- kein `--no-verify`.
- keinen Lauf vor dem Commit.
- keine Registrierung nach dem Commit ändern, um sie an die Messung anzupassen.
- keine Ausgabedatei vor der Adoption.

## Unklare Stellen (Nummern für Rückfragen)

- U1. Schreibweise von `protocol-fill`: instructions.md Z. 107 nutzt `"<Label>=<value>"` in einem Argument. cases.md Z. 41 und Z. 159 nutzen `"<label>" "<value>"` mit zwei Argumenten. Beides steht in den Quellen, ich weiß nicht sicher, welche Form gilt.
- U2. Promise-Sätze: instructions.md Z. 107 nennt `"C1 sentence=<value>"`, cases.md Z. 132–151 zeigt `sentence = "<…>"` in der TOML-Tabelle. instructions.md Z. 25–27 sagt, dass die TOML-Kopf von Hand gesetzt wird. Unklar, ob der Satz per `protocol-fill` oder von Hand kommt.
- U3. `chance_of()` und `null_band` stehen im Null-Bedingungstext des Stamps (cases.md Z. 91). Keine der beiden Dateien definiert sie oder sagt, woher sie kommen.
- U4. In T4 nennt das Gate nur „Question / hypothesis“, obwohl das Protokoll laut Situation noch wie gestampt ist. T3 hatte type, Terms, Data, Exclusions und Unit als fehlend gemeldet. Ich kann nicht sicher sagen, ob diese Felder bei low fällig sind. Dafür ist `protocol-check --contract` die Quelle, nicht die eine genannte Zeile.
- U5. Die Liste „vor dem vollen Lauf“ im Contract (cases.md Z. 163) nennt Data, Exclusions und Unit nicht, die Liste „schuldet“ (Z. 158) schon. Ich fülle sie trotzdem.
- U6. instructions.md Z. 149 sagt „measure … through runlog“, Z. 150 sagt bei low direkt `.venv/bin/python …/01_measure.py` im Vordergrund. Ich lese das so, dass bei low das Skript direkt läuft und runlog es nur prüft (vgl. cases.md Z. 196ff.).
- U7. cases.md Z. 28 zählt „a threshold or prompt chosen on performance data“ als fit. Bei T1 mit unbeschrifteten Daten ist unklar, ob das Abstimmen einer Erkennungsschwelle am eigenen Signal schon „performance data“ ist. instructions.md Z. 56–57 spricht allgemein von „adjust or select a procedure“. Die Grenze ist nicht scharf.
- U8. Der Hook in T3 (cases.md Z. 183–186) erlaubt „n/a — <Grund>“. Keine der beiden Dateien erwähnt diese Begründungsform.
- U9. T3 hat `git add -A` benutzt. Keine der beiden Dateien nennt eine Staging-Regel oder ein Kommando, um Fremdes wieder aus dem Index zu nehmen.
- U10. Die Eingabe data/ecg.csv kommt in keinem Hook vor. instructions.md Z. 148 verlangt „inputs“ zu committen, und das Finalisieren verlangt „source … tracked in git“ (cases.md Z. 46, 164). Das ist abgeleitet, nicht ausdrücklich genannt.

Es wurden keine Dateien geschrieben und keine Befehle ausgeführt.
