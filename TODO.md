# TODO — labkit

Stand: 2026-11-20. Diese Datei nennt den nächsten Auftrag, offene Entscheidungen und zurückgestellte Arbeit. Neue Vorhaben werden erst durch einen ausdrücklichen Auftrag zu Bau- oder Forschungsarbeit.

## Reihenfolge

**Als Nächstes bauen: Nachrechnung über mehrere Ausgabedateien und gemeinsame Lauf-Auswahl.** Beide Teile sind geplant, noch nicht gebaut. Dafür sind weder ein Modellversuch noch Änderungen an stagekit beauftragt.

| Status               | Thema                                           | Nächste Handlung                                                                                                   |
|----------------------|-------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| Beauftragt           | Mehrere Ausgabedateien nachrechnen              | Zwei-Dateien-Fall und Fehlerfälle umsetzen; eigener Commit.                                                        |
| Beauftragt           | Antwortenden Lauf auswählen                     | Bestehende Auswahl wiederverwenden; neuere Versuche dürfen einen übernommenen Lauf nicht ersetzen; eigener Commit. |
| Entscheidung nötig   | argmining27 als zweiter stagekit-Anwendungsfall | Autor entscheidet; noch kein Versuchsstart.                                                                        |
| Eigener Folgeauftrag | Globale Freigaberegel                           | Umsetzungsplan und Vertragsänderung erforderlich; noch nicht gebaut.                                               |
| Eigener Auftrag      | Bestehende Labore umziehen                      | Pins, Protokolle und gestempelte Skripte je Repo prüfen.                                                           |

**Bereits abgeschlossen:** Der explorative Ablauf und Standard 0.33 sind auf `main`. `v0.114.0` wurde am 2026-11-20 auf `377da497` veröffentlicht und mit Tag gepusht. Danach gebaute Änderungen stehen unter „Unreleased“ im [CHANGELOG](CHANGELOG.md); daraus folgt kein weiterer Release-Auftrag. Release, Tag und Push bleiben beim Autor.

## Nächster Bauauftrag: mehrere Dateien nachrechnen

Problem: Ein Modell erzeugt Einwände, ein zweites beurteilt sie. Die Ergebniszahl braucht beide Ausgabedateien; die bestehende Nachrechnung erwartet nur eine. Zusätzlich wurde die Auswahl des Messlaufs in den Anwendungsbereichen mehrfach von Hand geschrieben.

