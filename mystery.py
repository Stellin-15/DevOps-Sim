"""
Mystery Incidents — free-form diagnosis. The player gets only a symptom
and a live sandbox environment (Linux or Docker) with a known, hidden
root cause. No steps, no prompts: any command, any order. Typing 'solve'
checks the real outcome (goals evaluated against the sandbox state), then
asks what the root cause was, so a lucky fix doesn't count.

Scored on: fixing it (goals met), understanding it (root-cause question),
efficiency (commands used vs an expert's count), and collateral damage
(e.g. killing sshd — on a real server that locks you out).
"""

import docker_sandbox
import linux_sandbox
from engine import normalize, read_input
from sandbox_common import run_command

SANDBOXES = {
    "linux": linux_sandbox,
    "docker": docker_sandbox,
}

# Processes that should never be killed while fixing something else. The
# value is what the debrief says about it.
PROTECTED = {
    "/sbin/init": "PID 1 — killing it takes down the whole machine",
    "sshd": "sshd — on a real server you just locked yourself out",
    "nginx": "nginx — the front door for every request, taken down on the way to fixing something else",
}

MAX_ANSWER_ATTEMPTS = 2


def build_state(mystery: dict) -> dict:
    setup = mystery["setup"]
    if mystery["sandbox"] == "linux":
        return linux_sandbox.generate_state(setup.get("seed"), setup["problems"])
    return docker_sandbox.generate_state(setup.get("seed"), setup["assignments"])


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
    return values


# ------------------------------------------------------------------ goals

def _check(state: dict, goal: dict) -> bool:
    kind = goal["check"]
    if kind == "service_active":
        return linux_sandbox._service_running(state, goal["service"])
    if kind == "disk_below":
        return linux_sandbox._disk_used_gb(state) / linux_sandbox.DISK_SIZE_GB * 100 < goal["percent"]
    if kind == "load_below_nproc":
        return linux_sandbox._load(state) < state["nproc"]
    raise ValueError(f"unknown goal check: {kind}")


def unmet_goals(state: dict, mystery: dict) -> list:
    return [g["description"] for g in mystery.get("goals", []) if not _check(state, g)]


def missing_evidence(seen: list, mystery: dict) -> list:
    """Each evidence entry lists substrings (case-insensitive), any one of
    which must have appeared in the output of a command the player ran.
    Outputs only, not the typed commands, so 'echo batch.jar' can't fake
    it. Stops the root-cause question from being answerable by guessing."""
    transcript = "\n".join(seen).lower()
    return [e["description"] for e in mystery.get("evidence", [])
            if not any(s.lower() in transcript for s in e["seen_any"])]


def _protected_pids(state: dict) -> dict:
    found = {}
    for p in state.get("processes", []):
        for needle, reason in PROTECTED.items():
            if needle in p["command"]:
                found[p["pid"]] = reason
    return found


# ------------------------------------------------------------------- scoring

def score(commands: int, expert: int, wrong_answers: int, collateral: int) -> int:
    over = max(0, commands - 2 * expert)  # generous: twice the expert's count is free
    points = 100 - 20 * wrong_answers - 15 * collateral - min(30, 2 * over)
    return max(0, points)


def rating(points: int) -> str:
    if points >= 90:
        return "Excellent — senior on-call material."
    if points >= 70:
        return "Solid — you'd handle this on a real shift."
    return "Solved — now try it again with fewer commands and no collateral damage."


# ---------------------------------------------------------------------- run

def _ask_root_cause(mystery: dict, input_fn):
    q = mystery["question"]
    letters = "abcdefgh"
    print(f"\n{q['prompt']}")
    for i, option in enumerate(q["options"]):
        print(f"  {letters[i]}) {option}")
    wrong = 0
    while wrong < MAX_ANSWER_ATTEMPTS:
        raw = normalize(input_fn("\nYour answer: "))
        index = letters.find(raw) if len(raw) == 1 and raw in letters else (int(raw) - 1 if raw.isdigit() else -1)
        if not 0 <= index < len(q["options"]):
            print("Answer with a letter, e.g. 'b'.")
            continue
        if index == q["answer"]:
            print("Correct.")
            return True, wrong
        wrong += 1
        if wrong < MAX_ANSWER_ATTEMPTS:
            print("Not quite — think about what the evidence actually showed. One more try.")
    print(f"The root cause was: {q['options'][q['answer']]}")
    return False, wrong


def run_mystery(mystery: dict, input_fn=None) -> dict:
    """Returns {"solved", "score", "commands", "collateral", "gave_up"}."""
    input_fn = input_fn or read_input
    module = SANDBOXES[mystery["sandbox"]]
    state = build_state(mystery)
    protected = _protected_pids(state)
    collateral = []
    commands = 0
    seen = []

    print(f"\n=== MYSTERY: {mystery['title']} ===")
    print(f"\n{mystery['symptom']}")
    if mystery.get("goals"):
        print("\nYou're done when:")
        for g in mystery["goals"]:
            print(f"  - {g['description']}")
    print("\nInvestigate with any commands (pipes work; 'help' lists them). "
          "Type 'solve' when you're done, 'giveup' to see the answer, 'exit' to leave.")

    while True:
        raw = input_fn("\n$ ")
        norm = normalize(raw)
        if not norm:
            continue
        if norm in {"exit", "quit", ":q"}:
            print("\nLeaving the mystery unsolved.")
            return {"solved": False, "score": 0, "commands": commands, "collateral": collateral, "gave_up": False}
        if norm in {"giveup", "give up"}:
            print(f"\n=== The answer ===\n{mystery['question']['options'][mystery['question']['answer']]}")
            print(f"\n{mystery['debrief']}")
            return {"solved": False, "score": 0, "commands": commands, "collateral": collateral, "gave_up": True}
        if norm == "solve":
            remaining = unmet_goals(state, mystery)
            if remaining:
                print("\nNot fixed yet — still failing:")
                for r in remaining:
                    print(f"  - {r}")
                continue
            unproven = missing_evidence(seen, mystery)
            if unproven:
                print("\nYou haven't found the evidence for this yet — keep investigating:")
                for u in unproven:
                    print(f"  - {u}")
                continue
            correct, wrong = _ask_root_cause(mystery, input_fn)
            points = score(commands, mystery["expert_commands"], wrong, len(collateral)) if correct else 0
            print(f"\n=== {'SOLVED' if correct else 'FIXED, BUT ROOT CAUSE MISSED'} ===")
            print(f"Commands used: {commands} (an experienced engineer: ~{mystery['expert_commands']})")
            for c in collateral:
                print(f"Collateral damage: you killed {c}")
            if correct:
                print(f"Score: {points}/100 — {rating(points)}")
            print(f"\n{mystery['debrief']}")
            path = [cmd.format(**placeholders(build_state(mystery))) for cmd in mystery["solution_commands"]]
            print("\nOne efficient path:\n  " + "\n  ".join(path))
            return {"solved": correct, "score": points, "commands": commands, "collateral": collateral, "gave_up": False}

        if norm not in {"help", "?"}:
            commands += 1
        output = run_command(module.handle_command, state, raw)
        seen.append(output or "")
        if output:
            print(f"\n{output}")
        for pid, reason in list(protected.items()):
            if not any(p["pid"] == pid for p in state.get("processes", [])):
                collateral.append(reason)
                del protected[pid]
