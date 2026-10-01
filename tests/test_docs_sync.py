"""The counts quoted in GAPS.md, README.md, and CLAUDE.md must match the
content. If this fails after adding scenarios, run:

    python tools/sync_docs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import sync_docs


def test_doc_counts_match_the_content():
    stale, problems = sync_docs.run(write=False)
    assert problems == [], "a category has no row yet, or a count line was reworded: " + "; ".join(problems)
    assert stale == [], f"run 'python tools/sync_docs.py' to update: {stale}"


def test_counts_add_up():
    c = sync_docs.counts()
    assert c["tutorials"] == sum(t for t, _ in c["per_category"].values())
    assert c["incidents"] == sum(i for _, i in c["per_category"].values())
    assert c["categories"] == len(c["per_category"]) > 0


def test_gaps_parts_are_renumbered_in_file_order():
    text = "# Part 1 — A\nx\n# Part 7 — B\ny\n# Part 7 — C\n"
    import re
    numbers = iter(range(1, 10))
    out = re.sub(r"^# Part \d+ — ", lambda m: f"# Part {next(numbers)} — ", text, flags=re.M)
    assert out == "# Part 1 — A\nx\n# Part 2 — B\ny\n# Part 3 — C\n"
