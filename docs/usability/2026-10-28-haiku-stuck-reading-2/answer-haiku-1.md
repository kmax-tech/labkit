Antwort der Instruction-Comprehension-Probe (nur instructions.md und cases.md gelesen, nichts ausgeführt, nichts geschrieben).

Quelle: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-stuck-reading-2/instructions.md (im Folgenden „Anleitung“, mit Zeilenangabe). Glossar: Konklusion = das Conclusion-Feld im Protokoll; Handover = geordnete Übergabe ohne Ergebnis; Gate = Prüfung mit Exit-Code; Freeze = Einfrieren der Registrierung vor dem Lauf.

---

## S1: compute-hrv, repeat_cost low, kind compute

**(a) Probleme**
1. Die Sub-Sample-Verfeinerung schneidet die Peak-Positionen auf das 10-ms-Raster ab (scripts/01_measure.py:113, BLOCKER in 2026-10-27T22-45-analysis.toml, Befund 1). Dadurch enthält rmssd_ms = 26.94 künstlichen Jitter.
2. Das Protokoll zitiert den überholten Lauf 8b74 (PROTOCOL-compute-hrv.md:5, :19, :46, :77). Die Ausgabedatei gehört aber zu Lauf 5de6.
3. [result] zeigt auf 8b74; der Antwort-Lauf laut report-check ist 4268.
4. Kein Analyse-Audit hat den jetzigen Code (f6f4fb122c8d) gesehen.
5. Die Zeile „Recorded results“ weicht von ihrem Rendering ab; zwei Limit-Zeilen aus Record 22-41 sind durch keinen gültigen Record gedeckt.
6. 02_analyze.py --check schlägt fehl (Zahlen nicht im Protokoll).
7. Audit 2026-10-27T22-38-analysis.toml#2 ist „accepted“, aber nie nachverfolgt.
8. Limit #2 (WARNING) behauptet „within physiological measurement precision“, ohne Prüfung.
9. pred_results/hrv.csv existiert, aus dem überholten Lauf 8b74.

Unsicher: Ob der Antwort-Lauf 4268 den Fehler auch hat. Der Befund nennt Lauf 5de6; der Code wurde nach dem Audit geändert. Wahrscheinlich hat 4268 ihn ebenfalls, aber das lese ich nicht sicher aus dem Gelesenen.

**(b) Offene Optionen**
- Implementierungsfehler: Code korrigieren, unter unveränderter Registrierung neu messen, neuen Lauf auditieren, `fixed` mit benannter Änderung (Anleitung :169-171, :271-272). Hilft: ja, das ist hier der Fehler.
- Verfehltes Kriterium: nicht anwendbar, compute hat kein Kriterium.
- Unbeurteilbare Zusage (`--effect "<ID> not assessable"`, :277-279): hilft nicht, der Fehler ist behebbar.
- Ungültige Registrierung, neues Protokoll mit [replaces] (:280-293): hilft nicht, die Registrierung ist nicht das Problem.
- `accepted` mit `--effect stands` für Befund 1 (:180-185): hilft nicht, die Zahl wäre falsch.
- `deferred` (Handover-Weg): nur als Ausweg, wenn der Fehler nicht behoben werden kann.
- Handover („none of these“, :294-310): zulässig, ergibt dann keine Zahl.
- `--from-run 4268 --force`, das report-check vorschlägt: hilft nicht, solange der Fehler im Lauf steckt.

