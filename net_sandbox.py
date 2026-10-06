"""
Networking sandbox — you're SSH'd into app-1 (10.0.1.10) on a small modelled
network, and things that should connect don't. Every connection is worked
out layer by layer, the way a real packet's fate is: name resolution
(/etc/hosts first, then the DNS server in /etc/resolv.conf), the route
(local subnet or the default gateway), ARP for the next hop, the local
firewall, whether anything listens on the far end, and finally the MTU.
So each layer fails with its own real symptom: 'Temporary failure in name
resolution', 'No route to host', a timeout, 'Connection refused', or a
transfer that starts and then hangs.

Two of five problems are seeded:
  wrong_gateway      the default route points at 10.0.1.254, which doesn't exist
  dead_dns           resolv.conf names a DNS server that was decommissioned
  stale_hosts        /etc/hosts pins api.shop.example to the API's old address
  firewall_blocks_db a leftover OUTPUT rule drops traffic to PostgreSQL
  jumbo_mtu          eth0 was set to MTU 9000 on a 1500-byte network

Nothing here sends a real packet.
"""

import ipaddress
import random
import shlex

from sandbox_common import render_table, run_loop

PROBLEMS = ["wrong_gateway", "dead_dns", "stale_hosts", "firewall_blocks_db", "jumbo_mtu"]

REPORTS = {
    "wrong_gateway": "app-1 can't reach anything outside its own subnet: not the API, not the package mirror.",
    "dead_dns": "Everything on app-1 that uses a hostname fails, though some things work by IP.",
    "stale_hosts": "The app on app-1 times out calling api.shop.example, but the API team says it's healthy "
                   "and DNS is correct.",
    "firewall_blocks_db": "The app on app-1 can't reach its database since last night's hardening work.",
    "jumbo_mtu": "Health checks from app-1 pass, but big responses (the product catalogue, package downloads) "
                 "hang forever.",
}

MY_IP, MY_NET = "10.0.1.10", "10.0.1.0/24"
GOOD_GW, BAD_GW = "10.0.1.1", "10.0.1.254"
GOOD_DNS, DEAD_DNS = "10.0.1.2", "10.0.0.53"
API_IP, OLD_API_IP = "10.0.2.15", "10.0.2.40"
PATH_MTU = 1500

# Every machine that answers, and the TCP/UDP ports it serves.
HOSTS = {
    GOOD_GW: {"name": "gw-1", "ports": set()},
    GOOD_DNS: {"name": "dns-1", "ports": {53}},
    "10.0.1.20": {"name": "db-1", "ports": {5432, 22}},
    API_IP: {"name": "api-1", "ports": {443, 80, 22}},
    "203.0.113.80": {"name": "mirror", "ports": {443, 80}},
}
DNS_RECORDS = {
    "api.shop.example": API_IP,
    "db-1.shop.internal": "10.0.1.20",
    "dns-1.shop.internal": GOOD_DNS,
    "gw-1.shop.internal": GOOD_GW,
    "packages.example.org": "203.0.113.80",
}
MACS = {GOOD_GW: "52:54:00:1a:2b:01", GOOD_DNS: "52:54:00:1a:2b:02", "10.0.1.20": "52:54:00:1a:2b:20"}

HELP_TEXT = """Supported commands (a modelled network; no real packets are sent):
  ip addr | ip route | ip route get <ip> | ip link | ip neigh
  cat /etc/resolv.conf | /etc/hosts | /etc/nsswitch.conf
  getent hosts <name>   dig <name> [@server] [+short]   nslookup <name>
  ping [-c N] [-s SIZE] [-M do] <host>   traceroute <host>   tracepath <host>
  curl [-v] <url>   nc -zv [-w N] <host> <port>   pg_isready -h <host>
Changes:
  ip route replace|add|del default [via <ip>]   ip link set eth0 mtu <n> | up | down
  sed -i 's/old/new/' <file>   sed -i '/pattern/d' <file>   echo "text" >|>> <file>
  iptables -L [CHAIN] -n [--line-numbers] | -S | -D <CHAIN> <n> | -A/-I ... | -F | -P
  help | exit          (pipes work: ip route | grep default)"""


