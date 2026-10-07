# Code navigation, round 1 (2026-10-07): how a newcomer finds their way in the code

Question: before a navigation rule enters the coding style — what makes a
repo's code fast to find one's way in, and does uniagent's code map (the
README's "Code — wo was liegt" table and "Ein Fall, Schritt für Schritt")
help more than labkit's?

Instrument: `usability nav` (labkit 0.61.0). A cold Sonnet agent gets the
repo and five questions that describe a behaviour, answers each with
`path:line`, and may read and search but change nothing. The truth is a
function, class or module-level name, resolved from the source with `ast`;
an answer counts when its file matches and its line falls inside the
truth's span. Effort comes from the transcript. Two agents per repo — a
qualitative pilot.

| repo | found | seconds | tool calls | files opened |
|---|---|---|---|---|
| uniagent, agent 1 | 5/5 | 65 | 10 | 5 |
| uniagent, agent 2 | 5/5 | 87 | 11 | 5 |
| labkit, agent 1 | 5/5 | 31 | 8 | 3 |
| labkit, agent 2 | 5/5 | 41 | 9 | 4 |

Files opened counts reads of repo files; `sed -n` ranges count as reads.

What the agents did (from the transcripts, every shell command read):

- **No agent read the README, a code map or `docs/architecture.md`.**
  Every agent opened with a file listing and a `grep -rn` for words of the
  question — `majority`, `quote`, `baseline`, `fallback`, `fingerprint`,
  `complete`, `after.run`, `area_test` — then read line ranges around the
  hits (`sed -n a,bp`) and a `grep -n "^def "` of the candidate module.
- **They found everything because the code's names carry the behaviour's
  words:** `majority`, `parse_answer` (the quote check inside it, reached
  through the error kind `quote_rejected`), `aggregate_baseline`,
  `label_for`, `fallback`, `area_tests`, `run_state`/`completion_state`.
  Where the name did not carry the word ("fingerprint" vs `scope_sha`),
  the module's own vocabulary (`sha`) did.
- **The questions leaked the code's words.** "baseline", "fallback",
  "majority", "quote" are identifiers in uniagent; the probe measured
  grep, not navigation. At this difficulty it does not separate the two
  repos: labkit was faster, but its five truths sit in four small,
  well-named modules, uniagent's in five packages.

Consequences:

1. The finding that holds: **an agent navigates by names, not by maps.**
   A name that carries the behaviour's everyday word (and an error kind or
   constant that does) is what made every answer one grep away. This is
   CS-007's "the field's standard term" seen from the reader's side.
2. Whether a map helps cannot be read off this round: no agent opened one,
   and the questions did not need it. A human in an editor navigates
   differently (file tree, go-to-definition) and is not measured here.
3. Round 2 before any rule: questions in a person's words with no
   identifier in them, and questions that need the flow ("what happens to
   a case between reading its documents and the model's rule review?"),
   on the same two repos.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round1/`.

## Round 2 (2026-10-07): questions in a person's words, along the flow

The same two repos, four new cold agents, five questions each with no
identifier in them ("the model claims a document says something it does
not say — where is that caught?", "follow one application from start to
finish: where are its steps run in order?").

| repo | found (truth as registered) | found (two truths widened, see below) | seconds | tool calls |
|---|---|---|---|---|
| uniagent, agent 1 | 4/5 | 5/5 | 89 | 10 |
| uniagent, agent 2 | 4/5 | 5/5 | 54 | 10 |
| labkit, agent 1 | 4/5 | 5/5 | 45 | 9 |
| labkit, agent 2 | 4/5 | 5/5 | 63 | 11 |

**Two truths were widened after the answers were read**, both because the
answers were right and the registered truth too narrow: uniagent's "which
tests are switched on" — both agents answered `rulebase/register.py:
load_profile`, whose docstring reads "Load the profile that says which
checks a run activates"; labkit's "instruction text of the empty form left
in a filled record" — both answered inside `protocol_check.main`, where
the comparison is done (`template_lines` only builds the set). Large truth
spans (`runlog.Run`, 217 lines; `FrameworkClassifier`, 247) are lenient.

How they searched (every command read):

- Again no agent opened a README, a code map or `docs/architecture.md`.
- They built the map themselves: a file listing, then `grep -n "^def
  \|^class "` over the packages whose names fit (`deciding/`, `model/`,
  `running/`, `rulebase/`; `scope_sha.py`, `runs.py`), then searches for
  synonyms of the question's words ("verbatim", "hallucin", "ground",
  "stale", "audited", "instruction", "placeholder"), then the first lines
  of the hits.
- What a name did not say, a first docstring line or an error kind did:
  `load_profile`'s docstring, the error kind `quote_rejected`.
- The one thing found only by reading a long body is the one without a
  name of its own: the leftover-template check inside a 250-line `main`.

Consequences, written into the coding style as CS-015 Make the code
findable by name (dotfiles `coding-style.md`):

1. The names and the first docstring lines are the map an agent reads;
   logic someone will look for gets its own function named for what it
   does, its first docstring line carries the word a person would search.
