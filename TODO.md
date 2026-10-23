# TODO — labkit

Diese Datei hält offene Arbeit, geltende Entscheidungen und ihre Auslöser.
Sie ist kein Änderungsprotokoll. Implementierte Verträge stehen in
[Architektur](docs/architecture.md), [README](README.md) und
[Laborstandard](labkit/docs/standard.md); Formatbrüche im
[CHANGELOG](CHANGELOG.md), Änderungen im Git-Verlauf. Datierte Audits und
Messungen sind Belege für ihren damaligen Stand, keine aktuellen Aufgabenlisten.

## Reihenfolge

**Beschlossene Richtung:** Maschinelle Verträge strukturiert, fachliche
Erklärung als Prosa, Ergebnisdarstellung aus gebundenen Quellen — die
Linie für 1.0. Die fünf Umbauphasen sind umgesetzt; Verträge stehen in
[Architektur](docs/architecture.md), [README](README.md) und
[Laborstandard](labkit/docs/standard.md), die Formatbrüche im CHANGELOG.
`protocol-fill` behält seinen Namen; Setzen, Rendern und Freigeben sind
getrennte Funktionen. Aktuell: Standard `0.22`, `kind` im Kopf
(`compute | fit | apply`), `Conclusion` für die fachliche Antwort und
`Recorded results` für die erzeugten Werte.

**Umgesetzt, kein offener Bauauftrag:** Audit-Snapshot, typisierte
Run-Records und Backend-Konfigurationen, Paketstruktur und Modulteilungen,
`run_kind`, strukturierte Ergebnis-/Modell-/Labeldeklaration und
Ergebnisrenderer. Aus der fünften Haiku-Runde zusätzlich: Berichtsblöcke
mit Protokollzuordnung, Block-Pflicht für geänderte zitierende Berichte,
Registrierung bei `seconds` gegen den Commit der ersten Messung,
Analyse-Records gelöschter Läufe als Blocker und die Entscheidungsprüfung.
Aus dem Review 2026-10-22: doppelte erzeugte Zeilen blocken (`8578d67`),
`preflight_audit` nennt den entschiedenen Record statt einer Zeile mit
`scope sha` (`965c0ee`, Breaking — der letzte maschinell gelesene Text in
einem TOML-Wert). `docs/workflow.md` mit ausführbarem Zählbeispiel und
kalter Leseprobe (`26513e9`, `eab6c68`). Die Übernahme in andere Repos
bleibt ein eigener Auftrag.

**Entscheidungsprüfung als Blocker (entschieden und umgesetzt 2026-10-22,
`86e38bc`, eng gehalten):** ein akzeptierter BLOCKER mit `stands` blockt
`report-check` und damit `--from-run`, bis eine gültige Prüfung ihn
bestätigt; veraltet, `rejected`, `insufficient`, widersprüchlich oder
unlesbar gibt nicht frei. Eine akzeptierte WARNING mit `stands` bleibt
Warnung. Umgesetzt und getestet:

- Bindung an Record, Entscheidungsstand, Code, gezeigten Lauf und Anspruch
  (`claim_sha`: die Conclusion; Recorded results und Limit-Zeilen sind
  erzeugt und über Record und Lauf gebunden — der Reviewer sieht sie, wie
  `--from-run` sie rendern wird; eine Bindung an sie machte jede Prüfung
  bei der Übernahme ungültig, End-to-End-Test 2026-10-22).
- Alle Prüfungen desselben Stands zählen; ein `rejected` oder
  `insufficient` wird durch ein späteres `upheld` nicht aufgehoben.
  `--again` dient der Messung und gibt einen strittigen Stand nicht frei.
- Nach `rejected` zuerst neu entscheiden: Anspruch begrenzen, Wirkung
  ändern oder Fehler beheben. Neues Audit nur bei geänderter Grundlage
  oder bestrittenem Befund, nicht als Erledigung der Ablehnung.
  Nach `insufficient` Beleg ergänzen und erneut prüfen.

Belege: [Replay mit zwei Durchläufen](docs/usability/2026-10-22-decision-review-replay-v5.md)
(13 von 15 Urteilen gleich) und
[Quellenbewertung aller 15 Entscheidungen](docs/usability/2026-10-22-decision-review-assessment-v5.md).
Die schwankende Baseline-Entscheidung bündelt den nachgerechneten Wert
und eine daraus von Hand abgeleitete Verbesserungsbehauptung. Abhilfe:
Baseline und Differenz im Lauf berechnen. Die Bewertung hat die Größe
des Selektionsbias und die Auswirkung des t18-Off-by-one nicht gemessen;
Aussagen über deren Größe sind dadurch nicht abgesichert.
Frische Runde auf `86e38bc` ([Bericht](docs/usability/2026-10-22-sandbox-86e38bc.md)):
sechs von sechs Zahlen richtig und gebunden, 4,22 USD; der einzige
Judge mit BLOCKER-`stands` lief `--review` von selbst aus AGENTS.md.
Seine zwei Verweigerungen waren der neue Schritt und sind behoben
(`7f7cd6f`): `--review` verlangt die Conclusion zuerst, `--record` nimmt
den bloßen Dateinamen. **Offen:** ob akzeptierte WARNINGs mit `stands`
ebenfalls eine Prüfung schulden — erst nach Beleg, dass eine solche
Warnung einen falschen Anspruch durchließ.

