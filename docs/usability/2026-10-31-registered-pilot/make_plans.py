"""Write plans/<task>.md, the control arm's PLAN.md, from protocols/<task>.md:
the same fields and the verbatim task, without labkit's terms."""

import re
from pathlib import Path

HERE = Path(__file__).parent
KEEP = (
    "Terms of this protocol",
    "Question / hypothesis",
    "Inference criterion",
    "Quality check",
    "Data / scope",
    "Data profile",
    "Model / tool",
    "Null condition / anchors (in the same run)",
    "Exclusions / filters",
    "Unit",
)
PLAIN = [
    ("at least the null lane's accuracy plus margin", "at least the placebo prompt's accuracy plus margin"),
    ("the null lane asks the placebo", "the placebo prompt asks"),
    ("the item fields 00_prepare.py writes from the record", "the record's fields"),
    ("which the prompts name; ", ""),
    (" (a placebo shown the question answered it: part 0, null 27 of 50 against 21.2)", ""),
    (", which the model template computes exactly (`_expected_correct`)", ", computed exactly"),
    ("The lane must sit within", "The placebo prompt's correct count must sit within"),
    ("a null lane further off tracks the gold, and the run has no verdict",
     "a placebo further off tracks the gold, and the run gives no verdict"),
    ("one call per item and lane (50 labelled questions × registered and null lane)",
     "one call per labelled question and prompt (50 × the question prompt and the placebo prompt)"),
    (" (the model template's parser)", ""),
    (" (the model template's parser, labkit 0.104.4)", ""),
    (
        "; the files stay outside git, pinned by the sha256 the run records for them",
        "; the files are used as supplied, not copied or changed",
    ),
    (
        "; the file stays outside git, pinned by the sha256 the run records for it",
        "; the file is used as supplied, not copied or changed",
    ),
    ("; then the counts protocol-fill --data-counts writes after 00_prepare.py", ""),
    (" (the skeleton's fit plan at low repeat cost)", ""),
    (", built by `make_estimator()` in scripts/01_measure.py", ""),
    ("n/a — no model call; the instrument is ", ""),
    ("**Terms of this protocol:**", "**Terms:**"),
    ("the registered lane's ", "the "),
    ("the null lane's ", "the "),
    ("the registered ", "the "),
    (
        ". The model template's null check at half the items (two classes) does not apply to three answers; "
        "the measurement script replaces it with this one",
        "",
    ),
    ("a broken null lane", "a broken null check"),
    ("[criterion-1] ", ""),
    ("[quality-check-1] ", ""),
    ("[quality-check-2] ", ""),
]
LABKIT_WORDS = re.compile(
    r"labkit|protocol-fill|runlog|sha256|repeat cost|skeleton|template|\blane\b|\[criterion|\[quality"
)


def plan(protocol: str) -> str:
    head = re.search(r"^# Experiment protocol: (.+)$", protocol, re.M)
    if head is None:
        raise ValueError("protocol without its '# Experiment protocol: <title>' line")
    title = head.group(1)
    lines = [
        f"# Plan: {title}",
        "",
        "The plan for this task, written before any work on it. Follow it; where it cannot be followed, say so in REPORT.md.",
        "",
    ]
    for label in KEEP:
        m = re.search(rf"^- \*\*{re.escape(label)}:\*\* (.*)$", protocol, re.M)
        if m:
            lines.append(
                f"- **{label.replace(' (in the same run)', '')}:** {m.group(1)}"
            )
    prompt = re.search(
        r"\*\*Prompt \(verbatim, per variant\):\*\*\n\n  ```text\n(.*?)\n  ```",
        protocol,
        re.S,
    )
    if prompt:
        lines += ["- **Prompt (verbatim):**", "", "  ```text", prompt.group(1), "  ```"]
    consts = [
        (pid, c)
        for pid, c in re.findall(
            r'^id = "([\w-]+)"\n.*?\nconstants = \{(.*?)\}', protocol, re.M | re.S
        )
        if c.strip()
    ]
    names = {
        "criterion-1": "criterion",
        "quality-check-1": "first check",
        "quality-check-2": "null check",
    }
    if consts:
        lines += [
            "",
            "Fixed numbers, set before any result: "
            + "; ".join(f"{names[p]}: {c.strip()}" for p, c in consts)
            + ".",
        ]
    task = re.search(
        r"^## Task \(verbatim, as given to the agent\)\n\n.*?\n\n(  ```text\n.*?\n  ```)",
        protocol,
        re.M | re.S,
    )
    if task is None:
        raise ValueError(
            f"{title}: no '## Task (verbatim, as given to the agent)' section with a text block"
        )
    lines += ["", "## Task (verbatim)", "", task.group(1)]
    text = "\n".join(lines) + "\n"
    # labkit's pins of data outside git (Data / scope) are the lab arm's; the plan says the same in words
    text = re.sub(r"; they stay outside git, pinned by labkit's source digest[^\n]*",
                  "; the files are used as supplied, not copied or changed", text)
    for a, b in PLAIN:
        text = text.replace(a, b)
    left = LABKIT_WORDS.findall(text)
    if left:
        raise ValueError(f"{title}: labkit words left in the plan: {left}")
    return text


if __name__ == "__main__":
    for f in sorted((HERE / "protocols").glob("*.md")):
        (HERE / "plans" / f.name).write_text(plan(f.read_text()))
        print(f.name, "written")
