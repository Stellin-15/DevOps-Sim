"""
Kubernetes sandbox — no scoring, no steps. Generates a random fake cluster
(pods with random names, statuses, and resource usage) and lets the player
poke at it with free-form kubectl-style commands.

Persistence (keep/discard, saved sessions under sandbox_data/saved/) and
the interactive loop live in sandbox_common.py, shared with the Docker and
Linux sandboxes.
"""

import random
import string
from datetime import datetime

from engine import normalize
from sandbox_common import render_table, run_loop

SERVICE_NAMES = [
    "checkout-service", "auth-service", "payment-gateway", "frontend",
    "redis-cache", "user-api", "notification-worker", "inventory-service",
    "order-processor", "analytics-collector", "billing-service", "email-sender",
]

VERSIONS = ["1.0.0", "1.2.3", "1.4.1", "2.0.1", "2.3.0", "latest", "3.1.0"]

STATUSES = ["Running"] * 65 + ["CrashLoopBackOff"] * 10 + ["Pending"] * 10 \
    + ["OOMKilled"] * 10 + ["Error"] * 5

CONFIGMAP_DATA = {"APP_MODE": "production", "LOG_LEVEL": "info"}
SECRET_DATA = {"DB_PASSWORD": "aHVudGVyMg==", "API_KEY": "c2VjcmV0LWFwaS1rZXk="}

HELP_TEXT = """Supported commands:
  kubectl get pods [-o wide]
  kubectl get pod <name>
  kubectl get deployments | deploy
  kubectl get svc | services
  kubectl get configmaps | cm
  kubectl get secrets
  kubectl get nodes
  kubectl get events
  kubectl get all
  kubectl describe pod|deployment|svc|configmap|secret|node <name>
  kubectl logs <name>
  kubectl top pod [<name>]
  kubectl top nodes
  help
  exit"""


def random_suffix(n: int) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=n))


def format_age(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h{minutes % 60}m"
    days = hours // 24
    return f"{days}d"


def generate_pod(service: str) -> dict:
    status = random.choice(STATUSES)
    restarts = 0
    if status == "CrashLoopBackOff":
        restarts = random.randint(4, 15)
    elif status == "OOMKilled":
        restarts = random.randint(1, 4)
    elif status == "Error":
        restarts = random.randint(1, 3)

    ready = "1/1" if status == "Running" else "0/1"
    cpu = f"{random.randint(5, 480)}m"
    mem_limit = random.choice([128, 256, 512, 1024])
    if status == "OOMKilled":
        mem_usage = mem_limit + random.randint(5, 60)
    else:
        mem_usage = random.randint(int(mem_limit * 0.2), int(mem_limit * 0.9))

    age_minutes = random.randint(1, 4000)

    return {
        "name": f"{service}-{random_suffix(10)}-{random_suffix(5)}",
        "service": service,
        "image": f"{service}:{random.choice(VERSIONS)}",
        "namespace": "default",
        "status": status,
        "ready": ready,
        "restarts": restarts,
        "age": format_age(age_minutes),
        "node": f"node-{random.randint(1, 3)}",
        "cpu": cpu,
        "memory": f"{mem_usage}Mi",
        "memory_limit": f"{mem_limit}Mi",
    }


def random_cluster_ip() -> str:
    return f"10.96.{random.randint(0, 255)}.{random.randint(1, 254)}"


def generate_events(pods: list) -> list:
    reason_for_status = {
        "CrashLoopBackOff": ("Warning", "BackOff", "Back-off restarting failed container"),
        "OOMKilled": ("Warning", "OOMKilling", "Memory cgroup out of memory: killed process"),
        "Pending": ("Warning", "FailedScheduling", "0/3 nodes are available: insufficient cpu"),
        "Error": ("Warning", "Failed", "Error: container process exited with non-zero status"),
    }
    events = []
    for pod in pods:
        if pod["status"] == "Running":
            events.append({
                "last_seen": pod["age"],
                "type": "Normal",
                "reason": "Started",
                "object": f"pod/{pod['name']}",
                "message": "Started container",
            })
            continue
        event_type, reason, message = reason_for_status[pod["status"]]
        events.append({
            "last_seen": pod["age"],
            "type": event_type,
            "reason": reason,
            "object": f"pod/{pod['name']}",
            "message": message,
        })
    return events


def generate_state() -> dict:
    services = random.sample(SERVICE_NAMES, k=random.randint(4, 6))

    pods = []
    deployments = []
    services_list = []
    for svc in services:
        desired = random.randint(1, 3)
        svc_pods = [generate_pod(svc) for _ in range(desired)]
        pods.extend(svc_pods)

        ready_count = sum(1 for p in svc_pods if p["status"] == "Running")
        deployments.append({
            "name": svc,
            "desired": desired,
            "ready": ready_count,
            "up_to_date": desired,
            "available": ready_count,
            "age": format_age(random.randint(60, 20000)),
        })
        services_list.append({
            "name": svc,
            "type": "ClusterIP",
            "cluster_ip": random_cluster_ip(),
            "port": random.choice([80, 8080, 443, 3000, 5432]),
            "age": format_age(random.randint(60, 20000)),
        })

    nodes = [
        {"name": f"node-{i}", "status": "Ready", "age": format_age(random.randint(1000, 40000))}
        for i in range(1, 4)
    ]

    configmaps = [{"name": "app-config", "data": dict(CONFIGMAP_DATA), "age": format_age(random.randint(60, 20000))}]
    secrets = [{"name": "app-secrets", "type": "Opaque", "data": dict(SECRET_DATA), "age": format_age(random.randint(60, 20000))}]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "namespace": "default",
        "pods": pods,
        "deployments": deployments,
        "services": services_list,
        "nodes": nodes,
        "configmaps": configmaps,
        "secrets": secrets,
        "events": generate_events(pods),
    }