**Abnahme des aktuellen Stands:** Die nächste Runde in labkit-paper
Bereich 09 bewertet den fertigen Bericht am Entscheidungspunkt
`number_from_code`; grüne Blöcke allein reichen nicht. Kalte Count- und
Judge-Proben prüfen zusätzlich Bedienbarkeit, Fehlalarme, Zeit und
Kosten. Die Replay-Kopien bekannter Fehler ersetzen diese Nutzung nicht.
Die Count-/Judge-Proben auf `86e38bc` sind gelaufen (oben); die Runde in
Bereich 09 steht aus.

Die Messlatte trennt zwei Fragen: Rechnet und bindet labkit dieselben
gespeicherten Antworten gleich (Nachrechnen ohne Modellkosten)? Und
kommen kalte Agenten mit labkit zurecht? Gleiche Trefferquoten frischer
Modellaufrufe sind keine feste Latte. Die letzte abgeschlossene Reihe
auf dem Release 0.102.0 beantwortete beide Fragen positiv
([Bericht](docs/usability/2026-10-22-sandbox-4e07c9d.md)); sie belegt
nicht die danach geänderten Gates.

**Releases bis 1.0 (entschieden 2026-10-22):** Änderungen sammeln sich
unter „Unreleased“; ein Release erst an der Messlatte, nicht je Fix.
Brüche nennen die letzte lesende Version, ohne Altformat-Leser.
0.103.0 (`4be4ddd`) bleibt wie geschnitten. Studi-Repos behalten ihren
Pin. Release und externer Rollout bleiben eigene Aufträge.

**Für die übrigen Punkte ist keine neue Umsetzungsreihenfolge beschlossen.**
Für neue Prüfungen gilt: Erst ein belegter Fehler und sein korrekter
Zwilling, dann die kleinste passende Prüfung. Static evidence warnt und
beweist keine Semantik. Bis zur Messlatte bleibt das Stabilisierungsfenster;
weitere Vorschläge werden dadurch nicht vorgezogen.
Forschung und Benchmark-Fallliste liegen in
`~/work/projects/labkit-paper/`.

## Offene Verträge und Korrektheitslücken

- **claude-cli: Modellwechsel nach Sicherheitsabbruch — gebaut 2026-10-22
  (`aad2c54`, LAB-029).** Eine Antwort gilt nur, wenn `modelUsage` allein
  das angeforderte Modell zeigt, `safety_stops = 0` und `num_turns = 1`
  (Felder an der echten CLI 2.1.304 geprüft); sonst `UnprovenAnswer`,
  ohne Wiederholung. Nicht belegt: dass die JSON-Antwort beim echten
  Abbruch genau diese Felder setzt — die Antworten der Probe-Audits sind
  nicht gespeichert, der Check scheitert deshalb im Zweifel. Fit-Probe auf
  `4f4f238` (fester Prüfer `claude-opus-5-5`): alle acht Audit-Versuche
  gestoppt und von `claude-opus-4-8` fortgesetzt, labkit hat trotzdem
  wiederholt statt `UnprovenAnswer` zu werfen — vermutlich kam der
  Abbruch als `is_error`, die Felder gingen verloren; keine Zahl
  übernommen, fit-2 abgebrochen. Behoben in `1fc05e1`: Stopp und fremdes
  Modell vor `is_error`, jede Meldung nennt die Felder. Fit-Probe auf
  `97e6470` (unter `caffeinate -i`) hat den Nachweis gebracht: die CLI im
  Container (2.1.285) meldet den Abbruch als `subtype = "success"`,
  `is_error = false`, `num_turns = 2`, beide Modelle in `modelUsage`, ohne
  `safety_stops` — das Feld gibt es erst ab 2.1.304. Die Vermutung
  `is_error` war falsch; das Pflichtfeld `safety_stops` machte jede
  Antwort der älteren CLI zum wiederholbaren `ReplyError`. Behoben in
  `1fa93f6`: Pflicht sind `modelUsage` und `num_turns`, `safety_stops`
  zählt, wo vorhanden. Am echten System belegt auf `927159d`: zwei
  gestoppte Versuche sofort verweigert und als gescheiterte Audits
  gespeichert (einer davon setzte `claude-opus-5-5` selbst fort — nur die
  Zugzahl fing ihn), der dritte ein reines 5.5-Audit, Zahl übernommen.
  Regression Count/Judge auf `4c2c098` (Runner
  `~/projects/labkit-probes-sandbox-4c2c098`): 6 von 6 richtig, report-check
  sauber bis auf die gewollten Warnungen; jeder Haiku- und Opus-Aufruf der
  CLI 2.1.285 bestand den Herkunftscheck (ein Modell, kein Abbruch). Danach
  gebaut: Abbruch beim ersten `unproven` (`1014ad0`), Grund in report-check
  und Score (`02ec772`), `stop_reason = refusal` als Absicherung ohne
  Beleg (`fde9e11`), `failure.json` für abgebrochene Läufe (`e640614`).
  Erledigt; die Notiz
  ([Notiz](docs/usability/2026-10-22-sandbox-de663ed.md)).

