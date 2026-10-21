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

- **Protokollprosa:** Der Record bindet Code, Promise-Block und beim
  Analyse-Audit den Lauf samt dem Gezeigten (`shown_sha`). Die übrige
  Protokollprosa hat keinen eigenen Digest — entschieden 2026-10-20:
  vorerst nicht binden, weil jede Prosakorrektur ein bezahltes Audit fällig
  machte. Auslöser: ein echter Fall, in dem eine Prosaänderung ein
  berichtetes Ergebnis verfälscht hat. Für den bestehenden Snapshot gilt:
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
| Run-Tabellen | `RunConfig` typisiert die Felder, die labkit schreibt; `models_resolved` und `promises` bleiben geprüfte Tabellen (entschieden 2026-10-20, [Notiz](docs/notes/2026-10-20-typed-run-metadata.md)). | Typen in `llm_specs` bzw. `promises` ergänzen, sobald eine konkrete Invariante sie verlangt — nicht vorab. |
| Findings | Die erste Fehlklassifikation ist eingetreten und eng behoben (`e6dbb08`): Protokoll-ID-Befunde tragen ihren Grad als `GateFinding`, `grade_of` liest nur das erste Wort. `code_check.code_findings` liefert weiter Text, gradiert über das führende `BLOCKER ·`/`WARNING ·`. | Beim nächsten Fehlgrad oder Wartungsproblem Grad, Stufe, Fundstelle und Nachricht als Daten bis zur CLI reichen. Gemeinsame Prüfliste beibehalten. |

### Restarbeiten aus dem Code-Audit

Kandidaten aus [Code-Audit](docs/audit-2026-10-18.md); vor Umsetzung am
aktuellen Code prüfen, keine alten Zeilennummern als offenen Befund übernehmen:

- Namen prüfen: `area: Path`, Wurzelpfade, Digest-Begriffe,
  `trace`/`timeline`, `registry`/`ledger`. Keine pauschale Umbenennung.
- Verbleibende `noqa: C901` entlang fachlicher Abläufe abbauen, wenn dort
  gearbeitet wird; nicht allein nach Dateilänge teilen.
- Der Wächter für `repo.shown` in `tests/test_one_home.py` erkennt nur die
  Bedingungsform (`is_relative_to`), keine neue `try`/`except
  ValueError`-Kopie.

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
  [Judge](docs/usability/2026-10-14-judge-minutes.md). Die `seconds`-Reihe
  auf `db1695d` ist abgeschlossen ([Bericht](docs/usability/2026-10-20-cold-probes-db1695d.md)):
  alle Zahlen gebunden, Median Count 2m44s, Judge 4m10s; Wiederholung nach
  den Werkzeugkorrekturen unten.
