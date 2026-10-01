"""Keep the counts in GAPS.md, README.md, and CLAUDE.md in step with the
content under scenarios/.

    python tools/sync_docs.py          # rewrite the docs
    python tools/sync_docs.py --check  # exit 1 if they are out of date

It only touches numbers: per-category tutorial/incident counts, the
totals, Writing Lab and career-path counts, and the 'Part N' numbers of
GAPS.md's headings (renumbered in file order, so a new part can be
inserted anywhere). The prose around them is written by hand. A category
with no row yet is reported, not invented: add its row, then run again.
tests/test_docs_sync.py fails when the docs are stale.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scenario_loader  # noqa: E402

# Table label per category, where it differs from a plain capitalised key.
LABELS = {
    "cicd": "CI/CD", "mlops": "MLOps", "aws": "AWS", "gcp": "Google Cloud",
    "servers": "Server Fleet Ops", "sre": "SRE", "systemdesign": "System Design",
    "webservers": "Web Servers & Proxies", "identity": "Identity & Secrets",
    "finops": "FinOps", "landscape": "The Wider Landscape",
    "dataeng": "Data Engineering",
}

# How each category's GAPS.md part heading starts, where it isn't the label.
GAPS_HEADINGS = {
    "servers": "Server Fleet Operations", "webservers": "Web Servers and Proxies",
    "identity": "Identity and Secrets",
}


def label(category: str) -> str:
    return LABELS.get(category, category.capitalize())


def counts() -> dict:
    per_category = {
        c: (len(scenario_loader.load_tutorials(c)), len(scenario_loader.load_incidents(c)))
        for c in scenario_loader.list_categories()
    }
    return {
        "per_category": per_category,
        "tutorials": sum(t for t, _ in per_category.values()),
        "incidents": sum(i for _, i in per_category.values()),
        "labs": len(scenario_loader.load_yaml_labs()),
        "paths": len(scenario_loader.load_career_paths()),
        "categories": len(per_category),
    }


def _sub(text: str, pattern: str, repl: str, problems: list, what: str, flags=re.M) -> str:
    new, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n == 0:
        problems.append(f"not found: {what}")
    return new


def sync_gaps(text: str, c: dict, problems: list) -> str:
    # Renumber the parts in file order.
    numbers = iter(range(1, 1000))
    text = re.sub(r"^# Part \d+ — ", lambda m: f"# Part {next(numbers)} — ", text, flags=re.M)

    for cat, (tut, inc) in c["per_category"].items():
        row = re.escape(label(cat))
        text = _sub(text, rf"^\| {row} \| \d+ \| \d+ \|", f"| {label(cat)} | {tut} | {inc} |",
                    problems, f"GAPS.md table row for '{label(cat)}'")
        # The '**Content:** N tutorials, M incidents' line under the category's own part.
        heading = re.escape(GAPS_HEADINGS.get(cat, label(cat)))
        part = re.search(rf"^# Part \d+ — {heading}.*?(?=^# Part \d+ — |\Z)", text, flags=re.M | re.S)
        if part is None:
            problems.append(f"not found: GAPS.md part for '{label(cat)}'")
            continue
        body = re.sub(r"\*\*Content:\*\* \d+ tutorials, \d+ incidents",
                      f"**Content:** {tut} tutorials, {inc} incidents", part.group(0), count=1)
        text = text[:part.start()] + body + text[part.end():]

    text = _sub(text, r"\| \*\*Total\*\* \| \*\*\d+\*\* \| \*\*\d+\*\* \| \d+ Writing Labs, \d+ career paths,",
                f"| **Total** | **{c['tutorials']}** | **{c['incidents']}** | {c['labs']} Writing Labs, {c['paths']} career paths,",
                problems, "GAPS.md total row")
    text = _sub(text, r"The \d+ incidents are modeled", f"The {c['incidents']} incidents are modeled",
                problems, "GAPS.md 'The N incidents are modeled'")
    text = _sub(text, r"addressed: \d+ Writing Labs now", f"addressed: {c['labs']} Writing Labs now",
                problems, "GAPS.md 'N Writing Labs now'")
    text = _sub(text, r"Play all \w+ Career Paths", f"Play all {c['paths']} Career Paths",
                problems, "GAPS.md 'Play all N Career Paths'")
    return text


def sync_readme(text: str, c: dict, problems: list) -> str:
    for cat, (tut, inc) in c["per_category"].items():
        row = re.escape(label(cat))
        text = _sub(text, rf"^\| {row} \| \d+ \| \d+ \|", f"| {label(cat)} | {tut} | {inc} |",
                    problems, f"README.md table row for '{label(cat)}'")
    text = _sub(text, r"\| \*\*Total\*\* \| \*\*\d+\*\* \| \*\*\d+\*\* \| \+ \d+ Writing Labs \|",
                f"| **Total** | **{c['tutorials']}** | **{c['incidents']}** | + {c['labs']} Writing Labs |",
                problems, "README.md total row")
    text = _sub(text, r"Plus \*\*\d+ Career Paths\*\*", f"Plus **{c['paths']} Career Paths**",
                problems, "README.md career path count")
    text = _sub(text, r"\d+ labs across", f"{c['labs']} labs across", problems, "README.md lab count")
    return text


def sync_claude(text: str, c: dict, problems: list) -> str:
    for cat, (tut, inc) in c["per_category"].items():
        text = _sub(text, rf"^- {re.escape(cat)}: \d+ / \d+", f"- {cat}: {tut} / {inc}",
                    problems, f"CLAUDE.md depth line for '{cat}'")
    text = _sub(text, r"- \*\*total: \d+ tutorials, \d+ incidents, \d+ Writing Labs, \d+ career paths",
                f"- **total: {c['tutorials']} tutorials, {c['incidents']} incidents, {c['labs']} Writing Labs, {c['paths']} career paths",
                problems, "CLAUDE.md total line")
    text = _sub(text, r"Currently \d+ paths", f"Currently {c['paths']} paths", problems, "CLAUDE.md path count")
    text = _sub(text, r"spanning \d+ categories", f"spanning {c['categories']} categories",
                problems, "CLAUDE.md category count")
    return text


SYNCERS = {"GAPS.md": sync_gaps, "README.md": sync_readme, "CLAUDE.md": sync_claude}


def run(write: bool) -> tuple:
    """Returns (stale_files, problems)."""
    c = counts()
    stale, problems = [], []
    for name, syncer in SYNCERS.items():
        path = ROOT / name
        old = path.read_text(encoding="utf-8")
        new = syncer(old, c, problems)
        if new != old:
            stale.append(name)
            if write:
                path.write_text(new, encoding="utf-8")
    return stale, problems


if __name__ == "__main__":
    check_only = "--check" in sys.argv
    stale_files, found_problems = run(write=not check_only)
    for p in found_problems:
        print("PROBLEM:", p)
    if stale_files:
        print(("out of date: " if check_only else "updated: ") + ", ".join(stale_files))
    else:
        print("docs already match the content")
    sys.exit(1 if found_problems or (check_only and stale_files) else 0)
