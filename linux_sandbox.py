"""
Linux sandbox — a fake server with two randomly chosen real problems:
  failed_service  a service won't start: a stray old process holds its port
  disk_full       a runaway debug log filled / (and is held open by a process)
  runaway_cpu     a report script pegging the CPUs
  memory_hog      a batch job ate the RAM; the OOM killer took out postgres

Unlike the read-only Kubernetes and Docker sandboxes, this one reacts to
fixes: kill, systemctl restart/start, rm, and truncate change the state —
including the classic trap where rm on a file a process still holds open
frees no space until that process restarts (see linux-incident-002).
"""

import random
from datetime import datetime

from engine import normalize
from sandbox_common import render_table, run_loop

PROBLEMS = ["failed_service", "disk_full", "runaway_cpu", "memory_hog"]

HELP_TEXT = """Supported commands:
  uptime   nproc   hostname   uname -a   free -h   df -h
  du -sh <dir>/*   du -sh <dir>   ls -lh <dir>
  ps aux [--sort=-%cpu | --sort=-%mem]   top
  systemctl status <svc>   systemctl --failed   systemctl list-units --type=service
  systemctl restart|start <svc>
  journalctl -u <svc> [-n N]   journalctl -p err   dmesg [-T]
  ss -tulnp   lsof +L1
  kill [-9] <pid>   rm <file>   truncate -s 0 <file>
  help | exit          (pipes work: ps aux | grep python)"""

BASE_USED_GB = 9
DISK_SIZE_GB = 50


def _svc(name, desc, port=None, pid=None):
    return {"name": name, "description": desc, "active": "active", "enabled": True,
            "port": port, "pid": pid, "journal": [f"Started {desc}."], "blocked_by": None,
            "killed_by_oom": False}


def generate_state(seed=None) -> dict:
    rng = random.Random(seed)
    problems = rng.sample(PROBLEMS, k=2)
    nproc = rng.choice([2, 4])
    mem_total = rng.choice([4096, 8192])

    services = [
        _svc("sshd", "OpenSSH server daemon", 22, 610),
        _svc("cron", "Regular background program processing daemon", None, 640),
        _svc("nginx", "A high performance web server", 80, 812),
        _svc("app", "Acme API server", 8080, 1204),
        _svc("worker", "Acme background worker", None, 1290),
        _svc("postgres", "PostgreSQL database server", 5432, 920),
    ]
    processes = [
        {"pid": 1, "user": "root", "cpu": 0.0, "mem_mb": 12, "command": "/sbin/init"},
        {"pid": 610, "user": "root", "cpu": 0.0, "mem_mb": 8, "command": "sshd: /usr/sbin/sshd -D"},
        {"pid": 640, "user": "root", "cpu": 0.0, "mem_mb": 3, "command": "/usr/sbin/cron -f"},
        {"pid": 812, "user": "www-data", "cpu": 0.4, "mem_mb": 24, "command": "nginx: master process"},
        {"pid": 1204, "user": "appsvc", "cpu": 3.1, "mem_mb": 310, "command": "node /opt/app/server.js"},
        {"pid": 1290, "user": "appsvc", "cpu": 1.2, "mem_mb": 180, "command": "python3 /opt/worker/run.py"},
        {"pid": 920, "user": "postgres", "cpu": 0.8, "mem_mb": 420, "command": "postgres: main"},
    ]
    files = {
        "/var/log/syslog": {"size_gb": 0.2, "open_by": None, "deleted": False},
        "/var/log/nginx/access.log": {"size_gb": 0.6, "open_by": "nginx", "deleted": False},
        "/var/log/worker/worker.log": {"size_gb": 0.1, "open_by": "worker", "deleted": False},
        "/var/lib/postgresql/data": {"size_gb": 3.2, "open_by": "postgres", "deleted": False},
    }
    dmesg = ["[    0.000000] Linux version 6.8.0-45-generic", "[    2.114502] EXT4-fs (sda1): mounted filesystem"]

    by_name = {s["name"]: s for s in services}

    if "failed_service" in problems:
        stray_pid = rng.randint(2000, 2999)
        processes.append({"pid": stray_pid, "user": "deploy", "cpu": 0.2, "mem_mb": 90,
                          "command": "node /home/deploy/old-api/server.js"})
        app = by_name["app"]
        app.update(active="failed", pid=None, blocked_by=stray_pid, journal=[
            "Started Acme API server.",
            "Error: listen EADDRINUSE: address already in use :::8080",
            "app.service: Main process exited, code=exited, status=1/FAILURE",
            "app.service: Failed with result 'exit-code'.",
        ])
        processes[:] = [p for p in processes if p["pid"] != 1204]
        app["stray_listener"] = stray_pid

    if "disk_full" in problems:
        files["/var/log/worker/debug.log"] = {"size_gb": 35.5, "open_by": "worker", "deleted": False}
        by_name["worker"]["journal"].append("DEBUG logging enabled (LOG_LEVEL=debug)")

    if "runaway_cpu" in problems:
        processes.append({"pid": rng.randint(3000, 3999), "user": "reports", "cpu": round(nproc * 99.0, 1),
                          "mem_mb": 150, "command": "python3 /opt/reports/generate.py --all-time"})

    if "memory_hog" in problems:
        hog_pid = rng.randint(4000, 4999)
        processes.append({"pid": hog_pid, "user": "batch", "cpu": 12.0, "mem_mb": int(mem_total * 0.8),
                          "command": "java -Xmx8g -jar /opt/batch/batch.jar"})
        pg = by_name["postgres"]
        pg.update(active="failed", pid=None, killed_by_oom=True, journal=[
            "Started PostgreSQL database server.",
            "postgres.service: Main process exited, code=killed, status=9/KILL",
            "postgres.service: Failed with result 'signal'.",
        ])
        processes[:] = [p for p in processes if p["pid"] != 920]
        dmesg += [f"[86412.338101] Out of memory: Killed process 920 (postgres) total-vm:6412000kB",
                  "[86412.341007] oom_reaper: reaped process 920 (postgres)"]
        pg["oom_hog"] = hog_pid

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "hostname": f"srv-{rng.choice(['api', 'web', 'app'])}-{rng.randint(1, 9):02d}",
        "nproc": nproc,
        "mem_total_mb": mem_total,
        "uptime_days": rng.randint(3, 180),
        "services": services,
        "processes": processes,
        "files": files,
        "dmesg": dmesg,
        "problems": problems,
    }


