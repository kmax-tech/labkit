# Student repos

How a student thesis repo gets labkit, and how it moves to a newer one. Decided 2026-10-07: student repos pin labkit like the lab repos; nothing is copied into them. A student repo is a lab repo: the same layout, standard and checks.

## Getting labkit

`labkit-init lab <DIR>` (since 0.78.0) lays the repo out and writes a `requirements.txt` that pins labkit on GitHub at the release tag of the installed version:

```
labkit @ git+https://github.com/kmax-tech/labkit.git@v<version>
```

The student sets it up once, from the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/labkit-hooks install
.venv/bin/pip freeze > requirements.lock
```

The hooks hold every commit to the checks; without them nothing stops an unchecked commit. The lock names the environment every run records; without it a run records `unpinned`. Commit `requirements.txt` and `requirements.lock`.

The commands (`protocol-check`, `intent-check`, `scope-sha`, `runlog`, …) then live in `.venv/bin/`; scripts import `from labkit.run import llm, runlog`. The lab standard comes with the pin (`python -m labkit.formats.rules show LAB-nnn`), nothing is copied. Until the tag is pushed the pin does not install; `--labkit-ref <commit>` pins a pushed commit instead. Run from a source checkout, `labkit-init lab` refuses unless the checkout's lab templates are those of the ref it pins, so a repo never gets an `AGENTS.md` its labkit does not match.

`labkit-init exp <name>` stamps an area and its protocol's id; a protocol copied by hand still carries `id = "<protocol-id>"` and binds no run — stamp a fresh area instead of copying one.

The author's house keeps a thesis starter (`local-init.py --thesis` in the dotfiles): it runs `labkit-init lab` and adds thesis material beside it (journal, outline, Overleaf hand-over, first reads); it stays in the house layer.

## Files are shared through git

The supervisor works from a clone of the student's repo. PDFs and data the work depends on are real files in the repository, never symbolic links into a personal folder, which the clone cannot open. Large or licensed raw data is not committed; student and supervisor agree where it lives.

## The audit model

`labkit-audit` calls the `opus` alias of `models.toml`, which `labkit-init lab` stamps with `backend = "claude-cli"`: the `claude` command-line tool, installed and logged in. A student without it has two ways:

- **Claude access** — through the lab or their own account; then nothing changes.
- **Another model for the audits** — an alias for a model the student can reach (a lab server through `ollama`, for example) in `models.toml`, set as `[audit] model = "<alias>"` before the first audit. The audit records name the model, so the supervisor sees which model checked; a weaker model checks less.

## Moving to a newer version

Never automatic — the pin exists so nothing shifts under a running experiment. `labkit-check` says when the installed labkit lags the pin or the source has a newer tag; it reports and changes nothing.

1. Change the pin line in `requirements.txt` to the new tag.
2. `.venv/bin/pip install -r requirements.txt`.
3. `.venv/bin/pip freeze > requirements.lock` — until then the lock names the old version, and `labkit-check` reports the pin as stale.
4. `.venv/bin/labkit-hooks install` — the hooks the repo carries come from the installed version; `labkit-hooks check` names them stale until then.
5. Where the release changed the stamped `AGENTS.md` (its `CHANGELOG.md` entry says so): `mv AGENTS.md AGENTS.md.old && .venv/bin/labkit-init lab .` writes the new one (it writes only files that are absent); carry the repo's own additions over from `AGENTS.md.old`, then delete it.
6. Run the tests, commit `requirements.txt`, `requirements.lock`, the reinstalled hooks and `AGENTS.md`. The commit history then says which labkit produced which run.

The student or the supervisor (a commit in the student's repo) can do it. A breaking release names in `CHANGELOG.md` the last version that reads the old formats; a repo with frozen protocols in an old format stays on its pin until new work starts there. Since 0.71.0 `frozen = true` owes the `[[promise]]` tables and a run records every registered constant unchanged; an area frozen under 0.70.0 or earlier is checked and reproduced with that version — its tables are not added afterwards, that would be a new registration.

## What it rests on

- **The tag is on GitHub.** pip installs from the remote; a tag that exists only on the author's machine breaks every install (`git push origin --tags`).
- **The repo is readable for the student**: public, or a collaborator invitation plus a token for pip.
- **Every release bumps the version.** pip does not reinstall a git source whose version number did not change.
