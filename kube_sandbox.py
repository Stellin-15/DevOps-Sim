"""
Kubernetes sandbox (fixable) — a small cluster where every pod's status has
a cause, and real kubectl commands fix it.

Unlike sandbox.py (random statuses, read-only, good for practising how to
look around), nothing here is random at read time: pod status is DERIVED
from the deployment's template, the ConfigMaps, the nodes, and the
Services every time you look. Change the cause and the status changes.

Namespace 'shop':
  deployment web     3 replicas, shop/web     Service web (80 -> 8080), behind the ingress
  deployment api     2 replicas, shop/api     Service api (8080)
  deployment worker  2 replicas, shop/worker  reads QUEUE_URL from ConfigMap worker-config
  3 nodes with 2 CPUs each; every pod requests 500m

Status rules, in the order the kubelet would hit them:
  no schedulable node with room            -> Pending (FailedScheduling)
  image tag not in the registry            -> ImagePullBackOff
  env refers to a missing ConfigMap key    -> CreateContainerConfigError
  memory limit below what the app needs    -> CrashLoopBackOff (last state OOMKilled)
  readiness path the app doesn't serve     -> Running, 0/1 (never Ready)
  otherwise                                -> Running, 1/1
A Service's endpoints are the Ready pods its selector matches.

Random problems (two per cluster in sandbox mode):
  bad_image, selector_mismatch, bad_readiness_probe, missing_configmap_key,
  oom_limit, nodes_drained

Input is parsed case-sensitively (shlex), not through engine.normalize,
because env keys and JSON patches are case-sensitive.
"""

import copy
import hashlib
import json
import random
import shlex

from sandbox_common import render_table, run_loop

PROBLEMS = ["bad_image", "selector_mismatch", "bad_readiness_probe",
            "missing_configmap_key", "oom_limit", "nodes_drained"]

NAMESPACE = "shop"
REGISTRY = {"shop/web": ["2.4.0", "2.4.1"], "shop/api": ["1.8.9", "1.9.0"], "shop/worker": ["3.1.0", "3.2.0"]}
NODE_CPU_M = 2000
POD_CPU_M = 500
QUEUE_URL = "amqp://rabbitmq.shop.svc:5672"

HELP_TEXT = """Supported commands (namespace 'shop' is the default; -n shop and -A are accepted):
  kubectl get pods [-o wide] [-l app=<x>]      kubectl get deploy | svc | endpoints | nodes | cm | events
  kubectl get cm <name> -o yaml
  kubectl describe pod|deployment|svc|node|cm <name>
  kubectl logs <pod> [--previous]              kubectl top pods | nodes
  kubectl rollout status|history|undo deployment/<name>
  kubectl set image deployment/<name> <container>=<image>
  kubectl set env deployment/<name> KEY=value
  kubectl set resources deployment <name> --limits=memory=512Mi
  kubectl set selector service <name> app=<value>
  kubectl patch configmap <name> -p '{"data":{"KEY":"value"}}'
  kubectl scale deployment <name> --replicas=<n>
  kubectl cordon|uncordon <node>               kubectl delete pod <name>
  kubectl exec <pod> -- curl http://<service>[:port]/
  curl https://shop.example.com                (from outside, through the ingress)
  help | exit          (pipes work: kubectl get pods | grep -v Running)"""

RESOURCE_ALIASES = {
    "po": "pod", "pods": "pod", "pod": "pod",
    "deploy": "deployment", "deployments": "deployment", "deployment": "deployment",
    "svc": "service", "services": "service", "service": "service",
    "ep": "endpoints", "endpoints": "endpoints",
    "no": "node", "nodes": "node", "node": "node",
    "cm": "configmap", "configmaps": "configmap", "configmap": "configmap",
    "ev": "events", "events": "events", "event": "events",
    "rs": "replicaset", "replicasets": "replicaset", "replicaset": "replicaset",
}


# ------------------------------------------------------------------ state

def _template(image, readiness="/healthz", limit_mem=512, env=None):
    return {"image": image, "readiness_path": readiness, "limit_mem": limit_mem,
            "env": env or {}, "change_cause": "initial release"}


