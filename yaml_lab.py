"""
YAML Lab mode — real manifest-editing practice, the one CKA/production
skill a pure command-matcher can't simulate (see GAPS.md).

Unlike tutorials/incidents, a lab doesn't ask you to type a command that
matches a string. It writes a real file to workspace/, tells you what to
build or fix, and waits while you edit it in your own editor (vim, nano,
VS Code — whatever you'd actually use). When you type the apply command,
the game reads your real file off disk, parses it as YAML, and checks it
against the expected structure — giving field-by-field feedback, not just
pass/fail.
"""

import re
from pathlib import Path

import yaml

from engine import QuitScenario, read_input

BASE_DIR = Path(__file__).parent
WORKSPACE_DIR = BASE_DIR / "workspace"

PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]")


def get_value(obj, path: str):
    """Resolve a dotted path with optional [N] indices, e.g.
    'spec.containers[0].image'. Returns (found: bool, value)."""
    current = obj
    for token in PATH_TOKEN_RE.findall(path):
        if token.startswith("["):
            index = int(token[1:-1])
            if not isinstance(current, list) or index >= len(current):
                return False, None
            current = current[index]
        else:
            if not isinstance(current, dict) or token not in current:
                return False, None
            current = current[token]
    return True, current


def validate_manifest(parsed, validate_spec: dict) -> list:
    """Returns a list of human-readable problems; empty list means it passed."""
    if parsed is None:
        return ["File is empty or contains no valid YAML document."]
    if not isinstance(parsed, dict):
        return ["Top-level YAML must be a mapping (key: value), not a list or plain scalar."]

    problems = []

    expected_kind = validate_spec.get("kind")
    if expected_kind:
        found, kind = get_value(parsed, "kind")
        if not found:
            problems.append("kind is missing")
        elif kind != expected_kind:
            problems.append(f"kind is '{kind}', expected '{expected_kind}'")

    for path, expected in validate_spec.get("fields", {}).items():
        found, value = get_value(parsed, path)
        if not found:
            problems.append(f"{path} is missing")
        elif expected != "ANY" and value != expected:
            problems.append(f"{path} is {value!r}, expected {expected!r}")

    return problems


def prepare_file(step: dict) -> Path:
    WORKSPACE_DIR.mkdir(exist_ok=True)
    file_path = WORKSPACE_DIR / step["file"]
    file_path.write_text(step.get("starter_content", ""), encoding="utf-8")
    return file_path


def load_and_parse(file_path: Path):
    """Returns (parsed_obj_or_None, problems_list)."""
    if not file_path.exists():
        return None, ["File not found — did you save it?"]
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return None, [f"Couldn't read the file: {e}"]
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return None, [f"YAML syntax error: {e}"]
    return parsed, []


def run_yaml_step(step: dict, step_num: int, total_steps: int, file_path: Path) -> None:
    print(f"\n--- File {step_num}/{total_steps}: {step['file']} ---")
    print(step["prompt"])
    print(f"\nEdit this file in your own editor, then come back here:\n  {file_path}")

    apply_commands = {c.lower() for c in step.get("apply_commands", [])}
    attempts = 0

    while True:
        raw = read_input("\n$ ")
        if not raw:
            continue
        norm = raw.strip().lower()

        if norm in {"exit", "quit", ":q"}:
            raise QuitScenario()

        if norm not in apply_commands:
            shown = ", ".join(step.get("apply_commands", []))
            print(f"\nType one of: {shown} (or 'exit')")
            continue

        attempts += 1
        parsed, parse_problems = load_and_parse(file_path)
        problems = parse_problems if parse_problems else validate_manifest(parsed, step["validate"])

        if not problems:
            print(f"\n{step.get('fake_output', step['file'] + ' applied.')}")
            if step.get("explanation"):
                print(f"\n{step['explanation']}")
            if step.get("why"):
                print(f"\nWhy this way: {step['why']}")
            return

        print(f"\nNot quite — {len(problems)} issue(s):")
        for problem in problems[:6]:
            print(f"  - {problem}")

        if attempts == 2 and step.get("hint"):
            print(f"\nHint: {step['hint']}")
        elif attempts >= 4 and step.get("solution"):
            print(f"\nHere's a working version of {step['file']}:\n")
            print(step["solution"].rstrip())
            print(f"\n(Copy this into {file_path}, save, then re-run the apply command to continue.)")


def run_yaml_lab(scenario: dict) -> bool:
    """Runs a YAML lab end to end. Returns True if completed, False if quit early."""
    print(f"\n=== {scenario['title']} ===")
    if scenario.get("intro"):
        print(f"\n{scenario['intro']}")

    steps = scenario["steps"]
    try:
        for i, step in enumerate(steps, start=1):
            file_path = prepare_file(step)
            run_yaml_step(step, i, len(steps), file_path)
    except QuitScenario:
        print("\nExiting YAML lab...")
        return False

    print("\n=== Lab Complete ===")
    if scenario.get("resolution"):
        print(scenario["resolution"])
    return True