# ------------------------------------------------------------------ helpers

def _service(state, name):
    name = name.removesuffix(".service")
    return next((s for s in state["services"] if s["name"] == name), None)


def _process(state, pid):
    return next((p for p in state["processes"] if p["pid"] == pid), None)


def _service_running(state, name) -> bool:
    s = _service(state, name)
    return bool(s and s["active"] == "active")


def _disk_used_gb(state) -> float:
    used = BASE_USED_GB
    for f in state["files"].values():
        if not f["deleted"]:
            used += f["size_gb"]
        elif f["open_by"] and _service_running(state, f["open_by"]):
            used += f["size_gb"]  # deleted but still held open: space not freed
    return used


def _gb(value: float) -> str:
    return f"{value:.1f}G" if value < 10 else f"{value:.0f}G"


def _load(state) -> float:
    return round(0.3 + sum(p["cpu"] for p in state["processes"]) / 100, 2)


def _mem_used(state) -> int:
    return sum(p["mem_mb"] for p in state["processes"]) + 400


# ----------------------------------------------------------------- commands

def cmd_uptime(state) -> str:
    load = _load(state)
    return (f" 10:42:01 up {state['uptime_days']} days,  2 users,  load average: "
            f"{load:.2f}, {load * 0.9:.2f}, {load * 0.6:.2f}")


def cmd_free(state) -> str:
    total = state["mem_total_mb"]
    used = min(_mem_used(state), total - 60)
    avail = total - used
    rows = [["Mem:", f"{total / 1024:.1f}Gi", f"{used / 1024:.1f}Gi", f"{avail * 0.4 / 1024:.1f}Gi",
             f"{avail / 1024:.1f}Gi"], ["Swap:", "0B", "0B", "0B", ""]]
    return render_table(["", "total", "used", "free", "available"], rows)


