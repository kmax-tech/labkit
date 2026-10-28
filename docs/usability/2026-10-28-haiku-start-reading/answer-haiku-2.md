Leseprobe, Antworten zu T1 bis T5. Quellen: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading/instructions.md (zitiert als instructions.md:Zeile) und /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading/cases.md (zitiert als cases.md:Zeile). Ich habe nur diese zwei Dateien mit Read gelesen.

Begriffe vorab: Stamp = das von labkit-init erzeugte Skelett (Protokoll, Skripte, Test). Registrierung = die Protokollfelder, die vor dem Lauf geschrieben und committet sein müssen. Freeze = `frozen = true` mit Preflight-Audit, bei repeat_cost "low" nicht geschuldet. Art (kind): fit = Modell trainieren oder auswählen; apply = unverändertes Modell gegen Labels beurteilen; compute = eine Größe berechnen.

## T1 (RMSSD, kind compute, repeat_cost low)

(a) Die Ausgabe verlangt zuerst die Prüfung der Art: trainiert oder wählt die Berechnung ein Modell oder Verfahren aus? Nein. Sagt die Zahl eine Vorhersage gegen Gold-Labels? Nein. Also bleibt compute, ein Wechsel entfällt. Danach Registrierung (Frage, Einheit, Daten, Ausschlüsse, Terms, type), Skripte (expected_ids, rows, evaluate_rows), Commit, Lauf im Vordergrund, dann finalize, Analyse-Audit und protocol-fill --from-run. Der Analyse-Audit vor dem Berichten gilt bei jeder Kostenstufe (instructions.md:161).

(b) Eigene Entscheidungen:
- type (exploratory oder confirmatory). Das Setzen des Typs belegt keine Gültigkeit (instructions.md:54).
- Terms of this protocol, Question / hypothesis, Data / scope (data/ecg.csv), Exclusions / filters, Unit (ein RMSSD je Aufnahme oder je Fenster).
- Inhalt von expected_ids(), rows(), evaluate_rows().
- kind = compute und repeat_cost = low: meine Wahl beim Stamp-Befehl, das Tool bestätigt sie nur.
Vom Tool gegeben: Skelettdateien, standard und id im Kopf, frozen = false und leerer preflight_audit (Freeze nicht geschuldet). Kein Kriterium, keine Admissibility, keine Null-Bedingung, kein Modellfeld, keine Promise-Tabelle, weil eine Berechnung keine Schranke hat. Recorded results, Conclusion und [result] run kommen erst nach dem Lauf.

(c) Der Reihe nach bis zur ersten vollen Messung:
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list und protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract
2. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md "type=…" "Terms of this protocol=…" "Question / hypothesis=…" "Data / scope=…" "Exclusions / filters=…" "Unit=…"
3. scripts/01_measure.py schreiben. Nach jeder Änderung code-check experiments/01-hrv, dazu der Test auf Hand-Fällen mit .venv/bin/python -m pytest -q (instructions.md:121-122). Kein --show, das gibt es für Compute nicht (instructions.md:118-119).
4. git add nur für die Protokolldatei und die Skripte, dann git commit.
5. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund.

(d) Nicht: kein fit und kein --change-kind, die Prüfung ergibt compute. Kein Freeze, kein Preflight, kein runlog start (instructions.md:146, 149). Kein --probe. Kein Kriterium oder keine Promise-Tabelle erfinden. Keine Zahl von Hand in Protokoll oder Ausgabe schreiben (instructions.md:37-40). Nicht vor dem Commit messen (T5). Kein git add -A.
Offen: Die Aufgabe verlangt pred_results/hrv.csv. Die Ausgabe nennt diesen Pfad nicht. Nach instructions.md:35-39 muss die Datei von diesem Lauf stammen (Skript schreibt sie oder ich kopiere die Ausgabe des Laufs). Das sollte vor dem Lauf geklärt werden.

## T2 (Klassifikator, kind fit, repeat_cost low)

(a) fit: Das Modell wird trainiert, und die Zahl beurteilt eine Vorhersage (auf gehaltenen gelabelten Zeilen). Also brauche ich Kriterium, Admissibility-Bedingung und Null-Bedingung, die in demselben Lauf berechnet werden. Danach Low-Schnitt füllen, Skripte (make_estimator(), SCORE, FEATURES_FIELD), Renderprobe, Commit, Lauf, finalize, Analyse-Audit, Übernahme.

