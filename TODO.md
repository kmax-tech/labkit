# TODO — labkit

Hier steht, was als Nächstes ansteht, welche Entscheidungen gelten und welche Vorschläge auf einen Auslöser warten. Stand: 2026-11-06. Die Reihenfolge unten ist maßgeblich.

Die bisherige Fassung mit den ausführlichen Herleitungen liegt im [historischen Anhang](TODO-history-2026-11-06.md). Dort stehen auch ältere offene Hinweise; sie sind erhalten, aber vor einer Umsetzung am aktuellen Stand nachzustellen. Implementierte Verträge stehen in [Architektur](docs/architecture.md), [README](README.md) und [Laborstandard](labkit/docs/standard.md), Formatbrüche im [CHANGELOG](CHANGELOG.md).

## Reihenfolge

### 1. Version 0.112.0 veröffentlichen — beim Autor

Die Test-Labore installieren labkit von GitHub und brauchen den veröffentlichten Stand. Vorher den Abschnitt „Unreleased“ im CHANGELOG mit den Änderungen abgleichen, dann `just release 0.112.0` ausführen und pushen.

Die Version bindet den vollständigen Review-Brief samt Standardauszug an die Berichtsprüfung: Ändert sich der Brief, wird die bisherige Prüfung ungültig. Durch den Formatbruch werden alle älteren Berichtsprüfungen einmal veraltet.

**Fertig, wenn:** Version und Tag auf GitHub verfügbar sind und die Test-Labore diesen Stand installieren können. Release und Push bleiben beim Autor.

### 2. Daten anhand des Laufdatensatzes prüfen — nach 0.112.0

Problem: Für Daten außerhalb von Git gibt es mehrere Nachweiswege. In Nutzungsrunde 23 fanden die Agenten keinen passenden Weg für die ignorierte Modellquelle und übergaben ohne Ergebnis.

**Beschlossen am 2026-11-05 und ergänzt am 2026-11-06:** Der Laufdatensatz (Record) ist der einzige Integritätsnachweis. Er hält die Prüfsummen der gelesenen Daten. `MANIFEST.sha256` und die Prüfsumme im Protokollfeld `Data / scope` entfallen; Herkunft, Zugangsweg und Version bleiben dort als Prosa.

| Zustand der Quelle | Künftige Prüfung |
|---|---|
| In Git getrackt oder durch eine Git-Regel ignoriert | Besteht, wenn die Bytes zur Prüfsumme im Laufdatensatz passen. |
| Ungetrackt und nicht ignoriert | Hält auch bei passender Prüfsumme: bewusst committen oder ignorieren. |
| Fehlend oder gegenüber dem Lauf verändert | Hält mit einem passenden Wiederherstellungs- oder Neumessungsweg. |

Keine neue Pin-Datei und kein neuer Schalter. Die Änderung bricht das bisherige Format; 0.112.0 ist die letzte Version mit den alten Nachweiswegen.

**Vor dem Bau prüfen:** Was passiert bei einem Commit, der den Bericht, aber nicht `runs/<id>/` enthält? Entweder verweigert schon der Commit diesen Stand, oder `finalize` und `report-check` müssen im frischen Klon ausdrücklich den fehlenden Datensatz melden. Ein stilles Bestehen wäre im selben Schritt zu beheben.

**Fertig, wenn:** Die Fälle aus dem [Entwurf zur Pin-Route](docs/notes/2026-11-06-pin-route.md) samt korrekten Gegenfällen geprüft sind und die Reparaturprobe mit ignorierter Modellquelle bis zu Übernahme und Commit durchläuft. Prognose: etwa 130 Paketzeilen weniger; bei weniger als 100 eingesparten Zeilen oder einem neuen Modul den Entwurf erneut bewerten.

### 3. Umsetzungsfehler von Deutungsfragen unterscheiden

Problem: `labkit-next` bietet heute bei einem Befund im Protokoll selbst `--decide … limitation` an, ohne dessen fachliche Ursache zu kennen. So kann ein fehlender registrierter Check denselben Rat erhalten wie eine Beschreibungsfrage.

**Änderung:** Der Auditor benennt, ob der Befund eine Umsetzungsabweichung oder eine Deutung betrifft. `--decide limitation` wird für eine Umsetzungsabweichung verweigert. Die eigene Entscheidungswahl in `next_step._finding_on_the_field` entfällt.

