"""Tests for scenario JSON loading (scenario_loader.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scenario_loader import load_incidents, load_scenarios, load_tutorials


def test_load_tutorials_returns_all_tutorial_files():
    tutorials = load_tutorials()
    ids = {t["id"] for t in tutorials}
    assert len(tutorials) >= 6
    assert "tutorial-001" in ids


def test_load_incidents_returns_all_incident_files():
    incidents = load_incidents()
    ids = {i["id"] for i in incidents}
    assert len(incidents) >= 5
    assert "incident-001" in ids


def test_missing_folder_returns_empty_list():
    assert load_scenarios("does-not-exist") == []


def test_tutorials_and_incidents_are_disjoint_sets():
    tutorial_ids = {t["id"] for t in load_tutorials()}
    incident_ids = {i["id"] for i in load_incidents()}
    assert tutorial_ids.isdisjoint(incident_ids)
