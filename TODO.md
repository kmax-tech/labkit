# TODO — labkit

Stand: 2026-11-20. Diese Datei nennt den nächsten Auftrag, offene Entscheidungen und zurückgestellte Arbeit. Neue Vorhaben werden erst durch einen ausdrücklichen Auftrag zu Bau- oder Forschungsarbeit.

## Reihenfolge

**Gebaut und auf `main`, noch nicht veröffentlicht: Nachrechnung über mehrere Ausgabedateien und gemeinsame Lauf-Auswahl.** Gebaut: die Prompt-Anbindung im begrenzten Weg ([Notiz](docs/notes/2026-11-20-stagekit-prompt-binding-plan.md)) — `protocol-fill --prompts --prompt-file NAME=PATH`, `prompt_check.require_registered_templates` vor dem ersten Modellaufruf, Szenariotest mit Ersatzmodell. Als Nächstes erst auf Auftrag: ein konkreter Zwei-Stufen-Fall mit stagekit und festen Ersatzantworten, der zeigt, ob die Benutzung verständlich bleibt. Dabei muss die spätere stagekit-Anbindung ihre Zeilendateien nachvollziehbar aus den JSON-Stufenausgaben erzeugen und im Lauf registrieren. Die Vorlagenliste für `prompt_check.require_registered_templates` nimmt der Bereich aus stagekits eigener Auflösung (`stagekit.analysis.repro_hash.instrument_snapshot`: `uses_prompts` der Stufen plus Vorlagen der `llm_task`), nicht aus einer zweiten, von Hand gepflegten Liste; labkit prüft nur, was übergeben wird. Abnahme des Falls: (1) beide Stufen senden die geprüften Vorlagen, (2) fehlende oder veränderte Registrierung verhindert jeden Modellaufruf, (3) beide Ausgaben werden registriert und gemeinsam nachgerechnet. **Erprobt 2026-11-21** im lokalen Beispiel-Repo `~/projects/twostage-argument-demo` (feste Antworten über labkits Wiedergabe-Cache, kein Modellaufruf): alle drei Punkte durch Tests gezeigt (17 Tests, Exit 0), Punkt 3 nur mit einem ausgewiesenen Ersatz-Audit. 19 Nutzungsfunde (10 labkit, 8 stagekit, 1 Hook) im internen Beleg-Repo unter `2026-11-21-twostage-stagekit-trial/`; bewertet in `triage.md` daneben (18 bestätigt, 1 fehlgelesen, dazu neu: ein Lauf mit Modellantworten nennt im Laufdatensatz kein Modell, `finalize` meldet trotzdem „all clear“); keiner behoben. Auftragskandidaten: Modellaufrufe aus `llm-calls.jsonl` zählen (labkit), öffentliche Ablage von Ersatzantworten (labkit), gelesene Vorlagen und Eingaben ausweisen (stagekit), keine still reparierte Antwort (stagekit), Doku für stagekit-Bereiche — Auswahl beim Autor. Ein neuer Versuch in argmining27 bleibt separat freizugeben. Weder ein Modellversuch noch Änderungen an stagekit sind beauftragt.

| Status               | Thema                                           | Nächste Handlung                                                                                              |
|----------------------|-------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| Gebaut               | Mehrere Ausgabedateien nachrechnen              | `recheck.holds_outputs`; Szenario `tests/test_recheck_outputs_scenario.py`. Release beim Autor.               |
| Gebaut               | Antwortenden Lauf auswählen                     | Öffentlich: `recheck.answering_run_dir`; Test `tests/test_public_api.py`, `AnsweringRun`. Release beim Autor. |
| Entscheidung nötig   | argmining27 als zweiter stagekit-Anwendungsfall | Autor entscheidet; noch kein Versuchsstart.                                                                   |
| Eigener Folgeauftrag | Globale Freigaberegel                           | Umsetzungsplan und Vertragsänderung erforderlich; noch nicht gebaut.                                          |
| Eigener Auftrag      | Bestehende Labore umziehen                      | Pins, Protokolle und gestempelte Skripte je Repo prüfen.                                                      |

