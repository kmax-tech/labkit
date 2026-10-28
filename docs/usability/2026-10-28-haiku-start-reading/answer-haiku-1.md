Probe-Bericht: Lesen von instructions.md und cases.md (nur Read, keine weiteren Tools). Quellen: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading/instructions.md und /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading/cases.md.

Abkürzungen vorab: RMSSD = Wurzel aus dem mittleren quadrierten Abstand aufeinanderfolgender Herzschläge (eine Kennzahl der Herzfrequenzvariabilität, HRV); EKG = Elektrokardiogramm; out-of-fold (OOF) = Vorhersage für Zeilen, die beim Training nicht vorkamen. "Registrierung" meint hier die vor dem Lauf festgelegten Protokollfelder.

## T1 — Rechenbereich (compute) frisch angelegt

(a) Die Ausgabe verlangt zuerst die Art der Zahl zu prüfen: Trainiert oder wählt die Fläche ein Modell oder Verfahren (dann fit), urteilt die Zahl über ein unverändertes Modell gegen Labels (apply), sonst compute. RMSSD hat weder Modell noch Labels, also bleibt kind = compute. Dann: Protokoll-Kopf type, danach Frage, Einheit, Daten, Ausschlüsse; kein Kriterium. Skript: expected_ids(), rows(), evaluate_rows(); nach jeder Änderung code-check; committen; Skript im Vordergrund starten.

(b) Vom Werkzeug gesetzt (nicht meine Entscheidung): kind = compute, repeat_cost = low, standard, id, frozen = false, die Skelett-Skripte. Kein Freeze, keine Preflight-Zeile nötig.
Eigene Entscheidungen vor dem Commit:
- type (exploratory oder confirmatory; die Ausgabe gibt keine Vorgabe)
- Terms of this protocol
- Question / hypothesis
- Data / scope (data/ecg.csv, Herkunft)
- Exclusions / filters
- Unit (eine Zahl pro Aufnahme oder pro Intervall)
- der Code in 01_measure.py und der Test
Nicht zu füllen: Kriterium, Zulässigkeit, Nullbedingung, Promise-Tabelle, Recorded results und Conclusion (nach dem Lauf).
Grenze: Wird eine Peak-Schwelle an Leistungs- oder Referenzdaten gewählt, ist es fit (Ausgabe Schritt 1). Eine Schwelle allein am Signal ist nach meiner Lesart kein Leistungsdatum; die Ausgabe lässt das offen.

(c) In dieser Reihenfolge:
1. Felder füllen: protocol-fill experiments/01-hrv/PROTOCOL-hrv.md "<Label>" "<Wert>" für Terms, Question / hypothesis, Data / scope, Exclusions / filters, Unit; type im Kopf setzen (protocol-fill oder von Hand). Falls protocol-fill nicht im PATH liegt: .venv/bin/ davor.
2. protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract (und --list)
3. scripts/01_measure.py schreiben; Test mit Hand-geprüften Fällen: .venv/bin/python -m pytest -q
4. code-check experiments/01-hrv
5. git add nur die Bereichspfade, git commit
6. .venv/bin/python experiments/01-hrv/scripts/01_measure.py (Vordergrund) — erster voller Lauf

(d) Nicht: kind auf fit ändern, nur weil Zahlen gerechnet werden; --show und --probe (compute hat beide nicht); Freeze, Preflight oder frozen = true (low); pred_results/hrv.csv von Hand oder außerhalb des Laufs berechnen; --from-run oder --force vor finalize und Analyse-Audit; Ergebnisse vor der Adoption als Antwort berichten.

## T2 — Fit-Bereich (Klassifikator auf Assay-Verbindungen) frisch angelegt

(a) Die Ausgabe verlangt: Protokoll-Low-Schnitt füllen (type, Frage, Einheit, Daten, Ausschlüsse, Kriterium, Zulässigkeitsbedingung, Nullbedingung); Skript make_estimator(), SCORE, FEATURES_FIELD; --show 3; code-check; committen; Lauf im Vordergrund; finalize; Analyse-Audit; --from-run. Das Kriterium bewertet den Schätzer auf OOF-Zeilen; die Vorhersagen für unbeschriftete Zeilen sind das Ziel.

