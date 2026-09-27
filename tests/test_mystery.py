"""Tests for mystery.py and every mystery file: each mystery must start
unsolved, be solvable by its stored expert path, and score correctly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import mystery
from sandbox_common import run_command
from scenario_loader import load_mysteries

ALL = load_mysteries()


def _id(m):
    return m["id"]


def scripted(answers):
    it = iter(answers)
    return lambda prompt="": next(it)


def expert_path(m):
    state = mystery.build_state(m)
    values = mystery.placeholders(state)
    return [cmd.format(**values) for cmd in m["solution_commands"]]


def correct_letter(m):
    return "abcdefgh"[m["question"]["answer"]]


# ---------------------------------------------------------------- content

def test_mysteries_exist():
    assert len(ALL) >= 6


@pytest.mark.parametrize("m", ALL, ids=_id)
def test_schema(m):
    for field in ["id", "type", "category", "sandbox", "title", "setup", "symptom",
                  "question", "expert_commands", "solution_commands", "debrief"]:
        assert field in m, f"{m.get('id')} missing {field}"
    assert m["type"] == "mystery"
    assert m["sandbox"] in mystery.SANDBOXES
    q = m["question"]
    assert 0 <= q["answer"] < len(q["options"]) and len(q["options"]) >= 3


@pytest.mark.parametrize("m", ALL, ids=_id)
def test_goals_start_unmet(m):
    """A mystery whose goals already pass at the start is not a mystery."""
    if m.get("goals"):
        assert mystery.unmet_goals(mystery.build_state(m), m), f"{m['id']} is already solved at the start"


@pytest.mark.parametrize("m", ALL, ids=_id)
def test_expert_path_solves_it(m):
    """The stored solution must actually work against the seeded state —
    proves every mystery is solvable, and that the path shown in the
    debrief is correct."""
    state = mystery.build_state(m)
    module = mystery.SANDBOXES[m["sandbox"]]
    for cmd in expert_path(m):
        out = run_command(module.handle_command, state, cmd)
        assert out is not None and "not simulated" not in out and "isn't simulated" not in out, (m["id"], cmd, out)
    assert mystery.unmet_goals(state, m) == [], f"{m['id']}: expert path leaves goals unmet"


@pytest.mark.parametrize("m", ALL, ids=_id)
def test_has_evidence_requirements(m):
    """Without evidence, a mystery with no goals (the Docker ones) could be
    'solved' by guessing the multiple-choice answer with zero commands."""
    assert m.get("evidence"), f"{m['id']} has no evidence requirements"
    for e in m["evidence"]:
        assert e["description"] and e["seen_any"], m["id"]


@pytest.mark.parametrize("m", ALL, ids=_id)
def test_expert_path_finds_the_evidence(m):
    state = mystery.build_state(m)
    module = mystery.SANDBOXES[m["sandbox"]]
    outputs = [run_command(module.handle_command, state, cmd) or "" for cmd in expert_path(m)]
    assert mystery.missing_evidence(outputs, m) == [], m["id"]


@pytest.mark.parametrize("m", ALL, ids=_id)
def test_evidence_is_not_on_screen_at_the_start(m):
    """The symptom and help text shouldn't satisfy the evidence by themselves."""
    assert len(mystery.missing_evidence([m["symptom"]], m)) == len(m["evidence"]), m["id"]


@pytest.mark.parametrize("m", ALL, ids=_id)
def test_symptom_does_not_give_away_the_answer(m):
    answer = m["question"]["options"][m["question"]["answer"]].lower()
    for giveaway in ["oom", "port 8080 is held", "debug log", "restart loop", "config.yml"]:
        if giveaway in answer:
            assert giveaway not in m["symptom"].lower(), f"{m['id']} symptom reveals '{giveaway}'"


# ---------------------------------------------------------------- scoring

