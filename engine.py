"""
Generic scenario engine. Knows nothing about kubectl specifically — it just
reads a scenario dict (loaded from JSON) and validates typed commands against
expected patterns. Same engine can run any category of scenario.
"""

import re

QUIT_COMMANDS = {"exit", "quit", ":q"}


class QuitScenario(Exception):
    """Raised when the player exits a scenario early, back to the menu."""


def read_input(prompt: str = "") -> str:
    """input() that strips a stray UTF-8 BOM some Windows shells (e.g. PowerShell
    piping) prepend to the first line of stdin."""
    return input(prompt).lstrip("﻿").strip()


def normalize(cmd: str) -> str:
    """Lowercase, collapse whitespace, normalize --flag=value vs --flag value."""
    cmd = cmd.lstrip("﻿").strip().lower()
    cmd = re.sub(r"\s+", " ", cmd)
    cmd = re.sub(r"(--\w[\w-]*)\s+(?=[^\s-])", r"\1=", cmd)
    return cmd


def tokens(cmd: str) -> set:
    return set(normalize(cmd).split())


def matches(player_input: str, expected_commands: list) -> bool:
    player_norm = normalize(player_input)
    for expected in expected_commands:
        expected_norm = normalize(expected)
        if player_norm == expected_norm:
            return True
        if tokens(player_norm) == tokens(expected_norm):
            return True
    return False


def is_close(player_input: str, expected_commands: list) -> bool:
    """Right verb + resource, but something else off — used for a friendlier nudge."""
    player_tokens = normalize(player_input).split()
    if not player_tokens:
        return False
    player_head = tuple(player_tokens[:2])
    for expected in expected_commands:
        expected_tokens = normalize(expected).split()
        if tuple(expected_tokens[:2]) == player_head:
            return True
    return False


def run_step(step: dict, step_num: int, total_steps: int) -> None:
    print(f"\n--- Step {step_num}/{total_steps} ---")
    print(step["prompt"])

    attempts = 0
    while True:
        player_input = read_input("\n$ ")
        if not player_input:
            continue
        if normalize(player_input) in QUIT_COMMANDS:
            raise QuitScenario()
        attempts += 1

        if matches(player_input, step["expected_commands"]):
            print(f"\n{step['fake_output']}")
            if step.get("explanation"):
                print(f"\n{step['explanation']}")
            if step.get("why"):
                print(f"\nWhy this way: {step['why']}")
            return

        if attempts == 2 and step.get("hint"):
            print(f"\nHint: {step['hint']}")
        elif attempts >= 4:
            print(f"\nThe command was: {step['expected_commands'][0]}")
        elif is_close(player_input, step["expected_commands"]):
            print("\nClose — check your flags.")
        else:
            print("\nNot quite. Try again. (type 'exit' to leave this scenario)")


def run_scenario(scenario: dict) -> bool:
    """Runs a scenario end to end. Returns True if completed, False if the player quit early."""
    print(f"\n=== {scenario['title']} ===")
    if scenario.get("intro"):
        print(f"\n{scenario['intro']}")

    steps = scenario["steps"]
    try:
        for i, step in enumerate(steps, start=1):
            run_step(step, i, len(steps))
    except QuitScenario:
        print("\nExiting scenario...")
        return False

    print("\n=== Scenario Complete ===")
    if scenario.get("resolution"):
        print(scenario["resolution"])
    return True
