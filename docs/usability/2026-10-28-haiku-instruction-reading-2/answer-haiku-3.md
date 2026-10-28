Bericht zur Verständlichkeitsprobe (2026-10-28-haiku-instruction-reading-2). Gelesen wurden nur instructions.md und cases.txt, beides vollständig. Zeilenangaben beziehen sich auf instructions.md.

**Fall 1 (RandomForest, 5 s, unbeschriftete Testzeilen)**
- Nächste Schritte: kind = `fit`, repeat_cost = `low`, type = `confirmatory`. Zitat: "A RandomForest fitted in seconds is `fit`, usually at `low` repeat cost" (Z. 59). Bei `low` gilt "Neither `low` nor `exploratory` removes a fit/apply's criterion or audits" (Z. 61). Anlage: `labkit-init exp <name> --repeat-cost low --kind fit` (Z. 83-84). type setzen per `protocol-fill <PROTOCOL> "type=confirmatory" …` (Muster Z. 105-106). Vorher `protocol-check <PROTOCOL> --contract` (Z. 91).
- Owed: Kriterium, Zulässigkeitsbedingung und Nullbedingung (Z. 96-97). Analysis-Audit ja: "`labkit-audit <area> --mode analysis` before reporting any result, at either cost" (Z. 159-160). Preflight-Audit und Freeze nicht geschuldet (Z. 144). `--show 2` gilt für Estimator-Skelette (Z. 115-116). `--probe` nicht bei `low` (Z. 133-134).
- Erlaubte Aussage: bis Analysis-Audit ohne offene BLOCKER nur Beschreibung, keine Erfolgsaussage.
- Unklar: Z. 57-58 verlangt Auswertung "on held-out labelled rows", der Auftrag verlangt Vorhersagen für unbeschriftete Zeilen. Der Text sagt nicht, wie das beschriftete Holdout aus den Daten abzuleiten ist.

**Fall 2 (Dokumente zählen, 6 h)**
- kind = `compute` ("Otherwise … `compute`", Z. 57-58). repeat_cost = `high` ("a repeat needs protection by a preflight audit and freeze", Z. 52). type: nicht vorgegeben, eigene Entscheidung nach Z. 53.
- --show: nicht geschuldet ("compute has no `--show`", Z. 116-117). --probe: nicht geschuldet ("Compute has no `--probe`; test its calculation", Z. 133-134). Berechnung an handgeprüften Fällen testen (Z. 117-118).
- Preflight (`preflight <area>`) und `labkit-audit <area> --mode preflight` sind geschuldet (Z. 138-139). Freeze geschuldet: `preflight_audit` im Kopf, `frozen = true` (Z. 141-142). Start über `.venv/bin/runlog start …` (Z. 149-152).
- Unklar: Der Text sagt nicht, was "not casually repeated" außer Freeze und Preflight bedeutet. Wie ein Compute-Preflight aussieht, ist nicht beschrieben.

**Fall 3 (unveränderter LLM gegen Gold, viele Stunden)**
- kind = `apply` (Z. 60). repeat_cost = `high` (Dauer der Messung, Z. 52).
- Sequenz vor dem Lauf: `labkit-init exp <name> --repeat-cost high --kind apply --model <alias>` (Z. 83-84); `protocol-fill <PROTOCOL> --list` und `protocol-check <PROTOCOL> --contract` (Z. 91-92); Frage, Daten, Ausschlüsse, Einheit, Kriterium, Zulässigkeit, Nullbedingung (Z. 95-97); Data profile und `protocol-fill <PROTOCOL> --prompts` (Z. 99-100). Dann `01_measure.py --show 2` (Z. 115-116), `code-check <area>` (Z. 118), `--probe` (Z. 129-131), `preflight`, `labkit-audit --mode preflight`, `preflight_audit`, `--report`, `frozen = true` (Z. 138-143). Commit (Z. 146), dann `runlog start` (Z. 149-152).
- Bei wiederholbarem Lauf (`low`): kein Freeze, kein Preflight-Audit (Z. 144), kein eigener Probelauf (Z. 133-134), Vordergrund-Lauf (Z. 147-148). Pflicht bleibt Commit vor dem Lauf, Finalize und Analysis-Audit (Z. 146, 159-160).
- Reicht das Data-Profile-Hilfsprogramm? Nein. "its counts are hints, not the judgement" (Z. 124-125). Die Judgement-Frage ("could surface features answer the question", Z. 122-123) bleibt bei dir und wird im Data profile festgehalten.
- Unklar: "--show 2" nennt nur "estimator/prompt skeletons"; ob das für apply genau gilt, steht nicht explizit.

