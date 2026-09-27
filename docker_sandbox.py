"""
Docker sandbox — a fake Docker host with 4-6 containers, one or two of
which have a real, randomly chosen problem (OOM-killed, crashed on
startup, stuck in a restart loop, or failing its healthcheck), plus
dangling images and volumes quietly eating disk. Explore it with the same
docker commands you'd use on a real host. No scoring — the point is
practicing the investigation.
"""

import random
from datetime import datetime

from engine import normalize
from sandbox_common import render_table, run_loop

APPS = [
    {"name": "web", "image": "acme/web:2.4.0", "ports": "0.0.0.0:8080->3000/tcp", "cmd": "node server.js"},
    {"name": "api", "image": "acme/api:1.9.2", "ports": "0.0.0.0:9000->9000/tcp", "cmd": "python -m api"},
    {"name": "worker", "image": "acme/worker:1.9.2", "ports": "", "cmd": "python -m worker"},
    {"name": "db", "image": "postgres:16", "ports": "5432/tcp", "cmd": "postgres"},
    {"name": "cache", "image": "redis:7", "ports": "6379/tcp", "cmd": "redis-server"},
    {"name": "proxy", "image": "nginx:1.25", "ports": "0.0.0.0:80->80/tcp", "cmd": "nginx -g daemon off;"},
]

PROBLEMS = ["oom", "crash", "restart_loop", "unhealthy"]

HELP_TEXT = """Supported commands:
  docker ps [-a]                       docker images
  docker logs [--tail N] <container>   docker top <container>
  docker inspect <container> [--format '{{.State.ExitCode}}']
      formats: .State.Status .State.ExitCode .State.OOMKilled
               .State.Health.Status .RestartCount .Config.Image
               .HostConfig.RestartPolicy.Name .HostConfig.Memory
               .NetworkSettings.Networks
  docker stats [--no-stream] [container]
  docker exec [-it] <container> env | ps aux
  docker volume ls [-f dangling=true]  docker network ls
  docker network inspect <network>     docker system df
  help | exit          (pipes work: docker ps -a | grep Exited)"""


def _hex(rng: random.Random, n: int = 12) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _healthy_logs(app: dict) -> list:
    return {
        "web": ["Server listening on port 3000", "GET / 200 12ms", "GET /api/products 200 48ms"],
        "api": ["Uvicorn running on http://0.0.0.0:9000", "GET /health 200", "POST /orders 201"],
        "worker": ["Connected to queue", "Processed job 8812", "Processed job 8813"],
        "db": ["database system is ready to accept connections"],
        "cache": ["Ready to accept connections tcp"],
        "proxy": ["start worker processes", "GET / HTTP/1.1 200"],
    }[app["name"]]


def _make_container(app: dict, problem, rng: random.Random, network: str) -> dict:
    mem_limit = rng.choice([256, 512, 1024])
    c = {
        "id": _hex(rng),
        "name": app["name"],
        "image": app["image"],
        "command": app["cmd"],
        "ports": app["ports"],
        "network": network,
        "restart_policy": rng.choice(["unless-stopped", "always", "no"]),
        "restart_count": 0,
        "exit_code": 0,
        "oom_killed": False,
        "health": "healthy" if app["name"] in ("web", "api") else None,
        "state": "running",
        "status": f"Up {rng.randint(2, 30)} hours",
        "cpu_percent": round(rng.uniform(0.2, 25.0), 2),
        "mem_limit_mb": mem_limit,
        "mem_used_mb": rng.randint(int(mem_limit * 0.15), int(mem_limit * 0.6)),
        "env": [f"NODE_ENV=production", f"PORT={app['ports'].split('->')[-1].split('/')[0] if '->' in app['ports'] else ''}"],
        "logs": _healthy_logs(app),
        "problem": problem,
    }

    if problem == "oom":
        c.update(state="exited", status="Exited (137) 4 minutes ago", exit_code=137, oom_killed=True,
                 mem_used_mb=0, cpu_percent=0.0,
                 logs=c["logs"] + ["Loading product catalog into memory (2.1GB)..."])
    elif problem == "crash":
        c.update(state="exited", status="Exited (1) 11 minutes ago", exit_code=1, mem_used_mb=0, cpu_percent=0.0,
                 env=[e for e in c["env"] if not e.startswith("DATABASE_URL")],
                 logs=["Starting...", "KeyError: 'DATABASE_URL'", "  File \"/app/config.py\", line 8, in <module>",
                       "    DB = os.environ['DATABASE_URL']"])
    elif problem == "restart_loop":
        c.update(state="restarting", status="Restarting (1) 8 seconds ago", exit_code=1,
                 restart_policy="always", restart_count=rng.randint(40, 300), cpu_percent=0.0,
                 logs=["Error: config file not found: /etc/app/config.yml"] * 4)
    elif problem == "unhealthy":
        c.update(status=f"Up {rng.randint(1, 5)} hours (unhealthy)", health="unhealthy",
                 cpu_percent=round(rng.uniform(85, 99), 2),
                 logs=c["logs"] + ["WARN event loop blocked for 4812ms", "GET /health 503 5002ms",
                                   "WARN event loop blocked for 5120ms"])
        c["health"] = "unhealthy"
    else:
        c["env"].append("DATABASE_URL=postgres://db:5432/app")
    return c


