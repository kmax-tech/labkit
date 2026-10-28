Probe-Antworten zu instructions.md (gelesen vollständig; cases.txt gelesen). Keine anderen Dateien geöffnet, keine Befehle ausgeführt, keine Datei geschrieben. Zeilenangaben beziehen sich auf instructions.md. Begriffe: kind = Art (fit/apply/compute), repeat_cost = Wiederholkosten (low/high), type = wissenschaftlicher Typ (confirmatory/exploratory), Zulassungsbedingung = admissibility, Nullbedingung = null condition, BLOCKER = schwerer Audit-Befund, Handover = geordnete Übergabe ohne Ergebnis.

**1. RandomForest in fünf Sekunden, Vorhersage unbeschrifteter Testzeilen**
- Setting: kind = fit (Z. 53-57: "Choose fit, even if the deliverable is predictions without gold labels"; "A RandomForest fitted in seconds is fit, usually at low"). repeat_cost = low (Z. 57). type = confirmatory (Z. 51: "test a question and criterion specified before the relevant results"), übernommen aus dem Fallsachverhalt.
- Kriterium und Analyse-Audit sind geschuldet: Z. 88-90 ("Fit/apply: also criterion, admissibility condition and null condition"), Z. 59 ("Neither low nor exploratory removes a fit/apply's criterion or audits"), Z. 151-152 (analysis audit vor jedem Bericht, bei beiden Kosten). Preflight-Audit und Freeze nicht geschuldet (Z. 136).
- Nächste Schritte: `labkit-init exp <name> --repeat-cost low --kind fit` (Z. 75-76); `protocol-fill <PROTOCOL> --list` und `protocol-check <PROTOCOL> --contract` (Z. 83-84); Registrierung mit `protocol-fill <PROTOCOL> "type=confirmatory" ...` (Z. 97-98); committen vor der ersten vollen Messung (Z. 101-102). Schritt 2: `.venv/bin/python <area>/scripts/01_measure.py --show 2`, falls es ein Estimator-Skelett ist (Z. 107-109), `code-check <area>` (Z. 110), Tests an Hand-Fällen (Z. 111). Commit, dann `.venv/bin/python <area>/scripts/01_measure.py` im Vordergrund (Z. 138-140). Danach `finalize <area>` (Z. 151), `labkit-audit <area> --mode analysis` (Z. 152), `--findings` und `--decide` (Z. 153-157).
- Erlaubte Aussage jetzt: keine. Gemessene Werte bleiben Beschreibung, keine Erfolgsaussage (Z. 174-175).
- Offen: Der Fall nennt "unlabelled test rows", die Bewertung muss aber auf gelabelten Held-out-Zeilen laufen (Z. 55-56); woher sie stammen, sagt die Anleitung nicht. type = confirmatory ist meine Ableitung aus "specified before results", nicht aus der Anleitung geprüft.

**2. Lokale Dokumente zählen, Lauf sechs Stunden, nicht leichtfertig wiederholbar**
- kind = compute (Z. 49: "calculate a quantity without judging predictions"; Z. 58-59). repeat_cost = high (Z. 50: "a repeat needs protection by a preflight audit and freeze"). Die sechs Stunden sind die Messkosten, das passt laut Z. 50.
- --show: nicht geschuldet (Z. 108-109, "compute has no --show"). --probe: nicht geschuldet (Z. 124-125); stattdessen die Berechnung testen (Z. 125-126).
- Geschuldet: `labkit-audit <area> --mode preflight` nach `preflight <area>` (Z. 130-131), Befunde entscheiden (Z. 131-132), Aufzeichnung in `preflight_audit` der Protokollkopf (Z. 132-133), `labkit-init exp <name> --report` ausfüllen und `frozen = true` setzen (Z. 133-134). Ein Code-Fix nach dem Audit verlangt einen neuen Audit (Z. 135).
- Lauf: committen (Z. 138), dann `.venv/bin/runlog start <area> -- .venv/bin/python <area>/scripts/01_measure.py` (Z. 141-143), überwachen mit `.venv/bin/runlog <area> --wait` (Z. 144). Nicht im Vordergrund, weil Runlog das Ablösen verlangt (Z. 289-290). Danach finalize und analysis-Audit (Z. 151-152).
- Erlaubte Aussage: keine vor dem Analyse-Audit.
- Offen: type ist nicht genannt (confirmatory oder exploratory). Ohne Vorab-Festlegung der Zählfrage kann ich das nicht entscheiden.

