Antworten zu S1, S2, S4, S5. Gelesen: nur instructions.md und cases.md. Kürzel: BLOCKER = Befund, der die Abgabe sperrt; WARNING = Befund, der nur die Aussage begrenzt; Adoption = Übernahme eines Laufs als Ergebnis (`protocol-fill --from-run`); Handover = geordnete Übergabe ohne Ergebnis.

## S1 (compute-hrv, repeat_cost low, kind compute)

**(a) Probleme**
1. Die Sub-Sample-Verfeinerung wird auf das 10-ms-Raster zurückgeschnitten (`peaks.copy()` erbt den Integer-dtype; `01_measure.py:113`, Zuweisung `:123`). Der Befund ist BLOCKER, Klasse "implementation error". Folge: `rmssd_ms` = 26.94 ist Jitter, kein Ergebnis.
2. Das Protokoll berichtet den überholten Run 8b74 (`PROTOCOL-compute-hrv.md:19`, `:46`, `:77`); die Output-Datei gehört zu 5de6. Die 26.05 ist jetzt `rmssd_ms_grid`.
3. Der Analysis-Audit sieht nicht den aktuellen Code (`no analysis audit saw the area as it is now`).
4. Report-Block und `02_analyze.py --check` passen nicht (drei Schlüssel fehlen, Zahlen stehen nicht im Protokoll).
5. Befund 22-38 `#2` ist `accepted` und nie nachgezogen.
6. `pred_results/hrv.csv` ist aus dem überholten Run geschrieben.

**(b) Optionen laut Anleitung und Tool**
- Implementation error: Code fixen, unter unveränderter Registrierung neu messen, neu auditieren, `fixed` mit benannter Änderung. Hilft: Der Befund ist ein Codefehler.
- Missed criterion: berichten. Passt nicht, der Fehler liegt im Code.
- Unjudged promise (`accepted` mit `--effect "<ID> not assessable"`): nur, wenn der Fehler nicht behebbar ist. Hier behebbar.
- Invalid registration (neues Protokoll mit `[replaces]`): passt nicht, die Registrierung ist nicht widersprüchlich.
- None of these / Handover: nur als Rückfall, falls die Korrektur scheitert.
- `deferred` hilft nicht, es verschiebt nur. `--effect stands` nur nach Review.

**(c) Wahl: implementation error.** Befehle in dieser Reihenfolge (`.venv/bin/` vorne, wo nicht im PATH):
1. In `experiments/01-compute-hrv/scripts/01_measure.py` die Peak-Positionen als Float halten (`:113`, `:123`), Check `refined_peak_fraction_nonint` ergänzen, Test ergänzen.
2. `set -o pipefail; .venv/bin/python -m pytest -q`
3. `code-check experiments/01-compute-hrv`
4. `git add <eigene Pfade>` und `git commit` (nur der Code).
5. `.venv/bin/python experiments/01-compute-hrv/scripts/01_measure.py` (low, im Vordergrund)
6. `.venv/bin/finalize experiments/01-compute-hrv`
7. `.venv/bin/labkit-audit experiments/01-compute-hrv --mode analysis` (als Hintergrund-Task, das dauert)
8. `.venv/bin/labkit-audit experiments/01-compute-hrv --findings`, dann je Befund `--decide N fixed|accepted "<Grund>" --record <neue Record-Datei>`
9. Conclusion neu setzen (`protocol-fill … "Conclusion=…" --force`), dann `protocol-fill … --from-run <neue run_id> --force`, `--render`, `--into REPORT.md`.
10. Protokoll, Report, Outputs, Records gemeinsam committen.

Unsicher: Der Report-Check nennt Run 4268 als Antwort-Run und empfiehlt `--from-run 4268 --force`, sobald seine Prüfungen halten. Dieser Lauf ist nach demselben Verfeinerungscode entstanden; ob er den Fehler hat, sagt die Ausgabe nicht. Ich würde ihn nicht adoptieren, bevor der Code gefixt ist.