**Bereits abgeschlossen:** Der explorative Ablauf und Standard 0.33 sind auf `main`. `v0.114.0` wurde am 2026-11-20 auf `377da497` veröffentlicht und mit Tag gepusht. Danach gebaute Änderungen stehen unter „Unreleased“ im [CHANGELOG](CHANGELOG.md); daraus folgt kein weiterer Release-Auftrag. Release, Tag und Push bleiben beim Autor.

## Nächster Bauauftrag: mehrere Dateien nachrechnen

Problem: Ein Modell erzeugt Einwände, ein zweites beurteilt sie. Die Ergebniszahl braucht beide Ausgabedateien; die bestehende Nachrechnung erwartet nur eine. Zusätzlich wurde die Auswahl des Messlaufs in den Anwendungsbereichen mehrfach von Hand geschrieben.

1. **Nachrechnung erweitern — gebaut.** `recheck.holds_outputs` prüft die benötigten Ausgabedateien eines Laufs gemeinsam und berechnet daraus seine gespeicherten Ergebnisse nach. Szenariotest: zwei Dateien, korrekte Nachrechnung. Gegenfälle: zweite Datei fehlt, zweite Datei nach dem Lauf verändert, gespeichertes Ergebnis falsch. Jeder Gegenfall muss die Prüfung verweigern.
2. **Gemeinsame Lauf-Auswahl anbieten — gebaut.** `recheck.answering_run_dir(area, protocol)` verwendet die vorhandene Auswahl `recheck.chosen_run`: den übernommenen Lauf, sonst den gemäß bestehender Regel gewählten. Test: Ein neuerer Versuch ersetzt einen übernommenen Lauf nicht. Keine zweite Auswahlregel einführen. Gegen [Architektur, Public API](docs/architecture.md#public-api) geprüft: Der Name folgt dem README-Begriff „answering run“; der Einstieg liegt in `recheck`, weil `labkit.run` die Prüfschicht nicht importieren darf, und ist dort der einzige öffentliche Name.

Je Teil ein begrenzter Commit. Keine weitere allgemeine Planrunde. Format am Code geklärt: `recheck` liest Zeilendateien (ein JSON-Objekt je Zeile); stagekit schreibt jede Stufenausgabe als ein eingerücktes JSON-Dokument. Der Bereich schreibt daraus eigene Zeilendateien im Lauf und registriert sie; ein JSON-Dokument verweigert `recheck` mit dem Namen der Ausgabe. Die Abnahme umfasst den Zwei-Dateien-Ablauf und die Gegenfälle. Bestehende historische Nachrechnung, Codevergleich und Freigabebindung erhalten.

Hintergrund und Abgrenzung: [Zwei-Stufen-Plan](docs/notes/2026-11-20-two-stage-model-measurement.md). stagekit organisiert die Stufen; labkit sichert die Messung ab. labkit bleibt ohne Abhängigkeit von stagekit.

## Offene Entscheidungen — noch kein Bauauftrag

1. **Zweiter stagekit-Anwendungsfall.** Soll argmining27 den bisher vorgesehenen Fall counterfactual-worlds ersetzen oder ergänzen? Nach Freigabe prüft der erste Auftrag nur die Übertragung mit vorhandenen Antworten beziehungsweise kontrollierten Daten. Bei identischen Eingaben und gleicher Auswertung müssen die Zahlen exakt stimmen. Neue bezahlte Modellmessungen brauchen einen weiteren Forschungsauftrag. [Plan und offene Fragen](docs/notes/2026-11-20-two-stage-model-measurement.md#questions-for-the-author).
2. **Prompt-Nachweis und Wiederaufnahme.** Wo werden Prompt-Dateien angebunden, wie werden bezahlte Antworten nach Abbruch sicher wiederverwendet, und was zieht eine Wiederholung? Gesamtverfahren und Richter bei festen Generatorausgaben sind verschiedene Untersuchungen. Eine Vorlagen-Prüfsumme belegt allein nicht den gesendeten Prompt; Tests müssen Füllung und Übergang zum Modellaufruf abdecken. Noch keine stagekit-Änderung oder allgemeines stagekit-Skelett beschlossen. [Offene Funktionen](docs/notes/2026-11-20-two-stage-model-measurement.md#open-not-solved).
3. **Probelauf-Zahlen.** Sollen bereits gesehene Zahlen aus Probeläufen eine spätere Registrierung binden? Bis zur Entscheidung bleibt der Vertrag unverändert: Ein belegter Probelauf bindet keine Registrierung. [Startbelege und Grenzen](docs/notes/2026-11-18-run-start-record.md).
4. **Herkunft berichteter Zahlen.** Welche Quellen und nachvollziehbaren Korrekturen sind zulässig? Von den Regeln für Audit-Aufzeichnungen getrennt behandeln; kein pauschales Änderungsverbot für alle Belegarten. [Einzelfragen](docs/notes/2026-11-11-open-assignments.md).
5. **Fortgesetzte Ergebniszeilen.** Welche Skripte müssen welche Herkunftsdaten liefern? Die bisherige Prüfung erfasst dynamisch geladenen Code nicht vollständig. Vor einer zusätzlichen Gate-Prüfung erst den Vertrag festlegen; kein neuer Check aus diesem Eintrag. [Bisherige Grenzen](labkit/checks/run_record_check.py).
6. **Regel- und Formatzuordnungen.** Offene Fragen betreffen unter anderem gespeicherte oder berechnete Vergleichsurteile, leere Code-Bereiche von Versprechen und die Grundlage von `kind` / `[kept]` in der Registrierungssperre. Am geltenden Text und am aktuellen Inventar prüfen, nicht anhand alter Befundzahlen. [Einzelentscheidungen](docs/notes/2026-11-11-open-assignments.md), [Zuordnungsprüfung](docs/notes/2026-11-11-rule-assignment-review.md).
7. **Nutzungsrunde ergänzen.** Die Runde vom 2026-11-13 lieferte 6 und 4 vollständige Ergebnisse; der registrierte Gewinn ist „nicht gezeigt“. Sechs von 18 Versuchen wurden am Zeitlimit abgeschnitten. Ob sie wiederholt werden, entscheidet der Autor. Eine Ergänzung auf dem damaligen Paketstand von einer neuen Runde auf heutigem labkit unterscheiden. [Ergebnis und Funde](docs/notes/2026-11-13-usage-round-24-findings.md).

## Beschlossen, noch nicht umgesetzt: globale Freigaberegel

Nutzer oder Labor sollen zwischen „streng“ und „mit dokumentiertem Audit-Einwand“ wählen können. Der ausführende Agent darf die Einstellung nicht lockern. Die Alternative ist keine bestandene Prüfung: Entscheidung, Grund, offene Befunde und betroffene Aussagen müssen im Bericht erkennbar bleiben. Technische Voraussetzungen wie lesbare Belege und vorhandene Messwerte bleiben verbindlich.

Vor dem Bau sind Geltungsbereich, Speicherort und Weitergabe an Gates, Zweitprüfung und Bericht festzulegen; die Umsetzung braucht eine versionierte Vertragsänderung. Es gibt dafür noch keine verfügbare Flag. [Bestandsaufnahme und beschlossene Grenzen](docs/notes/2026-11-16-audit-record-lifecycle.md).

Originalantworten, ursprüngliche Befunde und Zweitprüfungen bleiben erhalten. Entscheidungen und erzeugte Darstellungen dürfen geändert werden; alte Bestätigungen gelten nicht automatisch für neue Entscheidungen. Ein zusätzlicher Inhaltsvergleich vor dem ersten Commit bleibt zurückgestellt: Die lokale Anfangskopie ist kein unabhängiger Echtheitsnachweis. Nicht jeder uncommittete Zwischenstand muss aufbewahrt werden.

## Notiert, nicht geplant

Diese Punkte sind keine neue Audit-Welle und keine automatischen Release-Bedingungen. Vor einem Bau den aktuellen Fall nachstellen oder den jeweils genannten Auslöser belegen. Die vollständigen ursprünglichen Beschreibungen bleiben im [Verlauf](TODO-history-2026-11-20.md#notiert-nicht-geplant).

### Nutzungsfunde zu Wartung und Lesbarkeit

| Thema                             | Status oder Auslöser                                                                                                                                                                           |
|-----------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mehrstufige Modellversuche        | Entwurf vorhanden; der begrenzte nächste Bauauftrag steht am Anfang dieser Datei.                                                                                                              |
| Vier Schritte in `evaluate_rows`  | Empfohlene Gliederung: Antworten lesen, Werte je Einheit bilden, Qualitätsprüfungen, Kriterien. Keine starre Pflicht; nur übernehmen, wo sie hilft. Hausstiländerung wäre ein eigener Auftrag. |
| Laufquellen aus anderen Bereichen | Zurückgestellt. Die jetzige Herkunftsprüfung bleibt auf denselben Bereich begrenzt; Erweiterung braucht eindeutige Quellen und Prüfregeln.                                                     |
| Prompt-Erklärungen                | Ein unausgefüllter Erklärungssatz über einem Prompt-Block wird nicht automatisch gemeldet. Neue Prüfung erst mit konkretem übersehenem Fehler.                                                 |
| Veraltete argmining27-Anleitung   | Externer Rollout: den alten `bin/lib exp … --cost seconds`-Hinweis am aktuellen Repo prüfen.                                                                                                   |

Belege der ursprünglichen Funde: [argmining27-Fundliste](TODO-history-2026-11-20.md#nutzungsfunde-zu-wartung-und-lesbarkeit--argmining27-experimente-0204-2026-11-17). Bereits behoben sind Konstanten-Typprüfung, verständlichere statische Warnungen, Kaltleser-Hinweis bei niedrigen Kosten, die Meldung zum abgebrochenen ersten Start, Schreibhinweise und getrennte Prompt-Blöcke. Diese Reparaturen sind keine offenen Bauaufträge.

### Protokolle verständlicher erklären — vorerst nur notiert

Anlass: Im gelesenen [Protokoll von argmining27 Experiment 06](/Users/max/projects/argmining27/experiments/06-missci-objection-weighting/PROTOCOL-missci-objection-weighting.md:5) bündelt die Summary Ergebnis, Erklärung und Grenzen in zwei langen Sätzen; die Begriffsliste steht vor der Frage. Das Feedback nennt auch Experimente 04 und 05; sie sind für diesen Eintrag nicht geprüft.

Begrenzter Folgeplan für Anleitung und Vorlagen, nach dem laufenden Prompt-Auftrag:

1. **Frage zuerst.** Den Zweck in Alltagssprache erklären, dann ein Beispiel und die benötigten Begriffe. Leserführung: Frage → Beispiel und Vergleich → Messung und Kriterium → Ergebnis → Bedeutung und Grenzen.
2. **Bedingungen vergleichbar machen.** Wenn mehrere Varianten vorkommen, eine kleine Tabelle mit Bedingung, Beispiel und Zweck anbieten; im Belegfall kein Zusatz, echter Einwand, irrelevanter Zusatz und Scheineinwand.
3. **Ergebnis und Deutung trennen.** Die Summary beantwortet die Frage knapp; Einzelzahlen und Fallkennungen stehen in einer anschließenden Tabelle. Unterschiedliche Messverfahren getrennt beurteilen. Fehlender Messspielraum, verfehltes Kriterium und eine unklare Kontrollbedingung sind verschiedene Grenzen; keine pauschale Schlussfolgerung daraus machen.
4. **An einem Beispiel prüfen.** Einen lesbaren Entwurf mit dem Original abgleichen: Aussagen, Vergleiche, Unsicherheit, Prompts und technische Prüfdetails bleiben erhalten. Pflichtfelder nicht ohne Prüfung ihrer Leser verschieben oder umbenennen. Erst danach über allgemeine Vorlagenänderungen entscheiden.

Kein neuer Gate-Check, keine zusätzliche Erfolgspflicht und kein Auftrag, historische Protokolle in argmining27 umzuschreiben. Vollständige Prompts und technische Referenzangaben bleiben zugänglich; die kurze Erklärung soll ihnen vorausgehen. Der Eintrag ändert die aktuelle Baureihenfolge nicht.

### Audit und Wartbarkeit

| Thema                                   | Wann wieder aufgreifen?                                                                                                                                                                                                                                                                                                                 |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Gemeinsame Einordnung verlorener Läufe  | Nur gemäß [begrenztem Entwurf](docs/notes/2026-11-19-shared-run-classification-plan.md). Gemeinsam gehören Einordnung und Gründe; keine pauschale gemeinsame Meldungsfunktion bauen.                                                                                                                                                    |
| Doppelte Berechnung der Audit-Abdeckung | Erst bei gemessenen Kosten, widersprüchlichen Beobachtungen oder konkretem Wartungsproblem. [Kontrollfluss-Review](docs/notes/2026-11-12-control-flow-review.md).                                                                                                                                                                       |
| Protokollkopf gemeinsam schreiben       | Vorher Bestand zu `--change-kind`, doppelten Feldern und `--force` aktuell prüfen. [Früherer Plan](TODO-history-2026-11-12.md#umfang-und-zuständigkeiten-vereinfachen).                                                                                                                                                                 |
| Weitere Abstraktionen und Doppelarbeit  | Kein Umbau nur für ein einheitliches Muster oder kleinere Funktionen; konkreten Nutzen belegen. [Testmodell](docs/notes/2026-11-10-test-model.md), [Wartbarkeitsplan](docs/notes/2026-11-03-maintainability-repair-plan.md).                                                                                                            |
| Berichts-Review aufteilen               | Bleibt ein Ganzes; erst bei gemessenem Aufwand veralteter Reviews neu bewerten. [Entscheidung](docs/notes/2026-11-06-report-review-stays-whole.md).                                                                                                                                                                                     |
| Kleine Audit-Reste                      | Staged-Check des Vorgängers in anderem Bereich, „cut“ im Hilfetext, Umbenennung von Stationen und `FieldReport.missing_must`: nur beim Anfassen oder nach aktueller Nachstellung. [Audit vom 18.11.](docs/notes/audit-2026-11-18.md), [vollständiger Verlauf](TODO-history-2026-11-20.md#codeklarheit-zuständigkeiten-und-wartbarkeit). |

### Aufzeichnungen und bekannte Grenzen

| Thema                                               | Grenze oder nächster Auslöser                                                                                                                                                                                                                                                                                           |
|-----------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Gezeigte Laufkennungen im Audit                     | Die spätere Datennutzungswarnung vergleicht Zeiten, nicht die tatsächlich gezeigten Unterlagen. Exakte Erfassung braucht eine eigene Formatentscheidung. [Explorationsplan](docs/notes/2026-11-14-exploratory-workflow-plan.md).                                                                                        |
| Wiederholungsantworten                              | Im eigenen Laufordner aufbewahren; erst zusammen mit Schritt 6 des [stagekit-Plans](docs/notes/2026-11-03-stagekit-plan.md) bauen.                                                                                                                                                                                      |
| Öffentliche Namen und Code-Dateiformate             | Alte Namen nur nach Übergangsversion entfernen. `source-untracked/` und `code/` zusammenzuführen wäre ein eigener Formatbruch; kein Bauauftrag.                                                                                                                                                                         |
| Fremder und dynamisch geladener Code                | Aufzeichnung und historische Vergleichbarkeit sind nicht gleichbedeutend. Insbesondere externe importierte Module können die Nachrechnung „nicht verifizierbar“ machen; am konkreten Fall prüfen, keine stille Ausnahme.                                                                                                |
| Nachrechnung vor dem letzten Lesen                  | `recheck` ruft die Auswertung auf, bevor es den damaligen `[kept]`-Schlüssel liest; ist dieser Text nicht lesbar, wurde schon gerechnet. Harmlos nur unter der dokumentierten Voraussetzung, dass die Auswertung nichts schreibt (`labkit/checks/recheck.py`, Modul-Docstring). Zurückgestellt (Einordnung 2026-11-20). |
| Zeilenweiser Prompt-Vergleich (`lanes`, Konstanten) | Zeilen mit Platzhalter werden nie verglichen; Reihenfolge und Zuordnung zur Vorlage nicht geprüft; Konstanten ohne `PROMPT`-Namen liest die statische Prüfung nicht. Bleibt so; Änderung wäre ein eigener Vertragsauftrag. [Grenzen](docs/notes/2026-11-20-stagekit-prompt-binding-plan.md#known-limits-unchanged).     |
| Laufüberwachung und gleichzeitige Starts            | Restfälle zu PID-Wiederverwendung, fehlendem `ps`, `python -m`, Kollisionen und Zeitzonen erst konkret nachstellen; keine automatische Verzögerung. [Grenzen](docs/notes/2026-11-04-liveness-and-wait.md). UTC-Startbelege sind bereits gebaut.                                                                         |
| Änderungen vor erstem Commit                        | Nicht manipulationssicher belegt. Zusätzliche Zeugen oder Entfernen früher veröffentlichter Belege brauchen eine eigene Entscheidung.                                                                                                                                                                                   |
| Weitere Parser-, Git- und Bedienfälle               | Nur nach aktueller Nachstellung. Plausible, unbestätigte Altfunde sind keine Reparaturaufträge. [Verlauf](TODO-history-2026-11-20.md).                                                                                                                                                                                  |
| r2-Laufzeit                                         | Unverändert lassen, wie entschieden. Einzelmessung und ganze Auswertung nicht verwechseln. [Messung und Grenze](docs/notes/2026-11-15-usage-round-24-acceptance.md#exact-r2-cost-2026-11-16).                                                                                                                           |
| Feste Vorhersagen und Annotierung                   | Gerüstpflichten erst am konkreten Anwendungsfall klären; kein neuer Versuch oder Compute-Skelett beschlossen.                                                                                                                                                                                                           |

### Vorschläge, die weitere Belege brauchen

1. **Regelauswahl durch ein Labor:** methodische Wahlmöglichkeiten von technischen Voraussetzungen und ihren Abhängigkeiten trennen. Keine allgemeine Schalterverwaltung vorweg bauen; von der globalen Audit-Freigaberegel getrennt halten.
2. **Vorab festgelegter Bewertungsplan:** Bewerter an bekannten richtigen und falschen Antworten prüfen, unwirksame Läufe als „nicht getestet“ zählen, frühere Nutzung der Testdaten dokumentieren. Erst am Benchmark-Piloten prüfen, ob diese Ergänzungen eine Entscheidung ändern.
3. **Ausfallzustände der Prüfungen:** Ein erklärter Ausgang je Fehlerfall könnte getestet werden. Erst bei einem konkreten Fall aufgreifen, in dem eine ausgefallene Prüfung nichts meldet; kein stilles Durchlassen übernehmen.
4. **Formulare und öffentliche Typen vereinfachen:** weitere Änderungen erst nach Schreib- und Nutzungsprobe beziehungsweise bei konkretem Bedarf.

Herkunft und Grenzen der beiden Anregungen aus Academic Research Skills bleiben im [Verlauf](TODO-history-2026-11-20.md#vorschläge-die-weitere-belege-brauchen). Keiner dieser Vorschläge ist ein Bauauftrag.

## Bei der nächsten Nutzung beobachten

Kein Modellversuch ohne Forschungsauftrag. Technisch ist die Übergabe von Auswahl und Vorgeschichte an den Prüfer abgenommen; ob echte Agenten dadurch wissenschaftlich besser entscheiden, ist nicht untersucht.

1. **Lieferfähigkeit:** vollständige Zahl und fachliches Urteil; brauchbare Reparaturwege; Trennung von Beschreibung und Ergebnisbehauptung.
2. **Entscheidungen:** Begründung, Häufigkeit und Kosten von Begrenzungen und Zweitprüfungen; ob offene Fragen tatsächlich geklärt werden.
3. **Aufwand:** Fehlalarme, Fehlbedienung, Audit-Runden, Wartezeit und Kosten aus vollständigen Transkripten; keine Deduplizierung ohne belegtes Problem.
4. **Wirksame Prüfungen:** aktuelle Bestände aus `python -m labkit.tools.check_inventory`, echte Fehler und Fehlalarme je zugeordneter Ursache; kein neues Register oder neue Regel allein aus Zählungen.
5. **Sporadische Testfehler:** Bei erneutem Auftreten von `test_runlog_wait` oder Stop-Budget-Fehlern volle Ausgabe sichern und nachstellen. Zeitgrenzen nicht wegen unbelegten Lastverdachts erhöhen.
6. **Hinweise und Textqualität:** Befolgen Agenten Kaltleser- und Schreibhinweise? Platzhalter, kopierte Conclusions und Prompt-Erklärungen nur bei erneutem Problem aufgreifen.

## Rollout und Aufgaben außerhalb dieses Repos

Externe Repos behalten ihren Pin bis zu einem eigenen Auftrag. Historische Läufe bleiben mit damaligem Commit und Pin reproduzierbar. Alte Vorlagen nicht ungeprüft von Hand ändern; den jeweiligen aktuellen Bestand zuerst lesen.

| Ort                               | Eigener Auftrag oder Grenze                                                                                                                                                                     |
|-----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Labor- und Studi-Repos            | Migration nach [CHANGELOG](CHANGELOG.md) und [Einstieg](docs/student-repos.md): Pins, Hooks und neu gestempelte Beispiele prüfen.                                                               |
| labkit-paper                      | Nutzungsrunde, Branch-Zusammenführung, eigener Paket-Pin und Agenten-Image getrennt behandeln.                                                                                                  |
| stagekit und Labor-Pipelines      | Weitere Schritte des [stagekit-Plans](docs/notes/2026-11-03-stagekit-plan.md); Änderungen und Versuchsstart dort separat beauftragen.                                                           |
| Codex-Hooks und Pilot-Images      | Installation und Pins separat; das effektive `exec_command.workdir` fehlt im Hook-Ereignis. [Vertrag](docs/codex-hooks.md).                                                                     |
| Konkrete externe Reparaturen      | `fallacy-dataset-generation`: Bilanz mit Eingabefingerabdruck; `counterfactual-worlds`: alte `endpoint`-Form; uniagent: TOML-Quoting; argmining27: veraltete Anleitung. Jeweils Bestand prüfen. |
| Ruhende Repos                     | Pins unverändert; bei neuer Arbeit in `thesis-dagidir` eigener Import- und Pin-Umzug. Vollständige Liste im [Verlauf](TODO-history-2026-11-20.md#rollout-und-aufgaben-außerhalb-dieses-repos).  |
| Veröffentlichung und Hausmaterial | Release, Tag und Push beim Autor; PyPI, Hausvorlagen, Hausregeln und Löschung unbenutzter Vorlagen sind eigene Aufträge.                                                                        |

## Abgeschlossen — Nachweise statt neue Aufträge

Der vollständige bisherige TODO-Text ist im [Verlauf vom 20.11.](TODO-history-2026-11-20.md) erhalten. Er enthält bewusst auch überholte Zwischenstände; für die aktuelle Reihenfolge gilt diese Datei. Ältere Archive: [12.11.](TODO-history-2026-11-12.md), [06.11.](TODO-history-2026-11-06.md).

Geltende Verträge stehen in [Architektur](docs/architecture.md), [Ablauf](docs/workflow.md), [Laborstandard](labkit/docs/standard.md) und [CHANGELOG](CHANGELOG.md), nicht in historischen Arbeitsaufträgen.

| Abgeschlossen                                                                | Nachweise                                                                                                                                                                                                                                                                                           |
|------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Explorative Entwicklung, Quellen, historische Nachrechnung und Standard 0.33 | [Vertragsplan](docs/notes/2026-11-14-exploratory-workflow-plan.md), [Standardvorschlag und Abgleich](docs/notes/2026-11-19-standard-0.33-proposal.md); in 0.114.0 veröffentlicht.                                                                                                                   |
| Nutzungsreparaturen und gezielte Wirkung von „nicht beurteilbar“             | [Abnahme](docs/notes/2026-11-15-usage-round-24-acceptance.md), [Entscheidungswirkung](docs/notes/2026-10-23-decision-review-history.md). Wirkung auf echte Agenten nicht gezeigt.                                                                                                                   |
| Startbelege und verlorene Messungen                                          | [Startbeleg](docs/notes/2026-11-18-run-start-record.md), [verlorene erste Messung](docs/notes/2026-11-18-lost-first-measurement.md).                                                                                                                                                                |
| Audit-Reparaturen und Kommandowege                                           | [Audit 18.11.](docs/notes/audit-2026-11-18.md), [Audit 19.11.](docs/notes/2026-11-19-repo-audit.md). Kein Auftrag zu einer weiteren allgemeinen Audit-Welle.                                                                                                                                        |
| Audit 21.11. — repariert, nicht veröffentlicht                               | [Audit 21.11.](docs/notes/2026-11-21-repo-audit.md): alle sieben Punkte und `labkit-hooks install --help` (installierte statt Hilfe) auf `main`, 144eee70..8d868e98. `.githooks/checks full` auf 8d868e98: Exit 0, 4390 passed, 1 skipped (Tree vor/nach gleich). Reste unter „Audit-Reste 21.11.“. |
| Formulare und Terminologie                                                   | [Feldauswahl](docs/notes/2026-11-13-protocol-field-selection-plan.md), [Begriffe](docs/notes/2026-11-14-null-band-wording-plan.md).                                                                                                                                                                 |

**Audit-Reste 21.11.** (aus den Berichten der Reparatur, nicht gebaut):

1. preflight-Station 5 kann noch an `RuntimeError`/`OSError` aus `scope_sha.exploration_basis` abbrechen.
2. `console.asks_help` greift auch, wenn `--help` als Wert einer Option steht (`labkit-params AREA --run --help` zeigt die Hilfe); Docstring und CHANGELOG sagen es nicht.
3. `repo.py`: `PROTOCOL_GLOB`, `PROTOCOL_FILE`, `PROTOCOL_NAME` sind drei Formen eines Namens, nur per Kommentar unterschieden; `protocol_file_name`-Docstring klingt nach Nachschlagen.
4. `claude-hook EVENT EXTRA` ignoriert das Zusatzwort weiter (Ablehnen würde jeden Bash-Aufruf blockieren); `labkit-calltree` reicht Wörter nach dem Ziel absichtlich durch.
5. Verhaltensänderungen zum Ansagen im Release: `protocol-fill` lehnt jetzt auch eine Option ab, die die Operation nicht nimmt (`--list --force`); `PROTOCOL-.md` gilt nicht mehr als Protokollname; ein ungeschlossener Prompt-Block blockiert jetzt auch `code-check`.
6. Prüferabdeckung: der unabhängige Leser (`code-clarity`) las am Ende nur `params.py`, `repo.py`, `console.py` und das CHANGELOG; jeder Agent ließ seinen eigenen Diff lesen (A und D nicht).

### 6b. Die Einzelprüfung der Blocker umsetzen — abgeschlossen 2026-11-12, mit drei Grenzen

Historischer Abschluss mit damaligen Grenzen: [Verlauf](TODO-history-2026-11-20.md#6b-die-einzelprüfung-der-blocker-umsetzen--abgeschlossen-2026-11-12-mit-drei-grenzen). Die dort noch genannte bereichsweite Nachrechnung ist inzwischen durch die Prüfung je Protokoll ersetzt.

### 6c. Ein klares Testmodell und der Umbau der Checks — abgeschlossen 2026-11-12

[Abstraktionsbilanz und Testmodell](docs/notes/2026-11-10-test-model.md): kein weiterer Umbau nur für ein einheitliches Muster. Die Überschriften zu 6b und 6c bleiben als Ziele bestehender Verweise erhalten.