**(c) Befehle in dieser Reihenfolge** (Pfade relativ zum Repo-Root, mit `.venv/bin/` wo nötig)
1. `rm pred_results/hrv.csv`
2. In scripts/01_measure.py die Peak-Positionen als Float halten; Test ergänzen; `.venv/bin/python -m pytest -q`; `code-check experiments/01-compute-hrv`.
3. Committen (nur die eigenen Pfade).
4. `.venv/bin/python experiments/01-compute-hrv/scripts/01_measure.py` (low, Vordergrund).
5. `finalize experiments/01-compute-hrv`
6. `labkit-audit experiments/01-compute-hrv --mode analysis`
7. `labkit-audit experiments/01-compute-hrv --findings`, dann pro Befund `labkit-audit experiments/01-compute-hrv --decide <N> <STATUS> "<GRUND>" --record <neuer Record>`. Vorher die angeforderte Diagnose `refined_peak_fraction_nonint` laufen lassen (:169-170).
8. `protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md "Conclusion=<Antwort>"`, nur mit Zahlen aus dem neuen Lauf.
9. `protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --from-run <neue run_id> --force`, dann `--render`, dann `--into REPORT.md`. Die Zusammenfassung und die Limit-Zeilen schreibe ich selbst aus dem neuen Lauf (:215-226, :234-237).
10. `.venv/bin/python experiments/01-compute-hrv/scripts/02_analyze.py --check` und `report-check experiments/01-compute-hrv` (Exit 0).
11. Erst dann pred_results/hrv.csv aus der Ausgabedatei des adoptierten Laufs kopieren.
12. Commit.

**(d) Nicht tun**
- Lauf 4268 per `--from-run` adoptieren, bevor der Fehler geklärt ist.
- `--effect stands` für Befund 1 oder 2.
- Zahlen 26.05 oder 26.94 von Hand ins Protokoll oder in die CSV schreiben.
- Audit- oder Run-Records von Hand ändern (:311-316).
- `--no-verify`, `--again`, um Freigaben zu erzwingen.

**(e) Ausgabedatei**
pred_results/hrv.csv sofort löschen (:40-46: „remove the output file at once“). Neu schreiben erst aus dem neu adoptierten Lauf, kopiert aus seiner Ausgabe, nicht neu getippt (:38-40).

---

## S2: fit-assay, repeat_cost low, kind fit

**(a) Probleme**
1. Nach dem Lauf d0c0 wurde die Registrierung geändert (Text und Kriterium von 0.15 auf 0.25). Anleitung :111-113: „Set its criteria and constants before seeing results; later changes do not answer the original registered question.“ intent-check blockt dies.
2. Schon beim Registrieren waren Text (0.15) und Konstante (0.25) uneinig. Die Registrierung war damit in sich widersprüchlich, bevor der Lauf kam.
3. 02_analyze.py --check schlägt fehl (Promise-Block d37c… gegen f571…).
4. WARNING 1: Die Registrierung beschreibt ein abgestimmtes Instrument, der Code tut kein Tuning (scripts/01_measure.py:139).
5. WARNING 2: Die Margin im Protokoll wurde nach dem Lauf geändert (PROTOCOL-fit-assay.md:22).
6. Die „stands“-Limits auf den akzeptierten WARNINGs sind nicht reviewed.

Unsicher: Welche Margin registriert war, entscheidet weder Gate noch Anleitung. Die Anleitung sagt auch nicht, was gilt, wenn Text und Konstante schon beim Registrieren nicht übereinstimmen.

**(b) Offene Optionen**
- Implementierungsfehler: Code an die Registrierung anpassen, neu messen (:169-170). Hilft nur, wenn 0.15 registriert war. Nicht mit „Margin senken“ verwechseln: „Lowering the margin is not a repair“ (:275-276).
- Verfehltes Kriterium: das Ergebnis berichten. Hilft nur, wenn die Registrierung eindeutig ist.
- Ungültige Registrierung, neues Protokoll mit `type = "exploratory"` und [replaces] (:280-293). Passt, wenn sich nicht klären lässt, was gemeint war. Der alte Lauf bleibt sichtbar.
- Unbeurteilbare Zusage (:277-279): für den Fall, dass die Frage offen bleibt.
- Handover (:294-310): zulässig.
- `--review` für `stands` (:199-206): hilft erst, wenn die Registrierung feststeht.
- Text zurück auf 0.15 setzen, ohne Klärung: hilft nicht, das wäre dieselbe Änderung nach dem Sehen.

