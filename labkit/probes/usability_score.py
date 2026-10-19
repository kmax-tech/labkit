"""usability_score — scoring a finished cold-agent probe.

Reads what the probe left — the agent's log (`parse_log`: steps, gaps,
reads of labkit's source), its answers and the run they cite
(`load_probe_run`, `latest_run`) — and scores it against the task's
truth (`score`), or a reading probe against its questions (`cmd_*`).
`archive` copies the record into the repo. Reads the probe directory;
writes only the score and the archive.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from labkit.probes import agent_transcript, code_navigation, protocol_reading
from labkit.formats import promises, runs, answering_run
from labkit.probes.usability import (
    LOG_LINE,
    LOG_TAGS,
    Probe,
    SOURCE_READ,
    TOL,
    read_answer,
    read_probe,
    sidecar,
    recount,
)


#: a silence between two stamps this long is not work — an outage, a
#: forgotten agent — and is reported beside the span, not hidden in it
GAP_SECONDS = 600


@dataclass(frozen=True)
class LogTrace:
    """What the agent's log says: stamps and counts per tag."""

    lines: int
    wall_seconds: int | None  # max − min over the stamps; None below two
    gap_seconds: int  # sum of silences ≥ GAP_SECONDS between stamps
    monotonic: bool  # stamps never run backwards
    read: int
    run: int
    edit: int
    unsure: int
    gate: int
    untagged: int  # off-contract lines, counted, never dropped
    source_reads: int  # `read` lines naming labkit's source or the lab standard


def parse_log(text: str) -> LogTrace:
    """Read an agent's step log (`HH:MM:SS · tag · text` per line) into counts and wall-clock."""
    counts = {t: 0 for t in LOG_TAGS}
    untagged = 0
    source_reads = 0
    stamps: list[int] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = LOG_LINE.match(line)
        if not m or m.group(4).lower() not in counts:
            untagged += 1
            continue
        counts[m.group(4).lower()] += 1
        if m.group(4).lower() == "read" and SOURCE_READ.search(m.group(5)):
            source_reads += 1
        stamps.append(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
    wall = (max(stamps) - min(stamps)) if len(stamps) >= 2 else None
    gaps = sum(b - a for a, b in zip(stamps, stamps[1:]) if b - a >= GAP_SECONDS)
    return LogTrace(
        lines=len(stamps) + untagged,
        wall_seconds=wall,
        gap_seconds=gaps,
        monotonic=all(a <= b for a, b in zip(stamps, stamps[1:])),
        untagged=untagged,
        source_reads=source_reads,
        **counts,
    )


def latest_run(area: Path) -> Path | None:
    """The newest completed run — run_ids start with the timestamp, so
    their sort order is their start order (runlog.Run). Not the answering
    choice (`answering_run.bound_answering_run`, behind recheck and finalize): the
    scorer reads what the cold agent produced, bound or not — an unbound
    run is a finding of the probe, not a run to leave out."""
    try:
        return answering_run.newest_completed(area, with_repeats=False)
    except runs.RunConfigError as exc:  # unreadable, or two newest in one second
        raise SystemExit(f"usability: {exc}") from exc


@dataclass(frozen=True)
class Score:
    """What a probe's score found: the number, its binding, the log and the transcript."""

    probe: Probe
    run_id: str | None
    number: float | None  # metrics[metric_key], or None when absent
    expected: float | None  # the recounted truth (count), None for a model's number
    number_ok: bool  # equals the truth, or (judge) present and within [0, 1]
    null_reported: (
        bool | None
    )  # judge: an a<i>_* key (admissibility, the null lane) in metrics.json
    bound_to: str | None  # config["protocol"]["path"]
    frozen: bool | None
    cost_tier: str | None
    log: LogTrace | None
    form: protocol_reading.Form | None = None  # how the bound protocol reads
    transcript: agent_transcript.TranscriptTrace | None = (
        None  # measured, not self-reported
    )
    agent: str | None = (
        None  # the model that drew, as the operator names it (`--agent`)
    )


def archive(root: Path, transcript: Path, dest: Path) -> list[Path]:
    """Keep a probe for later debugging: the transcript (gzip, mtime 0 so
    the bytes depend on the content only), its timeline and the score, as
    `<dest>/<probe>.jsonl.gz`, `.timeline.txt`, `.score.json`. Claude Code
    deletes transcripts after `cleanupPeriodDays` (30 by default), and a
    transcript is what showed an agent's source reads and detours on
    2026-10-07. A file already there with other bytes is refused, never
    overwritten."""
    import gzip

    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        dest / f"{root.name}.jsonl.gz": gzip.compress(transcript.read_bytes(), mtime=0),
        dest / f"{root.name}.timeline.txt": (
            "\n".join(agent_transcript.timeline(transcript)) + "\n"
        ).encode("utf-8"),
        dest / f"{root.name}.score.json": sidecar(root, "score.json").read_bytes(),
    }
    clash = [p for p, b in payload.items() if p.exists() and p.read_bytes() != b]
    if clash:
        raise SystemExit(
            f"usability: archive refuses to overwrite {', '.join(map(str, clash))} — "
            f"another probe of the same name? archive into another directory"
        )
    for path, body in payload.items():
        path.write_bytes(body)
    return list(payload)


