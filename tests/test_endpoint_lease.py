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

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.run import endpoint_lease as el  # noqa: E402

EP = "http://gammaweb07.medien.uni-weimar.de:11726"
EP2 = "http://gammaweb09.medien.uni-weimar.de:11490"


class TestEndpointLease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._prev_lease_dir = os.environ.get("LABKIT_LEASE_DIR", "")
        os.environ["LABKIT_LEASE_DIR"] = self.tmp.name
        os.environ.pop("LABKIT_NO_ENDPOINT_LEASE", None)
        el.release_all()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(el.release_all)
        # restore, never pop: the suite-wide isolation (conftest) must outlive
        # this test, or every later test leases into ~/.labkit again
        self.addCleanup(
            os.environ.__setitem__, "LABKIT_LEASE_DIR", self._prev_lease_dir
        )

    def _foreign(
        self,
        endpoint,
        alias,
        pid,
        script="01_measure.py",
        started="2026-09-08T17:00:00",
    ):
        """A lease record of ANOTHER process, written by hand."""
        d = Path(self.tmp.name) / el.endpoint_dir(endpoint)
        d.mkdir(parents=True, exist_ok=True)
        rec = {
            "alias": alias,
            "pid": pid,
            "script": script,
            "endpoint": endpoint,
            "started": started,
            "argv": script,
        }
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
        el.acquire("gpt-oss-vllm", [EP])  # must not raise
        self.assertTrue(any(h["pid"] == os.getpid() for h in el.holders(EP)))

    def test_other_endpoint_is_untouched(self):
        pid, script = self._live_other_process()
        self._foreign(EP, "gpt-oss-vllm", pid=pid, script=script)
        el.acquire("qwen", [EP2])  # different slot, no conflict
        self.assertEqual([h["alias"] for h in el.holders(EP2)], ["qwen"])

    def test_two_endpoints_one_slug_are_two_slots(self):
        """`a-b` and `a_b` shared one directory: one slot's lease refused
        the other (review 2026-10-14, reproduced)."""
        pid, script = self._live_other_process()
        self._foreign("http://host/a-b", "gpt-oss-vllm", pid=pid, script=script)
        el.acquire("qwen", ["http://host/a_b"])  # must not raise
        self.assertNotEqual(
            el.endpoint_dir("http://host/a-b"), el.endpoint_dir("http://host/a_b")
        )

    def test_one_endpoint_spelled_twice_is_one_slot(self):
        """Host case and a trailing slash name the same slot; two directories
        meant no interlock at all (on a case-sensitive filesystem — macOS
        hid the case half)."""
        self.assertEqual(
            el.endpoint_dir("http://Host:8000/v1/"),
            el.endpoint_dir("HTTP://host:8000/v1"),
        )
        pid, script = self._live_other_process()
        self._foreign("http://Host:8000/v1/", "gpt-oss-vllm", pid=pid, script=script)
        with self.assertRaises(SystemExit):
            el.acquire("qwen", ["HTTP://host:8000/v1"])

    def test_writers_in_the_same_second_are_ordered(self):
        """On the second alone both re-reads saw the other as no younger and
        both yielded; the token makes the order total — exactly one yields."""
        a = {"started": "2026-10-14T12:00:00", "token": "1" * 32}
        b = {"started": "2026-10-14T12:00:00", "token": "2" * 32}
        yields = [el._order(b) < el._order(a), el._order(a) < el._order(b)]
        self.assertEqual(yields.count(True), 1)
        self.assertLess(
            el._order({"started": "2026-10-14T11:59:59", "token": "f" * 32}),
            el._order(a),
        )  # the time decides first

    def test_dead_holder_does_not_block_forever(self):
        """A crashed run must not own the slot; PID 999999 is nobody."""
        self._foreign(EP, "gpt-oss-vllm", pid=999999)
        el.acquire("qwen25-32b-awq", [EP])
        self.assertEqual([h["alias"] for h in el.holders(EP)], ["qwen25-32b-awq"])

    def test_undecidable_holder_counts_as_alive(self):
        """Failure direction: a wrong refusal costs a message, a wrong
        admission costs the run. A record without a script name makes liveness
        undecidable (runs.is_alive -> None) -> the lease is kept."""
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
        el.acquire("haiku", None)  # claude-cli has no endpoint
        self.assertEqual(el.holders(EP), [])

    def test_release_frees_the_slot(self):
        el.acquire("gpt-oss-vllm", [EP])
        el.release_all()
        self.assertEqual(el.holders(EP), [])
        el.acquire("qwen25-32b-awq", [EP])  # must not raise

    def test_opt_out_env(self):
        pid, script = self._live_other_process()
        self._foreign(EP, "gpt-oss-vllm", pid=pid, script=script)
        os.environ["LABKIT_NO_ENDPOINT_LEASE"] = "1"
        el.acquire("qwen25-32b-awq", [EP])  # deliberate exception
        self.addCleanup(lambda: os.environ.pop("LABKIT_NO_ENDPOINT_LEASE", None))

    def _broken(self, age_s: float) -> Path:
        d = Path(self.tmp.name) / el.endpoint_dir(EP)
        d.mkdir(parents=True, exist_ok=True)
        f = d / "broken.json"
        f.write_text("{not json", encoding="utf-8")
        then = time.time() - age_s
        os.utime(f, (then, then))
        return f

    def test_fresh_unreadable_record_counts_as_busy(self):
        """Undecidable = busy: it may be another process' lease (review
        2026-10-06 — deleting on sight could drop a live holder)."""
        f = self._broken(age_s=1)
        with self.assertRaises(SystemExit):
            el.acquire("qwen25-32b-awq", [EP])
        self.assertTrue(f.exists())

    def test_old_unreadable_record_is_removed_loudly(self):
        f = self._broken(age_s=el.UNREADABLE_GRACE_S + 5)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(el.holders(EP), [])
        self.assertFalse(f.exists())
        self.assertIn("removing unreadable lease record", err.getvalue())

    def test_record_is_written_whole_and_lock_is_not_a_record(self):
        el.acquire("qwen25-32b-awq", [EP])
        d = Path(self.tmp.name) / el.endpoint_dir(EP)
        names = sorted(p.name for p in d.iterdir())
        self.assertEqual(names, [".lock", f"qwen25_32b_awq.{os.getpid()}.json"])
        json.loads((d / names[1]).read_text(encoding="utf-8"))

    def test_concurrent_acquires_of_two_aliases_admit_exactly_one(self):
        """Two processes race for one endpoint with different aliases."""
        code = (
            "import os,sys,time; sys.path.insert(0, %r);"
            "from labkit.run import endpoint_lease as el;"
            "time.sleep(max(0, float(sys.argv[2]) - time.time()));"
            "el.acquire(sys.argv[1], [%r]); time.sleep(1.5); print('ADMITTED')"
            % (str(Path(__file__).resolve().parents[1]), EP)
        )
        start = time.time() + 1.0
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", code, alias, str(start)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ},
            )
            for alias in ("alias-a", "alias-b")
        ]
        outs = [p.communicate(timeout=30)[0] for p in procs]
        self.assertEqual(sum("ADMITTED" in o for o in outs), 1, outs)

    def test_llm_complete_leases_implicitly(self):
        """The point of the design: the SCRIPT does not have to remember."""
        from labkit.run import llm

        pid, script = self._live_other_process()
        self._foreign(EP, "other-alias", pid=pid, script=script)
        llm._FROZEN["probe-alias"] = {
            "alias": "probe-alias",
            "backend": "openai",
            "model": "m",
            "endpoint": EP,
            "endpoints": [EP],
            "controls_temperature": True,
        }
        self.addCleanup(lambda: llm._FROZEN.pop("probe-alias", None))
        with self.assertRaises(SystemExit):
            llm.complete("probe-alias", "hi", attempts=1)


if __name__ == "__main__":
    unittest.main()