def _hosts_file(stale: bool) -> list:
    lines = ["127.0.0.1\tlocalhost", f"{MY_IP}\tapp-1.shop.internal app-1", "",
             "# The following lines are desirable for IPv6 capable hosts",
             "::1\tip6-localhost ip6-loopback"]
    if stale:
        lines += ["", "# temporary: pin the API during the March migration (dana)", f"{OLD_API_IP}\tapi.shop.example"]
    return lines


def generate_state(seed=None, problems=None) -> dict:
    """Random 2 problems by default; mystery incidents pass an explicit list."""
    rng = random.Random(seed)
    problems = list(problems) if problems is not None else rng.sample(PROBLEMS, k=2)
    firewall = {
        "INPUT": [{"target": "ACCEPT", "proto": "tcp", "dport": 22, "dest": "0.0.0.0/0", "comment": "ssh"},
                  {"target": "ACCEPT", "proto": "tcp", "dport": 8080, "dest": "0.0.0.0/0", "comment": "app"}],
        "OUTPUT": [],
    }
    if "firewall_blocks_db" in problems:
        firewall["OUTPUT"] = [
            {"target": "ACCEPT", "proto": "tcp", "dport": 443, "dest": "0.0.0.0/0", "comment": "https out"},
            {"target": "DROP", "proto": "tcp", "dport": 5432, "dest": "10.0.1.0/24",
             "comment": "CIS 3.5 test - remove after review"},
        ]
    state = {
        "seed": seed,
        "problems": problems,
        "link": {"name": "eth0", "up": True, "mtu": 9000 if "jumbo_mtu" in problems else 1500,
                 "mac": "52:54:00:1a:2b:10", "addr": f"{MY_IP}/24"},
        "default_gw": BAD_GW if "wrong_gateway" in problems else GOOD_GW,
        "files": {
            "/etc/resolv.conf": ["# Generated by the provisioning script; edit with care",
                                 f"nameserver {DEAD_DNS if 'dead_dns' in problems else GOOD_DNS}",
                                 "search shop.internal"],
            "/etc/hosts": _hosts_file("stale_hosts" in problems),
            "/etc/nsswitch.conf": ["passwd:         files", "group:          files",
                                   "hosts:          files dns", "networks:       files"],
        },
        "firewall": firewall,
    }
    state["policy"] = {"INPUT": "DROP", "FORWARD": "DROP", "OUTPUT": "ACCEPT"}
    state["console"] = False
    return state


# ------------------------------------------------------------ the network

def _nameserver(state: dict):
    for line in state["files"]["/etc/resolv.conf"]:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            return parts[1]
    return None


def _hosts_lookup(state: dict, name: str):
    for line in state["files"]["/etc/hosts"]:
        parts = line.split("#", 1)[0].split()
        if len(parts) >= 2 and name in parts[1:]:
            return parts[0]
    return None


def _is_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def _local(ip: str) -> bool:
    return ipaddress.ip_address(ip) in ipaddress.ip_network(MY_NET)


def next_hop(state: dict, ip: str):
    """(hop, error): the address we must ARP for, or why there's none."""
    if not state["link"]["up"]:
        return None, "Network is unreachable"
    if _local(ip):
        return ip, None
    if state["default_gw"] is None:
        return None, "Network is unreachable"
    return state["default_gw"], None


def arp_ok(hop: str) -> bool:
    return hop in HOSTS


