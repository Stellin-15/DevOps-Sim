import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import gcp_sandbox as g
from sandbox_common import run_command

PATHS = {
    "web": ("internet", "web-1", 443),
    "iap": ("iap", "worker-1", 22),
    "db": ("web-1", "db-1", 5432),
    "worker_out": ("worker-1", "internet", 443),
}

BREAKS = {
    "wrong_tag": {"web", "db"},          # tags are identity: without 'web', web-1 also loses its DB access
    "no_nat": {"worker_out"},
    "iap_rule_missing": {"iap"},
    "deny_rule_priority": {"web"},
    "db_rule_wrong_source": {"db"},
    "no_external_ip": {"web"},
}

SSH = "gcloud compute ssh worker-1 --zone europe-west1-b --tunnel-through-iap"
FW = "gcloud compute firewall-rules"


def run(state, cmd):
    return run_command(g.handle_command, state, cmd)


def broken(state):
    return {k for k, p in PATHS.items() if g.reachability(state, *p) is not None}


class TestGeneration:
    def test_healthy_project_works(self):
        assert broken(g.generate_state(1, [])) == set()

    def test_the_database_is_never_reachable_from_the_internet(self):
        assert g.reachability(g.generate_state(1, []), "internet", "db-1", 5432) is not None

    @pytest.mark.parametrize("problem", g.PROBLEMS)
    def test_each_problem_breaks_exactly_its_paths(self, problem):
        assert broken(g.generate_state(1, [problem])) == BREAKS[problem]

    def test_random_projects_have_two_problems_and_every_type_occurs(self):
        seen = set()
        for seed in range(200):
            s = g.generate_state(seed)
            assert len(set(s["problems"])) == 2
            seen.update(s["problems"])
        assert seen == set(g.PROBLEMS)

    def test_seed_is_deterministic(self):
        assert g.generate_state(9) == g.generate_state(9)


class TestFixes:
    def fixed(self, problem, commands):
        s = g.generate_state(4, [problem])
        for cmd in commands:
            out = run(s, cmd)
            assert "ERROR" not in out and "usage" not in out, (cmd, out)
        assert broken(s) == set()
        return s

    def test_adding_the_right_tag(self):
        s = self.fixed("wrong_tag", ["gcloud compute instances add-tags web-1 --zone europe-west1-b --tags web"])
        assert g.collateral_issues(s) == set()

    def test_router_then_nat_in_the_right_region(self):
        self.fixed("no_nat", [
            "gcloud compute routers create router-ew1 --network prod-vpc --region europe-west1",
            "gcloud compute routers nats create nat-ew1 --router router-ew1 --region europe-west1 "
            "--auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges"])

    def test_nat_in_another_region_does_not_help(self):
        s = g.generate_state(4, ["no_nat"])
        run(s, "gcloud compute routers create router-use1 --network prod-vpc --region us-east1")
        run(s, "gcloud compute routers nats create nat-use1 --router router-use1 --region us-east1 "
               "--auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges")
        assert "worker_out" in broken(s)

    def test_nat_needs_a_router_first(self):
        out = run(g.generate_state(4, ["no_nat"]),
                  "gcloud compute routers nats create nat-ew1 --router router-ew1 --region europe-west1")
        assert "ERROR" in out and "router" in out.lower()

    def test_recreating_the_iap_rule(self):
        self.fixed("iap_rule_missing", [
            f"{FW} create allow-iap-ssh --network prod-vpc --allow tcp:22 --source-ranges 35.235.240.0/20"])

    def test_deleting_the_shadowing_deny_rule(self):
        self.fixed("deny_rule_priority", [f"{FW} delete deny-legacy-ports"])

    def test_lowering_the_denys_priority_also_works(self):
        self.fixed("deny_rule_priority", [f"{FW} update deny-legacy-ports --priority 2000"])

    def test_fixing_the_source_tag(self):
        self.fixed("db_rule_wrong_source", [f"{FW} update allow-db-from-web --source-tags web"])

    def test_adding_an_external_ip(self):
        self.fixed("no_external_ip", ["gcloud compute instances add-access-config web-1 --zone europe-west1-b"])


