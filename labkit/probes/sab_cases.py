"""SAB-like cases for the usability probe: one task per kind, read the way a ScienceAgentBench task reads.

    compute-hrv     heart rate and RMSSD from a resting ECG     trap: the time base (100 Hz)
    fit-assay       a classifier on train / val / test           trap: a column the label is thresholded from
    apply-screen    a supplied screening model on a new cohort   traps: a stale precomputed table, the model's own scaling

Each case gives the agent what a ScienceAgentBench task gives (a dataset
directory, a task text with domain knowledge, a folder tree and previews,
an output file under `pred_results/`) and keeps what it withholds: the
evaluation, which runs at score time and never enters the probe. The agent
has to combine tools — read the files, process them with numpy, pandas,
scipy or scikit-learn, and keep the number through labkit.

Everything is generated from a fixed seed with the standard library (labkit
has no dependencies). What the agent must not see — the true beat times,
the test labels — is regenerated from the seed at score time and never
written into the probe (`truth`, `evaluate`), as the count's truth is
recounted from its files (`usability.recount`).

    plant(root, task)        the dataset under data/raw/<dataset>/; returns its paths
    task_text(root, task)    the task as the sheet shows it (task, knowledge, tree, previews, output)
    truth(root, task)        the kept number's true value, or None where the number has no truth (fit)
    number_within(task, number, expected)   the kept number against the truth or its range
    evaluate(root, task)     (verdict 0|1, detail): the hidden evaluation on pred_results/

Why (2026-10-27): the labkit-paper main round runs six ScienceAgentBench
tasks with known traps; these cases have the same shape at a probe's scale
(seconds, no network, no benchmark data), so a cold agent can show where
labkit's commands, gates and hooks break on a realistic task before a
round costs half an hour per attempt.
"""

from __future__ import annotations

import csv
import io
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from labkit.formats import standard_contract


@dataclass(frozen=True)
class Case:
    """One SAB-like task: what the probe stages and how its outputs are held."""

    task: str  # key into usability.TASKS
    kind: str  # compute | fit | apply — what the kept number asserts
    dataset: str  # directory under data/raw/
    output: str  # the file under pred_results/ the evaluation reads
    metric_key: str  # where the kept number lands in metrics.json — the skeleton's key, never one of the harness's own
    tolerance: (
        float | None
    )  # relative tolerance against the truth; None: no truth, the range [0, 1]
    packages: tuple[str, ...]  # what the agent's venv needs beyond labkit


#: relative error the evaluation allows on heart rate and RMSSD — the R peaks sit on a 10 ms grid
HRV_TOLERANCE = 0.10
#: Where a stamped skeleton with a criterion keeps the number: the estimator
#: skeleton (fit; apply without a model in the loop) reports [C1] as
#: `c1_score`, by labkit's contract (intent-check holds every registered id
#: to its key). Asking for the task's own name (`val_roc_auc`, `agreement`)
#: measured the harness, not labkit: three draws kept the right number under
#: `c1_score` and scored "absent" (docs/usability/2026-10-28-sab-cases-haiku-main.md).
#: A computation has no criterion; its sheet names the key (`rmssd_ms`).
CRITERION_KEY = standard_contract.criterion_key(standard_contract.ESTIMATOR)
CASES = {
    c.task: c
    for c in (
        Case(
            "compute-hrv",
            "compute",
            "biosignals",
            "hrv.csv",
            "rmssd_ms",
            HRV_TOLERANCE,
            ("numpy", "pandas", "scipy"),
        ),
        Case(
            "fit-assay",
            "fit",
            "assay",
            "test_pred.csv",
            CRITERION_KEY,
            None,
            ("numpy", "pandas", "scikit-learn"),
        ),
        Case(
            "apply-screen",
            "apply",
            "screening",
            "screen_pred.csv",
            CRITERION_KEY,
            1e-6,
            ("numpy", "pandas"),
        ),
    )
}
SEED = 20261027
RAW = Path("data") / "raw"
PRED = Path("pred_results")


def case(task: str) -> Case:
    """The case of TASK; refuses a task that is no SAB-like case."""
    if task not in CASES:
        raise KeyError(f"{task!r} is not a SAB-like case ({', '.join(CASES)})")
    return CASES[task]


def _csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return out.getvalue()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- compute-hrv

