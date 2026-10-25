"""Tests for what a computation over a model's outputs claims (`[model]
number_describes`, `annotation_validity`).

Why this exists: until the 0.22 rename a `compute` head with a `[model]`
table was refused — a model in the loop was taken to judge predictions. A
share of model labels judges none, but it may claim a property of the data
through the model as annotator ("30 % of the texts are causal"), and then
the annotator's suitability needs evidence (TODO, `compute` plan item 2).
labkit holds the claim and the evidence to each other and binds a protocol
reference; whether the evidence carries the annotation stays the audit's.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import (  # noqa: E402
    protocol_block,
    protocol_check,
    protocol_history,
    standard_contract,
)
from labkit.formats.gate import BLOCKER  # noqa: E402
from labkit.probes import usability  # noqa: E402
from labkit.tools import scaffold  # noqa: E402
from protocol_fixture import registration_of, head, run_record  # noqa: E402

VALIDATION_ID = "p-1111111111111111"
RUN = "2026-10-23T10-00-00_ab12"
DOI = "10.18653/v1/2023.acl-long.1"
#: what the validation run recorded (`models_resolved`): another model than
#: the fixture's models.toml names today
RECORDED = {
    "haiku": {
        "backend": "claude-cli",
        "model": "claude-haiku-4-5",
        "alias": "haiku",
        "controls_temperature": False,
    }
}


def _compute(claim: str) -> str:
    return head(repeat_cost="high", kind="compute", model="haiku", claim=claim)


def _gap(text: str) -> str | None:
    return protocol_check.kind_gap(text, protocol_block.head(text))


class Parse(unittest.TestCase):
    """The claim keys are exact keys with typed values: a typo is a loud
    error naming the field, never a silent absence."""

    def test_a_value_outside_the_two_is_refused(self):
        with self.assertRaisesRegex(protocol_block.BlockError, "model_outputs"):
            protocol_block.model(_compute('number_describes = "texts"'))

    def test_the_evidence_is_one_protocol_id_or_one_doi(self):
        for bad in (
            '{ protocol = "p-1", doi = "10.1000/x" }',
            '{ url = "https://x" }',
            '{ protocol = "p-123" }',
            '{ doi = "doi:10.1000/x" }',
            '"p-1111111111111111"',
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(protocol_block.BlockError):
                    protocol_block.model(
                        _compute(
                            'number_describes = "target_property"\n'
                            f"annotation_validity = {bad}"
                        )
                    )

    def test_a_stamped_placeholder_reads_as_unset_but_present(self):
        m = protocol_block.model(_compute(scaffold.COMPUTE_CLAIM))
        assert m is not None
        self.assertIsNone(m.number_describes)
        self.assertEqual(m.claim_keys, frozenset({"number_describes"}))

    def test_both_forms_of_evidence_parse(self):
        for raw, want in (
            (f'{{ protocol = "{VALIDATION_ID}" }}', ("protocol", VALIDATION_ID)),
            (f'{{ doi = "{DOI}" }}', ("doi", DOI)),
        ):
            m = protocol_block.model(
                _compute(
                    f'number_describes = "target_property"\nannotation_validity = {raw}'
                )
            )
            assert m is not None and m.annotation_validity is not None
            self.assertEqual(
                (m.annotation_validity.key, m.annotation_validity.value), want
            )


class KindGap(unittest.TestCase):
    """The claim and the evidence held to each other and to the kind."""

    def test_a_computation_with_a_model_says_what_its_number_describes(self):
        for claim in ("", scaffold.COMPUTE_CLAIM):
            with self.subTest(claim=claim):
                gap = _gap(_compute(claim))
                assert gap is not None
                self.assertIn("number_describes", gap)
                self.assertIn("model_outputs", gap)
                self.assertIn("target_property", gap)

    def test_the_model_outputs_owe_no_evidence(self):
        self.assertIsNone(_gap(_compute('number_describes = "model_outputs"')))

    def test_evidence_with_model_outputs_claims_more_than_the_number(self):
        gap = _gap(
            _compute(
                'number_describes = "model_outputs"\n'
                f'annotation_validity = {{ doi = "{DOI}" }}'
            )
        )
        assert gap is not None
        self.assertIn('"model_outputs"', gap)

    def test_a_property_of_the_data_owes_the_evidence(self):
        gap = _gap(_compute('number_describes = "target_property"'))
        assert gap is not None
        self.assertIn("annotation_validity", gap)

    def test_a_property_of_the_data_with_evidence_holds(self):
        for raw in (f'{{ protocol = "{VALIDATION_ID}" }}', f'{{ doi = "{DOI}" }}'):
            with self.subTest(raw=raw):
                self.assertIsNone(
                    _gap(
                        _compute(
                            'number_describes = "target_property"\n'
                            f"annotation_validity = {raw}"
                        )
                    )
                )

    def test_a_fit_or_an_apply_carries_no_claim_keys(self):
        for kind, claim in (
            ("apply", 'number_describes = "model_outputs"'),
            ("fit", f'annotation_validity = {{ doi = "{DOI}" }}'),
        ):
            with self.subTest(kind=kind):
                gap = _gap(
                    head(repeat_cost="high", kind=kind, model="haiku", claim=claim)
                )
                assert gap is not None
                self.assertIn(f'kind = "{kind}"', gap)
        self.assertIsNone(_gap(head(repeat_cost="high", kind="apply", model="haiku")))

    def test_a_computation_with_a_model_owes_no_bar(self):
        """compute judges no prediction, with or without a model: the
        registration adds the data profile, never the criterion."""
        self.assertEqual(
            standard_contract.registration_fields("compute", True),
            ("Question / hypothesis", "Data profile"),
        )
        bar = [f for f in protocol_check.FIELDS if f.low_cut == "lb"]
        self.assertTrue(bar)
        self.assertFalse(any(protocol_check.bar_owed(f, "compute") for f in bar))


class Binding(unittest.TestCase):
    """`{ protocol = … }` names one apply protocol of the repo with a
    declared result; a DOI is held to its form only."""

    def _bound(self, d: str, text: str) -> dict[str, list[Path]]:
        p = Path(d) / "PROTOCOL-validation.md"
        p.write_text(text, encoding="utf-8")
        return {VALIDATION_ID: [p]}

    def _findings(self, d: str, ids: dict[str, list[Path]], raw: str):
        path = Path(d) / "PROTOCOL-share.md"
        text = _compute(
            f'number_describes = "target_property"\nannotation_validity = {raw}'
        )
        path.write_text(text, encoding="utf-8")
        return protocol_history.check_annotation_validity(path, text, ids)

    def test_an_apply_with_a_declared_result_binds(self):
        with tempfile.TemporaryDirectory() as d:
            ids = self._bound(
                d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
            )
            found = self._findings(d, ids, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual(found, [])

    def test_a_computation_is_no_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            ids = self._bound(d, head(id=VALIDATION_ID, kind="compute", result=RUN))
            found = self._findings(d, ids, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual([f.grade for f in found], [BLOCKER])
        self.assertIn('kind = "compute"', found[0].text)

    def test_an_apply_without_its_number_is_no_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            ids = self._bound(d, head(id=VALIDATION_ID, kind="apply", model="haiku"))
            found = self._findings(d, ids, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual([f.grade for f in found], [BLOCKER])
        self.assertIn("declares no result", found[0].text)

    def test_an_id_of_no_protocol_here_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            found = self._findings(d, {}, f'{{ protocol = "{VALIDATION_ID}" }}')
        self.assertEqual([f.grade for f in found], [BLOCKER])
        self.assertIn("no protocol of this repo", found[0].text)

    def test_a_doi_is_bound_to_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self._findings(d, {}, f'{{ doi = "{DOI}" }}'), [])

    def test_the_repo_index_resolves_the_reference(self):
        """Through `repo_protocol_ids`, the one index of the repo's ids."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            self._bound(
                d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
            )
            share = Path(d) / "PROTOCOL-share.md"
            share.write_text(
                _compute(
                    'number_describes = "target_property"\n'
                    f'annotation_validity = {{ protocol = "{VALIDATION_ID}" }}'
                ),
                encoding="utf-8",
            )
            ids = protocol_block.repo_protocol_ids(share)
            self.assertIn(VALIDATION_ID, ids)
            found = protocol_history.check_annotation_validity(
                share, share.read_text(encoding="utf-8"), ids
            )
        self.assertEqual(found, [])