def generate_state(seed=None, problems=None) -> dict:
    rng = random.Random(seed)
    if problems is None:
        problems = rng.sample(PROBLEMS, 2)

    web_good = _template("shop/web:2.4.0")
    api_good = _template("shop/api:1.8.9")
    worker_good = _template("shop/worker:3.1.0", env={"QUEUE_URL": {"configmap": "worker-config", "key": "QUEUE_URL"}})

    def release(good, **changes):
        new = copy.deepcopy(good)
        new.update(changes)
        return new

    web = release(web_good, image="shop/web:2.4.2-rc" if "bad_image" in problems else "shop/web:2.4.1",
                  change_cause="release 2.4.2-rc (image built by CI)" if "bad_image" in problems else "release 2.4.1")
    api = release(api_good, image="shop/api:1.9.0",
                  readiness_path="/ready" if "bad_readiness_probe" in problems else "/healthz",
                  change_cause="release 1.9.0 (probe path 'cleanup')" if "bad_readiness_probe" in problems else "release 1.9.0")
    worker = release(worker_good, image="shop/worker:3.2.0",
                     limit_mem=64 if "oom_limit" in problems else 512,
                     change_cause="release 3.2.0 (cost saving: lower memory limit)" if "oom_limit" in problems else "release 3.2.0")

    config_key = "QUEUE_ADDR" if "missing_configmap_key" in problems else "QUEUE_URL"
    drained = ["node-2", "node-3"] if "nodes_drained" in problems else []
    return {
        "problems": problems,
        "deployments": [
            {"name": "web", "replicas": 3, "template": web, "history": [web_good], "health_path": "/healthz",
             "needs_mem": 180, "port": 8080, "deleted": False, "generation": 0},
            {"name": "api", "replicas": 2, "template": api, "history": [api_good], "health_path": "/healthz",
             "needs_mem": 220, "port": 8080, "deleted": False, "generation": 0},
            {"name": "worker", "replicas": 2, "template": worker, "history": [worker_good], "health_path": "/healthz",
             "needs_mem": 200, "port": 9090, "deleted": False, "generation": 0},
        ],
        "services": [
            {"name": "web", "selector": {"app": "webapp" if "selector_mismatch" in problems else "web"},
             "port": 80, "target_port": 8080, "cluster_ip": f"10.96.{rng.randint(1, 250)}.{rng.randint(2, 250)}"},
            {"name": "api", "selector": {"app": "api"}, "port": 8080, "target_port": 8080,
             "cluster_ip": f"10.96.{rng.randint(1, 250)}.{rng.randint(2, 250)}"},
        ],
        "configmaps": {"worker-config": {config_key: QUEUE_URL, "CONCURRENCY": "4"}},
        "nodes": [{"name": f"node-{i}", "cordoned": f"node-{i}" in drained} for i in (1, 2, 3)],
    }


# ------------------------------------------------------- derived cluster state

def _hash(text: str, n: int) -> str:
    digest = hashlib.md5(text.encode()).hexdigest()
    return "".join("bcdfghjklmnpqrstvwxz2456789"[int(digest[i:i + 2], 16) % 27] for i in range(0, 2 * n, 2))


def _deployment(state, name):
    return next((d for d in state["deployments"] if d["name"] == name and not d["deleted"]), None)


def _image_ok(image: str) -> bool:
    repo, _, tag = image.partition(":")
    return tag in REGISTRY.get(repo, [])


def _env_problem(state, template):
    for key, value in template["env"].items():
        if isinstance(value, dict):
            data = state["configmaps"].get(value["configmap"])
            if data is None:
                return f"configmap \"{value['configmap']}\" not found"
            if value["key"] not in data:
                return f"couldn't find key {value['key']} in ConfigMap {NAMESPACE}/{value['configmap']}"
    return None


def pods(state: dict) -> list:
    """Every pod, with status derived from the current spec and cluster."""
    free = {n["name"]: NODE_CPU_M for n in state["nodes"] if not n["cordoned"]}
    out = []
    for dep in state["deployments"]:
        if dep["deleted"]:
            continue
        tpl = dep["template"]
        rs = _hash(dep["name"] + json.dumps(tpl, sort_keys=True), 9)
        for i in range(dep["replicas"]):
            suffix = _hash(f"{rs}-{i}-{dep['generation']}", 5)
            pod = {"name": f"{dep['name']}-{rs}-{suffix}",
                   "app": dep["name"], "deployment": dep["name"], "image": tpl["image"], "node": None,
                   "ip": None, "restarts": 0, "ready": False, "reason": None, "message": None, "last_state": None}
            node = max(free, key=lambda n: free[n]) if free and max(free.values()) >= POD_CPU_M else None
            if node is None:
                cordoned = sum(1 for n in state["nodes"] if n["cordoned"])
                full = len(state["nodes"]) - cordoned
                parts = ([f"{full} Insufficient cpu"] if full else []) + \
                        ([f"{cordoned} node(s) were unschedulable"] if cordoned else [])
                pod.update(status="Pending",
                           message=f"0/{len(state['nodes'])} nodes are available: {', '.join(parts)}.")
                out.append(pod)
                continue
            free[node] -= POD_CPU_M
            pod.update(node=node, ip=f"10.244.{node[-1]}.{10 + len(out)}")
            env_problem = _env_problem(state, tpl)
            if not _image_ok(tpl["image"]):
                pod.update(status="ImagePullBackOff",
                           message=f"Failed to pull image \"{tpl['image']}\": rpc error: code = NotFound desc = "
                                   f"failed to resolve reference \"registry.example.com/{tpl['image']}\": "
                                   f"manifest unknown")
            elif env_problem:
                pod.update(status="CreateContainerConfigError", message=f"Error: {env_problem}")
            elif tpl["limit_mem"] < dep["needs_mem"]:
                pod.update(status="CrashLoopBackOff", restarts=14 + i, last_state="OOMKilled",
                           message="Back-off restarting failed container")
            elif tpl["readiness_path"] != dep["health_path"]:
                pod.update(status="Running",
                           message=f"Readiness probe failed: HTTP probe failed with statuscode: 404")
            else:
                pod.update(status="Running", ready=True)
            out.append(pod)
    return out


