Fourth version, 2026-11-12, after the whole table was read under the third. No reading has used it yet. The third version (`object-property-definitions-3.md`) stays as the state the 297 rows were read under. What changed, by the author's answer: how exact a row is cut is stated apart from the property (`unit`, rule 3; "bundle" is no answer in place of a property any more); a required object or element that is missing is completeness, binding is between things that are there (rule 4); access refused, a timeout and a failure of git are limits of the execution (rule 7); a text rebuilt from a commit and a patch is a version of its own. Rule 4 on a registered part, and rules 8 and 9, are the author's rulings of the same day on three further questions. No value was added.

For each cause, read the condition the code tests and state three things apart: the objects the condition tests, each with its role and its version, and the property or relation tested.

**Judge by the condition.** State what the code tests and what it compares. Do not judge by the way out the message offers, nor by the wording of the message. Do not ask which side of a comparison is wrong: a comparison is described by its two sides and nothing else.

## Objects

| Object                       | Holds                                                                                                           |
|------------------------------|-----------------------------------------------------------------------------------------------------------------|
| protocol                     | the protocol file: its text, head, promise block, prompt block, `[result]`                                      |
| run record                   | a run directory: config, metrics, the kept outputs and their rows, the patch, the kept copies                   |
| area code                    | the area's scripts and the helpers they import                                                                  |
| area checks                  | the area's tests and its analysis check                                                                         |
| audit and review records     | audit records, their findings and decisions, decision reviews, report reviews, handovers                        |
| generated block or line      | a block or line labkit writes into the protocol or the report                                                   |
| report                       | the report file and its sentences outside a generated block                                                     |
| text beside the protocol     | notes, the README                                                                                               |
| repository and working state | git's history, index and working tree as such, hooks, the installation, files labkit keeps while a command runs |

## Roles

An object is listed for the role it plays in the condition, one entry per role. The roles follow from the property:

| Property or relation                                           | Roles                                                                                                                          |
|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| completeness, readability, form, uniqueness, inner consistency | `tested`: the one object                                                                                                       |
| agreement                                                      | `side`, twice                                                                                                                  |
| binding                                                        | `holds the reference`, `referred to`                                                                                           |
| audit coverage                                                 | `covering record`, `state covered`; where a decision and the review that confirms it are both read: `decision`, `confirmation` |
| order in time                                                  | `earlier`, `later`                                                                                                             |
| result of an executed area check                               | `tested`: the area checks                                                                                                      |

Three rules of counting:

1. **One entry per role.** Several things of one kind in the same role (three decision reviews, every run of the area) are one entry. One kind in two roles is two entries: an audit record as `decision` and a review record as `confirmation` are both "audit and review records", listed twice.
2. **A precondition is no object.** What must be there or read before the condition can be tested, or decides whether the check applies at all, and whose content the condition does not test, goes into `preconditions`, not into `objects`. Example: the head registers a report, and the condition then tests whether a first measurement reads — the protocol is a precondition, the run record is the object.
3. **An object decided at run time.** Where the code fixes the object only when the check runs (any file of a bundle), answer `"object": "decided at run time"` with the kinds it can be in `candidates`, as far as you read them. The kind may stay open: do not pick one. Its role is stated all the same.

## Version

For each object, one of these; where none describes it, say in words what the version is and do not press it into one:

