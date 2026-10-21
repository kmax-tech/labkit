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

**Beschlossene Richtung (2026-10-21): Maschinelle Verträge strukturiert,
fachliche Erklärung als Prosa, Ergebnisdarstellung aus gebundenen Quellen
— die Linie für 1.0.** Befund: Nur sieben Angaben des Protokolls steuern
Prüfungen (Answer-Zahlen und Run-ID, Answering run, Runs-Liste,
Modell-Alias und Arme, Prompt-Block, Gate labels, Limit-Zeilen; 27 Aufrufe
in 8 Modulen, 10 in `finalize`); 33 der 40 Felder werden nur auf
Vollständigkeit geprüft. Für die sieben trägt labkit 21 Prosa-Muster in
vier Modulen (Labels, Platzhalter, Fences, Kommentare, Schnittmarken), und
dort entstehen die Kanten jeder Probe (allein 2026-10-21: Platzhalter
mitten im Wert, Result als Key-Dump, `cost` im Kopf).

Ziel: Maschinelle Entscheidungen lesen typisierte Quellen — den
TOML-Block, die Run-Records und `audits/*.toml`, jede mit eigenem
typisiertem Validator (tomllib meldet Syntax mit Zeile, kein Schema;
`protocol_block.head` ist das Muster). Die Stufen bezeichnen Prüfungen,
keine Dateiformate: jede Prüfung behält ihre ausdrücklich bestimmte Stufe
(„erzeugter Abschnitt entspricht seinen Quellen“ ist exakt; eine fachliche
Aussage wird durch TOML nicht garantiert richtig). Die Ergebnisdarstellung wird aus diesen Quellen erzeugt, nie aus
der Prosa zurückgelesen: Answer aus `metrics.json` des Laufs in
`[result]`, Limits aus `audits/*.toml`, Prompt aus den `PROMPT`-Konstanten.
Erzeugte Abschnitte sind im Markdown abgegrenzt, und ihre Übereinstimmung
mit den Quellen wird geprüft (erzeugt == neu erzeugt); so ist das Markdown
eine Ansicht, keine zweite Wahrheit. Exakte Zahlprüfungen gelten nur
diesen erzeugten Abschnitten — ein Token-Scan über freie Prosa findet
Zahlen, kann aber Stichprobe, Schwelle und Ergebnis nicht auseinanderhalten;
freie fachliche Aussagen bleiben Gegenstand des Audits. Welche
Prosa-Felder vor einem Lauf zwingend vorliegen (Frage, Kriterium,
Zulassungsbedingung, LAB-003/-004), bleibt Entscheidung des Standards,
nicht des Formats: das Formatproblem rechtfertigt keine schwächere
Pflicht; was sinkt, ist nur die Lesung von Labels, die kein Gate mehr
steuern (Phase 5 prüft jedes Feld einzeln auf seinen Grad). Fehler
werden exakt (`[result].run fehlt`, `[model].arms.before: kein String`);
`protocol-fill` schrumpft auf `protocol-set key=value` und
`protocol-render`.

Nach außen ein zusammenhängender angekündigter Formatbruch (CHANGELOG
nennt die letzte Version, die Maschinenfelder aus der Prosa liest; keine
stückweisen Legacy-Pfade); intern in Phasen, jede mit derselben
Messlatte davor und danach. Studi-Repos pinnen und bleiben unberührt.