FS = 100  # Hz — stated in the file name only, as in ScienceAgentBench task 34
HRV_SECONDS = 300
HRV_FILE = "resting_5min_100hz.csv"


def beat_times() -> list[float]:
    """The true R-peak times in seconds: about 75 bpm, a slow sinusoidal
    swing and beat-to-beat noise."""
    rng = random.Random(SEED)
    t, out, i = 0.6, [], 0
    while t < HRV_SECONDS - 0.5:
        out.append(t)
        t += 0.8 + 0.04 * math.sin(2 * math.pi * i / 12) + rng.gauss(0.0, 0.015)
        i += 1
    return out


def ecg_rows() -> list[list[float]]:
    """One row per sample: ECG (R spike, T wave, baseline wander, noise) and a
    respiration trace that is not needed."""
    rng = random.Random(SEED + 1)
    beats = beat_times()
    rows = []
    k = 0
    for n in range(FS * HRV_SECONDS):
        t = n / FS
        while k + 1 < len(beats) and beats[k + 1] <= t - 0.5:
            k += 1
        ecg = 0.1 * math.sin(2 * math.pi * 0.25 * t) + rng.gauss(0.0, 0.02)
        for b in beats[max(k - 1, 0) : k + 3]:
            ecg += math.exp(-(((t - b) / 0.012) ** 2) / 2)
            ecg += 0.25 * math.exp(-(((t - b - 0.25) / 0.04) ** 2) / 2)
        rsp = math.sin(2 * math.pi * 0.25 * t) + rng.gauss(0.0, 0.05)
        rows.append([round(ecg, 5), round(rsp, 5)])
    return rows


def hrv_truth() -> dict[str, float]:
    """Mean heart rate (bpm) and RMSSD (ms) of the true beats."""
    beats = beat_times()
    rr = [b - a for a, b in zip(beats, beats[1:])]
    diffs = [(b - a) * 1000 for a, b in zip(rr, rr[1:])]
    return {
        "heart_rate_bpm": 60 / (sum(rr) / len(rr)),
        "rmssd_ms": math.sqrt(sum(d * d for d in diffs) / len(diffs)),
    }


# --------------------------------------------------------------------------- fit-assay

ASSAY_SPLITS = {"train": 240, "val": 80, "test": 80}
ASSAY_FEATURES = (
    "mol_weight",
    "logp",
    "hbd",
    "hba",
    "rot_bonds",
    "tpsa",
    "aromatic_rings",
)
ASSAY_BAR = 0.75  # test ROC-AUC the hidden evaluation asks for


def assay_rows() -> dict[str, list[dict]]:
    """Compounds per split: seven descriptors on their natural scales, the
    measured IC50 (µM) and the label `active` = IC50 < 10 µM. The IC50 is
    what the label is thresholded from — kept in every split, as task 3's
    related properties were."""
    rng = random.Random(SEED + 2)
    out: dict[str, list[dict]] = {}
    n = 0
    for split, size in ASSAY_SPLITS.items():
        rows = []
        for _ in range(size):
            n += 1
            x = {
                "mol_weight": rng.gauss(380, 90),
                "logp": rng.gauss(2.5, 1.4),
                "hbd": rng.randint(0, 5),
                "hba": rng.randint(1, 10),
                "rot_bonds": rng.randint(0, 12),
                "tpsa": rng.gauss(85, 30),
                "aromatic_rings": rng.randint(0, 4),
            }
            score = (
                0.9 * (x["logp"] - 2.5) / 1.4
                - 0.7 * (x["tpsa"] - 85) / 30
                + 0.5 * (x["aromatic_rings"] - 2)
                - 0.3 * (x["mol_weight"] - 380) / 90
                + rng.gauss(0.0, 1.0)
            )
            ic50 = 10 * math.exp(-score)
            rows.append(
                {
                    "compound_id": f"C{n:04d}",
                    **{k: round(v, 3) for k, v in x.items()},
                    "ic50_um": round(ic50, 4),
                    "active": int(ic50 < 10),
                }
            )
        out[split] = rows
    return out


def roc_auc(labels: list[int], scores: list[float]) -> float:
    """ROC-AUC as the Mann-Whitney statistic, ties counted half."""
    pos = [s for y, s in zip(labels, scores) if y == 1]
    neg = [s for y, s in zip(labels, scores) if y == 0]
    if not pos or not neg:
        raise ValueError("roc_auc: both classes must be present")
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


