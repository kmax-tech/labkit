# labkit's commands to copy and run: `just` lists them, `just <name> ARGS` runs one.
# Install once: brew install just. The same in VS Code: .vscode/launch.json.

venv := ".venv/bin"

# list the recipes
default:
    @just --list

# the commit gate: ruff, format, pyright, pytest (the hook itself, one home)
check:
    .githooks/pre-commit

# the suite, or the tests matching NAME
test name="":
    {{venv}}/pytest -q {{ if name != "" { "-k " + quote(name) } else { "" } }}

# stop at the first line of the tests matching NAME (pdb)
test-start name:
    {{venv}}/pytest -q -k {{quote(name)}} --trace

# run the tests matching NAME, open pdb where one fails
test-fail name:
    {{venv}}/pytest -q -k {{quote(name)}} --pdb

# a labkit module under pdb from its entry point: just debug audit AREA --mode preflight
debug module *args:
    {{venv}}/python -m pdb -m labkit.{{module}} {{args}}

# what one run of a command called, cut to labkit: just calltree protocol-check --contract
calltree command *args:
    {{venv}}/labkit-calltree {{command}} -- {{args}}

# runs the module FILE, not -m: with -m, --include_files keeps nothing (viztracer 1.1.1);
# the leading - opens the timeline even when the command exits non-zero

# the run as a timeline in the browser: just timeline protocol_check --contract
timeline module *args:
    -{{venv}}/viztracer --quiet --include_files ./labkit -o /tmp/labkit-timeline.json -- labkit/{{module}}.py {{args}}
    {{venv}}/vizviewer /tmp/labkit-timeline.json