| Phase | Inhalt | Abnahme |
|---|---|---|
| 1 Messlatte | Heutiges Verhalten sichern: Judge- und Count-Reihe (je drei kalte Läufe) auf dem Stand nach `2f61ab0`, plus Gegenbeispiele und die lane-spezifischen Pflichten (`seconds`, `minutes`/`hours`) als Tests — richtige und gebundene Zahl, Fehlaufrufe, Gate-Ablehnungen, Zeit, Kosten | Reihe und Zwillinge liegen vor; ohne sie findet kein Bruch statt. Erfüllt 2026-10-21: mechanisch `tests/test_migration_bar.py` (Leser-Inventar, Deklaration, Lane-Pflichten, Write-back), die Reihe in `docs/usability/2026-10-21-sandbox-fb5d681.md` (sechs von sechs Zahlen richtig und gebunden, keine Gate-Ablehnung, 3,69 USD; Läufe in `~/projects/labkit-probes-sandbox-fb5d681/`). Dieselben sechs Proben laufen nach Phase 3 und nach Phase 5 erneut |
| 2 Kopplung | Gemeinsame Audit-Auswahl und Snapshot-Bildung unterhalb der Gates: `covering_analysis` (`gates/report_check.py:251`) braucht `run_shown` aus `gates/audit`, ein bloßes Verschieben nach `formats/findings` importierte nach oben — beide Fragen („welche Records decken diesen Stand?“, „was wurde dem Audit gezeigt?“) ziehen gemeinsam in eine Schicht unter den Gates; die Ergebnisübernahme (`protocol_fill.adopt`, `:483`) ruft die Freigabeprüfung weiterhin verbindlich auf und stellt bei Ablehnung den alten Inhalt wieder her — „Tool ohne Gate-Import“ ist kein Ziel. Befunde als Daten (Grad, Regel, Fundstelle, Text) bis zur CLI — neun Stellen lesen den Grad heute aus Text, die Parkbedingung ist mit `e6dbb08` erfüllt | Auswahl und Snapshot ohne Import aus `gates`; `adopt` ruft `report_check` auf (Test bleibt); kein `grade_of` auf Text außerhalb der Textquellen. Erfüllt 2026-10-21: `checks/audit_binding.py` (Run-Wahl, Snapshot, abdeckende Records; `0b9a66d`), Code-Befunde als `GateFinding` mit Grad, Fundstelle, Regel, Abhilfe (`gate.coded`), `grade_of` entfernt; Ausgabe auf den sechs Proben und einem Fehlerfall alt = neu bis auf die Regelstelle zweier Prompt-Check-Befunde |
| 3 `[result] run = "<run_id>"` | Die ausdrückliche Deklaration „berichtet“ ersetzt Answering-run-Zeile und Run-ID in der Answer; `report-check`, Stop-Hook, Pre-Commit lesen den Kopf; Answer und Limits werden daraus erzeugt | Reihe grün; `cited_runs`/`answering_run_field` ohne Prosa-Leser; Zwilling: ein Protokoll ohne `[result]` ist Exploration, kein Fehler. Umgesetzt 2026-10-21 (`9b657d4`, `515bd77`, `a49b7e6`): Leser-Inventar 12 → 8, Answering-run-Zeile aus dem Template, Breaking-Eintrag nennt 0.100.0 (`c4ed126`, `ff78d8b`). Die Reihe darauf ist gestaged in `/Users/max/projects/labkit-probes-sandbox-ff78d8b/` (Wheel 0.100.0 von `ff78d8b`, je drei judge- und count-Proben), Läufe und Scoring stehen aus |
| 4 `[model] alias, arms` und `[gate] labels` | Ersetzen das Parsen von Model / tool, Arm-Zeilen und Gate labels (`model_named_in`, `arm_findings`); die Registrierung wird strukturiert, die semantische Zuordnung bleibt beim Audit: `gate_label_scan` extrahiert Stringvergleiche als Material für den Code-Check-Agenten und urteilt nicht — daraus wird beim Formatwechsel kein harter Gleichheitstest, denn nicht jeder Stringvergleich gehört zum Labelalphabet; ein exakter Vergleich braucht einen enger bestimmten Gegenstand und korrekte Gegenbeispiele | `finalize` hält Arme gegen den Lauf aus dem Kopf; der Code-Check-Agent erhält die Labels aus dem Kopf statt aus der Prosa |
| 5 Prosa einzeln | Jedes verbliebene Prosa-Muster auf seinen notwendigen Grad prüfen: Pflichtfeld des Standards (bleibt must), Vollständigkeitshinweis (Warnung) oder entbehrlich; `protocol-fill` → `protocol-set` + `protocol-render`; Schnittmarken nur noch Template-Sache | Pre-Commit blockt auf Kopf, Lauf, Findings und die vom Standard genannten Pflichtfelder; der Rest warnt |

Bis zur Messlatte gilt ein Stabilisierungsfenster: keine neue Prüfung,
ein Release statt vieler (119 Releases in sieben Wochen, 25 an einem Tag;
312 Commits in der Woche bis 2026-10-21, davon ein Drittel Buchführung).
Die Buchführung schrumpft mit: Unreleased (819 Zeilen) in das Release,
diese Datei auf Reihenfolge und Auslösertabellen, Herleitungen in
`docs/notes/`.