def dns_query(state: dict, name: str, server=None):
    """(ip or None, error or None) as a DNS client sees it, ignoring /etc/hosts."""
    server = server or _nameserver(state)
    if server is None:
        return None, "no servers could be reached"
    hop, err = next_hop(state, server)
    if err or not arp_ok(hop) or server not in HOSTS or 53 not in HOSTS[server]["ports"]:
        return None, "timed out"
    fqdn = name if name in DNS_RECORDS else f"{name}.shop.internal"
    if fqdn in DNS_RECORDS:
        return DNS_RECORDS[fqdn], None
    return None, "NXDOMAIN"


def resolve(state: dict, name: str):
    """(ip, error) the way most programs resolve: nsswitch 'files dns'."""
    if _is_ip(name):
        return name, None
    pinned = _hosts_lookup(state, name)
    if pinned:
        return pinned, None
    ip, err = dns_query(state, name)
    if ip:
        return ip, None
    return None, "Temporary failure in name resolution" if err == "timed out" else "Name or service not known"


def _firewall_verdict(state: dict, ip: str, port: int) -> str:
    for rule in state["firewall"]["OUTPUT"]:
        if rule["proto"] == "tcp" and rule["dport"] == port and \
                ipaddress.ip_address(ip) in ipaddress.ip_network(rule["dest"]):
            return rule["target"]
    return "ACCEPT"


def connect(state: dict, target: str, port: int, large=False):
    """(outcome, ip). Outcomes, each a different layer:
    dns, unreachable (no route at all), no_route (ARP for the next hop
    failed), timeout (dropped somewhere), refused (nothing listening, or a
    REJECT), stall (connected, but big packets vanish), ok."""
    ip, err = resolve(state, target)
    if err:
        return "dns", None
    hop, err = next_hop(state, ip)
    if err:
        return "unreachable", ip
    if not arp_ok(hop):
        return "no_route", ip
    if ip not in HOSTS:
        return "timeout", ip
    verdict = _firewall_verdict(state, ip, port)
    if verdict == "DROP":
        return "timeout", ip
    if verdict == "REJECT" or port not in HOSTS[ip]["ports"]:
        return "refused", ip
    if large and state["link"]["mtu"] > PATH_MTU:
        return "stall", ip
    return "ok", ip


# ------------------------------------------------------------ connectivity

SMALL_PATHS = {"", "/", "/healthz", "/health", "/status"}


def _ping(state: dict, args: list) -> str:
    count, size, df, target, i = 4, 56, False, None, 0
    while i < len(args):
        a = args[i]
        if a == "-c" and i + 1 < len(args):
            count, i = int(args[i + 1]), i + 2
            continue
        if a == "-s" and i + 1 < len(args):
            size, i = int(args[i + 1]), i + 2
            continue
        if a == "-M" and i + 1 < len(args):
            df, i = args[i + 1] == "do", i + 2
            continue
        if not a.startswith("-"):
            target = a
        i += 1
    if not target:
        return "ping: usage error: Destination address required"
    ip, err = resolve(state, target)
    if err:
        return f"ping: {target}: {err}"
    hop, err = next_hop(state, ip)
    if err:
        return f"ping: connect: {err}"
    packet = size + 28
    head = f"PING {target} ({ip}) {size}({packet}) bytes of data."
    tail = f"\n--- {target} ping statistics ---\n{count} packets transmitted, "
    if df and packet > state["link"]["mtu"]:
        return f"{head}\nping: local error: message too long, mtu={state['link']['mtu']}" \
               f"{tail}0 received, +{count} errors, 100% packet loss, time {count - 1}000ms"
    if not arp_ok(hop):
        lines = [f"From {MY_IP} icmp_seq={n} Destination Host Unreachable" for n in range(1, count + 1)]
        return "\n".join([head, *lines]) + f"{tail}0 received, +{count} errors, 100% packet loss, " \
                                           f"time {count - 1}000ms"
    lost = ip not in HOSTS or (packet > PATH_MTU and packet <= state["link"]["mtu"])
    if lost:
        return f"{head}{tail}0 received, 100% packet loss, time {count - 1}000ms"
    ttl = 64 if _local(ip) else (63 if ip.startswith("10.") else 54)
    ms = 0.4 if _local(ip) else (0.7 if ip.startswith("10.") else 11.8)
    lines = [f"{size + 8} bytes from {ip}: icmp_seq={n} ttl={ttl} time={ms + n * 0.02:.2f} ms"
             for n in range(1, count + 1)]
    return "\n".join([head, *lines]) + f"{tail}{count} received, 0% packet loss, time {count - 1}000ms\n" \
                                       f"rtt min/avg/max/mdev = {ms:.3f}/{ms + 0.05:.3f}/{ms + 0.1:.3f}/0.031 ms"


