"""
AWS sandbox — a fake AWS account with one VPC, explored and fixed with
real `aws ec2 ...` commands.

Layout (ids and IPs are random per seed):
  public-a  (10.0.1.0/24)  web-1      serves 443 to the internet; NAT gateway lives here
  private-a (10.0.2.0/24)  api-1      serves 8080 to web-1
                           worker-1   needs outbound 443 to pull packages

Traffic is evaluated for real, layer by layer: public IP -> route table
(IGW / NAT) -> network ACLs (stateless: the return path on ephemeral ports
must be allowed too) -> security groups (stateful). Every failure looks the
same from outside — a timeout — so the player has to read the config to
find which layer drops it.

Random problems (two per account in sandbox mode):
  missing_igw_route      public route table has no 0.0.0.0/0 -> IGW
  private_no_egress      private route table has no 0.0.0.0/0 -> NAT
  sg_missing_port        web-sg allows SSH from the office but not 443
  nacl_ephemeral_block   public NACL egress allows only 80/443, so replies
                         to clients (ephemeral ports) are dropped
  no_public_ip           web-1 launched without a public IP (an unused
                         Elastic IP is sitting in the account)
  api_sg_wrong_source    api-sg allows 8080 from the wrong source

Reactive: create-route, replace-route, authorize/revoke-security-group-
ingress, replace/create-network-acl-entry, associate-address,
create-nat-gateway, and terminate-instances change the state.
"""

import ipaddress
import json
import random

from engine import normalize
from sandbox_common import render_table, run_loop

PROBLEMS = ["missing_igw_route", "private_no_egress", "sg_missing_port",
            "nacl_ephemeral_block", "no_public_ip", "api_sg_wrong_source"]

LAPTOP_IP = "203.0.113.50"        # the player's office/home IP
OFFICE_CIDR = "203.0.113.0/24"
INTERNET_IP = "93.184.216.34"      # stands in for any public host
EPHEMERAL = 50000                  # a representative client-side port
REGION = "us-east-1"
ACCOUNT = "123456789012"
REPO_HOST = "cdn.amazonlinux.com"

HELP_TEXT = """Supported commands (output is always shown as a table; --query/--output are accepted and ignored):
  aws sts get-caller-identity
  aws ec2 describe-instances [--instance-ids <id>] [--filters Name=tag:Name,Values=web-1]
  aws ec2 describe-vpcs | describe-subnets | describe-route-tables | describe-internet-gateways
  aws ec2 describe-nat-gateways | describe-security-groups [--group-ids <sg>]
  aws ec2 describe-network-acls | describe-addresses | describe-vpc-endpoints
     (describe-subnets/route-tables/network-acls accept --filters Name=association.subnet-id,Values=<id>)
  aws ec2 create-route | replace-route --route-table-id <rtb> --destination-cidr-block 0.0.0.0/0 --gateway-id <igw> | --nat-gateway-id <nat>
  aws ec2 authorize-security-group-ingress | revoke-security-group-ingress --group-id <sg> --protocol tcp --port <n> --cidr <cidr> | --source-group <sg>
  aws ec2 replace-network-acl-entry | create-network-acl-entry --network-acl-id <acl> --rule-number <n> --protocol tcp
        --port-range From=<a>,To=<b> --cidr-block <cidr> --rule-action allow|deny --egress|--ingress
  aws ec2 associate-address --instance-id <id> --allocation-id <eipalloc>
  aws ec2 create-nat-gateway --subnet-id <subnet> --allocation-id <eipalloc>
  aws ec2 terminate-instances --instance-ids <id>
  aws ssm start-session --target <instance-id>      (a shell on the instance; 'exit' ends it)
From your laptop:  curl [-m N] <url>   nc -zv <ip> <port>   ssh ec2-user@<ip>   curl ifconfig.me
Inside a session:  curl <url>   nc -zv <host> <port>   sudo dnf check-update   ss -tulnp   hostname   exit
  help | exit"""


# ------------------------------------------------------------------ state

def _hex(rng, n):
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _entry(rule, proto, lo, hi, cidr, action="allow"):
    return {"rule": rule, "protocol": proto, "from": lo, "to": hi, "cidr": cidr, "action": action}


