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
| Pilot | drei Benchmark-Fälle im Labor `~/projects/labkit-paper`, Matrix vorher eingefroren | **erledigt 2026-10-06: `model-holds`** — Sonnet-Audit trifft A1, B10, K1 je 2/2, 0 Fehlalarme, Anker 2/2 (Lauf `2026-10-06T18-59-26_09a0`, Labor-Commit `6ac8b2e`); leichte Fälle, n = 2 — kein Beleg für echten Code |
| 1b/3 | nur, was der Pilot verlangt: Punkt 3 (static evidence), Punkt 6 `labkit audit` mit Punkt 1, Punkt 4 | wartet auf den Pilot |
| 2 | Benchmark — Stufe 1 + Katalog in gefüllten Proben (`count`, `judge`) | **Stufe erledigt 2026-10-06: `generalises`** — Sonnet findet 4/5 Haus-, 4/5 Katalogfälle, 0 Fehlalarme auf 22 stillen Ziehungen; B1 (positionaler Join) 0/3 übersehen (Lauf `2026-10-06T19-22-09_d352`, Labor `fe6a434`). Zweiter Auditor erledigt: `experiment-preflight` (Opus, Narbentabelle) findet B1 3/3, 5/5 + 5/5, 0 Fehlalarme (Labor `03`, Lauf `2026-10-06T19-56-51_8a20`) — **für `labkit audit` und `promote`: experiment-preflight, und WARNINGs sind Befunde zum Entscheiden**, denn B1 kommt nur als WARNING |
| 4 | Usability mit/ohne labkit (Punkt 2 erweitert) | eigene Ansage |
| D | Doktrin und Gerüstbauer ins Paket (Punkt 5; `AGENTS.md`-Vorlage aus Punkt 6 inbegriffen) | **erledigt 2026-10-12** — Phase 1 (0.77.0) und Phase 2 (0.78.0) gebaut; der Thesis-Starter bleibt Haus (entschieden 2026-10-12, s. Punkt 5). Auslöser war 2026-10-09: verwirrt den Autor selbst |
| R | Rollout in einem Release: die Pins der Labor- und Thesis-Repos heben, Punkt 7 Schritte 0, 2–4, Punkt 8 (Kopffelder als Daten, Altpfade raus) | **Kern erledigt 2026-10-12 (Tag `v0.85.0` auf GitHub):** die vier aktiven Labor-Repos auf dem Tag, je ein Commit; Reste unter Punkt 5, „Zeile R“ |
| Tokenkosten | messen statt schätzen — `llm.last_usage()`, `labkit-audit` druckt Prompt- und Output-Tokens, `agent_transcript.tokens` liest die Usage-Blöcke der Claude-Code-Transkripte (0.81.0, 2026-10-11) | **erledigt 2026-10-11.** Auslöser: 30 Transkripte (labkit, uniagent) summieren 7 Mrd. Cache-Read-Tokens, die alten Subagenten-Audits je 3,65 Mio., und keine labkit-Zeile sagte, was ein Aufruf kostet. Pilot `labkit-paper` Bereich 04 (`audit-on-reachable-code-holds`, Lauf `2026-10-11T14-00-57_071a`): die direkten Importe auf erreichbaren Code zu kürzen spart 0–16 % des Prompts (Median 8 % über 24 uniagent-Bereiche) — **an der Renderprobe gestoppt, kein Modellaufruf; LAB-103 The audit reads by declared scope, not by import graph bleibt.** Der Prompt ist groß, weil die Zahl fast den ganzen Agenten braucht (Bereich 19: 142 von 155 kB Importe erreicht), nicht wegen ungenutztem Code; Fixkosten je Audit ~69 kB (Instruktionen 9, zitierte Regeln 19, Protokoll 26, Index 15). Ein kleinerer Audit bräuchte eine andere Frage (Audit je Versprechen über seinen deklarierten Scope), kein Schnitt. Die Hauptsitzungen (Median 400–500 k Kontext je Aufruf) sind Sitzungshygiene, keine labkit-Aufgabe. |

