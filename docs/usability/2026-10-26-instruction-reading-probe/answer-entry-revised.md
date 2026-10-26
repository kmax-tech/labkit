# Antworten zur überarbeiteten Einstiegsanweisung

Grundlage sind ausschließlich `cases.txt` und `revised-entry-instructions.md`. Alle sechs Fälle gehören zur Lane `low` und zur Art `fit`. Die folgenden Befehle sind Handlungsvorschläge; ich habe weder Messungen noch Audits ausgeführt. `N` bezeichnet die tatsächlich ausgegebene Finding-Nummer. Wo die Anweisung keinen konkreten Messbefehl oder Statuswert nennt, erfinde ich keinen.

## 1. Saubere Messung, leere Conclusion

**Nächste Aktion:** Die Frage anhand der Messung beantworten und die Conclusion vor der Adoption schreiben, höchstens zwei einfache Sätze. Danach den vorhandenen Lauf übernehmen und den Ergebnisblock erzeugen:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<Antwort auf die Frage in höchstens zwei einfachen Sätzen>"
protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392
protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md
```

Die Adoption führt `report-check` aus und behält die Änderungen nur bei Erfolg. Ein Decision Review ist bei einem Audit ohne Findings nicht gefordert. Falls ein Modell beteiligt ist, zusätzlich das geforderte Raw output aus der tatsächlichen Ausgabedatei eintragen: ein echtes Prompt-Antwort-Paar pro Finding; der Fall nennt keine Findings und sagt nicht ausdrücklich, ob ein Modell beteiligt ist. Danach den Bericht einschließlich der extern verlangten Dateien, Formate und Inhalte prüfen, die Änderungen einschließlich Protokoll und gegebenenfalls noch nicht versionierter `output/`- und `runs/`-Dateien committen und den fertigen Bericht liefern. Die installierten Hooks müssen die Änderungen akzeptieren. Der bereits bestandene Abschluss und das saubere Audit begründen allein keinen weiteren Messlauf.

**Jetzt berichtbar:** Der Fall enthält noch keinen übernommenen Ergebnislauf. Die Zahlen daher erst nach erfolgreicher Adoption als Ergebnis in den generierten Block übernehmen. Die Conclusion muss das tatsächlich Gezeigte beschreiben; die Anweisung erlaubt keine automatische Aussage über eine allgemeine Modellfähigkeit allein aus dem Bestehen der Gates.

**Beleg:** Low 5: „Before adoption, write the Summary's **Conclusion** … answer the question in at most two plain sentences“. Low 6: „then runs `report-check` on the written protocol and puts the file back if it refuses“; „A report outside the protocol … shows the result as a generated block“; „Commit `output/` and `runs/` with the protocol“. Einstieg: „check their paths, file formats and contents before delivery“.

**Offen:** Die konkrete inhaltliche Conclusion und externe Lieferanforderungen sind nicht gegeben. Ein zusätzlicher eigenständiger `report-check`-Aufruf nach der Blockerzeugung ist hier nicht ausdrücklich als eigener Schritt vorgeschrieben; die Adoption und die Hooks leisten die genannten Prüfungen.

## 2. Zwei undichte Features, erst eines entfernt

**Nächste Aktion:** Den Fehler vollständig beheben, also auch das zweite im Finding benannte undichte Feature entfernen. Nach jeder Codeänderung `code-check` ausführen; auch die bereits erfolgte Änderung schuldet diesen Check, falls er noch nicht lief. Die angeforderte Diagnose ausführen und fachlich auswerten. Danach beziehungsweise als Teil des korrigierten Laufs die vorgeschriebene Wiederholung durchführen:

```sh
code-check experiments/01-study
# Korrigierten Code committen; dokumentierten Messbefehl des Projekts im Vordergrund ausführen.
finalize experiments/01-study
labkit-audit experiments/01-study --mode analysis
labkit-audit experiments/01-study --findings
```

Die Diagnose muss zu den korrigierten Bedingungen passen; ihre genaue Position relativ zur Messung hängt vom nicht gelieferten Diagnoseauftrag ab. Nach vollständiger Behebung und durchgeführter, beurteilter Diagnose kann die alte Feststellung mit dem dokumentierten Entscheidungsmuster als `fixed` dokumentiert werden:

```sh
labkit-audit experiments/01-study --decide N fixed "<vollständige Korrektur und bewertete Diagnose mit Nachweis>" --record 2026-10-26T08-28-analysis.toml
```

Der neue Analyse-Audit muss seinerseits entschieden werden. Anschließend folgen Conclusion, Adoption des neuen Laufs und Bericht wie in Fall 1. Den alten Audit und fehlgeschlagene Versuche aufbewahren.

**Jetzt berichtbar:** Es besteht weiterhin ein offener BLOCKER; eine Teilkorrektur ohne neue Messung behebt das alte Ergebnis nicht. Kein korrigiertes, geprüftes Ergebnis und keine nachgewiesene Fehlerbehebung behaupten. Als Arbeitsstand darf die Teilkorrektur benannt werden; den alten Lauf nicht als bereits repariertes Ergebnis darstellen.

**Beleg:** Low 3: „run `code-check <area>` after every code change“. Low 5: „A finding is `fixed` only after the named fault has been fully corrected and the requested diagnostic has been run and assessed“; „a status and reason record your decision, not proof of a fix“; „If measurement code changes, repeat steps 3–5: commit the corrected code, measure again, finalize and audit the new code and run“; „The old run is not repaired by editing its script“.

**Offen:** Diagnosebefehl, Messbefehl, Feature-Namen und Finding-Nummer fehlen. Die Anweisung bestimmt nicht den exakten Zeitpunkt des Statuswechsels innerhalb des Wiederholungsvorgangs, aber eindeutig dessen materielle Voraussetzungen. Meine fachliche Beurteilung der Diagnose kann die Anweisung nicht ersetzen.

## 3. Akzeptierter BLOCKER mit `stands`; unabhängig davon abgelehntes Review

**Nächste Aktion beim akzeptierten BLOCKER:** Die Conclusion innerhalb der akzeptierten Einschränkung schreiben, danach die Entscheidung überprüfen lassen, erst nach einem bestätigenden Review adoptieren und berichten:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<Antwort innerhalb der akzeptierten Einschränkung>"
labkit-audit experiments/01-study --review
protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392
protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md
```

