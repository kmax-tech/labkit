# TODO — labkit

*Offene Werkzeugarbeit, jede mit Beleg, Auslöser und Prüfstelle. Stand
2026-10-06, nach der Usability-Reihe (`docs/usability/2026-10-05-trace.md`).
Reihenfolge ist Priorität. Nichts hier wird vorsorglich gebaut: jeder Punkt
wartet auf seinen Auslöser, und die Prüfstelle ist der Ort, an dem man ihn
sieht.*

## Reihenfolge (2026-10-06): die Evaluation steuert die Entwicklung

Behauptung, um die gebaut wird: *labkit detects violations of explicitly
encoded scientific intent across implementation, execution and reporting.*
Jede Prüfung gehört einer von drei Stufen an und sagt das in ihrer Meldung:
**guaranteed** (exakt, mechanisch) · **static evidence** (Indiz, Warnung) ·
**agent audit** (Semantik). Ein Lint wird nie als Beweis von Semantik
ausgegeben. Begründung, Stand der Technik und Paper-Rahmen:
`~/work/projects/labkit-paper/` (Paper-Plan, `stand-der-technik-kette.md`).

**Altlasten (2026-10-06): harte Änderungen statt Legacy-Pfade.** Code
ist für das aktuelle Format gebaut, klar und modular; alte Formate liest
er nicht mehr. Eine Formatänderung ist ein angekündigter Bruch
(`CHANGELOG.md`, Abschnitt „Breaking“, mit der letzten Version, die das
alte Format liest). Reproduktion läuft über den Pin: jedes Repo pinnt
labkit auf Tag oder Commit, sein eigener Commit plus diese Version
rechnet einen alten Lauf nach. Wir iterieren schnell; Kompatibilität ist
kein Ziel.

| Schritt | Inhalt | Stand |
|---|---|---|
| 0 | Stand der Technik, Positionierung | erledigt 2026-10-06 |
| 1a | Vertragskern, nur guaranteed (Teil von Punkt 7) | erledigt 2026-10-06, s. u. |
| Pilot | drei Benchmark-Fälle im Labor `~/projects/labkit-paper`, Matrix vorher eingefroren | als Nächstes |
| 1b/3 | nur, was der Pilot verlangt: Punkt 3 (static evidence), Punkt 6 `labkit audit` mit Punkt 1, Punkt 4 | wartet auf den Pilot |
| 2 | Benchmark voll | danach |
| 4 | Usability mit/ohne labkit (Punkt 2 erweitert) | eigene Ansage |
| R | Rollout in einem Release: Punkt 7 Schritte 0, 2–4, Punkt 8 (Kopffelder als Daten, Altpfade raus), Punkt 5, `AGENTS.md` von `lib init` gestempelt (Punkt 6; im labkit-Repo gibt es sie seit `61e90df`) | eigene Aufträge |

