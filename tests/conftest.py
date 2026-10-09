"""Suite-wide isolation: no test writes outside a temporary directory.

`llm.complete` takes an endpoint lease; without this, every test that calls
it wrote into the real ~/.labkit/leases, and failed with PermissionError
where home is read-only (review 2026-10-07). Tests that need their own
lease directory still set LABKIT_LEASE_DIR themselves.

Git's own variables are dropped for the same reason: inside a git hook (the
pre-commit hook runs this suite) git exports GIT_DIR, GIT_INDEX_FILE and
friends, and every `git init` / `git config` / `git commit` a test aims at its
temporary repo then lands in the real one. Run from a worktree on 2026-10-09,
the suite set `core.bare = true` and a local user `t <t@t>` in labkit's own
.git/config, tagged a test commit `v1.0.0` and committed onto the worktree's
HEAD (`tests/test_git_env_isolation.py`).
"""

import os
import tempfile

os.environ["LABKIT_LEASE_DIR"] = tempfile.mkdtemp(prefix="labkit-test-leases-")
for _name in [n for n in os.environ if n.startswith("GIT_")]:
    del os.environ[_name]


# A debugger stops where a test fails, not inside pytest's report: with
# LABKIT_TEST_RAISE=1 (set by the VS Code debug configs in .vscode/launch.json)
# a failure propagates out of pytest, and the debugger's "Uncaught Exceptions"
# breakpoint lands on it — the IDE's counterpart of `pytest --pdb`.
if os.environ.get("LABKIT_TEST_RAISE") == "1":
    import pytest

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[object]) -> None:
        """Re-raise the test's exception so the attached debugger sees it uncaught."""
        if call.excinfo is not None:
            raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[BaseException]) -> None:
        """Re-raise pytest's own errors for the same reason."""
        raise excinfo.value
