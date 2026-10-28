Antworten zu den Fällen 13 bis 15 (nur instructions.md gelesen, Zeilenangaben beziehen sich darauf; cases.txt habe ich wie beauftragt gelesen).

**Fall 13: Alter Bereich mit `standard = "0.21"`, neues Pin, Analyse heute nachvollziehen und neue Frage starten**

Explizit in der Anleitung:
- Welche labkit-Version gilt: die Zeile `labkit` in `requirements.lock`, sonst `requirements.txt` (Z. 65-66). Sie gilt für das ganze Repo. `labkit-check` zeigt sie neben der installierten Version (Z. 66-67).
- `standard = "…"` im Protokollkopf benennt das Protokollformat, nicht die Paketversion (Z. 67-68). Die Refusal von `protocol-check` kommt also nicht von diesem Wert allein, sondern vom Pin-Wechsel.
- Audit-Abdeckung: Ein angehobener Pin ändert jeden Bereich-Stempel, daher deckt kein früheres Audit einen Bereich danach ab (Z. 68-69).
- Alten Bereich nicht umstellen: Historische Protokolle und Läufe bleiben mit ursprünglichem Commit und Paketpin erhalten, nicht konvertieren, sondern am Commit mit eigenem `requirements.lock`-venv reproduzieren (Z. 70-73).
- Neue Frage: `labkit-init exp <name> --repeat-cost <cost> --kind <kind>` (Z. 84), dann `protocol-fill <PROTOCOL> --list` und `protocol-check <PROTOCOL> --contract` (Z. 92-93).
- Früheres Ergebnis nicht verwerfen: "A new area is not a way to discard an earlier result." (Z. 79-80).

Eigenes Urteil oder Lücke:
- Wie genau die Analyse "heute" reproduziert wird, nennt die Anleitung nicht. Sie verlangt nur den Commit mit eigenem Pin (Z. 72-73). Ein Befehl dafür ist nicht dokumentiert.
- Ob der vorhandene Analyse-Record (2026-10-26-08-28-analysis.toml) für den alten Bereich nach dem Reproduzieren noch gilt, ist nicht geregelt. Z. 68-69 spricht dagegen, nur für den neuen Pin.
- Ob der alte Bereich `01-study` ist, sagt der Fall nicht eindeutig. Ich setze das nicht voraus.
- Die Anleitung sagt nichts dazu, wie eine neue Frage in einem Repo mit altem Bereich nummeriert oder benannt wird.

**Fall 14: Protokoll A (fit) verfehlt C1, Verfehlen berichtet; neues Modell aus anderer Familie auf denselben Daten**

Explizit:
- Keine Ersetzung: `[replaces]` ist nur für eine Registrierung, die "cannot be answered as written" (Z. 272-273). Eine Frage nach einem gültigen Ergebnis, "a miss included, such as another model on the same data", ist "a protocol of its own, without `[replaces]`" (Z. 274-276).
- Welche Registrierung: ein eigenes neues Protokoll, angelegt wie in Z. 84 (`labkit-init exp <name> …`). Kind: Modell wird trainiert oder ausgewählt, also `fit` (Z. 55-56). Bei `--model` wird `[model] alias` geschrieben (Z. 86-87).
- Wo A benannt wird: "its Question / hypothesis names that protocol and what it showed" (Z. 276-278).
- Typ: "its type is `exploratory`" (Z. 278). Z. 53 erklärt den Unterschied; ein confirmatory-Test auf Ergebnisse, die schon vorliegen, passt nicht.
- Kriterien vor Ergebnissen setzen: "Set its criteria and constants before seeing results" (Z. 110-112).
- A's Verfehlen: "a missed criterion — that is the result: report the miss first" (Z. 260-261). "a new approach never turns an earlier miss into a pass" (Z. 271-273). Margin senken ist keine Reparatur (Z. 261-262). Historie bleibt (Z. 296-299). A wird nicht umgeschrieben.

Eigenes Urteil oder Lücke:
- Ob "anderes Modell auf denselben Daten" ein Fall von "builds on what an earlier protocol showed" ist, muss ich bewerten. Die Anleitung sagt es nicht ausdrücklich. Mein Urteil: ja, dann `exploratory` und Verweis auf A.
- Ob die neue Registrierung in einen neuen Bereich oder in denselben Bereich kommt, ist nicht festgelegt. Z. 311-312 (ein Bereich pro Frage) spricht für einen neuen.
- Welche C1-Schwelle gilt, ist nicht vorgegeben. Die Anleitung verlangt nur, dass sie vor dem Ergebnis steht.
- Ob die Datenteilung identisch bleibt, muss das neue Protokoll im Data profile festhalten (Z. 100-101). Das ist Ihre Entscheidung, nicht die der Anleitung.

**Fall 15: Analyse-Audit ohne Befunde, aktueller Code/Zusagen/Lauf; adoptieren? Was, wenn ein früherer BLOCKER behoben wurde?**

Explizit:
- Ja, adoptierbar: "An analysis audit with no findings covers the run when it saw the current code, promises and run: there is nothing to decide." (Z. 217-219).
- Adoption: `protocol-fill <PROTOCOL> --from-run <run_id>` (Z. 214-216). Voraussetzungen: Messung, abgeschlossenes deckendes Analyse-Audit und `02_analyze.py --check` müssen gelten (Z. 216-217).
- Vorher Conclusion schreiben: `Conclusion=…` "before adoption" (Z. 188-189).
- Früherer BLOCKER: "It re-checks each earlier decided BLOCKER itself; adoption needs it to find that fix in place — you add nothing to the record." (Z. 219-221).
- Eine Code-Korrektur repariert keinen alten Lauf: "Editing code does not repair an old run." (Z. 172-173). Nach einer Messcode-Korrektur: Test, Commit, neue Messung, `finalize`, Analyse-Audit (Z. 170-172). Ohne neue Messung: Ausgabedatei entfernen (Z. 40-43).
- Bei `repeat_cost = high`: vor dem Reparaturzyklus `frozen = false` setzen, dann neues Preflight-Audit und neues Einfrieren (Z. 174-177).

Eigenes Urteil oder Lücke:
- Ob "nothing to decide" auch bedeutet, dass kein Rohausgabe-Paar nötig ist, ist unklar. Z. 191-192 verlangt ein Paar "per finding". Ohne Befunde folgt daraus kein Paar, die Anleitung sagt es aber nicht ausdrücklich.
- Ob der bekannte Lauf 2026-10-26T08-18-33_7392 nach einer behobenen Code-Korrektur adoptierbar ist, sagt die Anleitung nicht ausdrücklich. Nach Z. 172-173 nein, er braucht eine neue Messung nach der Korrektur. Ob der Record 2026-10-26-08-28-analysis.toml Befunde enthält, weiß ich nicht.
- Ob der Record nach einer Korrektur eine Entscheidung zur behobenen Befundnummer braucht, sagt Z. 171-172 nur für ungelöste Fälle ("unresolved ones are carried"). Gelöste werden nicht übertragen; eine Entscheidung zu "fixed" ist nicht ausdrücklich verlangt.
