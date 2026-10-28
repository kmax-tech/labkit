Bericht der Instruktions-Probe. Gelesen nur: /Users/max/projects/labkit-stuck-clarity/docs/usability/2026-10-28-haiku-stuck-reading/instructions.md und cases.md (dieselbe Verzeichnis). Zeilenangaben "Z." beziehen sich auf instructions.md, "cases.md:NN" auf cases.md. Keine Datei geschrieben.

Vorab zwei Begriffe: Adoption = Übernahme eines Laufs als Ergebnis (`protocol-fill --from-run`). Handover = geordneter Abbruch ohne Ergebnis (`protocol-fill --handover`).

## S1 compute-hrv (low, compute)

(a) Probleme
1. Instrumentfehler: Die Sub-Sample-Verfeinerung wird auf das 10-ms-Raster zurückgeschnitten (cases.md:40, Punkt scripts/01_measure.py:113/:123). Die RMSSD 26,94 aus Lauf 5de6 enthält künstlichen Jitter. BLOCKER, unentschieden.
2. Das Protokoll berichtet den überholten Lauf 8b74 (26,053) in Summary, Runs-Liste und `[result] run` (cases.md:41, cases.md:39). Seither hat sich der Code geändert.
3. Kein Analysis-Audit deckt den aktuellen Code (cases.md:42). `02_analyze.py --check` schlägt fehl (cases.md:46).
4. Recorded-results-Zeile und zwei Limit-Zeilen sind nicht mehr gedeckt (cases.md:43–45). Der Befund 38-analysis #2 ist "accepted" und nicht weiterverfolgt (cases.md:47).
5. pred_results/hrv.csv ist aus 8b74 geschrieben, also aus einer Zahl, die der aktuelle Code nicht erzeugt.
6. Der Commit wird abgelehnt.

(b) Optionen
- Implementierungsfehler (Code korrigieren, unter unveränderter Registrierung neu messen, neu auditieren; `fixed` nennt die Änderung, cases.md:12). Hilft. Der Code führt die Verfeinerung nicht aus, was Z. 40–45 und der Befundtext als Implementierungsfehler lesbar machen. Unsicher: der Audit nennt den Befund "new class" (cases.md:40), keine der vier Klassen.
- "Unjudged promise" (`--effect "<ID> not assessable"`): trifft nicht zu, Compute hat keine Versprechen (cases.md:42, "promises none").
- Ungültige Registrierung, neues Protokoll mit `[replaces]`: hilft nicht, die Registrierung ist nicht falsch, der Code ist es.
- `--effect stands` auf dem BLOCKER: nein. Z. 179–184 erlauben "stands" nur, wenn das Urteil unter der Grenze gilt. Hier verfälscht der Fehler die Zahl.
- `deferred`: nein. Es lässt den Befund offen (Z. 201–205 und cases.md:40).
- `protocol-fill --from-run 2026-10-27T22-46-40_4268 --force` (cases.md:39): nein. Dieser Lauf nutzt den fehlerhaften Code. Laut Z. 193 ist `--force` nur für eine Änderung der Konklusion nach Adoption gedacht. Die Ausgabe widerspricht dem.
- Handover: zulässiges Ende, falls der Fix nicht trägt (Z. 290–301).

(c) Befehle, in dieser Reihenfolge
1. Im Code `peaks_refined` als Gleitkomma-Array halten (scripts/01_measure.py:113), Handfälle testen: `.venv/bin/python -m pytest -q`
2. `code-check experiments/01-compute-hrv`
3. `git add experiments/01-compute-hrv/scripts/01_measure.py` (plus Test), `git commit -m "01-compute-hrv: keep refined peak positions as floats"` mit Co-Authored-By-Zeile
4. `.venv/bin/python experiments/01-compute-hrv/scripts/01_measure.py` (low, im Vordergrund)
5. `finalize experiments/01-compute-hrv`
6. `labkit-audit experiments/01-compute-hrv --mode analysis`
7. `labkit-audit experiments/01-compute-hrv --findings`, dann pro Befund `--decide N <STATUS> "<Grund>" --record <neue Record>`. BLOCKER 1 mit `fixed` samt Änderung.
8. `protocol-fill experiments/01-compute-hrv/PROTOCOL-compute-hrv.md --from-run <neuer Lauf>` (ohne `--force`)
9. `protocol-fill ... --render`, dann `protocol-fill ... --into REPORT.md`. Summary und Limit-Zeilen aus dem neuen Lauf neu schreiben, nicht abtippen (Z. 226–232).
10. `02_analyze.py --check`, dann `report-check experiments/01-compute-hrv`
11. Commit: Protokoll, Report, Audit-Records und Run-Dateien gemeinsam stagen.

