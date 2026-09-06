# labkit — geteilte Labor-Helfer

Die vier Bausteine, die jedes Experiment-Repo importiert, an **einer** Stelle:
Ledger (`runlog`), LLM-Backend (`llm`), fortsetzbare Ausgabedatei (`batch`) und
der Protokoll-Checker (`protocol_check`, installiert als `protocol-check`).

Vorher lagen sie als Kopie in jedem Repo — bis zu drei Fassungen pro Datei
(`experiments/`, `resources/templates/`, `~/.claude/resources/`). Am 2026-09-01
war `experiments/llm.py` in einem aktiven Repo 379 Zeilen hinter dem Master,
während der Drift-Check „in sync" meldete: er verglich den Schnappschuss,
nicht die importierte Datei.

## Benutzen

```bash
pip install ~/projects/labkit      # in Repos: gepinnt via requirements.txt/.lock
```

```python
from labkit import runlog, llm, batch
```

Zwei **Konsolen-Kommandos** kommen mit der Installation (beide mit `--help`):

```bash
protocol-check <PROTOCOL-*.md>...   # Pflichtfelder-Check (MUST/SHOULD-Kontrakt)
runlog [<bereich>]                  # offene Läufe: run_id, running/crashed, Skript
```

**Version pinnen, nie `pip install -e` in einem Experiment-Repo.** Ein Lauf
protokolliert seine Umgebung; könnten sich die Helfer unter einem
abgeschlossenen Lauf ändern, ist dieser Eintrag eine Behauptung über eine
Umgebung, die es nicht mehr gibt. Editable gehört hierher, wo die Tests sind.

Repos mit flachen Alt-Imports (`import runlog`) brauchen nichts umzuschreiben —
ein Shim pro Modul genügt. Kanonische Form ist der Modul-Handover (nie
`import *`: das verliert die privaten Namen, und Monkeypatching landet auf
einer Kopie):

```python
# lib/runlog.py
import sys
from labkit import runlog as _mod
sys.modules[__name__] = _mod
```

`lib init <repo> --sync check` erkennt genau diese Form als Shim („nothing to
sync"); ein Guard-Test im Repo (`test_shared_helpers_come_from_labkit.py`)
schlägt an, wenn jemand eine Implementierung zurück in die Shim-Datei klebt.

## Entwickeln

```bash
python3 -m unittest discover -s tests -v
```

Änderung → Test → `version` in `pyproject.toml` erhöhen → Tag. Die
Experiment-Repos ziehen über ihren Pin nach, jedes zu seinem Zeitpunkt; ein
laufendes Experiment wird nie von einem Bugfix überrascht.

## Grenze

Hier wohnt nur, was **mehr als ein Repo** benutzt. Projekt-eigene Helfer
bleiben im Projekt (`lib/`) — ein Modul wandert erst hierher, wenn es zum
zweiten Mal gebraucht wird.

Nicht hier: Templates zum Ausfüllen (`~/.claude/resources/`, sie sollen
divergieren) und Prosa-Referenzen wie der Style-Guide (gelesen, nicht
importiert).
