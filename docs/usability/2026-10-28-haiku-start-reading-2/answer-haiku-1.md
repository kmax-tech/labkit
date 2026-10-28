Quellen: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading-2/instructions.md (kurz instructions.md) und .../cases.md (kurz cases.md). Zeilenangaben beziehen sich darauf. Geschrieben wurde nichts.

Begriffe: fit = hier wird ein Modell oder Verfahren trainiert oder angepasst. apply = ein unverändertes Modell wird an Labels bewertet. compute = eine Größe wird nur berechnet. Registrierung = schriftliche Festlegung der Frage vor dem ersten Lauf, committet (bei fit/apply zusätzlich Kriterium, Zulässigkeit, Null-Bedingung). RMSSD = Wurzel aus dem mittleren quadrierten Abstand aufeinanderfolgender Herzschlagintervalle (Herzfrequenzvariabilität).

## T1: compute-Bereich (hrv, low, compute)

(a) Die Ausgabe verlangt zuerst die Art-Prüfung: trainiert oder wählt die Area ein Modell oder Verfahren auf Leistungsdaten? Nein, also compute, weil die RMSSD nur berechnet wird. Danach: Protokoll im low-Umfang füllen, drei Funktionen implementieren, testen, committen, im Vordergrund messen, finalize, Analyse-Audit, Konklusion, Übernahme mit protocol-fill --from-run.

(b) Vor dem nächsten Commit:
- Vom Tool gegeben (aus dem Stempelaufruf): kind = compute, repeat_cost = low, frozen = false, kein preflight_audit, keine Promise-Tabelle, kein Modellabschnitt.
- Meine Entscheidungen: type (exploratory oder confirmatory; der Wert verleiht keine wissenschaftliche Gültigkeit, instructions.md:54), Terms of this protocol (RMSSD, Definition der Herzschlagintervalle), Question / hypothesis, Data / scope (data/ecg.csv, N), Exclusions / filters, Unit (ms).
- Nicht zu füllen: Kriterium, Zulässigkeit, Null-Bedingung (instructions.md:97-99, cases.md:29-30).

(c) Bis zur ersten vollen Messung:
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list und protocol-check … --contract.
2. protocol-fill mit type und Terms, Question, Data, Exclusions, Unit in einem Aufruf.
3. protocol-check … --contract erneut, muss passen.
4. expected_ids(), rows(), evaluate_rows() in scripts/01_measure.py implementieren, dann code-check experiments/01-hrv.
5. tests/test_01_hrv.py mit Handfällen, dann .venv/bin/python -m pytest -q.
6. git add mit expliziten Pfaden (Protokoll, Skript, Test, ggf. data/ecg.csv), dann git commit.
7. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund.

(d) Nicht:
- Keine Schwelle oder Erkennungsparameter auf Leistungsdaten abstimmen. Das wäre fit (cases.md:29).
- Kein frozen = true, kein Preflight-Audit (instructions.md:145-146).
- Kein --probe, kein --show; compute hat beides nicht (instructions.md:118-119, 134-136).
- Keine Zahl und keine Konklusion vor dem Lauf, keine Ausgabedatei von Hand (instructions.md:37-40, 189).

Unklar:
1. Ob die R-Zacken-Erkennung ein fit ist, wenn sie gegen Referenzannotationen abgestimmt wird, sagt die Quelle nicht (cases.md:29 nennt nur die Schwelle).
2. cases.md:31-34 nennt die Skripte ohne Interpreter-Präfix; instructions.md:150 verlangt .venv/bin/python. Ich nehme den Präfix.

## T2: fit-Bereich (assay, low, fit)

(a) Klassifikator auf gelabelten Verbindungen trainieren, unlabelled vorhersagen, pred_results/assay_pred.csv schreiben. Vor dem Commit Kriterium, Zulässigkeit, Null-Bedingung und Konstanten festlegen; dann 00_prepare.py (roh nach data/prepared/), 01_measure.py (make_estimator(), SCORE, FEATURES_FIELD), Tests, Commit, Lauf, finalize, Analyse-Audit, Konklusion, --from-run.