**(c) Befehle**
Zuerst eine Frage an dich, weil es eine Forschungsentscheidung ist: Welche Margin war bei der Registrierung gemeint, 0.15 oder 0.25?
Lesend vorher: `git log --oneline -- experiments/01-fit-assay/PROTOCOL-fit-assay.md` und `git show <Commit des ersten Messlaufs>:experiments/01-fit-assay/PROTOCOL-fit-assay.md`.
- Falls 0.15 registriert war: Protokolltext auf den committeten Stand zurücksetzen; die Konstante im Skript auf 0.15 setzen; `.venv/bin/python -m pytest -q`; `code-check experiments/01-fit-assay`; committen; `.venv/bin/python experiments/01-fit-assay/scripts/01_measure.py`; `finalize experiments/01-fit-assay`; `labkit-audit experiments/01-fit-assay --mode analysis`; Befunde mit `--decide` entscheiden; bei `stands` `labkit-audit experiments/01-fit-assay --review --record <Record>`.
- Falls 0.25 gemeint war: `labkit-init exp <neuer-name> --kind fit --repeat-cost low`, mit `type = "exploratory"` und [replaces] auf den alten Protokoll-Stand registrieren, Konflikt im Protokoll erklären, committen, erst dann messen.

**(d) Nicht tun**
- Den 0.25-Text als Registrierung stehen lassen oder die Konstante nachträglich an den Hash anpassen.
- `--effect stands` ohne Review.
- Lauf d0c0 löschen oder den Audit-Record umschreiben.
- Eine Margin wählen, weil man die Ergebnisse gesehen hat.
- `--no-verify`.

**(e) Ausgabedatei**
Die Aufgabe nennt keine Ausgabedatei. Falls eine genannt wird: sie bleibt weg, bis Registrierung und Lauf geklärt sind (:40-46).

---

## S4: apply-screen, kind apply, kein Modell im Lauf

**(a) Probleme**
1. Drei Läufe (19-53-56, 19-55-02, 19-55-33) liefen unter drei verschiedenen Registrierungen. Die Margin wurde zwischen den Läufen auf 0 gesetzt, und die Registrierung wurde erst danach committet. Anleitung :111: „Commit the registration before the first full measurement.“
2. Der erste Registrierungs-Commit fehlt Pflichtfelder: Frage, Erfolgskriterium, Zulassungsbedingung, Nullbedingung, repeat_cost.
3. Die Null-Lane misst kein Grundrauschen: sie ist mit der registrierten Lane identisch (finalize-Gate).
4. Kein Analyse-Audit, und 02_analyze.py --check schlägt fehl, weil keine Antwort existiert.
5. pred_results/screen_pred.csv existiert nicht.

Unsicher: Anleitung :80-81 sagt „A new area is not a way to discard an earlier result“, und :282-283 verlangt für eine Neu-Registrierung `labkit-init exp <new-name>`. Ich lese beides so, dass die alten Läufe sichtbar bleiben müssen. Ob das bei dieser Lage erlaubt ist, steht nicht eindeutig da.

**(b) Offene Optionen**
- Neu registrieren, nach dem Gate-Text: neues Protokoll, `type = "exploratory"`, vor dem ersten Lauf committet, [replaces] auf p-6a698091085d4ac7 mit je einem `[[replaces.change]]` gegen jede der drei Registrierungen. Hilft: ja, das ist der einzige Weg, auf dem eine Zahl wieder eine registrierte Frage beantwortet. Die Null-Lane muss dann eigene Nullbedingung haben (Gold-Labels permutiert). „exploratory“ bestätigt nichts (:54).
- Handover (:294-310): zulässig, ohne Zahl.
- Lauf 19-55-33 per `--from-run` adoptieren, wie es die letzte Zeile der Gate-Ausgabe nahelegt: hilft nicht, denn welche Registrierung galt, lässt sich nicht sagen.
- Nur fehlende Felder nachtragen und committen: hilft nicht, das ist Nachträglichkeit.
- Analyse-Audit zuerst laufen lassen: nötig, aber nutzlos, solange die Registrierung ungültig ist.