def generate_state(seed=None, problems=None) -> dict:
    rng = random.Random(seed)
    if problems is None:
        problems = rng.sample(PROBLEMS, 2)

    def rid(prefix, n=17):
        return f"{prefix}-0{_hex(rng, n - 1)}"

    vpc = rid("vpc")
    igw, nat = rid("igw"), rid("nat")
    pub_subnet, priv_subnet = rid("subnet"), rid("subnet")
    pub_rt, priv_rt = rid("rtb"), rid("rtb")
    pub_acl, priv_acl = rid("acl"), rid("acl")
    web_sg, api_sg, worker_sg = rid("sg"), rid("sg"), rid("sg")

    def pub_ip():
        return f"54.{rng.randint(80, 240)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"

    public_routes = [{"dest": "10.0.0.0/16", "target": "local"}]
    if "missing_igw_route" not in problems:
        public_routes.append({"dest": "0.0.0.0/0", "target": igw})
    private_routes = [{"dest": "10.0.0.0/16", "target": "local"}]
    if "private_no_egress" not in problems:
        private_routes.append({"dest": "0.0.0.0/0", "target": nat})

    if "nacl_ephemeral_block" in problems:
        pub_egress = [_entry(100, "tcp", 443, 443, "0.0.0.0/0"),
                      _entry(110, "tcp", 80, 80, "0.0.0.0/0"),
                      _entry(120, "all", 0, 65535, "10.0.0.0/16")]
    else:
        pub_egress = [_entry(100, "all", 0, 65535, "0.0.0.0/0")]
    pub_ingress = [_entry(100, "tcp", 443, 443, "0.0.0.0/0"),
                   _entry(110, "tcp", 22, 22, OFFICE_CIDR),
                   _entry(120, "tcp", 1024, 65535, "0.0.0.0/0"),
                   _entry(130, "all", 0, 65535, "10.0.0.0/16")]

    web_ingress = [{"protocol": "tcp", "port": 22, "cidr": OFFICE_CIDR, "source_group": None}]
    if "sg_missing_port" not in problems:
        web_ingress.insert(0, {"protocol": "tcp", "port": 443, "cidr": "0.0.0.0/0", "source_group": None})
    api_source = worker_sg if "api_sg_wrong_source" in problems else web_sg

    web_ip = None if "no_public_ip" in problems else pub_ip()
    eip_alloc = rid("eipalloc")
    return {
        "account": ACCOUNT,
        "region": REGION,
        "problems": problems,
        "vpc": {"id": vpc, "cidr": "10.0.0.0/16", "name": "prod-vpc"},
        "igw": {"id": igw, "vpc": vpc},
        "nat_gateways": [{"id": nat, "subnet": pub_subnet, "state": "available", "public_ip": pub_ip()}],
        "subnets": [
            {"id": pub_subnet, "name": "public-a", "cidr": "10.0.1.0/24", "az": "us-east-1a",
             "route_table": pub_rt, "nacl": pub_acl, "auto_public_ip": False},
            {"id": priv_subnet, "name": "private-a", "cidr": "10.0.2.0/24", "az": "us-east-1a",
             "route_table": priv_rt, "nacl": priv_acl, "auto_public_ip": False},
        ],
        "route_tables": [
            {"id": pub_rt, "name": "public-rt", "routes": public_routes},
            {"id": priv_rt, "name": "private-rt", "routes": private_routes},
        ],
        "nacls": [
            {"id": pub_acl, "name": "public-nacl", "ingress": pub_ingress, "egress": pub_egress},
            {"id": priv_acl, "name": "private-nacl",
             "ingress": [_entry(100, "all", 0, 65535, "0.0.0.0/0")],
             "egress": [_entry(100, "all", 0, 65535, "0.0.0.0/0")]},
        ],
        "security_groups": [
            {"id": web_sg, "name": "web-sg", "ingress": web_ingress},
            {"id": api_sg, "name": "api-sg",
             "ingress": [{"protocol": "tcp", "port": 8080, "cidr": None, "source_group": api_source}]},
            {"id": worker_sg, "name": "worker-sg", "ingress": []},
        ],
        "instances": [
            {"id": rid("i"), "name": "web-1", "subnet": pub_subnet, "private_ip": f"10.0.1.{rng.randint(10, 250)}",
             "public_ip": web_ip, "groups": [web_sg], "state": "running", "listens": [443, 22]},
            {"id": rid("i"), "name": "api-1", "subnet": priv_subnet, "private_ip": f"10.0.2.{rng.randint(10, 120)}",
             "public_ip": None, "groups": [api_sg], "state": "running", "listens": [8080, 22]},
            {"id": rid("i"), "name": "worker-1", "subnet": priv_subnet, "private_ip": f"10.0.2.{rng.randint(130, 250)}",
             "public_ip": None, "groups": [worker_sg], "state": "running", "listens": [22]},
        ],
        "addresses": [{"allocation": eip_alloc, "ip": pub_ip(), "instance": None}],
        "endpoints": ["ssm", "ssmmessages", "ec2messages"],
        "session": None,
    }


# ----------------------------------------------------------------- lookups

def _find(items, key, value):
    return next((i for i in items if i[key] == value), None)


def _instance(state, ref):
    """By id, name, private IP, or public IP."""
    for i in state["instances"]:
        if ref in (i["id"], i["name"], i["private_ip"], i["public_ip"]):
            return i
    return None


def _subnet(state, sid):
    return _find(state["subnets"], "id", sid)


def _sg(state, gid):
    return _find(state["security_groups"], "id", gid)


def _label(state, rid):
    """'sg-0abc (web-sg)' style label for any id with a name."""
    for coll in ("subnets", "route_tables", "nacls", "security_groups", "instances"):
        item = _find(state[coll], "id", rid)
        if item:
            return f"{rid} ({item['name']})"
    return rid


def _in(ip, cidr) -> bool:
    return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)


def _default_route(state, subnet):
    rt = _find(state["route_tables"], "id", subnet["route_table"])
    return next((r["target"] for r in rt["routes"] if r["dest"] == "0.0.0.0/0"), None)


# -------------------------------------------------------------- reachability

def _nacl_allows(state, subnet, egress: bool, port: int, remote_ip: str) -> bool:
    nacl = _find(state["nacls"], "id", subnet["nacl"])
    for e in sorted(nacl["egress" if egress else "ingress"], key=lambda e: e["rule"]):
        proto_ok = e["protocol"] in ("all", "tcp")
        if proto_ok and e["from"] <= port <= e["to"] and _in(remote_ip, e["cidr"]):
            return e["action"] == "allow"
    return False  # the implicit '*' deny