(b)
- Tool (Stempel): standard, id, Promise-key, scope.
- kind = fit, repeat_cost = low: mein Stempelaufruf. fit stimmt, weil ein Klassifikator trainiert wird (instructions.md:56-58).
- frozen = false, preflight_audit leer: Tool; bei low bleibt das so.
- type: meine Entscheidung.
- Terms, Question, Data/scope, Exclusions, Unit: meine Entscheidung.
- Kriterium [C1], Zulässigkeit [A1], Null-Bedingung [A2] (Sätze): meine Entscheidung.
- margin = 0.25, max_empty = 0, null_band = 0.1: Stempel-Beispiele; cases.md:59 verlangt, jeden Wert auf seinen Satz zu setzen, also meine Entscheidung.
- Model/tool (n/a — no model call): Stempeltext; ich prüfe, ob er zutrifft.
- make_estimator(), SCORE, FEATURES_FIELD: mein Code.
- Recorded results, Conclusion, Runs: nach dem Lauf.
Die Konstanten setze ich von Hand im TOML-Kopf; das Protokoll ist mein (instructions.md:26-27).

(c)
1. protocol-fill … --list und protocol-check … --contract.
2. protocol-fill für type, Terms, Question, Kriterium, Zulässigkeit, Null-Bedingung, Data, Exclusions, Unit; Sätze über "C1 sentence=…", Konstanten von Hand im TOML.
3. protocol-check … --contract, muss grün sein.
4. .venv/bin/python experiments/01-assay/scripts/00_prepare.py.
5. 01_measure.py implementieren, --show 3 lesen.
6. code-check experiments/01-assay, dann tests/test_01_assay.py mit Handfällen.
7. git add mit expliziten Pfaden, git commit.
8. .venv/bin/python experiments/01-assay/scripts/01_measure.py im Vordergrund.

(d) Nicht:
- Kein --probe (nur high, instructions.md:130-131), kein frozen = true, kein Preflight-Audit.
- Die Stempelwerte 0.25, 0 und 0.1 nicht übernehmen; Schwellen nicht nach Sicht der Ergebnisse setzen (instructions.md:111-113).
- Kein Lauf vor dem Commit, kein LABKIT_UNFROZEN=1.
- data/prepared/ danach nicht ändern (instructions.md:327).
- Keine Hyperparameter auf den Held-out-Zeilen wählen. Das folgt aus "evaluate on held-out labelled rows" (instructions.md:58-59), steht aber nicht ausdrücklich da.

Unklar:
1. Ob data/prepared/ vor dem Commit committet wird: instructions.md:148 nennt "inputs", cases.md:60 nicht.
2. cases.md:158 zählt Model/tool als Pflicht bei einem Bar, cases.md:163 nennt es vor dem Lauf nicht.
3. Welcher Typ für ein fit passt, legt die Quelle nicht fest (instructions.md:54).

## T3: Stempel-Commit abgelehnt

(a) Der Pre-Commit-Hook lehnt ab. Pflichtfelder fehlen: type und die Platzhalter Terms, Question, Data/scope, Exclusions, Unit. Sie sind auszufüllen oder mit "n/a — <Grund>" zu begründen. Die Runs-Zeile ist eine Notiz; der Runs-Eintrag entsteht erst durch --from-run nach dem Lauf.

(b) Meine Entscheidungen: type, Terms (RMSSD-Definition), Question, Data/scope (data/ecg.csv), Exclusions, Unit (ms). type schreibe ich nicht als "n/a", weil instructions.md:94-95 verlangt, type als Vor-Lauf-Feld auszufüllen. Der Runs-Eintrag bleibt unangetastet.

(c)
1. protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list.
2. protocol-fill mit type, Terms, Question, Data, Exclusions, Unit.
3. protocol-check … --contract.
4. git add mit den Pfaden des Stempels (Protokoll, Skripte, Test, README), dann git commit mit englischer Nachricht.

(d) Nicht:
- Kein git add -A (globale Regel: nur eigene Pfade stagen; das Repo hat macOS-Beifang).
- Kein --no-verify (instructions.md:315-316).
- Kein Runs-Eintrag von Hand, kein Ergebnis, keine Konklusion.
- Keine Platzhalter stehen lassen.

Unklar:
1. Ob die Runs-Zeile den Commit blockiert, sagt cases.md:176 nicht; sie ist nicht als MISSING markiert.
2. cases.md:183-186 erlaubt "n/a" für Pflichtfelder, instructions.md:94-95 verlangt type ausgefüllt. Ich folge dem Ausfüllen.

