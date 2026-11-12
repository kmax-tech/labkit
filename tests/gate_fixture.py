"""Rule assignments for the tests of the gate's own mechanics: a finding
is built with its rule assignment or refused (`gate.GateFinding.rule`), so
a synthetic finding says which one it carries and why. A finding that
stands in for a real site carries that site's assignment instead."""

from __future__ import annotations

from labkit.formats import gate

#: one assignment of every kind (`gate.RULE_KINDS`): a test whose statement
#: holds whatever the rule runs over all of them
EVERY_RULE = (
    gate.cited_rule("LAB-004 Identifiers make the intent addressable"),
    gate.TECHNICAL_RULE,
    gate.OPEN_RULE,
    gate.NEW_CLASS_RULE,
)
#: the assignment of a synthetic finding whose line a test spells out as a
#: breach: told without a mark it needs a decided basis, and of the two the
#: technical contract adds no rule name to the line
BREACH = gate.TECHNICAL_RULE
