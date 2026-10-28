#!/bin/sh
# count-walkthrough.sh — one kept number, end to end, in a fresh lab repo.
#
#     docs/examples/count-walkthrough.sh <empty or missing directory> [VENV]
#
# Walks `docs/workflow.md` on the stamped count task (the mean number of
# documents per case over twelve cases; the truth is 3.5): registration,
# run, finalize, the analysis record, adoption, the report block, the gate
# — then retypes a generated number and shows which check refuses it.
# VENV is a virtualenv with this labkit installed (default: the one whose
# `usability` is on PATH). Every command it runs is one a person runs;
# the one exception is marked STAND-IN. Exit 0 when the walk ends where
# the text says it ends; `tests/test_workflow_example.py` runs it.
set -eu

DIR=${1:?usage: count-walkthrough.sh <directory> [VENV]}
VENV=${2:-$(dirname "$(dirname "$(command -v usability)")")}
LAB=$DIR/lab
AREA=experiments/01-docs-per-case
P=$AREA/PROTOCOL-docs-per-case.md

say() { printf '\n== %s\n' "$*"; }
run() { printf '$ %s\n' "$*"; "$@"; }

say "1. a lab repo with the count task stamped (what labkit-init lab + labkit-init exp --repeat-cost low --kind compute leave)"
mkdir -p "$DIR"
run "$VENV/bin/usability" stage "$LAB" --task count --venv "$VENV" >/dev/null
cd "$LAB"
V=.venv/bin
run git log --oneline

say "2. the measurement: the skeleton's TODOs filled (four constants, three functions)"
"$V/python" - <<'EOF'
import re
from pathlib import Path

p = Path("experiments/01-docs-per-case/scripts/01_measure.py")
s = p.read_text(encoding="utf-8")
consts = {
    "SOURCE": 'REPO / "data" / "raw" / "cases.jsonl"',
    "INPUTS": 'REPO / "data" / "raw" / "inputs"',
    "COUNT_FIELD": '"n_docs"',
    "METRIC_KEY": '"mean_docs_per_case"',
}
for name, value in consts.items():
    s, n = re.subn(rf"^{name} = .*$", f"{name} = {value}", s, count=1, flags=re.M)
    assert n == 1, name
bodies = {
    'raise NotImplementedError("expected_ids(): the ids SOURCE lists")': (
        "return [json.loads(line)['case_id']\n"
        "            for line in SOURCE.read_text(encoding='utf-8').splitlines() if line.strip()]"
    ),
    'raise NotImplementedError("rows(): one dict per id, fail loud on a missing one")': (
        "records = {json.loads(line)['case_id']: json.loads(line)\n"
        "               for line in SOURCE.read_text(encoding='utf-8').splitlines() if line.strip()}\n"
        "    out = []\n"
        "    for item_id in ids:\n"
        "        files = visible(input_dir(records[item_id], item_id))\n"
        "        if not files:\n"
        "            raise ValueError(f'rows(): {item_id} has no documents')\n"
        "        out.append({'case_id': item_id, COUNT_FIELD: len(files)})\n"
        "    return out"
    ),
    'raise NotImplementedError("evaluate_rows(): compute the number(s) from items")': (
        "return {METRIC_KEY: sum(r[COUNT_FIELD] for r in items) / len(items)}"
    ),
}
for old, new in bodies.items():
    assert old in s, old
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("filled: SOURCE, INPUTS, COUNT_FIELD, METRIC_KEY, expected_ids(), rows(), evaluate_rows()")
EOF
run "$V/code-check" "$AREA"

say "3. the registration, written before the run (the fields the low cut owes: protocol-check --contract)"
run "$V/protocol-fill" "$P" type=exploratory \
    "Terms of this protocol=n/a — no coinage" \
    "Question / hypothesis=What is the mean number of input documents per case over the cases in data/raw/cases.jsonl?" \
    "Data / scope=data/raw/cases.jsonl (12 cases); a case's documents are the files under data/raw/inputs/<case_id>/" \
    "Exclusions / filters=hidden files and nested directories are not counted; no case is dropped" \
    "Unit=one document = one visible regular file directly in a case's directory"