- **Namenskandidat `compute` statt `count` (2026-10-22).** Prüfen, ob
  `compute` die Kategorie besser bezeichnet: direkte Berechnungen wie
  Zählen, Summen und Mittelwerte, deren berichtete Zahl keine
  Modellvorhersage bewertet. „Modellunabhängig“ wäre zu streng: Die
  Eingabedaten können zuvor von einem Modell erzeugt worden sein.
  `kind` beschreibt den Anspruch der Zahl, `cost` den Aufwand des Laufs;
  auch eine direkte Berechnung kann Sekunden, Minuten oder Stunden
  kosten. Der breitere Name macht verständlicher, warum diese Kategorie
  unterschiedliche Kostenstufen hat. Die vereinfachte Spur wurde
  eingeführt, weil der Auditaufwand bei einfachen Experimenten die
  eigentliche Messdauer übersteigen konnte. Eine Umbenennung ändert
  diese Prüfpflichten nicht. Kandidat für bessere Namensgebung, noch
  kein beschlossener Formatbruch und kein vorgezogener Bauauftrag.

  **Plan (entworfen 2026-10-23, wartet auf Entscheidung).** Einteilung
  nach dem Anspruch der Zahl, zwei Prüffragen: (1) Bewertet die Zahl die
  Vorhersagegüte eines Modells oder Vorhersageverfahrens? nein → `compute`;
  (2) im Experiment trainiert, angepasst oder ausgewählt? ja → `fit`,
  nein → `apply`. Fachanschluss: `fit` wörtlich aus der ML-Vorlesung
  („Learning task: Fit D“, model selection ML:II-189); `compute` = die
  Statistik-Seite (descriptive / inferential, ML:VII-1), nicht „estimate“
  (dort Lernvokabular: „least square estimates from D“). Getrennte Fragen:
  Anspruch (`kind`), Herkunft (`[model]`), Eignung des Instruments (neu).
  1. Umgesetzt (`a30e9bd`): `count` → `compute` innerhalb des unveröffentlichten Standards 0.22
     (CHANGELOG „Unreleased“: kein zusätzlicher Bruch für Releases, nur
     für dev-gepinnte Sandbox-Protokolle). Leser: `protocol_block.KINDS`,
     `standard_contract.COUNT_KIND`, `scaffold.py`, `protocol_check.py`,
     `start_check.py`, `protocol_report.py`, `probes/usability*.py`,
     Templates, README-Zeile `kind`, Standard, Field Guide, ~15 Testdateien.
     Migrationshinweis im CHANGELOG für auf Zwischencommits gepinnte Repos
     (`kind = "count"` → `"compute"`). Nach Bedeutung umbenennen, nicht
     global: das allgemeine Skelett (`standard_contract.COUNT`) heißt
     `compute`; die Usability-Aufgabe `count`, `usability-task-count` und
     `count-walkthrough.sh` zählen wirklich und bleiben.
  2. Umgesetzt (Commit „kind: a computation with a model says what its
     number describes“): `[model] number_describes = "model_outputs" |
     "target_property"`, bei `target_property` `annotation_validity = {
     protocol = "p-…" }` oder `{ doi = "10.…" }`; Bindung in
     `protocol_history.check_annotation_validity` (protocol-check,
     preflight). Fachbegriff annotation validity (NLP:III-167/173). Offen:
     - Skelett für `compute` + `[model]`: entschieden 2026-10-23, kein
       eigenes, bis ein konkreter Bedarf da ist. `[model]` heißt nicht, dass
       der Lauf ein Modell aufruft; er kann gespeicherte Annotationen
       auswerten. Annotiert der Lauf selbst, wird der Modellaufruf mit
       Herkunft und Ausgaben erfasst, ohne Gold oder Leistungskriterium zu
       verlangen. Befund: die Mittel gibt es (`labkit/run/llm.py:164`
       `resolve` in die Run-Config, `labkit/run/batch.py:222` `Store` mit
       `_instrument`/`_prov` je Zeile), das compute-Skelett
       (`measure-quick-script.py.template`) bindet sie nicht ein — und
       bekommt auch keine auskommentierte Variante. Steht ein echter
       Annotierungslauf an, an ihm den Ablauf entwickeln, danach
       entscheiden, ob ein Beispiel oder eine eigene Vorlage lohnt.
     - Audit-Bündel: erledigt 2026-10-23. `audit.validity_evidence` zeigt
       dem Preflight- und Analyse-Audit das gebundene apply-Protokoll, die
       `metrics.json` des erklärten Laufs, den `models.toml`-Eintrag und den
       Prompt; ungebunden eine Zeile „NOT BOUND“, DOI „form only“.
       Digest erledigt 2026-10-23: der Area-Stempel (`scope_sha`) deckt den
       Beleg mit (`validation_basis`), ohne Schemaänderung; eine geänderte
       Validierung macht den Record stale, eine DOI bindet nur ihren String.
     Offene Grenze, nicht geplant: `fit`/`apply` auf Trainings- oder
     Testdaten, die ein Modell annotiert hat (silver standard als Gold).
  3. Umgesetzt (Commit „docs: choosing the kind“): zwei Prüffragen in
     `labkit-init exp --help` und `AGENTS.md.template`; „Choosing the kind“
     mit Grenzfalltabelle (13 Fälle) im Field Guide.
  4. Probe: erledigt 2026-10-23. Kalter Haiku-Agent, nur `--help` und der
     kind-Abschnitt des Field Guides, zehn neue Fälle (nicht aus der
     Tabelle), Erwartung vorab festgelegt: 10/10 bei `kind` und
     `number_describes`. Lücke: Auswahl auf demselben Set, auf dem berichtet
     wird (Few-shot-Fall), war als `fit` richtig, aber die Doku sagte nicht,
     dass die Zahl dann optimistisch ist — Satz im Field Guide ergänzt.
     Clustering (Silhouette) ohne Tabellenzeile richtig als `compute`.
  Release 0.104.0 hängt an der Abnahme, nicht allein an diesem Umbau;
  Push und Tag beim Nutzer.