1. **Nachrechnung erweitern.** `recheck` prüft die benötigten Ausgabedateien eines Laufs gemeinsam und berechnet daraus seine gespeicherten Ergebnisse nach. Szenariotest: zwei Dateien, korrekte Nachrechnung. Gegenfälle: zweite Datei fehlt, zweite Datei nach dem Lauf verändert, gespeichertes Ergebnis falsch. Jeder Gegenfall muss die Prüfung verweigern.
2. **Gemeinsame Lauf-Auswahl anbieten.** Eine öffentliche Funktion verwendet die vorhandene Auswahl `recheck.chosen_run`: den übernommenen Lauf, sonst den gemäß bestehender Regel gewählten. Test: Ein neuerer Versuch ersetzt einen übernommenen Lauf nicht. Keine zweite Auswahlregel einführen. Name und öffentlicher Einstieg werden gegen die vorhandene Schnittstelle in [Architektur, Public API](docs/architecture.md#public-api) geprüft.

Je Teil ein begrenzter Commit. Keine weitere allgemeine Planrunde. Die nötigen Formate der Ausgabedateien sind am konkreten Fall zu prüfen; stagekits JSON-Ausgaben und labkits Zeilendateien nicht ungeprüft gleichsetzen. Die Abnahme umfasst den Zwei-Dateien-Ablauf und die Gegenfälle. Bestehende historische Nachrechnung, Codevergleich und Freigabebindung erhalten.

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

### Audit und Wartbarkeit

| Thema                                   | Wann wieder aufgreifen?                                                                                                                                                                                                                                                                                                           |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Gemeinsame Einordnung verlorener Läufe  | Nur gemäß [begrenztem Entwurf](docs/notes/2026-11-19-shared-run-classification-plan.md). Gemeinsam gehören Einordnung und Gründe; keine pauschale gemeinsame Meldungsfunktion bauen.                                                                                                                                              |
| Doppelte Berechnung der Audit-Abdeckung | Erst bei gemessenen Kosten, widersprüchlichen Beobachtungen oder konkretem Wartungsproblem. [Kontrollfluss-Review](docs/notes/2026-11-12-control-flow-review.md).                                                                                                                                                                 |
| Protokollkopf gemeinsam schreiben       | Vorher Bestand zu `--change-kind`, doppelten Feldern und `--force` aktuell prüfen. [Früherer Plan](TODO-history-2026-11-12.md#umfang-und-zuständigkeiten-vereinfachen).                                                                                                                                                           |
| Weitere Abstraktionen und Doppelarbeit  | Kein Umbau nur für ein einheitliches Muster oder kleinere Funktionen; konkreten Nutzen belegen. [Testmodell](docs/notes/2026-11-10-test-model.md), [Wartbarkeitsplan](docs/notes/2026-11-03-maintainability-repair-plan.md).                                                                                                      |
| Berichts-Review aufteilen               | Bleibt ein Ganzes; erst bei gemessenem Aufwand veralteter Reviews neu bewerten. [Entscheidung](docs/notes/2026-11-06-report-review-stays-whole.md).                                                                                                                                                                               |
| Kleine Audit-Reste                      | Staged-Check des Vorgängers in anderem Bereich, „cut“ im Hilfetext, Umbenennung von Stationen und `FieldReport.missing_must`: nur beim Anfassen oder nach aktueller Nachstellung. [Audit vom 18.11.](docs/audit-2026-11-18.md), [vollständiger Verlauf](TODO-history-2026-11-20.md#codeklarheit-zuständigkeiten-und-wartbarkeit). |

### Aufzeichnungen und bekannte Grenzen

| Thema                                    | Grenze oder nächster Auslöser                                                                                                                                                                                                                   |
|------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Gezeigte Laufkennungen im Audit          | Die spätere Datennutzungswarnung vergleicht Zeiten, nicht die tatsächlich gezeigten Unterlagen. Exakte Erfassung braucht eine eigene Formatentscheidung. [Explorationsplan](docs/notes/2026-11-14-exploratory-workflow-plan.md).                |
| Wiederholungsantworten                   | Im eigenen Laufordner aufbewahren; erst zusammen mit Schritt 6 des [stagekit-Plans](docs/notes/2026-11-03-stagekit-plan.md) bauen.                                                                                                              |
| Öffentliche Namen und Code-Dateiformate  | Alte Namen nur nach Übergangsversion entfernen. `source-untracked/` und `code/` zusammenzuführen wäre ein eigener Formatbruch; kein Bauauftrag.                                                                                                 |
| Fremder und dynamisch geladener Code     | Aufzeichnung und historische Vergleichbarkeit sind nicht gleichbedeutend. Insbesondere externe importierte Module können die Nachrechnung „nicht verifizierbar“ machen; am konkreten Fall prüfen, keine stille Ausnahme.                        |
| Laufüberwachung und gleichzeitige Starts | Restfälle zu PID-Wiederverwendung, fehlendem `ps`, `python -m`, Kollisionen und Zeitzonen erst konkret nachstellen; keine automatische Verzögerung. [Grenzen](docs/notes/2026-11-04-liveness-and-wait.md). UTC-Startbelege sind bereits gebaut. |
| Änderungen vor erstem Commit             | Nicht manipulationssicher belegt. Zusätzliche Zeugen oder Entfernen früher veröffentlichter Belege brauchen eine eigene Entscheidung.                                                                                                           |
| Weitere Parser-, Git- und Bedienfälle    | Nur nach aktueller Nachstellung. Plausible, unbestätigte Altfunde sind keine Reparaturaufträge. [Verlauf](TODO-history-2026-11-20.md).                                                                                                          |
| r2-Laufzeit                              | Unverändert lassen, wie entschieden. Einzelmessung und ganze Auswertung nicht verwechseln. [Messung und Grenze](docs/notes/2026-11-15-usage-round-24-acceptance.md#exact-r2-cost-2026-11-16).                                                   |
| Feste Vorhersagen und Annotierung        | Gerüstpflichten erst am konkreten Anwendungsfall klären; kein neuer Versuch oder Compute-Skelett beschlossen.                                                                                                                                   |

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

| Abgeschlossen                                                                | Nachweise                                                                                                                                                                         |
|------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Explorative Entwicklung, Quellen, historische Nachrechnung und Standard 0.33 | [Vertragsplan](docs/notes/2026-11-14-exploratory-workflow-plan.md), [Standardvorschlag und Abgleich](docs/notes/2026-11-19-standard-0.33-proposal.md); in 0.114.0 veröffentlicht. |
| Nutzungsreparaturen und gezielte Wirkung von „nicht beurteilbar“             | [Abnahme](docs/notes/2026-11-15-usage-round-24-acceptance.md), [Entscheidungswirkung](docs/notes/2026-10-23-decision-review-history.md). Wirkung auf echte Agenten nicht gezeigt. |
| Startbelege und verlorene Messungen                                          | [Startbeleg](docs/notes/2026-11-18-run-start-record.md), [verlorene erste Messung](docs/notes/2026-11-18-lost-first-measurement.md).                                              |
| Audit-Reparaturen und Kommandowege                                           | [Audit 18.11.](docs/audit-2026-11-18.md), [Audit 19.11.](docs/notes/2026-11-19-repo-audit.md). Kein Auftrag zu einer weiteren allgemeinen Audit-Welle.                            |
| Formulare und Terminologie                                                   | [Feldauswahl](docs/notes/2026-11-13-protocol-field-selection-plan.md), [Begriffe](docs/notes/2026-11-14-null-band-wording-plan.md).                                               |

### 6b. Die Einzelprüfung der Blocker umsetzen — abgeschlossen 2026-11-12, mit drei Grenzen

Historischer Abschluss mit damaligen Grenzen: [Verlauf](TODO-history-2026-11-20.md#6b-die-einzelprüfung-der-blocker-umsetzen--abgeschlossen-2026-11-12-mit-drei-grenzen). Die dort noch genannte bereichsweite Nachrechnung ist inzwischen durch die Prüfung je Protokoll ersetzt.

### 6c. Ein klares Testmodell und der Umbau der Checks — abgeschlossen 2026-11-12

[Abstraktionsbilanz und Testmodell](docs/notes/2026-11-10-test-model.md): kein weiterer Umbau nur für ein einheitliches Muster. Die Überschriften zu 6b und 6c bleiben als Ziele bestehender Verweise erhalten.
