"""Tests for sandbox.py — random cluster generation and free-form command handling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sandbox


def make_state(pods, **overrides):
    state = {"generated_at": "2026-01-01T00:00:00", "namespace": "default", "pods": pods}
    state.update(overrides)
    return state


def make_deployment(**overrides):
    dep = {"name": "web", "desired": 3, "ready": 3, "up_to_date": 3, "available": 3, "age": "5m"}
    dep.update(overrides)
    return dep


def make_service(**overrides):
    svc = {"name": "web", "type": "ClusterIP", "cluster_ip": "10.96.0.1", "port": 80, "age": "5m"}
    svc.update(overrides)
    return svc


def make_configmap(**overrides):
    cm = {"name": "app-config", "data": {"APP_MODE": "production"}, "age": "5m"}
    cm.update(overrides)
    return cm


def make_secret(**overrides):
    s = {"name": "app-secrets", "type": "Opaque", "data": {"DB_PASSWORD": "aHVudGVyMg=="}, "age": "5m"}
    s.update(overrides)
    return s


def make_node(**overrides):
    n = {"name": "node-1", "status": "Ready", "age": "10d"}
    n.update(overrides)
    return n


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
    def test_generates_between_4_and_6_services(self):
        state = sandbox.generate_state()
        assert 4 <= len(state["deployments"]) <= 6
        assert len(state["deployments"]) == len(state["services"])

    def test_pod_count_matches_deployment_replicas(self):
        state = sandbox.generate_state()
        # Each service has 1-3 replica pods, so total pods scales with deployments.
        assert len(state["deployments"]) <= len(state["pods"]) <= len(state["deployments"]) * 3

    def test_pod_names_are_unique(self):
        state = sandbox.generate_state()
        names = [p["name"] for p in state["pods"]]
        assert len(names) == len(set(names))

    def test_includes_nodes_configmaps_secrets_events(self):
        state = sandbox.generate_state()
        assert len(state["nodes"]) == 3
        assert len(state["configmaps"]) >= 1
        assert len(state["secrets"]) >= 1
        assert len(state["events"]) == len(state["pods"])

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


class TestDeployments:
    def test_get_deployments_lists_all(self):
        state = make_state([], deployments=[make_deployment(name="web"), make_deployment(name="api")])
        output = sandbox.handle_command(state, "kubectl get deployments")
        assert "web" in output and "api" in output

    def test_get_deploy_alias_works(self):
        state = make_state([], deployments=[make_deployment(name="web")])
        output = sandbox.handle_command(state, "kubectl get deploy")
        assert "web" in output

    def test_get_deployment_by_name_unknown(self):
        state = make_state([], deployments=[make_deployment(name="web")])
        output = sandbox.handle_command(state, "kubectl get deployment nonexistent")
        assert "NotFound" in output

    def test_describe_deployment(self):
        state = make_state([], deployments=[make_deployment(name="web", desired=3, ready=2)])
        output = sandbox.handle_command(state, "kubectl describe deployment web")
        assert "web" in output
        assert "2" in output and "3" in output

    def test_describe_deployment_requires_name(self):
        state = make_state([], deployments=[make_deployment(name="web")])
        output = sandbox.handle_command(state, "kubectl describe deployment")
        assert "must specify" in output


class TestServices:
    def test_get_svc_lists_all(self):
        state = make_state([], services=[make_service(name="web"), make_service(name="db")])
        output = sandbox.handle_command(state, "kubectl get svc")
        assert "web" in output and "db" in output

    def test_get_services_alias_works(self):
        state = make_state([], services=[make_service(name="web")])
        output = sandbox.handle_command(state, "kubectl get services")
        assert "web" in output

    def test_describe_service_shows_cluster_ip(self):
        state = make_state([], services=[make_service(name="web", cluster_ip="10.96.5.5")])
        output = sandbox.handle_command(state, "kubectl describe svc web")
        assert "10.96.5.5" in output

    def test_get_service_unknown_name(self):
        state = make_state([], services=[make_service(name="web")])
        output = sandbox.handle_command(state, "kubectl get svc nonexistent")
        assert "NotFound" in output


class TestConfigMapsAndSecrets:
    def test_get_configmaps(self):
        state = make_state([], configmaps=[make_configmap(name="app-config")])
        output = sandbox.handle_command(state, "kubectl get configmaps")
        assert "app-config" in output

    def test_get_cm_alias_works(self):
        state = make_state([], configmaps=[make_configmap(name="app-config")])
        output = sandbox.handle_command(state, "kubectl get cm")
        assert "app-config" in output

    def test_describe_configmap_shows_data(self):
        state = make_state([], configmaps=[make_configmap(name="app-config", data={"APP_MODE": "production"})])
        output = sandbox.handle_command(state, "kubectl describe configmap app-config")
        assert "APP_MODE" in output and "production" in output

    def test_get_secrets_hides_values(self):
        state = make_state([], secrets=[make_secret(name="app-secrets", data={"DB_PASSWORD": "aHVudGVyMg=="})])
        output = sandbox.handle_command(state, "kubectl get secrets")
        assert "app-secrets" in output
        assert "aHVudGVyMg==" not in output

    def test_describe_secret_shows_keys_not_values(self):
        state = make_state([], secrets=[make_secret(name="app-secrets", data={"DB_PASSWORD": "aHVudGVyMg=="})])
        output = sandbox.handle_command(state, "kubectl describe secret app-secrets")
        assert "DB_PASSWORD" in output
        assert "aHVudGVyMg==" not in output


class TestNodesAndEvents:
    def test_get_nodes_lists_all(self):
        state = make_state([], nodes=[make_node(name="node-1"), make_node(name="node-2")])
        output = sandbox.handle_command(state, "kubectl get nodes")
        assert "node-1" in output and "node-2" in output

    def test_describe_node_lists_pods_on_it(self):
        state = make_state(
            [make_pod(name="web-abc", node="node-1")],
            nodes=[make_node(name="node-1")],
        )
        output = sandbox.handle_command(state, "kubectl describe node node-1")
        assert "web-abc" in output

    def test_top_nodes_sums_pod_usage(self):
        state = make_state(
            [make_pod(name="a", node="node-1", cpu="100m", memory="50Mi"),
             make_pod(name="b", node="node-1", cpu="150m", memory="70Mi")],
            nodes=[make_node(name="node-1")],
        )
        output = sandbox.handle_command(state, "kubectl top nodes")
        assert "250m" in output
        assert "120Mi" in output

    def test_get_events(self):
        state = make_state([], events=[
            {"last_seen": "5m", "type": "Warning", "reason": "BackOff", "object": "pod/x", "message": "boom"}
        ])
        output = sandbox.handle_command(state, "kubectl get events")
        assert "BackOff" in output and "boom" in output

    def test_get_events_empty(self):
        state = make_state([], events=[])
        output = sandbox.handle_command(state, "kubectl get events")
        assert "No resources found" in output


class TestGetAll:
    def test_get_all_includes_pods_services_deployments(self):
        state = make_state(
            [make_pod(name="web-abc")],
            services=[make_service(name="web")],
            deployments=[make_deployment(name="web")],
        )
        output = sandbox.handle_command(state, "kubectl get all")
        assert "pod/web-abc" in output
        assert "service/web" in output
        assert "deployment.apps/web" in output
