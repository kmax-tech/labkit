# A lab's templates and its pin come from one ref (2026-10-27)

**Problem.** `labkit-init lab` writes two things that must agree: the
stamped files (`AGENTS.md`, the editor settings, …) and the pin in
`requirements.txt`. The pin named the release tag of the installed
version; the templates were read from wherever the package lives. From a
source checkout (an editable install) that is the working tree — main,
ahead of the tag. A lab scaffolded on 2026-10-27 through the house's
fallback (labkit's own development venv) got an `AGENTS.md` that tells the
agent `labkit-init exp NAME --repeat-cost <cost> --kind <kind>`, pinned to
`v0.103.0`, whose `labkit-init exp` knows only `--cost seconds|minutes|hours`.
The 0.88.7 guard (`pinned_ref`: installed metadata against the checkout's
`pyproject.toml`) did not see it: both said 0.103.0, because the repeat-cost
break was built but not released.

**Decision.** `check_lab_pin` at the entry of `lab`: from a checkout, the
lab templates (`LAB_TEMPLATES`) in the working tree are compared with the
ref the pin names (`lab_templates_off_ref`, byte for byte through
`git show <ref>:<path>`); any difference refuses and names the templates.
A ref the checkout does not hold (a tag not fetched) refuses too — a check
that could not run blocks. An installed release reads its own templates;
nothing is compared.

**Rejected.**
- *Release and be done.* It closes today's gap; the next commit to a
  template opens it again.
- *Pin the checkout's HEAD instead of the tag.* Uncommitted template edits
  still leak, and an unpushed commit does not install.
- *Compare the whole package.* A code-only commit after the tag would
  refuse a stamp whose files are identical — a false blocker.

**Limits.** The texts `scaffold.py` holds inline (`GITIGNORE`,
`REQUIREMENTS`) are not compared. `labkit-init exp` is not held to the
lab's pin: in a lab with its own venv the pinned labkit stamps its areas.
The six tests that only need a lab as a fixture stamp it through
`stamp_lab`, which compares nothing; `main(["lab", …])` is tested with the
comparison replaced.
