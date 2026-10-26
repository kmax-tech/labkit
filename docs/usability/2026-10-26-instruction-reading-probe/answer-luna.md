# Antworten

## 1. Abschlussbericht bei sauberem Audit

**Nächste Schritte:** Zuerst die eigene Summary-Conclusion in höchstens zwei schlichten Sätzen ergänzen, innerhalb etwaiger Limit-Zeilen. Danach `protocol-check` ausführen, damit Conclusion (und bei Modellaufgaben Raw output) geprüft werden. Dann den Run mit `protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392` als Ergebnis übernehmen. Das erzeugt die Ergebniszeile und Run-Zeile aus `metrics.json` und führt `report-check` aus. Bei erfolgreicher Adoption den Berichtblock mit `protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md` erzeugen. Committen sind `output/`, `runs/` und das Protokoll zusammen; die externen Berichtdatei muss ebenfalls den generierten Block exakt enthalten und wird am Stop/Commit geprüft. Die Aufforderung „final report“ enthält keinen ausdrücklichen Wunsch, einen Commit zu erstellen; falls Lieferung den Commit meint, ist die nötige Reihenfolge nach den genannten Checks: committen, nicht pushen.

**Was jetzt in `REPORT.md` behauptbar ist:** Noch kein Resultatblock oder Ergebniswert: Conclusion ist leer und Run noch nicht adoptiert. Nach erfolgreicher Adoption darf dort der von labkit erzeugte Recorded-results-Block samt Limits stehen. Der userseitige Schluss gehört in Conclusion des Protokolls, nicht nochmals in Recorded results. Hier gibt es keine Findings zu berichten. Bei `kind=fit` ist kein modellbezogenes Raw-output-Erfordernis dokumentiert, weil die Anweisung dieses ausdrücklich „with a model“ verknüpft und kein Modellfall genannt ist.

**Beleg:** Lane low, Schritt 6: `--from-run` adoptiert und prüft; anschließend „what is still yours: the Summary's Conclusion“, `protocol-check` hält beide nach Messrun; Berichtblock über `--into REPORT.md`; Ausgabe und Runs gemeinsam committen. Schritt 5 beschreibt Audit/Entscheidungen. „Nothing more is owed on this lane“.

**Offen:** Nicht angegeben ist, ob ein konkretes „final report“ zusätzlich als Commit oder nur als Datei geliefert werden soll. Der genaue Inhalt der Conclusion kann ohne das Forschungsresultat nicht formuliert werden.

## 2. BLOCKER mit zwei Target-Leakage-Features, nur eines entfernt

**Nächste Aktion:** Das Finding noch nicht als behoben markieren. Die verlangte Korrektur zu Ende führen (beide genannten Features entfernen) und das im Finding verlangte Diagnostic ausführen. Da Code geändert wurde, die dokumentierte `code-check experiments/01-study`-Prüfung erneut ausführen; danach eine neue Analysis-Audit-Aufzeichnung mit `labkit-audit experiments/01-study --mode analysis` erstellen und das neue Finding beurteilen. Die instruktion sagt, Findings werden mit `labkit-audit … --decide N STATUS "REASON" --record …` entschieden; `--findings` listet vorhandene Aufzeichnungen, ist aber kein neuer Audit. Ein altes Finding erst dann als fixed/geschlossen behandeln, wenn der erforderliche Diagnosebeleg und die erneute Prüfung zeigen, dass es behoben ist; wie genau ein Status „fixed“ kodiert wird, ist nicht festgelegt. Danach müssen für den Run `finalize experiments/01-study` und der Analysis-Audit vor Adoption erfolgreich sein.

**Was in REPORT.md behauptbar ist:** Der vorhandene Run kann nicht als erfolgreicher, unbelasteter Beleg dargestellt werden. Noch ist kein neuer geprüfter Run genannt. Ein konkreter Berichtsvorgang/Refusal ist bislang nicht angegeben; die Regeln zum nicht adoptierten Run greifen nur, wenn Adoption tatsächlich verweigert wird. Also derzeit keine neue Resultatbehauptung aus diesem unvollständigen Fix.

