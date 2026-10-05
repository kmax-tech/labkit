# Was die Agent-Audits in sechs Labor-Repos gefunden haben, nach Klassen

*Recherche-Note · Korpus: 26 Protokolle mit Audit-Zeilen in counterfactual-worlds
(16), fallacy-datasets, fallacy-detection, paper-organization, thesis-nair,
uniagent · Stand 2026-10-05 · Klassifikation durch einen Lese-Agenten (Opus),
Rohdump `2026-10-05-audit-records.txt`, Skript `2026-10-05-audit-extract.py`.*

> Frage: Welche Befundklassen wiederholen sich über Repos hinweg, und welche
> davon könnte ein Gate statt ein Agent prüfen? Anlass: die Usability-Trace
> vom selben Tag (`2026-10-05-trace.md`), die bei Zählläufen den Agent-Audit
> auf die Beförderung verschoben hat.

## Zahlen

22 Audit-Protokolle mit Schweregrad-Aufteilung erklären 230 Befunde (40
Blocker, 109 Warnungen, 81 Notizen); 171 davon sind im Protokolltext
einzeln benannt, der Rest steht nur als Zahl („Einzelheiten: Commit"). Fünf
von 22 Audits fanden null Blocker (23 %), keines fand null Befunde.

| Klasse | Befunde | Blocker | Gate möglich? |
|---|---:|---:|---|
| A Gezählte Einheit / Nenner | 31 | 2 (+3) | teils: Ausbeute je Stufe und `n` je Kriterium abgleichen; nicht: ob „je Kontrast" oder „über sechs Welten" die registrierte Einheit ist |
| B Herkunft (Output nicht an Lauf gepinnt, Quelle nicht frisch, Prompt vom Konstantenwert abgedriftet) | 40 | 3 (+2) | ja, fast ganz: `finalize` Station 4 deckt Quelle/Dateien; fehlen: Prompt-Block == `--show`-Ausgabe als Test, jede Zahl im Ergebnisblock aus einem gebundenen Lauf, run_id-Pflicht |
| C Kriterium gegen Code (registrierte Regel ohne Zweig oder Schlüssel, Schwelle deklariert und nie angewendet) | 24 | 4 (+1) | teils: `intent-check` hat den größten Teil; dazu `code-check`: deklarierte Konstante, die in keinem Vergleich gelesen wird |
| D Parser / Antwortform | 5 | 0 | ja: jede `parse_*`-Funktion braucht einen Fixture-Test mit echten Rohantworten |
| E Nullbedingung / Anker falsch | 19 | 4 (+1) | die wichtige Hälfte nein: eine rückwärts gedachte Positivkontrolle sieht kein Check |
| F Auflösung (Kriterium bei diesem n unerreichbar) | 13 | 0 | teils: `evaluate()` meldet den erreichbaren Boden neben jedem p, Gate fällt bei Boden > Schwelle |
| G Nur Dokumentation | 9 | 0 | ja, weitgehend vorhanden |
| H Leckage (Anker/Placebo teilen Daten mit dem gemessenen Arm; Knopf auf dem Testsplit gewählt) | 5 | (+1) | ja, neu und am ergiebigsten: Mengen-Schnitt der Item-Hashes von Anker/Tor/Placebo gegen die Messmenge, nichtleer = Blocker |
| I Konfund benannt, nicht quantifiziert | 7 | 2 (+1) | nein: welcher Störfaktor, ist Fachwissen |
| J Berichtete Zahl ist nicht, was sie behauptet | 4 | 2 | nein, bis auf: kein berichteter Schlüssel `null`, solange seine Eingaben existieren |
| K Fail-loud | 5 | 0 | ja: AST-Regeln in `code-check` |
| L Endpunkt-Pacht umgangen | 4 | 0 | ja: Test, dass kein Modellaufruf an `llm.complete` vorbei geht |
| M Lauf kann seinen Anspruch nicht einlösen (Ergebnis durch Tests vorbestimmt) | 2 | 1 | nein |
| N Sonstiges | 3 | 0 | gemischt |

A, B und C sind 95 von 171 Befunden (56 %).

## Wo der Agent seinen Preis verdient hat

1. **E, Nullbedingung falsch herum.** Die registrierte Positivkontrolle
   `total` hätte „Instrument tot" genau im interessanten Fall gemeldet;
   `none` bewies nur, dass der Richter Ja sagen kann; die Nullbedingung
   schlug das Register 0,86 zu 0,14 durch Nichtstun. Kein Gate liest die
   beabsichtigte Richtung einer Kontrolle.
2. **I, unregistrierter Konfund.** Der teuerste Befund im Korpus: „in Stufe A
   war die höhere p-Seite in 48/48 Paaren zugleich die längere" — eine ganze
   annotierte Stufe wurde zurückgezogen, zwei Ersatzstufen gebaut, und im Code
   war nichts falsch.
3. **J und M, Zahl gegen Satz.** Zwei Audits kippten berichtete Kopfzahlen;
   die Stop-Ursache war die entgegengesetzte Fehlzurechnung; ein Ergebnis war
   durch Golden-Tests vorbestimmt. Das ist die Beziehung zwischen einer Zahl
   und dem Satz daneben, und die liest kein Checker.

## Konsequenz

Die Einteilung von heute hält über sechs Repos: Was sich wiederholt, ist
Herkunft, Nenner und Kriterium-gegen-Code, und das ist Gate-Material. Was den
Agenten braucht, ist die Richtung einer Kontrolle, ein unbenannter Konfund
und die Zahl gegen ihren Satz — und das sind genau die Fragen, die bei der
Beförderung einer Zahl gestellt werden sollten, nicht bei jedem Lauf.

Kandidaten für neue Gates, nach Ertrag je Zeile Code:

1. **Leckage-Schnitt** (H): Item-Hashes von Anker, Tor, Placebo gegen die
   Messmenge; nichtleer = Blocker. Drei Befunde in drei Repos, ein bestehendes
   `--exclude` war zu eng gefasst.
2. **Parser-Fixture-Pflicht** (D) in `code-check`: jede `parse_*`-Funktion
   hat einen Test mit echten Rohantworten.
3. **Prompt-Block == `--show`** (B) als Test im Bereich: der Block im
   Protokoll ist die gerenderte Ausgabe, keine Abschrift.
4. **Ausbeute-Abgleich** (A): jede Stufe meldet `n_in`/`n_out`, jedes
   Kriterium sein `n`, und die n's müssen sich mit den Eingabezeilen
   schließen.
5. **Erreichbarer Boden** (F): `evaluate()` meldet den Boden neben jedem p;
   Boden > Schwelle fällt.

Nicht bauen: einen Agenten je Modul. Die Befunde sitzen zwischen den Modulen
(Nenner aus der Ausgabe statt aus der Quelle, Analyse an die falsche Datei
gebunden); ein Modul-Prüfer sieht die Naht nicht. Parallelisieren lohnt bei
den drei unabhängigen Fragen des Auswertungs-Audits, je mit eigenem Bündel.
