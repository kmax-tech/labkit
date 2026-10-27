# Unabhängige Lektüre: entry-instructions.md

Grundlage ausschließlich `entry-instructions.md`; die Zeilenangaben beziehen sich auf diese Datei. Alle Befehle sind vorgeschlagene Handlungen für die fiktiven Fälle, keine ausgeführten Experimente. Konsolenbefehle laufen vom Repository-Wurzelverzeichnis aus und erhalten nötigenfalls das Präfix `.venv/bin/` (Z. 3–7).

## 1. Schneller RandomForest, anschließend ungelabelte Vorhersagen

- **Nächste Schritte:** `kind=fit`, regelmäßig `repeat_cost=low`; fünf Sekunden allein beweisen allerdings nicht, dass die Messung nach Belieben wiederholbar ist. Unter dieser naheliegenden Fallannahme `low`. `type=confirmatory`, sofern Frage und Kriterium tatsächlich vor den relevanten Ergebnissen festgelegt wurden. Beispielsweise `labkit-init exp study --repeat-cost low --kind fit`, anschließend `protocol-fill experiments/01-study/PROTOCOL-study.md --list` und `protocol-check experiments/01-study/PROTOCOL-study.md --contract`. Fit verlangt Kriterium, Zulässigkeitsbedingung und im selben Lauf berechnete Nullbedingung. Auf zurückgehaltenen gelabelten Zeilen evaluieren. Nach Messung `finalize experiments/01-study` und `labkit-audit experiments/01-study --mode analysis`.
- **Jetzt zulässige Aussage:** Eine registrierte bestätigende Fit-Untersuchung ist vorgesehen; die ungelabelten Vorhersagen belegen noch keine Vorhersagegüte oder erfolgreiche Beantwortung.
- **Beleg:** Z. 13–23, 39–54, 62–64, 110–113.
- **Lücke/Urteil:** Wiederholbarkeit und vorhandene gelabelte Evaluationsdaten sind nicht ausdrücklich gegeben. Die Typangabe allein verbürgt keine wissenschaftliche Gültigkeit (Z. 15).

## 2. Sechsstündiges Zählen lokaler Dokumente

- **Nächste Schritte:** `kind=compute`, `repeat_cost=high`, da die Wiederholung geschützt werden soll. `labkit-init exp study --repeat-cost high --kind compute`; Vertragsfelder ermitteln und ausfüllen. Compute hat weder `--show` noch `--probe`; stattdessen Berechnung testen. Vor dem vollständigen Lauf `preflight experiments/01-study`, danach `labkit-audit experiments/01-study --mode preflight`, Findings entscheiden, passenden Recordnamen im Protokollkopf unter `preflight_audit` eintragen, `labkit-init exp study --report`, Vertragsfelder ausfüllen und `frozen = true` setzen. Code, Registrierung und Eingaben committen; dann den dokumentierten High-Lauf starten und überwachen.
- **Jetzt zulässige Aussage:** Geplant ist eine aufwendig wiederholbare Berechnung; noch kein gezähltes Ergebnis. Compute schuldet kein Vorhersagekriterium.
- **Beleg:** Z. 13–15, 32–35, 68–70, 80–103.
- **Lücke/Urteil:** Für Compute nennt der Text keinen eigenen Probe-Befehl und verlangt ihn ausdrücklich nicht; die konkrete Prüfung der Berechnung bleibt dem Fallentwurf überlassen.

## 3. Unverändertes LLM gegen Goldlabels