- **Kalte Reihe `seconds` nach den Fixes:** erledigt 2026-10-20 auf
  `22483de` ([Bericht](docs/usability/2026-10-20-cold-probes-22483de.md)):
  Fehlbedienung Count 11 → 1, Judge 2 → 0; alle Zahlen gebunden. Die
  Folgepunkte sind umgesetzt (CHANGELOG, Unreleased): Count-Stempel
  schließt seinen TOML-Block; `labkit-audit --decide`; je Probe `.tmp/`,
  festes labkit beim Stagen, Pfade außerhalb der Probe im Score. Grenze der
  Isolation: Subagents erben Umgebung und Scratchpad der Sitzung. Seit
  2026-10-21 laufen Proben in der Agent-Sandbox von `labkit-paper`
  (Container ohne Host-Mounts, Proxy mit Abo-Token, nur `/v1/messages`),
  Runner `~/projects/labkit-probes-sandbox-44db3ac/run.py`: Gegenprobe
  ohne und mit Modell bestanden, count-1 normal durchgelaufen (Hooks der
  Probe feuern erstmals). Reihe abgeschlossen 2026-10-21
  ([Bericht](docs/usability/2026-10-21-sandbox-probes-44db3ac.md)): alle
  Zahlen gebunden, kein Pfad außerhalb, Kosten gemessen (3,63 USD).
  Behoben danach: `labkit-audit` listet die gespeicherten Befunde mit der
  Nummer für `--decide` (aus dem Record) und READ-Zeilen getrennt als
  Lesehinweis (CHANGELOG, Fixed). Paket `~/projects/agentsandbox`
  herausgelöst 2026-10-21 (Commit `260370b` dort): Versuch, Proxy,
  Claude-Code-Adapter mit Einrichtungsschritt, Kosten mit
  Proxy-Gegenprüfung, Selbsttest (20 von 20 gegen die gebauten Images).
  Count-Reihe auf dem Paket 2026-10-21 ([Bericht](docs/usability/2026-10-21-sandbox-count-bcea990.md)):
  keine Fehlbedienung, `--decide` in allen drei Läufen richtig. Nächste
  Punkte nach Beleg: (a) Count-Fixture gibt jedem Fall einen eigenen
  `inputs`-Pfad, das Skelett friert nur `INPUTS` ein — Audit warnt in
  jedem Lauf; entscheiden: Skelett liest aus `INPUTS` und lehnt
  abweichende Records ab, oder die Fixture verliert das Feld. (b) Die
  Count-Ausnahme (kein Kriterium, keine Promise-Tabelle) steht in
  `promises.py` und AGENTS.md, nicht im Standard — Audit-Fehlalarm in 1
  von 3. (c) Skelett-Docstring nennt „three TODOs“, `INPUTS` ist ein
  vierter. — Alle drei behoben (`45bb0a2`); Wiederholung
  ([Bericht](docs/usability/2026-10-21-sandbox-count-45bb0a2.md)): keine
  Audit-Befunde mehr aus diesen Widersprüchen, keine Fehlbedienung.
  Entschieden 2026-10-21: `visible()` bleibt (regulär, keine Punkt-Datei,
  nicht verschachtelt); was ein Dokument ist und was nicht — etwa eine
  `~$`-Office-Sperrdatei — legt das Protokoll im Feld `Unit` fest; eine
  feste Ausschlussliste nähme diese Entscheidung vorweg. Die Warnung in
  count-3 war ein sinnvoller Befund, begründet abgelehnt. Beobachten:
  Commit vor `finalize`, Audit im Vordergrund bei `seconds`.
  Judge-Reihe auf `45bb0a2` ([Bericht](docs/usability/2026-10-21-sandbox-judge-45bb0a2.md)):
  `--decide` ohne Fehlnummer, aber die Liste geht in der Pipe verloren
  (stderr vor gepuffertem stdout, `tail` schneidet sie ab); judge-1 zahlte
  ein zweites Audit, nur um sie zu sehen. Vorschlag, zu entscheiden: Liste
  auf stdout nach dem Bericht; `labkit-audit AREA --findings` zeigt die
  Liste des neuesten Records ohne neuen Aufruf. — Umgesetzt (`a2302bc`);
  Wiederholung ([Bericht](docs/usability/2026-10-21-sandbox-judge-a2302bc.md)):
  Fehlbedienung 4 → 0, kein zweites Audit, die Liste stand in der
  gekürzten Ausgabe. Bleibt: das lange Judge-Skelett (436 Zeilen für
  sechs Stellen), Raw output vor dem Lauf in `--list`.
  Judge-Skelett geteilt (`be50b1b`, `labkit.run.lanes`); Reihe
  ([Bericht](docs/usability/2026-10-21-sandbox-judge-be50b1b.md)): gleiche
  Prüfungen und Bindung, keine Fehlbedienung, Mess-Skript 436 → 255
  Zeilen (Ziel waren ~150; weiter kürzen hieße die Formeln oder die
  Dokumentation aus dem Bereich nehmen, die das Audit lesen soll),
  Kontext 37–41k → 34–38k (auch andere Einflüsse; kein Zeit- oder
  Kostenschluss). Nächste Punkte nach Beleg: (a) das
  gestempelte `00_prepare.py` mit seinem TODO `audit()` (Audit-Befund in
  2 von 3 Läufen, nun der größere Leseanteil) — zuerst klären, welche
  fachliche Prüfung `audit()` verlangt und warum der unveränderte TODO
  Befunde erzeugt; nur streichen, wenn keine nötige Entscheidung
  verschwindet; (b) `Raw output` — erledigt: `--list` führt es unter
  „after the run — yours“, `--from-run` nennt es danach mit den
  Ausgabedateien des Laufs (schreibt es nicht: welches Paar einen Befund
  zeigt, steht in keinem Record). Ursache des `--force` in judge-2: der
  Agent füllte das Feld bei der Registrierung mit „filled after the run“.
  judge-2 hatte einen BLOCKER (Prompt „states or implies“ breiter als
  das Gold) akzeptiert, und „C1 not met“ ging durch, die Einschränkung
  nur im Audit-Record. Entschieden: Zahl und Urteil getrennt — erledigt
  (`b7802b3`): `--decide … accepted … --effect stands | "C1 not
  assessable"`, `--from-run` schreibt je akzeptiertem BLOCKER eine Zeile
  `Limit (audit <record> #N)` und „C1 not assessable with this run“ in die
  Antwort, report-check hält Protokoll und Record zusammen. Ob die
  Einschränkung fachlich reicht, prüft keine Maschine. Offen: nur
  Analyse-Records, akzeptierte BLOCKER aus Preflight-Records (minutes/
  hours) noch nicht. (a) erledigt (`df504b4`): `labkit.run.profile`,
  `00_prepare.py --audit` druckt Items und mittlere Wortzahl je Klasse,
  `MARKERS`/`CONFOUNDS` (None „not decided“, () „none applies“, ohne
  Treffer „checked, no hit“); neues Feld Data profile, bei `seconds` mit
  Modell Teil der Registrierung, also vor dem Messlauf verlangt. Reihe
  auf `07a610e` ([Bericht](docs/usability/2026-10-21-sandbox-judge-07a610e.md)):
  Profil in 3 von 3 vor dem Lauf bewertet (Marker nach Lesen der Daten
  gewählt — ein ungesehener Cue ist nicht belegt), akzeptierter BLOCKER
  in 1 von 1 als Limit-Zeile und „C1 not assessable“ im Protokoll, Raw
  output ohne Nacharbeit, Fehlbedienung 0; Kontext +3–8k. Akzeptierte
  WARNINGs: erledigt (`63d1104`) — `--effect` freiwillig, eine genannte
  Wirkung landet als Limit-Zeile und als Vermerk in der Antwort („read
  within …“); welche Wirkung, folgt aus dem, was C1 behauptet, nicht aus
  dem Schweregrad. Nicht mit kalten Proben gemessen. Beobachten (kein
  statischer Check bei zwei Fällen): Prompt breiter als das Gold („state
  or imply“) in 2 von 6 Judge-Proben, vom Audit erst nach dem Lauf
  erkannt — bei `seconds` ist das Analyse-Audit das einzige
  (LAB-017); falls es wiederkommt: prüfen, ob `code-check` vor dem Lauf
  die Prompt-Gold-Passung fragen kann.
  Zitierte Run-ID muss existieren: erledigt (`1e78f50`) — jedes Token in
  Run-ID-Form ist ein Zitat, eines ohne runlog-Format oder ohne `runs/<id>/`
  blockt (labkit-paper Bereich 08: `…T12-48-00_final` erfunden, Gates
  sahen kein Zitat). labkit-paper pinnt 0.85 — wirkt dort erst nach dem
  Umstieg auf ein neues Release.
  Erledigt: die labkit-Proben laufen auf dem Paket (Runner
  `~/projects/labkit-probes-sandbox-bcea990/run.py`). Offen als eigener
  Auftrag: labkit-paper umstellen und seine Kopie in `lib/agentsandbox`
  entfernen — bis dahin liegt der Code zweimal vor; batch, arms,
  benches, standard_check bleiben dort.
  Entschieden 2026-10-21: der allgemeine Sandbox-Code wird ein **eigenes
  Paket** `~/projects/agentsandbox` (eigenes Git-Repo, Python, Docker als
  ausdrücklich benötigte externe Laufzeit) — nicht nach labkit, damit die
  Messinfrastruktur nicht vom gemessenen Werkzeug kommt. Ins Paket: ein
  Versuch (Netze, Proxy, Container, Kopie hinein/heraus, Siegel, Manifest),
  Proxy mit Platzhalter-Token, Agenten-Adapter mit korrigierter
  Token-Zählung, Kosten je Sitzung mit Proxy-Gegenprüfung, Batch, die
  Gegenproben als Selbsttest. Draußen: Benchmarks und ihre Bewertung,
  labkit-spezifisches Stempeln, Token-Beschaffung (der Aufrufer übergibt
  ihn), das Fach-Basis-Image. labkit importiert das Paket nicht; es stempelt
  und bewertet, das Paket führt aus. Reihenfolge: erst die laufende Reihe
  abschließen und daraus den Umfang ableiten, dann herauslösen, dann die
  Nutzer (labkit-Proben, labkit-paper) je als eigenen Auftrag umstellen.
  Entschieden 2026-10-20: `runs.tsv` ist lokale Übersicht, git-ignoriert,
  `runlog reindex` stellt sie her (CHANGELOG, Changed).
  Notiert, nicht geplant: Run-Ids einer Sekunde unterscheiden sich nur im
  Zufallssuffix. Die Auswahl des antwortenden Laufs (`protocol-fill
  --from-run` ohne Run-Id, finalize: `answering_run.same_second_rival`)
  verweigert dann, statt zu raten. Feinere Startzeiten würden solche
  Verweigerungen vermeiden — spätere Verbesserung, kein Fehler.
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
| Zählvorlage aus Task-Feldern | Fable-/Sonnet-Probe benennt Stubs ebenfalls als Hindernis — **erfüllt 2026-10-20** (Count- und Judge-Agenten: ~650 Zeilen lesen für ~8 Änderungen). | `SOURCE`, `COUNT_FIELD`, `METRIC_KEY` und Ordner je Item gezielt unterstützen; nicht allein auf schwächstes Modell zuschneiden. |
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
