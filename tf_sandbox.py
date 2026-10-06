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
  terraform state mv <from> <to>   terraform state rm <addr>
  terraform apply [-auto-approve] [-refresh-only]   terraform import <addr> <id>
  terraform force-unlock [-force] <lock-id>
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


# ------------------------------------------------------------- state surgery

def _take_lock(state: dict, no_lock: bool):
    """None if the command may write the state; otherwise the lock error.
    -lock=false gets past a lock, which is recorded: if the run holding it
    were still alive, two writers would corrupt the state."""
    if not state["lock"]:
        return None
    if no_lock:
        state["lock_bypassed"] = True
        return None
    return _lock_error(state)


def _state_mv(state: dict, args: list) -> str:
    if len(args) != 2:
        return "Error: Exactly two arguments expected: the source and destination addresses."
    src, dst = args
    tfstate = state["tfstate"]
    if src not in tfstate:
        return (f"╷\n│ Error: Invalid source address\n│\n│ Cannot move {src}: does not match anything in the "
                "current state.\n╵")
    if dst in tfstate:
        return (f"╷\n│ Error: Invalid target address\n│\n│ Cannot move to {dst}: there is already a resource "
                "instance at that address in the current state.\n╵")
    if src.split(".")[0] != dst.split(".")[0]:
        return (f"╷\n│ Error: Invalid state move request\n│\n│ Cannot move {src} to {dst}: resource types "
                "don't match.\n╵")
    tfstate[dst] = tfstate.pop(src)
    return f'Move "{src}" to "{dst}"\nSuccessfully moved 1 object(s).'


def _state_rm(state: dict, args: list) -> str:
    if not args:
        return "Error: At least one address is required."
    missing = [a for a in args if a not in state["tfstate"]]
    if missing:
        return f"╷\n│ Error: Invalid target address\n│\n│ No matching objects found for {missing[0]}.\n╵"
    for addr in args:
        del state["tfstate"][addr]
    lines = [f"Removed {a}" for a in args]
    return "\n".join(lines + [f"Successfully removed {len(args)} resource instance(s)."])


# --------------------------------------------------------- apply and friends

PROMPT_NOTE = ("  Enter a value: (the sandbox can't answer prompts. Review the plan above; "
               "to go ahead, run the command again with {flag}.)")

ALREADY_EXISTS = {
    "aws_s3_bucket": "creating S3 Bucket ({v}): BucketAlreadyOwnedByYou: Your previous request to create the "
                     "named bucket succeeded and you already own it.",
    "aws_db_instance": "creating RDS DB Instance ({v}): DBInstanceAlreadyExists: DB instance already exists",
    "aws_security_group": "creating Security Group ({v}): InvalidGroup.Duplicate: The security group '{v}' "
                          "already exists",
}
ID_PREFIX = {"aws_instance": "i-0", "aws_security_group": "sg-0", "aws_vpc": "vpc-0"}


def _new_id(state: dict, rtype: str, attrs: dict) -> str:
    if rtype in IDENTITY:
        return attrs[IDENTITY[rtype]]
    state["next_id"] += 7919
    return f"{ID_PREFIX[rtype]}{state['next_id'] % (1 << 68):017x}"


def _create(state: dict, addr: str, attrs: dict):
    """Returns (id, None) or (None, error) when the unique name is taken."""
    rtype = addr.split(".")[0]
    key = IDENTITY.get(rtype)
    if key and any(o["type"] == rtype and o["attrs"].get(key) == attrs[key] for o in state["real"].values()):
        return None, ALREADY_EXISTS[rtype].format(v=attrs[key])
    rid = _new_id(state, rtype, attrs)
    state["real"][rid] = {"type": rtype, "attrs": dict(attrs)}
    state["tfstate"][addr] = {"id": rid, "attrs": dict(attrs)}
    return rid, None


