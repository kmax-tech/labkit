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

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from labkit.formats import runs
from labkit.formats.gate import OPEN_RULE, TECHNICAL_RULE
from labkit.formats.gate import GUARANTEED
from labkit.formats import promises, protocol_block, standard_contract
from labkit.formats.gate import AS_WRITTEN, BLOCKER, WARNING, GateFinding
from labkit.formats.protocol_block import COUNTS
from labkit.formats.protocol_check import (
    REGISTERED_FIELDS,
    field_name,
    field_values,
    line_list,
    low_registration_missing,
    repeated_fields,
)

if TYPE_CHECKING:
    from labkit.formats.runs import RunDir

from labkit.formats.repo import (
    rel_posix,
    GitError,
    blob_text,
    blobs_then,
    commit_known,
    git_root,
    git_run,
    text_at,
    unreadable_at,
)


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
    declaration, not a lowering). Walks the file's commits
    oldest first (`git log --reverse`, `git show` at each) and counts the
    unreadable ones it passes — a migrated protocol is compared from its
    migration commit on, and the count says so."""
    root = git_root(path)
    if root is None:
        return None
    rel = rel_posix(path, root)
    log = git_run(["log", "--reverse", "--format=%H", "--", rel], root)
    if log.returncode != 0 or not log.stdout.strip():
        return None
    unreadable = 0
    undeclared = 0
    for commit in log.stdout.split():
        shown = text_at(root, path, commit)
        if shown is None:  # the commit deleted the file
            continue
        try:
            value = protocol_block.head(shown).repeat_cost
        except protocol_block.BlockError:
            unreadable += 1
            continue
        if value is None:
            undeclared += 1
            continue
        return FirstRepeatCost(commit, value, unreadable, undeclared)
    return None


def registration_in_commit(
    path: Path, commit: str, kind_now: str | None = None
) -> list[str] | None:
    """What the low registration lacked in the protocol PATH as COMMIT
    holds it (`protocol_check.low_registration_missing`: the fields the
    lane owes written, the repeat_cost declared; a head this labkit cannot read
    is named as such) — [] when it stood whole — or None when that commit
    does not hold the file, or PATH lies outside a repository. The protocol is read as it was then (`git show`): the tree
    now says nothing about what stood before the number. KIND_NOW, the
    kind the protocol declares today: the fields are owed by it, and a
    commit that declared another kind lacks the kind — a kind changed after
    the measurement is not registered before it."""
    root = git_root(path)
    if root is None:
        return None
    shown = text_at(root, path, commit)
    if shown is None:
        return None
    return registration_missing(shown, kind_now)


def registration_missing(shown: str, kind_now: str | None = None) -> list[str]:
    """What the low registration lacks in SHOWN, a protocol as a commit held
    it (`registration_in_commit`): the fields KIND_NOW owes, the repeat_cost,
    one copy of each bound field (`repeated_fields`: `one copy of <label>
    (written N times, lines a and b)`), or a head this labkit cannot read —
    [] when it stood whole. Pure."""
    try:
        protocol_block.head(shown)
    except protocol_block.BlockError as exc:
        # `low_registration_missing` reads an unreadable head as "no
        # repeat_cost"; here the committed text is older than the reader, and the
        # sentence says so instead of naming a field
        return [f"a head this labkit reads ({exc})"]
    return low_registration_missing(shown, kind_now) + [
        f"one copy of {label} (written {len(at)} times, lines {line_list(at)})"
        for label, at in repeated_fields(shown)
    ]


#: why the protocol a first measurement's commit holds cannot be read
#: (`CommittedAt.cause`): the run recorded no commit, the repository does not
#: hold the commit it recorded, or that commit does not hold the protocol
NO_COMMIT = "no commit"
UNKNOWN_COMMIT = "unknown commit"
NOT_COMMITTED = "not committed"
UNREADABLE_COMMIT = "unreadable"


@dataclass(frozen=True)
class CommittedAt:
    """A protocol as the commit one run recorded holds it: TEXT, or None
    with CAUSE (`NO_COMMIT`, `UNKNOWN_COMMIT`, `NOT_COMMITTED`,
    `UNREADABLE_COMMIT` with git's own words in DETAIL); COMMIT the full
    sha the run recorded, None without one."""

    run: str
    commit: str | None
    text: str | None
    cause: str | None
    detail: str = ""


def protocol_path_at(root: Path, commit: str, pid: str) -> Path | None:
    """Where the protocol carrying id PID stood in COMMIT of the repository
    ROOT — the `PROTOCOL-*.md` whose head names PID —, or None when no file
    there does. The id is the binding and survives a rename or a move
    (docs/protocol-run-binding.md); the head is read as TOML only, since an
    older commit holds an older standard `protocol_block.head` refuses.
    Raises GitError when git cannot run."""
    listed = git_run(["ls-tree", "-r", "-z", "--name-only", commit], root)
    if listed.returncode != 0:
        raise GitError(f"git ls-tree {commit[:12]} in {root}: {listed.stderr.strip()}")
    names = [n for n in listed.stdout.split("\0") if n]
    for rel in sorted(n for n in names if Path(n).name.startswith("PROTOCOL-")):
        text = text_at(root, root / rel, commit)
        if text is None:
            continue
        try:
            table = protocol_block.parse_toml_block(text).get("protocol", {})
        except protocol_block.BlockError:
            continue  # a block that does not parse names no id to bind
        if isinstance(table, dict) and table.get("id") == pid:
            return root / rel
    return None


def committed_at(path: Path, rd: "RunDir", root: Path) -> CommittedAt:
    """The protocol PATH as the commit run RD recorded (`runs.recorded_commit`)
    holds it in the repository ROOT — the one reading of "what stood
    before the number" that the registration station
    (`report_check.registration_gaps`) and the binding of the report
    registered before it share. Read at PATH, and where the commit holds
    nothing there, by the id RD's run is bound to (`protocol_path_at`): a
    protocol renamed or moved since stood before the number all the same.
    RD's config must read. Raises GitError when git cannot run."""
    from labkit.formats.runs import recorded_commit

    assert rd.config is not None, "a run whose config reads"
    commit = recorded_commit(rd.config)
    if commit is None:
        return CommittedAt(rd.dir.name, None, None, NO_COMMIT)
    if not commit_known(root, commit):
        return CommittedAt(rd.dir.name, commit, None, UNKNOWN_COMMIT)
    text = text_at(root, path, commit)
    if text is None:
        # `text_at` says None for an absent file and for git failing alike:
        # a commit git cannot read is no "nothing stood before the number"
        unread = unreadable_at(root, path, commit)
        if unread:
            return CommittedAt(rd.dir.name, commit, None, UNREADABLE_COMMIT, unread)
        # absent at PATH: renamed or moved since, found by its id
        pid = rd.config.protocol.id
        then = protocol_path_at(root, commit, pid) if pid is not None else None
        text = text_at(root, then, commit) if then is not None else None
    if text is None:
        return CommittedAt(rd.dir.name, commit, None, NOT_COMMITTED)
    return CommittedAt(rd.dir.name, commit, text, None)


def repeat_cost_lowered(path: Path, head: protocol_block.Head) -> str | None:
    """A WARNING when the protocol's repeat cost is lower now than in the
    commit that added it, or None. A lower tier owes less (`low`: no
    audit before the run, no freeze; LAB-017 The number of audits follows
    the cost tier), so lowering it is the next way round a gate once `n/a`
    is refused — the same move as rewriting the promises until no check is
    due. Exact over git: the head as it
    was first committed against the head now; a legitimate correction says
    why in the protocol. Static evidence, never a blocker."""
    was = first_repeat_cost(path)
    if was is None or head.repeat_cost is None:
        return None
    commit, first = was.commit, was.repeat_cost
    tiers = runs.REPEAT_COSTS
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
    from the text, which carries the path (a PROTOCOL-WARNING.md would turn
    a doubled id into a warning). Its shape is the head parser's job, an
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
                + ". An id binds runs to ONE protocol",
                form=AS_WRITTEN,
                fix="re-stamp the copy: `labkit-init exp <name> --kind …` writes "
                "a fresh id, and the copy's text moves into it",
                evidence_kind=GUARANTEED,
                rule=TECHNICAL_RULE,
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
                rule=TECHNICAL_RULE,
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
    and the audit's evidence pieces (`audit_prompt.validity_evidence`) read this."""
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
            f"{bound} has adopted no result yet ([result] run); a validation "
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
            BLOCKER,
            f"{where} — {bound}",
            form=AS_WRITTEN,
            fix="bind it to one apply protocol of this repo whose head has adopted "
            "its result (`[result] run`, adopted there first), or name a DOI",
            evidence_kind=GUARANTEED,
            rule=OPEN_RULE,
        )
    ]