def _find_pod(state, name):
    return next((p for p in pods(state) if p["name"] == name), None)


def endpoints(state: dict, service: dict) -> list:
    return [f"{p['ip']}:{service['target_port']}" for p in pods(state)
            if p["ready"] and all(p.get(k) == v for k, v in service["selector"].items())]


def _service(state, name):
    return next((s for s in state["services"] if s["name"] == name), None)


def deployment_available(state, name) -> bool:
    dep = _deployment(state, name)
    if not dep or dep["replicas"] == 0:
        return False
    mine = [p for p in pods(state) if p["deployment"] == name]
    return all(p["ready"] for p in mine)


# ------------------------------------------------------------------ parsing

VALUE_FLAGS = {"-n": "namespace", "--namespace": "namespace", "-o": "output", "--output": "output",
               "-l": "selector", "--selector": "selector", "-p": "patch", "--patch": "patch",
               "--replicas": "replicas", "--limits": "limits", "--requests": "requests", "--type": "type",
               "--tail": "tail", "--sort-by": "sort-by", "-c": "container", "--image": "image",
               "--to-revision": "to-revision", "--from-literal": "from-literal"}
BOOL_FLAGS = {"-A": "all-namespaces", "--all-namespaces": "all-namespaces", "--previous": "previous",
              "-w": "watch", "--watch": "watch", "-it": "it", "-i": "it", "-t": "it", "--rm": "rm"}


def _parse(tokens):
    """(flags, positional, command-after-double-dash)."""
    flags, pos, tail = {}, [], []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            tail = tokens[i + 1:]
            break
        name, eq, value = tok.partition("=")
        if tok == "-owide":
            flags["output"] = "wide"
        elif name in VALUE_FLAGS:
            if eq:
                flags[VALUE_FLAGS[name]] = value
            elif i + 1 < len(tokens):
                flags[VALUE_FLAGS[name]] = tokens[i + 1]
                i += 1
        elif tok in BOOL_FLAGS:
            flags[BOOL_FLAGS[tok]] = True
        elif tok.startswith("-") and len(tok) > 1 and not tok[1:].isdigit():
            flags[tok.lstrip("-")] = value if eq else True
        else:
            pos.append(tok)
        i += 1
    return flags, pos, tail


def _resource_and_name(pos):
    """['deployment/web'] or ['deploy', 'web'] -> ('deployment', 'web')."""
    if not pos:
        return None, None
    if "/" in pos[0]:
        kind, name = pos[0].split("/", 1)
        return RESOURCE_ALIASES.get(kind, kind), name
    return RESOURCE_ALIASES.get(pos[0], pos[0]), pos[1] if len(pos) > 1 else None


def _not_found(kind, name):
    plural = {"pod": "pods", "deployment": "deployments.apps", "service": "services", "node": "nodes",
              "configmap": "configmaps", "endpoints": "endpoints"}.get(kind, kind)
    return f"Error from server (NotFound): {plural} \"{name}\" not found"


# --------------------------------------------------------------------- get

