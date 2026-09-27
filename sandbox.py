"""
Sandbox mode — no scoring, no steps. Generates a random fake cluster (pods
with random names, statuses, and resource usage) and lets the player poke at
it with free-form kubectl-style commands.

State is written to a local JSON file while the session is active. On exit,
the player chooses to keep it (saved under sandbox_data/saved/ for future
sessions to load) or discard it (the file is deleted).
"""

import json
import random
import re
import string
from datetime import datetime
from pathlib import Path

from engine import normalize, read_input

BASE_DIR = Path(__file__).parent
SANDBOX_DIR = BASE_DIR / "sandbox_data"
SAVED_DIR = SANDBOX_DIR / "saved"
CURRENT_FILE = SANDBOX_DIR / "current_session.json"

SERVICE_NAMES = [
    "checkout-service", "auth-service", "payment-gateway", "frontend",
    "redis-cache", "user-api", "notification-worker", "inventory-service",
    "order-processor", "analytics-collector", "billing-service", "email-sender",
]

VERSIONS = ["1.0.0", "1.2.3", "1.4.1", "2.0.1", "2.3.0", "latest", "3.1.0"]

STATUSES = ["Running"] * 65 + ["CrashLoopBackOff"] * 10 + ["Pending"] * 10 \
    + ["OOMKilled"] * 10 + ["Error"] * 5

HELP_TEXT = """Supported commands:
  kubectl get pods [-o wide]
  kubectl get pod <name>
  kubectl get all
  kubectl describe pod <name>
  kubectl logs <name>
  kubectl top pod [<name>]
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


def generate_state() -> dict:
    services = random.sample(SERVICE_NAMES, k=random.randint(4, 7))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "namespace": "default",
        "pods": [generate_pod(s) for s in services],
    }


def find_pod(state: dict, name: str):
    name = name.lower()
    for pod in state["pods"]:
        if pod["name"].lower() == name:
            return pod
    return None


def format_pod_row(pod: dict, wide: bool) -> str:
    row = f"{pod['name']:<38}{pod['ready']:<8}{pod['status']:<20}{pod['restarts']:<10}{pod['age']:<8}"
    if wide:
        row += f"{pod['node']:<10}"
    return row


def cmd_get_pods(state: dict, wide: bool) -> str:
    header = f"{'NAME':<38}{'READY':<8}{'STATUS':<20}{'RESTARTS':<10}{'AGE':<8}"
    if wide:
        header += f"{'NODE':<10}"
    lines = [header] + [format_pod_row(pod, wide) for pod in state["pods"]]
    return "\n".join(lines)


def cmd_get_pod(state: dict, name: str, wide: bool) -> str:
    pod = find_pod(state, name)
    if not pod:
        return f'Error from server (NotFound): pods "{name}" not found'
    header = f"{'NAME':<38}{'READY':<8}{'STATUS':<20}{'RESTARTS':<10}{'AGE':<8}"
    if wide:
        header += f"{'NODE':<10}"
    return header + "\n" + format_pod_row(pod, wide)


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
    header = f"{'NAME':<38}{'CPU':<10}{'MEMORY':<10}"
    if name:
        pod = find_pod(state, name)
        if not pod:
            return f'Error from server (NotFound): pods "{name}" not found'
        return header + "\n" + f"{pod['name']:<38}{pod['cpu']:<10}{pod['memory']:<10}"
    lines = [header]
    for pod in state["pods"]:
        lines.append(f"{pod['name']:<38}{pod['cpu']:<10}{pod['memory']:<10}")
    return "\n".join(lines)


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
        return cmd_get_pods(state, wide=False)

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

    return "Unknown command. Type 'help' for a list of supported commands."


def list_saved_sessions() -> list:
    if not SAVED_DIR.exists():
        return []
    return sorted(SAVED_DIR.glob("*.json"))


def save_current(state: dict) -> None:
    SANDBOX_DIR.mkdir(exist_ok=True)
    with open(CURRENT_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def choose_or_generate_state() -> dict:
    saved = list_saved_sessions()
    if saved:
        print("\nYou have saved cluster states:")
        for i, path in enumerate(saved, start=1):
            print(f"  {i}. {path.stem}")
        print(f"  {len(saved) + 1}. Generate a new random cluster")
        choice = read_input("\nChoose an option: ")
        if choice.isdigit() and 1 <= int(choice) <= len(saved):
            with open(saved[int(choice) - 1], "r", encoding="utf-8") as f:
                return json.load(f)
    return generate_state()


def prompt_keep(state: dict) -> None:
    choice = read_input("\nKeep this cluster state for future reference? (y/N): ").lower()
    if choice == "y":
        SAVED_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = SAVED_DIR / f"session-{ts}.json"
        dest.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"Saved. You can pick this cluster again next time you enter Sandbox.")
    else:
        if CURRENT_FILE.exists():
            CURRENT_FILE.unlink()
        print("Discarded — this cluster state is gone.")


def run_sandbox() -> None:
    print("\n=== Sandbox Mode ===")
    state = choose_or_generate_state()
    save_current(state)

    print(f"\nCluster snapshot generated at {state['generated_at']} (namespace: {state['namespace']})")
    print(f"{len(state['pods'])} pods running. Explore with kubectl commands — find out what's broken.")
    print("Type 'help' for supported commands, 'exit' to leave sandbox.")

    while True:
        raw = read_input("\n$ ")
        if not raw:
            continue
        output = handle_command(state, raw)
        if output is None:
            break
        print(f"\n{output}")

    prompt_keep(state)