## T4: Messung abgelehnt, Registrierung fehlt

(a) Die Messung wird abgelehnt, weil für compute die Frage (Question / hypothesis) fehlt. Ich soll die Registrierung schreiben, committen und den Lauf neu starten. Probe und LABKIT_UNFROZEN=1 liefern keine berichtbaren Zahlen (cases.md:198).

(b) Question / hypothesis ist meine Entscheidung. Die Ausgabe nennt nur diese Lücke (cases.md:197); der Hook aus T3 verlangt außerdem type, Terms, Data, Exclusions und Unit. Ich fülle alle sechs. Skript und Test gehören in denselben Commit (instructions.md:148).

(c)
1. protocol-fill … --list.
2. protocol-fill mit Question und den übrigen Feldern.
3. protocol-check … --contract.
4. code-check experiments/01-hrv, dann der Bereichstest.
5. git add mit expliziten Pfaden, git commit.
6. .venv/bin/python experiments/01-hrv/scripts/01_measure.py, derselbe Befehl (instructions.md:154).

(d) Nicht:
- Kein LABKIT_UNFROZEN=1, kein run_kind=probe, um an eine Zahl zu kommen.
- Die Frage nach einem Blick auf Ergebnisse nicht umschreiben (instructions.md:111-113).
- Kein Freeze, kein Preflight-Audit, keine Ausgabedatei von Hand.

Unklar: cases.md:197 nennt nur die Question, cases.md:177-183 (T3) verlangt fünf weitere Felder; ich gehe von beiden Gates aus. T4 setzt außerdem einen Stand voraus, den T3 nicht committen konnte; ich nehme an, der Lauf wurde ohne Commit versucht.

## T5: Protokoll nicht committet

(a) Die Messung hält sich an die Registrierung, die der Commit enthält. Protokoll und Skript sind nicht committet. Ich soll committen und dann den Lauf starten. Probe und LABKIT_UNFROZEN=1 gelten auch hier nicht.

(b) Meine Entscheidungen: die Commit-Nachricht (englisch) und die Auswahl der Pfade. Die Registrierung ist fertig (cases.md:203-204); keine Werte ändern.

(c)
1. git status zur Kontrolle, welche Pfade offen sind.
2. Vorher protocol-check … --contract und code-check; falls noch nicht gelaufen, der Bereichstest.
3. git add für experiments/01-hrv/PROTOCOL-hrv.md, experiments/01-hrv/scripts/01_measure.py, tests/test_01_hrv.py und ggf. data/ecg.csv.
4. git commit -m "<englische Nachricht>".
5. .venv/bin/python experiments/01-hrv/scripts/01_measure.py im Vordergrund.

(d) Nicht:
- Kein Lauf vor dem Commit, kein --no-verify, keine Probe, kein LABKIT_UNFROZEN=1.
- Die Registrierung nach dem Commit nicht ändern, um den Lauf zu retten; spätere Änderungen beantworten die ursprünglich registrierte Frage nicht (instructions.md:111-113).
- Kein git add -A, keine Ausgabedatei vor dem Lauf.

Unklar: ob data/ecg.csv getrackt ist, sagt die Ausgabe nicht; die Quelle verlangt die Eingaben im Commit (instructions.md:148).

## Offene Punkte

1. Ob die R-Zacken-Erkennung ein fit ist, wenn sie auf Referenzen abgestimmt wird (T1, cases.md:29).
2. Interpreter-Präfix für die Skripte in T1 (cases.md:31-34 gegen instructions.md:150).
3. type für ein fit: welcher Wert? Keine Regel in der Quelle (T2, instructions.md:54).
4. Ob data/prepared/ committet wird (T2, instructions.md:148 gegen cases.md:60).
5. Model/tool-Feld: Pflicht vor dem Lauf oder nicht (T2, cases.md:158 gegen cases.md:163).
6. Ob die Runs-Zeile den Commit blockiert (T3, cases.md:176).
7. "n/a" oder ausfüllen bei type (T3, cases.md:183-186 gegen instructions.md:94-95).
8. Welche Pflichtfelder vor dem Commit der Registrierung gelten (T4, cases.md:197 gegen cases.md:177-183).
9. Ob data/ecg.csv getrackt ist (T5).
