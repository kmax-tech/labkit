"""The installed labkit's version has one reading (`console.installed_version`),
and each caller says what its absence means: labkit run from a source tree
that is not installed (on `PYTHONPATH` only) ends a run that declares an
answer reading and a `labkit-init` that needs a pin with a sentence, never
a traceback; the hooks' mark says "unknown"."""

from __future__ import annotations

import unittest
from unittest import mock

from labkit.formats import console
from labkit.gates import install_hooks
from labkit.run import runlog
from labkit.tools import scaffold


class NotInstalled(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(console, "installed_version", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_run_declaring_an_answer_reading_is_refused_with_a_sentence(self):
        with self.assertRaises(SystemExit) as cm:
            runlog._declared_under()
        self.assertIn("not installed", str(cm.exception))
        self.assertIn("pip install -e .", str(cm.exception))

    def test_the_pin_of_a_new_lab_is_refused_with_a_sentence(self):
        with self.assertRaises(console.Refused) as cm:
            scaffold.pinned_ref()
        self.assertIn("no installed version to pin", str(cm.exception))

    def test_the_hooks_mark_says_unknown(self):
        self.assertEqual(install_hooks.labkit_version(), "unknown")


class Installed(unittest.TestCase):
    """The twins: with the package installed each caller gets its version."""

    def test_the_version_reads(self):
        installed = console.installed_version()
        assert installed is not None, "the suite runs with labkit installed"
        self.assertEqual(runlog._declared_under(), installed)
        self.assertEqual(install_hooks.labkit_version(), installed)


if __name__ == "__main__":
    unittest.main()
