"""Validates every yaml_lab scenario file's schema, and — critically —
that each step's own 'solution' actually parses and passes its own
'validate' spec. This is the yaml_lab equivalent of
test_scenario_content.py's self-consistency check for expected_commands:
it catches typos in hand-written solution YAML before a player hits them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import yaml

import yaml_lab
from scenario_loader import load_yaml_labs

ALL_LABS = load_yaml_labs()
REQUIRED_STEP_FIELDS = ["file", "prompt", "apply_commands", "validate", "fake_output"]


def _id(lab):
    return lab["id"]


def test_at_least_one_lab_exists():
    assert len(ALL_LABS) >= 1


@pytest.mark.parametrize("lab", ALL_LABS, ids=_id)
def test_lab_has_required_top_level_fields(lab):
    for field in ["id", "type", "category", "title", "difficulty", "steps"]:
        assert field in lab, f"{lab.get('id', '?')} missing '{field}'"
    assert lab["type"] == "yaml_lab"


@pytest.mark.parametrize("lab", ALL_LABS, ids=_id)
def test_each_step_has_required_fields(lab):
    for i, step in enumerate(lab["steps"]):
        for field in REQUIRED_STEP_FIELDS:
            assert field in step, f"{lab['id']} step {i} missing '{field}'"
        assert isinstance(step["apply_commands"], list) and step["apply_commands"]


@pytest.mark.parametrize("lab", ALL_LABS, ids=_id)
def test_starter_content_is_valid_yaml_when_present(lab):
    for i, step in enumerate(lab["steps"]):
        starter = step.get("starter_content", "")
        if not starter.strip():
            continue  # blank-slate labs are allowed
        try:
            yaml.safe_load(starter)
        except yaml.YAMLError as e:
            pytest.fail(f"{lab['id']} step {i} starter_content is not valid YAML: {e}")


@pytest.mark.parametrize("lab", ALL_LABS, ids=_id)
def test_solution_parses_and_passes_its_own_validate_spec(lab):
    """The core regression guard: a hand-typo'd solution would otherwise
    silently show players a 'working' answer that doesn't actually pass."""
    for i, step in enumerate(lab["steps"]):
        solution = step.get("solution")
        if not solution:
            continue
        try:
            parsed = yaml.safe_load(solution)
        except yaml.YAMLError as e:
            pytest.fail(f"{lab['id']} step {i}'s solution is not valid YAML: {e}")
        problems = yaml_lab.validate_manifest(parsed, step["validate"])
        assert problems == [], f"{lab['id']} step {i}'s solution fails its own validate spec: {problems}"


@pytest.mark.parametrize("lab", ALL_LABS, ids=_id)
def test_validate_spec_has_kind_and_fields(lab):
    for i, step in enumerate(lab["steps"]):
        validate = step["validate"]
        assert "kind" in validate, f"{lab['id']} step {i} validate spec missing 'kind'"
        assert "fields" in validate and validate["fields"], f"{lab['id']} step {i} validate spec has no fields"


def test_all_lab_ids_are_unique():
    ids = [lab["id"] for lab in ALL_LABS]
    assert len(ids) == len(set(ids))