def find_pod(state: dict, name: str):
    name = name.lower()
    for pod in state["pods"]:
        if pod["name"].lower() == name:
            return pod
    return None


def format_pod_row(pod: dict, wide: bool) -> list:
    row = [pod["name"], pod["ready"], pod["status"], pod["restarts"], pod["age"]]
    if wide:
        row.append(pod["node"])
    return row


def cmd_get_pods(state: dict, wide: bool) -> str:
    headers = ["NAME", "READY", "STATUS", "RESTARTS", "AGE"]
    if wide:
        headers.append("NODE")
    rows = [format_pod_row(pod, wide) for pod in state["pods"]]
    return render_table(headers, rows)


def cmd_get_pod(state: dict, name: str, wide: bool) -> str:
    pod = find_pod(state, name)
    if not pod:
        return f'Error from server (NotFound): pods "{name}" not found'
    headers = ["NAME", "READY", "STATUS", "RESTARTS", "AGE"]
    if wide:
        headers.append("NODE")
    return render_table(headers, [format_pod_row(pod, wide)])


def cmd_describe_pod(state: dict, name: str) -> str:
    pod = find_pod(state, name)
    if not pod:
        return f'Error from server (NotFound): pods "{name}" not found'

    lines = [
        f"Name:         {pod['name']}",
        f"Namespace:    {pod['namespace']}",
        f"Node:         {pod['node']}",
        f"Status:       {pod['status']}",
        f"Image:        {pod['image']}",
        f"Restart Count: {pod['restarts']}",
        "Limits:",
        f"  memory:     {pod['memory_limit']}",
    ]

    if pod["status"] == "CrashLoopBackOff":
        lines += [
            "",
            "Events:",
            "  Warning  BackOff  kubelet  Back-off restarting failed container",
        ]
    elif pod["status"] == "OOMKilled":
        lines += [
            "",
            "Events:",
            "  Warning  OOMKilling  kubelet  Memory cgroup out of memory: killed process",
        ]
    elif pod["status"] == "Pending":
        lines += [
            "",
            "Events:",
            "  Warning  FailedScheduling  default-scheduler  0/3 nodes are available: insufficient cpu",
        ]
    elif pod["status"] == "Error":
        lines += [
            "",
            "Events:",
            "  Warning  Failed  kubelet  Error: container process exited with non-zero status",
        ]

    return "\n".join(lines)