| Version              | Means                                                                                                                              |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------|
| as it stands         | the file as the check's file state holds it now; where the working tree and the index are compared or differ, say which of the two |
| as a commit holds it | the file in a named commit: say which (the commit a run recorded, HEAD)                                                            |
| as a run recorded it | what a run's record keeps of it (a digest, a kept copy, the patch)                                                                 |
| rebuilt              | a text put together from several sources: say from which (the commit a run recorded with the run's kept patch applied)             |

Where two versions of one object are compared, the object has two entries, one `side` each.

## Property or relation tested

A property belongs to one object, a relation to two.

| Value                            | The condition asks                                                                                            | Not this value                                                                                                      |
|----------------------------------|---------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| completeness                     | is every owed part of the object there and filled                                                             | a mark or a file that is there and records a state (see rule 4)                                                     |
| readability                      | can the object, which is there, be read and interpreted in its format                                         | a value that reads and has a form its place does not take (form)                                                    |
| form                             | does a value, or a file, have one of the forms its place allows                                               | a file that does not parse (readability); a value that is missing (completeness); where a reference leads (binding) |
| uniqueness                       | is there exactly one where exactly one is asked for                                                           | two things compared and found equal (see rule 5)                                                                    |
| inner consistency                | do two parts of the same object contradict each other                                                         | the same part written twice, values not compared (uniqueness)                                                       |
| agreement                        | do two objects, or two versions, say the same — in either direction                                           |                                                                                                                     |
| binding                          | does a reference in one object lead to a thing that is there and is of the kind the place takes               | the form of the reference alone, where nothing is looked up (form)                                                  |
| audit coverage                   | does an audit or review record belong to the state as it is, and release it                                   |                                                                                                                     |
| order in time                    | did one thing stand before another: the condition reads two points in time, or an order of commits or records | two states read now and combined, where no time or order is read                                                    |
| result of an executed area check | did a check of the area run, and what did it return                                                           |                                                                                                                     |

"Form" is narrow. It holds two things: the pattern a value must match in its place (a field that takes a record's file name), and the kind a file must be (a regular file, not a symbolic link). It is no place for whatever is "not allowed".

"Uniqueness" holds a field or an id written twice, and a choice that needs exactly one candidate (several protocol files and none named).

## Rules

1. **Something that does not read.** Where the condition is that a file does not read or parse, the property is readability of that file — also when the message says a further check could not run because of it. The check that was prevented is another check.
2. **Where it is tested, where it is told.** State both places with `path:line`: `tested_at`, where the code evaluates the condition, and `told_at`, where the finding is built. They may be the same line. Describe the condition at the place where it is tested. That a site tells a condition tested elsewhere is no property of the condition and changes none of the three answers.
3. **The unit of a row is stated apart from its property.** The code decides, not the words of the row. Follow the row to the code that tests, and answer `unit`:
   - `"one"`: one test stands behind the row — also when the telling site passes its text on without reading it.
   - `"aggregated"`: several tests stand behind it and all have the same objects, the same property and the same outcome. List them in `bundled` and classify the row.
   - `"mixed"`: several tests that differ in objects, property or outcome. List them in `bundled`, each with its property, and give the row no property of its own (`"fits": "mixed"`).
   - `"joined"`: the finding is told only when several conditions hold together. List each in `bundled` and say that they are joined: none of them is a finding that triggers alone.
   - `"open"`: the site catches by an error's type and the tests behind it are no closed list. Say what was found.

   That a reader refuses a file is no property. Behind "does not read" look at what the reader refuses: text that does not parse is readability, a required key that is missing is completeness, a value of a form its place does not take is form.
4. **Missing is completeness; binding is between things that are there.** A required object or element that is missing is completeness — a file a run owes, a registered report, a field. Binding asks whether things that are there are assigned to each other: a reference that leads to a thing of the wrong kind, a thing that cannot be assigned to the place that names it. Agreement asks whether a thing that is there differs from what was recorded, and also whether one side holds what the other registers: a part the protocol registers that a run, or the area's code, does not hold is agreement with the registration, since both sides are needed to tell it. It is completeness of the run record only where the run record's own format asks for the part. A condition that fires because a mark, a flag or a file is there tests a state the mark records, not completeness: say which state; there is no value "presence", and if no value names that state, rule 6 holds. Missing is not completeness by itself: ask whether the missing thing is the requirement this condition tests, or only a technical precondition of another check (no git repository, so a comparison cannot run). The second is a limit of the execution (rule 7).
5. **The operator is not the property.** A condition is not classified by the comparison it is written with. A test for equality is part of many checks: of agreement, where two things should say the same, and of others, where a finding is told because two things are the same. State what the test establishes about the objects. "Equality" is no value, and a test that fires on sameness is not uniqueness.
6. **No forcing.** The values need not take every cause. Where none fits, answer `"fits": "no"` and say in a few words what the condition tests instead. Where a value fits only loosely, `"fits": "weak"`. Where you are not sure, `"unsure": true` and name the alternative.

7. **A limit of the execution is no property of the object.** Where the check could not be carried out — access to a file refused, a timeout, git fails for a technical reason, the check's own procedure cannot evaluate a text that reads and parses — nothing is shown about the object. That is the check's outcome. Answer the objects and the property of the check that could not run, and set `"check_limit": true`. A limit is not assumed either: a file the condition requires and that is missing is a condition about the object (rule 4).

8. **An open finding does not make a record incomplete.** An audit finding that is documented in full and not decided leaves its record complete. A condition that reads whether a finding is decided or released tests the decision or release status — the half of audit coverage that asks whether the record releases the state.
9. **An object is what this check tests.** The protocol's claim is an object of a check only where that check itself judges or compares it. Where a gate reads only review records, the claim is the review's object and at most a precondition of the gate.

10. **A thing read that is in no object of the list** is named in plain words ("input data", "model profile") with `"object": "not listed: …"`. Its place in the list is open; what it is must be said.

## Answer

One JSON object per cause:

```json
{"n": 1,
 "objects": [{"object": "protocol", "role": "side", "version": "as it stands"},
             {"object": "run record", "role": "side", "version": "as it stands"}],
 "preconditions": [],
 "property": "agreement",
 "fits": "yes",
 "unsure": false,
 "alternative": "",
 "tested_at": "path:line",
 "told_at": "path:line",
 "unit": "one",
 "bundled": [],
 "check_limit": false,
 "condition": "one sentence: what the code tests"}
```

An object decided at run time: `{"object": "decided at run time", "candidates": ["protocol", "area code"], "role": "tested", "version": "as it stands"}`.
