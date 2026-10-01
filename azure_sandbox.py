"""
Azure sandbox — a fake subscription with one resource group, explored and
fixed with real `az ...` commands.

Layout (rg-web-prod, vnet-web-prod 10.20.0.0/16, peered to a hub VNet):
  snet-web (10.20.1.0/24, nsg-web)            vm-web-01   public IP, serves 443
  snet-app (10.20.2.0/24, nsg-app, rt-app)    vm-app-01   private, serves 8080 to the web subnet
  hub: Azure Firewall fw-hub at 10.0.0.4; rt-app sends 0.0.0.0/0 to it

Traffic is evaluated the way Azure does it:
  inbound:  public IP -> subnet NSG -> NIC NSG (both must allow) -> the VM
  outbound: the subnet's route table decides the next hop; a user-defined
            route to a virtual appliance is followed blindly, so a wrong IP
            black-holes the traffic
NSG rules are evaluated by priority, lowest number first, first match
wins, with Azure's hidden default rules (65000 AllowVnetInBound, 65001
AllowAzureLoadBalancerInBound, 65500 DenyAllInBound) at the end.

Random problems (two per subscription in sandbox mode):
  nsg_deny_shadow        nsg-web has a Deny at priority 90 with source '*',
                         ahead of Allow-HTTPS at 100
  nic_nsg_deny           a forgotten NSG on vm-web-01's NIC denies all inbound
  udr_blackhole          rt-app's next hop is 10.0.0.5, where nothing exists
  vm_deallocated         vm-web-01 was deallocated by an auto-shutdown schedule
  app_nsg_missing_allow  nsg-app's Deny-All (4000) has no Allow for 8080 above it

Reactive: nsg rule create/update/delete, nic update (remove its NSG),
route update, and vm start/deallocate change the state.
"""

import ipaddress
import json
import random

from engine import normalize
from sandbox_common import parse_flags, render_table, run_loop

PROBLEMS = ["nsg_deny_shadow", "nic_nsg_deny", "udr_blackhole", "vm_deallocated", "app_nsg_missing_allow"]

LAPTOP_IP = "203.0.113.50"
OFFICE_CIDR = "203.0.113.0/24"
INTERNET_IP = "93.184.216.34"
RG = "rg-web-prod"
HUB_RG = "rg-network-hub"
FIREWALL_IP = "10.0.0.4"
VNET_SPACE = ["10.20.0.0/16", "10.0.0.0/16"]  # the VNet plus the peered hub
SUBSCRIPTION = "33333333-dddd-4eee-8fff-444444444444"

ALIASES = {"-g": "resource-group", "-n": "name", "-d": "show-details", "-o": "output"}
BOOLEANS = {"show-details", "include-default"}

DEFAULT_RULES = [
    {"name": "AllowVnetInBound", "priority": 65000, "access": "Allow", "source": "VirtualNetwork", "port": "*"},
    {"name": "AllowAzureLoadBalancerInBound", "priority": 65001, "access": "Allow", "source": "AzureLoadBalancer", "port": "*"},
    {"name": "DenyAllInBound", "priority": 65500, "access": "Deny", "source": "*", "port": "*"},
]

HELP_TEXT = """Supported commands (-g/--resource-group and -n/--name work as in az; output is always a table):
  az account show        az group list
  az vm list -d          az vm show -g <rg> -n <vm> -d
  az vm start | deallocate -g <rg> -n <vm>
  az vm run-command invoke -g <rg> -n <vm> --command-id RunShellScript --scripts "<curl|nc|hostname ...>"
  az network vnet subnet list -g <rg> --vnet-name <vnet>
  az network nsg list
  az network nsg rule list -g <rg> --nsg-name <nsg> [--include-default]
  az network nsg rule create -g <rg> --nsg-name <nsg> -n <rule> --priority <n> --access Allow|Deny
        --destination-port-ranges <port> --source-address-prefixes <cidr|*|Internet|VirtualNetwork>
  az network nsg rule update -g <rg> --nsg-name <nsg> -n <rule> [--source-address-prefixes ..] [--access ..] [--priority ..]
  az network nsg rule delete -g <rg> --nsg-name <nsg> -n <rule>
  az network nic list-effective-nsg -g <rg> -n <nic>
  az network nic update -g <rg> -n <nic> --network-security-group ""      (detach the NIC's NSG)
  az network watcher test-ip-flow -g <rg> --vm <vm> --direction Inbound --protocol TCP --local <ip:port> --remote <ip:port>
  az network watcher show-next-hop -g <rg> --vm <vm> --source-ip <ip> --dest-ip <ip>
  az network route-table route list -g <rg> --route-table-name <rt>
  az network route-table route update -g <rg> --route-table-name <rt> -n <route> --next-hop-ip-address <ip>
  az network nic show-effective-route-table -g <rg> -n <nic>
  az network firewall show -g <rg> -n <firewall>        az network public-ip list
From your laptop:  curl [-m N] <url>   nc -zv <ip> <port>   curl ifconfig.me
  help | exit"""


