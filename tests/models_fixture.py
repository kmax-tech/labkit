"""A models.toml for tests whose code resolves an alias (`llm.spec`).

A stamped script finds its lab's models.toml from its own path; imported
by a test, it searches from pytest's. `serve` points `llm` at a file of the
test's own and forgets every frozen spec for the test's span, so a test can
also play a new process reading an edited file (`llm.identity`).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.run import llm


def toml(alias: str, model: str) -> str:
    """A claude-cli entry for ALIAS answering with MODEL."""
    return f'[models.{alias}]\nbackend = "claude-cli"\nmodel = "{model}"\n'


def serve(case: type[unittest.TestCase] | unittest.TestCase, text: str) -> Path:
    """models.toml with TEXT for CASE (a class: until its last test; an
    instance: until this test ends), `llm` reading it with nothing frozen.
    Returns the file — rewrite it and clear `llm._FROZEN` to play a new
    process after an edit."""
    path = Path(tempfile.mkdtemp()) / "models.toml"
    path.write_text(text, encoding="utf-8")
    patches = (
        mock.patch.object(llm, "_find_models_toml", lambda: path),
        mock.patch.dict(llm._FROZEN, clear=True),
    )
    for p in patches:
        if isinstance(case, type):
            case.enterClassContext(p)
        else:
            case.enterContext(p)
    return path
