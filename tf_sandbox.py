"""
Terraform sandbox — a working directory for the shop's production stack,
modelled in three layers that real Terraform compares on every plan:
  config   what the code declares (address -> type and attributes)
  tfstate  what Terraform remembers (address -> real id and attributes)
  real     what actually exists in the AWS account (id -> type and attributes)

`terraform plan` really diffs them: a resource in config but not in state
is a create, one in state but not in config is a destroy, a difference
between config and the real object is an update, or a replacement when the
attribute can't change in place. Two of five problems are seeded:
  drift              someone opened SSH on the web security group in the console
  stale_lock         a cancelled CI run left the state locked
  renamed            the code renamed aws_instance.web, so plan wants to replace it
  unmanaged_bucket   the code declares a bucket that exists but isn't in state
  handed_over        the reports database moved to another team's stack and
                     was deleted from this code, so plan wants to destroy it

Nothing here runs real Terraform or touches a cloud account.
"""

import random
import shlex

from sandbox_common import render_table, run_loop

PROBLEMS = ["drift", "stale_lock", "renamed", "unmanaged_bucket", "handed_over"]

REPORTS = {
    "drift": "Security says port 22 on the web servers is open to the internet, and nobody changed the code.",
    "stale_lock": "Every Terraform pipeline since 02:14 fails with a state lock error.",
    "renamed": "A code-tidying pull request renamed the web instance; review the plan before anyone applies it.",
    "unmanaged_bucket": "The apply that adds the assets bucket fails every time, saying the bucket already exists.",
    "handed_over": "The reports database now belongs to the data team's stack and was removed from this code. "
                   "Make sure this stack lets go of it without harming it.",
}

# Attributes that can't change in place: a new value means destroy and re-create.
FORCE_NEW = {
    "aws_vpc": {"cidr_block"},
    "aws_security_group": {"name"},
    "aws_instance": {"ami"},
    "aws_s3_bucket": {"bucket"},
    "aws_db_instance": {"identifier", "engine"},
}
# The attribute AWS uses as a unique name, if any: creating a second
# resource with the same value fails with an "already exists" error.
IDENTITY = {"aws_security_group": "name", "aws_s3_bucket": "bucket", "aws_db_instance": "identifier"}

LOCK_PATH = "shop-tfstate/prod/terraform.tfstate"

HELP_TEXT = """Supported commands (a simulated Terraform working directory; nothing real is changed):
  terraform init | validate | plan [-refresh-only] [-lock=false]
  terraform state list | state show <addr> | state pull
  cat main.tf     ls
  help | exit          (pipes work: terraform state list | grep aws_instance)"""


def _hexid(rng, n=17):
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _base(rng):
    """The stack as it was before any problem: (config, tfstate, real)."""
    ids = {
        "vpc": f"vpc-0{_hexid(rng)}",
        "sg": f"sg-0{_hexid(rng)}",
        "web": f"i-0{_hexid(rng)}",
        "reports_sg": f"sg-0{_hexid(rng)}",
    }
    resources = {
        "aws_vpc.main": (ids["vpc"], {"cidr_block": "10.0.0.0/16", "name": "shop-prod"}),
        "aws_security_group.web": (ids["sg"], {"name": "shop-web", "ingress_ports": [80, 443]}),
        "aws_instance.web": (ids["web"], {"ami": "ami-0c55b159cbfafe1f0", "instance_type": "t3.small",
                                          "name": "shop-web"}),
        "aws_s3_bucket.logs": ("shop-logs-prod", {"bucket": "shop-logs-prod"}),
        "aws_db_instance.main": ("shop-db", {"identifier": "shop-db", "engine": "postgres",
                                             "instance_class": "db.t3.medium"}),
    }
    config, tfstate, real = {}, {}, {}
    for addr, (rid, attrs) in resources.items():
        rtype = addr.split(".")[0]
        config[addr] = {"type": rtype, "attrs": dict(attrs)}
        tfstate[addr] = {"id": rid, "attrs": dict(attrs)}
        real[rid] = {"type": rtype, "attrs": dict(attrs)}
    return config, tfstate, real


def generate_state(seed=None, problems=None) -> dict:
    """Random 2 problems by default; mystery incidents pass an explicit list."""
    rng = random.Random(seed)
    problems = list(problems) if problems is not None else rng.sample(PROBLEMS, k=2)
    config, tfstate, real = _base(rng)
    state = {"seed": seed, "problems": problems, "config": config, "tfstate": tfstate, "real": real,
             "lock": None, "lock_bypassed": False, "next_id": rng.randrange(1 << 40)}

    if "drift" in problems:
        sg = tfstate["aws_security_group.web"]["id"]
        real[sg]["attrs"]["ingress_ports"] = [80, 443, 22]
    if "stale_lock" in problems:
        state["lock"] = {"id": f"{_hexid(rng, 8)}-{_hexid(rng, 4)}-{_hexid(rng, 4)}-{_hexid(rng, 4)}-{_hexid(rng, 12)}",
                         "who": "runner@ci-runner-7", "operation": "OperationTypeApply",
                         "created": "2026-10-06 02:14:09.411 +0000 UTC", "version": "1.9.5"}
    if "renamed" in problems:
        config["aws_instance.app"] = config.pop("aws_instance.web")
    if "unmanaged_bucket" in problems:
        config["aws_s3_bucket.assets"] = {"type": "aws_s3_bucket", "attrs": {"bucket": "shop-assets-prod"}}
        real["shop-assets-prod"] = {"type": "aws_s3_bucket", "attrs": {"bucket": "shop-assets-prod"}}
    if "handed_over" in problems:
        attrs = {"identifier": "shop-reports", "engine": "postgres", "instance_class": "db.r6g.large"}
        tfstate["aws_db_instance.reports"] = {"id": "shop-reports", "attrs": dict(attrs)}
        real["shop-reports"] = {"type": "aws_db_instance", "attrs": dict(attrs)}

    state["baseline_ids"] = sorted(real)
    return state


