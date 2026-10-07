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
