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
- Schließen ist kein Entscheiden (2026-10-23, sechste Runde t5:
  `dismissed` mit „insufficient evidence withdrawn“ nach `insufficient`
  gab frei): Hat eine Prüfung eine Entscheidung zu einem Befund im selben
  Record nicht bestätigt, bleibt der Befund auch unter `dismissed`,
  `fixed` oder `deferred` gehalten, bis eine Prüfung die neue Entscheidung
  bestätigt
  (`reviews.once_not_upheld`, `findings.CLOSING`). Note nach Grad wie
  beim `stands`: BLOCKER blockt, WARNING warnt. `--review` legt dem
  Prüfer Status, Begründung und das frühere Urteil vor; die
  Prüferanweisung sagt je Status, was die Begründung zeigen muss.
  `deferred` gehört dazu (entschieden 2026-10-24): Es entfernt den Befund
  ebenso aus den ausgewiesenen Einschränkungen wie `dismissed`. Deshalb
  darf das Zurückstellen eine zuvor nicht bestätigte Entscheidung nicht
  ohne weitere Prüfung freigeben. Die zusätzliche Prüfpflicht greift nur,
  wenn bereits eine Entscheidung zu diesem Befund im selben Record nicht
  bestätigt wurde. Ohne diese Vorgeschichte löst `deferred` sie nicht aus.
  Ein Wechsel auf `not assessable` braucht keinen erneuten Modellaufruf
  zur Prüfung: Der Befund bleibt als Einschränkung sichtbar, und die
  benannten Zusagen gelten mit diesem Lauf als nicht beurteilbar. Damit
  wird der Anspruch begrenzt, statt der Befund aus den Limits entfernt.

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
Die Count-/Judge-Proben auf `86e38bc` sind gelaufen (oben). Die Runde in
Bereich 09 ist auf `c49e760` gelaufen (2026-10-23,
[Bericht](docs/usability/2026-10-23-sandbox-c49e760.md)): Verdikt
no-advantage (Erfolg labkit 1/3 gegen plain 2/3, stille Abweichungen 5 in
jedem Arm, Standard erfüllt 0/3). Die Gates hielten bei jeder Anfrage;
die Agenten gingen außen herum — Bericht aus dem Lauf statt aus dem
Protokoll (t3, t18), Commit in zwei Schritten (t5), `dismissed` nach
`insufficient` (t5), gelöschte Audit-Records (t3), nicht gewartetes Audit
(t18). Daraus fünf nummerierte offene Punkte im Bericht. Der erste und
zweite sind am 2026-10-23 umgesetzt (CHANGELOG Unreleased, „Fixed“):
eine gestagte Deklaration, die von HEAD abweicht, hält die committeten
Berichte, die den Lauf zitieren; ein Befund, den eine Prüfung nicht
bestätigt hat, bleibt unter `dismissed`, `fixed` oder `deferred`
gehalten, bis eine Prüfung die neue Entscheidung bestätigt. Der dritte
ist am 2026-10-24 in seinen ersten zwei Stufen umgesetzt (CHANGELOG
Unreleased, „Fixed“): das Zitat des antwortenden Laufs eines Protokolls
ohne Deklaration blockt am Stop und am Commit; ein nur angeschauter Lauf
wird als solcher zitiert, `run <id> (not reported: <was die Übernahme
verweigerte, was gefunden wurde>)`, die Begründung ist Pflicht, Zahlen
daneben sind ein Hinweis. Die dritte Stufe, das kleine Abschluss-Audit
des Berichts, steht unten bei den zurückgestellten Erweiterungen
([Bericht ohne Übernahme](docs/notes/2026-10-23-report-without-adoption.md)). Der vierte (gelöschte Audit-Records) und der
fünfte (Auditdauer gegen das Kommando-Timeout) stehen unten bei den
offenen Verträgen.
Die siebte Runde in Bereich 09 lief auf `e9f088f` (2026-10-25,
[Bericht](docs/usability/2026-10-25-sandbox-e9f088f.md)): wieder
no-advantage (Erfolg labkit 1/3 gegen plain 2/3, stille Abweichungen
4 / 5 / 4, Standard erfüllt 0/3, alle drei labkit-Agenten bei `low`). Die
Riegel der sechsten Runde hielten (`dismissed` nach abgelehnter Prüfung
blieb gehalten); die Agenten gingen eine Stufe weiter außen herum: Zahlen
bleiben neben `(not reported: …)` als Ergebnis im Bericht (t3, t18), die
Run-ID wird gelöscht, um am Hook vorbeizukommen (t5). Fünf nummerierte
offene Punkte im Bericht; der dritte (claude-cli lehnt eine
Zwei-Zug-Antwort ohne Werkzeuge als unvollständig ab, t18) ist am
2026-10-25 geklärt: kein falsches „unproven“ — die Antwort lief in das
Ausgabelimit der CLI und wurde fortgesetzt, `result` hielt nur den Rest
([Probe](docs/notes/2026-10-25-cli-output-limit.md)); die Meldung nennt
jetzt die Ursache. **Offen:** ob labkit `CLAUDE_CODE_MAX_OUTPUT_TOKENS`
für seine CLI-Aufrufe selbst setzt (ändert die Provenienz jedes Laufs)
und ob nach einem abgeschnittenen Audit ein Versuch mit mehr Raum
erlaubt sein soll, den `findings.stopped_attempt` heute abweist.
Der vierte (nach gescheitertem Audit nichts getan, t18) fällt in den
ersten: t18 hat den angebotenen Weg „nicht berichten“ formal genommen
(`run … (not reported: analysis audit failed …)`), nur die Zahlen
blieben stehen; ein Hold auf „zitiert einen Lauf mit gescheitertem
Audit“ sperrte genau diese richtige Markierung. Kein eigener Bau. Der
fünfte ist gezählt ([Präzision](docs/usability/2026-10-25-hint-precision-r7.md)):
12 von 54 markierten Zeilen falsch, jeder Bericht hat falsche und
richtige markierte Zeilen — der Hinweis trennt keinen falschen Bericht
von einem richtigen und bleibt Hinweis. Die falschen Zahlen sind
durchweg Fakten über die Eingaben (Zeilenzahlen, Median, Klassengrößen),
die der Code rechnet, aber in keiner behaltenen Datei ablegt. Die Handurteile
der Runden 5 bis 7 sind Entwürfe eines Richters je Aufgabe.

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

