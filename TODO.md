# TODO — labkit

Stand: 2026-11-12. Diese Datei hält die aktuelle Reihenfolge, offene Entscheidungen und die Auslöser zurückgestellter Arbeit. Abgeschlossene Zwischenstände sind keine neuen Aufträge.

Der vollständige Stand vor dieser Bereinigung liegt im [Verlauf vom 2026-11-12](TODO-history-2026-11-12.md); ältere Herleitungen im [Verlauf vom 2026-11-06](TODO-history-2026-11-06.md). Geltende Verträge stehen in [Architektur](docs/architecture.md), [README](README.md), [Laborstandard](labkit/docs/standard.md) und [CHANGELOG](CHANGELOG.md).

## Reihenfolge

Die technischen Aufgaben 2–6 einschließlich 6b und 6c sind abgeschlossen. Die bekannten Grenzen stehen unten; sie begründen keine weitere allgemeine Umbau- oder Prüfrunde. Der nächste größere Schritt ist Aufgabe 7.

### 7. Die nächste Nutzungsrunde durchführen — nach den Aufgaben 2–6 und 6c

Versuchsdesign, Bewertung und Start brauchen einen eigenen Forschungsauftrag des Autors. Aus dieser TODO folgt weder ein Versuchsstart noch ein Rollout. Die Runde soll prüfen, ob Agenten fachlich korrekte Arbeit verlässlicher und mit weniger Aufwand abschließen. Sie bewertet den abgeschlossenen Umbau als Paket; keine Vorhersage je Einzeländerung.

Vorbereitung im fremden Repo erst nach gesondertem Auftrag und aktueller Bestandsprüfung: `labkit-paper` hat einen Pin im Agenten-Image und einen eigenen Paket-Pin. Der letzte gelesene Stand vom 2026-11-08 nannte `sandbox/labkit.pin` bei `58aa7ae1` und `requirements.txt` bei `v0.85.0`; Bereiche 22 und 23 lagen nur auf `usage-round-4`, auf `main` standen offene Änderungen aus Bereich 09. Das ist historische Vorbereitung, keine Aussage über den heutigen Stand. Offen ist die Entscheidung über Branch-Zusammenführung und Pin-Anhebung. Push, Merges im fremden Repo und Versuchsstart bleiben beim Autor.

Für Design und bisherige Ergebnisse: [One-explainer-Plan](docs/notes/2026-11-04-one-explainer-plan.md) und [Vereinfachungsplan](docs/notes/2026-11-02-workflow-simplification.md). Die zu beobachtenden Fragen stehen im Abschnitt „Bei der nächsten Nutzung beobachten“.

## Offene Entscheidungen — kein Bauauftrag

