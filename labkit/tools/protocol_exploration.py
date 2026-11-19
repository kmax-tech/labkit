"""protocol_exploration — write a confirmation's link to its exploration
(`[explored_in]`).

    protocol-fill PROTOCOL --explored-in EXPLORATION_PROTOCOL

The link names the exploratory protocol by its id and the run that
protocol has adopted now, read once here (`exploration_link.adopted_link`);
no later check selects a newer adoption. It is written only when it is
valid as the start of the first confirming measurement holds it
(`exploration_link.linked_exploration`): PROTOCOL confirmatory, the
exploration one other protocol of this repo whose first measurements were
exploratory, the run its completed, adopted measurement. One link: an
earlier `[explored_in]` is replaced — after the first confirming
measurement that is a change of the registration, which finalize holds
(`protocol_history.scope_differences`). Writes the protocol file and
nothing else.
"""

from __future__ import annotations

from pathlib import Path

from labkit.formats import protocol_block
from labkit.formats.exploration_link import (
    NotLinked,
    adopted_link,
    linked_exploration,
)
from labkit.formats.protocol_block import ExploredIn

#: the header line of the link's table in the TOML block
_LINK_HEADER = protocol_block.table_header("explored_in")


def link_to(protocol: Path, text: str, exploration: Path) -> tuple[ExploredIn, str]:
    """(the link, TEXT with it): PROTOCOL (its text TEXT) linked to the
    protocol file EXPLORATION by that protocol's id and adopted run. Raises
    ValueError with the sentence when EXPLORATION is no file, has adopted
    no run, or the link is not valid (`linked_exploration`), and BlockError
    on a head of TEXT that does not read; RuntimeError when git fails."""
    if not exploration.is_file():
        raise ValueError(f"no such file: {exploration}")
    link = adopted_link(exploration.read_text(encoding="utf-8"))
    if isinstance(link, NotLinked):
        raise ValueError(f"{exploration.name}: {link.why}")
    new = with_link(text, link)
    bound = linked_exploration(new, protocol_block.repo_protocol_ids(protocol))
    if isinstance(bound, NotLinked):
        raise ValueError(bound.why)
    return link, new


def with_link(text: str, link: ExploredIn) -> str:
    """TEXT with LINK as its one `[explored_in]`: an earlier table removed,
    LINK's written at the end of the TOML block. Every other byte stays.
    Raises ValueError without a TOML block, and when the block does not
    read back with LINK."""
    span = protocol_block.toml_block_span(text)
    if span is None:
        raise ValueError("no ```toml block — the link is written into the head")
    start, end = span
    lines = text.split("\n")
    kept: list[str] = []
    in_link = False
    for line in lines[start:end]:
        if _LINK_HEADER.match(line):
            in_link = True
        elif protocol_block.TABLE_HEADER.match(line):
            in_link = False
        if not in_link:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    body = [*kept, "", *protocol_block.explored_in_toml(link).splitlines()]
    new = "\n".join([*lines[:start], *body, *lines[end:]])
    if protocol_block.explored_in(new) != link:
        raise ValueError("[explored_in] did not read back as written")
    return new