def generate_state(seed=None) -> dict:
    rng = random.Random(seed)
    apps = rng.sample(APPS, k=rng.randint(4, 6))
    # Only app containers break; the db/cache/proxy stay healthy so the
    # problem is always in something the player's team would own.
    breakable = [a["name"] for a in apps if a["name"] in ("web", "api", "worker")] or [apps[0]["name"]]
    broken = rng.sample(breakable, k=min(len(breakable), rng.randint(1, 2)))
    problems = rng.sample(PROBLEMS, k=len(broken))
    assignments = dict(zip(broken, problems))

    containers = [_make_container(a, assignments.get(a["name"]), rng, "app-net") for a in apps]

    images = [{"repository": c["image"].split(":")[0], "tag": c["image"].split(":")[1],
               "id": _hex(rng), "size_mb": rng.randint(40, 420)} for c in containers]
    images += [{"repository": "<none>", "tag": "<none>", "id": _hex(rng), "size_mb": rng.randint(300, 900)}
               for _ in range(rng.randint(3, 8))]
    volumes = [{"name": "db-data", "dangling": False}] + [
        {"name": _hex(rng, 24), "dangling": True} for _ in range(rng.randint(2, 6))]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "hostname": f"docker-host-{rng.randint(1, 9)}",
        "containers": containers,
        "images": images,
        "volumes": volumes,
        "networks": [
            {"name": "bridge", "driver": "bridge", "id": _hex(rng)},
            {"name": "host", "driver": "host", "id": _hex(rng)},
            {"name": "none", "driver": "null", "id": _hex(rng)},
            {"name": "app-net", "driver": "bridge", "id": _hex(rng)},
        ],
    }


def find_container(state: dict, ref: str):
    """By exact name, or by unique id prefix (3+ chars) — like Docker."""
    ref = ref.lower()
    for c in state["containers"]:
        if c["name"] == ref:
            return c
    matches = [c for c in state["containers"] if len(ref) >= 3 and c["id"].startswith(ref)]
    return matches[0] if len(matches) == 1 else None


def _no_such(ref: str) -> str:
    return f"Error response from daemon: No such container: {ref}"


def cmd_ps(state: dict, show_all: bool) -> str:
    rows = [[c["id"], c["image"], f"\"{c['command'][:18]}\"", c["status"], c["ports"], c["name"]]
            for c in state["containers"] if show_all or c["state"] != "exited"]
    return render_table(["CONTAINER ID", "IMAGE", "COMMAND", "STATUS", "PORTS", "NAMES"], rows)


def cmd_images(state: dict) -> str:
    rows = [[i["repository"], i["tag"], i["id"], f"{i['size_mb']}MB"] for i in state["images"]]
    return render_table(["REPOSITORY", "TAG", "IMAGE ID", "SIZE"], rows)


def cmd_logs(state: dict, ref: str, tail) -> str:
    c = find_container(state, ref)
    if not c:
        return _no_such(ref)
    lines = c["logs"]
    return "\n".join(lines[-tail:] if tail else lines)


