"""
Career Path mode — chains existing tutorials/incidents across categories
into one continuous playthrough, e.g. write infra with Terraform,
containerize with Docker, deploy to Kubernetes, wire up CI/CD, add
monitoring. Each step is just a normal scenario run via engine.run_scenario
— this module only resolves step ids to scenario dicts and sequences them.
"""

import progress as progress_module
from engine import run_scenario


def run_career_path(path: dict, scenarios_by_id: dict, progress: dict) -> bool:
    """Runs every step in path['steps'] in order. Returns True only if
    every step was completed; stops at the first step the player quits.

    Each sub-scenario's own attempt/completion is recorded into `progress`
    too (not just the path's own completion) — so finishing a tutorial via
    a career path also credits it when browsing that category directly."""
    print(f"\n=== Career Path: {path['title']} ===")
    if path.get("intro"):
        print(f"\n{path['intro']}")

    step_ids = path["steps"]
    for i, step_id in enumerate(step_ids, start=1):
        scenario = scenarios_by_id.get(step_id)
        if scenario is None:
            print(f"\n[skipping missing scenario: {step_id}]")
            continue

        print(f"\n>>> Stage {i}/{len(step_ids)} of this path <<<")
        completed = run_scenario(scenario)
        progress_module.record_attempt(progress, scenario["id"])
        if completed:
            progress_module.mark_completed(progress, scenario["id"], scenario["type"])
        if not completed:
            print(f"\nStopped mid-path at stage {i}/{len(step_ids)}. Re-enter this path to try again.")
            return False

    print(f"\n=== Career Path Complete: {path['title']} ===")
    if path.get("resolution"):
        print(path["resolution"])
    return True