# --------------------------------------------------------------------------- apply-screen

SCREEN_FEATURES = ("age", "systolic_bp", "bmi", "hba1c", "ldl", "smoker")
SCREEN_SITES = {
    "north": 0.0,
    "east": 0.0,
    "south": 1.0,
}  # south is older and heavier: its own statistics differ


def screen_model() -> dict:
    """The supplied model, version 2.1: standardise each feature with the
    model's own mean and std, logistic of the weighted sum, flag at 0.5."""
    return {
        "name": "cardiometabolic risk screen",
        "version": "2.1",
        "features": list(SCREEN_FEATURES),
        "mean": [52.0, 128.0, 27.0, 5.7, 3.1, 0.25],
        "std": [12.0, 16.0, 4.5, 0.8, 0.9, 0.43],
        "weights": [0.8, 0.6, 0.4, 1.1, 0.5, 0.7],
        "intercept": -1.2,
        "threshold": 0.5,
    }


def cohort_rows() -> list[dict]:
    """300 persons at three sites; a clinician's label for about a third."""
    rng = random.Random(SEED + 3)
    rows = []
    for i in range(300):
        site = list(SCREEN_SITES)[i % 3]
        shift = SCREEN_SITES[site]
        x = {
            "age": rng.gauss(52 + 8 * shift, 12),
            "systolic_bp": rng.gauss(128 + 6 * shift, 16),
            "bmi": rng.gauss(27 + 2 * shift, 4.5),
            "hba1c": rng.gauss(5.7 + 0.4 * shift, 0.8),
            "ldl": rng.gauss(3.1, 0.9),
            "smoker": int(rng.random() < 0.25),
        }
        x = {k: (v if k == "smoker" else round(v, 2)) for k, v in x.items()}
        p = screen_probability(x)
        label = (
            ""
            if rng.random() > 0.33
            else int(rng.random() < min(max(p + rng.gauss(0, 0.15), 0), 1))
        )
        rows.append(
            {"person_id": f"P{i + 1:03d}", "site": site, **x, "clinician_label": label}
        )
    return rows


def screen_probability(x: dict, model: dict | None = None) -> float:
    """The supplied model's probability for one person X (MODEL: another version, for the stale table)."""
    m = model or screen_model()
    z = m["intercept"] + sum(
        w * (float(x[f]) - mu) / sd
        for f, w, mu, sd in zip(m["features"], m["weights"], m["mean"], m["std"])
    )
    return 1 / (1 + math.exp(-z))


def stale_scores() -> list[list]:
    """The precomputed table of the retired version 1.4 (other weights, no
    hba1c): plausible, and wrong for 2.1."""
    old = {
        **screen_model(),
        "version": "1.4",
        "weights": [0.9, 0.7, 0.5, 0.0, 0.4, 0.9],
        "intercept": -0.9,
    }
    return [
        [r["person_id"], round(screen_probability(r, old), 6), "1.4"]
        for r in cohort_rows()
    ]


def screen_truth() -> dict[str, float]:
    """Per person the probability of model 2.1; and the agreement (accuracy)
    of its flag with the clinician's label over the labelled persons."""
    m = screen_model()
    rows = cohort_rows()
    probs = {r["person_id"]: screen_probability(r) for r in rows}
    labelled = [r for r in rows if r["clinician_label"] != ""]
    agree = sum(
        int(probs[r["person_id"]] >= m["threshold"]) == r["clinician_label"]
        for r in labelled
    )
    return {**probs, "agreement": agree / len(labelled)}


# --------------------------------------------------------------------------- the three entry points


