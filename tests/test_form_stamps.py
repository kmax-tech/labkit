"""The 24 forms `protocol_stamp` writes match the kept files byte for byte.

Three kinds, two repeat costs, a model named or not, the short form or the
report form (`form_stamps_fixture`). A change in the field selection or the
template that alters any form fails here; a deliberate one rewrites the
files (`form_stamps_fixture.py --write`). What `--report` on an existing
area and `--change-kind` write is held in `test_form_stamp_paths.py`.
"""

from __future__ import annotations

import tempfile
import unittest

from form_stamps_fixture import lab, stamp_cases, stamp_file, stamped


class StampedForms(unittest.TestCase):
    def test_every_form_matches_its_kept_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = lab(tmp)
            for cost, kind, model, report in stamp_cases():
                with self.subTest(cost=cost, kind=kind, model=model, report=report):
                    kept = stamp_file(cost, kind, model, report)
                    self.assertEqual(
                        stamped(root, cost, kind, model, report),
                        kept.read_text(encoding="utf-8"),
                        f"differs from {kept.name}",
                    )


if __name__ == "__main__":
    unittest.main()