class TestFirewallSemantics:
    def test_deny_wins_at_equal_priority(self):
        s = g.generate_state(4, [])
        run(s, f"{FW} create deny-443 --network prod-vpc --action deny --rules tcp:443 --source-ranges 0.0.0.0/0 --priority 1000")
        assert "web" in broken(s)

    def test_a_rule_with_target_tags_ignores_untagged_vms(self):
        s = g.generate_state(4, [])
        run(s, f"{FW} create allow-5432-web --network prod-vpc --allow tcp:5432 --source-ranges 0.0.0.0/0 --target-tags web")
        assert g.reachability(s, "internet", "db-1", 5432) is not None


class TestSsh:
    def test_iap_failure_and_troubleshoot_explain_it(self):
        s = g.generate_state(4, ["iap_rule_missing"])
        assert "failed to connect to backend" in run(s, SSH)
        assert "35.235.240.0/20" in run(s, SSH + " --troubleshoot")
        assert s["session"] is None

    def test_command_flag_runs_one_command_without_opening_a_session(self):
        s = g.generate_state(4, ["no_nat"])
        assert "connection timed out" in run(s, SSH + " --command 'sudo apt update'")
        assert s["session"] is None

    def test_session_runs_commands_on_the_vm_and_exit_ends_it(self):
        s = g.generate_state(4, [])
        assert "you are now on worker-1" in run(s, SSH)
        assert run(s, "hostname") == "worker-1"
        assert run(s, "curl ifconfig.me") == s["nat_ip"]
        assert "closed" in run(s, "exit") and s["session"] is None
        assert run(s, "exit") is None

    def test_boolean_flag_before_the_vm_name_still_parses(self):
        s = g.generate_state(4, [])
        assert "you are now on worker-1" in run(s, "gcloud compute ssh --tunnel-through-iap worker-1 --zone=europe-west1-b")


class TestOutputAndCollateral:
    def test_failures_from_the_laptop_are_plain_timeouts(self):
        s = g.generate_state(4, ["deny_rule_priority"])
        out = run(s, f"curl -m 5 https://{g.placeholders(s)['web_ip']}")
        assert "Timeout was reached" in out and "firewall" not in out.lower()

    def test_describe_shows_tags_and_rule_targets(self):
        s = g.generate_state(4, ["wrong_tag"])
        assert "http-server" in run(s, "gcloud compute instances describe web-1 --zone europe-west1-b")
        assert "targetTags: [web]" in run(s, f"{FW} describe allow-https-web")

    def test_rule_without_target_tags_says_it_applies_everywhere(self):
        assert "every VM" in run(g.generate_state(4, []), f"{FW} describe allow-iap-ssh")

    def test_unsupported_command(self):
        assert "isn't simulated" in run(g.generate_state(4, []), "gcloud sql instances list")

    def test_ssh_open_to_the_world_is_flagged(self):
        s = g.generate_state(4, ["iap_rule_missing"])
        run(s, f"{FW} create allow-ssh --network prod-vpc --allow tcp:22")
        assert any("port 22" in i and "EVERY VM" in i for i in g.collateral_issues(s))

    def test_untargeted_443_rule_is_flagged(self):
        s = g.generate_state(4, ["wrong_tag"])
        run(s, f"{FW} create allow-https-all --network prod-vpc --allow tcp:443 --source-ranges 0.0.0.0/0")
        assert any("no target tags" in i for i in g.collateral_issues(s))

    def test_external_ip_on_a_private_vm_is_flagged(self):
        s = g.generate_state(4, ["no_nat"])
        run(s, "gcloud compute instances add-access-config worker-1 --zone europe-west1-b")
        assert any("worker-1" in i for i in g.collateral_issues(s))