# ------------------------------------------------------------------ state

def _rule(name, priority, access, source, port):
    return {"name": name, "priority": priority, "access": access, "source": source, "port": str(port)}


def generate_state(seed=None, problems=None) -> dict:
    rng = random.Random(seed)
    if problems is None:
        problems = rng.sample(PROBLEMS, 2)
    web_public = f"20.{rng.randint(50, 120)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"
    web_private = f"10.20.1.{rng.randint(4, 250)}"
    app_private = f"10.20.2.{rng.randint(4, 250)}"

    web_rules = [_rule("Allow-HTTPS", 100, "Allow", "Internet", 443),
                 _rule("Allow-SSH-Office", 110, "Allow", OFFICE_CIDR, 22)]
    if "nsg_deny_shadow" in problems:
        web_rules.insert(0, _rule("Block-Scanner", 90, "Deny", "*", "*"))
    app_rules = [_rule("Deny-All-Inbound", 4000, "Deny", "*", "*")]
    if "app_nsg_missing_allow" not in problems:
        app_rules.insert(0, _rule("Allow-Web-To-App", 100, "Allow", "10.20.1.0/24", 8080))

    nsgs = {"nsg-web": web_rules, "nsg-app": app_rules}
    if "nic_nsg_deny" in problems:
        nsgs["nsg-vm-web-01"] = [_rule("Deny-All-Inbound", 100, "Deny", "*", "*")]

    return {
        "subscription": SUBSCRIPTION,
        "problems": problems,
        "nsgs": nsgs,
        "subnets": [
            {"name": "snet-web", "prefix": "10.20.1.0/24", "nsg": "nsg-web", "route_table": None},
            {"name": "snet-app", "prefix": "10.20.2.0/24", "nsg": "nsg-app", "route_table": "rt-app"},
        ],
        "route_tables": {"rt-app": [{"name": "to-firewall", "prefix": "0.0.0.0/0", "type": "VirtualAppliance",
                                     "next_hop": "10.0.0.5" if "udr_blackhole" in problems else FIREWALL_IP}]},
        "firewall": {"name": "fw-hub", "rg": HUB_RG, "ip": FIREWALL_IP},
        "vms": [
            {"name": "vm-web-01", "subnet": "snet-web", "nic": "nic-vm-web-01", "private_ip": web_private,
             "public_ip": web_public, "nic_nsg": "nsg-vm-web-01" if "nic_nsg_deny" in problems else None,
             "power": "deallocated" if "vm_deallocated" in problems else "running", "listens": [443, 22]},
            {"name": "vm-app-01", "subnet": "snet-app", "nic": "nic-vm-app-01", "private_ip": app_private,
             "public_ip": None, "nic_nsg": None, "power": "running", "listens": [8080, 22]},
        ],
    }


# ----------------------------------------------------------------- lookups

def _vm(state, ref):
    for vm in state["vms"]:
        if ref in (vm["name"], vm["nic"], vm["private_ip"], vm["public_ip"]):
            return vm
    return None


def _subnet(state, name):
    return next(s for s in state["subnets"] if s["name"] == name)


def _in(ip, cidr) -> bool:
    return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)


def _source_matches(source: str, ip: str) -> bool:
    s = source.lower()
    if s in ("*", "any"):
        return True
    in_vnet = any(_in(ip, c) for c in VNET_SPACE)
    if s == "internet":
        return not in_vnet
    if s == "virtualnetwork":
        return in_vnet
    if s == "azureloadbalancer":
        return ip == "168.63.129.16"
    try:
        return _in(ip, source)
    except ValueError:
        return False


