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
| P | Pilotrunden 2026-10-16 (Haiku v1, Sonnet v2/v3, Labor `labkit-paper` Bereich 09): Plan „Kein stiller Ausweg“ unten — A Marke und Verweigerung · B Berichtsfelder vor dem Lauf · C Vorlage ohne Modell · D Doktrin zum Vorab-Blick | **geplant 2026-10-17**; A1, A3, A4 gebaut (0.99.0); nächster Schritt A5 (Ergebnisfreigabe bei `seconds`, notiert 2026-10-19) |

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

## Plan 2026-10-17: Kein stiller Ausweg — was die Pilotrunden verlangen

**Befund in einem Satz:** labkit hat in den Pilotrunden die richtigen
Belege erzeugt (den Leckage-BLOCKER, die Bestätigung `unfrozen_ack`, das
Fehlen eines Laufs), und nichts hat sie in die berichtete Zahl gezwungen.
Die Gates prüfen, ob etwas da ist, nicht, ob der Bericht es sagt. Beleg: die
drei Einträge unter „Notiert, nicht geplant“ vom 2026-10-16/17 (Haiku t3,
`--report`, Vorab-Blick); dieser Plan ist ihre Heimat für die Reihenfolge.
**Auslöser:** die Runden selbst — neun Versuche, drei Aufgaben, drei
Modelle; in keinem lief der Weg bis `report-check`, und zwei Zahlen gingen
ohne Gate aus dem Bereich. Nicht im Plan: ein „schlanker Weg für
`minutes`“ (t18 scheiterte an 2400 Waldanpassungen je Lane, nicht an
labkit; erst der Trace entscheidet), ein Sehen von `measure()`-Aufrufen
ohne runlog (unmöglich), `finalize` verlangt weiter nicht `frozen = true`
(das ist Station 1 von `report-check`, die Stufen bleiben getrennt).
Ebenfalls nicht gelöst, und das sagt der Plan ausdrücklich: die inhaltlich
leeren Kriterien von Haiku bleiben stehen — t5 „Test-ROC-AUC“ ohne
Testlabels, t18 „Accuracy ≥ 0.5“ als Hürde, t3 ein C1, dessen Test-Gold
Nullen sind (Test-MAE 0.0) und das der Code zu „Vorhersagen erzeugt“
umdeutete, während der Promise-Satz weiter „MAE within 10 %“ sagt. Das
sieht der Audit; A sorgt nur dafür, dass ein Audit nicht übergangen wird.
Mechanisch greifbar wäre davon ein Stück: eine Lane, deren Gold-Werte in
den Ausgabezeilen alle gleich oder null sind, hat keine Auflösung — static
evidence, geparkt bis zum zweiten Fall (Kandidat, nicht im Plan).

Jeder Schritt ein Commit, Zwillingstest (der Fehlerfall blockt, die
korrekte Variante bleibt still), `ruff`, `ruff format`, `pyright`, Suite
grün. A1–A3 und B1 sind Stufe guaranteed und zusammen ein Release; A4
ist zurückgestellt (s. dort); C1 klein dahinter, C3 ohne Rang; C2 ein
eigenes Release; D hebt den Standard und wartet auf die Entscheidung des
Autors.

| Schritt | Inhalt | Stufe | Prüfstelle |
|---|---|---|---|
| A1 | **Erledigt 2026-10-18 (Commit 95ebabc, Unreleased):** runlog verweigert den vollen Lauf über einen `open` BLOCKER eines Preflight-Records, mit und ohne Bestätigung; offene WARNINGs stehen in der Warnzeile; `tests/test_runlog_unfrozen_blocker.py`. Ursprünglich: **runlog verweigert über einen ungelesenen BLOCKER hinweg.** `runlog.py:1121` nimmt `LABKIT_UNFROZEN=1` heute immer. Neu: liegt in `audits/` ein Preflight-Record (`findings.area_records`, `mode == "preflight"`) mit einem `open` Finding der Stufe BLOCKER, verweigert runlog auch mit Bestätigung und nennt Datei und Befund; offene WARNINGs stehen in der Warnzeile der Bestätigung. Ohne Record bleibt der Pilot möglich (v2: Audit nicht erreichbar). Nur volle Läufe (`long=True`, die Sperre steht unter `if long:`, `runlog.py:1121`): `--probe` muss einen BLOCKER untersuchen können, sonst ist er nicht zu entscheiden. Haiku t3: die Datei lag beim ersten Lauf bereits da. | guaranteed | `tests/test_runlog_unfrozen_blocker.py`: offener BLOCKER + Bestätigung → `SystemExit` nennt ihn; kein `audits/` + Bestätigung → startet, `unfrozen_ack = true`; BLOCKER `fixed`/`accepted` → startet; Probe trotz offenem BLOCKER → läuft |
| A1b | **Der laufende Audit zählt.** A1 sieht nur einen fertigen Record; zehn Sekunden früher gerechnet, und Haiku t3 wäre durch. `labkit-audit` schreibt vor dem Modellaufruf `audits/<datum>-<modus>.running` (pid, Start) und entfernt ihn im `finally`; runlog hält den Vermerk für lebendig, solange die pid läuft (wie `active()` für Runs), und sagt dann „warte: audit since <Start>, pid N“, auch mit Bestätigung; ein Vermerk ohne lebende pid ist ein abgebrochener Audit, `unavailable` nach V1, und sperrt den vollen Lauf ebenso (entschieden 2026-10-17: laut scheitern statt still markieren); der Ausweg ist ein neuer `labkit-audit`, der den Vermerk durch ein Ergebnis ersetzt, nicht das Löschen der Datei (Haikus zweiter Audit starb mit SIGTERM nach 70 s). `audit.py` schreibt heute vor dem Aufruf nichts. | guaranteed | `tests/test_runlog_audit_running.py`: Vermerk mit lebender pid → `SystemExit` „warte“; Vermerk mit toter pid → `SystemExit` „audit unavailable“, `--probe` läuft; kein Vermerk → unverändert |
| A2 | **Die Marke steht in der Antwortzeile.** `protocol_fill.answer_line` liest `runs.read_run_config` des Laufs; bei `unfrozen_ack = true` endet die Zeile `(run <id>, unfrozen — acknowledged with LABKIT_UNFROZEN=1)`, in Answer und Result gleich. `recheck.cited` findet die Run-ID weiter (`runs.RUN_ID` ist wortbegrenzt). v2 t5 schrieb das von Hand unter „Deviations after freeze“, ein Feld für etwas anderes. | guaranteed | `tests/test_protocol_fill_unfrozen.py`: Lauf mit Marke → Zeile trägt sie; ohne → Zeile unverändert; `--check` hält beide |
| A3 | **Erledigt 2026-10-18 (Unreleased, Branch `claude/no-silent-exit-a3-xo1x2e`):** `finalize` Station 8 „audit findings“ (offene Befunde jeder Datei, BLOCKER → Blocker, WARNING → Warnung), Station 1 warnt vor einem Pilotlauf; `report-check` blockt ihn (`runs.unreportable`: `long=False`, `unfrozen_ack`, oder ein Record ohne `long`); jeder Lauf schreibt `long` in `config.json`; `tests/test_finalize_open_findings.py`. **Erweitert um Läufe ohne `long=True`** (zweite Haiku-Runde, s. Befund unten). Ursprünglich: **finalize nennt offene Befunde, report-check blockt den bestätigten Piloten.** `finalize_area`: neue Station nach „answering run“ — `open` Findings aus `audits/` (jeder Modus): BLOCKER → Blocker, WARNING → Warnung, je mit Datei; dazu die Warnung „answering run acknowledged unfrozen“, wenn der Lauf die Marke trägt. `report_check.later_gaps`: ein antwortender Lauf mit `unfrozen_ack = true` ist ein Blocker („a reported number owes a frozen run“). Das ist der ältere Kandidat „finalize führt unentschiedene BLOCKER auf“. | guaranteed | `tests/test_finalize_open_findings.py`: offener BLOCKER → exit 1 mit Datei; alle entschieden → still; Lauf mit Marke → finalize warnt, report-check blockt; ohne Marke beide still |
| A4 | **In anderer Form gebaut 2026-10-18 (Unreleased, Branch `claude/no-silent-exit-a3-xo1x2e`):** nicht die Run-ID in geänderten Dateien, sondern der Bereich, in dem die Sitzung eine Datei geändert hat (git status) bzw. in dem eine gestagte Datei liegt — hält er einen Audit-BLOCKER mit `status = "open"`, schickt `claude-hook stop` den Agenten zurück (exit 2, einmal) und der Pre-Commit verweigert über `claude-hook undecided <paths>`; `claude_hooks.undecided_blockers`, `tests/test_claude_hooks_undecided.py`. Auslöser: dritte Haiku-Runde auf 0.99.0, t5 — Audit gestartet, vier BLOCKER gelesen, alle zwölf Befunde offen gelassen, mit long=False gemessen, berichtet; report-check hätte verweigert, aber niemand ruft ihn. Ein Gate, das der Agent aufrufen muss, ist keins. Alte Bereiche blocken nicht (nur berührte), damit der Einwand vom 17.10. nicht greift. Der ursprüngliche Zuschnitt bleibt notiert: **Der Stop-Hook folgt der Zahl, nicht dem Dateinamen.** Eine Heimat `finalize.cited_elsewhere(repo, paths)`: in jeder geänderten Datei (`claude_hooks._git_changed`) jede `runs.RUN_ID`-Fundstelle; existiert `runs/<id>/config.json` in einem Bereich des Repos, ist dessen `protocol`-Bindung das Protokoll, das `finalize_area` bekommt — auch wenn es selbst keinen Lauf zitiert (`--if-reported` überspringt es sonst). `claude_hooks.stop` und der von `install_hooks` gestempelte Pre-Commit der Labor-Repos (heute `finalize --if-reported` auf gestagten Protokollen) rufen dieselbe Funktion. Eine Run-ID ohne Verzeichnis im Repo zählt nicht (kein Fehlalarm aus einer Notiz über ein anderes Repo). Haiku t3: REPORT.md im Root zitiert den Lauf, das Protokoll nicht — heute kein Gate. **Zurückgestellt (2026-10-17):** der eine Fall war vom Sandbox-Prompt verlangt; in einem Labor-Repo zitieren TODO und Notizen alte Läufe desselben Bereichs, und jeder Stop zöge `finalize` auf unberührte Protokolle. Befund dazu: `notes_check` kennt heute weder Run-IDs noch `finalize`, der vorgesehene Weg ist `02_analyze.py --check` über `report-check`. **Auslöser:** ein zweiter Fall in einem echten Labor-Repo — dann zuerst auf `notes/messung/` begrenzt, wo der Stop-Hook schon hinschaut. | guaranteed | `tests/test_claude_hooks.py` erweitert: geänderte `REPORT.md` zitiert einen Lauf, dessen Protokoll keine Antwort trägt → exit 2 mit Protokollname; Datei ohne Run-ID → 0; Run-ID ohne Verzeichnis → 0; Pre-Commit derselbe Fall über `finalize --cited-in <paths>` |
| B1 | **Erledigt 2026-10-19 (Unreleased, übernommen aus Branch `claude/zealous-davinci-3hbhvk`, `c465d40`):** `protocol_check.written_before_run`, `tests/test_protocol_check_report_before_run.py`. Ursprünglich: **Berichtsfelder vor dem Lauf.** `protocol_check`: ein Feld der Klasse `report` (`Field("Did", "report")`, Outcome, Rival check, Caps/drops) oder „Result“ (Klasse `after`) ist gefüllt, „Answering run“ offen (`answering_run_open`) und `runs.bound_answering_run` findet keinen abgeschlossenen Lauf → WARNING „written before any run“ je Feld. Läuft damit in `preflight`, `protocol-check` und dem PostToolUse-Hook. t18 v2 und v3: „Did“ behauptet Grid und 55 Testmoleküle, `runs/` hält nur die Vorbereitung. Dass der Text einen Lauf *behauptet*, bleibt Semantik; dass er vor jedem Lauf geschrieben wurde, ist exakt. | guaranteed (die Meldung sagt, was sie weiß) | `tests/test_protocol_check_report_before_run.py`: Did gefüllt + kein Lauf → Warnung; Did gefüllt + abgeschlossener Lauf → still; Did Platzhalter → still |
| C1 | **Erledigt 2026-10-19 (Unreleased, übernommen aus Branch `claude/zealous-davinci-3hbhvk`, `1fe430f`):** `scaffold.DETERMINISTIC_NA` hält nur noch das Parser-Feld; `tests/test_scaffold.py` (`Report`, `ModelNamed`). Ursprünglich: **`--report` erklärt nichts mehr für deterministisch.** `scaffold.DETERMINISTIC_NA` (`scaffold.py:409`) behält nur „Parser cases harvested“; „Randomness controls“ und „Noise ceiling → threshold“ bleiben ohne Modell geschuldet, weil ein Schätzer mit Seed sie schuldet. CHANGELOG „Changed“: zwei Felder kommen für modellfreie Bereiche als Platzhalter zurück. Beleg v2 t5 gegen v3 t5 (Streuung 0.116 über zehn Seeds). | guaranteed | `tests/test_scaffold_report.py`: ohne Modell bleibt „Randomness controls“ Platzhalter, „Parser cases“ gefüllt; mit Modell unverändert |
| C2 | **Vorlage für die Messung ohne Modell.** `labkit-init exp --estimator` (Name offen) stempelt `measure-estimator-script.py.template`: registrierte Lane = Schätzer auf wahren Labels, Null-Lane = derselbe Schätzer auf permutierten Labels in jedem Trainingsfold, A1 Yield (`max_empty`), A2 Null-Bande (`null_band`), C1 `margin`; Felder „Prompt“, „Render check“, „Parser cases“ vorgefüllt „n/a — no model“, Test-Vorlage mit den vier Extremen (perfekt, Zufall, leer, Null außerhalb). Beleg: neun von neun Versuchen waren modellfrei; drei von drei Modellen bauten das Skelett um (Sonnet v3 t3 schreibt es), Haiku ließ `margin`, `max_empty`, `null_band_items` als Reste stehen. Rollout in Labor-Repos ist eine eigene Aufgabe. | Doktrin (Gerüst) | `tests/test_scaffold_estimator.py`: der gestempelte Bereich besteht `preflight` ohne Must-Lücke außer der Registrierung; sein Test läuft grün; `protocol-check` meldet keinen Vorlagenrest |
| C3 | **Unerwähnte Konstante.** `promises`: ein registrierter Konstantenname, der weder im `sentence` seines Promise noch in einer Scope-Datei vorkommt → WARNING in `protocol-check`/`preflight` („constant `null_band_items` is named by no sentence and read by no scope file“). Haiku 3 von 3, mit umgedeutetem `margin = 0.70` als Schwelle bei t5. | static evidence | `tests/test_promises_constant_mentioned.py`: Rest → Warnung; im Satz genannt → still; nur im Scope gelesen → still |
| D1 | **Feldführer: Banden an der Null-Lane kalibrieren.** `labkit/protocol-field-guide.md`, „Noise ceiling → threshold“ und „Instrument check“: Kalibrierung an der Null-Lane oder an einem Ausschnitt; die registrierte Lane auf allen Items vor dem Freeze macht den Freeze leer und steht, wenn geschehen, unter „Noise ceiling“ mit Zahl und Seeds. Beleg v3 t3 (Seeds 1–5 ad hoc, R² 0.910–0.916 vor dem Freeze), v3 t5 (zehn Seeds, AUC 0.93–0.96); Gegenbeispiel v3 t18. | Doktrin | Lesen; kein Test |
| A5 | **Ergebnisfreigabe bei `seconds`: der Auswertungs-Audit an der Beförderung.** `report-check` endet bei `cost = "seconds"` heute mit Exit 0, ohne eine Station zu prüfen (`report_check.py`, „nothing owed here“), obwohl LAB-017 dort den **einen** Audit (Modus `analysis`) an der Beförderung der Zahl verlangt — und die Beförderung ist genau der Moment, in dem `report-check` gerufen wird. `finalize` grün plus `report-check` grün belegen bei `seconds` also keine Freigabe. Auslöser: Bereich 09 des Labors (2026-10-19) bewertet labkits vorgesehenen Ablauf ohne vorgegebene Stufe; für Random-Forest-Aufgaben ist `seconds` die passende Stufe, und die Bewertung muss den Audit selbst über `findings.audit_coverage` im Image fragen (`lib/agentsandbox/standard_check.py` im Labor) — eine zweite Heimat, die mit diesem Punkt zurück nach labkit zieht. **Zuschnitt:** bei `seconds` läuft in `report-check` Station 2 (der antwortende Lauf ist ein voller Lauf, `runs.unreportable`) und Station 3 (ein entschiedener Analysis-Record zu Code, Promises und antwortendem Lauf, `findings.audit_coverage`), Station 1 (Freeze) und Station 4 (`02_analyze.py --check`) bleiben der langen Spur; die Meldung nennt LAB-017 statt LAB-050. **Nicht:** kein externes Strict-Flag, kein pauschaler Blocker, weil ein Bereich nur Probeläufe hält — eine Exploration darf ohne freigegebenes Ergebnis enden; erst eine ausdrücklich als Ergebnis verwendete Zahl (Answer-Zeile per `protocol-fill --from-run`, Note per `--check`, oder wer `report-check` ruft) schuldet, was ihre Stufe verlangt. Die Seconds-Spur in `AGENTS.md.template` nennt den Audit „eine spätere, eigene Aufgabe“ — der Satz bleibt richtig, wenn er dazusagt, dass `report-check` diese Aufgabe prüft. | guaranteed | `tests/test_report_check.py`: `seconds` ohne Analysis-Record des antwortenden Laufs → exit 1 nennt LAB-017; mit entschiedenem Record und vollem Lauf → 0; `seconds` mit Probe als antwortendem Lauf → exit 1; `test_seconds_owes_nothing_here` wird zum Zwilling „owes no freeze“ |
| D2 | **Der Audit fragt danach.** LAB-015 Preflight audit before freezing bekommt den Satz: der Auditor fragt, ob die registrierte Zahl vor dem Freeze gesehen wurde, und wo das steht. `labkit-audit` schneidet LAB-015 in den Prompt, also reicht der Satz im Standard; `rules.tsv` und `labkit/rules.py` halten die Referenzen. Standard 0.19 → 0.20, ein Breaking im Sinne des Ledgers. Entscheidung des Autors. | agent audit | Benchmark-Fall im Labor: v3 t3 als Proband, Befund erwartet; v3 t18 als Zwilling, still |