- **Auditdauer bei `seconds`:** Die Fit-Probe verfehlte das
  Fünf-Minuten-Ziel (14m20s); zwei Analyse-Audits brauchten 75 % der Zeit
  und 86 % der Kosten, alles bis finalize 2m36s. Offen für den Autor:
  Zählt das geschuldete Audit zum Ziel, soll es gleich im Hintergrund
  laufen? Noch keine Ablaufänderung beschlossen.
  Beleg: [Fit-Probe](docs/usability/2026-10-22-sandbox-3e9784c.md).
  Sechste Runde (t18): das Analyse-Audit lief über das 120-s-Timeout des
  Agenten-Kommandos, wurde in den Hintergrund geschoben, der Container
  endete vor dem Record. Kandidaten ohne Bauauftrag: die AGENTS.md des
  Gerüsts nennt die Dauer und ein langes Timeout; das Audit druckt seine
  Fortschrittszeile vor dem Modellaufruf.
- **Compute mit Modellannotation:** Kein eigenes Skelett beschlossen,
  solange kein konkreter Bedarf besteht (Entscheidung 2026-10-23).
  `[model]` kann gespeicherte Annotationen beschreiben. Annotiert der
  Lauf selbst, sind Modellherkunft und Ausgaben zu erfassen; `llm.resolve`
  und `batch.Store` bieten die Mittel, das Compute-Skelett bindet sie
  nicht ein. Den Ablauf am ersten echten Annotierungslauf entwickeln,
  danach über ein Beispiel oder eine Vorlage entscheiden.
