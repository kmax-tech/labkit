# TODO — labkit

*Offene Werkzeugarbeit, jede mit Beleg, Auslöser und Prüfstelle. Stand
2026-10-06, nach der Usability-Reihe (`docs/usability/2026-10-05-trace.md`).
Reihenfolge ist Priorität. Nichts hier wird vorsorglich gebaut: jeder Punkt
wartet auf seinen Auslöser, und die Prüfstelle ist der Ort, an dem man ihn
sieht.*

## 1. `promote <bereich>` — der Beförderungs-Audit als Kommando

**Was:** Die Regel seit 2026-10-05 (§2.A12): bei `Cost: seconds` kein
Agent-Audit je Lauf; der unabhängige Audit kommt, wenn die Zahl in eine Note
oder ein Paper geht oder eine Entscheidung steuert. Dafür gibt es die Regel,
aber kein Werkzeug. `promote <bereich>` startet den Agenten
`experiment-preflight` im Modus `analysis`, **synchron, Zeitlimit 10
Minuten** (Konstante `PROMOTE_TIMEOUT_S` in `labkit/promote.py`,
überschreibbar per `--timeout`; bei Ablauf Abbruch mit Meldung, kein stilles
Weiterwarten), entscheidet die Befunde mit dem Nutzer und stempelt die Zeile
`Analysis audit †:` mit `scope sha` ins Protokoll.

**Beleg:** Opus (Probe 11) wartete sechs Minuten auf einen Audit, der erst
nach seinem Bericht kam; vier Agenten nannten das Warten als größte Senke.

**Auslöser:** die erste echte Beförderung — uniagent Bereich 01, Weiche [W1]
(sieben Registereinträge tragen nichts), die eine Entscheidung steuert.
Bauen, wenn sie ansteht, nicht vorher.

**Prüfstelle:** Schritt 11 des Arbeitsablaufs (Ergebnis-Note schreiben). Wer
dort steht und das Feld `Analysis audit †: none yet` vorfindet, baut erst
dieses Kommando.

## 2. Nachmessung mit n = 3 je Stand, dann Rollout

**Was:** Je Aufgabe (`count`, `judge`) drei kalte Läufe auf dem aktuellen
labkit, Median der Wandzeit, und drei Bedingungen, die `usability score`
prüft: `equals the truth` (count: der gehaltene Mittelwert ist 3,5,
nachgezählt aus den gepflanzten Dateien) bzw. `within [0, 1]` plus `null
condition reported` (judge) · Fehlalarme = `gate`-Zeilen im Log, deren
Ursache kein Fehler des Agenten war (von Hand aus dem Bericht gezählt, Ziel
0) · `reads of labkit source / standard` = 0 (gezählt aus den `read`-Zeilen
des Logs, seit v0.44.0 in der Score-Tabelle). Erst damit steht der Stand auf
Daten; danach `lib sync pull` in counterfactual-worlds, fallacy-datasets,
fallacy-detection, paper-organization (eigener Auftrag, §7.4: Kern und
Rollout trennen).

**Beleg:** Zählung 4m20s, 6m01s, 9m58s auf drei Ständen — die Streuung
zwischen Agenten ist größer als die Wirkung der letzten Änderungen; drei
Einzelläufe trennen Stand und Agent nicht.

**Auslöser:** vor dem nächsten Rollout, oder nach der nächsten Änderung an
Templates oder Gates.

**Prüfstelle:** der Commit, der labkit oder einen Stempel ändert — seine
Nachricht nennt die drei Läufe oder sagt, warum nicht.

## 3. `code-check`: jede registrierte Kennung braucht einen Zweig, nicht nur einen Schlüssel

**Was:** Eine Kennung ist ein Versprechen des Protokolls an den Code: `[N1]`
„die Null-Spur liegt bei 0,5 ± ein Item, sonst kein Inhaltswert". Heute
prüft `code-check`, dass sie als Schlüssel im Code vorkommt
(`metrics["n1_pass"] = …`). Ein Schlüssel ohne Zweig ist ein Label ohne
Wirkung: `n1_pass` wird berechnet, aber nichts hängt davon ab — der
Inhaltswert `k1_pass` wird auch dann berichtet, wenn `n1_pass` falsch ist.
Der Zweig wäre `if not metrics["n1_pass"]: metrics["k1_pass"] = None`.
Prüfung: jeder `[K]/[S]/[N]`-Schlüssel wird mindestens einmal **gelesen** (in
einer Bedingung, einem Vergleich, einem Rückgabewert), nicht nur
geschrieben — per AST, wie `code_check` heute Lese- und Schreibstellen der
Datenfelder trennt.

**Beleg:** Opus-Audit (Probe 11): „[N1] war ein Label ohne Effekt — die
registrierte Regel ‚über 0.58 kein Inhaltswert' hatte keinen Zweig"; in der
Klassifikation über sechs Repos Klasse C (24 Befunde).

**Auslöser:** der nächste Bereich mit Nullbedingung, der durch `code-check`
geht — dann an echtem Code bauen.

**Prüfstelle:** `code-check` selbst; bis dahin druckt er den Hinweis „Zweig
je Kennung: nicht geprüft".

## 4. `--draw N` im Mess-Skelett — die Wiederholungs-Ziehung

**Was:** `01_measure.py --draw N` fährt dieselben Jobs ein weiteres Mal:
genau **ein** zusätzlicher Durchgang je Aufruf, Ausgabedatei
`<name>_draw<N>.jsonl`, eigener Lauf mit `derived_from=<run_id des ersten>`
in der Config, gleiche Sampling-Einstellung (claude-cli kennt keine
Temperatur, also Backend-Standard; bei Ollama derselbe Seed-Modus wie der
erste Lauf, in der Config notiert). `evaluate_rows()` läuft je Ziehung
unverändert; die Aggregation (Spannweite der `k1_accuracy` über die
Ziehungen, Anzahl gekippter Items) macht `02_analyze.py`, nicht das
Mess-Skript. Opus hat genau das von Hand gebaut; es ist universell.

**Beleg:** Zweite Ziehung derselben 24 Aufrufe gab 10/12 statt 11/12, drei
Items kippten — die Zahl trägt ±1 Item Rauschen, und ohne zweite Ziehung
sieht das niemand.

**Auslöser:** der nächste Modell-Lauf, dessen Zahl berichtet wird.

**Prüfstelle:** `finalize` bei `Cost: seconds` mit Modell — eine Warnung
„eine Ziehung, keine Streuung", bis `--draw` existiert.

## Notiert, nicht geplant

- Die Vertragskarte im Bereichs-README hält die Agenten nicht vom Lesen des
  Standards ab (vier von vier lasen ihn trotzdem). Kein Werkzeugproblem;
  nicht weiter optimieren — aber zählen (`reads of labkit source / standard`
  in `usability score`), damit sichtbar bleibt, ob es sich ändert.
- Eine Stub-Zeile für `s1_*`/`k1_*` neben den TODOs im Zähl-Skelett (Sonnet,
  Probe 15) — erst, wenn das Zähl-Skelett Kennungen bekommt.
