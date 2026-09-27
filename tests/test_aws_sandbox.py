import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import aws_sandbox as a
from sandbox_common import run_command

PATHS = {
    "web": ("internet", "web-1", 443),
    "ssh": ("internet", "web-1", 22),
    "api": ("web-1", "api-1", 8080),
    "worker_out": ("worker-1", "internet", 443),
}

# Which paths each problem must break (and nothing else).
BREAKS = {
    "missing_igw_route": {"web", "ssh", "worker_out"},   # NAT needs the IGW route too
    "private_no_egress": {"worker_out"},
    "sg_missing_port": {"web"},
    "nacl_ephemeral_block": {"web", "ssh"},
    "no_public_ip": {"web", "ssh"},
    "api_sg_wrong_source": {"api"},
}


def run(state, cmd):
    return run_command(a.handle_command, state, cmd)


def broken(state):
    return {k for k, p in PATHS.items() if a.reachability(state, *p) is not None}


class TestGeneration:
    def test_healthy_network_works_end_to_end(self):
        assert broken(a.generate_state(1, [])) == set()

    @pytest.mark.parametrize("problem", a.PROBLEMS)
    def test_each_problem_breaks_exactly_its_paths(self, problem):
        assert broken(a.generate_state(1, [problem])) == BREAKS[problem]

    def test_random_accounts_have_two_problems_and_every_type_occurs(self):
        seen = set()
        for seed in range(200):
            s = a.generate_state(seed)
            assert len(set(s["problems"])) == 2
            seen.update(s["problems"])
        assert seen == set(a.PROBLEMS)

    def test_seed_is_deterministic(self):
        assert a.generate_state(42) == a.generate_state(42)

    def test_ids_look_like_aws_ids(self):
        s = a.generate_state(5, [])
        assert s["vpc"]["id"].startswith("vpc-0") and len(s["vpc"]["id"]) == 21
        assert all(i["id"].startswith("i-0") for i in s["instances"])


class TestFixes:
    """Each problem's real fix, typed as the player would, restores exactly
    the broken path — the sandbox is reactive, not scripted."""

    def fix_and_check(self, problem, commands):
        s = a.generate_state(7, [problem])
        ph = a.placeholders(s)
        for cmd in commands:
            out = run(s, cmd.format(**ph))
            assert "error occurred" not in out.lower() and "usage" not in out.lower(), (cmd, out)
        assert broken(s) == set()
        return s

    def test_missing_igw_route(self):
        self.fix_and_check("missing_igw_route", [
            "aws ec2 create-route --route-table-id {public_rt} --destination-cidr-block 0.0.0.0/0 --gateway-id {igw_id}"])

    def test_private_no_egress(self):
        self.fix_and_check("private_no_egress", [
            "aws ec2 create-route --route-table-id {private_rt} --destination-cidr-block 0.0.0.0/0 --nat-gateway-id {nat_id}"])

    def test_sg_missing_port(self):
        self.fix_and_check("sg_missing_port", [
            "aws ec2 authorize-security-group-ingress --group-id {web_sg} --protocol tcp --port 443 --cidr 0.0.0.0/0"])

    def test_nacl_ephemeral_block(self):
        self.fix_and_check("nacl_ephemeral_block", [
            "aws ec2 create-network-acl-entry --network-acl-id {public_nacl} --rule-number 130 --protocol tcp "
            "--port-range From=1024,To=65535 --cidr-block 0.0.0.0/0 --rule-action allow --egress"])

    def test_no_public_ip(self):
        self.fix_and_check("no_public_ip", [
            "aws ec2 associate-address --instance-id {web_id} --allocation-id {eip_alloc}"])

    def test_api_sg_wrong_source(self):
        self.fix_and_check("api_sg_wrong_source", [
            "aws ec2 authorize-security-group-ingress --group-id {api_sg} --protocol tcp --port 8080 --source-group {web_sg}"])

    def test_nacls_are_stateless_opening_inbound_alone_is_not_enough(self):
        s = a.generate_state(7, ["nacl_ephemeral_block"])
        ph = a.placeholders(s)
        # Inbound 443 was already allowed — the replies are what's dropped.
        run(s, f"aws ec2 replace-network-acl-entry --network-acl-id {ph['public_nacl']} --rule-number 100 --protocol tcp "
               f"--port-range From=443,To=443 --cidr-block 0.0.0.0/0 --rule-action allow --ingress")
        assert "web" in broken(s)

    def test_route_to_a_nat_that_does_not_exist_is_rejected(self):
        s = a.generate_state(7, ["private_no_egress"])
        out = run(s, f"aws ec2 create-route --route-table-id {a.placeholders(s)['private_rt']} "
                     "--destination-cidr-block 0.0.0.0/0 --nat-gateway-id nat-0000000000000000")
        assert "InvalidNatGatewayID.NotFound" in out and "worker_out" in broken(s)

    def test_create_route_twice_says_use_replace(self):
        s = a.generate_state(7, [])
        out = run(s, f"aws ec2 create-route --route-table-id {a.placeholders(s)['public_rt']} "
                     f"--destination-cidr-block 0.0.0.0/0 --gateway-id {s['igw']['id']}")
        assert "RouteAlreadyExists" in out and "replace-route" in out