def cmd_df(state) -> str:
    used = min(_disk_used_gb(state), DISK_SIZE_GB)
    pct = round(used / DISK_SIZE_GB * 100)
    rows = [["/dev/sda1", f"{DISK_SIZE_GB}G", _gb(used), _gb(max(DISK_SIZE_GB - used, 0)), f"{pct}%", "/"],
            ["tmpfs", "2.0G", "0", "2.0G", "0%", "/dev/shm"]]
    return render_table(["Filesystem", "Size", "Used", "Avail", "Use%", "Mounted on"], rows)


def _visible_files(state) -> dict:
    return {path: f for path, f in state["files"].items() if not f["deleted"]}


def cmd_du(state, target: str) -> str:
    target = target.rstrip("/")
    list_children = target.endswith("/*")
    base = target[:-2] if list_children else target
    base = base.rstrip("/") or "/"
    files = _visible_files(state)

    def size_under(prefix):
        return sum(f["size_gb"] for p, f in files.items() if p == prefix or p.startswith(prefix.rstrip("/") + "/"))

    if not list_children:
        if size_under(base) == 0 and not any(p.startswith(base) for p in files):
            return f"du: cannot access '{base}': No such file or directory"
        return f"{_gb(size_under(base))}\t{base}"

    children = {}
    for path in files:
        if path.startswith(base.rstrip("/") + "/"):
            child = base.rstrip("/") + "/" + path[len(base.rstrip("/")) + 1:].split("/")[0]
            children[child] = size_under(child)
    if not children:
        return f"du: cannot access '{base}/*': No such file or directory"
    return "\n".join(f"{_gb(size)}\t{path}" for path, size in sorted(children.items()))


def cmd_ls(state, directory: str) -> str:
    directory = directory.rstrip("/")
    entries = [(p, f) for p, f in _visible_files(state).items() if p.rsplit("/", 1)[0] == directory]
    if not entries:
        return f"ls: cannot access '{directory}': No such file or directory"
    return "\n".join(f"-rw-r--r-- 1 appsvc appsvc {_gb(f['size_gb']):>6} Sep 27 10:40 {p.rsplit('/', 1)[1]}"
                     for p, f in entries)


def cmd_ps(state, sort_key) -> str:
    procs = list(state["processes"])
    if sort_key == "cpu":
        procs.sort(key=lambda p: -p["cpu"])
    elif sort_key == "mem":
        procs.sort(key=lambda p: -p["mem_mb"])
    total = state["mem_total_mb"]
    rows = [[p["user"], p["pid"], f"{p['cpu']:.1f}", f"{p['mem_mb'] / total * 100:.1f}", p["mem_mb"] * 1024,
             p["command"]] for p in procs]
    return render_table(["USER", "PID", "%CPU", "%MEM", "RSS", "COMMAND"], rows)


def cmd_top(state) -> str:
    load = _load(state)
    header = (f"top - 10:42:01 up {state['uptime_days']} days, load average: {load:.2f}\n"
              f"MiB Mem : {state['mem_total_mb']} total, {min(_mem_used(state), state['mem_total_mb'] - 60)} used\n")
    return header + "\n" + cmd_ps(state, "cpu")


def cmd_systemctl_status(state, name) -> str:
    s = _service(state, name)
    if not s:
        return f"Unit {name}.service could not be found."
    if s["active"] == "active":
        state_line = "active (running) since Sat 2026-09-27 08:00:12"
        pid_line = f"\n   Main PID: {s['pid']} ({s['name']})"
    else:
        state_line = "failed (Result: exit-code) since Sat 2026-09-27 03:12:05"
        pid_line = ""
    tail = "\n".join(f"Sep 27 {s['name']}[{s['pid'] or 0}]: {line}" for line in s["journal"][-3:])
    return (f"● {s['name']}.service - {s['description']}\n"
            f"     Loaded: loaded (/lib/systemd/system/{s['name']}.service; "
            f"{'enabled' if s['enabled'] else 'disabled'})\n"
            f"     Active: {state_line}{pid_line}\n\n{tail}")


def cmd_systemctl_failed(state) -> str:
    failed = [s for s in state["services"] if s["active"] == "failed"]
    if not failed:
        return "0 loaded units listed."
    rows = [[f"● {s['name']}.service", "loaded", "failed", "failed", s["description"]] for s in failed]
    return render_table(["UNIT", "LOAD", "ACTIVE", "SUB", "DESCRIPTION"], rows) + f"\n\n{len(failed)} loaded units listed."


