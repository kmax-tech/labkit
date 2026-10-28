Bericht des Probelesers (Haiku 5.5). Gelesen wurden nur die zwei Dateien, vollständig: [I] = /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading-3/instructions.md (AGENTS.md, 333 Zeilen), [C] = /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-start-reading-3/cases.md. Abkürzungen: RMSSD = Wurzel aus dem Mittel der quadrierten Differenzen aufeinanderfolgender Herzschlagintervalle; ECG = Elektrokardiogramm; "Freeze" = Einfrieren des Protokolls vor dem Lauf; "Probe" = Probelauf, der keine berichtbare Zahl liefert; "Adoption" = Übernahme eines Laufs als Ergebnis (`protocol-fill --from-run`).

## T1 — Berechnung RMSSD, Area just stamped (repeat_cost low, kind compute)

**(a) Was die Ausgabe verlangt.** Zuerst die Art prüfen: trainiert, passt an oder wählt die Area ein Modell oder Verfahren (auch eine auf Leistungsdaten gewählte Schwelle)? Ja: `fit`. Sonst: beurteilt die Zahl die Vorhersage eines unverändert benutzten Modells gegen Gold-Labels? Ja: `apply`, sonst `compute` [C] Zeile 28. Bei `low` wird nichts eingefroren und es gibt kein Audit vor dem Lauf; der Lauf selbst ist die Instrumentenprüfung [C] Zeile 27. Für `compute` schuldet das Protokoll nur Frage, Daten, Ausschlüsse, Einheit und Begriffe, kein Kriterium und keine Promise-Tabelle [C] Zeilen 30, 40.

**(b) Was ich vor dem nächsten Commit festlege.**

| Feld / Einstellung | Wert | Wer entscheidet |
|---|---|---|
| `kind` | compute (bleibt) | Prüfung durch mich: kein Modell, keine Schwelle auf Leistungsdaten; Werkzeug hat es gestempelt |
| `repeat_cost` | low | Werkzeug (Stempel) |
| `type` im Kopf | confirmatory oder exploratory | ich; die Quellen sagen für eine Berechnung nichts. Typ beweist keine Gültigkeit [I] Zeile 54 |
| Terms of this protocol | RMSSD-Definition, Erkennung der R-Zacken, Glossar | ich |
| Question / hypothesis | Frage nach RMSSD aus `data/ecg.csv` | ich (Inhalt aus der Aufgabe) |
| Data / scope | `data/ecg.csv`, welche Teile | ich |
| Exclusions / filters | Artefakte, Mindestlänge, Ausreißer | ich, vor dem Commit festgelegt |
| Unit | ms (Vorschlag) | ich; die Aufgabe nennt nur den Pfad `pred_results/hrv.csv`, nicht das Format |
| Criterion, admissibility, null condition, Model/tool | nicht geschuldet | Werkzeug [C] Zeile 40 |
| `[model]`, Data profile, Prompt | nicht geschuldet (kein Modell) | Werkzeug |
| Recorded results, Conclusion | nach dem Lauf | Recorded results erzeugt das Werkzeug; Conclusion ich, nach dem Lauf |
| `scripts/01_measure.py`: `expected_ids()`, `rows()`, `evaluate_rows()` | Implementierung | ich |
| `tests/test_01_hrv.py` | handgeprüfte Fälle | ich |
| Commit-Message, gestagte Pfade | nur eigene Pfade | ich |

