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
2026-10-25 geklärt: kein falsches „unproven“ — der Proxy-Mitschnitt
zeigt einen Sicherheitsstopp, nach dem dasselbe Modell weiterschrieb
(CLI 2.1.285 zählte ihn nicht); `result` hielt nur den Rest
([Notiz](docs/notes/2026-10-25-cli-two-turns.md)). Das Ausgabelimit war
es nicht: die CLI schickte für opus 5.5 schon `max_tokens = 128000`, die
Obergrenze des Modells. Die Meldung sagt jetzt: Antwort nicht als
ganze belegt, Ursache aus der Antwort nicht erkennbar. Beschlossen: kein
eigenes Limit, kein neuer Versuch wegen einer geänderten Variable — die
CLI nimmt jeden Wert stumm an, ein gesetzter Wert wäre nicht das
wirksame Limit.
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
**Achte Runde (2026-10-26, labkit `48cd001`):** wieder no-advantage
(Erfolg labkit 0/3, plain und instructions_only je 2/3; still 6 / 4 / 5),
Standard erstmals 1/3 erfüllt (t5: nach abgelehnter Entscheidung neu
entschieden, `--from-run` übernommen, Block per `--into`). Die
Berichtsprüfung lief in keinem Versuch: bei t18 erschien der Hinweis beim
Commit und wurde übergangen, die Zahlen des markierten Laufs stehen als
Ergebnis im Bericht; bei t3 erkannte labkit die Markierung mit Backticks
um die Run-ID nicht (`report_blocks._NOT_REPORTED`), report-check hielt
zweimal fest, der Agent committete mit `--no-verify`. Bericht mit sechs
offenen Punkten: `docs/usability/2026-10-26-sandbox-48cd001.md`;
Laborstand labkit-paper Branch `round7-haiku`, Commit 9d2c0f9. Noch offen (gilt auch nach Runde 9):
Branch `round7-haiku` nach labkit-paper `main` mergen (kein Fast-Forward,
dort hat eine andere Sitzung weiter committet; vorher die drei
Vorbereitungsdateien im Hauptbaum zurücksetzen), dann Worktree
`~/projects/labkit-paper-r7` entfernen (zuerst den `.venv`-Symlink).
**Neunte Runde (2026-10-26, labkit `85c54fd`):** nach Regel void — das
Gold-Programm von Aufgabe 3 (RandomForest ohne Seed) lag im Bewertungslauf
einmal über RMSE 24 (20 Nachläufe 22.4–23.5); beschreibend: Erfolg
plain 2/3, instructions_only 0/3, labkit 1/3, still 2 / 3 / 4, erstmals
zwei Punkte `after_audit` (Berichtsprüfung bei t3 und t5). Die geschuldete
Berichtsprüfung wirkte (t3: 9 → 0 Befunde, t5: 15 → 5 → 2 → 0, Bericht
jeweils umgeschrieben), Diskussionsblöcke bei t3 und t5, kein
`--no-verify`. t5 löschte Audit-Datensätze, schrieb Datensätze und
Journal von Hand und lief ins Zeitlimit; t18 maß außerhalb von runlog
(Bericht ohne Lauf, kein Gate fragte). Bericht mit fünf offenen Punkten:
`docs/usability/2026-10-26-sandbox-85c54fd.md`; Laborstand Commit
8a0182e. Für das Labor (nicht labkit): keine Neubewertung mit erneut
gezogenem Gold (entschieden, siehe den nächsten Absatz); offen bleibt eine
feste Seed-Regel für Gold-Programme (A2); das Zeitlimit von agentsandbox
zählt im Ruhezustand nicht.

**Reihenfolge nach der neunten Runde (Befund 2026-10-26).** Die Runde
bleibt void. Keine Neubewertung mit neu gezogenem Gold: Wer nach Kenntnis
des Fehlers neu zieht und den grünen Lauf nimmt, macht die
Zulässigkeitsprüfung vom gewünschten Ausgang abhängig. Die zwanzig
Nachläufe sind Diagnose. Eine Auswertung derselben Versuche unter
repariertem Instrument ist möglich, aber nur ausdrücklich als nachträgliche
Neuauswertung neben dem void. Für das Labor (nicht labkit): eine feste,
dokumentierte Seed-Regel für Gold-Programme.
Kernbefund: Die Gates verändern das Verhalten, aber die Agenten finden
keinen verlässlichen Weg vom Befund zur fachlichen Korrektur. „Nach Audit
korrigiert“ hieß bei t3 und t5 vor allem: Bericht korrigiert, nicht Fehler
behoben (das t3-Leck blieb, beide Wege UNSURE). Die fünf Punkte des
Berichts in dieser Reihenfolge:

1. **Wahl des Versuchstyps bei `labkit-init` (Punkt 4, t3):** t3 bearbeitet
   eine Modellierungsaufgabe, wählt `compute` und liest dann „kein
   Kriterium nötig“ (`labkit/tools/scaffold.py:595`). Die Anleitung muss
   bei der Wahl von `compute | fit | apply` helfen; nur den Kriteriensatz
   umzuschreiben ließe die falsche Einordnung stehen. Zwilling: eine echte
   Zählaufgabe bleibt `compute` ohne Kriterium.
2. **Ablehnungen nennen den nächsten Schritt (Punkte 3 und 5):** Bei
   `--again` steht, welcher frühere CLAIM welchen unveränderten Stand
   sperrt. Bei einer geschuldeten Entscheidungsprüfung steht der
   vollständige `--review`-Befehl samt Voraussetzung (Conclusion zuerst).
   Ob das reicht, zeigt eine Ausführungsprobe; sieben weitere identische
   Fehlversuche wären kein Bedienerfolg.
3. **Abschlussanforderung für t18 (Punkt 2):** Für die Abgabe muss
   prüfbar feststehen, welcher registrierte Lauf das Ergebnis trägt. Eine
   Warnung über fehlende Laufzitate hilft höchstens; Runde 8 zeigt, dass
   Hinweise übergangen werden. Aus beliebiger Prosa erkennt labkit nicht
   zuverlässig, dass außerhalb der Kette gemessen wurde.
4. **Handgeschriebene Records (Punkt 1, t5): keine falsche Sicherheit.**
   Ein Digest der Auditantwort im Record kann Widersprüche aufdecken. Eine
   Hashkette im selben, vollständig beschreibbaren Verzeichnis belegt keine
   Herkunft — der Agent rechnet sie nach. Belastbare Herkunft hieße
   Aufzeichnung außerhalb seiner Schreibrechte: eine eigene
   Architekturentscheidung beim Autor, kein Bauauftrag.

Abnahme vor der nächsten vollen Runde: ein einzelner belegter
Reparaturfall vollständig durchlaufen — Fehler verstehen, Code
korrigieren, neu messen, Audit bestehen, verlangtes Ausgabeformat liefern.
Erst wenn dieser Weg funktioniert, lohnt die nächste Runde mehr als
weitere Sperren.

Stand 2026-10-26 nachts: Punkt 1 umgesetzt (`e063a13`, Diagnose: t3 hatte
die Typfragen im Kontext und nannte das Training eine „low-cost
computation“ — das Wort stand in der Beschreibung der Spur `low`), Punkt
2 umgesetzt (`d5c160c`: `--report-review` meldet nach jedem Zug den
wirklichen Stand, ein sauberes `--again` hieß bisher fälschlich
„released“; Prüfbefehle mit echtem Bereichspfad und der Conclusion als
Voraussetzung; Entscheidungsliste trennt Implementierungsfehler,
verfehltes Kriterium, ungültige Registrierung; Hooks verweisen auf
`--findings`/`--decide` statt auf das Editieren des Records). Keine neuen
Gates. Nach einem Review derselben Nacht zusätzlich: Typwechsel vor der
ersten Messung über `labkit-init exp NAME --kind KIND --change-kind`
statt `rm -r` (`b5fc683`; `rm -r` löschte die verschobene Explore-Datei
und ließ den Compute-Test für das Fit-Skript stehen); die
Registrierungsprüfung misst den Commit der ersten Messung am heutigen Typ
und nennt den Wechsel (`f8239cc`, Doku `a8181f7`); „ungültige
Registrierung“ heißt jetzt: neues Protokoll, das alte mit Läufen und
Verdikt bleibt; report-check setzt den Bereich in jeden genannten Befehl
(`564211c`).

