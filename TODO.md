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

## 5. Englisch als Master — die Bedingung für ein öffentliches labkit

**Was:** Wird labkit öffentlich, muss alles, was ein Nutzer liest, englisch
sein, und Deutsch wird eine abgeleitete Hausfassung. Das Paket selbst ist es
fast schon: Code, Templates, Feld-Guide, Fehlermeldungen — 7 Zeilen mit
deutschem Rest (`protocol_check.py` 6, `code_check.py` 1). Deutsch sind die
Doktrin und ihr Einstieg, und die liegen nicht im Paket, sondern in den
dotfiles: `arbeitsstandard.md.template` (1600 Zeilen, 77 §-Regeln, 42
Beleg-Absätze, 28 Zeilen mit Hauspfaden wie `~/work` oder `webis`),
`CLAUDE.md.template` (235 Zeilen) und 52 deutsche Zeilen im Scaffolder
(Schnellstart-Texte, Hook-Meldungen). Die Gates zitieren §-IDs, die ein
externer Nutzer heute nicht lesen kann — das ist der eigentliche Blocker.

**Plan, in Phasen:**

1. **Die Doktrin zieht ins Paket.** `labkit/docs/standard.md` wird der
   englische Master; `lib init` stempelt daraus. Die §-IDs bleiben die Anker;
   die Belege werden in die zwei Schichten getrennt (unten: allgemeines
   Beispiel ins Paket, datierter Hausbeleg in die Evidenz-Datei des Labors),
   Hauspfade werden zu Platzhaltern (`<work>` statt `~/work`).
2. **Einmal übersetzen, dann flippen.** Deutsch → Englisch per `labkit.llm`
   mit gepinntem Modell, §-Block für §-Block, mit Durchsicht jedes Blocks wie
   bei Code-Review. Danach ist Englisch die Prägestelle: Änderungen passieren
   dort, die deutsche Fassung `standard.de.md` wird abgeleitet.
3. **Abgeleitete Fassung mit Hash-Stempel.** Jeder §-Block der deutschen
   Fassung trägt den Hash seines englischen Blocks; `lib sync check` meldet
   „de: 3 Blöcke hinter en", `lib sync translate` übersetzt nur diese Blöcke
   neu. Übersetzung ist kein Diff: geänderte Blöcke werden beim Commit
   gelesen, der Stempel zeigt, welche.
4. **`--lang` wählt die Fassung, nicht ein Wort.** `lib init <repo> --lang
   en|de` stempelt `docs/arbeitsstandard.md` und den Merkzettel aus der
   gewählten Fassung; ein Repo hat eine Sprache. Scaffolder-Texte und
   Hook-Meldungen englisch, die 52 Zeilen.
5. **Paket-Rest:** die 7 Zeilen, dazu die Hausbegriffe im Glossar der
   Protokolle (`Instrumentenprobe`, `Renderprobe` → instrument check, render
   check — der Code sagt es schon so).

**Entschieden (2026-10-06): zwei Beleg-Schichten, und labkit lernt dazu.**
Jede Regel hat heute zwei Absätze — den Regeltext und `*Beleg (Datum,
Bereich):*` mit dem Unfall, der sie geprägt hat. Für die Veröffentlichung
werden daraus zwei Schichten derselben Stelle:

- **Allgemein (öffentlich):** je Regel ein anonymisiertes Beispiel, aus
  unserem Beleg abgeleitet — was schiefgeht, nicht wo. Reist mit dem Paket.
- **Haus (privat):** unsere datierten Belege mit Bereich und Zahl, als
  eigene Datei neben dem Standard (`standard.evidence.md` je Labor, nicht im
  Paket). Beim Stempeln rendert `lib init` beide Schichten unter die Regel,
  die Haus-Schicht nur, wo sie existiert.

Damit wird der Beleg zum **Feature für den Nutzer**: Ein fremdes Labor
startet mit den allgemeinen Beispielen und sammelt seine eigenen Unfälle an
derselben Stelle. Dafür ein Kommando `lib scar <§-ID> "<was passierte>"`,
das den Absatz datiert in die Haus-Schicht schreibt — und die Gates liefern
die Kandidaten: ein Blocker aus `code-check`, `finalize` oder einem Audit,
der sich als echt erwies, ist ein Beleg; `finalize` fragt am Ende „als Beleg
zu §x festhalten?". So ergänzt sich labkit selbst mit den Fehlern und
Problemen, die es gefangen hat, je Haus, und die allgemeine Schicht wächst
aus den Haus-Schichten, die ihre Nutzer beisteuern wollen.