def cmd_get(state, flags, pos) -> str:
    kind, name = _resource_and_name(pos)
    ns = flags.get("namespace", NAMESPACE)
    if ns != NAMESPACE and not flags.get("all-namespaces") and kind != "node":
        return f"No resources found in {ns} namespace."
    wide = flags.get("output") == "wide"

    if kind == "pod":
        selector = dict(p.split("=", 1) for p in str(flags.get("selector", "")).split(",") if "=" in p)
        rows = []
        for p in pods(state):
            if name and p["name"] != name:
                continue
            if any(p.get(k) != v for k, v in selector.items()):
                continue
            row = [p["name"], "1/1" if p["ready"] else "0/1", p["status"], p["restarts"], "6m"]
            rows.append(row + ([p["ip"] or "<none>", p["node"] or "<none>"] if wide else []))
        if name and not rows:
            return _not_found("pod", name)
        if not rows:
            return f"No resources found in {NAMESPACE} namespace."
        return render_table(["NAME", "READY", "STATUS", "RESTARTS", "AGE"] + (["IP", "NODE"] if wide else []), rows)

    if kind == "deployment":
        rows = []
        for d in state["deployments"]:
            if d["deleted"] or (name and d["name"] != name):
                continue
            ready = sum(1 for p in pods(state) if p["deployment"] == d["name"] and p["ready"])
            rows.append([d["name"], f"{ready}/{d['replicas']}", d["replicas"], ready, "41d"])
        if name and not rows:
            return _not_found("deployment", name)
        return render_table(["NAME", "READY", "UP-TO-DATE", "AVAILABLE", "AGE"], rows)

    if kind == "service":
        rows = [[s["name"], "ClusterIP", s["cluster_ip"], "<none>", f"{s['port']}/TCP", "41d"]
                for s in state["services"] if not name or s["name"] == name]
        if name and not rows:
            return _not_found("service", name)
        return render_table(["NAME", "TYPE", "CLUSTER-IP", "EXTERNAL-IP", "PORT(S)", "AGE"], rows)

    if kind == "endpoints":
        rows = [[s["name"], ",".join(endpoints(state, s)) or "<none>", "41d"]
                for s in state["services"] if not name or s["name"] == name]
        if name and not rows:
            return _not_found("endpoints", name)
        return render_table(["NAME", "ENDPOINTS", "AGE"], rows)

    if kind == "node":
        rows = [[n["name"], "Ready,SchedulingDisabled" if n["cordoned"] else "Ready", "<none>", "120d", "v1.30.4"]
                for n in state["nodes"] if not name or n["name"] == name]
        return render_table(["NAME", "STATUS", "ROLES", "AGE", "VERSION"], rows) if rows else _not_found("node", name)

    if kind == "configmap":
        if name:
            data = state["configmaps"].get(name)
            if data is None:
                return _not_found("configmap", name)
            if flags.get("output") in ("yaml", "json"):
                body = "\n".join(f"  {k}: {v}" for k, v in data.items())
                return f"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {name}\n  namespace: {NAMESPACE}\ndata:\n{body}"
        rows = [[n, len(d), "41d"] for n, d in state["configmaps"].items() if not name or n == name]
        return render_table(["NAME", "DATA", "AGE"], rows)

    if kind == "events":
        return cmd_events(state)
    if kind == "replicaset":
        rows = []
        for d in state["deployments"]:
            if not d["deleted"]:
                mine = [p for p in pods(state) if p["deployment"] == d["name"]]
                if mine:
                    rows.append([mine[0]["name"].rsplit("-", 1)[0], d["replicas"], len(mine), sum(p["ready"] for p in mine), "6m"])
        return render_table(["NAME", "DESIRED", "CURRENT", "READY", "AGE"], rows)
    return f"error: the server doesn't have a resource type \"{pos[0] if pos else ''}\" (in this sandbox). Type 'help'."


def _pod_events(p) -> list:
    """(type, reason, message) tuples for one pod."""
    if p["status"] == "Pending":
        return [("Warning", "FailedScheduling", p["message"])]
    events = [("Normal", "Scheduled", f"Successfully assigned {NAMESPACE}/{p['name']} to {p['node']}")]
    if p["status"] == "ImagePullBackOff":
        events += [("Warning", "Failed", p["message"]), ("Warning", "Failed", "Error: ErrImagePull"),
                   ("Normal", "BackOff", f"Back-off pulling image \"{p['image']}\"")]
    elif p["status"] == "CreateContainerConfigError":
        events.append(("Warning", "Failed", p["message"]))
    elif p["status"] == "CrashLoopBackOff":
        events += [("Normal", "Started", "Started container"), ("Warning", "BackOff", p["message"])]
    elif not p["ready"]:
        events += [("Normal", "Started", "Started container"), ("Warning", "Unhealthy", p["message"])]
    else:
        events.append(("Normal", "Started", "Started container"))
    return events


def cmd_events(state) -> str:
    rows = []
    for p in pods(state):
        rows += [["2m", t, r, f"pod/{p['name']}", m] for t, r, m in _pod_events(p) if t == "Warning"]
    for n in state["nodes"]:
        if n["cordoned"]:
            rows.append(["3h", "Normal", "NodeNotSchedulable", f"node/{n['name']}", f"Node {n['name']} status is now: NodeNotSchedulable"])
    return render_table(["LAST SEEN", "TYPE", "REASON", "OBJECT", "MESSAGE"], rows) if rows else \
        f"No events found in {NAMESPACE} namespace."


# ---------------------------------------------------------------- describe

def _env_lines(template) -> str:
    lines = []
    for key, value in template["env"].items():
        if isinstance(value, dict):
            lines.append(f"      {key}:  <set to the key '{value['key']}' of config map '{value['configmap']}'>")
        else:
            lines.append(f"      {key}:  {value}")
    return "\n".join(lines) or "      <none>"