- **Registrierung für klassisches ML — entschieden und gebaut 2026-10-22
  (`e4157cb`, Standard 0.22; Fit-Probe `d549696`).** Beschluss des Autors:
  Schema `kind ∈ {count, fit, apply}` mit den Pflichten der Schreibprobe;
  `kind` beschreibt den Qualitätsanspruch der berichteten Zahl, nicht alle
  Operationen des Laufs. Bedingungen erfüllt: unbekannte oder
  widersprüchliche Angaben scheitern laut (`protocol_block.head`,
  `protocol_check.kind_gap`, `labkit-init` ohne `--kind` stempelt nichts),
  kein stilles Zurückfallen auf `count`; Migration ausdrücklich und
  getestet — ein 0.21-Kopf wird mit dem Satz verweigert, der die zwei
  Edits nennt (`protocol_block.MIGRATION`), kein Altformat-Leser. Runde
  auf `d549696` gelaufen (Runner `~/projects/labkit-probes-sandbox-d549696`):
  sieben von sieben richtig, keine Fehlklassifikation, kein Rückfall auf
  `count`. Ihre zwei Befunde behoben: finalize übersprang `intent-check`,
  wenn die Prosa `C1:` statt `[C1]` schrieb (`f1c5cdf`, sieben Fixtures
  hingen an dem Loch); `00_prepare.py --audit` des Schätzers rief das
  Textprofil (`15cc01b`). Dazu stempeln Fit und Apply `[C1]`/`[A1]`/`[A2]`
  vor die Platzhalter (`ab37f65`). Ein Count schuldet auf keiner Stufe
  eine Bar und wird ohne Bar-Felder und Promise-Tabellen gestempelt
  (`3e9784c`; vorher blockte ihn seit `f1c5cdf` sein eigener Stempel).
  Fit-Probe auf `3e9784c` (Runner `~/projects/labkit-probes-sandbox-3e9784c`):
  der kalte Agent übernimmt `[C1]`/`[A1]`/`[A2]`, `--audit` läuft durch,
  finalize prüft drei Ids gegen metrics.json, report-check sauber, Zahl
  0,719 wie zuvor. Ihr Analyse-Audit fand, dass das geteilte
  `02_analyze.py --draws` beim Schätzer `c1_accuracy None` druckte —
  behoben (`61fc6ee`), beide Skelette getestet (`ab22d9d`). Zeitziel
  verfehlt (14m20s statt 5 min); die Anteile stehen in
  [der Notiz](docs/usability/2026-10-22-sandbox-3e9784c.md): zwei
  Analyse-Audits 75 % der Zeit und 86 % der Kosten, alles bis finalize
  2m36s. Noch keine Änderung daraus; offen für den Autor: zählt das bei
  `seconds` geschuldete Audit zum 5-Minuten-Ziel, soll es gleich im
  Hintergrund laufen? Volle Runde auf `de663ed` (alle Fixes): sieben von
  sieben richtig, Ids überall geprüft, keine Verweigerung
  ([Notiz](docs/usability/2026-10-22-sandbox-de663ed.md)). Vorgeschichte: die
  Pflichtfelder folgten
  `standard_contract.registration_fields`; ohne `[model]` schuldet ein
  Seconds-Experiment nur die Frage und bekommt das Zählskelett. t5 und
  t18 (RandomForest) hätten die neue Commit-Bindung deshalb bestanden.
  Der Standard nimmt ausdrücklich nur den „plain count whose prose names
  no id“ aus (0.87.1), nicht den Schätzer. Vorschlag (2026-10-22): Kopffeld
  `[protocol] kind = "count" | "fit" | "apply"`, klein auf `main` gebaut —
  `labkit-init exp --kind …` statt des impliziten `--model`,
  `registration_fields(kind)` (count: Frage; fit: dazu Kriterium und
  Zulassung; apply: dazu Datenprofil), `skeleton(cost, kind)` gibt dem
  Schätzer bei `seconds` sein Skelett, der Standard-Satz nennt den Count
  beim Namen; Breaking unter Unreleased. Branch
  `origin/claude/zealous-davinci-3hbhvk` (32 Commits, Basis 2026-10-17,
  flaches Layout) ist Vorlage, nicht mergebar. Beschluss 2026-10-22:
  Option A bevorzugt, erst die Schreibprobe als Entscheidungstor —
  gelaufen ([Notiz](docs/notes/2026-10-22-kind-writing-probe.md)): Count,
  zwei Fits (DILI, DKPES) und der Judge sind ohne Sonderregel
  registrierbar; `kind` bezeichnet, was die berichtete Zahl behauptet,
  reine Inferenz ohne berichtete Zahl braucht keinen vierten Wert.
  B und C dort verworfen. **Nächster Schritt: verbindliche
  Schemaentscheidung des Autors, dann der Bau.** Der labkit-paper-Check
  verlangt die drei Felder bereits; Übernahme ist ein eigener Auftrag.
- **Protokollprosa außerhalb des geprüften Anspruchs:** Die
  Entscheidungsprüfung bindet die Conclusion (Recorded results und
  Limit-Zeilen sind erzeugt und über Record und Lauf gebunden). Die
  übrige Prosa hat keinen eigenen Digest im
  Analyse-Record. Beschluss vom 2026-10-20: keine pauschale Bindung,
  weil jede Prosakorrektur ein bezahltes Audit fällig machte. Auslöser
  für eine Erweiterung bleibt ein belegter Fehler in diesen übrigen
  Feldern. Prompt und Snapshot müssen dieselben gelesenen Bytes
  beschreiben (`tests/test_audit.py`, `OneSnapshot`).
