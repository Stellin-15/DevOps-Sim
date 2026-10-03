"""Tests for scaffold.py (`python game.py add-scenario`), plus the tripwire
that keeps half-written scaffolds out of the real content."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import scaffold
from scenario_loader import SCENARIOS_DIR


@pytest.fixture
def root(tmp_path):
    for cat in ("kubernetes", "git"):
        (tmp_path / cat / "tutorials").mkdir(parents=True)
        (tmp_path / cat / "incidents").mkdir(parents=True)
    (tmp_path / "git" / "tutorials" / "git-tutorial-011-large-repos.json").write_text("{}")
    (tmp_path / "kubernetes" / "tutorials" / "tutorial-038-x.json").write_text("{}")
    return tmp_path


def test_no_scaffold_markers_left_in_real_content():
    """A scaffold committed before every TODO was replaced fails here."""
    unfinished = [p.relative_to(SCENARIOS_DIR).as_posix() for p in SCENARIOS_DIR.rglob("*.json")
                  if scaffold.TODO in p.read_text(encoding="utf-8")]
    assert unfinished == []


def test_slugify():
    assert scaffold.slugify("Sparse Checkout & Partial Clones!") == "sparse-checkout-partial-clones"
    assert scaffold.slugify("???") == "untitled"


@pytest.mark.parametrize("kind, category, sandbox, prefix", [
    ("tutorial", "kubernetes", None, "tutorial"),
    ("incident", "kubernetes", None, "incident"),
    ("tutorial", "git", None, "git-tutorial"),
    ("yaml_lab", "docker", None, "yaml"),
    ("career_path", None, None, "path"),
    ("mystery", "databases", "db", "mystery-db"),
])
def test_id_prefixes_follow_the_naming_scheme(kind, category, sandbox, prefix):
    assert scaffold.id_prefix(kind, category, sandbox) == prefix


def test_next_id_continues_numbering(root):
    assert scaffold.next_id(root / "git" / "tutorials", "git-tutorial") == "git-tutorial-012"
    assert scaffold.next_id(root / "git" / "incidents", "git-incident") == "git-incident-001"
    assert scaffold.next_id(root / "kubernetes" / "tutorials", "tutorial") == "tutorial-039"


def test_next_id_matches_on_real_content():
    folder = SCENARIOS_DIR / "kubernetes" / "tutorials"
    existing = {json.loads(p.read_text(encoding="utf-8"))["id"] for p in folder.glob("*.json")}
    assert scaffold.next_id(folder, "tutorial") not in existing


@pytest.mark.parametrize("kind", scaffold.TYPES)
def test_skeleton_has_what_the_content_tests_require(kind):
    data = scaffold.skeleton(kind, "x-001", "A title", "git", steps=3, sandbox="git")
    assert data["id"] == "x-001" and data["type"] == kind and data["title"] == "A title"
    assert scaffold.TODO in json.dumps(data)
    if kind == "mystery":
        for field in ["category", "sandbox", "setup", "symptom", "question", "expert_commands",
                      "solution_commands", "debrief", "evidence", "goals"]:
            assert field in data
        assert "wrong_branch" in data["setup"]["problems"][0]  # the sandbox's own problem names
    else:
        assert len(data["steps"]) == 3
    if kind == "tutorial":
        assert all("why" in s for s in data["steps"])
    if kind == "incident":
        assert "resolution" in data and "real_commands_used" in data


def test_kubernetes_labs_ask_for_a_kind():
    assert "kind" in scaffold.skeleton("yaml_lab", "yaml-001", "t", "kubernetes")["steps"][0]["validate"]
    assert "kind" not in scaffold.skeleton("yaml_lab", "yaml-001", "t", "docker")["steps"][0]["validate"]


def test_cli_writes_the_file(root, capsys):
    path = scaffold.main(["--type", "tutorial", "--category", "git", "--title", "Sparse checkout",
                          "--steps", "2"], root=root)
    assert path == root / "git" / "tutorials" / "git-tutorial-012-sparse-checkout.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["id"] == "git-tutorial-012" and len(data["steps"]) == 2
    out = capsys.readouterr().out
    assert "Created" in out and "TODO(scaffold)" in out and "sync_docs" in out


def test_cli_refuses_an_unknown_category(root):
    with pytest.raises(SystemExit):
        scaffold.main(["--type", "tutorial", "--category", "gti", "--title", "x", "--steps", "1"], root=root)


def test_cli_creates_a_new_category_when_asked(root, capsys):
    path = scaffold.main(["--type", "incident", "--category", "observability2", "--new-category",
                          "--title", "x", "--steps", "1"], root=root)
    assert path.parent == root / "observability2" / "incidents"
    assert "New category" in capsys.readouterr().out


def test_interactive_flow(root, monkeypatch):
    answers = iter(["2", "2", "Pending pods after a node pool change", ""])  # incident, kubernetes, title, 5 steps
    monkeypatch.setattr(scaffold, "read_input", lambda prompt="": next(answers))
    path = scaffold.main([], root=root)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["id"] == "incident-001" and data["category"] == "kubernetes" and len(data["steps"]) == 5