def cmd_describe(state, flags, pos) -> str:
    kind, name = _resource_and_name(pos)
    if not name:
        return "error: you must specify a name, e.g. kubectl describe pod <name>"
    if kind == "pod":
        p = _find_pod(state, name)
        if not p:
            return _not_found("pod", name)
        tpl = _deployment(state, p["deployment"])["template"]
        if p["status"] == "Running":
            state_block = "    State:          Running"
        elif p["status"] == "Pending":
            state_block = "    State:          (not scheduled)"
        else:
            state_block = f"    State:          Waiting\n      Reason:       {p['status']}"
        if p["last_state"]:
            state_block += f"\n    Last State:     Terminated\n      Reason:       {p['last_state']}\n      Exit Code:    137"
        events = "\n".join(f"  {t:<8} {r:<17} {m}" for t, r, m in _pod_events(p))
        return (f"Name:         {p['name']}\nNamespace:    {NAMESPACE}\nNode:         {p['node'] or '<none>'}\n"
                f"Labels:       app={p['app']}\nStatus:       {'Pending' if p['status'] != 'Running' else 'Running'}\n"
                f"IP:           {p['ip'] or '<none>'}\nContainers:\n  {p['deployment']}:\n"
                f"    Image:          {p['image']}\n{state_block}\n    Ready:          {p['ready']}\n"
                f"    Restart Count:  {p['restarts']}\n    Limits:\n      memory:  {tpl['limit_mem']}Mi\n"
                f"    Requests:\n      cpu:     {POD_CPU_M}m\n"
                f"    Readiness:      http-get http://:8080{tpl['readiness_path']} delay=5s timeout=1s period=10s\n"
                f"    Environment:\n{_env_lines(tpl)}\nEvents:\n  Type     Reason            Message\n{events}")
    if kind == "deployment":
        d = _deployment(state, name)
        if not d:
            return _not_found("deployment", name)
        tpl = d["template"]
        ready = sum(1 for p in pods(state) if p["deployment"] == name and p["ready"])
        return (f"Name:               {name}\nNamespace:          {NAMESPACE}\nSelector:           app={name}\n"
                f"Replicas:           {d['replicas']} desired | {d['replicas']} updated | {d['replicas']} total | "
                f"{ready} available | {d['replicas'] - ready} unavailable\n"
                f"Annotations:        kubernetes.io/change-cause: {tpl['change_cause']}\n"
                f"Pod Template:\n  Labels:  app={name}\n  Containers:\n   {name}:\n    Image:      {tpl['image']}\n"
                f"    Limits:\n      memory:  {tpl['limit_mem']}Mi\n"
                f"    Readiness:  http-get http://:8080{tpl['readiness_path']} delay=5s timeout=1s period=10s\n"
                f"    Environment:\n{_env_lines(tpl)}\n"
                f"Conditions:\n  Available      {'True' if ready == d['replicas'] and ready else 'False'}")
    if kind == "service":
        s = _service(state, name)
        if not s:
            return _not_found("service", name)
        selector = ",".join(f"{k}={v}" for k, v in s["selector"].items())
        return (f"Name:              {s['name']}\nNamespace:         {NAMESPACE}\nSelector:          {selector}\n"
                f"Type:              ClusterIP\nIP:                {s['cluster_ip']}\n"
                f"Port:              <unset>  {s['port']}/TCP\nTargetPort:        {s['target_port']}/TCP\n"
                f"Endpoints:         {','.join(endpoints(state, s)) or '<none>'}")
    if kind == "node":
        n = next((n for n in state["nodes"] if n["name"] == name), None)
        if not n:
            return _not_found("node", name)
        mine = [p for p in pods(state) if p["node"] == name]
        taint = "node.kubernetes.io/unschedulable:NoSchedule" if n["cordoned"] else "<none>"
        listing = "\n".join(f"  {NAMESPACE}   {p['name']}   {POD_CPU_M}m" for p in mine) or "  (none)"
        return (f"Name:               {name}\nTaints:             {taint}\nUnschedulable:      {str(n['cordoned']).lower()}\n"
                f"Allocatable:\n  cpu:     {NODE_CPU_M}m\nAllocated resources:\n  cpu requests:  {len(mine) * POD_CPU_M}m "
                f"({len(mine) * POD_CPU_M * 100 // NODE_CPU_M}%)\nNon-terminated Pods:\n{listing}")
    if kind == "configmap":
        data = state["configmaps"].get(name)
        if data is None:
            return _not_found("configmap", name)
        body = "\n".join(f"{k}:\n----\n{v}\n" for k, v in data.items())
        return f"Name:         {name}\nNamespace:    {NAMESPACE}\n\nData\n====\n{body}"
    return f"error: describe for \"{pos[0]}\" isn't simulated here. Type 'help'."


# ---------------------------------------------------------------- pod-level