- **Abschluss-Audit des fertigen Berichts:** Als Pflicht zurückgestellt.
  Berichtsblöcke decken ihre erzeugten Werte; die Entscheidungsprüfung
  prüft vorhandene `stands`-Entscheidungen gegen den Protokollanspruch.
  Neue Überansprüche oder falsch bezeichnete Zahlen in freier
  Berichtsprosa können beiden entgehen. Auslöser bleibt ein solcher
  Fehler in der nächsten Runde trotz der neuen Prüfungen. Ein Versuch
  ohne Sperrwirkung ist ein Vorschlag, noch kein Bauauftrag. Ein
  vollständiges zusätzliches Analyse-Audit erhöht den Auditaufwand;
  die Kosten einer begrenzten Berichtsprüfung sind nicht gemessen.
- **Limit-Zeilen aus Preflight-Records:** Der Renderer übernimmt Limits
  aus abdeckenden Analyse-Records. Akzeptierte Preflight-BLOCKER
  (`minutes`/`hours`) sind noch nicht einbezogen. In der fünften Runde
  nicht erprobt, alle Versuche liefen bei `seconds`; zurückgestellt.
- **Hinweise am Stop:** Zahlen außerhalb der Berichtsblöcke bleiben
  static evidence. Der Stop-Hook zeigt sie nur neben einem Blocker;
  im direkten Aufruf und beim Commit sind sie sichtbar. Im t5-Replay
  nennt der Scan die erfundenen und viele richtige Zahlen auf insgesamt
  29 Zeilen. Sichtbarkeit und Signalqualität in der nächsten Nutzung
  beobachten, noch keine neue Ausgaberegel beschlossen.
- **Historische Zitate und gelöschte Läufe:** Geänderte bzw. gestagte
  zitierende Markdown-Berichte sind geprüft; ein unberührtes altes
  Zitat öffnet nichts. Pauschales Verfolgen aller Zitate und ein
  `rm`-Wächter unter `runs/` bleiben zurückgestellt. Analyse-Records
  gelöschter Läufe werden bereits von `finalize` beanstandet; ein
  zusätzlicher Wächter braucht einen erneuten belegten Bedarf.

## Architektur und Lesbarkeit — notiert, nicht geplant

### Audit 2026-10-23

Befunde mit Belegen: [Repo-Audit](docs/audit-2026-10-23.md) (Stand
`b4cd032`). Abgearbeitet am 2026-10-23 (Commits `b8c0ed2`…, CHANGELOG
Unreleased): Drift D1–D6, B1 (finalize-Gründe im Blocker), B2 (atomare
Schreibzugriffe überall), C1 (`findings.open_findings` mit der Tabelle der
Gate-Regeln — die Unterschiede sind Absicht), C2/C3/C6 (Gate-Reihenfolge
in `docs/architecture.md`, Exit-Vertrag in jedem `--help`, `labkit-audit`
behält Exit 1 bei Warnung und sagt es), die sechs doppelten Heimaten,
der Kleinkram. Entschieden:

- Gate-Urteile werden neu berechnet, nie protokolliert — festgeschrieben
  in `docs/architecture.md`, „Where verdicts are recorded“. Ein
  Urteils-Log wäre eine zweite Wahrheit, die vom beurteilten Stand
  wegdriftet.
- Keine Breaking-Pause vor 1.0: das Repo ist in der Entwicklung, die
  Lab-Repos ziehen über die Migrationssätze im CHANGELOG nach.

**C5, zweiter Teil — `evidence_kind` am Gate-Finding (geplant, ein
Commit).** Namen sind seit `ce7defc` eindeutig (`Lane.cost_tier`). Offen
ist das Datenfeld. Durchgang über die echten Findings (2026-10-23):

| Finding (Text im Gate) | Gate | grade | evidence_kind |
|---|---|---|---|
| `[C1] registered, no key literal in the scripts` | code-check | BLOCKER | guaranteed |
| `[A1] key written, never read` | code-check | WARNING | static evidence |
| `stamp coverage: sys.path edit at scripts/01_measure.py:12` | code-check | WARNING | static evidence |
| `cost tier lowered since the first commit` | protocol-check, preflight | WARNING | static evidence |
| `no completed run bound to p-…; r1: …` | finalize | BLOCKER | guaranteed |
| `intent-check: [A2] registered, but metrics.json has no 'a2'` | finalize | BLOCKER | guaranteed |
| `test_01_x.py failed (1 failed)` | finalize, preflight | BLOCKER | guaranteed |
| `pytest is not installed — tests not run` | finalize, preflight | WARNING | guaranteed |
| `<record>: … — undecided (LAB-015)` | finalize, preflight, runlog, Hooks | nach Grad des Records | guaranteed |
| `no analysis audit saw the area as it is now` | report-check | BLOCKER | guaranteed |

Drei Festlegungen daraus:

1. **Das Feld klassifiziert den Satz in `text`, nicht die Sache.** „Record
   X hält einen unentschiedenen BLOCKER" ist eine Registerabfrage,
   guaranteed; das Agentenurteil steht im Record mit eigenem Grad.
   Darum hat `GateFinding.evidence_kind` zwei Werte, `guaranteed` und
   `static evidence`; `agent audit` ist keine Gate-Aussage, sondern die
   Natur von `findings.Finding`. AGENTS.md nennt drei Stufen, das bleibt
   richtig: die dritte lebt in den Records, nicht im Gate.
