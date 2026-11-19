"""One home per question — held by grep, not by memory.

`docs/architecture.md` names the home of every recurring question and says
a second answer is drift. Copies of the same kinds — a hand-spelled
sha256, a `git` run outside `repo`, a `PROTOCOL-*.md` scan, the id letters,
a fence regex — come back while memory alone holds them. This test greps
`labkit/*.py` for the shapes a copy takes; a match outside the home fails,
naming file and line. A line that must stay says why in a comment on it or
directly above it that names the home it is not after `home:`.

The tests' own shared helpers are held the same way (`TEST_RULES`): a git
runner, a main-runner or a repository setup written into a test file beside
`repo_fixture` or `command_fixture` fails, naming file and function. A
function that keeps its own form on purpose is exempt by name, with the
reason beside it.
"""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path
from typing import get_args

from labkit.formats import runs

PACKAGE = Path(__file__).resolve().parents[1] / "labkit"
TESTS = Path(__file__).resolve().parent
#: labkit's console commands (`[project.scripts]`), longest first, as one
#: alternation: a command added there is held by the command rules below
CONSOLE_COMMANDS = "|".join(
    re.escape(name)
    for name in sorted(
        tomllib.loads((PACKAGE.parent / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["scripts"],
        key=len,
        reverse=True,
    )
)
#: rules that also hold in the stamped script templates — a stamped area reads
#: its tier off the contract like labkit does
IN_TEMPLATES = {
    "a tier rule read off the head",
    "an adopt command spelled by hand",
    "a criterion bar computed by hand",
}

#: (what, the shape of a copy, the module(s) where it belongs)
RULES: list[tuple[str, str, set[str]]] = [
    ("sha256 by hand", r"hashlib\.", {"digests"}),
    # a margin added by hand in a skeleton misses a bar the task states:
    # `criterion_bar.bar_of`
    (
        "a criterion bar computed by hand",
        r"Fraction\(str\([^)]*\b(margin|at_least)\)\)",
        {"criterion_bar"},
    ),
    (
        "git outside repo.git_run",
        r"subprocess\.\w+\(\s*\[\s*\"git\"",
        {"repo"},
    ),
    ("a PROTOCOL-*.md scan", r"r?glob\(\s*\"PROTOCOL-", {"repo"}),
    (
        "pip's name normalisation",
        r"\.lower\(\)\.replace\(\"_\", \"-\"\)",
        {"requirements"},
    ),
    ("a fence regex", r"re\.compile\([^\n]*(`\{3|```|~\{3)", {"markdown"}),
    ("a fence toggled by hand", r"startswith\(\(?\"(```|~~~)", {"markdown"}),
    ("the id letters", r"\[(?:[cab]{2,3}|[CAB]{2,3})\]|\^a\\d", {"promises"}),
    ("the area name NN-slug", r"\^\(\\d\+\)-", {"repo"}),
    ("a temp-and-rename write", r"os\.replace\(", {"files"}),
    ("the run-id shape", r"\\d\{4\}-\\d\{2\}-\\d\{2\}T", {"runs"}),
    # "relative to the repo, else absolute" has one answer; the conditional
    # form is held here, the try/except copy among the block rules
    ("a path shown relative by hand", r"\.is_relative_to\(", {"repo", "runs"}),
    # a shell line is cut one way, for the hook and the transcript alike
    ("a shell line cut by hand", r"shlex\.(shlex|split)\(", {"shell"}),
    # a command line is cut at `--` in one place (runlog start, usability log)
    ("a command cut at -- by hand", r"\.index\(\s*[\"']--[\"']\s*\)", {"console"}),
    # `protocol-fill <file name> --from-run` spelled by hand fails run from
    # the repo root, and one with no protocol at all is refused by argparse
    (
        "an adopt command spelled by hand",
        r"protocol-fill (?:\{[^}]*\} --from-run|--from-run \{)",
        {"commands"},
    ),
    # a run record's `data=` entry read by key can turn a missing path into
    # "None"; `runs.data_entries`
    (
        "a data= entry read by key",
        r"""(\.get\(|\[)\s*["']rows["']""",
        {"runs"},
    ),
    # the run record's file names are constants; `runs.CONFIG_FILE`,
    # `COMPLETION_FILE`, `OUTPUTS_FILE`
    (
        "a run record file spelled by hand",
        r"/ \"(config|completion|outputs)\.json\"",
        {"runs"},
    ),
    # a kind is a constant, never compared as a word;
    # `standard_contract.*_KIND`
    (
        "a kind compared as a word",
        r"kind [=!]= \"(compute|fit|apply)\"",
        {"standard_contract"},
    ),
    # a protocol type is a constant with one definition, never compared as a
    # word; `protocol_block.EXPLORATORY`, `CONFIRMATORY`
    (
        "a protocol type named by hand",
        r"[=!]= \"(exploratory|confirmatory)\"|^(EXPLORATORY|CONFIRMATORY)\b.* = ",
        {"protocol_block"},
    ),
    # `core.hooksPath` is set in one place
    (
        "core.hooksPath set by hand",
        r"\"core\.hooksPath\", \"\.githooks\"",
        {"install_hooks"},
    ),
    # the audit and both reviewers share the answer-line separator and the
    # prompt's joining; `findings.SEP`, `findings.LEAD`, `prompts.prompt_body`
    ("an answer-line separator spelled by hand", r"\(\?:·\|—\|–\|:\)", {"findings"}),
    (
        "a prompt joined by hand",
        r"\.join\(f\"===== \{|f\"\\n?===== FILE: \{",
        {"prompts"},
    ),
    # an `--into` command spelled by hand can name the protocol relative to
    # the report and the report relative to the repo, and run from neither;
    # `commands.into_command`
    (
        "an --into command spelled by hand",
        r"protocol-fill \{[^}]*\} --into",
        {"commands"},
    ),
    # config.json's labkit fields are not read by key: RunConfig holds them
    # typed where the record is read
    (
        "a run record read by key",
        r"read_run_config\([^)]*\)\s*or \{\}|\.config\.get\(\"",
        {"runs"},
    ),
    # a record's time has one spelling
    ("a record time spelled by hand", r"%Y-%m-%dT%H:%M:%S", {"runs"}),
    # an audit file's minute has one spelling; `runs.name_minute`,
    # `runs.date_minute`
    ("a record minute spelled by hand", r"%Y-%m-%dT%H[-:]%M[\"']", {"runs"}),
    # runlog's repeat_of and start_check's derived_from read their parent run
    # in one place; `start_check.completed_parent`
    ("a parent run read by hand", r"names no completed run", {"start_check"}),
    # finalize and preflight render the area-test run alike, so a fix lands
    # in both; `preflight.tell_test_run`
    (
        "an area-test run rendered by hand",
        r"pytest is not installed in this",
        {"preflight"},
    ),
    # a skeleton's stamped kept key named by hand in a probe drifts, and a
    # draw scores "absent"; `standard_contract.stamped_kept_key`
    (
        "a stamped kept key named by hand",
        r"\"metric_key\":\s*\"(?:score|accuracy)\"",
        {"standard_contract"},
    ),
    # what a second reviewer's draws release is one rule for a finding's
    # decision and a report claim's; `reviews.released_by`
    (
        "the release rule of a review's draws spelled by hand",
        r"any\(\s*not \w+\.again\b",
        {"reviews"},
    ),
    # audit modes, the experiments folder and a file:// URL have one
    # spelling each
    (
        "an audit mode spelled by hand",
        r"[=!]= \"(?:analysis|preflight)\"|mode=\"(?:analysis|preflight)\"",
        {"standard_contract"},
    ),
    (
        "the experiments folder named by hand",
        r"\"experiments\"[,)]|/ \"experiments\"",
        {"repo"},
    ),
    (
        "a file:// URL read by hand",
        r"url\[7:\]|removeprefix\(\"(?:git\+)?file://\"\)",
        {"repo"},
    ),
    # the run's start and reindex share the index's name and header check;
    # `run_index.RUN_INDEX`, `header_refusal`
    ("the run index named by hand", r"\"runs\.tsv\"", {"run_index"}),
    # a ref's commit is asked of git in one place; `repo.commit_of`,
    # `repo.text_at`
    ("a ref's commit asked of git by hand", r"\^\{\{commit\}\}", {"repo"}),
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
    # head's word: a comparison by hand lets the gate and the skeleton
    # disagree
    ("a tier rule read off the head", r"[=!]=\s*\{?\"low\"", {"standard_contract"}),
    # the walk over the records for `open` findings grades one way;
    # `findings.open_findings` holds the walk and the table of the gates' rules
    ("an open-finding walk", r"for \w+ in \w+\.open\b(?!\()", {"findings"}),
    # the printed `--decide` line is built one way; `commands.decide_command`
    ("a decide command spelled by hand", r"--decide \{", {"commands"}),
    # the stop, the handover and --findings filter open findings to BLOCKERs
    # in one place; `findings.open_blockers`
    (
        "open BLOCKERs filtered by hand",
        r"\.grade == \"BLOCKER\" and \w+\.status == \"open\"|"
        r"open_findings\([^\n]*\) if \w+\.grade ==",
        {"findings"},
    ),
    # a run's directory and its metrics file are spelled in one place;
    # `runs.run_path`, `runs_path`, `metrics_path`
    (
        "a run directory spelled by hand",
        r"/ [\"']runs[\"']|[\"']runs[\"'] /|f\"runs/",
        {"runs"},
    ),
    ("the metrics file spelled by hand", r"\"metrics\.json\"", {"runs"}),
    # JSONL lines become objects in one place, with one error sentence;
    # `jsonl.objects` / `data_rows`, `batch` keeps the torn-last-line loop
    # that is its own
    ("a JSONL line parsed by hand", r"json\.loads\(line\)", {"jsonl", "batch"}),
    # `scope_sha.area_files` is where an area's code is
    (
        "an area's code globbed by hand",
        r"glob\(\"(scripts|analysis)/\*\.py\"\)|\"scripts\"\)\.glob\(",
        {"scope_sha"},
    ),
    # a protocol's `## ` headings are found by one reader, which skips
    # fences; `markdown.section_starts`
    (
        "a section heading found by hand",
        r"startswith\(\"## \"\)|\(\?=\^## ",
        {"markdown"},
    ),
    # the decided statuses, and the rule that a carried finding closed as a
    # false positive owes a review, have one home: `findings.DECIDED_LIST`,
    # `findings.CLOSING`
    (
        "the decided statuses spelled by hand",
        r"fixed / limitation / false-positive|\(\"fixed\", \"false-positive\"\)",
        {"findings"},
    ),
    # a decision status is a constant, never compared as a word — a mistyped
    # word compares false without an error: `findings.OPEN`, `FIXED`,
    # `LIMITATION`, `FALSE_POSITIVE`. The shape is the quoted word beside
    # `==`, `!=` or `in`, so the word in a sentence does not match
    (
        "a decision status compared as a word",
        r"(?:[=!]=\s*|\bin\s*[(\[{][^)\]}\n]*)"
        r"[\"'](?:open|fixed|limitation|false-positive)[\"']"
        r"|[\"'](?:open|fixed|limitation|false-positive)[\"']\s*"
        r"(?:[=!]=|(?:not\s+)?in\b)",
        {"findings"},
    ),
    # the same for a run's kind: `runs.PREPARATION`, `PROBE`, `MEASUREMENT`
    (
        "a run kind compared as a word",
        r"(?:[=!]=\s*|\bin\s*[(\[{][^)\]}\n]*)"
        r"[\"'](?:preparation|probe|measurement)[\"']"
        r"|[\"'](?:preparation|probe|measurement)[\"']\s*"
        r"(?:[=!]=|(?:not\s+)?in\b)",
        {"runs"},
    ),
    # a bare area name is read neither by a glob, whose `*` runs over
    # dashes, nor by a slug comparison taking the first match:
    # `repo.areas_named` reads it by the name grammar
    (
        "an area name globbed by hand",
        r"glob\(f?\"(\[0-9\]\*|\*)-|split_area_name\([^)]*\)\[1\] ==",
        {"repo"},
    ),
    # the area's test file is named in one place, so an area without a
    # number gets no `test__<slug>.py`: `repo.area_test_stem`
    (
        "an area's test file named by hand",
        r"f[\"']test_\{",
        {"repo"},
    ),
    # a `[table]` of the TOML head is found by one regex:
    # `protocol_block.table_span`
    (
        "a head table header spelled by hand",
        r"(?<!\\\[)\\\[\\s\*[a-z]+\\s\*\\\](?!\\\])",
        {"protocol_block"},
    ),
    # "is a value the stamp's <…>" has one answer:
    # `protocol_block.is_stamp_placeholder`
    (
        "a stamp placeholder tested by hand",
        r"startswith\(\"<\"\)[^\n]*endswith\(\">\"\)",
        {"protocol_block"},
    ),
    # a restore from git a way out names is one quoted line, so a path with
    # a space gives a command that runs: `commands.checkout_command`
    ("a git restore spelled by hand", r"git checkout (?:HEAD|\{)", {"commands"}),
    # a command's refusals and progress lines go through `console.refuse`,
    # `console.progress`
    (
        "a refusal or progress line printed by hand",
        r"print\(f\"[a-z-]+: .*file=sys\.stderr",
        {"console"},
    ),
    # a printed command names its path through a builder, which quotes it as
    # the working directory reaches it: a console command opening a
    # backticked line with an interpolated first argument, or
    # `protocol-fill <PROTOCOL>` with an interpolated one after it, is a
    # line spelled by hand. A sentence with slots only (`<PROTOCOL>`,
    # `<area>`) names no path and stands, as does the area slot a gate
    # fills (`gate.AREA_SLOT`)
    (
        "a console command spelled by hand",
        rf"`(?:{CONSOLE_COMMANDS})(?: [a-z-]+)? \{{(?!AREA_SLOT\}})"
        r"|protocol-fill <PROTOCOL> [^`\n]*\{",
        {"commands"},
    ),
    # a staging is one quoted line after `--`, each path as the working
    # directory reaches it: `commands.stage_command`
    (
        "a staging spelled by hand",
        r"""git add[^`\n]*(?:\{|["'] \+)""",
        {"commands"},
    ),
    # a `runlog AREA` line outside backticks (the status and wait lines of a
    # detached start) escapes the console-command rule above:
    # `commands.gate_command`, `wait_command`, `detached_start_command`
    ("a runlog line spelled by hand", r"runlog (?:start )?\{", {"commands"}),
    # a protocol as a printed command names it — quoted, as the working
    # directory reaches it — is `commands.protocol_word`
    (
        "a protocol's word spelled by hand",
        r"shlex\.quote\(\s*shown\(\s*protocol\b",
        {"commands"},
    ),
    # a discussion block's line quotes its paths in one place:
    # `report_blocks.discuss_command`
    ("a discuss command spelled by hand", r"--discuss \{", {"report_blocks"}),
    # the measurement script is `runs.MEASURE_SCRIPT`, as a path and in a
    # printed line (`commands.measure_command`, `measure_slot_command`)
    (
        "the measurement script named by hand",
        r"/ \"01_measure\.py\"|\}/scripts/01_measure\.py",
        {"runs"},
    ),
    # a path relative to the repository root, as git names it, is
    # `repo.rel_posix`: it resolves the root and says where a path outside
    # it lies. The shape tells a repository from an area by the name of the
    # base alone (`root`, `repo`); a base under another name is not held
    (
        "a repo-relative path spelled by hand",
        r"\.relative_to\((?:root|repo)\)\.as_posix\(\)",
        {"repo"},
    ),
    # the same path taken with `str()`, as a record or a stamp writes it
    (
        "a repo-relative path spelled by hand (str form)",
        r"str\([^()\n]*\.relative_to\((?:root|repo)\)\)",
        {"repo"},
    ),
]


#: shapes over several lines — (what, regex over the file, the module(s) where it belongs)
BLOCK_RULES: list[tuple[str, str, set[str]]] = [
    # the conditional form is held above, the try/except copy here:
    # `repo.shown` for a shown path, `scope_sha._key` for a stamp's key, else
    # the question is answered elsewhere
    (
        "a path shown relative by hand (try/except form)",
        r"try:\n[^\n]*\.relative_to\([^\n]*\n\s*except ValueError:",
        {"repo", "runs", "scope_sha"},
    ),
    # the one-line form is held above, a print over several lines here,
    # beside `console.progress`. A `labkit-*` command's own line only: what
    # `batch`, `llm` and `runlog` tell the operator from inside a run is
    # not a command's progress
    (
        "a labkit command's line printed by hand (multi-line form)",
        r"print\(\n\s*f\"labkit-[a-z]+: [^\n]*\n(?:[^\n]*\n){0,3}?\s*file=sys\.stderr",
        {"console"},
    ),
    # the one-line form is held above; here the command closes one string
    # piece and its interpolated path opens the next
    (
        "a console command spelled by hand (split form)",
        rf"`(?:{CONSOLE_COMMANDS})(?: [a-z-]+)? \"\n\s*f?\"\{{(?!AREA_SLOT\}})",
        {"commands"},
    ),
    # "the adopted run, None where `[result]` does not read" has one
    # answer: `answering_run.adopted_run`. A reader that keeps the sentence
    # (`report_context.declaration`) or refuses with it is not this shape
    (
        "an adopted run read by hand",
        r"try:\n[^\n]*declared_run\([^\n]*\n\s*except [^\n]*BlockError[^\n]*:"
        r"\n\s*(?:return None|\w+ = None|pass)\n",
        {"answering_run"},
    ),
]


#: the shapes a copy of a shared test helper takes — (what, regex over the
#: file, the fixture module where it belongs, the functions that keep their
#: own form as `file.py:function`, each with its reason)
TEST_RULES: list[tuple[str, str, str, set[str]]] = [
    # a function that takes `*args` and passes them to `["git", …]`:
    # `repo_fixture.git`
    (
        "a git runner beside repo_fixture.git",
        r"def \w+\([^)]*\*(\w+)[^)]*\)[^:\n]*:\n"
        r"(?:[^\n]*\n){0,8}?[^\n]*\[\s*\"git\",[^\]]*\*\1\b",
        "repo_fixture",
        {
            # returns the process, and `check=False` lets a test read the
            # exit of a commit its hook refused
            "test_install_hooks.py:run_git",
            # reads labkit's own repository, not a fixture's: no identity,
            # a timeout, and a failing git (a shallow clone) is not an error
            "test_release_tags.py:_git",
        },
    ),
    # stdout caught, a `main` called, (exit code, text) returned — with or
    # without stderr, a working directory or a patched model around it:
    # `command_fixture.run_main`. A helper that returns the two streams apart
    # or joins them after the call is not this shape
    (
        "a main-runner beside command_fixture.run_main",
        r"redirect_stdout\((\w+)\)(?:[^\n]*\n){1,6}?\s+(\w+) = [\w.]+\.main\("
        r"(?:[^\n]*\n){1,14}?\s+return \2, \1\.getvalue\(\)$",
        "command_fixture",
        set(),
    ),
    # an identity written into a repository's config by hand:
    # `repo_fixture.init_repo`
    (
        "a repository identity set beside repo_fixture.init_repo",
        r"\"config\",\s*\"user\.(?:email|name)\"",
        "repo_fixture",
        {
            # the three below run git with its exit unchecked, as they did
            # before the home existed: a setup that failed went on
            "test_preflight.py:_area",
            "test_protocol_id.py:_repo",
            "test_runlog_active.py:_repo",
            # a script run under a decoy GIT_DIR — where its `git config`
            # lands is what the test asserts
            "test_git_env_isolation.py:<module>",
        },
    ),
]


def enclosing_function(text: str, start: int, end: int) -> str:
    """The function the match TEXT[START:END] lies in: the `def` the match
    opens with, else the nearest `def` above it that is indented less than
    the match's least indented line; `<module>` outside every function."""
    opened = re.match(r"def (\w+)\(", text[start:])
    if opened:
        return opened.group(1)
    line_start = text.rfind("\n", 0, start) + 1
    lines = [ln for ln in text[line_start:end].splitlines() if ln.strip()]
    indent = min(len(ln) - len(ln.lstrip()) for ln in lines)
    for above in reversed(text[:line_start].splitlines()):
        found = re.match(r"([ \t]*)def (\w+)\(", above)
        if found and len(found.group(1)) < indent:
            return found.group(2)
    return "<module>"


def helper_copies(shape: str, home: str) -> dict[str, int]:
    """Where the tests hold SHAPE outside its HOME module and this file (its
    samples): `file.py:function` to the line of the first match there."""
    out: dict[str, int] = {}
    pattern = re.compile(shape, re.MULTILINE)
    for path in sorted(TESTS.glob("*.py")):
        if path.stem in {home, Path(__file__).stem}:
            continue
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            name = f"{path.name}:{enclosing_function(text, m.start(), m.end())}"
            out.setdefault(name, text.count("\n", 0, m.start()) + 1)
    return out


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

    def test_no_copy_of_a_shared_test_helper(self):
        """A test file calls the shared helper; a function named as exempt
        still holds the shape (an exemption that names nothing is drift)."""
        for what, shape, home, exempt in TEST_RULES:
            with self.subTest(what=what):
                found = helper_copies(shape, home)
                copies = [
                    f"{name.replace(':', f':{line}:')}: {what}"
                    for name, line in found.items()
                    if name not in exempt
                ]
                self.assertEqual(copies, [], "\n" + "\n".join(copies))
                self.assertEqual(exempt - set(found), set(), "exempt, but not found")

    def test_the_test_rules_bite(self):
        samples = {
            "a git runner beside repo_fixture.git": (
                "def _git(cwd: Path, *args: str) -> None:\n"
                '    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)\n'
            ),
            "a main-runner beside command_fixture.run_main": (
                "    buf = io.StringIO()\n"
                "    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):\n"
                "        code = finalize.main(argv)\n"
                "    return code, buf.getvalue()\n"
            ),
            "a repository identity set beside repo_fixture.init_repo": (
                '    _git(root, "config", "user.email", "t@t")\n'
            ),
        }
        self.assertEqual(set(samples), {what for what, _, _, _ in TEST_RULES})
        for what, shape, _, _ in TEST_RULES:
            with self.subTest(what=what):
                self.assertIsNotNone(
                    re.compile(shape, re.MULTILINE).search(samples[what]), shape
                )

    def test_a_copy_is_named_by_its_function(self):
        text = (
            "class A:\n"
            "    def helper(self):\n"
            "        def fake():\n"
            "            return 1\n"
            "        with (\n"
            "            x,\n"
            "        ):\n"
            "            pass\n"
            "        return 2\n"
            "def top(*args):\n"
            "    pass\n"
        )
        inner, last = text.index("x,"), text.index("return 2") + len("return 2")
        self.assertEqual(enclosing_function(text, inner, last), "helper")
        opened = text.index("def top")
        self.assertEqual(enclosing_function(text, opened, len(text)), "top")
        self.assertEqual(enclosing_function(text, 0, len("class A:")), "<module>")

    def test_the_run_kinds_are_the_named_constants(self):
        """`RunKind` is a Literal, whose words cannot be built from the
        constants: the two spellings are held equal here."""
        self.assertEqual(
            get_args(runs.RunKind), (runs.PREPARATION, runs.PROBE, runs.MEASUREMENT)
        )

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
            "a console command spelled by hand (split form)": (
                '            fix=f"repair what the sentence names; `intent-check "\n'
                '            f"{shlex.quote(shown(protocol, Path.cwd()))}` holds it alone",\n'
            ),
            "an adopted run read by hand": (
                "    try:\n"
                "        tree_run = protocol_block.declared_run(tree)\n"
                "    except protocol_block.BlockError:\n"
                "        tree_run = None\n"
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
            "a criterion bar computed by hand": "bar = base + Fraction(str(cfg.margin))",
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
            "a run record file spelled by hand": 'cfg = run_dir / "config.json"',
            "a data= entry read by key": 'n = entry.get("rows")',
            "a kind compared as a word": 'if kind == "apply":',
            "a protocol type named by hand": 'if head.type != "confirmatory":',
            "core.hooksPath set by hand": 'git_run(["config", "core.hooksPath", ".githooks"], root)',
            "an answer-line separator spelled by hand": 'CLAIM = re.compile(r"CLAIM\\s*(?:·|—|–|:)")',
            "a prompt joined by hand": 'body = "".join(f"===== {lbl} =====\\n{txt}\\n" for lbl, txt in p)',
            "an --into command spelled by hand": 'f"protocol-fill {protocol} --into {rel}"',
            "a run record read by key": "cfg = read_run_config(run) or {}",
            "a record time spelled by hand": 'started = time.strftime("%Y-%m-%dT%H:%M:%S")',
            "a stamped kept key named by hand": '"metric_key": "score",',
            "an audit mode spelled by hand": 'if record.mode == "analysis":',
            "the experiments folder named by hand": 'experiments = root / "experiments"',
            "a file:// URL read by hand": "return Path(url[7:])",
            "the run index named by hand": 'index = base_dir / "runs.tsv"',
            "a ref's commit asked of git by hand": 'git_run(["rev-parse", f"{ref}^{{commit}}"], d)',
            "an area-test run rendered by hand": '"pytest is not installed in this interpreter — tests not run"',
            "a parent run read by hand": 'f"runlog: repeat_of={x!r} names no completed run under {d}"',
            "a record minute spelled by hand": 'stamp = time.strftime("%Y-%m-%dT%H-%M", when)',
            "a run id's start second compared by hand": "if answering_run.start_second(a) == answering_run.start_second(b):",
            "a requirements pin spelled by hand": 'if ln.startswith("labkit"):',
            "a tier rule read off the head": 'if head.repeat_cost == "low":',
            "an open-finding walk": "for f in rec.open:",
            "a decide command spelled by hand": 'f"{cmd} --decide {n} fixed \\"<why>\\""',
            "open BLOCKERs filtered by hand": 'held = [u for u in open_findings(rs) if u.grade == "BLOCKER"]',
            "a run directory spelled by hand": 'run_dir = area / "runs" / run_id',
            "the metrics file spelled by hand": 'metrics = run_dir / "metrics.json"',
            "the decided statuses spelled by hand": 'if f.status in ("fixed", "false-positive"):',
            "a decision status compared as a word": 'if decided.status == "limitation":',
            "a run kind compared as a word": 'and cfg.run_kind == "preparation"',
            "an area name globbed by hand": 'hits = sorted(experiments.glob(f"[0-9]*-{name}"))',
            "a JSONL line parsed by hand": "row = json.loads(line)",
            "an area's code globbed by hand": 'scripts = sorted(area.glob("scripts/*.py"))',
            "a section heading found by hand": 'if line.startswith("## "):',
            "a refusal or progress line printed by hand": 'print(f"labkit-audit: {exc}", file=sys.stderr)',
            "an area's test file named by hand": 'stem = f"test_{nn}_" + name',
            "a stamp placeholder tested by hand": 'if v.startswith("<") and v.endswith(">"):',
            "a git restore spelled by hand": 'f"restore it (`git checkout HEAD -- {path}`)"',
            "the release rule of a review's draws spelled by hand": "return any(not cr.again for cr, _ in pairs) and all(",
            "a head table header spelled by hand": 'H = re.compile(r"^\\s*\\[\\s*result\\s*\\]\\s*$")',
            "a console command spelled by hand": 'fix=f"freeze it: `preflight {shlex.quote(shown(ctx.area, Path.cwd()))}` "',
            "a staging spelled by hand": 'fix = f"stage it: `git add -- {outside_index[token]}`"',
            "a runlog line spelled by hand": 'print(f"status:  runlog {area}        wait:  runlog {area} --wait")',
            "a protocol's word spelled by hand": "named = shlex.quote(shown(protocol, Path.cwd()))",
            "a discuss command spelled by hand": 'f"`protocol-fill {name} --discuss {run_id} --why …`"',
            "the measurement script named by hand": 'script = area / "scripts" / "01_measure.py"',
            "a repo-relative path spelled by hand": "rel = {f.relative_to(root).as_posix() for f in files}",
            "a repo-relative path spelled by hand (str form)": "runs = sorted(str(rd.dir.relative_to(repo)) for rd in found)",
        }
        for what, shape, _ in RULES:
            with self.subTest(what=what):
                self.assertIsNotNone(re.compile(shape).search(samples[what]), shape)


if __name__ == "__main__":
    unittest.main()