Unsicher: ob der Befund 2 (überholter Lauf) durch die Neu-Adoption erledigt ist; ob eine Konklusionsänderung bei Neu-Adoption `--force` braucht (Z. 188–196 gegen Z. 214–217); ob die Diagnose `refined_peak_fraction_nonint` (cases.md:40) einen eigenen Befehl hat, den die Ausgabe nicht nennt.

(d) Nicht tun: `--force` (Z. 193); `stands`; `deferred`; Zahlen tippen (Z. 228); Läufe oder Audit-Records von Hand ändern (cases.md:25–27 / Z. 25–27); Läufe löschen (Z. 303–305, "Preserve run evidence"); `--no-verify`.

(e) pred_results/hrv.csv: nicht mit 8b74 committen. Nach gültigem Lauf die eigene Ausgabedatei des Laufs an den Task-Pfad kopieren, nicht neu rechnen (Z. 35–45). Gibt es keinen gültigen Lauf, die Datei entfernen und im Report begründen.

## S2 fit-assay (low, fit)

(a) Probleme
1. Nach dem Lauf d0c0 wurde die Marge im Text von 0.15 auf 0.25 geändert (cases.md:87, cases.md:75). Das verletzt "Set its criteria and constants before seeing results" (Z. 111–112). BLOCKER "intent-check".
2. Die Registrierung selbst war widersprüchlich: Text 0.15, Konstante 0.25 (Ausgangssituation). Der Lauf nutzte 0.25. Welches Kriterium registriert war, ist nicht eindeutig.
3. WARNING 2 (PROTOCOL :22) steht als "stands" ohne Review da (cases.md:89–90).
4. WARNING 1: Die Registrierung beschreibt ein abgestimmtes Instrument, der Code tut das nicht (01_measure.py:139, cases.md:72).
5. `02_analyze.py --check` schlägt aus demselben Grund fehl (cases.md:88). Der Commit wird abgelehnt.

(b) Optionen
- Befunde `accepted` mit `--effect "C1 not assessable"` (Z. 74, 182–183). Hilft für beide WARNINGs, weil "not assessable" keine Review-Pflicht auslöst (Z. 209). "stands" bräuchte ein Review und ist hier nicht passend.
- Ungültige Registrierung, neues exploratives Protokoll mit `[replaces]` und einer `[[replaces.change]]` je Änderung (Z. 272–285). Passt, weil "incompatible definitions" (Z. 275–277) auf zwei Margen zutrifft. Forschungsentscheidung, daher Nutzerfrage.
- Handover (Z. 286–301). Hilft jetzt, ist ein ehrlicher Abschluss ohne Zahl.
- Implementierungsfehler: trifft nicht zu. Ein Registrierungsfehler ist kein Codefehler, und Nachtuning wäre ein neuer Lauf nach Sicht.
- Die Marge wieder auf 0.25 setzen oder das Kriterium als erfüllt werten: nein.
- Unsicher: ob das Zurücknehmen des Textes auf den Erstmessungs-Stand den intent-check wieder herstellt. Die Ausgabe nennt nur einen Hash, keine Regel dazu.

(c) Befehle
1. `git log --oneline -- experiments/01-fit-assay/PROTOCOL-fit-assay.md`, dann den Commit der Erstmessung suchen und `git show <sha>:experiments/01-fit-assay/PROTOCOL-fit-assay.md` lesen.
2. Den Text der C1-Zeile und des Kriteriums auf den Erstmessungs-Stand zurücknehmen, eigener Commit: `git commit -m "01-fit-assay: restore registration text as committed before run d0c0"`.
3. `labkit-audit experiments/01-fit-assay --decide 1 accepted "<Grund>" --effect "C1 not assessable" --record experiments/01-fit-assay/audits/2026-10-27T23-21-analysis.toml`, dasselbe für 2.
4. `protocol-fill experiments/01-fit-assay/PROTOCOL-fit-assay.md --handover --why "<was blockiert, ohne Lauf-IDs>" --tried "<was versucht wurde>" --into REPORT.md`
5. Stagen: REPORT.md, Protokoll, Handover-Record, Audit-Record. Dann `git commit`.

(d) Nicht tun: Text oder Konstante erneut ändern; mit 0.15 oder 0.25 nachmessen; `--force`; "stands" ohne Review; d0c0 als bestätigt melden; Lauf löschen; `--no-verify`.

(e) Im Task ist keine Ausgabedatei genannt. Falls doch eine verlangt ist: nicht aus d0c0 erzeugen. Der Handover-Block nennt keine Zahl, und der Report sagt, warum die Datei fehlt.

## S4 apply-screen (low, apply)