def _evaluate(rules: list, src_ip: str, port: int):
    """Returns (allowed, rule name) for an inbound packet: lowest priority
    number first, first match wins, default rules last."""
    for r in sorted(rules + DEFAULT_RULES, key=lambda r: r["priority"]):
        if r["port"] in ("*", str(port)) and _source_matches(r["source"], src_ip):
            return r["access"].lower() == "allow", r["name"]
    return False, "DenyAllInBound"


def _inbound(state, vm, src_ip: str, port: int):
    """(allowed, deciding rule) through the subnet NSG and then the NIC NSG."""
    subnet = _subnet(state, vm["subnet"])
    for scope, nsg in (("subnet", subnet["nsg"]), ("networkInterface", vm["nic_nsg"])):
        if not nsg:
            continue
        ok, rule = _evaluate(state["nsgs"].get(nsg, []), src_ip, port)
        if not ok:
            return False, f"{scope}/{nsg}/{rule}"
    final_nsg = vm["nic_nsg"] or subnet["nsg"]
    return True, f"{final_nsg}/{_evaluate(state['nsgs'].get(final_nsg, []), src_ip, port)[1]}"


def _next_hop(state, vm, dest_ip: str):
    """(type, ip, route table) Azure would use for dest_ip from this VM."""
    if any(_in(dest_ip, c) for c in VNET_SPACE):
        return "VnetLocal", None, None
    rt = _subnet(state, vm["subnet"])["route_table"]
    for route in state["route_tables"].get(rt, []) if rt else []:
        if _in(dest_ip, route["prefix"]):
            return route["type"], route["next_hop"], rt
    return "Internet", None, None


def reachability(state, source: str, target: str, port: int):
    """None when a TCP connection works, else a short reason (hidden from
    the player). source/target are 'internet' or a VM name."""
    if source == "internet":
        vm = _vm(state, target)
        if vm["power"] != "running":
            return "vm not running"
        if not vm["public_ip"]:
            return "no public ip"
        ok, rule = _inbound(state, vm, LAPTOP_IP, port)
        if not ok:
            return f"nsg: {rule}"
        return None if port in vm["listens"] else "refused"
    src = _vm(state, source)
    if src["power"] != "running":
        return "vm not running"
    if target == "internet":
        hop_type, hop_ip, _ = _next_hop(state, src, INTERNET_IP)
        if hop_type == "VirtualAppliance" and hop_ip != state["firewall"]["ip"]:
            return "next hop is not a real appliance"
        return None
    dst = _vm(state, target)
    if dst["power"] != "running":
        return "vm not running"
    ok, rule = _inbound(state, dst, src["private_ip"], port)
    if not ok:
        return f"nsg: {rule}"
    return None if port in dst["listens"] else "refused"


# ----------------------------------------------------------------- helpers

def _err(code: str, message: str) -> str:
    return f"({code}) {message}\nCode: {code}\nMessage: {message}"


def _need_rg(flags, expected=RG):
    rg = flags.get("resource-group")
    if rg and rg not in (expected, HUB_RG, RG):
        return _err("ResourceGroupNotFound", f"Resource group '{rg}' could not be found.")
    return None


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
        if host != target["public_ip"]:
            return "unroutable"
        return reachability(state, "internet", target["name"], port)
    if target is None:
        return reachability(state, source_vm["name"], "internet", port)
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
        return source_vm["public_ip"] or "20.61.200.4"  # the firewall's public IP
    reason = _connect(state, source_vm, host, port)
    if reason is None:
        target = _vm(state, host)
        if target and target["name"] == "vm-web-01":
            return "<!doctype html><title>Shop</title><h1>Welcome to the shop</h1>"
        if target:
            return '{"status":"ok","service":"app"}'
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


# ---------------------------------------------------------------- commands

def cmd_vm_list(state) -> str:
    rows = [[vm["name"], RG, f"VM {vm['power']}", vm["public_ip"] or "", vm["private_ip"], "westeurope"]
            for vm in state["vms"]]
    return render_table(["Name", "ResourceGroup", "PowerState", "PublicIps", "PrivateIps", "Location"], rows)


def cmd_vm_power(state, flags, action: str) -> str:
    vm = _vm(state, flags.get("name"))
    if not vm:
        return _err("ResourceNotFound", f"The Resource 'Microsoft.Compute/virtualMachines/{flags.get('name')}' was not found.")
    vm["power"] = "running" if action == "start" else "deallocated"
    return ""