def cmd_logs(state: dict, name: str) -> str:
    pod = find_pod(state, name)
    if not pod:
        return f'Error from server (NotFound): pods "{name}" not found'

    if pod["status"] == "CrashLoopBackOff":
        return "panic: connection refused: unable to reach dependency\n[fatal] exiting"
    if pod["status"] == "OOMKilled":
        return "Killed"
    if pod["status"] == "Pending":
        return "Error from server (BadRequest): container has not started"
    if pod["status"] == "Error":
        return "[ERROR] unhandled exception during startup\nexit status 1"
    return f"[INFO] {pod['service']} started successfully\n[INFO] listening on port 8080"


def cmd_top_pod(state: dict, name: str = None) -> str:
    headers = ["NAME", "CPU", "MEMORY"]
    if name:
        pod = find_pod(state, name)
        if not pod:
            return f'Error from server (NotFound): pods "{name}" not found'
        return render_table(headers, [[pod["name"], pod["cpu"], pod["memory"]]])
    rows = [[pod["name"], pod["cpu"], pod["memory"]] for pod in state["pods"]]
    return render_table(headers, rows)


def find_by_name(items: list, name: str):
    name = name.lower()
    for item in items:
        if item["name"].lower() == name:
            return item
    return None


def cmd_get_deployments(state: dict, name: str = None) -> str:
    deployments = state.get("deployments", [])
    if name:
        dep = find_by_name(deployments, name)
        if not dep:
            return f'Error from server (NotFound): deployments.apps "{name}" not found'
        deployments = [dep]
    headers = ["NAME", "READY", "UP-TO-DATE", "AVAILABLE", "AGE"]
    rows = [[d["name"], f"{d['ready']}/{d['desired']}", d["up_to_date"], d["available"], d["age"]] for d in deployments]
    return render_table(headers, rows)


def cmd_describe_deployment(state: dict, name: str) -> str:
    dep = find_by_name(state.get("deployments", []), name)
    if not dep:
        return f'Error from server (NotFound): deployments.apps "{name}" not found'
    return "\n".join([
        f"Name:               {dep['name']}",
        "Namespace:          default",
        f"Replicas:           {dep['desired']} desired | {dep['ready']} updated | {dep['available']} available",
        f"Selector:           app={dep['name']}",
        "StrategyType:       RollingUpdate",
    ])


def cmd_get_services(state: dict, name: str = None) -> str:
    services = state.get("services", [])
    if name:
        svc = find_by_name(services, name)
        if not svc:
            return f'Error from server (NotFound): services "{name}" not found'
        services = [svc]
    headers = ["NAME", "TYPE", "CLUSTER-IP", "PORT(S)", "AGE"]
    rows = [[s["name"], s["type"], s["cluster_ip"], f"{s['port']}/TCP", s["age"]] for s in services]
    return render_table(headers, rows)


def cmd_describe_service(state: dict, name: str) -> str:
    svc = find_by_name(state.get("services", []), name)
    if not svc:
        return f'Error from server (NotFound): services "{name}" not found'
    return "\n".join([
        f"Name:              {svc['name']}",
        f"Type:              {svc['type']}",
        f"IP:                {svc['cluster_ip']}",
        f"Port:              <unset>  {svc['port']}/TCP",
        f"Selector:          app={svc['name']}",
    ])


def cmd_get_configmaps(state: dict, name: str = None) -> str:
    configmaps = state.get("configmaps", [])
    if name:
        cm = find_by_name(configmaps, name)
        if not cm:
            return f'Error from server (NotFound): configmaps "{name}" not found'
        configmaps = [cm]
    headers = ["NAME", "DATA", "AGE"]
    rows = [[cm["name"], len(cm["data"]), cm["age"]] for cm in configmaps]
    return render_table(headers, rows)


def cmd_describe_configmap(state: dict, name: str) -> str:
    cm = find_by_name(state.get("configmaps", []), name)
    if not cm:
        return f'Error from server (NotFound): configmaps "{name}" not found'
    lines = [f"Name:         {cm['name']}", "", "Data", "===="]
    for k, v in cm["data"].items():
        lines.append(f"{k}:\n----\n{v}")
    return "\n".join(lines)