**3. Unverändertes LLM gegen Gold-Labels, eine Messung dauert viele Stunden**
- kind = apply (Z. 58: "An unchanged LLM judged against labels is apply"). repeat_cost = high (Z. 50). type aus der Registrierung, nicht genannt.
- Reihenfolge vor dem Lauf: `labkit-init exp <name> --repeat-cost high --kind apply --model <alias>` (Z. 75-77; Alias in models.toml, Z. 295). `protocol-check <PROTOCOL> --contract` (Z. 83-84). Vor dem Lauf ausfüllen: Frage, Daten/Umfang, Ausschlüsse, Einheit (Z. 87); Kriterium, Zulassungsbedingung, Nullbedingung im selben Lauf (Z. 88-90); Data profile (Z. 91); Prompt-Konstanten per `protocol-fill <PROTOCOL> --prompts` (Z. 91-92); Versprechen C/A/B mit Satz (Z. 94-98). Registrierung committen vor der ersten vollen Messung (Z. 101-102).
- Schritt 2: `.venv/bin/python <area>/scripts/01_measure.py --show 2` (Z. 107-109), `code-check <area>` (Z. 110), Hand-Fälle testen (Z. 111). Oberflächenmerkmale prüfen und im Data profile festhalten (Z. 114-115). `00_prepare.py --audit` ist nur Hilfe (Z. 116-117).
- Zusätzlich bei high: `--probe` (Z. 120-121), repräsentative Rohbeispiele ins Protokoll, Auswertung an synthetischen Extremen testen vor dem Freeze (Z. 122-123). Dann `preflight <area>`, Preflight-Audit, Befunde, `preflight_audit`, `--report`, `frozen = true` (Z. 130-134). Commit, `runlog start`, `runlog --wait` (Z. 138-144). Den Audit im Hintergrund-Task warten, nicht per Prozessnamen-Polling (Z. 145-147).
- Bei wiederholbar beliebig (low): kein Freeze, kein Preflight-Audit (Z. 136), kein separater Probelauf (Z. 125-126), Lauf im Vordergrund (Z. 139-140). Weiterhin geschuldet: Kriterium, Zulassung, Nullbedingung (Z. 59, 88-90), Data profile (Z. 68-69 "all other steps apply to both costs"), --show, code-check, Hand-Fall-Tests, Commit, analysis-Audit (Z. 151-152).
- Helfer ausführen reicht nicht: "its counts are hints, not the judgement" (Z. 116-117); die Beurteilung muss im Data profile stehen (Z. 114-115).
- Unsicher: ob ein Probelauf bei low wirklich entfällt, obwohl der Prompt neu ist, ist nur über Z. 125-126 begründet.

**4. Low-fit committed, finalize ok, analysis-Audit ohne Befunde, Conclusion leer**
- Reihenfolge: (a) `protocol-fill <PROTOCOL> "Conclusion=<...>"`, höchstens zwei schlichte Sätze, vor der Übernahme (Z. 179-180). (b) Übrige Felder nach dem Lauf füllen; Raw output nur bei einem Modell (Z. 181-183). (c) `protocol-fill <PROTOCOL> --from-run <run_id>` (Z. 201-202). Der Befehl setzt [result] run, Recorded results und Laufeintrag, prüft mit report-check und setzt bei Ablehnung zurück (Z. 202-204). (d) `protocol-fill <PROTOCOL> --into REPORT.md` (Z. 209-210). (e) Report-Erklärung von Hand, konsistent mit der Conclusion (Z. 211-212). Gezählte Größen nach metrics.json aus den Rohzeilen (Z. 213-215). (f) Gemeinsam stagen: Report, Protokoll, Ausgaben, Läufe, Audit-Nachweise inkl. audits/attempts.jsonl (Z. 225-228), committen (Z. 228-229).
- Generiert: [result]-Block, Laufeintrag, Recorded results mit abgeleitetem Verdikt (Z. 201-207), Ergebnisblock und Grenzen (Z. 209-210).
- Von Hand: Conclusion (Z. 179-180), Report-Erklärung (Z. 211-212), die Werte in metrics.json (Z. 213-215).
- Erlaubt: nur die Conclusion-Grenze (Z. 174-175, 180).
- Offen: Ob ein Audit ohne Befunde als "decided covering" gilt, ist nicht ausdrücklich gesagt (Z. 203). Welche Nachfelder nötig sind, steht nur im Contract. Die run_id ist nicht genannt; cases.txt nennt 2026-10-26T08-18-33_7392 als bekannten Lauf, ob das dieser ist, weiß ich nicht.

