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



# ------------------------------------------------------------ connectivity

def test_healthy_network_connects_everywhere():
    s = fresh()
    for target, port in [("api.shop.example", 443), ("db-1", 5432), ("packages.example.org", 443)]:
        assert net.connect(s, target, port, large=True)[0] == "ok"
    assert "0% packet loss" in run(s, "ping -c 2 api.shop.example")
    assert "1843200 bytes" in run(s, "curl https://api.shop.example/catalog")


def test_each_layer_has_its_own_symptom():
    assert "Could not resolve host" in run(fresh("dead_dns"), "curl https://api.shop.example/healthz")
    assert "No route to host" in run(fresh("wrong_gateway"), "curl https://api.shop.example/healthz")
    assert "Timeout was reached" in run(fresh("stale_hosts"), "curl https://api.shop.example/healthz")
    assert "Connection timed out" in run(fresh("firewall_blocks_db"), "nc -zv db-1 5432")
    assert "Connection refused" in run(fresh(), "nc -zv db-1 80")
    out = run(fresh("jumbo_mtu"), "curl https://api.shop.example/catalog")
    assert "Operation timed out" in out and "2896 out of" in out


def test_ip_addresses_bypass_broken_dns():
    s = fresh("dead_dns")
    assert "succeeded" in run(s, "nc -zv 10.0.2.15 443")
    assert "Temporary failure in name resolution" in run(s, "ping api.shop.example")


def test_wrong_gateway_spares_the_local_subnet():
    s = fresh("wrong_gateway")
    assert "succeeded" in run(s, "nc -zv db-1 5432")
    out = run(s, "ping -c 2 api.shop.example")
    assert "Destination Host Unreachable" in out and "100% packet loss" in out
    assert "!H" in run(s, "traceroute api.shop.example")


def test_jumbo_mtu_small_works_large_fails():
    s = fresh("jumbo_mtu")
    assert '{"status":"ok"}' in run(s, "curl https://api.shop.example/healthz")
    assert "0% packet loss" in run(s, "ping -c 2 -M do -s 1472 api.shop.example")
    assert "100% packet loss" in run(s, "ping -c 2 -M do -s 2000 api.shop.example")
    assert "pmtu 9000" in run(s, "tracepath api.shop.example")


def test_df_ping_larger_than_the_interface():
    out = run(fresh(), "ping -c 1 -M do -s 2000 db-1")
    assert "message too long, mtu=1500" in out


def test_stale_hosts_times_out_beyond_the_gateway():
    s = fresh("stale_hosts")
    out = run(s, "traceroute api.shop.example")
    assert "10.0.2.40" in out and "* * *" in out


def test_pg_isready_and_verbose_curl():
    assert "accepting connections" in run(fresh(), "pg_isready -h db-1.shop.internal")
    assert "no response" in run(fresh("firewall_blocks_db"), "pg_isready -h db-1.shop.internal")
    assert "Connected to api.shop.example (10.0.2.15) port 443" in run(fresh(), "curl -v https://api.shop.example/")


# --------------------------------------------------------------------- fixes

def test_replacing_the_default_route():
    s = fresh("wrong_gateway")
    assert run(s, "ip route add default via 10.0.1.1") == "RTNETLINK answers: File exists"
    assert "invalid gateway" in run(s, "ip route replace default via 10.9.9.9")
    run(s, "ip route replace default via 10.0.1.1")
    assert "succeeded" in run(s, "nc -zv api.shop.example 443")


def test_deleting_then_adding_the_route():
    s = fresh("wrong_gateway")
    run(s, "ip route del default")
    assert "Network is unreachable" in run(s, "ping api.shop.example")
    assert "No such process" in run(s, "ip route del default")
    run(s, "ip route add default via 10.0.1.1 dev eth0")
    assert "0% packet loss" in run(s, "ping -c 1 api.shop.example")


def test_fixing_resolv_conf():
    s = fresh("dead_dns")
    run(s, "sed -i 's/10.0.0.53/10.0.1.2/' /etc/resolv.conf")
    assert run(s, "getent hosts api.shop.example").startswith("10.0.2.15")
    s = fresh("dead_dns")
    run(s, 'echo "nameserver 10.0.1.2" > /etc/resolv.conf')
    assert run(s, "cat /etc/resolv.conf") == "nameserver 10.0.1.2"


def test_removing_the_stale_hosts_entry():
    s = fresh("stale_hosts")
    assert "10.0.2.40" not in run(s, "sed '/api.shop.example/d' /etc/hosts")
    run(s, "sed -i '/api.shop.example/d' /etc/hosts")
    assert '{"status":"ok"}' in run(s, "curl https://api.shop.example/healthz")
    assert "localhost" in run(s, "cat /etc/hosts")


def test_deleting_the_firewall_rule():
    s = fresh("firewall_blocks_db")
    listing = run(s, "iptables -L OUTPUT -n --line-numbers")
    assert "2    DROP" in listing and "dpt:5432" in listing
    assert "Index of deletion too big" in run(s, "iptables -D OUTPUT 9")
    run(s, "iptables -D OUTPUT 2")
    assert "succeeded" in run(s, "nc -zv db-1 5432")
    assert "-A OUTPUT" in run(s, "iptables -S") and "5432" not in run(s, "iptables -S")


def test_lowering_the_mtu():
    s = fresh("jumbo_mtu")
    assert "Invalid" in run(s, "ip link set dev eth0 mtu 99999")
    run(s, "ip link set dev eth0 mtu 1500")
    assert "1843200 bytes" in run(s, "curl https://packages.example.org/pool/main/big.deb")


def test_cutting_off_your_own_ssh():
    s = fresh()
    out = run(s, "iptables -F")
    assert "Broken pipe" in out and s["console"]
    s = fresh()
    assert "Broken pipe" in run(s, "ip link set eth0 down")
    assert "Network is unreachable" in run(s, "ping 10.0.1.20")
    run(s, "ip link set eth0 up")
    assert "0% packet loss" in run(s, "ping -c 1 db-1")


def test_appending_a_rule():
    s = fresh()
    run(s, "iptables -I OUTPUT -p tcp --dport 443 -d 10.0.2.0/24 -j REJECT")
    assert "Connection refused" in run(s, "nc -zv api.shop.example 443")
