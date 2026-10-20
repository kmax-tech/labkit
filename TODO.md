# TODO — labkit

Diese Datei hält offene Arbeit, geltende Entscheidungen und ihre Auslöser.
Sie ist kein Änderungsprotokoll. Implementierte Verträge stehen in
[Architektur](docs/architecture.md), [README](README.md) und
[Laborstandard](labkit/docs/standard.md); Formatbrüche im
[CHANGELOG](CHANGELOG.md), Änderungen im Git-Verlauf. Datierte Audits und
Messungen sind Belege für ihren damaligen Stand, keine aktuellen Aufgabenlisten.

## Reihenfolge

Die beschlossene Folge **A5 → Audit-Snapshot → typisierte Run-Records →
Backend-Typen ist umgesetzt**. Auch Paketstruktur und Modulteilungen sind
umgesetzt. Ihre Übernahme in andere Repos ist ein eigener Auftrag.

**Zusätzlich umgesetzt:** `run_kind="preparation" | "probe" | "measurement"`
ersetzt `long`; bei `seconds` ist keine gesonderte Probe zulässig. Ergebnisfreigabe bleibt
eine eigene Prüfung.

**Für die übrigen Punkte ist keine neue Umsetzungsreihenfolge beschlossen.**
Die offenen Vertragsfragen und Korrektheitslücken unten sind sichtbar, aber dadurch
nicht vorgezogen. Strukturierte Findings bleiben ausdrücklich geparkt,
bis eine Fehlklassifikation oder ein konkretes Wartungsproblem sie verlangt.

Für neue Prüfungen gilt: Die Evaluation steuert die Entwicklung. Erst ein
belegter Fehler und sein korrekter Zwilling, dann die kleinste passende
Prüfung. Static evidence warnt und beweist keine Semantik. Rollout,
Veröffentlichung und Änderungen der Hausregeln brauchen einen eigenen
Auftrag. Forschung und Benchmark-Fallliste liegen in
`~/work/projects/labkit-paper/`.

## Offene Verträge und Korrektheitslücken

### Audit-Bindung und Hook-Auswahl

- **Protokollprosa und Lauf-Inhalte:** Der Record bindet den Promise-Block
  und beim Analyse-Audit die Lauf-ID. Übrige Protokollprosa und gezeigte
  Ausgabezeilen des Laufs haben keinen eigenen gebundenen Digest. Eine
  Erweiterung verändert, wann ein Audit fällig wird, und braucht eine
  ausdrückliche Vertragsentscheidung. Für den bestehenden Snapshot gilt:
  Prompt und Stempel müssen dieselben gelesenen Bytes beschreiben;
  Änderungsfälle gehören in `tests/test_audit.py` (`OneSnapshot`).
- **Berichte außerhalb des Protokolls:** Nicht jede Run-ID in einer Notiz
  löst ein Gate aus. Automatisches Verfolgen bleibt zurückgestellt:
  alte Zitate würden unberührte Bereiche öffnen. Auslöser: zweiter echter
  Laborfall; zuerst auf Messnotizen begrenzen, altes unbetroffenes Zitat
  als Zwilling testen.

## Architektur und Lesbarkeit — notiert, nicht geplant

### Typisierte Grenzen vervollständigen

| Bereich | Noch offen | Bedingung / Vertrag |
|---|---|---|
| Run-Records | `runlog.active` liefert Dicts mit hineingemischter Config. Eigene Config-Felder werden nach der Lesegrenze weiterhin über Schlüssel gelesen. | Öffentliche Skript-API gesondert behandeln. Vollständige `RunConfig` nur mit klaren Invarianten für die eigenen Felder; Experiment-Config bleibt frei. |
| Backend-Aufrufe | `max_tokens` bleibt bei claude-cli wirkungslos; ein Default unterscheidet explizite Angabe nicht von Vorgabe. Server-Antworten sind noch nicht durchgängig strikt typisiert. | Aufrufvertrag festlegen, etwa optionales `max_tokens`, dann unbediente Optionen verweigern. Antwortparser als eigener Schritt mit fehlerhaften Antworten testen. |
| Findings | `GateFinding` existiert; die gemeinsame Prüfliste `code_check.code_findings` liefert Text. `grade_of` liest den Grad daraus; ungradierter Text zählt als Blocker. | Erst bei konkreter Fehlklassifikation oder Wartungsproblem Grad, Stufe, Fundstelle und Nachricht als Daten bis zur CLI reichen. Gemeinsame Prüfliste beibehalten. |

