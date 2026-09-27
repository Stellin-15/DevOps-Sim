"""Tests for career_path.py — chaining existing scenarios across categories."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import career_path
import progress as progress_module


def make_scenario(scenario_id, expected="do thing", scenario_type="tutorial"):
    return {
        "id": scenario_id,
        "type": scenario_type,
        "title": f"Scenario {scenario_id}",
        "intro": "intro",
        "steps": [
            {
                "prompt": "Do the thing.",
                "expected_commands": [expected],
                "fake_output": "done",
            }
        ],
    }


def make_path(steps):
    return {"id": "path-test", "title": "Test Path", "intro": "path intro", "steps": steps}


class TestRunCareerPath:
    def test_completes_all_steps_returns_true(self, monkeypatch):
        scenarios_by_id = {"a": make_scenario("a"), "b": make_scenario("b")}
        monkeypatch.setattr("builtins.input", lambda _: "do thing")
        progress = progress_module._fresh_progress()
        assert career_path.run_career_path(make_path(["a", "b"]), scenarios_by_id, progress) is True

    def test_completed_sub_scenarios_are_recorded_in_progress(self, monkeypatch):
        scenarios_by_id = {"a": make_scenario("a"), "b": make_scenario("b", scenario_type="incident")}
        monkeypatch.setattr("builtins.input", lambda _: "do thing")
        progress = progress_module._fresh_progress()
        career_path.run_career_path(make_path(["a", "b"]), scenarios_by_id, progress)
        assert progress_module.is_completed(progress, "a", "tutorial")
        assert progress_module.is_completed(progress, "b", "incident")
        assert progress_module.attempt_count(progress, "a") == 1
        assert progress_module.attempt_count(progress, "b") == 1

    def test_quitting_mid_path_returns_false(self, monkeypatch):
        scenarios_by_id = {"a": make_scenario("a"), "b": make_scenario("b")}
        monkeypatch.setattr("builtins.input", lambda _: "exit")
        progress = progress_module._fresh_progress()
        assert career_path.run_career_path(make_path(["a", "b"]), scenarios_by_id, progress) is False

    def test_stops_at_first_incomplete_step(self, monkeypatch, capsys):
        scenarios_by_id = {"a": make_scenario("a", expected="do thing"), "b": make_scenario("b")}
        # First step's input never matches -> quit via exit on the retry.
        inputs = iter(["wrong", "exit"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        progress = progress_module._fresh_progress()
        result = career_path.run_career_path(make_path(["a", "b"]), scenarios_by_id, progress)
        assert result is False
        assert "Stopped mid-path" in capsys.readouterr().out
        # The step the player quit on isn't marked complete, but the attempt still counts.
        assert not progress_module.is_completed(progress, "a", "tutorial")
        assert progress_module.attempt_count(progress, "a") == 1

    def test_missing_scenario_id_is_skipped_not_fatal(self, monkeypatch, capsys):
        scenarios_by_id = {"a": make_scenario("a")}
        monkeypatch.setattr("builtins.input", lambda _: "do thing")
        progress = progress_module._fresh_progress()
        result = career_path.run_career_path(make_path(["a", "does-not-exist"]), scenarios_by_id, progress)
        assert result is True
        assert "skipping missing scenario" in capsys.readouterr().out
