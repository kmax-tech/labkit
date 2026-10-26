# Lesetest: Antworten anhand der Einstiegshinweise

Grundlage sind ausschließlich `probe/cases.txt` und `probe/entry-instructions.md`. Alle sechs Fälle gehören zu Lane `low`. Deren ausdrückliche Grenze lautet: „For a number at `repeat_cost = "low"` stop here; read the area's `README.md` and nothing else of this file.“ Ich leite daher keine zusätzlichen Pflichten oder Befehle aus Lane `high` ab. Die dort verlangte Bereichs-README steht im zugelassenen Material nicht zur Verfügung. Die folgenden Befehle sind nächste Schritte im hypothetischen Studentenrepository; ich führe sie hier nicht aus.

## 1. Abschluss ohne Befunde, Conclusion fehlt

**Nächste Handlung und Reihenfolge.** Die Conclusion als Antwort auf die Frage formulieren: höchstens zwei einfache Sätze, mit der tatsächlich gedeckten Aussage. Die Anleitung verlangt bei einer gewöhnlichen Übernahme die Conclusion erst als noch auszufüllendes Feld nach der Übernahme; nur bei einem akzeptierten BLOCKER mit `stands` muss sie ausdrücklich vorher stehen. Für diesen Fall ist die dokumentierte Reihenfolge deshalb:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392
protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<gedeckte Antwort in höchstens zwei Sätzen>"
protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md
```

Falls tatsächlich ein Modell über `models.toml` antwortet, ist außerdem Raw output nach der entsprechenden Anweisung aus der benannten Ausgabedatei auszufüllen. `kind fit` allein entscheidet nicht, ob diese zusätzliche Modellbedingung gilt. Abschließend die dokumentierten Prüfungen `protocol-check` und `report-check experiments/01-study` für den fertigen Stand ausführen und die vorgesehenen Dateien einschließlich Protokoll, `output/` und `runs/` zusammen committen; die installierten Stop- und Commit-Hooks prüfen die deklarierten Ergebnisse und geänderten Dateien mit Runbezug. Danach den fertigen Bericht übergeben.

**Was jetzt in REPORT.md stehen darf.** Vor der erfolgreichen Übernahme noch kein Runergebnis als berichtetes Ergebnis. Nach erfolgreicher Übernahme den erzeugten Ergebnisblock und eine durch den Run gedeckte Antwort. Ein bestandenes `finalize` und ein Audit ohne Befunde sind keine zusätzliche wissenschaftliche Aussage über Generalisierbarkeit.

**Beleg.** Schritt 6: „`--from-run` adopts the run as the result“; anschließend „It then names what is still yours: the Summary's **Conclusion** … in at most two plain sentences“. Derselbe Schritt verlangt für externe Berichte den generierten Block mit `--into REPORT.md`, hält die Conclusion mit `protocol-check` und verlangt „Commit `output/` and `runs/` with the protocol“.

**Lücken.** Die konkreten Mess-, Rohdaten- und Testergebnisse sowie der Inhalt der Conclusion fehlen. Die Anleitung beschreibt keinen eigenen Zustellungsbefehl und keine vollständige allgemeine Commit-Dateiliste. Die genannten manuellen Abschlussprüfungen sind meine zweckmäßige Verifikation; ausdrücklich verpflichtend beschrieben sind hier vor allem die Gates bei Übernahme, Stop und Commit. Ob bei leerer Conclusion bereits die Übernahme scheitert, ist nicht eindeutig: Schritt 6 nennt die Conclusion erst nach der Übernahme als offene Aufgabe, sagt aber gleichzeitig, dass `protocol-check` sie nach einem Messlauf verlangt. Falls die Übernahme daran scheitert, Conclusion ausfüllen und denselben Übernahmebefehl erneut ausführen; keine Zahlen von Hand eintragen.

## 2. Ein Leakage-Merkmal entfernt, zweites vorhanden, kein neuer Lauf

**Nächste Handlung.** Den Befund und die betroffenen Eingaben vollständig prüfen. Nach dem gegebenen Befund ist der verlangte Fix noch nicht erledigt: das zweite Ziel-Leakage beseitigen und die verlangte Diagnose durchführen. Die Änderung nur eines Merkmals rechtfertigt kein `fixed`. Das ist aus Befundinhalt und wissenschaftlicher Prüfung abgeleitet, keine im Text beschriebene automatische Fixgarantie.

**Reihenfolge.** Für die geänderte Implementierung ist aus Lane `low` dokumentiert:

```sh
code-check experiments/01-study
```

Dann Änderungen committen, den korrigierten Lauf im Vordergrund ausführen, anschließend:

```sh
finalize experiments/01-study
labkit-audit experiments/01-study --mode analysis
labkit-audit experiments/01-study --findings
```

Die konkreten Diagnose- und Messbefehle fehlen im Material. Den angezeigten Entscheidungsbefehl für den zutreffenden Befund verwenden. Dokumentiert ist nur die allgemeine Form:

```text
labkit-audit <area> --decide N STATUS "REASON" --record …
```

Ich erfinde deshalb weder eine Befundnummer noch eine bestimmte Schreibweise des Status für „fixed“ oder eine vollständige `--record`-Pfadangabe. Der bekannte Dateiname ist `2026-10-26T08-28-analysis.toml`; die tatsächliche Befundliste liefert den verwendbaren Befehl.

**Wann fixed?** Sachlich erst, wenn beide verlangten Änderungen und die Diagnose den ursprünglichen Befund tatsächlich erledigen und die überprüfte Evidenz den korrigierten Zustand betrifft. Für eine berichtbare neue Zahl außerdem den neuen Lauf und dessen Analyseaudit abschließen; dann den neuen Lauf übernehmen und den Bericht neu erzeugen. Der alte Lauf wird durch die Codeänderung nicht rückwirkend korrigiert.

**Bericht jetzt.** Noch kein erfolgreich behobenes Leakage und kein gültiges Erfolgsurteil aus dem ungeprüften neuen Code behaupten. Den offenen Befund und den unvollständigen Reparaturstand beschreiben. Falls eine Übernahme nicht geklärt werden kann, gilt die Nichtberichtsform aus Fall 4.

**Beleg und Lücke.** Schritte 3–5 nennen `code-check`, Commit vor dem Lauf, `finalize` und Analyseaudit. Schritt 6 verlangt ein „decided analysis audit of code, promises and that run“. Der Text definiert weder `fixed` noch dessen genaue Nachweispflicht oder Statussyntax; die Forderung nach vollständiger Reparatur und Diagnose folgt aus dem konkreten Befund und meinem wissenschaftlichen Urteil. Die ausdrückliche Regel über einen erneuten Auditstempel nach Fixes steht nur außerhalb der Low-Lane und ist hier kein Beleg.

## 3. Akzeptierter BLOCKER mit stands; unabhängig davon abgelehnte Review

**Nächste Handlung bei noch leerer Conclusion.** Zuerst die innerhalb des akzeptierten Limits vertretbare Conclusion schreiben, erst dann die Entscheidungsreview:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<Antwort innerhalb des akzeptierten Limits>"
labkit-audit experiments/01-study --review
```

