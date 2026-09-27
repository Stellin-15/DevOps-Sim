"""Validates every career_path scenario file: schema, and — critically —
that every referenced step id actually resolves to a real tutorial or
incident. This is the career_path equivalent of the other self-
consistency checks: it catches a typo'd step id before a player hits it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from scenario_loader import load_all_scenarios_by_id, load_career_paths

ALL_PATHS = load_career_paths()
SCENARIOS_BY_ID = load_all_scenarios_by_id()


def _id(path):
    return path["id"]


def test_at_least_one_career_path_exists():
    assert len(ALL_PATHS) >= 1


@pytest.mark.parametrize("path", ALL_PATHS, ids=_id)
def test_path_has_required_fields(path):
    for field in ["id", "type", "title", "steps"]:
        assert field in path, f"{path.get('id', '?')} missing '{field}'"
    assert path["type"] == "career_path"


@pytest.mark.parametrize("path", ALL_PATHS, ids=_id)
def test_path_has_at_least_two_steps(path):
    assert isinstance(path["steps"], list)
    assert len(path["steps"]) >= 2, f"{path['id']} should chain at least 2 scenarios"


@pytest.mark.parametrize("path", ALL_PATHS, ids=_id)
def test_every_step_id_resolves_to_a_real_scenario(path):
    """The core regression guard: a typo'd step id would otherwise
    silently skip a stage at runtime (career_path.py logs and continues
    rather than crashing) instead of failing loudly here."""
    for step_id in path["steps"]:
        assert step_id in SCENARIOS_BY_ID, f"{path['id']} references unknown scenario id '{step_id}'"


@pytest.mark.parametrize("path", ALL_PATHS, ids=_id)
def test_path_spans_more_than_one_category(path):
    """Career paths exist specifically to combine categories — a path
    that's accidentally single-category defeats the point."""
    categories = {SCENARIOS_BY_ID[step_id]["category"] for step_id in path["steps"] if step_id in SCENARIOS_BY_ID}
    assert len(categories) >= 2, f"{path['id']} only spans one category: {categories}"


def test_all_path_ids_are_unique():
    ids = [p["id"] for p in ALL_PATHS]
    assert len(ids) == len(set(ids))