def plant(root: Path, task: str) -> list[Path]:
    """Write the task's dataset under data/raw/<dataset>/; returns the files.
    Side effects: writes them; nothing the evaluation withholds."""
    c = case(task)
    d = root / RAW / c.dataset
    d.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    if task == "compute-hrv":
        files[HRV_FILE] = _csv(["ECG", "RSP"], ecg_rows())
    elif task == "fit-assay":
        cols = ["compound_id", *ASSAY_FEATURES, "ic50_um", "active"]
        for split, rows in assay_rows().items():
            # test.csv loses the label and keeps the IC50 it is thresholded from — task 3's leak
            keep = [k for k in cols if not (split == "test" and k == "active")]
            files[f"{split}.csv"] = _csv(keep, [[r[k] for k in keep] for r in rows])
    elif task == "apply-screen":
        cols = ["person_id", "site", *SCREEN_FEATURES, "clinician_label"]
        files["cohort.csv"] = _csv(cols, [[r[k] for k in cols] for r in cohort_rows()])
        files["model.json"] = json.dumps(screen_model(), indent=1) + "\n"
        files["precomputed_scores.csv"] = _csv(
            ["person_id", "risk_score", "model_version"], stale_scores()
        )
    written = []
    for name, text in files.items():
        (d / name).write_text(text, encoding="utf-8")
        written.append(d / name)
    return written


TASK_TEXT = {
    "compute-hrv": (
        'Use the recording in "resting_5min_100hz.csv" to compute the mean heart rate and the heart rate '
        "variability index RMSSD. Find the R peaks of the ECG signal, derive the RR intervals, and save the mean "
        "heart rate in beats per minute and the RMSSD in milliseconds to 'pred_results/hrv.csv' with the columns "
        "heart_rate_bpm and rmssd_ms (one row).",
        "RMSSD is the root mean square of the successive differences between adjacent RR intervals. You may use "
        "scipy.signal or NeuroKit-style peak detection; the ECG carries baseline wander and noise.",
    ),
    "fit-assay": (
        "Train a model on the assay data to predict whether a compound is active. Choose the model and its "
        "hyperparameters with the validation split, then save the predicted probability of being active for every "
        "test compound, in the order of test.csv, to 'pred_results/test_pred.csv' with the columns compound_id and "
        "p_active.",
        "A compound is active when its IC50 in the primary assay is below 10 µM. The descriptors are on their "
        "natural scales (molecular weight in Da, TPSA in Å², counts as integers).",
    ),
    "apply-screen": (
        "Apply the supplied screening model (model.json) unchanged to every person in cohort.csv. Save each "
        "person's predicted probability and flag (1 if the probability is at least the model's threshold) to "
        "'pred_results/screen_pred.csv' with the columns person_id, probability and flag, and report the "
        "agreement (accuracy) of the flag with the clinician's label over the persons who have one.",
        "The model standardises each feature with its own mean and standard deviation, takes the weighted sum plus "
        "the intercept and applies the logistic function. A clinician's label is 1 for a referral, 0 otherwise, "
        "and empty where no clinician saw the person.",
    ),
}


def _tree(c: Case, files: list[Path]) -> str:
    return "\n".join([f"|-- {c.dataset}/", *(f"|---- {p.name}" for p in sorted(files))])


def _preview(path: Path, lines: int = 4) -> str:
    head = path.read_text(encoding="utf-8").splitlines()[:lines]
    return (
        f"[START Preview of {path.parent.name}/{path.name}]\n"
        + "\n".join(head)
        + f"\n...\n[END Preview of {path.parent.name}/{path.name}]"
    )


def task_text(root: Path, task: str) -> str:
    """The task as the sheet shows it, after ScienceAgentBench's prompt: task,
    domain knowledge, the dataset's tree and previews of its files."""
    c = case(task)
    files = sorted((root / RAW / c.dataset).iterdir())
    inst, knowledge = TASK_TEXT[task]
    previews = "\n".join(_preview(p) for p in files)
    return (
        f"Task:\n{inst}\n\nDomain knowledge:\n{knowledge}\n\n"
        f"The dataset is at `{(RAW / c.dataset).as_posix()}/`. Its directory structure:\n```\n{_tree(c, files)}\n```\n"
        f"Previews of the dataset files:\n{previews}"
    )


def truth(root: Path, task: str) -> float | None:
    """The kept number's true value — regenerated from the seed, never read
    from a file the agent could write; None for the fit (a fitted model's
    validation score has no single true value). apply-screen's `c1_score` is
    the agreement when the skeleton's SCORE is accuracy; another SCORE is
    named by `meaning_gap`, not taken for a wrong number."""
    del root  # the truth depends on the seed alone; the probe directory is not read
    if task == "compute-hrv":
        return hrv_truth()["rmssd_ms"]
    if task == "apply-screen":
        return screen_truth()["agreement"]
    case(task)
    return None


