"""protocol_history — what git knows about a protocol.

The ids every protocol of the repo claims (`repo_protocol_ids`, one scan
per invocation), the id and the cost tier a protocol had in its first
commit, and the checks built on them: a cost tier lowered since then
(`cost_lowered`, static evidence — a lower tier owes less) and an id
changed or taken twice (`check_protocol_id`). Read-only; git is asked
through `repo.git_run`.
"""

from pathlib import Path

from labkit.formats import protocol_block
from labkit.formats.repo import git_root, git_run, repo_protocols


def repo_protocol_ids(start: Path) -> dict[str, list[Path]]:
    """Every protocol id in the repo, mapped to the files carrying it — read
    now, never cached: the caller holds the index for as long as it may
    trust it (`main`: one scan per repo per invocation). A module-level
    cache kept a duplicate made later in the same process invisible.

    Uniqueness cannot be settled at the stamp alone: copying a protocol or
    editing the id by hand makes a duplicate long after `labkit-init exp` ran, and
    two protocols with one id bind their runs to the same thing.
    """
    root = git_root(start)
    if root is None:
        return {}
    index: dict[str, list[Path]] = {}
    for f in repo_protocols(root):
        try:
            pid = protocol_block.id_of(f.read_text(encoding="utf-8"))
        except OSError:
            continue
        if pid:
            index.setdefault(pid, []).append(f)
    return index


def id_in_git_head(path: Path) -> str | None:
    """The id the version committed in git HEAD carries (`git show HEAD:…`),
    not the protocol's [protocol] head — None when the file
    is new, git is absent, or the call fails. Never a proof of immutability:
    after the next commit a changed id IS the state. It catches the edit
    while it is still in the working tree."""
    root = git_root(path)
    if root is None:
        return None
    rel = path.resolve().relative_to(root)
    r = git_run(["show", f"HEAD:{rel}"], root)
    return protocol_block.id_of(r.stdout) if r.returncode == 0 else None


def cost_in_first_commit(path: Path) -> tuple[str, str | None] | None:
    """(commit, cost) of the protocol as its first commit added it — the cost
    tier it was registered at — or None when the file is new to git, outside
    a repo, or that version has no readable head. `git log --diff-filter=A`
    names the adding commit; `git show` reads the file as it was then."""
    root = git_root(path)
    if root is None:
        return None
    rel = path.resolve().relative_to(root).as_posix()
    log = git_run(["log", "--diff-filter=A", "--format=%H", "--", rel], root)
    if log.returncode != 0 or not log.stdout.strip():
        return None
    first = log.stdout.split()[-1]  # the oldest adding commit, if several
    shown = git_run(["show", f"{first}:{rel}"], root)
    if shown.returncode != 0:
        return None
    try:
        return first, protocol_block.head(shown.stdout).cost
    except protocol_block.BlockError:
        return None


def cost_lowered(path: Path, head: protocol_block.Head) -> str | None:
    """A WARNING when the protocol's cost tier is lower now than in the
    commit that added it, or None. A lower tier owes less (`seconds`: no
    audit before the run, no freeze; LAB-017 The number of audits follows
    the cost tier), so lowering it is the next way round a gate once `n/a`
    is refused — the same move as rewriting the promises until no check is
    due (third haiku round on 0.99.0, t5). Exact over git: the head as it
    was first committed against the head now; a legitimate correction says
    why in the protocol. Static evidence, never a blocker."""
    was = cost_in_first_commit(path)
    if was is None or head.cost is None:
        return None
    commit, first = was
    tiers = protocol_block.COST_TIERS
    if first not in tiers or tiers.index(head.cost) >= tiers.index(first):
        return None
    return (
        f"{path}: WARNING: cost tier lowered since the protocol's first commit "
        f"({commit[:7]}: {first} -> {head.cost}) — a lower tier owes less "
        f"(LAB-017 The number of audits follows the cost tier); say why in the "
        f"protocol, or restore it"
    )


def check_protocol_id(
    path: Path, head: protocol_block.Head, ids: dict[str, list[Path]]
) -> list[str]:
    """Uniqueness against IDS (`repo_protocol_ids` of the repo) and
    working-tree divergence of the protocol id; its shape is the head
    parser's job, an unstamped id a must placeholder."""
    if head.id is None:
        return []
    out = []
    others = [q for q in ids.get(head.id, []) if q.resolve() != path.resolve()]
    if others:
        out.append(
            f"{path}: DUPLICATE protocol id {head.id} — also carried by "
            + ", ".join(str(q) for q in others)
            + ". An id binds runs to ONE protocol; re-stamp the copy."
        )
    was = id_in_git_head(path)
    if was and was != head.id:
        out.append(
            f"{path}: WARNING: protocol id changed against HEAD "
            f"({was} -> {head.id}) — runs bound to the old id stop "
            f"resolving."
        )
    return out
