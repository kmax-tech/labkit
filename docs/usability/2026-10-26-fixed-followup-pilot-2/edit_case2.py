"""Build one case of the second fixed-followup pilot on a copy of t3's work/.

    python3 -I edit_case2.py <case> <work dir>

Common to every case (the new trial state): the protocol registers the
task's feature rule as [A3] (key a3_pass, the excluded columns as a
constant) and a question that matches the task; 00_prepare.py builds the
feature array from ONE table FEATURES (name, source columns, extractor);
01_measure.py reports feature_sources from that same table and a3_pass by
the registered rule, and withholds [C1] when [A3] fails. Record 08-17 #1
gets the check the pilot pre-registers (`feature_sources`).

A: the delivered features (elastic_anisotropy, G_VRH, space_group).
B: the leaking set (A plus poisson_ratio).
C: formula and structure features; feature_sources in metrics.json.
D: the code of C without feature_sources in metrics.json.
"""

import re
import sys
from pathlib import Path

case, work = sys.argv[1], Path(sys.argv[2])
area = work / "experiments" / "01-bulk-modulus"
proto = area / "PROTOCOL-bulk-modulus.md"
prep = area / "scripts" / "00_prepare.py"
meas = area / "scripts" / "01_measure.py"
record = area / "audits" / "2026-10-26T08-17-analysis.toml"