def _sg_allows(state, inst, port: int, src_ip: str, src_inst=None) -> bool:
    for gid in inst["groups"]:
        for rule in _sg(state, gid)["ingress"]:
            if rule["protocol"] not in ("tcp", "all") or rule["port"] not in (port, -1):
                continue
            if rule["cidr"] and _in(src_ip, rule["cidr"]):
                return True
            if rule["source_group"] and src_inst and rule["source_group"] in src_inst["groups"]:
                return True
    return False


def _egress_to_internet(state, inst, port: int) -> str | None:
    """None if inst can open a TCP connection to the internet on port,
    else the (hidden) reason — used by tests, never shown to the player."""
    if inst["state"] != "running":
        return "instance not running"
    subnet = _subnet(state, inst["subnet"])
    if not _nacl_allows(state, subnet, True, port, INTERNET_IP) or \
            not _nacl_allows(state, subnet, False, EPHEMERAL, INTERNET_IP):
        return "nacl"
    target = _default_route(state, subnet)
    if target is None:
        return "no default route"
    if target == state["igw"]["id"]:
        return None if inst["public_ip"] else "no public ip"
    nat = _find(state["nat_gateways"], "id", target)
    if not nat or nat["state"] != "available":
        return "nat missing"
    nat_subnet = _subnet(state, nat["subnet"])
    if nat_subnet["id"] != subnet["id"]:
        # instance -> NAT crosses into the NAT's subnet, and the reply comes back
        if not _nacl_allows(state, nat_subnet, False, port, inst["private_ip"]) or \
                not _nacl_allows(state, nat_subnet, True, EPHEMERAL, inst["private_ip"]):
            return "nat subnet nacl"
    if _default_route(state, nat_subnet) != state["igw"]["id"]:
        return "nat subnet has no igw route"
    if not _nacl_allows(state, nat_subnet, True, port, INTERNET_IP) or \
            not _nacl_allows(state, nat_subnet, False, EPHEMERAL, INTERNET_IP):
        return "nat subnet nacl"
    return None


def _ingress_from_internet(state, inst, port: int, src_ip: str = LAPTOP_IP) -> str | None:
    if inst["state"] != "running":
        return "instance not running"
    if not inst["public_ip"]:
        return "no public ip"
    subnet = _subnet(state, inst["subnet"])
    if _default_route(state, subnet) != state["igw"]["id"]:
        return "no igw route"
    if not _nacl_allows(state, subnet, False, port, src_ip) or \
            not _nacl_allows(state, subnet, True, EPHEMERAL, src_ip):
        return "nacl"
    if not _sg_allows(state, inst, port, src_ip):
        return "security group"
    if port not in inst["listens"]:
        return "refused"
    return None


def _between(state, src, dst, port: int) -> str | None:
    if src["state"] != "running" or dst["state"] != "running":
        return "instance not running"
    s_sub, d_sub = _subnet(state, src["subnet"]), _subnet(state, dst["subnet"])
    if s_sub["id"] != d_sub["id"]:
        # NACLs only apply when traffic crosses a subnet boundary
        if not (_nacl_allows(state, s_sub, True, port, dst["private_ip"]) and
                _nacl_allows(state, d_sub, False, port, src["private_ip"]) and
                _nacl_allows(state, d_sub, True, EPHEMERAL, src["private_ip"]) and
                _nacl_allows(state, s_sub, False, EPHEMERAL, dst["private_ip"])):
            return "nacl"
    if not _sg_allows(state, dst, port, src["private_ip"], src):
        return "security group"
    if port not in dst["listens"]:
        return "refused"
    return None


def reachability(state, source: str, target: str, port: int) -> str | None:
    """Public entry point for goals and tests. source/target are 'internet'
    or an instance name/id. Returns None when the connection works."""
    if source == "internet":
        return _ingress_from_internet(state, _instance(state, target), port)
    src = _instance(state, source)
    if target == "internet":
        return _egress_to_internet(state, src, port)
    return _between(state, src, _instance(state, target), port)


# ------------------------------------------------------------------ helpers

def _args(tokens):
    """--flag=value / --flag value / bare --flag, from normalized tokens."""
    opts = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("--"):
            if "=" in t:
                k, v = t[2:].split("=", 1)
                opts[k] = v
            elif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                opts[t[2:]] = tokens[i + 1]
                i += 1
            else:
                opts[t[2:]] = True
        i += 1
    return opts


def _filters(opts) -> dict:
    """'name=tag:name,values=web-1' -> {'tag:name': ['web-1']} (one filter)."""
    raw = opts.get("filters") or opts.get("filter")
    if not isinstance(raw, str) or "values=" not in raw:
        return {}
    name_part, values_part = raw.split(",values=", 1) if ",values=" in raw else (raw, "")
    name = name_part.replace("name=", "", 1)
    return {name: values_part.split(",")}


def _indent(text, pad="  "):
    return "\n".join(pad + line for line in text.splitlines())


def _error(code, op, message):
    return f"An error occurred ({code}) when calling the {op} operation: {message}"


def _timeout(host, port):
    return f"curl: (28) Failed to connect to {host} port {port} after 5002 ms: Timeout was reached"


# ----------------------------------------------------------------- describe