- **Nächste Schritte:** `kind=apply`, bei schutzbedürftiger Wiederholung `repeat_cost=high`. `labkit-init exp study --repeat-cost high --kind apply --model <alias>` nur mit Alias, wenn `models.toml` benutzt wird. Mit `protocol-fill <PROTOCOL> --list` und `protocol-check <PROTOCOL> --contract` die Vorabfelder bestimmen: Frage, Scope, Ausschlüsse, Einheit, Kriterium, Zulässigkeits- und Nullbedingung; mit `[model]` zusätzlich Data profile. Vorhandene PROMPT-Konstanten mit `protocol-fill <PROTOCOL> --prompts` übernehmen. Typ begründet wählen, Begriffe definieren, Registrierung vor der ersten vollständigen Messung committen. Instrument und Bereichstest ausfüllen, `--show 2` des vorhandenen Prompt-Skeletts lesen, `code-check experiments/01-study` und handgeprüfte Tests ausführen. Oberflächenmerkmale selbst beurteilen und in Data profile festhalten. Bei high `--probe` des Skeletts, repräsentative Rohbeispiele und synthetische Extreme; danach `preflight`, Preflight-Audit, Entscheidungen, Recordverweis, `--report` und Freeze wie in Fall 2. Änderungen am Code vor Freeze erneut auditieren. Code, Registrierung und Eingaben committen, dann `.venv/bin/runlog start experiments/01-study -- .venv/bin/python experiments/01-study/scripts/01_measure.py` und `.venv/bin/runlog experiments/01-study --wait`.
- **Bei beliebiger Wiederholbarkeit:** `low`; kein gesonderter Probe, kein Freeze und kein Preflight-Audit. Der volle Lauf prüft das Instrument mit und läuft im Vordergrund über `.venv/bin/python experiments/01-study/scripts/01_measure.py`. Kriterium, Tests, Data-profile-Urteil und anschließender Analysis-Audit bleiben geschuldet.
- **Jetzt zulässige Aussage:** Geplante Bewertung eines unveränderten Modells, noch kein Leistungsnachweis. Der Data-profile-Helfer allein reicht ausdrücklich nicht: Seine Zählungen sind Hinweise.
- **Beleg:** Z. 13–26, 39–85, 89–113.
- **Lücke/Urteil:** Viele Stunden allein legen die Wiederholbarkeit nicht logisch fest. `type` und Alias sind nicht vorgegeben. Der genaue Aufruf für `--show`/`--probe` hängt vom tatsächlich gestempelten Skript ab; der Text nennt dafür keinen einheitlichen Skriptnamen.

## 4. Leere Conclusion nach sauberem Analysis-Audit

- **Nächste Schritte:** `protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<Antwort innerhalb der Grenzen>"`; höchstens zwei verständliche Sätze als Antwort auf die Frage. Übrige Nachherfelder füllen, gegebenenfalls echte Prompt/Antwort-Beispiele. Dann `protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392`, anschließend `protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md`. Eigene Erklärung konsistent mit der Conclusion verfassen, externe Abgabeanforderungen prüfen und Bericht, Protokoll, Outputs, Runs sowie Auditevidenz einschließlich `audits/attempts.jsonl` gemeinsam stagen. `02_analyze.py --check` muss für die Übernahme gelten. Ohne Findings ist kein hier genannter Entscheidungsreview fällig.
- **Jetzt zulässige Aussage:** Die sauberen Prüfungen ersetzen noch keine ausgefüllte und übernommene Antwort; Erfolg hängt vom tatsächlichen registrierten Urteil ab.
- **Generiert/verfasst:** Generiert werden bei Übernahme `[result] run`, Recorded results und Laufeintrag; für REPORT.md Ergebnisblock und Grenzen. Conclusion und Berichtserklärung verfasst man selbst; die Erklärung wird nicht aus dem Block kopiert. Weitere berichtete Mengen aus aufbewahrten Zeilen nach `metrics.json` berechnen, damit sie ebenfalls generiert werden können.
- **Beleg:** Z. 134–166, 176–182.
- **Lücke/Urteil:** Der Fall enthält keine Messwerte und damit keine Grundlage für eine konkrete positive Conclusion. Der Text gibt hier keinen vollständigen Aufrufpfad für `02_analyze.py --check` an.

## 5. Zwei verbotene Merkmale, nur eines entfernt

