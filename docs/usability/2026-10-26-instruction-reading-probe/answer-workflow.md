# Unabhängiger Lesetest: Entry und Workflow

Grundlage ausschließlich `cases.txt`, `entry-instructions.md` und `workflow-instructions.md`. Die Fälle behandle ich unabhängig. Die folgenden Befehle sind vorgeschlagene Schritte; ich habe weder Experimente noch Modellaufrufe ausgeführt. Alle Fälle liegen auf der Lane `low`; Anforderungen der Lane `high` übertrage ich nicht darauf.

## 1. Sauberer Lauf, Conclusion noch leer

**Nächste Handlung:** Die Conclusion als Antwort auf die registrierte Frage formulieren. Dass finalize besteht und das Analyseaudit keine Findings hat, ersetzt diese Antwort nicht.

**Restliche Reihenfolge:**

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<höchstens zwei klare Sätze zur Frage>"
protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392
protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md
report-check experiments/01-study
```

Den Berichtstext um den generierten Block herum ausarbeiten und auf zutreffende Interpretation prüfen. Falls ein Modell eingebunden ist, zusätzlich die verlangten Raw-output-Beispiele aus der benannten Ausgabedatei beachten; bei null Findings wird kein Beispiel „per finding“ konkret verlangt. Den fertigen Stand einschließlich Protokoll, Bericht und gegebenenfalls noch nicht erfasster Auditdateien committen; `output/` und `runs/` müssen ebenfalls in Git sein. Der Workflow dokumentiert dafür `git add -A && git commit`; der installierte Pre-commit prüft den Index. Bei einem Blocker erst dessen Ursache beheben. Danach den fertigen Bericht ausliefern; auch der Stop-Hook hält den Bericht an die Prüfungen.

**Was in REPORT.md behauptet werden darf:** Jetzt, vor Adoption und Berichtsgenerierung, ist der Messwert noch kein freigegebenes berichtetes Ergebnis. Nach erfolgreicher Adoption darf der generierte Ergebnisblock die gespeicherten Messwerte zeigen; daneben steht die fachlich gerechtfertigte Antwort. Keine frei erfundenen oder von Hand übertragenen Ergebniszahlen. Ein bestandener Gate beweist nicht die semantische Richtigkeit der Interpretation.

**Belege:** Entry low 6: „never retype them“, Conclusion als „the question's answer in at most two plain sentences“, `--into REPORT.md`, sowie „Commit output/ and runs/ with the protocol“. Workflow 7: „The Conclusion is the author's sentence, written before this step“; Workflow 8 beschreibt den generierten Block und erklärt zur Prosa: „What it does not: the prose beside it.“ Workflow 9 nennt Stop und Commit als Gatezeitpunkte. Workflow 4: finalize „does not release one“.

**Offen:** Die tatsächliche Conclusion und der fachlich tragfähige Anspruch fehlen in der Fallbeschreibung. `kind fit` allein sagt nicht, ob ein `[model]`-Backend beteiligt ist. Ein spezieller Auslieferungsbefehl wird nicht dokumentiert. Eine Decision Review ist ohne entsprechenden akzeptierten BLOCKER nicht verlangt.

## 2. Zwei Leckagefeatures, nur eines entfernt, kein neuer Lauf

**Nächste Handlung:** Das Finding bleibt ungelöst. Die konkrete Forderung umfasst beide Features und eine Diagnose; eine einzelne Codeänderung ohne neuen Lauf erfüllt sie nicht. Für eine Behebung das zweite Feature entfernen und die verlangte Diagnose planen und durchführen. Nach Codeänderungen:

```sh
code-check experiments/01-study
```

Anschließend den geänderten Code committen und mit ihm neu messen; der dokumentierte Aufruf ist:

```sh
git add -A && git commit
.venv/bin/python experiments/01-study/scripts/01_measure.py
git add -A && git commit
finalize experiments/01-study
labkit-audit experiments/01-study --mode analysis
```

Die Diagnose muss tatsächlich aussagekräftige Evidenz liefern; der genaue Diagnosebefehl steht hier nicht. Den bisherigen Datensatz nicht als Ergebnis des reparierten Instruments ausgeben. Das neue Analyseaudit muss zum jetzigen Code und neuen antwortenden Lauf passen. Die Findings anhand der neuen Evidenz entscheiden; die dokumentierte Entscheidungsform für das alte Finding lautet:

```sh
labkit-audit experiments/01-study --decide <N> fixed "<Begründung mit Belegen zur vollständigen Behebung und Diagnose>" --record 2026-10-26T08-28-analysis.toml
```

Danach gegebenenfalls neue Findings entscheiden und die Folge aus Conclusion, Adoption des neuen Laufs, Berichtsgenerierung und Gate durchlaufen.

**Wann `fixed`:** Erst wenn die benannte Ursache vollständig beseitigt und die verlangte Diagnose durchgeführt sowie bewertet ist. Das ist meine wissenschaftliche Auslegung der konkreten Findingforderung, keine ausdrücklich definierte automatische `fixed`-Prüfung. Das bloße Eintragen von `fixed` behebt weder den alten Lauf noch dessen Leckage. Der Workflow verlangt einen deckenden Analyseaudit zum aktuellen Code und Lauf; ein alter Auditstamp reicht nach Änderungen nicht. Eine Reviewpflicht für jedes erstmalige `fixed` ist nicht dokumentiert. Falls eine Review diese Entscheidung vorher nicht bestätigt hatte, greift dagegen die zusätzliche Reviewpflicht aus Workflow 6; diese Vorgeschichte nennt der Fall nicht.

**Was in REPORT.md jetzt steht:** Kein sauberer Erfolg auf Basis eines reparierten Instruments. Sachlich berichtbar ist der offene Leckagebefund, die teilweise Codekorrektur und das Fehlen der Wiederholung. Für die Darstellung eines nicht adoptierten Laufs dient der Diskussionsblock aus Fall 4, mit dem zutreffenden Grund und offener Frage.

**Belege:** Workflow 1: `code-check` „after every code change“; Entry low 4: „Commit, then the run“; Workflow 5 bindet Auditrecords an `scope_sha`, `block_sha`, Registrierung und Lauf. Workflow 7 verlangt Records, deren Stamps „are the area's now“. Workflow 6 beschreibt für überprüftes `fixed` die Frage, ob „the fault [is] gone in the files as audited“.

**Offen:** Weder die Diagnose noch ein allgemeines Beweisverfahren oder eine genaue zeitliche CLI-Pflicht für das erstmalige Setzen von `fixed` wird festgelegt. Die Findingnummer ist nicht gegeben. Die Anleitung erläutert nicht, wie ein altes Finding nach einem Neuaudit mit veränderten Stamps formal fortgeführt wird; ich erfinde dafür keinen Schalter.

## 3. Akzeptierter BLOCKER mit `stands`; unabhängig davon abgelehnte Review

**Erster Teil – nächste Schritte:** Zuerst die Conclusion innerhalb der akzeptierten Einschränkung schreiben, dann die Decision Review anstoßen:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<Antwort innerhalb der akzeptierten Grenze>"
labkit-audit experiments/01-study --review --record 2026-10-26T08-28-analysis.toml
```

