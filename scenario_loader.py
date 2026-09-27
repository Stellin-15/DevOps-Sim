"""Loads scenario JSON files from /scenarios/<category>/<tutorials|incidents>/*.json,
plus flat (non-category) content: yaml_labs and career_paths.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
SCENARIOS_DIR = BASE_DIR / "scenarios"

# Folders under scenarios/ that hold category subfolders (tutorials/incidents
# within each), as opposed to flat scenario-per-file folders like yaml_labs
# and career_paths.
NON_CATEGORY_DIRS = {"yaml_labs", "career_paths"}


def _load_json_files(folder: Path) -> list:
    if not folder.exists():
        return []
    scenarios = []
    for path in sorted(folder.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            scenarios.append(json.load(f))
    return scenarios


def list_categories() -> list:
    """Every category under scenarios/ that has a tutorials/ or incidents/
    subfolder — dynamically discovered, so adding a new category folder
    needs zero code changes here."""
    if not SCENARIOS_DIR.exists():
        return []
    categories = []
    for entry in sorted(SCENARIOS_DIR.iterdir()):
        if not entry.is_dir() or entry.name in NON_CATEGORY_DIRS:
            continue
        if (entry / "tutorials").exists() or (entry / "incidents").exists():
            categories.append(entry.name)
    return categories


def load_tutorials(category: str = None) -> list:
    if category:
        return _load_json_files(SCENARIOS_DIR / category / "tutorials")
    scenarios = []
    for cat in list_categories():
        scenarios.extend(_load_json_files(SCENARIOS_DIR / cat / "tutorials"))
    return scenarios


def load_incidents(category: str = None) -> list:
    if category:
        return _load_json_files(SCENARIOS_DIR / category / "incidents")
    scenarios = []
    for cat in list_categories():
        scenarios.extend(_load_json_files(SCENARIOS_DIR / cat / "incidents"))
    return scenarios


def load_yaml_labs() -> list:
    return _load_json_files(SCENARIOS_DIR / "yaml_labs")


def load_career_paths() -> list:
    return _load_json_files(SCENARIOS_DIR / "career_paths")


def load_all_scenarios_by_id() -> dict:
    """Every tutorial and incident across every category, keyed by id —
    used by career_path.py to resolve a path's step ids to full scenario
    dicts without caring which category each step belongs to."""
    by_id = {}
    for scenario in load_tutorials() + load_incidents():
        by_id[scenario["id"]] = scenario
    return by_id