(a) Probleme
1. Drei Erstmessungen liefen unter drei verschiedenen Registrierungen (cases.md:117). Die Registrierung wurde während der Läufe gefüllt und erst danach committed. Das verletzt "Commit the registration before the first full measurement" (Z. 111).
2. Der Commit der Erstmessung enthält keine Frage, kein Kriterium, keine Admissibility- oder Null-Bedingung (cases.md:116). Das ist "No run without an intent paragraph".
3. Die Null-Lane ist identisch mit der registrierten Lane und misst kein Rauschen (cases.md:118). Die Null-Bedingung muss im selben Lauf liegen (Z. 97–98).
4. Die Marge wurde zwischen den Läufen auf 0 gesetzt, nachdem Ergebnisse sichtbar waren. "Lowering the margin is not a repair" (Z. 266–268), und eine nachträglich gesetzte Schwelle beantwortet keine registrierte Frage (cases.md:13 analog).
5. Kein Analysis-Audit, kein Ergebnis, `--check` exit 1 (cases.md:119–120, cases.md:107).
6. pred_results/screen_pred.csv existiert nicht.

(b) Optionen
- Neues exploratives Protokoll mit `[replaces]` (cases.md:117, Z. 272–285). Formal passend, weil die Registrierung nicht als geschrieben beantwortbar ist. Ein solches Ergebnis wäre aber exploratorisch, und die Margen-Änderung nach Sicht lässt sich nicht heilen. Forschungsentscheidung, daher Nutzerfrage.
- Handover (cases.md:117 zweite Option, Z. 286–301). Hilft jetzt und ist der ehrliche Abschluss ohne Zahl.
- Implementierungsfehler (Null-Lane): Der Code-Fix wäre möglich, verlangt aber "unter unveränderter Registrierung". Die gibt es nicht. Allein hilft das nicht.
- `protocol-fill --from-run 2026-10-27T19-55-33_a71c` (cases.md:120): nein. Es wählt eine von drei Registrierungen als Antwort.
- Analysis-Audit, um die Lücke zu schließen: nein, er prüft nur eine ungültige Grundlage.
- Unsicher: ob "keine Registrierung zum ersten Lauf" unter "invalid registration" fällt oder nur unter den Intent-Blocker. Die Ausgabe und die Regeln geben dazu keine klare Zuordnung.

(c) Befehle
1. Nutzer fragen: neues exploratives Protokoll oder Abbruch? (Forschungsentscheidung)
2. Bei Abbruch: `protocol-fill experiments/01-apply-screen/PROTOCOL-apply-screen.md --handover --why "<Registrierung nach Sicht geändert; Erstmessungen nicht eindeutig zuordenbar; Null-Bedingung misst kein Rauschen>" --tried "<Versuche, ohne Lauf-IDs>" --into REPORT.md`
3. Stagen: REPORT.md, Protokoll, Handover-Record, verbleibende Audit-Belege. Dann `git commit`.
4. Nur bei Neustart: `labkit-init exp <neuer-name> --repeat-cost low --kind apply`, Null-Bedingung und Kriterium vor dem ersten Lauf committen, dann messen.

(d) Nicht tun: `--from-run` auf eine der drei Läufe; einen Lauf als Ergebnis melden; screen_pred.csv aus einem Lauf oder von Hand erzeugen; die Marge erneut ändern; Lauf-Dateien löschen (Z. 303–305); Lauf-IDs im Handover-Text (Z. 297); `--no-verify`.

(e) Nichts erzeugen. Die Datei existiert nicht, es gibt nichts zu entfernen (Z. 40–45 gilt nur für bestehende Ausgaben). Der Report nennt das fehlende Deliverable und den Grund ohne Zahl.

## S5 compute-hrv (low, compute)

(a) Probleme
1. Befund 2 (Peak-Detektor findet falsche Schläge, rr_outlier_fraction 0.12 gegen ≈0) ist `deferred`, obwohl ein Review das abgelehnt hat (cases.md:166). Das ist der Commit-Blocker.
2. WARNING 1 (Abtastrate fest auf 100, 01_measure.py:131) ist ebenfalls `deferred` mit einem abgelehnten Review (cases.md:164).
3. Konklusion nennt 98,09 bpm und 186,78 ms, und pred_results/hrv.csv enthält sie. Beide Werte hängen laut Befund direkt an der festen Abtastrate und am fehlerhaften Detektor (cases.md:164).
4. Die Erstmessung (Commit 6a83) hat keine Frage und kein repeat_cost (cases.md:162). Das verletzt "No run without an intent paragraph".
5. `02_analyze.py --check` schlägt fehl, weil noch keine Adoption existiert (cases.md:163).

