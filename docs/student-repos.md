# Student repos

How a student thesis repo gets labkit, and how it moves to a newer one.
Decided 2026-10-07: student repos pin labkit like the lab repos; nothing is
copied into them.

## Getting labkit

`labkit-init lab <DIR>` (since 0.78.0) lays the repo out and writes a
`requirements.txt` that pins labkit on GitHub at the release tag of the
installed version:

```
labkit @ git+https://github.com/kmax-tech/labkit.git@v<version>
```

The student installs it once:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

The commands (`protocol-check`, `intent-check`, `scope-sha`, `runlog`, …)
then live in `.venv/bin/`; scripts import `from labkit.run import llm, runlog`.
The lab standard comes with the pin (`python -m labkit.formats.rules show LAB-nnn`),
nothing is copied. Until the tag is pushed the pin does not install;
`--labkit-ref <commit>` pins a pushed commit instead.

The author's house keeps a separate thesis starter
(`local-init.py --thesis` in the dotfiles) that adds house
material around the same pin; it stays in the house layer.

## Moving to a newer version

Never automatic — the pin exists so nothing shifts under a running
experiment.
`labkit-check` says when the installed labkit lags the pin or the source has
a newer tag; it reports and changes nothing.

1. Change the pin line in `requirements.txt` to the new tag.
2. `.venv/bin/pip install -r requirements.txt`.
3. `.venv/bin/labkit-hooks install` — the hooks the repo carries come from
   the installed version; `labkit-hooks check` names them stale until then.
4. Run the tests, commit `requirements.txt` and the reinstalled hooks. The
   commit history then says which labkit produced which run.

The student or the supervisor (a commit in the student's repo) can do it.
A breaking release names in `CHANGELOG.md` the last version that reads the
old formats; a repo with frozen protocols in an old format stays on its pin
until new work starts there. Since 0.71.0 `frozen = true` owes the
`[[promise]]` tables and a run records every registered constant
unchanged; an area frozen under 0.70.0 or earlier is checked and
reproduced with that version — its tables are not added afterwards, that
would be a new registration.

## What it rests on

- **The tag is on GitHub.** pip installs from the remote; a tag that exists
  only on the author's machine breaks every install
  (`git push origin --tags`).
- **The repo is readable for the student**: public, or a collaborator
  invitation plus a token for pip.
- **Every release bumps the version.** pip does not reinstall a git source
  whose version number did not change.

## The example experiment

`experiments/example-stance/` in the starter carries the TOML head and
C/A/B ids; its script reports `c1_pass` and `a1_pass`. Its two runs from
2026-08-25 were recorded before runs carried their protocol and a completion
record: labkit lists them as `unreadable` with the reason and never picks
them (read them with labkit 0.47). A student's first `run_experiment.py`
starts a fresh `runs.tsv`.

`labkit-init exp <name>` stamps the protocol's id; a protocol copied by
hand still carries `id = "<protocol-id>"` and binds no run — stamp a fresh
area instead of copying one.
