Lesebericht zur Instruktionsprobe. Gelesen: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading/instructions.md (kurz "instructions.md") und /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading/cases.md ("cases.md"). Keine weiteren Dateien, keine Befehle, keine Schreibvorgänge.

Vorab: Unklarheiten, die mehrere Situationen betreffen (nummeriert, damit "1 ja" als Antwort reicht):

1. Zeigeschritt bei Schätzern: instructions.md:118 verlangt `--show 2`, cases.md:60 (T2) druckt `--show 3`. Ich würde `--show 3` ausführen (reiner Lesebefehl, kein Lauf) und den Widerspruch melden.
2. Area-Test fehlt in den Next-Listen: instructions.md:117 und :120-122 verlangen "fill the area test" und einen Test auf handgeprüften Fällen (Befehl: instructions.md:322 `.venv/bin/python -m pytest -q`). T1 (cases.md:31-32) und T2 (cases.md:60-61) nennen ihn nicht. Ich würde ihn trotzdem ausführen.
3. runlog oder Vordergrund: instructions.md:149 sagt "measure ... through `runlog`", :150 sagt "At low, run ... in the foreground". T4/T5 zeigen, dass das Messskript über ein runlog-Gate läuft. Ich würde den gedruckten Befehl unverändert ausführen; die Beziehung ist nicht erklärt.
4. "Freeze first" in T4/T5 (cases.md:195, :207) gegen low ohne Freeze (instructions.md:146). Die Klammer dort sagt, dass für low die Registrierung genügt; ich folge der Klammer und instructions.md:146.
5. Konstanten im Stempel (T2, cases.md:132-148: margin 0.25, max_empty 0, null_band 0.1) stehen als Zahlen da. instructions.md:112-113 verlangt, Kriterien und Konstanten vor Ergebnissen selbst zu setzen. Unklar, ob die Stempelwerte Vorschläge oder Vorgaben sind.
6. Woher die Deliverable-Datei (pred_results/...) kommt, sagt keine der Ausgaben. instructions.md:35-40 verlangt die Datei aus dem antwortenden Lauf, nie neu getippt oder getrennt berechnet.
7. T4 nennt nur Question / hypothesis als fehlend, T3 (cases.md:173-180) nannte sechs Pflichtfelder. Unklar, ob type, Terms, Data, Exclusions und Unit zum Zeitpunkt T4 schon fällig sind. Ich würde sie ausfüllen.
8. Conclusion: instructions.md:189 verlangt sie "before adoption"; die T1-Next-Liste erwähnt sie nicht. Nicht vor dem Lauf nötig.

SITUATION T1 (RMSSD aus data/ecg.csv, labkit-init exp hrv --repeat-cost low --kind compute)

(a) Die Ausgabe verlangt zuerst die Art-Prüfung: Trainiert, passt an oder wählt die Area ein Modell oder Verfahren (auch Schwelle oder Prompt auf Leistungsdaten)? Dann fit. Sonst: beurteilt die Zahl die Vorhersage eines unverändert genutzten Modells gegen Gold-Labels? Dann apply. Sonst compute (cases.md:28; instructions.md:56-62). RMSSD ist eine Berechnung ohne Modell, also compute; kein --change-kind. Dann Protokoll low ausfüllen (type, Question, Data, Exclusions, Unit; keine Kriterien), die drei Funktionen implementieren, committen, im Vordergrund messen, finalize, Analyse-Audit, Adoption (cases.md:29-34, :40-47).

(b) Vor dem nächsten Commit:
- Eigene Entscheidungen: type (exploratory oder confirmatory, Definition instructions.md:54); Terms of this protocol; Question / hypothesis; Data / scope (data/ecg.csv, Quelle, N); Exclusions / filters; Unit (instructions.md:97, :110).
- Vom Werkzeug gesetzt: kind = compute, repeat_cost = low (beide über meine Init-Flags gestempelt); standard, id; frozen = false; preflight_audit leer; kein [model] (kein --model).
- Nicht zu setzen: Kriterium, Admissibility, Null-Bedingung, Promise-Tabelle (cases.md:44-45; instructions.md:98-100 gilt nur für fit und apply).

(c) Befehle bis zum ersten vollen Lauf, in Reihenfolge:
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list (instructions.md:93)
2. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md "type=<Wahl>" "Terms of this protocol=…" "Question / hypothesis=…" "Data / scope=…" "Exclusions / filters=…" "Unit=…" (Form nach instructions.md:107-109)
3. protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract (instructions.md:93)
4. scripts/01_measure.py: expected_ids(), rows(), evaluate_rows() implementieren; den Area-Test füllen (instructions.md:117)
5. code-check experiments/01-hrv nach jeder Änderung (cases.md:31)
6. .venv/bin/python -m pytest -q (instructions.md:322)
7. git add mit den konkreten Pfaden (Protokoll, Skript, Test, Code), dann git commit (instructions.md:148)
8. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund (instructions.md:150; cases.md:32). Das ist der erste volle Lauf und zugleich der Instrumenten-Check.

