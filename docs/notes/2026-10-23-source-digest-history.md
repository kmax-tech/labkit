# Note 2026-10-23 — source digest history

The source digest helper was named `sha256_file` until 2026-10-23. The
name described an algorithm and a file, although the helper also covered
directory sources. It became `source_digest` (`e1b2f67`) to match its
responsibility and the other digest names.

Directory support closed an earlier gap: a directory source could not be
frozen, and finalize refused runs of the stamped compute skeleton. The
directory digest includes visible files' relative paths and contents so
that added, removed, renamed and edited files affect it.

The current contract is in `labkit/run/provenance.py:source_digest`.