def cmd_get_secrets(state: dict, name: str = None) -> str:
    secrets = state.get("secrets", [])
    if name:
        s = find_by_name(secrets, name)
        if not s:
            return f'Error from server (NotFound): secrets "{name}" not found'
        secrets = [s]
    headers = ["NAME", "TYPE", "DATA", "AGE"]
    rows = [[s["name"], s["type"], len(s["data"]), s["age"]] for s in secrets]
    return render_table(headers, rows)


def cmd_describe_secret(state: dict, name: str) -> str:
    s = find_by_name(state.get("secrets", []), name)
    if not s:
        return f'Error from server (NotFound): secrets "{name}" not found'
    lines = [f"Name:         {s['name']}", f"Type:         {s['type']}", "", "Data", "===="]
    for k, v in s["data"].items():
        lines.append(f"{k}:  {len(v)} bytes")
    return "\n".join(lines)


def cmd_get_nodes(state: dict, name: str = None) -> str:
    nodes = state.get("nodes", [])
    if name:
        n = find_by_name(nodes, name)
        if not n:
            return f'Error from server (NotFound): nodes "{name}" not found'
        nodes = [n]
    headers = ["NAME", "STATUS", "ROLES", "AGE"]
    rows = [[n["name"], n["status"], "<none>", n["age"]] for n in nodes]
    return render_table(headers, rows)


def cmd_describe_node(state: dict, name: str) -> str:
    n = find_by_name(state.get("nodes", []), name)
    if not n:
        return f'Error from server (NotFound): nodes "{name}" not found'
    pods_here = [p for p in state["pods"] if p["node"] == n["name"]]
    lines = [f"Name:         {n['name']}", f"Status:       {n['status']}", "", "Non-terminated Pods:"]
    for p in pods_here:
        lines.append(f"  {p['namespace']}  {p['name']}  cpu={p['cpu']}  memory={p['memory']}")
    if not pods_here:
        lines.append("  (none)")
    return "\n".join(lines)


def cmd_get_events(state: dict) -> str:
    events = state.get("events", [])
    if not events:
        return "No resources found in default namespace."
    headers = ["LAST SEEN", "TYPE", "REASON", "OBJECT", "MESSAGE"]
    rows = [[e["last_seen"], e["type"], e["reason"], e["object"], e["message"]] for e in events]
    return render_table(headers, rows)


def parse_cpu_millis(cpu_str: str) -> int:
    return int(cpu_str.rstrip("m"))


def parse_mem_mi(mem_str: str) -> int:
    return int(mem_str.rstrip("Mi"))


def cmd_top_nodes(state: dict) -> str:
    nodes = state.get("nodes", [])
    headers = ["NAME", "CPU(cores)", "MEMORY(bytes)"]
    rows = []
    for n in nodes:
        node_pods = [p for p in state["pods"] if p["node"] == n["name"]]
        total_cpu = sum(parse_cpu_millis(p["cpu"]) for p in node_pods)
        total_mem = sum(parse_mem_mi(p["memory"]) for p in node_pods)
        rows.append([n["name"], f"{total_cpu}m", f"{total_mem}Mi"])
    return render_table(headers, rows)


def cmd_get_all(state: dict) -> str:
    sections = []

    pod_rows = [[p["name"], p["ready"], p["status"], p["restarts"], p["age"]] for p in state["pods"]]
    sections.append(render_table(["NAME", "READY", "STATUS", "RESTARTS", "AGE"], pod_rows, prefix="pod/"))

    services = state.get("services", [])
    if services:
        svc_rows = [[s["name"], s["type"], s["cluster_ip"], f"{s['port']}/TCP", s["age"]] for s in services]
        sections.append(render_table(["NAME", "TYPE", "CLUSTER-IP", "PORT(S)", "AGE"], svc_rows, prefix="service/"))

    deployments = state.get("deployments", [])
    if deployments:
        dep_rows = [[d["name"], f"{d['ready']}/{d['desired']}", d["up_to_date"], d["available"], d["age"]] for d in deployments]
        sections.append(render_table(
            ["NAME", "READY", "UP-TO-DATE", "AVAILABLE", "AGE"], dep_rows, prefix="deployment.apps/"
        ))

    return "\n\n".join(sections)


