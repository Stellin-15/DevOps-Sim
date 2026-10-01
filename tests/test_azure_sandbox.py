import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import azure_sandbox as z
from sandbox_common import run_command

PATHS = {
    "web": ("internet", "vm-web-01", 443),
    "ssh": ("internet", "vm-web-01", 22),
    "app": ("vm-web-01", "vm-app-01", 8080),
    "app_out": ("vm-app-01", "internet", 443),
}

BREAKS = {
    "nsg_deny_shadow": {"web", "ssh"},
    "nic_nsg_deny": {"web", "ssh"},
    "udr_blackhole": {"app_out"},
    "vm_deallocated": {"web", "ssh", "app"},     # a stopped web VM can't call the app either
    "app_nsg_missing_allow": {"app"},
}

RULE = "az network nsg rule"


def run(state, cmd):
    return run_command(z.handle_command, state, cmd)


def broken(state):
    return {k for k, p in PATHS.items() if z.reachability(state, *p) is not None}


class TestGeneration:
    def test_healthy_network_works(self):
        assert broken(z.generate_state(1, [])) == set()

    @pytest.mark.parametrize("problem", z.PROBLEMS)
    def test_each_problem_breaks_exactly_its_paths(self, problem):
        assert broken(z.generate_state(1, [problem])) == BREAKS[problem]

    def test_random_subscriptions_have_two_problems_and_every_type_occurs(self):
        seen = set()
        for seed in range(200):
            s = z.generate_state(seed)
            assert len(set(s["problems"])) == 2
            seen.update(s["problems"])
        assert seen == set(z.PROBLEMS)

    def test_seed_is_deterministic(self):
        assert z.generate_state(9) == z.generate_state(9)


class TestFixes:
    def fixed(self, problem, commands):
        s = z.generate_state(4, [problem])
        for cmd in commands:
            out = run(s, cmd)
            assert "notfound" not in out.lower() and "usage" not in out.lower(), (cmd, out)
        assert broken(s) == set()
        return s

    def test_narrowing_the_deny_rule_source(self):
        s = self.fixed("nsg_deny_shadow", [
            f"{RULE} update -g rg-web-prod --nsg-name nsg-web -n Block-Scanner --source-address-prefixes 192.0.2.66"])
        assert z.collateral_issues(s) == set()

    def test_deleting_the_deny_rule_also_works(self):
        self.fixed("nsg_deny_shadow", [f"{RULE} delete -g rg-web-prod --nsg-name nsg-web -n Block-Scanner"])

    def test_moving_the_deny_rule_below_the_allow_works(self):
        s = z.generate_state(4, ["nsg_deny_shadow"])
        run(s, f"{RULE} update -g rg-web-prod --nsg-name nsg-web -n Block-Scanner --priority 200")
        assert "web" not in broken(s)   # Allow-HTTPS (100) now wins

    def test_detaching_the_nic_nsg(self):
        self.fixed("nic_nsg_deny", ['az network nic update -g rg-web-prod -n nic-vm-web-01 --network-security-group ""'])

    def test_subnet_rules_cannot_override_a_nic_level_deny(self):
        s = z.generate_state(4, ["nic_nsg_deny"])
        run(s, f"{RULE} create -g rg-web-prod --nsg-name nsg-web -n Allow-Again --priority 120 --access Allow "
               "--destination-port-ranges 443 --source-address-prefixes Internet")
        assert "web" in broken(s)

    def test_pointing_the_route_at_the_real_firewall(self):
        self.fixed("udr_blackhole", [
            "az network route-table route update -g rg-web-prod --route-table-name rt-app -n to-firewall --next-hop-ip-address 10.0.0.4"])

    def test_starting_the_vm(self):
        self.fixed("vm_deallocated", ["az vm start -g rg-web-prod -n vm-web-01"])

    def test_adding_the_missing_allow_above_the_deny(self):
        self.fixed("app_nsg_missing_allow", [
            f"{RULE} create -g rg-web-prod --nsg-name nsg-app -n Allow-Web-To-App --priority 100 --access Allow "
            "--destination-port-ranges 8080 --source-address-prefixes 10.20.1.0/24"])

    def test_an_allow_below_the_deny_does_nothing(self):
        s = z.generate_state(4, ["app_nsg_missing_allow"])
        run(s, f"{RULE} create -g rg-web-prod --nsg-name nsg-app -n Too-Late --priority 4050 --access Allow "
               "--destination-port-ranges 8080 --source-address-prefixes 10.20.1.0/24")
        assert "app" in broken(s)

    def test_duplicate_priority_is_rejected(self):
        s = z.generate_state(4, [])
        out = run(s, f"{RULE} create -g rg-web-prod --nsg-name nsg-web -n Dup --priority 100 --access Allow "
                     "--destination-port-ranges 80 --source-address-prefixes Internet")
        assert "SecurityRuleConflict" in out