**Fertig, wenn:** Die eigene Sonde den Reparaturweg und den korrekten Gegenfall prüft und `tests/test_architecture.py` absichert: `next_step` wählt keine Entscheidungsart selbst. Details: [Zuständigkeitsgrenze im One-explainer-Plan](docs/notes/2026-11-04-one-explainer-plan.md#next-architectural-boundary-to-repair). Dort heißt diese Aufgabe „Schritt (4) Befundart“.

### 4. Einen ausdrücklichen Antwortblock im Bericht entwerfen

Problem: Sechs der sieben Fehlversuche in Nutzungsrunde 23 lieferten einen Bericht ohne Zahl oder Verdikt.

**Entwurf liegt vor (2026-11-06):** [Antwortblock](docs/notes/2026-11-06-answer-block.md). Kein neuer Block: der Ergebnisblock zeigt schon Zahl und Verdikt je Zusage; er bekommt zwei erzeugte Zeilen darüber, die Frage und die `Conclusion` des Protokolls wörtlich, und erbt Schreiber, exakte Prüfung, Pflicht und Veralten. Eine leere `Conclusion` verweigern Schreiber (`--into`) und Prüfung (`block_gaps`) aus derselben Funktion, auch bei einem von Hand geschriebenen Block. Die Antwortzeile ist übertragen, nicht bestätigt: Der Review-Brief sagt ausdrücklich, dass sie eine Aussage des Autors ist, die gegen das Verdikt zu prüfen ist (Prüffall: korrekter Block, Antwort „cannot be assessed“ bei „not met“). Reichweite: sichert die sichtbare Antwort bei übernommenem Ergebnis; die drei sts512-Übergaben und die fehlenden Spalten von Task 34 r1 erreicht sie nicht. Breaking: jeder bisherige Ergebnisblock veraltet einmal. Offen beim Autor: (1) welche Frage — die registrierte `Question / hypothesis` (empfohlen; nach der ersten Messung unveränderlich) oder die Klartext-Frage `Question †` aus der Summary (nach dem Lauf geschrieben); die frühere Formulierung hier verwechselte beide; (2) zwei Zeilen im Ergebnisblock (empfohlen) oder ein eigener Block. Diese Aufgabe ist im bisherigen Plan „Schritt (5) Antwortblock“.

### 5. Die nächste Nutzungsrunde durchführen — nach den Aufgaben 2–4

Die Runde prüft, ob Agenten fachlich korrekte Arbeit verlässlicher und mit weniger Aufwand abschließen. Sie bewertet die Aufgaben 2–4 als ein Paket, ohne Vorhersage je Änderung (entschieden 2026-11-06: Maßstab ist ein klares, wartbares Repo, nicht welche Einzeländerung wie viele Versuche umdreht). `limitation`-Entscheidungen weiter zählen: In Runde 23 waren es 36, zuvor 19 beziehungsweise 20. Dass ein Teil davon dem fertig angebotenen Entscheidungsbefehl folgte, ist bisher eine Vermutung.

Versuchsdesign, Bewertung und Start bleiben ein eigener Forschungsauftrag. Die bestehende Zweitprüfung und die Auswertungsfolge 17 → 18 bleiben erhalten. Herleitung und bisherige Ergebnisse: [One-explainer-Plan](docs/notes/2026-11-04-one-explainer-plan.md) und [Vereinfachungsplan](docs/notes/2026-11-02-workflow-simplification.md).

## Notiert, nicht geplant

Diese Punkte haben keinen Platz vor den Aufgaben 1–5. Eine Bedingung nennt, wann sie wieder geprüft werden; sie ist kein Bauauftrag. Ältere Detailbefunde sind im verlinkten Anhang erhalten und dadurch weder bestätigt noch geschlossen.

### Umfang und Zuständigkeiten vereinfachen

| Aufgabe | Auslöser und nächster Schritt |
|---|---|
| Formate und Gates auf Doppelarbeit prüfen | Ohne Termin zurückgestellt: pro Format und Gate das gesicherte Glied der Kette Absicht → Zusage → Code → Lauf → Zahl, seine Leser und „bleibt / verschmilzt mit X / entfällt“ festhalten. Die Tabelle im [One-explainer-Plan](docs/notes/2026-11-04-one-explainer-plan.md) ist der Ausgangspunkt; keine pauschale Kürzung nach Funktionsgröße. |
| Den konkreten Fortsetzungsschritt eines unentschiedenen Blockers als Daten führen | „Fix 5“ wartet auf Phase 4, das Zustandsmodell im selben Plan. Heute kommen die Blocker-Texte aus vier Quellen; der Umbau braucht einen eigenen Formatvertrag. |
| Einen gemeinsamen Ergebnistyp für die Prüfketten einführen | Zurückgestellt: die doppelte Kette kostete im Zähl-Labor 0,06 s. Erst bei einem Widerspruch trotz gemeinsamer Leser oder bei messbaren Kosten neu bewerten. |
| Die Berichtsprüfung in Teile zerlegen | Entschieden 2026-11-06: bleibt ein Ganzes — der Reviewer braucht den ganzen Bericht, eine veraltete Prüfung kostet wenig (157 / 186 / 215 s je Runde), die Prüfsumme nennt den geänderten Teil schon. Neu bewerten, wenn eine Runde veraltete Prüfungen als sichtbaren Zeitanteil zeigt oder `RUNS` eigene Befunde liefert (bisher 0 in 30 Bundles); dann nach Aufgabe teilen, nicht nach Abschnitt. [Note](docs/notes/2026-11-06-report-review-stays-whole.md). |
| Weitere Wartbarkeitsreparaturen | Im [Wartbarkeitsplan](docs/notes/2026-11-03-maintainability-repair-plan.md) sind die Schritte 1–6 und 9 gebaut. Schritte 7 und 8 erst nachstellen. |
| Große Module, komplexe Funktionen und bekannte Schichtverletzungen bereinigen | Wenn die betreffende Stelle ohnehin bearbeitet wird. Nach fachlicher Zuständigkeit teilen; die Ausnahmeliste in `tests/test_architecture.py` nicht beiläufig erweitern. Ältere Kandidaten: [Architektur und Lesbarkeit](TODO-history-2026-11-06.md#architektur-und-lesbarkeit--notiert-nicht-geplant). |

### Laufdatensätze, LLM-Antworten und öffentliche Schnittstelle

Die labkit-Schritte für öffentliche Schnittstelle, Antwort-Cache und Herkunft über mehrere Repos sind integriert. Aktueller Vertrag und Fortschritt: [Architektur](docs/architecture.md), [LLM- und Pipeline-Entscheidungen](docs/notes/2026-11-02-llm-layer-and-pipeline-runs.md) und [stagekit-Plan](docs/notes/2026-11-03-stagekit-plan.md).

1. **Antworten eines Wiederholungslaufs in dessen Laufordner ablegen.** Beschlossen für Schritt 6 des stagekit-Plans; erst zusammen damit bauen, damit auch dieser Lauf ohne neue Modellaufrufe wiedergegeben werden kann.
2. **Den alten Namen `_find_models_toml` entfernen.** Erst in der Release nach der Übergangsversion, in der `find_models_toml` eingeführt wurde und der alte Name warnt; als Breaking-Änderung ankündigen.
3. **Die zwei Ablagen für unversionierten Code zusammenführen.** `source-untracked/` und `code/` sind Kandidaten für einen eigenen Formatbruch; noch kein Bauauftrag.
4. **Weitere Cache-Felder nur bei konkretem Bedarf öffentlich machen.** `llm_cache.fresh_usage` und `CACHE_VERSION` bleiben intern. Falls `complete` künftig einen Seed sendet, muss dieser in den Cache-Schlüssel.
5. **Grenzen der Herkunftsprüfung beachten.** Helfer aus anderen Repos werden aufgezeichnet, aber von `run_record_check` nicht verglichen. Kosten des Code-Scans nur bei messbarem Nutzungsproblem angehen.

### Offene Korrektheitsfragen erst nachstellen

| Thema | Bedingung und verbleibende Frage |
|---|---|
| Laufüberwachung | PID und Skript reichen bei wiederverwendeter PID, fehlendem `ps` oder `python -m` nicht zuverlässig. Eine Kernel-Sperre im Laufordner braucht einen eigenen Formatvertrag. Weitere Grenzen: [Prozesszustand und Warten](docs/notes/2026-11-04-liveness-and-wait.md). |
| Mehrere Laufstarts in einer Sekunde und Zeitzonen | Erst bei einem echten Laborfall oder passendem Formatbruch einen Vertrag für eindeutige Zeitordnung entwerfen. Produktive Läufe nicht automatisch verzögern oder umsortieren. Frühere Befunde: [Phase-2-Reste](TODO-history-2026-11-06.md#phase-2-reste-2026-10-27) und [Zeitordnung](TODO-history-2026-11-06.md#kern-doktrin-und-formatbrüche). |
| Git-Lesefehler und unlesbare Records | Verbleibende Leser nach Risiko einzeln prüfen. Fehler dürfen nicht als „Datei fehlt“ oder „keine Freigabe“ verschwinden. Bereits behobene und ungeprüfte Leser stehen [im damaligen Befund](TODO-history-2026-11-06.md#erledigt-fehlender-finalize-halt-im-korrektur-end-to-end-test-2026-11-0304). |
| Schutz vor Veränderungen vor dem ersten Commit | Ein Vergleich mit gespeicherten Antworten oder ein zusätzlicher Laufzeuge wäre eine eigene Entscheidung. Kein Auftrag für manipulationssichere Speicherung; die Grenzen der Git-Belege bleiben bestehen. |
| Verbliebene Parser-, Pfad- und Bedienfälle | Die älteren [Vertragsbefunde](TODO-history-2026-11-06.md#offene-verträge-und-korrektheitslücken) und [Phase-2-Reste](TODO-history-2026-11-06.md#phase-2-reste-2026-10-27) enthalten die einzelnen Fälle, darunter XML-Prompts, Symlinks und wenig hilfreiche Auswege. Vor einer Reparatur prüfen, ob der Fall im aktuellen Stand noch besteht. |
| Versuchstyp für feste Vorhersagen ohne Leistungskriterium | Definition und Gerüstpflichten gemeinsam klären. Aufgabe 60 bleibt historischer Grenzfall; kein neuer Vergleichslauf damit. [Bisherige Einordnung](TODO-history-2026-11-06.md#typgrenze-bei-fester-vorhersagebewertung-2026-11-01). |
| Modellannotierte Daten | Den Ablauf am ersten echten Annotierungslauf entwickeln. Für `compute` mit Modellannotation ist kein eigenes Skelett beschlossen; modellannotierte Trainings- und Testdaten bleiben eine eigene offene Grenze. |

### Vorschläge, die weitere Belege brauchen

1. **Neue statische Hinweise und Audit-Pflichten:** Erst einen konkreten übersehenen Fehler und einen korrekten Gegenfall belegen; statische Indizien warnen und beweisen keine Semantik. Die [bisherigen Kandidaten](TODO-history-2026-11-06.md#neue-audit-hinweise-erst-nach-benchmark-beleg) bleiben zurückgestellt.
2. **Vorlagen, Feldnamen und Ablauf weiter vereinfachen:** Erst eine Schreib- und Nutzungsprobe mit einer anderen Person. Die bisherigen Entscheidungen des Autors ersetzen diese Probe nicht. [Messungen und Vorschläge](TODO-history-2026-11-06.md#evaluation-und-vorschläge-mit-auslöser).
3. **Öffentliche API oder Formate aufräumen:** Öffentliche Namen erst nach einer Übergangsversion entfernen. Weitere Typen und ein eigener Doktrin-Namensraum brauchen eine konkrete Invariante bzw. ein Labor, das die Trennung benötigt. [Verbliebene Kandidaten](TODO-history-2026-11-06.md#architektur-und-lesbarkeit--notiert-nicht-geplant).
4. **Früher veröffentlichte Versuchsbelege nachträglich entfernen:** Entscheidung des Autors offen; eine Umschreibung gepushter Historie gehört nicht zu diesem Auftrag. Neue echte Antworten und aufgabenbezogene Logauszüge bleiben seit 2026-10-28 intern in `/Users/max/projects/labkit-evidence`; öffentlich bleiben Kriterien, synthetische Tests und knappe Beschreibungen.

## Bei der nächsten Nutzung beobachten

1. **Vollständige Antworten:** Liefert der Agent Zahl und fachliches Verdikt, bearbeitet er eine verweigerte Übernahme sinnvoll, und unterscheidet das Review vorläufige Werte von Ergebnisbehauptungen?
2. **Entscheidungen zu Befunden:** Häufigkeit und Begründung von `limitation`, `stands` und `not assessable` erfassen. Beobachten, ob eine teure Neuprüfung dazu führt, dass ein sachlicher Fehler bestehen bleibt.
3. **Aufwand:** Fehlalarme, Fehlbedienung, Audit-Runden, Wartezeiten, Zeit und Kosten zusammen mit der Lieferfähigkeit erfassen. Ungeklärte Wartezeiten anhand vollständiger Transkripte untersuchen.
4. **Hooks und teilweise gestagte Änderungen:** Prüfen, ob derselbe Befund unnötig wiederholt wird oder alte Änderungen den Stop immer wieder in denselben Bereich führen. Deduplizierung erst bei belegtem Nutzungsproblem.
5. **Verdächtige Zeittests:** Bei erneutem Fehlschlag des Stop-Budget-Tests die vollständige Ausgabe sichern. Der Lastverdacht ist bisher unbelegt; keine Zeitgrenze nebenbei erhöhen. [Befund](TODO-history-2026-11-06.md#verdacht-zeittest-der-stop-hülle-unter-last-2026-11-03).
6. **Weitere ältere Beobachtungen:** Eigene Platzhalter, kopierte Conclusions, Prompt-Wortlaut und Bedienhinweise nur bei erneutem Auftreten aufgreifen. Die [bisherigen Beobachtungen](TODO-history-2026-11-06.md#bei-der-nächsten-nutzung-beobachten) bleiben als Belege erhalten.

## Rollout und Aufgaben außerhalb dieses Repos

Externe Repos behalten ihren Pin bis zu einem eigenen Auftrag. Historische Protokolle und Läufe bleiben mit ihrem damaligen Commit und Pin reproduzierbar. Angaben aus älteren Runden sind vor einer Änderung im jeweiligen Repo neu zu prüfen.

| Ort | Offene Arbeit oder Grenze |
|---|---|
| labkit-paper | Nutzungsrunden und deren Merges bleiben beim Autor. Ältere Hinweise zu Bereichsnummern, erster Messung, t18-Zeilenversatz und Sandbox-Archivierung stehen im [Anhang](TODO-history-2026-11-06.md#rollout-und-aufgaben-außerhalb-dieses-repos) sowie bei den damaligen Runden. |
| stagekit und Labor-Pipelines | Die übrigen Schritte des [stagekit-Plans](docs/notes/2026-11-03-stagekit-plan.md) laufen in den dort genannten Repos. Die labkit-Restarbeit ist oben erfasst. |
| Codex-Hooks und Pilot-Images | Die Hooks sind in labkit umgesetzt. Codex liefert das effektive `exec_command.workdir` im Hook-Ereignis nicht mit; gleichnamige relative Skripte bleiben dadurch eine bekannte Grenze. Externe Installation und Pins separat behandeln. [Vertrag](docs/codex-hooks.md). |
| Labor- und Studi-Repos, Hausvorlagen, Starter | Pins und Imports bewusst anheben, Hooks installieren und das gestempelte Beispiel prüfen. Neue Bindungen können neue Audits verlangen; alte Stempel nicht von Hand umschreiben. [Einstieg für Studi-Repos](docs/student-repos.md). |
| Konkrete externe Reparaturen | `fallacy-dataset-generation`: Bilanz auf `Store.ledger` mit Eingabefingerabdruck; `counterfactual-worlds`: alte `endpoint`-Form; uniagent: TOML-Quoting für `[models.llama3.1-8b]`. Vorher den aktuellen Stand prüfen. |
| Ruhende Repos | fallacy-datasets, visual-argument-spec, fallacy-detection, finance-discourse und paper-organization behalten ihren Pin. `thesis-dagidir` braucht bei neuer Arbeit einen gesonderten Import- und Pin-Umbau. |
| Veröffentlichung und Bereinigung | PyPI bleibt eine offene Entscheidung. Unbenutzte Vorlagen nur nach aktuellem Vergleich zur Löschung vorlegen. Hausmaterial und Änderungen an Hausregeln sind eigene Aufträge. |