1. **Integrität von Laufausgaben und Audit-Belegen.** Zwei getrennte Verträge klären: Woher muss eine berichtete Zahl stammen, und welche Entscheidungen, Ergänzungen oder Korrekturen dürfen Belege verändern? Vor einem Vertrag zu Audit-Belegen die Änderungen lesen, die labkit selbst schreibt. Kein gemeinsamer pauschaler Unveränderlichkeitssatz; Grundsatz ist nachvollziehbare Herkunft. Bestehende Sperren bleiben bis zu einer ausdrücklichen Entscheidung bestehen. [Bisherige Einzelprüfungen](docs/notes/2026-11-11-open-assignments.md).
2. **Herkunft fortgesetzter Zeilen.** Anderer Code ist nicht grundsätzlich unzulässig. Vor einer zusätzlichen Gate-Prüfung festlegen, welche Skripte welche Herkunftsdaten liefern müssen. `finalize` vergleicht die Zeilen-Digests nicht; die beiden Skelett-Prüfungen halten Skript- und lokale Helferänderungen, dynamisch geladener Code ist nicht erfasst. Der Helferfall ist getestet (`tests/test_apply_skeleton.py`). Keine zusätzliche Prüfung ohne eigenen Auftrag. [Grenzen](labkit/checks/run_record_check.py), `_continued_with_other_code`.
3. **Übrige offene Regelzuordnungen.** Den aktuellen Bestand liefert `python -m labkit.tools.check_inventory`; keine historischen Zählungen aus den Verlaufsnotizen als Arbeitsliste verwenden. Offen heißt, dass die Grundlage ungeklärt ist, nicht dass die Prüfung abgeschaltet wäre. Nur konkrete Streitfälle bearbeiten; eine vorhandene Prüfung rechtfertigt keine neue Laborregel. [Einzelentscheidungen](docs/notes/2026-11-11-open-assignments.md), [Nachprüfung](docs/notes/2026-11-11-rule-assignment-review.md).
4. **Offene Format- und Standardfragen.** Darf ein Vergleichsurteil aus gespeicherten Werten berechnet werden oder muss es gespeichert sein? Welche Pflicht trägt einen leeren Code-Bereich eines Versprechens, `kind` oder `[kept]` in der Registrierungssperre? Soll LAB-018 zusätzlich die Quelltextkonvention aus CODE-016 nennen? Der fehlende Schema-Verweis bei den Notizarten bleibt ein Quellenproblem; keine Metadatenpflicht nebenbei ergänzen. Nur am jeweiligen geltenden Text entscheiden. [Verlauf der Zuordnungsprüfung](docs/notes/2026-11-11-rule-assignment-review.md).

## Abgeschlossen — geltender Stand und Grenzen

### Aufgaben 1–6