(d) Nicht tun:
- Kein Freeze, kein preflight, kein frozen = true, kein Preflight-Audit: bei low nicht geschuldet (instructions.md:146).
- Kein --probe: compute hat keinen (instructions.md:135-136); auch kein --show (instructions.md:118-119).
- Keine Kriterien oder Konstanten erfinden, die compute nicht braucht (cases.md:44-45).
- Kein --change-kind: kind bleibt compute.
- Die Zahl nicht selbst rechnen oder nach pred_results/hrv.csv tippen; die Datei kommt aus dem Lauf (instructions.md:35-40).
- Kein --no-verify (instructions.md:315-316).

SITUATION T2 (Klassifikator auf data/assay.csv, labkit-init exp assay --repeat-cost low --kind fit)

(a) Kind fit ist richtig: trainiert oder wählt das Verfahren, auch wenn das Ergebnis Vorhersagen ohne Gold-Labels sind; bewertet wird auf zurückgehaltenen gelabelten Zeilen (instructions.md:56-58). Die Ausgabe verlangt den low-Schnitt mit type, Question, Unit, Data, Exclusions, Kriterium, Admissibility und Null-Bedingung, weil fit eine Schranke hat (cases.md:58-59). Dann Estimator (make_estimator(), SCORE, FEATURES_FIELD), --show 3, Commit, Vordergrund-Lauf, finalize, Analyse-Audit, Adoption (cases.md:60-63).

(b) Eigene Entscheidungen (vor dem Commit):
- type; Terms; Question / hypothesis; Data / scope (Quelle, N, Produzent-Skript, Pilot-Teilmenge); Exclusions; Unit.
- Sätze der Promises: C1 (Kriterium), A1 (Ausbeute), A2 (Null-Bedingung, Design: Labels je Trainings-Fold permutiert, Erwartung chance_of() innerhalb null_band). Die Wahl ist meine, auch wenn der Stempel Beispielsätze mit Platzhaltern liefert; das ist unklar (Unklarheit 5).
- Die Konstanten margin, max_empty, null_band: Stempelwerte 0.25, 0, 0.1. Ob ich sie übernehme, entscheide ich vor dem Sehen von Ergebnissen (instructions.md:112-113); der Stempel erklärt sie nicht.
- Code: make_estimator(), SCORE, FEATURES_FIELD.

Vom Werkzeug gesetzt (nicht ändern): kind = fit und repeat_cost = low (meine Init-Flags, gestempelt); standard = "0.23"; id; frozen = false; preflight_audit = ""; die Promise-Schlüssel c1_pass, a1_pass, a2_pass und ihre scope-Liste; die Zeile Model / tool "n/a — no model call" (vorgefüllt; ich prüfe, ob sie zutrifft). Kein [model], also kein Data profile (instructions.md:101-102).

(c) Befehle bis zum ersten vollen Lauf:
1. protocol-fill experiments/01-assay/PROTOCOL-assay.md --list und protocol-check … --contract (instructions.md:93)
2. protocol-fill mit "type=…", "Question / hypothesis=…", "Terms of this protocol=…", "Success / failure criterion=…", "Admissibility condition=…", "Null condition / anchors=…", "Data / scope=…", "Exclusions / filters=…", "Unit=…" und den Promise-Sätzen. Unklar, ob C1, A1, A2 eigene Label-Formen brauchen; --list zeigt es (Unklarheit 5 und instructions.md:107).
3. Estimator implementieren; .venv/bin/python experiments/01-assay/scripts/01_measure.py --show 3 (Unklarheit 1)
4. code-check experiments/01-assay nach jeder Code-Änderung (cases.md:60)
5. .venv/bin/python -m pytest -q auf handgeprüften Fällen (instructions.md:120-122, :322)
6. git add mit konkreten Pfaden, git commit (instructions.md:148)
7. .venv/bin/python experiments/01-assay/scripts/01_measure.py im Vordergrund (cases.md:61)

(d) Nicht tun:
- Kein Freeze, kein Preflight, kein frozen = true (instructions.md:146).
- Kein --probe (nur bei high: instructions.md:130-136).
- Keine Konstante nach dem Sehen von Ergebnissen senken: eine gesenkte Schwelle ist keine Reparatur (instructions.md:274-276).
- Kein --change-kind: fit ist richtig.
- Die Vorhersagedatei nicht von Hand schreiben (instructions.md:35-40).
- Kein Data profile, kein [model]: keine Modellaufrufe.
- Kein --no-verify.

SITUATION T3 (git add -A && git commit -m "stamp" wird vom Hook abgelehnt)

(a) Der Hook verlangt die Pflichtfelder: [protocol] type fehlt; Terms, Question, Data / scope, Exclusions und Unit sind Platzhalter (cases.md:173-180). Jedes Feld ausfüllen oder mit "n/a — <Grund>" begründen; der Grund muss dastehen, nicht nur die Klammern (cases.md:180). Die Zeile "Runs: the stamped entry is written by protocol-fill --from-run …" (cases.md:173) ist Hinweis, kein Fehler: der Lauf-Eintrag kommt erst mit dem Adoptionsbefehl.