### Restarbeiten aus dem Code-Audit

Kandidaten aus [Code-Audit](docs/audit-2026-10-18.md); vor Umsetzung am
aktuellen Code prüfen, keine alten Zeilennummern als offenen Befund übernehmen:

- Verbliebene Sonderausgaben über `console.refuse` und den gemeinsamen
  Exit-Vertrag führen.
- Wiederholte Pfaddarstellung und Zeitstempel zusammenführen; Shell-Segmente
  für Hook und Transkript gemeinsam lesen; `LABKIT_COMMANDS` aus den
  registrierten Einstiegspunkten beziehen. Je Umzug eine One-Home-Prüfung.
- `Path | int` in der Laufauswahl von `intent_check` durch klares Ergebnis
  oder Ausnahme ersetzen.
- Namen prüfen: `area: Path`, Wurzelpfade, Digest-Begriffe,
  `trace`/`timeline`, `registry`/`ledger`. Keine pauschale Umbenennung.
- Verbleibende `noqa: C901` entlang fachlicher Abläufe abbauen, wenn dort
  gearbeitet wird; nicht allein nach Dateilänge teilen.

### Kern, Doktrin und Formatbrüche

Die aktuellen Kopplungen stehen in `tests/test_architecture.py`
(`KNOWN_CROSSINGS`). Bei Arbeiten an einer solchen Stelle die Kopplung
abbauen; die Liste nicht beiläufig erweitern. Eigener Doktrin-Namensraum
erst, wenn Kern-Evaluation oder zweites Labor den Kern ohne Doktrin braucht.

| Kandidat | Auslöser und Abnahme |
|---|---|
| Startzeit mit Subsekunden im Record | Gleichsekunden-Sperre trifft ein Labor oder passender Formatbruch steht an. Eindeutige zeitliche Wahl im Orakel `tests/test_answering_run_exhaustive.py`; kein Altformat-Leser. |
| `notes_check` und deutsche Notizkonventionen nach LOCAL; Herkunft von Paper-Zahlen nach LAB | Fremdes Labor braucht die Trennung oder passende Breaking-Release. Beide Richtungen mit Regeltext und Hook-Anpassung gemeinsam behandeln. |
| Englische Notizverzeichnisse | Angekündigter Bruch mit Regeltext, Scaffolder, Lesern, Hooks und externem Rollout. Kein Umbenennen nebenbei. |
| Instrument als Kopffeld `kind` (`apply`/`fit`/`count`) | Offene Forschungsentscheidung. Konkrete Instrumente müssen verschiedene Pflichten brauchen, die Vorlagenwahl nicht ausdrückt. Ein `RandomForest(…)`, das im Feld „Model / tool“ Modellpflichten auslöst, ist ein Indiz. Branch `claude/zealous-davinci-3hbhvk` ist Material, kein beschlossener Plan. |

## Evaluation und Vorschläge mit Auslöser

### Messungen

- **Aktuelle Vorlagen und Gates:** Vor Rollout bzw. nach entsprechenden
  Änderungen `count` und `judge` mit je drei kalten Läufen messen:
  richtige und gebundene Zahl, Median der Wandzeit, Fehlalarme,
  Quelltext-/Standard-Lesungen. Alte Reihen belegen nur ihren Stand.
  Die `minutes`-Reihe ist abgeschlossen; Wiederholung erst nach relevanter
  Änderung. Belege: [Count](docs/usability/2026-10-12-cloud-fable.md),
  [Judge](docs/usability/2026-10-14-judge-minutes.md).