**(d) Nicht tun:** die 26.05 weiter berichten; Run 4268 adoptieren, solange der Fehler drin ist; `--effect stands` ohne zweiten Auditor; Befunde auf `deferred` setzen; Audit- oder Run-Records von Hand ändern; Zahlen in Report oder CSV abtippen; `--no-verify`.

**(e) Output-Datei:** `pred_results/hrv.csv` sofort entfernen. Sie speist sich aus dem überholten Run, und der Audit-BLOCKER gegen den Code ist offen. Neu schreiben nur als Kopie der eigenen Output-Datei des neuen, adoptierten Antwort-Runs, nicht neu gerechnet. Bei Handover bleibt sie weg, und der Report nennt den Grund.

## S2 (fit-assay, repeat_cost low, kind fit)

**(a) Probleme**
1. Im Commit der Registrierung widersprechen sich Text (Marge 0,15) und Konstante (0,25). Der Lauf d0c0 nahm 0,25.
2. Die nachträgliche Textänderung auf 0,25 ist der Auslöser des intent-check-BLOCKERs (Promise-Block d37c… → f571…). Anleitung: "Set its criteria and constants before seeing results; later changes do not answer the original registered question."
3. WARNING 1: `kind = fit`, der Code tunt aber nichts (`01_measure.py:139`). Anleitung: fit heißt "train, adjust or select".
4. WARNING 2: Die Limit-Änderung 0,15→0,25 steht als `stands` ohne Review.
5. `02_analyze.py --check` scheitert am selben Promise-Wechsel.

**(b) Optionen**
- Implementation error (Code an die Registrierung angleichen, neu messen): nur wenn 0,15 die gewollte Marke war. Das ist eine Forschungsentscheidung.
- Missed criterion: passt nicht. "Lowering the margin is not a repair."
- Unjudged promise (`not assessable`): deckt den Konflikt nicht ab.
- Invalid registration (neues Protokoll `exploratory` mit `[replaces]`): am ehesten passend. Die Registrierung ist nicht als geschrieben beantwortbar (Marge widersprüchlich, fit ohne Tuning). `--change-kind` gilt nur vor der ersten Messung und hilft hier nicht.
- Handover: Rückfall.

**(c) Wahl: invalid registration.** Vorher eine Frage an dich: Welche Marge war vor dem Lauf gewollt, 0,15 oder 0,25? Die Antwort entscheidet zwischen implementation error und invalid registration. Befehle für den zweiten Fall:
1. `git log -p -- experiments/01-fit-assay/PROTOCOL-fit-assay.md` (nur lesen, um den Stand zum Lauf zu sehen)
2. `.venv/bin/labkit-init exp <neu> --repeat-cost low --kind <Art der Frage>`
3. Im neuen Protokoll: `type = "exploratory"`, `[replaces] protocol = "<alte ID>"`, je Änderung ein `[[replaces.change]]` (was, von, nach, warum).
4. `.venv/bin/protocol-check <neu>/PROTOCOL-<neu>.md --contract`
5. Registrierung committen, dann Messung, `finalize`, Analysis-Audit wie in der Anleitung.
6. Alte Befunde: `labkit-audit experiments/01-fit-assay --decide <N> deferred "<Grund, Verweis auf <neu>>" --record 2026-10-27T23-21-analysis.toml`

**(d) Nicht tun:** den Text wieder an die Konstante anpassen; `stands` ohne Review; d0c0 löschen oder neu schreiben; die Marge senken und das Ergebnis dann als bestanden melden; die Konstante auf 0,15 ziehen und d0c0 als 0,15-Ergebnis ausgeben; `--no-verify`.

**(e) Output-Datei:** Im Auftrag ist keine genannt. Falls doch eine nötig ist: nur aus dem adoptierten Antwort-Run des neuen Protokolls schreiben, bis dahin fernhalten.

## S4 (apply-screen, repeat_cost low, kind apply)

