Fixed for the sample of 2026-11-12; not changed while the sample is read.

For each cause, read the condition the code tests at the named function and state three things apart: the objects the condition reads, the version of each object, and the property or relation it tests.

**Judge by the condition.** State what the code tests and what it compares. Do not judge by the way out the message offers, nor by the wording of the message. Do not ask which side of a comparison is wrong: a comparison is described by its two sides and nothing else.

## Objects

One object, or the two that are compared (seldom three).

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

## Version

For each object, one of:

| Version              | Means                                                                   |
|----------------------|-------------------------------------------------------------------------|
| as it stands         | the file as the check's file state holds it now (working tree or index) |
| as a commit holds it | the file in a named commit: say which (the commit a run recorded, HEAD) |
| as a run recorded it | what a run's record keeps of it (a digest, a kept copy, the patch)      |

Where two versions of one object are compared, name the object twice, once per version.

## Property or relation tested

A property belongs to one object, a relation to two.

| Value                            | The condition asks                                                                              |
|----------------------------------|-------------------------------------------------------------------------------------------------|
| completeness                     | is every owed part of the object there and filled                                               |
| readability                      | is the object there, and can it be read and interpreted in its format                           |
| inner consistency                | do two parts of the same object contradict each other                                           |
| agreement                        | do two objects, or two versions, say the same — in either direction                             |
| binding                          | does a reference in one object lead to a thing that is there and is of the kind the place takes |
| audit coverage                   | does an audit or review record belong to the state as it is, and release it                     |
| order in time                    | did one thing stand before another                                                              |
| result of an executed area check | did a check of the area run, and what did it return                                             |

## Three rules

1. **Something that does not read.** Where the condition is that a file does not read or parse, the property is readability of that file — also when the message says a further check could not run because of it. The check that was prevented is another check.
2. **A forwarded error.** Where the site only passes on an error text raised elsewhere and its own code does not tell the causes apart, say so (`"forwarded": true`) and describe what the site itself tests.
3. **No forcing.** Where no value fits, answer `"fits": "no"` and say in a few words what the condition tests instead. Where a value fits only loosely, `"fits": "weak"`. Where you are not sure, `"unsure": true` and name the alternative.

## Answer

One JSON object per cause:

```json
{"n": 1,
 "objects": [{"object": "protocol", "version": "as it stands"},
             {"object": "run record", "version": "as it stands"}],
 "property": "agreement",
 "fits": "yes",
 "unsure": false,
 "alternative": "",
 "forwarded": false,
 "condition": "one sentence: what the code tests, with path:line"}
```