2. Package, file, error-kind and constant names that say what they mean
   are search hits.
3. A README code map is not what agents use; it may still orient a person,
   who was not measured here.
4. The probe saturates: both repos at 20/20 with comparable effort. To
   separate repos or rule changes it needs harder questions (several hops
   along the flow) or a weaker reader.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round2/`.

## Round 3 (2026-10-07): questions across several hops, a weaker reader

Five harder questions per repo — each answer is reached only by following
the flow ("the model has said some order lines are contract goods: where
are their amounts added up into the figure a fixed check later decides
on?"); two Haiku and two Sonnet agents per repo. Truths registered before
the run, none widened.

| repo | Sonnet (2 agents) | Haiku (2 agents) | Sonnet calls | Haiku calls |
|---|---|---|---|---|
| uniagent | 10/10 | 9/10 | 9, 11 | 21, 23 |
| labkit | 10/10 | 5/10 | 9, 11 | 22, 25 |

The probe separates now — not by the strong reader, by the weak one, and
it separates the repos.

Where Haiku missed in labkit (every miss read in the transcript and the
code):

- **Two settings blocks** (h4: "every experiment record carries a small
  block of settings at its end — where is the list it must contain?"):
  both answered the run's `config.json` fields in `runlog.py` instead of
  the protocol head's `HEAD_FIELDS`. The question said "record", which
  fits both; labkit has two blocks of settings, one per protocol and one
  per run, and their names (`head`, `config`) do not say which belongs to
  what. Partly a flaw of the question, partly the finding.
- **Two fingerprints** (h3: helper files imported by an experiment): one
  agent answered `promises.declared_scope_sha` — the digest over a
  promise's declared files — instead of `scope_sha.imported_lib`. Two
  mechanisms hash code, in two modules, with the same word "scope".
- **Two checks against what the run recorded** (h2: a promised constant
  compared with the value the run used): one agent answered `finalize`'s
  check that a criterion's n matches a recorded input count, instead of
  `intent_check.constant_findings`.
- **Logic without a name of its own** (h5: which Python runs the area's
  tests): one agent never opened `preflight.py` and answered
  `pyproject.toml`; the choice of interpreter is four lines inside
  `area_tests`, with no function or constant that names it.
- In uniagent the one Haiku miss is defensible: `extract.MARKERS`, the
  table `classify_document` decides by.

**Maps:** only the two Haiku agents in labkit opened a map — `README.md`,
`docs/architecture.md`, `CLAUDE.md` — when lost; it did not lead them to
the answer. No Sonnet agent in three rounds, and no Haiku agent in
uniagent, opened one.

Consequences for CS-015 Make the code findable by name (dotfiles
`coding-style.md`, sharpened):

1. Two mechanisms that do similar things need names that say how they
   differ — the misses cluster where labkit has two of a kind.
2. Logic someone will look for gets its own name — confirmed a third time
   (the interpreter choice inside `area_tests`).
3. A map is what a struggling reader turns to; it does not rescue names
   that do not separate.

For labkit this is a work list, not yet done: the protocol head vs the run
config, the area stamp (`scope_sha`) vs the declared-scope digest
(`promises.declared_scope_sha`), the criterion-n check vs the constant
check, the interpreter choice in `area_tests`.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round3/`.

## Round 4 (2026-10-07): labkit after the renames (0.62.0), the weaker reader again

labkit 0.62.0 gave the four places of round 3's misses names that tell two
of a kind apart (`PROTOCOL_HEAD_KEYS`, `imported_repo_helpers`,
`promised_constant_mismatches` vs `criterion_n_input_mismatches`) and the
interpreter choice a function of its own (`area_test_python`), with first
docstring lines that say what each is not. Then round 3's labkit questions
again, Haiku only, in two versions: the **same** wording, and a
**reworded** one without the words the new names now carry ("promised",
"helper", "settings", "Python installation"), so that a gain cannot come
from a question that names the answer.

| labkit, Haiku | found | calls | maps opened |
|---|---|---|---|
| round 3, before the renames (2 agents) | 5/10 | 22, 25 | README, architecture, CLAUDE.md |
| round 4, same questions (2 agents) | 10/10 | 32, 19 | none |
| round 4, reworded questions (2 agents) | 10/10 | 21, 16 | none |

- **The weaker reader found every place, in both wordings,** and no agent
  turned to a map. labkit now reads like uniagent did for Haiku in round 3
  (9/10).
- **What this shows and what not:** the questions sit exactly on the
  places that were changed — the round shows that the change fixes what
  was missed, not that labkit as a whole is now easier to navigate. The
  reworded h4 is also clearer than round 3's ("written plan" instead of
  the ambiguous "record"), so part of that one gain is the question's.
  Two to four agents per cell; one agent needed 32 calls for 5/5 — the
  variance between agents is as large as the effect on effort, so only the
  found count is read.

Consequence: CS-015 Make the code findable by name holds up in the one
test that can falsify it — rename what a weak reader confused, and the
weak reader stops confusing it. A fresh question set on untouched parts of
both repos would show how far it generalizes.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round4/`.
