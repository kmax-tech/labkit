#!/usr/bin/env python3
"""Tests for runlog's model-identity field (`models_resolved`).

Why here: the field is *recorded provenance*. If resolution silently skips
or crashes, nothing fails at run time — the config just keeps naming an
alias whose meaning drifts with models.toml (the 2026-09-09 scar: 25 run
configs said "sonnet"; the answering weights were reconstructable only via
the pinned commit). Same silent class as the env fingerprint.

Run:  .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]

from labkit.run import provenance  # noqa: E402


class ResolveModels(unittest.TestCase):
    def test_model_and_suffixed_keys_resolve(self):
        spec = {"alias": "sonnet", "model": "claude-sonnet-5", "backend": "cli"}
        with mock.patch("labkit.run.llm.resolve", return_value=spec) as res:
            got = provenance.resolve_models(
                {"model": "sonnet", "judge_model": "sonnet", "n": 5}
            )
        self.assertEqual(got, {"sonnet": spec})
        self.assertEqual(res.call_count, 2)  # both keys, deduped by alias key

    def test_non_model_keys_and_non_strings_skipped(self):
        with mock.patch("labkit.run.llm.resolve") as res:
            got = provenance.resolve_models(
                {"n": 5, "temperature": 0.0, "model": 7, "modelling": "x"}
            )
        self.assertEqual(got, {})
        res.assert_not_called()

    def test_failure_recorded_not_raised(self):
        with mock.patch(
            "labkit.run.llm.resolve",
            side_effect=KeyError("alias 'x' not in models.toml"),
        ):
            got = provenance.resolve_models({"model": "x"})
        self.assertIn("unresolved:", got["x"])
        self.assertIn("models.toml", got["x"])


class UnpinnedWarning(unittest.TestCase):
    def test_unpinned_env_warns_on_stderr(self):
        import tempfile

        lockless = Path(tempfile.mkdtemp())
        err = io.StringIO()
        with redirect_stderr(err):
            state = provenance.env_state(lockless)
        self.assertTrue(state.endswith("| unpinned"))
        self.assertIn("unpinned", err.getvalue())
        self.assertIn("requirements.lock", err.getvalue())


if __name__ == "__main__":
    unittest.main()