class TestDiagnostics:
    def test_ip_flow_verify_names_the_deciding_rule(self):
        s = z.generate_state(4, ["nsg_deny_shadow"])
        ip = z.placeholders(s)["web_private_ip"]
        out = run(s, f"az network watcher test-ip-flow -g rg-web-prod --vm vm-web-01 --direction Inbound "
                     f"--protocol TCP --local {ip}:443 --remote 203.0.113.50:50000")
        assert '"access": "Deny"' in out and "Block-Scanner" in out

    def test_ip_flow_names_the_nic_level_rule(self):
        s = z.generate_state(4, ["nic_nsg_deny"])
        ip = z.placeholders(s)["web_private_ip"]
        out = run(s, f"az network watcher test-ip-flow -g rg-web-prod --vm vm-web-01 --direction Inbound "
                     f"--protocol TCP --local {ip}:443 --remote 203.0.113.50:50000")
        assert "networkInterface/nsg-vm-web-01" in out

    def test_next_hop_shows_the_wrong_appliance_ip(self):
        s = z.generate_state(4, ["udr_blackhole"])
        out = run(s, "az network watcher show-next-hop -g rg-web-prod --vm vm-app-01 --source-ip 10.20.2.4 --dest-ip 20.50.1.10")
        assert '"nextHopIpAddress": "10.0.0.5"' in out
        assert "10.0.0.4" in run(s, "az network firewall show -g rg-network-hub -n fw-hub")

    def test_default_rules_are_hidden_unless_asked_for(self):
        s = z.generate_state(4, [])
        assert "DenyAllInBound" not in run(s, f"{RULE} list -g rg-web-prod --nsg-name nsg-web")
        assert "DenyAllInBound" in run(s, f"{RULE} list -g rg-web-prod --nsg-name nsg-web --include-default")

    def test_effective_nsg_lists_both_associations(self):
        out = run(z.generate_state(4, ["nic_nsg_deny"]), "az network nic list-effective-nsg -g rg-web-prod -n nic-vm-web-01")
        assert "subnet snet-web" in out and "networkInterface nic-vm-web-01" in out

    def test_run_command_executes_inside_the_vm(self):
        s = z.generate_state(4, ["udr_blackhole"])
        out = run(s, 'az vm run-command invoke -g rg-web-prod -n vm-app-01 --command-id RunShellScript --scripts "curl -m 5 https://example.com"')
        assert "[stdout]" in out and "Timeout was reached" in out

    def test_run_command_needs_a_running_vm(self):
        s = z.generate_state(4, ["vm_deallocated"])
        out = run(s, 'az vm run-command invoke -g rg-web-prod -n vm-web-01 --command-id RunShellScript --scripts "hostname"')
        assert "not running" in out
        assert "VM deallocated" in run(s, "az vm list -d")

    def test_failures_from_the_laptop_are_plain_timeouts(self):
        s = z.generate_state(4, ["nsg_deny_shadow"])
        out = run(s, f"curl -m 5 https://{z.placeholders(s)['web_ip']}")
        assert "Timeout was reached" in out and "nsg" not in out.lower()

    def test_unknown_resource_group_and_unsupported_command(self):
        s = z.generate_state(4, [])
        assert "ResourceGroupNotFound" in run(s, "az vm list -g nope")
        assert "isn't simulated" in run(s, "az sql server list")


class TestCollateral:
    def test_allowing_ssh_from_anywhere_is_flagged(self):
        s = z.generate_state(4, [])
        run(s, f"{RULE} create -g rg-web-prod --nsg-name nsg-web -n ssh-any --priority 200 --access Allow "
               "--destination-port-ranges 22 --source-address-prefixes '*'")
        assert any("port 22" in i for i in z.collateral_issues(s))

    def test_allow_everything_is_flagged(self):
        s = z.generate_state(4, ["nsg_deny_shadow"])
        run(s, f"{RULE} update -g rg-web-prod --nsg-name nsg-web -n Block-Scanner --access Allow")
        assert any("every port" in i for i in z.collateral_issues(s))
