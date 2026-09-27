"""Local progress tracking — completed scenarios and attempt counts.

Stored in a single progress.json at the project root (gitignored — this is
per-player local state, not project content). Schema matches SPEC.md:

{
  "tutorials_completed": ["tutorial-001", ...],
  "incidents_completed": ["incident-001", ...],
  "yaml_labs_completed": ["yaml-001", ...],
  "career_paths_completed": ["path-001", ...],
  "exam_history": [{"category": "docker", "score": 8, "total": 10, ...}],
  "attempts": {"tutorial-001": 1, "incident-001": 3}
}

Scenario ids are globally unique across every category (e.g.
"docker-tutorial-001" vs "tutorial-001" vs "terraform-tutorial-001"), so
this stays flat rather than nested per category — no migration needed as
categories are added.

"attempts" counts how many times a scenario has been played (run to
completion or quit early) — a rough measure of how much a scenario was
struggled with.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROGRESS_FILE = BASE_DIR / "progress.json"

DEFAULT_PROGRESS = {
    "tutorials_completed": [],
    "incidents_completed": [],
    "yaml_labs_completed": [],
    "career_paths_completed": [],
    "exam_history": [],
    "attempts": {},
}

COMPLETED_KEY = {
    "tutorial": "tutorials_completed",
    "incident": "incidents_completed",
    "yaml_lab": "yaml_labs_completed",
    "career_path": "career_paths_completed",
}


def load_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return _fresh_progress()
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for key, default in DEFAULT_PROGRESS.items():
        data.setdefault(key, [] if isinstance(default, list) else {})
    return data


def save_progress(progress: dict) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def record_attempt(progress: dict, scenario_id: str) -> None:
    progress["attempts"][scenario_id] = progress["attempts"].get(scenario_id, 0) + 1


def mark_completed(progress: dict, scenario_id: str, scenario_type: str) -> None:
    key = COMPLETED_KEY[scenario_type]
    if scenario_id not in progress[key]:
        progress[key].append(scenario_id)


def is_completed(progress: dict, scenario_id: str, scenario_type: str) -> bool:
    key = COMPLETED_KEY[scenario_type]
    return scenario_id in progress[key]


def attempt_count(progress: dict, scenario_id: str) -> int:
    return progress["attempts"].get(scenario_id, 0)


def _fresh_progress() -> dict:
    return {
        "tutorials_completed": [],
        "incidents_completed": [],
        "yaml_labs_completed": [],
        "career_paths_completed": [],
        "exam_history": [],
        "attempts": {},
    }
