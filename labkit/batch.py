"""batch — a resumable, inspectable output file for item-by-item runs.

The three habits every batch script needs and every prototype skips: don't let
a second process write the same file, don't redo what is already done, and be
able to say what is missing without re-running anything. Hand-rolling them
costs ~40 lines each time and gets skipped exactly when it matters — an
interrupted connection then costs the whole run (2026-08-12: a socket timeout
killed a scoring run at 49 of 96 items; only the resume made it a non-event).

    import batch

    with batch.Store(out_path) as store:            # takes <out>.lock
        for rec in store.pending(records):          # skips ids already scored
            store.append(score(rec))                # one line, flushed
    print(store.status(records))

Resuming is re-running the same command: ids in the output file are skipped.
Records are matched by `id_key` (default "id"), so the input file and the
output file are joined on it — a partial output stays a valid output.

Deliberately NOT here: retries (they belong at the call that fails, see
`llm.complete`) and yield counting (what "complete" means is domain-specific —
count it in the experiment and report it, Arbeitsstandard §2).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Iterable, Iterator


class Store:
    """Append-only JSONL output with a lock, resume-by-id and a status view.

    `prov`: per-row provenance stamp. Provenance normally lives in the join
    row -> file -> runs.tsv -> config.json; copy, filter or merge the file and
    the join dies — the file goes silent about what produced it (that is how
    old/new hybrid files happen). With `prov` every appended record carries a
    `_prov` object, so each row stays self-contained:

        with batch.Store(out, prov={**llm.provenance("gpt-oss"),
                                    "run": run.run_id}) as store:

    Values may be callables — evaluated at append time, because with a
    multi-endpoint alias the serving endpoint differs per row
    (llm.provenance passes `llm.last_endpoint` as a callable). The stamp
    holds the pointer (run) plus the facts that die with the join (model
    identity, endpoint instance); everything else stays in the run config.
    An explicit `_prov` already present in a record is never overwritten.
    """

    def __init__(self, path: str | Path, id_key: str = "id",
                 prov: dict | None = None):
        self.path = Path(path)
        self.id_key = id_key
        self.prov = dict(prov) if prov else {}
        self.lock = self.path.with_suffix(self.path.suffix + ".lock")
        self._fh = None

    # -- lock -------------------------------------------------------------
    def __enter__(self) -> "Store":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.lock.open("x", encoding="utf-8") as f:
                f.write(f"pid {os.getpid()} · {time.strftime('%Y-%m-%dT%H:%M:%S')} · "
                        f"{' '.join(sys.argv)}\n")
        except FileExistsError:
            raise SystemExit(
                f"{self.lock} exists — another run is writing this output:\n"
                f"  {self.lock.read_text(encoding='utf-8').strip()}\n"
                f"Use a different output file, or delete the lock if that run "
                f"is dead (`.venv/bin/runlog <area>` shows which "
                f"runs are still alive).")
        self._fh = self.path.open("a", encoding="utf-8")
        return self

    def __exit__(self, *exc) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self.lock.unlink(missing_ok=True)

    # -- reading ----------------------------------------------------------
    def records(self) -> list[dict]:
        """Everything written so far. A truncated final line (a process killed
        mid-write) is reported and skipped, never silently dropped. A `_meta`
        header line (see write_dataset) is documentation, not a record —
        skipped here, so every consumer reading through this sees data only."""
        if not self.path.exists():
            return []
        out = []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and "_meta" in obj:
                    continue
                out.append(obj)
            except json.JSONDecodeError:
                where = "last" if i == len(lines) - 1 else f"line {i + 1}"
                print(f"batch: skipping unparseable {where} line of {self.path} "
                      f"(interrupted write?) — it will be redone",
                      file=sys.stderr)
        return out

    def done_ids(self) -> set:
        return {r[self.id_key] for r in self.records() if self.id_key in r}

    def pending(self, records: Iterable[dict]) -> Iterator[dict]:
        """The input records that have no output line yet, in input order."""
        done = self.done_ids()
        for rec in records:
            if rec[self.id_key] not in done:
                yield rec

    # -- writing ----------------------------------------------------------
    def append(self, record: dict) -> None:
        """One record, one line, flushed — a crash costs the current item only."""
        if self._fh is None:
            raise RuntimeError("Store.append outside the `with` block")
        if self.prov and "_prov" not in record:
            record = {**record,
                      "_prov": {k: (v() if callable(v) else v)
                                for k, v in self.prov.items()}}
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    # -- status -----------------------------------------------------------
    def status(self, records: Iterable[dict] | None = None) -> dict:
        """done / missing / stray by id, plus who holds the lock. No model load."""
        done = self.records()
        done_ids = {r[self.id_key] for r in done if self.id_key in r}
        info: dict = {"path": str(self.path), "done": len(done_ids)}
        if records is not None:
            want = [r[self.id_key] for r in records]
            missing = [i for i in want if i not in done_ids]
            info["total"] = len(want)
            info["missing"] = len(missing)
            info["missing_ids"] = missing[:10]
            stray = sorted(done_ids - set(want))
            if stray:                     # output holds ids the input never had
                info["stray"] = stray[:10]
        if self.lock.exists():
            info["locked_by"] = self.lock.read_text(encoding="utf-8").strip()
        return info


def write_dataset(path: Path, rows: list[dict], *, about: str,
                  fields: dict[str, str], producer: str) -> None:
    """Write a prepared dataset that explains itself: first line is a `_meta`
    header (about, field legend, producer), then one record per line.

    Store.records() — and everything reading through it, e.g.
    answers.read_jsonl — skips the header, so consumers see data only; a
    human opening the file sees FIRST what it is. Every row is validated
    against the legend: field drift (a renamed or forgotten column) fails
    loudly at write time, not silently at analysis time.
    """
    for i, r in enumerate(rows):
        extra, missing = set(r) - fields.keys(), fields.keys() - set(r)
        if extra or missing:
            raise ValueError(f"row {i} does not match the field legend "
                             f"(extra: {sorted(extra)}, missing: {sorted(missing)})")
    meta = {"_meta": {"about": about, "fields": fields, "producer": producer}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n"
                            for x in [meta, *rows]), encoding="utf-8")