def cmd_list_units(state) -> str:
    rows = [[f"{s['name']}.service", "loaded", s["active"], "running" if s["active"] == "active" else "failed",
             s["description"]] for s in state["services"]]
    return render_table(["UNIT", "LOAD", "ACTIVE", "SUB", "DESCRIPTION"], rows)


def cmd_restart(state, name) -> str:
    s = _service(state, name)
    if not s:
        return f"Failed to restart {name}.service: Unit {name}.service not found."
    blocker = s.get("blocked_by")
    if blocker and _process(state, blocker):
        s["active"] = "failed"
        s["journal"].append("Error: listen EADDRINUSE: address already in use :::8080")
        return (f"Job for {s['name']}.service failed because the control process exited with error code.\n"
                f"See \"systemctl status {s['name']}.service\" and \"journalctl -xeu {s['name']}.service\" for details.")
    hog = s.get("oom_hog")
    if hog and _process(state, hog):
        s["journal"].append("postgres.service: Main process exited, code=killed, status=9/KILL")
        state["dmesg"].append(f"[86999.100200] Out of memory: Killed process {s['pid'] or 921} (postgres)")
        return (f"Job for {s['name']}.service failed. The process was killed shortly after starting.\n"
                f"See \"journalctl -u {s['name']}\" and \"dmesg -T\" for details.")
    if s["active"] != "active" or s["pid"] is None:
        s["pid"] = random.randint(5000, 5999)
        s["active"] = "active"
        state["processes"].append({"pid": s["pid"], "user": "appsvc", "cpu": 1.0, "mem_mb": 200,
                                   "command": f"{s['name']} (restarted)"})
    s["journal"].append(f"Started {s['description']}.")
    # Restarting releases file handles: deleted-but-open files are freed.
    for path, f in list(state["files"].items()):
        if f["deleted"] and f["open_by"] == s["name"]:
            del state["files"][path]
    return ""


def cmd_journal(state, name, n) -> str:
    s = _service(state, name)
    if not s:
        return "-- No entries --"
    lines = s["journal"][-n:] if n else s["journal"]
    return "\n".join(f"Sep 27 03:12:05 {state['hostname']} {s['name']}[{s['pid'] or 0}]: {l}" for l in lines)


def cmd_journal_errors(state) -> str:
    lines = []
    for s in state["services"]:
        lines += [f"Sep 27 {s['name']}: {l}" for l in s["journal"] if any(w in l for w in ("Error", "Failed", "KILL", "FAILURE"))]
    lines += [f"Sep 27 kernel: {l.split('] ', 1)[1]}" for l in state["dmesg"] if "Out of memory" in l]
    return "\n".join(lines) or "-- No entries --"


def cmd_dmesg(state) -> str:
    return "\n".join(state["dmesg"])


def cmd_ss(state) -> str:
    rows = []
    for s in state["services"]:
        if s["port"] and s["active"] == "active":
            rows.append(["tcp", "LISTEN", f"0.0.0.0:{s['port']}", f"users:((\"{s['name']}\",pid={s['pid']}))"])
    for s in state["services"]:
        stray = s.get("stray_listener")
        if stray and _process(state, stray):
            rows.append(["tcp", "LISTEN", f"*:{s['port']}", f"users:((\"node\",pid={stray}))"])
    return render_table(["Netid", "State", "Local Address:Port", "Process"], rows)


def cmd_lsof_deleted(state) -> str:
    rows = []
    for path, f in state["files"].items():
        s = _service(state, f["open_by"]) if f["open_by"] else None
        if f["deleted"] and s and s["active"] == "active":
            rows.append([s["name"], s["pid"], "appsvc", "4w", "REG", int(f["size_gb"] * 1024 ** 3), 0, f"{path} (deleted)"])
    if not rows:
        return ""
    return render_table(["COMMAND", "PID", "USER", "FD", "TYPE", "SIZE/OFF", "NLINK", "NAME"], rows)


def cmd_kill(state, pid: int) -> str:
    p = _process(state, pid)
    if not p:
        return f"bash: kill: ({pid}) - No such process"
    state["processes"].remove(p)
    for s in state["services"]:
        if s["pid"] == pid:
            s["active"], s["pid"] = "failed", None
            s["journal"].append(f"{s['name']}.service: Main process exited, code=killed, status=15/TERM")
    return ""