class Stamp(unittest.TestCase):
    """`labkit-init exp --kind compute --model` stamps the claim keys
    instead of refusing; the usability staging no longer rewrites it."""

    def test_a_computation_with_a_model_is_stamped_with_its_claim(self):
        tmpl = scaffold.template(scaffold.PROTOCOL_TEMPLATE.name)
        with tempfile.TemporaryDirectory() as d:
            text = scaffold.stamped_head(tmpl, Path(d), "x", "low", "compute", True)
        self.assertEqual(scaffold.asked_kind("compute"), "compute")
        self.assertIn(scaffold.COMPUTE_CLAIM, text)
        scaffold.check_stamped_head(text, "low", "compute", True)

    def test_an_apply_is_stamped_without_it(self):
        tmpl = scaffold.template(scaffold.PROTOCOL_TEMPLATE.name)
        with tempfile.TemporaryDirectory() as d:
            text = scaffold.stamped_head(tmpl, Path(d), "x", "low", "apply", True)
        m = protocol_block.model(text)
        assert m is not None
        self.assertEqual(m.claim_keys, frozenset())

    def test_the_staging_keeps_the_computation(self):
        self.assertEqual(
            usability.stamp_flags("count", None, True), ("low", "compute", True)
        )


if __name__ == "__main__":
    unittest.main()


