"""Tests for docker_sandbox.py — state invariants and each problem type's evidence."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import docker_sandbox as d
from sandbox_common import run_command

SEEDS = range(200)


def state_with(problem):
    for seed in SEEDS:
        state = d.generate_state(seed)
        for c in state["containers"]:
            if c["problem"] == problem:
                return state, c
    raise AssertionError(f"no seed produced {problem}")


def run(state, cmd):
    return run_command(d.handle_command, state, cmd)


class TestGeneration:
    def test_every_state_has_one_or_two_problems(self):
        for seed in SEEDS:
            broken = [c for c in d.generate_state(seed)["containers"] if c["problem"]]
            assert 1 <= len(broken) <= 2

    def test_only_app_containers_break(self):
        for seed in SEEDS:
            for c in d.generate_state(seed)["containers"]:
                if c["problem"]:
                    assert c["name"] in ("web", "api", "worker")

    def test_all_problem_types_occur(self):
        seen = {c["problem"] for seed in SEEDS for c in d.generate_state(seed)["containers"]}
        assert set(d.PROBLEMS) <= seen

    def test_same_seed_same_state(self):
        a, b = d.generate_state(5), d.generate_state(5)
        a.pop("generated_at"), b.pop("generated_at")
        assert a == b


class TestProblemEvidence:
    def test_oom_shows_exit_137_and_oomkilled(self):
        s, c = state_with("oom")
        assert run(s, f"docker inspect {c['name']} --format '{{{{.State.ExitCode}}}}'") == "137"
        assert run(s, f"docker inspect {c['name']} --format='{{{{.State.OOMKilled}}}}'") == "true"
        assert c["name"] not in run(s, "docker ps")
        assert c["name"] in run(s, "docker ps -a")

    def test_crash_logs_show_the_missing_env_var(self):
        s, c = state_with("crash")
        assert "DATABASE_URL" in run(s, f"docker logs {c['name']}")
        assert run(s, f"docker inspect {c['name']} --format '{{{{.State.ExitCode}}}}'") == "1"

    def test_restart_loop_is_visible_in_ps_and_restart_count(self):
        s, c = state_with("restart_loop")
        assert "Restarting" in run(s, f"docker ps | grep {c['name']}")
        assert int(run(s, f"docker inspect {c['name']} --format '{{{{.RestartCount}}}}'")) >= 40

    def test_unhealthy_shows_in_ps_and_health_status(self):
        s, c = state_with("unhealthy")
        assert "(unhealthy)" in run(s, "docker ps")
        assert run(s, f"docker inspect {c['name']} --format '{{{{.State.Health.Status}}}}'") == "unhealthy"


class TestCommands:
    @pytest.fixture
    def s(self):
        return d.generate_state(3)

    def test_container_by_id_prefix(self, s):
        c = s["containers"][0]
        assert run(s, f"docker logs {c['id'][:5]}") == "\n".join(c["logs"])

    def test_unknown_container(self, s):
        assert "No such container" in run(s, "docker logs nope")

    def test_exec_into_exited_container_fails(self):
        s, c = state_with("oom")
        assert "is not running" in run(s, f"docker exec -it {c['name']} env")

    def test_system_df_shows_reclaimable_space(self, s):
        assert "RECLAIMABLE" in run(s, "docker system df")

    def test_dangling_volume_filter(self, s):
        dangling = [v for v in s["volumes"] if v["dangling"]]
        assert run(s, "docker volume ls -f dangling=true | grep -c local") == str(len(dangling))

    def test_aliases(self, s):
        assert run(s, "docker container ls -a") == run(s, "docker ps -a")
        assert run(s, "docker image ls") == run(s, "docker images")

    def test_non_docker_command_gets_a_nudge(self, s):
        assert "Docker host" in run(s, "kubectl get pods")

    def test_exit(self, s):
        assert d.handle_command(s, "exit") is None