(b) Eigene Entscheidungen:
- type; Terms; Question / hypothesis; Data / scope; Exclusions / filters; Unit.
- [C1] Kriterium: welches Maß und gegen welche Referenz.
- [A1] Admissibility-Bedingung und [A2] Null-Bedingung (Permutation innerhalb der Folds, Vergleich mit chance_of()).
- Code: make_estimator(), SCORE, FEATURES_FIELD.
- kind = fit und repeat_cost = low: meine Wahl beim Stamp-Befehl.
Bereits im Stamp gesetzt, nicht von mir in diesem Schritt:
- standard = "0.23", id, frozen = false, preflight_audit leer.
- "Model / tool: n/a — no model call": das stimmt mit dem Fall überein, kein [model]-Block. Ich übernehme es.
- Die Konstanten margin = 0.25 (C1), max_empty = 0 (A1), null_band = 0.1 (A2) stehen schon im Stamp. Woher sie kommen, sagt die Ausgabe nicht. Vor dem Commit muss ich sie bewusst bestätigen oder ändern, nicht nach dem Ergebnis (instructions.md:111-113).
- Summary, Recorded results und Runs sind Platzhalter bis nach dem Lauf.

(c) Der Reihe nach:
1. protocol-fill experiments/01-assay/PROTOCOL-assay.md --list und protocol-check experiments/01-assay/PROTOCOL-assay.md --contract
2. protocol-fill experiments/01-assay/PROTOCOL-assay.md mit "type=…", "Terms of this protocol=…", "Question / hypothesis=…", "Success / failure criterion=…", "Admissibility condition=…", "Null condition / anchors=…", "C1 sentence=…", "A1 sentence=…", "A2 sentence=…", "Data / scope=…", "Exclusions / filters=…", "Unit=…"
3. Konstanten im TOML-Kopf von Hand prüfen (das Protokoll ist meins, instructions.md:25-27).
4. Skripte schreiben; code-check experiments/01-assay nach jeder Änderung; .venv/bin/python -m pytest -q.
5. Renderprobe, siehe unten bei den offenen Punkten.
6. git add nur für die Protokolldatei, die Skripte und den Test, dann git commit.
7. .venv/bin/python experiments/01-assay/scripts/01_measure.py im Vordergrund.

(d) Nicht: kein --probe, kein Preflight, kein Freeze, kein runlog start (alles nur bei high, instructions.md:130-146). Kein --change-kind, kind fit ist richtig. Kein [model]-Block und keine Data profile oder Prompt, weil kein Modell aufgerufen wird. Kriterium und Konstanten nicht nach dem Blick auf Ergebnisse ändern, und margin nicht senken, um zu bestehen (instructions.md:274-276). Ergebnis und Conclusion nicht vorwegnehmen. Keine Datei unter data/prepared von Hand anlegen. Kein LABKIT_UNFROZEN.
Offen (siehe Liste unten): --show 2 oder 3, 00_prepare.py, Pilot.

## T3 (erster Commit nach dem Stamp wird verweigert)

(a) Der Hook verweigert den Commit, weil Pflichtfelder fehlen oder nur Platzhalter enthalten: [protocol] type fehlt, und Terms, Question, Data/scope, Exclusions und Unit stehen als Platzhalter (cases.md:175-180). Sie müssen ausgefüllt oder mit "n/a — <Grund>" begründet werden. Die Zeile zu den Runs ist keine Pflicht. Der Eintrag entsteht nach dem Lauf über protocol-fill --from-run (cases.md:173).

(b) Eigene Entscheidungen: type, Terms, Question, Data/scope, Exclusions, Unit. "n/a" kommt hier nicht in Frage, weil Frage, Daten und Einheit für diese Messung gelten. Vom Tool: der Runs-Eintrag. Kind compute und repeat_cost low stammen aus meinem Stamp-Befehl (T1).

(c) Der Reihe nach:
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list
2. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md mit den sechs Labels ("type=…" und die fünf Felder).
3. protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract, dann git add experiments/01-hrv (nur dieser Bereich, nicht -A) und git commit.
4. Danach weiter wie T1, ab Schritt 3.