Das Review muss die Behauptung innerhalb der Einschränkung bestätigen. Die Limit-Zeile und die Kennzeichnung der Einschränkungen werden generiert und müssen erhalten bleiben. Danach externe Lieferanforderungen prüfen und Änderungen mit erfolgreichen Hooks committen.

**Jetzt berichtbar:** `stands` ist eine begründungsbedürftige Entscheidung, noch keine bestätigte Freigabe der Behauptung. Vor dem bestätigenden Review und der Adoption noch keinen freigegebenen Ergebnisbericht liefern. Nach deren Erfolg darf die Zahl mit der dokumentierten Einschränkung berichtet werden; `stands` bedeutet, dass die Urteile innerhalb dieser Einschränkung bestehen bleiben.

**Unabhängiger Ablehnungsfall:** Nicht einfach erneut auf ein günstigeres Review hoffen. Die Ablehnung bearbeiten und neu entscheiden: Conclusion einschränken, Effekt ändern oder Fehler beheben. Eine geänderte Conclusion beziehungsweise Entscheidung anschließend erneut reviewen lassen. Bei einer Codekorrektur zusätzlich die Mess- und Auditfolge aus Fall 2 wiederholen. Auch ein Wechsel auf `fixed`, `dismissed` oder `deferred` nach dem nicht bestätigenden Review verlangt ein bestätigendes Review der neuen Entscheidung. Bei geänderter Entscheidung bereits erzeugte Ergebnisdarstellungen mit `--render` erneuern und den externen Block neu erzeugen, soweit vorhanden.

**Beleg:** Low 5: „A BLOCKER accepted with `stands` then owes a decision review“; „a rejection means deciding again (limit the Conclusion, change the effect, or fix the fault), not drawing again“; „A finding closed as `fixed`, `dismissed` or `deferred` after a review did not uphold it also needs an upholding review of that new decision“. Low 6: „a changed decision is written again with `--render`“.

