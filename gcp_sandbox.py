"""
Google Cloud sandbox — a fake project with one global VPC, explored and
fixed with real `gcloud ...` commands.

Layout (project shop-prod-217733, network prod-vpc, region europe-west1):
  web-1     public-ew1   external IP, network tag 'web', serves 443
  db-1      private-ew1  no external IP, tag 'db', serves 5432 to tag 'web'
  worker-1  private-ew1  no external IP, tag 'worker', needs outbound 443

Traffic is evaluated the way GCP does it:
  ingress:  a firewall rule applies to a VM only if the rule has no target
            tags or the VM carries one of them; lowest priority number
            wins, deny beats allow at equal priority, and the implied
            rule denies all other ingress
  egress:   a VM with an external IP goes straight out; one without needs
            Cloud NAT (a Cloud Router + NAT config) in ITS region
  shell:    `gcloud compute ssh --tunnel-through-iap` needs a rule allowing
            tcp:22 from Google's IAP range 35.235.240.0/20

Random problems (two per project in sandbox mode):
  wrong_tag             web-1 carries 'http-server' instead of 'web'
  no_nat                no Cloud Router/NAT in europe-west1
  iap_rule_missing      the allow-iap-ssh rule was deleted by a cleanup
  deny_rule_priority    a deny rule at priority 500 shadows allow-https-web
  db_rule_wrong_source  allow-db-from-web has source tag 'app', not 'web'
  no_external_ip        web-1 has no external IP

Reactive: add-tags/remove-tags, firewall-rules create/update/delete,
routers create + nats create, and add-access-config change the state.
"""

import ipaddress
import random

from engine import normalize
from sandbox_common import parse_flags, render_table, run_loop

PROBLEMS = ["wrong_tag", "no_nat", "iap_rule_missing", "deny_rule_priority",
            "db_rule_wrong_source", "no_external_ip"]

LAPTOP_IP = "203.0.113.50"
INTERNET_IP = "93.184.216.34"
IAP_RANGE = "35.235.240.0/20"
IAP_IP = "35.235.240.10"
PROJECT = "shop-prod-217733"
NETWORK = "prod-vpc"
REGION = "europe-west1"
ZONE = "europe-west1-b"
REPO_HOST = "deb.debian.org"

BOOLEANS = {"tunnel-through-iap", "troubleshoot", "auto-allocate-nat-external-ips",
            "nat-all-subnet-ip-ranges", "enabled", "quiet"}

HELP_TEXT = """Supported commands (--flag=value and --flag value both work; output is always a table):
  gcloud config list
  gcloud compute instances list | describe <vm> --zone <zone>
  gcloud compute instances add-tags | remove-tags <vm> --zone <zone> --tags <tag>
  gcloud compute instances add-access-config <vm> --zone <zone>
  gcloud compute firewall-rules list | describe <rule>
  gcloud compute firewall-rules create <rule> --network prod-vpc --allow tcp:<port> | --action deny --rules tcp:<port>
        --source-ranges <cidr> | --source-tags <tag>  [--target-tags <tag>] [--priority <n>]
  gcloud compute firewall-rules update <rule> [--target-tags ..] [--source-tags ..] [--source-ranges ..] [--priority ..]
  gcloud compute firewall-rules delete <rule>
  gcloud compute networks subnets list
  gcloud compute routers list | create <router> --network prod-vpc --region <region>
  gcloud compute routers nats create <nat> --router <router> --region <region>
        --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges
  gcloud compute routers nats list --router <router> --region <region>
  gcloud compute ssh <vm> --zone <zone> --tunnel-through-iap [--troubleshoot] [--command '<cmd>']
From your laptop:  curl [-m N] <url>   nc -zv <ip> <port>   curl ifconfig.me
Inside an SSH session:  curl <url>   nc -zv <host> <port>   sudo apt update   hostname   exit
  help | exit"""


# ------------------------------------------------------------------ state

def _fw(name, priority, action, ports, source_ranges=None, source_tags=None, target_tags=None):
    return {"name": name, "priority": priority, "action": action, "ports": ports,
            "source_ranges": source_ranges or [], "source_tags": source_tags or [],
            "target_tags": target_tags or []}