INSPECT_FORMATS = {
    "{{.state.status}}": lambda c: c["state"],
    "{{.state.exitcode}}": lambda c: str(c["exit_code"]),
    "{{.state.oomkilled}}": lambda c: str(c["oom_killed"]).lower(),
    "{{.state.health.status}}": lambda c: c["health"] or "<no value>",
    "{{.restartcount}}": lambda c: str(c["restart_count"]),
    "{{.config.image}}": lambda c: c["image"],
    "{{.hostconfig.restartpolicy.name}}": lambda c: c["restart_policy"],
    "{{.hostconfig.memory}}": lambda c: str(c["mem_limit_mb"] * 1024 * 1024),
    "{{.networksettings.networks}}": lambda c: f"map[{c['network']}:0xc000a1b200]",
}


def cmd_inspect(state: dict, ref: str, fmt) -> str:
    c = find_container(state, ref)
    if not c:
        return _no_such(ref)
    if fmt:
        fmt = fmt.strip("'\"")
        if fmt not in INSPECT_FORMATS:
            return f"(format {fmt} isn't simulated — type 'help' for the supported ones)"
        return INSPECT_FORMATS[fmt](c)
    health = f'\n        "Health": {{"Status": "{c["health"]}"}},' if c["health"] else ""
    return (
        f'[{{\n    "Id": "{c["id"]}...",\n    "Name": "/{c["name"]}",\n    "State": {{\n'
        f'        "Status": "{c["state"]}",\n        "ExitCode": {c["exit_code"]},\n'
        f'        "OOMKilled": {str(c["oom_killed"]).lower()},{health}\n    }},\n'
        f'    "RestartCount": {c["restart_count"]},\n    "Config": {{"Image": "{c["image"]}", '
        f'"Env": {c["env"]}}},\n    "HostConfig": {{"Memory": {c["mem_limit_mb"] * 1024 * 1024}, '
        f'"RestartPolicy": {{"Name": "{c["restart_policy"]}"}}}}\n}}]'
    )


def cmd_stats(state: dict, ref) -> str:
    running = [c for c in state["containers"] if c["state"] != "exited"]
    if ref:
        c = find_container(state, ref)
        if not c:
            return _no_such(ref)
        running = [c]
    rows = [[c["id"], c["name"], f"{c['cpu_percent']:.2f}%",
             f"{c['mem_used_mb']}MiB / {c['mem_limit_mb']}MiB",
             f"{c['mem_used_mb'] / c['mem_limit_mb'] * 100:.2f}%"] for c in running]
    return render_table(["CONTAINER ID", "NAME", "CPU %", "MEM USAGE / LIMIT", "MEM %"], rows)


def _not_running(c: dict) -> str:
    return f"Error response from daemon: container {c['id']} is not running"


def cmd_top(state: dict, ref: str) -> str:
    c = find_container(state, ref)
    if not c:
        return _no_such(ref)
    if c["state"] == "exited":
        return _not_running(c)
    return render_table(["UID", "PID", "PPID", "CMD"], [["root", 4000 + len(c["name"]), 3990, c["command"]]])


def cmd_exec(state: dict, ref: str, rest: list) -> str:
    c = find_container(state, ref)
    if not c:
        return _no_such(ref)
    if c["state"] != "running":
        return _not_running(c)
    if rest[:1] == ["env"]:
        return "\n".join(["PATH=/usr/local/bin:/usr/bin:/bin", f"HOSTNAME={c['id']}"] + [e for e in c["env"] if not e.endswith("=")])
    if rest[:2] == ["ps", "aux"]:
        return f"PID   USER  %CPU  COMMAND\n1     root  {c['cpu_percent']}  {c['command']}"
    return "(only 'env' and 'ps aux' are simulated inside containers)"


def cmd_volumes(state: dict, dangling_only: bool) -> str:
    rows = [["local", v["name"]] for v in state["volumes"] if v["dangling"] or not dangling_only]
    return render_table(["DRIVER", "VOLUME NAME"], rows)


def cmd_networks(state: dict) -> str:
    return render_table(["NETWORK ID", "NAME", "DRIVER", "SCOPE"],
                        [[n["id"], n["name"], n["driver"], "local"] for n in state["networks"]])


def cmd_network_inspect(state: dict, name: str) -> str:
    if not any(n["name"] == name for n in state["networks"]):
        return f"Error response from daemon: network {name} not found"
    attached = [c for c in state["containers"] if c["network"] == name and c["state"] != "exited"]
    body = ",\n".join(f'        "{c["id"]}": {{"Name": "{c["name"]}"}}' for c in attached)
    return f'[{{\n    "Name": "{name}",\n    "Containers": {{\n{body}\n    }}\n}}]'