- **Andere Person:** Schreibprobe und Usability-Runde vor weiteren
  Änderungen am Protokollstandard. Bisherige Vorlagenentscheidungen des
  Autors ersetzen diese Probe nicht.
- **Audit-Läufer und Modellwahl:** Paketaufruf gegen früheren Subagenten
  auf denselben Benchmark-Fällen prüfen, einschließlich positionalem Join
  und korrekten Zwillingen. Lokales Modell erst nach gemessener Fangquote
  und Fehlalarmrate als geeigneten Prüfer behandeln. Modellunabhängiger
  Aufruf des bisherigen code-check-Subagenten bleibt bei Bedarf offen.
- **Audit-Kosten:** Beobachten, ob ein Korrektheitsbefund nur wegen der
  Kosten eines Neu-Audits als `accepted` endet. Erst dann Regeländerung.
  Ungeklärte lange Wartezeiten nur anhand eines Transkripts untersuchen.

### Werkzeuge und Standard

| Vorschlag | Auslöser | Abnahme / Grenze |
|---|---|---|
| Workflow als `docs/workflow.md` | Arbeitsablauf unabhängig vom Haus-Skill zugänglich machen. | Englischer Ablauf von Absicht über Probe und Validierung bis Bericht; Haus-Skill verweist darauf. Einzelverträge verlinken. |
| `promote <area>` | Erste echte Beförderung, bei der vorhandene Kommandos nicht reichen. | Dünne Hülle um Analyse-Audit und Entscheidungen, synchron mit Zeitlimit. `report-check` prüft die Freigabe bereits. |
| Protokollstandard 0.20 | Schreibprobe und externe Usability-Probe. | Kandidaten gemeinsam entscheiden: `Result`/`Answer`, Frage in Summary, verpflichtender antwortender Lauf, Weichenwerte als Daten, kürzere Vorlage. |
| Bereichsstand als Faktenzeile | Andere Person zeigt, dass die Zeile gebraucht und gelesen wird. | Bestehende Fakten projizieren: Registrierung, Probe, Freeze, Lauf, Tests, Zitat. Keine zweite Statusquelle. |
| Zählvorlage aus Task-Feldern | Fable-/Sonnet-Probe benennt Stubs ebenfalls als Hindernis. | `SOURCE`, `COUNT_FIELD`, `METRIC_KEY` und Ordner je Item gezielt unterstützen; nicht allein auf schwächstes Modell zuschneiden. |
| Rückschrift am Laufende / weniger Kommandos | Gemessener Umweg trotz `protocol-fill --from-run`. | Bewusste Prüfung erzeugter Zeilen klären. `finalize` bleibt lesend; kein `finalize --write-back`. |
| Eigene Meldung für laufenden/abgebrochenen Audit | Realer Fall braucht mehr als bestehende Verweigerung ohne gültigen Record. | Keine zweite Heimat für „Audit ohne Ergebnis“. Frühere `.running`-/`unavailable`-Skizze ist kein offener Implementierungsplan. |
| `labkit-rules` | Modulpfad behindert Nutzung nachweisbar. | Kürzerer Einstieg, keine neue Regellogik. |

### Neue Audit-Hinweise erst nach Benchmark-Beleg

- **Stille Rückfälle:** Fehlende Gold-Werte werden mit `.get(key, 0)` zur
  Zahl; Zwilling scheitert explizit. Erst bei verfehltem Audit Narbenzeile,
  statische Hinweise erst nach weiterem echten Fall; immer Warnungen.
- **Befundbasis `evidence` / `inference` / `unknown`:** Erst wenn eine
  Entscheidung an bloßer Vermutung scheitert oder Auswertung die Trennung
  braucht. Neues Pflichtfeld ist Formatbruch; `unknown` braucht Leseprobe.
- **Grundschicht aus der Literatur:** Vorhandene Tabelle nicht automatisch
  in Prompt aufnehmen. Erst gleiche/bessere Fangquote ohne zusätzliche
  Fehlalarme belegen. Fehlende Klassen und Registrierungsfelder am
  Benchmark prüfen.
