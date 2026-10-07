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
