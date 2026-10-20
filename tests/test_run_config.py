"""runs.RunConfig: config.json read once into labkit's own fields, held to
their types, every key the writer writes and no other; the experiment's own
settings (`config`) free JSON; nested values handed out as copies.

    .venv/bin/python -m pytest tests/test_run_config.py
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import head

from labkit.formats import runs
from labkit.run import runlog

BASE = {"schema_version": 3, "run_kind": "measurement"}


class Fields(unittest.TestCase):
    def test_a_labkit_field_of_the_wrong_type_is_unreadable_by_name(self) -> None:
        for key, value in (
            ("pid", "123"),
            ("pid", True),
            ("unfrozen_ack", "yes"),
            ("command", "python x.py"),
            ("data", ["x"]),
            ("git", 7),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaisesRegex(runs.RunConfigError, f"^{key} = "):
                    runs.parse_run_config({**BASE, key: value})

    def test_twin_the_experiments_own_config_is_free(self) -> None:
        own = {"anything": [1, {"nested": None}], "pid": "not labkit's", "run_kind": 3}
        cfg = runs.parse_run_config({**BASE, "config": own})
        self.assertEqual(cfg.config, own)

    def test_a_key_labkit_does_not_write_is_refused_by_name(self) -> None:
        with self.assertRaisesRegex(
            runs.RunConfigError, "^seed: not a field labkit writes"
        ):
            runs.parse_run_config({**BASE, "seed": 3})

    def test_an_older_record_names_its_version_not_its_keys(self) -> None:
        with self.assertRaisesRegex(runs.RunConfigError, "0.99.0"):
            runs.parse_run_config({"schema_version": 2, "long": True})


class WriterReaderParity(unittest.TestCase):
    def test_the_writer_writes_exactly_the_fields_the_reader_knows(self) -> None:
        area = Path(tempfile.mkdtemp())
        (area / "PROTOCOL-x.md").write_text(head(promises=None), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            with runlog.run("x", {"k": 1}, area) as run:
                run.metrics(n=1)
        written = json.loads((run.dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(written), sorted(runs.RUN_CONFIG_KEYS))
        cfg = runs.read_run_config(run.dir)
        assert cfg is not None
        self.assertEqual(cfg.as_record(), written)


class NestedValuesAreCopies(unittest.TestCase):
    """`frozen=True` freezes the fields, not a dict inside one: the nested
    tables are stored as their JSON text and every read is a fresh copy, so
    one reader's change reaches no other (decided 2026-10-20 over storing
    read-only views, which json.dumps cannot write)."""

    def test_changing_what_was_read_changes_nothing_stored(self) -> None:
        cfg = runs.parse_run_config(
            {**BASE, "config": {"a": [1]}, "data": {"x": {"rows": 2}}, "command": ["p"]}
        )
        cfg.config["a"].append(2)
        cfg.data["x"]["rows"] = 99
        assert cfg.command is not None
        cfg.command.append("q")
        cfg.as_record()["config"]["a"] = []
        cfg.repeat_basis()["data"]["x"] = None
        self.assertEqual(
            (cfg.config, cfg.data, cfg.command),
            ({"a": [1]}, {"x": {"rows": 2}}, ["p"]),
        )


if __name__ == "__main__":
    unittest.main()