def _apply(state: dict, flags: set) -> str:
    blocked = _take_lock(state, "-lock=false" in flags)
    if blocked:
        return blocked
    plan = compute_plan(state)
    if "-refresh-only" in flags:
        out = render_plan(state, plan, refresh_only=True)
        if not plan["drifted"]:
            return out
        if "-auto-approve" not in flags:
            return out + "\n\nWould you like to update the Terraform state to reflect these detected changes?\n" \
                + PROMPT_NOTE.format(flag="-auto-approve")
        for addr in list(state["tfstate"]):
            obj = state["real"].get(state["tfstate"][addr]["id"])
            if obj is None:
                del state["tfstate"][addr]
            else:
                state["tfstate"][addr]["attrs"] = dict(obj["attrs"])
        return out + "\n\nApply complete! Resources: 0 added, 0 changed, 0 destroyed."
    if not plan["changes"]:
        return render_plan(state, plan) + "\n\nApply complete! Resources: 0 added, 0 changed, 0 destroyed."
    if "-auto-approve" not in flags:
        return (render_plan(state, plan) + "\n\nDo you want to perform these actions?\n"
                "  Terraform will perform the actions described above.\n  Only 'yes' will be accepted to approve.\n\n"
                + PROMPT_NOTE.format(flag="-auto-approve"))

    lines, done = [], {"added": 0, "changed": 0, "destroyed": 0}
    for action, addr, d in plan["changes"]:
        res = state["config"].get(addr)
        if action in ("destroy", "replace"):
            lines.append(f"{addr}: Destroying... [id={d['id']}]")
            state["real"].pop(d["id"], None)
            state["tfstate"].pop(addr, None)
            lines.append(f"{addr}: Destruction complete after 3s")
            done["destroyed"] += 1
        if action in ("create", "replace"):
            lines.append(f"{addr}: Creating...")
            rid, error = _create(state, addr, res["attrs"])
            if error:
                rtype, name = addr.split(".", 1)
                lines += ["", "╷", f"│ Error: {error}", "│", f"│   with {addr},",
                          f'│   on main.tf, in resource "{rtype}" "{name}":', "╵"]
                return "\n".join(lines)
            lines.append(f"{addr}: Creation complete after 4s [id={rid}]")
            done["added"] += 1
        if action == "update":
            lines.append(f"{addr}: Modifying... [id={d['id']}]")
            state["real"][d["id"]]["attrs"].update(res["attrs"])
            state["tfstate"][addr]["attrs"] = dict(state["real"][d["id"]]["attrs"])
            lines.append(f"{addr}: Modifications complete after 2s [id={d['id']}]")
            done["changed"] += 1
    lines += ["", f"Apply complete! Resources: {done['added']} added, {done['changed']} changed, "
                  f"{done['destroyed']} destroyed."]
    return "\n".join(lines)


def _import(state: dict, words: list, flags: set) -> str:
    if len(words) != 2:
        return "Error: The import command expects two arguments: the resource address and the remote id."
    blocked = _take_lock(state, "-lock=false" in flags)
    if blocked:
        return blocked
    addr, rid = words
    if addr not in state["config"]:
        return (f"╷\n│ Error: resource address \"{addr}\" does not exist in the configuration.\n│\n"
                f"│ Before importing this resource, please create its configuration in main.tf.\n╵")
    if addr in state["tfstate"]:
        return (f"╷\n│ Error: Resource already managed by Terraform\n│\n│ Terraform is already managing a remote "
                f"object for {addr}. To import to this address you must first remove the existing object from "
                "the state.\n╵")
    obj = state["real"].get(rid)
    rtype = addr.split(".")[0]
    if obj is None or obj["type"] != rtype:
        return (f"╷\n│ Error: Cannot import non-existent remote object\n│\n│ While attempting to import an "
                f"existing object to \"{addr}\", the provider detected that no object exists with the given id. "
                "Only pre-existing objects can be imported; check that the id is correct and that it is "
                "associated with the provider's configured region or endpoint.\n╵")
    state["tfstate"][addr] = {"id": rid, "attrs": dict(obj["attrs"])}
    return (f"{addr}: Importing from ID \"{rid}\"...\n{addr}: Import prepared!\n  Prepared {rtype} for import\n"
            f"{addr}: Refreshing state... [id={rid}]\n\nImport successful!\n\n"
            "The resources that were imported are shown above. These resources are now in\n"
            "your Terraform state and will henceforth be managed by Terraform.")


def _force_unlock(state: dict, words: list, flags: set) -> str:
    if not words:
        return "Error: Expected a single argument: LOCK_ID"
    lock = state["lock"]
    if lock is None:
        return "Failed to unlock state: no lock is held on this state."
    if words[0] != lock["id"]:
        return f'Failed to unlock state: lock ID "{words[0]}" does not match existing lock ID "{lock["id"]}"'
    if "-force" not in flags:
        return ("Do you really want to force-unlock?\n  Terraform will remove the lock on the remote state.\n"
                "  This will allow local Terraform commands to modify this state, even though it\n"
                "  may still be in use. Only 'yes' will be accepted to confirm.\n\n"
                + PROMPT_NOTE.format(flag="-force"))
    state["lock"] = None
    return ("Terraform state has been successfully unlocked!\n\nThe state has been unlocked, and Terraform commands "
            "should now be able to\nobtain a new lock on the remote state.")


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
    if sub == "apply":
        return _apply(state, flags)
    if sub == "import":
        return _import(state, words[1:], flags)
    if sub == "force-unlock":
        return _force_unlock(state, words[1:], flags)
    if sub == "destroy":
        return "terraform destroy isn't available here: it would delete the whole production stack."
    if sub == "state":
        action = words[1] if len(words) > 1 else ""
        if action == "list":
            return "\n".join(sorted(state["tfstate"]))
        if action == "show":
            return _state_show(state, words[2]) if len(words) > 2 else "Error: Exactly one argument expected."
        if action in ("mv", "rm"):
            blocked = _take_lock(state, no_lock)
            if blocked:
                return blocked
            return _state_mv(state, words[2:]) if action == "mv" else _state_rm(state, words[2:])
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