def cmd_describe_instances(state, opts) -> str:
    rows = []
    wanted_ids = str(opts.get("instance-ids", "")).split(",") if opts.get("instance-ids") else None
    flt = _filters(opts)
    for i in state["instances"]:
        if wanted_ids and i["id"] not in wanted_ids:
            continue
        keys = {"tag:name": i["name"], "subnet-id": i["subnet"], "vpc-id": state["vpc"]["id"],
                "instance-state-name": i["state"], "instance-id": i["id"]}
        if any(keys.get(k) not in v for k, v in flt.items()):
            continue
        rows.append([i["id"], i["name"], i["state"], _label(state, i["subnet"]), i["private_ip"],
                     i["public_ip"] or "-", ", ".join(_label(state, g) for g in i["groups"])])
    if wanted_ids and not rows:
        return _error("InvalidInstanceID.NotFound", "DescribeInstances",
                      f"The instance ID '{wanted_ids[0]}' does not exist")
    return render_table(["INSTANCE ID", "NAME", "STATE", "SUBNET", "PRIVATE IP", "PUBLIC IP", "SECURITY GROUPS"], rows)


def cmd_describe_vpcs(state) -> str:
    v = state["vpc"]
    return render_table(["VPC ID", "NAME", "CIDR", "STATE"], [[v["id"], v["name"], v["cidr"], "available"]])


def cmd_describe_subnets(state, opts) -> str:
    flt = _filters(opts)
    rows = []
    for s in state["subnets"]:
        keys = {"vpc-id": state["vpc"]["id"], "subnet-id": s["id"], "tag:name": s["name"]}
        if any(keys.get(k) not in v for k, v in flt.items()):
            continue
        rows.append([s["id"], s["name"], s["cidr"], s["az"], _label(state, s["route_table"]),
                     _label(state, s["nacl"]), "yes" if s["auto_public_ip"] else "no"])
    return render_table(["SUBNET ID", "NAME", "CIDR", "AZ", "ROUTE TABLE", "NETWORK ACL", "AUTO-ASSIGN PUBLIC IP"], rows)


def _assoc_filter(state, opts, key):
    flt = _filters(opts)
    wanted = flt.get("association.subnet-id")
    ids = [s[key] for s in state["subnets"] if not wanted or s["id"] in wanted]
    extra = flt.get("route-table-id") or flt.get("network-acl-id")
    return [i for i in ids if not extra or i in extra]


def cmd_describe_route_tables(state, opts) -> str:
    blocks = []
    for rid in _assoc_filter(state, opts, "route_table"):
        rt = _find(state["route_tables"], "id", rid)
        subnets = ", ".join(_label(state, s["id"]) for s in state["subnets"] if s["route_table"] == rid)
        rows = [[r["dest"], r["target"], "active"] for r in rt["routes"]]
        blocks.append(f"{rt['id']} ({rt['name']})   associated with: {subnets}\n" +
                      _indent(render_table(["DESTINATION", "TARGET", "STATE"], rows)))
    return "\n\n".join(blocks) or "(no route tables match)"


def _acl_rows(entries):
    rows = [[str(e["rule"]), e["protocol"], "all" if e["protocol"] == "all" else
             (str(e["from"]) if e["from"] == e["to"] else f"{e['from']}-{e['to']}"), e["cidr"], e["action"].upper()]
            for e in sorted(entries, key=lambda e: e["rule"])]
    rows.append(["*", "all", "all", "0.0.0.0/0", "DENY"])
    return rows


def cmd_describe_network_acls(state, opts) -> str:
    blocks = []
    for aid in _assoc_filter(state, opts, "nacl"):
        acl = _find(state["nacls"], "id", aid)
        subnets = ", ".join(_label(state, s["id"]) for s in state["subnets"] if s["nacl"] == aid)
        blocks.append(
            f"{acl['id']} ({acl['name']})   associated with: {subnets}\n"
            f"  INBOUND\n" + _indent(render_table(["RULE", "PROTOCOL", "PORTS", "SOURCE", "ACTION"], _acl_rows(acl["ingress"]))) +
            f"\n  OUTBOUND\n" + _indent(render_table(["RULE", "PROTOCOL", "PORTS", "DESTINATION", "ACTION"], _acl_rows(acl["egress"]))))
    return "\n\n".join(blocks)


def cmd_describe_security_groups(state, opts) -> str:
    wanted = str(opts.get("group-ids", "")).split(",") if opts.get("group-ids") else None
    flt = _filters(opts)
    blocks = []
    for g in state["security_groups"]:
        if wanted and g["id"] not in wanted:
            continue
        if flt.get("group-name") and g["name"] not in flt["group-name"]:
            continue
        rows = [[r["protocol"], str(r["port"]), r["cidr"] or _label(state, r["source_group"])] for r in g["ingress"]]
        inbound = _indent(render_table(["PROTOCOL", "PORT", "SOURCE"], rows)) if rows else "  (no inbound rules — nothing can connect in)"
        blocks.append(f"{g['id']} ({g['name']})   vpc: {state['vpc']['id']}\n  INBOUND\n{inbound}\n"
                      f"  OUTBOUND\n  all traffic -> 0.0.0.0/0")
    if wanted and not blocks:
        return _error("InvalidGroup.NotFound", "DescribeSecurityGroups", f"The security group '{wanted[0]}' does not exist")
    return "\n\n".join(blocks)


def cmd_describe_igws(state) -> str:
    return render_table(["INTERNET GATEWAY ID", "ATTACHED VPC", "STATE"],
                        [[state["igw"]["id"], state["igw"]["vpc"], "available"]])