- **Modellannotierte Trainings-/Testdaten:** `fit`/`apply` auf Daten,
  die ein Modell annotiert hat (silver standard als Gold), bleibt eine
  offene Grenze ohne Bauauftrag. Die bereits gebaute
  `annotation_validity`-Bindung für `compute` löst diese Frage nicht.

### Abgeschlossene Vertragsarbeiten — Belege

- **CLI-Modellherkunft:** Sicherheitsabbruch, Modellwechsel und mehrere
  Züge werden verweigert, gescheiterte Audits gespeichert. Pflichtfelder
  sind `modelUsage` und `num_turns`; `safety_stops` wird geprüft, wo
  vorhanden. Am echten System und durch Count-/Judge-Regression belegt;
  kein offener Bauauftrag. Details:
  [Probe und Nachtrag](docs/usability/2026-10-22-sandbox-de663ed.md).
- **Registrierung und `compute | fit | apply`:** Schema, Skelette,
  `--kind`-Pflicht, Umbenennung `count` → `compute`, Modellanspruch
  (`number_describes`), Annotationseignung und Audit-Bündel samt Digest
  sind umgesetzt. Die kalte Klassifikationsprobe vom 2026-10-23 bestand
  zehn von zehn neuen Fällen; der Hinweis auf optimistische Werte nach
  Auswahl auf dem Berichtsset ist ergänzt. Vertrag und Wahlhilfe:
  [Field Guide](labkit/docs/protocol-field-guide.md); Format und Migration:
  [CHANGELOG](CHANGELOG.md). Belege:
  [Schreibprobe](docs/notes/2026-10-22-kind-writing-probe.md),
  [Fit-Probe](docs/usability/2026-10-22-sandbox-3e9784c.md),
  [volle Runde](docs/usability/2026-10-22-sandbox-de663ed.md).
  Es steht keine Schemaentscheidung oder Implementierung mehr aus;
  Release und externe Übernahme bleiben eigene Aufträge.

