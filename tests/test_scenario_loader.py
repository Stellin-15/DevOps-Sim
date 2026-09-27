"""Tests for scenario JSON loading (scenario_loader.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scenario_loader import (
    list_categories,
    load_all_scenarios_by_id,
    load_career_paths,
    load_incidents,
    load_tutorials,
    load_yaml_labs,
)


def test_list_categories_finds_expected_categories():
    categories = list_categories()
    for expected in ["kubernetes", "docker", "linux", "terraform", "networking", "cicd", "monitoring", "mlops"]:
        assert expected in categories


def test_load_tutorials_with_no_category_aggregates_all():
    all_tutorials = load_tutorials()
    kubernetes_only = load_tutorials("kubernetes")
    assert len(all_tutorials) > len(kubernetes_only)
    assert len(kubernetes_only) >= 6


def test_load_tutorials_with_category_filters():
    docker_tutorials = load_tutorials("docker")
    assert all(t["category"] == "docker" for t in docker_tutorials)


def test_load_incidents_with_no_category_aggregates_all():
    all_incidents = load_incidents()
    kubernetes_only = load_incidents("kubernetes")
    assert len(all_incidents) > len(kubernetes_only)


def test_load_from_nonexistent_category_returns_empty():
    assert load_tutorials("does-not-exist") == []
    assert load_incidents("does-not-exist") == []


def test_tutorials_and_incidents_are_disjoint_sets():
    tutorial_ids = {t["id"] for t in load_tutorials()}
    incident_ids = {i["id"] for i in load_incidents()}
    assert tutorial_ids.isdisjoint(incident_ids)


def test_load_yaml_labs_returns_labs():
    labs = load_yaml_labs()
    assert len(labs) >= 1
    assert all(lab["type"] == "yaml_lab" for lab in labs)


def test_load_career_paths_returns_paths():
    paths = load_career_paths()
    assert len(paths) >= 1
    assert all(p["type"] == "career_path" for p in paths)


def test_load_all_scenarios_by_id_covers_every_tutorial_and_incident():
    by_id = load_all_scenarios_by_id()
    for scenario in load_tutorials() + load_incidents():
        assert by_id[scenario["id"]] is scenario or by_id[scenario["id"]] == scenario