**5. Low-fit, Audit nennt zwei verbotene Leck-Features, eine Diagnose verlangt; nur eines entfernt, nicht neu gemessen, "fixed" gewünscht**
- Zuerst: beide Features im Code entfernen, nicht die Ausschlussregel ändern (Z. 241-242). Die verlangte Diagnose laufen lassen und bewerten (Z. 158-160: "fixed" heißt, die ganze Störung ist behoben und die Diagnose gelaufen und bewertet). Dann testen (Z. 110-112), committen (Z. 138), neu messen (Z. 139-140; 161-162), finalize (Z. 151), neuer analysis-Audit, der frühere BLOCKER wird übernommen (Z. 161-163). Erst dann `labkit-audit <area> --decide <N> fixed "<REASON>" --record <record>` (Z. 156).
- Die Ausschlussregel zu ändern repariert nichts: "Remove it from the code, not from the exclusion rule" (Z. 241-242); "Editing code does not repair an old run" (Z. 163-164).
- Ergebnisdatei: wenn das Ergebnis nicht mehr gilt, aus einer Messung nach dem Fix neu schreiben oder die Datei entfernen; der Bericht sagt, was und warum (Z. 38-43). Alte Läufe und Audit-Antworten bleiben (Z. 276-279).
- Erlaubt jetzt: keine Adoption; gemessene Werte bleiben Beschreibung (Z. 174-175).
- Offen: Ob ein ungefixter BLOCKER die Übernahme sperrt, ist nicht ausdrücklich gesagt; Z. 38-41 legt es nahe.

**6. Gültiger low-fit verfehlt C1; breiteres Nullband und niedrigere Marge im selben Protokoll, oder neue Area, die die Frage als beantwortet erklärt**
- Sofort richtig: den Verfehlen berichten, "that is the result: report the miss first" (Z. 243-244). Conclusion schreiben, `--from-run`, Report; ein Kriterium mit gültiger Zulassung und Verfehlen ist ein berichtbarer Verfehlen (Z. 206-207).
- Verboten: Marge senken ist keine Reparatur (Z. 244-245). Konstanten nach Ergebnissen ändern beantwortet die registrierte Frage nicht (Z. 102-103). Eine neue Area macht keinen Verfehlen zum Bestehen (Z. 255-257).
- Nicht verboten: eine spätere Untersuchung, wenn sie offenlegt, was schon beobachtet wurde (Z. 256-258), und wenn es eine unabhängige Frage ist, ist sie keine Ersetzung (Z. 257-258). Exploratory passt, wenn sie auf Beobachtetem aufbaut (Z. 51-52). Typ-Wahl ist Urteil.
- Offen: Die Anleitung nennt keine Form für "deliberately changed follow-up" im Register.