#: the fields that say what a number is about — the question and its words,
#: the data and what is dropped from it, the unit — held with the head's kind,
#: `[kept]` and `[reference]` from the first measurement on (`scope_differences`):
#: every kind writes them before the commit, and a computation has no promise
#: block to hold instead (docs/notes/2026-10-31-scope-frozen.md)
SCOPE_FIELDS = (
    "Question / hypothesis",
    "Terms of this protocol",
    "Data / scope",
    "Exclusions / filters",
    "Unit",
)


#: the fields held once registered: the registration's own (`protocol_check`)
#: and what the number is about (SCOPE_FIELDS) — a reading hint that rewrites
#: one is a departure, not a hint (`audit_decisions.read_hints`)
HELD_FIELDS = tuple(dict.fromkeys(REGISTERED_FIELDS + SCOPE_FIELDS))


#: the fields no correction in place releases (`correctable`): the question
#: states the requirement itself, so it stands as registered, a typo
#: included, and a different question is a protocol of its own
#: (docs/notes/2026-11-02-registered-field-repair.md)
UNCORRECTABLE_FIELDS = ("Question / hypothesis",)
#: what one of UNCORRECTABLE_FIELDS is after the first measurement: the
#: hold of its change (`registration_hold.correction_way`) and the decision's line
#: (`audit_decisions.repair_hint`, which states the condition) say it so
STANDS_AS_REGISTERED = (
    "has no correction in place — it stands as registered, a typo included; "
    "a different question is a protocol of its own"
)