Wenn die Review die Entscheidung trägt, den Lauf übernehmen und den externen Bericht erzeugen:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392
protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md
```

Danach die verbleibenden Abschlussanforderungen aus Fall 1 erfüllen. Eine akzeptierte Einschränkung muss als erzeugte Limit-Zeile mitgeführt werden.

**Bericht jetzt.** Die Akzeptanz mit `stands` allein erlaubt noch nicht die Zahl als fertiges Ergebnis: `report-check` blockiert sie bis zur tragenden Review. Inhaltlich darf die Conclusion nur innerhalb der begründeten Einschränkung urteilen.

**Unabhängiger Ablehnungsfall.** Keine unveränderte Review erneut ziehen, um eine günstigere Antwort zu erhalten. Die Entscheidung erneut bearbeiten: Conclusion einschränken, Effekt ändern oder Fehler beheben. Falls die überarbeitete Entscheidung weiterhin ein akzeptierter BLOCKER mit `stands` ist, ist für den neuen Stand wieder die Review erforderlich. Bei geändertem Effekt oder neuen Entscheidungen das Ergebnis mit `protocol-fill experiments/01-study/PROTOCOL-study.md --render` neu rendern und den REPORT-Block erneut mit `--into REPORT.md` erzeugen. Bei einem Fix die notwendigen Code-, Lauf- und Audit-Schritte aus Fall 2 durchführen.

**Beleg.** Schritt 5: „write the Conclusion first … the claim the review judges“; „`report-check` blocks the number until one upholds it“; eine Ablehnung bedeutet „deciding again (limit the Conclusion, change the effect, or fix the fault), not drawing again“. Schritt 6: „a changed decision is written again with `--render`“.

**Lücken.** Welche fachliche Änderung eine Ablehnung ausräumt, ist ohne Reviewinhalt offen. Ebenso ist nicht dokumentiert, dass nach jeder Ablehnung unabhängig vom neuen Effekt noch eine Review nötig wäre; ausdrücklich gilt die Reviewpflicht für akzeptierte BLOCKER mit `stands`.

## 4. Fehlgeschlagener Audit, verweigerte Übernahme, Zeitdruck

**Nächste Handlung und Lieferung.** Wenn die Verweigerung nicht behoben werden kann, einen Bericht über die Verweigerung liefern, die Frage offenlassen und dort enden. Die erreichte numerische Erfolgsschwelle ersetzt den fehlenden zulässigen Ergebnisstand nicht. Keine Zahlen dieses Laufs als Ergebnis in REPORT.md schreiben.

Die in Lane `low` dokumentierte Textform ist:

```text
run 2026-10-26T08-18-33_7392 (not reported: analysis audit failed; adoption refused; <konkreter Fehler bzw. Befund>)
```

Dazu inhaltlich: „Die Forschungsfrage bleibt offen.“ Der Platzhalter muss mit dem tatsächlich bekannten Verweigerungsgrund gefüllt werden; der Fall liefert die konkrete Fehlerursache nicht. Im vorliegenden Lesetest wird kein Bericht im hypothetischen Repository geschrieben.

**Was behauptet werden darf.** Der Auditversuch scheiterte, ein Fehlerrecord wurde geschrieben und die Übernahme verweigert. Es liegt kein übernommenes Ergebnis vor. Nicht behaupten: Erfolg der wissenschaftlichen Aussage wegen erfüllter Metrikschwelle.

**Beleg.** Schritt 6: „When the adoption is refused and you cannot clear it, do not write the run's numbers into a report as the result“; „A refusal is a finding to report, not an obstacle to route around: cite the run as `run <run_id> (not reported: <what refused the adoption, what you found>)`, say that the question stays open, and end there.“

**Lücken.** Lane `low` nennt hierfür die Textform, keinen eigenen Befehl zur Erstellung dieses Blocks. Ein möglicher Befehl in Lane `high` ist wegen der ausdrücklichen Lesebegrenzung kein dokumentierter Low-Lane-Schritt. Auch die Syntax und Auswertung des fehlgeschlagenen Auditrecords sind hier nicht beschrieben.

## 5. Stärkere Conclusion nach tragender Entscheidungsreview

**Nächste Handlung.** Noch nicht liefern. Die veränderte Conclusion erneut reviewen lassen:

```sh
labkit-audit experiments/01-study --review
```

Nur wenn die Review den neuen Anspruch innerhalb des akzeptierten Limits trägt, kann der fertige Stand passieren. Bei Ablehnung den Anspruch oder die Entscheidung sachlich überarbeiten, wie in Fall 3; keine unveränderten Wiederholungen zum Erlangen eines günstigen Urteils.

Anschließend den endgültigen Stand mit `report-check experiments/01-study` prüfen; Stop- und Commit-Hooks halten ihn ebenfalls. Falls REPORT.md eigene Schlussfolgerungen enthält, müssen sie den tatsächlich getragenen Anspruch wiedergeben. Der bereits vorhandene erzeugte Ergebnisblock bleibt exakt; bei unveränderten Run- und Entscheidungsdaten gibt es im Text keine Pflicht, ihn allein wegen einer Conclusion-Änderung neu zu generieren. Eine reine Conclusion-Änderung verlangt hier auch keinen neuen Messlauf oder neuen gewöhnlichen Analyseaudit.

**Bericht jetzt.** Der bisherige Ergebnisblock trägt keine zusätzliche Garantie für die nachträglich verstärkte Conclusion. Die frühere Review ist kein Beleg für den neuen Anspruch.

**Beleg.** Schritt 5 nennt die Conclusion „the claim the review judges“ und ausdrücklich: „a review made before it goes stale when it is written“. Die Review beurteilt „whether the claim stands within that limit“; `report-check` blockiert bis zur tragenden Review.

**Lücke.** Der Satz über Veralten nennt wörtlich eine Review vor dem Schreiben der Conclusion. Er formuliert nicht ausdrücklich „jede spätere Änderung“. Dass eine inhaltlich verstärkte Conclusion die erneute Review erfordert, ist die naheliegende Auslegung daraus, dass die Review gerade diesen Anspruch prüft. Ob und wie das Gate diese konkrete Änderung technisch als veraltet erkennt, lässt sich aus dem Text nicht beweisen. Der Text nennt keine Pflicht, wegen einer bloßen Conclusion-Änderung `--render` auszuführen; er nennt das bei geänderten Entscheidungen.

## 6. Predictions am falschen Pfad trotz finalize

**Nächste Handlung.** Die externe Anforderung ist noch nicht erfüllt: Die gegebene Ausgabe existiert nur unter `experiments/01-study/output/pred_results/predictions.csv`, verlangt ist `pred_results/predictions.csv` an der Repositorywurzel. Den vorhandenen Output und die externe Vorgabe prüfen und die zugehörigen Vorhersagen am verlangten Pfad bereitstellen. Inhalt, Zuordnung zu den erwarteten Beispielen und Dateiformat anhand des externen Auftrags verifizieren. Falls dafür die Erzeugung geändert werden muss, den korrigierten Code mit `code-check`, Commit, neuem Lauf, `finalize`, Analyseaudit und Übernahme nach dem dokumentierten Ablauf prüfen.

**Befehle.** Die Einstiegshinweise enthalten weder einen Export-/Kopierbefehl noch einen Prüfaufruf, der die externe Pfadvorgabe garantiert. Ich nenne daher keinen solchen Befehl als dokumentierte Pflicht. Ein manuelles Bereitstellen bzw. eine reine Kopie könnte genügen, falls Inhalt und externer Auftrag das zulassen; das ist hier eine Umsetzungsentscheidung, keine zugesicherte Labkit-Funktion. Ob diese Kopie erneut Messung oder Audit erfordert, wird nicht entschieden.

**Bericht jetzt.** Berichtbar sind der tatsächlich vorhandene Outputpfad und das bestandene `finalize`. Die vollständige Erledigung der externen Aufgabe darf noch nicht behauptet werden.

**Beleg.** Schritt 6 beschreibt `finalize` in diesem Zusammenhang als Prüfung der „provenance“ und verlangt `output/` und `runs/` in Git. Die Übernahmebedingungen sind vollständiger Lauf, entschiedener Analyseaudit und `scripts/02_analyze.py --check`. Keine dieser Textstellen nennt den externen Wurzelpfad. Schritt 3 verlangt das Füllen des Skeletons und `code-check`; deren genaue Prüfreichweite steht hier ebenfalls nicht.

**Lücke und wissenschaftliches Urteil.** Aus einem bestandenen Gate folgt ohne dokumentierten Prüfvertrag keine Erfüllung jeder externen Dateipfadpflicht. Das ist mein Schluss aus der konkreten Aufgabenabweichung, keine zusätzliche Gatefunktion. Die Anleitung lässt offen, welcher bestehende Check die externe Vorgabe überhaupt kennt, wie Auslieferungsartefakte registriert werden und ob ein bestimmter Check den Pfad kontrolliert. Dies muss außerhalb dieses eingeschränkten Lesetests anhand des externen Auftrags bzw. der Bereichsdokumentation geklärt werden.
