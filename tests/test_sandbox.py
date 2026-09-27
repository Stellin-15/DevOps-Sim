"""Tests for sandbox.py — random cluster generation and free-form command handling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sandbox


def make_state(pods):
    return {"generated_at": "2026-01-01T00:00:00", "namespace": "default", "pods": pods}


def make_pod(**overrides):
    pod = {
        "name": "checkout-service-abc1234567-xyz89",
        "service": "checkout-service",
        "image": "checkout-service:1.0.0",
        "namespace": "default",
        "status": "Running",
        "ready": "1/1",
        "restarts": 0,
        "age": "5m",
        "node": "node-1",
        "cpu": "100m",
        "memory": "128Mi",
        "memory_limit": "256Mi",
    }
    pod.update(overrides)
    return pod


class TestGenerateState:
    def test_generates_between_4_and_7_pods(self):
        state = sandbox.generate_state()
        assert 4 <= len(state["pods"]) <= 7

    def test_pod_names_are_unique(self):
        state = sandbox.generate_state()
        names = [p["name"] for p in state["pods"]]
        assert len(names) == len(set(names))

    def test_crashloop_pods_have_restarts(self):
        # Run many times since status is randomized; just prove the invariant holds.
        for _ in range(50):
            pod = sandbox.generate_pod("checkout-service")
            if pod["status"] == "CrashLoopBackOff":
                assert pod["restarts"] >= 4
            if pod["status"] == "Running":
                assert pod["ready"] == "1/1"
            else:
                assert pod["ready"] == "0/1"


class TestHandleCommand:
    def test_get_pods_lists_all(self):
        state = make_state([make_pod(name="a"), make_pod(name="b")])
        output = sandbox.handle_command(state, "kubectl get pods")
        assert "a" in output and "b" in output

    def test_get_pods_wide_includes_node(self):
        state = make_state([make_pod(node="node-2")])
        output = sandbox.handle_command(state, "kubectl get pods -o wide")
        assert "node-2" in output

    def test_get_pod_by_name(self):
        state = make_state([make_pod(name="my-pod")])
        output = sandbox.handle_command(state, "kubectl get pod my-pod")
        assert "my-pod" in output

    def test_get_pod_unknown_name_returns_not_found(self):
        state = make_state([make_pod(name="my-pod")])
        output = sandbox.handle_command(state, "kubectl get pod nonexistent")
        assert "NotFound" in output

    def test_describe_pod_known(self):
        state = make_state([make_pod(name="my-pod", status="CrashLoopBackOff")])
        output = sandbox.handle_command(state, "kubectl describe pod my-pod")
        assert "my-pod" in output
        assert "CrashLoopBackOff" in output
        assert "BackOff" in output  # events section

    def test_logs_crashloop_pod(self):
        state = make_state([make_pod(name="my-pod", status="CrashLoopBackOff")])
        output = sandbox.handle_command(state, "kubectl logs my-pod")
        assert "panic" in output.lower() or "fatal" in output.lower()

    def test_logs_running_pod(self):
        state = make_state([make_pod(name="my-pod", status="Running")])
        output = sandbox.handle_command(state, "kubectl logs my-pod")
        assert "started successfully" in output

    def test_top_pod_single(self):
        state = make_state([make_pod(name="my-pod", cpu="250m", memory="64Mi")])
        output = sandbox.handle_command(state, "kubectl top pod my-pod")
        assert "250m" in output and "64Mi" in output

    def test_top_pod_all(self):
        state = make_state([make_pod(name="a"), make_pod(name="b")])
        output = sandbox.handle_command(state, "kubectl top pod")
        assert "a" in output and "b" in output

    def test_exit_returns_none(self):
        state = make_state([make_pod()])
        assert sandbox.handle_command(state, "exit") is None
        assert sandbox.handle_command(state, "quit") is None

    def test_help_returns_help_text(self):
        state = make_state([make_pod()])
        output = sandbox.handle_command(state, "help")
        assert "kubectl get pods" in output

    def test_unknown_command_gives_a_nudge(self):
        state = make_state([make_pod()])
        output = sandbox.handle_command(state, "asdf")
        assert "Unknown command" in output

    def test_singular_and_plural_pod_resource_both_work(self):
        state = make_state([make_pod(name="a")])
        assert "a" in sandbox.handle_command(state, "kubectl get pod")
        assert "a" in sandbox.handle_command(state, "kubectl get pods")