(b) Optionen
- Implementierungsfehler (Detektor, 01_measure.py:65): Code korrigieren, neu messen, neu auditieren; `fixed` nennt die Änderung (cases.md:142). Passt zum Befund. Hilft aber nur, wenn die Registrierung trägt, was Punkt 4 fraglich macht.
- `--effect "<ID> not assessable"` (cases.md:144): ehrlicher Rest, falls der Fix nicht trägt. Zahlen nur als Beschreibung, kein Urteil. Unsicher, wie die ID bei einer Compute-Registrierung ohne Versprechen lautet.
- Erneutes `deferred`: nein. Ohne bestätigendes Review gilt es nicht (Z. 201–205).
- `--review` (cases.md:164): fragt einen zweiten Auditor. Hilft nur mit neuer Evidenz, etwa Zeilenzahl und Zeitschritt. Mit dem Grund "100 Hz" allein wird es wieder abgelehnt.
- Neues exploratives Protokoll mit `[replaces]` (cases.md:145): wegen Punkt 4 denkbar. Die Ausgabe nennt keinen Weg für "Frage fehlt im ersten Commit". Unsicher, Nutzerentscheidung.
- Handover (Z. 290–301): zulässig, falls der Fix nicht gelingt.
- Konklusion so stehen lassen: nein. Z. 208 ("Changing only the Conclusion does not require another measurement") gilt nicht, weil die Zahlen vom fehlerhaften Detektor abhängen.

(c) Befehle
1. Nutzer fragen: Fortsetzung mit Fix (dann Punkt 2 bis 6) oder neues exploratives Protokoll? (Forschungsentscheidung, Punkt 4)
2. `labkit-audit experiments/01-compute-hrv --findings --record experiments/01-compute-hrv/audits/2026-10-27T20-30-analysis.toml`
3. Detektor in scripts/01_measure.py:65 korrigieren, Abtastrate aus den Zeitstempeln statt 100 (:131). Test auf synthetischer Kontrolle. `code-check experiments/01-compute-hrv`
4. Eigener Commit, dann `.venv/bin/python experiments/01-compute-hrv/scripts/01_measure.py`, `finalize experiments/01-compute-hrv`, `labkit-audit experiments/01-compute-hrv --mode analysis`
5. Befunde: `--decide 2 fixed "<Änderung>"` und `--decide 1 fixed "<Abtastrate aus Daten: Zeilenzahl, Zeitschritt>"`, jeweils mit `--record` des neuen Records.
6. Ist BLOCKER 2 nicht behebbar: `--decide 2 accepted "<Grund>" --effect "<ID> not assessable"`, Konklusion nur als Beschreibung.
7. `protocol-fill ... --from-run <neuer Lauf>`, `--render`, `--into REPORT.md`, `02_analyze.py --check`, `report-check experiments/01-compute-hrv`.

(d) Nicht tun: `deferred` wiederholen; 98,09 bpm und 186,78 ms stehen lassen; `--effect stands` ohne Review; die Registrierung nachträglich im ersten Commit ergänzen; `--no-verify`.

(e) pred_results/hrv.csv mit 98,09/186,78 nicht committen. Nach einem gültigen Lauf die Ausgabedatei des Laufs kopieren. Gibt es keinen, die Datei entfernen (Z. 40–45).

## Wo die Anleitung unklar ist oder sich widerspricht

- S1: Die Ausgabe schlägt `--force` vor, Z. 193 erlaubt es nur für eine Konklusionsänderung. Der Vorschlag würde einen Lauf mit offenem BLOCKER adoptieren.
- S1: Der Befund "new class" passt in keine der vier Klassen der Ausgabe.
- S1/S5: "not assessable" setzt Versprechen voraus. Bei Compute ohne Versprechen ist unklar, wie es greift.
- S2: Ob eine Rücknahme des Textes den intent-check wieder herstellt, sagt die Anleitung nicht.
- S4/S5: Die Anleitung behandelt eine fehlende Registrierung zum ersten Lauf nicht ausdrücklich. Die Zuordnung zu "invalid registration" bleibt offen.
- Gesamt: "fixed" (Z. 168–170) und "stands" (Z. 179–184) sind nicht klar gegeneinander abgegrenzt, wenn ein Fehler nur teilweise die Zahl verfälscht.

## Offene Punkte für den Nutzer

1. S1: Fix des Detektors-Verfeinerung wie beschrieben umsetzen, ja/nein?
2. S2: Neues exploratives Protokoll (Marge-Frage weiterverfolgen) oder Handover?
3. S4: Neues exploratives Protokoll mit eigener Null-Bedingung oder Handover?
4. S5: Fix des Detektors und der Abtastrate, oder neues exploratives Protokoll, weil die Erstmessung keine Frage trug?
5. S1/S4/S5: Welche Ausgabedateien sollen aus welchem Lauf kommen, falls die Läufe bestehen bleiben?