def _parse_url(url: str):
    scheme = "https" if url.startswith("https://") else "http"
    rest = url.split("://", 1)[-1]
    hostport, _, path = rest.partition("/")
    host, _, port = hostport.partition(":")
    return host, int(port) if port else (443 if scheme == "https" else 80), "/" + path if path else ""


def _curl(state: dict, args: list) -> str:
    urls = [a for a in args if "." in a and not a.startswith("-") and a not in ("/dev/null",)]
    if not urls:
        return "curl: try 'curl --help' or 'curl --manual' for more information"
    host, port, path = _parse_url(urls[0])
    verbose = "-v" in args or "--verbose" in args
    outcome, ip = connect(state, host, port, large=path not in SMALL_PATHS)
    pre = []
    if verbose and ip:
        pre.append(f"*   Trying {ip}:{port}...")
    if outcome == "dns":
        return f"curl: (6) Could not resolve host: {host}"
    if outcome == "unreachable":
        return "\n".join(pre + [f"curl: (7) Failed to connect to {host} port {port} after 0 ms: "
                                f"Couldn't connect to server"])
    if outcome == "no_route":
        return "\n".join(pre + [f"curl: (7) Failed to connect to {host} port {port} after 3071 ms: No route to host"])
    if outcome == "timeout":
        return "\n".join(pre + [f"curl: (28) Failed to connect to {host} port {port} after 10002 ms: "
                                "Timeout was reached"])
    if outcome == "refused":
        return "\n".join(pre + [f"curl: (7) Failed to connect to {host} port {port} after 1 ms: Connection refused"])
    if verbose:
        pre.append(f"* Connected to {host} ({ip}) port {port}")
    if outcome == "stall":
        return "\n".join(pre + ["curl: (28) Operation timed out after 30001 milliseconds with 2896 out of "
                                "1843200 bytes received"])
    if path in SMALL_PATHS:
        body = '{"status":"ok"}'
    else:
        body = "(1843200 bytes received: 1.8 MB, complete)"
    return "\n".join(pre + ([f"< HTTP/1.1 200 OK"] if verbose else []) + [body])


def _nc(state: dict, args: list) -> str:
    words = [a for a in args if not a.startswith("-")]
    if "-w" in args:
        w = args.index("-w")
        if w + 1 < len(args) and args[w + 1] in words:
            words.remove(args[w + 1])
    if len(words) < 2 or not words[1].isdigit():
        return "usage: nc -zv <host> <port>"
    host, port = words[0], int(words[1])
    outcome, ip = connect(state, host, port)
    if outcome == "dns":
        return f'nc: getaddrinfo for host "{host}" port {port}: Temporary failure in name resolution'
    reasons = {"unreachable": "Network is unreachable", "no_route": "No route to host",
               "timeout": "Connection timed out", "refused": "Connection refused"}
    if outcome in reasons:
        return f"nc: connect to {host} ({ip}) port {port} (tcp) failed: {reasons[outcome]}"
    return f"Connection to {host} ({ip}) {port} port [tcp/*] succeeded!"