def cmd_rm(state, path: str) -> str:
    f = state["files"].get(path)
    if not f or f["deleted"]:
        return f"rm: cannot remove '{path}': No such file or directory"
    f["deleted"] = True
    return ""


def cmd_truncate(state, path: str) -> str:
    f = state["files"].get(path)
    if not f or f["deleted"]:
        return f"truncate: cannot open '{path}' for writing: No such file or directory"
    f["size_gb"] = 0.0
    return ""


# ------------------------------------------------------------------ dispatch

def handle_command(state: dict, raw: str):
    norm = normalize(raw)
    if norm in {"exit", "quit", ":q"}:
        return None
    if norm in {"help", "?"}:
        return HELP_TEXT

    tokens = norm.split()
    if tokens and tokens[0] == "sudo":
        tokens = tokens[1:]
    if not tokens:
        return HELP_TEXT
    cmd, args = tokens[0], tokens[1:]
    positional = [a for a in args if not a.startswith("-")]

    if cmd == "uptime":
        return cmd_uptime(state)
    if cmd == "nproc":
        return str(state["nproc"])
    if cmd == "hostname":
        return state["hostname"]
    if cmd == "uname":
        return f"Linux {state['hostname']} 6.8.0-45-generic #45-Ubuntu SMP x86_64 GNU/Linux"
    if cmd == "free":
        return cmd_free(state)
    if cmd == "df":
        return cmd_df(state)
    if cmd == "du":
        return cmd_du(state, positional[0]) if positional else cmd_du(state, "/var")
    if cmd == "ls":
        return cmd_ls(state, positional[0]) if positional else "(try: ls -lh /var/log/worker)"
    if cmd == "ps":
        sort = "cpu" if "--sort=-%cpu" in args else "mem" if "--sort=-%mem" in args else None
        return cmd_ps(state, sort)
    if cmd in ("top", "htop"):
        return cmd_top(state)
    if cmd == "systemctl":
        if "--failed" in args or "--state=failed" in args:
            return cmd_systemctl_failed(state)
        if positional[:1] == ["list-units"]:
            return cmd_list_units(state)
        if positional[:1] == ["status"] and len(positional) > 1:
            return cmd_systemctl_status(state, positional[1])
        if positional[:1] in (["restart"], ["start"]) and len(positional) > 1:
            return cmd_restart(state, positional[1])
        return "(supported: systemctl status|restart|start <svc>, systemctl --failed, systemctl list-units)"
    if cmd == "journalctl":
        if "-p" in args and "err" in args:
            return cmd_journal_errors(state)
        unit = None
        for i, a in enumerate(args):
            if a == "-u" and i + 1 < len(args):
                unit = args[i + 1]
            elif a.startswith("-u") and len(a) > 2:
                unit = a[2:]
        n = next((int(args[i + 1]) for i, a in enumerate(args) if a == "-n" and i + 1 < len(args) and args[i + 1].isdigit()), None)
        if unit:
            return cmd_journal(state, unit, n)
        return "(try: journalctl -u <service> or journalctl -p err)"
    if cmd == "dmesg":
        return cmd_dmesg(state)
    if cmd in ("ss", "netstat"):
        return cmd_ss(state)
    if cmd == "lsof" and ("+l1" in args or "+L1" in args):
        return cmd_lsof_deleted(state)
    if cmd == "kill":
        pids = [a for a in positional if a.isdigit()]
        return cmd_kill(state, int(pids[0])) if pids else "kill: usage: kill [-9] pid"
    if cmd == "rm":
        return cmd_rm(state, positional[0]) if positional else "rm: missing operand"
    if cmd == "truncate":
        return cmd_truncate(state, positional[-1]) if positional else "truncate: missing file operand"
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


def describe_state(state: dict) -> list:
    return [
        f"You're logged into {state['hostname']} ({state['nproc']} CPUs, {state['mem_total_mb'] // 1024}GB RAM, "
        f"up {state['uptime_days']} days).",
        "Users are complaining. Two separate things are wrong on this box — find both, and fix them.",
    ]


def run_sandbox() -> None:
    run_loop("linux", "server", generate_state, handle_command, describe_state)