def cmd_logs(state, flags, pos) -> str:
    kind, name = _resource_and_name(pos)
    if kind == "deployment":
        mine = [p for p in pods(state) if p["deployment"] == name]
        if not mine:
            return _not_found("deployment", name)
        name = mine[0]["name"]
    elif kind != "pod" or name is None:
        name = pos[0] if pos else None
    p = _find_pod(state, name) if name else None
    if not p:
        return _not_found("pod", name)
    dep = _deployment(state, p["deployment"])
    if p["status"] in ("ImagePullBackOff", "CreateContainerConfigError", "Pending"):
        why = "trying and failing to pull image" if p["status"] == "ImagePullBackOff" else p["status"]
        return (f"Error from server (BadRequest): container \"{p['deployment']}\" in pod \"{p['name']}\" "
                f"is waiting to start: {why}")
    if p["status"] == "CrashLoopBackOff":
        lines = [f"{p['deployment']} starting, memory limit {dep['template']['limit_mem']}Mi",
                 "loading job definitions into memory...", "connecting to queue...", "Killed"]
        return "\n".join(lines if flags.get("previous") else lines[:2])
    if not p["ready"]:
        return (f"{p['deployment']} listening on :8080 (health endpoint: {dep['health_path']})\n"
                f"GET {dep['template']['readiness_path']} 404 (kube-probe/1.30)\n"
                f"GET {dep['template']['readiness_path']} 404 (kube-probe/1.30)")
    return (f"{p['deployment']} listening on :{dep['port']} (health endpoint: {dep['health_path']})\n"
            f"GET {dep['health_path']} 200 (kube-probe/1.30)\nrequest completed in 12ms")


def cmd_top(state, pos) -> str:
    kind = RESOURCE_ALIASES.get(pos[0], pos[0]) if pos else None
    if kind == "node":
        rows = []
        for n in state["nodes"]:
            count = sum(1 for p in pods(state) if p["node"] == n["name"])
            rows.append([n["name"], f"{count * 180}m", f"{count * 9}%", f"{count * 310}Mi", f"{count * 8}%"])
        return render_table(["NAME", "CPU(cores)", "CPU%", "MEMORY(bytes)", "MEMORY%"], rows)
    if kind == "pod":
        rows = []
        for p in pods(state):
            if p["status"] == "Running":
                dep = _deployment(state, p["deployment"])
                rows.append([p["name"], "180m", f"{min(dep['needs_mem'], dep['template']['limit_mem'])}Mi"])
        return render_table(["NAME", "CPU(cores)", "MEMORY(bytes)"], rows)
    return "usage: kubectl top pods | kubectl top nodes"


def _in_cluster_curl(state, command) -> str:
    urls = [a for a in command[1:] if not a.startswith("-") and not a.isdigit()]
    if not urls:
        return "curl: no URL specified"
    url = urls[0].split("://", 1)[-1]
    hostport = url.split("/", 1)[0]
    host, _, port = hostport.partition(":")
    svc = _service(state, host.split(".")[0])
    if not svc:
        return f"curl: (6) Could not resolve host: {host}"
    port = int(port) if port.isdigit() else svc["port"]
    if port != svc["port"] or not endpoints(state, svc):
        return f"curl: (7) Failed to connect to {host} port {port} after 2 ms: Connection refused"
    return f'{{"service":"{svc["name"]}","status":"ok"}}'


def cmd_exec(state, pos, tail) -> str:
    p = _find_pod(state, pos[0]) if pos else None
    if not p:
        return _not_found("pod", pos[0] if pos else "")
    if p["status"] != "Running":
        return f"error: unable to upgrade connection: container not found (\"{p['deployment']}\" is {p['status']})"
    if not tail:
        return "error: you must specify at least one command for the container (after --)"
    if tail[0] == "curl":
        return _in_cluster_curl(state, tail)
    if tail[0] == "env":
        return "\n".join(f"{k}={v}" for k, v in _resolved_env(state, p["deployment"]).items()) or "(no app env set)"
    return f"{tail[0]}: not simulated inside the pod (try: curl http://<service>/, env)"


def _resolved_env(state, dep_name) -> dict:
    out = {}
    for key, value in _deployment(state, dep_name)["template"]["env"].items():
        out[key] = state["configmaps"].get(value["configmap"], {}).get(value["key"], "") if isinstance(value, dict) else value
    return out


# ------------------------------------------------------------------ change

def _new_revision(dep, cause, **changes):
    dep["history"].append(copy.deepcopy(dep["template"]))
    dep["template"].update(changes)
    dep["template"]["change_cause"] = cause


def cmd_rollout(state, flags, pos) -> str:
    action = pos[0] if pos else ""
    kind, name = _resource_and_name(pos[1:])
    dep = _deployment(state, name) if kind == "deployment" else None
    if not dep:
        return _not_found("deployment", name) if name else "usage: kubectl rollout status|history|undo deployment/<name>"
    if action == "history":
        rows = [[i + 1, t["change_cause"]] for i, t in enumerate(dep["history"] + [dep["template"]])]
        return f"deployment.apps/{name}\n" + render_table(["REVISION", "CHANGE-CAUSE"], rows)
    if action == "undo":
        if not dep["history"]:
            return f"error: no rollout history found for deployment \"{name}\""
        target = int(flags["to-revision"]) - 1 if str(flags.get("to-revision", "")).isdigit() else len(dep["history"]) - 1
        if not 0 <= target < len(dep["history"]):
            return f"error: unable to find specified revision {flags.get('to-revision')} in history"
        previous = dep["history"].pop(target)
        dep["history"].append(dep["template"])
        dep["template"] = previous
        return f"deployment.apps/{name} rolled back"
    if action == "status":
        mine = [p for p in pods(state) if p["deployment"] == name]
        ready = sum(p["ready"] for p in mine)
        if mine and ready == len(mine):
            return f"deployment \"{name}\" successfully rolled out"
        return (f"Waiting for deployment \"{name}\" rollout to finish: {ready} of {dep['replicas']} updated replicas "
                f"are available...\n(still waiting; check the pods)")
    if action == "restart":
        dep["generation"] += 1
        return f"deployment.apps/{name} restarted"
    return "usage: kubectl rollout status|history|undo|restart deployment/<name>"