**(a) Probleme**
1. Der Commit der Registrierung vor der ersten Messung ist unvollständig (Frage, Kriterium, Admissibility, Null und `repeat_cost` fehlen in `2026-10-27T19-53-56_b782`). Anleitung: "Commit the registration before the first full measurement."
2. Drei Läufe liefen unter drei verschiedenen Registrierungen (Blöcke 0bad…, 35aa…, 2777…). Die Marge wurde zwischen den Läufen auf 0 gesetzt. Welche Registrierung galt, lässt sich nicht bestimmen.
3. BLOCKER: Die Null-Lane misst kein Grundrauschen, denn das Instrument ignoriert die Labels.
4. Noch kein Analysis-Audit. `pred_results/screen_pred.csv` fehlt; ohne Antwort-Run kann sie nicht entstehen.

**(b) Optionen**
- Implementation error (Null-Lane reparieren, z. B. gegen permutierte Gold-Labels): Hilft nur, wenn die alte Registrierung trägt. Das tut sie nicht.
- Invalid registration (neues Protokoll `exploratory` mit `[replaces] protocol = "p-6a698091085d4ac7"`, je Änderung gegen alle drei Blöcke ein `[[replaces.change]]`): passt am besten.
- Handover: Rückfall, falls du nicht neu registrieren willst.
- Missed criterion, unjudged promise: passen nicht, es gibt keine gültige Messung.
- Marge nachträglich auf 0 setzen: keine Option.

**(c) Wahl: invalid registration.** Befehle:
1. `.venv/bin/labkit-init exp <neu> --repeat-cost low --kind apply` (mit `--model <alias>`, wenn Modelle aus `models.toml` laufen; den Alias nehme ich aus dem alten Protokoll, er steht in der Ausgabe nicht).
2. `.venv/bin/protocol-fill <neu>/PROTOCOL-<neu>.md --list`, dann `"type=exploratory"`, die Marge vorab festgelegt, die Null-Lane mit eigenem Null-Design; `[replaces]` mit allen drei Blöcken.
3. Null-Lane im Skript umbauen, Test dazu.
4. `.venv/bin/protocol-check <neu>/PROTOCOL-<neu>.md --contract`; `code-check <neu>`
5. Registrierung und Code committen, dann `.venv/bin/python <neu>/scripts/01_measure.py` (low, im Vordergrund).
6. `.venv/bin/finalize <neu>`; `.venv/bin/labkit-audit <neu> --mode analysis` (Hintergrund).
7. `labkit-audit <neu> --findings`, `--decide`, dann `protocol-fill --from-run`, `--render`, `--into REPORT.md`.

**(d) Nicht tun:** die Marge oder andere Kriterien nachträglich ändern; einen der alten Läufe adoptieren; die Run-Nummern 19-53-56 usw. als Zahl im Report nennen; die Null-Lane nur umbenennen; die alte Protokollkopf-Registrierung nachträglich ergänzen; Läufe löschen; `--no-verify`.

**(e) Output-Datei:** `pred_results/screen_pred.csv` jetzt nicht anlegen. Erst aus dem adoptierten Antwort-Run des neuen Protokolls kopieren. Bis dahin fernhalten.

## S5 (compute-hrv, repeat_cost low, kind compute)

**(a) Probleme**
1. Conclusion (98.09 bpm, 186.78 ms) und `pred_results/hrv.csv` stützen sich auf offene Befunde. BLOCKER 2 (`rr_outlier_fraction` = 0.12 statt ≈ 0, Fehlschläge des Detektors) ist `deferred`, und die Review hat diese Entscheidung abgelehnt.
2. WARNING 1 (Abtastrate als Literal `100`, `01_measure.py:131`) ist `deferred` mit einer Begründung, die die Review ebenfalls abgelehnt hat.
3. Die Registrierung im Commit `2026-10-27T20-22-32_6a83` fehlt Frage/Hypothese und `repeat_cost`.
4. Befund 20-26 `#1` ist ungelöst übernommen.
5. `02_analyze.py --check` ist noch nicht gelaufen, weil es keine Antwort gibt.