def cmd_system_df(state: dict) -> str:
    img_total = sum(i["size_mb"] for i in state["images"])
    img_reclaim = sum(i["size_mb"] for i in state["images"] if i["repository"] == "<none>")
    stopped = [c for c in state["containers"] if c["state"] == "exited"]
    dangling = [v for v in state["volumes"] if v["dangling"]]
    rows = [
        ["Images", len(state["images"]), len(state["containers"]), f"{img_total / 1000:.2f}GB",
         f"{img_reclaim / 1000:.2f}GB ({img_reclaim * 100 // max(img_total, 1)}%)"],
        ["Containers", len(state["containers"]), len(state["containers"]) - len(stopped), "48MB",
         f"{len(stopped) * 12}MB"],
        ["Local Volumes", len(state["volumes"]), len(state["volumes"]) - len(dangling),
         f"{len(state['volumes']) * 180}MB", f"{len(dangling) * 180}MB"],
    ]
    return render_table(["TYPE", "TOTAL", "ACTIVE", "SIZE", "RECLAIMABLE"], rows)


def _flag_value(tokens: list, name: str):
    for i, tok in enumerate(tokens):
        if tok.startswith(name + "="):
            return tok.split("=", 1)[1]
        if tok == name and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def handle_command(state: dict, raw: str):
    """Returns output text, or None if the player wants to exit."""
    norm = normalize(raw)
    if norm in {"exit", "quit", ":q"}:
        return None
    if norm in {"help", "?"}:
        return HELP_TEXT

    tokens = norm.split()
    if not tokens or tokens[0] != "docker":
        return "Unknown command. This is a Docker host — try 'docker ps -a', or type 'help'."
    args = tokens[1:]
    if args[:2] == ["container", "ls"]:
        args = ["ps"] + args[2:]
    if args[:2] == ["image", "ls"]:
        args = ["images"] + args[2:]
    if not args:
        return HELP_TEXT
    verb, rest = args[0], args[1:]
    positional = [t for t in rest if not t.startswith("-")]

    if verb == "ps":
        return cmd_ps(state, show_all=bool({"-a", "--all"} & set(rest)))
    if verb == "images":
        return cmd_images(state)
    if verb == "logs":
        tail = _flag_value(rest, "--tail") or _flag_value(rest, "-n")
        refs = [t for t in positional if t != tail]
        if not refs:
            return "\"docker logs\" requires exactly 1 argument."
        return cmd_logs(state, refs[-1], int(tail) if tail and tail.isdigit() else None)
    if verb == "inspect":
        fmt = _flag_value(rest, "--format") or _flag_value(rest, "-f")
        refs = [t for t in positional if t != fmt and not t.startswith("'{{") and not t.startswith("{{")]
        if not refs:
            return "\"docker inspect\" requires at least 1 argument."
        return cmd_inspect(state, refs[0], fmt)
    if verb == "stats":
        return cmd_stats(state, positional[0] if positional else None)
    if verb == "top":
        return cmd_top(state, positional[0]) if positional else "\"docker top\" requires a container."
    if verb == "exec":
        if not positional:
            return "\"docker exec\" requires a container and a command."
        return cmd_exec(state, positional[0], positional[1:])
    if verb == "volume" and positional[:1] == ["ls"]:
        return cmd_volumes(state, dangling_only="dangling=true" in norm)
    if verb == "network" and positional[:1] == ["ls"]:
        return cmd_networks(state)
    if verb == "network" and positional[:1] == ["inspect"] and len(positional) > 1:
        return cmd_network_inspect(state, positional[1])
    if verb == "system" and positional[:1] == ["df"]:
        return cmd_system_df(state)
    return f"'docker {verb}' isn't simulated in the sandbox. Type 'help' for supported commands."


def describe_state(state: dict) -> list:
    running = sum(1 for c in state["containers"] if c["state"] != "exited")
    return [
        f"Host {state['hostname']} (snapshot {state['generated_at']})",
        f"{len(state['containers'])} containers ({running} not exited), {len(state['images'])} images, "
        f"{len(state['volumes'])} volumes. Something here isn't right — find out what, and why.",
    ]


def run_sandbox() -> None:
    run_loop("docker", "Docker host", generate_state, handle_command, describe_state)