def generate_state(seed=None, problems=None) -> dict:
    rng = random.Random(seed)
    if problems is None:
        problems = rng.sample(PROBLEMS, 2)

    def ext_ip():
        return f"34.{rng.randint(70, 140)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"

    rules = [
        _fw("allow-https-web", 1000, "allow", ["443"], source_ranges=["0.0.0.0/0"], target_tags=["web"]),
        _fw("allow-db-from-web", 1000, "allow", ["5432"],
            source_tags=["app" if "db_rule_wrong_source" in problems else "web"], target_tags=["db"]),
    ]
    if "iap_rule_missing" not in problems:
        rules.append(_fw("allow-iap-ssh", 1000, "allow", ["22"], source_ranges=[IAP_RANGE]))
    if "deny_rule_priority" in problems:
        rules.append(_fw("deny-legacy-ports", 500, "deny", ["443", "8443"], source_ranges=["0.0.0.0/0"], target_tags=["web"]))

    web_ip, spare_ip = ext_ip(), ext_ip()
    routers = [] if "no_nat" in problems else [{"name": "router-ew1", "region": REGION, "nats": ["nat-ew1"]}]
    return {
        "project": PROJECT,
        "problems": problems,
        "firewall_rules": rules,
        "routers": routers,
        "subnets": [
            {"name": "public-ew1", "region": REGION, "range": "10.10.0.0/20"},
            {"name": "private-ew1", "region": REGION, "range": "10.20.0.0/20"},
        ],
        "instances": [
            {"name": "web-1", "zone": ZONE, "subnet": "public-ew1", "internal_ip": f"10.10.0.{rng.randint(2, 250)}",
             "external_ip": None if "no_external_ip" in problems else web_ip, "spare_ip": web_ip if "no_external_ip" in problems else spare_ip,
             "tags": ["http-server"] if "wrong_tag" in problems else ["web"], "listens": [443, 22]},
            {"name": "db-1", "zone": ZONE, "subnet": "private-ew1", "internal_ip": f"10.20.0.{rng.randint(2, 120)}",
             "external_ip": None, "tags": ["db"], "listens": [5432, 22]},
            {"name": "worker-1", "zone": ZONE, "subnet": "private-ew1", "internal_ip": f"10.20.0.{rng.randint(130, 250)}",
             "external_ip": None, "tags": ["worker"], "listens": [22]},
        ],
        "nat_ip": ext_ip(),
        "session": None,
    }


# ----------------------------------------------------------------- lookups

def _vm(state, ref):
    for vm in state["instances"]:
        if ref in (vm["name"], vm["internal_ip"], vm["external_ip"]):
            return vm
    return None


def _rule(state, name):
    return next((r for r in state["firewall_rules"] if r["name"] == name), None)


def _in(ip, cidr) -> bool:
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False


def _ingress(state, vm, port: int, src_ip: str, src_vm=None):
    """(allowed, rule name). Only rules that target this VM are considered."""
    matches = []
    for r in state["firewall_rules"]:
        if r["target_tags"] and not set(r["target_tags"]) & set(vm["tags"]):
            continue
        if str(port) not in r["ports"] and "all" not in r["ports"]:
            continue
        by_range = any(_in(src_ip, c) for c in r["source_ranges"])
        by_tag = src_vm is not None and bool(set(r["source_tags"]) & set(src_vm["tags"]))
        if by_range or by_tag:
            matches.append(r)
    if not matches:
        return False, "implied-deny-ingress"
    best = min(matches, key=lambda r: (r["priority"], r["action"] != "deny"))
    return best["action"] == "allow", best["name"]


def _has_nat(state, region: str) -> bool:
    return any(r["region"] == region and r["nats"] for r in state["routers"])


