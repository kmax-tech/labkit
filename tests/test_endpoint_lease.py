"""Tests for the endpoint lease — one alias at a time per model slot.

Occasion (2026-09-08): a judge test fired next to a running probe on the same
swap proxy. Both aliases resolve to one GPU slot, so they evicted each other
(~5 min per swap); the timeouts came back as empty answers, and the area's
stop rule "more than 2 of 96 rounds without a parsed mechanism => the parser
is the finding" counts exactly those. An operator slip that lands in a
reported number is a missing interlock, so the interlock gets the parser
treatment: the properties are tested, not the happy path.

`batch.Store`'s lock is not this lock — it guards the output FILE and says
nothing about who is using the model.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import endpoint_lease as el          # noqa: E402

EP = "http://gammaweb07.medien.uni-weimar.de:11726"
EP2 = "http://gammaweb09.medien.uni-weimar.de:11490"


class TestEndpointLease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LABKIT_LEASE_DIR"] = self.tmp.name
        os.environ.pop("LABKIT_NO_ENDPOINT_LEASE", None)
        el.release_all()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(el.release_all)
        self.addCleanup(lambda: os.environ.pop("LABKIT_LEASE_DIR", None))

    def _foreign(self, endpoint, alias, pid, script="01_measure.py",
                 started="2026-09-08T17:00:00"):
        """A lease record of ANOTHER process, written by hand."""
        d = Path(self.tmp.name) / el._slug(endpoint)
        d.mkdir(parents=True, exist_ok=True)
        rec = {"alias": alias, "pid": pid, "script": script,
               "endpoint": endpoint, "started": started, "argv": script}
        (d / f"{alias}.{pid}.json").write_text(json.dumps(rec), encoding="utf-8")
        return rec

    def _live_other_process(self):
        """A real, live, FOREIGN process — the own pid cannot serve here.

        The lease deliberately never blocks its OWN process: a script that
        runs the generator stage and then the judge stage is exactly the
        staggering the rule wants, and it holds two aliases in one pid.
        """
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc.pid, Path(sys.executable).name

    # -- the rule ---------------------------------------------------------
    def test_free_endpoint_is_leased(self):
        el.acquire("gpt-oss-vllm", [EP])
        self.assertEqual([h["alias"] for h in el.holders(EP)], ["gpt-oss-vllm"])

    def test_second_alias_is_refused(self):
        """The case that cost the day: judge test next to a running probe."""
        pid, script = self._live_other_process()
        self._foreign(EP, "gpt-oss-vllm", pid=pid, script=script)
        with self.assertRaises(SystemExit) as cm:
            el.acquire("qwen25-32b-awq", [EP])
        msg = str(cm.exception)
        self.assertIn("gpt-oss-vllm", msg)
        self.assertIn("LABKIT_NO_ENDPOINT_LEASE", msg)

    def test_same_alias_may_share(self):
        """Sharing an alias costs throughput, never a swap — pilot next to resume."""
        pid, script = self._live_other_process()
        self._foreign(EP, "gpt-oss-vllm", pid=pid, script=script)
        el.acquire("gpt-oss-vllm", [EP])          # must not raise
        self.assertTrue(any(h["pid"] == os.getpid() for h in el.holders(EP)))

    def test_other_endpoint_is_untouched(self):
        pid, script = self._live_other_process()
        self._foreign(EP, "gpt-oss-vllm", pid=pid, script=script)
        el.acquire("qwen", [EP2])                 # different slot, no conflict
        self.assertEqual([h["alias"] for h in el.holders(EP2)], ["qwen"])

    def test_dead_holder_does_not_block_forever(self):
        """A crashed run must not own the slot; PID 999999 is nobody."""
        self._foreign(EP, "gpt-oss-vllm", pid=999999)
        el.acquire("qwen25-32b-awq", [EP])
        self.assertEqual([h["alias"] for h in el.holders(EP)], ["qwen25-32b-awq"])

    def test_undecidable_holder_counts_as_alive(self):
        """Failure direction: a wrong refusal costs a message, a wrong
        admission costs the run. A record without a script name makes liveness
        undecidable (runlog.is_alive -> None) -> the lease is kept."""
        self._foreign(EP, "gpt-oss-vllm", pid=1, script="")
        with self.assertRaises(SystemExit):
            el.acquire("qwen25-32b-awq", [EP])

    def test_idempotent(self):
        el.acquire("gpt-oss-vllm", [EP])
        el.acquire("gpt-oss-vllm", [EP])
        self.assertEqual(len(el.holders(EP)), 1)

    def test_multi_endpoint_alias_leases_all(self):
        el.acquire("gpt-oss", [EP, EP2])
        self.assertEqual(len(el.holders(EP)), 1)
        self.assertEqual(len(el.holders(EP2)), 1)

    def test_no_endpoints_leases_nothing(self):
        el.acquire("haiku", None)                 # claude-cli has no endpoint
        self.assertEqual(el.holders(EP), [])

    def test_release_frees_the_slot(self):
        el.acquire("gpt-oss-vllm", [EP])
        el.release_all()
        self.assertEqual(el.holders(EP), [])
        el.acquire("qwen25-32b-awq", [EP])        # must not raise

    def test_opt_out_env(self):
        pid, script = self._live_other_process()
        self._foreign(EP, "gpt-oss-vllm", pid=pid, script=script)
        os.environ["LABKIT_NO_ENDPOINT_LEASE"] = "1"
        el.acquire("qwen25-32b-awq", [EP])        # deliberate exception
        self.addCleanup(lambda: os.environ.pop("LABKIT_NO_ENDPOINT_LEASE", None))

    def test_corrupt_record_is_dropped(self):
        d = Path(self.tmp.name) / el._slug(EP)
        d.mkdir(parents=True, exist_ok=True)
        (d / "broken.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(el.holders(EP), [])

    def test_llm_complete_leases_implicitly(self):
        """The point of the design: the SCRIPT does not have to remember."""
        from labkit import llm
        pid, script = self._live_other_process()
        self._foreign(EP, "other-alias", pid=pid, script=script)
        llm._FROZEN["probe-alias"] = {"alias": "probe-alias", "backend": "openai",
                                      "model": "m", "endpoint": EP,
                                      "endpoints": [EP],
                                      "controls_temperature": True}
        self.addCleanup(lambda: llm._FROZEN.pop("probe-alias", None))
        with self.assertRaises(SystemExit):
            llm.complete("probe-alias", "hi", attempts=1)


if __name__ == "__main__":
    unittest.main()