def swap(path: Path, old: str, new: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise SystemExit(f"{path.name}: {old[:70]!r} stands {text.count(old)}x, want {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# --- the protocol: the task's feature rule as [A3], a question that matches it
swap(proto, "- **Terms of this protocol:** RandomForestRegressor with n_estimators=500; features are elastic_anisotropy, G_VRH, space_group (poisson_ratio excluded due to target leakage: K_VRH = 2G(1+ν)/(3(1−2ν))); target is K_VRH",
     "- **Terms of this protocol:** RandomForestRegressor with n_estimators=500; the features are the table FEATURES in scripts/00_prepare.py, each with the source columns it is computed from; target is K_VRH")
swap(proto, "Can a random forest trained on composition and elastic properties predict bulk modulus",
     "Can a random forest trained on features from the material's composition and crystal structure (the task, instruction.md) predict bulk modulus")
swap(proto, "- **Admissibility condition:** [A1] at most 0 labelled items without a prediction",
     "- **Admissibility condition:** [A1] at most 0 labelled items without a prediction; [A3] no feature is computed from a column of the elastic tensor K_VRH comes from (G_VRH, poisson_ratio, elastic_anisotropy)")
swap(proto, '''constants = { null_band = 0.15 }
```''', '''constants = { null_band = 0.15 }

[[promise]]
id = "A3"
key = "a3_pass"
sentence = "the feature rule: the task (instruction.md) asks for features generated from material compositions and crystal structures; G_VRH, poisson_ratio and elastic_anisotropy come from the same computed elastic tensor as the target K_VRH, so no feature may be computed from them — checked on the source columns every feature names in FEATURES"
scope = ["scripts/00_prepare.py", "scripts/01_measure.py"]
constants = { excluded_columns = "G_VRH,poisson_ratio,elastic_anisotropy" }
```''')

# --- 00_prepare.py: one FEATURES table builds the array
COLUMN = '''def column(name: str):
    """The extractor that reads one CSV column as a float."""
    return lambda row: float(row[name])


'''
STRUCTURE = '''def structure_numbers(row) -> dict:
    """n_sites, volume_per_atom and n_elements from the structure text."""
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
    return {"n_sites": float(n_sites), "volume_per_atom": volume / n_sites,
            "n_elements": float(len(set(re.findall(r"[A-Z][a-z]?", formula))))}


'''
TABLES = {
    "A": '''#: the features, in order: (name, the source columns it is computed from,
#: the extractor). The array of every item is built from this table and
#: 01_measure.py reports the sources from it — one table, no second list.
FEATURES = [
    ("elastic_anisotropy", ("elastic_anisotropy",), column("elastic_anisotropy")),
    ("G_VRH", ("G_VRH",), column("G_VRH")),
    ("space_group", ("space_group",), column("space_group")),
]
''',
    "B": '''#: the features, in order: (name, the source columns it is computed from,
#: the extractor). The array of every item is built from this table and
#: 01_measure.py reports the sources from it — one table, no second list.
FEATURES = [
    ("elastic_anisotropy", ("elastic_anisotropy",), column("elastic_anisotropy")),
    ("G_VRH", ("G_VRH",), column("G_VRH")),
    ("space_group", ("space_group",), column("space_group")),
    ("poisson_ratio", ("poisson_ratio",), column("poisson_ratio")),
]
''',
    "C": '''#: the features, in order: (name, the source columns it is computed from,
#: the extractor). The array of every item is built from this table and
#: 01_measure.py reports the sources from it — one table, no second list.
FEATURES = [
    ("space_group", ("space_group",), column("space_group")),
    ("n_sites", ("structure",), lambda row: structure_numbers(row)["n_sites"]),
    ("volume_per_atom", ("structure",), lambda row: structure_numbers(row)["volume_per_atom"]),
    ("n_elements", ("structure",), lambda row: structure_numbers(row)["n_elements"]),
]
''',
}
TABLES["D"] = TABLES["C"]
helpers = COLUMN + (STRUCTURE if case in ("C", "D") else "")
swap(prep, 'OUT = AREA / "data" / "prepared" / "compounds_v1.jsonl"\n',
     'OUT = AREA / "data" / "prepared" / "compounds_v1.jsonl"\n\n\n' + helpers + TABLES[case])
text = prep.read_text(encoding="utf-8")
feature_lists = re.findall(r"        features = \[\n(?:            .*\n)+?        \]", text)
if len(feature_lists) != 2:
    raise SystemExit(f"00_prepare.py: {len(feature_lists)} feature lists, want 2")
for block in feature_lists:
    text = text.replace(block, "        features = [extract(row) for _, _, extract in FEATURES]", 1)
text = re.sub(r"        # Features: .*\n(        # .*\n)*", "", text)
text = text.replace('"features": "list of three numeric features: [elastic_anisotropy, G_VRH, space_group]"',
                    '"features": "one number per entry of FEATURES, in its order"')
prep.write_text(text, encoding="utf-8")

# --- 01_measure.py: the registered rule, the sources from the same table
swap(meas, """    null_band: float            # [A2]""", """    excluded_columns: str       # [A3]: comma-separated source columns no feature may be computed from
    null_band: float            # [A2]""")
swap(meas, "def evaluate_rows(", '''def feature_table() -> list:
    """00_prepare.FEATURES — the one table the feature array is built from."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("prepare_00", HERE / "00_prepare.py")
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    return prep.FEATURES


def feature_rule(cfg: MeasureConfig) -> dict:
    """[A3] by the registered rule: the source columns of every feature in
    FEATURES against the excluded columns of the protocol."""
    excluded = {c.strip() for c in cfg.excluded_columns.split(",")}
    sources = {name: list(cols) for name, cols, _ in feature_table()}
    return {"feature_sources": sources,
            "a3_pass": not any(c in excluded for cols in sources.values() for c in cols)}


def evaluate_rows(''')
swap(meas, """    if not (metrics["a1_pass"] and metrics["a2_pass"]):""", """    rule = feature_rule(cfg)
    metrics["a3_pass"] = rule["a3_pass"]
    if REPORT_SOURCES:
        metrics["feature_sources"] = rule["feature_sources"]
    if not (metrics["a1_pass"] and metrics["a2_pass"] and metrics["a3_pass"]):""")
swap(meas, 'C1_VALUE_KEY = "c1_score"\n', 'C1_VALUE_KEY = "c1_score"\n'
     f'#: whether metrics.json carries the feature sources (the check of audit 08-17 #1)\n'
     f'REPORT_SOURCES = {case != "D"}\n')
swap(meas, """    for key in ("a1_pass", "a1_empty", "a2_score", "a2_chance", "a2_pass",
                "c1_score", "c1_threshold", "c1_pass"):""", """    for key in ("a1_pass", "a1_empty", "a2_score", "a2_chance", "a2_pass",
                "a3_pass", "c1_score", "c1_threshold", "c1_pass"):""")

# --- record 08-17 #1: the pre-registered check, kept in text and field
rec = record.read_text(encoding="utf-8")
m = re.search(r'(\[\[finding\]\]\ngrade = "BLOCKER"\ntext = ")(.*?)("\n)', rec)
if m is None or "check: feature_sources" in m.group(2):
    raise SystemExit("record: BLOCKER #1 not found, or already checked")
rec = rec[: m.end(2)] + " · check: feature_sources" + m.group(3) + 'check = "feature_sources"\n' + rec[m.end():]
record.write_text(rec, encoding="utf-8")

for stale in (area / "data" / "prepared" / "compounds_v1.jsonl", area / "output" / "bulk-modulus.jsonl"):
    if stale.exists():
        stale.chmod(0o644)
        stale.unlink()
print(f"case {case}: built in {work}")
