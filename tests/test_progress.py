"""Tests for progress.py (progress.json read/write, completion + attempt tracking)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import progress as progress_module


def test_fresh_progress_shape():
    p = progress_module._fresh_progress()
    assert p == {
        "tutorials_completed": [],
        "incidents_completed": [],
        "yaml_labs_completed": [],
        "career_paths_completed": [],
        "exam_history": [],
        "attempts": {},
    }


def test_record_attempt_increments():
    p = progress_module._fresh_progress()
    progress_module.record_attempt(p, "tutorial-001")
    progress_module.record_attempt(p, "tutorial-001")
    assert progress_module.attempt_count(p, "tutorial-001") == 2


def test_attempt_count_defaults_to_zero():
    p = progress_module._fresh_progress()
    assert progress_module.attempt_count(p, "never-played") == 0


def test_mark_completed_tutorial():
    p = progress_module._fresh_progress()
    progress_module.mark_completed(p, "tutorial-001", "tutorial")
    assert progress_module.is_completed(p, "tutorial-001", "tutorial")
    assert "tutorial-001" in p["tutorials_completed"]


def test_mark_completed_incident():
    p = progress_module._fresh_progress()
    progress_module.mark_completed(p, "incident-001", "incident")
    assert progress_module.is_completed(p, "incident-001", "incident")


def test_mark_completed_yaml_lab():
    p = progress_module._fresh_progress()
    progress_module.mark_completed(p, "yaml-001", "yaml_lab")
    assert progress_module.is_completed(p, "yaml-001", "yaml_lab")
    assert "yaml-001" in p["yaml_labs_completed"]


def test_mark_completed_career_path():
    p = progress_module._fresh_progress()
    progress_module.mark_completed(p, "path-001", "career_path")
    assert progress_module.is_completed(p, "path-001", "career_path")
    assert "path-001" in p["career_paths_completed"]


def test_mark_completed_is_idempotent():
    p = progress_module._fresh_progress()
    progress_module.mark_completed(p, "tutorial-001", "tutorial")
    progress_module.mark_completed(p, "tutorial-001", "tutorial")
    assert p["tutorials_completed"] == ["tutorial-001"]


def test_is_completed_false_when_not_played():
    p = progress_module._fresh_progress()
    assert not progress_module.is_completed(p, "tutorial-001", "tutorial")


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    fake_file = tmp_path / "progress.json"
    monkeypatch.setattr(progress_module, "PROGRESS_FILE", fake_file)

    p = progress_module._fresh_progress()
    progress_module.mark_completed(p, "tutorial-001", "tutorial")
    progress_module.record_attempt(p, "tutorial-001")
    progress_module.save_progress(p)

    assert fake_file.exists()
    loaded = progress_module.load_progress()
    assert loaded["tutorials_completed"] == ["tutorial-001"]
    assert loaded["attempts"]["tutorial-001"] == 1


def test_load_progress_returns_fresh_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(progress_module, "PROGRESS_FILE", tmp_path / "does_not_exist.json")
    assert progress_module.load_progress() == progress_module._fresh_progress()


def test_load_progress_fills_in_missing_keys(tmp_path, monkeypatch):
    fake_file = tmp_path / "progress.json"
    fake_file.write_text(json.dumps({"tutorials_completed": ["tutorial-001"]}), encoding="utf-8")
    monkeypatch.setattr(progress_module, "PROGRESS_FILE", fake_file)

    loaded = progress_module.load_progress()
    assert loaded["tutorials_completed"] == ["tutorial-001"]
    assert loaded["incidents_completed"] == []
    assert loaded["attempts"] == {}