**Was A gegen jeden Pilotfall tut:** Haiku t3 — A1 verweigert den
Lauf, bis der BLOCKER entschieden ist; hätte er ihn entschieden
(`accepted`) und mit Bestätigung gerechnet, trüge die Antwortzeile die
Marke (A2), `finalize` nennte die Entscheidung (A3); die REPORT.md im
Root bliebe ungeprüft, bis A4 gebaut ist (zurückgestellt). Zehn Sekunden
früher gerechnet, träfe A1b statt A1. Sonnet v2 t3/t5 — A2 setzt die Marke statt des Freitexts unter
„Deviations“, A3 blockt den Bericht in `report-check`, bis Audit und Freeze
nachgeholt sind; die Zahl bleibt als Pilotzahl lesbar. Sonnet t18 — B1
warnt bei `preflight`, bevor „Did“ einen Lauf behauptet, den es nicht
gibt.

**Befund zweite Haiku-Runde auf 0.98.0 (2026-10-18, Labor `labkit-paper`
Bereich 09, Zweig `sr-only`):** Erfolg labkit 2/3, ohne 1/3; stille
Abweichungen 2 gegen 2; kein labkit-Agent startete einen Audit, also griff
A1 nie. Zwei Wege am Freeze vorbei: t3 und t18 messen ohne `long=True`
(für labkit ein Probelauf, weder Freeze noch Audit fällig) und berichten
die Zahl; t5 misst mit `long=True` und `LABKIT_UNFROZEN=1`, was ohne jeden
Audit-Record erlaubt war. Die Leckage über G_VRH bei t3 blieb diesmal in
beiden Armen still und undokumentiert. Nebenbefund t5-labkit: „Test-Accuracy“
gegen die Platzhalter -999 als Klasse 0 gerechnet, bedeutungslos — Semantik,
Sache des Audits (keine Katalogstelle). **Gebaut dazu (Unreleased):** A3
mit Probelauf-Sperre (oben) und der **Notausgang rastet ein**: bei
`minutes`/`hours` nimmt `runlog` `LABKIT_UNFROZEN=1` nur über einem
fehlgeschlagenen Audit-Versuch, den `labkit-audit` selbst geschrieben hat
(`audits/<datum>-preflight-failed.toml` bei `llm.BackendError`: Fehlertext,
scope sha, block sha, Timeout, Kommando; `findings.write_failed`), passend
zu Code und Promises jetzt und mit mindestens dem Standard-Timeout
(`findings.ATTEMPT_TIMEOUT_S`); der Lauf schreibt `audit_failed` in
`config.json`; `tests/test_runlog_unfrozen_failed_audit.py`.
**Umgehbarkeit, ehrlich:** die Datei lässt sich von Hand schreiben (kein
Geheimnis auf dem Rechner, stdlib, also keine Signatur, die der Agent
nicht selbst hätte) oder über ein absichtlich kaputtes Backend
(`models.toml` verbogen) erzeugen. Was labkit garantiert: jede Umgehung
hinterlässt eine Datei in labkits Form mit genanntem Fehler, der Lauf
nennt sie, `uncommitted.patch` zeigt ein verbogenes `models.toml`, und die
Zahl bleibt eine Pilotzahl — `report-check` verweigert sie (A3). Die
billigen Wege sind zu: kein Audit starten, `--timeout 1`, ein Versuch an
anderem Code oder nach einer Promise-Änderung, ein Analysis-Versuch für
den Preflight. **Dritte Haiku-Runde auf 53f81a6 (2026-10-19, Labor `labkit-paper`, Handurteile offen):**
labkit 1/3, ohne 2/3. Die neue Meldung wirkt teilweise: t5 startete erstmals
den Audit, las vier BLOCKER, dampfte das Protokoll auf „nur Vorhersagen“
ein und rechnete als Probelauf (zwölf Befunde offen). t3 schrieb das Skript
von Anfang an ohne `long=True`. t18 setzte `frozen = true` mit selbst
geschriebenem `preflight_audit = "n/a — …"`, das runlog als Entscheidung
nahm. Niemand rief finalize oder report-check. **Gebaut dazu (Unreleased):**
Stop-Hook und Pre-Commit über offenem BLOCKER im berührten Bereich (A4 in
anderer Form, s. o.; die Runde lief ohne diesen Commit); `n/a` bei
`minutes`/`hours` verweigert (`findings.audit_line_gap`, eine Heimat für
runlog und preflight; Standard-Absatz korrigiert, Stempel 0.20 beim
Release); Warnung, wenn die Kostenstufe seit dem ersten Commit des
Protokolls sank (`protocol_check.cost_lowered`). **Nicht in labkit lösbar:**
t3, der Bericht außerhalb des Protokolls — die Bewertung im Labor liest
`runs.unreportable` des zitierten Laufs, dann zählt eine Probezahl als nicht
berichtbar, ob report-check lief oder nicht. **Wort (2026-10-18, nach den Transkripten):** die Agenten nannten die
Abkürzung „Pilot“, weil die Verweigerung sie so anbot („Pilot it with
long=False … A long PILOT acknowledges …“); die Meldungen des Gates nennen
jetzt die Folge (die Zahl ist nicht berichtbar) statt des Auswegs und
sagen „probe“ (labkits Wort für `long=False`) und „acknowledged run“.
„Pilot“ bleibt im Protokoll-Vokabular (MUST „every pilot“, Pilot-Note von
`protocol-check`, „pilot part“ des Gerüsts) — das ist Doktrin und die
Entscheidung des Autors. **Offen, Entscheidung des Autors:** ob ein Fehlversuch
altert (heute zählt er, solange Code und Promises unverändert sind), und
A1b (der laufende Audit). **Vierte Haiku-Runde auf v0.99.0 (2026-10-19,
Handurteile offen):** labkit 1/3, ohne 2/3; t3-labkit lief den Audit,
entschied alle acht Befunde, nahm das Leck heraus und verfehlte die Hürde
ehrlich, dann maß es als Probe; t5 und t18 maßen als Probe ohne Audit. Die
Bewertung des Labors prüft seit 2026-10-19 jeden abgegebenen Stand mit labkits
eigenen Gates im Image (isolierte Kopie, nichts nachgeholt): alle drei
`minutes`, alle drei nicht erfüllt — t3: Probe, kein Analysis-Audit; t5:
kein antwortender Lauf (Messung außerhalb von runlog), Protokoll beim ersten
Lauf nicht committet; t18: Probe, kein Audit, Protokoll beim ersten Lauf
nicht committet. Die Runde lief noch mit vorgeschriebenem `minutes`; die
Vorgabe ist ab jetzt weg (Stufe nach LAB-017, Kriterium bei jeder Stufe
verlangt) und bleibt als mögliche Einflussgröße notiert, nicht als Ursache —
Bereich 09, Protokoll „Changed“ und „Notes“. Für labkit folgt daraus A5.