**Beleg:** 15 Spuren heute lasen die deutsche Doktrin ohne Befund — die
englische Fassung braucht nicht der Agent, sondern der Mensch, der labkit
ohne dieses Haus benutzt. Die 42 Beleg-Absätze sind das Wertvollste am
Standard, weil sie jede Regel mit ihrem Unfall begründen, und verraten
zugleich, woran hier gearbeitet wird — darum zwei Schichten.

**Aufwand:** Erstübersetzung ein LLM-Durchlauf plus ein Lesetag; die
Mechanik (Umzug, Beleg-Schichten mit `lib scar`, Hash-Stempel, `sync
translate`, `--lang`) drei bis vier Nachmittage im Scaffolder. Reihenfolge:
1 und 2 zusammen (die Schichtung der 42 Belege ist Teil der Durchsicht
beim Übersetzen), dann 3, dann 4 — 5 nebenbei; `lib scar` und der
`finalize`-Vorschlag kommen zuletzt, weil sie erst mit Nutzern außerhalb
des Hauses etwas zu sammeln haben.

**Auslöser:** die Entscheidung, labkit zu veröffentlichen.
**Prüfstelle:** der erste Leser außerhalb des Hauses — vorher wird nichts
davon gebaut, weil zwei Fassungen bis dahin nur Pflege sind.

## 6. Harness-unabhängig — Codex und andere Agenten

**Befund (2026-10-06):** Die harte Schicht von labkit ist schon
harness-unabhängig: `runlog` (Freeze-, Leckage-, Detach-Riegel), die vier
Gates, `recheck`, der git-Pre-Commit-Hook — alles Code und git, kein Agent im
Spiel. Claude-spezifisch sind vier Stellen in der weichen Schicht:

| Stelle | heute | für jeden Agenten |
|---|---|---|
| Einstiegsdatei | `CLAUDE.md` (Claude Code liest sie) | `AGENTS.md` als gestempelte Datei (Codex, Cursor, Gemini-CLI lesen sie oder eine Variante); `CLAUDE.md` wird ein Symlink darauf. Der Scaffolder stempelt beide, `lib sync` hält eine. |
| Live-Hooks | `claude-hook pre-run/post-change` über `.claude/settings.json` (PreToolUse/PostToolUse-JSON) | bleiben als **Adapter** für Claude Code; der Riegel in `runlog` und der Pre-Commit-Hook sind die Schicht, die ohne Harness hält (§2.A8: „die Regel, die der Agent vergisst, steht im Riegel"). Ein zweiter Adapter je Harness nur, wenn er Hooks hat. |
| Audit-Agenten | `experiment-preflight`, `code-check` als Claude-Subagenten (`~/.claude/agents/*.md`) | `labkit audit <bereich> --mode preflight\|analysis`: die Audit-Prompts ziehen ins Paket, `code-check --bundle` liefert heute schon das Bündel, der Aufruf geht über `labkit.llm` mit beliebigem Backend (claude-cli, openai, ollama), **synchron mit Zeitlimit**, Befunde als Text zurück. Das ist zugleich die Mechanik für `promote` (Punkt 1). |
| Harness-Erkennung | `CLAUDECODE` in der Umgebung entscheidet den Detach-Riegel | generisch: `LABKIT_FOREGROUND_TIMEOUT_S` (gesetzt vom Harness-Adapter oder vom Nutzer) statt eines Harness-Namens; `CLAUDECODE` setzt ihn als Vorgabe. |

Das Modell-Backend für Experimente ist bereits frei (`models.toml`:
claude-cli, openai, ollama); ein Codex-Nutzer trägt sein Backend ein. Der
Usability-Harness ist dateibasiert (`TASK.md`, Log, Score) und läuft mit
jedem Agenten, der eine Shell hat — nur der Start des kalten Agenten ist
Sache der Session.

**Reihenfolge:** `AGENTS.md` zuerst (eine Stunde, kein Risiko), dann
`labkit audit` (ein Nachmittag, bringt `promote` mit), dann die
Harness-Erkennung. Die Claude-Hooks bleiben, wie sie sind.

**Beleg:** Alle 15 Spuren heute liefen in Claude Code; kein Teil der
Messung hängt daran außer dem Start — die Agenten lasen `CLAUDE.md`, weil es
so heißt, nicht weil sie Claude sind.

**Auslöser:** derselbe wie Punkt 5 — die Veröffentlichung — oder der erste
Mitarbeitende, der mit Codex im Labor arbeitet. **Prüfstelle:** `lib init`
stempelt ab dann `AGENTS.md`; bis dahin steht hier der Plan.