- **Nächste Schritte:** Noch nicht `fixed` entscheiden. Den gesamten benannten Fehler beheben, also auch das zweite Merkmal entfernen; angeforderte Diagnostik ausführen und beurteilen. Nach Änderung am Messcode Schritte 2–4 wiederholen: Implementierung testen, `code-check experiments/01-study`, committen, neue vollständige Messung im Vordergrund, `finalize experiments/01-study`, `labkit-audit experiments/01-study --mode analysis`. Findings mit `labkit-audit experiments/01-study --findings` und den ausgegebenen vollständigen Befehlen entscheiden, Schema: `labkit-audit experiments/01-study --decide <N> fixed "<vollständige Korrektur und Diagnostik>" --record <record>`. Frühere ungelöste BLOCKER werden im neuen Record weitergeführt und dort entschieden.
- **Jetzt zulässige Aussage:** Der alte Lauf ist durch die Codeänderung nicht repariert; kein aus der Teilkorrektur abgeleiteter Erfolgsanspruch. Ausschlussregel ändern repariert den Implementierungsfehler nicht.
- **Beleg:** Z. 110–123, 190–193, 214–219.
- **Lücke/Urteil:** Art der Diagnostik und Findingnummer fehlen; sie müssen aus dem Finding stammen, nicht erfunden werden. Die hier geforderte Reihenfolge ergibt sich aus der vollständigen Fehlerbehebung und den wiederholten Schritten; `fixed` allein beweist nichts.

## 6. Gültiger Fit verfehlt C1

- **Nächste Schritte:** Den verfehlten registrierten Maßstab zuerst als Ergebnis berichten. Conclusion entsprechend ausfüllen, gegebenenfalls Findings entscheiden, vorhandenen beantwortenden Lauf mit `--from-run 2026-10-26T08-18-33_7392` übernehmen und Bericht mit `--into REPORT.md` generieren. Weder Nullband erweitern noch Marge absenken, um den alten Lauf nachträglich zum Erfolg zu machen. Eine neue Area darf das frühere Ergebnis nicht entsorgen.
- **Jetzt zulässige Aussage:** C1 wurde unter gültiger Zulässigkeitsbedingung verfehlt. Das ist ein berichtbares Ergebnis.
- **Spätere Untersuchung:** Nicht verboten. Eine bewusst geänderte Folgefrage muss bereits Beobachtetes offenlegen; ihre neue Herangehensweise macht den alten Misserfolg nicht zum Erfolg. Eine unabhängige Frage ist nicht automatisch eine Ersatzregistrierung. Der ausführliche Ersatzweg ist ausdrücklich für eine ungültige, nicht bloß verfehlte Registrierung beschrieben.
- **Beleg:** Z. 35, 62–64, 152–158, 194–209.
- **Lücke/Urteil:** Für jede denkbare gültige explorative Folgefrage liefert der Text keinen gesonderten kompletten Sonderablauf. Die frühere Verfehlung allein rechtfertigt jedenfalls nicht den Ersatzweg für unvereinbare Definitionen.

## 7. Rohe Pass-Werte, aber A3 nicht beurteilbar

- **Nächste Schritte:** Entscheidung samt `--effect "A3 not assessable"` dokumentieren. Bei bereits übernommener Entscheidung `protocol-fill experiments/01-study/PROTOCOL-study.md --render`, danach `protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md`; für erstmalige Übernahme gelten die üblichen Voraussetzungen und `--from-run`. `metrics.json` nicht zum künstlichen Umschalten der Rohwerte bearbeiten.
- **Jetzt zulässige Aussage:** A3 ist nicht beurteilbar. Als Zulässigkeitsbedingung lässt es sämtliche Kriterien einschließlich C1 nicht beurteilbar; `c1_pass=True` und `a3_pass=True` begründen dann keinen Erfolgsanspruch. Gemessene Werte bleiben beschreibend. Der Effekt allein verlangt keinen Entscheidungsreview.
- **Beleg:** Z. 125–130, 147–148, 152–162, 214–219.
- **Lücke/Urteil:** Die konkrete Rolle von A3 ist im Fall nicht ausgeschrieben. Die Folgerung „alle Kriterien nicht beurteilbar“ gilt ausdrücklich, wenn A3 eine Zulässigkeitsbedingung ist; allein aus dem Namen erklärt der Text dessen Bedeutung nicht. Unabhängig davon darf A3 selbst nicht als bestanden berichtet werden.

