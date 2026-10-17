"""Deciding a finding the way the person does: status and reason in the record."""

from __future__ import annotations

from pathlib import Path


def set_status(path: Path, n: int, status: str, reason: str = "") -> None:
    """Edit the n-th finding the way the person does: status and reason."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("[[finding]]")
    block = (
        parts[n]
        .replace('status = "open"', f'status = "{status}"')
        .replace('reason = ""', f'reason = "{reason}"')
    )
    parts[n] = block
    path.write_text("[[finding]]".join(parts), encoding="utf-8")


def decide(path: Path, status: str, reason: str = "seen and kept") -> None:
    """The first finding of PATH decided as STATUS with REASON."""
    set_status(path, 1, status, reason)
