"""Edit one pilot copy of t3's work/ into case B, C or D (A stays as delivered).

    python3 -I edit_case.py <case> <work dir>

B: the leaking feature set back (poisson_ratio added).
C: features from formula and structure only, the diagnostic in the run's metrics.json.
D: the code of C without the diagnostic.
Removes the prepared file and the measured output so the image writes them anew.
"""

import sys
from pathlib import Path

case, work = sys.argv[1], Path(sys.argv[2])
area = work / "experiments" / "01-bulk-modulus"
prep = area / "scripts" / "00_prepare.py"
meas = area / "scripts" / "01_measure.py"


def swap(path: Path, old: str, new: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise SystemExit(f"{path.name}: {old[:60]!r} stands {text.count(old)}x, want {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


OLD_FEATURES = """        features = [
            float(row['elastic_anisotropy']),
            float(row['G_VRH']),
            float(row['space_group']),
        ]"""

if case == "B":
    swap(prep, OLD_FEATURES, """        features = [
            float(row['elastic_anisotropy']),
            float(row['G_VRH']),
            float(row['space_group']),
            float(row['poisson_ratio']),
        ]""", count=2)
    swap(prep, '"list of three numeric features: [elastic_anisotropy, G_VRH, space_group]"',
         '"list of four numeric features: [elastic_anisotropy, G_VRH, space_group, poisson_ratio]"')
elif case in ("C", "D"):
    swap(prep, OLD_FEATURES, "        features = structure_features(row)", count=2)
    swap(prep, '"list of three numeric features: [elastic_anisotropy, G_VRH, space_group]"',
         '"list of four numeric features: FEATURE_COLUMNS, each from formula or structure (FEATURE_SOURCES)"')
    swap(prep, 'OUT = AREA / "data" / "prepared" / "compounds_v1.jsonl"\n', '''OUT = AREA / "data" / "prepared" / "compounds_v1.jsonl"

#: the features, in order — composition and crystal structure only. The
#: elastic columns G_VRH, poisson_ratio and elastic_anisotropy come from the
#: same computed elastic tensor as the target K_VRH and are never read.
FEATURE_COLUMNS = ["space_group", "n_sites", "volume_per_atom", "n_elements"]
FEATURE_SOURCES = {
    "space_group": "column space_group",
    "n_sites": "structure text: the N of `Sites (N)`",
    "volume_per_atom": "structure text: cell volume from `abc` and `angles`, over n_sites",
    "n_elements": "structure text: elements in `Reduced Formula`",
}
EXCLUDED_COLUMNS = ["G_VRH", "poisson_ratio", "elastic_anisotropy"]


def structure_features(row) -> list[float]:
    """FEATURE_COLUMNS of one CSV row, from space_group and the structure text."""
    import math
    import re

    text = row["structure"]
    n_sites = int(re.search(r"Sites \\((\\d+)\\)", text).group(1))
    a, b, c = (float(v) for v in re.search(r"abc\\s*:\\s*(\\S+)\\s+(\\S+)\\s+(\\S+)", text).groups())
    al, be, ga = (math.radians(float(v)) for v in
                  re.search(r"angles\\s*:\\s*(\\S+)\\s+(\\S+)\\s+(\\S+)", text).groups())
    volume = a * b * c * math.sqrt(1 - math.cos(al) ** 2 - math.cos(be) ** 2 - math.cos(ga) ** 2
                                   + 2 * math.cos(al) * math.cos(be) * math.cos(ga))
    formula = re.search(r"Reduced Formula:\\s*(\\S+)", text).group(1)
    n_elements = len(set(re.findall(r"[A-Z][a-z]?", formula)))
    return [float(row["space_group"]), float(n_sites), volume / n_sites, float(n_elements)]
''')
    if case == "C":
        swap(meas, '''        evaluate(OUT, cfg, items, run)
        print(f"run: {run.run_id}''', '''        evaluate(OUT, cfg, items, run)
        run.metrics(**leak_diagnostic())
        print(f"run: {run.run_id}''')
        swap(meas, "\ndef main() -> None:", '''
def leak_diagnostic() -> dict:
    """What the features are and why the elastic columns are out: the
    feature columns with the source of each (00_prepare.FEATURE_SOURCES),
    the excluded columns, and R² of the closed-form identity
    K = 2G(1+nu)/(3(1-2nu)) on the excluded G_VRH and poisson_ratio over the
    labelled train rows — near 1 means the pair restates the target."""
    import csv
    import importlib.util

    spec = importlib.util.spec_from_file_location("prepare_00", HERE / "00_prepare.py")
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    rows = list(csv.DictReader(open(prep.SOURCE_TRAIN, encoding="utf-8")))
    k = [float(r["K_VRH"]) for r in rows]
    pred = [2 * float(r["G_VRH"]) * (1 + float(r["poisson_ratio"]))
            / (3 * (1 - 2 * float(r["poisson_ratio"]))) for r in rows]
    mean = sum(k) / len(k)
    r2 = 1 - sum((a - p) ** 2 for a, p in zip(k, pred)) / sum((a - mean) ** 2 for a in k)
    return {"feature_columns": prep.FEATURE_COLUMNS,
            "feature_sources": prep.FEATURE_SOURCES,
            "excluded_columns": prep.EXCLUDED_COLUMNS,
            "identity_r2_excluded_pair": round(r2, 7),
            "identity_rows": len(k)}


def main() -> None:''')
else:
    raise SystemExit(f"case {case!r}: one of B, C, D")

for stale in (area / "data" / "prepared" / "compounds_v1.jsonl",
              area / "output" / "bulk-modulus.jsonl"):
    if stale.exists():
        stale.chmod(0o644)
        stale.unlink()
print(f"case {case}: edited {work}")