2. **Pflichtangabe ohne Default; `static evidence` + BLOCKER ist ein
   `ValueError` in `__post_init__`**, mit Twin-Test. `ParamRow.tier` wird
   `evidence_kind` und liest dieselben Konstanten aus `gate`.
3. **Anzeige nur, wo sie trägt**: in der `labkit-params`-Spalte wie heute
   und in der gepunkteten Form der Code-Checks (`WARNING · static evidence
   · a.py:12 · …`), weil dort schon Teile stehen. Prefixed-Zeilen bleiben
   `WARNING: …`; die Summary zählt: `2 blocker(s), 3 warning(s) (2 static
   evidence)`. C5 schließt, wenn Feldbedeutung (Punkt 1) in `gate.py`
   dokumentiert und getestet ist.

Notiert, nicht geplant: Audit-Records um die Protokoll-id ergänzen. Heute
wird der Abgleich gegen die Registrierung aus dem Protokolltext berechnet;
in einem Bereich mit mehreren Protokollen wählt das Gate das Protokoll
vorher (`repo.the_protocol`). Bauauftrag erst, wenn ein Fall zeigt, dass
ein Record dem falschen Protokoll zugeordnet wurde.

### Core und Doktrin auffindbar erklären

Lesebefund vom 2026-10-22: Die Definition in
[`docs/architecture.md`](docs/architecture.md) steht unter dem Fettwort
„Core or doctrine.“ mitten im Abschnitt; beim Sprung zur Modultabelle
wurde sie überlesen. Das README führt den Begriff Doktrin nicht ein,
und die Tabelle verweist nicht zur Definition zurück. Die Unterscheidung
soll einen eigenen, verlinkbaren Abschnitt bekommen: Core beantwortet
die laborübergreifenden Fragen der Rückverfolgbarkeit; Doktrin bezeichnet
Entscheidungen, die ein anderes Labor anders treffen könnte. Streich-Test,
Importregel und Abgrenzung zum Haus dort zusammen erklären. An der Tabelle
ausdrücklich sagen: Die dritte Spalte nennt die Doktrinmodule; alle übrigen
Module der zweiten Spalte sind Core. Vom README und von der Tabelle auf
diese Erklärung verweisen.

### Typisierte Grenzen vervollständigen

| Bereich | Noch offen | Bedingung / Vertrag |
|---|---|---|
| Run-Tabellen | `RunConfig` typisiert die Felder, die labkit schreibt; `models_resolved` und `promises` bleiben geprüfte Tabellen (entschieden 2026-10-20, [Notiz](docs/notes/2026-10-20-typed-run-metadata.md)). | Typen in `llm_specs` bzw. `promises` ergänzen, sobald eine konkrete Invariante sie verlangt — nicht vorab. |

### Restarbeiten aus dem Code-Audit

Kandidaten aus [Code-Audit](docs/audit-2026-10-18.md); vor Umsetzung am
aktuellen Code prüfen, keine alten Zeilennummern als offenen Befund übernehmen:

- Voneinander abhängige Tests: `tests/test_end_to_end.py` (Klasse `Judge`,
  `test_04`–`test_06` brauchen `run_id` aus früheren Schritten) läuft nur
  mit `--dist loadscope` grün (2026-10-23, fünf Fehler unter `-n auto`
  allein). Der Hook setzt es; unabhängig sind die Tests damit nicht.
- Namen prüfen: `area: Path`, Wurzelpfade, Digest-Begriffe,
  `trace`/`timeline`, `registry`/`ledger`. Keine pauschale Umbenennung.
- Verbleibende `noqa: C901` entlang fachlicher Abläufe abbauen, wenn dort
  gearbeitet wird; nicht allein nach Dateilänge teilen.
- Der Wächter für `repo.shown` in `tests/test_one_home.py` erkennt nur die
  Bedingungsform (`is_relative_to`), keine neue `try`/`except
  ValueError`-Kopie.

### Run-ID-Kollision

2026-10-21 kollidierten in `test_repeats` zwei zufällige 4-Hex-Suffixe
bei Starts in derselben Sekunde; `mkdir` brach mit `FileExistsError` ab.
Ein neues Suffix bei dieser Kollision wäre die enge Korrektur, ohne
Formatbruch. Vor Umsetzung am aktuellen `Run.__init__` prüfen;
keine beschlossene Priorität.

### Kern, Doktrin und Formatbrüche

Die aktuellen Kopplungen stehen in `tests/test_architecture.py`
(`KNOWN_CROSSINGS`). Bei Arbeiten an einer solchen Stelle die Kopplung
abbauen; die Liste nicht beiläufig erweitern. Eigener Doktrin-Namensraum
erst, wenn Kern-Evaluation oder zweites Labor den Kern ohne Doktrin braucht.

| Kandidat | Auslöser und Abnahme |
|---|---|
| Startzeit mit Subsekunden im Record | Gleichsekunden-Sperre trifft ein Labor oder passender Formatbruch steht an. Eindeutige zeitliche Wahl im Orakel `tests/test_answering_run_exhaustive.py`; kein Altformat-Leser. Zufällige Suffix-Kollisionen sind ein eigener Fehler, siehe oben. |
| `notes_check` und deutsche Notizkonventionen nach LOCAL; Herkunft von Paper-Zahlen nach LAB | Fremdes Labor braucht die Trennung oder passende Breaking-Release. Beide Richtungen mit Regeltext und Hook-Anpassung gemeinsam behandeln. |
| Englische Notizverzeichnisse | Angekündigter Bruch mit Regeltext, Scaffolder, Lesern, Hooks und externem Rollout. Kein Umbenennen nebenbei. |

