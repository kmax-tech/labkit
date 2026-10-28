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

from protocol_fixture import run_record, head

from labkit.formats import runs
from labkit.run import runlog

BASE = run_record()


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

    def test_a_missing_field_is_refused_and_null_only_where_the_writer_writes_it(
        self,
    ) -> None:
        """Missing is no null and no default (2026-10-20); null is a value
        only where the writer writes one."""
        for key in runs.RUN_CONFIG_KEYS[1:]:  # without the schema: its own check
            with self.subTest(missing=key):
                record = run_record(drop=(key,))
                with self.assertRaisesRegex(runs.RunConfigError, f"^{key} missing"):
                    runs.parse_run_config(record)
        cfg = runs.parse_run_config(run_record(promises=None, derived_from=None))
        self.assertIsNone(cfg.promises)  # a protocol without a block
        for key in ("config", "data", "protocol", "unfrozen_ack", "pid"):
            with self.subTest(null=key):
                with self.assertRaisesRegex(runs.RunConfigError, f"^{key} = null, not"):
                    runs.parse_run_config(run_record({key: None}))

    def test_an_acknowledged_run_stays_unreportable_and_without_the_field_unreadable(
        self,
    ) -> None:
        """Deleting `"unfrozen_ack": true` from config.json made an acknowledged
        run read as a plain measurement, its number reportable (review
        2026-10-20). The complete record stays unreportable; without the
        field it is no record."""
        area = Path(tempfile.mkdtemp())
        run = area / "runs" / "2026-01-01T00-00-00_aaaa"
        run.mkdir(parents=True)
        record = run_record(unfrozen_ack=True)
        (run / "config.json").write_text(json.dumps(record), encoding="utf-8")
        cfg = runs.read_run_config(run)
        assert cfg is not None
        self.assertIn("LABKIT_UNFROZEN=1", " ".join(runs.unreportable(cfg)))
        del record["unfrozen_ack"]
        (run / "config.json").write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(runs.RunConfigError, "unfrozen_ack missing"):
            runs.read_run_config(run)

    def test_an_older_record_names_its_version_not_its_keys(self) -> None:
        with self.assertRaisesRegex(runs.RunConfigError, "0.99.0"):
            runs.parse_run_config({"schema_version": 2, "long": True})
        with self.assertRaisesRegex(runs.RunConfigError, "0.103.0"):
            runs.parse_run_config({"schema_version": 3, "cost_tier": "hours"})

    def test_the_records_repeat_cost_holds_the_heads_two_values_or_null(self) -> None:
        """A retired or mistyped value is corrupt metadata, not a readable run
        (review 2026-10-25: schema 4 read "hours" as a string and went on)."""
        for value in ("hours", "seconds", "unexpected"):
            with self.subTest(value):
                with self.assertRaisesRegex(
                    runs.RunConfigError, f"repeat_cost = {value!r}"
                ):
                    runs.parse_run_config(run_record({"repeat_cost": value}))
        for value in ("low", "high", None):
            with self.subTest(value):
                self.assertEqual(
                    runs.parse_run_config(
                        run_record({"repeat_cost": value})
                    ).repeat_cost,
                    value,
                )


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


class ReviewFindings(unittest.TestCase):
    """The independent review of 8d789b4 and e0c21e0 (2026-10-20)."""

    def test_the_record_keeps_its_key_order(self) -> None:
        cfg = runs.parse_run_config({**BASE, "config": {"zeta": 1, "alpha": 2}})
        self.assertEqual(list(cfg.config), ["zeta", "alpha"])
        self.assertEqual(list(cfg.as_record()["config"]), ["zeta", "alpha"])

    def test_the_status_line_prints_the_config_as_stored(self) -> None:
        from labkit.run import runlog_command

        area = Path(tempfile.mkdtemp())
        run = area / "runs" / "2026-01-01T00-00-00_aaaa"
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps(run_record(config={"zeta": "ü", "alpha": [0]})),
            encoding="utf-8",
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            runlog_command._print_status(str(area), runlog.active(area), [])
        self.assertIn('{"zeta": "ü", "alpha": [0]}', out.getvalue())

    def test_the_binding_holds_id_and_path_only_and_reads_back_as_stored(self) -> None:
        with self.assertRaisesRegex(runs.RunConfigError, "protocol.zz: not a field"):
            runs.parse_run_config(
                {**BASE, "protocol": {"id": "x", "path": "p", "zz": 1}}
            )
        unbound = runs.parse_run_config(
            {**BASE, "protocol": {"id": None, "path": None}}
        )
        self.assertEqual(unbound.protocol, runs.ProtocolBinding(None, None))
        self.assertEqual(unbound.as_record()["protocol"], {"id": None, "path": None})

    def test_bytes_no_text_and_runaway_nesting_are_an_unreadable_run(self) -> None:
        area = Path(tempfile.mkdtemp())
        for name, raw in (
            ("2026-01-01T00-00-00_aaaa", b"\xff\xfe{"),
            ("2026-01-01T00-00-01_bbbb", b"[" * 100_000),
        ):
            (area / "runs" / name).mkdir(parents=True)
            (area / "runs" / name / "config.json").write_bytes(raw)
            with self.assertRaises(runs.RunConfigError):
                runs.read_run_config(area / "runs" / name)
        self.assertEqual(
            [r.state for r in runlog.active(area)], ["unreadable", "unreadable"]
        )

    def test_an_active_run_has_a_config_or_an_error_exactly_one(self) -> None:
        d = Path("runs/x")
        cfg = runs.parse_run_config(dict(BASE))
        for config, error in ((None, None), (cfg, "broken")):
            with self.subTest(config=config, error=error):
                with self.assertRaises(ValueError):
                    runlog.ActiveRun("x", d, "unreadable", None, config, error)
        runlog.ActiveRun("x", d, "crashed", False, cfg, None)  # the twins
        runlog.ActiveRun("x", d, "unreadable", None, None, "broken")


if __name__ == "__main__":
    unittest.main()