@dataclass(frozen=True)
class ProbeRun:
    """A staged probe and its latest completed run, read once — one home for
    what `score` and the reading probes both need."""

    probe: Probe
    area: Path
    run: Path | None  # None: no completed run yet
    config: dict[str, object]
    metrics: dict[str, object]
    protocol: Path | None  # the protocol the run names, resolved; None: none named
    protocol_as_recorded: str | None  # the path as config.json holds it
    bound: bool  # the run recorded the protocol's id — a path alone goes stale
    cost_tier: str | None


def load_probe_run(root: Path) -> ProbeRun:
    """Read `<dir>.probe.json` and the probe area's latest completed run.
    Raises SystemExit when the probe was not staged here."""
    probe_file = sidecar(root, "probe.json")
    if not probe_file.is_file():
        raise SystemExit(f"usability: {probe_file} missing — was {root} staged here?")
    probe = read_probe(probe_file)
    area = root / "experiments" / probe.area
    run = latest_run(area)
    if run is None:
        return ProbeRun(probe, area, None, {}, {}, None, None, False, None)
    config = runs.read_run_config(run)
    if config is None:
        raise SystemExit(f"usability: {run} has no config.json — not a run")
    metrics = runs.read_metrics(run / "metrics.json")
    binding = config.get("protocol") or {}
    named = binding.get("path")
    protocol = None
    if named:
        protocol = Path(named) if Path(named).is_absolute() else area / named
    tier = config.get("cost_tier")
    return ProbeRun(
        probe,
        area,
        run,
        config,
        metrics,
        protocol,
        str(named) if named else None,
        bool(binding.get("id")),
        str(tier) if tier is not None else None,
    )


def _bound_protocol(root: Path) -> tuple[Path, protocol_reading.Truth]:
    """The protocol the probe's latest run names, and what the run says."""
    pr = load_probe_run(root)
    if pr.run is None:
        raise SystemExit(f"usability: {pr.area} has no completed run — nothing to read")
    if pr.protocol is None:
        raise SystemExit(f"usability: run {pr.run.name} is bound to no protocol")
    try:
        truth = protocol_reading.truth_from_metrics(pr.metrics, pr.probe.metric_key)
    except ValueError as exc:
        raise SystemExit(f"usability: run {pr.run.name}: {exc}") from exc
    return pr.protocol, truth


