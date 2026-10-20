"""usability_command — the `usability` console command.

`usability stage` plants a probe repo from labkit's own scaffold,
`restamp` moves it to the installed version, `log` appends a step to
the probe's log, `score` and the `*-score` subcommands score a finished
probe, `archive` keeps its record. The work is done in `usability`
(staging) and `usability_score` (scoring); this module parses the
arguments and dispatches.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from labkit.probes import agent_transcript
from labkit.formats import console
from labkit.probes.usability import LOG_TAGS, TASKS, log_step, restamp, stage
from labkit.probes.usability_score import (
    archive,
    cmd_glance,
    cmd_glance_score,
    cmd_human,
    cmd_nav,
    cmd_nav_score,
    cmd_read_score,
    cmd_reader,
    cmd_terms,
    score,
)


#: the one spelling of the log line's command line, in its usage and its refusal
LOG_USAGE = "usability log TAG TEXT [--log FILE] [-- CMD ...]"


def main(argv: list[str]) -> int:  # noqa: C901 complexity baseline 2026-10-08
    """Command line of `usability`: stage probes and score what cold agents and readers did."""
    # only `log` runs a command; for the others a `--` is argparse's own
    words, log_cmd = console.split_command(argv)
    if argv[:1] == ["log"]:
        argv = words
    ap = argparse.ArgumentParser(
        prog="usability", description=(__doc__ or "").split("\n\n")[0]
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage", help="stamp a probe lab repo with one kept-number task")
    s.add_argument("dir")
    s.add_argument("--venv", help="link this venv instead of creating one")
    s.add_argument(
        "--restamp",
        action="store_true",
        help="stamp the probe in DIR again with this labkit, in place; task "
        "and tier come from <dir>.probe.json",
    )
    s.add_argument(
        "--keep",
        action="append",
        metavar="PATH",
        help="with --restamp: a hand-edited path the stamp leaves alone "
        "(repeatable; default: the paths kept last time)",
    )
    s.add_argument(
        "--cost",
        choices=("seconds", "minutes", "hours", "unset"),
        metavar="TIER",
        help="the cost tier stamped into the protocol (default: the task's, "
        "seconds); unset = the agent declares it, the full form is stamped",
    )
    s.add_argument(
        "--model",
        action="store_true",
        help="a model in the loop: the full measure skeleton (prompt, parser, "
        "probe) and, at seconds, the three model fields in the cut "
        "(default for --task judge)",
    )
    s.add_argument(
        "--task",
        choices=sorted(TASKS),
        help="which task sheet and fixture: count (deterministic, the default) "
        "or judge (a model)",
    )
    lg = sub.add_parser(
        "log",
        help="append one step line with the time, then run CMD",
        usage=LOG_USAGE,
        epilog="CMD: every word after the first `--`, run after the line is "
        "written; the exit code is CMD's (0 without one). TEXT cannot begin "
        "with `-`.",
    )
    lg.add_argument("tag", choices=LOG_TAGS)
    lg.add_argument("text", help="the step, in a few words")
    lg.add_argument(
        "--log",
        default="log.md",
        metavar="FILE",
        help="the log file (default: ./log.md)",
    )
    c = sub.add_parser("score", help="number, binding and log of a finished probe")
    c.add_argument("dir")
    c.add_argument(
        "--transcript",
        help="the agent's session transcript (JSONL): wall-clock, tool calls, "
        "files and refusals measured instead of self-reported",
    )
    c.add_argument(
        "--agent",
        help="the model that drew, e.g. fable-5.1 — stated by the operator, kept in the score",
    )
    c.add_argument(
        "--archive",
        metavar="DIR",
        help="with --transcript: keep transcript (gzip), timeline and score in DIR",
    )
    tr = sub.add_parser("trace", help="the timeline of one agent transcript")
    tr.add_argument("transcript")
    rd = sub.add_parser(
        "reader", help="write the cold-reader prompt for the probe's protocol"
    )
    rd.add_argument("dir")
    rs = sub.add_parser(
        "read-score", help="hold the reader's answer to the run's number"
    )
    rs.add_argument("dir")
    rs.add_argument("--transcript", help="the reader's transcript: its reading time")
    gl = sub.add_parser(
        "glance", help="write the prompt for a reader who sees only the first lines"
    )
    gl.add_argument("dir")
    gs = sub.add_parser("glance-score", help="hold the glance answer to the run")
    gs.add_argument("dir")
    te = sub.add_parser(
        "terms", help="the reader's unclear terms against the Summary and Terms"
    )
    te.add_argument("dir")
    nv = sub.add_parser(
        "nav", help="write the prompt for a cold agent finding its way in a repo"
    )
    nv.add_argument("repo")
    nv.add_argument("--questions", required=True, help="TOML: questions and truth")
    nv.add_argument(
        "--out", required=True, help="prefix of the prompt and answer files"
    )
    nv.add_argument("--shuffle", type=int, help="seed: draw the question order from it")
    ns = sub.add_parser("nav-score", help="hold the navigation answers to the truth")
    ns.add_argument("repo")
    ns.add_argument("--questions", required=True)
    ns.add_argument("--out", required=True)
    ns.add_argument("--transcript", help="the agent's transcript: its effort")
    hu = sub.add_parser(
        "human", help="a person answers behaviour questions at the keyboard, timed"
    )
    hu.add_argument("repo")
    hu.add_argument("--questions", required=True, help="TOML with [[choice]] questions")
    hu.add_argument(
        "--ids", required=True, help="the question ids to ask, comma-separated"
    )
    hu.add_argument("--out", required=True, help="prefix of the record file")
    hu.add_argument(
        "--count-help",
        action="store_true",
        help="ask after each answer how many questions went to an assistant",
    )
    args, stray = ap.parse_known_args(argv)
    if stray and args.cmd == "log":
        lg.error(
            f"unexpected {' '.join(map(repr, stray))} — the command goes after "
            f"`--`: {LOG_USAGE}"
        )
    if stray:
        ap.error(f"unrecognized arguments: {' '.join(stray)}")
    if args.cmd == "human":
        return cmd_human(
            Path(args.repo).resolve(),
            Path(args.questions).resolve(),
            args.ids.split(","),
            Path(args.out).resolve(),
            args.count_help,
        )
    if args.cmd == "nav":
        return cmd_nav(
            Path(args.repo).resolve(),
            Path(args.questions).resolve(),
            Path(args.out).resolve(),
            args.shuffle,
        )
    if args.cmd == "nav-score":
        return cmd_nav_score(
            Path(args.repo).resolve(),
            Path(args.questions).resolve(),
            Path(args.out).resolve(),
            Path(args.transcript).resolve() if args.transcript else None,
        )
    if args.cmd == "log":
        return log_step(Path(args.log), args.tag, args.text, log_cmd or [])
    if args.cmd == "glance":
        return cmd_glance(Path(args.dir).resolve())
    if args.cmd == "glance-score":
        return cmd_glance_score(Path(args.dir).resolve())
    if args.cmd == "terms":
        return cmd_terms(Path(args.dir).resolve())
    if args.cmd == "reader":
        return cmd_reader(Path(args.dir).resolve())
    if args.cmd == "read-score":
        return cmd_read_score(
            Path(args.dir).resolve(),
            Path(args.transcript).resolve() if args.transcript else None,
        )
    if args.cmd == "trace":
        try:
            lines = agent_transcript.timeline(Path(args.transcript))
        except (agent_transcript.TranscriptError, OSError) as exc:
            raise console.Refused("usability", f"transcript: {exc}") from exc
        print("\n".join(lines))
        return 0
    root = Path(args.dir).resolve()
    if args.cmd == "stage":
        venv = Path(args.venv).resolve() if args.venv else None
        if args.restamp:
            if args.cost or args.task or args.model:
                ap.error("--restamp takes task, tier and model from <dir>.probe.json")
            return restamp(root, args.keep, venv)
        if args.keep:
            ap.error("--keep belongs to --restamp")
        return stage(
            root, venv, cost=args.cost, task=args.task or "count", model=args.model
        )
    if args.archive and not args.transcript:
        ap.error("--archive needs --transcript")
    transcript = Path(args.transcript).resolve() if args.transcript else None
    rc = score(root, transcript, args.agent)
    if args.archive and transcript is not None:
        for path in archive(root, transcript, Path(args.archive)):
            print(f"  archived {path}")
    return rc


def cli() -> None:
    """Console entry point of `usability`."""
    console.exit_with(main)


if __name__ == "__main__":
    cli()
