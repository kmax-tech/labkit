"""protocol_history — what git knows about a protocol.

The id and the repeat cost a protocol had in its first
commit, the registration as a given commit held it
(`registration_in_commit` — report-check holds the low lane to the
commit of the first measurement), and the checks built on them: a repeat cost
lowered since then (`repeat_cost_lowered`, static evidence — a lower tier
owes less), an id changed or taken twice (`check_protocol_id`) and the
apply protocol an annotation validity names (`bound_validation`).
Read-only; git is asked through `repo.git_run`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from labkit.formats.gate import GUARANTEED
from labkit.formats import protocol_block, standard_contract
from labkit.formats.gate import AS_WRITTEN, BLOCKER, WARNING, GateFinding
from labkit.formats.protocol_check import low_registration_missing
from labkit.formats.repo import git_root, git_run, text_at


def id_in_git_head(path: Path) -> str | None:
    """The id the version committed in git HEAD carries (`git show HEAD:…`),
    not the protocol's [protocol] head — None when the file
    is new, git is absent, or the call fails. Never a proof of immutability:
    after the next commit a changed id IS the state. It catches the edit
    while it is still in the working tree."""
    root = git_root(path)
    if root is None:
        return None
    text = text_at(root, path, "HEAD")
    return protocol_block.id_of(text) if text is not None else None


@dataclass(frozen=True)
class FirstRepeatCost:
    """The protocol's `repeat_cost` as the oldest commit this standard reads
    committed it — the tier it was registered at.

    Attributes:
        commit: That commit's hash.
        repeat_cost: The head's value there — declared, never the placeholder.
        earlier_unreadable: Commits before it that touched the file but whose
            head this labkit does not read (another standard): the history
            before a migration, which no reader compares.
        earlier_undeclared: Commits before it whose head still held the
            placeholder — a stamp committed before the registration; they
            declare nothing, so they are no base to compare against.
    """

    commit: str
    repeat_cost: str
    earlier_unreadable: int
    earlier_undeclared: int


def first_repeat_cost(path: Path) -> FirstRepeatCost | None:
    """The protocol's `repeat_cost` in the oldest commit whose head this
    standard reads AND declares one, or None when the file is new to git,
    outside a repo, or no committed version declares it (a placeholder
    committed with the stamp is skipped: lowering from it is a first
    declaration, not a lowering — review 2026-10-25). Walks the file's commits
    oldest first (`git log --reverse`, `git show` at each) and counts the
    unreadable ones it passes — a protocol migrated from 0.22 is compared
    from its migration commit on, and the count says so."""
    root = git_root(path)
    if root is None:
        return None
    rel = path.resolve().relative_to(root).as_posix()
    log = git_run(["log", "--reverse", "--format=%H", "--", rel], root)
    if log.returncode != 0 or not log.stdout.strip():
        return None
    unreadable = 0
    undeclared = 0
    for commit in log.stdout.split():
        shown = git_run(["show", f"{commit}:{rel}"], root)
        if shown.returncode != 0:  # the commit deleted the file
            continue
        try:
            value = protocol_block.head(shown.stdout).repeat_cost
        except protocol_block.BlockError:
            unreadable += 1
            continue
        if value is None:
            undeclared += 1
            continue
        return FirstRepeatCost(commit, value, unreadable, undeclared)
    return None


def registration_in_commit(path: Path, commit: str) -> list[str] | None:
    """What the low registration lacked in the protocol PATH as COMMIT
    holds it (`protocol_check.low_registration_missing`: the fields the
    lane owes written, the repeat_cost declared; a head this labkit cannot read
    is named as such) — [] when it stood whole — or None when that commit
    does not hold the file, or PATH lies outside a repository. The protocol is read as it was then (`git show`): the tree
    now says nothing about what stood before the number."""
    root = git_root(path)
    if root is None:
        return None
    rel = path.resolve().relative_to(root).as_posix()
    shown = git_run(["show", f"{commit}:{rel}"], root)
    if shown.returncode != 0:
        return None
    try:
        protocol_block.head(shown.stdout)
    except protocol_block.BlockError as exc:
        # `low_registration_missing` reads an unreadable head as "no
        # repeat_cost"; here the committed text is older than the reader, and the
        # sentence says so instead of naming a field
        return [f"a head this labkit reads ({exc})"]
    return low_registration_missing(shown.stdout)


def repeat_cost_lowered(path: Path, head: protocol_block.Head) -> str | None:
    """A WARNING when the protocol's repeat cost is lower now than in the
    commit that added it, or None. A lower tier owes less (`low`: no
    audit before the run, no freeze; LAB-017 The number of audits follows
    the repeat cost), so lowering it is the next way round a gate once `n/a`
    is refused — the same move as rewriting the promises until no check is
    due (third haiku round on 0.99.0, t5). Exact over git: the head as it
    was first committed against the head now; a legitimate correction says
    why in the protocol. Static evidence, never a blocker."""
    was = first_repeat_cost(path)
    if was is None or head.repeat_cost is None:
        return None
    commit, first = was.commit, was.repeat_cost
    tiers = protocol_block.REPEAT_COSTS
    if first not in tiers or tiers.index(head.repeat_cost) >= tiers.index(first):
        return None
    since = (
        "the first commit this standard reads "
        f"({was.earlier_unreadable} earlier at another standard, not compared)"
        if was.earlier_unreadable
        else "the protocol's first commit"
    )
    return (
        f"{path}: WARNING: repeat cost lowered since {since} "
        f"({commit[:7]}: {first} -> {head.repeat_cost}) — a lower tier owes less "
        f"(LAB-017 The number of audits follows the cost tier); say why in the "
        f"protocol, or restore it"
    )


def check_protocol_id(
    path: Path, head: protocol_block.Head, ids: dict[str, list[Path]]
) -> list[GateFinding]:
    """Uniqueness against IDS (`protocol_block.repo_protocol_ids` of the repo) and
    working-tree divergence of the protocol id, each with its grade as data:
    a doubled id blocks, a changed one warns. The grade is never read back
    from the text, which carries the path (PROTOCOL-WARNING.md turned a
    doubled id into a warning). Its shape is the head parser's job, an
    unstamped id a must placeholder."""
    if head.id is None:
        return []
    out: list[GateFinding] = []
    others = [q for q in ids.get(head.id, []) if q.resolve() != path.resolve()]
    if others:
        out.append(
            GateFinding(
                BLOCKER,
                f"{path}: DUPLICATE protocol id {head.id} — also carried by "
                + ", ".join(str(q) for q in others)
                + ". An id binds runs to ONE protocol; re-stamp the copy.",
                form=AS_WRITTEN,
                evidence_kind=GUARANTEED,
            )
        )
    was = id_in_git_head(path)
    if was and was != head.id:
        out.append(
            GateFinding(
                WARNING,
                f"{path}: WARNING: protocol id changed against HEAD "
                f"({was} -> {head.id}) — runs bound to the old id stop "
                f"resolving.",
                form=AS_WRITTEN,
                evidence_kind=GUARANTEED,
            )
        )
    return out


class BoundValidation(NamedTuple):
    """The apply protocol `[model] annotation_validity = { protocol = … }`
    names, bound: its path, its text as read, the run it declares."""

    protocol: Path
    text: str
    run: str


def bound_validation(
    text: str, ids: dict[str, list[Path]]
) -> BoundValidation | str | None:
    """The one binding of `[model] annotation_validity = { protocol = "p-…" }`
    against IDS (`protocol_block.repo_protocol_ids` of the repo): the id names exactly one
    protocol, an apply (`kind = "apply"`, the model judged as it is used
    here) with a declared result (`[result] run`). The bound validation, or
    why it is not bound (a sentence), or None when the protocol names no
    such evidence (not a computation, no `[model]`, a DOI, an unreadable
    head — the head check names that). The gate (`check_annotation_validity`)
    and the audit's evidence pieces (`audit.validity_evidence`) read this."""
    try:
        m = protocol_block.model(text)
        kind = protocol_block.head(text).kind
    except protocol_block.BlockError:
        return None
    if (
        m is None
        or kind != standard_contract.COMPUTE_KIND
        or m.annotation_validity is None
        or m.annotation_validity.key != "protocol"
    ):
        return None
    hits = ids.get(m.annotation_validity.value, [])
    if len(hits) != 1:
        return (
            "names "
            + (
                "no protocol of this repo"
                if not hits
                else f"{len(hits)} protocols ({', '.join(str(h) for h in hits)})"
            )
            + "; the evidence must be one apply protocol here, or a DOI"
        )
    bound = hits[0]
    try:
        bound_text = bound.read_text(encoding="utf-8")
        bound_kind = protocol_block.head(bound_text).kind
        bound_run = protocol_block.declared_run(bound_text)
    except (OSError, protocol_block.BlockError) as exc:
        return f"{bound} does not read: {exc}"
    if bound_kind != standard_contract.APPLY_KIND:
        return (
            f'{bound} has kind = "{bound_kind}"; the evidence that an annotator '
            "suits is an apply: the model, used unchanged, judged against gold labels"
        )
    if bound_run is None:
        return (
            f"{bound} declares no result yet ([result] run); a validation "
            "without its number is no evidence"
        )
    return BoundValidation(bound, bound_text, bound_run)


def check_annotation_validity(
    path: Path, text: str, ids: dict[str, list[Path]]
) -> list[GateFinding]:
    """A blocker when `[model] annotation_validity = { protocol = … }` is not
    bound (`bound_validation`). This makes the bound validation checkable;
    that it carries this annotation — same model, prompt and target — stays
    the audit's. A DOI is held to its form by the head parser and bound to
    nothing here."""
    bound = bound_validation(text, ids)
    if not isinstance(bound, str):
        return []
    m = protocol_block.model(text)
    assert m is not None and m.annotation_validity is not None  # bound said so
    where = (
        f"{path}: [model] annotation_validity protocol = {m.annotation_validity.value}"
    )
    return [
        GateFinding(
            BLOCKER, f"{where} — {bound}", form=AS_WRITTEN, evidence_kind=GUARANTEED
        )
    ]
