"""kube-sim — terminal-based Kubernetes/DevOps learning game. Entry point."""

import sys

import progress as progress_module
import sandbox
from engine import read_input, run_scenario
from scenario_loader import load_incidents, load_tutorials


def choose_from_list(scenarios: list, label: str, scenario_type: str, progress: dict):
    if not scenarios:
        print(f"\nNo {label} available yet.")
        return None

    print(f"\n=== {label.title()} ===")
    for i, s in enumerate(scenarios, start=1):
        done = progress_module.is_completed(progress, s["id"], scenario_type)
        mark = "x" if done else " "
        attempts = progress_module.attempt_count(progress, s["id"])
        attempts_note = f", {attempts} attempt{'s' if attempts != 1 else ''}" if attempts else ""
        print(f"  {i}. [{mark}] [{s.get('difficulty', '?')}] {s['title']}{attempts_note}")
    print("  b. Back to main menu")

    choice = read_input("\nChoose one: ").lower()
    if choice in ("b", "back", "exit", "quit"):
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(scenarios):
        return scenarios[int(choice) - 1]

    print("Invalid choice.")
    return None


def play(scenario: dict, progress: dict) -> None:
    completed = run_scenario(scenario)
    progress_module.record_attempt(progress, scenario["id"])
    if completed:
        progress_module.mark_completed(progress, scenario["id"], scenario["type"])
    progress_module.save_progress(progress)


def main_menu_loop() -> None:
    tutorials = load_tutorials()
    incidents = load_incidents()
    progress = progress_module.load_progress()

    while True:
        print("\n=== kube-sim ===")
        print("  1. Learn (tutorials)")
        print("  2. Incidents")
        print("  3. Sandbox (random cluster)")
        print("  q. Quit")

        choice = read_input("\nChoose: ").lower()

        if choice in ("q", "quit", "exit"):
            print("\nGoodbye!")
            return
        elif choice == "1":
            scenario = choose_from_list(tutorials, "tutorials", "tutorial", progress)
            if scenario:
                play(scenario, progress)
        elif choice == "2":
            scenario = choose_from_list(incidents, "incidents", "incident", progress)
            if scenario:
                play(scenario, progress)
        elif choice == "3":
            sandbox.run_sandbox()
        else:
            print("Invalid choice.")


def main() -> None:
    try:
        main_menu_loop()
    except (KeyboardInterrupt, EOFError):
        print("\n\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