# ---------------------------------------------------------------------- plan

def compute_plan(state: dict) -> dict:
    """{"changes": [(action, addr, detail)], "drifted": [(addr, attr, old, new)]}.
    Actions: create, update, replace, destroy. Like real Terraform, the plan
    compares the code with the refreshed (real) objects, not with the state."""
    changes, drifted = [], []
    tfstate, real = state["tfstate"], state["real"]
    for addr, res in state["config"].items():
        st = tfstate.get(addr)
        obj = real.get(st["id"]) if st else None
        if st is None or obj is None:
            changes.append(("create", addr, {"attrs": res["attrs"], "gone": st is not None}))
            continue
        diffs = {k: (obj["attrs"].get(k), v) for k, v in res["attrs"].items() if obj["attrs"].get(k) != v}
        if diffs:
            force = any(k in FORCE_NEW.get(res["type"], ()) for k in diffs)
            changes.append(("replace" if force else "update", addr, {"id": st["id"], "diffs": diffs}))
    for addr, st in tfstate.items():
        if addr not in state["config"]:
            changes.append(("destroy", addr, {"id": st["id"], "attrs": st["attrs"]}))
        obj = real.get(st["id"])
        if obj is not None:
            for k, v in obj["attrs"].items():
                if st["attrs"].get(k) != v:
                    drifted.append((addr, k, st["attrs"].get(k), v))
    return {"changes": changes, "drifted": drifted}


