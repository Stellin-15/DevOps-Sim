"""Loads scenario JSON files from /scenarios/<category>/*.json."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
SCENARIOS_DIR = BASE_DIR / "scenarios"


def load_scenarios(folder_name: str) -> list:
    folder = SCENARIOS_DIR / folder_name
    if not folder.exists():
        return []
    scenarios = []
    for path in sorted(folder.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            scenarios.append(json.load(f))
    return scenarios


def load_tutorials() -> list:
    return load_scenarios("tutorials")


def load_incidents() -> list:
    return load_scenarios("incidents")