def cmd_run_command(state, flags) -> str:
    vm = _vm(state, flags.get("name"))
    if not vm:
        return _err("ResourceNotFound", f"The Resource 'Microsoft.Compute/virtualMachines/{flags.get('name')}' was not found.")
    if vm["power"] != "running":
        return _err("OperationNotAllowed", f"The VM '{vm['name']}' is not running. Run Command needs a running VM.")
    script = flags.get("scripts")
    if not isinstance(script, str) or not script:
        return "usage: az vm run-command invoke -g <rg> -n <vm> --command-id RunShellScript --scripts \"<command>\""
    tokens = script.split()
    if tokens[0] == "sudo":
        tokens = tokens[1:]
    if tokens[0] == "curl":
        out = cmd_curl(state, vm, tokens[1:])
    elif tokens[0] in ("nc", "ncat"):
        out = cmd_nc(state, vm, tokens[1:])
    elif tokens[0] == "hostname":
        out = vm["name"]
    else:
        out = f"{tokens[0]}: not simulated inside the VM (try curl, nc -zv, hostname)"
    return f"[stdout]\n{out}\n[stderr]"


def cmd_subnet_list(state) -> str:
    rows = [[s["name"], s["prefix"], s["nsg"] or "", s["route_table"] or ""] for s in state["subnets"]]
    return render_table(["Name", "AddressPrefix", "NetworkSecurityGroup", "RouteTable"], rows)


def cmd_nsg_list(state) -> str:
    def attached(nsg):
        subs = [f"subnet {s['name']}" for s in state["subnets"] if s["nsg"] == nsg]
        nics = [f"nic {vm['nic']}" for vm in state["vms"] if vm["nic_nsg"] == nsg]
        return ", ".join(subs + nics) or "(not attached)"
    return render_table(["Name", "ResourceGroup", "AttachedTo"], [[n, RG, attached(n)] for n in state["nsgs"]])


def _rule_rows(rules):
    return [[r["name"], r["priority"], "Inbound", r["access"], "Tcp" if r["port"] != "*" else "*",
             r["source"], r["port"]] for r in sorted(rules, key=lambda r: r["priority"])]


RULE_HEADERS = ["Name", "Priority", "Direction", "Access", "Protocol", "SourceAddressPrefix", "DestinationPortRange"]


def cmd_rule_list(state, flags) -> str:
    rules = state["nsgs"].get(flags.get("nsg-name"))
    if rules is None:
        return _err("ResourceNotFound", f"The Resource 'Microsoft.Network/networkSecurityGroups/{flags.get('nsg-name')}' was not found.")
    shown = rules + (DEFAULT_RULES if flags.get("include-default") else [])
    if not shown:
        return "(no custom rules; add --include-default to see Azure's built-in ones)"
    return render_table(RULE_HEADERS, _rule_rows(shown))


def _find_rule(state, flags):
    rules = state["nsgs"].get(flags.get("nsg-name"))
    if rules is None:
        return None, None, _err("ResourceNotFound", f"The Resource 'Microsoft.Network/networkSecurityGroups/{flags.get('nsg-name')}' was not found.")
    name = str(flags.get("name", "")).lower()
    return rules, next((r for r in rules if r["name"].lower() == name), None), None


def _apply_rule_flags(rule, flags) -> str | None:
    if "priority" in flags:
        if not str(flags["priority"]).isdigit() or not 100 <= int(flags["priority"]) <= 4096:
            return _err("SecurityRuleInvalidPriority", "Priority must be between 100 and 4096.")
        rule["priority"] = int(flags["priority"])
    if "access" in flags:
        rule["access"] = "Deny" if str(flags["access"]).lower() == "deny" else "Allow"
    if "source-address-prefixes" in flags or "source-address-prefix" in flags:
        raw = str(flags.get("source-address-prefixes", flags.get("source-address-prefix")))
        rule["source"] = {"internet": "Internet", "virtualnetwork": "VirtualNetwork"}.get(raw, raw)
    if "destination-port-ranges" in flags or "destination-port-range" in flags:
        rule["port"] = str(flags.get("destination-port-ranges", flags.get("destination-port-range")))
    return None


