# Note 2026-10-23 — console output history

A Haiku 5.5 probe on 2026-10-13 read Python's broken-pipe traceback and
exit 120 as a command crash after closing an output pipe early. The
console wrapper handles BrokenPipeError during output or flushing,
redirects stdout to /dev/null and exits 0.

The audit of 2026-10-15 counted 44 refusals on stdout and 25 on stderr.
Callers reading stdout for findings could mistake a usage error for a
finding. `console.refuse` centralizes the stderr line; callers retain
responsibility for the exit code. The later progress helper keeps
diagnostic output on stderr as well.

The current contracts are in `labkit/formats/console.py`.