(d) Nicht: kein --no-verify (instructions.md:315-316). Kein git add -A, das würde fremde Dateien mitnehmen. Keine Platzhalter stehen lassen und kein "n/a" ohne Begründung. Den Runs-Eintrag nicht von Hand schreiben. Hook und Ignore-Regeln nicht ändern.

## T4 (Messung verweigert, Registrierung fehlt)

(a) Das Gate verlangt die Registrierung, die die Art fordert, bevor ein Lauf eine berichtbare Zahl liefert. Bei compute ist das die Frage. Freeze ist bei low nicht nötig. Die Alternativen (Probe, LABKIT_UNFROZEN=1) liefern keine berichtbare Zahl; report-check verwirft sie (cases.md:195).

(b) Eigene Entscheidungen: type, Terms, Question / hypothesis, Data / scope, Exclusions / filters, Unit. Das Gate nennt nur die Frage, der Contract zählt fünf Felder (cases.md:46). Ich fülle alle fünf, nicht nur die Frage. Vom Tool: frozen und preflight, weil nicht geschuldet, und kein Kriterium, weil compute keine Schranke hat.

(c) Der Reihe nach:
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list und protocol-check … --contract
2. protocol-fill mit type und den fünf Feldern.
3. protocol-check experiments/01-hrv/PROTOCOL-hrv.md muss passieren.
4. git add für Protokoll und Skript, dann git commit.
5. .venv/bin/python experiments/01-hrv/scripts/01_measure.py

(d) Nicht: kein LABKIT_UNFROZEN=1 und kein run_kind='probe', um das Gate zu umgehen. Kein Freeze oder Preflight, das ist bei low nicht geschuldet. Die Frage nicht nach dem Ergebnis formulieren, die Registrierung kommt vor der Messung.

## T5 (Protokoll nicht committed)

(a) Die erste Messung hält sich an den Stand, den der Commit enthält. Das Protokoll ist nicht committet, also muss ich committen und dann den Lauf starten. Der Hinweis zum Freeze gilt wieder nicht.

(b) Eigene Entscheidungen: Commit-Umfang. Das Protokoll und das Skript gehören zusammen, weil das Skript das Instrument ist (instructions.md:148). Die Ausgabe nennt nur das Protokoll. Die Commit-Message ist meine Entscheidung und auf Englisch (globale Sprachregel für Commit-Messages). Vom Tool: nichts.

(c) Der Reihe nach:
1. code-check experiments/01-hrv, falls das Skript seit dem letzten Check geändert wurde.
2. git add experiments/01-hrv/PROTOCOL-hrv.md experiments/01-hrv/scripts/01_measure.py (und den Test, falls geändert).
3. git commit -m "01-hrv: registration committed before the first measurement"
4. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund.

(d) Nicht: das Skript nicht erneut starten, bevor committet ist. Kein --no-verify und kein LABKIT_UNFROZEN. Das Protokoll nach dem Commit nicht ändern, ohne erneut zu committen, sonst hält sich die Messung an den alten Stand. Kein git add -A. Kein Freeze.

## Offene Punkte und Widersprüche

1. T1 und T2: Die Ausgabe nennt den Pfad der Aufgabe (pred_results/hrv.csv bzw. pred_results/assay_pred.csv) nicht. Laut instructions.md:35-39 muss die Datei aus dem antwortenden Lauf stammen. Wie sie dorthin gelangt, bleibt offen.
2. T2: Die Renderprobe ist widersprüchlich. cases.md:60 sagt --show 3, instructions.md:118 sagt --show 2 für Schätzer-Skelette. Ich würde --show 2 nehmen, weil es die Arbeitsanweisung ist, bitte bestätigen.
3. T2: cases.md:159 nennt 00_prepare.py im Contract, die Schrittliste in cases.md:60-63 erwähnt es nicht. Unklar, ob data/assay.csv vorher vorbereitet werden muss.
4. T2: Die Konstanten margin = 0.25, max_empty = 0 und null_band = 0.1 stehen bereits im Stamp (cases.md:132-148). Die Herkunft ist nicht angegeben. Ich würde sie bewusst bestätigen, bevor ich committe.
5. T2: Data/scope im Stamp sagt "pilot subset first" (cases.md:88). Die Schrittliste verlangt keinen Pilot. Unklar, ob einer Pflicht ist.
6. T4: Das Gate nennt nur Question / hypothesis (cases.md:194), der Contract fordert fünf Felder (cases.md:46). Ich fülle alle fünf.