def cmd_describe_nats(state) -> str:
    if not state["nat_gateways"]:
        return "(no NAT gateways)"
    return render_table(["NAT GATEWAY ID", "SUBNET", "STATE", "PUBLIC IP"],
                        [[n["id"], _label(state, n["subnet"]), n["state"], n["public_ip"]] for n in state["nat_gateways"]])


def cmd_describe_addresses(state) -> str:
    return render_table(["ALLOCATION ID", "PUBLIC IP", "ASSOCIATED INSTANCE"],
                        [[a["allocation"], a["ip"], _label(state, a["instance"]) if a["instance"] else "-"]
                         for a in state["addresses"]])


def cmd_describe_endpoints(state) -> str:
    return render_table(["SERVICE", "TYPE", "STATE"],
                        [[f"com.amazonaws.{REGION}.{e}", "Interface", "available"] for e in state["endpoints"]])


# ------------------------------------------------------------------ mutate

def _route_table_or_error(state, opts, op):
    rt = _find(state["route_tables"], "id", opts.get("route-table-id"))
    if not rt:
        return None, _error("InvalidRouteTableID.NotFound", op,
                            f"The routeTable ID '{opts.get('route-table-id')}' does not exist")
    return rt, None


def cmd_route(state, opts, replace: bool) -> str:
    op = "ReplaceRoute" if replace else "CreateRoute"
    rt, err = _route_table_or_error(state, opts, op)
    if err:
        return err
    dest = opts.get("destination-cidr-block")
    target = opts.get("gateway-id") or opts.get("nat-gateway-id")
    if not dest or not target:
        return "usage: --route-table-id <rtb> --destination-cidr-block <cidr> (--gateway-id <igw> | --nat-gateway-id <nat>)"
    if opts.get("gateway-id") and target != state["igw"]["id"]:
        return _error("InvalidGatewayID.NotFound", op, f"The gateway ID '{target}' does not exist")
    if opts.get("nat-gateway-id") and not _find(state["nat_gateways"], "id", target):
        return _error("InvalidNatGatewayID.NotFound", op, f"The natGateway ID '{target}' does not exist")
    existing = next((r for r in rt["routes"] if r["dest"] == dest), None)
    if existing and not replace:
        return _error("RouteAlreadyExists", op,
                      f"The route identified by {dest} already exists. (Use replace-route to change its target.)")
    if not existing and replace:
        return _error("InvalidRoute.NotFound", op, f"no route with destination-cidr-block {dest} in the route table {rt['id']}")
    if existing:
        existing["target"] = target
    else:
        rt["routes"].append({"dest": dest, "target": target})
    return '{\n    "Return": true\n}'


def _parse_port(opts):
    port = opts.get("port")
    if port in (None, True):
        return None
    try:
        return int(str(port).split("-")[0])
    except ValueError:
        return None


def cmd_sg_ingress(state, opts, revoke: bool) -> str:
    op = "RevokeSecurityGroupIngress" if revoke else "AuthorizeSecurityGroupIngress"
    g = _sg(state, opts.get("group-id"))
    if not g:
        return _error("InvalidGroup.NotFound", op, f"The security group '{opts.get('group-id')}' does not exist")
    port = _parse_port(opts)
    proto = opts.get("protocol", "tcp")
    cidr, source = opts.get("cidr"), opts.get("source-group")
    if port is None or not (cidr or source):
        return "usage: --group-id <sg> --protocol tcp --port <n> (--cidr <cidr> | --source-group <sg>)"
    if source and not _sg(state, source):
        return _error("InvalidGroup.NotFound", op, f"The security group '{source}' does not exist")
    rule = {"protocol": proto, "port": port, "cidr": cidr if isinstance(cidr, str) else None,
            "source_group": source if isinstance(source, str) else None}
    match = next((r for r in g["ingress"] if r == rule), None)
    if revoke:
        if not match:
            return _error("InvalidPermission.NotFound", op, "The specified rule does not exist in this security group.")
        g["ingress"].remove(match)
        return '{\n    "Return": true\n}'
    if match:
        return _error("InvalidPermission.Duplicate", op, "the specified rule already exists")
    g["ingress"].append(rule)
    return '{\n    "Return": true,\n    "SecurityGroupRules": [{"IsEgress": false, "IpProtocol": "' + proto + '", "FromPort": ' + str(port) + '}]\n}'


def cmd_nacl_entry(state, opts, replace: bool) -> str:
    op = "ReplaceNetworkAclEntry" if replace else "CreateNetworkAclEntry"
    acl = _find(state["nacls"], "id", opts.get("network-acl-id"))
    if not acl:
        return _error("InvalidNetworkAclID.NotFound", op, f"The network ACL '{opts.get('network-acl-id')}' does not exist")
    try:
        rule_no = int(opts.get("rule-number"))
    except (TypeError, ValueError):
        return "usage: --network-acl-id <acl> --rule-number <n> --protocol tcp --port-range From=<a>,To=<b> --cidr-block <cidr> --rule-action allow --egress|--ingress"
    proto = str(opts.get("protocol", "tcp"))
    proto = "all" if proto in ("-1", "all") else proto
    lo, hi = 0, 65535
    pr = opts.get("port-range")
    if isinstance(pr, str):
        parts = dict(p.split("=", 1) for p in pr.split(",") if "=" in p)
        try:
            lo, hi = int(parts.get("from", 0)), int(parts.get("to", 65535))
        except ValueError:
            return "--port-range must look like From=1024,To=65535"
    elif proto != "all":
        return "--port-range From=<a>,To=<b> is required for tcp rules"
    direction = "egress" if opts.get("egress") else "ingress"
    entries = acl[direction]
    existing = next((e for e in entries if e["rule"] == rule_no), None)
    if replace and not existing:
        return _error("InvalidNetworkAclEntry.NotFound", op, f"The network acl entry identified by {rule_no} does not exist")
    if not replace and existing:
        return _error("NetworkAclEntryAlreadyExists", op, f"The network acl entry identified by {rule_no} already exists")
    new = _entry(rule_no, proto, lo, hi, str(opts.get("cidr-block", "0.0.0.0/0")),
                 "deny" if opts.get("rule-action") == "deny" else "allow")
    if existing:
        entries[entries.index(existing)] = new
    else:
        entries.append(new)
    return ""