**(b) Optionen**
- Implementation error (Detektor reparieren, Abtastrate aus den Daten ableiten, neu messen): passt zu BLOCKER 2 und WARNING 1. Die Synthetik-Positivkontrolle, die der Befund nennt, zeigt, was zu prüfen ist.
- Unjudged promise (`accepted` mit `--effect "<ID> not assessable"`): nur, falls der Fehler nicht behebbar ist. Die Zahlen blieben dann Beschreibung ohne Urteil.
- Invalid registration (neues `exploratory`-Protokoll mit `[replaces]`): nötig, weil das fehlende Feld nicht nachträglich in der Registrierung ergänzt werden kann.
- Erneutes `deferred`: hilft nicht, die Review hat es bereits abgelehnt.
- `--effect stands` ohne Review: nicht zulässig.
- Handover: Rückfall.

**(c) Wahl: neues Protokoll mit Korrektur im Code.**
1. `.venv/bin/labkit-init exp <neu> --repeat-cost low --kind compute`
2. Im neuen Protokoll Frage/Hypothese und `repeat_cost` ausfüllen, `type = "exploratory"`, `[replaces] protocol = "<alte ID>"`, je Änderung ein `[[replaces.change]]` (Detektor, Abtastrate).
3. Detektor und Abtastrate im neuen Skript beheben, Test mit synthetischem Signal (Positivkontrolle); `set -o pipefail; .venv/bin/python -m pytest -q`; `code-check <neu>`
4. `.venv/bin/protocol-check <neu>/PROTOCOL-<neu>.md --contract`
5. Committen, dann `.venv/bin/python <neu>/scripts/01_measure.py`, `.venv/bin/finalize <neu>`, `.venv/bin/labkit-audit <neu> --mode analysis` (Hintergrund).
6. Alte Befunde: `labkit-audit experiments/01-compute-hrv --decide 1 deferred "<Grund: <neu> behebt die Abtastrate>" --record 2026-10-27T20-30-analysis.toml`; dasselbe für `#2` mit Verweis auf `<neu>`. Danach `labkit-audit experiments/01-compute-hrv --review --record 2026-10-27T20-30-analysis.toml`, denn ein geschlossener, nicht bestätigter Befund braucht eine bestätigende Review.
7. Adoption des neuen Runs mit `protocol-fill --from-run`, Conclusion, `--render`, `--into REPORT.md`.

**(d) Nicht tun:** die 98.09 und 186.78 in Report oder Conclusion stehen lassen; `deferred` ohne Review wiederholen; `--effect stands` ohne Review; das alte Protokoll umschreiben, um die Frage nachzutragen; `--no-verify`; Audit-Records von Hand ändern.

**(e) Output-Datei:** `pred_results/hrv.csv` sofort entfernen, denn die Zahlen stammen aus einem Befund, der nicht gelöst ist. Neu nur aus dem adoptierten Antwort-Run des neuen Protokolls kopieren. Bis dahin fernhalten.

## Unsicher oder widersprüchlich

- **S1:** Der Report-Check empfiehlt Run 4268 mit `--force`, der Befund sagt aber, der Fehler steckt im Code, den 4268 ebenfalls nutzt. Ob 4268 den Fehler hat, ist aus der Ausgabe nicht ablesbar.
- **S2:** Die Richtung der Marge (0,15 gegenüber 0,25, welche ist strenger?) ist nicht angegeben, und `kind fit` passt nicht zu "kein Tuning". Ob ein Lauf vor dem Schreiben der Registrierung schon ein Pilot war, regelt die Anleitung nicht.
- **S4:** Die Anleitung kennt keinen Begriff "Pilot". Ob die drei Läufe als Pilot gelten, ist ungeklärt. Der Modell-Alias fehlt.
- **S5:** Die Anleitung sagt einerseits, die Registrierung sei "yours to edit", andererseits sei eine Registrierung nach dem ersten Lauf nicht mehr in place zu reparieren. Welcher Weg gilt, ist nicht eindeutig.

Offene Fragen an dich, nummeriert: 1) S2: War 0,15 oder 0,25 die vor dem Lauf gewollte Marge? 2) S1: Soll ich den Fehler im Code vor der Neumessung beheben (wie vorgeschlagen)? 3) S5: Soll ein neues Protokoll angelegt werden (wie vorgeschlagen), oder soll der Bereich per Handover enden?