run "$V/protocol-check" "$P"
echo "   (every commit below runs the probe's pre-commit hook: protocol-check on staged protocols, report-check on declared results)"
run git add "$AREA"
run git commit -q -m "Register docs-per-case: the question, scope and unit; the count filled" -- "$AREA"

say "4. the run — runlog refuses it unless the registration is written; at low repeat cost it is the instrument check too"
run "$V/python" "$AREA/scripts/01_measure.py"
RUN=$(ls "$AREA/runs" | tail -1)
run git add "$AREA"
run git commit -q -m "Run $RUN: output and run record" -- "$AREA"

say "5. finalize — the answering run chosen, its record held, source and output tracked"
run "$V/finalize" "$AREA"

say "6. the analysis audit — the lane's one audit, decided before the number leaves"
echo "   in a lab: $V/labkit-audit $AREA --mode analysis   (one model call; then --decide each finding)"
echo "   STAND-IN here: the record a clean audit writes, so the walk needs no model; its shape is labkit's own"
"$V/python" - <<'EOF'
from pathlib import Path
from labkit.checks import audit_binding
from labkit.formats import findings, promises, protocol_block, protocol_check, scope_sha

area = Path("experiments/01-docs-per-case")
run = sorted((area / "runs").iterdir())[-1]
text = (area / "PROTOCOL-docs-per-case.md").read_text(encoding="utf-8")
path = findings.write(
    area, "analysis", "walkthrough-stand-in",
    scope_sha.area_stamp(area)[0], promises.block_stamp(text), (0, 0, 0), [],
    registration=protocol_check.registration_stamp(text),
    run_id=run.name,
    shown_sha=audit_binding.run_shown(area, run, "", protocol_block.declared_run(text)).sha,
)
print(f"wrote {path} — code {scope_sha.area_stamp(area)[0]}, run {run.name}, no findings")
EOF

say "7. the Conclusion (the author's sentence, written first), then the adoption — the number written back from metrics.json, never retyped; report-check runs on the written protocol"
run "$V/protocol-fill" "$P" "Conclusion=The twelve cases hold 3.5 documents each on average; no file was skipped by the visibility filter."
run "$V/protocol-fill" "$P" --from-run "$RUN"
grep -n "Recorded results\|Conclusion\|^run = " "$P"

say "8. the report block — the declared result in a note outside the protocol"
printf '# Report\n\nThe cases carry a few documents each.\n' > REPORT.md
run "$V/protocol-fill" "$P" --into REPORT.md
cat REPORT.md

say "9. the gate at the stop and the commit, on the report and the protocol"
run "$V/report-check" --if-reported REPORT.md "$P"
run git add "$AREA" REPORT.md
run git commit -q -m "Adopt $RUN as the result; the report block" -- "$AREA" REPORT.md

say "10. a generated number retyped — which check refuses it"
echo "   retyping 3.5 as 3.6 inside REPORT.md's result block"
sed -i.bak 's/mean_docs_per_case = 3\.5/mean_docs_per_case = 3.6/' REPORT.md && rm REPORT.md.bak
printf '$ %s\n' "$V/report-check --if-reported REPORT.md"
if "$V/report-check" --if-reported REPORT.md; then
    echo "UNEXPECTED: the retyped block passed"; exit 1
fi
echo "   refused, as it must be: the block differs from what the protocol renders"
run git checkout -q REPORT.md
echo "   retyping 3.5 as 3.6 in the protocol's Recorded results line"
sed -i.bak 's/mean_docs_per_case = 3\.5 (run/mean_docs_per_case = 3.6 (run/' "$P" && rm "$P.bak"
printf '$ %s\n' "$V/report-check $AREA"
if "$V/report-check" "$AREA"; then
    echo "UNEXPECTED: the retyped Recorded results passed"; exit 1
fi
echo "   refused, as it must be: the Recorded results line differs from the run's metrics.json"
run git checkout -q "$P"
run "$V/report-check" --if-reported REPORT.md "$P"

say "done — the number 3.5 is kept under $RUN, declared in $P, shown in REPORT.md, and held by report-check"