WIDE_TOKENS = {"-o", "-o=wide", "wide", "--output=wide", "--output", "-owide"}


def handle_command(state: dict, raw: str):
    """Returns output text, or None if the player wants to exit sandbox."""
    norm = normalize(raw)
    if norm in {"exit", "quit", ":q"}:
        return None
    if norm in {"help", "?"}:
        return HELP_TEXT

    toks = norm.split()
    if not toks or toks[0] != "kubectl":
        return "Unknown command. Type 'help' for a list of supported commands."

    verb = toks[1] if len(toks) > 1 else ""
    resource = toks[2] if len(toks) > 2 else ""
    rest = toks[3:]

    if verb == "get" and resource in ("pod", "pods"):
        wide = any(t in WIDE_TOKENS for t in rest)
        names = [t for t in rest if t not in WIDE_TOKENS]
        if names:
            return cmd_get_pod(state, names[0], wide)
        return cmd_get_pods(state, wide)

    if verb == "get" and resource == "all":
        return cmd_get_all(state)

    if verb == "describe" and resource in ("pod", "pods"):
        if not rest:
            return "error: you must specify a pod name"
        return cmd_describe_pod(state, rest[0])

    if verb == "logs":
        name = resource
        if not name:
            return "error: you must specify a pod name"
        return cmd_logs(state, name)

    if verb == "top" and resource in ("pod", "pods"):
        name = rest[0] if rest else None
        return cmd_top_pod(state, name)

    if verb == "top" and resource in ("node", "nodes"):
        return cmd_top_nodes(state)

    if verb == "get" and resource in ("deployment", "deployments", "deploy"):
        name = rest[0] if rest else None
        return cmd_get_deployments(state, name)

    if verb == "describe" and resource in ("deployment", "deployments", "deploy"):
        if not rest:
            return "error: you must specify a deployment name"
        return cmd_describe_deployment(state, rest[0])

    if verb == "get" and resource in ("svc", "service", "services"):
        name = rest[0] if rest else None
        return cmd_get_services(state, name)

    if verb == "describe" and resource in ("svc", "service", "services"):
        if not rest:
            return "error: you must specify a service name"
        return cmd_describe_service(state, rest[0])

    if verb == "get" and resource in ("configmap", "configmaps", "cm"):
        name = rest[0] if rest else None
        return cmd_get_configmaps(state, name)

    if verb == "describe" and resource in ("configmap", "configmaps", "cm"):
        if not rest:
            return "error: you must specify a configmap name"
        return cmd_describe_configmap(state, rest[0])

    if verb == "get" and resource in ("secret", "secrets"):
        name = rest[0] if rest else None
        return cmd_get_secrets(state, name)

    if verb == "describe" and resource in ("secret", "secrets"):
        if not rest:
            return "error: you must specify a secret name"
        return cmd_describe_secret(state, rest[0])

    if verb == "get" and resource in ("node", "nodes"):
        name = rest[0] if rest else None
        return cmd_get_nodes(state, name)

    if verb == "describe" and resource in ("node", "nodes"):
        if not rest:
            return "error: you must specify a node name"
        return cmd_describe_node(state, rest[0])

    if verb == "get" and resource == "events":
        return cmd_get_events(state)

    return "Unknown command. Type 'help' for a list of supported commands."


def describe_state(state: dict) -> list:
    return [
        f"Cluster snapshot generated at {state['generated_at']} (namespace: {state['namespace']})",
        f"{len(state['pods'])} pods across {len(state.get('deployments', []))} deployments, "
        f"{len(state.get('services', []))} services, {len(state.get('nodes', []))} nodes. "
        "Explore with kubectl commands — find out what's broken.",
    ]


def run_sandbox() -> None:
    run_loop("kubernetes", "cluster", generate_state, handle_command, describe_state)