def correctable(label: str) -> bool:
    """Can a correction in place — a finding placed on the field, decided
    `fixed`, judged `resolved` — release a change of the field LABEL? Not
    for UNCORRECTABLE_FIELDS, compared by `field_name`. The one rule the
    correction (`findings.corrected_field`), the hold and the decision's
    line (`registration_hold.correction_way`) read. Pure."""
    return field_name(label) not in {field_name(f) for f in UNCORRECTABLE_FIELDS}


def scope_value(value: str) -> str:
    """A scope field's VALUE as it is compared: whitespace folded, the
    generated data counts of Data / scope left out (`COUNTS`; the prepare run
    writes them, not the author), the separator before them dropped."""
    flat = " ".join(value.split())
    m = COUNTS.search(flat)
    if m:
        flat = flat[: m.start()].rstrip(" ·;")
    return flat


def scope_differences(old: str, new: str) -> list[tuple[str, str, str]]:
    """(what, from, to) for every difference between the protocol texts OLD
    and NEW in what the number is about: each of SCOPE_FIELDS
    (`scope_value`), the head's kind, its `[kept]` and its `[reference]` as
    the head writes them. ABSENT where one text has nothing; a head or a `[reference]` that
    does not read is compared as the sentence its error says, so the fields
    are compared whatever the head held then — a first measurement may have
    run on a commit whose `[reference]` did not read yet. Pure."""
    out: list[tuple[str, str, str]] = []
    ka, kb = _head_part(old, "kind"), _head_part(new, "kind")
    if ka != kb:
        out.append(("kind", ka, kb))
    for table in ("kept", "reference"):
        ta, tb = _head_part(old, table), _head_part(new, table)
        if ta != tb:
            out.append((f"[{table}]", ta, tb))
    # the raw values say which field is written; each copy is compared as
    # `scope_value` reads it, so the counts of one copy cut no other
    fa, fb = field_values(old), field_values(new)
    sa, sb = field_values(old, scope_value), field_values(new, scope_value)
    for label in SCOPE_FIELDS:
        x = sa[name] if fa.get(name := field_name(label)) else ABSENT
        y = sb[name] if fb.get(name) else ABSENT
        if x != y:
            out.append((label, x, y))
    return out


def _head_part(text: str, part: str) -> str:
    """The head's PART of TEXT as `scope_differences` compares it: "kind"
    its kind, "kept" its `[kept]` and "reference" its `[reference]` as TOML
    on one line (ABSENT without the table); `(does not read: …)` with the
    error where the head or the table does not parse."""
    try:
        if part == "kind":
            return str(protocol_block.head(text).kind)
        if part == "kept":
            kept = protocol_block.kept(text)
            toml = protocol_block.kept_toml(kept) if kept is not None else None
        else:
            ref = protocol_block.reference(text)
            toml = protocol_block.reference_toml(ref) if ref is not None else None
    except protocol_block.BlockError as exc:
        return f"(does not read: {exc})"
    return " ".join(toml.split()) if toml is not None else ABSENT


