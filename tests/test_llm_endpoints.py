"""Named endpoints, round-robin and failover in lib/llm.py.

Why this file exists: a second ollama URL (second srun session) used to mean
either editing every model block or ad-hoc URL juggling in scripts. Now
[endpoints] names URLs once, a model may list several, and llm round-robins
across them with failover. Two servers are two INSTRUMENT INSTANCES (batch
invariance), so which server answered must be observable per call — these
tests pin the resolution rules AND the actually-requested URLs, in the spirit
of test_llm_chat_options.py: test what is sent, and where.
"""
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


TOML = """\
[endpoints]
a = "http://a.invalid:1111"
b = "http://b.invalid:2222"

[models.one]
backend = "ollama"
model = "m:latest"
endpoint = "a"

[models.both]
backend = "ollama"
model = "m:latest"
endpoints = ["a", "b"]

[models.literal]
backend = "ollama"
model = "m:latest"
endpoint = "http://raw.invalid:3333"

[models.dangling]
backend = "ollama"
model = "m:latest"
endpoint = "nosuch"
"""


class _Base(unittest.TestCase):
    def setUp(self):
        from labkit import llm
        self.llm = llm
        self._saved = (llm._find_models_toml, llm._ollama_digest,
                       llm.urllib.request.urlopen, llm.time.sleep,
                       dict(llm._FROZEN), dict(llm._RR), llm._RETRIES["n"])
        self.tmp = tempfile.TemporaryDirectory()
        toml_path = Path(self.tmp.name) / "models.toml"
        toml_path.write_text(TOML, encoding="utf-8")
        llm._find_models_toml = lambda: toml_path
        llm._ollama_digest = lambda ep, model, headers=None: "d34db33f4242"
        llm._FROZEN.clear()
        llm._RR.clear()
        llm.time.sleep = lambda s: None

    def tearDown(self):
        llm = self.llm
        (llm._find_models_toml, llm._ollama_digest,
         llm.urllib.request.urlopen, llm.time.sleep,
         frozen, rr, retries) = self._saved
        llm._FROZEN.clear(); llm._FROZEN.update(frozen)
        llm._RR.clear(); llm._RR.update(rr)
        llm._RETRIES["n"] = retries
        self.tmp.cleanup()


class TestResolveEndpoints(_Base):
    def test_named_endpoint_resolves_to_url(self):
        spec = self.llm.resolve("one")
        self.assertEqual(spec["endpoint"], "http://a.invalid:1111")
        self.assertEqual(spec["endpoints"], ["http://a.invalid:1111"])

    def test_endpoint_list_resolves_and_first_is_legacy_endpoint(self):
        spec = self.llm.resolve("both")
        self.assertEqual(spec["endpoints"],
                         ["http://a.invalid:1111", "http://b.invalid:2222"])
        self.assertEqual(spec["endpoint"], "http://a.invalid:1111")

    def test_literal_url_passes_through(self):
        spec = self.llm.resolve("literal")
        self.assertEqual(spec["endpoint"], "http://raw.invalid:3333")

    def test_unknown_endpoint_name_raises_with_known_names(self):
        with self.assertRaises(KeyError) as ctx:
            self.llm.resolve("dangling")
        self.assertIn("nosuch", str(ctx.exception))
        self.assertIn("a", str(ctx.exception))


class TestDigestAggregation(unittest.TestCase):
    def test_agreement_yields_the_digest(self):
        from labkit import llm
        self.assertEqual(llm._aggregate_digests({"a": "x", "b": "x"}), "x")

    def test_unreachable_endpoints_do_not_hide_the_reachable_one(self):
        from labkit import llm
        self.assertEqual(llm._aggregate_digests({"a": "x", "b": "unavailable"}), "x")

    def test_disagreement_is_loud(self):
        from labkit import llm
        got = llm._aggregate_digests({"a": "x", "b": "y"})
        self.assertTrue(got.startswith("MISMATCH:"))
        self.assertIn("x", got); self.assertIn("y", got)

    def test_nothing_reachable_is_unavailable(self):
        from labkit import llm
        self.assertEqual(llm._aggregate_digests({"a": "unavailable"}), "unavailable")


class TestRoundRobinAndFailover(_Base):
    def _urls_of_calls(self, responses):
        """Run complete() len(responses) times; record each requested URL."""
        urls = []

        def fake_urlopen(req, timeout=None):
            urls.append(req.full_url)
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return _FakeResponse(r)

        self.llm.urllib.request.urlopen = fake_urlopen
        return urls

    def test_two_endpoints_round_robin(self):
        ok = {"message": {"content": "x"}}
        urls = self._urls_of_calls([ok, ok, ok])
        for _ in range(3):
            self.llm.complete("both", "p", attempts=1)
        self.assertEqual([u.split("/api")[0] for u in urls],
                         ["http://a.invalid:1111", "http://b.invalid:2222",
                          "http://a.invalid:1111"])

    def test_failover_retries_on_the_other_endpoint(self):
        ok = {"message": {"content": "x"}}
        urls = self._urls_of_calls(
            [urllib.error.URLError("down"), ok])
        out = self.llm.complete("both", "p", attempts=2)
        self.assertEqual(out, "x")
        self.assertEqual([u.split("/api")[0] for u in urls],
                         ["http://a.invalid:1111", "http://b.invalid:2222"])

    def test_last_endpoint_names_the_server_that_answered(self):
        ok = {"message": {"content": "x"}}
        self._urls_of_calls([ok, ok])
        self.llm.complete("both", "p", attempts=1)
        self.assertEqual(self.llm.last_endpoint(), "http://a.invalid:1111")
        self.llm.complete("both", "p", attempts=1)
        self.assertEqual(self.llm.last_endpoint(), "http://b.invalid:2222")

    def test_single_endpoint_behaves_exactly_as_before(self):
        ok = {"message": {"content": "x"}}
        urls = self._urls_of_calls([ok, ok])
        self.llm.complete("one", "p", attempts=1)
        self.llm.complete("one", "p", attempts=1)
        self.assertEqual([u.split("/api")[0] for u in urls],
                         ["http://a.invalid:1111", "http://a.invalid:1111"])


class TestProvenanceBuilder(_Base):
    def test_model_digest_and_endpoint_callable(self):
        prov = self.llm.provenance("one")
        self.assertEqual(prov["model"], "m:latest@d34db33f4242")
        self.assertIs(prov["endpoint"], self.llm.last_endpoint)


if __name__ == "__main__":
    unittest.main()
