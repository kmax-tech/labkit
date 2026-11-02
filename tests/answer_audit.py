"""`labkit-audit` with the model's answer given — the real command in a lab
repo, only `llm.complete` replaced, for tests that run each step as a
person runs it (`tests/test_repair_paths.py`).

    python answer_audit.py ANSWER_FILE -- ARGS...

ANSWER_FILE holds the answer the model would give; ARGS are labkit-audit's
own (`AREA --mode analysis`, `AREA --report-review REPORT`, `AREA --review
--record FILE`). Exits with labkit-audit's exit code."""

import sys
from pathlib import Path

from labkit.gates import audit

answer = Path(sys.argv[1]).read_text(encoding="utf-8")
args = sys.argv[sys.argv.index("--") + 1 :]
audit.llm.complete = lambda alias, prompt, **kw: answer
audit.llm.takes_max_tokens = lambda alias: True
sys.exit(audit.main(args))
