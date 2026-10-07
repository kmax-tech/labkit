"""Suite-wide isolation: no test writes outside a temporary directory.

`llm.complete` takes an endpoint lease; without this, every test that calls
it wrote into the real ~/.labkit/leases, and failed with PermissionError
where home is read-only (review 2026-10-07). Tests that need their own
lease directory still set LABKIT_LEASE_DIR themselves.
"""
import os
import tempfile

os.environ["LABKIT_LEASE_DIR"] = tempfile.mkdtemp(prefix="labkit-test-leases-")