def reachability(state, source: str, target: str, port: int):
    """None when a TCP connection works, else a short hidden reason.
    source/target: 'internet', 'iap', or a VM name."""
    if source in ("internet", "iap"):
        vm = _vm(state, target)
        if source == "internet" and not vm["external_ip"]:
            return "no external ip"
        ok, rule = _ingress(state, vm, port, LAPTOP_IP if source == "internet" else IAP_IP)
        if not ok:
            return f"firewall: {rule}"
        return None if port in vm["listens"] else "refused"
    src = _vm(state, source)
    if target == "internet":
        if src["external_ip"] or _has_nat(state, REGION):
            return None
        return "no external ip and no cloud nat"
    dst = _vm(state, target)
    ok, rule = _ingress(state, dst, port, src["internal_ip"], src)
    if not ok:
        return f"firewall: {rule}"
    return None if port in dst["listens"] else "refused"


# ------------------------------------------------------------ connectivity

def _timeout(host, port):
    return f"curl: (28) Failed to connect to {host} port {port} after 5002 ms: Timeout was reached"


def _parse_target(url: str):
    scheme = "https"
    if "://" in url:
        scheme, url = url.split("://", 1)
    hostport = url.split("/", 1)[0]
    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
        return host, int(port) if port.isdigit() else 443
    return hostport, 443 if scheme == "https" else 80


def _connect(state, source_vm, host: str, port: int):
    target = _vm(state, host)
    if source_vm is None:
        if target is None:
            return None
        if host != target["external_ip"]:
            return "unroutable"
        return reachability(state, "internet", target["name"], port)
    if target is None:
        return reachability(state, source_vm["name"], "internet", port)
    if target is source_vm:
        return None
    return reachability(state, source_vm["name"], target["name"], port)


def cmd_curl(state, source_vm, args) -> str:
    urls = [a for a in args if not a.startswith("-") and not a.isdigit()]
    if not urls:
        return "curl: no URL specified"
    host, port = _parse_target(urls[0])
    if not host:
        return "curl: (3) URL rejected: No host part in the URL"
    if host == "ifconfig.me":
        if source_vm is None:
            return LAPTOP_IP
        if reachability(state, source_vm["name"], "internet", 443):
            return _timeout(host, port)
        return source_vm["external_ip"] or state["nat_ip"]
    reason = _connect(state, source_vm, host, port)
    if reason is None:
        target = _vm(state, host)
        if target and target["name"] == "web-1":
            return "<!doctype html><title>Shop</title><h1>Welcome to the shop</h1>"
        return "<!doctype html><html>... (200 OK)"
    if reason == "refused":
        return f"curl: (7) Failed to connect to {host} port {port}: Connection refused"
    return _timeout(host, port)


def cmd_nc(state, source_vm, args) -> str:
    positional = [a for a in args if not a.startswith("-")]
    if len(positional) < 2 or not positional[1].isdigit():
        return "usage: nc -zv <host> <port>"
    host, port = positional[0], int(positional[1])
    reason = _connect(state, source_vm, host, port)
    if reason is None:
        return f"Connection to {host} {port} port [tcp/*] succeeded!"
    verdict = "Connection refused" if reason == "refused" else "Connection timed out"
    return f"nc: connect to {host} port {port} (tcp) failed: {verdict}"


def run_on_vm(state, vm, tokens) -> str:
    """One shell command inside a VM (an SSH session or --command)."""
    if tokens and tokens[0] == "sudo":
        tokens = tokens[1:]
    if not tokens:
        return ""
    cmd, args = tokens[0], tokens[1:]
    if cmd == "curl":
        return cmd_curl(state, vm, args)
    if cmd in ("nc", "ncat"):
        return cmd_nc(state, vm, args)
    if cmd == "hostname":
        return vm["name"]
    if cmd in ("apt", "apt-get") and args[:1] == ["update"]:
        if reachability(state, vm["name"], "internet", 443) is None:
            return (f"Hit:1 https://{REPO_HOST}/debian bookworm InRelease\n"
                    "Get:2 https://deb.debian.org/debian-security bookworm-security InRelease [48.0 kB]\n"
                    "Reading package lists... Done")
        return (f"Err:1 https://{REPO_HOST}/debian bookworm InRelease\n"
                f"  Could not connect to {REPO_HOST}:443 (151.101.2.132), connection timed out\n"
                "W: Some index files failed to download. They have been ignored, or old ones used instead.")
    return f"{cmd}: not simulated inside the VM (try curl, nc -zv, sudo apt update, hostname, exit)"


