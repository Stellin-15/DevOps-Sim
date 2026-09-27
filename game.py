"""kube-sim — terminal-based DevOps learning game. Entry point."""

import sys

import career_path
import progress as progress_module
import sandbox
import yaml_lab
from engine import read_input, run_scenario
from scenario_loader import (
    list_categories,
    load_career_paths,
    load_all_scenarios_by_id,
    load_incidents,
    load_tutorials,
    load_yaml_labs,
)

CATEGORY_LABELS = {
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "linux": "Linux",
    "terraform": "Terraform",
    "networking": "Networking",
    "cicd": "CI/CD",
    "monitoring": "Monitoring",
    "mlops": "MLOps",
}


def choose_from_list(scenarios: list, label: str, scenario_type: str, progress: dict):
    if not scenarios:
        print(f"\nNo {label} available yet.")
        return None

    print(f"\n=== {label} ===")
    for i, s in enumerate(scenarios, start=1):
        done = progress_module.is_completed(progress, s["id"], scenario_type)
        mark = "x" if done else " "
        attempts = progress_module.attempt_count(progress, s["id"])
        attempts_note = f", {attempts} attempt{'s' if attempts != 1 else ''}" if attempts else ""
        print(f"  {i}. [{mark}] [{s.get('difficulty', '?')}] {s['title']}{attempts_note}")
    print("  b. Back")

    choice = read_input("\nChoose one: ").lower()
    if choice in ("b", "back", "exit", "quit"):
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(scenarios):
        return scenarios[int(choice) - 1]

    print("Invalid choice.")
    return None


def choose_category():
    """Returns a category name, None for 'all categories', or 'BACK'."""
    categories = list_categories()
    print("\n=== Choose a Category ===")
    for i, cat in enumerate(categories, start=1):
        print(f"  {i}. {CATEGORY_LABELS.get(cat, cat.title())}")
    print(f"  {len(categories) + 1}. All categories")
    print("  b. Back to main menu")

    choice = read_input("\nChoose one: ").lower()
    if choice in ("b", "back", "exit", "quit"):
        return "BACK"
    if choice.isdigit():
        n = int(choice)
        if 1 <= n <= len(categories):
            return categories[n - 1]
        if n == len(categories) + 1:
            return None
    print("Invalid choice.")
    return "BACK"


def play(scenario: dict, progress: dict, runner=run_scenario) -> None:
    completed = runner(scenario)
    progress_module.record_attempt(progress, scenario["id"])
    if completed:
        progress_module.mark_completed(progress, scenario["id"], scenario["type"])
    progress_module.save_progress(progress)


def practice_menu(progress: dict) -> None:
    category = choose_category()
    if category == "BACK":
        return

    label = CATEGORY_LABELS.get(category, category.title() if category else "All Categories")

    while True:
        print(f"\n=== {label} ===")
        print("  1. Learn (tutorials)")
        print("  2. Incidents")
        print("  b. Back")

        choice = read_input("\nChoose: ").lower()
        if choice in ("b", "back", "exit", "quit"):
            return
        elif choice == "1":
            scenario = choose_from_list(load_tutorials(category), f"{label} Tutorials", "tutorial", progress)
            if scenario:
                play(scenario, progress)
        elif choice == "2":
            scenario = choose_from_list(load_incidents(category), f"{label} Incidents", "incident", progress)
            if scenario:
                play(scenario, progress)
        else:
            print("Invalid choice.")


def career_paths_menu(progress: dict) -> None:
    paths = load_career_paths()
    scenarios_by_id = load_all_scenarios_by_id()
    chosen = choose_from_list(paths, "Career Paths", "career_path", progress)
    if chosen:
        play(chosen, progress, runner=lambda p: career_path.run_career_path(p, scenarios_by_id, progress))


def main_menu_loop() -> None:
    progress = progress_module.load_progress()

    while True:
        print("\n=== kube-sim ===")
        print("  1. Practice (pick a category)")
        print("  2. Career Paths (chained scenarios across categories)")
        print("  3. YAML Labs (edit real manifests in your own editor)")
        print("  4. Sandbox (random cluster)")
        print("  q. Quit")

        choice = read_input("\nChoose: ").lower()

        if choice in ("q", "quit", "exit"):
            print("\nGoodbye!")
            return
        elif choice == "1":
            practice_menu(progress)
        elif choice == "2":
            career_paths_menu(progress)
        elif choice == "3":
            scenario = choose_from_list(load_yaml_labs(), "YAML Labs", "yaml_lab", progress)
            if scenario:
                play(scenario, progress, runner=yaml_lab.run_yaml_lab)
        elif choice == "4":
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