def cmd_reader(root: Path) -> int:
    """Write `<dir>.reader-prompt.md`: the bound protocol for a cold reader."""
    protocol, _ = _bound_protocol(root)
    answer = sidecar(root, "reader-answer.json")
    prompt = sidecar(root, "reader-prompt.md")
    prompt.write_text(
        protocol_reading.reader_prompt(
            protocol.read_text(encoding="utf-8"), str(answer)
        ),
        encoding="utf-8",
    )
    print(f"reader prompt → {prompt}\nthe reader writes → {answer}")
    return 0


def cmd_glance(root: Path) -> int:
    """Write `<dir>.glance-prompt.md`: only the first lines of the bound protocol."""
    protocol, _ = _bound_protocol(root)
    g = protocol_reading.glance(protocol.read_text(encoding="utf-8"))
    answer = sidecar(root, "glance-answer.json")
    prompt = sidecar(root, "glance-prompt.md")
    prompt.write_text(
        protocol_reading.glance_prompt(g.excerpt, str(answer)), encoding="utf-8"
    )
    print(
        f"glance prompt → {prompt} ({g.lines} lines, {g.chars} chars; Summary "
        f"fields inside: {', '.join(g.summary_fields) or 'none'})\n"
        f"the reader writes → {answer}"
    )
    return 0


def cmd_glance_score(root: Path) -> int:
    """Hold the glance answer to the run; `<dir>.glance.json`."""
    protocol, truth = _bound_protocol(root)
    text = protocol.read_text(encoding="utf-8")
    g = protocol_reading.glance(text)
    answer = read_answer(sidecar(root, "glance-answer.json"), "reader")
    try:
        got = protocol_reading.score_glance_answer(answer, truth)
    except ValueError as exc:
        raise SystemExit(f"usability: {exc}") from exc
    hits = protocol_reading.terms_coverage(text, got.unclear, str(protocol))
    out = {
        **asdict(got),
        "lines": g.lines,
        "chars": g.chars,
        "summary_fields": list(g.summary_fields),
        "terms": [asdict(h) for h in hits],
        "truth": asdict(truth),
    }
    sidecar(root, "glance.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"  first {g.lines} lines, {g.chars} chars · Summary fields inside: "
        f"{', '.join(g.summary_fields) or 'none'} · number {got.number_ok}, "
        f"criterion {got.criterion_ok} · answered {len(got.answered)}/"
        f"{len(protocol_reading.GLANCE_CONTENT_KEYS)} · "
        f"unclear {len(got.unclear)}, of them in the Summary "
        f"{sum(h.in_summary for h in hits)}"
    )
    return 0 if got.number_ok is not False and got.criterion_ok is not False else 1


def cmd_terms(root: Path) -> int:
    """The full reader's unclear terms against the Summary and Terms."""
    protocol, _ = _bound_protocol(root)
    answer = read_answer(sidecar(root, "reader-answer.json"), "reader")
    unclear = json.loads(answer).get("unclear") or []
    hits = protocol_reading.terms_coverage(
        protocol.read_text(encoding="utf-8"), unclear, str(protocol)
    )
    for h in hits:
        where = "Summary" if h.in_summary else "Terms" if h.in_terms else "nowhere"
        print(f"  {where:8} {h.term}")
    print(
        f"  {len(hits)} unclear · in the Summary {sum(h.in_summary for h in hits)} "
        f"· in Terms (occurs, static evidence) {sum(h.in_terms for h in hits)}"
    )
    return 0