**Fall 4 (Fit committed, finalize ok, Audit ohne Befund, Conclusion leer)**
- Reihenfolge: Conclusion vor Adoption setzen, höchstens zwei Sätze: `protocol-fill <PROTOCOL> "Conclusion=…"` (Z. 187-188). Übrige After-Run-Felder füllen (Z. 189). Adoption: `protocol-fill <PROTOCOL> --from-run <run_id>` (Z. 213-214), Voraussetzungen Z. 215-216. Dann `protocol-fill <PROTOCOL> --into REPORT.md` (Z. 224-225). Report-Erklärung selbst schreiben (Z. 226-227). Zählwerte in `metrics.json` aus Zeilen rechnen (Z. 228-230). Staging und Commit mit Audit-Belegen (Z. 240-244).
- Generiert: Recorded results und Run-Eintrag (Z. 213-214, 220-222); Ergebnisblock und Grenzen in REPORT.md (Z. 224-225). "Never retype those values" (Z. 225).
- Eigene Arbeit: Conclusion (Z. 187), Report-Erklärung (Z. 226-227), Eingaben für `metrics.json` (Z. 229-230).
- Unklar: welche Felder "other after-run fields" sind; ob die Conclusion im REPORT.md-Block erscheint, ist nicht gesagt.

**Fall 5 (zwei verbotene Leak-Merkmale, nur eines entfernt, "fixed" gewünscht)**
- Erst nicht "fixed" setzen. "`fixed` means the whole named fault was corrected and its requested diagnostic run and assessed" (Z. 166-168). Beide Merkmale entfernen, Diagnoselauf durchführen und bewerten, dann Schritte 2-4 wiederholen: test, commit, neue Messung, finalize, Analysis-Audit (Z. 169-171). Code-check nach jeder Codeänderung (Z. 118). Entscheidung dann per `labkit-audit <area> --decide <N> fixed "<REASON>" --record <record>` (Z. 164).
- Ausschlussregel ändern repariert nicht: "Remove it from the code, not from the exclusion rule" (Z. 256-257). Ein alter Lauf wird durch Codeänderung nicht repariert: "Editing code does not repair an old run" (Z. 171-172).
- Unklar: wer die Diagnose "assessed" bewertet und wie, ist nicht gesagt.

**Fall 6 (C1 verfehlt, breitere Nullbande oder neue Area "beantwortet")**
- Sofortiger Weg: den Fehlschlag berichten. "that is the result: report the miss first" (Z. 258-259). Ein verfehltes Kriterium bei gültiger Zulässigkeit ist eine berichtbare Verfehlung (Z. 221-222). Conclusion innerhalb der Grenzen (Z. 187).
- Breitere Nullbande und niedrigere Marge: "Lowering the margin is not a repair" (Z. 259-260). Kriterien und Konstanten sind vor Ergebnissen festzulegen, "later changes do not answer the original registered question" (Z. 109-111).
- Neue Area mit Behauptung: nein. "a new approach never turns an earlier miss into a pass" (Z. 268-269).
- Spätere Untersuchung ist nicht verboten. Sie braucht ein eigenes Protokoll ohne `[replaces]`, `type = "exploratory"`, und die Question nennt A und was A zeigte (Z. 271-275).
- Unklar: ob eine Folgeuntersuchung in derselben Area möglich ist, sagt der Text nicht ("a protocol of its own").

**Fall 7 (c1_pass=True, a3_pass=True, Befund akzeptiert mit "A3 not assessable")**
- Anzeigbares Urteil: "An unassessable … admissibility condition leaves every criterion not assessable" (Z. 180-181). Also nicht "C1 bestanden", trotz c1_pass=True. "Measured values remain description, not a success claim" (Z. 182-183).
- metrics.json nicht editieren. "raw metrics in the run remain unchanged" (Z. 220-222). Das Urteil leitet Recorded results ab.
- Decision-Review: nicht nötig, "`not assessable` does not itself require a decision review" (Z. 208). Review nur für BLOCKER mit "stands" (Z. 197-198).
- Unklar: ob der Befund BLOCKER oder WARNING war (beide möglich, Z. 178-181). Wie die Ableitung aus c1_pass=True genau erscheint, ist nicht beschrieben.