(b) Vom Stempel gesetzt: kind = fit, repeat_cost = low, standard, id, frozen = false, preflight_audit = "", Model/tool "n/a — no model call" (Begründung vom Stempel; ich prüfe sie). Zusätzlich stehen im [[promise]]-Block Konstanten: margin = 0.25 (C1), max_empty = 0 (A1), null_band = 0.1 (A2). Das sind Festlegungen vor dem Ergebnis; ich bestätige oder ändere sie vor dem Commit, nicht danach.
Eigene Entscheidungen:
- type
- Terms, Question / hypothesis
- Satz C1 (Stempel-Text als Vorlage), Satz A1 (Ausbeute), Satz A2 (Labels innerhalb jeder Trainingsfalte permutiert, erwartet bei chance_of())
- Data / scope (Quelle, N, Erzeugerskript; Pilot-Teilmenge?), Exclusions, Unit
- Schätzer, SCORE, FEATURES_FIELD im Skript
Nicht zu füllen: Conclusion, Recorded results, Runs (nach dem Lauf). Kein [model]-Block, also kein Data profile und kein Prompt.

(c) In dieser Reihenfolge:
1. protocol-fill für type, Terms, Question, Data / scope, Exclusions, Unit, C1, A1, A2; Konstanten bei Bedarf im TOML-Kopf von Hand ändern.
2. protocol-check experiments/01-assay/PROTOCOL-assay.md --contract (und --list)
3. Skript füllen; .venv/bin/python experiments/01-assay/scripts/01_measure.py --show 2 (oder --show 3, siehe Lücke 1 unten)
4. code-check experiments/01-assay; Test mit Hand-geprüften Fällen (.venv/bin/python -m pytest -q)
5. git add der Bereichspfade, git commit
6. .venv/bin/python experiments/01-assay/scripts/01_measure.py (Vordergrund) — erster voller Lauf

(d) Nicht: frozen = true oder Preflight (low); --probe (bei low entfällt der eigene Probelauf; die volle Messung prüft das Instrument); Margin, max_empty oder null_band nach Sicht der Ergebnisse ändern; pred_results/assay_pred.csv von Hand schreiben; Schätzer- oder Modellwahl an Testlabels ausrichten; Vorhersagen vor der Adoption berichten.

## T3 — erster Stempel-Commit abgewiesen

(a) Der Hook verlangt die Pflichtfelder: [protocol] type im Kopf, Terms (Zeile 9), Question (10), Data / scope (18), Exclusions (19), Unit (20). Sie sind noch Platzhalter. Die Zeile "Runs: … nach dem Lauf" trägt kein (must) und ist daher kein Blocker; ich lese sie als Hinweis.

(b) Eigene Entscheidungen: type (exploratory oder confirmatory), Terms, Question / hypothesis, Data / scope, Exclusions (oder "n/a — <Grund>"), Unit. Nicht zu füllen: der Runs-Eintrag (schreibt protocol-fill --from-run nach dem Lauf). Kriterium und Zulässigkeit werden für compute nicht verlangt.

(c) Felder füllen (protocol-fill oder von Hand bei type), protocol-check --contract prüfen, dann nur die Stempel-Dateien dieses Bereichs stagen (git add experiments/01-hrv/...), git commit. Der Hook läuft erneut.

(d) Nicht: --no-verify, den Hook abschalten, Platzhalter ohne Begründung durchwinken; git add -A (globale Regel: nur eigene Pfade stagen; die Lab-Regel verlangt ohnehin gemeinsames Stagen der Bereichsdateien); den Runs-Eintrag vorab schreiben.

## T4 — Messung abgewiesen: Registrierung nicht geschrieben

(a) Der Lauf wird abgewiesen, weil die Registrierung fehlt. Genannt wird nur Question / hypothesis. Die Ausgabe enthält außerdem die Zeile "Freeze first" (preflight, audit, frozen = true) und in Klammern: bei low genügt die Registrierung, die die Art verlangt. Probe-Läufe und LABKIT_UNFROZEN=1 liefern keine zählbare Zahl.

(b) Eigen: der Satz zu Question / hypothesis (die Frage). Festgestellt: Die Ausgabe nennt nur dieses Feld, im Stempel-Protokoll (siehe T3) sind aber auch Terms, Data, Exclusions und Unit leer. Ich fülle alle fünf vor dem Commit. Freeze und Preflight: nicht fällig.

(c) protocol-fill "Question / hypothesis" "<Satz>" (und die übrigen Felder), protocol-check --contract, dann committen (T5), dann den Lauf erneut starten: .venv/bin/python experiments/01-hrv/scripts/01_measure.py.