(b) Eigene Entscheidungen: type (instructions.md:54), Terms, Question, Data / scope, Exclusions, Unit, jeweils mit Wert oder begründetem "n/a". Nichts Weiteres: kein Kriterium, kein Freeze. Der Runs-Eintrag gehört nicht mir.

(c) Befehle:
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list (instructions.md:93)
2. protocol-fill mit den sechs Feldern (instructions.md:107-109)
3. protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract
4. Index prüfen und nur die konkreten Pfade stagen: Protokoll, Skript, Test, Code (instructions.md:148, :258-260). Das `-A` des ersten Versuchs hat alles gestagt; das Dokument nennt -A nicht.
5. git commit; der Hook prüft den gestagten Stand (instructions.md:258-260).

(d) Nicht tun:
- Kein --no-verify, und Hook oder Ignore-Regeln nicht ändern (instructions.md:315-316).
- Keine Platzhalter stehen lassen und kein "n/a" ohne Grund (cases.md:180).
- Keinen Runs-Eintrag von Hand schreiben (cases.md:173; instructions.md:215-216).
- Kein frozen, kein Freeze: bei low nicht geschuldet (instructions.md:146).
- Nicht messen, bevor die Registrierung committet ist (cases.md:206 in T5).

SITUATION T4 (Messung abgelehnt: Question / hypothesis fehlt)

(a) Der Lauf wird verweigert, weil das Protokoll für eine Messung nicht bereit ist: Question / hypothesis fehlt. Bei low ist das Gate die Registrierung der Art, nicht ein Freeze (cases.md:194-195). Der Satz "Freeze first" steht trotzdem da; die Klammer sagt, dass bei low die Registrierung genügt.

(b) Eigene Entscheidung: Question / hypothesis, die eine Frage (instructions.md:97). Dazu die übrigen offenen Pflichtfelder (Unklarheit 7). Vom Werkzeug gesetzt: kind, repeat_cost, frozen = false, standard, id. Die Messung wurde abgelehnt, also liegen keine Zahlen vor: die Frage darf jetzt festgelegt werden, ohne dass Ergebnisse sie beeinflussen (instructions.md:112-113).

(c) Befehle:
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list
2. protocol-fill mit "Question / hypothesis=…" und den übrigen offenen Feldern
3. protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract
4. code-check experiments/01-hrv (die Funktionen wurden geändert; cases.md:31, instructions.md:120)
5. git add mit konkreten Pfaden, git commit (Registrierung vor der ersten Messung, instructions.md:111, cases.md:45)
6. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund

(d) Nicht tun:
- Kein preflight, kein Freeze, kein frozen = true (instructions.md:146; cases.md:195).
- Kein LABKIT_UNFROZEN=1 und kein Probe-Lauf, um doch eine Zahl zu bekommen: report-check verwirft solche Zahlen (cases.md:195).
- Die Frage nicht nach dem Sehen von Ergebnissen ändern (instructions.md:112-113).
- Kein --probe: compute hat keinen (instructions.md:135-136).

SITUATION T5 (Messung abgelehnt: Protokoll nicht committet)

(a) Das Protokoll ist nicht committet. Die erste Messung ist an die Registrierung gebunden, die der Commit hält. Protokoll committen, dann den Lauf starten (cases.md:206).

(b) Eigene Entscheidungen: welche Pfade im Commit liegen (Registrierung, Code, Test, Eingaben; instructions.md:148) und die Commit-Nachricht. Die jetzt ausgefüllten Felder (type, Terms, Question, Data, Exclusions, Unit) werden mit dem Commit zur Registrierung. Ich prüfe den Wortlaut, bevor ich committe, weil spätere Änderungen die beantwortete Frage nicht mehr deckeln (instructions.md:112-113). Vom Werkzeug gesetzt: frozen = false, preflight_audit = "".

(c) Befehle:
1. code-check experiments/01-hrv, falls der Code seit der letzten Prüfung geändert wurde (instructions.md:120)
2. protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract (Kontrolle)
3. git add mit konkreten Pfaden: Protokoll, Skript, Test, Code
4. git commit
5. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund (cases.md:206; instructions.md:150)

(d) Nicht tun:
- Kein git add -A; die Pfade, die zu Registrierung und Code gehören (instructions.md:148, :258-260).
- Keinen Lauf vor dem Commit, kein LABKIT_UNFROZEN=1 (cases.md:207).
- Kein --no-verify.
- Kein frozen = true, kein Freeze bei low (instructions.md:146).
- Das Protokoll nach dem Commit nicht stillschweigend ändern: offen, wie die Regel für Änderungen zwischen Commit und erstem Lauf lautet (Unklarheit 7 und Frage nach instructions.md:112-113).