**1a gebaut (2026-10-06):** `labkit/promises.py` ist die eine Heimat des
Alphabets (C/A/B plus Altbuchstaben K/S/W/N in Prosa) und des
Versprechens-Blocks (```toml mit `[[promise]]`: id, key, sentence, scope,
constants). `runlog` zeichnet je Lauf Block-Hash und Scope-Hash je
Versprechen auf und verweigert einen kaputten Block vor `mkdir`;
`intent-check` prüft Text = Block, exakten Schlüssel und „der Lauf lief
unter diesem Block“; `recheck` verweigert das Nachrechnen über einen
veränderten Scope. Der Scope-Hash behauptet nur „deklarierte Region
unverändert“ (`tests/test_promises.py`, Klasse `ScopeHash`); seit
`01006c5` heißt er `declared_scope_sha`. Altbuchstaben K/S/W/N sind seit
0.48.0 (`8ea59e9`) entfernt — nur noch erkannt und verweigert, kein
Stichtag, kein Alias (Leitsatz „Altlasten“). Seit 0.71.0 (`fd78941`)
verlangt `frozen = true` den Block, und `runlog` verweigert vor `mkdir`
einen Lauf, dessen Config eine registrierte Konstante nicht oder anders
trägt (Name = Config-Schlüssel, `promises.all_constants`).

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

- **Stand 2026-10-08, was labkit noch schuldet** (nach Standard 0.19,
  `labkit-params`, Runde 14/15):
  1. [x] **Modell-Provenienz, die labkit nicht sieht** — die Hotel-Bereiche
     14–17 zeichnen das aufgelöste Modell unter `config.judge` auf,
     `runlog` kennt nur `model`/`*_model`, `labkit-params` meldet „not
     recorded“. `finalize` warnt, wenn der antwortende Lauf Modellaufrufe
     hatte (`llm_retries`/`model_calls` in metrics) und kein Lauf seiner
     Herkunft `models_resolved` trägt; `labkit-params` zeigt ein Dict mit
     `alias`/`model`/`endpoint` unter fremdem Schlüssel als Indiz-Zeile.
     Beides static evidence, kein Legacy-Lesen (0.72.2).
  2. [ ] **`code-check`: jeder registrierte Schlüssel wird gelesen, nicht
     nur geschrieben** (Punkt 3 unten) — Bereich 17 als Zwilling.
  3. [ ] **Nachmessung `count`/`judge` mit n = 3** (Punkt 2 unten); die
     Navigationsaufgabe ist gemessen (Runde 14).
  4. [ ] **Standard 0.20** als ein Sprung — Kandidaten oben; Voraussetzung:
     eine Schreibprobe und Runde 16 (andere Person).
  5. [ ] `promote` (Punkt 1), `--draw N` (Punkt 4), harness-unabhängig
     (Punkt 6) — je bei ihrem Auslöser; Englisch (Punkt 5) jetzt, Zeile D.
  6. [ ] Thesis-Starter-Beispielprotokoll in der gestempelten Form (mit
     `[[promise]]`-Tabellen).
  7. [ ] **Stand eines Bereichs als eine Zeile aus Fakten** (Kaltleser
     2026-10-09 auf drei Repos: „aktueller Stand 4/10", der Leser
     rekonstruierte ihn aus Dateinamen und Git): Registrierung geschrieben ·
     Probe gelaufen · eingefroren · Läufe (antwortender Lauf) · Tests ·
     Antwort zitiert — alles Tatsachen, die `protocol_check`, `runs` und
     `area_tests` schon lesen. Projektion, keine zweite Wahrheit; Heimat
     wohl `runlog <area>` (eine Kopfzeile) oder `labkit-status`. Nicht
     bauen, bevor Runde 16 zeigt, dass die Zeile gelesen wird.
  8. [ ] **`labkit-params`: eine Skript-Kopie `MIN_F1` zu `min_f1` nennen**
     (Kaltleser 2026-10-09): die Indiz-Zeilen sehen nur Großbuchstaben, die
     Konstanten sind klein — die Kopie steht als eigene Zeile, die
     registrierte sagt nur „not recorded". Lookup auch unter `name.upper()`.
  Nicht nötig, geprüft: Schichten und eine Heimat je Frage
  (`tests/test_architecture.py`, `docs/architecture.md`), Hook mit vier
  Prüfungen, Vorlagen auf Stand 0.19. Die eigentliche Schuld liegt außerhalb
  des Codes: Runde 16 mit einer anderen Person — jede Vorlagenänderung von
  heute beruht auf n = 1.
- [x] **Bilanz eines Item-Laufs: `batch.Store.ledger` (2026-10-09, 0.76.0).**
      Auslöser: fallacy-dataset-generation, Bereich 01
      (`scripts/00_seed_proposals.py`, `lib/seed_review.audit_proposals`,
      Commit `8971386`) baute die Bilanz von Hand, weil `status` sie nicht
      hielt — Dubletten waren unsichtbar (behoben in 0.75.1) und nichts
      hielt den Lauf auf. Jetzt: jedes Eingabe-Item genau eine Zeile, keine
      fremde, keine ohne id, je Feld der erwartete Wert (`expect`, Konstante
      oder Funktion des Eingabe-Records); `require_complete()` im
      `with runlog.run(...)`-Block verhindert `completion.json` und die
      `runs.tsv`-Zeile. Stufe guaranteed. Was als gültige Antwort zählt
      (`problem`, `n_invalid`), bleibt im Experiment.
- [x] **Ein Läufer für den Preflight-Audit: `labkit-audit` (2026-10-10,
      0.79.0).** Auslöser: uniagent, 50 Audits als Claude-Subagent, je im
      Median 295 k frische Tokens und 33 Tool-Calls, der 1539-Zeilen-Standard
      88-mal gelesen; die Hauskopie `~/.claude/agents/experiment-preflight.md`
      war 2026-10-07 schon einmal vom Paket abgedriftet. Jetzt: die Hauskopie
      ist gelöscht, LAB-015 nennt nur das Kommando, der Prompt trägt nur die
      zitierten Regeln (LAB-015, LAB-017, LAB-004, LAB-050, ~18 kB statt 117 kB),
      im Modus `analysis` die ersten 50 und letzten 20 Zeilen jeder
      registrierten Output-Datei plus `metrics.json`. **Offen, nicht
      gemessen:** ob der eine Aufruf mit Opus dieselben Treffer liefert wie
      der Subagent (Pilot 2026-10-06 verglich Anweisungen, Läufer war der
      Subagent). Prüfstelle: die drei Benchmark-Fälle in
      `~/projects/labkit-paper`, Auftrag auf Ansage. Punkt 6, Zeile
      „Audit-Agenten": erledigt.
  - [ ] **Rollout (eigener Auftrag, anderes Repo):** Pin in
        fallacy-dataset-generation heben, `audit()` dort auf
        `store.ledger(..., expect={"prompt_sha": …, "input_sha": …})`
        umstellen, `audit_proposals` behält nur `unparsed`/`invalid`.
- [ ] **Kandidaten für Protokoll-Standard 0.20** (gesammelt 2026-10-08,
      Runde 15 und Review): `Result` → `Answer` umbenennen und `Question`
      als Pflichtfeld der Summary; `Answering run` als geschuldetes Feld
      (heute ungeprüfte Zeile, von `finalize` gehalten, wenn geschrieben);
      Weichenwerte als Daten in der Tabelle (`values = [...]` an `[B…]`),
      dann hält `finalize` `b1_branch` exakt daran — vorher ist jede
      Prüfung nur Indiz; Vorlage entschlacken (Frage je Feld, Rest im
      Field Guide), danach eine Schreibprobe. Alles zusammen in einem
      Sprung, weil jede Label- oder Stufenänderung die eingefrorenen
      0.19-Protokolle (uniagent 16, 17) vom `protocol-check` trennt.
- [x] **`labkit-params <area>` gebaut (2026-10-08, 0.70.0):** Auslöser
      Runde 13 („Protokolle, measure und runs mit Configs — wo anfangen"):
      die Werte des antwortenden Laufs in einer Tabelle, je Zeile Heimat
      und Stufe; Vollständigkeit des Records behauptet die Ansicht nicht
      (das hält der Bereichstest des Config-Objekts). Die Promise-Konstanten
      mit Config-gleichen Namen kamen mit 0.71.0 (`fd78941`): `runlog`
      verweigert vor `mkdir`, was nicht wie registriert in der Config steht.
- **Studi-Läufe ohne `requirements.lock`** (2026-10-07): `runlog` notiert die
  Umgebung eines Laufs über die Lock-Datei; der Starter legt keine an, also
  startet jeder Studi-Lauf mit „env unpinned" und die labkit-Version ist nur
  über den git-Verlauf von `requirements.txt` belegt. Vorschlag: die
  Installationsanleitung des Starters um `.venv/bin/pip freeze >
  requirements.lock` (mitcommitten) ergänzen. Stand: `docs/student-repos.md`.
- **labkit auf PyPI?** (2026-10-07, Entscheidung offen): stdlib-only, also
  problemlos veröffentlichbar; Studis bräuchten dann weder Repo-Zugriff noch
  Token (`labkit==0.49.1`). Dafür ein öffentliches Release. Solange nicht:
  GitHub-Repo für Studis lesbar halten, Tags pushen.

- [x] **Push und Tags** — erledigt 2026-10-08: v0.58.1 … v0.72.0 auf
      GitHub (`kmax-tech/labkit`), `v0.63.2` auf dem grünen Stand `30762d3`.
      uniagent hat kein Remote (Push dort offen).
- [ ] **Pin für `thesis-dagidir`:** einziges labkit-Repo ohne Pin
      (Stand 2026-10-06); zöge beim nächsten Install die Brüche aus
      `CHANGELOG.md`.
- [x] `CHANGELOG.md` mit den Brüchen seit v0.45.0 (`b355333`).

**Befunde des Pilots für das Werkzeug (2026-10-06):**
- Der Auditor arbeitet in den Kennungen des TOML-Blocks (`[C1]`, `[A1]`,
  ihre Sätze), obwohl der code-check-Prompt nur K/S/W/N nennt — die
  Kennungen tragen als Übergabe; den Prompt auf C/A/B ziehen (Punkt 7,
  Schritt 3).
- Warnungen streuen zwischen Ziehungen: ein echter, nicht eingebauter
  Fehler (`a1 = all(...)` bei leerer Ankerdatei trivial wahr) kam in 3 von
  16 Ziehungen, nie am Zwilling. Ein Audit-Lauf ist eine Ziehung — für
  `promote` (Punkt 1) mehr als eine.
- Zeilennummern in Befunden stimmen oft nicht; der Text trifft.
- Der in jedes Labor gestempelte Schutztest prüfte `runlog._is_alive` und
  brach mit `fc6e2fc`; Master in den dotfiles nachgezogen (`334e948`) —
  der angekündigte Bruch trifft genau so.

**Befunde der Benchmark-Stufe für das Werkzeug (2026-10-06):**
- **Fehler im Haus-Template:** `measure-script.py.template:143`, Null-Band
  `abs(null_acc - 0.5) <= 1 / max(len(null), 1)`. Registriert ist „0,5 ±
  ein Item“ inklusiv, in Gleitkomma fällt aber ein Item darüber durch (7/12:
  0,0833…37 > 0,0833…33), eines darunter besteht. Gefunden vom Audit in 7
  von 22 stillen Ziehungen (WARNING), nachgerechnet. Reparatur: in
  Item-Zählungen vergleichen statt in Anteilen. Betrifft jedes gestempelte
  Labor mit Null-Spur.
- **Erwartete Fallzahl als Versprechens-Konstante:** K4 (ein Fall doppelt in
  den Daten) sah der Audit nur, weil das Protokoll „12 cases“ registrierte
  und die Ergebniszeile 13 zeigte. Als Konstante im Block (`N = 12`) gegen
  `c<i>_n` gehalten, wäre das eine exakte Prüfung der Stufe guaranteed —
  `finalize` schweigt heute zu Recht, weil 13 die Eingabe *ist*.
- **B1 (positionaler Join) übersieht der günstige Audit 0/3** — den
  Originalfall fand `experiment-preflight` (Opus, Narbentabelle). Der
  nächste Benchmark-Schritt misst genau diesen Unterschied.

**Befunde aus dem Preflight-Audit von Bereich 03 (2026-10-06):**
- **Ein Pin-Wechsel ohne Versionssprung installiert nichts.** labkit steht
  seit vielen Commits auf `0.45.0`; `pip install -r requirements.txt` mit
  neuem Commit-Pin meldet „erfüllt“ und lässt den alten Code im venv. Erst
  `--force-reinstall --no-deps` zog `bd8cd29`. Abhilfe: Version je Release
  heben (Punkt R) — oder `runlog`s Pin-Drift-Prüfung, die den installierten
  Commit gegen die Lock vergleicht, auch beim Install-Schritt nutzen.
- `llm` ruft `claude -p` jetzt ohne Werkzeuge auf (`--tools ""`, `bd8cd29`).
- **Wer Audit-Berichte maschinell zählt, braucht eine Nullmessung.** Die
  ersten Zielmuster zählten Schlüsselwörter irgendwo in einer Befundzeile
  und trafen auch Berichte über korrekten Code (bis 7 von 17). Gilt für
  `promote` und `labkit audit` (Punkte 1, 6), sobald sie Befunde auswerten
  statt sie nur anzuzeigen: an die Stelle binden, Trefferquote auf stillen
  Fällen mitmessen. Umsetzung im Labor: `lib/audit_eval.py`,
  `lib/audit_targets.py`.

## Ablauf ins Paket: `run-experiment` als `docs/workflow.md`

**Was:** Der Ablauf des Skills `run-experiment` (Absicht → Pilot →
Validierung → Protokoll) zieht als englische `docs/workflow.md` ins Paket;
der Claude-Skill wird ein dünner Verweis darauf. Heute verlangt der Skill
noch `[K1]/[S1]/[W1]/[N1]`, kennt den Versprechens-Block nicht und liegt
in den dotfiles, wo eine Cloud-Session oder ein anderer Agent ihn nicht
sieht. **Beleg:** Pilot 2026-10-06 — der Skill-Ablauf musste für das neue
Format von Hand abgewandelt werden. **Auslöser:** Rollout mit Punkt 7
und 6. **Prüfstelle:** `docs/workflow.md` existiert.

**`labkit-audit` gebaut (2026-10-06, Punkt 6 teilweise):** der
experiment-preflight-Audit als Kommando über `labkit.llm`, Anweisungen im
Paket (`experiment-preflight.agent.md`), Exit 1 auch bei einer Warnung.
Echter Lauf auf Bereich 01 des Labors (Sonnet, 93 s) fand dieselben
Messschwächen wie der Opus-Audit von Bereich 03. Offen: `promote` (Punkt 1)
als dünne Hülle — `labkit-audit --mode analysis` plus Stempeln des
Protokollfelds nach den Entscheidungen; der Claude-Agent in den dotfiles
wird zur gestempelten Kopie der Paketdatei (Rollout).

## 1. `promote <bereich>` — der Beförderungs-Audit als Kommando

**Was:** Die Regel seit 2026-10-05 (LAB-015 Preflight audit before freezing): bei `Cost: seconds` kein
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

**Stand 2026-10-08, Navigationsaufgabe gemessen (Runde 14):** Haiku drei Läufe je Stand vor/nach den Umbenennungen von 0.62.0 — {2, 3, 4} gegen {3, 3, 5} von 5; ein Lauf trennt die Stände nicht, das Mittel über n = 5 (2,8 → 4,2) schon. Für `count`/`judge` offen.

**Was:** Je Aufgabe (`count`, `judge`) drei kalte Läufe auf dem aktuellen
labkit, Median der Wandzeit, und drei Bedingungen, die `usability score`
prüft: `equals the truth` (count: der gehaltene Mittelwert ist 3,5,
nachgezählt aus den gepflanzten Dateien) bzw. `within [0, 1]` plus `null
condition reported` (judge) · Fehlalarme = `gate`-Zeilen im Log, deren
Ursache kein Fehler des Agenten war (von Hand aus dem Bericht gezählt, Ziel
0) · `reads of labkit source / standard` = 0 (gezählt aus den `read`-Zeilen
des Logs, seit v0.44.0 in der Score-Tabelle). Erst damit steht der Stand auf
Daten; danach `lib sync pull` in counterfactual-worlds, fallacy-datasets,
fallacy-detection, paper-organization (eigener Auftrag, LAB-098 Separate core and rollout: Kern und
Rollout trennen).

**Beleg:** Zählung 4m20s, 6m01s, 9m58s auf drei Ständen — die Streuung
zwischen Agenten ist größer als die Wirkung der letzten Änderungen; drei
Einzelläufe trennen Stand und Agent nicht.

**Auslöser:** vor dem nächsten Rollout, oder nach der nächsten Änderung an
Templates oder Gates.

**Prüfstelle:** der Commit, der labkit oder einen Stempel ändert — seine
Nachricht nennt die drei Läufe oder sagt, warum nicht.

**Stand 2026-10-07 (labkit 0.52, `docs/usability/2026-10-07-remeasure.md`):**
6 von 6 Zahlen richtig und gebunden, Median count 1m16s, judge 2m23s, 0
Lesezugriffe auf Quelltext oder Standard. Zwei Fehlalarme gefunden und
behoben (`3e93af3`: Lock-Drift bei editierbarer Installation,
Platzhalter außerhalb des Sekunden-Schnitts). Offen vor dem Rollout: der
Scaffolder stempelt ohne `--cost` das Modell-Skelett auch für eine
Zählung (Haus-Vorlage, eigener Auftrag). — Nachtrag: der Stempel kam aus
der Probe (ohne `--cost` gestempelt), nicht aus dem Weg; Runde 2 mit dem
Stempel des Wegs: 6 von 6 richtig, Median count 0m56s, judge 2m04s, 0
Gate-Zeilen, ein Rest-Fehlalarm behoben (`6dacdc3`). Offen und nicht
labkit: Repo-`CLAUDE.md` (239 Zeilen) für die Sekunden-Spur, siehe
Abschnitt „Still open“ der Auswertung.
Runde 3 (Vorlagen nachgezogen, Messung mit Transkript): 6 von 6 richtig
und gebunden, Median count 1:21, judge 2:18 (gemessen, nicht geloggt), 0
Quelltext-Zugriffe, fünf von sechs füllen mit `protocol-fill`. Damit steht
der Stand auf Daten; als Nächstes der Rollout (eigener Auftrag).

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

- **Cloud-Leseprobe, Stand nach dem ersten Durchgang (2026-10-12).** Aufbau:
  Probe-Repo `kmax-tech/labkit-probe` (öffentlich — pip klont labkit nur
  anonym, also musste auch labkit öffentlich werden), Umgebung in
  claude.ai/code mit Setup-Skript (`cd "$CLAUDE_PROJECT_DIR"`, venv,
  `pip install -r requirements.txt`, `labkit-hooks install`), Netzwerk
  „Trusted", kein Schlüssel; der Agent pusht `probe-count`, lokal wird der
  Branch zu `probe-count-N`, `log.md` neben das Verzeichnis, `usability
  score`. Durchgang 1 (0.85.0): 3,5 richtig, gebunden, 4m27s, 3 read · 17
  run · 7 edit · 3 unsure · 3 gate, 0 Quelltext-Lesungen
  (`docs/usability/2026-10-12-cloud-fable-count-1.score.json`). Drei Befunde als
  Vorlagenfehler behoben (0.86.0: pytest, `evaluate_rows`, keine A2-Tabelle
  ohne Modell). Noch offen, aus dem Bericht des Agenten: (a) `protocol-fill
  --from-run <run_id>` schreibt Antwortzeile und Laufzeile aus
  `metrics.json` — die Rückschrift von Hand war die eine Stelle, an der der
  Agent brach (LAB-041 Generate numbers, don't retype them); (b) die
  `--help`-Texte von `finalize`, `intent-check`, `code-check` sagen bei
  seconds, dass nur die erste Zeile von `protocol-check --contract` zählt;
  (c) `runs.tsv` nach dem ersten Lauf ungetrackt, `.gitignore` nennt nur
  das Lock — der Stempel sollte sagen, dass der Index committet wird.
  Durchgang 2 (0.86.0): 3,5 richtig, gebunden, 2m28s, 4 read · 10 run · 7
  edit · 2 unsure · 2 gate (`2026-10-12-cloud-fable-count-2.score.json`). Drei
  weitere Vorlagenfehler behoben (0.86.1: `_prov` je Zeile, Lock mit pytest,
  `--show`/`--probe` nur mit Modell). Aus dem zweiten Bericht offen, als
  Entscheidungen: (d) bei `cost = "seconds"` ohne Modell C1/A1 und die
  Zulassungsbedingung weglassen — eine deterministische Zählung hat kein
  Kriterium, der Agent registrierte Tautologien; (e) `type = "exploratory"`
  bei seconds vorbelegen oder `protocol-fill` den TOML-Kopf setzen lassen;
  (f) die Feldführer-Prosa aus der gestempelten Vorlage in
  `protocol-check --guide` — ein Drittel der Sitzung war Lesen. Reihe: noch
  zwei Durchgänge auf 0.86.0 (n = 3), dann 0.86.1 stempeln.
  **Vorbehalt (2026-10-12):** der Cloud-Agent ist Fable 5.1, der stärkste
  verfügbare — die Zeiten sind eine Untergrenze, und „0 Quelltext-Lesungen"
  sagt bei ihm wenig über Sonnet oder ein lokales Modell. Was er an
  Vorlagenfehlern findet, gilt für jeden Agenten; ob die Korrekturen einem
  schwächeren Agenten reichen, zeigt erst dieselbe Reihe mit Sonnet (lokal)
  oder einem Ollama-Modell.
  Durchgang 3 (Stempel 0.86.1, venv aber 0.86.0 — die Cloud cacht das venv
  der vorigen Sitzung, `pip install -r` wechselte den Tag nicht): 3,5 richtig,
  gebunden, 2m26s, 3 read · 13 run · 6 edit · 0 unsure · 2 gate
  (`2026-10-12-cloud-fable-count-3.score.json`); ein Drittel der Zeit ging
  an die Lock-Abweichung aus dem Cache-Artefakt, nicht an labkit. Setup-Skript
  ab Durchgang 4: `rm -rf .venv` vor dem Bau. Neue Vorschläge des dritten
  Agenten: (j) `--check`, `protocol-check` und `finalize` als ein Kommando
  nach dem Lauf, der Hook wiederholt es nicht, wenn es gerade grün war; (k)
  das Mess-Skript schreibt die Antwortzeile selbst (= (a)); (l) ein Lauf ist
  `+dirty` auch bei nur ungetrackten Dateien — Frage, ob `??` zählen soll.
  Durchgang 4 (0.86.1 sauber, frisches venv): 3,5 richtig, gebunden, 2m09s,
  4 read · 9 run · 6 edit · 0 unsure · 1 gate
  (`2026-10-12-cloud-fable-count-4.score.json`). Behoben in 0.86.2: Pfad-
  beispiele in Code-Spannen galten `finalize` als Platzhalter. Neu
  notiert: (m) README dupliziert Frage und Vertrag des Protokolls; (n)
  `SOURCE`, `COUNT_FIELD`, `METRIC_KEY` aus den Argumenten von `labkit-init
  exp` stempeln, dann bleiben nur die drei Funktionen; (o) der Agent pusht
  zwei Branches, weil die Cloud-Sitzung einen eigenen vorgibt — Artefakt.
  Die Entscheidung (d), keine Versprechen-Tabellen bei einer Zählung, nennt
  jetzt jeder der vier Agenten als größten Schnitt.
  Durchgang 5 (Stempel 0.86.2, venv aber wieder 0.86.1 — das Setup-Skript
  baute das venv nicht neu, `pip install -r` wechselt den Tag eines schon
  installierten VCS-Pins nicht): 3,5 richtig, gebunden, 2m39s, 4 read · 10
  run · 6 edit · 1 unsure · 2 gate (`2026-10-12-cloud-fable-count-5.score.json`);
  ~40 s Lock-Abweichung aus dem Cache, der Rest wie Durchgang 4. **Stand der
  Reihe (n = 5, Fable):** 4m27s → 2m28s → 2m26s → 2m09s → 2m39s; Zahl und
  Bindung immer; unsicher 3 → 0/1, Gate 3 → 1/2; 0 Quelltext-Lesungen in
  allen. Was bleibt, sind Entscheidungen am Standard: (d) keine Versprechen-
  Tabellen und C/A-Felder bei einer Zählung, (f) Prosa der Vorlage hinter
  `--guide`, (p) Summary-Felder bei seconds auf eine Result-Zeile. Dazu ein
  Cloud-Punkt: ein VCS-Pin braucht `pip install --upgrade --force-reinstall
  --no-deps` oder ein frisches venv, sonst bleibt der alte Tag stehen.
  Durchgang 6 (0.87.0): 3,5 richtig, gebunden, 3m36s, 10 read · 15 run · 7
  edit · 1 unsure · 3 gate, 1 Quelltext-Lesung „weil das Gate es erzwang"
  (`2026-10-12-cloud-fable-count-6.score.json`) — der Schnitt 0.87.0 war
  unvollständig: `protocol-check` verlangte die Tabellen, `runlog` Kriterium
  und Zulassungsbedingung; behoben in 0.87.1 (eine Regel: wer keine Kennung
  registriert, schuldet keine Tabelle; das Sekunden-Gate ist die Frage).
  Durchgang 7 (Stempel 0.87.1, venv aber 0.87.0 — der Lauf zeichnet
  `drift:1` auf, labkit auf 79bda9b statt 20c98d3): 4m23s, 8 read · 13 run ·
  6 edit · 1 unsure · 3 gate, 1 Quelltext-Lesung
  (`2026-10-12-cloud-fable-count-7.score.json`). **Kein Beleg für 0.87.1:**
  die zwei Gates sind die von 0.87.0. Dreimal (3, 5, 7) hatte das Cloud-venv
  den Tag der vorigen Sitzung; `rm -rf .venv` im Setup-Skript war nicht
  wirksam oder nicht gespeichert — vor Durchgang 8 das Setup-Log der Sitzung
  lesen (pwd, pip, `labkit-check`-Zeilen), nicht raten.
  **Ursache gefunden (2026-10-12, im Browser nachgesehen):** die Cloud
  nimmt den Container der vorigen Sitzung wieder auf und überspringt das
  Setup-Skript, solange die Umgebung unverändert ist — Sitzungen 2, 4, 6
  (Umgebung kurz zuvor editiert) zeigen „Ran setup script", 3, 5, 7 nicht.
  Abhilfe im Probe-Repo: ein SessionStart-Hook in `.claude/settings.json`
  prüft `labkit-check` und baut das venv sonst aus dem Pin neu; läuft vor
  dem ersten Schritt des Agenten, nicht im Log.
  Durchgang 8 (0.87.1, venv passend, `drift:0`): 3,5 richtig, gebunden,
  2m20s, 6 read · 14 run · 6 edit · 1 unsure · **0 gate**, 0 Quelltext-
  Lesungen (`2026-10-12-cloud-fable-count-8.score.json`) — der erste Beleg
  für den Schnitt: kein erfundenes Kriterium, keine Tabelle, kein Gate.
  Übrig laut Agent: der Feldführer ist 480 Zeilen und `--guide` druckt nur
  den Pfad (ein Drittel der Zeit), `finalize` warnt beim ersten Durchlauf
  immer über das noch ungetrackte `output/` (zwei Durchläufe), und die
  Rückschrift von Hand (Idee (a)). Der eine Fehlschlag im Log war ein `wc -l`
  auf Verzeichnisse, kein Gate.
  Durchgang 9 (0.87.1, `drift:0`): 3,5 richtig, gebunden, 2m06s laut Log,
  0 Gate-Treffer außer der README-Warnung von `finalize`, 0 Quelltext-
  Lesungen (`2026-10-12-cloud-fable-count-9.score.json`). Neu genannt: (q)
  `protocol-check --contract` druckt bei seconds die volle Form, obwohl nur
  die erste Zeile zählt — bei seconds nur die geschuldete Zeile drucken;
  (r) der README-Vertragsabsatz ist ein Platzhalter, den erst `finalize`
  nach dem Lauf meldet — bei seconds weglassen oder in `protocol-fill --list`
  aufnehmen; (s) Terms/Unit/Exclusions bei einer Dateizählung wiederholen
  `visible()` in Prosa.
  Durchgang 10 (0.87.1, `drift:0`): 3,5 richtig, gebunden, 3m42s (ein
  eigener Edit-Fehlschlag, zwei finalize), 0 gate
  (`2026-10-12-cloud-fable-count-10.score.json`). **Reihe abgeschlossen:**
  n = 3 auf 0.87.1 — 2m20s · 2m06s · 3m42s, Median 2m20s, 0–1 Gate-Zeile, 0
  Quelltext-Lesungen; Spur: `docs/usability/2026-10-12-cloud-fable.md`.
  **Sonnet 5.5, ein Durchgang (0.87.1):** 3,5 richtig, gebunden, 0m42s laut
  Log (spät gestartet, Untergrenze), 4 read · 7 run · 4 edit ·
  0 unsure · 0 gate, 0 Quelltext-Lesungen
  (`2026-10-12-cloud-sonnet-count-1.score.json`); SessionStart-Hook hat das
  venv neu gebaut. Nennt dieselben fünf Schnitte wie Fable; neu: „Result"
  ist zweideutig zwischen Summary-Zeile und Result-Abschnitt (t).
  **Haiku 5.5, ein Durchgang (0.87.1):** 3,5 richtig, gebunden, 2m10s,
  14 read · 19 run · 5 edit · 1 unsure · 0 gate, 0
  Quelltext-Lesungen (`2026-10-12-cloud-haiku-count-1.score.json`) — doppelt
  so viele Lese- und Laufschritte wie Sonnet, jeder Platzhalter ein eigener
  Umweg; die Rückschrift der Zahl von Hand in drei Zeilen ist der erste
  Punkt auf seiner Liste. Damit kommen alle drei Modelle ohne Quelltext zur
  gebundenen Zahl; die sechs offenen Schnitte sind modellunabhängig.
  **Entschieden und gebaut 2026-10-12 (0.87.0):** (d) keine Versprechen-
  Tabellen und kein Kriterium bei einer Zählung, (f) einzeilige Platzhalter,
  Langform im Feldführer, (p) Summary bei seconds = Result-Zeile. Prüfstelle:
  die nächste Cloud-Reihe auf 0.87.0 — erwartet unter 2 Minuten und null
  erfundene Kriterien.
  Nachtrag aus den Beobachtungen des zweiten Agenten: (g) `log.md` im Repo
  macht jeden Lauf `+dirty` (der Patch ist nur das Log) — beim nächsten
  Stempel `log.md` in die `.gitignore` und im TASK `git add -f log.md` am
  Ende; (h) Post-Change-Hook, `protocol-check` und Pre-Commit drucken
  dieselbe Meldung dreimal — laut, nicht falsch, Dedupe später; (i) `Raw
  output` ohne Modell und die `--bundle`-Meldung bei seconds: behoben in
  0.86.1.

- **Englische Namen für die Notiz-Verzeichnisse** (2026-10-12) — das Paket
  stempelt und liest `notes/theorie`, `notes/messung`, `notes/results`
  (`scaffold.LAB_DIRS`, `notes_check`, `claude_hooks`, LAB-082 In `notes/messung/`), die
  Glossar-Note heißt seit heute `terms.md` (war `begriffe.md`: ein
  Bezeichner, den der Standard zitiert, reist englisch, LAB-072 Identifiers travel in English).
  Die Verzeichnisse sind ein angekündigter Bruch mit Rollout (Regeltext,
  `notes-check`, Hook, alle Labore per `git mv`), kein Nebenbei. uniagent
  und finance-discourse tragen `begriffe.md` → beim Rollout R umbenennen.

- ~~**Aus der Audit-Auswertung uniagent — vier Hebel**~~ **alle vier gebaut
  2026-10-12 (0.85.0): `labkit/findings.py` + Station 2b in `preflight`;
  `code_check.stamp_coverage_findings`; Narbenzeile „Criterion fails on
  noise“ + Absatz „What no audit sees“ in LAB-015; `audit.early_for_tier`.
  Prüfstelle: der nächste Audit-Zyklus in uniagent — zählt der Ertrag je
  Klasse aus den `audits/*.toml`, und bleibt die Stempel-Warnung still, wo
  sie still sein soll?** Ursprünglicher Eintrag (2026-10-12, 23 Preflight-
  und 21 Analysis-Audits, 46 Leseproben):
  1. **Audit-Befunde als Daten, nicht als Prosa.** Heute landet ein Audit als
     eine lange `preflight_audit`-Zeile; was „angenommen" oder „eigener
     Auftrag" war, verschwindet darin. uniagent: der in 16 vertagte Befund
     (Wortlaut der Referenzzeile nicht im Fingerabdruck) biss in 17; derselbe
     Befund „Skript von 14 außerhalb des Stempels" dreimal angenommen; 13 von
     44 Audit-Zeilen enden mit angenommen/verworfen. `labkit-audit` schreibt
     seine Befunde je Bereich als Datei mit Status (fixed / accepted /
     deferred / rejected + Grund); `preflight` listet offene deferred-Befunde
     des Repos; der Ertrag eines Audits wird damit zählbar statt von Hand
     gelesen. Stufe: guaranteed für die Buchführung, der Befund selbst bleibt
     Agent-Audit.
  2. **Static evidence: Importe außerhalb jedes deklarierten Scopes.** Fünfmal
     in uniagent (15, 16, 17: Skript von 14; 22: `predict.py`; 23:
     Leser-Module) meldete erst der Agent, dass Code, den das Mess-Skript
     importiert, in keinem Scope liegt. Das ist mechanisch: `code-check`
     warnt, wenn ein Repo-Modul im Importgraphen des Mess-Skripts von keinem
     `[[promise]].scope` gedeckt ist. Der Pilot-Beleg, auf den Punkt 3
     wartet, ist damit da.
  3. **Narbentabelle, neue Zeile: Kriterium ohne Rauschgrenze.** Bereich 26:
     [C3] zählte jede Ablehnung, auch durch eine Regel, die die Änderung nicht
     berührt; eine Einzelstimme in einem Durchgang kippte das Kriterium, das
     Preflight (1 Blocker zur Renderprobe) sah es nicht, nach dem Freeze blieb
     nur Offenlegung. Zeile für LAB-015 und die experiment-preflight-
     Anweisung: „ein C auf Modellausgaben nennt seine Rauschgrenze (Mehrheit
     über n Ziehungen, nur Ablehnungen mit Beteiligung der geänderten
     Komponente) oder sagt, warum nicht" — Bezug LAB-036 Validate, don't trust a single run.
  4. **Zahl der Audits folgt der Kostenstufe, mechanisch.** Bereich 01 bekam
     bei Cost seconds zwei Preflights und ein Analysis-Audit; das Protokoll
     sagt selbst, eines nach dem ersten Lauf hätte gereicht. `labkit-audit`
     warnt bei `cost = "seconds"` ohne vorhandenen Lauf: der Lauf ist die
     billigere Probe (LAB-017 The number of audits follows the cost tier).
  Nicht lösbar durch ein Audit, und so in LAB-015 festhalten: Modellverhalten
  (16 und 24: Grenze ohne Geltungsbereich; 14 und 17: Zitat aus der Tabelle)
  fand in uniagent nie ein Audit, immer der Lauf — die Probe dafür ist die
  Instrumentenprobe an Randfällen, nicht mehr Audit.

- ~~**`labkit-check`: ist dieses Repo auf Stand?**~~ **gebaut 2026-10-12
  (0.84.0, `labkit/repo_check.py`)** — Auslöser: Frage beim Rollout R; vorher drei getrennte Prüfungen: `labkit-hooks check` (Hook
  gegen Installation), `lib init . --sync check` (geerbte Blöcke, dotfiles),
  `python -m labkit.rules refs` (Regelverweise). Niemand prüft Pin gegen
  Installation (in allen vier aktiven Repos lag die Installation hinter dem
  Pin) oder zeigt an, dass das Master-Repo einen neueren Tag hat. Ein
  Kommando, fünf Zeilen: Pin · installiert · neuester Tag · Hook · Verweise;
  nur Anzeige, der Pin wird weiter bewusst gehoben. Auslöser: der Rollout
  zeigt, dass die drei Einzelprüfungen vergessen werden.

- **Audit je Versprechen über seinen deklarierten Scope** (2026-10-11):
  der Preflight-Audit liest heute den ganzen Bereich samt direkten Importen
  (Bereich 19 in uniagent: 248 kB, davon 142 kB erreichter Agentencode);
  der Schnitt auf erreichbaren Code brachte nur 8 % (labkit-paper Bereich
  04, Zeile T). Der andere Hebel: ein Aufruf je `[[promise]]` mit Protokoll,
  Satz, Konstanten und nur den Dateien seines `scope` — kleinere Prompts,
  Befunde adressiert je Kennung, aber kein Blick auf das Zusammenspiel der
  Versprechen. Auslöser: wenn der Audit je Bereich spürbar teurer wird als
  der Lauf, den er prüft, oder ein Befund „über Versprechen hinweg" im
  Benchmark fehlt. Prüfstelle: labkit-paper, dieselben 34 Fälle wie Bereich
  03 — findet der Audit je Versprechen B1 noch?
- **Präfixe der Regelkennungen englisch — gemacht (2026-10-11, 0.82.0):**
  `AS`/`HS`/`CS` waren Abkürzungen deutscher Namen; jetzt `LAB` (ausgelieferter
  Laborstandard), `LOCAL` (Regeln eines Hauses, eigenes Register), `CODE`
  (Coding-Regeln), Nummer für Nummer, hart und ohne Alias oder Altleser — vor
  der Veröffentlichung ist das billig, danach Altbestand. Die sieben
  Hausnummern (2, 70, 73, 78, 80, 81, 99) sind Lücken im LAB-Ledger und leben
  als LOCAL-nnn im Haus-Register. Eingefrorene Protokolle, Snapshots und
  historische Berichte behalten ihre alten Kennungen. Rollout: dotfiles
  erledigt (Master-Standard, Registry, CLAUDE.md, Agenten, Scaffolder, Hook;
  dotfiles 803db72), labkit-paper erledigt (Pin 0.82.0, lebende Dateien;
  Bereiche 01–03 und Traces bleiben alt; `docs/arbeitsstandard.md` für den
  Sync „diverged", bis Zeile R den Pin auf ein Tag hebt), uniagent erledigt
  (Pin 0.82.0; CLAUDE.md, Standardkopie, Begriffsnote, Style-Guides). Alt
  bleiben dort die 23 eingefrorenen Protokolle, sechs gestempelte
  Mess-Skripte und zwei `CS-016`-Zitate in `src/measure/` — die liegen im
  Audit-Scope von 19 Bereichen, eine Änderung verschiebt jeden Stempel;
  umstellen beim nächsten Re-Audit dieser Module.
- **Prüfer auf einem lokalen Modell** (2026-10-11): `labkit-audit` läuft
  schon heute mit jedem `models.toml`-Alias (`--model`); seit 0.83.0 schneidet
  Ollama einen langen Audit-Prompt nicht mehr still ab (`num_ctx`,
  `PromptTruncated`). Offen: (a) `code-check` ist noch ein Claude-Subagent
  (`model: sonnet`) und läuft nur auf dem Modell der Session — als
  `labkit-audit --mode code-check` (das Bündel inline, ein Aufruf über
  `labkit.llm`) liefe er auf jedem Backend; das ist die Zeile „Audit-Agenten"
  in Punkt 6, kein eigener Punkt. (b) Bevor ein lokales Modell als Prüfer
  zählt: über die Benchmark-Fälle von labkit-paper laufen lassen, Fangquote
  neben Opus. Der Agent, der einen Lauf startet und überwacht, bleibt die
  Session; Überwachen braucht kein LLM (ferry + Skript). Auslöser: wer einen
  Prüfer ohne Claude-Abo braucht (Studierende, Veröffentlichung).
- Die Vertragskarte im Bereichs-README hält die Agenten nicht vom Lesen des
  Standards ab (vier von vier lasen ihn trotzdem). Kein Werkzeugproblem;
  nicht weiter optimieren — aber zählen (`reads of labkit source / standard`
  in `usability score`), damit sichtbar bleibt, ob es sich ändert.
- Eine Stub-Zeile für `s1_*`/`k1_*` neben den TODOs im Zähl-Skelett (Sonnet,
  Probe 15) — erst, wenn das Zähl-Skelett Kennungen bekommt.
- Allgemeine Beispiele je Regel im Paketstandard und `lib scar <LAB-nnn>`
  (datierter Beleg in die Haus-Schicht, Kandidaten aus echten Blockern) —
  aus Punkt 5 herausgenommen am 2026-10-09; erst, wenn ein Labor außerhalb
  des Hauses Belege sammelt.

## 5. Doktrin und Gerüstbauer ins Paket — nur Englisch

**Entschieden (2026-10-06): nur Englisch, keine deutsche Fassung.** Was die
Maschine liest, ist englisch, und die Doktrin lesen vor allem Agenten; eine
abgeleitete deutsche Fassung wären zwei Wahrheiten, die driften. Deutsch
bleibt die Sprache der Unterhaltung und der Notizen im Faden.

**Entschieden (2026-10-09): jetzt, nicht erst bei der Veröffentlichung.**
Regeln, Vorlagen und Werkzeuge liegen an vier Orten (`docs/architecture.md`,
„Where what lives“), und das verwirrt schon den Autor. Zuordnungsregel: was
ein fremdes Labor braucht, liegt in labkit; was nur dieses Haus betrifft, in
den dotfiles. Daraus:

- **Doktrin teilen.** Labor-, Schreib- und Notationsregeln ziehen englisch ins
  Paket; die Haus-Kapitel (Wissensseite, `~/work`, Paper-Port) bleiben deutsch
  in den dotfiles.
- **Vom Gerüstbauer zieht der Labor-Teil um** (Repo, Bereich, Thesis); der
  Faden-Teil (`~/work`, accessio) bleibt.
- **Coding-Style bleibt in den dotfiles** (er gilt für jeden Code); labkit
  behält die gestempelte Kopie.
- **Labor-Repos bekommen einen Verweis statt einer Kopie:** der Standard reist
  mit dem Pin. Der größte Teil von `sync` entfällt, statt portiert zu werden.

**Befund (2026-10-09):** 26 Regelkennungen im Paket, 9 davon in
Laufzeitmeldungen (`preflight`, `code_check`, `runlog`, `claude_hooks`,
`protocol_check`); ihr Text liegt nicht im Repo, und ob es sie gibt, prüft
nur `check_refs` in den dotfiles. `labkit-audit` liest den Standard aus der
Kopie des Labors (`audit.py`), `usability stage` Vorlagen und Gerüstbauer aus
`~/.claude/resources` (`usability.py`). Die Vorlage hat 1513 Zeilen und 102
Regeln, die Belege liegen schon getrennt (`arbeitsstandard.evidence.md`), etwa
27 datierte Fragmente stehen noch im Regeltext.

**Grundsätze:**

- **labkit vergibt alle LAB-Nummern.** `labkit/docs/rules.tsv` führt alle
  Kennungen, Hausregeln mit Status `house` und ohne Titel. Neue Hausregeln
  heißen in den dotfiles `LOCAL-nnn` und behalten ihre Nummer.
- **Nichts wird gelöscht.** Im dotfiles-Register bekommen umgezogene Zeilen
  den Status `moved:labkit` (`check_ledger`: „retire it, never delete“).
- **Eine Heimat für den Parser:** `labkit/rules.py`. Die dotfiles rufen ihn als
  Kommando aus dem labkit-venv auf und behalten keine Kopie.

### Phase 1 — Standard schneiden, übersetzen, prüfbar machen (0.77.0, Breaking)

**Erledigt 2026-10-10** (labkit `a32dc51`…`1584579`, Version 0.77.0, noch
nicht getaggt; dotfiles `4405df7`, `7f271bc`). Abweichungen vom Plan: das
Schnitt-Inventar `docs/standard-cut.tsv` bleibt als Beleg des Schnitts
(der Übersetzungsbericht zitiert es), die Seite trägt jetzt `rules.tsv` als
Status; `check_refs` liest eine Kennung in Inline-Code oder als nacktes
String-Literal als Argument, nicht als Zitat, und überlässt `moved:*`-Zeilen
dem Ledger, in das sie umgezogen sind.

labkit- und dotfiles-Teil landen am selben Tag, sonst werden die
dotfiles-Hooks rot.

1. **Schnitt** (erledigt 2026-10-09): `docs/standard-cut.tsv`, alle 102
   Kennungen mit genau einer Seite — 95 `package`, 7 `house` (LOCAL-002, LOCAL-070,
   LOCAL-073, LOCAL-078, LOCAL-080, LOCAL-081, LOCAL-099). Geprüft: erkannte Köpfe =
   Register, package ∩ house = ∅, package ∪ house = alle. LAB-071/072 sind aus
   2H herausgelöst; LAB-049 wird harness-neutral (überwachte
   Hintergrundausführung), LAB-074/076 auf research record bzw. documented
   limitation verallgemeinert, die Schreibregeln (LAB-089, 093, 094, 100, 101)
   gelten für Berichte, Protokolle und Agentenantworten, nicht für private
   Notizen. Ohne Kennung bleiben im Haus: Haus-Glossar, webis-Cluster,
   Geltung. Die Haus↔Fach-Tabelle kommt ins Paket (2026-10-09) als „Labkit
   terms and established terminology“ — sie kennzeichnet die Prägungen
   maßgeblich; das leere Kern-Glossar ist ein Gerüstbaustein und zieht in
   Phase 2 nach `labkit/templates/`. Das Blockmanifest
   `docs/standard-blocks.tsv` (jede Quellzeile in genau einem Block, Seite,
   Zielposition) ist entfallen, seit `rules.tsv` die Seite als Status trägt
   (2026-10-10; letzter Stand labkit `223e2fa`).
2. **Inline-Belege raus** in die private Evidenz-Datei. Die Narbentabelle zu
   LAB-015 Preflight audit before freezing bleibt als Tabelle von Fehlerklassen ohne Datum, der Audit braucht
   sie.
3. **Übersetzen:** Einmal-Skript außerhalb des Pakets, je Regelblock ein
   Sonnet-Aufruf über `labkit.llm`, Rohausgabe aufbewahrt. Ein fester
   Übersetzungsvertrag je Aufruf: normative Stärke erhalten (must / should /
   may nicht angleichen); Kennungen, Aliase, Code, Pfade und Fachbegriffe
   unverändert; nichts ergänzen oder verbessern; feste Terminologieliste;
   Kapitelüberschrift und unmittelbarer Kontext mitgesendet; Ausgabe nur als
   vollständiger Regelblock. Danach ein Opus-Konsistenzreview des
   zusammengesetzten Standards (ausgelassene Einschränkungen, wechselnde
   Begriffe, Widersprüche zwischen Regeln) und die Durchsicht Block für Block
   durch den Autor (etwa ein Lesetag).
4. **labkit:**
   - `labkit/docs/standard.md` und `labkit/docs/rules.tsv` (Spalten
     `id alias title status`, Titel englisch, `alias` behält die §-Kennungen),
     in `package-data`.
   - `labkit/rules.py` (Schicht 1): `RULE_HEAD_RE`, `check_registry`,
     `check_ledger`, `check_refs` aus `arbeitsstandard-init.py`, erweitert auf
     die Präfixe `LAB`, `LOCAL`, `CODE` und die Status `active`, `retired`,
     `moved:*`. Vertrag:
     ```
     python -m labkit.rules check
     python -m labkit.rules check --standard PATH --registry PATH --prefix LOCAL --prefix LAB
     python -m labkit.rules ledger BEFORE AFTER
     python -m labkit.rules refs --status active PATH…
     python -m labkit.rules show LAB-015
     ```
     `show` auf eine Hausregel sagt laut „house rule; text is not distributed“.
   - `tests/test_rules.py`: Köpfe = Register; jede LAB-Kennung in den lebenden
     Dateien (`labkit/`, `README.md`, `AGENTS.md`, `docs/*.md`; nicht
     `CHANGELOG.md` und `docs/usability/`, das sind historische Belege)
     existiert, ist aktiv und trägt ihren Namen; Zwilling: korrekter Verweis
     passiert. CODE-Verweise nur auf Form (CODE-Register liegt in den dotfiles).
   - Alle Meldungen und Docstrings mit den englischen Namen; fehlende Namen
     ergänzen (`preflight.py`, `finalize.py`).
   - `audit.py` liest den Paketstandard; `experiment-preflight.agent.md` zeigt
     auf dessen Abschnitte. `code_check.SEVERITY_LEGEND` (Handkopie) wird aus
     `standard.md` geschnitten — erst ein Test, der die Gleichheit zeigt.
   - Weitere Leser: `recheck.py`, `protocol-field-guide.md`,
     `usability-task-*.md.template`, Fixtures in `tests/test_audit*.py`, die
     Lese-Metrik in `usability.py` und `tests/test_agent_transcript.py` (zählt
     „arbeitsstandard“; ohne Anpassung fällt sie still auf 0).
   - `CHANGELOG.md` Breaking: Regelnamen englisch, audit liest den
     Paketstandard; letzte Version, die `docs/arbeitsstandard.md` liest: 0.76.0.
   - `docs/architecture.md`: „Where what lives“, „Known gap“, Schicht `rules`.
5. **dotfiles:**
   - `arbeitsstandard.md.template` schrumpft auf die Haus-Kapitel (deutsch),
     Kopfzeile „Labor-Regeln: labkit `docs/standard.md`“.
   - Register: umgezogene Zeilen `moved:labkit`.
   - pre-commit ruft nur noch `~/projects/labkit/.venv/bin/python -m
     labkit.rules` (`check` Haus, `ledger` gegen HEAD, `refs` über die
     gestagten Dateien); `--register`, `--refs` und die Parserfunktionen
     fliegen aus `arbeitsstandard-init.py`. Fehlt das venv, bricht der Hook laut
     ab und nennt das Setup-Kommando.
   - Leser der alten Namen nachziehen: `~/.claude/CLAUDE.md`,
     `CLAUDE.md.template`, Skills `run-experiment` und `research-repo-init`
     (widerspricht heute `docs/student-repos.md`), Agents `experiment-preflight`
     und `code-check`, `~/work/CLAUDE.md`.
   - **Schutz für alte Pins:** `--sync pull` von `docs/arbeitsstandard.md`
     verweigert laut, wenn das Repo labkit unter 0.77 pinnt („erst den Pin
     heben — Rollout“); sonst bekäme ein alter Audit still einen Standard ohne
     Narbentabelle.

### Phase 2 — Labor-Teil des Gerüstbauers ins Paket (0.78.0)

**Stand 2026-10-10:** `labkit-init lab` und `labkit-init exp` gebaut
(0.78.0), Vorlagen in `labkit/templates/`, `usability stage` ohne
`~/.claude`. Die `AGENTS.md`-Vorlage ist eine knappe englische Fassung der
beiden Spuren, keine Übersetzung der 258 Zeilen `CLAUDE.md.template` — der
Merkzettel und die Übergaben bleiben Haus. **Entschieden 2026-10-12: der
Thesis-Starter bleibt Haus** (`local-init.py --thesis`, bis 2026-10-12
`arbeitsstandard-init.py`). Er ist
die Fassung des Hausstandards für die Studierenden dieses Hauses —
Webis-Vorlesungslinks, eingefrorene Lauf-Snapshots mit Autor-Pfaden, eine
Skill-Kopie; im Wheel bräche er den Hausmarker-Test. Kein `labkit-init
thesis`; `docs/student-repos.md` und `docs/architecture.md` („What is still
in the dotfiles“) sagen das schon. Damit ist Phase 2 abgeschlossen.

- `labkit/scaffold.py` (Schicht tools), Console script `labkit-init` mit
  `lab`, `exp`. Portiert: `scaffold_repo`, `--exp`. Nicht portiert:
  `--thesis` (bleibt Haus, s. o.), `sync`, `--thread`, `refs`,
  `upsert_labs`, der accessio-Import, die Shim-Erkennung.
- Vorlagen nach `labkit/templates/`: Skript-Vorlagen (prepare, measure,
  analyze, explore, test-area, quick), `test-shared-helpers`, `models.toml`,
  `pyrightconfig`, `vscode-*`, eine englische `AGENTS.md`-Vorlage (erfüllt
  Punkt 6). Nicht `thesis-starter/` — bleibt Haus.
- Pin: `importlib.metadata.version("labkit")` → GitHub-Tag `v<version>`;
  `git+file://` fällt weg. `--labkit-ref REF` ausdrücklich für Entwicklung und
  Tests. Bis der Tag gepusht ist, ist der Pin nicht installierbar: Phase 2
  endet „ready to tag“, die Installations-Abnahme folgt nach Tag und Push.
- Deutsche Texte (etwa 230 Zeilen) englisch, Hauspfade raus.
- Tests: nur die Klassen zu init und exp aus `test_arbeitsstandard_init.py`.
- `usability.py`: `STAMPED`/`SCAFFOLDER` aus dem Paket; `usability stage`
  läuft dann ohne `~/.claude`.
- Lebende Leser: `README.md` (Hook-Installation, Sync-/Shim-Absatz),
  `docs/student-repos.md` (Thesis-Starter bleibt Haus), `labkit/docs/standard.md`
  (`lib exp` in LAB-003 No run without an intent paragraph und LAB-046 Notebooks: explore yes, report never → `labkit-init exp`); `package-data` für
  `docs/*.md`, `docs/*.tsv`, verschachteltes `templates/` erweitern.
- dotfiles am selben Tag: `IN_LABKIT`/`master_path` und der Test, der den
  labkit-Checkout liest, brechen beim Umzug; der Labor-Teil fliegt aus dem
  Gerüstbauer, `lib init/exp` rufen `labkit-init`. Faden-Teil und Stempeln des
  Coding-Style bleiben.

**Prüfstelle:**
- Hook grün, einmal zusätzlich `HOME=$(mktemp -d) .venv/bin/pytest -q`.
- Wheel: exakte Dateiliste; verboten sind `~/work`, `/Users/max`, `webis`,
  `~/.claude/resources`. Installiert in ein leeres venv laufen dort
  `python -m labkit.rules check`, `show LAB-015` und `labkit-init lab
  --labkit-ref …`.
- Register: jede LAB-Kennung genau einmal aktiv — labkit oder Haus, nie beides
  (liest die dotfiles nur, wenn vorhanden; sonst lauter Skip).
- Alter Pin: Wegwerf-Klon auf `v0.76.0`, `lib sync pull` → laute
  Verweigerung.
- Ende-zu-Ende ohne `~/.claude`: `labkit-init lab`, `labkit-init exp`,
  `preflight`, `labkit-audit --mode preflight`.
- Vorher/nachher `lib init --lab` in zwei Temp-Ordner, `diff -r`; die
  erwarteten Unterschiede stehen vorab als Liste im Commit.
- dotfiles: `python -m labkit.rules check|ledger|refs` grün über Hausdokument
  und Register.

**Zeile R — erledigt 2026-10-12 für die vier aktiven Repos** (uniagent
`4e3ec93`, fallacy-dataset-generation `949085f`, labkit-paper `f1fef6e`,
counterfactual-worlds — Pin `git+https://github.com/kmax-tech/labkit.git@v0.85.0`,
`labkit-hooks install`, `lib sync pull`, Kennungen in lebenden Dateien,
Suiten grün). `labkit-check` je Repo: Pin, Installation, neuester Tag, Hook OK;
die Zeile `refs` bleibt STALE in dreien, bewusst: `resources/templates/`
(Schnappschuss von vor 0.47, in uniagent und labkit-paper, nichts liest ihn —
löschen wäre die saubere Lösung, Entscheidung des Nutzers), `src/measure/
comparison.py:884` in uniagent (Audit-Scope von 19 eingefrorenen Bereichen),
20 alte Kapitelverweise (`§2.2`, `§12.4` …) in Notizen und Archiv von
counterfactual-worlds. Nebenbefund labkit-paper: Bereich 04 zitiert einen
Lauf, dessen Scope sich geändert hat — `finalize --if-reported` meldet 4
Blocker, der Hook hält jede Änderung an diesem Protokoll an, bis der Bereich
weiterbearbeitet wird. counterfactual-worlds importierte
`promises.registered_ids` (weg seit 0.74.1) — ein Bruch, den der CHANGELOG
nicht als solchen angekündigt hatte. Stand vorher:**

- **Prüfstelle je Repo:** `.venv/bin/labkit-check` aus dem Repo-venv, fünf
  Zeilen OK (0.84.0, gebaut 2026-10-12 für genau diesen Rollout).
- **Tag zuerst:** `v0.84.0` auf HEAD (Nutzer; 0.83.0 ist ohne Tag geblieben,
  der Rollout nimmt gleich die Version mit `labkit-check`). Die Labor-Pins zeigen auf
  `git+file://`, ein lokaler Tag reicht zum Installieren; der Push nach GitHub
  ist nur für Studi-Pins Voraussetzung. Ohne Versions-Tag verweigert
  `lib init . --sync pull` (Commit-Pin = „keine Version“).
- **Vier aktive Labor-Repos, Commit-Pin → `@v0.84.0`:** uniagent (0.82.0),
  labkit-paper (0.82.0), fallacy-dataset-generation (0.76.0),
  counterfactual-worlds (0.72.1). Je Repo in dieser Reihenfolge, ein Commit:
  Pin in `requirements.txt` und `.lock` · `pip install -r` · `labkit-hooks
  install` · `lib init . --sync pull` (uniagent und labkit-paper melden den
  geerbten Block „diverged“ — lokal steht nur die Umbenennung vom 2026-10-11,
  der Master trägt sie auch, geprüft per Diff: `--force`) · restliche
  `AS`-Kennungen außerhalb der geerbten Blöcke umbenennen · Suite · Commit.
  **Erledigt 2026-10-12, noch nicht committet:** die Umbenennung in den
  lebenden, nicht gesyncten Dateien von fallacy-dataset-generation (8 Dateien)
  und counterfactual-worlds (7), `labkit.rules refs` 0 Befunde (Prüfer an
  einem bekannten Fehler angeschlagen), Suiten grün bis auf einen Vorbefund
  in fallacy-dataset-generation (`test_probe_cases_are_pasted`, ein TODO des
  Repos). Nicht angefasst: eingefrorene Protokolle, `runs/`, `data/`, die
  Vorlagen-Schnappschüsse unter `resources/templates/` (Records).
  counterfactual-worlds: `tools/doktrin_drift.py` und sein Test lesen die
  `AS`-Köpfe des Projektstandards — nach dem Pull auf die `LOCAL`-Köpfe des
  Haus-Blocks umstellen.
- **Fünf ruhende Labor-Repos bleiben auf ihrem Pin** (0.23.0/0.25.0):
  fallacy-datasets, visual-argument-spec, fallacy-detection,
  finance-discourse, paper-organization — Altprotokolle in alter Form,
  Entscheid 2026-10-06 (Punkt 7, Schritt 4); heben, wenn dort neue Arbeit
  beginnt.
- **Thesis-Repos:** neun der zehn nutzen labkit nicht. thesis-dagidir trägt
  vendorte Helfer vom September (vor dem Pin-Entscheid 2026-10-07) und
  eingefrorene Läufe; ein Pin ist dort ein Umbau der Imports und kommt mit
  neuer Arbeit, Entscheidung beim Nutzer (Studi-Repo auf git.webis.de).
- **Punkt 7 Rest, Punkt 8:** in labkit erledigt; die 14 Altprotokolle bleiben
  (Entscheid 2026-10-06). Push und Tags beim Nutzer.

## 6. Harness-unabhängig — Codex und andere Agenten

**Befund (2026-10-06):** Die harte Schicht von labkit ist schon
harness-unabhängig: `runlog` (Freeze-, Leckage-, Detach-Riegel), die vier
Gates, `recheck`, der git-Pre-Commit-Hook — alles Code und git, kein Agent im
Spiel. Claude-spezifisch sind vier Stellen in der weichen Schicht:

| Stelle | heute | für jeden Agenten |
|---|---|---|
| Einstiegsdatei | `CLAUDE.md` (Claude Code liest sie) | `AGENTS.md` als gestempelte Datei (Codex, Cursor, Gemini-CLI lesen sie oder eine Variante); `CLAUDE.md` wird ein Symlink darauf. Der Scaffolder stempelt beide, `lib sync` hält eine. |
| Live-Hooks | `claude-hook pre-run/post-change` über `.claude/settings.json` (PreToolUse/PostToolUse-JSON) | bleiben als **Adapter** für Claude Code; der Riegel in `runlog` und der Pre-Commit-Hook sind die Schicht, die ohne Harness hält (LAB-011 Required-field check: „die Regel, die der Agent vergisst, steht im Riegel"). Ein zweiter Adapter je Harness nur, wenn er Hooks hat. |
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

**Auslöser:** die `AGENTS.md`-Vorlage kommt mit Punkt 5, Phase 2
(2026-10-09); `labkit audit` und die Harness-Erkennung bei der
Veröffentlichung oder dem ersten Mitarbeitenden, der mit Codex im Labor
arbeitet. **Prüfstelle:** `labkit-init lab` stempelt `AGENTS.md`.

## 7. Englische Kennungen: `[C]` · `[A]` · `[B]` statt `[K]` · `[S]` · `[W]` · `[N]`

**Was:** Die Kennungen auf den Versprechen des Protokolls (LAB-004 Identifiers make the intent addressable) sind
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
Erwartete nicht, gibt es kein Urteil (LAB-034 Null condition in the same run). Im Fach
sind positive controls und quality checks Beispiele für outcome-neutral
conditions. Die Baseline ohne Sollwert ist ein comparator und gehört in den
Text von `[C]`, nicht unter eine eigene Kennung. Die Pflicht „Kontrolle im
selben Lauf“ (LAB-034 Null condition in the same run) bleibt: `[A2]` verlangt `a2_pass`, also muss der Code
die Kontrolle erzeugen.

Buchstabenwahl gegen Kollision: `ID_KEY` (`intent_check.py:50`) liest jeden
Schlüssel `<buchstabe><ziffer>[_…]` als Kennung. Gesperrt deshalb F (`f1`),
P (`p1`, precision@1), R (`r1`, recall@1/ROUGE-1), Q (`q1`, Quartil),
H (`h1`, hits@1; außerdem in Vorregistrierungen die Hypothese).

**Schritte:**

0. ~~**Sofort und unabhängig:** Haus↔Fach-Tabelle im Master~~ — **erledigt
   2026-10-07** (dotfiles `98119fc`).
   Haus↔Fach-Tabelle im Master
   (`arbeitsstandard.md.template`, Zeilen „Stop rule“ und „Registrierte
   Weiche“): S ist kein *stopping rule* (das heißt im Fach: wann die
   Datenerhebung endet; preregister nutzt das Feld genau so) und kein
   *futility*, sondern eine outcome-neutral condition; Weiche ist
   conditional analysis, nicht „decision rule“ (zu breit — K und S sind
   auch Entscheidungsregeln).
1. ~~**labkit:** eine Heimat für das Alphabet~~ — **erledigt 2026-10-06**
   (`bbb5d9a`): `labkit/promises.py` ist die Heimat; `intent_check`,
   `recheck`, `code_check` und `finalize` importieren von dort.
   Kollisionstests in `tests/test_promises.py`. Altbuchstaben seit 0.48.0
   entfernt.
2. ~~**Template + Feld-Guide**~~ — **erledigt 2026-10-07** (0.47.0,
   `7dfce48`); die alten Labels liest `protocol-check` seit 0.48.0 nicht mehr.
   (`experiment-protocol.md.template`,
   `protocol-field-guide.md`): Feld-Label „stop rule“ →
   „admissibility condition“, Schlüsselwörter für `protocol-check`
   nachziehen.
3. **Doktrin im Master** — **erledigt 2026-10-07** bis auf `lib sync pull`
   in die Repos (dotfiles `51b9060`, `b6d54e2`; labkit `218bb68`). Das
   Mess-Skelett hält jetzt das C-Urteil zurück, wenn ein A fällt.
   LAB-004 Identifiers make the intent addressable, Abschnitt „Nullbedingung / Anker“,
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
Die Kennungen sind die Übergabe-Einheit zwischen Agenten (LAB-004 Identifiers make the intent addressable); ein
externer Leser kann `[S]`, `[W]` heute keinem Fachbegriff zuordnen, und
„stop rule“ führt ihn auf den falschen.

**Auslöser:** Punkt 5 (Englisch als Master) oder das nächste neue Protokoll,
je nachdem, was zuerst kommt — Schritt 0 sofort. **Prüfstelle:**
`labkit/promises.py` — Schritte 0–3 sind erledigt; offen ist der Rollout
in die Repos (`lib sync pull`, Pins auf v0.47.0) — Schritt 4 bleibt beim
Entscheid „nicht anfassen“.

## 8. Kopffelder als Daten: `[protocol]` im TOML-Block

**Was:** Die Felder, die eine Maschine liest — `Standard`, `Protocol id`,
`Type`, `Cost`, `Frozen before run`, `Preflight audit` — ziehen als
Tabelle `[protocol]` in denselben TOML-Block wie die Versprechen; ein
Parser (`tomllib`), exakte Werte, keine Schlüsselwort-Regex. Die
Prosafelder (Frage, Begriffe, Einheit, Ausschlüsse, Konfunde) bleiben
Markdown, weil ein Mensch sie schreibt und liest; ihre Prüfung erwartet
das exakte Label aus dem Template statt beliebiger Schlüsselwörter.
TOML, nicht YAML: stdlib-only.

**Bruch statt Altpfad (Leitsatz oben) — erledigt 2026-10-07 mit 0.48.0:**
Der Regex-Kopf fiel weg, und im selben Release die übrigen Altpfade (rund
45 Stellen in 8 Modulen, Stand 2026-10-06): Altbuchstaben K/S/W/N, Läufe ohne `schema_version`,
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

**Erledigt 2026-10-07 (0.48.0):** Kopf als `[protocol]`-Tabelle (`labkit/protocol_block.py`), Prosafelder über exakte Labels (`protocol_check.FIELDS`, ein Test bindet sie an die Vorlage), Altpfade entfernt — dazu `runlog migrate-index` und die Messungs-Kurzform. Die Import-Fallbacks für vendorte Kopien sind in 0.49 entfernt; entschieden 2026-10-07: Studi-Repos pinnen labkit von GitHub wie die Labore (`--thesis` schreibt `requirements.txt`, dotfiles `6b92c03`). Offen: Tags auf GitHub (Voraussetzung für jeden Studi-Pin), Pin für `thesis-dagidir`.

**Auslöser (war):** der Rollout von Punkt 7 (Template und Feld-Guide auf
`[C]/[A]/[B]`) — das Template ändert sich dann nur einmal.
**Prüfstelle:** `labkit/experiment-protocol.md.template`; solange der Kopf
dort Prosa-Felder stempelt, ist der Punkt offen.