def cmd_associate_address(state, opts) -> str:
    inst = _instance(state, opts.get("instance-id"))
    if not inst:
        return _error("InvalidInstanceID.NotFound", "AssociateAddress", f"The instance ID '{opts.get('instance-id')}' does not exist")
    addr = _find(state["addresses"], "allocation", opts.get("allocation-id"))
    if not addr:
        return _error("InvalidAllocationID.NotFound", "AssociateAddress", f"The allocation ID '{opts.get('allocation-id')}' does not exist")
    for other in state["instances"]:
        if other["public_ip"] == addr["ip"]:
            other["public_ip"] = None
    addr["instance"] = inst["id"]
    inst["public_ip"] = addr["ip"]
    return '{\n    "AssociationId": "eipassoc-0' + addr["allocation"][-8:] + '"\n}'


def cmd_create_nat(state, opts) -> str:
    subnet = _subnet(state, opts.get("subnet-id"))
    if not subnet:
        return _error("InvalidSubnetID.NotFound", "CreateNatGateway", f"The subnet ID '{opts.get('subnet-id')}' does not exist")
    addr = _find(state["addresses"], "allocation", opts.get("allocation-id"))
    if not addr or addr["instance"]:
        return _error("InvalidAllocationID.NotFound", "CreateNatGateway", "an unassociated --allocation-id is required")
    nat_id = "nat-0" + addr["allocation"][-16:]
    addr["instance"] = nat_id
    state["nat_gateways"].append({"id": nat_id, "subnet": subnet["id"], "state": "available", "public_ip": addr["ip"]})
    return (f'{{\n    "NatGateway": {{"NatGatewayId": "{nat_id}", "State": "pending", "SubnetId": "{subnet["id"]}"}}\n}}\n'
            "(In the sandbox it's available immediately; in real AWS this takes a minute or two. "
            "Note it costs money every hour it exists.)")


def cmd_terminate(state, opts) -> str:
    inst = _instance(state, opts.get("instance-ids"))
    if not inst:
        return _error("InvalidInstanceID.NotFound", "TerminateInstances", f"The instance ID '{opts.get('instance-ids')}' does not exist")
    inst["state"] = "terminated"
    inst["public_ip"] = None
    return f"{inst['id']}  running -> shutting-down"


# ----------------------------------------------------------- connectivity

def _parse_target(url: str):
    """curl target -> (host, port)."""
    scheme = "https"
    if "://" in url:
        scheme, url = url.split("://", 1)
    hostport = url.split("/", 1)[0]
    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
        return host, int(port) if port.isdigit() else 443
    return hostport, 443 if scheme == "https" else 80


def _connect(state, source_inst, host: str, port: int):
    """Returns (ok, reason) for a TCP connect from the laptop (source_inst
    None) or from an instance, to a host or IP."""
    target = _instance(state, host)
    if source_inst is None:
        if target is None:
            return True, None  # somewhere on the internet: fine from the laptop
        if host != target["public_ip"]:
            return False, "unroutable"  # private IP / name from the internet
        reason = _ingress_from_internet(state, target, port)
        return reason is None, reason
    if target is None:
        reason = _egress_to_internet(state, source_inst, port)
        return reason is None, reason
    if host == target["public_ip"] and source_inst is not target:
        reason = _egress_to_internet(state, source_inst, port) or _ingress_from_internet(state, target, port, INTERNET_IP)
        return reason is None, reason
    reason = _between(state, source_inst, target, port) if source_inst is not target else None
    return reason is None, reason


def _response_body(state, host):
    target = _instance(state, host)
    if target and target["name"] == "web-1":
        return "<!doctype html><title>Shop</title><h1>Welcome to the shop</h1>"
    if target and target["name"] == "api-1":
        return '{"status":"ok","service":"api"}'
    return "<!doctype html><html>... (200 OK)"


def cmd_curl(state, source_inst, args) -> str:
    urls = [a for a in args if not a.startswith("-") and not a.isdigit()]
    if not urls:
        return "curl: no URL specified"
    host, port = _parse_target(urls[0])
    if not host:
        return "curl: (3) URL rejected: No host part in the URL"
    if host == "ifconfig.me":
        if source_inst is None:
            return LAPTOP_IP
        if _egress_to_internet(state, source_inst, 443):
            return _timeout(host, port)
        if source_inst["public_ip"]:
            return source_inst["public_ip"]
        subnet = _subnet(state, source_inst["subnet"])
        return _find(state["nat_gateways"], "id", _default_route(state, subnet))["public_ip"]
    target = _instance(state, host)
    if source_inst is None and target and host == target["name"]:
        return f"curl: (6) Could not resolve host: {host}"
    ok, reason = _connect(state, source_inst, host, port)
    if ok:
        return _response_body(state, host)
    if reason == "refused":
        return f"curl: (7) Failed to connect to {host} port {port}: Connection refused"
    return _timeout(host, port)


