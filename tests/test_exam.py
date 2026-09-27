"""Tests for exam.py — question drawing, scoring, time limits, history."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import exam
import progress as progress_module
from scenario_loader import load_incidents, load_tutorials


def make_scenario(title, prompts_and_answers, category="docker"):
    return {
        "title": title,
        "category": category,
        "steps": [{"prompt": p, "expected_commands": [a]} for p, a in prompts_and_answers],
    }


def questions(n=3):
    s = make_scenario("S", [(f"prompt {i}", f"cmd {i}") for i in range(n)])
    return exam.build_questions([s], n, random.Random(0))


class FakeClock:
    def __init__(self, ticks):
        self.ticks = iter(ticks)
        self.last = 0

    def __call__(self):
        self.last = next(self.ticks, self.last)
        return self.last


def scripted(answers):
    it = iter(answers)
    return lambda prompt="": next(it)


class TestBuildQuestions:
    def test_draws_requested_count_without_duplicates(self):
        qs = questions(5)
        assert len(qs) == 5
        assert len({q["prompt"] for q in qs}) == 5

    def test_carries_previous_step_as_context(self):
        s = make_scenario("S", [("first", "a"), ("second", "b")])
        qs = {q["prompt"]: q for q in exam.build_questions([s], 2, random.Random(0))}
        assert qs["first"]["context"] is None
        assert qs["second"]["context"] == "first"

    def test_carries_previous_step_output_so_ids_are_answerable(self):
        s = {"title": "S", "steps": [
            {"prompt": "list containers", "expected_commands": ["docker ps -a"],
             "fake_output": "CONTAINER ID  STATUS\nb4c5d6e7f8a9  Exited (1)"},
            {"prompt": "check its logs", "expected_commands": ["docker logs b4c5d6e7f8a9"]},
        ]}
        qs = {q["prompt"]: q for q in exam.build_questions([s], 2, random.Random(0))}
        assert "b4c5d6e7f8a9" in qs["check its logs"]["context_output"]
        assert qs["list containers"]["context_output"] == ""

    def test_context_output_is_truncated(self):
        long_output = "\n".join(f"line {i}" for i in range(50))
        s = {"title": "S", "steps": [
            {"prompt": "a", "expected_commands": ["x"], "fake_output": long_output},
            {"prompt": "b", "expected_commands": ["y"]},
        ]}
        qs = {q["prompt"]: q for q in exam.build_questions([s], 2, random.Random(0))}
        assert len(qs["b"]["context_output"].splitlines()) == exam.MAX_CONTEXT_LINES

    def test_same_seed_same_questions(self):
        s = make_scenario("S", [(f"p{i}", f"c{i}") for i in range(20)])
        a = [q["prompt"] for q in exam.build_questions([s], 5, random.Random(42))]
        b = [q["prompt"] for q in exam.build_questions([s], 5, random.Random(42))]
        assert a == b

    def test_works_on_real_content(self):
        qs = exam.build_questions(load_tutorials("docker") + load_incidents("docker"), 10, random.Random(1))
        assert len(qs) == 10 and all(q["expected_commands"] for q in qs)


class TestRunExam:
    def test_scores_correct_wrong_and_skipped(self):
        qs = questions(3)
        answers = []
        for q in qs:
            answers.append(q["expected_commands"][0])
        answers[1] = "totally wrong"
        answers[2] = "skip"
        out = exam.run_exam(qs, 600, clock=FakeClock([0] * 20), input_fn=scripted(answers))
        statuses = [r["status"] for r in out["results"]]
        assert statuses == ["correct", "wrong", "skipped"]
        assert out["score"] == 1 and out["total"] == 3

    def test_pass_mark_is_66_percent(self):
        qs = questions(3)
        all_right = [q["expected_commands"][0] for q in qs]
        two_right = all_right[:2] + ["nope"]
        one_right = all_right[:1] + ["nope", "nope"]
        assert exam.run_exam(qs, 600, clock=FakeClock([0] * 20), input_fn=scripted(two_right))["passed"]
        assert not exam.run_exam(qs, 600, clock=FakeClock([0] * 20), input_fn=scripted(one_right))["passed"]

    def test_questions_after_time_runs_out_are_unanswered(self):
        qs = questions(3)
        answers = [q["expected_commands"][0] for q in qs]
        # start=0, q1 shown at 10 and answered at 20, then the clock jumps past the 60s limit
        clock = FakeClock([0, 10, 20, 100, 100, 100, 100, 100])
        out = exam.run_exam(qs, 60, clock=clock, input_fn=scripted(answers))
        assert [r["status"] for r in out["results"]] == ["correct", "unanswered", "unanswered"]

    def test_answer_submitted_after_deadline_does_not_count(self):
        qs = questions(1)
        clock = FakeClock([0, 5, 90, 90])  # question shown at 5s, answered at 90s, limit 60s
        out = exam.run_exam(qs, 60, clock=clock, input_fn=scripted([qs[0]["expected_commands"][0]]))
        assert out["results"][0]["status"] == "unanswered" and out["score"] == 0

    def test_exit_ends_exam_and_marks_rest_unanswered(self):
        qs = questions(3)
        answers = [qs[0]["expected_commands"][0], "exit"]
        out = exam.run_exam(qs, 600, clock=FakeClock([0] * 20), input_fn=scripted(answers))
        assert [r["status"] for r in out["results"]] == ["correct", "unanswered", "unanswered"]

    def test_no_feedback_during_exam_but_review_at_end(self, capsys):
        qs = questions(2)
        exam.run_exam(qs, 600, clock=FakeClock([0] * 20), input_fn=scripted(["wrong one", "wrong two"]))
        out = capsys.readouterr().out
        during, _, after = out.partition("=== EXAM RESULTS ===")
        assert "expected:" not in during
        assert "expected: cmd" in after and "you typed: wrong one" in after


class TestHistory:
    def test_record_and_best_percent(self):
        p = progress_module._fresh_progress()
        exam.record_result(p, "docker", {"score": 6, "total": 10, "passed": False, "seconds": 300})
        exam.record_result(p, "docker", {"score": 9, "total": 10, "passed": True, "seconds": 280})
        exam.record_result(p, None, {"score": 5, "total": 10, "passed": False, "seconds": 400})
        assert exam.best_percent(p, "docker") == 90
        assert exam.best_percent(p, None) == 50
        assert exam.best_percent(p, "linux") is None

    def test_old_progress_files_without_history_still_work(self):
        p = {"tutorials_completed": [], "attempts": {}}
        assert exam.best_percent(p, "docker") is None
        exam.record_result(p, "docker", {"score": 1, "total": 1, "passed": True, "seconds": 5})
        assert len(p["exam_history"]) == 1


def test_every_real_step_is_answerable_out_of_context():
    """Content regression guard: any id a step's answer needs (a pod name,
    container id, lock id) must be visible in its prompt, the previous
    step, or an earlier step's output — otherwise the exam must drop it,
    and in normal play the player would have to guess it. Dropping is a
    silent loss, so this fails loudly instead."""
    scenarios = load_tutorials() + load_incidents()
    total = sum(len(s["steps"]) for s in scenarios)
    drawn = exam.build_questions(scenarios, 10**6, random.Random(0))
    assert len(drawn) == total, f"{total - len(drawn)} step(s) reference an id the player never sees"