@dataclass(frozen=True)
class Meaning:
    """What a case's kept number is, held beside its key: the skeleton's
    SCORE, the labelled ITEMS it is scored over (metrics' `n_items`), and
    the quantity in words (SAID). A key that matches proves the name only;
    SCORE and ITEMS show whether the number is the task's (2026-10-28:
    fit-assay's `c1_score` is an out-of-fold AUC over train and val, never
    an AUC on the validation split alone)."""

    score: str
    items: int
    said: str


def meaning(task: str) -> Meaning | None:
    """What TASK's kept number means (`Meaning`); None for a computation,
    whose sheet names its own key and whose number has its own truth.
    Refuses a task that is no SAB-like case."""
    if task == "fit-assay":
        return Meaning(
            "auc",
            ASSAY_SPLITS["train"] + ASSAY_SPLITS["val"],
            "the out-of-fold ROC-AUC over the train and val compounds, the "
            "skeleton's held-out score — not an AUC on the validation split alone",
        )
    if task == "apply-screen":
        return Meaning(
            "accuracy",
            sum(1 for r in cohort_rows() if r["clinician_label"] != ""),
            "the agreement (accuracy) of the flag with the clinician's label "
            "over the labelled persons",
        )
    case(task)
    return None


def meaning_gap(task: str, score: object, n_items: object) -> str | None:
    """Why the kept number is not the quantity TASK means (`meaning`), or
    None: the run's SCORE (its config.json) and the labelled items it is
    over (metrics' N_ITEMS) against the case's. A sentence naming each
    difference, never a number that only looks valid."""
    m = meaning(task)
    if m is None:
        return None
    off = []
    if score != m.score:
        off.append(f"its SCORE is {score!r}, not {m.score!r}")
    if n_items != m.items:
        off.append(f"it is over {n_items!r} labelled item(s), not {m.items}")
    if not off:
        return None
    return (
        f"{case(task).metric_key} is not the task's number — {'; '.join(off)}; "
        f"the task's number is {m.said}"
    )


def number_within(task: str, number: float | None, expected: float | None) -> bool:
    """The kept number against the truth within the case's relative tolerance,
    or — without a truth — present and within [0, 1]."""
    tol = case(task).tolerance
    if number is None:
        return False
    if expected is None or tol is None:
        return 0.0 <= number <= 1.0
    return abs(number - expected) <= tol * abs(expected)


def evaluate(root: Path, task: str) -> tuple[int, str]:
    """The hidden evaluation on pred_results/<output>: (1 pass | 0 fail, detail).
    An output the evaluation cannot read is a fail with its reason, as
    ScienceAgentBench counts it — never a crash."""
    c = case(task)
    path = root / PRED / c.output
    if not path.is_file():
        return 0, f"{PRED / c.output} missing"
    try:
        rows = _read_csv(path)
        if task == "compute-hrv":
            t = hrv_truth()
            got = {k: float(rows[0][k]) for k in t}
            err = {k: abs(got[k] - t[k]) / t[k] for k in t}
            tol = HRV_TOLERANCE
            return int(all(e <= tol for e in err.values())), f"relative error {err}"
        if task == "fit-assay":
            test = assay_rows()["test"]
            if [r["compound_id"] for r in rows] != [r["compound_id"] for r in test]:
                return 0, "compound_id differs from test.csv's order"
            auc = roc_auc(
                [r["active"] for r in test], [float(r["p_active"]) for r in rows]
            )
            return int(auc >= ASSAY_BAR), f"test ROC-AUC {auc:.4f} (bar {ASSAY_BAR})"
        t = screen_truth()
        m = screen_model()
        wrong = [
            r["person_id"]
            for r in rows
            if abs(float(r["probability"]) - t[r["person_id"]]) > 1e-6
            or int(float(r["flag"])) != int(t[r["person_id"]] >= m["threshold"])
        ]
        missing = {r["person_id"] for r in cohort_rows()} - {
            r["person_id"] for r in rows
        }
        return int(
            not wrong and not missing
        ), f"{len(wrong)} persons off model 2.1, {len(missing)} missing"
    except (KeyError, ValueError, IndexError) as exc:
        return 0, f"unreadable: {type(exc).__name__}: {exc}"
