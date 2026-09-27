"""kube-sim — terminal-based Kubernetes/DevOps learning game. Entry point."""

import sys

import sandbox
from engine import read_input, run_scenario
from scenario_loader import load_incidents, load_tutorials


def choose_from_list(scenarios: list, label: str):
    if not scenarios:
        print(f"\nNo {label} available yet.")
        return None

    print(f"\n=== {label.title()} ===")
    for i, s in enumerate(scenarios, start=1):
        print(f"  {i}. [{s.get('difficulty', '?')}] {s['title']}")
    print("  b. Back to main menu")

    choice = read_input("\nChoose one: ").lower()
    if choice in ("b", "back", "exit", "quit"):
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(scenarios):
        return scenarios[int(choice) - 1]

    print("Invalid choice.")
    return None


def main_menu_loop() -> None:
    tutorials = load_tutorials()
    incidents = load_incidents()

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
            scenario = choose_from_list(tutorials, "tutorials")
            if scenario:
                run_scenario(scenario)
        elif choice == "2":
            scenario = choose_from_list(incidents, "incidents")
            if scenario:
                run_scenario(scenario)
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
