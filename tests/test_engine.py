"""Tests for the generic command-matching engine (engine.py).

The engine has zero kubectl-specific knowledge — these tests use plain
strings to prove that, and separately assert it correctly matches real
kubectl syntax variations.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import is_close, matches, normalize, run_scenario


class TestNormalize:
    def test_lowercases(self):
        assert normalize("KUBECTL GET PODS") == "kubectl get pods"

    def test_collapses_whitespace(self):
        assert normalize("kubectl   get    pods") == "kubectl get pods"

    def test_strips_leading_trailing_whitespace(self):
        assert normalize("  kubectl get pods  ") == "kubectl get pods"

    def test_strips_bom(self):
        # PowerShell prepends a UTF-8 BOM when piping strings to stdin.
        assert normalize("﻿kubectl get pods") == "kubectl get pods"

    def test_flag_space_becomes_equals(self):
        assert normalize("kubectl run pod --image nginx") == "kubectl run pod --image=nginx"

    def test_boolean_flag_does_not_swallow_following_flag(self):
        assert normalize("cmd --permanent --add-port=80/tcp") == "cmd --permanent --add-port=80/tcp"

    def test_flag_equals_stays_equals(self):
        assert normalize("kubectl run pod --image=nginx") == "kubectl run pod --image=nginx"


class TestMatches:
    def test_exact_match(self):
        assert matches("kubectl get pods", ["kubectl get pods"])

    def test_case_insensitive(self):
        assert matches("KUBECTL GET PODS", ["kubectl get pods"])

    def test_flag_space_vs_equals(self):
        assert matches("kubectl run my-pod --image nginx", ["kubectl run my-pod --image=nginx"])

    def test_extra_whitespace(self):
        assert matches("kubectl   get   pods", ["kubectl get pods"])

    def test_reordered_flags(self):
        assert matches(
            "kubectl create deployment web --replicas=3 --image=nginx",
            ["kubectl create deployment web --image=nginx --replicas=3"],
        )

    def test_reordered_boolean_and_valued_flags(self):
        assert matches(
            "firewall-cmd --permanent --add-port=8443/tcp",
            ["firewall-cmd --add-port=8443/tcp --permanent"],
        )

    def test_any_expected_command_can_match(self):
        expected = ["kubectl get pods", "kubectl get pod my-first-pod"]
        assert matches("kubectl get pod my-first-pod", expected)
        assert matches("kubectl get pods", expected)

    def test_wrong_command_does_not_match(self):
        assert not matches("kubectl delete pod my-pod", ["kubectl get pods"])

    def test_missing_flag_does_not_match(self):
        assert not matches("kubectl run my-pod", ["kubectl run my-pod --image=nginx"])

    def test_wrong_pod_name_does_not_match(self):
        assert not matches("kubectl get pod other-pod", ["kubectl get pod my-first-pod"])


class TestIsClose:
    def test_same_verb_and_resource_is_close(self):
        assert is_close("kubectl run my-pod", ["kubectl run my-pod --image=nginx"])

    def test_different_verb_is_not_close(self):
        assert not is_close("kubectl delete pod my-pod", ["kubectl run my-pod --image=nginx"])

    def test_empty_input_is_not_close(self):
        assert not is_close("", ["kubectl get pods"])

    def test_generic_engine_has_no_kubectl_knowledge(self):
        # The matcher is pure string/token comparison — it works identically
        # for a non-kubectl command, proving there's no hardcoded k8s logic.
        assert matches("docker ps -a", ["docker ps -a", "docker ps --all"])
        assert is_close("docker ps", ["docker ps -a"])


class TestRunScenario:
    def _scenario(self, why=None):
        step = {
            "prompt": "Do the thing.",
            "expected_commands": ["do thing"],
            "fake_output": "thing done",
            "explanation": "This is why it matters.",
        }
        if why:
            step["why"] = why
        return {"title": "Test Scenario", "intro": "intro text", "steps": [step]}

    def test_why_field_is_shown_on_correct_answer(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "do thing")
        run_scenario(self._scenario(why="Because reasons."))
        assert "Why this way: Because reasons." in capsys.readouterr().out

    def test_missing_why_field_prints_nothing_extra(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "do thing")
        run_scenario(self._scenario(why=None))
        assert "Why this way" not in capsys.readouterr().out

    def test_quit_mid_scenario_returns_false(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "exit")
        assert run_scenario(self._scenario()) is False

    def test_completing_all_steps_returns_true(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "do thing")
        assert run_scenario(self._scenario()) is True