def cmd_rule_create(state, flags) -> str:
    rules, existing, err = _find_rule(state, flags)
    if err:
        return err
    if existing:
        return _err("Conflict", f"Rule '{flags.get('name')}' already exists; use 'az network nsg rule update'.")
    if not flags.get("name") or "priority" not in flags:
        return "usage: az network nsg rule create -g <rg> --nsg-name <nsg> -n <rule> --priority <n> --access Allow --destination-port-ranges <port> --source-address-prefixes <src>"
    if any(r["priority"] == int(flags["priority"]) for r in rules if str(flags["priority"]).isdigit()):
        return _err("SecurityRuleConflict", f"Another rule already uses priority {flags['priority']}.")
    rule = _rule(flags["name"], 0, "Allow", "*", "*")
    err = _apply_rule_flags(rule, flags)
    if err:
        return err
    rules.append(rule)
    return json.dumps({"name": rule["name"], "priority": rule["priority"], "access": rule["access"],
                       "provisioningState": "Succeeded"}, indent=2)


def cmd_rule_update(state, flags) -> str:
    _, rule, err = _find_rule(state, flags)
    if err:
        return err
    if not rule:
        return _err("ResourceNotFound", f"Rule '{flags.get('name')}' was not found in {flags.get('nsg-name')}.")
    err = _apply_rule_flags(rule, flags)
    if err:
        return err
    return json.dumps({"name": rule["name"], "priority": rule["priority"], "access": rule["access"],
                       "sourceAddressPrefix": rule["source"], "destinationPortRange": rule["port"]}, indent=2)


def cmd_rule_delete(state, flags) -> str:
    rules, rule, err = _find_rule(state, flags)
    if err:
        return err
    if not rule:
        return _err("ResourceNotFound", f"Rule '{flags.get('name')}' was not found in {flags.get('nsg-name')}.")
    rules.remove(rule)
    return ""


def cmd_effective_nsg(state, flags) -> str:
    vm = _vm(state, flags.get("name"))
    if not vm:
        return _err("ResourceNotFound", f"NIC '{flags.get('name')}' was not found.")
    if vm["power"] != "running":
        return _err("NetworkInterfaceNotAttachedToRunningVm", "Effective rules are only available for a NIC on a running VM.")
    subnet = _subnet(state, vm["subnet"])
    blocks = []
    for scope, nsg in ((f"subnet {subnet['name']}", subnet["nsg"]), (f"networkInterface {vm['nic']}", vm["nic_nsg"])):
        if nsg:
            blocks.append(f"Association: {scope} ({nsg})\n" + render_table(RULE_HEADERS, _rule_rows(state["nsgs"][nsg])))
    return "\n\n".join(blocks) + "\n\n(traffic must be allowed by EVERY association listed)"


def cmd_nic_update(state, flags) -> str:
    vm = _vm(state, flags.get("name"))
    if not vm:
        return _err("ResourceNotFound", f"NIC '{flags.get('name')}' was not found.")
    if flags.get("network-security-group") in ("", "none", "null") or flags.get("remove") == "networksecuritygroup":
        vm["nic_nsg"] = None
        return json.dumps({"name": vm["nic"], "networkSecurityGroup": None, "provisioningState": "Succeeded"}, indent=2)
    return "(the sandbox supports detaching the NIC's NSG: --network-security-group \"\")"


def _split_endpoint(value):
    ip, _, port = str(value).rpartition(":")
    return ip, int(port) if port.isdigit() else None


def cmd_ip_flow(state, flags) -> str:
    vm = _vm(state, flags.get("vm"))
    if not vm:
        return _err("ResourceNotFound", f"VM '{flags.get('vm')}' was not found.")
    if vm["power"] != "running":
        return _err("VmNotRunning", "IP flow verify needs a running VM.")
    _, port = _split_endpoint(flags.get("local", ""))
    remote_ip, _ = _split_endpoint(flags.get("remote", ""))
    if port is None or not remote_ip:
        return "usage: --local <vm-ip:port> --remote <source-ip:port> --direction Inbound --protocol TCP"
    ok, rule = _inbound(state, vm, remote_ip, port)
    return json.dumps({"access": "Allow" if ok else "Deny", "ruleName": f"securityRules/{rule}"}, indent=2)


