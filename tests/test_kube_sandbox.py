"""Tests for kube_sandbox.py — pod status is derived from cause, so each
problem must show the right symptom and each real fix must clear it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import kube_sandbox as k
from sandbox_common import run_command

PATCH_QUEUE = """kubectl patch configmap worker-config -p '{"data":{"QUEUE_URL":"amqp://rabbitmq.shop.svc:5672"}}'"""


def run(state, cmd):
    return run_command(k.handle_command, state, cmd)


def health(state):
    """What's broken: unavailable deployments and services with no endpoints."""
    bad = {f"deploy/{d}" for d in ("web", "api", "worker") if not k.deployment_available(state, d)}
    return bad | {f"svc/{s['name']}" for s in state["services"] if not k.endpoints(state, s)}


BREAKS = {
    "bad_image": {"deploy/web", "svc/web"},
    "selector_mismatch": {"svc/web"},                 # every pod is healthy; only the Service is wrong
    "bad_readiness_probe": {"deploy/api", "svc/api"},
    "missing_configmap_key": {"deploy/worker"},
    "oom_limit": {"deploy/worker"},
    "nodes_drained": {"deploy/api", "deploy/worker"},
}

STATUS = {
    "bad_image": ("web", "ImagePullBackOff"),
    "missing_configmap_key": ("worker", "CreateContainerConfigError"),
    "oom_limit": ("worker", "CrashLoopBackOff"),
}


class TestGeneration:
    def test_healthy_cluster(self):
        s = k.generate_state(1, [])
        assert health(s) == set()
        assert len(k.pods(s)) == 7 and all(p["ready"] for p in k.pods(s))

    @pytest.mark.parametrize("problem", k.PROBLEMS)
    def test_each_problem_breaks_exactly_its_part(self, problem):
        assert health(k.generate_state(1, [problem])) == BREAKS[problem]

    @pytest.mark.parametrize("problem", STATUS)
    def test_status_shown_for_each_cause(self, problem):
        app, status = STATUS[problem]
        s = k.generate_state(1, [problem])
        assert {p["status"] for p in k.pods(s) if p["app"] == app} == {status}

    def test_random_clusters_have_two_problems_and_every_type_occurs(self):
        seen = set()
        for seed in range(200):
            s = k.generate_state(seed)
            assert len(set(s["problems"])) == 2
            seen.update(s["problems"])
        assert seen == set(k.PROBLEMS)

    def test_state_is_deterministic_and_json_serialisable(self):
        import json
        assert k.generate_state(7) == k.generate_state(7)
        json.dumps(k.generate_state(7))
        assert [p["name"] for p in k.pods(k.generate_state(7))] == [p["name"] for p in k.pods(k.generate_state(7))]


class TestFixes:
    def fixed(self, problem, commands):
        s = k.generate_state(3, [problem])
        for cmd in commands:
            out = run(s, cmd)
            assert "Error from server" not in out and not out.startswith(("error", "usage")), (cmd, out)
        assert health(s) == set()
        assert k.collateral_issues(s) == set()
        return s

    def test_bad_image_rollout_undo(self):
        self.fixed("bad_image", ["kubectl rollout undo deployment/web"])

    def test_bad_image_set_image(self):
        self.fixed("bad_image", ["kubectl set image deployment/web web=shop/web:2.4.1"])

    def test_selector(self):
        self.fixed("selector_mismatch", ["kubectl set selector service web app=web"])

    def test_readiness_probe_rollout_undo(self):
        self.fixed("bad_readiness_probe", ["kubectl rollout undo deployment/api"])

    def test_configmap_key_patch(self):
        self.fixed("missing_configmap_key", [PATCH_QUEUE])

    def test_configmap_key_can_also_be_fixed_with_a_literal_env(self):
        self.fixed("missing_configmap_key", ["kubectl set env deployment/worker QUEUE_URL=amqp://rabbitmq.shop.svc:5672"])

    def test_oom_limit(self):
        self.fixed("oom_limit", ["kubectl set resources deployment worker --limits=memory=512Mi"])

    def test_nodes_drained(self):
        self.fixed("nodes_drained", ["kubectl uncordon node-2", "kubectl uncordon node-3"])

    def test_deleting_a_broken_pod_fixes_nothing(self):
        s = k.generate_state(3, ["oom_limit"])
        old = k.placeholders(s)["worker_pod"]
        assert "replacement" in run(s, f"kubectl delete pod {old}")
        assert k.placeholders(s)["worker_pod"] != old
        assert "deploy/worker" in health(s)

    def test_a_still_too_small_memory_limit_keeps_crashing(self):
        s = k.generate_state(3, ["oom_limit"])
        run(s, "kubectl set resources deployment worker --limits=memory=128Mi")
        assert "deploy/worker" in health(s)

    def test_layered_failures_show_one_at_a_time(self):
        s = k.generate_state(3, ["missing_configmap_key", "oom_limit"])
        assert "CreateContainerConfigError" in run(s, "kubectl get pods -l app=worker")
        run(s, PATCH_QUEUE)
        assert "CrashLoopBackOff" in run(s, "kubectl get pods -l app=worker")

    def test_undo_twice_returns_to_the_broken_release(self):
        s = k.generate_state(3, ["bad_image"])
        run(s, "kubectl rollout undo deployment/web")
        run(s, "kubectl rollout undo deployment/web")
        assert "deploy/web" in health(s)