**Gebaut 2026-10-19 (Unreleased), zwei Schritte nach der dritten Runde:**
(1) `report-check` prüft an allen Kostenstufen; bei `seconds` entfällt nur
Station 1 (Freeze, Vorab-Audit, LAB-017), der Rest hält wie bei
`minutes`: finalize sauber (Lauf ans Protokoll gebunden und in der Antwort
zitiert), voller Lauf (`runs.unreportable`), entschiedener Analysis-Record
zu Code, Promises und Lauf (`findings.audit_coverage`), `02_analyze.py
--check`. finalize-Blocker stehen namentlich in der Liste
(`finalize_area(…, findings)`). Bis 0.99.0 endete der Befehl bei `seconds`
sofort mit 0, eine zurückgeschriebene Probezahl galt dort als berichtet.
(2) Stop-Hook und Pre-Commit rufen `report-check --if-reported`;
`finalize --if-reported` ist weg. Die vorhandene Ergebnisbindung drückt den
Anlass eindeutig aus: die Run-ID in „Answer to the question“
(`protocol-fill --from-run` schreibt sie, `finalize.cited_runs` liest sie)
ist die Erklärung „Ergebnis berichtet“; eine offene Antwort schuldet nichts,
eine Exploration endet mit „kein freigegebenes Ergebnis“, Probeläufe in
`runs/` oder nicht (`tests/test_claude_hooks.py` Stop, `tests/test_report_check.py`
IfReported). Eine Antwort ohne Run-ID ist weder berichtet noch offen:
`protocol-check` warnt (`answer_without_run`, static evidence), die Gates
schweigen. (3) **Ein Übernahmeweg** (Max, 2026-10-19): `protocol-fill
--from-run` schreibt die Zeilen, lässt `report-check` auf dem geschriebenen
Protokoll laufen und stellt bei einem Blocker die Datei wieder her
(`protocol_fill.adopt`, `tests/test_protocol_fill.py` Adopt). Das
Einschreiben erklärt die Zahl zum Ergebnis, die Prüfung sichert den
Anspruch; was über diesen Weg im Answer-Feld steht, hat jede Prüfung
durchlaufen. Vorläufige Zahlen bleiben Skizze in `runs/` und `output/`. Ob
jemand außerhalb des Wegs (REPORT.md, Chat) eine Zahl berichtet, bleibt
Arbeitsdisziplin bzw. Audit. **Folge für die Doktrin, Entscheidung des Autors:** LAB-017 sagt
für `seconds` „ein Analysis-Audit bei der Promotion, bis dahin Skizze“;
jetzt ist das Zurückschreiben der Antwort die Promotion, der Audit also vor
dem Stop bzw. Commit fällig, der sie trägt. Die `AGENTS.md`-Vorlage (Lane
seconds, Schritte 5–6) und der LAB-011-Absatz des Standards sagen das; der
Tabellensatz von LAB-017 selbst ist unverändert und gehört, wenn er
geändert wird, in den Ledger (0.20). Weiter nicht lösbar: der Bericht
außerhalb des Protokolls (t3) — kein Protokoll, keine Erklärung, kein Gate.

## Audit 2026-10-18: was unter dem Grep des One-Home-Tests liegt

Befund: `docs/audit-2026-10-18.md` (drei Fehler, reproduziert; die halben
Umzüge aus 0.96.x; Kopien, die `tests/test_one_home.py` nicht sieht).
Auslöser: der Autor nach den Commits vom 15.–17.10. — gibt es Drift,
mehrere Wahrheiten, doppelte Helfer? Prüfstelle: je Schritt eine
One-Home-Regel, die die Form beim Wiederkommen greift.