### Zurückgestellte Erweiterungen

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
  Berichtsprosa können beiden entgehen. **Erste zwei Fälle 2026-10-23
  (sechste Runde, t3 und t18):** `--from-run` verweigert, REPORT.md aus
  der metrics.json des Laufs geschrieben, der Hook warnte „exploration's
  run is cited“ und ließ durch — bei `seconds` ist der Bericht die
  Beförderung. Vorschlag in drei Stufen in
  [Bericht ohne Übernahme](docs/notes/2026-10-23-report-without-adoption.md).
  **Umgesetzt 2026-10-24, Stufe 1 und 2:** das Zitat des antwortenden
  Laufs eines Protokolls ohne Deklaration blockt am Stop und am Commit
  (`report_check.promotions`); Probe, quittierter Lauf und älterer Lauf
  bleiben die Warnung. Ausweg für einen nur angeschauten Lauf: die
  Markierung `run <id> (not reported: <was die Übernahme verweigerte,
  was gefunden wurde>)` — Begründung Pflicht wie bei `accepted`,
  `deferred`, `dismissed`; ohne sie oder auf einem deklarierten Lauf
  blockt sie. Zahlen im Absatz einer Markierung sind static evidence.
  Verweigerung der Übernahme und AGENTS.md des Gerüsts sagen dasselbe:
  eine Verweigerung ist ein Befund für den Bericht, kein Hindernis zum
  Umgehen. Entschieden dabei: Schreibweise (`lib term`: keine
  Fachprägung; „not reported“ stand im README schon für die Probe),
  Block am Stop wie am Commit, Bericht unter `notes/` wie an der
  Wurzel. **Offen:** Stufe 3, das kleine Berichts-Audit (Bericht,
  Protokoll, metrics.json; nur bei Markierung oder Zahlen daneben) —
  Kosten am ersten Fall messen, bevor es warnt. Und: der Blocker-Satz
  nennt das Übernahmekommando, nicht dessen Verweigerungsgründe; dafür
  müsste der Schreiber der Deklaration (`protocol_fill.fill_result_run`)
  unter das Gate ziehen. Erst, wenn ein Agent den Satz liest und die
  Übernahme trotzdem nicht aufruft.
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
  Zitat öffnet nichts. **Erster Fall 2026-10-23 (t5-labkit, sechste
  Runde):** Bericht mit Zitat committet, während das Protokoll mit der
  Deklaration ungestagt blieb (Warnung „exploration's run is cited“),
  dann das Protokoll committet, der Bericht unberührt — der gelieferte
  Stand hat den Blocker, kein Commit hatte ihn. **Umgesetzt 2026-10-23:**
  ein Protokoll unter den geprüften Pfaden, dessen `[result] run` von
  HEAD abweicht, hält jeden committeten Bericht, der diesen Lauf zitiert
  (`report_check.newly_declared`, `committed_reports`), am Stop und am
  Commit; der Zwilling mit bereits committetem Block besteht. Pauschales
  Verfolgen aller Zitate bleibt zurückgestellt: ein Zitat eines Laufs,
  dessen Deklaration sich nicht ändert, öffnet nichts.
  **Gelöschte Audit-Records (sechste Runde, t3):** der Agent löschte
  nach dem dritten Audit die zwei älteren Records (`rm audits/*.toml`),
  nichts bemerkte es. Erster Fall unter `audits/`; der `rm`-Wächter
  unter `runs/` bleibt zurückgestellt, für `audits/` ist noch keine
  kleinste Prüfung beschlossen (Kandidat: die Records, die HEAD unter
  `audits/` hält, fehlen im Stand — am Commit mechanisch prüfbar).
  Analyse-Records gelöschter Läufe werden bereits von `finalize`
  beanstandet.

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

Auch C4/C5/C7/C8 sind geschlossen: einheitliche Namen für Kostenklasse,
antwortenden Lauf und Provenienz (`ce7defc`); verpflichtende Evidenzart
am Gate-Finding (`fa8f7d0`); code-check-Docstring und Summary über
`Findings.report` (`497ce10`); dokumentierte Stop-/Commit-Hook-Grenze
(`a1af555`). Manuelle Audit-Refusals und Fortschrittsausgabe laufen über
`console` (`86df3ec`). Die Feldbedeutung und die Sperre gegen blockierende
statische Indizien stehen in `labkit/formats/gate.py` und werden in
`tests/test_gate.py` geprüft. Aus dem Audit vom 23. ist nichts mehr offen.

Notiert, nicht geplant: Audit-Records um die Protokoll-id ergänzen. Heute
wird der Abgleich gegen die Registrierung aus dem Protokolltext berechnet;
in einem Bereich mit mehreren Protokollen wählt das Gate das Protokoll
vorher (`repo.the_protocol`). Bauauftrag erst, wenn ein Fall zeigt, dass
ein Record dem falschen Protokoll zugeordnet wurde.

### Audit 2026-10-23, Nachkontrolle

Befunde mit Belegen: [Nachkontrolle](docs/audit-2026-10-23-followup.md)
(Stand `e5f0438`). Das Register vom Vormittag war abgearbeitet; übrig war
Prosa, die den neuen Heimaten nicht folgte, ein flatternder Test und ein
Blocker-Text, der Hinweiszeilen als Befunde auswies. Alle sieben Punkte
sind am 2026-10-23 abgearbeitet (`88b875d`…`7d1a2ed`, CHANGELOG
Unreleased): Uhr im Redraw-Test, Gate-Tabelle mit runlog-Zeile und
`audit_record_gap`, claude-hook-Exit-Vertrag, `intent_check.hold` als
Datenschnittstelle für finalize, drei Evidenz-Beschriftungen, die
übrigen Heimaten samt erweiterten Wächtern und Architektur-Tabelle, der
Kleinkram. Entschieden dabei: runlog meldet offene WARNINGs/NOTEs älterer
Preflight-Records weiterhin nur beim quittierten Start — der benannte
Record ist beim sauberen Start ganz entschieden (`audit_record_gap`),
ein älterer hält keinen Lauf. Aus der Nachkontrolle ist nichts mehr
offen; die Guards in `tests/test_one_home.py` halten weiterhin keinen
Grep für `runs.run_dirs` und `llm.model_entry` (bewusst: je ein Aufrufer
bzw. ein Test-gehaltener Walk).

### Typisierte Grenzen vervollständigen

| Bereich | Noch offen | Bedingung / Vertrag |
|---|---|---|
| Run-Tabellen | `RunConfig` typisiert die Felder, die labkit schreibt; `models_resolved` und `promises` bleiben geprüfte Tabellen (entschieden 2026-10-20, [Notiz](docs/notes/2026-10-20-typed-run-metadata.md)). | Typen in `llm_specs` bzw. `promises` ergänzen, sobald eine konkrete Invariante sie verlangt — nicht vorab. |

### Restarbeiten aus dem Code-Audit

Abgeglichen am 2026-10-23 mit dem aktuellen Code und Git-Verlauf.
Erledigt sind die Testabhängigkeiten (`9028414`), die Run-ID-Kollision
(`f75ef55`), die auffindbare Core-/Doktrin-Erklärung (`5f62601`) und der
`repo.shown`-Wächter für die try/except-Kopie (`dee9b19`). Belege für die
ursprünglichen Befunde: [Code-Audit](docs/audit-2026-10-18.md).

Übrig, ohne neue Priorisierung:

- Namen geprüft (2026-10-23): `registry`→`ledger` in `rules.py`,
  `trace`-Hilfetext, `sha256_file`→`source_digest` umgesetzt. Bleibt:
  `base_dir` in `runlog.run` ist das öffentliche Keyword der Vorlagen
  und Labs — nur mit Breaking-Release zu `area`; `--registry` als Flag
  ruft der Haus-Hook (`dotfiles/.githooks/pre-commit`) — Rollout.
- Verbleibende `noqa: C901` (16 nach dem 2026-10-23, code-check und
  intent-check sind abgebaut) entlang fachlicher Abläufe abbauen, wenn
  dort gearbeitet wird; nicht allein nach Dateilänge teilen.

### Kern, Doktrin und Formatbrüche

Die aktuellen Kopplungen stehen in `tests/test_architecture.py`
(`KNOWN_CROSSINGS`). Bei Arbeiten an einer solchen Stelle die Kopplung
abbauen; die Liste nicht beiläufig erweitern. Eigener Doktrin-Namensraum
erst, wenn Kern-Evaluation oder zweites Labor den Kern ohne Doktrin braucht.

| Kandidat | Auslöser und Abnahme |
|---|---|
| Startzeit mit Subsekunden im Record | Gleichsekunden-Sperre trifft ein Labor oder passender Formatbruch steht an. Eindeutige zeitliche Wahl im Orakel `tests/test_answering_run_exhaustive.py`; kein Altformat-Leser. Zufällige Suffix-Kollisionen sind seit `f75ef55` durch erneute ID-Wahl behandelt; das löst keine zeitliche Mehrdeutigkeit. |
| `notes_check` und deutsche Notizkonventionen nach LOCAL; Herkunft von Paper-Zahlen nach LAB | Fremdes Labor braucht die Trennung oder passende Breaking-Release. Beide Richtungen mit Regeltext und Hook-Anpassung gemeinsam behandeln. |
| Englische Notizverzeichnisse | Angekündigter Bruch mit Regeltext, Scaffolder, Lesern, Hooks und externem Rollout. Kein Umbenennen nebenbei. |
| Kostenstufe als Zweiwert: `repeat_cost = "low" \| "high"` — **gebaut 2026-10-25** (Protokollstandard 0.23, Bruch im CHANGELOG unter Unreleased), nicht released | Befund: die Gates kannten zwei Spuren (`standard_contract.lane`: `seconds` gegen den Rest), der Kopf drei Namen; `hours` versprach eine Prüfung, die es nie gab (888 Commits, counterfactual-worlds, uniagent: keine hours-eigene Narbe). Verworfen: `protection = rerun \| freeze` — beide Spuren frieren etwas ein. Doppelprägungs-Check leer (`lib term`, ML-Karte, Haus-Notes). Offen (Rollout, eigener Auftrag): Release 0.104.0 taggen und pushen; labkit-paper Areal 09 ist vorbereitet (Pin auf e9f088f, Zusatz, Standard-Check mit Versionsweiche, Zweiwert-Zählung für neue Runden; Image bauen erst nach dem Push, Store v7 und `BATCH` beim Start der Runde); Protokolle, `AGENTS.md` und Pins in counterfactual-worlds (0.85.0) und uniagent (0.88.8); LAB-017 behält den Namen, das Regelregister `~/.claude/resources/rule-registry.tsv` bleibt; die `minutes`/`hours`-Usability-Reihe (Abschnitt Messungen) läuft dann als `high`. |

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
| `promote <area>` | Erste echte Beförderung, bei der vorhandene Kommandos nicht reichen. | Dünne Hülle um Analyse-Audit und Entscheidungen, synchron mit Zeitlimit. `report-check` prüft die Freigabe bereits. |
| Weitere Protokollvereinfachung | Schreibprobe und externe Usability-Probe zeigen einen verbleibenden Bedarf. | Feldnamen, Frage in der Summary und Ergebnisdeklaration sind umgesetzt. Weichenwerte als Daten und eine kürzere Vorlage bleiben Kandidaten ohne Bauauftrag; Standard `0.22` ist kein offener Versionsplan. |
| Bereichsstand als Faktenzeile | Andere Person zeigt, dass die Zeile gebraucht und gelesen wird. | Bestehende Fakten projizieren: Registrierung, Probe, Freeze, Lauf, Tests, Zitat. Keine zweite Statusquelle. |
| Weiter vereinfachte Zählvorlage | Aktuelle Schreibprobe zeigt trotz der vier Konstanten und `input_dir()` einen konkreten Umweg. | `SOURCE`, `INPUTS`, `COUNT_FIELD` und `METRIC_KEY` sind umgesetzt; nur einen belegten verbleibenden Umweg vereinfachen. |
| Rückschrift am Laufende / weniger Kommandos | Gemessener Umweg trotz `protocol-fill --from-run`. | Bewusste Prüfung erzeugter Zeilen klären. `finalize` bleibt lesend; kein `finalize --write-back`. |
| Eigene Meldung für laufenden/abgebrochenen Audit | Realer Fall braucht mehr als bestehende Verweigerung ohne gültigen Record. | Keine zweite Heimat für „Audit ohne Ergebnis“. Frühere `.running`-/`unavailable`-Skizze ist kein offener Implementierungsplan. |
| `labkit-rules` | Modulpfad behindert Nutzung nachweisbar. | Kürzerer Einstieg, keine neue Regellogik. |

### Klarheit des Ablaufs

Workflow, ausführbares Zählbeispiel und kalte Leseprobe sind umgesetzt
und abgenommen (`26513e9`, `eab6c68`):
[Workflow](docs/workflow.md), [Beispiel](docs/examples/count-walkthrough.sh),
[Leseprobe](docs/usability/2026-10-22-workflow-reading-probe.md).
Kein offener Bauauftrag. Weitere Protokolländerungen verlangen die oben
unter „Messungen“ genannte Schreibprobe mit einer anderen Person.
Verbleibende Begriffsprobleme an konkreten Fehlwegen belegen;
Befund-Rückgaben bei ohnehin anstehenden Änderungen vereinheitlichen,
kein Gesamtumbau dafür. Änderungen am Haus-Skill bleiben externer Rollout.

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
  Die Entscheidungsprüfung ist inzwischen gebaut (offene WARNING-Frage
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



