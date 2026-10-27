# Gezielte unabhängige Zweitlektüre

Grundlage ausschließlich `entry-instructions-final.md`; alle Zeilenangaben beziehen sich darauf. Die Befehle beschreiben Handlungen für die fiktiven Fälle und wurden nicht ausgeführt. Die erste Antwortdatei bleibt unverändert.

## 13. Messcode eines bereits gemessenen High-Fits reparieren

**Explizite Reihenfolge:** Zuerst die Fehlerursache benennen (Z. 202–204). Vor dem Reparaturzyklus `frozen = false` setzen; registrierte Frage, Kriterien und Konstanten unverändert lassen (Z. 132–135). Den ganzen Implementierungsfehler korrigieren und angeforderte Diagnostik ausführen und beurteilen, bevor `fixed` gerechtfertigt ist (Z. 125–128, 206–209). Schritte 2–4 wiederholen: Instrument und Bereichstest bearbeiten, Ausgabe von `.venv/bin/python <area>/scripts/01_measure.py --show 2` lesen, `code-check <area>` und handgeprüfte Bereichstests ausführen; bei high auch `.venv/bin/python <area>/scripts/01_measure.py --probe`, repräsentative Rohbeispiele und synthetische Extreme vor Freeze (Z. 74–93).

Danach `preflight <area>` und `labkit-audit <area> --mode preflight`, Findings entscheiden, den passenden neuen Recordnamen unter `preflight_audit` eintragen, erforderliche Reportfelder ausfüllen und wieder `frozen = true` setzen. Der neue Audit muss den reparierten Code abdecken; der alte eingefrorene Zustand mit veraltetem Audit würde die Reparatur aufhalten (Z. 97–102, 132–135). Code, Registrierung und Eingaben committen. Erst nach diesem neuen abdeckenden Preflight-Audit und erneutem Freeze den neuen vollständigen Lauf starten: `.venv/bin/runlog start <area> -- .venv/bin/python <area>/scripts/01_measure.py`, danach `.venv/bin/runlog <area> --wait`; keinen gleichzeitigen zweiten Lauf beginnen (Z. 105–112). Anschließend `finalize <area>` und `labkit-audit <area> --mode analysis`; übernommene ungelöste BLOCKER im neuen Record entscheiden (Z. 118–131).

**Jetzt zulässige Aussage:** Die Codekorrektur repariert den alten Lauf nicht. Eine neue Messung unter unveränderter Registrierung ist erforderlich; noch kein durch die Reparatur belegter Erfolg (Z. 128–135, 206–209).

**Lücke/Urteil:** Der Text ordnet ausdrücklich Entfrieren, erneuten abdeckenden Preflight-Audit und erneuten Freeze an, gibt aber für das Setzen von `frozen` und `preflight_audit` keinen speziellen Schreibbefehl an. Der Kurzsatz „test, commit, new measurement“ in Z. 128–129 ist komprimiert; ich lese ihn wegen Z. 132–135 und der verpflichtenden Schritte 2–4 einschließlich der zusätzlichen High-Schritte, nicht als deren Auslassung. Ein neuer vollständiger Lauf ist erst nach diesen Voraussetzungen zulässig; der Probe ist ausdrücklich davor vorgesehen.

## 14. Weitergeführter BLOCKER soll dismissed oder deferred werden

**Explizit:** Ja, ein zustimmender Entscheidungsreview ist vor Freigabe erforderlich. Ein weitergeführter BLOCKER, der als `dismissed` oder `deferred` geschlossen wird, braucht ihn auch ohne frühere Ablehnung (Z. 155–158). Das Finding muss im neuen Record entschieden werden (Z. 129–131), mit dem ausgegebenen vollständigen Befehl, beispielsweise nach dessen Schema `labkit-audit <area> --decide <N> dismissed "<Begründung>" --record <new-record>` beziehungsweise `deferred`. Danach `labkit-audit <area> --review --record <new-record>`; bei mehreren Protokollen jeweils `--protocol <PROTOCOL>` beibehalten (Z. 8–10, 120–125, 152–158).

