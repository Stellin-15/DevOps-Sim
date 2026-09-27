"""Smoke tests for game.py — the entry point had no test coverage, which
let a syntax error reach the menu once. Importing it and driving the main
menu with scripted input catches that whole class of breakage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import game
import progress as progress_module


@pytest.fixture
def isolated_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(progress_module, "PROGRESS_FILE", tmp_path / "progress.json")


def drive(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr(game, "read_input", lambda prompt="": next(it))
    monkeypatch.setattr("engine.read_input", lambda prompt="": next(it))
    monkeypatch.setattr("exam.read_input", lambda prompt="": next(it))


def test_main_menu_quits_cleanly(monkeypatch, capsys, isolated_progress):
    drive(monkeypatch, ["q"])
    game.main_menu_loop()
    assert "Goodbye" in capsys.readouterr().out


def test_every_top_level_menu_entry_opens_and_backs_out(monkeypatch, capsys, isolated_progress):
    # 1 Practice -> back, 2 Career Paths -> back, 3 Writing Labs -> back,
    # 4 Exam -> category back, then quit.
    drive(monkeypatch, ["1", "b", "2", "b", "3", "b", "4", "b", "q"])
    game.main_menu_loop()
    out = capsys.readouterr().out
    for heading in ["Choose a Category", "Career Paths", "Writing Labs"]:
        assert heading in out


def test_exam_menu_runs_an_exam_and_records_it(monkeypatch, capsys, isolated_progress):
    # Exam -> category 2 -> 2 questions -> skip both -> quit
    drive(monkeypatch, ["4", "2", "2", "skip", "skip", "q"])
    game.main_menu_loop()
    out = capsys.readouterr().out
    assert "EXAM RESULTS" in out and "Score: 0/2" in out
    saved = progress_module.load_progress()
    assert len(saved["exam_history"]) == 1