**Offen:** Ob `stands` wissenschaftlich gerechtfertigt ist, folgt aus C1 und dem Fehler, die hier nicht vorliegen. Low 5 sagt ausdrücklich, dass der Effekt aus dem Inhalt von C1 folgt, nicht aus dem Schweregrad. Ein konkreter CLI-Statuswert für eine neue Akzeptanzentscheidung wird nicht genannt; dafür ist die ausgegebene Entscheidungsanweisung zu verwenden.

## 4. Fehlgeschlagener Analyse-Audit, Adoption verweigert, Zeitdruck

**Nächste Aktion:** Den verweigerten Ergebnisstatus offen berichten und den dokumentierten Diskussionsblock erzeugen:

```sh
protocol-fill experiments/01-study/PROTOCOL-study.md --discuss 2026-10-26T08-18-33_7392 --why "Der Analyse-Audit ist fehlgeschlagen; die Adoption wurde verweigert. Es liegt keine erfolgreiche Analyseabdeckung vor." --into REPORT.md
```

Den tatsächlichen Verweigerungsgrund bei Bedarf präziser ergänzen, ohne aus dem Fall unbekannte Ursachen zu erfinden. Dazu ausdrücklich schreiben: „Die Forschungsfrage bleibt offen. Dieser Bericht dokumentiert den fehlgeschlagenen Audit und die verweigerte Adoption; er erhebt keinen Erfolgsanspruch.“ Den fehlgeschlagenen Datensatz aufbewahren und den Bericht mit den nötigen Dateien und bestandenen Hooks liefern. Falls die Ablehnung noch rechtzeitig ordnungsgemäß behoben werden kann, ist das möglich; der Fall liefert dafür aber keinen erfolgreichen Audit.

**Jetzt berichtbar:** Eine Diskussion des Versuchs und der Ablehnung, kein angenommenes Ergebnis und kein Erfolg aufgrund des Schwellenwerts. Die Laufzahlen nicht von Hand als Ergebnis in `REPORT.md` schreiben. Was der Diskussionsblock genau enthält, lässt sich ohne Ausführung nicht behaupten; die Anweisung liefert den sicheren Erzeugungsweg.

**Beleg:** Low 5: „an unsuccessful audit supplies no analysis coverage“. Low 6: „When the adoption is refused and you cannot clear it, do not write the run's numbers into a report as the result“; „A refusal is a finding to report, not an obstacle to route around“; anschließend der `--discuss … --why … --into REPORT.md`-Befehl und „Say that the question stays open; a discussion is not a success claim“.

**Offen:** Der konkrete Auditfehler ist unbekannt. Das Bestehen einer metrischen Schwelle beantwortet nicht, ob die notwendige Analyseprüfung gelungen ist; eine Ausnahme wegen Zeitdruck ist nicht dokumentiert.

## 5. Conclusion nach bestätigtem Review verstärkt

**Nächste Aktion:** In diesem Zustand noch nicht liefern. Die geänderte Conclusion macht das bisherige Review ungültig. Den stärkeren Anspruch erneut überprüfen lassen:

```sh
labkit-audit experiments/01-study --review
```

Nur bei einem bestätigenden Review der geänderten Conclusion weiterliefern. Bei Ablehnung die Behauptung beziehungsweise Entscheidung sachlich überarbeiten, wie in Fall 3. Falls `REPORT.md` die alte Conclusion als eigenen Text enthält, diesen konsistent aktualisieren und die externen Anforderungen prüfen. Die Änderungen müssen die Hooks bestehen.

**Jetzt berichtbar:** Die vorherige Bestätigung trägt die neue stärkere Aussage nicht. Das bisherige Ergebnis darf nicht als Freigabe dieser Verstärkung ausgegeben werden. Ein bestätigendes Review ist die dokumentierte Voraussetzung, aber keine allgemeine Garantie semantischer Wahrheit.

**Was wiederholt werden muss:** Das Decision Review. Ein neuer Messlauf ist allein wegen der Conclusion-Änderung ausdrücklich nicht nötig. Auch ein neuer Analyse-Audit ist dafür nicht ausdrücklich gefordert. Ein `--render` ist für geänderte Entscheidungen dokumentiert; hier sind Entscheidungen und Messdaten unverändert. Der generierte Block enthält laut Anweisung Recorded results und Limit-Zeilen und muss daher aus diesem Grund nicht neu erzeugt werden. Ein erneuter separater Adoptionsbefehl wird für diesen Fall nicht ausdrücklich verlangt; die Hooks prüfen den erklärten Ergebnisstatus weiter.

