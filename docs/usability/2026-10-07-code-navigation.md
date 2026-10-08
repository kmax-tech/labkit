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

## Round 5 (2026-10-07): does an entry point need to read as named steps?

Candidate rule, proposed from outside the measurements: "an entry point
reads as a sequence of named steps; a consequential decision inside it
becomes a function of its own". Test case: `finalize.run` (labkit
`ac97187`), 210 lines in which seven stations and their decisions stand
inline, each station opened by a numbered section comment
(`# -- 1. completion check --`) and a printed header (`── completion ──`).
Plan: measure, refactor `run` into named steps, measure again.

Questions (Haiku, two agents): five decisions that have no name of their
own — which of several bound runs the checks hold the protocol to, whether
the cited run is the examined one, for which runs provenance is checked,
what happens with two protocols and none named, where an edited promise
scope is noticed — truths as line ranges of that commit; and one flow
question, the seven stations in order (scored mechanically, 0.63.0).

| `finalize.run` as it is | decisions found | stations named in order | calls | files opened |
|---|---|---|---|---|
| Haiku, agent 1 | 5/5 | 7/7 | 13 | 3 |
| Haiku, agent 2 | 5/5 | 7/7 | 13 | 4 |

Both agents went to `finalize.py` by its name, read it once, end to end,
and answered from it; the section comments and printed headers gave every
station and decision a findable label.

Consequences:

1. The candidate rule is **not supported**: a long entry point in one
   file, its stations labelled by numbered section comments, is followed
   perfectly by the weakest reader we use. The refactor was drafted but
   not applied — there is nothing the measure could show it improve.
2. What CS-015 Make the code findable by name already says holds: a name
   is what a reader searches for. Inside one file a section comment is
   such a name; across files only a function, file or constant name is
   found. The interpreter choice of round 3 was missed because it sat in
   another module with no label at all, not because it was inline.
3. Not added to the coding style.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round5/`.

## Round 6 (2026-10-07): fresh questions on parts nobody asked about or changed

How far does CS-015 Make the code findable by name carry beyond the places
it was built from? Five new questions per repo, in a person's words, on
code that no earlier round asked about and no rename touched
(uniagent: the month arithmetic of a deadline, whether a check applies to
a case, the trace format check, the sum of amounts, the comparison's
figures; labkit: runs still in progress, rebuilding the run list, a number
quoted in a note, a prompt read from a script without running it, two
writers of the run list at once). Haiku, two agents per repo.

| repo, Haiku | found | found as registered, strict paths | calls |
|---|---|---|---|
| uniagent | 10/10 | 8/10 | 15, 20 |
| labkit | 9/10 | 4/10 | 22, 31 |

Two scoring changes, both made after reading the answers and both
disclosed:

- **A truth widened:** "where is decided whether a check applies to an
  application?" — both uniagent agents answered `trigger.unmet_conditions`
  ("an empty list means the check applies"), not the registered
  `trigger_matches`, which decides one condition. Their answer is the
  better one.
- **Path tails accepted (0.63.1):** one labkit agent found all five places
  and wrote every path without the package folder (`runlog.py:1051`); a
  tail now counts when it names exactly one file in the repo.

The one real miss: "the list of all runs got lost — where can it be
rebuilt from the run folders?" One agent answered `runs.completed_runs`
(lists the completed run folders) instead of `runlog.reindex`, whose
first docstring line is "Append index rows for completed runs that have
none" — neither "rebuild" nor "list of runs" in it. A second instance of
round 3's finding: a first docstring line without the word a person
searches for, next to a neighbour that has it.

Consequences:

1. On untouched code the weaker reader finds 19 of 20 places: the two
   repos follow CS-015 well enough already; the gaps are single first
   docstring lines and near neighbours (`trigger_matches` /
   `unmet_conditions`, `reindex` / `completed_runs`).
2. Work list for labkit: `runlog.reindex`'s first docstring line names
   what it is for (rebuild the run index from the run folders).

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round6/`.

## Round 7 (2026-10-07): is the control flow understood better when the orchestrator reads as named steps?

