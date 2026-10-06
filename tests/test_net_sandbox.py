"""Tests for net_sandbox.py: each layer of the modelled network (names,
routes, ARP, firewall, listeners, MTU) fails with its own real symptom, and
each real fix clears it."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import net_sandbox as net
from sandbox_common import run_command


def fresh(*problems, seed=5):
    return net.generate_state(seed=seed, problems=list(problems))


def run(state, cmd):
    return run_command(net.handle_command, state, cmd)


# ---------------------------------------------------------------- generation

def test_random_state_has_two_problems():
    for seed in range(40):
        s = net.generate_state(seed=seed)
        assert len(s["problems"]) == 2 and set(s["problems"]) <= set(net.PROBLEMS)


def test_state_is_json_saveable():
    assert json.loads(json.dumps(fresh("stale_hosts", "jumbo_mtu")))["link"]["mtu"] == 9000


# ------------------------------------------------------------------- views

def test_ip_views():
    s = fresh("wrong_gateway", "jumbo_mtu")
    assert "mtu 9000" in run(s, "ip addr") and "10.0.1.10/24" in run(s, "ip a")
    assert "default via 10.0.1.254" in run(s, "ip route")
    assert "via 10.0.1.254" in run(s, "ip route get 10.0.2.15")
    assert "via" not in run(s, "ip route get 10.0.1.20")
    assert "10.0.1.254 dev eth0 FAILED" in run(s, "ip neigh")
    assert "mtu 9000" in run(s, "ip link")


def test_files():
    s = fresh("dead_dns", "stale_hosts")
    assert "nameserver 10.0.0.53" in run(s, "cat /etc/resolv.conf")
    assert "10.0.2.40\tapi.shop.example" in run(s, "cat /etc/hosts")
    assert "files dns" in run(s, "cat /etc/nsswitch.conf")
    assert "No such file" in run(s, "cat /etc/nope")


def test_hosts_file_beats_dns():
    s = fresh("stale_hosts")
    assert run(s, "getent hosts api.shop.example").startswith("10.0.2.40")
    assert run(s, "dig +short api.shop.example") == "10.0.2.15"  # dig skips /etc/hosts
    assert "Address: 10.0.2.15" in run(s, "nslookup api.shop.example")


def test_dead_dns_times_out_but_another_server_answers():
    s = fresh("dead_dns")
    assert "no servers could be reached" in run(s, "dig api.shop.example")
    assert run(s, "dig @10.0.1.2 +short api.shop.example") == "10.0.2.15"
    assert run(s, "getent hosts api.shop.example") == ""


def test_dns_needs_a_route_to_the_server():
    s = fresh("wrong_gateway", "dead_dns")  # 10.0.0.53 is off-subnet, so also behind the bad gateway
    assert "timed out" in run(s, "dig api.shop.example")


def test_search_domain_and_nxdomain():
    s = fresh()
    assert run(s, "dig +short db-1") == "10.0.1.20"
    assert "NXDOMAIN" in run(s, "dig nothing.shop.example")


def test_sudo_and_unknown_commands():
    s = fresh()
    assert "default via 10.0.1.1" in run(s, "sudo ip route")
    assert "not simulated" in run(s, "telnet db-1 5432")