# ---------------------------------------------------------------- commands

def _gerr(message: str) -> str:
    return f"ERROR: (gcloud) {message}"


def cmd_instances_list(state) -> str:
    rows = [[vm["name"], vm["zone"], "e2-medium", vm["internal_ip"], vm["external_ip"] or "", "RUNNING"]
            for vm in state["instances"]]
    return render_table(["NAME", "ZONE", "MACHINE_TYPE", "INTERNAL_IP", "EXTERNAL_IP", "STATUS"], rows)


def cmd_instances_describe(state, name) -> str:
    vm = _vm(state, name)
    if not vm:
        return _gerr(f"The resource 'projects/{PROJECT}/zones/{ZONE}/instances/{name}' was not found")
    nat = f"\n    accessConfigs:\n    - natIP: {vm['external_ip']}" if vm["external_ip"] else ""
    tags = "".join(f"\n  - {t}" for t in vm["tags"]) or " []"
    return (f"name: {vm['name']}\nzone: {vm['zone']}\nstatus: RUNNING\nnetworkInterfaces:\n"
            f"  - network: {NETWORK}\n    subnetwork: {vm['subnet']}\n    networkIP: {vm['internal_ip']}{nat}\n"
            f"tags:\n  items:{tags}")


def cmd_tags(state, name, flags, add: bool) -> str:
    vm = _vm(state, name)
    if not vm:
        return _gerr(f"The resource 'instances/{name}' was not found")
    tags = [t for t in str(flags.get("tags", "")).split(",") if t]
    if not tags:
        return "usage: gcloud compute instances add-tags <vm> --zone <zone> --tags <tag>[,<tag>]"
    for t in tags:
        if add and t not in vm["tags"]:
            vm["tags"].append(t)
        elif not add and t in vm["tags"]:
            vm["tags"].remove(t)
    return f"Updated [https://www.googleapis.com/compute/v1/projects/{PROJECT}/zones/{vm['zone']}/instances/{vm['name']}]."


def cmd_add_access_config(state, name) -> str:
    vm = _vm(state, name)
    if not vm:
        return _gerr(f"The resource 'instances/{name}' was not found")
    if vm["external_ip"]:
        return _gerr("At most one access config is currently supported on a network interface.")
    vm["external_ip"] = vm.get("spare_ip") or state["nat_ip"]
    return f"Updated [https://www.googleapis.com/compute/v1/projects/{PROJECT}/zones/{vm['zone']}/instances/{vm['name']}]."


def _rule_row(r):
    source = ",".join(r["source_ranges"]) or ("tags:" + ",".join(r["source_tags"]) if r["source_tags"] else "")
    ports = ",".join(f"tcp:{p}" for p in r["ports"])
    return [r["name"], "INGRESS", r["priority"], source, ports if r["action"] == "allow" else "",
            ports if r["action"] == "deny" else "", ",".join(r["target_tags"])]


def cmd_rules_list(state) -> str:
    rows = [_rule_row(r) for r in sorted(state["firewall_rules"], key=lambda r: r["priority"])]
    return (render_table(["NAME", "DIRECTION", "PRIORITY", "SOURCE", "ALLOW", "DENY", "TARGET_TAGS"], rows) +
            "\n(plus the implied rules: allow all egress, deny all ingress — priority 65535)")


def cmd_rule_describe(state, name) -> str:
    r = _rule(state, name)
    if not r:
        return _gerr(f"The resource 'projects/{PROJECT}/global/firewalls/{name}' was not found")
    key = "allowed" if r["action"] == "allow" else "denied"
    lines = [f"name: {r['name']}", f"network: {NETWORK}", "direction: INGRESS", f"priority: {r['priority']}",
             f"{key}:", "  - IPProtocol: tcp", "    ports: [" + ", ".join(r["ports"]) + "]"]
    if r["source_ranges"]:
        lines.append("sourceRanges: [" + ", ".join(r["source_ranges"]) + "]")
    if r["source_tags"]:
        lines.append("sourceTags: [" + ", ".join(r["source_tags"]) + "]")
    lines.append("targetTags: [" + ", ".join(r["target_tags"]) + "]" if r["target_tags"]
                 else "targetTags: (none: applies to every VM in the network)")
    return "\n".join(lines)