def _pg_isready(state: dict, args: list) -> str:
    host = args[args.index("-h") + 1] if "-h" in args and args.index("-h") + 1 < len(args) else "localhost"
    port = int(args[args.index("-p") + 1]) if "-p" in args and args.index("-p") + 1 < len(args) else 5432
    if host == "localhost":
        return f"{host}:{port} - no response"
    outcome, _ = connect(state, host, port)
    if outcome == "dns":
        return f'pg_isready: could not translate host name "{host}" to address'
    return f"{host}:{port} - " + ("accepting connections" if outcome == "ok" else "no response")


def _trace(state: dict, args: list, tracepath=False) -> str:
    targets = [a for a in args if not a.startswith("-")]
    if not targets:
        return "usage: traceroute <host>"
    target = targets[0]
    ip, err = resolve(state, target)
    if err:
        return f"{target}: {err}"
    lines = [f"traceroute to {target} ({ip}), 30 hops max, 60 byte packets"] if not tracepath else \
        [f" 1?: [LOCALHOST]                      pmtu {state['link']['mtu']}"]
    hop, err = next_hop(state, ip)
    if err:
        return f"connect: {err}"
    if not arp_ok(hop):
        return "\n".join(lines + [f" 1  app-1 ({MY_IP})  3006.193 ms !H  3006.155 ms !H  3006.140 ms !H"])
    n = 1
    if hop != ip:
        lines.append(f" {n}  gw-1 ({hop})  0.312 ms  0.288 ms  0.270 ms")
        n += 1
    if ip in HOSTS:
        lines.append(f" {n}  {HOSTS[ip]['name']} ({ip})  0.701 ms  0.689 ms  0.655 ms")
    else:
        lines += [f" {k}  * * *" for k in range(n, n + 4)]
    return "\n".join(lines)


# -------------------------------------------------------------------- views

def _ip(state: dict, args: list) -> str:
    obj = args[0] if args else ""
    link = state["link"]
    if obj in ("a", "addr", "address"):
        flags = "BROADCAST,MULTICAST,UP,LOWER_UP" if link["up"] else "BROADCAST,MULTICAST"
        oper = "UP" if link["up"] else "DOWN"
        return "\n".join([
            "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000",
            "    inet 127.0.0.1/8 scope host lo",
            f"2: eth0: <{flags}> mtu {link['mtu']} qdisc fq_codel state {oper} group default qlen 1000",
            f"    link/ether {link['mac']} brd ff:ff:ff:ff:ff:ff",
            f"    inet {link['addr']} brd 10.0.1.255 scope global eth0"])
    if obj in ("l", "link"):
        oper = "UP" if link["up"] else "DOWN"
        return "\n".join([
            "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT",
            f"2: eth0: <BROADCAST,MULTICAST{',UP,LOWER_UP' if link['up'] else ''}> mtu {link['mtu']} "
            f"qdisc fq_codel state {oper} mode DEFAULT",
            f"    link/ether {link['mac']} brd ff:ff:ff:ff:ff:ff"])
    if obj in ("r", "route", "ro"):
        if len(args) >= 3 and args[1] == "get":
            target = args[2]
            if not _is_ip(target):
                return f'Error: any valid prefix is expected rather than "{target}".'
            hop, err = next_hop(state, target)
            if err:
                return f"RTNETLINK answers: {err}"
            via = "" if hop == target else f" via {hop}"
            return f"{target}{via} dev eth0 src {MY_IP} uid 0\n    cache"
        lines = []
        if state["default_gw"] and state["link"]["up"]:
            lines.append(f"default via {state['default_gw']} dev eth0 proto static")
        if state["link"]["up"]:
            lines.append(f"{MY_NET} dev eth0 proto kernel scope link src {MY_IP}")
        return "\n".join(lines)
    if obj in ("n", "neigh", "neighbor", "neighbour"):
        rows = []
        for hop in sorted({state["default_gw"], GOOD_DNS, "10.0.1.20"} - {None}):
            if arp_ok(hop):
                rows.append(f"{hop} dev eth0 lladdr {MACS.get(hop, '52:54:00:1a:2b:99')} REACHABLE")
            else:
                rows.append(f"{hop} dev eth0 FAILED")
        return "\n".join(rows)
    return f"ip {obj}: not simulated in the sandbox. Type 'help' for supported commands."