Erst ein `upheld` gibt diesen Entscheidungspfad frei. Danach den Lauf adoptieren, den REPORT-Block generieren und die Gate-/Commitfolge aus Fall 1 durchlaufen. Vorher ist das akzeptierte `stands` allein keine Freigabe. Im fertigen REPORT stehen der generierte Messwert und seine generierten Limit-Zeilen; `stands` erlaubt nur die innerhalb dieser Grenze begründete Aussage.

**Zweiter, unabhängiger Teil – Review abgelehnt:** Keinen weiteren unveränderten Reviewaufruf auf eine günstigere Antwort hin versuchen. Entscheidung sachlich neu bearbeiten: Conclusion einschränken, Effekt ändern oder Fehler beheben. Anschließend eine Review der veränderten Entscheidung bzw. des veränderten Anspruchs, soweit erforderlich. Bei einem nun als `dismissed`, `fixed` oder `deferred` geschlossenen Finding hebt die Umbenennung die Prüfung nicht auf: Auch diese neue Entscheidung braucht nach der abgelehnten Review eine bestätigende Review. Ein sinnvoll begründetes `not assessable` ist als anderer Effekt dokumentiert; daraus darf kein erfülltes C1 behauptet werden.

**Belege:** Entry low 5: „write the Conclusion first“, die Review vor der Conclusion wird beim Schreiben veraltet; Ablehnung heißt „deciding again … not drawing again“. Workflow 6: „Only upheld releases“, „the command refuses a second draw on an unchanged state“ und „A reason alone releases nothing“; dort ausdrücklich die Reviewpflicht nach anschließendem `dismissed`, `fixed` oder `deferred`.

**Offen:** Welche Einschränkung wissenschaftlich genügt, kann ohne Finding, C1 und Daten nicht entschieden werden. Der Fall sagt im unabhängigen Ablehnungsszenario nicht, welche neue Entscheidung sachlich richtig ist. Die Anleitung definiert die formalen Grenzfälle einer Effektänderung nach Ablehnung nicht vollständig; ich unterstelle keine Freigabe durch einen bloßen Statuswechsel.