class TestScoring:
    def test_perfect_run(self):
        assert mystery.score(commands=5, expert=5, wrong_answers=0, collateral=0) == 100

    def test_twice_the_expert_count_is_free(self):
        assert mystery.score(commands=10, expert=5, wrong_answers=0, collateral=0) == 100

    def test_penalties(self):
        assert mystery.score(commands=5, expert=5, wrong_answers=1, collateral=0) == 80
        assert mystery.score(commands=5, expert=5, wrong_answers=0, collateral=1) == 85
        assert mystery.score(commands=15, expert=5, wrong_answers=0, collateral=0) == 90
        assert mystery.score(commands=100, expert=5, wrong_answers=0, collateral=0) == 70

    def test_never_negative(self):
        assert mystery.score(commands=100, expert=1, wrong_answers=2, collateral=5) == 0


# ------------------------------------------------------------------- flow

class TestRunMystery:
    def m(self, mystery_id="mystery-linux-001"):
        return next(m for m in ALL if m["id"] == mystery_id)

    def test_expert_run_scores_100(self):
        m = self.m()
        out = mystery.run_mystery(m, input_fn=scripted(expert_path(m) + ["solve", correct_letter(m)]))
        assert out["solved"] and out["score"] == 100 and out["collateral"] == []

    def test_solve_before_fixing_lists_unmet_goals(self, capsys):
        m = self.m()
        mystery.run_mystery(m, input_fn=scripted(["solve", "exit"]))
        assert "Not fixed yet" in capsys.readouterr().out

    def test_wrong_answer_then_right_costs_20(self):
        m = self.m()
        wrong = "abcd"[(m["question"]["answer"] + 1) % 4]
        out = mystery.run_mystery(m, input_fn=scripted(expert_path(m) + ["solve", wrong, correct_letter(m)]))
        assert out["solved"] and out["score"] == 80

    def test_two_wrong_answers_means_not_solved(self):
        m = self.m()
        wrongs = [l for l in "abcd" if l != correct_letter(m)][:2]
        out = mystery.run_mystery(m, input_fn=scripted(expert_path(m) + ["solve"] + wrongs))
        assert not out["solved"] and out["score"] == 0

    def test_killing_sshd_is_collateral(self):
        m = self.m()
        state = mystery.build_state(m)
        sshd = next(p["pid"] for p in state["processes"] if "sshd" in p["command"])
        cmds = [f"kill {sshd}"] + expert_path(m) + ["solve", correct_letter(m)]
        out = mystery.run_mystery(m, input_fn=scripted(cmds))
        assert out["solved"] and out["score"] == 85
        assert any("locked yourself out" in c for c in out["collateral"])

    def test_giveup_reveals_answer(self, capsys):
        m = self.m()
        out = mystery.run_mystery(m, input_fn=scripted(["giveup"]))
        assert out["gave_up"] and not out["solved"]
        assert m["question"]["options"][m["question"]["answer"]] in capsys.readouterr().out

    def test_docker_mystery_goes_straight_to_the_question(self):
        m = self.m("mystery-docker-001")
        out = mystery.run_mystery(m, input_fn=scripted(expert_path(m) + ["solve", correct_letter(m)]))
        assert out["solved"] and out["score"] == 100

    def test_guessing_without_investigating_is_refused(self, capsys):
        m = self.m("mystery-docker-001")
        out = mystery.run_mystery(m, input_fn=scripted(["solve", correct_letter(m), "exit"]))
        assert not out["solved"]
        assert "haven't found the evidence" in capsys.readouterr().out

    def test_typing_the_evidence_yourself_does_not_count(self, capsys):
        m = self.m("mystery-docker-002")
        out = mystery.run_mystery(m, input_fn=scripted(
            ["docker logs config.yml Restarting", "solve", correct_letter(m), "exit"]))
        assert not out["solved"]

    def test_help_does_not_count_as_a_command(self):
        m = self.m()
        out = mystery.run_mystery(m, input_fn=scripted(["help"] + expert_path(m) + ["solve", correct_letter(m)]))
        assert out["commands"] == len(expert_path(m))