def _fmt(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    if isinstance(value, str):
        return f'"{value}"'
    return "null" if value is None else str(value)


def _block(addr: str, sign: str, attrs: dict, rid=None, diffs=None) -> list:
    rtype, name = addr.split(".", 1)
    lines = [f'  {sign} resource "{rtype}" "{name}" {{']
    keys = sorted(set(attrs) | ({"id"} if rid else set()))
    width = max(len(k) for k in keys)
    for k in keys:
        if k == "id":
            lines.append(f'        {"id".ljust(width)} = "{rid}"')
        elif diffs and k in diffs:
            old, new = diffs[k]
            tail = " # forces replacement" if k in FORCE_NEW.get(rtype, ()) else ""
            lines.append(f"      ~ {k.ljust(width)} = {_fmt(old)} -> {_fmt(new)}{tail}")
        elif sign in ("+", "-"):
            lines.append(f"      {sign} {k.ljust(width)} = {_fmt(attrs[k])}")
    lines.append("    }")
    return lines


SYMBOLS = {"create": "+", "update": "~", "replace": "-/+", "destroy": "-"}
VERBS = {"create": "will be created", "update": "will be updated in-place",
         "replace": "must be replaced", "destroy": "will be destroyed"}


def render_plan(state: dict, plan: dict, refresh_only=False) -> str:
    out = [f"{addr}: Refreshing state... [id={st['id']}]" for addr, st in sorted(state["tfstate"].items())]
    out.append("")
    if plan["drifted"]:
        out += ["Note: Objects have changed outside of Terraform", ""]
        for addr, attr, old, new in plan["drifted"]:
            out.append(f"  # {addr} has changed")
            out.append(f"      ~ {attr} = {_fmt(old)} -> {_fmt(new)}")
        out.append("")
    if refresh_only:
        if not plan["drifted"]:
            out.append("No changes. Your infrastructure still matches the configuration.")
        else:
            out.append("This is a refresh-only plan, so Terraform will not take any actions to undo these.")
        return "\n".join(out)
    if not plan["changes"]:
        out.append("No changes. Your infrastructure matches the configuration.")
        return "\n".join(out)
    out += ["Terraform will perform the following actions:", ""]
    counts = {"add": 0, "change": 0, "destroy": 0}
    for action, addr, d in plan["changes"]:
        reason = ""
        if action == "create" and d.get("gone"):
            reason = " (the remote object no longer exists)"
        elif action == "destroy":
            reason = " (because it is not in configuration)"
        out.append(f"  # {addr} {VERBS[action]}{reason}")
        if action == "create":
            out += _block(addr, "+", d["attrs"])
            counts["add"] += 1
        elif action == "destroy":
            out += _block(addr, "-", d["attrs"], d["id"])
            counts["destroy"] += 1
        elif action == "update":
            out += _block(addr, "~", {k: v[1] for k, v in d["diffs"].items()}, d["id"], d["diffs"])
            counts["change"] += 1
        else:
            out += _block(addr, "-/+", {k: v[1] for k, v in d["diffs"].items()}, d["id"], d["diffs"])
            counts["add"] += 1
            counts["destroy"] += 1
        out.append("")
    out.append(f"Plan: {counts['add']} to add, {counts['change']} to change, {counts['destroy']} to destroy.")
    return "\n".join(out)


def _lock_error(state: dict) -> str:
    lock = state["lock"]
    return "\n".join([
        "╷",
        "│ Error: Error acquiring the state lock",
        "│",
        "│ Error message: ConditionalCheckFailedException: The conditional request failed",
        "│ Lock Info:",
        f"│   ID:        {lock['id']}",
        f"│   Path:      {LOCK_PATH}",
        f"│   Operation: {lock['operation']}",
        f"│   Who:       {lock['who']}",
        f"│   Version:   {lock['version']}",
        f"│   Created:   {lock['created']}",
        "│   Info:",
        "│",
        "│ Terraform acquires a state lock to protect the state from being written",
        "│ by multiple users at the same time. Please resolve the issue above and try",
        "│ again. For most commands, you can disable locking with the \"-lock=false\"",
        "│ flag, but this is not recommended.",
        "╵",
    ])


# --------------------------------------------------------------------- views

def render_config(state: dict) -> str:
    blocks = []
    for addr, res in state["config"].items():
        rtype, name = addr.split(".", 1)
        width = max(len(k) for k in res["attrs"])
        body = [f"  {k.ljust(width)} = {_fmt(v)}" for k, v in res["attrs"].items()]
        blocks.append("\n".join([f'resource "{rtype}" "{name}" {{', *body, "}"]))
    return "\n\n".join(blocks)


def _state_show(state: dict, addr: str) -> str:
    st = state["tfstate"].get(addr)
    if st is None:
        return f"No instance found for the given address!\n\nThis command requires that the address references one specific instance.\n(address: {addr})"
    rtype, name = addr.split(".", 1)
    attrs = dict(st["attrs"], id=st["id"])
    width = max(len(k) for k in attrs)
    body = [f"    {k.ljust(width)} = {_fmt(v)}" for k, v in sorted(attrs.items())]
    return "\n".join([f"# {addr}:", f'resource "{rtype}" "{name}" {{', *body, "}"])


# ------------------------------------------------------------------ commands

def _terraform(state: dict, args: list) -> str:
    flags = {a for a in args if a.startswith("-")}
    words = [a for a in args if not a.startswith("-")]
    sub = words[0] if words else ""
    no_lock = "-lock=false" in flags

    if sub == "init":
        return ("Initializing the backend...\n\nInitializing provider plugins...\n"
                "- Reusing previous version of hashicorp/aws from the dependency lock file\n"
                "- Using previously-installed hashicorp/aws v5.70.0\n\n"
                "Terraform has been successfully initialized!")
    if sub == "validate":
        return "Success! The configuration is valid."
    if sub == "plan":
        if state["lock"] and not no_lock:
            return _lock_error(state)
        return render_plan(state, compute_plan(state), refresh_only="-refresh-only" in flags)
    if sub == "state":
        action = words[1] if len(words) > 1 else ""
        if action == "list":
            return "\n".join(sorted(state["tfstate"]))
        if action == "show":
            return _state_show(state, words[2]) if len(words) > 2 else "Error: Exactly one argument expected."
        if action == "pull":
            import json
            return json.dumps({"version": 4, "terraform_version": "1.9.5", "resources": [
                {"mode": "managed", "type": a.split(".")[0], "name": a.split(".", 1)[1],
                 "instances": [{"attributes": dict(s["attrs"], id=s["id"])}]}
                for a, s in sorted(state["tfstate"].items())]}, indent=2)
        return f"terraform state {action}: not simulated in the sandbox. Type 'help' for supported commands."
    return f"terraform {sub}: not simulated in the sandbox. Type 'help' for supported commands."


def handle_command(state: dict, raw: str) -> str:
    try:
        tokens = shlex.split(raw)
    except ValueError as e:
        return f"parse error: {e}"
    if not tokens:
        return ""
    cmd, args = tokens[0], tokens[1:]
    if cmd in ("help", "?"):
        return HELP_TEXT
    if cmd == "terraform":
        return _terraform(state, args)
    if cmd == "cat" and args == ["main.tf"]:
        return render_config(state)
    if cmd == "ls":
        return ".terraform  .terraform.lock.hcl  main.tf  backend.tf"
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


def describe_state(state: dict) -> list:
    return ["You're in the shop's production Terraform directory (backend: S3, with DynamoDB locking).",
            "Reported:", *[f"  - {REPORTS[p]}" for p in state["problems"]],
            "Investigate and fix with Terraform. Nothing real is changed."]


def run_sandbox() -> None:
    run_loop("terraform", "working directory", generate_state, handle_command, describe_state)