def _mem_mi(text):
    text = text.strip()
    for suffix, factor in (("Gi", 1024), ("Mi", 1), ("G", 1000), ("M", 1)):
        if text.endswith(suffix) and text[:-len(suffix)].isdigit():
            return int(text[:-len(suffix)]) * factor
    return None


def cmd_set(state, flags, pos) -> str:
    what = pos[0] if pos else ""
    kind, name = _resource_and_name(pos[1:])
    rest = pos[2:] if pos[1:] and "/" in pos[1] else pos[3:]
    if what == "selector":
        svc = _service(state, name) if kind == "service" else None
        if not svc:
            return _not_found("service", name)
        pairs = dict(r.split("=", 1) for r in rest if "=" in r)
        if not pairs:
            return "usage: kubectl set selector service <name> app=<value>"
        svc["selector"] = pairs
        return f"service/{name} selector updated"
    dep = _deployment(state, name) if kind == "deployment" else None
    if not dep:
        return _not_found("deployment", name) if name else f"usage: kubectl set {what} deployment/<name> ..."
    if what == "image":
        images = [r.split("=", 1)[1] for r in rest if "=" in r]
        if not images:
            return "usage: kubectl set image deployment/<name> <container>=<image>"
        _new_revision(dep, f"kubectl set image {images[0]}", image=images[0])
        return f"deployment.apps/{name} image updated"
    if what == "env":
        env = copy.deepcopy(dep["template"]["env"])
        for r in rest:
            if r.endswith("-") and "=" not in r:
                env.pop(r[:-1], None)
            elif "=" in r:
                key, value = r.split("=", 1)
                env[key] = value
        _new_revision(dep, "kubectl set env", env=env)
        return f"deployment.apps/{name} env updated"
    if what == "resources":
        limits = dict(p.split("=", 1) for p in str(flags.get("limits", "")).split(",") if "=" in p)
        mem = _mem_mi(limits.get("memory", ""))
        if mem is None:
            return "usage: kubectl set resources deployment <name> --limits=memory=512Mi"
        _new_revision(dep, f"kubectl set resources --limits=memory={mem}Mi", limit_mem=mem)
        return f"deployment.apps/{name} resource requirements updated"
    return f"error: 'kubectl set {what}' isn't simulated here (try image, env, resources, selector)"


def cmd_patch(state, flags, pos) -> str:
    kind, name = _resource_and_name(pos)
    if kind != "configmap":
        return ("(the sandbox patches ConfigMaps only. For deployments use kubectl set image|env|resources "
                "or kubectl rollout undo)")
    if name not in state["configmaps"]:
        return _not_found("configmap", name)
    try:
        data = json.loads(str(flags.get("patch", "")))["data"]
    except (ValueError, KeyError, TypeError):
        return "error: expected a patch like -p '{\"data\":{\"KEY\":\"value\"}}'"
    for key, value in data.items():
        if value is None:
            state["configmaps"][name].pop(key, None)
        else:
            state["configmaps"][name][key] = str(value)
    return f"configmap/{name} patched"


def cmd_scale(state, flags, pos) -> str:
    kind, name = _resource_and_name(pos)
    dep = _deployment(state, name) if kind == "deployment" else None
    if not dep:
        return _not_found("deployment", name)
    if not str(flags.get("replicas", "")).isdigit():
        return "error: --replicas=<n> is required"
    dep["replicas"] = int(flags["replicas"])
    return f"deployment.apps/{name} scaled"


def cmd_cordon(state, pos, cordon: bool) -> str:
    node = next((n for n in state["nodes"] if pos and n["name"] == pos[0]), None)
    if not node:
        return _not_found("node", pos[0] if pos else "")
    if node["cordoned"] == cordon:
        return f"node/{node['name']} already {'cordoned' if cordon else 'uncordoned'}"
    node["cordoned"] = cordon
    return f"node/{node['name']} {'cordoned' if cordon else 'uncordoned'}"