def cmd_next_hop(state, flags) -> str:
    vm = _vm(state, flags.get("vm"))
    if not vm or not flags.get("dest-ip"):
        return "usage: az network watcher show-next-hop -g <rg> --vm <vm> --source-ip <ip> --dest-ip <ip>"
    hop_type, hop_ip, rt = _next_hop(state, vm, str(flags["dest-ip"]))
    return json.dumps({"nextHopType": hop_type, "nextHopIpAddress": hop_ip,
                       "routeTableId": f".../routeTables/{rt}" if rt else "System Route"}, indent=2)


def cmd_route_list(state, flags) -> str:
    routes = state["route_tables"].get(flags.get("route-table-name"))
    if routes is None:
        return _err("ResourceNotFound", f"Route table '{flags.get('route-table-name')}' was not found.")
    return render_table(["Name", "AddressPrefix", "NextHopType", "NextHopIpAddress"],
                        [[r["name"], r["prefix"], r["type"], r["next_hop"]] for r in routes])


def cmd_route_update(state, flags) -> str:
    routes = state["route_tables"].get(flags.get("route-table-name"))
    route = next((r for r in routes or [] if r["name"] == flags.get("name")), None)
    if not route:
        return _err("ResourceNotFound", f"Route '{flags.get('name')}' was not found.")
    if "next-hop-ip-address" not in flags:
        return "usage: ... route update -g <rg> --route-table-name <rt> -n <route> --next-hop-ip-address <ip>"
    route["next_hop"] = str(flags["next-hop-ip-address"])
    return json.dumps({"name": route["name"], "nextHopType": route["type"], "nextHopIpAddress": route["next_hop"]}, indent=2)


def cmd_effective_routes(state, flags) -> str:
    vm = _vm(state, flags.get("name"))
    if not vm:
        return _err("ResourceNotFound", f"NIC '{flags.get('name')}' was not found.")
    rt = _subnet(state, vm["subnet"])["route_table"]
    user = state["route_tables"].get(rt, []) if rt else []
    overridden = any(r["prefix"] == "0.0.0.0/0" for r in user)
    rows = [["Default", "Active", "10.20.0.0/16", "VnetLocal", ""],
            ["Default", "Active", "10.0.0.0/16", "VNetPeering", ""],
            ["Default", "Invalid" if overridden else "Active", "0.0.0.0/0", "Internet", ""]]
    rows += [["User", "Active", r["prefix"], r["type"], r["next_hop"]] for r in user]
    return render_table(["Source", "State", "Address Prefix", "Next Hop Type", "Next Hop IP"], rows)


def cmd_firewall_show(state, flags) -> str:
    fw = state["firewall"]
    if flags.get("name") != fw["name"]:
        return _err("ResourceNotFound", f"Azure Firewall '{flags.get('name')}' was not found.")
    return json.dumps({"name": fw["name"], "resourceGroup": fw["rg"], "provisioningState": "Succeeded",
                       "ipConfigurations": [{"privateIPAddress": fw["ip"]}]}, indent=2)


def cmd_public_ips(state) -> str:
    rows = [[f"pip-{vm['name']}", RG, vm["public_ip"], "Static", vm["nic"]] for vm in state["vms"] if vm["public_ip"]]
    return render_table(["Name", "ResourceGroup", "IpAddress", "AllocationMethod", "AttachedTo"], rows)


# ---------------------------------------------------------------- dispatch

