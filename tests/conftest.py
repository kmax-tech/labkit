"""Suite-wide isolation: no test writes outside a temporary directory.

`llm.complete` takes an endpoint lease; without this, every test that calls
it wrote into the real ~/.labkit/leases, and failed with PermissionError
where home is read-only (review 2026-10-07). Tests that need their own
lease directory still set LABKIT_LEASE_DIR themselves.
"""

import os
import tempfile

os.environ["LABKIT_LEASE_DIR"] = tempfile.mkdtemp(prefix="labkit-test-leases-")


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