(d) Nicht: LABKIT_UNFROZEN=1; den Lauf als Probe starten (report-check verweigert deren Zahlen); frozen = true von Hand wegen der "Freeze first"-Zeile setzen; einen Preflight-Audit anstoßen; die Frage nach einem Blick auf Ergebnisse umformulieren.

## T5 — Messung abgewiesen: Protokoll nicht committet

(a) Die Felder sind gefüllt und protocol-check läuft durch. Der Lauf wird trotzdem abgewiesen, weil das Protokoll nicht committet ist: Die erste Messung ist an die Registrierung gebunden, die ihr Commit enthält. Es soll committet werden, dann startet der Lauf. Die "Freeze first"-Zeile steht wieder dabei (siehe T4).

(b) Eigen: die sechs Felder (type, Terms, Question, Data, Exclusions, Unit) sind gesetzt und geprüft. Zusätzlich fällig: Das Skript 01_measure.py und der Test sind ebenfalls uncommittet. Die Ausgabe nennt nur das Protokoll, aber Schritt 3 und 4 des Ablaufs verlangen Code und Registrierung zusammen, und finalize prüft, dass die Quelle im Lauf eingefroren und in git verfolgt ist. Also committe ich das Skript mit.

(c) git add experiments/01-hrv/PROTOCOL-hrv.md experiments/01-hrv/scripts/01_measure.py (plus Test), git commit, dann .venv/bin/python experiments/01-hrv/scripts/01_measure.py (Vordergrund, erster voller Lauf). Danach finalize, Analyse-Audit, Adoption (später).

(d) Nicht: die Registrierung nach dem Commit ändern, um den Lauf zu retten; spätere Änderungen beantworten die ursprünglich registrierte Frage nicht. Nicht: --no-verify, LABKIT_UNFROZEN=1, Probe-Lauf als Umweg.

## Widersprüche und Lücken (nummeriert, für die Rückmeldung)

1. Anzahl bei --show: instructions.md:118 verlangt --show 2, cases.md T2 Schritt 2 verlangt --show 3. Welche gilt?
2. "Freeze first" in T4 und T5 (cases.md:194, 207) steht vor der Klammer, die bei low keinen Freeze verlangt. instructions.md:145-146 sagt ebenfalls: bei low keine Freeze- oder Preflight-Pflicht. Die Klammer löst es, die Zeile sollte bei low aber nicht erscheinen.
3. T4 nennt nur Question / hypothesis als fehlend, T3 zeigt Terms, Data, Exclusions und Unit als Platzhalter im selben Stempel-Zustand (cases.md:175-179). Prüft runlog nur das erste Feld?
4. Terms of this protocol: cases.md:40 nennt es als low-Pflicht, T1 Schritt 2 (cases.md:30) und die Vorlaufliste von T2 (cases.md:158-160) nennen es nicht. instructions.md:110 verlangt Terms. Ich folge dem Vertrag und fülle Terms.
5. Die Konstanten im T2-Stempel (margin 0.25, max_empty 0, null_band 0.1; cases.md:126-148) sind nicht als Platzhalter oder als Vorgabe gekennzeichnet. instructions.md sagt nur, Konstanten vor dem Ergebnis festzulegen. Dürfen die Stempelwerte stehen bleiben?
6. Data / scope im T2-Stempel sagt "pilot subset first" (cases.md:88). Bei low gibt es nach instructions.md:135-136 keinen eigenen Probelauf. Zählt ein Pilotlauf als run_kind probe, und bindet er die Registrierung?
7. T2 nennt kein 00_prepare.py, der Vertrag nennt es aber im Estimator-Skelett (cases.md:159). Müssen die Daten vor 01_measure.py vorbereitet werden?
8. Ausgabepfad: Aufgabe nennt pred_results/hrv.csv und pred_results/assay_pred.csv. Keine Ausgabe sagt, ob das Skript die Datei selbst schreibt oder ob sie aus dem Lauf kopiert wird (instructions.md:36-39). Das ist nur am Skript zu prüfen, das ich hier nicht öffnen darf.
9. "its reference" in cases.md:59 ist unklar: Nullanker, Vergleichswert oder Labelquelle?
10. T1: "a threshold ... chosen on performance data counts" (cases.md:28) ist für Peak-Schwellen nicht eindeutig. Ein Schwellwert, der an einer Referenz-Annotation geprüft wird, ist nach meiner Lesart fit; die Quelle sagt das nicht ausdrücklich.

Die Zeile "Runs: …" in T3 (cases.md:173) habe ich als Hinweis gelesen (siehe T3 a).
