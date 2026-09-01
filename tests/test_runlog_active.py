"""Tests fuer `runlog._is_alive` — die Frage „laeuft dieser Lauf noch?".

Warum das getestet gehoert: Der Arbeitsstandard sagt, was gerade laeuft, werde
**nachgesehen und nicht erfragt**. Eine falsche Auskunft ist damit teurer als
gar keine — sie fuehrt dazu, dass ein toter Lauf nicht neu gestartet wird.

Genau das passierte am 2026-08-15: `runlog` meldete einen Lauf vom 13. August
als laufend, weil das Betriebssystem dessen PID an einen macOS-Dienst
(`RemoteManagement`) neu vergeben hatte. Die Existenzpruefung per
`os.kill(pid, 0)` kann das prinzipiell nicht bemerken.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test

from labkit import runlog  # noqa: E402
from labkit.runlog import _command_of, _is_alive  # noqa: E402


class TestIsAlive(unittest.TestCase):

    def test_our_own_process_counts_as_alive_for_its_own_script(self):
        cmd = _command_of(os.getpid())
        self.assertIsNotNone(cmd, "ps nicht verfuegbar — Test waere sinnlos")
        token = next(t for t in cmd.split() if t)          # irgendein echtes Token
        self.assertTrue(_is_alive(os.getpid(), token))

    def test_a_recycled_pid_is_not_reported_as_running(self):
        """Der Fall vom 2026-08-15: PID lebt, ist aber ein anderer Prozess."""
        self.assertFalse(_is_alive(os.getpid(), "05_refusal.py"))

    def test_a_dead_pid_is_false(self):
        dead = 999_999                                     # praktisch sicher frei
        try:
            os.kill(dead, 0)
        except ProcessLookupError:
            self.assertFalse(_is_alive(dead, "irgendein_skript.py"))
        except PermissionError:
            self.skipTest("PID unerwartet belegt")

    def test_unknown_is_none_not_true(self):
        """Ohne Skriptnamen ist die Frage nicht entscheidbar — dann lieber
        `None` als ein falsches `True`."""
        self.assertIsNone(_is_alive(os.getpid(), None))
        self.assertIsNone(_is_alive(os.getpid(), ""))

    def test_a_missing_pid_field_is_none(self):
        self.assertIsNone(_is_alive(None, "x.py"))
        self.assertIsNone(_is_alive("81892", "x.py"))      # String, nicht int


if __name__ == "__main__":
    unittest.main()


class TestOutputsJson(unittest.TestCase):
    """runlog.Run.output (2026-08-18): Wer im Run-Verzeichnis steht, muss ohne
    Quellcode-Lektuere beantworten koennen, wohin der Lauf geschrieben hat —
    config.json friert nur die EINGABEN ein (Befund MH beim Lesen eines Runs)."""

    def test_registrierte_ausgabe_landet_mit_hash_in_outputs_json(self):
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            out = d / "output" / "x.jsonl"; out.parent.mkdir()
            with runlog.run("t", config={}, base_dir=d) as r:
                out.write_text("a\nb\n", encoding="utf-8")
                r.output(out)
            oj = json.loads(next((d / "runs").glob("*/outputs.json")
                                 ).read_text(encoding="utf-8"))
            self.assertEqual(oj[0]["lines"], 2)
            self.assertEqual(len(oj[0]["sha256"]), 16)

    def test_fehlende_datei_wird_benannt_statt_verschwiegen(self):
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with runlog.run("t", config={}, base_dir=d) as r:
                r.output(d / "output" / "nie-geschrieben.jsonl")
            oj = json.loads(next((d / "runs").glob("*/outputs.json")
                                 ).read_text(encoding="utf-8"))
            self.assertIsNone(oj[0]["sha256"])
            self.assertIn("nicht vorhanden", oj[0]["note"])


class TestUntrackedSourceSnapshot(unittest.TestCase):
    """source-untracked/ (2026-08-18, Einwand MH): Der Einzeldatei-Snapshot
    liess Nachbarmodule ungesichert — beim ersten Lauf eines frischen Bereichs
    ist der GANZE scripts/-Ordner untracked, in keinem Commit und keinem Diff.
    Jetzt: Patch = getrackter Drift, source-untracked/ = was git nicht sieht."""

    def _repo(self, d):
        import subprocess
        for cmd in (["git", "init", "-q"],
                    ["git", "config", "user.email", "t@t"],
                    ["git", "config", "user.name", "t"]):
            subprocess.run(cmd, cwd=d, capture_output=True)

    def test_untracked_nachbarn_werden_kopiert_getrackte_nicht(self):
        import json, subprocess, sys, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            d = Path(td); self._repo(d)
            scripts = d / "scripts"; scripts.mkdir()
            entry = scripts / "01_measure.py"; entry.write_text("# entry\n")
            (scripts / "helper.py").write_text("# untracked sibling\n")
            tracked = scripts / "committed.py"; tracked.write_text("# tracked\n")
            (scripts / "output").mkdir(); (scripts / "output" / "x.jsonl").write_text("{}\n")
            subprocess.run(["git", "add", "scripts/committed.py"], cwd=d, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "x"], cwd=d, capture_output=True)
            old_argv = sys.argv[0]
            sys.argv[0] = str(entry)
            try:
                with runlog.run("t", config={}, base_dir=d):
                    pass
            finally:
                sys.argv[0] = old_argv
            run_dir = next((d / "runs").glob("*"))
            copied = sorted(p.name for p in (run_dir / "source-untracked").rglob("*.py"))
            self.assertIn("helper.py", copied)
            self.assertIn("01_measure.py", copied)     # entry selbst auch untracked
            self.assertNotIn("committed.py", copied)   # getrackt -> Sache des Diffs
            self.assertEqual([], [p.name for p in
                                  (run_dir / "source-untracked").rglob("*.jsonl")],
                             "output/ darf nicht in den Quell-Snapshot")
            cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
            self.assertIn("helper.py", cfg["untracked_sources"])

    def test_ausserhalb_eines_git_repos_faellt_nichts_um(self):
        import sys, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            entry = d / "x.py"; entry.write_text("# e\n")
            old_argv = sys.argv[0]
            sys.argv[0] = str(entry)
            try:
                with runlog.run("t", config={}, base_dir=d) as r:
                    r.metrics(n=1)
            finally:
                sys.argv[0] = old_argv


    def test_getrackter_einstieg_schnappt_nicht(self):
        # Bereich einmal committet -> ab da gilt "vor dem Lauf committen",
        # nicht Kopieren; ein Snapshot, der weiter feuert, wuerde Daten saugen
        # (der erste Entwurf kopierte output/ und alte runs/ mit).
        import subprocess, sys, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            d = Path(td); self._repo(d)
            scripts = d / "scripts"; scripts.mkdir()
            entry = scripts / "01_measure.py"; entry.write_text("# entry\n")
            subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "x"], cwd=d, capture_output=True)
            (scripts / "spaeter.py").write_text("# neuer untracked Nachbar\n")
            old_argv = sys.argv[0]
            sys.argv[0] = str(entry)
            try:
                with runlog.run("t", config={}, base_dir=d):
                    pass
            finally:
                sys.argv[0] = old_argv
            run_dir = next((d / "runs").glob("*"))
            self.assertFalse((run_dir / "source-untracked").exists())