**(c) Befehle**
Vorher zwei Fragen an dich: Welches Modell beziehungsweise welche Vorhersagen werden angewandt? Welche Margin und welches Null gelten? Das sind Forschungsentscheidungen.
1. Keine weiteren Läufe.
2. `labkit-init exp <neuer-name> --repeat-cost low --kind apply` (ohne `--model`, da kein Modell im Lauf ist).
3. `protocol-fill <PROTOCOL-neu> --list` und `protocol-check <PROTOCOL-neu> --contract`.
4. `protocol-fill <PROTOCOL-neu> "type=exploratory" "C1 sentence=<...>" "<Label>=<...>"`, dazu [replaces] mit `protocol = "p-6a698091085d4ac7"` und je einem `[[replaces.change]]` gegen die Blöcke 0bad46b0ae1a, 35aae07be74c, 2777d8b2fc13. Nullbedingung mit eigenem Null im selben Lauf.
5. `.venv/bin/python -m pytest -q`, `code-check <neuer-name>`, `.venv/bin/python <neuer-name>/scripts/01_measure.py --show 2`.
6. Registrierung committen, bevor der Vollauf startet.
7. `.venv/bin/python experiments/<neuer-name>/scripts/01_measure.py` (low, Vordergrund).
8. `finalize <neuer-name>`, `labkit-audit <neuer-name> --mode analysis`, Befunde mit `--decide` entscheiden.
9. `protocol-fill <PROTOCOL-neu> "Conclusion=<...>"`, dann `--from-run <run_id>`, `--render`, `--into REPORT.md`.
10. Im alten Protokoll die Vorgänger-Blockaden `deferred` setzen mit Verweis auf das neue (:285-286).

**(d) Nicht tun**
- Einen der drei Läufe als Antwort adoptieren oder in den Report schreiben.
- Die Margin-Änderung als Registrierung ausgeben.
- Die Registrierung nachträglich umschreiben oder die Commit-Historie verändern.
- Die Null-Lane im alten Protokoll nachträglich reparieren.
- screen_pred.csv erzeugen oder von Hand schreiben.
- `--no-verify`.

**(e) Ausgabedatei**
pred_results/screen_pred.csv existiert nicht und wird jetzt nicht erzeugt. Sie kommt nur aus der Ausgabe des adoptierten Laufs des neuen Protokolls, kopiert. Bei Handover bleibt sie weg, und der Report sagt es.

---

## S5: compute-hrv, repeat_cost low, kind compute (zweite Lage)

**(a) Probleme**
1. Befund 2 (BLOCKER, Peak-Detektor findet Fehlbeats, rr_outlier_fraction 0.12) ist `deferred`; ein Review hat die Zurückstellung abgelehnt (report-check: „earlier rejected“).
2. Die Konklusion nennt trotzdem 98.09 bpm und 186.78 ms, obwohl der Detektor laut Befund nicht validiert ist.
3. Befund 1 (WARNING, 100 Hz fest verdrahtet, scripts/01_measure.py:131) ist `deferred`; das Review hat abgelehnt, die Begründung wiederholt nur die Annahme.
4. Der Befund 2026-10-27T20-26-analysis.toml#1 (Detektor nie validiert) bleibt offen.
5. pred_results/hrv.csv enthält die zwei Zahlen, obwohl ein BLOCKER gegen den Code, der sie erzeugt hat, offen ist.
6. Die Registrierung 20-22-32_6a83 fehlt Frage und repeat_cost.
7. 02_analyze.py --check schlägt fehl (keine Antwort).

Unsicher: Ob die Fehlbeats ein Implementierungsfehler sind oder eine Grenze des Verfahrens. Der Befund nennt eine Prüfung (synthetische Positivkontrolle, rr_outlier_fraction ungefähr 0), die das klären könnte. Außerdem: Ob die Registrierung ohne Frage ungültig ist oder nur unvollständig, lese ich aus der Anleitung nicht eindeutig ab.