def _getent(state: dict, args: list) -> str:
    if len(args) < 2 or args[0] != "hosts":
        return "getent: the sandbox supports: getent hosts <name>"
    ip, _ = resolve(state, args[1])
    return f"{ip:<15} {args[1]}" if ip else ""


def _dig(state: dict, args: list) -> str:
    server = next((a[1:] for a in args if a.startswith("@")), None)
    short = "+short" in args
    names = [a for a in args if not a.startswith(("@", "+", "-"))]
    if not names:
        return "dig: name required"
    name = names[0]
    used = server or _nameserver(state)
    ip, err = dns_query(state, name, server)
    if err == "timed out":
        return f";; communications error to {used}#53: timed out\n" * 2 + \
            f";; no servers could be reached"
    if short:
        return ip or ""
    status = "NOERROR" if ip else "NXDOMAIN"
    lines = [f"; <<>> DiG 9.18.28 <<>> {name}", ";; global options: +cmd", ";; Got answer:",
             f";; ->>HEADER<<- opcode: QUERY, status: {status}, id: 41204", "",
             ";; QUESTION SECTION:", f";{name}.\t\t\tIN\tA", ""]
    if ip:
        lines += [";; ANSWER SECTION:", f"{name}.\t\t300\tIN\tA\t{ip}", ""]
    lines += [";; Query time: 1 msec", f";; SERVER: {used}#53({used}) (UDP)"]
    return "\n".join(lines)


def _nslookup(state: dict, args: list) -> str:
    if not args:
        return "nslookup: name required"
    used = _nameserver(state)
    ip, err = dns_query(state, args[0])
    if err == "timed out":
        return f";; communications error to {used}#53: timed out\n;; no servers could be reached"
    head = f"Server:\t\t{used}\nAddress:\t{used}#53\n\n"
    if not ip:
        return head + f"** server can't find {args[0]}: NXDOMAIN"
    return head + f"Name:\t{args[0]}\nAddress: {ip}"


# --------------------------------------------------------------------- fixes

def ssh_alive(state: dict) -> bool:
    """You're connected over eth0 on port 22: both must keep working."""
    if not state["link"]["up"]:
        return False
    for rule in state["firewall"]["INPUT"]:
        if rule["proto"] == "tcp" and rule["dport"] == 22:
            return rule["target"] == "ACCEPT"
    return state["policy"]["INPUT"] == "ACCEPT"


def _ip_change(state: dict, obj: str, args: list):
    """None if this isn't a change command; otherwise the result."""
    if obj in ("r", "route", "ro") and args and args[0] in ("add", "replace", "del", "delete", "change"):
        verb, rest = args[0], args[1:]
        if not rest or rest[0] != "default":
            return "ip route: the sandbox only manages the default route (ip route replace default via <ip>)."
        if verb in ("del", "delete"):
            if state["default_gw"] is None:
                return "RTNETLINK answers: No such process"
            state["default_gw"] = None
            return ""
        if "via" not in rest or rest.index("via") + 1 >= len(rest):
            return 'Error: either "to" is duplicate, or "via" is a garbage.'
        gw = rest[rest.index("via") + 1]
        if not _is_ip(gw) or not _local(gw):
            return "Error: Nexthop has invalid gateway."
        if verb == "add" and state["default_gw"] is not None:
            return "RTNETLINK answers: File exists"
        state["default_gw"] = gw
        return ""
    if obj in ("l", "link") and args and args[0] == "set":
        rest = [a for a in args[1:] if a != "dev"]
        if not rest or rest[0] != "eth0":
            return 'Cannot find device "' + (rest[0] if rest else "") + '"'
        if "mtu" in rest:
            value = rest[rest.index("mtu") + 1] if rest.index("mtu") + 1 < len(rest) else ""
            if not value.isdigit() or not 68 <= int(value) <= 9000:
                return f'Error: argument "{value}" is wrong: Invalid "mtu" value'
            state["link"]["mtu"] = int(value)
        if "down" in rest:
            state["link"]["up"] = False
        if "up" in rest:
            state["link"]["up"] = True
        return ""
    return None


