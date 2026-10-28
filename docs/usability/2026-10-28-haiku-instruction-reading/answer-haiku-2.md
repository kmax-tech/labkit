Lesebericht zur Instruktions-Probe (nur instructions.md und cases.txt gelesen). Zeilenangaben „Z." beziehen sich auf /Users/max/projects/labkit-sab-cases-main/docs/usability/2026-10-28-haiku-instruction-reading/instructions.md. Abkürzungen: kind = Art der Aussage (fit, apply, compute); repeat_cost = Kosten einer Wiederholung (low, high); type = wissenschaftlicher Anspruch (confirmatory, exploratory); A/B/C = Versprechen (Zulassungsbedingung, registrierter Zweig, Kriterium); BLOCKER/WARNING = Befunde des Audits. [explizit] = steht so im Text; [Urteil] = meine Ableitung.

### Fall 1: RandomForest, fünf Sekunden, Vorhersage ungelabelter Zeilen
- kind = fit [explizit]: „A RandomForest fitted in seconds is fit, usually at low repeat cost." (Z. 57; Z. 53–55).
- repeat_cost = low [explizit] (Z. 57, Z. 50).
- type = confirmatory [Urteil]: Frage und Kriterium waren vor den Ergebnissen festgelegt (Z. 51). Der Text sagt zusätzlich: „Writing a type does not establish its scientific validity." (Z. 51–52).
- Kriterium owed: ja [explizit] („Neither low nor exploratory removes a fit/apply's criterion or audits.", Z. 59; Z. 88–90).
- Analyse-Audit owed: ja [explizit] („at either cost", Z. 151).
- Preflight-Audit und Freeze: nicht owed [explizit] („At low, no freeze or preflight audit is owed.", Z. 136).
- Nächste Schritte: `labkit-init exp <name> --repeat-cost low --kind fit` (Z. 75); `protocol-fill <PROTOCOL> --list` und `protocol-check <PROTOCOL> --contract` (Z. 83–84); Felder vor dem Lauf füllen (Z. 85–90); Registrierung committen (Z. 101–102); `code-check <area>` und Bereichstest (Z. 110–111); `.venv/bin/python <area>/scripts/01_measure.py` im Vordergrund (Z. 139–140); `finalize <area>` und `labkit-audit <area> --mode analysis` (Z. 151); `labkit-audit <area> --findings`, dann `--decide` (Z. 153–158); `protocol-fill <PROTOCOL> "Conclusion=…"` (Z. 179).
- --show: nur für estimator/prompt-Skelette (Z. 107–109); ob ein RandomForest-Skelett so heißt, geht aus dem Text nicht hervor.
- Zulässige Aussage: keine Erfolgsaussage vor Finalisierung, Analyse-Audit und Entscheidungen. Messwerte bleiben Beschreibung (Z. 175).
- Lücke: Z. 54–56 verlangt Auswertung auf gelabelten Held-out-Zeilen. Welche Zeilen das sind, sagt der Text nicht.

### Fall 2: Zählung lokaler Dokumente, sechs Stunden Laufzeit
- kind = compute [explizit]: keine Modellanpassung, keine Beurteilung von Vorhersagen (Z. 49, Z. 55–56).
- repeat_cost = high [Urteil auf Basis von Z. 50]: „high: a repeat needs protection by a preflight audit and freeze." Gemessen werden die Kosten der Messung, nicht der Gesamtaufgabe. Sechs Stunden, „nicht leichtfertig wiederholen" passen dazu.
- type: nicht vorgegeben. Die Definitionen (Z. 51) passen für ein reines Zählen nicht sauber. Lücke.
- --show: nicht owed [explizit] („compute has no --show", Z. 108–109).
- --probe: nicht owed [explizit] („Compute has no --probe; test its calculation.", Z. 125–126). Stattdessen die Berechnung testen.
- preflight: owed [explizit] (`preflight <area>`, Z. 130–131).
- preflight audit: owed [explizit] (`labkit-audit <area> --mode preflight`; Eintrag `preflight_audit` im Protokollkopf, Z. 131–133).
- freeze: owed [explizit] (`labkit-init exp <name> --report`, Pflichtfelder, `frozen = true`, Z. 133–134).
- Ablauf: committen (Z. 138); `.venv/bin/runlog start <area> -- .venv/bin/python <area>/scripts/01_measure.py` (Z. 141–143); überwachen mit `.venv/bin/runlog <area> --wait` (Z. 143–144); Audit als Hintergrundaufgabe (Z. 146–147); danach `finalize` und Analyse-Audit (Z. 151).
- Lücke: Der Skriptname für compute fehlt („the stamped script", Z. 139). Was der Analyse-Audit bei einer reinen Zählung prüft, ist unklar.

### Fall 3: unveränderter LLM gegen Gold-Labels, viele Stunden pro Messung
- kind = apply [explizit] (Z. 56–58: „An unchanged LLM judged against labels is apply").
- repeat_cost = high [Urteil, wie Fall 2].
- Reihenfolge vor dem Lauf (high):
  1. `labkit-init exp <name> --repeat-cost high --kind apply --model <alias>` (Z. 75–77).
  2. `protocol-check <PROTOCOL> --contract` (Z. 83–84).
  3. Felder: Frage, Daten, Ausschlüsse, Einheit (Z. 87); Kriterium, Zulassungsbedingung, Nullbedingung im selben Lauf (Z. 88–90); type und jeder Satz eines Versprechens (Z. 84–85); PROMPT-Konstanten mit `protocol-fill <PROTOCOL> --prompts` und Datenprofil (Z. 91–92); Begriffe unter „Terms of this protocol" (Z. 99–100).
  4. Registrierung committen (Z. 101–102).
  5. `01_measure.py --show 2` lesen (Z. 107–109); `code-check <area>`; Bereichstest (Z. 110–111).
  6. Datenprofil-Urteil festhalten (Z. 114–115).
  7. `01_measure.py --probe`; Rohbeispiele sichern; Auswertung an synthetischen Extremen prüfen (Z. 120–123).
  8. `preflight <area>`, `labkit-audit <area> --mode preflight`, Befunde entscheiden, `preflight_audit`, `--report`, `frozen = true` (Z. 130–134).
  9. Committen; `runlog start` und `runlog <area> --wait` (Z. 138–144).
- Bei Wiederholung nach Belieben (low): kein Probe-Lauf (Z. 125–126); kein Preflight-Audit und kein Freeze (Z. 136); Vordergrundlauf (Z. 139–140). Unverändert: Kriterium und Analyse-Audit (Z. 59, Z. 151), Datenprofil (Z. 91, Z. 114) und Konklusion mit Rohpaar (Z. 179–183).
- Datenprofil-Helfer ausführen reicht nicht [explizit]: Das Urteil, ob Oberflächenmerkmale die Frage ohne die Fähigkeit beantworten könnten, muss im Datenprofil stehen. `00_prepare.py --audit` liefert nur Hinweise (Z. 114–117).
- Lücke: Z. 138–140 lässt offen, ob ein low-Lauf über runlog oder nur im Vordergrund läuft.

### Fall 4: Fit, low, finalize besteht, Analyse-Audit ohne Befunde, Konklusion leer
- Befehle in dieser Reihenfolge:
  1. `protocol-fill <PROTOCOL> "Conclusion=…"`: höchstens zwei schlichte Sätze, innerhalb der Grenzen (Z. 179–180).
  2. Übrige Felder nach dem Lauf füllen (Z. 180–181). Welche das sind, steht nicht da.
  3. Keine Entscheidungsreview nötig: kein BLOCKER mit „stands" (Z. 185–186).
  4. `protocol-fill <PROTOCOL> --from-run <run_id>` (Z. 201–204). Voraussetzung: Messung, gedeckter Analyse-Audit, `02_analyze.py --check`.
  5. `protocol-fill <PROTOCOL> --into REPORT.md` (Z. 209–210).
  6. Erklärung im Report selbst schreiben, konsistent zur Konklusion (Z. 211–213).
  7. Gezählte Größen (Zahlen, Mediane) aus Rohzeilen in `metrics.json` (Z. 213–215).
  8. Externe Pfade und Formate selbst prüfen (Z. 225–226). Staging: Report, Protokoll, Outputs, Runs, Audit-Belege inkl. `audits/attempts.jsonl` (Z. 226–228). Der Commit prüft den gestagten Zustand (Z. 228).
- Generiert: Recorded results, `[result] run`, Run-Eintrag, abgeleitete Verdikte (Z. 201–208); Ergebnisblock und Grenzen in REPORT.md (Z. 209–210); `runs.tsv` ist nur eine Sicht (Z. 228–229).
- Geschrieben: Konklusion (Z. 179–180), Erklärung im Report (Z. 211–213). Die Werte in `metrics.json` sind eingegeben, werden aber gerendert [Urteil]. Das Rohpaar aus dem gespeicherten Output ist kopiert, nicht generiert (Z. 181–183); ob es für einen Fit ohne Modell gilt, ist offen.
- Zulässige Aussage: erst nach Adoption die Konklusion und die Verdikte aus Recorded results. Vorher keine.
- Lücken: Ob ein Audit ohne Befunde „entschieden" im Sinn von Z. 203–204 ist, ist offen. `finalize` allein ersetzt den Analyse-Audit nicht (Z. 151).

### Fall 5: Zwei verbotene Merkmale, eines entfernt, nicht neu gemessen, Status „fixed" gewünscht
- Nicht fixed [explizit]: „fixed means the whole named fault was corrected and its requested diagnostic run and assessed" (Z. 158–160). Das zweite Merkmal ist offen.
- Erster Schritt: zweites Merkmal im Code entfernen (Z. 239–242); `code-check <area>`, Bereichstest (Z. 110–111); committen; unter unveränderter Registrierung neu messen (Z. 239–240, Z. 138–140); `finalize`, Analyse-Audit (Z. 161–162). Der neue Audit führt offene BLOCKER mit (Z. 162–164). Danach `labkit-audit <area> --findings` (Z. 153–154), dann `--decide` mit der angeforderten Diagnose (Z. 156–160).
- Ausschlussregel ändern repariert nicht [explizit]: „Remove it from the code, not from the exclusion rule." (Z. 241–242). „Editing code does not repair an old run." (Z. 164).
- Alter Lauf und Audit bleiben erhalten (Z. 276–279).
- Lücke: Ob das Entfernen des zweiten Merkmals die Registrierung berührt, ist nicht ausdrücklich geregelt; Z. 239–240 verlangt, sie unverändert zu lassen.

### Fall 6: Low-Fit verfehlt C1; Vorschlag: breitere Nullbande und niedrigere Marge oder neue Area mit „beantwortet"
- Sofortiger Weg [explizit]: Die Verfehlung ist das Ergebnis; zuerst berichten (Z. 243–244). Lauf adoptieren, „A failed criterion under valid admissibility is a reportable miss." (Z. 201–207). Konklusion als Verfehlung (Z. 179–180).
- Marge senken ist keine Reparatur [explizit] (Z. 244–245). Kriterien und Konstanten werden vor den Ergebnissen gesetzt; spätere Änderungen beantworten die ursprüngliche Frage nicht (Z. 101–103). Die breitere Nullbande ist eine Änderung nach Ergebnis [Urteil].
- Neue Area als „beantwortet": nicht zulässig. Z. 256–258 („a new approach never turns an earlier miss into a pass"; „an independent question is not a replacement just because it comes later") steht im Abschnitt zur ungültigen Registrierung. Die Übertragung auf diesen Fall ist [Urteil]. `[replaces]` gilt nur bei ungültiger Registrierung (Z. 249–254); hier ist die Registrierung gültig.
- Spätere Untersuchung nicht verboten: `type = "exploratory"` für Untersuchung mit schon Beobachtetem (Z. 51–52). Ein absichtlich geänderter Folgeversuch muss offenlegen, was schon beobachtet wurde (Z. 257–258). Er darf nicht als Antwort auf die Originalfrage im REPORT.md stehen (Z. 230–231).
- Lücke: Ob eine eigene neue Area mit exploratory ohne `[replaces]` zulässig ist, sagt der Text nicht.

### Fall 7: c1_pass=True, a3_pass=True, Befund mit Wirkung „A3 not assessable"
- Verdikt im Report: nicht „bestanden". A ist die Zulassungsbedingung (Z. 94). „An unassessable or unmet admissibility condition leaves every criterion not assessable." (Z. 173–174). Also gilt für C1 „not assessable", obwohl `c1_pass=True` (Z. 246–248 für unbeurteilbare Versprechen).
- Messwerte bleiben Beschreibung (Z. 175). Die Verdikte leitet Recorded results ab; „raw metrics in the run remain unchanged" (Z. 205–207).
- `metrics.json` nicht ändern, um die Pass-Flags zu drehen [Urteil]. Der Text erlaubt dort nur gezählte Größen aus Rohzeilen (Z. 213–215); „Never retype those values." (Z. 210). Ein Verbot des Wortlauts „metrics.json" gibt es nicht.
- Keine Decision-Review durch diese Wirkung: nur „BLOCKER accepted with stands" braucht eine (Z. 185–186); „`not assessable` does not itself require a decision review." (Z. 196–197).
- Lücke: Genaue Schreibweise der ID (`A3` oder anders) im Befehl `--effect "<ID> not assessable"` (Z. 172–173) ist nicht erklärt.

### Fall 8: Upheld BLOCKER „stands", gerendert; nur die Konklusion verstärkt
- Veraltet: Die Review. „Changing the Conclusion or decision invalidates its review" (Z. 193–194). Neue Review nötig, weil „stands" eine Review verlangt: `labkit-audit <area> --review --record <record>` (Z. 185–186).
- Erklärung im REPORT.md muss zur neuen Konklusion passen; der generierte Block kopiert sie nicht (Z. 211–213).
- Nicht nötig: neue Messung, „Changing only the Conclusion does not require another measurement." (Z. 195).
- Wiederholt sich: die Review. Die Konklusion bleibt „within the limits" (Z. 179–180). Eine stärkere Aussage darf die Grenze der Wirkung „stands" nicht übersteigen (Z. 171–172) [Urteil].
- `--again` settelt nichts: „`--again` never supplies missing approval or overrules an earlier rejection." (Z. 196–197). Eine Ablehnung wird nicht durch wiederholtes Ziehen bis zur Zustimmung aufgehoben (Z. 186–187).
- Lücke: Z. 179–180 schreibt die Konklusion „before adoption". Wie eine Konklusion nach der Adoption geändert und neu adoptiert wird, steht nicht da.

### Fall 9: Analyse-Audit gescheitert, Adoption verweigert, Metriken gut, REPORT.md fällig
- Gescheiterter Audit zählt nicht als Deckung [explizit]: „they provide evidence of the attempt, not analysis coverage" (Z. 278–279); Adoption braucht gedeckten Audit (Z. 203–204).
- Gute Metriken sind kein Grund: „description, not a success claim" (Z. 175).
- Pfad [explizit]: Ursache benennen (Z. 235–236); `labkit-audit <area> --findings` (Z. 153–154). Unadoptierter Lauf: `protocol-fill <PROTOCOL> --discuss <run_id> --why "<was Adoption verhinderte, was gefunden wurde>" --into REPORT.md` (Z. 217–219). Im Text: Frage bleibt offen, keine Erfolgsaussage (Z. 219–220). Review: `labkit-audit <area> --report-review REPORT.md` am fertigen Report (Z. 220–221). Bei Befund Aussage korrigieren; ein sauberer Zug auf dem unveränderten Zustand gibt nichts frei (Z. 221–223).
- Nachweis: Report, Protokoll, Outputs, Runs, Audit-Belege inkl. `audits/attempts.jsonl` und Review-Records zusammen stagen (Z. 226–228). Kein `--no-verify` (Z. 280–281).
- Ohne Diskussion ist die Alternative das Handover: offene BLOCKER vorher entscheiden, dann `protocol-fill <PROTOCOL> --handover --why … --tried … --into REPORT.md` (Z. 259–266). Ein Ende ohne Ergebnis ist zulässig (Z. 235–236).
- Prosa allein reicht nicht [Urteil auf Basis von Z. 268–270]: Zitate in Prosa oder in anderen Reports brauchen Entfernung oder ausdrückliche Diskussion.
- Lücke: Wie ein Report-Review mit knapper Zeit abläuft, regelt der Text nicht.

### Fall 10: Registrierung mit unvereinbaren Definitionen des Beurteilungsgegenstands
- Ersatzweg [explizit] (Z. 249–254): Konflikt erklären; neu registrieren mit `labkit-init exp <new-name> --kind …`; `type = "exploratory"`; `[replaces] protocol = "<id>"`; je `[[replaces.change]]` mit what, from, to, why; offene BLOCKER des Vorgängers `deferred`.
- Der Typ ist exploratory (Z. 252). „Writing a type does not establish its scientific validity." (Z. 51–52).
- Frühere Befunde und Ergebnisse bleiben: „preserve run evidence, audit answers, earlier findings and history" (Z. 276–277). „A new area is not a way to discard an earlier result." (Z. 70–71). Das Verdikt des Vorgängers wird zuerst gerendert; ein neuer Ansatz macht eine frühere Verfehlung nicht zum Erfolg (Z. 254–256).
- Vorgänger-BLOCKER, die `deferred` geschlossen werden, brauchen eine bestätigende Review (Z. 189–191) [Urteil auf Basis dieser Zeilen].
- Nicht jede spätere unabhängige Frage muss ersetzen: „an independent question is not a replacement just because it comes later." (Z. 257–258).
- Lücke: Wann eine Änderung „absichtlich" ist und wann die Frage unabhängig, entscheidet der Text nicht. Welche Werte `--kind` hier gelten, ist nicht genannt.

### Fall 11: finalize besteht, externe Aufgabe verlangt `pred_results/predictions.csv` im Repo-Root, Datei liegt im Area-Output
- Nicht erledigt [explizit]: „a green gate proves only its encoded checks" (Z. 225–226). Externe Ausgaben sind die Lieferung; die Metriken ersetzen sie nicht (Z. 35–36).
- Pfad [explizit]: „Write each output from the measurement, at the path the task names." (Z. 37–38). Die Datei soll also aus der Messung am genannten Pfad entstehen.
- Kopieren aus dem Output-Ordner: nicht geregelt. Ob das als „aus der Messung geschrieben" gilt, ist offen. Wenn dafür Code geändert werden muss, gilt der Zyklus Test, Commit, Neumessung, finalize, Analyse-Audit (Z. 161–162) [Urteil].
- Analyse-Audit muss ebenfalls laufen (Z. 151, Z. 203–204).
- Was das Gate garantiert: nur seine kodierten Prüfungen (Z. 225–226). Existenz am Root-Pfad, Format und Inhalt werden von finalize nicht bestätigt [Urteil auf Basis dieser Zeile]. Der Commit prüft den gestagten Stand (Z. 228), daher die Datei zusammen mit dem Rest stagen (Z. 226–228).
- Lücke: Ob der Pfad aus dem Measure-Skript kommt oder außen gesetzt wird, ist nicht geregelt.

### Fall 12: --decide und neuer Report-Block, aber „evidence preserved"; Gültigkeit einer Version
- Erlaubt [explizit]: „Change decisions with --decide; generate result updates with protocol-fill. These permitted updates do not erase or rewrite the earlier measurements." (Z. 276–279). Nach geänderten Entscheidungen: `protocol-fill <PROTOCOL> --render`, dann Report-Block neu erzeugen (Z. 210–211). Jede Entscheidung mit dem gezeigten Befehl (Z. 158).
- Intakt bleiben [explizit]: Run-Evidenz, Audit-Antworten, frühere Befunde, Historie (Z. 276–277); gescheiterte Audits (Z. 278–279). Keine Änderung von Audit- oder Run-Records (Z. 26–27); keine Löschung oder Ignore-Regeln, kein `--no-verify` (Z. 280–281). Eine Entscheidungsänderung invalidiert die Review, die dann nötig ist (Z. 193–194, Z. 185–186).
- Gültige Version [explizit, mit Lücke]: Z. 3–4 nennt den im Repo gepinnten labkit-Standard; Z. 62–64: Pflichten aus `protocol-check <PROTOCOL> --contract`, nicht aus älteren Anleitungen; historische Protokolle „with their original commit and package pin"; nicht umschreiben, um Gates zu erfüllen. Das deutet auf den Pin des Protokolls ([Urteil]). Der Text sagt nicht ausdrücklich, was nach einem Pin-Upgrade gilt.

### Offene Punkte (für alle Fälle)
1. Schreibweise des Platzhalters `<PROTOCOL>`: Der Text nennt den Wert nicht („study" oder „PROTOCOL-study.md").
2. Skriptnamen und Skelett-Namen für compute und fit (Z. 107–109, Z. 139).
3. Ein Audit ohne Befunde: Gilt er als entschieden und gedeckt (Fall 4)?
4. Wie eine Konklusion nach der Adoption geändert wird (Fall 8).
5. Abgrenzung „absichtlich geänderte Folgefrage" gegen „unabhängige Frage" (Fälle 6 und 10).
Keine Datei geschrieben, keine Befehle ausgeführt, keine anderen Dateien gelesen.