def handle_az(state, tokens) -> str:
    flags, pos = parse_flags(tokens, ALIASES, BOOLEANS)
    err = _need_rg(flags)
    if err:
        return err
    path = " ".join(pos)

    simple = {
        "account show": lambda: json.dumps({"name": "Contoso-Prod", "id": state["subscription"],
                                            "user": {"name": "oncall@contoso.com", "type": "user"}}, indent=2),
        "group list": lambda: render_table(["Name", "Location", "Status"],
                                           [[RG, "westeurope", "Succeeded"], [HUB_RG, "westeurope", "Succeeded"]]),
        "vm list": lambda: cmd_vm_list(state),
        "vm show": lambda: cmd_vm_list(state) if not flags.get("name") else "\n".join(
            l for i, l in enumerate(cmd_vm_list(state).splitlines()) if i == 0 or str(flags["name"]) in l),
        "vm start": lambda: cmd_vm_power(state, flags, "start"),
        "vm deallocate": lambda: cmd_vm_power(state, flags, "deallocate"),
        "vm stop": lambda: cmd_vm_power(state, flags, "deallocate"),
        "vm run-command invoke": lambda: cmd_run_command(state, flags),
        "network vnet subnet list": lambda: cmd_subnet_list(state),
        "network nsg list": lambda: cmd_nsg_list(state),
        "network nsg rule list": lambda: cmd_rule_list(state, flags),
        "network nsg rule create": lambda: cmd_rule_create(state, flags),
        "network nsg rule update": lambda: cmd_rule_update(state, flags),
        "network nsg rule delete": lambda: cmd_rule_delete(state, flags),
        "network nic list-effective-nsg": lambda: cmd_effective_nsg(state, flags),
        "network nic update": lambda: cmd_nic_update(state, flags),
        "network nic show-effective-route-table": lambda: cmd_effective_routes(state, flags),
        "network watcher test-ip-flow": lambda: cmd_ip_flow(state, flags),
        "network watcher show-next-hop": lambda: cmd_next_hop(state, flags),
        "network route-table route list": lambda: cmd_route_list(state, flags),
        "network route-table route update": lambda: cmd_route_update(state, flags),
        "network route-table list": lambda: render_table(["Name", "ResourceGroup", "Subnets"], [["rt-app", RG, "snet-app"]]),
        "network firewall show": lambda: cmd_firewall_show(state, flags),
        "network public-ip list": lambda: cmd_public_ips(state),
    }
    if path in simple:
        return simple[path]()
    return f"'az {path}' isn't simulated in the sandbox. Type 'help' for supported commands."


def handle_command(state: dict, raw: str):
    norm = normalize(raw)
    if norm in {"exit", "quit", ":q"}:
        return None
    tokens = norm.split()
    if norm in {"help", "?"} or not tokens:
        return HELP_TEXT
    cmd, args = tokens[0], tokens[1:]
    if cmd == "az":
        return handle_az(state, args)
    if cmd == "curl":
        return cmd_curl(state, None, args)
    if cmd in ("nc", "ncat"):
        return cmd_nc(state, None, args)
    if cmd == "ping":
        return "(Azure blocks inbound ICMP at these NSGs — a failed ping proves nothing. Test the real port: nc -zv <ip> <port>.)"
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


# ------------------------------------------------------- mystery/sandbox hooks

def placeholders(state: dict) -> dict:
    web, app = state["vms"]
    return {"web_ip": web["public_ip"], "web_private_ip": web["private_ip"], "app_ip": app["private_ip"],
            "firewall_ip": state["firewall"]["ip"]}


GOAL_CHECKS = {
    "reachable": lambda state, g: reachability(state, g["from"], g["to"], g["port"]) is None,
    "not_reachable": lambda state, g: reachability(state, g["from"], g["to"], g["port"]) is not None,
}


def collateral_issues(state: dict) -> set:
    issues = set()
    for nsg, rules in state["nsgs"].items():
        for r in rules:
            wide_open = r["source"].lower() in ("*", "internet", "0.0.0.0/0")
            if r["access"] == "Allow" and wide_open and r["port"] not in ("80", "443"):
                what = "every port" if r["port"] == "*" else f"port {r['port']}"
                issues.add(f"opened {what} on {nsg} to the entire internet — "
                           "an allow rule that broad defeats the NSG")
    for s in state["subnets"]:
        if s["nsg"] and not state["nsgs"].get(s["nsg"]) and s["name"] == "snet-app":
            issues.add("deleted every rule in nsg-app, including its Deny-All — the app tier is now open to the whole VNet")
    if not any(r["prefix"] == "0.0.0.0/0" for r in state["route_tables"]["rt-app"]):
        issues.add("removed the route to the firewall — the app tier now bypasses egress filtering")
    return issues


def describe_state(state: dict) -> list:
    return [
        f"You're signed in to subscription Contoso-Prod, resource group {RG} (westeurope).",
        "Two VMs: vm-web-01 (snet-web, public, serves HTTPS) and vm-app-01 (snet-app, private, :8080 for the web tier).",
        f"The app subnet's outbound traffic is routed through the hub firewall fw-hub ({HUB_RG}).",
        f"Your laptop's public IP is {LAPTOP_IP}. Two things are broken here. Find the layer, and fix it.",
    ]


def run_sandbox() -> None:
    run_loop("azure", "subscription", generate_state, handle_command, describe_state)