**Beleg:** Lane low, Schritt 3 verlangt `code-check`; Schritt 5 sagt, Audit-Findings entscheiden und nennt Kommando; Schritt 6 verlangt den entschiedenen Analysis-Audit von Code, Promises und Run sowie bestandenes `02_analyze.py --check`. Allgemeine Regel im Schritt 4 (high lane) zu Checks nach Codeänderungen ist ausdrücklich high-lane und darf hier nicht als low-Pflicht ausgegeben werden; die erneute Prüfung ist meine wissenschaftliche Vorsicht. Der Text des Findings selbst fordert beide Features und ein Diagnostic.

**Offen:** Nicht festgelegt sind die konkrete Diagnose-CLI, ein Statusname oder ein Verfahren, ein einzelnes Finding als „fixed“ zu markieren. Auch ist nicht ausgesagt, ob bei Änderungen zwingend ein neuer Messrun oder nur ein erneuter Audit nötig ist; der alte Run kann weiterhin den alten Code repräsentieren.

## 3. Akzeptierter BLOCKER mit effect stands

**Nächste Schritte:** Conclusion verfassen (maximal zwei Sätze, innerhalb der Limitierung) mit `protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=…"`; dann die verpflichtende Entscheidungsprüfung `labkit-audit experiments/01-study --review` ausführen. Bis zur Bestätigung durch die Review darf der Ergebniswert nicht berichtet werden: `report-check` blockiert ihn. Wird die Review angenommen, Run adoptieren (`protocol-fill … --from-run <run_id>`), danach Berichtblock mit `--into REPORT.md` erzeugen und den von labkit gerenderten Block beibehalten.

**Unabhängiger Fall: Review verwirft die Entscheidung.** Nicht einfach nochmals anfragen, um eine günstigere Antwort zu erhalten. Die Anweisung sagt, bei Ablehnung erneut entscheiden: Conclusion begrenzen, effect ändern oder Fehler beheben. Danach die Entscheidung/Prüfung aktualisieren. Eine zweite Review ist nur soweit nötig, dass die Entscheidung upheld ist, bevor der Wert berichtet werden kann.

**Beleg:** Lane low, Schritt 5: akzeptierter BLOCKER braucht effect; `stands` bedeutet Verdicts gelten weiterhin, innerhalb des Limits. Ein solcher BLOCKER braucht Review; Conclusion zuerst, denn frühere Review wird stale; Review mit `--review`; `report-check` blockiert bis upheld; rejection means deciding again (Limit Conclusion, change effect, or fix fault), not drawing again. Schritt 6 beschreibt Adoption und externen Block.

**Offen:** Der tatsächliche Inhalt der Finding-Begründung, Conclusion und Limit ist nicht mitgeteilt; daher kann weder Conclusion noch der wissenschaftlich richtige effect genauer bestimmt werden. Status-Syntax zur erneuten Entscheidung ist nicht vollständig erläutert.

## 4. Analyse-Audit fehlgeschlagen, Adoption abgelehnt

**Zu liefern:** Keine Messwerte als Resultat ausgeben. Die Regeln sagen bei nicht behebbarer abgelehnter Adoption ausdrücklich: den Run nur als nicht berichtet diskutieren, sagen, dass die Frage offen bleibt, und dort enden. Dokumentierte Textform für lane low: `protocol-fill experiments/01-study/PROTOCOL-study.md --discuss 2026-10-26T08-18-33_7392 --why "<what refused the adoption, what you found>" --into REPORT.md`. Dabei `<what refused the adoption, what you found>` knapp mit dem Audit-Fehler, verweigerter Adoption und den beobachteten Fakten füllen; nicht behaupten, der Schwellenwert mache das Ergebnis berichtbar. Der hohe success score hebt die verweigerte Adoption nicht auf.

**Claim in `REPORT.md`:** `run 2026-10-26T08-18-33_7392 (not reported: <what refused the adoption, what you found>)`; die Frage bleibt offen. Kein Resultatwert und kein erfolgreicher Schluss.