**7. Metriken c1_pass=True und a3_pass=True; Befund zu A3 akzeptiert mit "A3 not assessable"**
- Berichtbares Verdikt: keines als Erfolg. "An unassessable or unmet admissibility condition leaves every criterion not assessable" (Z. 172-173). Also ist C1 ebenfalls nicht beurteilbar, obwohl c1_pass=True. Der Bericht zeigt deskriptive Werte und das Versprechen als nicht beurteilbar, nicht als Bestehen (Z. 246-248).
- metrics.json nicht editieren: Das abgeleitete Verdikt kommt aus Recorded results, Rohmetriken bleiben unverändert (Z. 205-207); nichts von Hand umschreiben (Z. 210-211, 277-279).
- Review: nicht geschuldet. Nur ein mit "stands" akzeptierter BLOCKER braucht Review (Z. 185-186); "not assessable" löst selbst keine Entscheidungs-Review aus (Z. 196-197).
- Offen: Der genaue Ausgabewert des Verdikts ist nicht festgelegt; "every criterion" lese ich als alle Kriterien der Area.

**8. Mit "stands" bestätigter BLOCKER, übernommen, in REPORT.md gerendert; nur die Conclusion verstärkt**
- Veraltet: die Review, denn "Changing the Conclusion ... invalidates its review; re-review if the current decision requires one" (Z. 193-194). Die Report-Erklärung, die von Hand zur Conclusion passen muss (Z. 211-212). Der Ergebnisblock wird nicht erneuert, denn Render ist nur nach geänderten Audit-Entscheidungen geschuldet (Z. 210-211).
- Wiederholen: die Review (`labkit-audit <area> --review --record <record>`, Z. 185-186). Eine neue Messung nicht: "Changing only the Conclusion does not require another measurement" (Z. 195).
- --again: "never supplies missing approval or overrules an earlier rejection" (Z. 196-197). Die Review ist durch die Änderung ungültig, also liefert ein unveränderter --again keine Zustimmung. Das ist eine Ableitung aus Z. 193-197; die Stelle zu --again selbst nennt keine Vorgabe für diesen Fall.
- Offen: ob eine nachträgliche Conclusion-Änderung eine erneute Adoption verlangt; Z. 179-180 sagt nur "before adoption". Ob die Conclusion im REPORT.md-Block vorkommt, ist nicht gesagt.

**9. Analysis-Audit gescheitert, Adoption verweigert; Metriken gut, Zeit knapp, REPORT.md fällig**
- Pfad: `labkit-audit <area> --findings` zuerst (Z. 19-25). Wenn der Audit-Aufruf fehlschlug und kein abgeschlossener Audit derselben Art ihn deckt, nennt der Befehl die Übergabe (Exit 2, Z. 22-25).
- Diskussion: `protocol-fill <PROTOCOL> --discuss <run_id> --why "<was die Adoption verweigerte, was gefunden wurde>" --into REPORT.md` (Z. 217-219). Die Frage bleibt offen; Diskussion ist keine Erfolgsaussage (Z. 219-220). Dann `labkit-audit <area> --report-review REPORT.md` des fertigen Berichts (Z. 220-221). Ein benannter Mangel wird korrigiert, der veränderte Zustand neu geprüft; ein sauberer Befund am unveränderten Zustand gibt nichts frei (Z. 221-223).
- Nachweis: Report, Protokoll, Ausgaben, Läufe und Audit-Nachweise zusammen stagen, inkl. audits/attempts.jsonl und Review-Protokolle (Z. 226-228). Der gescheiterte Audit bleibt erhalten (Z. 278-279).
- Metriken nicht als Antwort darstellen (Z. 230-231).
- Handover als zulässiges Ende, wenn die Zeit nicht reicht: `protocol-fill <PROTOCOL> --handover --why "<...>" --tried "<...>" --into REPORT.md` (Z. 29-31; 235-236; 259-274). Es entfernt die [result]-Blöcke dieses Protokolls aus dem gewählten Bericht und schreibt einen Handover-Block (Z. 265-268).
- Ist "Prosa: nicht berichtet" genug? Nein. Die Anleitung kennt nur die Wege --discuss mit Review oder --handover; Zitate in anderen Texten brauchen Entfernen oder ausdrückliche Diskussion (Z. 268-270).
- Unsicher: ob ein Handover in der Zeit geht, ist Urteil, kein Befehl.

