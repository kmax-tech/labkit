# Note 2026-10-19 — the layers as packages, the large modules split

The history behind the package layout. The layout itself stands in
`docs/architecture.md` (the layer table names each folder) and is held by
`tests/test_architecture.py`.

## Problem

All 37 modules, three templates, two agent instructions and the field
guide lay flat in `labkit/`. The architecture had five layers on paper and
none in the file tree, so a reader opening the folder saw an alphabetical
list. Four modules had grown past 1300 lines, each holding several
questions: `runlog` (2095), `usability` (1476), `code_check` (1395),
`protocol_check` (1331).

## Solution

- **One folder per layer:** `formats/`, `run/`, `checks/`, `gates/`,
  `tools/`, `probes/` (the cold-agent probes, split off the tools: one
  purpose the other tools do not share). The assets sit beside them in
  `templates/`, `agents/`, `docs/`, read through `labkit.PACKAGE_DIR`.
- **All modules moved, the eight that scripts import included.** Keeping
  `runlog`, `batch`, `llm`, `runs`, `promises`, `recheck`,
  `protocol_block`, `standard_contract` flat at the top was considered and
  rejected by the author: the house builds breaks, not legacy paths, and a
  top level of mixed layers is the confusion the move removes.
- **Each large module split along a block it already had,** no behaviour
  changed: `runlog` → `provenance`, `start_check`, `runlog_command`;
  `protocol_check` → `protocol_history`, `protocol_report`; `code_check` →
  `code_scan`, `gate_label_scan`, `import_check`, `prompt_check`;
  `usability` → `usability_score`, `usability_command`. A name used across
  modules lost its underscore.

## Notes

- **An editable install hides a missing package.** `packages = ["labkit"]`
  shipped none of the layer packages; the suite stayed green because the
  editable install finds the folders on disk, while a wheel held only the
  assets. `pyproject.toml` names every package and
  `tests/test_architecture.py` (`Packaging`) holds the list to the folders
  with an `__init__.py`.
- **A stamped test is code that runs elsewhere.** The lab template's guard
  test compared `mod.__name__` with `labkit.runlog`; the suite reads the
  templates but ran none of the stamped tests, so every newly stamped repo
  would have started red. `tests/test_scaffold.py` now stamps a lab and runs
  its tests.
- **Tests that loaded a module by file path** (`spec_from_file_location`,
  a leftover from the time the modules were scripts) broke on each move and
  hid types from pyright; they import the module now, and pyright found two
  Optionals the tests unpacked unchecked.
- **A mock patches where the name is looked up.** After a split,
  `mock.patch.object(runlog, "_env_state")` fails loud (no such attribute);
  the patch goes to the module that calls it (`provenance.env_state`).