Version `v0.112.0` ist veröffentlicht. Die Quellenprüfung anhand des Laufdatensatzes, die Unterscheidung von Umsetzungsfehlern und Deutungsfragen, der Antwortblock im Bericht, das Zustandsmodell und die Weitergabe von Fehlerursachen sind gebaut. Die ausführlichen Bau- und Messberichte stehen im [Verlauf](TODO-history-2026-11-12.md#reihenfolge). Verbleibende Versuche mit echten Agenten gehören in die ausdrücklich beauftragte Nutzungsrunde; Rollout bleibt getrennt.

### 6b. Die Einzelprüfung der Blocker umsetzen — abgeschlossen 2026-11-12, mit drei Grenzen

Gebaut sind die Zweitprüfung freigebender Entscheidungen, die protokollgebundenen Befundketten und Übernahmen, die ausdrückliche Endpunktexklusivität, `data=runlog.NO_INPUTS` und Entscheidungen zu Berichts-Reviews. Die getrennte Übernahme zweier Protokolle und der gedruckte Entscheidungsweg sind in `tests/test_adopt_per_protocol.py` abgenommen. Die Verträge stehen in der [Architektur](docs/architecture.md), die Herleitung im [Review-Vertrag](docs/notes/2026-11-10-report-claim-decisions.md).

Bekannte Grenzen, keine neue Abnahme vor der Nutzungsrunde:

- Die Nachrechnung (`scripts/02_analyze.py --check`) bleibt bereichsweit gekoppelt; Befundketten sind getrennt, Übernahmen nicht uneingeschränkt unabhängig.
- Stop und Commit wurden in dieser Abnahme nicht eigens auf ihre bereichsweite Sperrwirkung geprüft; die Aussage stammt aus dem Code.
- Die neue Anweisung für Berichts-Review-Entscheidungen ist technisch geprüft, nicht an einem echten Modell erprobt. Kein Versuch ohne Ansage.

### 6c. Ein klares Testmodell und der Umbau der Checks — abgeschlossen 2026-11-12

Plan, Messungen und [Abstraktionsbilanz](docs/notes/2026-11-10-test-model.md#6-abstraction-balance-of-the-whole-restructuring-2026-11-12) halten den begrenzten Erfolg fest: einzelne Bedingungen sind leichter zu ändern und zu testen, das Gesamtsystem und das Lesen eines Gates sind nicht einfacher geworden. Die doppelte Protokollauswahl ist zusammengeführt. Keine Umstellung weiterer Gates nur für ein einheitliches Muster; weitere Abstraktion braucht einen konkreten Nutzenbeleg.

Die Testebenen ergänzen sich: Regeltests halten die Bedingung aus Daten, Stationstests Auswahl, Weitergabe und Wirkung im Gate, Szenarien das Zusammenspiel der Kommandos und die gedruckten Reparaturwege. Eine reine Prüfung ersetzt keinen Test ihres Aufrufers. Welche Inventar-Werkzeuge künftig benutzt werden und wie verständlich `SourceNow` für Aufrufer ist, sind Beobachtungen, keine Prüfaufträge.

### Berichtspflicht — enger Vertrag abgeschlossen

Dauerhaft bindet nur das Berichtsziel im Commit einer ersten Messung, gelesen über die Protokoll-Kennung. Der Pfad darf wechseln; Streichen, Umbenennung und Löschen umgehen eine bestehende Pflicht nicht. Später eingetragene Ziele dürfen entfallen; solange sie im Kopf stehen, gelten die Berichtsprüfungen. Übernommene Ergebnisse und Audit-Belege behalten ihre eigenen Anforderungen. Der Historienlauf über alle späteren Commits ist entfernt und wird nicht durch neue Sonderfälle wieder eingeführt.

Nicht lesbare Evidenz ist nie „keine Pflicht“: Dazu zählen fehlende erste Messungen, unlesbare Lauf-Records und ein nicht lesbarer Commit beziehungsweise Protokollstand der ersten Messung. Solange kein aktuelles Ziel und keine lesbare erste Messung die Pflicht positiv feststellen, lautet der Ausgang „nicht ausführbar“. Wiederherstellen aus Belegen, nichts aus dem Gedächtnis erfinden. report-check, Stop und Commit erreichen verwaiste Pflichten. Übergaben hängen an der Kennung und dem Textfingerabdruck; Umbenennen ist möglich, Löschen des übergebenen Protokolls nicht.

Der enge Vertrag ist seit `7d2f9730` gebaut und dort vollständig geprüft. Das ist ein datierter Nachweis, keine Aussage über einen späteren Arbeitsstand oder den aktuellen Push-Status. Eine Rücknahme der ursprünglichen Berichtszusage bleibt bei der Übergabe; für ein eigenes Kommando fehlt ein konkreter Anwendungsfall.

### Taxonomie und Meldungsbereinigung — erste Fassung abgeschlossen

Die Agentenschleife ist berichtigt (2026-11-12, eigener Auftrag nach der Doku-Prüfung): `labkit-next` nennt für ein gelöschtes Protokoll mit Berichtspflicht den Wiederherstellungsweg des Gates, im Arbeitsbaum und im Index. Guide, Ablaufdoku und gedruckter Berichtshinweis beschreiben den bereits geltenden engen Vertrag. [Fehler und Abnahme](docs/notes/2026-11-12-next-agent-loop.md). Kein neuer methodischer Vertrag und kein Rollout in fremde Repos.

Die [Taxonomie-Note](docs/notes/2026-11-12-check-taxonomy.md) ist die Heimat der Definitionen, Zuordnungen und ihrer Herkunft. Bündel, nicht passende Werte und Unsicherheiten bleiben sichtbar. Zeilenabdeckung ist kein Anteil korrekt arbeitender Prüfungen. Pflege nur an konkreten Fällen; keine weitere allgemeine Leser- oder Zuordnungsrunde.

Überzogene Meldungen und die Weitergabe der Fehler im Versprechensblock sind bereinigt. Der Reparaturweg eines übernommenen Laufs ohne Intent-Schlüssel ist mit echten Kommandos und eingesetztem Audit-Record getestet; kein echtes Audit-Modell wurde dabei ausgeführt. `FieldReport.missing_must` bei späterer Arbeit an der Stelle passend umbenennen, kein eigener Taxonomie-Schritt.

## Notiert, nicht geplant

Diese Punkte sind keine Voraussetzungen für die Nutzungsrunde. Vor einer Änderung den aktuellen Fall nachstellen; historische Zeilennummern und Zwischenstände begründen keinen Auftrag.

### Codeklarheit, Zuständigkeiten und Wartbarkeit

- **Gemeinsame Audit-Abdeckung zurückgestellt.** Der [Kontrollfluss-Review](docs/notes/2026-11-12-control-flow-review.md#decided-by-the-author-on-2026-11-12) beschreibt mehrfaches Lesen und neu gebaute Zustände für Reparaturvorschläge. Erst bei gemessenen Kosten, widersprüchlichen Beobachtungen oder einem konkreten Wartungsproblem wieder aufgreifen; kein weiterer Umbau vor der Nutzungsrunde. Die Architektur verweist auf das Inventar, die dokumentierte Stationsabhängigkeit wird von `tests/test_report_check_stations.py` gehalten.
- **Audit des Check-Modells 2026-11-12:** Das einfache Modell (reine Prüffunktion, das Gate ruft sie auf) trifft auf einen Kern zu, 11 der 58 `check_*`-Funktionen; der Rest hat andere Formen. Entschieden und erledigt am selben Tag: eine bestätigte Doppelmeldung, ein Regelzitat, drei Tests, die Doku ([Stand](docs/audit-2026-11-12.md#decided-and-done-2026-11-12)). Zurückgestellt bleiben die Umbenennung der Stationen und Regelzitate aus den Daten. Kein Umbau vor der Nutzungsrunde.
- **Formate und Gates auf Doppelarbeit prüfen:** ohne Termin zurückgestellt. Ausgangspunkt ist der [One-explainer-Plan](docs/notes/2026-11-04-one-explainer-plan.md); keine pauschale Kürzung nach Funktionsgröße.
- **Ein gemeinsamer Schreiber für den Protokollkopf:** nach der Nutzungsrunde, mit derselben Prüffunktion wie die Gates. Die Bestandsaufnahme zu `--change-kind`, doppelten Feldern und `--force` steht im [Verlauf](TODO-history-2026-11-12.md#umfang-und-zuständigkeiten-vereinfachen); vor dem Bau aktuell prüfen.
- **Konkrete Fortsetzungsschritte als Daten und gemeinsamer Ergebnistyp:** eigene Formatverträge, kein unmittelbarer Bauauftrag. Den älteren Auslöser „wartet auf Phase 4“ nicht als offenen Zustand des inzwischen gebauten Zustandsmodells lesen. Ein gemeinsamer Ergebnistyp wird erst bei einem Widerspruch oder messbaren Kosten erneut bewertet.
- **Berichts-Review bleibt ein Ganzes.** Erst bei gemessenem Aufwand veralteter Reviews neu bewerten, dann nach Aufgabe teilen. [Entscheidung](docs/notes/2026-11-06-report-review-stays-whole.md).
- **Ältere Wartbarkeits- und Audit-Reste:** nur beim Anfassen der betreffenden Stelle oder nach aktueller Nachstellung. Dazu gehören die Schritte 7 und 8 des [Wartbarkeitsplans](docs/notes/2026-11-03-maintainability-repair-plan.md), die kosmetischen und Dokumentationsreste der Audits vom 2026-11-07 sowie Masken, Grad-Literale, manuelle Protokollfilter und Re-Exporte. Die einzelnen Befunde bleiben im [Verlauf](TODO-history-2026-11-12.md#audit-2026-11-07--struktur-drift-doppelte-heimaten).

### Laufdatensätze, öffentliche Schnittstelle und Korrektheit

- Antworten von Wiederholungsläufen in deren Laufordner ablegen: beschlossen für Schritt 6 des [stagekit-Plans](docs/notes/2026-11-03-stagekit-plan.md), erst zusammen damit bauen.
- Veraltete öffentliche Namen erst nach ihrer Übergangsversion entfernen. Den älteren Kandidaten `_find_models_toml` vor einer Änderung gegen den aktuellen Bestand prüfen; im Verlauf stehen widersprüchliche Statusangaben.
- `source-untracked/` und `code/` zusammenführen: Kandidat für einen eigenen Formatbruch, kein Bauauftrag. Weitere Cache-Felder nur bei konkretem Bedarf veröffentlichen; ein künftig gesendeter Seed muss in den Cache-Schlüssel.
- Helfer aus anderen Repos werden aufgezeichnet, aber nicht mit ihrem früheren Stand verglichen. Code-Scan-Kosten erst bei gemessenem Nutzungsproblem angehen.
- Laufüberwachung bei wiederverwendeten PIDs, fehlendem `ps` und `python -m`: erst konkret nachstellen; eine Kernel-Sperre braucht einen eigenen Vertrag. [Grenzen](docs/notes/2026-11-04-liveness-and-wait.md).
- Mehrere Laufstarts in einer Sekunde und Zeitzonen: erst bei einem echten Fall oder passenden Formatbruch einen Vertrag entwerfen; produktive Läufe nicht automatisch verzögern oder umsortieren. [Verlauf](TODO-history-2026-11-06.md#phase-2-reste-2026-10-27).
- Verbleibende Git-Lesefehler, unlesbare Records sowie Parser-, Pfad- und Bedienfälle vor einer Reparatur am aktuellen Stand nachstellen. [Ältere Befunde](TODO-history-2026-11-06.md#offene-verträge-und-korrektheitslücken).
- Veränderungen vor dem ersten Commit sind nicht manipulationssicher belegt. Zusätzliche Zeugen wären eine eigene Entscheidung, kein bestehender Auftrag.
- Versuchstyp für feste Vorhersagen ohne Leistungskriterium: Definition und Gerüstpflichten gemeinsam klären; kein neuer Lauf mit dem historischen Grenzfall. Modellannotierte Daten: Ablauf erst am ersten echten Annotierungslauf entwickeln, kein eigenes Compute-Skelett beschlossen.
- Einmaliger Fehler beim Warten auf den Laufstart (`tests/test_runlog_wait.py`): möglicher Wettlauf beim Schreiben des Test-Records, nicht geklärt. Nur bei erneutem Auftreten nachstellen und die volle Ausgabe sichern. [Bisherige Beobachtung](TODO-history-2026-11-12.md#notiert-nicht-geplant).

### Vorschläge, die weitere Belege brauchen

- Neue statische Hinweise oder Audit-Pflichten erst mit einem konkreten übersehenen Fehler und korrektem Gegenfall begründen. Statische Hinweise warnen, sie beweisen keine Semantik.
- Vorlagen, Feldnamen und Ablauf erst nach einer Schreib- und Nutzungsprobe mit einer anderen Person weiter vereinfachen. Weitere öffentliche Typen und ein Doktrin-Namensraum brauchen einen konkreten Bedarf.
- Früher veröffentlichte Versuchsbelege nachträglich entfernen: Entscheidung des Autors offen, keine Historienumschreibung in diesem Auftrag. Neue echte Antworten und aufgabenbezogene Logs bleiben intern in `/Users/max/projects/labkit-evidence`.

## Bei der nächsten Nutzung beobachten

1. **Lieferfähigkeit:** vollständige Zahl und fachliches Verdikt, sinnvolle Reparatur verweigerter Übernahmen, Unterscheidung vorläufiger Werte von Ergebnisbehauptungen. Die Quellenprüfung, der Antwortblock und die neue Nachfolger-Anweisung brauchen eine Erprobung mit echten Agenten; kein Versuch ohne Auftrag.
2. **Entscheidungen und Zweitprüfung:** Häufigkeit und Begründung von `limitation`, `stands`, `not assessable` und `undetermined`; wie oft der zweite Prüfer ablehnt und was er kostet. Runde 23 hatte 36 `limitation`-Entscheidungen, zuvor 19 beziehungsweise 20. Beobachten, ob Prüfkosten sachliche Fehler bestehen lassen oder ein Auditor mit ungeklärten Befunden ausweicht.
3. **Aufwand:** Fehlalarme, Fehlbedienung, Audit-Runden, Wartezeit, Kosten und Lieferfähigkeit aus vollständigen Transkripten erfassen. Wiederholte Stops und teilweise gestagte Änderungen beobachten; Deduplizierung erst bei belegtem Problem.
4. **Prüfungen, die anschlagen:** aus vollständigen Gate-Ausgaben je Prüfung echte Fehler, Fehlalarme und nie ausgelöste Prüfungen zählen. Bestand aus `python -m labkit.tools.check_inventory` (`just inventory`), Audit-Befunde aus `check_inventory --records <experiments>`. Pro Regel nur zugeordnete Ursachen zählen; offene Grundlagen und `new class` gesondert führen. Keine neue Regel und kein Register allein aus einer Zählung ableiten. [Grundsatz](docs/notes/2026-11-09-checks-have-no-switches.md).
5. **Verdächtige Zeittests:** bei erneutem Fehler des Stop-Budget-Tests vollständige Ausgabe sichern; Lastverdacht ist unbelegt, Zeitgrenze nicht nebenbei erhöhen. [Befund](TODO-history-2026-11-06.md#verdacht-zeittest-der-stop-hülle-unter-last-2026-11-03).
6. **Ältere Bedienbeobachtungen:** Platzhalter, kopierte Conclusions, Prompt-Wortlaut und Bedienhinweise nur bei erneutem Auftreten aufgreifen. [Belege](TODO-history-2026-11-06.md#bei-der-nächsten-nutzung-beobachten).

## Rollout und Aufgaben außerhalb dieses Repos

Externe Repos behalten ihren Pin bis zu einem eigenen Auftrag. Historische Läufe bleiben mit ihrem damaligen Commit und Pin reproduzierbar. Die folgenden Angaben sind vor einer Änderung im jeweiligen Repo neu zu prüfen.

| Ort                                           | Offene Arbeit oder Grenze                                                                                                                                                                                                   |
|-----------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| labkit-paper                                  | Nutzungsrunde, Branch-Zusammenführung und Pin-Anhebungen bleiben beim Autor; Vorbereitung oben, aktuelle Bestandsprüfung erforderlich.                                                                                      |
| stagekit und Labor-Pipelines                  | Übrige Schritte des [stagekit-Plans](docs/notes/2026-11-03-stagekit-plan.md) gehören in die dort genannten Repos.                                                                                                           |
| Codex-Hooks und Pilot-Images                  | Hooks sind in labkit gebaut. Das effektive `exec_command.workdir` fehlt im Codex-Hook-Ereignis; gleichnamige relative Skripte bleiben eine Grenze. Installation und Pins separat behandeln. [Vertrag](docs/codex-hooks.md). |
| Labor- und Studi-Repos, Hausvorlagen, Starter | Pins und Imports bewusst anheben, Hooks installieren und gestempeltes Beispiel prüfen. Neue Bindungen können Audits verlangen; alte Stempel nicht von Hand ändern. [Einstieg](docs/student-repos.md).                       |
| Konkrete externe Reparaturen                  | `fallacy-dataset-generation`: Bilanz mit Eingabefingerabdruck; `counterfactual-worlds`: alte `endpoint`-Form; uniagent: TOML-Quoting. Erst aktuellen Stand lesen.                                                           |
| Ruhende Repos                                 | fallacy-datasets, visual-argument-spec, fallacy-detection, finance-discourse und paper-organization behalten den Pin. `thesis-dagidir` braucht bei neuer Arbeit einen eigenen Import- und Pin-Umzug.                        |
| Veröffentlichung und Hausmaterial             | PyPI bleibt offen; unbenutzte Vorlagen erst nach aktuellem Vergleich zur Löschung vorlegen. Hausregeln und Hausvorlagen sind eigene Aufträge. Push, Release und Rollout bleiben beim Autor.                                 |
