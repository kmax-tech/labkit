"""The served instrument behind a vllm-swap proxy: read at resolution, pinned in models.toml, compared at the
end of a run.

The rules from data in memory (`served_instrument`), then what `llm` and `runlog` do with them against a fake
server on localhost that speaks vllm-swap's GET /health (v0.1.0) and the OpenAI chat route — and plain vLLM's
/health, which answers 200 with an empty body.
"""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from labkit.run import llm, llm_backends, runlog
from labkit.run.served_instrument import (
    NOT_REPORTED,
    NOTHING_REPORTED,
    ServedInstrumentChanged,
    ServedReading,
    agreed_value,
    instrument_changes,
    read_health,
    reading_from_health,
)

DIGEST_A = "3f2a9c01b7de"
DIGEST_B = "0badc0ffee42"


def proxy_health(alias="judge", digest=DIGEST_A, running=True, version="0.11.0"):
    """A /health as vllm-swap v0.1.0 writes one, ALIAS configured with DIGEST, running or not."""
    return {
        "tool": {"swap_proxy.py": "b3a2afc3cd05", "start-swap.sh": "fe51baa6c6a4"},
        "current": alias if running else None,
        "aliases": [alias],
        "instruments": {
            alias: {"served_model": "org/m", "cmd": ["vllm", "serve"], "digest": digest}
        },
        "running": {
            "alias": alias,
            "cmd": ["vllm"],
            "digest": digest,
            "vllm_version": version,
        }
        if running
        else None,
    }


class Reading(unittest.TestCase):
    def test_the_proxy_names_digest_tool_and_the_running_version(self):
        self.assertEqual(
            reading_from_health(proxy_health(), "judge"),
            ServedReading(
                DIGEST_A,
                "start-swap.sh=fe51baa6c6a4,swap_proxy.py=b3a2afc3cd05",
                "0.11.0",
            ),
        )

    def test_an_alias_not_loaded_has_its_digest_and_no_version(self):
        # the proxy loads a model on its first request: before it, only the configuration is known
        reading = reading_from_health(proxy_health(running=False), "judge")
        self.assertEqual(
            (reading.digest, reading.vllm_version), (DIGEST_A, NOT_REPORTED)
        )

    def test_another_alias_running_gives_no_version_for_this_one(self):
        health = proxy_health()
        health["running"]["alias"] = "other"
        self.assertEqual(
            reading_from_health(health, "judge").vllm_version, NOT_REPORTED
        )

    def test_a_proxy_before_the_version_and_tool_fields_reports_the_digest_only(self):
        # real: vllm-swap before f220e19 had no vllm_version, before 8a2c872 no tool
        health = proxy_health()
        del health["tool"]
        del health["running"]["vllm_version"]
        self.assertEqual(
            reading_from_health(health, "judge"),
            ServedReading(DIGEST_A, NOT_REPORTED, NOT_REPORTED),
        )

    def test_no_health_and_an_unconfigured_alias_report_nothing(self):
        self.assertEqual(reading_from_health(None, "judge"), NOTHING_REPORTED)
        self.assertEqual(
            reading_from_health(proxy_health(), "nosuch").digest, NOT_REPORTED
        )


class Agreement(unittest.TestCase):
    def test_endpoints_that_agree_give_their_value_and_silent_ones_do_not_count(self):
        self.assertEqual(
            agreed_value([DIGEST_A, NOT_REPORTED, DIGEST_A], NOT_REPORTED), DIGEST_A
        )

    def test_none_reporting_gives_the_missing_marker(self):
        self.assertEqual(
            agreed_value([NOT_REPORTED, NOT_REPORTED], NOT_REPORTED), NOT_REPORTED
        )

    def test_disagreeing_endpoints_are_a_mismatch_naming_both(self):
        self.assertEqual(
            agreed_value([DIGEST_B, DIGEST_A], NOT_REPORTED),
            f"MISMATCH:{DIGEST_B},{DIGEST_A}",
        )


