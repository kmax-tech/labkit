"""Case D2 of pilot 2: case D without the named switch.

    python3 -I edit_case_d2.py <work dir of a copy of case D>

Removes REPORT_SOURCES and the branch that read it: the measuring code
computes the feature sources for [A3] and writes only a3_pass, as code
that never wrote the check would. Removes the prepared file and the
measured output so the image writes them anew.
"""
import sys
from pathlib import Path

area = Path(sys.argv[1]) / "experiments" / "01-bulk-modulus"
meas = area / "scripts" / "01_measure.py"
text = meas.read_text(encoding="utf-8")
for old in ("#: whether metrics.json carries the feature sources (the check of audit 08-17 #1)\nREPORT_SOURCES = False\n",
            '    if REPORT_SOURCES:\n        metrics["feature_sources"] = rule["feature_sources"]\n'):
    if text.count(old) != 1:
        raise SystemExit(f"01_measure.py: {old[:50]!r} stands {text.count(old)}x")
    text = text.replace(old, "")
if "REPORT_SOURCES" in text:
    raise SystemExit("01_measure.py: REPORT_SOURCES still named")
meas.write_text(text, encoding="utf-8")
for stale in (area / "data" / "prepared" / "compounds_v1.jsonl", area / "output" / "bulk-modulus.jsonl"):
    if stale.exists():
        stale.chmod(0o644)
        stale.unlink()
print("case D2 built")