def _sed(state: dict, args: list) -> str:
    import re
    in_place = "-i" in args
    rest = [a for a in args if a != "-i"]
    if len(rest) != 2 or rest[1] not in state["files"]:
        return "sed: the sandbox supports: sed [-i] 's/old/new/[g]' <file> or sed [-i] '/pattern/d' <file>"
    script, path = rest
    lines = state["files"][path]
    try:
        if script.startswith("/") and script.endswith("/d"):
            rx = re.compile(script[1:-2])
            new = [l for l in lines if not rx.search(l)]
        elif script.startswith("s/") and script.count("/") >= 3:
            _, old, repl, opts = script.split("/", 3)
            rx = re.compile(old)
            new = [rx.sub(repl, l, count=0 if "g" in opts else 1) for l in lines]
        else:
            return "sed: the sandbox supports 's/old/new/[g]' and '/pattern/d'"
    except re.error as e:
        return f"sed: -e expression #1: {e}"
    if not in_place:
        return "\n".join(new)
    state["files"][path] = new
    return ""


def _echo(state: dict, args: list) -> str:
    for op in (">>", ">"):
        if op in args:
            i = args.index(op)
            text, target = " ".join(args[:i]), (args[i + 1] if i + 1 < len(args) else "")
            if target not in state["files"]:
                return f"bash: {target}: Permission denied" if target else "bash: syntax error"
            if op == ">":
                state["files"][target] = [text]
            else:
                state["files"][target].append(text)
            return ""
    return " ".join(args)


def _rule_line(n, rule, numbered):
    match = f"tcp dpt:{rule['dport']}"
    comment = f" /* {rule['comment']} */" if rule.get("comment") else ""
    num = f"{n:<5}" if numbered else ""
    return f"{num}{rule['target']:<10} tcp  --  0.0.0.0/0            {rule['dest']:<20} {match}{comment}"


def _iptables(state: dict, args: list) -> str:
    fw, policy = state["firewall"], state["policy"]
    chains = ["INPUT", "FORWARD", "OUTPUT"]
    if "-L" in args or "--list" in args:
        flag = "-L" if "-L" in args else "--list"
        i = args.index(flag)
        only = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("-") else None
        numbered = "--line-numbers" in args
        out = []
        for chain in ([only] if only else chains):
            if chain not in policy:
                return f"iptables: No chain/target/match by that name."
            out.append(f"Chain {chain} (policy {policy[chain]})")
            out.append(("num  " if numbered else "") + "target     prot opt source               destination")
            out += [_rule_line(n, r, numbered) for n, r in enumerate(fw.get(chain, []), start=1)]
            out.append("")
        return "\n".join(out).rstrip()
    if "-S" in args:
        out = [f"-P {c} {policy[c]}" for c in chains]
        for c in ("INPUT", "OUTPUT"):
            for r in fw[c]:
                comment = f' -m comment --comment "{r["comment"]}"' if r.get("comment") else ""
                out.append(f"-A {c} -d {r['dest']} -p tcp -m tcp --dport {r['dport']}{comment} -j {r['target']}")
        return "\n".join(out)
    if "-D" in args:
        i = args.index("-D")
        chain = args[i + 1] if i + 1 < len(args) else ""
        num = args[i + 2] if i + 2 < len(args) else ""
        if chain not in fw:
            return "iptables: No chain/target/match by that name."
        if not num.isdigit() or not 1 <= int(num) <= len(fw[chain]):
            return "iptables: Index of deletion too big." if num.isdigit() else \
                "iptables: the sandbox deletes by number: iptables -D <CHAIN> <n> (see --line-numbers)"
        fw[chain].pop(int(num) - 1)
        return ""
    if "-F" in args or "--flush" in args:
        i = args.index("-F" if "-F" in args else "--flush")
        chain = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("-") else None
        for c in ([chain] if chain else ["INPUT", "OUTPUT"]):
            if c in fw:
                fw[c] = []
        return ""
    if "-P" in args:
        i = args.index("-P")
        chain, target = (args[i + 1:i + 3] + ["", ""])[:2]
        if chain not in policy or target not in ("ACCEPT", "DROP"):
            return "iptables: Bad policy name."
        policy[chain] = target
        return ""
    for flag in ("-A", "-I"):
        if flag in args:
            i = args.index(flag)
            chain = args[i + 1] if i + 1 < len(args) else ""
            if chain not in fw or "--dport" not in args or "-j" not in args:
                return f"iptables: the sandbox supports: iptables {flag} <CHAIN> -p tcp --dport <port> [-d <cidr>] -j <TARGET>"
            rule = {"target": args[args.index("-j") + 1], "proto": "tcp", "dport": int(args[args.index("--dport") + 1]),
                    "dest": args[args.index("-d") + 1] if "-d" in args else "0.0.0.0/0", "comment": ""}
            if flag == "-I":
                fw[chain].insert(0, rule)
            else:
                fw[chain].append(rule)
            return ""
    return "iptables: the sandbox supports -L, -S, -D, -A, -I, -F, and -P."