class Evidence(unittest.TestCase):
    """The preflight audit is shown the bound validation itself — the apply
    protocol, its result, its model entry and its prompt — since a reference
    alone gives it nothing to judge (`audit.validity_evidence`)."""

    def _lab(self, d: str, validation: str | None) -> tuple[Path, str]:
        root = Path(d)
        (root / ".git").mkdir()
        (root / "models.toml").write_text(
            '[models.haiku]\nbackend = "claude-cli"\nmodel = "claude-haiku-5-5"\n',
            encoding="utf-8",
        )
        if validation is not None:
            val = root / "experiments" / "01-validation"
            (val / "scripts").mkdir(parents=True)
            (val / "PROTOCOL-validation.md").write_text(validation, encoding="utf-8")
            (val / "scripts" / "01_measure.py").write_text(
                'PROMPT = "Is this claim causal? Answer yes or no."\n', encoding="utf-8"
            )
            (val / "runs" / RUN).mkdir(parents=True)
            (val / "runs" / RUN / "metrics.json").write_text(
                '{"macro_f1": 0.87}\n', encoding="utf-8"
            )
            # the validation ran with another model than models.toml names today
            self._write_config(val, RECORDED)
        share = root / "experiments" / "02-share"
        share.mkdir(parents=True)
        return share, VALIDATION_ID

    @staticmethod
    def _write_config(val: Path, models_resolved: dict) -> None:
        (val / "runs" / RUN / "config.json").write_text(
            json.dumps(run_record(models_resolved=models_resolved)), encoding="utf-8"
        )

    def _evidence(self, share: Path, claim: str) -> str:
        from labkit.gates import audit

        text = _compute(claim)
        (share / "PROTOCOL-share.md").write_text(text, encoding="utf-8")
        return "\n".join(
            f"===== {label} =====\n{body}"
            for label, body in audit.validity_evidence(share, text)
        )

    def test_a_bound_apply_is_shown_with_result_model_and_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            share, pid = self._lab(
                d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
            )
            shown = self._evidence(
                share,
                'number_describes = "target_property"\n'
                f'annotation_validity = {{ protocol = "{pid}" }}',
            )
        self.assertIn("PROTOCOL-validation.md =====", shown)
        self.assertIn(f'id = "{VALIDATION_ID}"', shown)
        self.assertIn(f"runs/{RUN}/metrics.json =====", shown)
        self.assertIn('"macro_f1": 0.87', shown)
        self.assertIn("Is this claim causal?", shown)

    def test_the_model_shown_is_the_one_the_validation_ran_with(self):
        """The run record names the model that answered; today's models.toml
        may name another, and is shown only as such (review 2026-10-23,
        finding 4)."""
        with tempfile.TemporaryDirectory() as d:
            share, pid = self._lab(
                d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
            )
            shown = self._evidence(
                share,
                'number_describes = "target_property"\n'
                f'annotation_validity = {{ protocol = "{pid}" }}',
            )
        recorded, current = shown.split("===== EVIDENCE: current configuration")
        self.assertIn(f"recorded by run {RUN}", recorded)
        self.assertIn('"model": "claude-haiku-4-5"', recorded)
        self.assertNotIn("claude-haiku-5-5", recorded)
        self.assertIn("not necessarily what the validation ran with", current)
        self.assertIn('model = "claude-haiku-5-5"', current)

    def test_a_run_that_recorded_no_model_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            share, pid = self._lab(
                d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
            )
            self._write_config(Path(d) / "experiments" / "01-validation", {})
            shown = self._evidence(
                share,
                'number_describes = "target_property"\n'
                f'annotation_validity = {{ protocol = "{pid}" }}',
            )
        self.assertIn("recorded no model", shown)

    def test_an_unbound_reference_says_so_and_shows_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            share, pid = self._lab(
                d, head(id=VALIDATION_ID, kind="compute", result=RUN)
            )
            shown = self._evidence(
                share,
                'number_describes = "target_property"\n'
                f'annotation_validity = {{ protocol = "{pid}" }}',
            )
        self.assertIn("NOT BOUND", shown)
        self.assertIn('kind = "compute"', shown)
        self.assertNotIn("FILE:", shown)

    def test_a_doi_is_shown_as_checked_for_form_only(self):
        with tempfile.TemporaryDirectory() as d:
            share, _ = self._lab(d, None)
            shown = self._evidence(
                share,
                f'number_describes = "target_property"\nannotation_validity = {{ doi = "{DOI}" }}',
            )
        self.assertIn(DOI, shown)
        self.assertIn("form only", shown)

    def test_other_protocols_get_no_evidence_piece(self):
        from labkit.gates import audit

        with tempfile.TemporaryDirectory() as d:
            share, _ = self._lab(d, None)
            for text in (
                _compute('number_describes = "model_outputs"'),
                head(repeat_cost="high", kind="compute"),
                head(repeat_cost="high", kind="apply", model="haiku"),
            ):
                with self.subTest(text=text[-120:]):
                    self.assertEqual(audit.validity_evidence(share, text), ())