## Evaluation und Vorschläge mit Auslöser

### Messungen

- **Aktuelle Vorlagen und Gates:** Vor Rollout bzw. nach relevanten
  Änderungen `count` und `judge` mit je drei kalten Läufen messen:
  richtige und gebundene Zahl, Fehlalarme, Fehlbedienung, Zeit, Kosten
  und Quelltext-/Standard-Lesungen. Offene Abnahme: siehe Reihenfolge.
  Die `minutes`-Reihe ist abgeschlossen; Wiederholung nach relevanter
  Änderung. Belege: [Count](docs/usability/2026-10-12-cloud-fable.md),
  [Judge](docs/usability/2026-10-14-judge-minutes.md).
- **Umgesetzte Usability-Korrekturen:** Kein offener Bauauftrag für
  `--decide`/`--findings`, Count-Eingaben und -Ausnahme, Judge-Modulteilung,
  Data profile, Nachlauf-Felder oder erzeugte Limit-Zeilen. Belege:
  [kalte Reihe](docs/usability/2026-10-20-cold-probes-22483de.md),
  [Sandbox](docs/usability/2026-10-21-sandbox-probes-44db3ac.md),
  [Count](docs/usability/2026-10-21-sandbox-count-45bb0a2.md),
  [Befundliste](docs/usability/2026-10-21-sandbox-judge-a2302bc.md),
  [Judge-Teilung](docs/usability/2026-10-21-sandbox-judge-be50b1b.md),
  [Datenprofil und Limits](docs/usability/2026-10-21-sandbox-judge-07a610e.md),
  [WARNING-Effekte](docs/usability/2026-10-21-sandbox-judge-ef6c3b1.md).
  Der damalige Verlust der fachlichen Antwort im Key-Dump ist durch
  die Trennung von Conclusion und Recorded results behoben; die
  fachliche Tragfähigkeit der Conclusion bleibt Audit-Gegenstand.
- **Umfang der Limit-Zeilen:** In der Reihe auf `ef6c3b1` erhielt jede
  akzeptierte WARNING eine Wirkung, auch „one draw“. Ein Sammelvermerk
  ist umgesetzt (`8aabde6`); ob jede dieser WARNINGs eine eigene
  Limit-Zeile braucht, bleibt offen. Preflight-Limits: siehe Verträge.
- **Sandbox:** labkits Proben nutzen das separate Paket
  `~/projects/agentsandbox`. Die Umstellung von labkit-paper und das
  Entfernen seiner Kopie in `lib/agentsandbox` bleiben ein externer
  Auftrag; `batch`, `arms`, `benches` und `standard_check` gehören nicht
  zum allgemeinen Harness. Keine neue Sandbox-Implementierung in labkit.
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
| Workflow mit ausführbarem Zählbeispiel | Nächster Vorschlag zur Klarheit nach den expliziten Stufen in `report-check`; Arbeitsablauf unabhängig vom Haus-Skill zugänglich machen. | `docs/workflow.md` mit einem kleinen Beispiel und Leseprobe; Umfang und Abnahme unter „Klarheit des Ablaufs“. Einzelverträge verlinken. |
| `promote <area>` | Erste echte Beförderung, bei der vorhandene Kommandos nicht reichen. | Dünne Hülle um Analyse-Audit und Entscheidungen, synchron mit Zeitlimit. `report-check` prüft die Freigabe bereits. |
| Weitere Protokollvereinfachung | Schreibprobe und externe Usability-Probe zeigen einen verbleibenden Bedarf. | Feldnamen, Frage in der Summary und Ergebnisdeklaration sind umgesetzt. Weichenwerte als Daten und eine kürzere Vorlage bleiben Kandidaten ohne Bauauftrag; Standard `0.22` ist kein offener Versionsplan. |
| Bereichsstand als Faktenzeile | Andere Person zeigt, dass die Zeile gebraucht und gelesen wird. | Bestehende Fakten projizieren: Registrierung, Probe, Freeze, Lauf, Tests, Zitat. Keine zweite Statusquelle. |
| Weiter vereinfachte Zählvorlage | Aktuelle Schreibprobe zeigt trotz der vier Konstanten und `input_dir()` einen konkreten Umweg. | `SOURCE`, `INPUTS`, `COUNT_FIELD` und `METRIC_KEY` sind umgesetzt; nur einen belegten verbleibenden Umweg vereinfachen. |
| Rückschrift am Laufende / weniger Kommandos | Gemessener Umweg trotz `protocol-fill --from-run`. | Bewusste Prüfung erzeugter Zeilen klären. `finalize` bleibt lesend; kein `finalize --write-back`. |
| Eigene Meldung für laufenden/abgebrochenen Audit | Realer Fall braucht mehr als bestehende Verweigerung ohne gültigen Record. | Keine zweite Heimat für „Audit ohne Ergebnis“. Frühere `.running`-/`unavailable`-Skizze ist kein offener Implementierungsplan. |
| `labkit-rules` | Modulpfad behindert Nutzung nachweisbar. | Kürzerer Einstieg, keine neue Regellogik. |

### Klarheit des Ablaufs