def handle_command(state: dict, raw: str) -> str:
    alive_before = ssh_alive(state)
    out = _dispatch(state, raw)
    if alive_before and not ssh_alive(state):
        state["console"] = True
        return (out + "\n" if out else "") + ("client_loop: send disconnect: Broken pipe\n"
                                              "(Your SSH session to app-1 just died: you cut off your own access. "
                                              "You're now on the cloud provider's serial console, which is slow and "
                                              "audited, to put it back.)")
    return out


def _dispatch(state: dict, raw: str) -> str:
    try:
        tokens = shlex.split(raw)
    except ValueError as e:
        return f"parse error: {e}"
    if not tokens:
        return ""
    cmd, args = tokens[0], tokens[1:]
    if cmd == "sudo" and args:
        cmd, args = args[0], args[1:]
    if cmd in ("help", "?"):
        return HELP_TEXT
    if cmd == "ip":
        changed = _ip_change(state, args[0] if args else "", args[1:])
        return changed if changed is not None else _ip(state, args)
    if cmd == "sed":
        return _sed(state, args)
    if cmd == "echo":
        return _echo(state, args)
    if cmd == "iptables":
        return _iptables(state, args)
    if cmd == "cat":
        missing = [f for f in args if f not in state["files"]]
        if missing:
            return f"cat: {missing[0]}: No such file or directory"
        return "\n".join("\n".join(state["files"][f]) for f in args)
    if cmd == "getent":
        return _getent(state, args)
    if cmd == "dig":
        return _dig(state, args)
    if cmd == "nslookup":
        return _nslookup(state, args)
    if cmd == "ping":
        return _ping(state, args)
    if cmd == "curl":
        return _curl(state, args)
    if cmd in ("nc", "ncat", "netcat"):
        return _nc(state, args)
    if cmd == "pg_isready":
        return _pg_isready(state, args)
    if cmd in ("traceroute", "tracepath", "mtr"):
        return _trace(state, args, tracepath=cmd == "tracepath")
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


def describe_state(state: dict) -> list:
    return ["You're SSH'd into app-1 (10.0.1.10), an application server. Reported:",
            *[f"  - {REPORTS[p]}" for p in state["problems"]],
            "Find each cause and fix it from app-1. You're connected over eth0: careful with it."]


def run_sandbox() -> None:
    run_loop("net", "network", generate_state, handle_command, describe_state)