#: the registration fields outside the promise block and what the number is
#: about (SCOPE_FIELDS) that a replacement compares
COMPARED_FIELDS = ("Data profile",)


def registration_differences(old: str, new: str) -> list[tuple[str, str, str]]:
    """(what, from, to) for every difference of the registration between the
    protocol texts OLD and NEW (K1): the head's kind, per promise id its
    sentence, key, each constant and its scope, an id added or dropped,
    what the number is about (`scope_differences`: `[kept]`, `[reference]`
    and SCOPE_FIELDS — the one comparison finalize holds a protocol's first
    measurement to, so the hold that points to a new registration and the
    declaration it asks for name the same changes), and COMPARED_FIELDS.
    Values as `protocol_check.field_values` reads them (by `field_name`,
    whitespace folded); `(none)` where one has nothing.
    Pure; raises BlockError or PromiseError on a head or a block that does
    not read."""
    scope = scope_differences(old, new)
    out = [d for d in scope if d[0] == "kind"]
    out += promise_differences(old, new)
    out += [d for d in scope if d[0] != "kind"]
    fa, fb = field_values(old), field_values(new)
    for label in COMPARED_FIELDS:
        x = fa.get(field_name(label)) or ABSENT
        y = fb.get(field_name(label)) or ABSENT
        if x != y:
            out.append((label, x, y))
    return out


#: what a difference names where one registration has nothing
ABSENT = "(none)"


def promise_differences(old: str, new: str) -> list[tuple[str, str, str]]:
    """(what, from, to) for every difference of the promise blocks of the
    protocol texts OLD and NEW, by id in order: `<id>` alone for an id
    added or dropped (its sentence, ABSENT on the side without it), else
    `<id> sentence`, `<id> key`, `<id> scope` and `<id> <constant>`. Pure;
    raises PromiseError on a block that does not read."""
    a = {
        p.id: p
        for p in (promises.parse_block(old) or promises.PromiseTables((), "")).promises
    }
    b = {
        p.id: p
        for p in (promises.parse_block(new) or promises.PromiseTables((), "")).promises
    }
    out: list[tuple[str, str, str]] = []
    for pid in sorted(set(a) | set(b)):
        if pid not in a or pid not in b:
            out.append(
                (
                    pid,
                    a[pid].sentence if pid in a else ABSENT,
                    b[pid].sentence if pid in b else ABSENT,
                )
            )
        else:
            out += _promise_differences(a[pid], b[pid])
    return out


def _promise_differences(
    pa: promises.Promise, pb: promises.Promise
) -> list[tuple[str, str, str]]:
    """`registration_differences` of one promise id in both texts."""
    out = [
        (f"{pa.id} {what}", x, y)
        for what, x, y in (
            ("sentence", pa.sentence, pb.sentence),
            ("key", pa.key, pb.key),
            ("scope", ", ".join(sorted(pa.scope)), ", ".join(sorted(pb.scope))),
        )
        if x != y
    ]
    for name in sorted(set(pa.constants) | set(pb.constants)):
        x, y = pa.constants.get(name), pb.constants.get(name)
        if x != y:
            out.append(
                (
                    f"{pa.id} {name}",
                    ABSENT if x is None else str(x),
                    ABSENT if y is None else str(y),
                )
            )
    return out


def registrations_as_first_measured(
    protocol: Path, groups: Sequence[Sequence["RunDir"]], root: Path | None
) -> tuple[list[tuple[str, str]], str]:
    """([(text, where)], "") — PROTOCOL's text as each of its first
    measurements saw it (`area_state.Measured.first_groups`, every run at
    each first position; `as_measured`), one entry per distinct text,
    WHERE naming the run; its text as it stands when it has no measurement
    yet. Several entries are first measurements that saw different
    registrations: K3 holds that protocol, a replacement declares its
    changes against each (K1). ([], why) when one first measurement's
    registration cannot be read back. Never an invented earlier value.
    Raises RuntimeError when git fails."""
    if not groups:
        return [
            (protocol.read_text(encoding="utf-8"), "as it stands (no measurement yet)")
        ], ""
    texts: dict[str, str] = {}
    for rd in (rd for group in groups for rd in group):
        text, where = as_measured(protocol, rd, root)
        if text is None:
            return [], where
        texts.setdefault(text, where)
    return list(texts.items()), ""