**Beleg:** Low 5: „Changing the Conclusion or decision makes its review stale; review the changed claim or decision before reporting“; „A Conclusion-only change does not by itself require a new measurement“. Low 6 beschreibt den Inhalt des generierten Blocks und verlangt `--render` nach geänderter Entscheidung.

**Offen:** Ohne Inhalt der Verstärkung ist nicht zu beurteilen, ob sie innerhalb der akzeptierten Einschränkung bleibt. Das ist gerade Gegenstand des neuen Reviews.

## 6. Vorhersagen nur unter dem Ausgabeordner des Experiments

**Nächste Aktion:** Der externe Auftrag ist noch nicht erfüllt. Die geforderte Datei muss am Repository-Wurzelpfad `pred_results/predictions.csv` bereitgestellt und dort hinsichtlich Format und Inhalt geprüft werden. Die Datei unter `experiments/01-study/output/pred_results/predictions.csv` zunächst darauf prüfen, ob sie tatsächlich die geforderten Vorhersagen enthält, und dann passend am geforderten Ziel bereitstellen. Eine bloße Pfadkorrektur durch Kopieren ist eine mögliche eigene Umsetzung, kein vorgeschriebener labkit-Befehl. Die Anforderungen können etwa Spalten, Reihenfolge oder Vollständigkeit festlegen; solche konkreten Vorgaben sind nicht geliefert und werden nicht erfunden.

Falls dafür Messcode geändert wird, gilt erneut `code-check`, Commit, neue Messung, `finalize`, Analyse-Audit sowie Adoption und Bericht des neuen Laufs. Falls nur das bereits korrekte Artefakt an den Lieferpfad kopiert wird, nennt die Anweisung dafür keinen obligatorischen neuen Messlauf. Bei der Lieferung müssen weiterhin die sonstigen Reportingpflichten erfüllt sein; das bestandene `finalize` ersetzt sie ebenfalls nicht.

**Jetzt berichtbar:** `finalize` hat seine dokumentierten Prüfungen bestanden. Nicht behaupten, damit sei die externe Pfadanforderung oder der gesamte Auftrag erfüllt. Nach tatsächlicher Bereitstellung und Prüfung kann die Erfüllung der konkreten Lieferanforderung behauptet werden.

**Dokumentierte Prüfungen:** Der Einstieg verlangt ausdrücklich die Prüfung von Pfaden, Formaten und Inhalten der extern verlangten Lieferdateien. Er nennt dafür keinen dedizierten CLI-Befehl und garantiert nicht, dass `finalize`, `report-check`, `code-check` oder die Hooks den Wurzelpfad kontrollieren. Low 6 beschreibt `finalize` hinsichtlich Provenienz und der Versionierung von `output/` und `runs/`; daraus folgt keine Kontrolle dieses externen Zielpfads. Ein eigener Existenz-, Format- und Inhaltscheck wäre die praktische Umsetzung der Pflicht, ohne dadurch eine zusätzliche Gate-Garantie zu behaupten.

**Beleg:** Einstieg: „The external task still defines the required deliverables: check their paths, file formats and contents before delivery“ und „A clean labkit gate establishes its documented checks; it does not establish an external requirement that was never encoded in those checks“.

**Offen:** Konkretes CSV-Schema, verlangte Vorhersagen, Prüfverfahren und eine eventuelle maschinelle Kodierung der externen Anforderung fehlen. Aus dem Gate-Erfolg lässt sich diese Kodierung nicht ableiten.

## Grenzen der Lesart

Für diese Fälle erkenne ich keinen direkten Widerspruch innerhalb der einschlägigen Low-Lane-Regeln. Die fehlenden konkreten Mess-, Diagnose- und Lieferprüfbefehle sind Lücken, keine Erlaubnis, Befehle oder Garantien zu erfinden. Die Folge `code-check → Commit → Messung → finalize → Analyse-Audit` und die Reviewbedingungen sind dokumentierte Pflichten; die inhaltliche Beurteilung von Leakage, C1, Diagnose und zulässiger Conclusion bleibt wissenschaftliches Urteil.
