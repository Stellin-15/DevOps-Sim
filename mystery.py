"""
Mystery Incidents — free-form diagnosis. The player gets only a symptom
and a live sandbox environment (Linux, Docker, AWS, Azure, or Google Cloud) with a known, hidden
root cause. No steps, no prompts: any command, any order. Typing 'solve'
checks the real outcome (goals evaluated against the sandbox state), then
asks what the root cause was, so a lucky fix doesn't count.

Scored on: fixing it (goals met), understanding it (root-cause question),
efficiency (commands used vs an expert's count), and collateral damage
(e.g. killing sshd — on a real server that locks you out).
"""

import aws_sandbox
import azure_sandbox
import db_sandbox
import git_sandbox
import docker_sandbox
import gcp_sandbox
import kube_sandbox
import linux_sandbox
import net_sandbox
import tf_sandbox
from engine import normalize, read_input
from sandbox_common import run_command

# Each sandbox module supplies the mystery hooks: generate_state(**setup),
# GOAL_CHECKS {name: fn(state, goal) -> bool}, placeholders(state) -> dict
# of ids/pids for solution_commands, and collateral_issues(state) -> set of
# dangerous conditions (a new one appearing mid-mystery is collateral).
SANDBOXES = {
    "linux": linux_sandbox,
    "docker": docker_sandbox,
    "aws": aws_sandbox,
    "azure": azure_sandbox,
    "gcp": gcp_sandbox,
    "kube": kube_sandbox,
    "db": db_sandbox,
    "git": git_sandbox,
    "terraform": tf_sandbox,
    "net": net_sandbox,
}

MAX_ANSWER_ATTEMPTS = 2


def build_state(mystery: dict) -> dict:
    return SANDBOXES[mystery["sandbox"]].generate_state(**mystery["setup"])


def placeholders(mystery: dict, state: dict) -> dict:
    return SANDBOXES[mystery["sandbox"]].placeholders(state)


# ------------------------------------------------------------------ goals

def _check(mystery: dict, state: dict, goal: dict) -> bool:
    checks = SANDBOXES[mystery["sandbox"]].GOAL_CHECKS
    if goal["check"] not in checks:
        raise ValueError(f"unknown goal check for {mystery['sandbox']}: {goal['check']}")
    return checks[goal["check"]](state, goal)


def unmet_goals(state: dict, mystery: dict) -> list:
    return [g["description"] for g in mystery.get("goals", []) if not _check(mystery, state, g)]


def missing_evidence(seen: list, mystery: dict) -> list:
    """Each evidence entry lists substrings (case-insensitive), any one of
    which must have appeared in the output of a command the player ran.
    Outputs only, not the typed commands, so 'echo batch.jar' can't fake
    it. In diagnosis-only mysteries it gates the root-cause question, so
    the answer can't be guessed; where there are goals it is only reported
    in the debrief (see run_mystery)."""
    transcript = "\n".join(seen).lower()
    return [e["description"] for e in mystery.get("evidence", [])
            if not any(s.lower() in transcript for s in e["seen_any"])]


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
    baseline_issues = module.collateral_issues(state)
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
        if norm in {"exit", "quit", ":q"} and not state.get("session"):
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
            # Evidence only gates diagnosis-only mysteries (no goals), where
            # nothing else stops a guess. With goals, the fix is the proof —
            # and fixing first can make the evidence impossible to see (a
            # timeout can't be observed once the route exists), so gating
            # there would trap exactly the player who went straight to the cause.
            unproven = missing_evidence(seen, mystery)
            if unproven and not mystery.get("goals"):
                print("\nYou haven't found the evidence for this yet — keep investigating:")
                for u in unproven:
                    print(f"  - {u}")
                continue
            correct, wrong = _ask_root_cause(mystery, input_fn)
            points = score(commands, mystery["expert_commands"], wrong, len(collateral)) if correct else 0
            print(f"\n=== {'SOLVED' if correct else 'FIXED, BUT ROOT CAUSE MISSED'} ===")
            print(f"Commands used: {commands} (an experienced engineer: ~{mystery['expert_commands']})")
            for c in collateral:
                print(f"Collateral damage: you {c}")
            if correct:
                print(f"Score: {points}/100 — {rating(points)}")
            if unproven:
                print("\nYou fixed it without looking at (worth knowing how to check):")
                for u in unproven:
                    print(f"  - {u}")
            print(f"\n{mystery['debrief']}")
            path = [cmd.format(**placeholders(mystery, build_state(mystery))) for cmd in mystery["solution_commands"]]
            print("\nOne efficient path:\n  " + "\n  ".join(path))
            return {"solved": correct, "score": points, "commands": commands, "collateral": collateral, "gave_up": False}

        if norm not in {"help", "?"}:
            commands += 1
        output = run_command(module.handle_command, state, raw)
        seen.append(output or "")
        if output:
            print(f"\n{output}")
        for issue in sorted(module.collateral_issues(state) - baseline_issues):
            if issue not in collateral:
                collateral.append(issue)