def cmd_delete(state, pos) -> str:
    kind, name = _resource_and_name(pos)
    if kind == "pod":
        p = _find_pod(state, name)
        if not p:
            return _not_found("pod", name)
        _deployment(state, p["deployment"])["generation"] += 1
        return f"pod \"{name}\" deleted\n(its ReplicaSet created a replacement from the same template)"
    if kind == "deployment":
        dep = _deployment(state, name)
        if not dep:
            return _not_found("deployment", name)
        dep["deleted"] = True
        return f"deployment.apps \"{name}\" deleted"
    if kind == "configmap":
        if name not in state["configmaps"]:
            return _not_found("configmap", name)
        del state["configmaps"][name]
        return f"configmap \"{name}\" deleted"
    return "error: the sandbox supports deleting pods, deployments, and configmaps"


def cmd_external_curl(state, args) -> str:
    urls = [a for a in args if not a.startswith("-") and not a.isdigit()]
    if not urls or "shop.example.com" not in urls[0]:
        return "curl: (6) Could not resolve host (the site is https://shop.example.com)"
    if endpoints(state, _service(state, "web")):
        return "<!doctype html><title>Shop</title><h1>Welcome to the shop</h1>"
    return ("<html>\n<head><title>503 Service Temporarily Unavailable</title></head>\n"
            "<body><center><h1>503 Service Temporarily Unavailable</h1></center><hr><center>nginx</center></body>\n</html>")


# ---------------------------------------------------------------- dispatch

def handle_command(state: dict, raw: str):
    raw = raw.lstrip("﻿").strip()
    if raw.lower() in {"exit", "quit", ":q"}:
        return None
    if raw.lower() in {"help", "?"} or not raw:
        return HELP_TEXT
    try:
        tokens = shlex.split(raw)
    except ValueError:
        return "error: unbalanced quotes in the command"
    if tokens[0] == "curl":
        return cmd_external_curl(state, tokens[1:])
    if tokens[0] not in ("kubectl", "k"):
        return f"{tokens[0]}: not simulated in the sandbox. Type 'help' for supported commands."
    if len(tokens) < 2:
        return HELP_TEXT
    verb = tokens[1]
    flags, pos, tail = _parse(tokens[2:])
    if verb == "get":
        return cmd_get(state, flags, pos)
    if verb == "describe":
        return cmd_describe(state, flags, pos)
    if verb == "logs":
        return cmd_logs(state, flags, pos)
    if verb == "top":
        return cmd_top(state, pos)
    if verb == "rollout":
        return cmd_rollout(state, flags, pos)
    if verb == "set":
        return cmd_set(state, flags, pos)
    if verb == "patch":
        return cmd_patch(state, flags, pos)
    if verb == "scale":
        return cmd_scale(state, flags, pos)
    if verb in ("cordon", "uncordon"):
        return cmd_cordon(state, pos, verb == "cordon")
    if verb == "delete":
        return cmd_delete(state, pos)
    if verb == "exec":
        return cmd_exec(state, pos, tail)
    return f"'kubectl {verb}' isn't simulated in the sandbox. Type 'help' for supported commands."


# ------------------------------------------------------- mystery/sandbox hooks

def placeholders(state: dict) -> dict:
    all_pods = pods(state)
    values = {}
    for name in ("web", "api", "worker"):
        mine = [p for p in all_pods if p["deployment"] == name]
        if mine:
            values[f"{name}_pod"] = mine[0]["name"]
    pending = [p for p in all_pods if p["status"] == "Pending"]
    values["pending_pod"] = pending[0]["name"] if pending else ""
    return values


GOAL_CHECKS = {
    "deployment_available": lambda state, g: deployment_available(state, g["deployment"]),
    "service_has_endpoints": lambda state, g: bool(endpoints(state, _service(state, g["service"]))),
}


def collateral_issues(state: dict) -> set:
    issues = set()
    for d in state["deployments"]:
        if d["deleted"]:
            issues.add(f"deleted the deployment '{d['name']}' — the workload is gone, not fixed")
        elif d["replicas"] == 0:
            issues.add(f"scaled '{d['name']}' to zero — that hides failing pods by removing the service")
    if all(n["cordoned"] for n in state["nodes"]):
        issues.add("cordoned every node — nothing can be scheduled anywhere")
    if "worker-config" not in state["configmaps"]:
        issues.add("deleted the worker-config ConfigMap — every worker pod now fails to start")
    for d in state["deployments"]:
        if not d["deleted"] and d["template"]["limit_mem"] > 4096:
            issues.add(f"set {d['name']}'s memory limit above 4Gi — more than a third of a node for one pod")
    return issues


def describe_state(state: dict) -> list:
    return [
        f"kubectl is pointed at the production cluster, namespace '{NAMESPACE}' (3 nodes).",
        "Deployments: web (3), api (2), worker (2). Services: web and api. The site is https://shop.example.com.",
        "Two things are wrong, and each has a cause you can find and fix with kubectl.",
    ]


def run_sandbox() -> None:
    run_loop("kube", "cluster", generate_state, handle_command, describe_state)