**(b) Offene Optionen**
- Implementierungsfehler: Detektor korrigieren, mit synthetischer Positivkontrolle testen, neu messen, neu auditieren, mit `fixed` begründen (:169-171). Hilft: ja, und der Befund selbst nennt die Prüfung. Das ist der richtige erste Weg.
- Unbeurteilbare Zusage (`--effect "<ID> not assessable"`): hilft nur, wenn die Prüfung nicht gelingt. Die Begründung „keine Ground Truth“ ist abgelehnt, und die Zahlen wären dann nur Beschreibung.
- Handover (:294-310): zulässig, wenn nichts gelingt; dann keine Zahl und keine CSV.
- Erneut `deferred`: hilft nicht, die neue Entscheidung ist ungeprüft (report-check).
- `accepted` mit `--effect stands` und Review: hilft nicht, das Review hat die Begründung schon abgelehnt.
- `--again`: nicht zulässig (:211).
- Ungültige Registrierung, neues Protokoll (:280-293): nur erwägen, falls die fehlende Frage tatsächlich die Registrierung ungültig macht.

**(c) Befehle**
1. `rm pred_results/hrv.csv`
2. Konklusion im Protokoll entfernen oder ohne Zahlen neu setzen: `protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md "Conclusion=<ohne Zahlen>"`
3. `labkit-audit experiments/01-compute-hrv --findings` (nur lesen)
4. In scripts/01_measure.py:65 den Detektor korrigieren; Test mit synthetischer Positivkontrolle; `.venv/bin/python -m pytest -q`; `code-check experiments/01-compute-hrv`
5. Committen.
6. Zeitschritt aus den Rohdaten lesen (nur lesend), dann Befund 1 entscheiden: `fixed`, wenn das Raster bestätigt ist, sonst `accepted` mit Effekt.
7. `.venv/bin/python experiments/01-compute-hrv/scripts/01_measure.py`
8. `finalize experiments/01-compute-hrv`, `labkit-audit experiments/01-compute-hrv --mode analysis`
9. Befunde entscheiden; bei `stands` `labkit-audit experiments/01-compute-hrv --review --record <Record>`.
10. Konklusion, `--from-run <neue run_id> --force`, `--render`, `--into REPORT.md`, `02_analyze.py --check`, `report-check`.
11. Erst dann pred_results/hrv.csv kopieren.
12. Committen.
Falls der Detektor nicht korrigierbar ist: `protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --handover --why "<...>" --tried "<...>" --into REPORT.md`, nach den `deferred`-Entscheidungen mit Begründung.

**(d) Nicht tun**
- pred_results/hrv.csv stehen lassen.
- 98.09 bpm oder 186.78 ms als Ergebnis schreiben.
- Erneut `deferred` ohne neues Review.
- `--again` oder `--effect stands` ohne Review.
- Die Zahl mit „nicht beurteilbar“ retten, weil Ground Truth fehlt.
- Die 100-Hz-Annahme ohne Beleg akzeptieren.
- `--no-verify`.

**(e) Ausgabedatei**
pred_results/hrv.csv sofort löschen (:40-46). Neu schreiben erst aus dem neu adoptierten Lauf, nicht aus der alten Messung.

---

## Offene Punkte für dich (bitte nummeriert beantworten)
1. S2: Welche Margin war bei der Registrierung gemeint, 0.15 oder 0.25?
2. S4: Neu registrieren (dann: welches Modell, welche Margin, welches Null) oder Handover?
3. S1: Refinement-Fehler korrigieren und neu messen, oder Handover?
4. S5: Detektor-Fix mit synthetischer Positivkontrolle versuchen, oder direkt Handover?

## Anmerkungen zur Anleitung (Unklarheiten)
- :80-81 („A new area is not a way to discard an earlier result“) und :282-283 (Neu-Registrierung über `labkit-init exp <new-name>`) lassen offen, ob eine Neu-Registrierung in S4 erlaubt ist.
- Die Anleitung sagt nicht, was gilt, wenn Text und Konstante einer Registrierung schon beim Registrieren nicht übereinstimmen (S2).
- :14-15 spricht von „the three choices below“, es folgen aber mehr Abschnitte. Das ist nur ein Formfehler.
- Die Reihenfolge „Befund fixed“ und „neuer Lauf“ ist in :169-178 gut beschrieben, aber nicht, wann ein alter, bereits `deferred`-Befund einer Prüfung bedarf (S5).

Nichts ausgeführt, nichts geschrieben.