**Fall 8 (BLOCKER "stands", Conclusion verstärkt)**
- Befehl: `protocol-fill <PROTOCOL> "Conclusion=…" --force` (Z. 191-192).
- Bleibt gültig: adoptiertes Ergebnis und REPORT.md-Block (Z. 193-194).
- Veraltet: jedes Decision-Review (Z. 194-195); "Changing the Conclusion or decision invalidates its review" (Z. 205-206). Review neu: `labkit-audit <area> --review --record <record>` (Z. 197-198). Report-Erklärung muss passen (Z. 195, 226-227).
- Kein neuer Messlauf nötig (Z. 207). Die stärkere Conclusion darf nicht über die BLOCKER-Grenze hinausgehen (Z. 180).
- `--again`: "never supplies missing approval or overrules an earlier rejection" (Z. 208-209). Eine frühere Ablehnung verlangt Korrektur, nicht erneutes Ziehen (Z. 198-199).

**Fall 9 (Adoption verweigert, Metriken gut, Report fällig)**
- Erst `labkit-audit <area> --findings` (Z. 19-20, 22-24). Dann der Diskussionsweg: `protocol-fill <PROTOCOL> --discuss <run_id> --why "…" --into REPORT.md` (Z. 232-234). Frage bleibt offen, keine Erfolgsaussage (Z. 234-235). Pflicht: `labkit-audit <area> --report-review REPORT.md` (Z. 235-236). Korrigieren, dann neu prüfen; "a clean draw on the unchanged state releases nothing" (Z. 236-238).
- Belege: Fehlgeschlagene Audits bleiben, "Keep unsuccessful audits" (Z. 296-297). `audits/attempts.jsonl` und Review-Records mitstagen (Z. 241-243). Keine nicht übernommenen Zahlen als Antwort im REPORT.md (Z. 245-246).
- Reicht Prosa "nicht berichtet"? Der Text nennt dafür nichts. Der dokumentierte Weg ist `--discuss` plus Report-Review. Alternative bei unlösbarer Lage: Handover (Z. 278-291), das keine Zahl und keine Audit-Freigabe erlaubt (Z. 290-291).
- Unklar: ob der fehlgeschlagene Audit erst entschieden oder neu gestartet werden muss, und ob Zeitdruck einen Weg öffnet, sagt der Text nicht.

**Fall 10 (widersprüchliche Registrierung)**
- Weg: Konflikt erklären, dann `labkit-init exp <new-name> --kind …`, `type = "exploratory"`, `[replaces] protocol = "<id>"`, je Änderung ein `[[replaces.change]]` (was, von, nach, warum), offene BLOCKER des Vorgängers `deferred` (Z. 262-269). Verdikt des Vorgängers zuerst (Z. 268-269).
- Frühere Befunde und Ergebnisse bleiben (Z. 293-296).
- Nicht jede spätere Frage ersetzt: "Only a new attempt at the same question is a replacement" (Z. 270-273).
- Unklar: welcher `--kind` gilt, und wann eine Frage "dieselbe" ist, bleibt Judgement.

**Fall 11 (predictions.csv im Repo-Root verlangt)**
- Nicht erledigt. Benannte Ausgaben sind das Ergebnis (Z. 35-37). Die Datei kommt aus dem antwortenden Lauf: Das Skript schreibt sie dorthin, oder du kopierst die Ausgabedatei dieses Laufs. Nie neu tippen oder abseits des Laufs berechnen (Z. 37-39). Pfad, Format und Inhalt selbst prüfen (Z. 240-242).
- Was das Gate garantiert: nur die kodierten Prüfungen. "a green gate proves only its encoded checks" (Z. 240-242). Der Commit prüft den gestagten Stand (Z. 243-244). Dass die Root-Datei existiert und stimmt, garantiert nichts.
- Unklar: ob die Kopie vor der Adoption (Z. 213-214) zulässig ist.

**Fall 12 (--decide und neuer Report-Block, "Evidenz bleibt erhalten")**
- Erlaubt: "Change decisions with `--decide`; generate result updates with `protocol-fill`" (Z. 293-295). Nach geänderten Entscheidungen `protocol-fill --render`, dann Report-Block neu (Z. 225-226).
- Unverändert bleiben: Run-Evidenz, Audit-Antworten, frühere Befunde, Historie (Z. 293-294); "These permitted updates do not erase or rewrite the earlier measurements" (Z. 295-296); unerfolgreiche Audits (Z. 296-297); kein `--no-verify`, keine Record-Edits, keine Löschungen (Z. 297-298).
- Gültige Version: die Pin-Zeile von `requirements.lock`, sonst `requirements.txt` (Z. 65-66). Für historische Protokolle: ursprünglicher Commit und Pin (Z. 70-72).
- Unklar: die beiden Sätze (Pin gilt für das ganze Repo, Historie bleibt an ihrem Pin) sind nicht sauber auf eine ältere Area in einem neueren Repo abgebildet.

