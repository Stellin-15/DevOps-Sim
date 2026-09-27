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

import lab_formats
from engine import QuitScenario, read_input

BASE_DIR = Path(__file__).parent
WORKSPACE_DIR = BASE_DIR / "workspace"

PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]|\[\*\]")

# PyYAML follows YAML 1.1, where unquoted on/off/yes/no are booleans — so a
# GitHub Actions workflow's `on:` key parses as True. Paths still say "on".
YAML11_BOOL_KEYS = {"on": True, "yes": True, "true": True, "off": False, "no": False, "false": False}


def _lookup_key(mapping: dict, token: str):
    if token in mapping:
        return True, mapping[token]
    alias = YAML11_BOOL_KEYS.get(token.lower())
    if alias is not None and alias in mapping:
        return True, mapping[alias]
    return False, None


def get_values(obj, path: str) -> list:
    """Resolve a dotted path to every matching value. Supports [N] indices
    and [*], which matches any list element — e.g.
    'jobs.test.steps[*].run' returns the run command of every step."""
    currents = [obj]
    for token in PATH_TOKEN_RE.findall(path):
        found = []
        for current in currents:
            if token == "[*]":
                if isinstance(current, list):
                    found.extend(current)
            elif token.startswith("["):
                index = int(token[1:-1])
                if isinstance(current, list) and index < len(current):
                    found.append(current[index])
            elif isinstance(current, dict):
                ok, value = _lookup_key(current, token)
                if ok:
                    found.append(value)
        currents = found
    return currents


def get_value(obj, path: str):
    """Resolve a dotted path with optional [N] indices, e.g.
    'spec.containers[0].image'. Returns (found: bool, value)."""
    values = get_values(obj, path)
    if not values:
        return False, None
    return True, values[0]


def _equal(actual, expected) -> bool:
    """Lenient comparison for hand-written YAML: {"contains": ...} does
    substring checks, strings ignore surrounding whitespace, numbers match
    their string form (node-version: 20 vs '20'), and a one-element list
    matches its element (needs: test vs needs: [test])."""
    if isinstance(expected, dict) and "contains" in expected:
        wanted = expected["contains"]
        wanted = wanted if isinstance(wanted, list) else [wanted]
        return all(w in str(actual) for w in wanted)
    if isinstance(actual, list) and len(actual) == 1 and not isinstance(expected, list):
        return _equal(actual[0], expected)
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip() == expected.strip()
    if isinstance(actual, (int, float)) != isinstance(expected, (int, float)) and not isinstance(actual, bool):
        return str(actual).strip() == str(expected).strip()
    return actual == expected


def validate_manifest(parsed, validate_spec: dict, text: str = "") -> list:
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
        values = get_values(parsed, path)
        if not values:
            problems.append(f"{path} is missing")
        elif expected == "ANY":
            continue
        elif "[*]" in path:
            wanted = expected if isinstance(expected, list) else [expected]
            for item in wanted:
                if not any(_equal(v, item) for v in values):
                    problems.append(f"no {path} matches {item!r} (found {values!r})")
        elif not _equal(values[0], expected):
            if isinstance(expected, dict) and "contains" in expected:
                wanted = expected["contains"] if isinstance(expected["contains"], list) else [expected["contains"]]
                missing = [w for w in wanted if w not in str(values[0])]
                problems.append(f"{path} is missing: {', '.join(repr(m) for m in missing)}")
            else:
                problems.append(f"{path} is {values[0]!r}, expected {expected!r}")

    problems.extend(_check_order(parsed, validate_spec.get("order", [])))
    problems.extend(_check_absent(text or parsed.get("text", ""), validate_spec.get("absent", [])))
    return problems


def _check_order(parsed: dict, order: list) -> list:
    """Each substring must appear in parsed['lines'], in this sequence —
    e.g. a Dockerfile's COPY package*.json before RUN npm ci before COPY . ."""
    if not order:
        return []
    lines = parsed.get("lines", [])
    position = 0
    previous = None
    for wanted in order:
        index = next((i for i in range(position, len(lines)) if wanted in lines[i]), None)
        if index is None:
            if any(wanted in line for line in lines):
                return [f"'{wanted}' must come after '{previous}'"]
            return [f"missing a line containing '{wanted}'"]
        position = index + 1
        previous = wanted
    return []


def _check_absent(text: str, absent: list) -> list:
    """Substrings that must NOT appear anywhere in the file (a hardcoded
    password, an unquoted rm -rf, a secret baked into an image)."""
    return [f"file must not contain '{bad}'" for bad in absent if bad in text]


def prepare_file(step: dict) -> Path:
    WORKSPACE_DIR.mkdir(exist_ok=True)
    file_path = WORKSPACE_DIR / step["file"]
    file_path.write_text(step.get("starter_content", ""), encoding="utf-8")
    return file_path


def load_and_parse(file_path: Path, fmt: str = "yaml"):
    """Returns (parsed_obj_or_None, problems_list). fmt picks the parser
    from lab_formats: yaml, dockerfile, hcl, or bash."""
    if not file_path.exists():
        return None, ["File not found — did you save it?"]
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return None, [f"Couldn't read the file: {e}"]
    return lab_formats.parse(fmt, content)


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
        parsed, parse_problems = load_and_parse(file_path, step.get("format", "yaml"))
        if parse_problems:
            problems = parse_problems
        else:
            problems = validate_manifest(parsed, step["validate"], text=file_path.read_text(encoding="utf-8"))

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
