"""One home per question — held by grep, not by memory.

`docs/architecture.md` names the home of every recurring question and says
a second answer is drift. Three audits (2026-10-06, 2026-10-13,
2026-10-15) removed the same kinds of copies — a hand-spelled sha256, a
`git` run outside `repo`, a `PROTOCOL-*.md` scan, the id letters, a fence
regex — and they came back within two weeks each time. This test greps
`labkit/*.py` for the shapes a copy takes; a match outside the home fails,
naming file and line. A line that must stay says why in a comment on it or
directly above it that names the home it is not after `home:`.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "labkit"
#: rules that also hold in the stamped script templates — a stamped area reads
#: its tier off the contract like labkit does (review 2026-10-19)
IN_TEMPLATES = {"a tier rule read off the head", "an adopt command spelled by hand"}

#: (what, the shape of a copy, the module(s) where it belongs)
RULES: list[tuple[str, str, set[str]]] = [
    ("sha256 by hand", r"hashlib\.", {"scope_sha"}),
    (
        "git outside repo.git_run",
        r"subprocess\.\w+\(\s*\[\s*\"git\"",
        {"repo"},
    ),
    ("a PROTOCOL-*.md scan", r"r?glob\(\s*\"PROTOCOL-", {"repo"}),
    ("pip's name normalisation", r"\.lower\(\)\.replace\(\"_\", \"-\"\)", {"repo"}),
    ("a fence regex", r"re\.compile\([^\n]*(`\{3|```|~\{3)", {"protocol_block"}),
    ("a fence toggled by hand", r"startswith\(\(?\"(```|~~~)", {"protocol_block"}),
    ("the id letters", r"\[(?:[cab]{2,3}|[CAB]{2,3})\]|\^a\\d", {"promises"}),
    ("the area name NN-slug", r"\^\(\\d\+\)-", {"repo"}),
    ("a temp-and-rename write", r"os\.replace\(", {"files"}),
    ("the run-id shape", r"\\d\{4\}-\\d\{2\}-\\d\{2\}T", {"runs"}),
    # "relative to the repo, else absolute" stood about 18 times (audit
    # 2026-10-18); the conditional form is held here, a try/except copy is not
    ("a path shown relative by hand", r"\.is_relative_to\(", {"repo", "runs"}),
    # the hook and the transcript cut a shell line three ways (audit 2026-10-18)
    ("a shell line cut by hand", r"shlex\.(shlex|split)\(", {"shell"}),
    # runlog start and usability log each cut at `--` by hand (2026-10-20)
    ("a command cut at -- by hand", r"\.index\(\s*[\"']--[\"']\s*\)", {"console"}),
    # six sites spelled `protocol-fill <file name> --from-run`; run from the
    # repo root the bare name failed (count probe, 2026-10-20); finalize
    # printed one with no protocol at all, which argparse refuses (audit
    # 2026-10-27, H5)
    (
        "an adopt command spelled by hand",
        r"protocol-fill (?:\{[^}]*\} --from-run|--from-run \{)",
        {"repo"},
    ),
    # thirteen modules read config.json's labkit fields by key; RunConfig
    # holds them typed where the record is read (2026-10-20)
    (
        "a run record read by key",
        r"read_run_config\([^)]*\)\s*or \{\}|\.config\.get\(\"",
        {"runs"},
    ),
    # six hand-spelled copies of a record's time (audit 2026-10-18)
    ("a record time spelled by hand", r"%Y-%m-%dT%H:%M:%S", {"runs"}),
    (
        "a run id's start second compared by hand",
        r"start_second\(|rsplit\(\"_\", 1\)",
        {"answering_run"},
    ),
    (
        "a requirements pin spelled by hand",
        r"startswith\(\"labkit\"\)|\^\\s\*labkit",
        {"repo"},
    ),
    # what a tier owes is read off `standard_contract.lane`, never off the
    # head's word: seven modules compared it by hand and the gate and the
    # skeleton disagreed (audit 2026-10-19)
    ("a tier rule read off the head", r"[=!]=\s*\{?\"low\"", {"standard_contract"}),
    # four gates walked the records for `open` findings themselves, each
    # grading differently (audit 2026-10-23, C1); `findings.open_findings` holds
    # the walk and the table of the gates' rules
    ("an open-finding walk", r"for \w+ in \w+\.open\b(?!\()", {"findings"}),
    # the stop, the handover and --findings each filtered open findings to
    # BLOCKERs themselves, one by status and grade (audit 2026-10-27, table C);
    # `findings.open_blockers`
    (
        "open BLOCKERs filtered by hand",
        r"\.grade == \"BLOCKER\" and \w+\.status == \"open\"|"
        r"open_findings\([^\n]*\) if \w+\.grade ==",
        {"findings"},
    ),
    # about twenty call sites spelled a run's directory and its metrics file
    # by hand (audit 2026-10-23); `runs.run_path`, `runs_path`, `metrics_path`
    (
        "a run directory spelled by hand",
        r"/ [\"']runs[\"']|[\"']runs[\"'] /|f\"runs/",
        {"runs"},
    ),
    ("the metrics file spelled by hand", r"\"metrics\.json\"", {"runs"}),
    # six readers turned JSONL lines into objects themselves, each with its
    # own error sentence (audit 2026-10-23); `jsonl.objects` / `data_rows`,
    # `batch` keeps the torn-last-line loop that is its own
    ("a JSONL line parsed by hand", r"json\.loads\(line\)", {"jsonl", "batch"}),
    # four checks globbed an area's scripts by hand (audit 2026-10-23);
    # `scope_sha.area_files` is where an area's code is
    (
        "an area's code globbed by hand",
        r"glob\(\"(scripts|analysis)/\*\.py\"\)|\"scripts\"\)\.glob\(",
        {"scope_sha"},
    ),
    # four readers found a protocol's `## ` headings themselves, two inside
    # fences too (audit 2026-10-23); `protocol_block.section_starts`
    (
        "a section heading found by hand",
        r"startswith\(\"## \"\)|\(\?=\^## ",
        {"protocol_block"},
    ),
    # seven sites listed the decided statuses, two copied the rule that a
    # carried finding closed dismissed or deferred owes a review (audit
    # 2026-10-27, C17): `findings.DECIDED_LIST`, `carried_and_closed`
    (
        "the decided statuses spelled by hand",
        r"fixed / accepted / deferred / dismissed|\(\"dismissed\", \"deferred\"\)",
        {"findings"},
    ),
    # a bare area name was read by two globs, `*` running over dashes, and
    # three slug comparisons that took the first match (audit 2026-10-27):
    # `repo.areas_named` reads it by the name grammar
    (
        "an area name globbed by hand",
        r"glob\(f?\"(\[0-9\]\*|\*)-|split_area_name\([^)]*\)\[1\] ==",
        {"repo"},
    ),
    # labkit-audit printed three refusals and its progress lines itself
    # (audit 2026-10-18, half-finished move; 2026-10-23): `console.refuse`,
    # `console.progress`
    (
        "a refusal or progress line printed by hand",
        r"print\(f\"[a-z-]+: .*file=sys\.stderr",
        {"console"},
    ),
]


#: shapes over several lines — (what, regex over the file, the module(s) where it belongs)
BLOCK_RULES: list[tuple[str, str, set[str]]] = [
    # the conditional form is held above; the try/except copy was not
    # (TODO, 2026-10-23): `repo.shown` for a shown path, `scope_sha._key`
    # for a stamp's key, else the question is answered elsewhere
    (
        "a path shown relative by hand (try/except form)",
        r"try:\n[^\n]*\.relative_to\([^\n]*\n\s*except ValueError:",
        {"repo", "runs", "scope_sha"},
    ),
    # the one-line form is held above; two progress lines of labkit-audit
    # stood as a print over four lines beside `console.progress` (audit
    # follow-up 2026-10-23). A `labkit-*` command's own line only: what
    # `batch`, `llm` and `runlog` tell the operator from inside a run is
    # not a command's progress
    (
        "a labkit command's line printed by hand (multi-line form)",
        r"print\(\n\s*f\"labkit-[a-z]+: [^\n]*\n(?:[^\n]*\n){0,3}?\s*file=sys\.stderr",
        {"console"},
    ),
]


def block_offenders(what: str, shape: str, homes: set[str]) -> list[str]:
    """Like `offenders`, for a shape that spans lines; a copy that must stay
    says why with a `home:` note on the line after the `except`."""
    out = []
    pattern = re.compile(shape)
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.stem in homes:
            continue
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            after = text[m.end() : m.end() + 200].split("\n")[1]
            if "home:" in after:
                continue
            line = text.count("\n", 0, m.start()) + 1
            out.append(f"{path.name}:{line}: {what}")
    return out


def offenders(what: str, shape: str, homes: set[str]) -> list[str]:
    out = []
    pattern = re.compile(shape)
    paths = sorted(PACKAGE.rglob("*.py"))
    if what in IN_TEMPLATES:
        paths += sorted((PACKAGE / "templates").glob("*.py.template"))
    for path in paths:
        if path.stem in homes:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            said = "home:" in line or (n > 1 and "home:" in lines[n - 2])
            if pattern.search(line) and not said:
                out.append(f"{path.name}:{n}: {what} — {line.strip()[:80]}")
    return out


class OneHome(unittest.TestCase):
    def test_no_copy_outside_its_home(self):
        found = [o for rule in RULES for o in offenders(*rule)]
        found += [o for rule in BLOCK_RULES for o in block_offenders(*rule)]
        self.assertEqual(found, [], "\n" + "\n".join(found))

    def test_the_block_rules_bite(self):
        samples = {
            "a path shown relative by hand (try/except form)": (
                "try:\n    rel = p.relative_to(root)\nexcept ValueError:\n    rel = p\n"
            ),
            "a labkit command's line printed by hand (multi-line form)": (
                "        print(\n"
                '            f"labkit-audit: clarity · {protocol.name} · "\n'
                '            f"{args.model} · {len(prompt) // 1000} kB",\n'
                "            file=sys.stderr,\n"
                "        )\n"
            ),
        }
        self.assertEqual(set(samples), {what for what, _, _ in BLOCK_RULES})
        for what, shape, _ in BLOCK_RULES:
            with self.subTest(what=what):
                self.assertIsNotNone(re.compile(shape).search(samples[what]), shape)

    def test_the_rules_bite(self):
        """Each shape matches what it is written for (a rule that matches
        nothing guards nothing)."""
        samples = {
            "sha256 by hand": "h = hashlib.sha256(data).hexdigest()",
            "git outside repo.git_run": 'subprocess.run(["git", "status"])',
            "a PROTOCOL-*.md scan": 'for f in root.rglob("PROTOCOL-*.md"):',
            "pip's name normalisation": 'name.lower().replace("_", "-")',
            "a fence regex": 'FENCE = re.compile(r"^\\s*```")',
            "a fence toggled by hand": 'if line.strip().startswith("```"):',
            "the id letters": 'KEY = re.compile(r"([ca])\\d+_pass")',
            "the area name NN-slug": 'm = re.match(r"^(\\d+)-(.+)$", name)',
            "a temp-and-rename write": "os.replace(tmp, path)",
            "the run-id shape": 'RUN = re.compile(r"\\d{4}-\\d{2}-\\d{2}T")',
            "a path shown relative by hand": "shown = p.relative_to(b) if p.is_relative_to(b) else p",
            "a shell line cut by hand": "words = shlex.split(command)",
            "a command cut at -- by hand": "cut = argv.index('--')",
            "an adopt command spelled by hand": 'print(f"protocol-fill {PROTOCOL.name} --from-run {rid}")',
            "a run record read by key": "cfg = read_run_config(run) or {}",
            "a record time spelled by hand": 'started = time.strftime("%Y-%m-%dT%H:%M:%S")',
            "a run id's start second compared by hand": "if answering_run.start_second(a) == answering_run.start_second(b):",
            "a requirements pin spelled by hand": 'if ln.startswith("labkit"):',
            "a tier rule read off the head": 'if head.repeat_cost == "low":',
            "an open-finding walk": "for f in rec.open:",
            "open BLOCKERs filtered by hand": 'held = [u for u in open_findings(rs) if u.grade == "BLOCKER"]',
            "a run directory spelled by hand": 'run_dir = area / "runs" / run_id',
            "the metrics file spelled by hand": 'metrics = run_dir / "metrics.json"',
            "the decided statuses spelled by hand": 'if f.carries and f.status in ("dismissed", "deferred"):',
            "an area name globbed by hand": 'hits = sorted(experiments.glob(f"[0-9]*-{name}"))',
            "a JSONL line parsed by hand": "row = json.loads(line)",
            "an area's code globbed by hand": 'scripts = sorted(area.glob("scripts/*.py"))',
            "a section heading found by hand": 'if line.startswith("## "):',
            "a refusal or progress line printed by hand": 'print(f"labkit-audit: {exc}", file=sys.stderr)',
        }
        for what, shape, _ in RULES:
            with self.subTest(what=what):
                self.assertIsNotNone(re.compile(shape).search(samples[what]), shape)


if __name__ == "__main__":
    unittest.main()