**1a gebaut (2026-10-06):** `labkit/promises.py` ist die eine Heimat des
Alphabets (C/A/B plus Altbuchstaben K/S/W/N in Prosa) und des
Versprechens-Blocks (```toml mit `[[promise]]`: id, key, sentence, scope,
constants). `runlog` zeichnet je Lauf Block-Hash und Scope-Hash je
Versprechen auf und verweigert einen kaputten Block vor `mkdir`;
`intent-check` prüft Text = Block, exakten Schlüssel und „der Lauf lief
unter diesem Block“; `recheck` verweigert das Nachrechnen über einen
veränderten Scope. Der Scope-Hash behauptet nur „deklarierte Region
unverändert“ (`tests/test_promises.py`, Klasse `ScopeHash`); seit
`01006c5` heißt er `declared_scope_sha`. Altbuchstaben gelten bis zum
Rollout weiter und fallen dann mit Punkt 8 weg — kein Stichtag, kein Alias
(Leitsatz „Altlasten“).

**Befund aus dem Durchstich, behoben (2026-10-06):** `code-check` meldete
einen falschen Blocker, wenn ein Skript die Schlüssel als Keyword-Argumente
übergibt (`r.metrics(c1_pass=…)`) — `code_ids` las nur String-Literale; mit
`k1_pass=` identisch, seit es den Check gibt. Ein Fehlalarm der Stufe
guaranteed bricht ihre Zusage, also sofort behoben (Keyword-Namen in
Aufrufen per AST, `tests/test_code_ids_keywords.py`). Bleibt als
Köder-Paar im Benchmark: Dict-Literal und Keyword-Argument, gleiches
Urteil.

**Durchstich mit Fehlerfällen (2026-10-06):** elf eingebaute Fehler plus
Zwilling, deterministisch, ohne Agent-Audit (Harness im Scratchpad, zieht
mit dem Pilot ins Labor). Vier Lücken der Stufe guaranteed gefunden und
geschlossen (`c8925a6`, `9c66178`, `6a7e4eb`, `c62c635`); K1 micro statt
macro, K4 Duplikat, A1 Anker ohne Wirkung, B10 Konjunkt fehlt sieht kein
mechanischer Check — die Aufgabe des Pilots.

## Klein, ohne eigenen Punkt

- [ ] **Push und Tags:** `git push && git push origin --tags`. Die Tags
      fehlen auf GitHub; die Pins der Repos (`git+file://…@v0.45.0`) gelten
      bis dahin nur auf diesem Rechner, und Reproduktion über den Pin
      (Leitsatz „Altlasten“) setzt erreichbare Tags voraus.
- [ ] **Pin für `thesis-dagidir`:** einziges labkit-Repo ohne Pin
      (Stand 2026-10-06); zöge beim nächsten Install die Brüche aus
      `CHANGELOG.md`.
- [x] `CHANGELOG.md` mit den Brüchen seit v0.45.0 (`b355333`).

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

**Zweiter Kandidat derselben Stufe (Durchstich 2026-10-06):** eine
Konstante des Versprechens-Blocks, die das Skript als Literal neu setzt
(`MIN_F1 = 0.5` statt `promises.constants(...)`). Exakt gefangen wird sie
heute nur, wenn der Lauf den Wert in seiner Config ablegt (`c62c635`);
das Literal im Code wäre ein Indiz. Ebenfalls erst bauen, wenn der Pilot
es verlangt.

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

## 5. Nur Englisch — die Bedingung für ein öffentliches labkit

**Entschieden (2026-10-06): nur Englisch, keine deutsche Fassung.** Was die
Maschine liest, ist englisch, und die Doktrin lesen vor allem Agenten; eine
abgeleitete deutsche Fassung wären zwei Wahrheiten, die driften (dieselbe
Begründung wie gegen Legacy-Pfade, Leitsatz oben). Deutsch bleibt die
Sprache der Unterhaltung und der Notizen im Faden — `AGENTS.md`: „Talk to
the user … in German.“

**Was:** Wird labkit öffentlich, muss alles, was ein Nutzer liest, englisch
sein. Das Paket ist es fast schon: Code, Templates, Feld-Guide,
Fehlermeldungen; Rest sind deutsche Suchwörter in `protocol_check.py`, die
mit Punkt 8 wegfallen, und zwei, drei Kommentare mit deutschen Zitaten. Deutsch sind die
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
2. **Einmal übersetzen, dann ist Englisch die Prägestelle.** Deutsch →
   Englisch per `labkit.llm` mit gepinntem Modell, §-Block für §-Block, mit
   Durchsicht jedes Blocks wie bei Code-Review. Danach wird die deutsche
   Vorlage in den dotfiles durch einen Verweis auf den englischen Master
   ersetzt — keine Parallelfassung.
3. **Scaffolder und Hausbegriffe englisch:** `CLAUDE.md.template` (235
   Zeilen), die deutschen Schnellstart-Texte und Hook-Meldungen im
   Scaffolder, die Hausbegriffe im Glossar der Protokolle
   (`Instrumentenprobe`, `Renderprobe` → instrument check, render check —
   der Code sagt es schon so).

~~Abgeleitete deutsche Fassung mit Hash-Stempel je Block, `lib sync
translate`, `lib init --lang en|de`~~ — gestrichen 2026-10-06 (nur
Englisch).

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
Mechanik (Umzug, Beleg-Schichten mit `lib scar`) ein bis zwei Nachmittage
im Scaffolder. Reihenfolge: 1 und 2 zusammen (die Schichtung der 42 Belege
ist Teil der Durchsicht beim Übersetzen), 3 nebenbei; `lib scar` und der
`finalize`-Vorschlag kommen zuletzt, weil sie erst mit Nutzern außerhalb
des Hauses etwas zu sammeln haben.

**Auslöser:** die Entscheidung, labkit zu veröffentlichen.
**Prüfstelle:** der erste Leser außerhalb des Hauses, oder eine
Cloud-Session, die einer §-Regel folgen soll — die 53 §-Verweise in den
Meldungen des Pakets zeigen bis dahin auf eine Datei, die nicht im Repo
liegt.

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

## 7. Englische Kennungen: `[C]` · `[A]` · `[B]` statt `[K]` · `[S]` · `[W]` · `[N]`

**Was:** Die Kennungen auf den Versprechen des Protokolls (§2.A1a) sind
Bezeichner, die die Maschine liest — also englisch, und jede trägt den
Fachterminus, den ein externer Leser kennt. Heute sind K (Kriterium) und
W (Weiche) deutsch, S (stop) englisch, N doppeldeutig. Drei statt vier:

| neu | steht für | Hauswort | Fachterminus | löst ab |
|---|---|---|---|---|
| `[C]` | criterion | Erfolgskriterium, je Teil | inference criterion; co-primary (intersection–union) | `[K]` |
| `[A]` | admissibility | Gültigkeitsbedingung | outcome-neutral condition (Registered Reports); `INADMISSIBLE` (preregister) | `[S]` und `[N]` |
| `[B]` | branch | Weiche | pre-specified conditional analysis; decision tree (IF-THEN) | `[W]` |

Warum N in A aufgeht: Kontrollen mit Sollwert (`shuffled` < 0,05, `anchor`
trifft 0,716) haben dieselbe Folge wie eine Stop-Regel — zeigen sie das
Erwartete nicht, gibt es kein Urteil (§2 „Nullbedingung / Anker“). Im Fach
sind positive controls und quality checks Beispiele für outcome-neutral
conditions. Die Baseline ohne Sollwert ist ein comparator und gehört in den
Text von `[C]`, nicht unter eine eigene Kennung. Die Pflicht „Kontrolle im
selben Lauf“ (§2.C6) bleibt: `[A2]` verlangt `a2_pass`, also muss der Code
die Kontrolle erzeugen.

Buchstabenwahl gegen Kollision: `ID_KEY` (`intent_check.py:50`) liest jeden
Schlüssel `<buchstabe><ziffer>[_…]` als Kennung. Gesperrt deshalb F (`f1`),
P (`p1`, precision@1), R (`r1`, recall@1/ROUGE-1), Q (`q1`, Quartil),
H (`h1`, hits@1; außerdem in Vorregistrierungen die Hypothese).

**Schritte:**

0. **Sofort und unabhängig:** Haus↔Fach-Tabelle im Master
   (`arbeitsstandard.md.template`, Zeilen „Stop rule“ und „Registrierte
   Weiche“): S ist kein *stopping rule* (das heißt im Fach: wann die
   Datenerhebung endet; preregister nutzt das Feld genau so) und kein
   *futility*, sondern eine outcome-neutral condition; Weiche ist
   conditional analysis, nicht „decision rule“ (zu breit — K und S sind
   auch Entscheidungsregeln).
1. ~~**labkit:** eine Heimat für das Alphabet~~ — **erledigt 2026-10-06**
   (`bbb5d9a`): `labkit/promises.py` ist die Heimat; `intent_check`,
   `recheck`, `code_check` und `finalize` importieren von dort.
   Kollisionstests in `tests/test_promises.py`. Altbuchstaben gelten bis
   zum Rollout weiter (Schritt 4).
2. **Template + Feld-Guide** (`experiment-protocol.md.template`,
   `protocol-field-guide.md`): Feld-Label „stop rule“ →
   „admissibility condition“, Schlüsselwörter für `protocol-check`
   nachziehen.
3. **Doktrin im Master:** §2.A1a, Abschnitt „Nullbedingung / Anker“,
   Haus↔Fach-Tabelle, `CLAUDE.md.template`, `measure-script.py.template`,
   `test-area.py.template`, `arbeitsstandard-init.py`, Agent
   `experiment-preflight`, Skill `run-experiment` (je auch die Kopie im
   `thesis-starter/`). Dann `lib sync pull` in die Repos.
4. **Bestand: 14 Protokolle** (counterfactual-worlds 8, uniagent 3,
   paper-organization 2, fallacy-datasets 1). Eingefrorene Protokolle sind
   Registrierungen; Umschreiben änderte, was registriert war.
   **Entschieden 2026-10-06 (Leitsatz „Altlasten“):** nicht anfassen und
   keinen Stichtag-Alias bauen — das neue labkit liest die alten
   Buchstaben nicht mehr; Repos mit eingefrorenen Altprotokollen bleiben
   auf ihrem Pin, bis dort neue Arbeit beginnt, und heben ihn dann.

**Entschieden 2026-10-06: als Daten** — TOML-Block statt YAML
(stdlib-only), gebaut in 1a (`docs/promise-block.md`). Die Abwägung, wie
sie vorher stand:

**Vorher offen — Kennungen in Prosa oder als Daten?**
Heute zieht `intent-check` die Kennungen per Regex aus dem Fließtext und
sieht nur Existenz, nie den Wert; Schwellen wohnen doppelt, als Konstante im
Skript (`MIN_YIELD`, `MARGIN`) und als Zahl im Protokolltext. preregister
registriert Vorhersagen als YAML mit auswertbarem Vergleich
(`comparison: "thompson - ucb < -20"`, `examples/bandit_study/prereg.yaml`);
`prereg` (reproducible-science) bleibt bei Markdown (`PREREG.md`, Hash über
den Text). Kandidat: das Protokoll bleibt Markdown, die Versprechen ziehen
in einen YAML-Block im Kopf (id, Art, Schlüssel, Konstante, ein Satz) —
das Skript liest die Konstante von dort, der Freeze-Hash deckt sie. Wenn,
dann im selben Zug wie die Umbenennung, sonst wandern 14 Protokolle zweimal.

**Beleg:** Diskussion 2026-10-06, Abgleich mit Registered-Reports-Guidelines
und dem Code von preregister, sealedlab, prereg —
`~/work/resources/dev-environment/vorregistrierungs-werkzeuge-vs-labkit.md`.
Die Kennungen sind die Übergabe-Einheit zwischen Agenten (§2.A1a); ein
externer Leser kann `[S]`, `[W]` heute keinem Fachbegriff zuordnen, und
„stop rule“ führt ihn auf den falschen.

**Auslöser:** Punkt 5 (Englisch als Master) oder das nächste neue Protokoll,
je nachdem, was zuerst kommt — Schritt 0 sofort. **Prüfstelle:**
`labkit/promises.py` — Schritt 1 ist erledigt; offen sind Schritt 0
und der Rollout (Schritte 2–4), bis Template und Feld-Guide `[C]/[A]/[B]`
stempeln.

## 8. Kopffelder als Daten: `[protocol]` im TOML-Block

**Was:** Die Felder, die eine Maschine liest — `Standard`, `Protocol id`,
`Type`, `Cost`, `Frozen before run`, `Preflight audit` — ziehen als
Tabelle `[protocol]` in denselben TOML-Block wie die Versprechen; ein
Parser (`tomllib`), exakte Werte, keine Schlüsselwort-Regex. Die
Prosafelder (Frage, Begriffe, Einheit, Ausschlüsse, Konfunde) bleiben
Markdown, weil ein Mensch sie schreibt und liest; ihre Prüfung erwartet
das exakte Label aus dem Template statt beliebiger Schlüsselwörter.
TOML, nicht YAML: stdlib-only.

**Bruch statt Altpfad (Leitsatz oben):** Der Regex-Kopf fällt weg, und
im selben Release die übrigen Altpfade (rund 45 Stellen in 8 Modulen,
Stand 2026-10-06): Altbuchstaben K/S/W/N, Läufe ohne `schema_version`,
Protokolle unter Standard 0.16 (`choose_legacy`). Voraussetzungen: die
Tags auf GitHub (`git push origin --tags` — die Pins zeigen heute auf
`git+file://`, gelten also nur auf diesem Rechner); `thesis-dagidir`
bekommt einen Pin (einziges labkit-Repo ohne). Getrennt zu entscheiden:
die Import-Fallbacks für vendorte Kopien (`except ImportError`) — kein
Format-Legacy, sondern die Versorgung der Studi-Repos; fallen sie weg,
brauchen neu gestempelte Studi-Repos einen Pin statt Kopien.

**Beleg:** Durchstich 2026-10-06 — ein handgeschriebenes `**Terms:**`
fiel durch, weil das Muster `terms of` verlangt; die Protokoll-ID hatte
drei eigene Regex-Kopien, die schon verschieden reagierten (Review
2026-10-06, behoben in `598f566`).

**Auslöser:** der Rollout von Punkt 7 (Template und Feld-Guide auf
`[C]/[A]/[B]`) — das Template ändert sich dann nur einmal.
**Prüfstelle:** `labkit/experiment-protocol.md.template`; solange der Kopf
dort Prosa-Felder stempelt, ist der Punkt offen.
