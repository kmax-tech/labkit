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
pip install "labkit==0.1.0"        # aus diesem Verzeichnis: pip install ~/projects/labkit
```

```python
from labkit import runlog, llm, batch
```

**Version pinnen, nie `pip install -e` in einem Experiment-Repo.** Ein Lauf
protokolliert seine Umgebung; könnten sich die Helfer unter einem
abgeschlossenen Lauf ändern, ist dieser Eintrag eine Behauptung über eine
Umgebung, die es nicht mehr gibt. Editable gehört hierher, wo die Tests sind.

Repos mit flachen Alt-Imports (`import runlog`) brauchen nichts umzuschreiben —
eine Zeile pro Modul genügt:

```python
# lib/runlog.py
from labkit.runlog import *  # noqa: F401,F403
```

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