class TestConnectivityCommands:
    def test_curl_from_laptop_times_out_rather_than_explaining(self):
        s = a.generate_state(7, ["sg_missing_port"])
        out = run(s, f"curl -m 5 https://{s['instances'][0]['public_ip']}")
        assert "Timeout was reached" in out and "security group" not in out.lower()

    def test_ssh_from_the_office_works_when_only_443_is_missing(self):
        s = a.generate_state(7, ["sg_missing_port"])
        assert "Amazon Linux" in run(s, f"ssh ec2-user@{s['instances'][0]['public_ip']}")

    def test_private_ip_is_unreachable_from_the_laptop(self):
        s = a.generate_state(7, [])
        assert "Timeout" in run(s, f"curl http://{s['instances'][1]['private_ip']}:8080")

    def test_instance_name_does_not_resolve_from_the_laptop(self):
        assert "Could not resolve host" in run(a.generate_state(7, []), "curl https://web-1")

    def test_ssm_session_runs_commands_on_the_instance_and_exit_ends_it(self):
        s = a.generate_state(7, ["private_no_egress"])
        ph = a.placeholders(s)
        assert "Starting session" in run(s, f"aws ssm start-session --target {ph['worker_id']}")
        assert "Failed to download metadata" in run(s, "sudo dnf check-update")
        assert "ip-10-0-2-" in run(s, "hostname")
        assert "Exiting session" in run(s, "exit")
        assert s["session"] is None
        assert run(s, "exit") is None  # now exit leaves the sandbox

    def test_worker_egress_goes_out_through_the_nat_ip(self):
        s = a.generate_state(7, [])
        run(s, f"aws ssm start-session --target {a.placeholders(s)['worker_id']}")
        assert run(s, "curl ifconfig.me") == s["nat_gateways"][0]["public_ip"]

    def test_ping_explains_icmp(self):
        assert "ICMP" in run(a.generate_state(7, []), "ping 8.8.8.8")


class TestDescribe:
    def test_filters_narrow_to_one_subnet(self):
        s = a.generate_state(7, [])
        out = run(s, f"aws ec2 describe-route-tables --filters Name=association.subnet-id,Values={s['subnets'][1]['id']}")
        assert "private-rt" in out and "public-rt" not in out

    def test_instances_filter_by_name_tag(self):
        out = run(a.generate_state(7, []), "aws ec2 describe-instances --filters Name=tag:Name,Values=api-1")
        assert "api-1" in out and "web-1" not in out

    def test_missing_public_ip_is_visible(self):
        s = a.generate_state(7, ["no_public_ip"])
        web_line = next(l for l in run(s, "aws ec2 describe-instances").splitlines() if "web-1" in l)
        assert "  -  " in web_line

    def test_nacl_shows_the_implicit_deny(self):
        assert "DENY" in run(a.generate_state(7, []), "aws ec2 describe-network-acls")

    def test_unknown_ids_give_aws_style_errors(self):
        out = run(a.generate_state(7, []), "aws ec2 describe-security-groups --group-ids sg-0nope")
        assert out.startswith("An error occurred (InvalidGroup.NotFound)")

    def test_unsupported_command_says_not_simulated(self):
        assert "isn't simulated" in run(a.generate_state(7, []), "aws rds describe-db-instances")


class TestCollateral:
    def test_opening_ssh_to_the_world_is_flagged(self):
        s = a.generate_state(7, [])
        run(s, f"aws ec2 authorize-security-group-ingress --group-id {a.placeholders(s)['web_sg']} "
               "--protocol tcp --port 22 --cidr 0.0.0.0/0")
        assert any("port 22" in i for i in a.collateral_issues(s))

    def test_opening_443_to_the_world_is_fine(self):
        s = a.generate_state(7, ["sg_missing_port"])
        run(s, f"aws ec2 authorize-security-group-ingress --group-id {a.placeholders(s)['web_sg']} "
               "--protocol tcp --port 443 --cidr 0.0.0.0/0")
        assert a.collateral_issues(s) == set()

    def test_terminating_an_instance_is_flagged(self):
        s = a.generate_state(7, [])
        run(s, f"aws ec2 terminate-instances --instance-ids {a.placeholders(s)['web_id']}")
        assert any("terminated web-1" in i for i in a.collateral_issues(s))
