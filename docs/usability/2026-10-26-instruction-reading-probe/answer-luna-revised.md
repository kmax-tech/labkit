# Antworten zur Probe

## 1. Bericht nach sauberem Lauf

**Nächste Schritte:** Erst die Summary-Conclusion mit höchstens zwei schlichten Sätzen und innerhalb der Aussagegrenzen eintragen: `protocol-fill experiments/01-study/PROTOCOL-study.md "Conclusion=<...>"`. Danach den Lauf übernehmen: `protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392`. Das schreibt die protokollierten Ergebnisse aus `metrics.json` und führt `report-check` aus. Bei Erfolg den externen Bericht erzeugen: `protocol-fill experiments/01-study/PROTOCOL-study.md --into REPORT.md`. Commit von `output/`, `runs/`, Protokoll und Bericht; Hooks prüfen den Ergebnisstand.

**Jetzt in `REPORT.md behauptbar:** Nach erfolgreicher Übernahme den generierten Ergebnisblock einschließlich aller Limit-Zeilen unverändert verwenden. Im gegebenen Fall gibt es keine Audit-Findings. Vor erfolgreicher Übernahme ist noch kein Resultat in REPORT.md zu behaupten.

**Belege:** Lane low, Schritte 5–6: Conclusion vor Adoption; `--from-run` übernimmt und prüft; externer Bericht mit `--into`; `finalize` verlangt Provenienz und Git-Aufnahme. Analysis audit muss vor Berichterstattung vorliegen.

**Offen:** Der Fall sagt nicht, ob die neue Conclusion tatsächlich durch `report-check` akzeptiert wird oder welche konkreten Metriken/Resultatsätze aus dem Lauf hervorgehen.

## 2. Teilweise behobener Leckage-Befund

**Nächste Aktion:** Nicht als fixed entscheiden. Die genannte Fault ist noch nicht vollständig behoben und der verlangte diagnostische Lauf fehlt. Beide Features entfernen, dann nach Codeänderung Schritt 3–5 wiederholen: `code-check experiments/01-study`, commit des korrigierten Codes, neue Messung, `finalize experiments/01-study`, neue Analyseprüfung mit `labkit-audit experiments/01-study --mode analysis`. Die alte Messung wird durch Skriptänderung nicht repariert; frühere Audit- und Fehlversuchsrecords bleiben erhalten.

**Wann fixed:** Erst wenn beide benannten Lecks vollständig korrigiert sind und der angeforderte Diagnostic ausgeführt und bewertet wurde; dann kann die Finding-Entscheidung mit passendem Record erfolgen. Ein Status/Grund dokumentiert die Entscheidung, ist kein Fix-Beweis.

**Bericht:** Noch kein Resultat des alten Laufs als erfolgreich behaupten; Analyseprüfung ist nicht sauber abgeschlossen und die Finding ist offen.

**Belege:** Lane low, Schritt 5: fixed-Bedingung, Codeänderung wiederholt Schritte 3–5, alter Lauf wird nicht repariert.

**Offen:** Die konkrete Form des diagnostischen Befehls ist nicht dokumentiert; nicht erfinden. Auch die inhaltliche Bewertung nach Ausführung steht aus.

## 3. BLOCKER akzeptiert mit `stands`

**Nächste Schritte:** Conclusion vor Adoption verfassen, dann wegen akzeptiertem BLOCKER mit `stands` Review ausführen: `labkit-audit experiments/01-study --review`. Review liest Befund, Begründung, Conclusion, gerendertes Resultat und Lauf. Erst wenn Review die Aussage innerhalb dieser Begrenzung aufrecht erhält, kann adoptiert werden (`protocol-fill experiments/01-study/PROTOCOL-study.md --from-run 2026-10-26T08-18-33_7392`), danach Bericht erzeugen (`protocol-fill ... --into REPORT.md`). `report-check` blockiert die Zahl bis zu einem uphold.

**Falls Review ablehnt:** Nicht einfach erneut reviewen, um ein besseres Votum zu erhalten. Entscheidung ändern: Conclusion begrenzen, Effekt ändern oder Fault beheben und ggf. neu messen/auditieren. Eine geänderte Conclusion oder Entscheidung macht Review stale; geänderte Behauptung/Entscheidung muss erneut geprüft werden.

**Bericht:** Bis zur aufrecht erhaltenden Prüfung kein Resultat berichten/adoptieren. Bei Uphold nur innerhalb der festgestellten Grenze und mit generiertem Limit-Block.

**Belege:** Lane low, Schritt 5: stands-Review, Ablehnung und Konsequenzen; Schritt 6: Adoption und Limit-Zeilen.

**Offen:** Ob in diesem Fall `stands` sachlich passt, hängt von der konkreten C1-Aussage ab: Schwelle auf diesen Items oder unbelegte Fähigkeit. Der Fall gibt diese Aussage nicht.

## 4. Audit fehlgeschlagen, Adoption verweigert

**Nächste Aktion:** Metriken nicht als Ergebnis in REPORT.md eintragen. Wenn die Adoption nicht geklärt werden kann, die Verweigerung dokumentieren, offene Frage benennen und dabei enden: `protocol-fill experiments/01-study/PROTOCOL-study.md --discuss 2026-10-26T08-18-33_7392 --why "<was die Adoption verweigerte und was du festgestellt hast>" --into REPORT.md`.

**Jetzt behauptbar:** Die Frage bleibt offen; der Lauf bzw. seine Metriken sind kein adoptiertes Erfolgsergebnis. Der Diskussionstext berichtet die Verweigerung als Finding, keine Erfolgsaussage. Dass Metriken den Schwellenwert erfüllen, hebt die verweigerte Adoption nicht auf.

**Belege:** Lane low, Schritt 6: refused adoption darf nicht umgangen werden; `--discuss`-Form und offene Frage. Schritt 5 hält fest, dass fehlgeschlagene Audits keine Analyseabdeckung liefern.

**Offen:** Der konkrete Ablehnungsgrund muss in `--why` benannt werden; er ist im Fall nicht angegeben. Kein dokumentierter Weg, trotz fehlgeschlagener Prüfung die Zahl als Ergebnis auszugeben.

## 5. Conclusion gestärkt, Rest unverändert

**Lieferbar?** Nicht ohne erneute Prüfung. Conclusion-only change erfordert laut Anleitung keine neue Messung, aber macht die vorhandene Review stale. Die geänderte Behauptung muss erneut reviewed werden: `labkit-audit experiments/01-study --review`. Nur bei Uphold den geänderten Anspruch berichten; bei Ablehnung gilt die in Fall 3 beschriebene Korrekturfolge.

**Was zu wiederholen ist:** Review der geänderten Conclusion. Keine neue Messung allein wegen Conclusion-Änderung; der Fall sagt, Code, Metriken und Entscheidungen blieben unverändert. Danach den Berichtblock bei Bedarf mit `protocol-fill ... --into REPORT.md` aktualisieren, damit die geänderte Conclusion/der aktuelle Protokollinhalt im gelieferten Artefakt steht. Der generierte Resultatblock wird weiterhin exakt gehalten.

**Belege:** Lane low, Schritt 5: Conclusion-only change benötigt keine neue Messung; Änderung macht Review stale und erneute Review vor Berichterstattung. Schritt 6: Bericht aus Protokoll generieren.

**Offen:** Ob die stärkere Conclusion tatsächlich innerhalb der Limitation uphold wird, lässt sich erst durch Review entscheiden.

## 6. Externer Pfad fehlt

**Vollständig?** Nein. `finalize` bestätigt die dokumentierten Checks, aber keine externe Anforderung, sofern sie nicht in diese Checks codiert ist. Die Pflichtdatei wird unter Repository-Root `pred_results/predictions.csv` verlangt, während der Lauf sie nur unter `experiments/01-study/output/pred_results/predictions.csv` erzeugt hat.

**Nächste Aktion:** Externe Deliverable-Anforderung erfüllen: dafür sorgen, dass Vorhersagen am verlangten Root-Pfad liegen, und vor Abgabe Pfad, Dateiformat und Inhalt prüfen. Die Anleitung sagt nicht, welche konkrete Kopier-/Exportoperation oder welcher Test dafür gilt; keine CLI-Option erfinden. Falls der Root-Pfad im Protokoll/Code umgesetzt wird, nach Codeänderung `code-check`, commit, neu messen und `finalize` sowie Analyse-Audit gemäß low lane wiederholen. Keine Behauptung „Aufgabe vollständig“ bis Root-Datei vorhanden und geprüft ist.

**Checks:** Dokumentiert ist nur, dass `finalize <area>` Herkunft prüft und `output/` samt `runs/` im Git verlangt; `report-check` prüft die beschriebenen Ergebnis-/Audit-/Analysebedingungen. Keiner dieser Checks ist als Verifikation des externen Root-Pfads ausgewiesen. Die Einstiegspassage verlangt externe Pfade, Formate und Inhalte vor Auslieferung zu prüfen.

**Belege:** Einstieg: externe Deliverables und Grenze sauberer Gates. Lane low, Schritt 6: `report-check`-Bedingungen und Git-Provenienz.

**Offen:** Das erforderliche Dateiformat und die inhaltlichen Akzeptanzregeln der externen Aufgabe, sowie die konkrete Operation, um die Datei am Root-Pfad bereitzustellen. Die Probe gibt diese nicht an.