**Jetzt zulässige Aussage:** Die neue Entscheidung ist ohne zustimmenden Review noch nicht freigegeben; das Fehlen eines früher abgelehnten Reviews befreit diesen weitergeführten BLOCKER nicht.

**Lücke/Urteil:** Welche der beiden Entscheidungen sachlich gerechtfertigt ist, bleibt ohne Finding und Evidenz offen. „Carried“ verstehe ich hier unmittelbar als den in Z. 130–131 ins neue Audit übernommenen BLOCKER; für diesen Fall ist die Reviewpflicht eindeutig.

## 15. Zwei Protokolle, ausgegebener Entscheidungsbefehl mit --protocol

**Explizit:** Den Parameter nicht streichen und den ausgegebenen vollständigen Entscheidungsbefehl nicht durch ein verkürztes generisches Beispiel ersetzen. Z. 8–10 verlangen bei mehreren Protokollen die Auswahl mit `--protocol <PROTOCOL>` für Audit, Entscheidung und Review und das Beibehalten des Arguments aus ausgegebenen Befehlen; Z. 120–125 verlangen die Entscheidung mit dem ausgegebenen Befehl.

Für den Analysis-Audit entsprechend `labkit-audit <area> --mode analysis --protocol <PROTOCOL>`, für die erneute Anzeige `labkit-audit <area> --findings --protocol <PROTOCOL>`. Für die Entscheidung den vollständig ausgegebenen Befehl mit Protokoll und richtigem Record verwenden. Für den zugehörigen Entscheidungsreview `labkit-audit <area> --review --record <record> --protocol <PROTOCOL>`; der Record muss die zu prüfende Entscheidung enthalten (Z. 8–10, 118–125, 152–161). Auch ein erforderlicher Berichtsreview wählt das Protokoll: `labkit-audit <area> --report-review REPORT.md --protocol <PROTOCOL>` (Z. 8–10, 184–190).

**Jetzt zulässige Aussage:** Eine gezielte Prüfung oder Entscheidung für das betreffende Protokoll ist möglich; die generische Beispielzeile garantiert ohne Auswahl keine richtige Zuordnung.

**Lücke/Urteil:** Die generischen Beispiele lassen `--protocol` selbst weg; die ausdrückliche Regel am Anfang löst dies für mehrere Protokolle. Der konkrete Recordname muss aus dem tatsächlichen Audit stammen, nicht aus dem Beispiel geraten werden.

## 16. Drei verschiedene Findings eines Modellaudits

**Explizit:** Ein einziges allgemeines Prompt/Antwort-Paar genügt nicht als pauschaler Ersatz. Bei einem Modell verlangt Raw output ein echtes Paar **pro Finding**, gelesen aus dem aufbewahrten Output, den das Finding nennt (Z. 146–150). Für jedes der drei Findings daher dessen benannten Output lesen und das entsprechende echte Paar im Nachherfeld dokumentieren. Nicht selbst Beispiele erfinden oder nur ein vom Finding unabhängiges Beispiel auswählen. Die Conclusion weiterhin als höchstens zwei Sätze innerhalb der Grenzen verfassen (Z. 146–148).

**Jetzt zulässige Aussage:** Die Dokumentation muss die verlangten konkreten Rohbelege für alle drei Findings enthalten; Rohbelege allein beweisen weder Fehlerkorrektur noch Erfolg. `fixed` verlangt den gesamten korrigierten Fehler einschließlich ausgeführter und beurteilter Diagnostik (Z. 125–128).

**Lücke/Urteil:** Z. 149–150 verlangen Zuordnung je Finding, aber nicht ausdrücklich drei unterschiedliche Paare. Falls mehrere Findings tatsächlich denselben Output beziehungsweise dasselbe Paar benennen, könnte derselbe Beleg mehrere klar ausgewiesene Zuordnungen tragen; ein generisches Paar ohne diese Herkunft und Zuordnung erfüllt die Anweisung nicht. Falls ein Finding gar keinen aufbewahrten Output benennt oder kein zugehöriges Prompt/Antwort-Paar existiert, beschreibt der Text keinen Ersatzweg. Das wäre als Lücke offenzulegen statt durch einen erfundenen Beleg zu füllen.