**Fall 13 (Pin angehoben, alte Area mit standard "0.21")**
- Alte Area: nicht konvertieren. "reproduce them at that commit and pin" (Z. 70-72). Die Head-Angabe `standard` nennt das Protokollformat, nicht die Paketversion (Z. 66-67). Konkret: den Commit der Stempelung mit seinem Pin auschecken und dort reproduzieren. Das ist nur als Prinzip beschrieben, ein Befehl dafür steht nicht da.
- Neue Frage: `labkit-init exp <name> …` im aktuellen Pin (Z. 72, 83-84). Aktueller Pin: `labkit-check` zeigt ihn neben der Installation (Z. 66-67).
- Welche labkit-Version gilt: die Pin-Zeile in `requirements.lock` (Z. 65-66). Frühere Audits: "no earlier audit covers an area afterwards" (Z. 68-69). Für die alte Area am alten Pin ist das nicht eindeutig.

**Fall 14 (Protokoll A verfehlt C1, neue Modellfamilie)**
- Ersetzung? Unklar. Ein erneuter Versuch derselben Frage ist Ersatz ("Only a new attempt at the same question is a replacement", Z. 270-271), aber die Ersatzroute ist für ungültige Registrierungen beschrieben (Z. 262-270). Eine neue Modellfamilie ist eine Frage, die auf A aufbaut: eigenes Protokoll ohne `[replaces]`, `type = "exploratory"`, und die Question nennt A und was A zeigte (Z. 271-275).
- Registrierung: `labkit-init exp <new-name> --kind fit` (eigene Einordnung nach Z. 55-58, Modellwahl ist Teil von fit, Z. 55-56).
- A's Verfehlung bleibt. "a new approach never turns an earlier miss into a pass" (Z. 268-269).
- Unklar: ob Modellwechsel nach einem Verfehlen als explorativ gilt oder als Auswahl am Ergebnis, sagt der Text nicht direkt.

**Fall 15 (Analysis-Audit ohne Befund, früherer BLOCKER inzwischen behoben)**
- Adoption: ja, wenn Messung, Analysis-Audit und `02_analyze.py --check` gelten (Z. 213-216). "covers the run when it saw the current code, promises and run" (Z. 217-218).
- Nichts zu entscheiden (Z. 218). Aber: "an earlier BLOCKER still needs its fix confirmed in that record" (Z. 218-219).
- Wenn der Fix nach dem Lauf kam: ein alter Lauf wird durch Codeänderung nicht repariert (Z. 171-172). Neue Messung nach dem Fix nötig (Z. 169-170).
- Unklar: wie der Fix in einem Record ohne Befunde bestätigt wird, ist nicht beschrieben.

**Fall 16 (Conclusion nach Adoption abschwächen)**
- Befehl: `protocol-fill <PROTOCOL> "Conclusion=…" --force` (Z. 191-193).
- Bleibt gültig: adoptiertes Ergebnis und REPORT.md-Block (Z. 193-194).
- Veraltet: alle Decision-Reviews (Z. 194-195, 205-206). Wiederholen, wo geschuldet (Z. 205-206; bei BLOCKER "stands" Z. 197-198). Report-Erklärung neu schreiben, die Erklärung wird nicht kopiert (Z. 195, 226-227).
- Keine neue Messung (Z. 207).
- Unklar: ob die Conclusion im REPORT.md-Block steht. Z. 193-194 und 226-227 deuten darauf hin, dass sie es nicht tut, sagen es aber nicht ausdrücklich.

**Übergreifende Lücken**
1. Die Zuständigkeit für "fixed"-Diagnosen (Fall 5) ist nicht gesagt.
2. Wie ein Fix in einem Record ohne Befunde bestätigt wird (Fall 15) ist nicht beschrieben.
3. Ob Conclusion im Report-Block steht (Fall 16) ist unklar.
4. Ob ältere Areas am alten Commit reproduziert werden können und wie (Fall 13), ist nicht als Befehl beschrieben.