| Schritt | Inhalt | Stand |
|---|---|---|
| 1 | Die drei Fehler: `scope_sha.parse_source` als der eine Parse einer Scope-Datei (Audit-Bug 11 galt nur mit `lib/`) · `protocol_block.fenced_lines` statt sieben Hand-Toggles auf ``` · der Tag-Test-Skip (`.strip()`) | **gebaut 2026-10-18**, Branch `claude/project-thread-u3bner`; Release beim Autor |
| 2 | Die halben Umzüge: jede Verweigerung über `console.refuse` (neun Module drucken noch auf stdout, `scaffold` wirft `SystemExit`), code-check durch `gate.report` oder die Ausnahme dokumentiert, das Shim-Rezept aus `__init__` | offen |
| 3 | Drei neue Heimaten mit Regel: `repo.shown(path, base)` (18 Kopien), `runs.now_stamp()` (9), `shell_segments` in Schicht 1 (Hook und Transkript), `LABKIT_COMMANDS` aus `entry_points` | offen |
| 4 | Lesbarkeit: `preflight_area` nach dem finalize-Muster teilen, `usability` in Stage, Score und CLI, `Path | int` in `intent_check` durch eine Ausnahme ersetzen | offen |
| 5 | Namen in einem Commit: Fläche heißt `area: Path`, Wurzel nach ihrer Regel, `_sha256` → `_source_digest`, `trace` → `timeline`, `registry` oder `ledger` | offen |

## Audit 2026-10-15: Fehler zuerst, dann die zweiten Heimaten

Befund: `docs/audit-2026-10-15.md` (14 Fehler, reproduziert; ein Dutzend
Stellen, an denen eine Frage mit Heimat ein zweites Mal beantwortet wird).
Auslöser: der Audit selbst — `protocol-fill --from-run` schreibt in einem
Bereich mit zwei Protokollen die Zahl des falschen Laufs ins Protokoll
(`recheck.run_dir` wählt ohne Bindung, `finalize` mit). Prüfstelle: je
Schritt ein Test mit Zwilling; Phase C ein Test, der jede Kopie beim
Wiederkommen greift — die Audits vom 2026-10-06 und 2026-10-13 haben
dieselben Kopiearten entfernt, und sie kamen zurück.

| Phase | Inhalt | Stand |
|---|---|---|
| A · 0.94.0 | Stufe guaranteed: ein Wähler für den antwortenden Lauf (`recheck.run_dir` → `runs.bound_answering_run`, `holds` hält den Lauf an die Protokoll-ID der Notiz, `usability.latest_run` fällt) · `runlog <bereich>` verweigert einen unbekannten Bereich · HTTP 4xx ohne Retry · Prompt per stdin an `claude -p` (Linux: 128 kB je Argument) · Laufdatensatz atomar (CODE-013) · `recheck._present` maskiert Run-IDs und Daten · nicht parsender Skriptcode ist ein Blocker, kein Traceback · report-check zählt Must-Platzhalter · Kleinkram (`maxsplit`, `_ids`-Meldung, `agree` nach JSON-Rundreise, Area-Tests unter `layout_root`) | **gebaut 2026-10-15**, neun Commits auf `claude/gracious-dirac-s2botv`; Release `just release 0.94.0` beim Autor (CHANGELOG-Eintrag steht) |
| B · 0.95.0 | Audit-Kette und Hooks: Stamp vor dem Modellaufruf · `findings.write` verweigert ein Verdict mit mehr Blockern als Findings · preflight ruft `audit_stamp_drift` · pre-run über `shlex`-Tokens, `cd` verfolgt, Throwaway-Flags je Teilkommando · `git status -z` · `_ours` prüft den Pfad · Timeouts für Area-Tests und `--check` | **gebaut 2026-10-15**, sechs Commits auf `claude/gracious-dirac-s2botv`; Release `just release 0.95.0` beim Autor, nach 0.94.0 |
| C · 0.96.0 | Eine Heimat je Frage: `labkit/gate.py` (`Findings`, eine Schreibweise, ein Exit-Vertrag) · Fences und Labels nur aus `protocol_block`/`protocol_check` · `repo.repo_protocols` mit Skip-Regel, `repo.PROTOCOL_NAME`, `repo.lab_root`, `repo.AREA_NAME` · Digest und git ohne Kopie, `runs.RECORD_SHA_CHARS` · Alphabet nur aus `promises` · `AnsweringRun.explain()` · `tests/test_one_home.py` greift `hashlib.sha256(`, `subprocess.run(["git"`, `rglob("PROTOCOL-`, `[ca]\d+`, Fence-Regexe außerhalb ihrer Heimat | **gebaut 2026-10-15**, sieben Commits auf `claude/gracious-dirac-s2botv`; `tests/test_one_home.py` hält zehn Kopieformen; Release `just release 0.96.0` beim Autor, nach 0.95.0 |
| D | Doku und Hygiene: README-Zählungen, `docs/architecture.md` zur Atomarität, `docs/standard-*.tsv` einordnen, Befunde auf stdout und Bedienfehler auf stderr, CLAUDE.md „fresh clone with tags" | **gebaut 2026-10-15**, zwei Commits; `docs/standard-*.tsv` bleiben als Beleg des Schnitts (so schon unter Punkt 5 notiert), kein Release nötig |

**Laufauswahl systematisch geprüft (2026-10-15, nach 0.96.1).**
`tests/test_answering_run_exhaustive.py` hält `runs.bound_answering_run`
gegen ein Orakel aus den Docstrings: alle Bereiche bis drei Läufe aus neun
Arten, je an verschiedenen Tagen und in einer Sekunde (1640 Bereiche); drei
eingebaute Mutanten werden rot. Befund dabei, behoben (`68e0706`): zwei
Läufe derselben Sekunde ordnete das Zufallssuffix der Lauf-ID — jetzt ein
Blocker. **Fortgesetzt am selben Tag:** dieselbe Prüfung für die anderen
Wähler — finalize, intent-check, recheck, params und audit nennen auf allen
1640 Bereichen denselben Lauf (`17a02a7`); `runs.draws`/`next_draw` über
800 Bereiche: ein unlesbarer Lauf verschwand still aus der Streuung, eine
Nicht-Integer-Ziehung wurde beim Zählen übersprungen, zwei Ziehungen mit
einer Nummer liefen beide durch — jetzt Verweigerungen (`9790f1f`); ein
abgeleiteter Lauf durfte eine Wiederholung als Eltern nehmen und so die
beste Ziehung antworten lassen — jetzt Verweigerung (`50ab7e1`);
`completed_runs` im Orakel, `usability.latest_run` verweigert zwei Läufe
derselben Sekunde. Release steht aus (`CHANGELOG.md` „Unreleased“).

## Klein, ohne eigenen Punkt

- [x] **`usability stage --restamp`: die Probe stempelt das Werkzeug nach,
  nicht das Gedächtnis** (0.88.6, 2026-10-13). Auslöser: acht Nachstempel
  von `labkit-probe` von Hand, und zwei Sitzungen rekonstruierten das Rezept
  am selben Tag verschieden („nur fünf Dateien“ gegen „alle gestempelten,
  Cloud-Edits aussparen“). Jetzt: frischer Stempel über die Probe gelegt,
  `--keep` für die Hand-Edits (`TASK.md`, `.gitignore`,
  `.claude/settings.json`), in `probe.json` gemerkt; venv aus dem Pin,
  Commit am Hook vorbei, Push beim Autor. Erster Lauf: Probe auf v0.88.5
  (`0eed22d`). Nebenbefund dabei: die gestempelte `.gitignore` ignorierte nur
  das Verzeichnis `.venv/`, nicht den Link, den `--venv` legt — behoben.
  **Offen, nur notiert:** `labkit-check` meldet die Pin-Zeile der Probe als
  STALE, weil `requirements.txt` den Tag und das Lock (aus `pip freeze`) den
  Commit nennt, auf den der Tag zeigt — seit jedem Stempel so, kein Schaden
  (der SessionStart-Hook liest nur die `installed`-Zeile). Entscheiden: Tag
  auflösen und vergleichen, oder das Lock als Commit-Form des Tags lesen.
  **Gebaut 2026-10-14:** `labkit-check` löst den Tag an der Quelle auf
  (`git rev-parse` lokal, `git ls-remote` remote) und vergleicht Commits —
  gleiche Quelle, Lock auf dem Commit des Tags heißt OK; offline bei einer
  Remote-Quelle UNDECIDED. Gegen `labkit-probe` geprüft: `v0.88.7 (lock: its
  commit 7844ff168f4a) … OK`.
- [x] **Release in einem Schritt: `just release X.Y.Z`** (2026-10-13).
  Auslöser: der Tag `v0.88.5` wurde auf `35734e0` gesetzt, bevor der
  Versionscommit da war; der Tag-Test wurde rot, der Doku-Commit `a9dad50`
  ging mit `--no-verify` am Hook vorbei, und der Tag blieb auf dem alten
  Commit — wer `@v0.88.5` installierte, bekam die Fixes unter dem Namen
  0.88.4. Das Rezept hält die eine Reihenfolge ein: Changelog-Eintrag
  geschrieben → Version gesetzt → Commit durch den Hook → Tag auf diesen
  Commit; Push bleibt beim Autor. Prüfstelle: das nächste Release, der
  Tag-Test bleibt grün.
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
  2. [x] **`code-check`: jeder registrierte Schlüssel wird gelesen, nicht
     nur geschrieben** (Punkt 3 unten) — gebaut 2026-10-14, s. Punkt 3.
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
  8. [x] **`labkit-params`: eine Skript-Kopie `MIN_F1` zu `min_f1` nennen**
     (Kaltleser 2026-10-09): die Indiz-Zeilen sehen nur Großbuchstaben, die
     Konstanten sind klein — die Kopie steht als eigene Zeile, die
     registrierte sagt nur „not recorded". Lookup auch unter `name.upper()`.
     Gebaut 2026-10-14: die Kopie steht in der registrierten Zeile, keine
     eigene Indiz-Zeile mehr (`tests/test_params.py`).
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

**Gebaut 2026-10-14 (static evidence, WARNING), auf Ansage vor dem
Auslöser:** `code_check.admissibility_reads` — jeder [A]-Schlüssel des
Blocks, den der Code schreibt, muss an einer Entscheidungsstelle stehen
(`if`/`while`/`assert`-Test, bedingter Ausdruck, `and`/`or`/`not`,
`all()`/`any()`; `m[k]` über ein Schlüssel-Tupel wird aufgelöst). Nur [A]:
C ist das Urteil selbst, B meldet eine Weiche. Erste Fassung (Lesen
irgendwo) gab 9 Fehlalarme in uniagent 16–18 (`all(metrics[k] for k in
ADMISSIBILITY)`); die zweite schweigt auf allen 27 echten Bereichen mit
[A]-Versprechen und meldet alle drei Schlüssel, wenn in einer Kopie von
uniagent 16 die zurückhaltende Zeile fehlt. Der zweite Kandidat unten
(Literal-Kopie einer Konstante) ist seit `constant_copies` gebaut.

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

**Gebaut 2026-10-15 (0.93.0), anders als unten geplant:** nicht über
`derived_from` (das heißt seit 0.72 „liest alte Zeilen neu, kein
Modellaufruf, kein Modell-Record“), sondern als eigene Lauf-Beziehung
`repeat_of` mit Nummer `draw`; verweigert, wenn Protokoll, Block, Config
oder Eingaben abweichen. Eine Wiederholung antwortet nie (`bound_runs`,
`completed_runs(with_repeats=…)` an jeder Aufrufstelle). Berichtet wird
Ziehung 1, die Streuung ist Grenze (Variante (a)); ein Aggregat wäre eine
andere registrierte Auswertung. Skelett `--repeat-of`, `02_analyze.py
--draws`; `finalize` warnt bei einer Ziehung. Echt geprüft mit Haiku:
10/12, 10/12, 12/12, es kippen c08 und c12. Nebenbei behoben: ein bei
`seconds` mit Modell gestempelter Bereich stürzte seit 0.87.0 beim ersten
Lauf ab (Konstanten auskommentiert).

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

## Verbesserungen aus oh-my-codex (2026-10-17) — notiert, nicht geplant

*Drei Ideen aus den Prüf-Skills von oh-my-codex (omx,
`github.com/Yeachan-Heo/oh-my-codex`, gelesen bei Commit `beb2299`). Die
Skills selbst passen nicht: Sie hängen an omx' Laufzeit (`omx state write`,
tmux-Teams) und nehmen sich Dinge heraus, die labkit verbietet (Schleifen
mit automatischer Reparatur). Übernommen wird je eine Regel. Zu jedem Punkt
steht, wie omx es macht, und wie es in labkit direkt aussähe. Keiner rückt
vor Plan P; jeder wartet auf seinen Auslöser.*

### V1. Ein Audit, der nicht gelaufen ist, ist nicht bestanden: der Zustand `unavailable`

**Befund in labkit:** `labkit-audit` bricht bei `llm.BackendError`,
Zeitüberschreitung oder Abbruch mit Exit 2 ab und schreibt **nichts** nach
`audits/` (`audit.py:539–549`; `findings.write` steht erst danach). Ein
gescheiterter Audit sieht also genauso aus wie einer, den niemand gestartet
hat. A1 baut darauf sogar ausdrücklich: „Ohne Record bleibt der Pilot
möglich (v2: Audit nicht erreichbar)“. Haiku t3 hat genau diese Lücke
genommen: zweiter Aufruf abgebrochen, als gescheitert gedeutet, mit
`LABKIT_UNFROZEN=1` weitergerechnet.

**Wie omx es macht:**
- `skills/code-review/SKILL.md:35`: Kann einer der zwei unabhängigen Prüfer
  nicht starten oder liefert keine Belege, lautet das Ergebnis wörtlich
  `independent review unavailable`. Der Autor springt nicht selbst ein,
  und die Änderung gilt nicht als merge-bereit.
- `:81` und `:90`: Ein fehlender oder gescheiterter Prüfer ist ein
  *blockierender* Zustand, kein Rückfall auf Freigabe („missing or failed
  delegation is a blocking unavailable-review state, not an approval
  fallback“; „Do not self-review as a fallback“).
- `:83–88`: Die Prüfer-Urteile werden nach einer festen Tabelle
  kombiniert: BLOCK schlägt alles, dann REQUEST CHANGES, dann WATCH →
  COMMENT, APPROVE nur, wenn beide Prüfer Belege geliefert haben.
- `prompts/verifier.md:12`, `:41`: Der `verifier` trennt „Verhalten falsch“
  (FAIL) von „Beweis fehlt“ und hat dafür einen dritten Ausgang, PARTIAL.

**Vorschlag für labkit:**
1. `labkit-audit` schreibt im Fehlerpfad einen Record
   `audits/<datum>-<modus>.toml` mit `outcome = "unavailable"`, dem Grund
   (Exception-Text, Modell, Prompt-kB) und dem Stamp, der vor dem Aufruf
   schon feststeht (`Stamp(sha, stamped)`, `audit.py:527–528`). Bei SIGTERM
   leistet das der `.running`-Vermerk aus A1b: Ein Vermerk ohne lebende pid
   *ist* ein `unavailable`.
2. `findings.area_records` liest `unavailable` als eigenen Zustand neben
   „Befunde offen“ und „alles entschieden“. `preflight_audit` lässt sich
   damit nicht füllen.
3. `runlog` mit einem `unavailable` als jüngstem Preflight-Record
   **verweigert den vollen Lauf, auch mit `LABKIT_UNFROZEN=1`**, und sagt
   „audit unavailable since <Zeit>: <Grund> — rerun `labkit-audit
   <bereich>`“. `--probe` läuft weiter (wie bei A1: sonst lässt sich der
   Grund nicht untersuchen). Kein Record überhaupt bleibt der Pilotfall aus
   A1, denn seit Schritt 1 hinterlässt jeder gestartete Audit einen.
4. Kombination fest wie bei omx: ein offener BLOCKER in irgendeinem Record
   schlägt alles; dann `unavailable`; dann offene WARNINGs; „bestanden“ nur,
   wenn der jüngste Record ein Ergebnis hat und nichts offen ist. Eine
   Heimat: `findings.py`.

**Stufe:** guaranteed (ob ein Ergebnis vorliegt, ist exakt).
**Entschieden 2026-10-17 (Autor): `unavailable` blockt den vollen Lauf**
— laut scheitern statt still markieren, als allgemeines Prinzip, nicht nur
hier. Der Preis ist bewusst: Ist das Backend nicht erreichbar, steht der
volle Lauf, bis ein Audit durchkommt; Proben laufen. A1b ist darauf
angepasst (Vermerk mit toter pid sperrt).
**Auslöser:** beim Bau von A1b mitnehmen, denn derselbe Vermerk trägt
beides; sonst der nächste Lauf mit einem abgebrochenen Audit davor.
**Prüfstelle:** `tests/test_audit_unavailable.py`: Backend wirft →
Record mit `outcome = "unavailable"` und Grund, Exit 2; danach `runlog`
mit Bestätigung → `SystemExit` nennt Grund und Kommando; `--probe` → läuft;
danach Audit mit Ergebnis → voller Lauf startet (Zwilling, still).

### V2. Stille Rückfallpfade im Messcode: verdeckend oder begründet

**Befund in labkit:** Der Standard kennt die Nachbarn: LAB-023 No silent
loss (Parser verliert Antworten), LAB-033 A parameter that is accepted and
discarded is the most expensive bug, die Narbenzeile „Parser with a silent
format assumption“ (`standard.md:1233`). Es fehlt die allgemeine Form im
Auswertungscode: `row.get("score", 0)`, `except Exception: continue`,
`value or 0.0`, `if x is None: x = default`. Jede davon macht aus einem
fehlenden Feld still eine Zahl, und die berichtete Metrik sieht richtig aus.
Haiku t3 ist ein Verwandter: `c1_pass = true` bei `test_mae = 0.0`, weil
die fehlenden Testlabels zu Nullen wurden.

**Wie omx es macht:** `skills/ai-slop-cleaner/SKILL.md:24–26`, zwei
Schritte vor jeder Änderung:
- *Inventar* (`:24`): jeden rückfallartigen Pfad im Scope auflisten, also
  „swallowed errors, silent defaults, broad compatibility shims, duplicate
  alternate execution paths“, auch Kommentare wie „temporary workaround“,
  „just skip“.
- *Einteilung* (`:25`): **Masking fallback** = verdeckt Belege, umgeht den
  Vertrag, schaltet Prüfung ab, verschluckt Fehler, setzt still einen
  Standardwert oder fügt ungetestete Pfade hinzu. **Grounded fallback** =
  eng, an einer Grenze nach außen (fremde API, Version), Begründung
  steht da, der Fehler bleibt sichtbar, Haupt- und Rückfallpfad sind
  getestet.
- *Abhilfe* (`:26`): Ursache reparieren, löschen oder ausdrücklich
  scheitern lassen, nicht den Rückfall polieren.
- Ausgabe je Fund: `finding -> masking | grounded -> escalation`.

**Vorschlag für labkit:** in zwei Stufen, die zweite nur, wenn die erste
es verlangt.
1. *Benchmark-Fall zuerst* (Labor `labkit-paper`): ein gefüllter Proband,
   dessen `02_analyze.py` eine Metrik mit `.get(key, 0)` über fehlende
   Gold-Werte rechnet, und sein Zwilling mit explizitem `KeyError`. Frage:
   findet `experiment-preflight` den Fall, ohne dass die Narbentabelle ihn
   nennt?
2. *Findet er ihn nicht:* eine Narbenzeile im Standard, gebaut nach omx'
   Einteilung — Klasse „Silent fallback in the number's path“, Symptom
   „a missing field, a failed call or an unparsable value becomes a
   default that enters the reported number“; begründet ist ein Rückfall nur,
   wenn er an einer Grenze nach außen sitzt, gezählt wird und die Zählung
   im Bericht steht (das ist LAB-023, verallgemeinert). Der Auditor
   meldet je Fund `masking` oder `grounded` im vierten Feld seiner Zeile
   („which reported number goes wrong“).
3. *Statische Hilfe, erst nach einem zweiten echten Fall:* `code-check`
   listet `except …: pass|continue` und `.get(<k>, <Literal>)` in den
   Skripten des deklarierten Scopes als Hinweis („the auditor decides
   masking or grounded“), nie als Blocker.

**Stufe:** agent audit (1, 2), static evidence (3).
**Auslöser:** der nächste Benchmark-Durchgang (Schritt 2 der
Reihenfolge); Stufe 3 erst nach einem echten Fund in einem Labor-Repo.
**Prüfstelle:** Benchmark-Matrix: Proband → Befund mit `masking`;
Zwilling → still.

### V3. Jeder Befund sagt, worauf er steht: Evidence, Inference, Unknown

**Befund in labkit:** Eine Auditzeile hat sechs Felder
(`experiment-preflight.agent.md:138`), aber keines sagt, ob der Befund an
einer gelesenen Zeile hängt oder ein Schluss über mehrere ist. Die drei
Stufen (guaranteed, static evidence, agent audit) markieren das je
*Prüfung*, nicht je *Befund*. Beim Entscheiden (`fixed` / `accepted` /
`dismissed`) muss der Leser das selbst herausfinden. Beleg aus Schritt 2:
B1 (positionaler Join) kam nur als WARNING; ob der Auditor ihn sah oder
vermutete, steht nirgends.

**Wie omx es macht:** `skills/analyze/SKILL.md:30–36` verlangt für jede
wesentliche Behauptung eine Marke:
- **Evidence** — direkt in Code, Test, Artefakt, Konfiguration oder Doku
  gezeigt;
- **Inference** — ein Schluss aus zitierten Belegen;
- **Unknown** — vom Repo nicht entschieden.

Dazu „Never present guesses as evidence or inference“ (`:36`) und eine
Rangtabelle mit Konfidenz High/Medium/Low und der stärksten Stütze je
Erklärung (`:45`ff.). Für Unknown nennt omx die kleinste Leseprobe, die es
entscheiden würde.

**Vorschlag für labkit:**
1. Ein siebtes Feld in der Auditzeile, zwischen Ort und Befund:
   `BLOCKER · scripts/02_analyze.py:42 · evidence · …`. Werte `evidence`
   (die Zeile zeigt es), `inference` (Schluss über mehrere Stellen; die
   anderen Stellen stehen im Befundtext), `unknown` (der Code entscheidet
   es nicht; dann ist das letzte Feld die Leseprobe statt einer Änderung).
2. `findings.py` liest das Feld als `basis` und prüft die Werte (Werte
   sind Namen, LAB-086 Values rule (codes are names too): erst Fach- und Hausbegriff
   nachschlagen). `findings.write` speichert es.
3. Der Ertrag wird zählbar: Wie viele `inference`-Befunde enden in
   `dismissed`? Ist es die Mehrheit, weiß man, wo die Fehlalarme
   herkommen.

**Stufe:** Format (agent audit, Ausgabe); das Lesen in `findings.py` ist
guaranteed.
**Breaking:** ja — das Zeilenformat ändert sich, und `findings` liest das
alte nicht mehr (Leitsatz „Altlasten“). CHANGELOG „Breaking“ mit der
letzten Version, die sechs Felder liest.
**Auslöser:** der nächste Audit-Durchgang, bei dem eine Entscheidung
`dismissed` lautet, weil der Befund geraten war; oder Schritt 2, wenn man
den Ertrag je Klasse auszählt.
**Prüfstelle:** `tests/test_findings_basis.py`: Zeile mit `evidence` →
`basis` gelesen; fehlendes oder unbekanntes Feld → Fehler mit Feldname;
`unknown` ohne Leseprobe → Fehler.

## Notiert, nicht geplant

- **Externes Review 2026-10-18 (fünf Befunde, alle am Code bestätigt) —
  alle fünf gebaut 2026-10-18 (Commits 221a6f1, 9caf326, 95ebabc, 6235d0f,
  42e2c22; CHANGELOG Unreleased, Release offen).** Entschieden ohne den
  Autor: der Record bindet den Promise-Block-Digest (`block_sha`, nicht
  den Protokolltext — Freeze und Audit-Zeile ändern den Text, nicht die
  Promises) und beim Analyse-Audit die Run-ID des antwortenden Laufs;
  `code-check` folgt dem Gate-Vertrag (Exit 0 bei nur Warnungen) statt
  den Vertrag zu ändern. Beides ist umkehrbar, wenn der Autor anders
  entscheidet. Offen bleibt der Lesehinweis zur README (unten). Stand
  davor: drei waren schon notiert: die Bestätigung übergeht Audit-BLOCKER (= A1
  im Plan 2026-10-17), `code-check` liefert Exit 1 auch bei nur Warnungen
  entgegen dem Vertrag in `gate.py:4` (Audit 2026-10-18, Punkt 2 der
  Arbeitsordnung), `llm.py:41` zeigt `endpoint = "gamma2"`, das `resolve`
  seit 0.89.0 verweigert, und `__init__.py:13` empfiehlt den Shim
  (Audit 2026-10-18). Zwei sind neu:
  1. **Der Audit-Record bindet nur Modus und Code-Stempel.** `findings.read`
     hält `date, mode, model, scope_sha`; `audit_coverage`
     (`findings.py:237`) vergleicht nur `mode` und `scope_sha`. Der Stempel
     deckt laut `scope_sha.py:8` absichtlich nicht das Protokoll — ein
     Preflight-Audit liest aber das Protokoll (LAB-015), und nach einer
     Protokolländerung bei unverändertem Code gilt der alte Record weiter;
     ein Analyse-Audit gilt für jeden späteren Lauf mit demselben Code.
     Reproduziert am Code. Kandidat: der Record trägt zusätzlich den
     Digest des TOML-Blocks (Head + Promises, `promise_block`) und beim
     Analyse-Audit die Run-ID des beurteilten Laufs; `audit_coverage`
     bekommt beide als Pflichtargumente, `preflight` und `report-check`
     reichen sie durch. **Entscheidung des Autors:** was ein Audit bindet,
     bestimmt, wann er fällig wird — ein Protokoll-Digest macht jede
     Textkorrektur im Protokoll zu einem neuen Audit; die Alternative ist
     nur der Promise-Digest (`declared_scope_sha` je Promise). Stufe
     guaranteed; Prüfstelle `tests/test_findings_binding.py`: Protokoll
     geändert, Code gleich → `audit_coverage` nennt die Lücke; beides
     gleich → None.
  2. **Der Leser hält die Zähler nicht gegen die Tabellen.** `findings.write`
     verweigert `blockers`/`warnings` über der Zahl der `[[finding]]`-Tabellen
     (`findings.py:113`); `findings.read` nimmt `blockers = 2` ohne eine
     Tabelle, `audit_coverage` sieht dann nichts Offenes und besteht —
     reproduziert mit einem Hand-Record. Dieselbe Grenze in `_audit_table`
     als `FindingsError`, weil Menschen die Dateien bearbeiten. Stufe
     guaranteed, klein, passt zu A1–A3 ins selbe Release; Prüfstelle
     `tests/test_findings.py`: Zähler über den Tabellen → `FindingsError`
     nennt Datei und Zahlen; Zähler gleich → liest; `notes` bleibt frei.
  Dazu der Lesehinweis des Reviews: die README beginnt mit der Modulliste
  und der Entstehungsgeschichte (`README.md:3`), der Ablauf mit den drei
  Prüfstufen kommt erst aus vielen Befehlen zusammen — gehört zu
  „Ablauf ins Paket: `docs/workflow.md`“ unten.

- **Ein Bericht außerhalb des Protokolls löst kein Gate aus (2026-10-16). → Plan 2026-10-17 oben.**
  Labor `labkit-paper`, Bereich 09, Haiku-Runde, Versuch `t3-labkit-r1`
  (Speicher `output/attempts_pilot_haiku_v1/`, Transkript `out/trace.jsonl`):
  Der Agent lief `preflight`, startete den Preflight-Audit, wartete 30 s
  und dann 70 s, hielt den Audit für gescheitert und rechnete vier Läufe
  mit `LABKIT_UNFROZEN=1` (drei abgestürzt, einer fertig). `frozen` blieb
  `false`, `preflight_audit` leer, `finalize`, `protocol-fill --from-run`
  und `report-check` liefen nie. Der Audit schrieb seinen BLOCKER (`G_VRH`
  und `poisson_ratio` bestimmen K in geschlossener Form) kurz darauf nach
  `audits/`, ungelesen. Die Zahl ging in eine `REPORT.md` im Repo-Root mit
  Run-ID und wurde committet; `metrics.json` trägt `c1_pass = true` bei
  `test_mae = 0.0`, weil der Testsatz keine Labels hat. Die REPORT.md nennt
  beides als Abweichung: den unfrorenen Lauf und dass C1 „auf erfolgreiche
  Vorhersage statt MAE-Vergleich“ umgedeutet wurde — der Promise-Satz sagt
  weiter „MAE within 10 %“, die Umdeutung steht nur im Bericht. Was der
  Bericht nicht trägt, ist der Audit-Befund zur Leckage, den der Agent nie
  las. Kein Gate hat die Zahl gesehen: der Stop-Hook (`claude_hooks.py:551`) und `finalize
  --if-reported` prüfen nur geänderte Protokolle, die einen Lauf zitieren,
  und das Protokoll zitiert keinen. Drei mechanische Lücken, alle Stufe
  guaranteed:
  1. **runlog nimmt die Bestätigung immer** (`runlog.py:1123`). Liegt in
     `audits/` ein Preflight-Audit zu diesem Protokoll mit unentschiedenem
     BLOCKER und `preflight_audit` ist leer, ist das kein Pilot, sondern
     ein ignorierter Befund: verweigern, auch mit `LABKIT_UNFROZEN=1`, und
     den Befund nennen. Bei t3 lag die Datei beim ersten Lauf bereits da.
  2. **`unfrozen_ack` liest niemand.** runlog schreibt es in `config.json`
     (`runlog.py:1254`); finalize und report-check ignorieren es. Ein Lauf
     mit dieser Marke darf kein antwortender Lauf sein und keine Zahl ins
     Protokoll bringen — sonst wird aus dem „Pilot“ stillschweigend das
     Ergebnis. (Enthält den älteren Kandidaten: `finalize` führt
     unentschiedene BLOCKER aus `audits/` auf, solange `preflight_audit`
     leer ist.)
  3. **Der Stop-Hook hängt am Dateinamen, nicht an der Zahl.** Jede in der
     Session geänderte Datei, die eine Run-ID trägt (exakt erkennbar,
     `runs.RUN_ID`), zieht `finalize` für das Protokoll, an das dieser
     Lauf gebunden ist (`runs.bound_answering_run`). Dann sieht das Gate
     auch eine `REPORT.md` im Root. Das leere Kriterium (Nenner 0) fängt
     `finalize` bereits, sobald es läuft; Punkt 3 sorgt dafür, dass es
     läuft.


  **Zweiter Befund derselben Runde:** `t5-labkit` registriert „test ROC-AUC“
  als C1, der Code rechnet Trainings-AUC; `t18-labkit` belegt `a1_*`/`a2_*`
  mit Genauigkeiten anderer Konfigurationen — Kennung und Bedeutung laufen
  auseinander, ohne dass `code-check` es sieht (gehört zu Punkt 3).

  **Dauer, zur Einordnung:** 8 min für den halben Weg; der ganze Weg bis
  `report-check` brauchte in Durchgang 4 7m26s und mit Haiku in Durchgang 5
  12m31s (oben). Zeit war nicht knapp (Timebox 30 min im Protokoll); der
  Agent gab beim Audit zweimal zu früh auf. **Auslöser:** der nächste
  Pilot, in dem ein Agent `LABKIT_UNFROZEN=1` setzt, oder der nächste
  Breaking-Schritt an `runlog` ohnehin. **Prüfstelle:** Zwillingstest je
  Lücke — der Pilot ohne Audit-Datei startet weiter mit Bestätigung; ein
  Lauf mit `unfrozen_ack` wird von `finalize` als antwortender Lauf
  verweigert, ohne Marke nicht; eine geänderte Notiz mit fremder Run-ID
  zieht `finalize` genau einmal.

- **`--report` erklärt einen Wald mit Seed für deterministisch (2026-10-17). → Plan 2026-10-17 oben.**
  Labor `labkit-paper`, Bereich 09, Sonnet-Runde v2, Versuch `t5` (Protokoll
  `p-233d6d06bdd5422e`): „Randomness controls“ und „Noise ceiling →
  threshold“ tragen den Vermerk „auto-filled by --report“ mit „deterministic,
  no model: no seed, no temperature, one run“ und „repetition spread 0“.
  Dasselbe Protokoll nennt unter „Free knobs“ seed 0 für Wald, Folds und
  Permutation, und die v3-Runde misst auf denselben 44 Chemikalien eine
  Streuung der Null-AUC von 0.116 über zehn Seeds. labkit hat also eine
  falsche Aussage in genau das Feld geschrieben, das diese Streuung
  festhalten soll. Ursache: `scaffold.DETERMINISTIC_NA` (`scaffold.py:409`)
  füllt drei Felder, sobald `protocol_check.model_named` kein Modell findet;
  „kein Sprachmodell“ wird zu „keine Zufallsquelle“. Ein Schätzer mit Seed,
  ein Fold-Shuffle und eine Permutation sind Zufallsquellen. Kandidat, Stufe
  guaranteed: ohne Modell füllt `--report` nur „Parser cases harvested“ vor;
  „Randomness controls“ und „Noise ceiling“ bleiben geschuldet. v3 hat beide
  Felder von Hand richtig gefüllt (Seeds, Spread über Seeds). **Auslöser:**
  der nächste `labkit-init --report` auf einem Bereich ohne Modell, oder
  dieser Eintrag beim nächsten Release. **Prüfstelle:** Zwillingstest in
  `tests/` für `--report`: ohne Modell bleibt „Randomness controls“ ein
  Platzhalter, „Parser cases harvested“ wird gefüllt; mit Modell unverändert.

- **Die registrierte Zahl war vor dem Freeze bekannt (2026-10-17). → Plan 2026-10-17 oben.** Sonnet-
  Runde v3 (Manifest: `claude-sonnet-5-5` als Agent, `claude-opus-5-5` als
  Auditor; v2 lief ohne Auditor), Versuche `t3` (`p-6b594f6a815b4d40`) und `t5`
  (`p-102a187cacd44561`): beide eingefroren, gestempelt, bis `report-check`
  gegangen, und beide schreiben selbst, dass die registrierte Lane vorher auf
  allen Items gerechnet wurde. t3: Seeds 1–5 „ad hoc, ohne runlog“ mit
  CV-R² 0.910–0.916, danach eingefroren, gemessen 0.9116 („not blind
  predictions“). t5: zehn Seeds beider Lanes als „instrument check“, AUC
  0.93–0.96, dann eingefroren („the pass is not independent“). Der Freeze
  schützt dann nichts mehr; die Offenlegung steht in Freitext unter
  „Randomness controls“ und „Outcome“, kein Feld fragt danach, kein
  Prüfpunkt im Audit-Prompt. labkit sieht einen direkten Aufruf von
  `measure()` nicht; `--probe` ist für einen Wegwerfausschnitt gedacht, nicht
  für die volle Messung ohne Run-ID. t18 derselben Runde hat es richtig
  gemacht: Banden nur an der Null-Lane kalibriert, die registrierte Lane nur
  im reduzierten Probe. Kandidaten, Stufe Doktrin und Audit: (a) der
  Feldführer zu „Noise ceiling → threshold“ und „Instrument check“ sagt,
  dass Banden an der Null-Lane oder an einem Ausschnitt kalibriert werden,
  nie an der registrierten Lane auf allen Items; (b) der Preflight-Audit
  fragt: „Wurde die registrierte Zahl vor dem Freeze gesehen?“; (c) die
  Vorlage trägt ein Feld dafür, damit die Antwort nicht in „Randomness
  controls“ versteckt steht. Dazu aus denselben Runden, kleiner:
  `protocol-fill --from-run` trägt `unfrozen_ack` aus `config.json` nicht in
  die Antwortzeile (v2 t5 schreibt die Bestätigung von Hand unter
  „Deviations after freeze“, ein Feld für etwas anderes; gehört zu Lücke 2
  oben); die Vorlage ist LLM-förmig und kostet jedem ML-Versuch Turns für
  „Prompt“, Render check, Parser cases, bei Haiku mit Vorlagenresten in den
  Konstanten (`margin`, `max_empty`, `null_band_items` unter Sätzen, die sie
  nicht nennen; mechanisch prüfbar: Konstante weder im Satz noch im Scope);
  t18 schließt in v2 und v3 nicht ab: in `runs/` liegt jeweils nur der
  Vorbereitungslauf, kein Freeze, und das Feld „Did“ behauptet beide Male,
  das Grid sei gelaufen und die 55 Testmoleküle beschriftet — ein
  Berichtsfeld, vor dem Lauf gefüllt, als wäre er geschehen (81
  Gitterpunkte × 5 Folds × 3 Konfigurationen × 2 Lanes gegen das Zeitlimit
  des Versuchs von 1800 s; die „Timebox: 1h“ im Protokoll ist die Zahl des
  Agenten, nicht die Grenze, die griff). **Auslöser:** die Auswertung der Pilotrunden fürs Paper,
  oder der nächste Schnitt am Feldführer. **Prüfstelle:** ein Protokoll mit
  Offenlegung unter „Randomness controls“ bekommt vom Audit den Befund; eines
  ohne Vorab-Blick nicht (Zwilling); `--from-run` auf einem Lauf mit
  `unfrozen_ack = true` schreibt die Marke in die Antwortzeile.

- **Grundschicht aus der Literatur (2026-10-15).** Die Narbentabelle hält,
  was im Haus passiert ist; Fehler, die anderswo belegt sind, fängt sie
  zufällig. Abschnitt 8 des Standards trägt jetzt die Grundschicht (31
  Klassen aus Kapoor, REFORMS, Biderman, ABC, Wicherts, Makin, Lones;
  Entwurf aus der Note `narbentabelle-aus-der-literatur`), außerhalb jeder
  Regel, also **nicht im Audit-Prompt** (`labkit-audit` schneidet LAB-015
  von Kopf bis zur nächsten Überschrift). „Trivial solution passes" ist
  mit Pilot 06/07 eine Narbe geworden und steht in der Narbentabelle.
  **Auslöser** fürs Lesen durch den Auditor: die Benchmark-Fälle in
  `labkit-paper` noch einmal mit beiden Tabellen gezogen, Treffer gleich
  oder besser, Fehlalarme weiter null; eine Zeile, die Fehlalarme macht,
  fliegt. Die „new"-Zeilen, die Registrierungsfelder sind (Entwicklungs-
  gegen Auswertungsset, Einheit der Unabhängigkeit, Datum gegen
  Wissensstand, Baseline, Metrik), gehören in den Feldkatalog von
  Standard 0.20.

- **Die Startzeit im Datensatz, nicht nur im Namen (2026-10-15).** Die
  Run-ID trägt die Sekunde plus vier Hex Zufall; zwei Läufe in einer
  Sekunde sortieren per Zufall, und seit 0.97.0 verweigert jeder Wähler
  den Fall (`runs.same_second`, eine Heimat seit 0.97.1). Das ist die
  Sperre, nicht die Ursache. Ursache beheben: `config.json` trägt
  `started` mit Subsekunde (`time.time_ns()` oder ISO mit Mikrosekunden),
  und die Wähler ordnen nach dem Datensatz, der Name bricht nur noch den
  Gleichstand. Breaking (Schema 3, der Vergleich liest `started_ns`),
  klein. **Auslöser:** die Sperre beißt in einem Labor-Repo, oder das
  nächste Breaking-Release ohnehin. **Prüfstelle:** das Orakel in
  `tests/test_answering_run_exhaustive.py` ohne den Fall „eine Sekunde"
  als Verweigerung, dafür als geordnete Wahl.

- **Kern und Doktrin (2026-10-15).** Die Schichtentabelle in
  `docs/architecture.md` trägt eine Spalte „Doctrine“, und
  `tests/test_architecture.py` (`CoreAndDoctrine`) hält: ein Kern-Modul
  importiert kein Doktrin-Modul. Test: Wird eine Zahl ohne die Regel weniger
  nachvollziehbar (Kern), oder arbeitet das Labor nur anders (Doktrin)?
  Zwei Achsen, zwei Wortpaare: Kern/Doktrin sagt, was etwas leistet;
  LAB/LOCAL, für wen es gilt — „Haus“ heißt nur LOCAL und die Dotfiles. Sechs
  Übertretungen stehen heute mit Namen in `KNOWN_CROSSINGS`; die Liste
  darf nur schrumpfen:
  1. `runlog` → `findings.audit_coverage`, `protocol_check.seconds_registration_missing`
     — die Freeze-Sperre (LAB-015 Preflight audit before freezing) sitzt im
     Laufschreiber. Echtes Leck; Kandidat: die Sperre als Doktrin-Prüfung, die
     `runlog` über eine Schnittstelle fragt.
  2. `code_check` → `protocol_check.fields`, `rules.paragraph` — der
     Grenzfall: TOML-Kopf Kern, Feldkatalog Doktrin.
  3. `repo_check` → `rules.check_refs`, `install_hooks` — Pin-Prüfung Kern,
     Regelverweise und Hooks Doktrin.

  **Auslöser für den Umbau** in zwei Namensräume (`labkit` Kern,
  `labkit.doctrine` Standard, Vorlagen, Gate-Reihenfolge, Hooks, Notizen):
  die Kern-Evaluation fürs Paper, oder ein zweites Labor, das den Kern
  ohne die Doktrin will. Bis dahin nur die Liste abbauen, wo ein Schritt
  ohnehin an der Stelle arbeitet. Breaking, Pin-Heben in jedem Repo.
- **`notes_check` nach LOCAL (2026-10-15).** LAB-082 In `notes/messung/`
  und `labkit/notes_check.py` prüfen deutsche Hauskonventionen
  (Notizsorten „Instrument — Entwurf“, „Referenzkarte“ …) — nach dem
  LAB/LOCAL-Test Haus, kein Laborstandard. Umzug in die Dotfiles ist
  Breaking: ein Kommando verschwindet, der Hook ruft es. **Auslöser:** die
  nächste Breaking-Release ohnehin, oder ein Labor außerhalb des Hauses,
  das an der Prüfung scheitert. Gegenstück in die andere Richtung:
  LOCAL-073 (unten) — beide zusammen in ein Breaking-Release.
- **LOCAL-073 Paper-Zahlen tragen ihre Herkunft nach LAB (2026-10-15).**
  Nach dem Streichtest Kern-nah: ohne sie wird eine Paper-Zahl weniger
  nachvollziehbar, und sie verweist selbst auf LAB-041 Generate numbers,
  don't retype them und LAB-043 Runs go through `runlog`. Ein fremdes
  Labor bräuchte sie genauso. Umzug: Regeltext englisch in
  `labkit/docs/standard.md` als LAB-073 — dieselbe Nummer, wie beim Schnitt
  in 0.82.0 (073 ist im LAB-Ledger frei) —, LOCAL-073 im Haus-Ledger als
  `moved:labkit`. **Auslöser:** derselbe wie
  `notes_check`.

- **Narbentabelle gegen fremde Fehlerkataloge (2026-10-15) — Befund,
  nichts geändert.** Abgleich mit Kapoor & Narayanan (Leckage L1–L3),
  REFORMS (32 Punkte) und Biderman et al. (LM-Evaluation): fünf Klassen
  fehlen im Standard — Tuning am Auswertungsset, Gold im Prompt,
  Abhängigkeit zwischen Anker-/Few-shot- und Auswertungsfällen,
  Kontamination durch das Vortraining, Metrikwahl/Mittelung. Keine ist
  eine Hausnarbe; eine neue Zeile erst, wenn die K-Fälle des Benchmarks
  (K1, K3, K5) zeigen, dass der Auditor sie ohne Zeile übersieht.
  Herleitung: `~/work/projects/labkit-paper/narbentabelle-gegen-fremde.md`.
  **Gemessen 2026-10-15** (Labor `labkit-paper`, Pilot 06, Antwortlauf
  `2026-10-15T13-18-11_1ebf`): Der τ-bench-Fall aus ABC blieb unbenannt. Der
  blinde Bauer maß einen untätigen Agenten mit (19/50), aber als Untergrenze
  ohne Sollwert; Audit und `preflight` sahen nur die fehlende Registrierung.
  Kandidat für Narbenzeile oder Gate: *Nullprobe ohne Sollwert*. Nächster Fall
  (SWE-Lancer) entscheidet, ob es eine Zeile wird.
  **Zweiter Fall 2026-10-15** (Pilot 07, ScienceAgentBench Aufgabe 18,
  Antwortlauf `2026-10-15T16-43-25_b7b7`): wieder `missed`. Der Bauer fand den
  Pass des konstanten Prädiktors selbst und schrieb ihn in den Bericht,
  registrierte ihn aber als Frage ohne Hürde (`cost = "seconds"`). Offene
  Frage an labkit: LAB-004 verlangt `[[promise]]`-Tabellen „for every full
  run — so with cost = seconds always“; beide Bauer-Bereiche (labkit 0.96.1
  und 0.97.0) liefen ohne Tabellen, `preflight` 0 Blocker. Entweder gilt ein
  beschreibender Lauf nicht als full run (dann sagt der Standard es nicht),
  oder das Gate setzt die Regel nicht durch. Genau diese Lücke ließ in beiden
  Fällen die Nullprobe ohne Sollwert durch.
  Deutung nach Abgleich mit der Literatur: LAB-034 Null condition in the same
  run und LAB-037 Every anchor carries its target and rationale verlangen den
  Sollwert schon; die Bauer umgingen sie über den Namen („floor“,
  „reference predictor“). Kandidat: die Regeln an die Sache binden, nicht ans
  Wort. Dazu die Idee einer Literatur-Grundschicht unter der Narbentabelle
  (19 Klassen, Entwurf): `~/work/projects/labkit-paper/narbentabelle-aus-der-literatur.md`.

- **Repo-Audit 2026-10-13 (Klarheit, Drift, Doku) — Befund, nichts
  geändert.** Suite, ruff, pyright grün (1001 Tests). Drei Lesungen (große
  Module, Drift zwischen Modulen, Doku gegen Code); `path:zeile` sind
  Stand 0.88.8.
  - *Bug (guaranteed-Stufe bricht ihre Zusage):* `code_check.check_prompt_drift`
    stürzt mit `IndexError` ab, wenn ein Prompt-Fence leer ist
    (`labkit/code_check.py:1078`, `"".splitlines()[0]`; der erste `<`-Filter
    ist vom zweiten in :1082 ohnehin abgedeckt). Nachgestellt. Nebenbei:
    `_prompts` überspringt ein Skript mit `SyntaxError` still (:1024).
  - *Drift gegen die „eine Heimat"* (`docs/architecture.md`), jeweils verifiziert:
    `repo.choose_protocol` dreimal inline nachgebaut
    (`preflight.py:144-161`, `code_check.py:1147-1160`, `audit.py:242-252`);
    `scaffold.py:474-479` und `:586` parsen Kopf-Id und `cost` per Regex
    statt `protocol_block.head`, `:580` globt statt `repo.area_protocols`;
    `usability.py:830` liest `config.json` roh statt `runs.read_run_config`;
    `intent_check.py:432` listet Area-Skripte statt `scope_sha.area_files`;
    git außerhalb von `repo`: `runlog.py:275` (`_checkout_head`, ohne Timeout),
    `scaffold.py:714`, `usability._sh` (elf Stellen).
  - *Vierfach gleiche Hilfslogik:* Tree-Digest (`scope_sha.py:192`,
    `promises.py:434`, `runlog.py:443`, `usability.py:241`) mit
    Schattenkonstante `promises.DIGEST_CHARS` (:100, Kommentar gibt es zu)
    und Literalen `[:12]`/`[:16]` (`runlog.py:359,655,521,1154`);
    `_write_atomic` dreimal (`endpoint_lease.py:152`, `runlog.py:609`,
    `batch.py:234`); Run-Verzeichnis-Iteration sechsmal mit je eigener
    `RunConfigError`-Behandlung (`runs.py:327,380`, `runlog.py:1241,1346,1538`,
    `claude_hooks.py:468`); `"completed"` an zehn Stellen verglichen, ohne
    Konstante; Kostenstufen in `scaffold.py:50`, `usability.py:1317` neben
    `protocol_block.COST_TIERS`; Run-Id-Form dreimal (`runlog.py:1015`,
    `protocol_check.py:501`, `claude_hooks.py:397`); Pin-Grammatik viermal
    (`scope_sha.py:166`, `repo_check.py:46`, `runlog.py:195`, `usability.py:229`).
    `tests/test_architecture.py:73` sieht nur öffentliche Doppelnamen —
    für all das ist die Suite blind.
  - *Modulintern:* `protocol_check.main` (:749, 265 Zeilen) hält zwölf
    Befund-Flags als Locals und parst `fields()` bis zu siebenmal je Datei;
    Tests prüfen nur gedruckten Text. `usability.stage` (:354) wiederholt
    `_probe_venv` (:573) und den `git commit --no-verify`-Block viermal.
    `runlog.Run.__init__` liest das gebundene Protokoll dreimal
    (:769, :977, :810); Index-Zeile zweimal gebaut (:1209, :1557).
    `scaffold.stamp_area` druckt (:684, :717), `stamp_lab` gibt ein Log zurück —
    usability kapselt deshalb mit `redirect_stdout` (:393, :615).
    Toter Code: `_index_lock(timeout=)` (:567), `_registration_refusal(binding=None, registers=)`
    (:872), `llm.complete(keep_alive=)` (:472).
  - *Altpfade trotz Regel „keine Legacy-Pfade":* `llm.py:134` `endpoint = "<url>"`
    (Template `models.toml.template:21` nennt es noch gültig), `runlog.py:1377`
    „labkit before 0.69", `runlog.active` (:1259) lässt `legacy`-Läufe still
    fallen, `finalize.py:245-251` „protocols before 0.72.1" still durch,
    `protocol_check.py:564` „ledger"-Überschrift, `usability.py:188` `arbeitsstandard`.
  - *Doku gegen Code:* README „Sixteen" (17 Kommandos, :37); README `Develop`
    (:267) nennt `unittest discover` und Hand-Release, AGENTS.md und
    `just release` sagen anderes; README-Hook-JSON (:141) ohne `Stop`, Timeout 30
    statt 60 (`install_hooks.py:110-113`); Vor-Freeze-Gate „vier Stationen"
    (:216) vs. sieben in `preflight.py:13`, Post-Run „drei" (:225) vs. acht;
    `usability` hat acht ungenannte Subkommandos (`reader … human`);
    `protocol-fill --from-run` füllt auch „Answering run" (:184), README,
    Docstring, Template (:70-73) und `finalize.py:269` schicken trotzdem zu
    einem zweiten Aufruf; „Status fixed/accepted/deferred/dismissed":
    `audit.py:484` und Field Guide :148 lassen `deferred` weg;
    README :206 „thesis repos get `templates/PROTOCOL-FIELD-GUIDE.md`" — wird
    nicht gestampt; `AGENTS.md:83` zeigt auf Punkt 8 (seit 0.48.0 erledigt);
    `architecture.md:95` und `student-repos.md:31` nennen den Thesis-Starter
    offen (entschieden 2026-10-12); `student-repos.md:73` lässt die Id per
    `uuid` tippen (Field Guide :137: nie tippen); `protocol-run-binding.md:193`
    kennt `code-check --protocol` nicht; `architecture.md:73` `docs/standard.md`
    statt `labkit/docs/`; `CHANGELOG.md:17` „after the tag" (Rezept: vor dem
    Commit); `claude_hooks.py:8` Docstring aus der Zwei-Hook-Zeit;
    `tests/test_rules.py` globt `labkit/templates/*.template` nicht.
  - *Stand 2026-10-13, fünf Commits für 0.89.0 (CHANGELOG-Eintrag geschrieben,
    `just release 0.89.0` steht aus):* 1 Bug behoben; 2 `repo.the_protocol`
    als Heimat, scaffold liest über `protocol_block`; 3 `runs.run_dirs`,
    `runs.write_atomic`, `scope_sha.file_digest`/`tree_digest`;
    4 `protocol_check.check_protocol` liefert `FileReport` als Daten;
    5 Zustand `legacy`, `endpoint =`-String, `ledger`, `arbeitsstandard`
    raus (Breaking). Drei weitere Commits: `scaffold.stamp_area` gibt den
    Bericht zurück, `usability` mit `_commit`/`_read_probe`/`_answer_text`/
    `_probe_venv`, `runlog` liest das Protokoll einmal (`_Bound`), tote
    Parameter raus; Doku-Drifts behoben, README-Kommandoliste durch
    `tests/test_readme_commands.py` gehalten. Drei letzte Commits
    (2026-10-14): Requirement-Grammatik in `repo`, Run-Id-Form und
    `COMPLETED` in `runs`, `keep_alive` als Konstante, `_ollama_options`/
    `_warn_empty`, `code_check` `_name_of`/`_string_constants`,
    `protocol_check.fields` einmal geparst. **Der Audit-Befund ist damit
    abgearbeitet**; was bleibt, sind die 19 `noqa: C901`-Baselines
    (sichtbare Schuld, `grep`).

- **Judge auf `minutes`, Durchgang 2 in der Cloud (2026-10-14): voller Weg
  gemessen.** Eingefroren, Stufe gehalten, 0,8333, 22m35s (netto ~10 min,
  ~14 min Warten auf fertige Audits wegen einer `pgrep`-Schleife, die sich
  selbst findet → `c2b794a`). Der Preflight-Audit fand den Gleitkomma-
  Vergleich in [C1] der Mess-Vorlage (`fcc083d`), der Analyse-Audit eine
  abgetippte falsche Zählung. Auswertung `docs/usability/2026-10-14-judge-minutes.md`.
  **Entschieden und gebaut (0.90.0):** (a) streng — ein voller Lauf auf
  `minutes`/`hours` braucht einen entschiedenen Preflight-Record mit dem
  aktuellen `scope_sha` (`35d406b`); langfristig soll der Kopf auf den
  Record verweisen statt dessen Fakten als freien Text zu doppeln (nicht
  geplant). (b) `runlog start AREA -- <cmd>`, Log in `AREA/output/`
  (`6e390ea`). (c) keine Ausnahme: LAB-017 ordnet eine Handvoll Aufrufe
  `seconds` zu; die Probe erzwang `minutes`, um den langen Weg zu testen.
  **Durchgang 3 (0.90.0, 15m30s, netto 5m12s):** der strenge Riegel hielt
  (zweiter Audit nach dem Blocker), Start-Log im Bereich. **Offen,
  Entscheidung:** (d) Nenner der Mess-Vorlage — `_accuracy` teilt durch
  lesbare Antworten, die Registrierung sagt „über alle zwölf“; beide
  Cloud-Audits melden es (Durchgang 3 als BLOCKER). Vorschlag: leere Antwort
  zählt als nicht richtig, Nenner = alle Items der Spur ([A1] begrenzt die
  Leeren ohnehin). (e) `finalize` ist grün ohne `02_analyze.py --check` und
  Ergebnis-Note, obwohl Schritt 11 sie verlangt. (f) Erste Audit-Wartezeit
  wieder ~8 min — ohne Cloud-Transkript nicht aufzuklären.
  **Entschieden und gebaut (0.91.0, unreleased):** (d) Nenner = alle Items,
  leer zählt als nicht richtig (`724daba`); (e) eigener End-Gate
  `report-check` (`aa33896`), finalize bleibt vor dem Analyse-Audit.
  Nebenbei: `outputs.json` schrieb absolute Pfade, `--check` scheiterte in
  jedem anderen Checkout (`a4b7a75`). Offen: (f); und ob `report-check`
  in den Pre-Commit-Hook gehört (heute nur Kommando + AGENTS-Schritt 11).
  **Durchgang 4 (0.91.1, 7m26s): der ganze Weg bis `report-check` sauber**,
  auch lokal auf einem frischen Klon (relative Pfade tragen). **Offen,
  Entscheidung:** (g) Platzhalter-Sätze in `[[promise]]` eines eingefrorenen
  Kopfs werden nicht bemerkt (nur leer wird verweigert, `promises.py:219`);
  verweigern beim Freeze, oder den Satz aus dem Intent-Feld füllen? —
  **entschieden (a), gebaut in 0.91.2 (`2b414b0`).** (h) Der
  strenge Audit-Riegel zieht zu „accepted“ statt „fixed“ (8 accepted, 3
  fixed; der Agent nennt den Neu-Audit als Grund) — beobachten: im nächsten
  Durchgang je Befund Korrektheit vs. Wartbarkeit und den Grund für
  „accepted“ erfassen; ein aus Kostengründen akzeptierter Korrektheitsbefund
  ist der Auslöser für eine Regeländerung. **Haiku auf 0.91.2 (Durchgang 5,
  12m31s): ganzer Weg bis `report-check`, auch lokal sauber;** kein
  Korrektheitsbefund aus Kostengründen akzeptiert (3 fixed, 7 accepted mit
  am Lauf geprüftem Grund) — (h) ohne Auslöser. **Aus den wiederkehrenden
  Audit-Befunden gebaut (0.92.0):** Fortsetzen nur bei gleichem Instrument
  (`batch.Store(instrument=…)`, `9240b95`); Probe-Ausgabe mit echtem
  Testpfad und `PROBE_CASES`, `max_empty`-Kommentar (`3edff81`). **Keine
  Fehler, sondern Entscheidungen — entschieden 2026-10-14:** (i) Parser
  bleibt exakt, keine Codeänderung; (j) `audit()` wird nicht generisch
  automatisiert, der experimentabhängige Teil bleibt bewusst offen
  (allenfalls später die Pflicht zur Anpassung deutlicher machen). Die
  Begründungen: (i) Parser nur exakte
  Schreibung — der Prompt verlangt ein Wort, Abweichungen zählen sichtbar
  als unlesbar und [A1] begrenzt sie; jeder Audit meldet es trotzdem.
  (j) `audit()` in `00_prepare.py` druckt die Yields, die Confound-Analyse
  bleibt bewusst offen — ein generischer Confound-Audit gäbe falsche
  Sicherheit; eher den offenen Pflichtteil klarer markieren oder prüfen,
  dass er angepasst wurde. Die `minutes`-Reihe ist beendet; der nächste
  Durchgang erst nach einer Änderung an Vorlagen oder Gates.
  **Rollout (eigener Auftrag):** jeder eingefrorene uniagent-Bereich (21)
  schuldet bei gehobenem Pin vor dem nächsten vollen Lauf einen neuen
  Preflight-Audit.

- **Judge auf `minutes`, Durchgang 1 (2026-10-14, kalter Sonnet-Subagent).**
  Auswertung `docs/usability/2026-10-14-judge-minutes.md`. Zahl richtig und
  gebunden (0,8333, 2m28s), aber der Agent stellte den Kopf auf `seconds` —
  der volle Weg ist **noch nicht gemessen**. Vier labkit-Fehler im Stempel
  behoben (`93e2940` Prepare ohne Konstanten, `ec2dc52` `--from-run`
  übersprang „Answering run“ still, `cca7136` `--check` mit eigenem
  Zahlenformat, `6f740a8` WARNING aus der eigenen Analyse-Vorlage), dazu die
  Probe (`d0ad9cc`: Aufgabenblatt nennt die gestempelte Stufe). **Nächster
  Schritt:** Durchgang 2 auf dem behobenen Stempel; für die Claude-Hooks
  `claude` im Probe-Verzeichnis starten statt Subagent. Ungeprüft aus dem
  Bericht: `protocol-fill --list` zählt nach `--prompts` mehr offene Felder
  („Model I/O“); `finalize` warnt bei README-Platzhaltern und einer
  ungetrackten Ausgabedatei; mit Modell wird auch bei `seconds` das volle
  366-Zeilen-Skelett gestempelt (größte Lesezeit).

- **Nebenbefunde beim Aufstellen der Cloud-judge-Probe (2026-10-14), nicht
  behoben:** (1) `labkit-check` bricht mit Traceback ab, wenn das Lock die
  editierbare Form `-e git+…#egg=labkit` trägt (`repo_check.read_pins`
  wirft `ValueError`, `main` fängt ihn nicht) — erwartet: eine Zeile
  UNDECIDED, Exit 2. (2) `usability stage` ohne `--venv` installiert labkit
  editierbar aus dem lokalen Checkout und schreibt das Lock in dieser Form;
  für eine Cloud-Probe muss das venv danach vom Pin neu gebaut werden (von
  Hand gemacht, `labkit-probe-judge-cloud` `c594989`). Entscheiden: Stage
  baut vom Pin, wenn der Tag auf GitHub liegt, oder `--from-pin`.
- **Release 0.89.0 (2026-10-14):** erster voller Lauf von `just release`
  mit allen drei Korrekturen vom 13.10. — Hook grün, Tag `v0.89.0` auf
  `ccd24de`, gepusht. Prüfstelle aus „Release in einem Schritt“ erfüllt.

- **Fremd-Review 2026-10-14 (zweiter Agent, nichts geändert) — abgearbeitet.**
  Fünf Befunde, alle am Code bestätigt und behoben, je ein Commit mit
  Zwillingstest: Teilstring-Abgleich in `runs.is_alive` (`9f40916`),
  `run_started` bei unmöglichem Datum (Stop-Hook-Absturz), `rows_from`
  ohne Typprüfung (beide `9f40916`), Lease-Identität per Slug und
  Gleichstand im Tiebreak (`ebeba87`), modulweiter Cache der Protokoll-Ids
  (`d139fbf`). Der Versionsbefund (HEAD trägt 0.89.0-Verhalten unter
  0.88.8) erledigt sich mit `just release 0.89.0`. Bleibt notiert: die 19
  `noqa: C901`-Ausnahmen nach Lebenszyklus abbauen, nicht Dateien
  zerschneiden (runlog 1650, usability 1450, code_check 1330 Zeilen).

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
  `+dirty` auch bei nur ungetrackten Dateien — Frage, ob `??` zählen soll
  (entschieden 2026-10-13, 0.88.4: am Ende nein, am Start ja).
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
  **Gebaut 2026-10-12 (0.88.0): (a)/(k) `protocol-fill --from-run`** — Antwort-,
  Result- und Laufzeile aus `metrics.json`; Skelette und Spur nennen das
  Kommando. Prüfstelle: ein Cloud-Durchgang, dessen Log keine Hand-Rückschrift
  mehr zeigt.
  **Geprüft 2026-10-13, Durchgang 11 (Fable, 0.88.0, 3m11s):** das Log zeigt
  eine Zeile `protocol-fill --from-run`, keine Hand-Rückschrift; der Agent
  ließ die erzeugte Result-Zeile stehen, weil `--check` den Schlüssel wörtlich
  hält (`2026-10-13-cloud-fable-count-11.score.json`). Einzige Gate-Zeile:
  der README-Vertragsplatzhalter (r). Neu genannt: (u) die README dupliziert
  bei seconds das Protokoll (Frage, Vertrag, Kästchen) — bei seconds ohne
  README stempeln oder aus dem Protokoll füllen; (v) das Mess-Skript könnte
  die Rückschrift nach dem Lauf selbst ausführen — ein Kommando, ein Commit;
  (w) drei Commits für eine 0,1-s-Zählung (Commit vor dem Lauf, Lauf-
  Artefakte, README-Korrektur) — bei seconds einen Commit nach dem Lauf
  zulassen, wenn der Lauf aus dem committeten Stand reproduzierbar ist;
  (n) bleibt: Feldnamen aus dem Task stempeln.
  **Gebaut 2026-10-13 (0.88.1): (u)+(r)** — bei einer Zählung stempelt die
  README keinen Platzhalter mehr (Frage und Vertrag leben im Protokoll), und
  der Testpfad im Zustandskasten stimmt. Prüfstelle: ein Cloud-Durchgang auf
  0.88.1 mit null Gate-Zeilen.
  Durchgang 12 (Fable, noch 0.88.0, 1m34s, 0 Gate-Zeilen im Log, README-
  Warnung im selben Schritt erledigt) bestätigt 11; neu genannt: (x) `runlog`
  könnte den Commit vor dem Lauf selbst machen (`runlog --commit`) — gehört zu
  (w). Seit 0.88.2 trägt jede Score-Datei das Modell (`usability score
  --agent`).
  **Haiku 5.5 auf 0.88.1 (2026-10-13, 1m13s, `2026-10-13-cloud-haiku-count-2.score.json`):**
  zwei echte Befunde, beide in 0.88.3 behoben — `protocol-fill --list` nannte
  den Kopf-Platzhalter `type` nicht (Hook: „MISSING (must): [protocol] type“,
  Hand-Edit), und die Sekunden-Spur der Agenten-Vorlage verlangte noch
  Kriterium und Zulässigkeit (Widerspruch zu `--contract`, seit dem
  0.87.0-Schnitt veraltet). Haikus Liste sonst: (n), (v), (w) — schon notiert.
  Prüfstelle: ein Haiku-Durchgang auf 0.88.3 ohne `unsure`-Zeile.
  **Haiku H3 (noch 0.88.1, 2m30s, `2026-10-13-cloud-haiku-count-3.score.json`):**
  derselbe `type`-Umweg; neu und behoben in 0.88.4: (l) — der Index trug
  `+dirty` für jeden Lauf, weil der Endzustand die eigenen ungetrackten
  Produkte zählte (uniagent 74/74 Zeilen); jetzt zählen am Ende nur getrackte
  Dateien, am Start weiter auch ungetrackte. Haikus `unsure` (leerer
  Fall-Ordner: 0 oder Verweigerung?) ist eine Skelett-Formulierung, notiert
  als (y): „empty item" im Skelett-Docstring eindeutig machen.
  **Haiku H4 (noch 0.88.1, 1m47s, `2026-10-13-cloud-haiku-count-4.score.json`):**
  drei Befunde, alle in 0.88.5 behoben — BrokenPipe-Traceback bei `--contract
  | head` (jetzt ein Ausgang für alle Kommandos, `labkit/console.py`),
  `protocol-check PFAD --contract` las die Flagge als Datei, `--check` vor der
  Rückschrift sagte „numbers not in“ statt „noch keine Antwort, `--from-run`“.
  Neu notiert: (z) Skelett für eine Quelle mit Ordner je Item (`rows()` braucht
  den Pfad je Fall, nicht nur die id) — gehört zu (n). Prüfstelle: der nächste
  Durchgang auf v0.88.5, der erste mit allen Fixes seit 0.88.1.
  **Haiku H5 (0.88.5, 0m54s, `2026-10-13-cloud-haiku-count-5.score.json`):**
  Prüfstelle bestanden — keiner der drei H4-Befunde taucht in Log oder
  Bericht auf; 0 unsure, 0 Quelltext-Lesungen, 3 Edits, der kürzeste
  Durchgang der Reihe (Spanne mit Vorbehalt: Log erst nach den ersten
  Lesungen angelegt). Seine Liste: (n)/(z) die drei Stubs des Zählskeletts
  zwingen zum Lesen von Skript und Bereichstest; (w) `log.md` ignoriert
  kostet einen zweiten Commit. Neu notiert: (q) `Terms of this protocol`
  wird bei einer Zählung ohne Prägung geschuldet, und `protocol-fill` nimmt
  ein Label je Aufruf — entscheiden, ob das Feld bei seconds ohne Modell
  „n/a“ sein darf und ob `protocol-fill` mehrere Label in einem Aufruf
  nimmt; (t) `data=` friert die Fallliste ein, nicht die Dokumentdateien,
  die die Zahl zählt — die Zahl ist gegen `cases.jsonl` zitierbar, nicht
  gegen den Inhalt der Eingaben; entscheiden, ob das Zählskelett den
  Eingabeordner (Hash je Datei) mit einfriert.
  **Haiku H6 (0.88.5, 1m00s, `2026-10-13-cloud-haiku-count-6.score.json`):**
  zweiter Durchgang auf dem Stand, wieder ohne H4-Befunde; 0 unsure, 0
  Quelltext-Lesungen. Wiederholt (n)/(z), (w), (t). Neu notiert: (y) die
  gestempelte Runs-Zeile `<run_id> — <one sentence…>` gilt für `code-check`
  und den Hook vor dem Lauf als „still verbatim template text“, obwohl erst
  `--from-run` sie schreibt — der Agent prüfte, ob das blockt; entscheiden,
  ob die Zeile vor dem ersten Lauf ausgenommen wird oder die Meldung sagt
  „wird von `--from-run` geschrieben“. (aa) Bereichstest bei seconds
  weglassen, weil Lauf und `--check` die Arithmetik schon halten —
  Entscheidung, nicht Werkzeug.
  **Haiku H7 (0.88.5, 1m23s, `2026-10-13-cloud-haiku-count-7.score.json`):**
  dritter Durchgang, wieder ohne H4-Befunde; 26 run-Zeilen, sieben davon
  `protocol-fill` (die Frage zweimal umformuliert, einmal `--force`, nachdem
  das Label „Question / hypothesis“ zu einer erfundenen Erwartung verleitet
  hatte — gehört zu (q)). Drei gate- und zwei unsure-Zeilen nachträglich
  geschrieben, die Spanne enthält die Log-Durchsicht. Wiederholt (q), (n)/(z),
  (w), (y). Neu notiert: (ab) ein Helfer, der Log-Zeile und Schritt in einem
  Aufruf anhängt und ausführt — Logging von Hand verführt zum Bündeln.
  **Stand 0.88.5: n = 3, Median 1m00s (54 s, 60 s, 83 s) gegen Median 1m47s
  für Haiku auf 0.88.1 (1m13s, 2m30s, 1m47s).**
  **Entschieden 2026-10-13, gebaut in 0.88.7:** (q) `protocol-fill` mit
  mehreren `LABEL=WERT` je Aufruf, die Zähl-Platzhalter sagen „n/a — no
  coinage“ und „a count tests no hypothesis“ (Labels bleiben, eine Heimat je
  Feld); (t) `INPUTS` im Zählskelett, `data=` friert Quelle und Eingabeordner;
  (y) die gestempelte Runs-Zeile ist vor dem Lauf kein Rest, `protocol-check`
  nennt `--from-run`; (ab) `usability log` schreibt die Zeile und führt den
  Schritt aus, die Aufgabenblätter nennen es. **(aa) nein:** der Bereichstest
  bleibt, zahlproduzierende Funktion → Test. **(n)/(z) offen:** nicht auf das
  schwächste Modell zuschneiden; Prüfstelle ist die nächste Reihe auf 0.88.7
  — nennt ein Fable- oder Sonnet-Durchgang die Stubs noch, dann bauen.
  Prüfstelle für 0.88.7: Reihe n = 3, Median unter einer Minute, kein
  Durchgang nennt (q) mehr, keine nachträglichen Log-Zeilen.
  **Haiku H8 (0.88.7, 1m12s, `2026-10-13-cloud-haiku-count-8.score.json`):**
  erster Durchgang mit den vier Schnitten, alle gehalten — Registrierung in
  einem Aufruf, Terms „n/a — no coinage“, Frage ohne Hypothese, `inputs`
  eingefroren (42 Dateien), Log aus `usability log`, 0 unsure, 0 gate, keine
  nachträgliche Zeile. (q) wird nicht mehr als Aufrufzahl genannt, nur noch
  das Formulieren der Werte. Wiederholt (n)/(z). Neu: (ac) `.venv/bin/usability`
  aus dem Bereichsverzeichnis aufgerufen → exit 127; das Aufgabenblatt sagt
  „from the repo root“ oder nennt den absoluten Pfad. **Gebaut 2026-10-14:**
  beide Aufgabenblätter sagen oben, dass jeder `.venv/bin/…`-Pfad vom
  Repo-Root aus gilt; Prüfstelle: der nächste Durchgang, kein exit 127. (ad) Rückschrift als
  Teil des Laufs: `runlog.run(..., protocol=…)` schreibt Answer, Result und
  Runs am Ende eines abgeschlossenen Laufs — Entscheidung, spart zwei
  Kommandos und einen Commit, nimmt dem Agenten aber den Blick auf die
  Zeilen. (ae) Schrittlog bei seconds weglassen — nein, das Log ist das
  Messinstrument der Probe, nicht Regel der Lane.
  **Falle beim Nachstempeln, behoben (0.88.8, 2026-10-13):** `labkit_pin()`
  las die Version aus den Paket-Metadaten, die eines editierbaren Installs
  stammen vom letzten `pip install -e` — der erste `--restamp` nach dem
  Release 0.88.7 pinnte v0.88.5 mit 0.88.7-Vorlagen (zurückgesetzt, neu
  gestempelt). Jetzt verweigert `labkit_pin()` bei Widerspruch zwischen
  Metadaten und Quelle, und `just release` installiert nach dem Tag neu.
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

**Stand 2026-10-14: alle drei Zeilen gebaut.** `AGENTS.md` stempelt
`labkit-init lab` (0.78.0), der Audit ist `labkit-audit` (0.79.0), und die
Harness-Erkennung kam auf Ansage (Codex soll die Verallgemeinerung
mittragen können): `runlog.foreground_timeout()` liest
`LABKIT_FOREGROUND_TIMEOUT_S` (Sekunden, `0` = kein Limit) für jeden Agenten,
`CLAUDECODE` gilt ohne die Variable als 600 s. README („Detach gate“) und
die `AGENTS.md`-Vorlage (Setup) sagen, wo man sie setzt. **Offen:** ob
Codex seiner Shell die Variable per Konfiguration mitgibt, ist nicht
geprüft — Prüfstelle: der erste Codex-Lauf im Labor, dort einen
`long=True`-Lauf im Vordergrund starten und die Verweigerung sehen.
Die Claude-Hooks bleiben Adapter; ein zweiter Adapter nur für einen
Harness mit Hooks.

**Codex-Prüfung 2026-10-14 (Codex selbst, nichts geändert):**
`runlog.foreground_timeout()` liefert unter Codex `None` / mit `=300`
`(300.0, 'LABKIT_FOREGROUND_TIMEOUT_S')` / mit `=0` `None`; die Suite läuft
dort grün (1042 Tests, 117 s im Vordergrund). Codex dokumentiert kein
festes Zeitlimit für einen Vordergrundbefehl (Config Reference, geprüft:
nur `background_terminal_max_timeout` für das Polling), die Variable ist
dort also nicht nötig, solange nichts getötet wird. Setzen ginge über
`shell_environment_policy.set` in `~/.codex/config.toml` oder
`.codex/config.toml` (Config Reference: „Explicit environment values
injected after exclusions“) — so in README und `AGENTS.md`-Vorlage. Die
Probe gibt dem kalten Agenten jetzt `AGENTS.md` statt `CLAUDE.md` (Inhalt
gleich, `CLAUDE.md` ist der Link). Nebenbefund ohne labkit-Bezug: in der
Codex-Sandbox scheitert `pip install -e` am gesperrten Netz
(`setuptools>=68`), mit Netzfreigabe läuft es. Offen: ob Codex einen
Vordergrundprozess am Sitzungsende beendet — erst bei einem echten
Mehrstundenlauf unter Codex sichtbar.

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
