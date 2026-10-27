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
3. **Übergabe als funktionierender Ausweg, gebaut mit dem
   Abschlussvertrag 3.1 (t18, B3):** Vor neuen
   Integritätssperren einen expliziten `protocol-fill`-Schritt für einen
   erzeugten ungelösten Bericht bereitstellen. Name und Format vorher
   klären; keine nicht vorhandenen Skills als Voraussetzung.
   Kopf: Protokoll, Ursache, versuchte Schritte, bekannte Läufe/Records und
   offener Evidenzverlust. Muss ohne Lauf und bei fehlendem Record
   funktionieren. Übergabe bestätigt keine Zahl und heilt keinen
   beschädigten Beleg. Eine ausdrücklich ungelöste Abgabe muss den
   Abschlussweg erreichen, während Ergebnisfreigabe weiter verweigert
   wird; keine globale Unterdrückung offener BLOCKER. Der Ort des
   geschuldeten Berichts (3.1) wird hier mitgebaut: Stop und Pre-commit
   müssen den Übergabeblock finden.
   Zwei Fälle: (i) Ein lesbarer offener BLOCKER bekommt über `--decide`
   eine Entscheidung, ungelöst `deferred` mit Grund. Stop und Pre-commit
   halten heute nur `open`; am Hook ist dafür nichts zu bauen. Der
   Übergabeblock nennt die Befunde strukturiert (Record und Nummer); kein
   Gate liest den Grundtext als Marker — ein Prosamuster scheiterte schon
   an Backticks (V1). (ii) Ein fehlender Record oder ein unlesbares
   Journal gibt nur frei, wenn der TOML-Kopf der Übergabe genau diese
   Lücke nennt (Recordname bzw. Journal-Id): exakt und garantiert; die
   Prosa über noch vorhandene Belege ist es nicht. Den Verlust schreibt
   ein benannter Befehl mit Format-Heimat `attempts` (Name per
   `/naming`), keine erfundene Entscheidung; Gates drucken ihn nur als
   `fix`. Nur diese benannten Lücken enden; fremde oder neue offene
   Befunde bleiben gehalten, und keine Variante bestätigt eine Zahl.
   Eine ausstehende Entscheidungsprüfung hält die Ergebnisfreigabe,
   nicht die ausdrücklich ungelöste Übergabe. Diesen Unterschied auch
   mit 2.6 und dem Rückfall ohne Stop-Basis aus 2.7 gegenprüfen.
   Abnahme: offener lesbarer BLOCKER, zuvor abgelehnte Entscheidung,
   nie gestagter verlorener Record, unlesbares Journal und „Ergebnis
   deklariert, dann übergeben“ (der Schreiber zieht `[result] run`
   zurück); jeweils Übergabe samt Stop und Commit möglich,
   Ergebnisübernahme verweigert.
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

1. **Abschlussvertrag (gebaut mit 2.3):** Geschuldete Abgabeberichte ausdrücklich bestimmen,
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
3. **Gestempelte Anleitung:** „When you are stuck“ mit fünf kurzen Wegen:
   reparieren und neu messen; Kriteriumsverfehlen berichten; Anspruch
   begrenzen; mit Vorgänger neu registrieren; ungelöst übergeben. Echte
   Befehle und Voraussetzungen, beide Kostenstufen und alle Typen.
   Erlaubte Entscheidungen ändern den Record über `--decide`; die Anleitung
   darf deshalb nicht pauschal jede Änderung unter `audits/` verbieten.
   Die Wege der Vorlage und `audit.BLOCKER_ROUTES` hält ein Test gleich.
4. **Stolperdrähte:** Heuristische Erkennung von Shell-/Edit-/Write-Aktionen
   ist statische Evidenz und warnt, niemals BLOCKER. Keine Sperre auf
   Schlüsselwörter wie `reset`, `--amend` oder `audits/`; sie träfe auch
   legitime Operationen. Exakte Integritätsverstöße hält 2.5. Neue
   Heuristiken nur nach belegtem Bedarf und mit Fehlalarm-Gegenproben.
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
   an ihm vorbeigingen (`--no-verify`); nicht gebaut.

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



