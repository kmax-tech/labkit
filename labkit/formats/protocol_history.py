"""protocol_history — what git knows about a protocol.

The ids every protocol of the repo claims (`repo_protocol_ids`, one scan
per invocation), the id and the cost tier a protocol had in its first
commit, the registration as a given commit held it
(`registration_in_commit` — report-check holds the seconds lane to the
commit of the first measurement), and the checks built on them: a cost
tier lowered since then (`cost_lowered`, static evidence — a lower tier
owes less) and an id changed or taken twice (`check_protocol_id`).
Read-only; git is asked through `repo.git_run`.
"""

from pathlib import Path

from labkit.formats import protocol_block, standard_contract
from labkit.formats.gate import AS_WRITTEN, BLOCKER, WARNING, GateFinding
from labkit.formats.protocol_check import seconds_registration_missing
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


def registration_in_commit(path: Path, commit: str) -> list[str] | None:
    """What the seconds registration lacked in the protocol PATH as COMMIT
    holds it (`protocol_check.seconds_registration_missing`: the fields the
    lane owes written, the cost declared; a head this labkit cannot read
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
        # `seconds_registration_missing` reads an unreadable head as "no
        # cost"; here the committed text is older than the reader, and the
        # sentence says so instead of naming a field
        return [f"a head this labkit reads ({exc})"]
    return seconds_registration_missing(shown.stdout)


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
) -> list[GateFinding]:
    """Uniqueness against IDS (`repo_protocol_ids` of the repo) and
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
            )
        )
    return out


def check_annotation_validity(
    path: Path, text: str, ids: dict[str, list[Path]]
) -> list[GateFinding]:
    """The binding of `[model] annotation_validity = { protocol = "p-…" }`
    against IDS (`repo_protocol_ids` of the repo): the id names exactly one
    protocol, an apply (`kind = "apply"`, the model judged as it is used
    here) with a declared result (`[result] run`). A blocker each when not.
    This makes the bound validation checkable; that it carries this
    annotation — same model, prompt and target — stays the audit's. A DOI
    is held to its form by the head parser and bound to nothing here."""
    try:
        m = protocol_block.model(text)
        kind = protocol_block.head(text).kind
    except protocol_block.BlockError:
        return []  # the head check names it
    if (
        m is None
        or kind != standard_contract.COMPUTE_KIND
        or m.annotation_validity is None
        or m.annotation_validity.key != "protocol"
    ):
        return []
    pid = m.annotation_validity.value
    where = f"{path}: [model] annotation_validity protocol = {pid}"
    hits = ids.get(pid, [])
    if len(hits) != 1:
        return [
            GateFinding(
                BLOCKER,
                f"{where} — names "
                + (
                    "no protocol of this repo"
                    if not hits
                    else f"{len(hits)} protocols ({', '.join(str(h) for h in hits)})"
                )
                + "; the evidence must be one apply protocol here, or a DOI",
                form=AS_WRITTEN,
            )
        ]
    bound = hits[0]
    try:
        bound_text = bound.read_text(encoding="utf-8")
        bound_kind = protocol_block.head(bound_text).kind
        bound_run = protocol_block.declared_run(bound_text)
    except (OSError, protocol_block.BlockError) as exc:
        return [
            GateFinding(
                BLOCKER, f"{where} — {bound} does not read: {exc}", form=AS_WRITTEN
            )
        ]
    if bound_kind != standard_contract.APPLY_KIND:
        return [
            GateFinding(
                BLOCKER,
                f'{where} — {bound} has kind = "{bound_kind}"; the evidence that '
                "an annotator suits is an apply: the model, used unchanged, judged "
                "against gold labels",
                form=AS_WRITTEN,
            )
        ]
    if bound_run is None:
        return [
            GateFinding(
                BLOCKER,
                f"{where} — {bound} declares no result yet ([result] run); a "
                "validation without its number is no evidence",
                form=AS_WRITTEN,
            )
        ]
    return []