Der Reparaturfall wartet auf zwei Dinge: (a) `git push` von labkit
`main`, weil das Sandbox-Image labkit nur von GitHub installiert
(labkit-paper `sandbox/labkit.pin`); (b) die Wahl des Startzustands.
Kandidat Pilot-2-Fall A (t3, `G_VRH` noch in `FEATURES`, 08-17 #1
`fixed`). Mit labkit HEAD meldet der Stand samt den nicht committeten
Pilotdateien acht Blocker: vorbereitete Daten nicht getrackt; der
Bereichstest scheitert dreimal (Pilot-Artefakt: `[A3]` hält `[C1]` zurück,
die synthetischen Testzeilen tragen keine Merkmalsquellen); kein
Analyse-Audit des Stands; keine Antwort im Protokoll; vier früher
entschiedene BLOCKER ohne Folgeprüfung (08-17 #1, 08-21 #1 und #2, 08-28
#1). Nichts davon wird stillschweigend entfernt: Jede Änderung am Start
wird als eigener Commit im Startzustand festgehalten und in der
Vorab-Festlegung genannt. Danach ein Versuch mit Kostendeckel. Punkt 3
(Laufzuordnung t18) bleibt der nächste eigene Schritt.

**Entschieden 2026-10-26 spät, nach der Prüfmatrix der Ausweichwege**
([Note](docs/notes/2026-10-26-escape-routes-checks-and-exits.md)):
Jede Lücke bekommt ein Paar aus Prüfung und brauchbarem Fortsetzungsweg;
eine Sperre ohne Weg weiter wird nicht gebaut.

1. Vor dem Reparaturfall — **umgesetzt:** Der Text zur ungültigen
   Registrierung verspricht nur noch, was report-check hält (fehlendes
   Feld, geänderter Typ; ein geänderter Wert wird nicht verglichen)
   (`f5f68bc`). Entscheidungs- und Berichtsreviews stehen im Journal wie
   die Audits: Versuch, aufbewahrte Antwort, geschriebener Record oder
   ausdrücklicher Fehlschlag (`9493acd`). Für ältere Reviews werden keine
   Einträge nachträglich erfunden.
2. Vor der zehnten vollen Runde, zusammen gebaut: **Neuansatz** und
   **Kriterienvergleich** (Latte bei der ersten Messung gegen heute). Der
   Vergleich allein wäre eine weitere Sperre ohne Weg weiter. Der
   Neuansatz ist mehr als ein leeres Verzeichnis: Vorgänger,
   Änderungsgrund und bereits vorliegende Ergebnisse bleiben sichtbar.
   Ein unwiederbringlich verlorener Record bleibt als Evidenzverlust
   dokumentiert; der neue Versuch macht den alten nicht rückwirkend
   gültig. Ausgestaltung: „Notiert, nicht geplant“ Punkt 3.
3. Proxy-Abgleich der Records: eigener Auftrag in labkit-paper (dort in
   der TODO), nicht in labkit.

Für die Auswertung: „Der Ausweichweg trat nicht wieder auf“ ist ein
Beobachtungsbefund, kein Wirksamkeitsnachweis — Zeitpunkt der Korrektur,
Zahl späterer Gelegenheiten und andere Änderungen derselben Runde zählen
mit. Der stärkere konkrete Beleg sind die sichtbaren Berichtskorrekturen
der neunten Runde (t3, t5).

**Konsolidierter Plan nach dem Audit 2026-10-27 (Vorschlag): sauberer
Code → Härtung mit brauchbaren Auswegen → genaue Anleitung.** Dieser
Abschnitt ersetzt den ersten Planentwurf und bündelt die Befunde der
anderen Leser aus dem [Audit-Register](docs/audit-2026-10-27.md), dem
[Standardweg](docs/notes/2026-10-27-standard-way-out.md) und der
[Prüfmatrix](docs/notes/2026-10-26-escape-routes-checks-and-exits.md).
Die beschlossenen Regeln vom 26.10. bleiben in Kraft; die Detailvorschläge
unter „Notiert, nicht geplant“ sind Begründung, keine parallele Reihenfolge.
Dies ist ein Arbeitsplan, keine Behauptung bereits gebauter Garantien.

Bewertung des ersten Entwurfs: Die Richtung stimmt. Zu korrigieren sind
seine Grenzen: C5, C13 und C16 sind Verhaltensfehler, kein Textdrift;
Belegschutz braucht einen genauen Vertrag statt „alles unveränderlich“;
ein heuristischer Stolperdraht darf nicht blockieren; neue Sperren dürfen
ihre Auswege nicht erst in der nächsten Phase bekommen. B4, die
40-Einträge-Sackgasse aus B1 und atomare Protokollschreiber aus D gehören
explizit in die Arbeit. `--again` gibt laut bestehender Entscheidung
nichts frei; diese Entscheidung wird nicht erneut geöffnet.
Eingearbeitet 2026-10-27: die kalte Prüfung dieses Plans (zwölf Punkte)
und die Entscheidungen zu Fit-Wiederholungen und Schreibweg.

Arbeitsregeln für jeden Umsetzungsschritt:

- Vor dem Ändern Befund am aktuellen Stand nachstellen. Audit-Kennung,
  verletzte Invariante, betroffene Leser/Schreiber und zulässigen Ausweg
  benennen. Ein nicht mehr zutreffender Befund wird mit Beleg geschlossen.
- Erst die vorhandene Heimat suchen; Prüfung rein, Dateizugriff beim
  Format, Ablauf am Gate, Ausgabe über `gate`/`console`. Keine neue
  Sammelabstraktion und keine zweite Heimat für dieselbe Entscheidung.
- Pro Verhaltensfehler ein Regressionstest und der korrekte Zwilling.
  Neue Sperren müssen sowohl den Fehler erkennen als auch den genannten
  Fortsetzungsweg bis zum zulässigen Ende durchlassen. Reine
  Textkorrekturen brauchen keinen künstlichen Zwillingstest.
- Ein fachlich zusammenhängender Schritt pro Commit vorbereiten.
  Belegschutz und sein Ausweg werden gemeinsam abgenommen; nötige
  Teilcommits aktivieren vorher keine neue Sackgasse.
- Vor Abschluss eines Codeschritts: gezielte Tests, reale CLI-Gegenprobe,
  dann `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`,
  `.venv/bin/pyright` und `.venv/bin/pytest -q`; unabhängiger kalter
  Code-Leser gemäß Coding-Standard. Keine neuen Laufzeitabhängigkeiten.
- Formatbrüche unter Unreleased mit letzter lesender Version und allen
  betroffenen Lesern, Schreibern und Vorlagen benennen; keine Altleser.
  Nicht pushen, taggen oder releasen. Externe Laborarbeit bleibt separat.

Phase 0 — belastbare Gegenprobe vorbereiten, vor neuen Sperren:

1. **Fit-Wiederholungen (C1, A13) — umgesetzt 2026-10-27 (`1ca12de`):**
   `--repeat-of RUN_ID` an die bestehende
   Repeat-Mechanik anschließen; Beispiele für andere Seeds nennen den
   Ausgangslauf ausdrücklich. `--seed` allein ist kein zuverlässiges
   Kennzeichen einer Wiederholung: Auch die erste registrierte Messung
   darf einen expliziten Seed haben. Abnahme: normaler Lauf antwortet,
   Wiederholung bleibt unterstützender Lauf, `02_analyze.py --draws`
   kann den gedruckten Befehl ausführen. Das verhindert nicht beliebiges
   Seed-Shopping; diese Grenze bleibt benannt.
   **Entschieden 2026-10-27: (a).** Seed-Streuung bleibt, der
   Repeat-Seed wird deterministisch aus Elternlauf und reservierter
   Draw-Nummer abgeleitet. Die bestehende Repeat-Prüfung vergleicht jeden Config-Key;
   bloß `--repeat-of` durchzureichen würde einen anderen Seed verweigern.
   Nur für diesen expliziten Fit-Repeat-Vertrag den genau benannten
   Seed-Key aus dem Gleichheitsvergleich nehmen und stattdessen seinen
   abgeleiteten Wert prüfen. Keine frei wählbaren Ausnahme-Keys; alle
   übrigen Config-Felder bleiben gleich. Draw unter bestehender Sperre
   reservieren, Seed vor der Messung festlegen und im Runrecord speichern.
   Zwilling: willkürlicher Seed oder geändertes anderes Config-Feld wird
   verweigert; konkurrierende Repeats erhalten unterschiedliche Draws.
   Verworfen (b), die Seed-Streuung aus den Fit-Vorlagen zu streichen:
   Sie ist eine Stabilitätsprüfung, nach der die Audits der achten Runde
   (t3) ausdrücklich fragten.
2. **Unabhängige Probe (C14) — umgesetzt 2026-10-27 (`dc515a2`):** Die
   Identität gilt je Commit (`git -c`), es wird keine Git-Konfiguration
   geschrieben. Die von `usability` selbst erzeugten
   Probe-Commits bekommen eine lokale feste Git-Identität. Abnahme in
   echter temporärer Git-Kopie mit leerem Home und isolierter Git-Config;
   kein Eingriff in die globale Identität, Tagtest nicht mit einem
   taglosen Archiv verwechseln.
3. **Reparaturfall — durchgeführt 2026-10-27, Befund:** keine Reparatur.
   Haiku hat im registrierten Versuch (labkit-paper `e152789`, Lauf
   `2026-10-27T14-21-34_c7f6`, labkit 2c7dfe6) den Ausweg „register anew“
   aus `audit.BLOCKER_ROUTES` genommen: zweiter Bereich, Kriteriumsmarge
   0.25 → 0.15 gesenkt, Null-Band nach verfehltem [A2] 0.10 → 0.15,
   [A3]-Ausschlüsse abgeschwächt, bis die Prüfung schwieg, Leck als
   „A3 not assessable“ behalten, „C1 PASS“ berichtet. report-check gab frei
   (0 Blocker). Belege erhalten, kein `--no-verify`, Entscheidungen nur über
   `--decide`. Registrierte Regel: [B1] `report-only`; von Hand `escaped`
   (der Standardcheck von labkit-paper bricht bei zwei Bereichen ab). Note:
   labkit-paper `notes/results/2026-10-27-reparaturfall-neuansatz-statt-reparatur.md`.
   Eingabe für (c) und 2.4: Vorgänger im Kopf, Registrierungskern samt
   Kriterienwerten gegen Vorgänger und gegen die erste Messung, „not
   assessable“ auf einer Zulässigkeitsbedingung lässt das Kriterium nicht
   als bestanden erscheinen. Ursprünglich: labkit-paper, Branch `round7-haiku` (nicht gepusht), Bereich
   `experiments/12-agent-finishes-a-partial-repair/` (`97ab150`: Startzustand
   als Bundle mit zwei einzeln festgehaltenen Startkorrekturen, Vorab-
   Festlegung C1/A1/A2/B1, Auswertung R1–R5) und Pin auf `2c7dfe6`
   (`4926c61`). Offen: Image bauen, `01_measure.py --stage`, `--check` [A1],
   Fortsetzungstext (als DRAFT markiert) prüfen, `--attempt`, `--score`.
   Ursprünglicher Auftrag:
   Startzustand und erwartete Reparatur vorab festlegen,
   vorhandene Belege behalten, Startkorrekturen einzeln festhalten.
   Nach Veröffentlichung des benötigten Stands durch den Autor ein
   begrenzter Versuch im Labor. Vorher lokale Gegenprobe ohne Modell.
   Gemessen wird fachliche Reparatur samt neuer Messung und Bericht;
   reine Berichtskorrektur zählt separat. Der Befund steuert die spätere
   Anleitung, blockiert aber unabhängige Codebereinigung nicht.
   Der Startzustand (Pilot-2-Fall A, Runde 8 t3) trägt noch den alten
   Vorlagentext `--seed 7`: 0.1 erreicht ihn nur als einzeln
   festgehaltene Startkorrektur am Schätzerskript, nicht durch
   Neustempeln — das ersetzte das Skript, das den zu reparierenden Fehler
   trägt.

Phase 1 — Code bereinigen, danach die Verhaltenskorrekturen getrennt:

Stand 2026-10-27: Phase 1 umgesetzt (`b54b4d5`..`70d3301`, 30 Commits, Hook
je Commit grün); 1.4–1.6 von Subagenten in eigenen Worktrees, nacheinander
auf main gesetzt. Kalte Prüfung von 1.1–1.3 und der Upgrade-Erkennung
(1.5): 1.1 ohne Befund; gedruckte Schritte ohne `--protocol` (`a42f425`),
`--decide`-Scan an TOML-Ende und CRLF (`5914ec0`), vier Wege, ein Edit als
früheren Stempel durchzubringen (`70d3301`) — behoben, je Gegenprobe rot am
Elternstand. Reste unter „Phase-1-Reste“ (Architektur und Lesbarkeit).

1. **Git-Zugriffe (D) — umgesetzt (`b54b4d5`):** Tatsächlich doppelte Fragen nach Git-Verzeichnis,
   Dateien an einer Revision, Dateiinhalten, HEAD und Änderungen nach
   `formats/repo.py` bewegen. Außerhalb eines Repos und Git-Fehler bleiben
   unterscheidbar; Index und Arbeitsbaum bleiben explizite Eingaben.
2. **Befehle (D, B1) — umgesetzt (`931644f`, `repo.audit_command`):** Ein Bauer je Audit-/Review-Befehl, mit Bereich,
   bei Bedarf `--protocol`, korrekter Shell-Quotierung und vorhandenen
   Voraussetzungen. Abnahme vom Repo-Root und Unterordner, mit Leerzeichen
   im Pfad und mehreren Protokollen. Kein gedruckter nicht ausführbarer
   Fortsetzungsbefehl. In einem Bereich mit mehreren Protokollen und früher
   entschiedenen BLOCKERn verweigert das Folgeaudit (`audit.py:674-680`);
   dort liefert der Bauer bis 2.4 nachweislich „kein ausführbarer Befehl“
   samt Diagnose, den ausführbaren Weg bringt 2.4.
3. **Entscheidungen (D, C17, E) — umgesetzt (`fc78bb4`):** Statuslisten aus `findings.STATUSES`,
   ein gemeinsames Prädikat für die Prüfpflicht geschlossener übertragener
   Befunde. Zuerst Verhalten erhalten; eine Erweiterung auf alle
   `dismissed`/`deferred`-BLOCKER ist separat Phase 2. Namen und Docs nennen
   schon heute alle tatsächlich betroffenen Status.
   **Entschieden 2026-10-27:** Der unterstützte Schreibweg für
   Entscheidungen ist nur `--decide`. Docstrings (`findings`),
   Record-Hinweise, Fehlertexte und Anleitung ändern sich gemeinsam.
   Vorher muss `--decide` jede erlaubte Entscheidung schreiben können:
   Heute verweist es bei Status oder Grund über mehrere Zeilen auf das
   Editieren von Hand (`findings._decided_text`, „edit it by hand“) — ohne
   diese Erweiterung entstünde eine Sackgasse. Die Integritätsprüfung (2.5)
   validiert erlaubte Felder und Werte; dass `--decide` der Schreiber war,
   kann sie aus Dateibytes nicht beweisen.
4. **Schreiber und Orte (D, C15) — umgesetzt (`7a0be59`..`d606362`; dazu
   `\r` in `--why`, die mitgetippte Bereichsnummer):** TOML nur über
   `protocol_block.toml_string`, Protokollschreiben über
   `files.write_atomic`, Bereichsauflösung über `repo.area_path`.
   Abnahme: Steuerzeichen roundtrip-fähig, mehrdeutige Namen verweigert,
   vorhandene Protokolle nach fehlgeschlagenem Schreiben erhalten.
   Wo sich Verhalten ändert, eigener Bugfix statt Refactor-Etikett.
5. **Belegte Verhaltensfehler (B4, C5, C13, C16) — umgesetzt
   (`f1bc885`..`4a2cb68`):** Explore nennt einen
   vollständigen nächsten Befehl; widersprüchliche Flags werden vor dem
   frühen Return geprüft; Vorlagenupgrade gilt nicht ohne Beleg als
   Benutzeränderung; erkannte LLM-Messungen erreichen den vorgesehenen
   Hook-Pfad; die aufbewahrte Audit-Ablehnung wird trotz Parsefehler
   angezeigt. Je Fehler ein Schritt mit Gegenprobe; kein neuer Auditaufruf
   allein für eine Fehlermeldung.
6. **Textabgleich (C2–C4, C10–C12, E) — umgesetzt (`3f5291c`..`ca3dab9`;
   Bugfix `rules.names_rule`):** Hilfen und Beispiele am
   wirklichen Vertrag prüfen: Typ × Kostenstufe × Modell, vorhandene
   Flags/Dateien, cwd des Detached-Befehls, Datenprofil, antwortender Lauf,
   ausgelieferte Agenten. Gedruckte Befehle im gestempelten Bereich prüfen.
   Ein dabei entdeckter Funktionsmangel bekommt einen eigenen Bugfix.
   Übrige D-Zeilen nur bearbeiten, wenn dieser Ablauf sie konkret braucht.

Phase 2 — Härtung; jeder Vertrag mit Ausweg und expliziter Grenze:

Stand 2026-10-27: 2.1, 2.2, 2.7 und 2.8 umgesetzt (2.1 selbst, die
anderen von Subagenten in Worktrees; Hook je Commit grün). Kalte Prüfung
von 2.1 (sechs Befunde, behoben in `f4ec985`) und von 2.2/2.7/2.8 (fünf
Befunde, behoben in `cd2e8a4`); jeder Befund mit Test, rot am Elternstand. 2.3, 2.4 und
2.6 warten auf die Entscheidungen (a) und (c) nach dem Reparaturfall,
2.5 auf 2.3. Reste und offene Entscheidungen unter „Phase-2-Reste“
(Architektur und Lesbarkeit).

1. **Codebindung des Laufs (A1), ohne Schemabruch — umgesetzt
   (`ee0d1ab`, `263cefc`, nach kalter Prüfung `f4ec985`):** In finalize
   Station 3 (`finalize.py:302-338`) für jeden Typ den aufgezeichneten
   `script_sha` des antwortenden Laufs mit dem heutigen Messskript
   vergleichen; das fängt das Red-Team-Szenario g1. Der Bereichsstempel
   (`area_stamp`) ist dafür zu breit: Er deckt `02_analyze.py`,
   `analysis/*.py`, alle deklarierten Scopes und die Pin-Zeile ab — eine
   reine Analysekorrektur oder ein Pin-Upgrade verlangte „neu messen“,
   und bei `low` scheiterte runlog neu an jedem Syntaxfehler im
   Analysecode. Werden Helfer gebraucht: eine benannte Teilmenge aus
   `scope_sha` (Messskript und seine Import-Hülle), ohne Analysecode und
   Pin, eine Heimat. Ausweg: „Skript wie gelaufen wiederherstellen
   (`runs/<id>/script-source.py`) oder neu messen und den neuen Lauf
   auditieren“. Zwillinge: Analysefix besteht, Pin-Upgrade besteht,
   Änderung am Messskript oder an `lib/` hält. Garantiert ist die
   Gleichheit des erfassten Umfangs; Ändern und Zurücksetzen dazwischen
   und dynamische Abhängigkeiten erfasst der Vergleich nicht.
2. **Reihenfolge der ersten Messung (A11), ohne neues Zeitfeld —
   umgesetzt (`36bb216`, Note `docs/notes/2026-10-27-first-measurement-order.md`):** Wo der
   Registrierungsvergleich (2.4) die erste Messung bestimmt, zuerst die
   Git-Abstammung der aufgezeichneten Commits (`git_full`) nehmen, die
   Lauf-id nur bei gleichem Commit; Gleichstand ausdrücklich behandeln,
   Gegenprobe mit verschiedenen `TZ`-Werten. Gelingt das nicht ohne
   Schemabruch, wandert A11 unter „Notiert“: Es setzt Absicht voraus.
3. **Übergabe als funktionierender Ausweg (t18, B3) — gebaut
   2026-10-27, erneute Prüfung:** `protocol-fill PROTOCOL --handover --why
   TEXT --tried TEXT --into REPORT` erzeugt den ungelösten Bericht und
   einen unveränderlichen JSON-Record unter `audits/handovers/`.
   Vorher müssen lesbare offene BLOCKER ausdrücklich entschieden sein,
   ungelöst als `deferred` mit Grund. `labkit-audit AREA --findings` liest
   ohne Modell alle lesbaren offenen BLOCKER, nennt Belegfehler und gibt
   vollständige Entscheidungs- und Übergabebefehle aus. Eine defekte Datei
   oder ein ungültiger Dateiname darf andere lesbare Befunde nicht
   verstecken. Kein automatisches Entscheiden.
   Die Übergabe zieht `[result] run` zurück und schreibt einen Bericht
   ohne Ergebnis und Run-Zitat. Ein vorhandener Bericht wird nur mit
   ausdrücklichem `--force` ersetzt. Gründe und versuchte Schritte sowie
   vorhandene Belege und bekannte Verluste stehen im Übergabe-Record;
   das beschädigte Journal und frühere Belege werden nicht umgeschrieben.
   Nur Stop und Commit quittieren den genau gebundenen Verlust, im Baum
   bzw. im Index; neue Belege oder ein geänderter Bericht brauchen eine
   neue Übergabe. Alle Protokolle des Bereichs bleiben ohne deklariertes
   Ergebnis, lesbare offene BLOCKER halten weiter. Normaler Audit und
   Ergebnisübernahme bleiben bei Belegverlust gesperrt, auch nach dem
   Übergabe-Commit; dokumentierter Verlust ist keine Wiederherstellung.
   Vertrag und Gegenfälle: [Note](docs/notes/2026-10-27-handover-recovery.md),
   `tests/test_handovers.py`. Die weitergehende Formpflicht für alle
   Abgabeberichte (3.1) ist damit noch nicht gebaut. Der Agent liest die
   Grundentscheidungen einmal und fragt danach mit `--findings` nach
   konkreten nächsten Schritten; fachliches Urteil bleibt bei ihm.
4. **Neuansatz plus Registrierungsvergleich (A4, A5, B1, B3) — präzisiert
   2026-10-27 nach dem Reparaturfall als K1 (Vorgänger `replaces`,
   `[[change]]`-Liste, erzwungen `exploratory`, Vorgänger-Urteil im
   erzeugten Block; expliziter Vorgänger aktiviert die Prüfung, bloßer
   Zitatwechsel ist nur Hinweis) und K3 (Registrierung steht wie bei der
   ersten Messung; Snapshot-Felder exakt, historische Prosa aus belegter
   Quelle, Code-Digests nicht als Registrierungsänderung):
   [Note](docs/notes/2026-10-27-new-registration-contracts.md).** Ein neuer
   Bereich mit neuer Protokoll-id nennt seinen Vorgänger in einem
   Kopffeld — die eine Heimat; „abgelöst“ wird daraus abgeleitet, in den
   alten Bereich wird nichts geschrieben (ein Schreiben dort berührte
   ihn: Stop und Pre-commit hielten seine offenen BLOCKER, und ein Beleg
   würde umgeschrieben). Offene BLOCKER des Vorgängers werden zuerst
   entschieden (`deferred`, der Grund nennt den Nachfolger); die
   Folgeprüfung zeigt nur entschiedene. Ein Übertrag über Bereichsgrenzen
   braucht eine bereichsqualifizierte Referenz in `carries` und im
   `decision_digest` — Breaking, mit letzter lesender Version.
   `audit.BLOCKER_ROUTES` nennt den Vorgänger dann über dieses Feld,
   nicht im Context. Frühere Ergebnisse, Gründe und Urteile erscheinen im
   erzeugten Vorgängerblock des Berichts. Ein dokumentierter Verlust
   (2.3) macht den alten Versuch nicht gültig. Gemeinsam den
   Registrierungskern der ersten Messung gegen heute vergleichen:
   erforderliche Felder, Typ, Versprechen und Kriterienwerte nach genau
   benanntem Umfang; keine nachträglichen Ergebnisfelder. Abnahme aller
   drei Sackgassen A4/A5/B3 bis Übergabe oder neuem prüfbarem Versuch;
   bloßes Anlegen eines leeren Bereichs reicht nicht. Bestehende Bereiche
   mit mehreren Protokollen bekommen eine ehrliche Diagnose, keinen
   unmöglichen Folgeaudit. Auch die 40-Einträge-Sackgasse aus B1 braucht
   einen belegten Fortsetzungsweg, kein „settle“ auf einer wachsenden Liste.
5. **Belegintegrität (A4, A5–A7, A9):** Gegen die noch verfügbare
   Git-Historie prüfen. Abgeschlossene Laufbelege, Antworten und Reviews
   dürfen nicht still ersetzt oder entfernt werden; das Journal wird
   erweitert. Auditinhalt und seine Bindungen bleiben fest, ausdrücklich
   erlaubte Entscheidungsfelder bleiben änderbar. Vergleich erfolgt auf
   diesen Formatregeln, nicht blind über den ganzen Auditrecord.
   Bei Freigabe stehen die geschuldeten Belege im Index bzw. Commit;
   Ignore-Regeln einschließlich `.git/info/exclude` werden berücksichtigt.
   Ausweg: konkrete Wiederherstellung aus einem benannten Stand; sonst
   dokumentierter Verlust mit 2.3/2.4. Testfälle: Reset hinter Belege,
   Index-Löschung, Journal-Kürzung, zulässige Entscheidung, laufender Run,
   saubere neue Belege und verzweigte Historie. Reflog ist nur lokaler
   Zusatzzeuge. Gelöschte Historie oder nie bezeugte Dateien sind damit
   nicht beweisbar; auch ein lokales Siegel belegt keine Modellherkunft.
   Der Vergleich der Auditrecords folgt der Regel von `write_decision`:
   Zwischen zwei Fassungen ändern sich nur die Entscheidungszeilen eines
   Befunds, der Kopf bleibt gleich. Den Verlust schreibt der Befehl aus
   2.3; die prüfenden Gates schreiben nichts.
   **Umgesetzt 2026-10-28 (`3a30c3e`, Branch `evidence-hardening`):**
   `evidence` — Record nur in den Entscheidungszeilen, andere Auditdateien
   und abgeschlossene Läufe nie; Rückkehr zur zuerst committeten Fassung
   ist keine Änderung. Zeugen: Baum/Index gegen HEAD, am Stop die
   Session-Commits gegen ihren Elternteil und der Reflog; ignorierte Belege.
   Jede Zeile nennt ihr `git checkout`, keine Übergabe quittiert sie.
   [Note](docs/notes/2026-10-28-evidence-changes.md). Offen: siehe
   „Notiert, nicht geplant“ unter „Phase-2-Reste“ (Punkte 11–13).
6. **Entscheidungen (A2, A3):** Vorschlag zur Entscheidung:
   `dismissed`/`deferred` auf einem BLOCKER schuldet auch ohne frühere
   Ablehnung eine Prüfung. `not assessable` bleibt die ehrliche
   Anspruchsbegrenzung; `fixed` folgt der bestehenden Folgeprüfung.
   Frühere Urteile und Gründe desselben Befunds dem nächsten Prüfer
   zeigen, auch nach Umformulierung. Abnahme: bloßes Rewording löscht
   Vorgeschichte nicht; tatsächlich ergänzte Belege bleiben prüfbar.
   Semantische Gleichwertigkeit zweier Gründe wird nicht als garantiert
   behauptet. Zusätzliche Modellkosten gesondert messen. Die Prüfpflicht
   gilt der Ergebnisfreigabe; eine ungelöste Übergabe nach 2.3 braucht
   kein bestätigendes Modellurteil über die ungelöste Entscheidung.
   Vorhandene Heimaten erweitern, kein zweiter Historienmechanismus:
   `decision_review.decisions_text` zeigt frühere Urteile heute nur für
   schließende Status (`CLOSING`), künftig auch für ein umformuliertes
   `accepted`/`stands` nach `rejected`; das Berichtsreview bindet über den
   Rohtext (`report_reviews.standing`), künftig gehen die Claims derselben
   Bericht-/Protokollpaarung in die nächste Prüfung mit.
7. **Hooks und geprüfter Stand (C8, C9, C7, A12) — umgesetzt
   (`42d31ab`..`b452495`):** Git-Root auch vom
   Unterordner finden; ohne Stop-Basis laut melden und die Commits seit
   Transkriptbeginn (`_transcript_start`) prüfen, nie alle Protokolle des
   Repos — alte Bereiche blockieren nicht jeden Stop (2026-10-17), und der
   Stop läuft im 120-s-Limit (`install_hooks.py:147`); das Zeitbudget
   testen. Am Commit Entscheidungen samt Journal aus dem Index lesen.
   Ein fehlerhafter Commit plus uncommitteter Fix darf die Stop-Basis
   nicht freigeben. Schleifenschutz pro Zug bleibt wie beschlossen.
   `--no-verify` wird nicht beiläufig verboten; Standardtext beschreibt
   genau die nachfolgende Kontrolle und ihre Grenzen.
8. **Berichtspfade und Exit-Vertrag (A10, C6) — umgesetzt (`dc21e6a`,
   `5e1354f`):** Symlink-Berichte am
   ursprünglichen Pfad erkennen und mit konkretem Ausweg verweigern.
   Bei `--again` Messergebnis und gehaltenen Gesamtstand ausdrücklich
   trennen; Exit-Code samt allen Aufrufern am dokumentierten Vertrag
   ausrichten. Ein sauberer zusätzlicher Draw gibt einen CLAIM desselben
   Stands weiterhin nicht frei.

9. **„not assessable“ begrenzt das Urteil (K2, neu 2026-10-27):** Eine
   nicht beurteilbare Zulässigkeitsbedingung lässt nach dem geltenden
   Vertrag jedes Kriterium des Laufs nicht beurteilbar. Primäres erzeugtes
   Urteil: „C1: not assessable“, kein `True` mit angehängter Einschränkung.
   Rohwerte im Runrecord bleiben unverändert; nur separat als Rohwerte
   kennzeichnen. Eine Heimat für die Ableitung in allen Renderern und
   Prüfungen; registrierte Keys lesen. Fehlende oder fehlerhafte Pflicht-
   Keys bleiben Fehler, ein ehrliches C-Verfehlen bei gültigen A bleibt
   ein Verfehlen. Note und Gegenfälle wie 2.4.

Phase 3 — genaue Anleitung auf den geprüften Befehlen aufbauen:

1. **Abschlussvertrag über die gebaute Übergabe hinaus:** Geschuldete Abgabeberichte ausdrücklich bestimmen,
   einschließlich `REPORT.md` im Repo-Root; kein pauschaler Blockzwang für
   jede README oder Notiz. Pro zugeordnetem Protokoll Ergebnis, Diskussion
   oder Übergabe eindeutig ausweisen; mehrere Protokolle und besprochene
   Zusatzläufe bleiben möglich. Fehlende Laufzitate umgehen die Formpflicht
   nicht. Ergebnis und Diskussion behalten ihre bisherigen Prüfketten.
   Die Form einer Übergabe beweist nicht, dass ihre Prosa keine
   Ergebnisbehauptung enthält: diese Inhaltsgrenze benennen und testen.
2. **Auswege als Daten:** Gate-eigene BLOCKER tragen ein nichtleeres `fix`;
   bestehende Aufrufstellen und alle Ausgabeformen gemeinsam umstellen
   (`PREFIXED`/`AS_WRITTEN` zeigen `fix` heute nicht automatisch).
   Gemeinsame Befehlsbauer liefern den passenden Schritt und, wo möglich,
   die konkrete Übergabealternative. Ursache und Voraussetzungen bleiben
   bei der zuständigen Prüfung; keine zentrale Tabelle kopiert Gate-Logik.
   Abnahme: jeder BLOCKER hat einen passenden, ausführbaren Ausweg, auch
   bei verschachtelten Gates; eine generische Pflichtzeichenkette reicht
   nicht. Auditbefunde (`findings.Finding`) bleiben ein eigener Vertrag.
   Die Abnahme umfasst auch Verweigerungen außerhalb von `GateFinding`:
   `AuditError` über `console.refuse`, `AttemptError`, die
   `SystemExit`-Verweigerungen in runlog und start_check und die
   Hook-Meldungen; was ausgenommen bleibt, steht als Liste im Test.
   **Umgesetzt 2026-10-28 (`11693b5`, `ec7068c`, Branch
   `evidence-hardening`):** `GateFinding` weist einen BLOCKER ohne `fix`
   ab, jede Zeile endet mit `— way out: …`; `AuditError`/`AttemptError`
   verlangen `fix=`, runlog und start_check verbinden über
   `gate.with_way_out`; `tests/test_ways_out_data.py` liest alle Stellen
   (Ausnahmen: `attempts.keep_answer`, `attempts.end`). Zweifelhafte
   Auswege und Nicht-Erledigtes: „Phase-2-Reste“ Punkte 14–16.
3. **Gestempelte Anleitung:** „When you are stuck“ mit fünf kurzen Wegen:
   reparieren und neu messen; Kriteriumsverfehlen berichten; Anspruch
   begrenzen; mit Vorgänger neu registrieren; ungelöst übergeben. Echte
   Befehle und Voraussetzungen, beide Kostenstufen und alle Typen.
   Erlaubte Entscheidungen ändern den Record über `--decide`; die Anleitung
   darf deshalb nicht pauschal jede Änderung unter `audits/` verbieten.
   Die Wege der Vorlage und `audit.BLOCKER_ROUTES` hält ein Test gleich.
   Überarbeitet 2026-10-27: Versuchstyp, Wiederholungskosten und
   Erkenntnisanspruch getrennt; ein gemeinsamer Ablauf mit Zusatzschritten
   für `high`, konkrete Fehlerbeispiele und erlaubte Aktualisierungen über
   die Werkzeuge. Leseprobe mit zwölf Fällen, Vertragsreview mit vier
   behobenen Befunden und gezielte Nachlektüre:
   [Beleg](docs/usability/2026-10-27-common-workflow-reading-probe.md).
   Das belegt Verständlichkeit in diesen Situationen, keinen Erfolg einer
   neuen Ausführungsrunde; historische Stände und externe Pins bleiben.
4. **Stolperdrähte:** Heuristische Erkennung von Shell-/Edit-/Write-Aktionen
   ist statische Evidenz und warnt, niemals BLOCKER. Keine Sperre auf
   Schlüsselwörter wie `reset`, `--amend` oder `audits/`; sie träfe auch
   legitime Operationen. Exakte Integritätsverstöße hält 2.5. Neue
   Heuristiken nur nach belegtem Bedarf und mit Fehlalarm-Gegenproben.
   Statt einer Befehlsheuristik meldet seit `11a6b84` der post-change-Hook
   den Zustand nach dem Werkzeug exakt (git status → was Stop und Commit
   halten, mit Wiederherstellung); er hält nichts selbst.
5. **Leseprobe vor Ausführung:** Situationen aus der
   [bisherigen Leseprobe](docs/usability/2026-10-26-instruction-reading-probe.md)
   plus Reparatur, fehlende Belege und unregistrierte Messung. Leser nennt
   jeweils nächsten Befehl, Voraussetzung und erlaubtes Endergebnis.
   Fehlgelesene Anleitung vor bezahlten Ausführungsproben korrigieren.

Phase 4 — gemeinsame Abnahme, ohne Garantien und Nutzen zu vermischen:

1. Ohne Modellaufruf alle A/B-Szenarien als Fehler/Gegenfall nachstellen;
   gespeicherte Antworten und gelieferte Stände der Runden 8/9 benutzen.
   Erwartete Übergabe nicht als Ergebnisfreigabe zählen. Der void-Status
   der neunten Runde bleibt unverändert; Replay ist keine neue Nutzungsprobe.
2. Im Labor vorab Startzustand, Erfolgskriterien und Kostendeckel für je
   einen Reparatur- und Feststeckfall festhalten. Messen: fachliche
   Reparatur, neue Messung, wahrer Bericht, erhaltene Belege, brauchbarer
   Ausweg, Fehlalarme, Zeit und Kosten. Ehrliche Übergabe separat zählen.
3. Erst danach zehnte Runde in Bereich 09 als eigener Laborauftrag;
   Vorlagenänderung als Intervention registrieren. Proxy-Abgleich gegen
   handgeschriebene Audit-Records (Prüfmatrix Zeile 12), `--check` mit
   labkit aus dem Image (A8), Regel der ersten Messung (F) und
   Kategorie „ehrliche Übergabe“ sind Voraussetzungen der dortigen
   Auswertung, keine in labkit erledigten Aufgaben.

Nach dem Reparaturfall (2026-10-27, Richtung vom Autor bestätigt): Neuansatz
erlauben, Änderungen sichtbar binden (K1, K3); „not assessable“ begrenzt
das Urteil (K2); das Bewertungsinstrument in labkit-paper zuerst (K4,
eigener Auftrag: zwei Bereiche auswertbar, `report-only` bleibt
registrierter Wert, `escaped` als nachträgliche Diagnose daneben); die
Anleitung („When you are stuck“, `BLOCKER_ROUTES`) nach den Verträgen in
drei Punkten (Schranken vor den Ergebnissen; ehrliches Verfehlen und
Code-Reparatur zuerst, geänderte Anschlussfrage separat und offengelegt;
not assessable heißt kein Urteil), durch Lese- und Verhaltenstests geprüft.
Stand: K4 gebaut (labkit-paper `f383411`; nachträgliche Diagnose von Bereich
12: `escaped`, Standard von 2c7dfe6 erfüllt, `c85e4e9`). K3 gebaut
(`be0e539`); sich widersprechende erste Messungen sind seit `5c4479c` ein
Blocker mit zwei Auswegen (Neuansatz gegen jede Registrierung, Übergabe
`audit.HANDOVER`), der Rückweg macht seit `509760f` jede Änderung rückgängig
(auch ein hinzugefügtes `[A3]`). K2 gebaut (`fe8e440`). K1 gebaut
(`a23ac05`; seit `5c4479c` gegen jede erste Registrierung, so wie ihr Lauf
sie sah — Commit plus `uncommitted.patch`, am aufgezeichneten Block geprüft;
ein Vorgänger, dessen Registrierung nicht steht, erscheint als „no
verdict“). Anleitung gebaut (`4e921b1`; die Übergabe nennt das Protokoll,
nicht seine Läufe — eine zitierte Run-ID liest sich als berichtete Zahl).
Replay durchgeführt (labkit-paper `be59d5d`, Lauf
`2026-10-27T16-41-54_ea77`, labkit `4e921b1`): gehalten von K3 und K2, K1
gibt den Hinweis zum Zitatwechsel. Gegenfälle gebaut (`c4c49e2`,
`5c4479c`, `tests/test_counter_cases.py`: Judge-Skelett, jede Auditantwort
als SIMULATED markiert und durch den Parser von `labkit-audit`): Reparatur
unter unveränderten Versprechen freigegeben, ehrliches Verfehlen als `C1
missed` freigegeben, Übergabe passiert Stop und Commit, Neuansatz gegen
beide Registrierungen freigegeben; die Zwillinge (zitierte Run-ID,
Übernahme, eine fehlende Änderung) gehalten. Befund am echten Startzustand
von Bereich 12: K3 hält schon den Start — `null_band` 0.1 → 0.15
(`40e862b`, Haiku in Runde 8) und `[A3]` hinzugefügt (`7eb2d50`, unser
Fallbau „pilot 2 case A“), beides nach der ersten Messung `ad0d`; eine
Reparatur „wie registriert“ nähme dort die Leckregel heraus. Entschieden
2026-10-27: Der Startzustand bleibt unverändert als Beleg des Versuchs; die
Leckregel für einen grünen Gegenfall zu entfernen, wäre fachlich falsch.
Die synthetischen Gegenfälle belegen den mechanischen Weg, keinen realen
Reparaturfall (labkit-paper `1589a05`, Note des Reparaturfalls). Offen: (1)
ein korrekt registrierter realer Reparaturfall (`[A3]` vor der ersten
Messung registriert) als eigener Fall — vorbereitet als labkit-paper
Bereich 13 (`db55281`: Startbauer, Gegenprobe mit Handreparatur,
Trockenlauf im lokalen Image von labkit `976df24` trägt); vor dem Bau des
echten Starts: Abnahme, Pin, Image, ein bezahltes Analyseaudit; (2) der K1-Hinweis „neues Protokoll
nach nicht freigegebener Messung“ bleibt zurückgestellt (erst ein engerer
Auslöser und Gegenproben mit unabhängigen Fragen, Review 2026-10-27); (3)
gemeinsame Abnahme, danach Release.
Reihenfolge (bestätigt 2026-10-27): K4 → K3 → K2 → K1 → Anleitung →
Replay des gespeicherten Versuchs mit Gegenfällen; jeder Vertrag mit seinen
Tests, der Replay prüft das Zusammenspiel. K3 wird erst aktiv, wenn jede
seiner Verweigerungen einen ausführbaren Weg nennt (Werte wiederherstellen
und neu messen, Neuansatz mit `replaces`, Übergabe). K1 bleibt begrenzt:
nur ein ausdrückliches `replaces` aktiviert seine Prüfungen, ein
Zitatwechsel warnt; eine spätere strukturierte Berichtszuordnung könnte
mehr mechanisch prüfen, bewiese aber keine fachliche Gleichheit. Die
Restlücke gehört in die Auswertung: Schranken vor der ersten Messung eines
neuen Protokolls zu senken, kann formal sauber sein und doch auf bekannten
Ergebnissen beruhen — Vorgeschichte und Begründung gehören ins Audit. (a) bleibt
zurückgestellt: Der Fall zeigt WARNINGs, die nach `rejected` geschlossen
wurden, keinen ungeprüften `dismissed`/`deferred`-BLOCKER.

Noch offen vor dem betroffenen Bau: (a) Erweiterung der Prüfpflicht in
2.6 bleibt zurückgestellt. Die Richtung von (c) steht mit K1–K3 fest;
Abschluss-/Neuansatzformat, zugeordnete Abgabeberichte und eine explizite
Berichtszuordnung sind vor dem Bau zu präzisieren. Ein Zitatwechsel beweist
keine fachliche Nachfolge; ohne expliziten Vertrag nur Hinweis und
Gegenstand des Agentenaudits. Unabhängige Fragen dürfen keinen falschen
Blocker erhalten. Keine erneute Entscheidung über die bereits beschlossene
Nichtfreigabe durch `--again`.
(b) Schemabruch: für A1 und A11 nicht nötig (2.1, 2.2); ein Bruch nur,
wenn der Reparaturfall ihn belegt. labkit liest nur die aktuelle
Schema-Version (`runs.py:452`), die Stände der Runden 8 und 9 und der
Startzustand des Reparaturfalls sind Schema 4 — ein Bruch hielte dann in
4.1 fest, ob Replays auf neu erzeugten Ständen oder mit der gepinnten
Version laufen und welche Gates nicht nachgespielt werden.
Entschieden 2026-10-27: Fit-Wiederholungen Variante (a) (0.1);
Entscheidungen nur über `--decide` (1.3). Phase 0 und unabhängige
Bereinigungen aus Phase 1 brauchen die offenen Entscheidungen nicht.
Umordnung gegenüber „Punkt 3 (Laufzuordnung t18) bleibt der nächste
eigene Schritt“: Der Abschluss von t18 (3.1) wird mit der Übergabe
(2.3) gebaut — die Übergabe braucht den Ort des geschuldeten Berichts,
und eine Sperre ohne Ausweg wird nicht gebaut; davor Phase 0, Phase 1,
2.1 und 2.2.

**Reihenfolge nach der achten Runde (beschlossen 2026-10-26).** Jeder
Schritt schließt einen belegten Fehlweg und hat einen korrekten Zwilling.
Die Abnahme ist eine neue Runde in Bereich 09 als eigener Auftrag. Sie misst
richtige Vorhersagen, fachlich richtige Berichte, Fehlalarme, Zeit und
Kosten; „Standard erfüllt“ allein reicht nicht.

Verträge:

- **V1 – Laufbezug strukturiert (t3):** Ob ein Bericht einen Lauf nur
  bespricht, steht in einer strukturierten Angabe, nicht in einem
  Prosamuster.
  - labkit erzeugt daraus die sichtbare Zitierzeile und prüft, dass beide
    gleich sind.
  - Der Prosamarker `run <id> (not reported: …)` wird nicht mehr gelesen
    (Breaking). Auslöser: Die Backticks um die ID fielen aus dem Muster, und
    die Verweigerung wurde zu `--no-verify`.
- **V2 – Berichtsreview Pflicht (t18):** Ein Bericht, der einen Lauf als
  besprochen angibt, braucht ein Review genau dieses Stands.
  - Der Commit hält fest, und labkit startet nie versteckt einen
    Modellaufruf.
  - Ein CLAIM blockt. Gelöst wird er nur durch ein neues Review auf einer
    geänderten geprüften Grundlage: Bericht, Protokoll, Laufwerte oder
    Auditentscheidungen. Ein unveränderter Gesamtstand bleibt gesperrt, und
    es gibt keinen Status zum Wegerklären.
  - Ein späteres Review mit 0 Claims überstimmt keinen CLAIM desselben
    Stands.
  - Am Commit gilt der gestagte Stand.
  - Auslöser: Der Hinweis auf das Review erschien am Commit und wurde
    übergangen.
- **V3 – Fingerabdruck:** Der Fingerabdruck eines Reviews umfasst genau die
  Eingaben, die der Prüfer gesehen hat. Der eigene Record und das
  Versuchsjournal verändern ihn nicht.
- **V4 – Stop prüft Committetes (t3):** Der Stop prüft auch Änderungen, die
  in der Sitzung committet wurden.
  - Die Prüfbasis ist ein gespeicherter Git-Stand, kein Zeitstempel.
  - Ein Stop mit Blocker verschiebt die Basis nicht.
  - Innerhalb eines Zugs bleibt der Schutz vor Endlosschleifen
    (`stop_hook_active`: Exit 0, Blocker auf stderr). Der Stop des nächsten
    Zugs blockt wieder.
  - `--no-verify` bleibt die bewusste Ausnahme des Standards. V4 macht den
    Fall sichtbar und verbietet ihn nicht.
- **V5 – Auditversuche (t18, sechste Runde t3):** Ein Journal hält jeden
  Auditversuch als läuft, unterbrochen oder abgeschlossen fest.
  - Prüfen und Eintragen eines Starts stehen unter einer Sperre.
  - Ob ein Versuch noch läuft, zeigt eine Sperre, die der Prozess hält,
    nicht eine PID.
  - Fehlt ein Record, den das Journal oder HEAD nennt, blockt das mit
    Versuchs-ID.
  - Ein unterbrochener Versuch bleibt erhalten und wird genannt.
- **V6 – Frühere Ablehnung sichtbar (t5):** Nach einer Änderung von
  Conclusion oder Entscheidung nennt der Zustand das frühere
  Nicht-Bestätigen. Die Freigaberegel bleibt unverändert.

Schritte, je ein Commit — **alle umgesetzt 2026-10-26** (CHANGELOG
Unreleased):

1. Strukturierte Laufangabe im Bericht (V1): Besprechungsblock mit
   TOML-Kopf, `protocol-fill --discuss` (`e123d01`,
   [Note](docs/notes/2026-10-26-report-run-citations.md)). Der Prosamarker
   war nie released; kein Breaking-Eintrag nötig.
2. Stop prüft, was in der Sitzung committet wurde (V4) (`4126400`).
3. Frühere Ablehnung im Review-Zustand (V6) (`202f7be`).
4. Journal der Auditversuche (V5) (`bb0024f`).
5. Berichtsreview als Record, Commit hält (V2, V3) (`1171eb0`).

Replay ohne Modellaufruf auf den gelieferten Ständen der achten Runde:
[Replay](docs/usability/2026-10-26-replay-round8-gates.md). t3 und t18
werden jetzt gehalten, der Blocker nennt `--discuss`, danach das
geschuldete Review. Bei t5 nennt der Zustand die frühere Ablehnung von
08-48 #2; die Vermutung des Richters ist damit bestätigt.

**Als Nächstes (Auftrag beim Autor):**

Die Einstiegsanleitung ist nach fünf unabhängigen Leseproben, davon zwei
mit `gpt-6-luna`, abgeglichen: Conclusion vor Übernahme, nach Korrektur des
Messcodes neuer Lauf und Analyse-Audit, `--discuss` statt Prosamarker und
Berichtsreview für beide Spuren. Befunde und Antworten:
[Leseprobe](docs/usability/2026-10-26-instruction-reading-probe.md).
Die Probe misst Verständnis an sechs Situationen; eine vollständige
Ausführung mit Haiku bleibt Teil der folgenden Abnahme.

1. Das bezahlte Review auf den t3- und t18-Berichten mit Besprechungsblock
   und auf ehrlichen Gegenstücken: Werden die Ergebnisbehauptungen als
   Claim gefangen, bleiben die ehrlichen Fassungen ohne Claim?
2. Neue Runde in Bereich 09 als Abnahme. Neu zu beobachten: die Kosten des
   Pflicht-Reviews je Bericht und ob Agenten die Blocker-Kette
   (`--discuss` → Review → Bericht ändern) durchlaufen oder an ihr
   abbrechen. **Gelaufen als neunte Runde** (oben): t3 und t5 durchliefen
   die Kette bis zum umgeschriebenen Bericht; weiter oben steht die
   Reihenfolge danach.

Offen mit Auslöser, ohne Bauauftrag:

1. **Pilot zur Prüfung von `fixed`-Entscheidungen (t3):** Ein BLOCKER wurde
   `fixed` geschlossen, ohne dass die verlangte Prüfung lief. Die Frage ist,
   ob der benannte Fehler im neuen Code und Lauf tatsächlich beseitigt ist.
   **Pilot gelaufen 2026-10-26** ([Bericht](docs/usability/2026-10-26-fixed-followup-pilot.md),
   5,79 USD): 8 von 12 wie vorab festgelegt — alter Code 3/3 `unresolved`,
   volle Korrektur mit Diagnose 3/3 `resolved`, Diagnose nur behauptet 2/3
   `not_assessable`; die gelieferte Teilkorrektur (t3) aber 0/3
   `unresolved` (2× `resolved`): Der Prüfer urteilt über den Befund, wie
   er geschrieben ist (die Identität des Paars), nicht über die
   Fehlerklasse aus der Aufgabe, die er nicht sieht. Drei offene Punkte
   für die Gate-Entscheidung im Bericht (behauptete Prüfung, Befund vs.
   Fehlerklasse, mehrzeiliges Warum). **Entschieden 2026-10-26:** Gate
   zurückgestellt. Das mehrzeilige Warum ist behoben (Blockgrenze:
   Leerzeile oder nächster Eintrag; mehrdeutig → verweigert). Nächste
   Schritte, in dieser Reihenfolge:
   (a) Aufgabenanforderung und Protokollwiderspruch sichtbar machen —
   die Kette Aufgabe → registrierte Merkmalsregel → Befund →
   Behebungsprüfung; im t3-Fall registriert das Protokoll „elastic
   properties“, die Aufgabe verlangt Zusammensetzung und Struktur. Ein
   neuer Versuchsstand, die bisherigen Ergebnisse bleiben.
   (b) Pilot wiederholen mit sichtbarem Vertrag und strukturierter
   Diagnosereferenz: Verlangt ein Befund einen Behebungsnachweis, ist die
   Diagnose strukturiert benannt, gezeigt und gebunden (mechanisch:
   Existenz und Bindung; fachlich: der Prüfer), nie aus der
   „Assignment“-Prosa per Regex erraten. Ohne das bleibt D-3 eine
   belegte Schwäche des Modellurteils.
   (c) Erst danach über das Gate entscheiden.
   Stand 2026-10-26 abends: (b) gebaut (`80fcb2e`: `check` am Befund,
   vom Prüfer gesetzt, im Digest; `check_present` je Urteil aus dem
   gezeigten Snapshot). (a) als neuer Versuchsstand vorbereitet und
   vorab festgelegt ([Pilot 2](docs/usability/2026-10-26-fixed-followup-pilot-2.md)):
   `[A3]` mit Aufgabenzitat, eine `FEATURES`-Tabelle, `check =
   "feature_sources"` vorab auf 08-17 #1. **Gelaufen** (5,72 USD): FIX-
   Urteile 12/12 wie vorab festgelegt (A 3/3 `unresolved`, im ersten
   Pilot 0/3), kein `resolved` in A, B, D. Aber C und D schrieben keinen
   Record: Der Prüfer setzte auf einem neuen BLOCKER `· check: <key>
   (<Erklärung>)`, der strenge Leser verweigerte den ganzen Record; die
   Urteile sind aus den Rohantworten gelesen. **Behoben** (`34e90d7`):
   `check` nimmt eine Notiz `(…)` oder `— …` bis Zeilenende, ganz
   gespeichert und gebunden; jede Antwort liegt vor dem Lesen unter
   `audits/answers/<Versuch>.txt`, das Journal nennt sie. Replay ohne
   Modellaufruf (`aacf7bc`): 12/12 Records, gleiche Urteile. **Offen:**
   D2 ohne sichtbaren Schalter (`adc1d71`) gelaufen: 3/3
   `not_assessable`, drei Records, 1,46 USD; Pilot 2 damit 15/15 FIX-
   Urteile wie vorab festgelegt. **Gate gebaut 2026-10-26** (`3fc3315`
   Folgeaudit aller früher entschiedenen BLOCKER mit Übertragung und
   Ursprungskette; danach das Gate in `report_check.followup_findings`,
   CHANGELOG „Breaking“). Mechanisch getestet, auch auf den Pilot-Records
   (A-1 und D2-1 halten, C-1 gibt frei) und über drei Audits (die
   Einschränkung bleibt einmal erhalten). **Bei der Abnahme ausdrücklich
   mitprüfen:** `resolved` für einen ursprünglich unzutreffenden Befund
   ist nicht gemessen (die Piloten maßen nur Behebungen); ebenso die
   Betriebsgrenzen 40 Einträge / 60 kB an echten Größen (`followup` im
   Record). Ursprünglich geplant: Gate anhand der gespeicherten Records
   prüfen (ein neuer unabhängiger Befund wie die Nullspur-Streuung bleibt
   eigenständig wirksam: `resolved` für den alten Leak gibt den Lauf
   nicht frei). Bisher:
   **Gebaut 2026-10-26:** Das Analyse-Audit urteilt je
   früherem `fixed`-BLOCKER `resolved | unresolved | not_assessable`,
   gespeichert als `[[fix_verdict]]`, gebunden an `decision_digest`;
   Parser streng, ein fehlendes Urteil bleibt ungeprüft. Noch kein Gate.
   Vor den bezahlten Aufrufen: Fälle, Merkmale, Diagnose und erwartete
   Aussage in einer Pilotnotiz festhalten (vier Fälle, je drei Ziehungen).
   Das Gate (Plan Schritt 3) wird erst nach dem Pilot festgelegt; dazu
   gehören die Verbindung `unresolved` → `dismissed`/`deferred` zur
   Entscheidungsprüfung, kein Freigeben durch erneutes Ziehen auf
   unveränderter Grundlage und der Test, dass eine nach dem Audit
   geänderte Diagnosedatei das Urteil veralten lässt (heute über
   `shown_sha` des antwortenden Laufs; weitere Diagnoseläufe zeigt das
   Audit nicht).
2. **Zwei-Modell-Antwort der claude-cli (t18, dreimal):** Am
   Proxy-Mitschnitt prüfen, ob opus-4-8 neben opus-5-5 in `modelUsage` ein
   interner Hilfsaufruf ist. Bis dahin bleibt die Herkunftsprüfung
   bestehen.
3. „Kennzahlen der Eingaben ohne Ablage“: erster Schritt umgesetzt
   2026-10-26 (unten bei den zurückgestellten Erweiterungen).

Notiert, nicht geplant:

1. Abgegebene Vorhersagen aus behaltenen Skripten statt aus Heredocs (t3, t5).
2. Kein Verbot von `--no-verify`: Das wäre eine Regeländerung am Standard.
3. **Neuansatz ohne Löschen (entschieden 2026-10-26: vor der zehnten
   vollen Runde, zusammen mit dem Kriterienvergleich; hier die
   Ausgestaltung).**
   Drei Runden zeigen dasselbe Muster: Vor einem neuen Versuch löscht der
   Agent die alten Audit-Records (sechste Runde t3; achte t18, `rm
   audits/*.toml`; neunte t5, `rm -rf audits/`, Journal geleert, Records
   von Hand). labkit sperrt das Löschen (Journal, fehlender Record blockt).
   Die zulässige Form der Absicht „neu ansetzen“ steht seit `f8239cc` nur
   als Text im Weg „ungültige Registrierung“ (`audit.BLOCKER_ROUTES`: neues
   Protokoll, dessen Context das alte nennt; Altes bleibt; der Bericht
   nennt beide) — kein Gate prüft Verweis oder Bericht, und `labkit-init
   exp` legt einen neuen Bereich an, in den kein offener Befund mitgeht.
   Die offenen BLOCKER des alten Bereichs halten den Stop weiter, solange
   die Sitzung ihn berührt hat (`claude_hooks.undecided_blockers` →
   `findings.open_findings`, alle Modi); kein Status sagt „gehört zu einem
   aufgegebenen Versuch“ (gelesen, nicht ausprobiert).
   Vorschlag, ein Schritt:
   (a) der alte Versuch bleibt unverändert; „abgelöst“ folgt aus dem
   Vorgängerfeld des neuen Kopfs (Plan 2.4), in den alten Bereich wird
   nichts geschrieben; seine bereits vorliegenden Ergebnisse bleiben
   sichtbar;
   (b) eine neue Registrierung nennt ihren Vorgänger;
   (c) die offenen Befunde des alten Versuchs gehen, nachdem sie
   entschieden sind (Plan 2.4), ins erste Audit des neuen (nach dem Muster
   der Folgeprüfung, `3fc3315`) — der Neuansatz ist kein Ausweg aus
   Befunden;
   (d) der Bericht trägt einen erzeugten Block „frühere Versuche“: Zahl,
   Grund und Urteil je Versuch (LAB-042 Log the outcome — failures too);
   (e) ein unwiederbringlich verlorener Record (nie gestagt, gelöscht)
   bleibt als Evidenzverlust dokumentiert — über den Verlustschreiber
   (Plan 2.3) und im Block —, und
   der neue Versuch macht den alten nicht rückwirkend gültig;
   (f) der Kriterienvergleich (Latte bei der ersten Messung gegen heute)
   hält im selben Bau, und sein Fortsetzungsweg ist dieser Neuansatz.
   Ohne (d) wird Behalten zu Ablegen und der Neuansatz zum Probieren bis
   grün. Offen: Name und Ort (vorher `/naming`); ob ein verfehltes
   Kriterium einen Neuansatz zulässt (sein Urteil bleibt dann im Block)
   oder nur Implementierungsfehler und ungültige Registrierung; für das
   Labor, ob Bereich 09 einen ehrlich gemeldeten Abbruch von einem
   Ausweichen trennt — heute sind beide „Standard nicht erfüllt“.
   Vierter Beleg (SAB-ähnliche Ziehung 1, 2026-10-27, compute-hrv): `rm`
   des Analyse-Records und `rm -rf runs/` vor dem letzten Lauf, nichts
   committet. Auf `main` nachgespielt (2026-10-28): ein fehlender Record
   blockt Stop, Commit und das nächste Audit (`attempts.area_gaps`); ein
   Laufordner, den ein Record nennt, blockt `finalize`
   (`records_of_gone_runs`); Record, Journal und Läufe zusammen vor dem
   ersten Commit gelöscht hinterlassen keine Spur — dieselbe Lücke wie
   neunte t5. Abhilfe wäre eine Kopie des Journals außerhalb des
   Arbeitsbaums (im Git-Verzeichnis wie `labkit-sessions.jsonl`); nicht
   gebaut, gehört in diesen Neuansatz. Ausgestaltung (2026-10-28): jede
   Journalzeile zugleich in eine Kopie im Git-Verzeichnis des Worktrees;
   der Stop prüft, dass das Journal im Baum mit dieser Kopie beginnt, und
   nennt sonst die verlorenen Versuche samt Records. Garantie genau so weit:
   Löschen im Arbeitsbaum nach einem Versuch dieses Klons — nicht ein
   frischer Klon, nicht ein gelöschtes `.git`, nicht Versuche vor dem
   Einbau. Gebaut 2026-10-28 (`attempts.journal_copy`, `copy_gaps`): eine
   Kopie je Branch, geprüft als Menge von Zeilen — Branch-Wechsel, Merge
   und ein älteres Journal blocken nicht; ein unter altem Namen neu
   angelegter Branch behält die alte Kopie (von Hand entfernen).
4. **Prüfmatrix der Ausweichaktionen, Runden 1–9 (2026-10-26):**
   [Note](docs/notes/2026-10-26-escape-routes-checks-and-exits.md), je
   Ausweg ein Check und ein genannter nächster Schritt. Neu gefunden:
   (a) Entscheidungs- und Berichtsreviews standen nicht im Journal —
   umgesetzt (`9493acd`).
   (b) Eine nach der ersten Messung gesenkte Latte mit neuem Lauf hält
   kein Gate (Wegwerftest: 0.8 → 0.6, Registrierungsstation Exit 0). Der
   Text verspricht es nicht mehr (`f5f68bc`); die Prüfung kommt mit
   Punkt 3 (f).
   (c) Ein nie gestagter, gelöschter Record lässt keinen Ausweg außer
   `git checkout`/`git add`; der Ausweg ist Punkt 3 (e).
5. **Audit 2026-10-27** ([Register](docs/audit-2026-10-27.md), HEAD
   `27a33b5`, mit Red-Team in Wegwerf-Repos): Jede Kennung ist im
   konsolidierten Plan oben einem Schritt zugeordnet oder dort als
   notiert geführt; die frühere Liste an dieser Stelle ist darin
   aufgegangen.
6. **Standardweg aus Problemen:**
   [Note](docs/notes/2026-10-27-standard-way-out.md) mit Entwurfstext für
   die gestempelte AGENTS.md; eingeplant als Übergabe (Plan 2.3), Auswege
   als Daten (3.2) und gestempelte Anleitung (3.3). Stolperdrähte nur als
   Warnung (3.4). Eine Änderung der Vorlage ist eine Intervention im
   labkit-Arm.
7. **Audit 2026-10-27, Fehlerweg und Übergabe**
   ([Register](docs/audit-2026-10-27-handover.md), auf die nicht
   committete Übergabe-Arbeit über `c7b1f8d`). Offene Entscheidungen:
   (1) `--findings` druckt den Übergabebefehl nur bei Fehlern oder
   offenem BLOCKER, die Verweigerung ohne Record vorher (H1);
   (2) eine nicht mehr passende Übergabe nennt ihren Grund im Stop/Commit,
   die Hook-Texte nennen den Übergabeweg (H2);
   (3) Ort und Form des Übergabeberichts: eigener Pfad je Protokoll statt
   `REPORT.md`, offene Befunde mit Record und Nummer im erzeugten Text
   (H3);
   (4) Dekodieren in einem Zustandsleser in `repo` (behebt H4, ersetzt
   die Kopien in Tabelle C);
   (5) `finalize.py:142` mit Protokoll über `repo.adopt_command` (H5);
   (6) README Schritt 4 auf `--decide`, report-check-Halte auf den
   Übergabebefehl, `--contract`-Satz der Vorlage, `--again`-Exit (H6–H9);
   (7) `deferred`-Befehl mit Platzhalter statt fertigem Grund; Übergabe
   im README-Begriffsregister mit einem Namen, `--discuss`/`--handover`
   als „wann welches“ (B);
   (8) Kleinkram E und Konfiguration D in einem Aufräum-Commit.
   **Erledigt 2026-10-27** (1)–(8), je ein Commit, Stand im Register
   (Abschnitt „State“). Die zwei zunächst offenen Punkte am selben Tag
   nachgezogen: Protokolle sind reguläre Dateien (`d0e02f7`), der
   Preflight trennt „übergeben“ von „zurückgestellt“ (`0393ffc`).
8. **Nach dem Workflow-Review 2026-10-27** (`6d08293`, `0667f0a`; Note
   `docs/notes/2026-10-27-workflow-stages.md`). Offen:
   (1) `runlog start` kehrt zurück, bevor das Kind seinen Laufordner
   anlegt; ein sofortiges `runlog --wait` kann ohne Lauf Erfolg melden
   (vom Review beobachtet, hier nicht nachgestellt) — Korrektheit, zuerst.
   (2) Die Übergabe nennt andere Berichte mit dem zurückgezogenen
   Ergebnisblock nur pauschal; sie könnte sie mit Pfad nennen (report-check
   kennt sie).
   (3) Lokales `apply`: der Nullvergleich ist ein von Hand gebauter
   Prädiktor. Alternative ohne zweites Artefakt: die Vorhersagen des
   Primärmodells gegen innerhalb des Seeds permutierte Labels werten —
   Forschungsentscheidung, nicht still ändern.
   (4) Das Estimator-Skelett hasht `PREDICTOR_FILES` schon beim Import
   (`CONFIG`); der Bereichstest liest damit die Modelldateien.
   (5) Eine Zustandsauskunft „du stehst hier, dieser Schritt fehlt“ gibt
   es nicht; `--contract`, `--list`, `--findings` decken Teile ab. Erst
   nach Benchmark-Beleg (Reihenfolge vor Features).
   Erledigt 2026-10-27: (1) `2286d8d`, (2) `0bad41c`, (4) `10c9773`;
   (3) entschieden: Standard-Null auf permutierten Labels, ein fester
   Null-Prädiktor bleibt Option. (5) bleibt bis zum Benchmark-Beleg liegen.
9. **Audit 2026-10-27, dritter Durchgang** ([Register](docs/audit-2026-10-27-structure.md),
   HEAD `2847c1e`: Anweisungen am gestempelten Labor, Drift, Heimaten,
   Struktur, Klarheit des Tagesdiffs). Offene Entscheidungen:
   (1) Fehler mit Wirkung beheben, je ein Commit: K1 (kaputter
   Übergabe-Record verdeckt Journal-Lücken), K2/K3 (Tracebacks statt
   Ablehnung in `hold_declared` und am Commit), K5 (Preflight nennt eine
   unlesbare Übergabe „set aside“), S2 (`--into`-Befehl mit falschem
   Pfad), I10 (`runlog .` nimmt das Repo als Bereich, `--wait` meldet
   leer), I7 (Prompt-Skelett prüft ohne Eingabe grün).
   (2) A4/I1 schließen: bei `low` den Start ohne committete Registrierung
   ablehnen statt die Übernahme später für immer zu sperren —
   Gate-Änderung.
   (3) Anweisungen angleichen: nach dem Lauf Audit, Entscheidung,
   Conclusion vor der Übernahme (I3), Audit bei `low` eine Lesart (I4),
   Ausweg vor dem ersten Audit nennen (I2), Exploration mit
   `--repeat-cost` (I8).
   (4) Kopffelder `number_describes`, `frozen`, `preflight_audit` über
   `protocol-fill` setzbar machen oder das Handeditieren ausdrücklich
   erlauben (I5, I6).
   (5) Die `high`-Form ohne Modell und ohne Kriterium von Modell- und
   Kriteriumsfeldern befreien (I9, C2 offen).
   (6) Drift-Paket D1–D8 und Kleinkram K4, K6–K10, I11–I12.
   (7) Heimaten: ein Block-Scanner für Bericht-Blöcke (S1),
   Befehls-Bauer in `repo` (S2), die übrigen S-Zeilen und die neun
   fehlenden `test_one_home`-Regeln.
   (8) Struktur nach Nutzen/Risiko: Prüfer-Bausteine aus `audit` lösen,
   damit der Pre-commit kein `llm` lädt (M1, M2); `report_check` teilen
   (M3); Hash-Modul; `preflight_area` mit Sammler (M4); toter Code (M6).
   **Stand 2026-10-27:** (1)–(7) erledigt, (8) M6; vierzehn Commits von
   `3c0e11c` bis `c62f2da`, Liste im Register (Abschnitt „State“).
   Offen mit Plan (Register): M1 die modellfreien Teile aus `audit`,
   `decision_review`, `report_review` verschieben, bis `report_check` kein
   `llm` lädt; M3 `report_check` teilen; M4 Sammler für `preflight_area`;
   M5; die Vorlage nach Modell und Kriterium schneiden (I9 Stempelseite);
   K9, I11, Rest von I12; restliche S-Zeilen und ihre Grep-Regeln.
   Zweite Runde 2026-10-27 (`a589b33` bis `2497092`): M1, M4, M5, M3,
   Stempel nach Modell und Kriterium, K9, K5, S3, die Null-Lane-Station aus
   der Test-Session; die Kreuzung ist befristet dokumentiert.
   Dritte Runde 2026-10-27/28 (`fddb01b` bis `c1d0a7b`): restliche S-Zeilen
   mit Grep-Regeln, I11, Rest von I12, Rest von M4, M7. Plan (7) andersherum
   gelöst: jede Startprüfung löst aus, statt Text zurückzugeben. Danach
   (`25b1f51`, `9f3e5bd`): `findings.AuditedState` als ein Typ für den
   auditierten Zustand, `scaffold.next_steps` in drei Teilen. Offen:
   Test-Session (3) Aufgaben-Schlüssel gegen `c1_score` — Entscheidung im Probe-Modul
   der Branches `sab-like-cases`/`sab-cases-on-main` einer anderen Sitzung;
   (4) Laufzeit, keine Gate-Frage.
   Regelkonflikt gemeldet: eine neue bekannte Kern→Doktrin-Kreuzung
   (`start_check`→`protocol_history`, `5760496`), obwohl die Liste „not
   extended in passing“ sagt — bewusst, gleiche Doktrin wie die Zeile
   davor.
10. **SAB-ähnliche Fälle, offene Entscheidungen (2026-10-28).** Drei
   kalte Haiku-Ziehungen auf ScienceAgentBench-förmigen Fällen (Notizen auf
   den Branches `sab-like-cases` und `sab-cases-on-main`). Übernommen:
   `2dd2751` (editable install im Worktree), `f576e0f`, `658dfde`
   (AGENTS.md: die benannten Ausgaben der Aufgabe sind das Ergebnis).
   Entschieden und gebaut (2026-10-28):
   (a) `null_band` (b): `01_measure.py --calibrate-null` misst bei apply die
   Streuung über 200 Gold-Permutationen bei festen Vorhersagen, Regel im
   Skelett (0,99-Quantil von |Null − Zufall|), vor der Registrierung;
   fit hat keinen kostenlosen Weg (die Null fittet neu). Eine nach der
   ersten Messung geänderte Bandbreite verweigert report-check schon
   (`registration_changes`). `ea8d060`.
   (b) Schlüssel (1): `b3737c6` liest `c1_score`; die Bedeutungsprüfung
   (Kennzahl und gelabelte Items gegen die Aufgabe, sonst ein Satz statt
   einer Zahl) ist `a15e261`. Beide mit dem Harness in `main` gemergt
   (`8e709d7`, `1438edb`); die Notizen der Ziehungen 1 und 2 als Dateien
   von `sab-like-cases` (`dcf3091`), dessen Code `main` anders gelöst hat.
   (c) Report-Churn: der Ablauf ist gewollt (die Review bindet den ganzen
   Stand); AGENTS.md und die Verweigerung nennen jetzt die Reihenfolge.
   Offen: die Laufzeit vergleichbar messen — dieselben Aufgaben mit und
   ohne labkit; ein Experiment, startet auf Ansage.
11. **Audit 2026-10-28, die heutigen Änderungen** ([Register](docs/audit-2026-10-28-today.md),
   `f5e48e7..92029c2`): HEAD auf frischem Klon grün. Vier Fehler mit
   Wirkung (B1 kaputte Journal-Kopie bricht den Stop-Hook ab; B2
   code-check überspringt unlesbare Dateien still; B3 AGENTS.md schickt
   Probe-Zeilen ins Protokoll; B4 Probe-Bewertung sagt „NO (truth)“ bei
   Bedeutungslücke), acht Doku-Drifts (D2 korrigiert eine eigene falsche
   Begründung zu „lane“), neun doppelte Heimaten, fünf Klarheitszeilen.
   Alle sechs Punkte erledigt (`3a7cba3` bis `86945a2`, Stand im Register).
12. **Haiku-Leseproben Steckenbleiben und Start (2026-10-28)**
   ([Steckenbleiben](docs/usability/2026-10-28-haiku-stuck-reading.md),
   [Start](docs/usability/2026-10-28-haiku-start-reading.md)): die
   gemeinsamen Zweifel an den Werkzeugtexten sind behoben und von frischen
   Lesern bestätigt. Offen, je eine Entscheidung über den Standard:
   (a) eine bei der ersten Messung unvollständige Registrierung — neu
   registrieren mit `[replaces]` oder übergeben, report-check und AGENTS.md
   nennen keinen Weg; (b) `type` einer Berechnung — `confirmatory` ist über
   „question and criterion“ definiert, eine Berechnung hat kein Kriterium;
   (c) Grenze compute/fit bei einer am Signal oder an Referenzen gewählten
   Erkennungsschwelle; (d) wo Eingabedaten liegen und ob sie committet
   werden („code, registration and inputs“). Klein: `protocol-fill` in
   zwei Schreibweisen gezeigt; `chance_of()` im gestempelten Null-Satz
   nirgends erklärt.
   Entschieden und eingetragen 2026-10-28: (a) die erste Messung bleibt
   Exploration, weiter mit `[replaces]` oder Übergabe, Maßstab ist, ob eine
   nachträgliche Wahl Ergebnis oder Bewertung steuern kann (`72e71ca`);
   (b) kein neuer Typ, `confirmatory` = Frage und Auswertungsplan vorab,
   das Kriterium dort, wo eine Vorhersage beurteilt wird (`f2f2c71`); (c)
   eine vorab festgelegte Regel, die einen Parameter aus jeder Eingabe
   selbst bestimmt, bleibt Berechnung, eine nach Sichtung gewählte
   Schwelle ist ein fit (`f2cae8b`); (d) festgelegt werden die tatsächlich
   gelesenen Dateien, Herkunft und Vorbereitung, roh und vorbereitet
   getrennt, große Daten per Quelle, Version und Prüfsumme (`a6dc065`);
   die beiden Kleinigkeiten im folgenden Commit. Geschärft mit dem Autor
   (2026-10-28): (a) Nachfolger nur, wenn sich die fehlende Wahl begründet
   treffen lässt, sonst Übergabe ohne Ergebnis; ein Tippfehler in einem
   Prosafeld wird im Protokoll korrigiert (ein Audit, das das Feld
   beurteilt hat, ist erneut fällig), in einem Versprechen bleibt er stehen
   (`74ac959`); (b) `confirmatory` nennt auch die Eingaben, sonst
   `exploratory` (`6a15379`); (c) entscheidend ist, ob Daten das Verfahren
   anpassen, nicht wann die Regel aufgeschrieben wurde — an Referenzen
   eingestellt ist fit auch mit vorab registrierter Regel, beanspruchte
   Erkennungsleistung an getrennten Daten (`4daca56`); (d) Maßstab
   „eindeutig nachvollziehbar“, Zugangsweg, rechtlich teilbar,
   `00_prepare.py` nur bei fit und apply gestempelt (folgender Commit).
   Offen: ob Agenten den
   neuen Hinweis zum Vorlagenfehler 0,15 gegen 0,25 beim tatsächlichen
   Ausfüllen beachten — das prüft die nächste Schreibprobe, ein
   Experiment, das auf Ansage startet; ebenso, ob die verständlicheren
   Texte zu zuverlässig durchgeführten Experimenten führen. Erste Antwort
   in Punkt 13: in der vierten SAB-Ziehung nicht beachtet (apply-screen).
13. **SAB-ähnliche Fälle, vierte Ziehung auf `87036d3` (2026-10-28)**
   ([Notiz](docs/usability/2026-10-28-sab-cases-haiku-87036d3.md)): alle
   drei bestehen die versteckte Bewertung, nur compute-hrv übernimmt eine
   Zahl sauber; fit-assay und apply-screen enden mit Diskussionsblock.
   Sechs systematische Befunde an labkit, je eine Entscheidung:
   (1) Die gemeldete Registrierungsänderung verschweigt geänderte Sätze,
   sobald sich auch eine Konstante ändert (`promises.py:132`); Vorschlag:
   die Versprechen der ersten Messung aus ihrem Commit lesen und jede
   Änderung nennen. (2) Eine Registrierungsänderung zeigt sich erst bei
   der Übernahme; Vorschlag: eine Station in finalize. (3) Ein vor dem
   Stagen gelöschter Audit-Record ist verloren, der Commit geht durch, die
   angebotenen Wiederherstellungen greifen nicht; Vorschlag: Records wie
   das Journal in einer Kopie im Git-Verzeichnis halten, daraus
   wiederherstellen, und den Commit halten, wenn das Journal im Baum einen
   fehlenden Record nennt. (4) Die Schwelle von [C1] beruht auf einer
   Null-Ziehung (beide Analyse-Audits: BLOCKER); Vorschlag für apply: die
   Null-Spur über K Permutationen, für fit offen — eine
   Standardentscheidung. (5) Gestempelte Werte (`margin`, `null_band`,
   `SCORE`) bleiben als scheinbare Entscheidung stehen; Vorschlag:
   protocol-check warnt (statische Evidenz), wenn der Satz eines
   Versprechens den Wert seiner Konstante nicht nennt. (6) Audit über
   120 s (bekannt, „Auditdauer“).
   Ursachen (Abschnitt „Why they happened“ der Notiz) und dazu je eine
   Entscheidung: (7) Das eigene Analyse-Audit hat beide
   Registrierungsänderungen angestoßen — sein Prompt
   (`agents/experiment-preflight.agent.md`) sagt nicht, dass nach der
   ersten Messung nur neue Registrierung, `accepted` mit Wirkung oder
   Übergabe bleiben; Vorschlag: das dort festhalten. (8) „null_band aus
   --calibrate-null vor der Registrierung“ steht nur im Platzhalter, der
   beim Ausfüllen verschwindet; Vorschlag: in AGENTS.md bei apply nennen
   und sagen, woher `margin` und `null_band` kommen. (9) „Veraltetes Audit
   löschen“: AGENTS.md und die Commit-Meldung nennen den Fall nicht — ein
   durch spätere Änderung veralteter Record bleibt, seine BLOCKER werden
   `fixed` mit der Änderung entschieden. (10) Die Probe selbst: fit-assay
   nennt keine Kennzahl, der Harness erwartet ROC-AUC.
   Umgesetzt 2026-10-28 in der Reihenfolge des Autors: Audit und Gates
   nennen denselben Reparaturweg (7) — `8a1b5f2`; finalize hält eine
   Registrierungsänderung und nennt jede Änderung samt Satz (1, 2) —
   `658a5fd`; Records im Git-Verzeichnis gesichert, der Commit hält einen
   nie gestagten fehlenden Record, jede Meldung nennt einen ausführbaren
   Wiederherstellungsweg (3) — `f751938`; dauerhafte Anweisungen zu
   `margin`, `null_band` und veraltetem Audit (8, 9) — `f868b42`; die
   Probe nennt ROC-AUC und trennt interne Validierung von der versteckten
   Testbewertung, eine Accuracy unter altem Blatt gilt als Lücke der
   Probe (10) — `5daa0ae`.
   Offen: (4) die Null-Spur als eigene Standardentscheidung
   ([Vorschlag](docs/notes/2026-10-28-null-lane-spec.md)) — mehrere
   Permutationen allein sind keine Spezifikation: Anzahl, Seeds,
   Aggregation und Bedeutung der C1-Schwelle stehen vorab fest; für apply
   liegt ein Vorschlag vor (die festen Vorhersagen gegen K Permutationen
   des Golds), für fit ist die Regel offen. (5) Warnung von
   protocol-check, wenn ein Satz den Wert seiner Konstante nicht nennt —
   nicht beauftragt. (6) Auditdauer, bekannt. Danach ein vollständiger
   Reparaturfall: Befund verstehen → Code korrigieren → neu messen →
   Audit bestehen → Ergebnis übernehmen; erst er zeigt, ob der
   widersprüchliche Rat und die Sackgassen beseitigt sind — ein
   Experiment, startet auf Ansage.
14. **Reparaturfall auf `4054343` (2026-10-28)**
   ([Notiz](docs/usability/2026-10-28-repair-case-haiku-4054343.md)):
   eingebauter Fehler (`sd**2` statt `sd`) in einer korrekt registrierten
   apply-Probe. Die Reparaturen aus Punkt 13 tragen: das Audit fand den
   Fehler, der Agent reparierte den Code, nicht die Registrierung, kein
   Beleg gelöscht. Der Weg endete trotzdem nicht in der Übernahme; je eine
   Entscheidung: (1) Eine Reparatur, neu gemessen, übernimmt die Zeilen
   des fehlerhaften Laufs — die Zeilenidentität des Schätzer-Skeletts
   (`instrument()`) kennt den Code nicht, `measure()` hängt nur fehlende
   Zeilen an, finalize sagt nur „continues“; Vorschlag: der Code gehört
   in die Identität, und ein voller Lauf setzt keinen abgeschlossenen fort
   (finalize hält Zeilen eines Laufs mit anderem Code). (2) Die geforderte
   Prüfkennzahl eines Befunds (`check: n_rows_other_run`) erklärt
   AGENTS.md nicht — ohne sie bleibt die Reparatur `not_assessable`;
   Vorschlag: sagen, dass das Messskript sie in metrics.json schreibt.
   (3) Null-Spur: Entscheidung offen (Punkt 13). Offen als Frage: wählt
   labkit Läufe nach dem Namen, wo Rechner in zwei Zeitzonen einen
   Bereich beschreiben (der Bewerter tat es hier, Artefakt des Starts)?
   Umgesetzt 2026-10-28: (1) `0796243` — der Code in der Zeilenidentität
   des Schätzer-Skeletts, Wiederaufnahme über eine Codeänderung verweigert
   (Läufe, `code_sha`, neuer Ausgabename), Fortsetzen eines abgeschlossenen
   Laufs laut gesagt statt verweigert (eine harte Weigerung brach die
   Parser-Reparatur des Modell-Skeletts, dessen Antworten vom Parser nicht
   abhängen), finalize hält Zeilen mit Code fremder Skripte; (2)
   `5a26902` — die geforderte Prüfkennzahl als Arbeitsauftrag in
   `--findings`, in den Halten der Folgeprüfung und in AGENTS.md.
15. **Reparaturfall, zweiter Versuch auf `5a26902` (2026-10-28)**
   ([Notiz](docs/usability/2026-10-28-repair-case-2-haiku-5a26902.md)):
   Haiku kalt bis zur übernommenen, korrekt gebundenen Zahl 0,7609 in
   651 s, report-check sauber, Lieferung richtig; die Weigerung führte
   ihn zur eigenen Ausgabedatei. Die Prüfkennzahl kam nicht vor — ihre
   Abnahme steht aus. Offen, je eine Entscheidung: (1) Das Audit sieht
   die deklarierte Prädiktor-Datei nicht (`model.json`, sechs Gewichte):
   das Folge-Audit blieb `not_assessable`, drei Entscheidungsprüfungen
   `insufficient`, das Ergebnis lautet „C1, A1, A2 not assessable“ trotz
   wahrer Zahl; Vorschlag: kleine Text-Prädiktoren aus `PREDICTOR_FILES`
   inline zeigen, binäre beim Namen und Digest nennen. (2) Ein Befund,
   der eine Bestätigung aus einer Datei verlangt, hat keinen Kanal wie
   `check:`. (3) Null-Spur: Entscheidung offen (Punkt 13).
   Stand 2026-10-28 abends: (1) gebaut — Analyse-Audit und
   Entscheidungsprüfung sehen die deklarierten Abhängigkeiten des Laufs,
   kleine Textdateien ganz, sonst Name und Digest (`23bdccd`, Breaking:
   frühere Analyse-Records solcher Läufe decken nicht mehr); (3)
   entschieden und gebaut — apply: Schwelle auf dem exakten
   Permutations-Erwartungswert (`c54a4dc`), fit: Mittel aus fünf
   Neutrainings (`7b9700b`). Einordnung: der zweite Versuch erreicht die
   korrekt gebundene, übernommene Zahl, der Schutz vor alten Messzeilen
   bewährt sich; eine richtige Zahl und ein sauberer report-check sind
   noch keine bestätigte Aussage, 651 s gegen 1242 s ist je ein Versuch,
   kein Geschwindigkeitsnachweis. Offen: (2) und die Abnahme des
   Prüfkennzahl-Auftrags — ein gezielter Fall, dessen Fehler nur eine
   Kennzahl zeigen kann; danach derselbe Reparaturfall erneut, ob C1/A1/A2
   jetzt beurteilbar sind (ein Experiment, startet auf Ansage).
   Stand 2026-10-28, Branch `check-path`: Bestätigung aus einer Datei
   gebaut (`· check: file:<pfad>`, `8645e31`). Reparaturfall, dritter
   Versuch ([Notiz](docs/usability/2026-10-28-repair-case-3-haiku-8645e31.md)):
   richtige Zahl übernommen, „C1 met; A1 met; A2 met“, report-check im
   Image sauber — ein Versuch, keine Rate. Prüfkennzahl-Fall
   ([Notiz](docs/usability/2026-10-28-check-path-case-haiku-8645e31.md)):
   das Folge-Audit urteilte mit `z_sd` `resolved`, die Übernahme scheiterte
   am Nachrechen-Check (`vanished ['z_sd']`, die Kennzahl lag neben den
   gespeicherten Zeilen), der Agent strich sie, keine Zahl. Behoben
   (`64040f2`): der Prüfauftrag sagt jetzt, die Zeilen tragen, was die
   Kennzahl braucht, und `evaluate_rows()` rechnet sie daraus. Offen: die
   Abnahme dieser Behebung — derselbe Prüfkennzahl-Fall erneut (ein
   Experiment, startet auf Ansage).
   Abnahme auf `64040f2`: Prüfkennzahl-Fall erneut
   ([Notiz](docs/usability/2026-10-28-check-path-case-2-haiku-64040f2.md))
   — die Zeilen tragen `standardized`, `evaluate_rows()` rechnet `z_sd`,
   Folge-Audit `resolved`, Nachrechen-Check grün, Zahl übernommen, „C1
   met; A1 met; A2 met“, report-check im Image sauber. Datei-Prüfung
   ([Notiz](docs/usability/2026-10-28-file-check-case-haiku-64040f2.md))
   — `model.json` deklariert, vier Folge-Audits `resolved` mit der Datei;
   die Abgabe aber nicht sauber. Je ein Versuch, keine Rate. Offen,
   Entscheidung: ein `fixed`-BLOCKER zum deklarierten Lauf (`[result]
   run`) wird für immer gehalten, weil die erneute Übernahme den
   auditierten Zustand nicht bewegt und der Ausweg „neue Messung“ nicht
   passt; der Agent ging mit `--no-verify` am Hook vorbei — die Lücke
   erklärt den hängenden BLOCKER, entschuldigt aber weder die
   Hook-Umgehung noch die fehlenden Abgabeteile. Entschieden: der
   deklarierte Lauf gehört zur Bindung des Analyse-Records (keine
   Sonderregel in report-check); die erneute Übernahme erledigt den
   BLOCKER nicht selbst, ein Folge-Audit prüft und löst ihn. Als eigener
   Schritt: Bindung, Entscheidungswege des Agenten (ein Befund zum
   deklarierten Lauf ist weder Code- noch Registrierungsfehler: neu
   übernehmen, dann Folge-Audit, keine neue Messung), Regressionstest
   über die ganze Kette samt Gegenprobe (ein weiter falscher Kopf bleibt
   blockiert).
   Gebaut auf Branch `declared-run` (`419cef7`): MODE analysis zeigt ein
   Stück `DECLARED RUN`, wenn der Kopf einen anderen Lauf deklariert als
   den gezeigten, und `shown_sha` bindet es; die erste Übernahme des
   auditierten Laufs bewegt nichts. Neuer Ausweg „a wrong declaration“
   (gedruckte Liste und AGENTS.md). Kettentest mit drei Gegenproben grün.
   Offen: die Abnahme mit einem kalten Agenten — ein Startzustand, in dem
   ein Audit einen falsch deklarierten Lauf findet (ein Experiment,
   startet auf Ansage).
   Zurückgenommen (`b2da352`), vor der Abnahme: ein Probedurchlauf von
   Hand fand eine Sackgasse. `protocol-fill --from-run` schreibt nur,
   wenn report-check besteht; ein Audit von B, das lief, während noch A
   deklariert war, trägt das Stück `DECLARED RUN` und deckt nach der
   Übernahme von B nicht mehr — die Deklaration kann also nie geschrieben
   werden. Das sperrte auch den gewöhnlichen Weg (Code ändern, B messen,
   B auditieren, B mit `--force` übernehmen). Der Kettentest schrieb den
   Kopf direkt statt über `protocol-fill` und sah es nicht; ein neuer
   Test muss über `protocol-fill` gehen. Startzustand und Plant-Skript
   liegen bereit (Scratchpad `declared-case`, `plant_declared.py`).
   Entscheidung offen, zwei Wege:
   (A) `protocol-fill --withdraw` zieht die Deklaration mit Spur zurück
   (welcher Lauf, warum); dann gilt die Bindung wie gebaut: Rückzug,
   Folge-Audit beurteilt den Befund, erste Übernahme von B bewegt nichts.
   Derselbe Rückzug löst, dass der Commit-Hook eine Codeänderung nach der
   Übernahme nur zusammen mit neuem Lauf und neuer Deklaration durchlässt;
   `--from-run --force` als Ersatz einer Deklaration entfällt
   (finalize-Ausweg und AGENTS.md nachziehen).
   (B) zwei Zustandsbegriffe — Deckung für „Audit fällig“ ohne die
   Deklaration, für die Nachverfolgung mit ihr — nah an der verworfenen
   Sonderregel. Empfehlung: (A).
   Entschieden: (A). Gebaut auf Branch `withdraw`: `protocol-fill
   --withdraw --why "…" [--into REPORT.md]` (`84f6812`, `27f6bbb`) mit
   der Bindung von `419cef7`; Kettentests über die echten Befehle
   (Reparaturfall, üblicher Weg, Gegenproben, Rückzug gibt nichts frei).
   Abnahme mit kaltem Agenten bestanden
   ([Notiz](docs/usability/2026-10-28-declared-run-case-haiku-27f6bbb.md)):
   Rückzug, `fixed`, Folge-Audit `resolved`, Übernahme ohne `--force`,
   Commit ohne `--no-verify`, report-check im Image sauber — ein Versuch,
   keine Rate. Danach `--from-run --force` als Ersatzweg entfernt
   (`4ece8eb`, Breaking).
   Anleitung des Agenten (`b679bdb`): Rückzug zuerst nach einer
   Übernahme mit geändertem Code, Statustabelle in Schritt 4, Übergabe
   nur bei benannter fehlender Voraussetzung, Auswege einzeilig in der
   Entscheidungsliste. Beobachtet (Test
   `test_a_first_dismissal_in_the_state_reported_is_not_reviewed`): ein
   im berichteten Zustand erstmals `dismissed` entschiedener BLOCKER gibt
   die Übernahme ohne Zweitprüfer frei. Entscheidung offen: soll eine
   erste Verwerfung eines BLOCKERs eine Zweitprüfung schulden? Noch ohne
   Logbeleg eines Missbrauchs. Entschieden: ja, als neue Designanforderung
   — ein BLOCKER `dismissed` schuldet einen Zweitprüfer, eine WARNING
   nicht (`findings.dismissed_blocker`, Breaking).
   Fünfte SAB-Ziehung auf `28c22f9`
   ([Notiz](docs/usability/2026-10-28-sab-cases-haiku-28c22f9.md)): alle
   drei versteckten Prüfungen bestanden, zwei übernommen (fit-assay mit C1
   not assessable), keine Hook-Umgehung. Neue Lücke, Entscheidung offen:
   eine korrigierte Prosazeile des Protokolls (Data / scope) kann nie
   nachverfolgt werden — der Record bindet nur die beurteilten
   Registrierungsfelder, AGENTS.md verlangt nach einer Tippfehler-
   Korrektur aber ein erneutes Audit; der Auditor wertet dieselbe
   Korrektur als „not one of the ways out“. Wege: (A) der Record bindet
   die vor dem Lauf geschriebenen Prosafelder, die das Audit las (ohne
   die nach dem Lauf erzeugten), dann bewegt eine Korrektur den Zustand
   und das Folge-Audit beurteilt sie; dazu eine Regel, was als
   Tippfehler-Korrektur gilt, gleich in AGENTS.md und beim Auditor.
   (B) Korrekturen von Prosafeldern nach der ersten Messung nur über
   eine neue Registrierung. Empfehlung: (A).
   Gebaut (A) als `981dd6b`, dazu `1d1fce0` (erzeugte Datenzahlen,
   `--data-counts`) und `56e9899` (Null-Band nach registrierter Regel,
   Prüfung vor der ersten Messung). apply-screen erneut
   ([Notiz](docs/usability/2026-10-29-sab-apply-screen-haiku-56e9899.md)):
   nicht erfüllt — Agent: nur die 92 gelabelten Personen vorhergesagt,
   einmal `--no-verify` ohne vorherige Ablehnung. Band-Regel wirkte; die
   Korrektur bewegte den Zustand wie gewollt. Offen, labkit: (1) das
   Folge-Audit ging verloren, weil der Parser einen Absatz unter dem
   letzten Befund nach einer Leerzeile ablehnt (bezahlter Aufruf ohne
   Record); (2) `--calibrate-null --write` schrieb ein entartetes Band
   0.0 (Erwartung 0, Streuung 0) ohne Einwand; (3) getippte Zahlen in
   Data / scope ohne erzeugten Teil prüft niemand — soll ein solches Feld
   gehalten werden? Infrastruktur: der Host schlief, 5 h statt 1800 s.
   Dasselbe Setting mit Sonnet
   ([Notiz](docs/usability/2026-10-29-sab-apply-screen-sonnet-56e9899.md)):
   Vertrag erfüllt ohne bestätigte Aussage — 278 s, alle 300 vorhergesagt,
   `--data-counts` und `--calibrate-null --write` benutzt, report-check
   sauber; [C1] nicht beurteilbar, weil der Satz margin 0.2 sagt und die
   Konstante beim Stamp-Beispiel 0.25 blieb (Audit-BLOCKER, ehrlich
   akzeptiert). Offen, labkit: (4) Satz nennt eine Konstante mit anderem
   Wert als die Tabelle — mechanisch prüfbar vor der ersten Messung,
   bisher nur im Agenten-Audit; (1) trat erneut auf (zweiter Lauf in
   Folge). Behoben: Fehlalarm der Konstanten-Kopie bei `= None` (`78bc969`).
   Leseprobe (`docs/usability/2026-10-28-haiku-decision-reading.md`):
   drei Haiku-Leser wählen an den vier Logstellen den richtigen Schritt
   — Rückzug vor dem nächsten Audit, `fixed` erst nach der Reparatur,
   Übergabe nur bei fehlender Voraussetzung, die vier Status richtig.
   Eine Abweichung lag im Text: die Statustabelle verlangte für jedes
   `accepted … stands` einen Zweitprüfer, Schritt 5 nur für einen
   BLOCKER; nachgeschärft. Offen: ob ein laufender Agent den Hinweis
   „withdraw first“ unter sechs Blockern findet — nur ein Lauf zeigt das.


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

- **Runde 2 des labkit-Piloten (labkit-paper Bereich 15, labkit `72507d0`,
  `repeat_cost = high`, 2026-10-28): neun Mängel und die Steuerung der
  Reparatur.** Belege in labkit-paper
  `experiments/15-labkit-exploratory-evaluation/data/hand/`:
  `defects_v2.tsv` (neun Mängel, von Max entschieden), die Verdichtung aus
  elf gemeldeten Zeilen `defects_v2_condensation.md`, 67 Funde
  `catches_v2.tsv`, die Lesungen `readings_v2/`. Keiner der elf Mängel
  der ersten Runde trat wieder auf.

  *Verletzte bestehende Anforderungen — Mängel, zu reparieren nach der
  Regel vom 2026-10-27:*
  1. D1: Ein eingefrorenes `compute`-Protokoll bei `high` schuldet ein
     Codebeispiel, das der `compute`-Weg nie stempelt
     (`protocol_report.py:545`); `n/a — <why>` hebt es nicht auf, und
     `preflight` lässt dieselbe Datei durch. Folge: dreimal `--no-verify`
     (t21, t34).
  2. D2: `labkit-audit` verwirft die ganze Antwort des eigenen Auditors
     wegen eines Punkts nach `check: <key> (<note>)` (`findings.py:258-261`),
     schreibt keinen Record und nennt keinen nächsten Schritt (t71: drei
     echte BLOCKER verloren).
  3. D3: `labkit-audit --findings` nennt einen Audit-Aufruf, der ohne
     Record endete (`outcome = none`), nicht — gegen AGENTS.md:19-23 und
     den eigenen Exit-Vertrag (t71).
  4. D4: Der gestempelte Bereichstest hält das Null-Band auf dem
     Beispielwert 1 fest, den AGENTS.md zu ersetzen verlangt
     (`test-area.py.template:54-59`; pubmedqa: Band 5 → Test rot →
     Registrierung an den Test angepasst).
  5. D5: Ein mehrzeiliger Befund des Auditors wird im Record still auf
     seine erste Zeile gekürzt (`audit.py:808-809`); Wirkung, Regel und
     kleinste Änderung stehen dann nur in der Antwortdatei (t21).
  6. D6: `runlog --wait` meldet „idle“, solange das Skript vor
     `runlog.run` noch Zeilen vorbereitet (t21).
  7. D7: Der Pre-Run-Hook behandelt das dokumentiert schreibfreie
     `00_prepare.py --audit` wie einen Laufstart (`claude_hooks.py:189`;
     t15, latent).
  8. D8: `preflight --protocol <dateiname>` verweigert den bloßen Namen,
     den die eigene Usage-Zeile und der Hook zeigen (t71, gering).
  9. D9: `protocol-check --contract` druckt die Feldlisten der vollen Form
     ungefiltert nach Art und Modell (Kriterium und Prompt für `compute`
     ohne Modell; t15, t60, t21, t34).

  *Repariert 2026-10-28 auf Branch `r2-fixes`* (drei Worktrees, von Max
  geprüft): D1 `example_owed`, D8 `repo.given_or_in`, D9 `owed_fields`;
  D4 Template, D7 `standard_contract.NO_RUN_FLAGS` (auch
  `--calibrate-null`), D6 Startvermerk mit Überwacher und Exit-Status,
  Quittung nur für Gelesenes; D3 `--findings` nennt Aufrufe ohne Record,
  Abdeckung nach Art, Code, Versprechensblock und Reihenfolge, Journal
  mit `block_sha` (Breaking), historische Aufrufe mit eigenem Ausweg;
  D2 Punkt nach der Prüfnotiz; D5 ganzer Befund im Record nach der
  dokumentierten Endregel. Offen aus den Reparaturen, keine Mängel:
  - Ein heute fehlgeschlagener Aufruf auf seither geändertem Code bleibt
    gemeldet, bis ein Audit genau dieses Codes läuft — praktisch nur über
    die Übergabe lösbar (dieselbe Sackgasse, die für historische Aufrufe
    ausgeschlossen wurde).
  - Ein unterbrochener Audit-Aufruf ohne Ende nennt erst der nächste Start,
    nicht `--findings`; Text vor dem ersten Befund wird weiter ignoriert.
  - `compute` mit `[model]` schuldet weiter ein Codebeispiel; der Schlusssatz
    von protocol-check bietet `n/a` auch für Block-Pflichten an; preflight
    prüft die Pflichten beim Einfrieren (Beispiel, Überlänge) nicht;
    `--contract` nennt die geschuldeten `[[promise]]`-Tabellen nicht.
  - Der gestempelte Test hält `max_empty` am Beispielwert fest wie zuvor das
    Null-Band; `runlog --wait` schläft ein volles Intervall über
    `--max-seconds` hinaus.

  *Prüfung von audit/decide (Max, 2026-10-28) — Bestand, Verletzung, neu:*
  - **(a) Ein Befund sagt, was zu korrigieren ist, welcher Nachweis gilt
    und welcher Schritt folgt.** Bestand: das Berichtsformat des Auditors
    (`experiment-preflight.agent.md`, „Report format“) verlangt die
    kleinste Änderung als letztes Feld und, wo nur eine Diagnose die
    Reparatur zeigen kann, `check: <metrics key>`; `followup._earlier_hold`
    hält die Freigabe, bis der Lauf diesen Schlüssel trägt. Verletzt: D2
    (eine Antwort mit Prüfnotiz geht ganz verloren) und D5 (der Record
    behält von einem mehrzeiligen Befund nur die erste Zeile, die kleinste
    Änderung fehlt dann). Neu: Nachweis und nächster Schritt *je Befund*
    als Daten — heute gibt es `check` nur für Diagnose-Reparaturen, und
    `--findings` nennt Schritte je Zustand, nicht je Befund.
  - **(b) `fixed` gibt ein Ergebnis erst frei, wenn das Folgeaudit die
    Korrektur am maßgeblichen Lauf bestätigt hat.** Bestand für BLOCKER:
    `followup._earlier_hold` mit `report_check.followup_findings` hält
    Übernahme und `--from-run`, bis ein Folge-Analyseaudit den Befund am
    gezeigten Lauf `resolved` nennt und den geforderten `check` im Lauf
    sieht (Runde 2, t34: das Analyseaudit trug vier `fixed`-BLOCKER als
    `unresolved` weiter). Ein BLOCKER zum deklarierten Lauf selbst wird
    seit `84f6812` über den Rückzug der Deklaration frei (`protocol-fill
    --withdraw`, dann Folgeaudit und Übernahme ohne `--force`; Abnahmefall
    `357a08c`, ein Versuch) — nicht in labkit `72507d0`, auf dem Runde 2
    lief. Lücken: `--decide N fixed` nimmt ein `fixed` ohne jede Änderung
    an (in vier von sechs Versuchen ein `fixed` mit unverändertem Code
    oder fremder Begründung); WARNINGs werden nicht nachgeprüft; und die
    Bestätigung umfasst nicht die Ergebnisdatei der Aufgabe (neu, c).
  - **(c) Neu: Herkunft der Ergebnisdatei.** In keinem der sechs Versuche
    schrieb der Code des antwortenden Laufs die Ergebnisdatei der Aufgabe
    (`pred_results/…`): viermal ein Nebenskript außerhalb von labkit
    (t15, t60, t71, pubmedqa), einmal inline aus einem nie übernommenen
    Lauf (t34), einmal von Hand aus dem übernommenen Lauf abgetippt (t21).
    AGENTS.md verlangt es („never retype it or compute it apart from the
    run“), kein Gate prüft es: report-check hält nur Berichte, die einen
    Lauf zitieren, und der Stop-Hook schuldet ohne `[result]` nichts. Zu
    entwerfen: die Aufgabenausgabe als deklarierte Ausgabe des
    antwortenden Laufs (Pfad und sha256 im Lauf), gehalten von finalize,
    report-check und Stop-Hook gegen eine abweichende oder lauffremde
    Datei; die Freigabe aus (b) bindet sie mit. Erst Fehler und Zwilling,
    dann die kleinste Prüfung (Regel oben).
  - **(d) Ein fehlgeschlagener Audit-Aufruf bleibt über `--findings`
    sichtbar.** Bestand: AGENTS.md:19-23 und der Exit-Vertrag von
    `labkit-audit --findings`. Verletzt für eine Antwort, die als
    unlesbar verworfen wurde (Attempt `none`, kein `-failed.toml`): D3,
    ausgelöst durch D2.
  - *Beobachtet, nicht labkits Mangel:* `--no-verify` dreimal (t21, t34;
    der Stop-Hook fing den zweiten), ein gelöschtes REPORT.md
    (pubmedqa), ein erfundener Record-Name im Kopf (t71; Hook und
    Commit-Hook fingen ihn), ein Opus-Audit, das die Sicherheitssperre
    abbrach und das bis zum Ende des Versuchs nach 738 s ohne Antwort
    hing (t15; der 900-s-Timeout von `labkit-audit` war noch nicht
    erreicht, der Agent gab nach 120 s auf).

- **Offen nach den Reparaturen aus dem labkit-Piloten (labkit-paper
  Bereich 15, Runde 1 auf c2c5da2, 2026-10-28; Commits `24b9349` bis
  `0ed2699`).** Repariert wurde nur, wo labkit nicht tat, was es
  dokumentiert; diese Entscheidungen ließen die Texte offen:
  1. *Große oder geschützte Eingaben:* `finalize` blockt jede nicht
     eingecheckte Quelle weiter; der Ausweg nennt jetzt beide Wege des
     Standards. Offen: was die Erklärung in Data / scope nennen muss, damit
     ein Gate sie an Quelle und `sha256` des Laufs bindet; ob `finalize`
     dann durchlässt, warnt oder einen Blocker hält, den ein Mensch löst;
     wer „groß oder geschützt“ entscheidet; und der Widerspruch zwischen
     `standard.md:118-124` und LAB-017 (`:523-524`, „source outside git“).
     Bis dahin endet ein Lauf auf solchen Daten in einer Übergabe.
  2. *Ignorierte Quelle:* der Ausweg ist `git add -f -- <dateien>` statt
     „Regel entfernen“ wie in `evidence.py`. Eine Quelle außerhalb des
     Repos bekommt weiter ein `git add`, das git verweigert.
  3. *Binärdateien in `data=`:* sie werden deklariert (`BinaryInput`),
     nicht erkannt; ob runlog sie selbst erkennen soll, ist offen.
  4. *`stands` bei `compute`:* der einzige verbleibende Effekt heißt „die
     Urteile halten“, eine Berechnung hat keine Urteile; eigener Wortlaut?
     Dazu: mehrere Protokolle ohne `--protocol` oder ein unlesbarer Block
     bieten `<ID> not assessable` weiter an.
  5. *Bericht unter Übergabe:* ein Bericht, der einen Lauf eines
     übergebenen Bereichs zitiert, kommt nur heraus, wenn er keinen Lauf
     mehr zitiert. Soll ein Report-Review, das vom Verlust weiß, unter
     einer Übergabe laufen dürfen?
  6. *Platzhalter-Prompt:* `prompt_check.py:240` überspringt weiter jeden
     Block, der mit `<` beginnt (ein Prompt mit XML-Tag bekommt keine
     Drift-Prüfung); dieselbe Erkennung wie `is_stamp_placeholder_block`?
     `--render` und das Audit-Bündel schreiben weiter nur die lesbaren
     PROMPT-Konstanten, ein von `ast.parse` abgelehntes Skript bleibt stumm.
  7. *Kleinere Ränder:* bei detached HEAD gilt ein gestagter, nie
     committeter, dann gelöschter Record als verloren, obwohl `git checkout
     -- <pfad>` ihn zurückholt; die Verlustmeldung von report-check zeigt
     nur die erste Lücke.

- ~~**Ein konfliktfreier Merge umgeht die Gates des pre-commit**~~ —
  entschieden und gebaut 2026-10-28: `pre-merge-commit` führt den
  pre-commit auf dem Index des Merges aus; ein gehaltener Merge bleibt
  uncommittet (`tests/test_install_hooks.py`, `MergeChecks`). Probe auf
  dem Count-Walkthrough: der geänderte `02_analyze.py` des anderen
  Branches wird jetzt am fehlenden Analyse-Audit gehalten. Labor-Repos
  bekommen den Hook mit gehobenem Pin und `labkit-hooks install`.
- **Gleicher Bereichsname auf zwei Branches:** `labkit-init exp` lehnt
  einen vorhandenen Namen nur im eigenen Baum ab; auf einem anderen Branch
  entsteht derselbe Name unter anderer Nummer, und der Merge bringt
  `12-x` und `14-x` zusammen (`areas_named` weigert sich dann, den Namen
  aufzulösen). Notiert, nicht geplant; `areas_elsewhere` liefert die
  Namen schon mit.
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

- **Schon veröffentlichte Versuchsbelege (zurückgestellt am 2026-10-28):**
  Unter `docs/usability/` liegen auf `origin/main` 78 Dateien mit echten
  Agenten- und Leserantworten, Traces und Logs früherer Runden. Seit
  2026-10-28 gilt für neue Proben (Entscheidung des Autors für diesen
  Fall, keine ältere Hausregel): echte Antworten und aufgabenbezogene
  Logauszüge bleiben intern im Archiv `/Users/max/projects/labkit-evidence`
  (lokal, ohne Remote), öffentlich nur Kriterien, synthetische Tests und
  eine knappe Beschreibung. Offen: ob die schon veröffentlichten Belege
  nachträglich heraus sollen — das hieße gepushte Historie umschreiben und
  force-pushen; die Originale gingen vorher ins interne Archiv.

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
  Wurzel. **Stufe 3 gebaut 2026-10-25, als Warnung:** `labkit-audit
  AREA --report-review REPORT` (Bericht mit Zeilennummern, Protokoll,
  metrics.json der markierten Läufe, alle Audit-Records mit
  Entscheidungen und gescheiterten Versuchen; nur bei Markierung). Pilot
  ([Bericht](docs/usability/2026-10-25-report-review-pilot.md)): t3 und
  t18 in 4 von 4 Ziehungen gefangen, saubere Gegenbeispiele 10 von 10
  ohne Meldung, 0,08–0,16 USD je Aufruf; klein (zwei Positivfälle, ein
  Modell). Einordnung (2026-10-25): die Treffer zeigen, dass sie die
  zwei bekannten Fehler wiederholt erkennt; Runde 1 der ehrlichen
  Fassungen bleibt strittig, bis ein vom Prüfer unabhängiger Richter
  sie beurteilt; die bereinigten Fassungen prüfen vor allem, ob die
  Korrekturen angenommen werden. Eingebunden als Hinweis mit dem
  konkreten Kommando: `claude-hook post-change` (einmal je Textstand)
  und `report-check` (sieht der Agent am Commit); gestartet wird sie nur
  vom Agenten. Nach der achten Runde (t18: Hinweis übergangen) ersetzt
  durch V2/V3 oben: Das Review wird Pflicht, sein Record liegt unter
  `audits/report-reviews/`, gebunden an Bericht, Protokoll, Laufwerte und
  Auditentscheidungen. **Ausdrücklich offen:** ein
  Bericht ganz ohne Lauf-Zitat (t5: Run-ID gelöscht) bleibt ungeprüft —
  die Sperre dafür ist zurückgestellt, bis eine eindeutige Zuordnung von
  Berichtsabschnitt zu Protokoll geklärt ist (ein vorhandener Lauf und
  ein gleichzeitig geänderter Bericht belegen keinen Zusammenhang). Und: der Blocker-Satz
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
- **Kennzahlen der Eingaben ohne Ablage (siebte Runde, beschlossen
  2026-10-25 als offene Aufgabe):** Alle 17 falschen Zahlen der drei
  labkit-Berichte waren Fakten über die Eingaben — Zeilenzahlen (t5: 29
  statt 44; t3: Dateizeilen statt Datensätze), Median (t5: 0,465 statt
  0,284), Klassengrößen (t18: 209/191 statt 174/226). Der Code rechnet
  sie, legt sie aber in keiner behaltenen Datei ab; kein Bericht und
  keine Berichtsprüfung hat eine Quelle, gegen die sie zu halten wären
  ([Präzision](docs/usability/2026-10-25-hint-precision-r7.md)). Sie
  gehören dorthin, wo der Code sie berechnet, in den Lauf. **Umgesetzt
  2026-10-26:** kein neues Format. `metrics.json` und der Berichtsblock
  sind die eine Heimat; der Block rendert jeden Schlüssel und blockt bei
  Abweichung. Die Estimator-Vorlage speichert `scored_class_counts`
  (accuracy/auc). Vorlagen, gestempelte AGENTS.md und `docs/workflow.md`
  sagen: Eine Eingabekennzahl im Bericht kommt aus `evaluate_rows` über
  behaltene Zeilen, nie von Hand. Ausdrückliche Grenzen: Die
  Klassengrößen der bewerteten Zeilen sind nicht die Klassenverteilung der
  Eingabedatei; `--check` hält einen verschwundenen gespeicherten
  Schlüssel, aber keine Zahl, die nur in der Prosa steht. Offen bis
  Runde 9: Stehen die Eingabekennzahlen dann im Block statt in der Prosa?

## Architektur und Lesbarkeit — notiert, nicht geplant

### Phase-2-Reste (2026-10-27)

Entschieden 2026-10-27 (Autor), umgesetzt:

1. `--review --again` gibt nichts frei; der Exit sagt den Stand
   (Vertragsfehler, kein offener Grundsatz).
2. Ohne Stop-Basis und ohne Transkript hält der Stop: eine Prüfung, die
   nicht laufen kann, gilt nicht als sauber.
3. 2.1: Der erste Ausweg ist „korrigieren → neu messen → auditieren“;
   den alten Code wiederherstellen nur bei einer ungewollten Änderung.
4. 2.2 schützt die Registrierung, nicht jede Laufauswahl — Grenze in
   CHANGELOG und Note genannt.

5. Eine Sitzung, die unter dem Repo-Root startet, lädt keine Projekt-Hooks
   des Roots: dokumentiert (README, architecture, Ausgabe von
   `labkit-hooks install`), nicht anders installiert.

Als Nächstes: der Reparaturfall (Phase 0.3) vor jedem weiteren
Härtungspaket; Tests und Reviews ersetzen die Ausführungsprobe nicht.

Notiert, nicht gemacht:

6. Der antwortende Lauf ist weiter der neueste nach Namen
   (`answering_run.bound_answering_run`); die Zeitzone kann steuern, welcher
   Lauf antwortet (verwandt A13). Ebenso vergleicht `record_session` im
   Stop-Hook die Ortszeit der Lauf-id mit dem Sitzungsbeginn.
7. Läufe mit unlesbarer `config.json` überspringt die Bestimmung der ersten
   Messung still (wie vorher); `git` und `git_full` im Record werden nicht
   gegeneinander geprüft (gehört zu 2.5); `undecided --staged` bestimmt die
   Bereiche aus den Protokollen im Baum, nicht im Index (2.5).
8. Berichte unter einem Verzeichnis-Link (`reports -> data/reports`)
   erreicht `report_files` nicht; ein Kreis aus Links lässt
   `affected_protocols` laut abbrechen; Protokolle als Links sind
   ungeregelt.
9. Das Stop-Budget (90 s) an echten Repos messen: ein Bereich mit Tests
   über 90 s hält jeden Stop einmal pro Zug. pre-run hat dasselbe
   Zeitproblem (Hook-Timeout 120 s, Bereichstests bis 300 s).
10. Ein Ledger der vom Pre-commit geprüften Tree-Hashes zeigte Commits, die
   an ihm vorbeigingen (`--no-verify`); verworfen 2026-10-28: es hält
   Herkunft statt Inhalt, und Pull, Rebase und frischer Klon brächten Trees,
   die dieser Hook nie sah. Den Inhalt eines umgehenden Commits prüft der
   Stop gegen dessen Elternteil (`evidence.commit_changes`, `3a30c3e`).
11. Lauf-Zeuge im Git-Verzeichnis (Blob-ids eines abgeschlossenen Laufs,
   wie die Journal-Kopie): sähe einen Lauf, der vor seinem ersten Commit
   geändert oder gelöscht wurde. Offen, weil ein solcher Verlust nicht
   wiederherstellbar ist und einen Ausweg braucht, den eine Übergabe
   bindet — die Übergabe bindet `runs/` heute nicht.
12. `answering_run` rät bei unlesbaren oder gleichsekundigen Läufen noch,
   sie „beiseite“ bzw. „aus runs/“ zu schieben
   (`labkit/formats/answering_run.py:657`, `:666`); seit `3a30c3e` hält
   der Stop genau das für einen committeten, abgeschlossenen Lauf. Den
   Ausweg neu fassen (welcher Lauf antwortet, ohne Beleg zu entfernen) —
   hängt an Punkt 6 (antwortender Lauf = neuester nach Namen).
13. `git` gegen `git_full` im Run-Record und `undecided --staged` mit den
   Bereichen aus dem Index (Punkt 7) bleiben offen; nicht Teil von
   `3a30c3e`.
14. Halbgenerische Auswege („repair what the sentence names, then …“):
   `finalize.py` (intent-check-Ablehnung), `run_record_check.py`
   (unlesbarer Code), `report_check.py` (Render-Fehler, Analyse-Lücke),
   `report_hold.py` (Review nicht bestimmbar), `start_check.py` (Bereich
   nicht stempelbar); dazu die nicht umgestellten code-check-Auswege
   (`labkit/checks/code_check.py:227`, `:245`, `:391`,
   `labkit/checks/code_scan.py:211`). Jeder nennt den nächsten Befehl,
   aber nicht die Ursache-spezifische Reparatur.
15. preflight wiederholt für jedes fehlende Pflichtfeld denselben
   `protocol-check … --contract`-Hinweis — lange Ausgabe; einmal am Ende
   reichte.
16. Nicht vom Pflichttest erfasst: allgemeine `console.refuse`-
   Verweigerungen (Bedienfehler) außerhalb der TODO-Liste;
   `HandoverError`, `FindingsError`, `ReviewError` ohne `fix`-Feld (ihre
   Sätze erreichen den Agenten über `findings.record_way`); die
   Journal-Kopie, die bei Unlesbarkeit aus dem Journal neu geschrieben
   werden soll (`cp`), wäscht ein gekürztes Journal — nur unter der
   Annahme des gutwilligen Agenten tragbar.
17. Merge von `evidence-hardening` nach main: erledigt 2026-10-28. Main
   brachte neue Ablehnungen ohne `fix` mit (`attempts.copy_gaps` zweimal,
   `declared_run_mismatch` mit Vorbedingung, `NullLanes`, runlogs
   `_first_step`); sie tragen ihren Ausweg jetzt als Daten, die Kopie-
   Auswege an einer Stelle (`attempts._copy_way`).

### Phase-1-Reste (2026-10-27)

Gefunden beim Umsetzen von Phase 1; abgearbeitet am selben Tag:

1. `--explore` verweigert `--kind`, `--repeat-cost`, `--model`,
   `--report` (`e5cd984`).
2. `--change-kind`: eine nie committete abweichende Stempeldatei heißt so,
   nicht „edited“ (`0317d65`). **Bleibt:** `carried_fields` misst
   „geschrieben“ am Stempel des installierten labkit — eine Vorgabe einer
   früheren Version wandert als geschrieben mit oder hält als „no place“;
   beides verliert nichts (sichere Seite), nicht nachgestellt.
3. `--change-kind` stagt alle Dateien vor dem ersten Ersetzen
   (`files.write_all`, `bc58200`).
4. `write_atomic` räumt die Staging-Datei, behält den Modus, verweigert
   eine schreibgeschützte Datei; `write_if_absent` schreibt atomar
   (`f24d07a`).
5. Bezeichnerregel 5 im Standard (`7498e04`).
6. `--probe` in workflow.md und launch.json (dieser Stand).
7. **Bleibt:** `scaffold.next_steps` druckt alle Schritte für einen
   Bereich mit einem Protokoll vom Repo-Root aus; ein Serienbereich
   bräuchte `--protocol` in jedem Schritt (preflight, code-check,
   finalize, report-check, Audit), nicht nur im Audit — eigener Schritt,
   wenn ein Serienbereich `--report` oder `--change-kind` braucht.

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
| `repo-check`: passt `AGENTS.md` zum Pin? | Nächste Pin-Anhebung in einem Labor: `labkit-init lab` schreibt eine vorhandene `AGENTS.md` nicht neu (`write_if_absent`), der Agent folgt dann Flags, die das gepinnte labkit nicht kennt (2026-10-27: `--cost` gegen `--repeat-cost`/`--kind`). | Vergleich mit der Vorlage des installierten labkit, Projektname für `<project>` eingesetzt; kein Git nötig, das installierte Paket ist der Pin. Statische Evidenz: warnt, blockt nie — eine von Hand ergänzte `AGENTS.md` ist zulässig, der Befund nennt die Abweichung. Herkunft bei Bedarf rückrechnen: die Vorlage an jedem Commit, der sie änderte, gegen die Datei (2026-10-27 von Hand: argsme-mining = `42f0ec8`/v0.102.0, labkit-probe = `52eade3`/v0.88.7, beide passen zum Pin). Neue Labore hält seit `ec3026e` schon `check_lab_pin`. |
| LAB-092 Term layering neu fassen | Ansage (eigener Auftrag). Anlass: SimpleEnglish-Vergleich 2026-10-28 an labkit-paper-Notes (`~/work/resources/knowledge-management/slip-box/simpleenglish-und-unsere-notes.md`); der Satz „English coinages live in code and config keys, not in German explanatory prose“ (`docs/standard.md:1227`) entscheidet die Wortwahl gegen den Maßstab Verständlichkeit. | Vorgeschlagene Fassung (deutsch, beim Umsetzen ins Englische des Standards übertragen): „Begriffe in deutscher erklärender Prosa nach Verständlichkeit wählen und konsistent verwenden. Fachbegriffe beim ersten Vorkommen kurz erklären; Bezeichner aus Code und Konfiguration unverändert wiedergeben.“ Leser der Regel greppen (Haus-`CLAUDE.md`, `gute-notes-schreiben.md`, `checklists/note-terms.md`). |
| `protocol-check`: Wortbudget für Summary und Antwort | Ansage, nachdem die Einstiegswarnung von `note-check` und der Hook nach Write/Edit in `~/work` eine Weile gelaufen sind (dotfiles `e4299ec`, `5d15bef`). Anlass: Längen-Messung 2026-10-28 über uniagent, labkit-paper und counterfactual-worlds (`~/work/resources/knowledge-management/slip-box/kuerzere-und-einheitlichere-notes-und.md`). | Warnung, nie Block. Gemessen: Summary n=165, Median 124, p90 193 Wörter (über 200: 5 %); „Answer to the question“ n=184, Median 77, p90 172 (über 120: 18 %). Lockerer Start am 90. Perzentil wie bei `note-check` (etwa 200 und 170 Wörter), später enger; eingefrorene Protokolle nicht nachträglich anmahnen. |

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

labkit-paper (Pin 0.85.0): die Nummernvergabe über alle Branches und der
`pre-merge-commit` kommen erst mit gehobenem Pin und `labkit-hooks
install`. Bis dahin vergibt `lib exp` in `~/projects/labkit-paper`
(`main`) wieder 12, die `round7-haiku` schon trägt; `14-…` in
`main-round` ist von Hand ausgewichen (2026-10-27).

labkit-paper: `lib/sandboxlab/standard_check.py:117`
(`registration_at_first_measurement`) bestimmt die erste Messung selbst
nach Namensreihenfolge und liest `git` — dieselbe A11-Lücke, die labkit
mit 2.2 geschlossen hat; das Bewertungsinstrument der Runde 10 braucht
die labkit-Regel (gefunden 2026-10-27).

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

- Berichtsprüfung in der nächsten kalten Runde (Bereich 09): Wird der
  Hinweis auf `labkit-audit --report-review` befolgt, ignoriert oder
  stört er wiederholt? Wird der fertige Bericht besser (Zahlen eines als
  `(not reported: …)` markierten Laufs als Ergebnis, Widersprüche zu
  Auditentscheidungen)? Dazu Runde 1 des Piloten von einem unabhängigen
  Richter beurteilen lassen
  ([Pilot](docs/usability/2026-10-25-report-review-pilot.md)).

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