**Für die übrigen Punkte ist keine neue Umsetzungsreihenfolge beschlossen.**
Die offenen Vertragsfragen und Korrektheitslücken unten sind sichtbar, aber dadurch
nicht vorgezogen.

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
| Startzeit mit Subsekunden im Record | Gleichsekunden-Sperre trifft ein Labor oder passender Formatbruch steht an. Eindeutige zeitliche Wahl im Orakel `tests/test_answering_run_exhaustive.py`; kein Altformat-Leser. Beobachtet 2026-10-21: `test_repeats` legte drei Läufe in einer Sekunde an, zwei bekamen dasselbe zufällige 4-Hex-Suffix (`uuid4().hex[:4]`, `runlog.py:372`; 1/65536 je Paar) — `FileExistsError` beim `mkdir`, der Pre-Commit wies den Commit ab, der Wiederholungslauf war grün. Das ist eine Suffix-Kollision, keine Reihenfolgeannahme des Tests; die Kur ist ein neues Suffix bei `FileExistsError` (wenige Zeilen in `Run.__init__`), kein Formatbruch. |
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
  dem Schweregrad. Reihe auf `ef6c3b1`
  ([Bericht](docs/usability/2026-10-21-sandbox-judge-ef6c3b1.md)): 3 von 3
  setzen `--effect stands` für den Signalwort-Befund, begründet aus C1
  („a threshold on these 12 items“), Vermerk in der Antwort, Fehlbedienung
  0. Aber: jede akzeptierte WARNING bekam eine Wirkung (auch „one draw“),
  die Antwort sammelt bis zu drei Vermerke — offen, ob das so bleiben
  soll. Fehler im Profil gefunden und behoben (`e3731f2`): `" so "` mit
  Leerzeichen wurde nach Komma nicht gezählt (5/6 statt 6/6).
  Ein Sammelvermerk statt je einer Notiz (`8aabde6`); Marker nur statische
  Evidenz, verlangt ist die Datenbeurteilung (`acd872e`). Abschluss-Audit
  der fertigen Antworten ([Bericht](docs/usability/2026-10-21-final-answer-audit-ef6c3b1.md)):
  das unveränderte Analyse-Audit findet den Cue wieder und benennt in
  judge-1 die offene Frage („needs an item set with near cases, a new
  experiment“); verloren geht der Befund im Result-Feld, das `--from-run`
  in 3/3 mit der Answer-Zeile (Key-Dump) füllte und kein Autor umschrieb.
  Entschieden 2026-10-21: Result schreibt der Autor (`--from-run` schreibt
  Answer und Runs), `protocol-check` hält das leere Result nach einem
  Messlauf als Pflicht. Danach eine Judge-Reihe; erst wenn der Autor-Satz
  den Befund nicht trägt: (a) ein Abschluss-Audit nach `--from-run`
  (Kosten ×2 bei seconds) oder (c) die Analyse-Anweisung um „Frage gegen
  Kriterium“ schärfen (wirkt nur indirekt, das Audit sieht die fertige
  Antwort nicht); eine dritte Effektform („C1 steht, Frage offen“) erst
  dann. Neu gefunden: Chance
  für C1-Bestehen bei N=12 ≈ 0,073 (judge-3), Prepare-Lauf ohne `data=`. Beobachten (kein
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
- `--effect stands` als Reflex: In der Reihe auf `ef6c3b1` gaben alle
  drei Agenten jedem akzeptierten Befund `stands`, auch dem „ein Zug,
  Streuung ungemessen". Trägt der Effekt noch Information, wenn nie etwas
  anderes gewählt wird? In der nächsten Judge-Reihe zählen, wie oft `not
  assessable` vorkommt; Konsequenz erst bei Befund (2026-10-21).
- Platzhalter-Erkennung (`c1dd888`): exakt sind nur die Phrasen des
  Stempels; ein vom Autor geprägtes `<…>` mitten im eigenen Satz bleibt
  unerkannt — absichtlich, weil Inhalt und Platzhalter dort nicht
  mechanisch zu trennen sind. Beobachten, ob kalte Agenten solche eigenen
  Platzhalter hinterlassen (2026-10-21).