**Beleg:** Lane low, Schritt 6: wenn Adoption verweigert und nicht zu beheben ist, Zahlen nicht als Ergebnis eintragen; Refusal berichten mit `run <run_id> (not reported: …)`, Frage als offen bezeichnen und beenden. High lane beschreibt ebenfalls `--discuss`, aber gilt hier nicht. 

**Offen:** Was genau die Adoption verweigerte und welche Fakten die Fehlermeldung nannte, ist nicht angegeben; der Platzhalter muss daraus ergänzt werden. Ob der Auditfehler behoben werden kann, wird nicht gesagt; Antwort folgt dem Fallwortlaut, dass Adoption verweigert ist und die gewünschte Lieferung jetzt erfolgen soll.

## 5. Conclusion nach Adoption und Review geändert

**Ja, prinzipiell lieferbar, aber erst nach Wiederholung der dadurch entwerteten Prüfung.** Conclusion ist Teil des geprüften Anspruchs: eine Review vor Schreiben der Conclusion wird ausdrücklich stale. Deshalb nach der neuen Conclusion die Review erneut ausführen: `protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=…"`, danach `labkit-audit experiments/01-study --review`. Der aktualisierte Anspruch muss upheld sein, bevor `report-check` bzw. Report als gültiger Ergebnisbericht gelten kann. Die neuen Conclusion-Worte sind nicht Teil des erzeugten Ergebnisblocks. Da Code, Kennzahlen und Entscheidungen unverändert bleiben, ist kein neuer Messrun dokumentiert. Die Prüfung der Conclusion muss dennoch nach der Änderung erneut erfolgen; die explizite Stale-Regel macht eine neue Review nötig.

**Wat in de report:** De reeds gegenereerde blok blijft exact de labkit-rendering; schrijf daar geen handmatige edits in. De Conclusion staat in het protocol. Een bestaand `REPORT.md`-blok kan geleverd worden nadat de nieuwe review upheld is en de reguliere checks slagen.

**Beleg:** Lane low, stap 5: “a review made before it is written goes stale when it is written”; `report-check` blokkeert tot upheld. Stap 6: block is gegenereerd en exact gehouden. `protocol-check` controleert Conclusion na een meetrun.

**Onbeslist:** De tekst zegt niet expliciet welke van `protocol-check`, `report-check`, of allebei men na een post-adoption Conclusion-edit opnieuw moet uitvoeren. Wel is een nieuwe review expliciet nodig; `report-check` kan de rapportage niet toelaten totdat review uphold heeft.

## 6. Vereist extern pad voorspelling

**Nee, de opdracht is niet voltooid.** `finalize` is geen bewijs dat een bestand op het vereiste externe pad staat. Het is alleen bekend dat het run-bestand onder `experiments/01-study/output/pred_results/predictions.csv` staat; het externe contract eist repository-root `pred_results/predictions.csv`. Breng het bestand daarheen, behoud ook de run/output-kopie voor provenance en commit beide volgens de instructie. Voer daarna `finalize experiments/01-study` opnieuw uit, omdat het de provenance controleert en `output/` en `runs/` in git verwacht.

**Geclaimde checks:** De verstrekte instructies documenteren geen specifieke gate/check die `pred_results/predictions.csv` aan het externe taakcontract koppelt. `finalize <area>` controleert alleen genoemde provenance; `report-check` controleert resultaatadoptie, audit, analyzers en run-binding. Geen van beide wordt hier als externe-padcontrole beschreven. Dus het pad moet tegen de externe taakbeschrijving gecontroleerd worden; ik kan geen CLI-vlag of geautomatiseerde garantie claimen. De bedoelde kopie-/verplaatsingsopdracht is evenmin in de instructies gespecificeerd.

**Beleg:** Lane low, stap 6: commit `output/` en `runs/` met protocol; `finalize <area>` controleert provenance en verwacht die git-tracked. De beschreven `report-check` voorwaarden zijn run/adoption/analysis-verificaties, geen extern outputpad. Common case noemt expliciet het externe vereiste pad.

**Onbeslist:** Nicht gesagt ist, ob ein zusätzliches Task-Skript oder Auftraggeber-Check den Root-Pfad automatisch prüft; auch exakte Kopier- und Commit-Kommandos fehlen.