## 8. Nur Conclusion eines geprüften stands-BLOCKERs verstärkt

- **Nächste Schritte:** Die Änderung der Conclusion entwertet den bisherigen Review. Stärkere Aussage auf vorhandene Evidenz und Grenzen prüfen und gegebenenfalls korrigieren. Erneut `labkit-audit experiments/01-study --review --record 2026-10-26T08-28-analysis.toml`, da der angenommene BLOCKER mit `stands` weiter reviewpflichtig ist. Nur die Conclusion zu ändern verlangt keine neue Messung. Die Berichtserklärung muss zur aktuellen Conclusion passen; gegebenenfalls korrigieren und den Ergebnisblock mit `protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md` aktuell halten.
- **Jetzt zulässige Aussage:** Die frühere Freigabe deckt die verstärkte aktuelle Conclusion nicht ab. Ein unveränderter `--again`-Durchlauf liefert keine fehlende Zustimmung und hebt keine frühere Ablehnung auf.
- **Beleg:** Z. 139–148, 160–164, 173–174.
- **Lücke/Urteil:** Z. 145 benennt ausdrücklich den Review als ungültig; eine automatische Ungültigkeit des schon übernommenen Laufeintrags wird nicht behauptet. Ob die stärkere Conclusion sachlich zulässig ist, bleibt ohne Wortlaut und Evidenz offen.

## 9. Gescheiterter Audit, verweigerte Übernahme, knappe Frist

- **Nächste Schritte:** Ursache benennen und anhand der Recovery-Optionen prüfen, was möglich ist. Wenn ungelöst: im Bericht Hindernis, Versuche, betroffene Läufe und Findings nennen. Zur Diskussion des nicht übernommenen Laufs `protocol-fill experiments/01-study/PROTOCOL-study.md --discuss 2026-10-26T08-18-33_7392 --why "<Grund der verweigerten Übernahme und Befund>" --into REPORT.md`. Klar erklären, dass die Frage offenbleibt. Den fertigen Bericht mit `labkit-audit experiments/01-study --report-review REPORT.md` prüfen; beanstandete Aussage korrigieren und den geänderten Zustand erneut prüfen. Ein sauberer neuer Durchlauf auf unverändertem Zustand gibt nichts frei. Gesamte Evidenz einschließlich fehlgeschlagener Audits, Auditantworten, Historie, `audits/attempts.jsonl` und erforderlicher Reviews erhalten und gemeinsam mit Bericht, Protokoll, Outputs und Runs stagen.
- **Jetzt zulässige Aussage:** Beschreibende Diskussion des nicht übernommenen Laufs unter ausdrücklicher offener Frage; kein erfolgreicher Antwortanspruch aus den guten Metriken. Ein ehrlicher ungelöster Bericht ist zulässig.
- **Reicht „nicht berichtet“ als Prosa?** Nein, wenn die Zahlen diskutiert werden: Der Text schreibt den dokumentierten Diskussionsweg und Review vor. Eine solche Floskel ersetzt weder Offenlegung noch Evidenzpflichten oder Freigabe.
- **Beleg:** Z. 168–182, 186–219.
- **Lücke/Urteil:** Der konkrete Auditfehler ist unbekannt, daher kann kein bestimmter Reparaturweg behauptet werden. Für eine garantiert fristgerechte Freigabe nennt der Text keinen Ausweg; Zeitdruck hebt die Bedingungen nicht auf.

## 10. Unvereinbare Definitionen in der Registrierung