class Changes(unittest.TestCase):
    END = ServedReading(DIGEST_A, "t", "0.11.0")

    def test_the_same_instrument_at_both_ends_is_no_change(self):
        # twin of every blocker below: the correct run must pass
        self.assertEqual(instrument_changes(DIGEST_A, "0.11.0", self.END), [])

    def test_a_changed_digest_is_named(self):
        changes = instrument_changes(DIGEST_B, "0.11.0", self.END)
        self.assertEqual(
            changes, [f"the configuration digest changed from {DIGEST_B} to {DIGEST_A}"]
        )

    def test_an_end_without_digest_blocks(self):
        # a check that could not run blocks: which instrument answered last is not known
        changes = instrument_changes(DIGEST_A, "0.11.0", NOTHING_REPORTED)
        self.assertEqual(len(changes), 1)
        self.assertIn("the end reports no digest", changes[0])

    def test_a_changed_version_is_named(self):
        changes = instrument_changes(DIGEST_A, "0.10.2", self.END)
        self.assertEqual(changes, ["the vLLM version changed from 0.10.2 to 0.11.0"])

    def test_a_version_unknown_at_either_end_is_no_change(self):
        # another alias of the proxy ran last, or no answer came: nothing to compare
        self.assertEqual(instrument_changes(DIGEST_A, NOT_REPORTED, self.END), [])
        self.assertEqual(
            instrument_changes(
                DIGEST_A, "0.11.0", ServedReading(DIGEST_A, "t", NOT_REPORTED)
            ),
            [],
        )


