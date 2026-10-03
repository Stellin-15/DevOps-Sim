"""kube-sim — terminal-based DevOps learning game. Entry point."""

import sys

import random

import career_path
import exam
import mystery
import progress as progress_module
import aws_sandbox
import azure_sandbox
import db_sandbox
import git_sandbox
import docker_sandbox
import gcp_sandbox
import kube_sandbox
import linux_sandbox
import sandbox
import stats
import yaml_lab
from engine import read_input, run_scenario
from scenario_loader import (
    list_categories,
    load_career_paths,
    load_all_scenarios_by_id,
    load_incidents,
    load_mysteries,
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
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "Google Cloud",
    "security": "Security",
    "servers": "Server Fleet Ops",
    "sre": "SRE (big-tech practices)",
    "git": "Git",
    "systemdesign": "System Design",
    "databases": "Databases",
    "webservers": "Web Servers & Proxies",
    "identity": "Identity & Secrets",
    "scripting": "Scripting",
    "messaging": "Messaging",
    "serverless": "Serverless",
    "performance": "Performance",
    "finops": "FinOps",
    "dataeng": "Data Engineering",
    "landscape": "The Wider Landscape",
}


def choose_from_list(scenarios: list, label: str, scenario_type: str, progress: dict):
    if not scenarios:
        print(f"\nNo {label} available yet.")
        return None

    show_category = len({s.get("category") for s in scenarios}) > 1

    print(f"\n=== {label} ===")
    for i, s in enumerate(scenarios, start=1):
        done = progress_module.is_completed(progress, s["id"], scenario_type)
        mark = "x" if done else " "
        attempts = progress_module.attempt_count(progress, s["id"])
        attempts_note = f", {attempts} attempt{'s' if attempts != 1 else ''}" if attempts else ""
        category_note = f"[{CATEGORY_LABELS.get(s.get('category'), s.get('category'))}] " if show_category else ""
        print(f"  {i}. [{mark}] [{s.get('difficulty', '?')}] {category_note}{s['title']}{attempts_note}")
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


def exam_menu(progress: dict) -> None:
    category = choose_category()
    if category == "BACK":
        return
    scenarios = load_tutorials(category) + load_incidents(category)
    label = CATEGORY_LABELS.get(category, "All Categories") if category else "All Categories"
    pool_size = sum(len(s["steps"]) for s in scenarios)

    best = exam.best_percent(progress, category)
    print(f"\n=== {label} Exam ===")
    print(f"{pool_size} possible questions." + (f" Your best so far: {best}%." if best is not None else ""))
    raw = read_input("How many questions? [10]: ")
    count = int(raw) if raw.isdigit() and int(raw) > 0 else 10
    count = min(count, pool_size)

    questions = exam.build_questions(scenarios, count, random.Random())
    outcome = exam.run_exam(questions, time_limit=count * exam.SECONDS_PER_QUESTION)
    exam.record_result(progress, category, outcome)
    progress_module.save_progress(progress)


def mystery_menu(progress: dict) -> None:
    mysteries = load_mysteries()
    for m in mysteries:
        best = progress.get("mystery_scores", {}).get(m["id"])
        m["_display_title"] = m["title"] + (f"  (best: {best}/100)" if best is not None else "")
    listing = [{**m, "title": m["_display_title"]} for m in mysteries]
    chosen = choose_from_list(listing, "Mystery Incidents", "mystery", progress)
    if not chosen:
        return
    mystery_def = next(m for m in mysteries if m["id"] == chosen["id"])
    outcome = mystery.run_mystery(mystery_def)
    progress_module.record_attempt(progress, mystery_def["id"])
    if outcome["solved"]:
        progress_module.mark_completed(progress, mystery_def["id"], "mystery")
        scores = progress.setdefault("mystery_scores", {})
        scores[mystery_def["id"]] = max(scores.get(mystery_def["id"], 0), outcome["score"])
    progress_module.save_progress(progress)


SANDBOXES = [
    ("Kubernetes — a random cluster with broken pods (look around; read-only)", sandbox.run_sandbox),
    ("Kubernetes, fixable — a cluster where each failure has a cause kubectl can fix", kube_sandbox.run_sandbox),
    ("Docker — a host with crashed, OOM-killed, or unhealthy containers", docker_sandbox.run_sandbox),
    ("Linux — a server with two real problems to find AND fix", linux_sandbox.run_sandbox),
    ("AWS — a VPC where two network layers are broken (routes, NACLs, security groups...)", aws_sandbox.run_sandbox),
    ("Azure — NSG priorities, NIC-level NSGs, and a route to a firewall that may not exist", azure_sandbox.run_sandbox),
    ("Google Cloud — tag-based firewall rules, IAP SSH, and Cloud NAT", gcp_sandbox.run_sandbox),
    ("Database — a real SQL database with bad data, a lost index, and a backup to restore from", db_sandbox.run_sandbox),
    ("Git — a real repository: wrong branch, a leaked key, a stuck merge, lost commits, a bad release", git_sandbox.run_sandbox),
]


def sandbox_menu() -> None:
    print("\n=== Choose a Sandbox ===")
    for i, (label, _) in enumerate(SANDBOXES, start=1):
        print(f"  {i}. {label}")
    print("  b. Back")
    choice = read_input("\nChoose one: ").lower()
    if choice.isdigit() and 1 <= int(choice) <= len(SANDBOXES):
        SANDBOXES[int(choice) - 1][1]()
    elif choice not in ("b", "back", "exit", "quit"):
        print("Invalid choice.")


def show_stats(progress: dict) -> None:
    data = stats.build_stats(progress, load_tutorials(), load_incidents(), load_yaml_labs(),
                             load_career_paths(), load_mysteries())
    print("\n" + stats.render_stats(data, CATEGORY_LABELS))
    read_input("\nPress Enter to go back: ")


def main_menu_loop() -> None:
    progress = progress_module.load_progress()

    while True:
        print("\n=== kube-sim ===")
        print("  1. Practice (pick a category)")
        print("  2. Career Paths (chained scenarios across categories)")
        print("  3. Writing Labs (write real config files and scripts in your own editor)")
        print("  4. Exam Mode (timed, no hints, scored)")
        print("  5. Mystery Incidents (just a symptom — find and fix it your way)")
        print("  6. Sandbox (Kubernetes, Docker, Linux, AWS, Azure, Google Cloud, a real SQL database, or a real Git repository — explore freely)")
        print("  7. Stats (your progress, exam scores, and what to do next)")
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
            scenario = choose_from_list(load_yaml_labs(), "Writing Labs", "yaml_lab", progress)
            if scenario:
                play(scenario, progress, runner=yaml_lab.run_yaml_lab)
        elif choice == "4":
            exam_menu(progress)
        elif choice == "5":
            mystery_menu(progress)
        elif choice == "6":
            sandbox_menu()
        elif choice == "7":
            show_stats(progress)
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