## 4. Fehlgeschlagener Analyseaudit, Adoption verweigert, Zeit knapp

**Nächste Handlung und Lieferung:** Den verweigerten Ergebnisstatus offen berichten. Die erfüllte Metrikschwelle und der Zeitdruck ersetzen keinen deckenden, entschiedenen Analyseaudit. Wenn die Ursache jetzt nicht behoben werden kann, einen Diskussionsbericht liefern und die Frage ausdrücklich offenlassen:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md --discuss 2026-10-26T08-18-33_7392 --why "Adoption verweigert: Analyseaudit fehlgeschlagen; kein freigabefähiger Analyseaudit zum Lauf. Die Forschungsfrage bleibt offen." --into REPORT.md
```

Die konkrete Auditfehlermeldung und die tatsächlichen Beobachtungen gehören zusätzlich in den Grund, soweit bekannt. Der Grund oben erfindet keine Ursache für das Auditversagen. Danach den Bericht prüfen und im vorgesehenen Commit-/Stopprozess liefern. Kein generierter Ergebnisblock für einen adoptierten Lauf, kein von Hand als Ergebnis nachgeschriebener Schwellenwert oder Erfolgsclaim. Die Anleitung nennt als Textform außerdem:

```text
run 2026-10-26T08-18-33_7392 (not reported: Analyseaudit fehlgeschlagen; Adoption verweigert)
```

**Was behauptet werden darf:** Der Audit ist fehlgeschlagen, die Adoption wurde verweigert, die Frage bleibt offen. Die Zahlen sind damit nicht als berichtetes Ergebnis freigegeben. Ich würde auch kein „Erfolg trotz Audit“ formulieren. Die Anleitung nennt Zahlen in/neben Diskussionsblöcken nur Hinweise ohne Ergebnispromotion; sie fordert hier gerade, die Verweigerung zu berichten und dort zu enden.

**Belege:** Entry low 6: „do not write the run's numbers into a report as the result“, „A refusal is a finding to report“, die genannte `run … (not reported: …)`-Form und „say that the question stays open, and end there“. Workflow 8 dokumentiert ausdrücklich `--discuss … --why … --into REPORT.md`. Workflow 9 verlangt einen entschiedenen, deckenden Analyseaudit.

**Offen / Spannung:** Der Entry-Text bietet für `low` eine freie Textform an, während Workflow 8 einen strukturierten Diskussionsblock als Ausweg beschreibt. Ob die freie Textform allein den aktuellen Gate genügt, ist damit nicht eindeutig; ich verwende den ausdrücklich dokumentierten Blockbefehl. Was das fehlgeschlagene Audit technisch verursacht hat und wie man es repariert, ist nicht angegeben.

## 5. Conclusion nach bestätigter Review verstärkt

**Antwort:** In diesem Zustand nicht ausliefern. Der Anspruch hat sich geändert und damit ist die bisherige Review veraltet, obwohl Code, Messwerte und Entscheidungen gleich geblieben sind.

**Nächste Schritte:** Die stärkere Conclusion fachlich an den Limit-Zeilen messen; falls sie nicht getragen ist, zuerst einschränken. Dann die aktuelle Conclusion erneut reviewen:

```sh
labkit-audit experiments/01-study --review --record 2026-10-26T08-28-analysis.toml
report-check experiments/01-study
```

Bei `upheld` und sauberem Gate kann der fertige Stand durch Commit und Stop gehen. Bei Ablehnung entsprechend Fall 3 neu entscheiden; keine weiteren unveränderten Versuche. Ein neuer Messlauf oder ein neues Analyseaudit ist allein durch die veränderte Conclusion nicht dokumentiert vorgeschrieben: Workflow 5 grenzt die späteren Berichtsfelder von der auditgebundenen Registrierung ab. Auch erneute Adoption oder erneutes `--render` ist bei unveränderten Quellen und Entscheidungen nicht ausdrücklich gefordert; `--render` regeneriert die erzeugten Zeilen, bestätigt aber keine neue Conclusion. Den bestehenden REPORT-Block und die danebenstehende Prosa auf Konsistenz prüfen; bei geänderter Ergebnisdarstellung den dokumentierten `--into REPORT.md`-Befehl verwenden.

**Was REPORT.md jetzt behaupten darf:** Der bestehende Zahlenblock ändert sich durch die neue Conclusion nicht inhaltlich. Die stärkere Behauptung ist aber noch nicht durch die erforderliche aktuelle Decision Review freigegeben. Eine frühere Bestätigung darf nicht als Bestätigung des neuen Anspruchs dargestellt werden.

**Belege:** Workflow 6: Review ist „bound to the decision and the Conclusion as reviewed — change either and the review is stale“. Entry low 5 sagt schon für die nachträglich geschriebene Conclusion, dass eine vorherige Review veraltet. Workflow 8 begrenzt die Blockgarantie ausdrücklich gegenüber der umgebenden Prosa. Workflow 9 verlangt die bestätigte `stands`-Review am Gate.

**Offen:** Ob die verstärkte Conclusion tatsächlich tragfähig ist, ist ohne ihren Text und die Befunde nicht entscheidbar. Keine weitere formale Änderungsvoraussetzung für den erneuten Reviewaufruf wird hier beschrieben.

## 6. Vorhersagen am falschen Pfad

**Antwort:** Die externe Aufgabe ist nicht abgeschlossen. Das geforderte Artefakt fehlt unter `pred_results/predictions.csv` im Repositoryroot. Der vorhandene Pfad `experiments/01-study/output/pred_results/predictions.csv` ist ein anderer Ort. Das folgt unmittelbar aus der externen Aufgabenforderung, nicht aus einem behaupteten labkit-Gate.

**Nächste Handlung:** Die tatsächlichen Vorhersagen mit der vorgesehenen Struktur am geforderten Rootpfad bereitstellen und die gelieferte Datei prüfen. Falls der Messcode dafür geändert wird, anschließend `code-check experiments/01-study`, Commit und gegebenenfalls neuen Lauf samt nachfolgender Prüf-/Audit-/Berichtskette durchführen. Ob eine Kopie als reines Lieferartefakt genügt oder der Lauf den Rootpfad selbst erzeugen muss, ist nicht angegeben; ich entscheide das nicht durch Erfinden einer Provenienzregel. Nicht einfach erneut messen, ohne zu klären, wie die Ausgabe den externen Ort erreicht.

**Was REPORT.md behaupten darf:** Ein bestandener finalize zeigt nur die dokumentierten Prüfungen; es beweist weder vollständige externe Lieferung noch Vorhandensein der Rootdatei. Ein Bericht kann die Laufresultate nach der regulären Audit-/Adoptionsfolge darstellen, darf aber die externe Vorhersageabgabe derzeit nicht als erledigt ausgeben.

**Dokumentierte Checks und ihre Grenze:** Workflow 4 nennt als finalize-Stationen unter anderem „the output rows were written by it“, unveränderte deklarierte Scopes, Gittracking, Bereichstest und Nenner. „Clean means the run can carry a number; it does not release one.“ Workflow 9 ergänzt Analyseaudit, Rendering und `02_analyze.py --check`. Keine dieser Passagen nennt einen verpflichtenden Check auf den extern geforderten Repositoryrootpfad. `code-check` prüft laut Workflow 1 deklarierte Keys, PROMPT-Konstanten und Parserfixtures; das beweist keinen Lieferpfad. Auch die Garantie des Reportblocks aus Workflow 8 betrifft Quellenbindung und Protokollkette.

**Eigene Prüfung, keine dokumentierte labkit-Pflicht:** Existenz und Inhalt der tatsächlichen Rootdatei direkt gegen die externe Spezifikation prüfen, beispielsweise mittels eines geeigneten Dateiexistenz- und CSV-Inhaltschecks. Ein bloßer Existenzcheck würde noch keine korrekten Spalten, Zeilen, Zuordnungen oder Vorhersagewerte nachweisen. Dafür stehen hier weder Schema noch spezifischer Prüfcommand.

**Lücke:** Es wird kein labkit-Befehl dokumentiert, der diese externe Pfadanforderung mechanisch erfasst oder nachweist. Ebenso fehlen ein verbindlicher Liefer-/Kopierbefehl und Angaben, ob die externe Artefaktanforderung in der Registrierung oder im Bereichstest kodiert ist. Aus `finalize passed` darf diese Abdeckung nicht abgeleitet werden.

## Lesespannungen zwischen den beiden Anweisungen

Der Entry sagt am Ende der Low-Lane ausdrücklich, man solle dort aufhören und nur die Bereichs-README lesen. Die Probe weist mich dagegen explizit an, zusätzlich den Workflow zu lesen; für diesen Lesetest folge ich der Probe, nicht einem stillschweigenden Aufheben dieser Spannung für einen normalen Arbeitslauf. Außerdem beschreibt Entry low 6 die Conclusion als nach `--from-run` noch eigene Arbeit; Workflow 7 sagt ausdrücklich, sie werde davor geschrieben. Fall 1 folgt der präzisen Workflow-Reihenfolge. Bei `stands` verlangen ohnehin beide Texte zwingend Conclusion vor Review und Review vor Freigabe. Die unterschiedliche Dokumentation des Diskussionsauswegs ist in Fall 4 vermerkt.