def _ports(spec) -> list:
    """'tcp:443,tcp:8443' or 'tcp:22' or 'all' -> ['443', '8443']."""
    out = []
    for part in str(spec).split(","):
        proto, _, port = part.partition(":")
        out.append(port if port else ("all" if proto in ("all", "tcp") else proto))
    return out


def _list_flag(flags, key):
    return [v for v in str(flags[key]).split(",") if v] if key in flags and flags[key] is not True else None


def cmd_rule_create(state, name, flags) -> str:
    if not name:
        return "usage: gcloud compute firewall-rules create <rule> --network prod-vpc --allow tcp:<port> --source-ranges <cidr> [--target-tags <tag>]"
    if _rule(state, name):
        return _gerr(f"The resource 'projects/{PROJECT}/global/firewalls/{name}' already exists")
    if "allow" in flags:
        action, ports = "allow", _ports(flags["allow"])
    elif str(flags.get("action", "")) == "deny" and "rules" in flags:
        action, ports = "deny", _ports(flags["rules"])
    else:
        return _gerr("Must specify --allow tcp:<port>, or --action deny with --rules tcp:<port>.")
    ranges, stags = _list_flag(flags, "source-ranges"), _list_flag(flags, "source-tags")
    if not ranges and not stags:
        ranges = ["0.0.0.0/0"]  # gcloud's default when no source is given
    priority = int(flags["priority"]) if str(flags.get("priority", "")).isdigit() else 1000
    state["firewall_rules"].append(_fw(name, priority, action, ports, ranges, stags, _list_flag(flags, "target-tags")))
    return f"Creating firewall...done.\n" + render_table(
        ["NAME", "NETWORK", "DIRECTION", "PRIORITY", "ALLOW" if action == "allow" else "DENY"],
        [[name, NETWORK, "INGRESS", priority, ",".join(f"tcp:{p}" for p in ports)]])


def cmd_rule_update(state, name, flags) -> str:
    r = _rule(state, name)
    if not r:
        return _gerr(f"The resource 'projects/{PROJECT}/global/firewalls/{name}' was not found")
    for flag, field in (("target-tags", "target_tags"), ("source-tags", "source_tags"), ("source-ranges", "source_ranges")):
        value = _list_flag(flags, flag)
        if value is not None:
            r[field] = value
    if str(flags.get("priority", "")).isdigit():
        r["priority"] = int(flags["priority"])
    return f"Updated [https://www.googleapis.com/compute/v1/projects/{PROJECT}/global/firewalls/{name}]."


def cmd_rule_delete(state, name) -> str:
    r = _rule(state, name)
    if not r:
        return _gerr(f"The resource 'projects/{PROJECT}/global/firewalls/{name}' was not found")
    state["firewall_rules"].remove(r)
    return f"Deleted [https://www.googleapis.com/compute/v1/projects/{PROJECT}/global/firewalls/{name}]."