def cmd_nc(state, source_inst, args) -> str:
    positional = [a for a in args if not a.startswith("-")]
    if len(positional) < 2 or not positional[1].isdigit():
        return "usage: nc -zv <host> <port>"
    host, port = positional[0], int(positional[1])
    ok, reason = _connect(state, source_inst, host, port)
    if ok:
        return f"Connection to {host} {port} port [tcp/*] succeeded!"
    if reason == "refused":
        return f"nc: connect to {host} port {port} (tcp) failed: Connection refused"
    return f"nc: connect to {host} port {port} (tcp) failed: Connection timed out"


def cmd_ssh(state, args) -> str:
    targets = [a for a in args if not a.startswith("-") and not a.endswith(".pem")]
    if not targets:
        return "usage: ssh ec2-user@<public-ip>"
    host = targets[0].split("@")[-1]
    ok, reason = _connect(state, None, host, 22)
    if not ok:
        return f"ssh: connect to host {host} port 22: {'Connection refused' if reason == 'refused' else 'Connection timed out'}"
    inst = _instance(state, host)
    return (f"   ,     #_\n   ~\\_  ####_        Amazon Linux 2023\n  ~~  \\_#####\\\n"
            f"[ec2-user@ip-{inst['private_ip'].replace('.', '-')} ~]$ \n"
            "(Connected. The sandbox doesn't keep SSH shells open — use 'aws ssm start-session --target "
            f"{inst['id']}' for a shell on the instance.)")


def handle_session(state, tokens) -> str:
    inst = _instance(state, state["session"])
    if tokens[0] == "sudo":
        tokens = tokens[1:] or ["sudo"]
    cmd, args = tokens[0], tokens[1:]
    if cmd in ("exit", "logout"):
        state["session"] = None
        return f"\nExiting session with sessionId: ec2-user-0{inst['id'][-8:]}."
    if cmd == "curl":
        return cmd_curl(state, inst, args)
    if cmd in ("nc", "ncat"):
        return cmd_nc(state, inst, args)
    if cmd == "hostname":
        return f"ip-{inst['private_ip'].replace('.', '-')}.ec2.internal"
    if cmd in ("dnf", "yum") and args[:1] in (["check-update"], ["update"], ["upgrade"], ["makecache"]):
        reason = _egress_to_internet(state, inst, 443)
        if reason is None:
            return ("Amazon Linux 2023 repository                    41 MB/s |  28 MB     00:00\n"
                    "Last metadata expiration check: 0:00:01 ago.\n"
                    "openssl.x86_64                 1:3.0.8-1.amzn2023.0.14        amazonlinux")
        return (f"Errors during downloading metadata for repository 'amazonlinux':\n"
                f"  - Curl error (28): Timeout was reached for https://{REPO_HOST}/al2023/core/mirrors/latest/x86_64/mirror.list "
                f"[Failed to connect to {REPO_HOST} port 443 after 30000 ms: Timeout was reached]\n"
                "Error: Failed to download metadata for repo 'amazonlinux'")
    if cmd == "ss":
        rows = [["tcp", "LISTEN", f"0.0.0.0:{p}", "sshd" if p == 22 else inst["name"].split("-")[0]] for p in inst["listens"]]
        return render_table(["NETID", "STATE", "LOCAL ADDRESS:PORT", "PROCESS"], rows)
    if cmd == "aws":
        return handle_aws(state, args)
    return (f"{cmd}: not simulated inside the session. Try: curl <url>, nc -zv <host> <port>, "
            "sudo dnf check-update, ss -tulnp, hostname, exit")


def cmd_start_session(state, opts) -> str:
    inst = _instance(state, opts.get("target"))
    if not inst:
        return _error("InvalidInstanceId", "StartSession", f"Instance {opts.get('target')} is not connected to SSM")
    if inst["state"] != "running":
        return _error("TargetNotConnected", "StartSession", f"{inst['id']} is not connected.")
    state["session"] = inst["id"]
    return (f"Starting session with SessionId: ec2-user-0{inst['id'][-8:]}\n"
            f"sh-5.2$  (you are now on {inst['name']}, {inst['private_ip']} — 'exit' to leave the session)")


# ---------------------------------------------------------------- dispatch