class StaleEvidence(Evidence):
    """The audit record's stamp covers the evidence the audit was shown
    (`scope_sha.validation_basis`): when the bound validation changes, the
    old record no longer covers the area, and the refusal says the stamp
    covers the bound validation. A DOI binds only its string."""

    REF = (
        'number_describes = "target_property"\n'
        f'annotation_validity = {{ protocol = "{VALIDATION_ID}" }}'
    )

    def _area(self, d: str, ref: str = REF) -> tuple[Path, str, Path]:
        share, _ = self._lab(
            d, head(id=VALIDATION_ID, kind="apply", model="haiku", result=RUN)
        )
        (share / "scripts").mkdir()
        (share / "scripts" / "01_measure.py").write_text("N = 1\n", encoding="utf-8")
        text = _compute(ref)
        (share / "PROTOCOL-share.md").write_text(text, encoding="utf-8")
        return share, text, Path(d) / "experiments" / "01-validation"

    def _record(self, share: Path, text: str) -> str:
        from labkit.formats import findings, promises, scope_sha

        sha = scope_sha.area_stamp(share)[0]
        return findings.write(
            share,
            "preflight",
            "opus",
            sha,
            promises.block_stamp(text),
            (0, 0, 0),
            [],
            registration=registration_of(share),
        ).name

    def _gap(self, share: Path, name: str, text: str) -> str | None:
        from labkit.formats import findings

        return findings.audit_record_gap(share, name, text)

    def test_the_record_covers_the_area_while_nothing_changed(self):
        with tempfile.TemporaryDirectory() as d:
            share, text, _ = self._area(d)
            name = self._record(share, text)
            self.assertIsNone(self._gap(share, name, text))

    def test_a_changed_validation_stales_the_record(self):
        edits = {
            "the bound protocol": lambda v, root: (
                (v / "PROTOCOL-validation.md")
                .open("a", encoding="utf-8")
                .write("\nA line added after the audit.\n")
            ),
            "its result": lambda v, root: (
                v / "runs" / RUN / "metrics.json"
            ).write_text('{"macro_f1": 0.41}\n', encoding="utf-8"),
            "its prompt": lambda v, root: (v / "scripts" / "01_measure.py").write_text(
                'PROMPT = "Is this claim causal? Say yes."\n', encoding="utf-8"
            ),
            "its recorded model": lambda v, root: self._write_config(
                v, {"haiku": dict(RECORDED["haiku"], model="claude-opus-5-5")}
            ),
        }
        for what, edit in edits.items():
            with self.subTest(what=what), tempfile.TemporaryDirectory() as d:
                share, text, val = self._area(d)
                name = self._record(share, text)
                edit(val, Path(d))
                gap = self._gap(share, name, text)
                self.assertIsNotNone(gap)
                self.assertIn("covers the bound validation too", gap or "")
                self.assertIn(
                    "experiments/01-validation/PROTOCOL-validation.md", gap or ""
                )

    def test_todays_models_toml_leaves_the_record_standing(self):
        """What the validation ran with is its run record; models.toml may
        change after it without changing what was validated."""
        with tempfile.TemporaryDirectory() as d:
            share, text, _ = self._area(d)
            name = self._record(share, text)
            (Path(d) / "models.toml").write_text(
                '[models.haiku]\nbackend = "claude-cli"\nmodel = "claude-haiku-6"\n',
                encoding="utf-8",
            )
            self.assertIsNone(self._gap(share, name, text))

    def test_a_doi_binds_its_string_only(self):
        from labkit.formats import scope_sha

        ref = f'number_describes = "target_property"\nannotation_validity = {{ doi = "{DOI}" }}'
        with tempfile.TemporaryDirectory() as d:
            share, text, val = self._area(d, ref)
            before = scope_sha.area_stamp(share)[0]
            # the bound protocol is nobody's evidence here: editing it moves nothing
            (val / "PROTOCOL-validation.md").open("a", encoding="utf-8").write("\nx\n")
            self.assertEqual(scope_sha.area_stamp(share)[0], before)
            self.assertIn("its string only", scope_sha.validation_note(share))
            other = text.replace(DOI, "10.18653/v1/2023.acl-long.2")
            (share / "PROTOCOL-share.md").write_text(other, encoding="utf-8")
            self.assertNotEqual(scope_sha.area_stamp(share)[0], before)

    def test_an_area_without_the_evidence_keeps_its_stamp(self):
        from labkit.formats import scope_sha

        with tempfile.TemporaryDirectory() as d:
            share, _, _ = self._area(d)
            for text in (
                _compute('number_describes = "model_outputs"'),
                head(repeat_cost="high", kind="compute"),
            ):
                with self.subTest(text=text[-80:]):
                    (share / "PROTOCOL-share.md").write_text(text, encoding="utf-8")
                    snap = scope_sha.area_snapshot(share)
                    self.assertEqual(scope_sha.validation_basis(share), ([], ()))
                    self.assertEqual(snap.validation, ())
                    self.assertEqual(scope_sha.validation_note(share), "")