def cmd_routers(state, pos, flags) -> str:
    if pos[:1] == ["list"]:
        if not state["routers"]:
            return "Listed 0 items."
        return render_table(["NAME", "REGION", "NETWORK"], [[r["name"], r["region"], NETWORK] for r in state["routers"]])
    if pos[:1] == ["create"] and len(pos) > 1:
        if any(r["name"] == pos[1] for r in state["routers"]):
            return _gerr(f"The resource 'routers/{pos[1]}' already exists")
        region = str(flags.get("region", ""))
        if not region or region is True:
            return _gerr("argument --region: Must be specified.")
        state["routers"].append({"name": pos[1], "region": region, "nats": []})
        return f"Creating router [{pos[1]}]...done.\n" + render_table(["NAME", "REGION", "NETWORK"], [[pos[1], region, NETWORK]])
    if pos[:2] == ["nats", "create"] and len(pos) > 2:
        router = next((r for r in state["routers"] if r["name"] == flags.get("router")), None)
        if not router:
            return _gerr(f"The resource 'routers/{flags.get('router')}' was not found (create the Cloud Router first)")
        if router["region"] != str(flags.get("region", router["region"])):
            return _gerr(f"Router {router['name']} is in {router['region']}, not {flags.get('region')}.")
        router["nats"].append(pos[2])
        return f"Creating NAT [{pos[2]}] in router [{router['name']}]...done."
    if pos[:2] == ["nats", "list"]:
        router = next((r for r in state["routers"] if r["name"] == flags.get("router")), None)
        if not router:
            return _gerr(f"The resource 'routers/{flags.get('router')}' was not found")
        return render_table(["NAME", "ROUTER", "REGION"], [[n, router["name"], router["region"]] for n in router["nats"]]) \
            if router["nats"] else "Listed 0 items."
    return "(supported: routers list | create <name> --network --region | nats create <name> --router --region ... | nats list --router --region)"


def cmd_ssh(state, pos, flags) -> str:
    vm = _vm(state, pos[1]) if len(pos) > 1 else None
    if not vm:
        return _gerr("Could not find the instance. usage: gcloud compute ssh <vm> --zone <zone> --tunnel-through-iap")
    via_iap = bool(flags.get("tunnel-through-iap")) or not vm["external_ip"]
    reason = reachability(state, "iap" if via_iap else "internet", vm["name"], 22)
    if flags.get("troubleshoot"):
        net = ("OK" if reason is None else
               f"No ingress firewall rule allows traffic from the IAP range {IAP_RANGE} to port 22 on {vm['name']}."
               if via_iap else f"No ingress firewall rule allows your IP ({LAPTOP_IP}) to reach port 22 on {vm['name']}.")
        return ("---- Checking network connectivity ----\n" + net +
                "\n---- Checking user permissions ----\nUser has roles/iap.tunnelResourceAccessor. OK."
                "\n---- Checking VM status ----\nVM is RUNNING. Guest agent is healthy.")
    if reason is not None:
        if via_iap:
            return ("ERROR: (gcloud.compute.ssh) [/usr/bin/ssh] exited with return code [255].\n"
                    "ERROR: (gcloud.compute.start-iap-tunnel) Error while connecting [4003: 'failed to connect to backend']. "
                    "(Failed to connect to port 22)")
        return f"ssh: connect to host {vm['external_ip']} port 22: Connection timed out"
    if isinstance(flags.get("command"), str):
        return run_on_vm(state, vm, flags["command"].split())
    state["session"] = vm["name"]
    return f"oncall@{vm['name']}:~$   (you are now on {vm['name']}, {vm['internal_ip']} — 'exit' to leave the session)"


# ---------------------------------------------------------------- dispatch

def handle_gcloud(state, tokens) -> str:
    flags, pos = parse_flags(tokens, booleans=BOOLEANS)
    if pos[:2] == ["config", "list"]:
        return f"[compute]\nregion = {REGION}\nzone = {ZONE}\n[core]\naccount = oncall@example.com\nproject = {PROJECT}"
    if pos[:1] != ["compute"]:
        return f"'gcloud {' '.join(pos[:2])}' isn't simulated in the sandbox. Type 'help' for supported commands."
    pos = pos[1:]
    name = pos[2] if len(pos) > 2 else None
    if pos[:2] == ["instances", "list"]:
        return cmd_instances_list(state)
    if pos[:2] == ["instances", "describe"]:
        return cmd_instances_describe(state, name)
    if pos[:2] in (["instances", "add-tags"], ["instances", "remove-tags"]):
        return cmd_tags(state, name, flags, add=pos[1] == "add-tags")
    if pos[:2] == ["instances", "add-access-config"]:
        return cmd_add_access_config(state, name)
    if pos[:2] == ["firewall-rules", "list"]:
        return cmd_rules_list(state)
    if pos[:2] == ["firewall-rules", "describe"]:
        return cmd_rule_describe(state, name)
    if pos[:2] == ["firewall-rules", "create"]:
        return cmd_rule_create(state, name, flags)
    if pos[:2] == ["firewall-rules", "update"]:
        return cmd_rule_update(state, name, flags)
    if pos[:2] == ["firewall-rules", "delete"]:
        return cmd_rule_delete(state, name)
    if pos[:3] == ["networks", "subnets", "list"]:
        return render_table(["NAME", "REGION", "NETWORK", "RANGE"],
                            [[s["name"], s["region"], NETWORK, s["range"]] for s in state["subnets"]])
    if pos[:1] == ["routers"]:
        return cmd_routers(state, pos[1:], flags)
    if pos[:1] == ["ssh"]:
        return cmd_ssh(state, pos, flags)
    return f"'gcloud compute {' '.join(pos[:2])}' isn't simulated in the sandbox. Type 'help' for supported commands."


