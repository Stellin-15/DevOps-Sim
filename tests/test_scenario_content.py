"""Validates every scenario JSON file against the schema in SPEC.md, and
sanity-checks that each listed expected_commands entry actually matches
itself under the engine (catches typos/self-inconsistent scenario data).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from engine import matches
from scenario_loader import load_incidents, load_tutorials

ALL_SCENARIOS = load_tutorials() + load_incidents()

REQUIRED_TOP_LEVEL_FIELDS = ["id", "type", "category", "title", "difficulty", "steps"]
REQUIRED_STEP_FIELDS = ["prompt", "expected_commands", "fake_output"]


def _id(scenario):
    return scenario["id"]


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=_id)
def test_scenario_has_required_top_level_fields(scenario):
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        assert field in scenario, f"{scenario.get('id', '?')} missing '{field}'"


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=_id)
def test_scenario_type_is_valid(scenario):
    assert scenario["type"] in ("tutorial", "incident")


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=_id)
def test_scenario_has_at_least_one_step(scenario):
    assert isinstance(scenario["steps"], list)
    assert len(scenario["steps"]) >= 1


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=_id)
def test_each_step_has_required_fields(scenario):
    for i, step in enumerate(scenario["steps"]):
        for field in REQUIRED_STEP_FIELDS:
            assert field in step, f"{scenario['id']} step {i} missing '{field}'"


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=_id)
def test_expected_commands_is_nonempty_list_of_strings(scenario):
    for i, step in enumerate(scenario["steps"]):
        cmds = step["expected_commands"]
        assert isinstance(cmds, list) and len(cmds) >= 1, (
            f"{scenario['id']} step {i} expected_commands must be a non-empty list"
        )
        for cmd in cmds:
            assert isinstance(cmd, str) and cmd.strip(), (
                f"{scenario['id']} step {i} has a blank/non-string expected command"
            )


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=_id)
def test_every_expected_command_matches_itself(scenario):
    """Regression guard: each listed expected command must match its own
    step's expected_commands list under the real matcher. This mainly
    protects against copy-paste typos when authoring scenario JSON."""
    for i, step in enumerate(scenario["steps"]):
        for cmd in step["expected_commands"]:
            assert matches(cmd, step["expected_commands"]), (
                f"{scenario['id']} step {i}: '{cmd}' does not match its own expected_commands list"
            )


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=_id)
def test_incident_scenarios_have_resolution_and_real_commands(scenario):
    if scenario["type"] == "incident":
        assert scenario.get("resolution"), f"{scenario['id']} incident missing resolution"
        assert scenario.get("real_commands_used"), f"{scenario['id']} incident missing real_commands_used"


def test_all_scenario_ids_are_unique():
    ids = [s["id"] for s in ALL_SCENARIOS]
    assert len(ids) == len(set(ids)), "duplicate scenario ids found"
