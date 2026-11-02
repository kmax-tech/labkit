"""Fill the stamped count task's skeleton in the lab repo it runs from (the
current directory): SOURCE and INPUTS, expected_ids(), rows(),
evaluate_rows(), and the area test's hand-checked case — what a person
writes in step 2 of docs/examples/count-walkthrough.sh. Prints what it
filled; an AssertionError when the stamp no longer reads as expected."""

import re
from pathlib import Path

p = Path("experiments/01-docs-per-case/scripts/01_measure.py")
s = p.read_text(encoding="utf-8")
consts = {
    "SOURCE": 'REPO / "data" / "raw" / "cases.jsonl"',
    "INPUTS": 'REPO / "data" / "raw" / "inputs"',
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
        "        out.append({'case_id': item_id, 'n_docs': len(files)})\n"
        "    return out"
    ),
    'raise NotImplementedError("evaluate_rows(): compute the number(s) from items")': (
        "return {'mean_docs_per_case': sum(r['n_docs'] for r in items) / len(items)}"
    ),
}
for old, new in bodies.items():
    assert old in s, old
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
# the stamped test's case, checked by hand: two cases of 1 and 3 documents, a mean of 2.0
t = Path("tests/test_01_docs_per_case.py")
u = t.read_text(encoding="utf-8")
for stamped, filled in (
    ("KNOWN_IDS: list[str] = []", 'KNOWN_IDS: list[str] = ["c1", "c2"]'),
    (
        "KNOWN_ROWS: list[dict] = []",
        'KNOWN_ROWS: list[dict] = [{"case_id": "c1", "n_docs": 1}, {"case_id": "c2", "n_docs": 3}]',
    ),
    ("KNOWN_METRICS: dict = {}", 'KNOWN_METRICS: dict = {"mean_docs_per_case": 2.0}'),
):
    assert stamped in u, stamped
    u = u.replace(stamped, filled, 1)
t.write_text(u, encoding="utf-8")
print(
    "filled: SOURCE, INPUTS, expected_ids(), rows(), evaluate_rows(), the test's hand-checked case"
)