def handle_command(state: dict, raw: str):
    norm = normalize(raw)
    tokens = norm.split()
    if state.get("session"):
        if norm in {"help", "?"}:
            return HELP_TEXT
        if norm in {"exit", "logout"}:
            name = state["session"]
            state["session"] = None
            return f"logout\nConnection to {name} closed."
        return run_on_vm(state, _vm(state, state["session"]), tokens)
    if norm in {"exit", "quit", ":q"}:
        return None
    if norm in {"help", "?"} or not tokens:
        return HELP_TEXT
    cmd, args = tokens[0], tokens[1:]
    if cmd == "gcloud":
        return handle_gcloud(state, args)
    if cmd == "curl":
        return cmd_curl(state, None, args)
    if cmd in ("nc", "ncat"):
        return cmd_nc(state, None, args)
    if cmd == "ping":
        return "(no firewall rule here allows ICMP — a failed ping proves nothing. Test the real port: nc -zv <ip> <port>.)"
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


# ------------------------------------------------------- mystery/sandbox hooks

def placeholders(state: dict) -> dict:
    web, db, worker = state["instances"]
    return {"web_ip": web["external_ip"] or "", "web_internal_ip": web["internal_ip"],
            "db_ip": db["internal_ip"], "worker_ip": worker["internal_ip"], "zone": ZONE, "region": REGION}


GOAL_CHECKS = {
    "reachable": lambda state, g: reachability(state, g["from"], g["to"], g["port"]) is None,
    "not_reachable": lambda state, g: reachability(state, g["from"], g["to"], g["port"]) is not None,
}


def collateral_issues(state: dict) -> set:
    issues = set()
    for r in state["firewall_rules"]:
        if r["action"] != "allow" or "0.0.0.0/0" not in r["source_ranges"]:
            continue
        risky = [p for p in r["ports"] if p not in ("80", "443")]
        if risky:
            scope = f"VMs tagged {','.join(r['target_tags'])}" if r["target_tags"] else "EVERY VM in the network"
            issues.add(f"opened port {','.join(risky)} to the entire internet on {scope} (rule {r['name']})")
        elif not r["target_tags"]:
            issues.add(f"created rule {r['name']} with no target tags — it exposes 443 on every VM, including the database")
    for vm in state["instances"]:
        if vm["name"] != "web-1" and vm["external_ip"]:
            issues.add(f"gave {vm['name']} an external IP — a private VM is now directly on the internet")
    return issues


def describe_state(state: dict) -> list:
    return [
        f"You're in project {PROJECT}, network {NETWORK} (global VPC), working in {REGION}.",
        "Three VMs: web-1 (external IP, serves HTTPS), db-1 (private, :5432 for web-1), worker-1 (private, pulls packages).",
        f"Your laptop's public IP is {LAPTOP_IP}. Shell access is through IAP: gcloud compute ssh <vm> --zone {ZONE} --tunnel-through-iap",
        "Two things are broken here. Find the layer, and fix it.",
    ]


def run_sandbox() -> None:
    run_loop("gcp", "project", generate_state, handle_command, describe_state)