class TestDiagnostics:
    def test_describe_pod_explains_each_failure(self):
        cases = {"bad_image": ("web_pod", "manifest unknown"),
                 "missing_configmap_key": ("worker_pod", "couldn't find key QUEUE_URL"),
                 "oom_limit": ("worker_pod", "OOMKilled"),
                 "bad_readiness_probe": ("api_pod", "Readiness probe failed")}
        for problem, (pod_key, needle) in cases.items():
            s = k.generate_state(3, [problem])
            assert needle in run(s, f"kubectl describe pod {k.placeholders(s)[pod_key]}"), problem

    def test_pending_pods_say_why(self):
        s = k.generate_state(3, ["nodes_drained"])
        out = run(s, f"kubectl describe pod {k.placeholders(s)['pending_pod']}")
        assert "FailedScheduling" in out and "2 node(s) were unschedulable" in out and "1 Insufficient cpu" in out
        assert run(s, "kubectl get nodes").count("SchedulingDisabled") == 2

    def test_selector_mismatch_shows_empty_endpoints_with_healthy_pods(self):
        s = k.generate_state(3, ["selector_mismatch"])
        assert "<none>" in run(s, "kubectl get endpoints web")
        assert "app=webapp" in run(s, "kubectl describe svc web")
        assert "503" in run(s, "curl https://shop.example.com")
        assert "0/1" not in run(s, "kubectl get pods")

    def test_logs_previous_shows_the_kill(self):
        s = k.generate_state(3, ["oom_limit"])
        pod = k.placeholders(s)["worker_pod"]
        assert "Killed" in run(s, f"kubectl logs {pod} --previous")
        assert "Killed" not in run(s, f"kubectl logs {pod}")

    def test_logs_of_a_pod_that_never_started(self):
        s = k.generate_state(3, ["bad_image"])
        assert "waiting to start" in run(s, f"kubectl logs {k.placeholders(s)['web_pod']}")

    def test_readiness_logs_show_the_404_and_the_real_health_path(self):
        s = k.generate_state(3, ["bad_readiness_probe"])
        out = run(s, f"kubectl logs {k.placeholders(s)['api_pod']}")
        assert "GET /ready 404" in out and "/healthz" in out

    def test_in_cluster_curl_uses_service_endpoints(self):
        s = k.generate_state(3, ["bad_readiness_probe"])
        web = k.placeholders(s)["web_pod"]
        assert "Connection refused" in run(s, f"kubectl exec {web} -- curl http://api:8080/")
        run(s, "kubectl rollout undo deployment/api")
        assert '"status":"ok"' in run(s, f"kubectl exec {web} -- curl http://api:8080/")
        assert "Could not resolve host" in run(s, f"kubectl exec {web} -- curl http://nope/")

    def test_resource_forms_short_names_and_pipes(self):
        s = k.generate_state(3, [])
        assert "web" in run(s, "kubectl get deploy web") and "web" in run(s, "kubectl get deployment/web")
        assert run(s, "kubectl get po | grep -c Running") == "7"
        assert "REVISION" in run(s, "kubectl rollout history deploy/web")
        assert "QUEUE_URL" in run(s, "kubectl get cm worker-config -o yaml")

    def test_case_is_preserved_for_env_keys(self):
        s = k.generate_state(3, [])
        run(s, "kubectl set env deployment/api LOG_LEVEL=Debug")
        assert "LOG_LEVEL=Debug" in run(s, f"kubectl exec {k.placeholders(s)['api_pod']} -- env")

    def test_other_namespace_not_found_and_unknown_verb(self):
        s = k.generate_state(3, [])
        assert "No resources found in default namespace" in run(s, "kubectl get pods -n default")
        assert "NotFound" in run(s, "kubectl describe pod nope")
        assert "isn't simulated" in run(s, "kubectl apply -f x.yaml")
        assert k.handle_command(s, "exit") is None


class TestCollateral:
    def test_scaling_to_zero_and_deleting_are_flagged(self):
        s = k.generate_state(3, ["oom_limit"])
        run(s, "kubectl scale deployment worker --replicas=0")
        assert any("scaled 'worker' to zero" in i for i in k.collateral_issues(s))
        run(s, "kubectl delete deployment web")
        assert any("deleted the deployment 'web'" in i for i in k.collateral_issues(s))

    def test_absurd_memory_limit_is_flagged(self):
        s = k.generate_state(3, ["oom_limit"])
        run(s, "kubectl set resources deployment worker --limits=memory=8Gi")
        assert any("above 4Gi" in i for i in k.collateral_issues(s))