def handle_aws(state, tokens) -> str:
    if not tokens:
        return HELP_TEXT
    service, action, rest = tokens[0], tokens[1] if len(tokens) > 1 else "", tokens[2:]
    opts = _args(rest)
    if service == "sts" and action == "get-caller-identity":
        return json.dumps({"UserId": "AIDAEXAMPLE123", "Account": state["account"],
                           "Arn": f"arn:aws:iam::{state['account']}:user/oncall"}, indent=4)
    if service == "ssm" and action == "start-session":
        return cmd_start_session(state, opts)
    if service == "ec2":
        table = {
            "describe-instances": lambda: cmd_describe_instances(state, opts),
            "describe-vpcs": lambda: cmd_describe_vpcs(state),
            "describe-subnets": lambda: cmd_describe_subnets(state, opts),
            "describe-route-tables": lambda: cmd_describe_route_tables(state, opts),
            "describe-network-acls": lambda: cmd_describe_network_acls(state, opts),
            "describe-security-groups": lambda: cmd_describe_security_groups(state, opts),
            "describe-internet-gateways": lambda: cmd_describe_igws(state),
            "describe-nat-gateways": lambda: cmd_describe_nats(state),
            "describe-addresses": lambda: cmd_describe_addresses(state),
            "describe-vpc-endpoints": lambda: cmd_describe_endpoints(state),
            "create-route": lambda: cmd_route(state, opts, replace=False),
            "replace-route": lambda: cmd_route(state, opts, replace=True),
            "authorize-security-group-ingress": lambda: cmd_sg_ingress(state, opts, revoke=False),
            "revoke-security-group-ingress": lambda: cmd_sg_ingress(state, opts, revoke=True),
            "replace-network-acl-entry": lambda: cmd_nacl_entry(state, opts, replace=True),
            "create-network-acl-entry": lambda: cmd_nacl_entry(state, opts, replace=False),
            "associate-address": lambda: cmd_associate_address(state, opts),
            "create-nat-gateway": lambda: cmd_create_nat(state, opts),
            "terminate-instances": lambda: cmd_terminate(state, opts),
        }
        if action in table:
            return table[action]()
    return f"'aws {service} {action}' isn't simulated in the sandbox. Type 'help' for supported commands."


def handle_command(state: dict, raw: str):
    norm = normalize(raw)
    tokens = norm.split()
    if state.get("session"):
        if norm in {"help", "?"}:
            return HELP_TEXT
        return handle_session(state, tokens) if tokens else ""
    if norm in {"exit", "quit", ":q"}:
        return None
    if norm in {"help", "?"} or not tokens:
        return HELP_TEXT
    cmd, args = tokens[0], tokens[1:]
    if cmd == "aws":
        return handle_aws(state, args)
    if cmd == "curl":
        return cmd_curl(state, None, args)
    if cmd in ("nc", "ncat"):
        return cmd_nc(state, None, args)
    if cmd == "ssh":
        return cmd_ssh(state, args)
    if cmd == "ping":
        return ("(ping uses ICMP, which these security groups don't allow — a failed ping proves nothing on AWS. "
                "Test the real port: nc -zv <ip> <port> or curl.)")
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


# ------------------------------------------------------- mystery/sandbox hooks

def placeholders(state: dict) -> dict:
    """Ids a mystery's stored solution refers to ({web_sg} etc.)."""
    by_name = {i["name"]: i for i in state["instances"]}
    rts = {rt["name"]: rt["id"] for rt in state["route_tables"]}
    acls = {a["name"]: a["id"] for a in state["nacls"]}
    sgs = {g["name"]: g["id"] for g in state["security_groups"]}
    return {
        "web_id": by_name["web-1"]["id"], "api_id": by_name["api-1"]["id"], "worker_id": by_name["worker-1"]["id"],
        "web_ip": by_name["web-1"]["public_ip"] or "", "igw_id": state["igw"]["id"],
        "nat_id": state["nat_gateways"][0]["id"] if state["nat_gateways"] else "",
        "public_rt": rts["public-rt"], "private_rt": rts["private-rt"],
        "public_nacl": acls["public-nacl"], "private_nacl": acls["private-nacl"],
        "web_sg": sgs["web-sg"], "api_sg": sgs["api-sg"], "worker_sg": sgs["worker-sg"],
        "eip_alloc": state["addresses"][0]["allocation"],
        "public_subnet": state["subnets"][0]["id"], "private_subnet": state["subnets"][1]["id"],
    }


GOAL_CHECKS = {
    "reachable": lambda state, g: reachability(state, g["from"], g["to"], g["port"]) is None,
    "not_reachable": lambda state, g: reachability(state, g["from"], g["to"], g["port"]) is not None,
}


def collateral_issues(state: dict) -> set:
    """Dangerous states a careless fix leaves behind. Mysteries report any
    that weren't there at the start."""
    issues = set()
    for g in state["security_groups"]:
        for r in g["ingress"]:
            if r["cidr"] == "0.0.0.0/0" and r["port"] not in (80, 443):
                issues.add(f"opened port {r['port']} on {g['name']} to the entire internet (0.0.0.0/0) — "
                           "scanners find exposed SSH/database ports within minutes")
    for i in state["instances"]:
        if i["state"] == "terminated":
            issues.add(f"terminated {i['name']} — its data and IP are gone; that doesn't fix a network problem")
    for acl in state["nacls"]:
        for e in acl["ingress"]:
            if e["action"] == "allow" and e["protocol"] == "all" and e["cidr"] == "0.0.0.0/0" and acl["name"] == "public-nacl":
                issues.add("allowed ALL inbound traffic from the internet on public-nacl — the fix needed one port range, not everything")
    return issues


def describe_state(state: dict) -> list:
    return [
        f"You're signed in to AWS account {state['account']} ({state['region']}), VPC {state['vpc']['id']} (prod-vpc).",
        "Three instances: web-1 (public, serves HTTPS), api-1 (private, :8080 for web-1), worker-1 (private, pulls packages).",
        f"Your laptop's public IP is {LAPTOP_IP} (inside the office range {OFFICE_CIDR}).",
        "Two things in this network are broken. Find which layer drops the traffic, and fix it.",
    ]


def run_sandbox() -> None:
    run_loop("aws", "account", generate_state, handle_command, describe_state)