class AffectedByEvidence(StaleEvidence):
    """A change to the bound validation stales the computation's audit
    (`StaleEvidence`), so the automatic choice of what to recheck — the
    stop, the commit's gate, report-check (`scope_sha.areas_touched`) —
    picks the computation's area too, not only the validation's (review
    2026-10-23, finding 3)."""

    def _changed(self, val: Path, root: Path) -> dict[str, Path]:
        return {
            "the bound protocol": val / "PROTOCOL-validation.md",
            "its result": val / "runs" / RUN / "metrics.json",
            "its prompt": val / "scripts" / "01_measure.py",
            "its recorded model": val / "runs" / RUN / "config.json",
        }

    def test_a_changed_validation_touches_the_area_that_rests_on_it(self):
        from labkit.formats import scope_sha

        with tempfile.TemporaryDirectory() as d:
            share, _, val = self._area(d)
            root = Path(d)
            for what, path in self._changed(val, root).items():
                with self.subTest(what=what):
                    touched = scope_sha.areas_touched([path], root)
                    self.assertIn(share.resolve(), [a.resolve() for a in touched])

    def test_a_doi_ties_the_area_to_no_file(self):
        from labkit.formats import scope_sha

        ref = f'number_describes = "target_property"\nannotation_validity = {{ doi = "{DOI}" }}'
        with tempfile.TemporaryDirectory() as d:
            share, _, val = self._area(d, ref)
            root = Path(d)
            for what, path in self._changed(val, root).items():
                with self.subTest(what=what):
                    touched = scope_sha.areas_touched([path], root)
                    self.assertNotIn(share.resolve(), [a.resolve() for a in touched])

    def test_the_staged_gate_reopens_the_computation(self):
        import subprocess

        from labkit.gates import report_check

        def git(root: Path, *args: str) -> None:
            subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)

        with tempfile.TemporaryDirectory() as d:
            share, _, val = self._area(d)
            root = Path(d)
            (root / ".git").rmdir()
            git(root, "init", "-q")
            git(root, "add", ".")
            git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i")
            metrics = val / "runs" / RUN / "metrics.json"
            metrics.write_text('{"macro_f1": 0.41}\n', encoding="utf-8")
            git(root, "add", ".")
            picked = report_check.affected_protocols([metrics], root, staged=True)
            self.assertIn(
                (share / "PROTOCOL-share.md").resolve(), [p.resolve() for p in picked]
            )