def cmd_nav(repo: Path, questions: Path, out: Path, shuffle: int | None = None) -> int:
    """Write `<out>.nav-prompt.md` for a cold agent in `repo`; with `shuffle`
    the questions come in an order drawn from that seed, so agents compared
    across two versions do not all meet them in one order."""
    qs = code_navigation.load_questions(questions)
    for q in qs:
        for t in q.truth:
            code_navigation.symbol_span(repo, t)  # a stale truth refuses now
    answer = out.with_name(out.name + ".nav-answer.json")
    prompt = out.with_name(out.name + ".nav-prompt.md")
    flows_list = code_navigation.load_flows(questions)
    choices_list = code_navigation.load_choices(questions)
    if shuffle is not None:
        rng = random.Random(shuffle)
        rng.shuffle(qs)
        rng.shuffle(flows_list)
        rng.shuffle(choices_list)
    flows, choices = tuple(flows_list), tuple(choices_list)
    if not (qs or flows or choices):
        raise SystemExit(f"usability: {questions} holds no question")
    prompt.write_text(
        code_navigation.nav_prompt(repo, qs, str(answer), flows, choices),
        encoding="utf-8",
    )
    print(f"navigation prompt → {prompt}\nthe agent writes → {answer}")
    return 0


def cmd_nav_score(
    repo: Path, questions: Path, out: Path, transcript: Path | None
) -> int:
    """Hold the answers to the truth; `<out>.nav.json`."""
    qs = code_navigation.load_questions(questions)
    answer = read_answer(out.with_name(out.name + ".nav-answer.json"), "agent")
    try:
        got = code_navigation.score_nav_answer(answer, qs, repo)
    except (ValueError, code_navigation.NavigationError) as exc:
        raise SystemExit(f"usability: {exc}") from exc
    eff = code_navigation.effort(transcript, repo) if transcript else None
    try:
        flows = code_navigation.score_flows(
            answer, code_navigation.load_flows(questions)
        )
        choices = code_navigation.score_choices(
            answer, code_navigation.load_choices(questions)
        )
    except ValueError as exc:
        raise SystemExit(f"usability: {exc}") from exc
    out.with_name(out.name + ".nav.json").write_text(
        json.dumps(
            {
                "found": [asdict(f) for f in got],
                "flows": flows,
                "choices": {k: asdict(v) for k, v in choices.items()},
                "effort": asdict(eff) if eff else None,
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for f in got:
        mark = "found" if f.found else "file only" if f.file_right else "missed"
        print(f"  {mark:9} {f.id}: {f.answer} (truth {f.truth})")
    for fid, (n, of) in flows.items():
        print(f"  flow {fid}: {n}/{of} steps named in order")
    for cid, cs in choices.items():
        extra = (f" missed {list(cs.missed)}" if cs.missed else "") + (
            f" invented {list(cs.invented)}" if cs.invented else ""
        )
        print(f"  {'right' if cs.right else 'WRONG':9} {cid}{extra}")
    if choices:
        print(
            f"  {sum(cs.right for cs in choices.values())}/{len(choices)} behaviour "
            f"questions right · {sum(len(cs.missed) for cs in choices.values())} "
            f"missed · {sum(len(cs.invented) for cs in choices.values())} invented"
        )
    print(
        f"  {sum(f.found for f in got)}/{len(got)} found"
        + (
            f" · {eff.seconds}s · {eff.calls} calls {eff.by_tool} · "
            f"{len(eff.files_opened)} files opened"
            if eff
            else ""
        )
    )
    return 0


def cmd_human(
    repo: Path, questions: Path, ids: list[str], out: Path, count_help: bool
) -> int:
    """A person answers behaviour questions about `repo` at the keyboard;
    time per question, the answers and the score go to `<out>.human.json`.
    The verdict is shown only at the end, so it cannot steer later answers."""
    by_id = {c.id: c for c in code_navigation.load_choices(questions)}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise SystemExit(f"usability: no choice question {unknown} in {questions}")
    chosen = [by_id[i] for i in ids]
    print(
        f"Open {repo} in your editor. Answer from the code; nothing is scored until the end."
    )
    answers = code_navigation.human_session(chosen, input, time.monotonic, count_help)
    scored = code_navigation.score_choices(
        json.dumps({a.id: list(a.picked) for a in answers}), chosen
    )
    record = [{**asdict(a), **asdict(scored[a.id])} for a in answers]
    out.with_name(out.name + ".human.json").write_text(
        json.dumps(
            {"repo": str(repo), "answers": record}, indent=1, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    print()
    for r in record:
        print(f"  {'right' if r['right'] else 'WRONG':6} {r['id']} · {r['seconds']} s")
    print(
        f"  {sum(r['right'] for r in record)}/{len(record)} right · "
        f"{round(sum(r['seconds'] for r in record))} s"
        + (
            f" · {sum(r['help_questions'] for r in record)} questions asked"
            if count_help
            else ""
        )
    )
    return 0


def cmd_read_score(root: Path, transcript: Path | None) -> int:
    """Hold the reader's answer to the run's number; `<dir>.reader.json`."""
    _, truth = _bound_protocol(root)
    answer = read_answer(sidecar(root, "reader-answer.json"), "reader")
    try:
        got = protocol_reading.score_reader_answer(answer, truth)
    except ValueError as exc:
        raise SystemExit(f"usability: {exc}") from exc
    seconds = None
    if transcript is not None:
        _, first, last = agent_transcript.read_calls(transcript)
        seconds = round(last - first)
    out = {**asdict(got), "truth": asdict(truth), "reader_seconds": seconds}
    sidecar(root, "reader.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"  {got.correct}/{got.checkable} checkable answers right (number "
        f"{got.number_ok}, criterion {got.criterion_ok}, admissibility "
        f"{got.admissible_ok}) · "
        f"effort {got.effort} · unclear {len(got.unclear)}"
        + (f" · {seconds}s" if seconds is not None else "")
    )
    for u in got.unclear:
        print(f"    unclear: {u}")
    return 0 if got.correct == got.checkable else 1


def score(  # noqa: C901 complexity baseline 2026-10-08
    root: Path, transcript: Path | None = None, agent: str | None = None
) -> int:
    """Score a staged probe: its latest run's number against the truth, the binding, the log; write `<dir>.score.json`.

    `agent` names the model that drew (`fable-5.1`, `sonnet-5.5`): a cloud
    session leaves no transcript, so the operator states it and the score
    carries it — twelve score files named the model only in their file name
    (2026-10-13)."""
    pr = load_probe_run(root)
    probe, run, metrics = pr.probe, pr.run, pr.metrics
    expected = recount(root) if probe.task == "count" else None
    number = bound_to = frozen = tier = None
    form: protocol_reading.Form | None = None
    null_reported = None
    if run is not None:
        number = protocol_reading.metric_number(metrics, probe.metric_key)
        bound_to = pr.protocol_as_recorded if pr.bound else None
        tier = pr.cost_tier
        if probe.task != "count":
            null_reported = any(
                promises.key_kind(k) == "admissibility" for k in metrics
            )
        if pr.bound and pr.protocol is not None:
            from labkit.formats import (
                protocol_block,
            )  # lazy: labkit modules import each other

            p = pr.protocol
            if p.is_file():
                form = protocol_reading.form(p.read_text(encoding="utf-8"))
            try:
                frozen = (
                    protocol_block.head(p.read_text(encoding="utf-8")).frozen
                    if p.is_file()
                    else None
                )
            except protocol_block.BlockError as exc:
                print(f"  protocol head unreadable — {exc}")
                frozen = None
    log = sidecar(root, "log.md")
    trace = parse_log(log.read_text(encoding="utf-8")) if log.is_file() else None
    try:
        measured = (
            agent_transcript.trace(transcript, root, SOURCE_READ)
            if transcript is not None
            else None
        )
    except (agent_transcript.TranscriptError, OSError) as exc:
        raise SystemExit(f"usability: transcript: {exc}") from exc
    sc = Score(
        probe=probe,
        run_id=run.name if run else None,
        number=number,
        expected=expected,
        number_ok=(number is not None and abs(number - expected) <= TOL)
        if expected is not None
        else (number is not None and 0.0 <= number <= 1.0),
        null_reported=null_reported,
        bound_to=bound_to,
        frozen=frozen,
        cost_tier=tier,
        log=trace,
        form=form,
        transcript=measured,
        agent=agent,
    )
    sidecar(root, "score.json").write_text(
        json.dumps(asdict(sc), indent=1), encoding="utf-8"
    )

    rows = [
        ("agent", agent or "not stated (--agent)"),
        ("labkit in probe", probe.labkit_installed),
        ("scaffold sha", probe.scaffold_sha),
        ("run", sc.run_id or "none"),
        (f"number ({probe.metric_key})", "absent" if number is None else str(number)),
        (
            "equals the truth" if expected is not None else "within [0, 1]",
            "yes"
            if sc.number_ok
            else (f"NO (truth {expected})" if expected is not None else "NO"),
        ),
        *(
            [("null condition reported", "yes" if null_reported else "NO")]
            if probe.task != "count"
            else []
        ),
        ("bound to", bound_to or "NOTHING"),
        ("frozen", {True: "yes", False: "no", None: "n/a"}[frozen]),
        ("cost tier", tier or "undeclared"),
    ]
    if trace is None:
        rows.append(("log", "missing — no trace, no measurement"))
    else:
        w = trace.wall_seconds
        rows.append(
            (
                "wall-clock (log span)",
                f"{w // 60}m{w % 60:02d}s" if w is not None else "n/a",
            )
        )
        if trace.gap_seconds:
            g = trace.gap_seconds
            net = (w - g) if w is not None else None
            rows.append(
                (
                    f"silences ≥ {GAP_SECONDS // 60} min",
                    f"{g // 60}m{g % 60:02d}s"
                    + (
                        f" → net {net // 60}m{net % 60:02d}s" if net is not None else ""
                    ),
                )
            )
        if not trace.monotonic:
            rows.append(("log order", "stamps run backwards — span is unreliable"))
        rows += [
            (f"steps · {t}", str(getattr(trace, t))) for t in (*LOG_TAGS, "untagged")
        ]
        rows.append(
            (
                "reads of labkit source / standard",
                str(trace.source_reads)
                + ("" if trace.source_reads == 0 else " — the card did not suffice"),
            )
        )
    if form is not None:
        rows += [
            ("protocol · lines", str(form.lines)),
            (
                "protocol · prose before the first field",
                str(form.prose_before_first_field),
            ),
            ("protocol · · chains (> 2 items)", str(form.chains)),
            ("protocol · longest field (chars)", str(form.longest_field)),
            ("protocol · codes in the Summary", str(form.summary_codes)),
            ("protocol · answer as a table", "yes" if form.answer_has_table else "no"),
        ]
    if measured is not None:
        w, tool = measured.wall_seconds, measured.tool_seconds
        rows += [
            ("transcript · wall-clock", f"{w // 60}m{w % 60:02d}s"),
            ("transcript · in tools / thinking", f"{tool}s / {w - tool}s"),
            ("transcript · tool calls", str(measured.calls)),
            (
                "transcript · labkit commands",
                ", ".join(f"{k} ×{v}" for k, v in sorted(measured.commands.items()))
                or "none",
            ),
            ("transcript · gate refusals", str(measured.refusals)),
            ("transcript · tokens", agent_transcript.describe_tokens(measured.tokens)),
            ("transcript · files opened", str(len(measured.files_read))),
            (
                "transcript · source / standard reads",
                str(len(measured.source_reads))
                + (
                    " — " + "; ".join(measured.source_reads[:3])
                    if measured.source_reads
                    else ""
                ),
            ),
        ]
    width = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k:<{width}}  {v}")
    over = (
        trace is not None
        and trace.wall_seconds is not None
        and trace.wall_seconds - trace.gap_seconds > probe.target_minutes * 60
    )
    print(
        f"  target: one kept number under {probe.target_minutes} min"
        + (" — MISSED" if over else "")
    )
    print(f"→ {sidecar(root, 'score.json')}")
    return 0 if sc.number_ok and bound_to else 1
