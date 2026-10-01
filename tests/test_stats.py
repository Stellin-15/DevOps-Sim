"""Tests for stats.py — the numbers, the suggestions, and the rendering,
on small synthetic content plus a smoke test over the real content."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import progress as progress_module
import stats
from scenario_loader import load_career_paths, load_incidents, load_mysteries, load_tutorials, load_yaml_labs


def item(id_, category, title=None):
    return {"id": id_, "category": category, "title": title or id_}


TUTORIALS = [item("k-t1", "kubernetes", "Pods"), item("k-t2", "kubernetes", "Deployments"),
             item("d-t1", "docker", "Images")]
INCIDENTS = [item("k-i1", "kubernetes", "CrashLoop"), item("d-i1", "docker", "Exited")]
LABS = [{"id": "lab-1", "title": "Pod YAML"}, item("lab-2", "docker", "Dockerfile")]  # lab-1: no category
PATHS = [{"id": "p1", "title": "Ship it"}]
MYSTERIES = [item("m1", "docker", "Vanishing container")]


def build(progress):
    return stats.build_stats(progress, TUTORIALS, INCIDENTS, LABS, PATHS, MYSTERIES)


def fresh(**overrides):
    p = progress_module._fresh_progress()
    p.update(overrides)
    return p


def row(s, category):
    return next(c for c in s["categories"] if c["category"] == category)


class TestBuildStats:
    def test_fresh_progress_is_all_zero(self):
        s = build(fresh())
        assert s["done"] == 0 and s["total"] == 9  # 3 + 2 + 2 + 1 mystery + 1 path
        assert row(s, "kubernetes")["tutorials"] == (0, 2)
        assert s["exams_passed"] == (0, 2) and s["mystery_average"] is None and s["struggles"] == []

    def test_counts_per_category_and_overall(self):
        s = build(fresh(tutorials_completed=["k-t1", "d-t1"], incidents_completed=["d-i1"],
                        yaml_labs_completed=["lab-1"], career_paths_completed=["p1"],
                        mysteries_completed=["m1"], mystery_scores={"m1": 80}))
        assert row(s, "kubernetes")["tutorials"] == (1, 2)
        assert row(s, "kubernetes")["labs"] == (1, 1)      # a lab with no category counts as kubernetes
        assert row(s, "docker")["done"] == 3 and row(s, "docker")["total"] == 4
        assert s["done"] == 6 and s["paths"] == (1, 1) and s["mystery_average"] == 80

    def test_completed_ids_that_no_longer_exist_are_ignored(self):
        s = build(fresh(tutorials_completed=["deleted-scenario"]))
        assert s["done"] == 0

    def test_exam_best_and_pass_mark(self):
        history = [{"category": "docker", "score": 5, "total": 10}, {"category": "docker", "score": 7, "total": 10},
                   {"category": "kubernetes", "score": 6, "total": 10}]
        s = build(fresh(exam_history=history))
        assert row(s, "docker")["exam_best"] == 70 and row(s, "docker")["exam_passed"]
        assert row(s, "kubernetes")["exam_best"] == 60 and not row(s, "kubernetes")["exam_passed"]
        assert s["exams_passed"] == (1, 2) and s["exams_taken"] == 3

    def test_struggles_are_the_most_attempted_and_need_two_attempts(self):
        s = build(fresh(attempts={"k-i1": 5, "k-t1": 2, "d-t1": 1, "gone": 9}))
        assert [x["id"] for x in s["struggles"]] == ["k-i1", "k-t1"]
        assert s["struggles"][0]["title"] == "CrashLoop"


class TestSuggestions:
    def test_new_player_is_pointed_at_the_first_kubernetes_tutorial(self):
        suggestions = build(fresh())["suggestions"]
        assert len(suggestions) == 1 and "Start here" in suggestions[0] and "Pods" in suggestions[0]

    def test_only_mysteries_solved_still_counts_as_a_new_player(self):
        suggestions = build(fresh(mysteries_completed=["m1"]))["suggestions"]
        assert "Start here" in suggestions[0] and "Pods" in suggestions[0]

    def test_finish_the_category_you_started(self):
        suggestions = build(fresh(tutorials_completed=["k-t1"]))["suggestions"]
        assert "Finish kubernetes's tutorials (1 left)" in suggestions[0] and "Deployments" in suggestions[0]

    def test_tutorials_done_but_exam_not_passed_suggests_the_exam(self):
        s = build(fresh(tutorials_completed=["d-t1"],
                        exam_history=[{"category": "docker", "score": 5, "total": 10}]))
        assert any("Take the docker exam" in x and "50%" in x for x in s["suggestions"])

    def test_passed_exam_moves_on_to_incidents_then_mysteries(self):
        passed = [{"category": "docker", "score": 9, "total": 10}]
        s = build(fresh(tutorials_completed=["d-t1"], exam_history=passed))
        assert any("incident in docker" in x for x in s["suggestions"])
        assert not any("exam" in x for x in s["suggestions"])
        s = build(fresh(tutorials_completed=["d-t1"], incidents_completed=["d-i1"], exam_history=passed))
        assert any("mystery in docker" in x for x in s["suggestions"])

    def test_never_more_than_three(self):
        s = build(fresh(tutorials_completed=["k-t1", "d-t1"]))
        assert 1 <= len(s["suggestions"]) <= stats.MAX_SUGGESTIONS


class TestRender:
    def test_render_contains_the_key_numbers(self):
        s = build(fresh(tutorials_completed=["k-t1"], attempts={"k-i1": 3},
                        exam_history=[{"category": "docker", "score": 7, "total": 10}]))
        out = stats.render_stats(s, {"kubernetes": "Kubernetes"})
        assert "1/9 completed (11%)" in out
        assert "Kubernetes" in out and "docker" in out          # label used when given, id otherwise
        assert "70% PASSED" in out and "not taken" in out
        assert "3x  CrashLoop" in out and "Suggested next:" in out

    def test_bar_is_fixed_width(self):
        assert len(stats._bar(0, 10)) == len(stats._bar(10, 10)) == stats.BAR_WIDTH + 2
        assert stats._bar(5, 10).count("#") == stats.BAR_WIDTH // 2
        assert stats._bar(0, 0).count("#") == 0


def test_real_content_renders_for_fresh_and_complete_progress():
    content = (load_tutorials(), load_incidents(), load_yaml_labs(), load_career_paths(), load_mysteries())
    s = stats.build_stats(progress_module._fresh_progress(), *content)
    assert s["done"] == 0 and s["total"] == sum(len(c) for c in content)
    assert "0%" in stats.render_stats(s)

    everything = progress_module._fresh_progress()
    for key, items in zip(["tutorials_completed", "incidents_completed", "yaml_labs_completed",
                           "career_paths_completed", "mysteries_completed"], content):
        everything[key] = [i["id"] for i in items]
    full = stats.build_stats(everything, *content)
    assert full["done"] == full["total"]
    assert "(100%)" in stats.render_stats(full)