class FakeServer:
    """A server on localhost: `health` is what GET /health answers (None: an empty 200 body, as plain vLLM
    answers it); POST /v1/chat/completions answers "OK". Change `health` while it runs."""

    def __init__(self, health):
        self.health = health
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002 the base's name
                pass

            def _send(self, body: bytes):
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path != "/health":
                    self.send_error(404)
                    return
                self._send(
                    b"" if fake.health is None else json.dumps(fake.health).encode()
                )

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                reply = {
                    "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]
                }
                self._send(json.dumps(reply).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class _WithServer(unittest.TestCase):
    """A fake server and a models.toml whose alias `v` serves the proxy alias `judge` from it."""

    HEALTH: dict | None = None

    def setUp(self):
        self.fake = FakeServer(
            self.HEALTH if self.HEALTH is None else json.loads(json.dumps(self.HEALTH))
        )
        self.addCleanup(self.fake.close)
        self.tmp = Path(tempfile.mkdtemp())
        saved_find = llm.find_models_toml
        saved_frozen, saved_first = dict(llm._FROZEN), dict(llm._FIRST_VERSION)
        saved_rr = dict(llm_backends._RR)

        def restore():
            llm.find_models_toml = saved_find
            llm._FROZEN.clear()
            llm._FROZEN.update(saved_frozen)
            llm._FIRST_VERSION.clear()
            llm._FIRST_VERSION.update(saved_first)
            llm_backends._RR.clear()
            llm_backends._RR.update(saved_rr)

        self.addCleanup(restore)
        llm._FROZEN.clear()
        llm._FIRST_VERSION.clear()
        llm_backends._RR.clear()

    def models_toml(self, extra: str = "") -> None:
        path = self.tmp / "models.toml"
        path.write_text(
            f'[models.v]\nbackend = "openai"\nmodel = "judge"\nendpoints = ["{self.fake.url}"]\n{extra}',
            encoding="utf-8",
        )
        llm.find_models_toml = lambda: path


class Resolution(_WithServer):
    HEALTH = proxy_health(running=False)

    def test_the_record_names_the_served_digest(self):
        self.models_toml()
        self.assertEqual(llm.resolve("v")["served_digest"], DIGEST_A)

    def test_a_pin_the_proxy_reports_resolves_and_is_recorded(self):
        self.models_toml(f'instrument_digest = "{DIGEST_A}"\n')
        self.assertEqual(llm.resolve("v")["instrument_digest"], DIGEST_A)

    def test_a_pin_the_proxy_does_not_report_refuses_the_alias(self):
        self.models_toml(f'instrument_digest = "{DIGEST_B}"\n')
        with self.assertRaises(ValueError) as ctx:
            llm.spec("v")
        self.assertIn(f"says '{DIGEST_A}'", str(ctx.exception))

    def test_a_pin_that_is_no_digest_is_refused_naming_the_form(self):
        self.models_toml('instrument_digest = "latest"\n')
        with self.assertRaises(ValueError) as ctx:
            llm.spec("v")
        self.assertIn("12 lowercase hex digits", str(ctx.exception))


class PlainVllm(_WithServer):
    HEALTH = None  # plain vLLM: /health answers 200 with an empty body

    def test_its_health_reads_as_none(self):
        self.assertIsNone(read_health(self.fake.url, {}))

    def test_it_is_recorded_as_not_reported_and_calls_go_through(self):
        self.models_toml()
        self.assertEqual(llm.resolve("v")["served_digest"], NOT_REPORTED)
        self.assertEqual(llm.complete("v", "hi", attempts=1), "OK")

    def test_a_pin_on_it_refuses_the_alias(self):
        self.models_toml(f'instrument_digest = "{DIGEST_A}"\n')
        with self.assertRaises(ValueError) as ctx:
            llm.spec("v")
        self.assertIn("says 'not reported'", str(ctx.exception))


class EndOfRun(_WithServer):
    HEALTH = proxy_health(running=False)

    def run_area(self, during=None) -> Path:
        """One run that asks `v` once and then calls DURING (a change to the server), in an area of its
        own; its run directory."""
        self.models_toml()
        area = self.tmp / "area"
        area.mkdir()
        with runlog.run("t", config={"model": "v"}, base_dir=area):
            self.fake.health = proxy_health()  # the first request loads the model
            llm.complete("v", "hi", attempts=1)
            if during is not None:
                during()
        return self.only_run(area)

    def only_run(self, area: Path) -> Path:
        (run_dir,) = (area / "runs").iterdir()
        return run_dir

    def test_the_same_instrument_completes_and_records_both_ends(self):
        run_dir = self.run_area()
        served = json.loads((run_dir / "completion.json").read_text())[
            "served_instruments"
        ]
        self.assertEqual(
            served,
            {
                "v": {
                    "start_digest": DIGEST_A,
                    "first_vllm_version": "0.11.0",
                    "digest": DIGEST_A,
                    "tool": "start-swap.sh=fe51baa6c6a4,swap_proxy.py=b3a2afc3cd05",
                    "vllm_version": "0.11.0",
                }
            },
        )
        config = json.loads((run_dir / "config.json").read_text())
        self.assertEqual(config["models_resolved"]["v"]["served_digest"], DIGEST_A)

    def assert_unfinalized(self, during, said: str) -> None:
        area = self.tmp / "area"
        with self.assertRaises(ServedInstrumentChanged) as ctx:
            self.run_area(during)
        self.assertIn(said, str(ctx.exception))
        run_dir = self.only_run(area)
        self.assertTrue(
            (run_dir / "metrics.json").is_file()
        )  # the numbers stay on disk
        self.assertFalse((run_dir / "completion.json").exists())
        failure = json.loads((run_dir / "failure.json").read_text())
        self.assertEqual(failure["error"], "ServedInstrumentChanged")

    def test_a_configuration_changed_during_the_run_leaves_it_unfinalized(self):
        def edit():
            self.fake.health = proxy_health(digest=DIGEST_B)

        self.assert_unfinalized(edit, f"changed from {DIGEST_A} to {DIGEST_B}")

    def test_a_vllm_version_changed_during_the_run_leaves_it_unfinalized(self):
        def new_session():
            self.fake.health = proxy_health(version="0.12.0")

        self.assert_unfinalized(
            new_session, "the vLLM version changed from 0.11.0 to 0.12.0"
        )

    def test_a_proxy_gone_at_the_end_leaves_it_unfinalized(self):
        def gone():
            self.fake.health = None

        self.assert_unfinalized(gone, "the end reports no digest")


if __name__ == "__main__":
    unittest.main()