Vorschlag vom 2026-10-22, am selben Tag umgesetzt: 1 als
`docs/workflow.md`, `docs/examples/count-walkthrough.sh` und
`tests/test_workflow_example.py` (`26513e9`); 2 und 3 im bearbeiteten
Ablauf (`e8698ab`: Stufen am Einstieg von `report-check`,
`Findings.take_all`, Glossarbegriffe in Code und Ausgabe), nicht
paketweit. Abnahme gelaufen: die kalte Leseprobe beantwortete alle vier
Fragen richtig ([Protokoll](docs/usability/2026-10-22-workflow-reading-probe.md));
ihre Stolperstellen sind eingearbeitet (`eab6c68`, Meldungen in
`report_check` danach). Offen bleibt nur die Schreibprobe vor weiteren
Protokolländerungen. Der Vorschlag im Wortlaut:

1. **Workflow und Zählbeispiel gemeinsam.** `docs/workflow.md` erklärt
   auf Englisch Registrierung → Lauf → Finalize → Analyse-Audit →
   Entscheidungen → gegebenenfalls Entscheidungsprüfung → Übernahme →
   Berichtsblock; die zusätzlichen Schritte bei `minutes`/`hours` werden
   an ihrer Stelle genannt. Pro Schritt: Befehl, gelesene und veränderte
   Dateien, Voraussetzungen und Bedeutung eines erfolgreichen Abschlusses.
   Regeln aus Architektur und Standard verlinken, nicht erneut definieren.
   Ein kleines ausführbares Zählbeispiel zeigt Protokoll, Lauf,
   Recorded results und report result block. Danach eine erzeugte Zahl
   ändern und zeigen, welche Prüfung sie zurückweist. Ein Count ohne
   BLOCKER demonstriert keine Entscheidungsprüfung; deren bedingte
   Pflicht muss trotzdem verständlich werden.
2. **Begriffe in Code und Ausgabe nachziehen.** `run`, `answering run`,
   `declared run`, `run entry`, `recorded results` und `report result block`
   nach dem README-Glossar verwenden. Meldungen nennen das betroffene
   Objekt und den konkreten nächsten Schritt. Verbleibende Irrwege an
   der Leseprobe festmachen, keine pauschale Umbenennung.
3. **Befund-Rückgaben bei ohnehin anstehenden Änderungen vereinheitlichen.**
   Neue oder bearbeitete Checks geben möglichst `GateFinding` zurück;
   der Einstieg hält Reihenfolge und Bedingungen, `Findings` sammelt und
   zeigt die Daten. Kein Gesamtumbau nur zur Vereinheitlichung.

**Abnahme:** Eine Person, die den Code nicht geschrieben hat, verfolgt
das Beispiel und erklärt ohne Hilfe: Wo wird der antwortende Lauf
ausgewählt? Wann ist eine Entscheidungsprüfung nötig? Welche Datei
verändert `--from-run`? Was garantiert der Berichtsblock, und was bleibt
fachliches Urteil? Konkrete Fehlwege aufzeichnen und gezielt korrigieren.
Die bestehende Schreibprobe vor weiteren Protokolländerungen bleibt nötig.
Änderungen am Haus-Skill sind externer Rollout, kein Teil dieses Schritts.

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

Für labkit-paper, Bereich 09 (eigener Auftrag): t18s Setup und Code
schneiden die MC-/LC-/NC-Blöcke um eine Zeile versetzt; die Behauptung
„verified“ ist falsch. Die tatsächlichen Zeilenbereiche sind MC 1–174, LC 175–434,
NC 435–661. Auswirkung auf die berichtete Genauigkeit noch nicht
nachgemessen. Beleg: [Quellenbewertung](docs/usability/2026-10-22-decision-review-assessment-v5.md).

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
- `--effect stands` als Reflex: Die frühen Judge-Reihen wählten fast
  ausschließlich `stands`; auf `42f0ec8` erstmals einmal `not assessable`.
  Die Entscheidungsprüfung ist inzwischen gebaut (offene Blocker-Frage
  oben). In der nächsten Reihe beobachten, ob sie begründete
  Neuentscheidungen bewirkt und wie oft `not assessable` gewählt wird.
  Zusätzlich prüfen, ob Autoren den Beispielsatz der Seconds-Spur nur
  kopieren oder die Conclusion fachlich schreiben und ob sie dort
  erzeugte Werte wiederholen. Noch keine Regel gegen die Kopie.
- Platzhalter-Erkennung (`c1dd888`): exakt sind nur die Phrasen des
  Stempels; ein vom Autor geprägtes `<…>` mitten im eigenen Satz bleibt
  unerkannt — absichtlich, weil Inhalt und Platzhalter dort nicht
  mechanisch zu trennen sind. Beobachten, ob kalte Agenten solche eigenen
  Platzhalter hinterlassen (2026-10-21).
- Prompt weiter als die Gold-Legende: 3 von 30 kalten Judges schrieben
  „state or imply“ statt der Legende „claims“; im Eingriff (je fünf
  Ziehungen, nur die Frage getauscht) 8–9/12 gegen 10–11/12, C1 an der
  Kante ([Notiz](docs/notes/2026-10-21-judge-prompt-wider-than-gold.md)). Das
  Audit fand es (judge-3). Möglicher Hinweis im Skelett beim `PROMPT`-TODO:
  die Frage in den Worten der Gold-Legende stellen. Neue Vorgabe — erst
  nach dem Stabilisierungsfenster und nur, wenn es wieder vorkommt; das
  Audit fängt es heute (2026-10-21).
