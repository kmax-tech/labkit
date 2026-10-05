# TODO — labkit

*Offene Werkzeugarbeit, jede mit Beleg und Auslöser. Stand 2026-10-05, nach
der Usability-Reihe (`docs/usability/2026-10-05-trace.md`). Reihenfolge ist
Priorität. Nichts hier wird vorsorglich gebaut: jeder Punkt wartet auf
seinen Auslöser.*

## 1. `promote <bereich>` — der Beförderungs-Audit als Kommando

**Was:** Die Regel seit heute (§2.A12): bei `Cost: seconds` kein Agent-Audit
je Lauf, der unabhängige Audit kommt, wenn die Zahl in eine Note oder ein
Paper geht oder eine Entscheidung steuert. Dafür gibt es die Regel, aber kein
Werkzeug. `promote <bereich>` startet den Agenten `experiment-preflight` im
Modus `analysis`, **synchron mit Zeitlimit**, entscheidet die Befunde mit dem
Nutzer und stempelt die Zeile `Analysis audit †:` mit `scope sha` ins
Protokoll.

**Beleg:** Opus (Probe 11) wartete sechs Minuten auf einen Audit, der erst
nach seinem Bericht kam; vier Agenten nannten das Warten als größte Senke.

**Auslöser:** die erste echte Beförderung — uniagent Bereich 01, Weiche
[W1] (sieben Registereinträge tragen nichts), die eine Entscheidung steuert.
Bauen, wenn sie ansteht, nicht vorher.

## 2. Nachmessung mit n = 3 je Stand, dann Rollout

**Was:** Je Aufgabe (`count`, `judge`) drei kalte Läufe auf v0.43.0, Median
der Wandzeit, Zahl der Fehlalarme (Gate rot ohne echten Fehler) und ob der
Agent labkit-Quelltext las. Erst damit steht der heutige Stand auf Daten;
danach `lib sync pull` in counterfactual-worlds, fallacy-datasets,
fallacy-detection, paper-organization (eigener Auftrag, §7.4: Kern und
Rollout trennen).

**Beleg:** Zählung 4m20s, 6m01s, 9m58s auf drei Ständen — die Streuung
zwischen Agenten ist größer als die Wirkung der letzten Änderungen; drei
Einzelläufe trennen Stand und Agent nicht.

**Auslöser:** vor dem nächsten Rollout, oder nach der nächsten Änderung an
Templates oder Gates. Kennzahl ist nicht die Minute, sondern: Zahl richtig ·
null Fehlalarme · kein Quelltext gelesen.

## 3. `code-check`: jede registrierte Kennung braucht einen Zweig, nicht nur einen Schlüssel

**Was:** Heute prüft `code-check`, dass `[K1]/[S1]/[W1]/[N1]` als Schlüssel im
Code vorkommen. Ein Schlüssel ohne Zweig ist ein Label ohne Wirkung: `n1_pass`
berechnet, aber nichts hängt davon ab. Prüfung: der Schlüssel wird in einem
Vergleich oder einer Bedingung gelesen, nicht nur geschrieben (AST, wie die
Schema-Fakten).

**Beleg:** Opus-Audit (Probe 11): „[N1] war ein Label ohne Effekt — die
registrierte Regel ‚über 0.58 kein Inhaltswert' hatte keinen Zweig"; in der
Klassifikation über sechs Repos Klasse C (24 Befunde).

**Auslöser:** der nächste Bereich mit Nullbedingung, der durch `code-check`
geht — dann an echtem Code bauen.

## 4. `--draw N` im Mess-Skelett — die Wiederholungs-Ziehung

**Was:** Dieselben Aufrufe ein zweites Mal, eigene Ausgabedatei, eigener
Lauf, damit die Streuung der Zahl neben der Zahl steht. Opus hat es von Hand
gebaut; es ist universell.

**Beleg:** Zweite Ziehung derselben 24 Aufrufe gab 10/12 statt 11/12, drei
Items kippten — die Zahl trägt ±1 Item Rauschen, und ohne zweite Ziehung
sieht das niemand.

**Auslöser:** der nächste Modell-Lauf, dessen Zahl berichtet wird.

## Notiert, nicht geplant

- Die Vertragskarte im Bereichs-README hält die Agenten nicht vom Lesen des
  Standards ab (vier von vier lasen ihn trotzdem). Kein Werkzeugproblem;
  nicht weiter optimieren.
- Eine Stub-Zeile für `s1_*`/`k1_*` neben den TODOs im Zähl-Skelett (Sonnet,
  Probe 15) — erst, wenn das Zähl-Skelett Kennungen bekommt.