The thesis (the user's): code is understood through its control and data
flow; the entry point should show that flow as a table of contents, the
functions below it how each station works. Tested on `finalize`, whose two
versions exist side by side: `ac97187` (one 210-line `run`, stations inline,
shared mutable `newest_dir`/`blocked`) and `30762d3` (0.63.2, `run` as seven
named station calls over a `Gate`, each station's inputs in its signature).
Behaviour identical, checked line by line on six real areas.

Instrument (0.65.0/0.65.1): ten behaviour questions with fixed choices,
scored by exact set, with the right choices **missed** and the wrong ones
**invented** counted apart — which stations run when no run is bound, which
examine the run the completion station chose, which can block, whether
warnings alone change the exit code, which situations end finalize before
any station and with which code, what an hours-tier protocol does with
provenance, what still runs after failing tests, whether a later station
can change the examined run, what a failing intent-check does.

Design against chance: both versions exported clean (`git archive`, without
`CHANGELOG.md` and `docs/usability/`, which name the refactor) under
neutral names assigned by seed 20261007 (`repo-a` = new, `repo-b` = old,
recorded before the run); three Haiku agents per version; each agent got
the questions in its own seeded order (`--shuffle`).

| version (blind) | right | missed | invented | seconds | calls | tokens |
|---|---|---|---|---|---|---|
| new, named stations (3 agents) | 30/30 | 0 | 0 | 87, 69, 77 | 13, 7, 11 | 50k, 49k, 53k |
| old, inline (3 agents) | 30/30 | 0 | 0 | 75, 69, 79 | 7, 7, 10 | 49k, 45k, 50k |

- **No difference.** Every agent answered every behaviour question right in
  both versions, missed nothing and invented no dependency; effort overlaps.
- **Why, from the transcripts:** in both versions every agent read
  `finalize.py` whole (one file, about 400 lines) and answered from it. At
  that size the inline version's numbered section comments carry the flow
  as well as named calls do — the same finding as round 5, now for
  understanding, not only finding.
- **What this does not test:** a flow that spans files and packages, where
  a reader cannot hold the whole in one read; a reader with a budget (a few
  reads, as a person skimming); a person.

Consequences:

1. The candidate rule ("the entry point exposes the workflow; data from
   earlier stages passes through parameters and return values") is **not
   supported by a measured difference** at this size, and is not added to
   the coding style on that ground. The refactor stands on CS-006 One
   function, one thing — and keep I/O at the edges (each decision testable alone), as before.
2. The thesis is not refuted either: the test case is small enough to read
   whole. A fair test needs a flow across files, or a reading budget.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round7/`.

## Round 8 (2026-10-08): a person, with a fresh assistant

Round 7's behaviour questions, answered by a person (the lab's author) at
the keyboard with `usability human` (0.66.0): one question at a time,
timed, the verdict only at the end. Each version got one of two matched
sets of five questions (two multi-select, three single-choice each), so no
question was answered twice; the order of versions was drawn by seed
20261008 (`repo-b` first). The person read the code in VS Code and could ask
a fresh Claude Code session started inside that version anything,
including how the code behaves; the number of such questions was recorded.
The assignment was revealed only after both passes. n = 1: a case, not a
measurement.

| pass | version | right | seconds | questions to the assistant |
|---|---|---|---|---|
| 1 (b1, b3, b6, b7, b9) | old, stations inline in one 210-line `run` | 2/5 | 292 | 2 |
| 2 (b2, b4, b5, b8, b10) | new, `run` as named station calls | 2/5 | 306 | 0 |

Agents on the same code and questions (round 7): 30/30 per version.

Where the answers went wrong — mostly too few, rarely invented:

- b1 (old): which stations report "no completed run to check" — 1 of 3
  named; b2 (new): which stations examine the chosen run — 1 of 4 named.
- b5 (new): which situations end finalize before any station — only "the
  settings block cannot be read", which stands in `run`; the two that sit
  inside `choose_protocol` were missed.
- b8 (new): after the area tests fail, "none" — the criterion-n station
  still runs; nothing in `run` says that a blocker does not stop the
  stations after it.
- b3 (old): "open fields" invented as able to block, "provenance" missed.
- The two questions answered with the assistant's help were right.

The person's own words (recorded as given):

- pass 1: "4 und 5 extrem schwer zu beantworten und 5 war nicht klar, was
  es meint" (b7, b9); "Kommentare, die den Orchestrator erklären, waren
  hilfreich, d. h. wo welche Stage ausgeführt wird; nur die Nummerierung
  mit a, b und dann wieder hoch zur nächsten Zahl war verwirrend".
- pass 2: "das File war kürzer, besser zu navigieren, aber ich hatte
  teilweise Probleme, nach den Modulen zu schauen, da sie importiert werden
  und dann bei bestimmter Stufe mit gecalled werden".

Consequences:

1. **Agent readers are no proxy for a person on flow questions.** 30/30
   against 4/10 on the same code; an agent reads the file whole in
   seconds, a person spends a minute per question and jumps. Every agent
   result in this document on understanding (rounds 5, 7) says nothing
   about people.
2. **A table of contents of named steps is not enough; the conditions
   are what was missed.** In both versions the person lost the answer
   where a condition sat one level down — the skip when no run is bound
   inside each station, the early exits inside `choose_protocol`, the fact
   that a blocker does not stop later stations. The candidate rule stands,
   sharpened by the person: the entry point shows the order of the steps
   **and** the conditions under which a step is skipped or the operation
   ends; one level down is how a step works, not whether it runs.
3. **Section comments that name the stage help; sub-numbers (2b, 4b)
   confuse.** A sequence is numbered flat.
4. One question (b9, "can a later station change which run the later
   ones examine?") was unclear to the person — an instrument flaw to
   reword before the next person.

Next, if wanted: a third version of `run` that keeps the named stations
and lifts their skip conditions and early exits into `run`, tested by
people from the lab (crossed order, reworded b9), not by agents.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round8-human/`.

## Round 9 (2026-10-08): the person reads the third version

The third version of `run` (0.66.1: the flow plan in its docstring, every
skip condition and early end visible in its body, flat numbers 0–7) read
by the same person, `run` only, against three questions — what happens
without a run, what provenance does at cost = hours, whether step 7 runs
after failing tests and with which exit code. Not timed; the person had
seen round 8's questions, so this is a reading, not a measurement.

- **No run:** read as "the protocol is not found" (step 0, exit 2). The
  function was called `run`, the experiment's execution is a "run", the
  variable `run_dir` — one word for three things.
- **cost = hours:** read as "provenance is checked". The condition was
  `if not provenance_owed(head):`, a negated helper name; the comment
  saying "only for cost = seconds" did not carry it.
- **Failing tests:** step 7 still runs if a run exists, then the report —
  right; the exit code was not stated (`return report(gate)` does not say
  it).

Changed in 0.67.0: `run` is `finalize_area`, `run_dir` is
`measurement_run` and the plan defines a measurement run; the provenance
condition stands literally (`if head.cost != "seconds":`); the last line
says what the report returns. Consequence for the coding style: the
earlier finding "a decision gets its own name" (round 3) has a limit for a
person — a one-line condition behind a negated name hides more than it
names; and one word for one thing applies to function names as much as
to concepts.

## Round 10 (2026-10-08): measuring the code-clarity agent before trusting it

A reviewer agent for agent-written code (`code-clarity`, dotfiles
`agents/code-clarity.md`): it reads one change and reports where the person
reviewing it would lose the thread — rules drawn from rounds 3, 8 and 9
(conditions one level down, one word for two things, a condition behind a
negated helper, two of a kind not told apart, sub-numbers, state a step
needs not in its signature, a copy of logic). Static evidence: it reports,
never blocks. Before it becomes routine: does it find planted defects, and
does it stay quiet on code without them?

- **Fresh case** (the one that counts — its names appear nowhere in the
  agent's rules): a small `shop/ship.py` written twice. The seeded version
  plants four defects — every skip condition inside the steps, "batch" for
  the function, the class and the day's orders, `if not needs_customs(…)`,
  a "Step 2b". The clean version lifts the conditions into the entry point,
  names apart, numbers flat.
- **Known case** (in-sample: the rules quote it): finalize's refactor
  ac97187→30762d3 (its end state has the three defects of round 9) and the
  fix 3a85427→d542e6c.

Sonnet, as the agent definition says; two agents per toy version, one per
finalize version.

| case | planted defects found | reports on code without them |
|---|---|---|
| toy, seeded (2 agents) | 4/4 and 4/4 | — (plus uneven check names, results passed through shared state, vague first docstring lines — all real) |
| toy, clean (2 agents) | — | 1 each, the same, and right: `write_label` raises `KeyError` on a delivered order without a street, so "a problem never stops the next step" is false — a bug planted by accident |
| finalize, seeded (in-sample) | 3/3 | — (plus "2b"/"4b" left in the module docstring, `Gate` for a collector while the gate is the whole command — both true of today's code) |
| finalize after the fix | — | 4, all true: `run_dir` beside `measurement_run`, "not a run of seconds" using "run" for the cost tier, `preflight.run` (renamed in 0.68.0, after that state), a first docstring line starting with "Run" |

- Every planted defect was found, in the fresh case too, by both agents.
- No report on the clean versions was invented; each pointed at something
  real. Two agents per version is too few for a false-alarm rate; what
  shows is that "verdict: 0 findings" is not forced (the agent may say it)
  and that its reports could all be checked in the code.
- What it found on today's code was fixed in 0.68.2.

Consequence: the agent is fit for routine use as static evidence, run by
an agent other than the author. Its `MODE: questions` backs the skill
`code-quiz` (dotfiles): on request, three behaviour questions for the
person, answers only after they answered.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/clarity-agent/`.

## Round 11 (2026-10-08): reconstructing an experiment months later — agents and the person

A different chain from the rounds before: not labkit's code but a lab's
experiment, protocol → script → run → number, as someone returning to it
would need it. Real case: uniagent areas 08 and 09. Eight questions, every
truth checked in the files — which of the four runs called the model, was
its code committed, where "no new false rejection" is decided, which file
holds the cases and gold, how the kept run is started, which run of 08
area 09 holds itself to, where it refuses otherwise, where the submission
branch is computed. Two Haiku agents; then the person (the lab's author,
who wrote these areas with agents a day earlier), timed, with a fresh
assistant in the repo allowed.

| reader | right | seconds | calls / files | questions to the assistant |
|---|---|---|---|---|
| Haiku, agent 1 | 8/8 | 163 | 28 / 12 | — |
| Haiku, agent 2 | 8/8 | 133 | 26 / 11 | — |
| the person | 1/8 | 414 | — | 2 |

The agents' effort is the highest of any round (earlier 7–25 calls): no
agent opened the area's README; both listed the tree with `find`, opened
all four run folders' config, metrics and completion, read the area
script and both measure modules whole. Everything was found, nothing was
in one place.

The person's misses, each read against the repo:

- **Which run called the model** (r1): picked the newest. `config.json`
  says `derived_from: null` for the one that did; `runs.tsv` and `runlog
  <area>` (which lists only live runs) show no such thing.
- **Was the code committed** (r2): picked yes, while noting "ich sehe
  uncommitted patch". The run says `git: 22215c2+dirty` and holds a
  7.8 KB `uncommitted.patch`; nothing says in plain words "this run's
  code was not committed".
- **Where c2 is decided** (r3h, 158 s, one assistant question): picked
  the submission branch. The chain is area `evaluate_rows` → `positions.
  evaluate` → `comparison.evaluate_rows` (217 lines, the condition in an
  inner helper, `c2_pass` set at line 572) — four functions named
  `evaluate`/`evaluate_rows` in three modules. The person, after the
  assistant laid the chain out: "das ist extrem kompliziert mit dem
  Verstehen, was passiert". The assistant's own route worked in three
  greps: the metrics key as a string leads to the one place that sets it.
- **Which file holds the cases** (r4): picked the hand labels. The
  protocol's Data field names the file; the person went to the script,
  where it is `ITEMS`, next to `LABELS` and `AREA_06_ROWS`, and the file
  lives under area 05.
- **How the kept run is started** (r5): picked `--derive`. The script head
  lists six invocations; the kept one says "full run (Cost hours: `runlog
  start -- …`)". No run records the command it was started with.
- **Where 09 refuses** (r7h): picked `main`, which calls the function
  that raises — a near miss.
- **The submission branch** (r8h): found `SUBMISSION = {True: …}` in
  `positions.py`, then picked `comparison.evaluate_rows`.
- The area README is the stamped template, placeholders unfilled, and its
  contract text says "the formula stands once, in scripts/01_measure.py"
  — not true for this area, whose formula is in `src/measure/`.

The person's words: "das meine genaue measure.py hat geholfen, aber manche
Referenzen etc. sind zu verwirrend".

Consequences (a case, n = 1; the agents' effort says the same):

1. **What a run is must stand in one listing**: model run or derived from
   which, code committed or not, the command that started it. Today it is
   spread over `config.json` keys (`derived_from`, `git …+dirty`) and a
   patch file, and the command is not recorded at all. A labkit change.
2. **The registered keys lead to one function by grep**, and the area
   says where: the script head (and the README) names the file and
   function that sets the metrics keys. Delegation chains that reuse one
   name (`evaluate_rows` → `evaluate` → `evaluate_rows`) are what "one
   word, one thing" forbids, across modules too. A coding-style rule and
   a uniagent change.
3. **The stamped README must not say what is not so**: a template text
   that asserts where the formula is, left unfilled, misleads more than no
   README. Template rollout.
4. The data an area measures on is named in the protocol (Data / scope);
   the person did not look there. The script's constant should carry the
   word a person searches (`CASES_WITH_GOLD`, not `ITEMS`).

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round11-reconstruct/`.

## Round 12 (2026-10-08): after the changes of round 11 — agents only

What changed since round 11: labkit 0.69 records a run's command and
`runlog <area>` lists the finished runs with what each is; uniagent's
position areas keep their data under `data/` as symlinks with constants
named for what they hold, the script heads of 08 and 09 say where each
registered key is set, README 08 is filled; CS-016 The experiment area
reconstructs itself in the coding style. The person cannot be measured
again on questions they have seen; two fresh Haiku agents, same eight
questions, same seeds' shuffles.

| reader | right | calls / files | opened the README | used `runlog` |
|---|---|---|---|---|
| before (round 11), agents 1–2 | 8/8, 8/8 | 28/12, 26/11 | no, no | no, no |
| after, agents 3–4 | 7/8, 8/8 | 27/10, 39/14 | yes, yes | no, yes |

- **No gain in agent effort**, and one miss (agent 3 answered "python
  scripts/01_measure.py" for the kept run, not `runlog start -- …`). The
  agents now open the README, which has content; the one that ran
  `runlog` still read every run folder as well. An agent reads
  exhaustively whatever the area says — effort does not fall when the
  facts move into one place, because it was never the agent's problem.
- The changes were made for the person (round 11: 1/8). Whether they
  help a person is untested: the author knows these questions now. A
  fair test is the same question types on area 12 (which got the same
  treatment) with the author, or area 08 with someone else from the lab.
- Not done: the chain `evaluate_rows` → `evaluate` → `evaluate_rows`
  across `src/measure/` stays — renaming it touches every area's script
  and the area another session is running today; a separate task.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round12-after/`.

## Round 13 (2026-10-08): the person on area 12, after the treatment

Area 12 got the round-11 treatment (data under `data/` as symlinks, named
constants, the script head saying where each key is set) but not a filled
README; `runlog <area>` now lists the finished runs. The same eight question
types as round 11, answered by the same person at the keyboard with a fresh
assistant, timed. Second pass for the person: practice and the assistant
confound the comparison.

| | right | seconds | questions to the assistant |
|---|---|---|---|
| round 11, area 08, before | 1/8 | 414 | 2 |
| round 13, area 12, after | 7/8 | 817 | 10 |

- **Right where it was wrong**: which runs were fresh (`runlog` lists it),
  whether the code was committed, which file holds the cases (now a link
  under the area's own `data/`), how the run is started, which run of 09
  is the anchor. Each took 54–155 s and at least one assistant question —
  found, not fast.
- **The one miss is the same miss**: "where is c2 decided" — picked
  `positions.evaluate`, the middle of the chain `evaluate_rows` →
  `evaluate` → `evaluate_rows` that was not renamed (173 s, the longest).
- The person's words: "es gibt Protokolle, measure und auch runs mit ihren
  configs — teilweise verwirrend, wo man anfangen soll"; and on
  `src/measure/positions.py:evaluate` ("[C4] [C5] [A4] of p"): "das klingt
  nach einem bestimmten Protokoll, ist aber hier im allgemeinen Code".

Consequences:

1. What was changed is found; the gain in right answers cannot be
   separated from practice and ten assistant questions (n = 1, second
   pass). Time went up, not down: an area still has no entry point that
   says where to start — the protocol, the script and the runs each tell
   part. The area README is that entry point; area 12's was the stamp.
2. The chain of three functions sharing one name across modules cost the
   only miss, twice now. Its rename stays the next uniagent task.
3. **Protocol ids in shared code** (uniagent): `src/measure/positions.py`
   sets `c4_pass`, `c5_…`, `a4_…` and names them in docstrings — the ids
   of one protocol, in a module seven areas share. Shared code should
   name the thing (`binding_case_rejected`), and each area map it to its
   own id. A design question for the lab, not a labkit change.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/navigation-round13-human-area12/`.