- **Konstante oder nur null Gold-Werte:** Static-evidence-Kandidat bis zum
  zweiten echten Fall geparkt. Kein Beweis für inhaltlich leeres Kriterium.
- **Audit je Versprechen:** Erst wenn Bereichsaudit spürbar teurer als Lauf
  wird oder Benchmark eine Lücke zeigt. Zusammenspiel weiter prüfen.
- **Allgemeine Regelbeispiele / `lib scar`:** Erst wenn fremdes Labor eigene
  Belege sammelt. Datierte Belege von geltenden Regeln getrennt halten.

## Rollout und Aufgaben außerhalb dieses Repos

Eigene Aufträge. Pins bewusst heben; eingefrorene Protokolle und Läufe
bleiben mit damaligem Commit und Pin reproduzierbar.

- **Release:** Vor Veröffentlichung Unreleased gegen CHANGELOG abgleichen.
  Release und Push bleiben beim Autor. Ohne veröffentlichten Tag
  installiert eine frisch gestempelte Usability-Probe nicht vom Pin.
- **Paketstruktur:** Mit neuem Pin Imports/Modulaufrufe in Labor-/Studi-Repos,
  Hausvorlagen und Thesis-Starter umstellen. Neue Scope-Bindungen können
  neue Audits erfordern; alte Stempel nicht von Hand umschreiben.
- **Konkrete externe Lücken:** `fallacy-dataset-generation`: Bilanz auf
  `Store.ledger` mit Prompt-/Eingabefingerabdruck umstellen.
  `counterfactual-worlds`: alte `endpoint`-Form. uniagent: TOML-Quoting für
  `[models.llama3.1-8b]`. Stand im jeweiligen Repo vor Änderung neu prüfen.
- **Ruhende Repos:** fallacy-datasets, visual-argument-spec,
  fallacy-detection, finance-discourse, paper-organization behalten ihren
  Pin bis zu neuer Arbeit. `thesis-dagidir` braucht dann gesonderten
  Import-/Pin-Umbau, keine automatische Aktualisierung.
- **Starter:** Beispielprotokoll in gestempelter Form prüfen;
  `requirements.lock` und Umgebungserfassung in Anleitung prüfen.
  Hausmaterial bleibt im Haus; neutraler Einstieg:
  [student-repos](docs/student-repos.md).
- **Alte Verweise/Kopien:** Unbenutzte `resources/templates/` in Laboren zur
  Löschung vorlegen; auditgebundene Module erst mit neuem Audit umstellen.
  Historische Protokolle und Archive nicht als lebende Dokumente behandeln.
- **PyPI:** Entscheidung offen; bis dahin gepinnte GitHub-Tags für
  Studierende erreichbar halten.
- **Harness:** Weitere Live-Hooks nur für Harness mit passender
  Schnittstelle. Überleben eines langen Vordergrundprozesses am Ende
  einer Codex-Sitzung erst am echten Mehrstundenlauf prüfen.

## Bei der nächsten Nutzung beobachten

- Teilweise gestagte berichtete Bereiche werden verweigert; Arbeitsbaum
  und Index müssen zur geprüften Zahl passen. Alte Änderungen können den
  Stop-Hook wiederholt in denselben Bereich führen. Reale Nutzung muss
  zeigen, ob Bedienung verbessert werden muss.
- Hook, `protocol-check` und Pre-Commit wiederholen teils denselben Befund.
  Deduplizierung erst bei belegtem Nutzungsproblem.
- Noch nicht erneut geprüfte Usability-Hinweise: `protocol-fill --list`
  nach `--prompts`, README-/Output-Warnungen, Leselast des Modellskeletts
  bei `seconds`. Vor Bauauftrag am aktuellen Stempel nachstellen.
- Parser bleiben absichtlich exakt; unlesbare Antworten werden gezählt
  und durch die Zulassungsbedingung begrenzt. Fachlicher Confound-Audit
  bleibt experimentabhängig. Wünsche nach generischen Rückfällen sind
  keine offenen Reparaturen.