**(c) Befehle in dieser Reihenfolge, bis zum ersten vollen Lauf.** Stehen `protocol-fill`, `protocol-check`, `code-check` oder `labkit-audit` nicht im PATH, ist das Präfix `.venv/bin/` zu setzen [I] Zeile 5.
1. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list` (offene Felder)
2. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md "type=…" "Terms of this protocol=…" "Question / hypothesis=…" "Data / scope=…" "Exclusions / filters=…" "Unit=…"` (Labels laut Vertrag [C] Zeile 41)
3. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract` (nichts mehr offen)
4. Funktionen in `scripts/01_measure.py` füllen, Tests in `tests/test_01_hrv.py` auf handgeprüften Fällen, dann `.venv/bin/python -m pytest -q tests/test_01_hrv.py` (der Area-Testpfad ist meine Ableitung aus [I] Zeile 322)
5. `code-check experiments/01-hrv` nach jeder Codeänderung [I] Zeile 122
6. `git add <nur die eigenen Pfade>`, dann `git commit` (Pre-commit-Hook prüft die Felder der ersten Zeile)
7. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund. Das ist der erste volle Lauf; hier ende ich.

**(d) Was ich nicht tue, und warum.**
- Kein `--change-kind`: die Art bleibt compute, kein Fit.
- Kein Kriterium und keine Promise-Tabelle: eine Berechnung beurteilt keine Vorhersage, es gibt also keine Latte zu überspringen [C] Zeile 30.
- Kein `--show` (gibt es für compute nicht [I] Zeile 119), kein `--probe` (Probe nur bei `high` [I] Zeile 131–136), kein Preflight, kein `frozen = true`, kein Preflight-Audit: bei `low` nicht geschuldet [I] Zeile 146.
- Keine Ausgabedatei `pred_results/hrv.csv` vor der Adoption, keine Zahl von Hand eingetippt: die Datei kommt aus dem angenommenen Lauf [I] Zeilen 36–46, Zahlen erzeugen statt abtippen [I] Zeile 236.
- Keine Schwellenwahl nach Sicht der Ergebnisse: das wäre eine Auswahl, also ein `fit`.
- Kein `git add -A`, kein Push (Push ist Sache des Nutzers).

**Offene Punkte T1 (Sie entscheiden):**
1. [C] Zeile 28 sagt „a threshold … chosen on performance data counts“. Ob eine R-Zacken-Schwelle, die ich nach Sicht des EKG-Signals wähle, als Auswahl gilt, steht in den Quellen nicht. Ich behandle sie als nicht erlaubt ohne `fit`. Entscheidung nötig; bei Ja: `--change-kind` vor dem ersten Lauf.
2. Der Typ (confirmatory oder exploratory) für eine Berechnung ist in [I] Zeile 54 nicht geregelt.
3. [I] Zeile 327 sagt „Prepared data is read-only“, aber die Stempel-Skelette haben keinen Prepare-Schritt. Die Quellen sagen nicht, ob `data/ecg.csv` direkt gelesen wird.
4. Die Einheit (ms) und das Format von `pred_results/hrv.csv` sind nicht festgelegt.

## T4 — Messung abgelehnt: Registrierung nicht geschrieben (low)

**(a) Was die Ausgabe verlangt.** Der Lauf wurde abgelehnt, weil die Registrierung fehlt; bei `low` ist das Gate die Registrierung, die die Art schuldet, und nicht ein Freeze. Ich schreibe und committe die Registrierung und starte den Lauf danach neu. Ein Probelauf oder `LABKIT_UNFROZEN=1` liefert keine berichtbare Zahl [C] Zeilen 57–59.

**(b) Was ich vor dem nächsten Commit festlege.**

| Feld | Wert | Wer entscheidet |
|---|---|---|
| Question / hypothesis | Frage nach RMSSD; das Gate prüft genau dieses Feld | ich |
| Terms, Data / scope, Exclusions / filters, Unit, type | wie in T1 (b) | ich; der Commit schuldet sie alle [C] Zeile 58 |
| kind = compute, repeat_cost = low | bleibt | Werkzeug (Stempel) |
| Criterion, null condition, admissibility, Model | nicht geschuldet | Werkzeug |
| Conclusion, Recorded results | nach dem Lauf | Werkzeug bzw. ich |
| Code (`expected_ids`, `rows`, `evaluate_rows`) und Test | schon geschrieben, noch nicht geprüft | ich; vor dem Commit `code-check` und Test |
| Commit-Inhalt und Commit-Message | nur eigene Pfade | ich |

**(c) Befehle in dieser Reihenfolge, bis zum ersten vollen Lauf.**
1. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --list` (mit `.venv/bin/` falls nötig)
2. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md "Question / hypothesis=…" "type=…" "Terms of this protocol=…" "Data / scope=…" "Exclusions / filters=…" "Unit=…"`
3. `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract`
4. `code-check experiments/01-hrv`, dann `.venv/bin/python -m pytest -q tests/test_01_hrv.py`
5. `git add <nur die eigenen Pfade>`, dann `git commit`
6. `.venv/bin/python experiments/01-hrv/scripts/01_measure.py` im Vordergrund (derselbe Befehl wie vorher; er ist der erste volle Lauf)

**(d) Was ich nicht tue, und warum.**
- Kein `LABKIT_UNFROZEN=1`: es gilt nur bei `high` über einen abgelehnten Audit [C] Zeile 59.
- Kein Probelauf als Umweg; er liefert keine Zahl.
- Kein neuer Bereich und kein `--change-kind`: die Ablehnung betrifft die Registrierung, nicht die Art.
- Kein `--no-verify`, keine Änderung am Gate oder an den Run-Records [I] Zeilen 315–316.
- Kein Commit vor vollständiger Registrierung: der Hook prüft die Felder der ersten Zeile, und der erste Lauf wird am Commit gemessen [C] Zeile 45.
- Keine Conclusion und kein Ergebnis vor dem Lauf; keine Ausgabedatei.

**Offene Punkte T4:**
1. Ob ein abgelehnter Lauf eine Spur hinterlässt, die später zählt, steht in [C] Zeilen 57–59 nicht.
2. Die Ablehnung nennt nur Question / hypothesis als Gate, der Commit aber alle Felder. Ich fülle deshalb alle, statt auf das Gate allein zu vertrauen.

## Widersprüche zwischen den Quellen

Keine harten Widersprüche. [C] Zeile 27 und [I] Zeilen 146–148 stimmen bei `low` überein; [C] Zeile 34 und [I] Zeilen 36–46 stimmen bei der Ausgabedatei überein. Die Lücken stehen oben unter den offenen Punkten.
