"""Tests for linux_sandbox.py — state invariants, and each problem's full
diagnose-and-fix workflow (this sandbox reacts to fixes)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import linux_sandbox as L
from sandbox_common import run_command

SEEDS = range(200)


def state_with(problem):
    seed = next(s for s in SEEDS if problem in L.generate_state(s)["problems"])
    return L.generate_state(seed)


def run(state, cmd):
    return run_command(L.handle_command, state, cmd)


def df_percent(state):
    line = run(state, "df -h | grep sda1")
    return int(line.split()[4].rstrip("%"))


class TestGeneration:
    def test_exactly_two_problems(self):
        for seed in SEEDS:
            assert len(L.generate_state(seed)["problems"]) == 2

    def test_disk_never_reports_over_100_percent(self):
        for seed in SEEDS:
            assert df_percent(L.generate_state(seed)) <= 100

    def test_all_problems_occur(self):
        seen = {p for seed in SEEDS for p in L.generate_state(seed)["problems"]}
        assert seen == set(L.PROBLEMS)


class TestFailedService:
    def test_restart_fails_until_stray_process_is_killed(self):
        s = state_with("failed_service")
        assert "app.service" in run(s, "systemctl --failed")
        assert "EADDRINUSE" in run(s, "journalctl -u app")
        stray = next(sv for sv in s["services"] if sv["name"] == "app")["stray_listener"]
        assert f"pid={stray}" in run(s, "ss -tulnp | grep 8080")

        assert "failed" in run(s, "systemctl restart app")
        run(s, f"kill {stray}")
        assert run(s, "systemctl restart app") == ""
        assert "active (running)" in run(s, "systemctl status app")


class TestDiskFull:
    def test_rm_on_open_file_frees_nothing_until_restart(self):
        s = state_with("disk_full")
        before = df_percent(s)
        assert before >= 90
        biggest = max(run(s, "du -sh /var/log/*").splitlines(), key=lambda l: float(l.split()[0].rstrip("G")))
        assert biggest.endswith("/var/log/worker")

        run(s, "rm /var/log/worker/debug.log")
        assert df_percent(s) == before, "deleting a file still held open must not free space"
        assert "(deleted)" in run(s, "lsof +L1")

        run(s, "systemctl restart worker")
        assert df_percent(s) < 40
        assert run(s, "lsof +L1") == ""

    def test_truncate_frees_space_immediately(self):
        s = state_with("disk_full")
        run(s, "truncate -s 0 /var/log/worker/debug.log")
        assert df_percent(s) < 40


class TestRunawayCpu:
    def test_top_cpu_process_is_found_and_killed(self):
        s = state_with("runaway_cpu")
        load_before = float(run(s, "uptime").split("load average: ")[1].split(",")[0])
        top = run(s, "ps aux --sort=-%cpu | head -2").splitlines()[1]
        assert "generate.py" in top
        run(s, f"kill {top.split()[1]}")
        load_after = float(run(s, "uptime").split("load average: ")[1].split(",")[0])
        assert load_after < load_before


class TestMemoryHog:
    def test_postgres_stays_down_until_the_hog_is_gone(self):
        s = state_with("memory_hog")
        assert "Out of memory" in run(s, "dmesg -T | grep -i 'out of memory'")
        assert "failed" in run(s, "systemctl restart postgres")
        hog = run(s, "ps aux --sort=-%mem | head -2").splitlines()[1].split()[1]
        run(s, f"sudo kill -9 {hog}")
        assert run(s, "systemctl restart postgres") == ""
        assert "postgres" not in run(s, "systemctl --failed")


class TestCommands:
    def test_unknown_command(self):
        assert "not simulated" in run(L.generate_state(1), "vim /etc/hosts")

    def test_kill_missing_pid(self):
        assert "No such process" in run(L.generate_state(1), "kill 99999")

    def test_exit(self):
        assert L.handle_command(L.generate_state(1), "exit") is None


class TestCryptominer:
    def miner(self, s):
        return next(p for p in s["processes"] if "kdevtmpfsi" in p["command"])

    def test_miner_is_visible_the_usual_ways(self):
        s = L.generate_state(3, ["cryptominer"])
        assert "kdevtmpfsi" in run(s, "ps aux --sort=-%cpu | head -2")
        assert "45.9.148.3:3333" in run(s, "ss -tnp")
        assert "/tmp/.x/kdevtmpfsi" in run(s, f"ls -l /proc/{self.miner(s)['pid']}/exe")
        assert "ldr.sh" in run(s, "crontab -l -u www-data")

    def test_killing_it_without_removing_cron_brings_it_back_with_a_new_pid(self):
        s = L.generate_state(3, ["cryptominer"])
        old = self.miner(s)["pid"]
        run(s, f"kill -9 {old}")
        run(s, "uptime")  # time passes; cron fires
        assert self.miner(s)["pid"] != old

    def test_removing_cron_first_then_killing_sticks(self):
        s = L.generate_state(3, ["cryptominer"])
        run(s, "crontab -r -u www-data")
        run(s, f"kill -9 {self.miner(s)['pid']}")
        run(s, "uptime")
        assert not any("kdevtmpfsi" in p["command"] for p in s["processes"])
        assert L.GOAL_CHECKS["load_below_nproc"](s, {})

    def test_process_gone_goal_accounts_for_a_pending_respawn(self):
        s = L.generate_state(3, ["cryptominer"])
        run(s, f"kill -9 {self.miner(s)['pid']}")
        assert not L.GOAL_CHECKS["process_gone"](s, {"match": "kdevtmpfsi"})

    def test_crontab_r_without_u_deletes_roots_own_crontab(self):
        s = L.generate_state(3, ["cryptominer"])
        run(s, "crontab -r")
        assert any("backup" in i for i in L.collateral_issues(s))
        assert L._miner_persistence(s)


class TestSshBackdoor:
    def test_evidence_is_in_the_logs(self):
        s = L.generate_state(3, ["ssh_backdoor"])
        assert "185.220.101.4" in run(s, "last -a")
        assert "Accepted password for root" in run(s, "grep -i accepted /var/log/auth.log")
        assert "new user: name=sysupdate, UID=0" in run(s, "cat /var/log/auth.log")
        assert "sysupdate" in run(s, "awk -F: '$3 == 0' /etc/passwd")
        assert "PermitRootLogin yes" in run(s, "cat /etc/ssh/sshd_config")

    def test_cleanup_meets_the_goals(self):
        s = L.generate_state(3, ["ssh_backdoor"])
        assert not L.GOAL_CHECKS["no_extra_uid0"](s, {})
        run(s, "userdel -r sysupdate")
        run(s, "sed -i '/sysadmin@kali/d' /root/.ssh/authorized_keys")
        assert L.GOAL_CHECKS["no_extra_uid0"](s, {})
        assert L.GOAL_CHECKS["file_lacks"](s, {"file": "/root/.ssh/authorized_keys", "text": "kali"})
        assert L.collateral_issues(s) == set()

    def test_deleting_every_key_locks_out_the_admins(self):
        s = L.generate_state(3, ["ssh_backdoor"])
        run(s, "sed -i '/ssh-ed25519/d' /root/.ssh/authorized_keys")
        assert any("locked out" in i for i in L.collateral_issues(s))

    def test_healthy_server_has_only_root_as_uid0(self):
        assert L.GOAL_CHECKS["no_extra_uid0"](L.generate_state(3, []), {})