**10. Widersprüchliche Definitionen der beurteilten Größe; Frage nicht wie registriert beantwortbar**
- Pfad: den Konflikt erklären, dann neu registrieren mit `labkit-init exp <new-name> --kind …` (Z. 249-252). type = exploratory, `[replaces] protocol = "<id>"`, je Änderung ein `[[replaces.change]]` (what, from, to, why), offene BLOCKERs des Vorgängers mit `deferred` entscheiden (Z. 252-255).
- Frühere Befunde und Ergebnisse bleiben (Z. 63-64; 276-279). Der Vorgänger-Verdikt wird zuerst gerendert, ein neuer Ansatz macht einen Verfehlen nicht zum Bestehen (Z. 255-257).
- Nicht jede spätere unabhängige Frage muss ersetzen: "an independent question is not a replacement just because it comes later" (Z. 257-258). Eine bewusst geänderte Folgefrage muss offenlegen, was schon beobachtet wurde (Z. 256-258).
- Offen: Das Format von [[replaces.change]] ist nur mit den Feldnamen angegeben; die TOML-Syntax fehlt.

**11. finalize ok, externe Aufgabe verlangt pred_results/predictions.csv im Repo-Wurzel, Datei liegt im Output-Verzeichnis der Area**
- Die Aufgabe ist nicht erledigt. "Check the external task's required paths, formats and contents yourself: a green gate proves only its encoded checks" (Z. 225-227). Die Ausgabe ist die Lieferung; die Metriken ersetzen sie nicht (Z. 35-37). "Write each output from the measurement, at the path the task names" (Z. 36-38).
- Was das Gate garantiert: nur die kodierten Prüfungen (Messung, Audit, `02_analyze.py --check`, Z. 203-204). Der Pfad im Repo-Wurzel ist nicht Teil davon.
- Nächster Schritt: Datei am verlangten Pfad aus der Messung schreiben, Format und Inhalt gegen die Aufgabe prüfen, mit den übrigen Nachweisen stagen und committen (Z. 226-229).
- Offen: Ob eine Kopie der Output-Datei an den Wurzelpfad genügt oder die Messung den Pfad schreiben muss, sagt die Anleitung nicht; das ist eine Frage für den Nutzer. Eine Pfadänderung im Code wäre eine Codeänderung mit Neumessung (Z. 161-163), sonst nichts Ausdrückliches.

**12. --decide auf einem Befund setzen und neuen Report-Block erzeugen, zugleich "evidence is preserved"**
- Erlaubt: "Change decisions with --decide; generate result updates with protocol-fill" (Z. 276-278). Neuer Block nach geänderten Entscheidungen: `protocol-fill <PROTOCOL> --render`, dann Block neu erzeugen (Z. 210-211). Die Erlaubnis gilt nur, wenn die Änderungen die frühere Messung nicht umschreiben (Z. 278-279).
- Intakt bleiben: Laufbelege, Audit-Antworten, frühere Befunde und Historie (Z. 276-277); gescheiterte Audits (Z. 279-280). Nicht erlaubt: --no-verify, Eingriffe an Records, Löschen, Ignore-Regeln (Z. 280-281).
- "fixed" ist eine Entscheidung, kein Beweis (Z. 158-160). Eine Entscheidung, die eine Review braucht, verlangt sie danach (Z. 188-194).
- Welche Version gilt: Die Anleitung sagt, die Pflichten kommen aus `protocol-check <PROTOCOL> --contract` und nicht aus älteren Anleitungen (Z. 61-63), und historische Protokolle bleiben mit ihrem Commit und Paket-Pin (Z. 63-64). Also gilt für eine gepinnte Area der Stand des Pins, den sie bei ihrer Entstehung hatte, nicht der neueste Stand des Repos (Z. 3-4 nennt das gepinnte labkit des Repos).
- Offen: Wie man den Pin einer Area findet, steht im Text nicht; ich habe nur die Pin-Angabe aus Z. 3-4 und 61-64.

Keine Datei geschrieben, keine Befehle ausgeführt, kein Modell aufgerufen. Hinweis: Ein Docs-Tool-Aufruf (guide) lief versehentlich in diesem Lauf; er hat keine Dokumente verändert.