def unread_measurements(
    protocol: Path, runs: "Sequence[RunDir]", root: Path
) -> list[str]:
    """Why PROTOCOL as each of RUNS saw it cannot be read back
    (`as_measured`), one sentence per run that cannot — what a comparison
    with those texts (`first_measured_differences`) passes over, and so the
    hold that names it: a comparison that could not run is no "nothing
    changed". Empty when every text reads. ROOT is the repository; outside
    one no text is read back at all and nothing is said here. Pure but for
    git's reads."""
    return [
        why
        for rd in runs
        for text, why in [as_measured(protocol, rd, root)]
        if text is None
    ]


def first_measured_differences(
    protocol: Path,
    firsts: "Sequence[RunDir]",
    text: str,
    root: Path | None,
    compare: "Callable[[str, str], list[tuple[str, str, str]]]",
) -> "tuple[RunDir, list[tuple[str, str, str]]] | None":
    """(first, differences): the first of FIRSTS — first measurements of
    PROTOCOL — whose protocol as it saw it (`as_measured`) differs from
    TEXT under COMPARE (`scope_differences`, `promise_differences`), with
    COMPARE's (what, from, to); None when every first measurement that can
    be read back agrees. A first measurement whose protocol cannot be read
    back is passed over: the registration station names that state. The one
    comparison of a text with the first measurements — finalize holds the
    answering run's text and the protocol as it stands to it, the `fixed`
    line of `labkit-audit --decide` names what it would hold. Raises
    RuntimeError when git fails, and what COMPARE raises."""
    for first in firsts:
        then, _ = as_measured(protocol, first, root)
        if then is None:
            continue
        diffs = compare(then, text)
        if diffs:
            return first, diffs
    return None


def as_measured(
    protocol: Path, rd: "RunDir", root: Path | None
) -> tuple[str | None, str]:
    """(text, where): PROTOCOL as run RD saw it — its recorded commit's text
    with the part of the run's `uncommitted.patch` that touches the protocol
    applied (`repo.blobs_then`), held to the promise block the run recorded.
    TEXT None, WHERE then saying why and what brings it back, when that
    cannot be read: no recorded commit, a commit this clone does not hold
    (`git fetch` brings it), git unable to read that commit's tree or the
    blob, or a patch that does not apply (git's own error), a tree without
    the protocol (untracked when the run started), a text whose block is
    not the one the run recorded. A comparison that needs the text holds
    on None (`unread_measurements`), never reads it as no change."""
    from labkit.formats.runs import patch_path, recorded_commit

    commit = recorded_commit(rd.config) if rd.config is not None else None
    if commit is None or root is None:
        return None, f"its first measurement {rd.dir.name} recorded no commit"
    if not commit_known(root, commit):
        return None, (
            f"its first measurement {rd.dir.name} started at {commit[:12]}, a commit "
            f"this clone does not hold — `git fetch` brings it"
        )
    patch_file = patch_path(rd.dir)
    patch = patch_file.read_text(encoding="utf-8") if patch_file.is_file() else ""
    pid = rd.config.protocol.id if rd.config is not None else None
    try:
        blob = blobs_then(root, commit, patch, [protocol])[protocol]
        then = protocol_path_at(root, commit, pid) if blob is None and pid else None
        if then is not None:  # renamed or moved since: found by its id
            blob = blobs_then(root, commit, patch, [then])[then]
    except GitError as exc:
        return None, f"its first measurement {rd.dir.name}: {exc}"
    if blob is None:
        return None, (
            f"its first measurement {rd.dir.name} ran with the protocol untracked: "
            f"no commit holds what it registered"
        )
    try:
        text = blob_text(root, blob)
    except RuntimeError as exc:  # `git cat-file` could not read the blob
        return None, f"its first measurement {rd.dir.name}: {exc}"
    patched = " with its uncommitted.patch" if patch.strip() else ""
    recorded = (rd.config.promises or {}).get("block_sha") if rd.config else None
    if recorded is not None and _block_sha(text) != recorded:
        return None, (
            f"its first measurement {rd.dir.name} recorded block {recorded}, and "
            f"{commit[:12]}{patched} gives {_block_sha(text)}: what it registered "
            f"cannot be read back"
        )
    return (
        text,
        f"as its first measurement {rd.dir.name} saw it ({commit[:12]}{patched})",
    )


def _block_sha(text: str) -> str | None:
    """The digest of TEXT's promise block; None without one or unreadable."""
    try:
        block = promises.parse_block(text)
    except promises.PromiseError:
        return None
    return block.sha if block is not None else None