- **Nächste Schritte:** Konflikt zuerst erklären. Danach `labkit-init exp <new-name> --kind <kind>` mit begründetem Kind und Kostenwahl; neue Registrierung `type = "exploratory"`, `[replaces] protocol = "<id>"` und je Änderung ein `[[replaces.change]]` mit `what`, `from`, `to`, `why`. Offene BLOCKER des Vorgängers mit den dokumentierten `--decide`-Befehlen als `deferred` entscheiden. Neue Untersuchung durch den vollständigen passenden Workflow führen. Frühere Protokolle, Messungen, Findings und Historie erhalten; das Vorgängerurteil wird zuerst gerendert, eine neue Lösung macht einen früheren Miss nicht zum Pass.
- **Jetzt zulässige Aussage:** Die ursprüngliche Frage ist in ihrer registrierten Fassung nicht beantwortbar. Die neue Registrierung ist explorativ; ein späterer Erfolg beantwortet nicht rückwirkend die ursprüngliche Frage.
- **Unabhängige spätere Frage:** Muss nicht ersetzen; zeitliche Reihenfolge allein ist kein Ersatzgrund. Eine bewusst geänderte Folgefrage muss die vorhandenen Beobachtungen offenlegen.
- **Beleg:** Z. 27–28, 200–219.
- **Lücke/Urteil:** Tatsächliche Protokoll-ID, Änderungsinhalte und Findingnummern fehlen. Der Text nennt TOML-Felder, aber keinen speziellen Befehl zum automatischen Schreiben aller Ersatzmetadaten.

## 11. Geforderte CSV liegt am falschen Ort

- **Nächste Schritte:** Aufgabe noch nicht fertig. Die verlangte Datei unter `pred_results/predictions.csv` im Repository-Wurzelverzeichnis bereitstellen und selbst Pfad, Format und Inhalt gegen den externen Auftrag prüfen. Die Provenienz der aufbewahrten Outputs und die übrigen Abgabepflichten weiter beachten.
- **Jetzt zulässige Aussage:** `finalize` hat seine kodierten Prüfungen bestanden; das bescheinigt nicht den extern geforderten Ablagepfad. Ein grünes Gate allein erfüllt den Abgabeauftrag nicht.
- **Beleg:** Z. 176–180.
- **Lücke/Urteil:** Der Text gibt hierfür keinen Export- oder Kopierbefehl an. Welche konkrete Dateihandlung erforderlich ist, ist eine Umsetzungsentscheidung anhand des Auftrags, keine dokumentierte labkit-Garantie.

## 12. Entscheidungen und Ergebnisblock aktualisieren, Evidenz erhalten

- **Nächste Schritte:** Ja, beides ist ausdrücklich erlaubt. `labkit-audit experiments/01-study --findings` liefert vollständige Entscheidungsbefehle; Schema `labkit-audit experiments/01-study --decide <N> <STATUS> "<REASON>" --record 2026-10-26T08-28-analysis.toml`, mit erforderlichem Effekt und Review je Entscheidung. Nach geänderten Auditentscheidungen `protocol-fill experiments/01-study/PROTOCOL-study.md --render`, danach `protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md`. Ändert sich die Conclusion oder Entscheidung, ihre Reviewgültigkeit nach Z. 139–148 erneut prüfen.
- **Jetzt zulässige Aussage:** Die aktuelle Entscheidung und der generierte Ergebnisblock dürfen aktualisiert werden; deren Inhalt muss weiterhin innerhalb des registrierten, beurteilbaren Urteils und der nötigen Freigaben bleiben.
- **Was bleibt erhalten:** Messungen und Rohmetriken, Laufevidenz, Auditantworten, frühere Findings und Historie; auch erfolglose Audits als Versuchsevidenz. Keine Umgehung durch `--no-verify`, manuelle Recordedits, Löschen oder Ignore-Regeln. Erlaubte Updates über `--decide` und `protocol-fill` schreiben keine früheren Messungen um.
- **Welche Fassung gilt:** Der mit der gepinnten labkit-Version ausgelieferte Laborstandard und der konkrete Vertrag aus `protocol-check experiments/01-study/PROTOCOL-study.md --contract`; keine älteren Laboranweisungen. Historische Protokolle und Runs bleiben mit ursprünglichem Commit und Paketpin erhalten, statt für aktuelle Gates konvertiert zu werden.
- **Beleg:** Z. 3–7, 25–28, 110–148, 156–162, 214–219.
- **Lücke/Urteil:** Ohne konkrete Version und Vertrag lässt sich nicht sagen, welche zusätzlichen Felder dieses gepinnte Experiment verlangt. Die Erlaubnis zu dokumentierten Updates ist ausdrücklich, keine Ausnahme durch eigene Interpretation.
