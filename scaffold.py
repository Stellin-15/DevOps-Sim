"""
`python game.py add-scenario` — scaffolds a new content file so nobody has
to hand-write the JSON skeleton (SPEC.md's v6).

    python game.py add-scenario                      # asks for everything
    python game.py add-scenario --type tutorial --category git --title "Sparse checkout" --steps 4
    python game.py add-scenario --type mystery --sandbox db --title "..."

It picks the next free id in the project's naming scheme (Kubernetes keeps
its unprefixed tutorial-NNN / incident-NNN; every other category prefixes
its name), writes the file to the right folder, and fills every field the
content tests require with a TODO(scaffold) marker. The marker is a
deliberate tripwire: tests/test_scaffold.py fails while any content file
still contains one, so a half-written scenario can't be committed quietly.
"""

import argparse
import json
import re
from pathlib import Path

from engine import read_input
from scenario_loader import SCENARIOS_DIR, list_categories

TODO = "TODO(scaffold)"
TYPES = ["tutorial", "incident", "yaml_lab", "career_path", "mystery"]
DIFFICULTIES = ["beginner", "intermediate", "advanced"]
COMMANDS_DIR = SCENARIOS_DIR.parent / "commands"


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-") or "untitled"


def id_prefix(kind: str, category: str = None, sandbox: str = None) -> str:
    if kind in ("tutorial", "incident"):
        return kind if category == "kubernetes" else f"{category}-{kind}"
    return {"yaml_lab": "yaml", "career_path": "path", "mystery": f"mystery-{sandbox}"}[kind]


def folder_for(kind: str, category: str = None, root: Path = SCENARIOS_DIR) -> Path:
    if kind in ("tutorial", "incident"):
        return root / category / f"{kind}s"
    return root / {"yaml_lab": "yaml_labs", "career_path": "career_paths", "mystery": "mysteries"}[kind]


def next_id(folder: Path, prefix: str) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)")
    numbers = [int(m.group(1)) for p in folder.glob("*.json") if (m := pattern.match(p.name))]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _todo(what: str) -> str:
    return f"{TODO}: {what}"


def _sandbox_hints(sandbox: str):
    """The seeded problems and goal checks a mystery on this sandbox can use."""
    try:
        import mystery
        module = mystery.SANDBOXES[sandbox]
    except (ImportError, KeyError):
        return "a problem name", "a goal check"
    problems = ", ".join(getattr(module, "PROBLEMS", [])) or "see the sandbox's generate_state"
    checks = ", ".join(getattr(module, "GOAL_CHECKS", {})) or "none (diagnosis only; rely on evidence)"
    return f"one or more of: {problems}", f"one of: {checks}"


def skeleton(kind: str, sid: str, title: str, category: str = None, steps: int = 5, sandbox: str = None) -> dict:
    head = {"id": sid, "type": kind}
    if kind != "career_path":
        head["category"] = category
    head.update({"title": title, "difficulty": "intermediate", "tags": [category or "TODO"],
                 "intro": _todo("one paragraph that sets the scene: who you are and what's going on")})

    if kind == "tutorial":
        head["steps"] = [{
            "prompt": _todo(f"step {n}: what to do, naming every id or value the answer needs"),
            "expected_commands": [_todo("the command, then accepted variants (short flags, aliases)")],
            "fake_output": _todo("realistic output"),
            "hint": _todo("a nudge, not the answer"),
            "explanation": _todo("what the command did"),
            "why": _todo("why this way beats the alternatives"),
        } for n in range(1, steps + 1)]
    elif kind == "incident":
        head["steps"] = [{
            "prompt": _todo(f"step {n}: what the on-call engineer checks next"),
            "expected_commands": [_todo("the command, then accepted variants")],
            "fake_output": _todo("output containing the next clue"),
            "hint": _todo("a nudge, not the answer"),
            "explanation": _todo("what the output shows"),
        } for n in range(1, steps + 1)]
        head["resolution"] = _todo("the root cause, the fix, and how to prevent it")
        head["real_commands_used"] = [_todo("each distinct command used above")]
    elif kind == "yaml_lab":
        validate = {"fields": {_todo("dotted.path"): _todo("expected value")}}
        if category == "kubernetes":
            validate["kind"] = _todo("Deployment, Service, ...")
        head["steps"] = [{
            "file": _todo("file name, e.g. deployment.yaml"),
            "format": "yaml",
            "starter_content": "",
            "prompt": _todo(f"step {n}: what to write or fix"),
            "apply_commands": [_todo("the command that applies the file")],
            "validate": validate,
            "hint": _todo("a nudge"),
            "solution": _todo("a complete file that passes validate"),
            "fake_output": _todo("what applying it prints"),
            "explanation": _todo("what the file does"),
            "why": _todo("why it's written this way"),
        } for n in range(1, steps + 1)]
    elif kind == "career_path":
        head["tags"] = [_todo("categories the path spans")]
        head["steps"] = [_todo("an existing tutorial or incident id") for _ in range(steps)]
        head["resolution"] = _todo("what the path as a whole taught")
    elif kind == "mystery":
        problems, checks = _sandbox_hints(sandbox)
        head.update({
            "sandbox": sandbox,
            "setup": {"seed": 1, "problems": [_todo(problems)]},
            "symptom": _todo("only what a user or alert would report; no evidence strings"),
            "goals": [{"check": _todo(checks), "description": _todo("what 'fixed' means")}],
            "evidence": [{"description": _todo("what the player must have seen"),
                          "seen_any": [_todo("text that appears in command output")]}],
            "question": {"prompt": "What was the root cause?",
                         "options": [_todo(f"option {c}") for c in "abcd"], "answer": 0},
            "expert_commands": steps,
            "solution_commands": [_todo("the efficient path, one command each")],
            "debrief": _todo("what happened, how the evidence showed it, and the lesson"),
        })
        del head["intro"]
    return head


def write(kind: str, title: str, category: str = None, steps: int = 5, sandbox: str = None,
          root: Path = SCENARIOS_DIR) -> Path:
    folder = folder_for(kind, category, root)
    folder.mkdir(parents=True, exist_ok=True)
    sid = next_id(folder, id_prefix(kind, category, sandbox))
    path = folder / f"{sid}-{slugify(title)}.json"
    data = skeleton(kind, sid, title, category, steps, sandbox)
    path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return path


def next_steps(kind: str, path: Path, category: str = None, new_category: bool = False) -> list:
    lines = [f"Created {path}", f"Replace every {TODO} marker; the test suite fails while any remain."]
    if category and (COMMANDS_DIR / f"{category}.md").exists():
        lines.append(f"Take commands from commands/{category}.md so the syntax matches the real tool.")
    if kind == "tutorial":
        lines.append("Every step needs 'why'. Name in the prompt any id the answer uses (exam answerability).")
    if kind == "mystery":
        lines.append("Evidence must come from command output and must not appear in the symptom.")
    if new_category:
        lines.append("New category: add its rows to GAPS.md (table and a Part before the Backlog), README.md, "
                     "CLAUDE.md's depth list, and game.CATEGORY_LABELS (see CLAUDE.md, Testing).")
    lines.append("Then run: python -m pytest   and   python tools/sync_docs.py")
    return lines


def _choose(label: str, options: list, default=None) -> str:
    print(f"\n{label}:")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    while True:
        raw = read_input(f"Choose{f' (Enter for {default})' if default else ''}: ").strip()
        if not raw and default:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print("Pick a number from the list.")


def main(argv=None, root: Path = SCENARIOS_DIR) -> Path:
    parser = argparse.ArgumentParser(prog="python game.py add-scenario",
                                     description="Scaffold a new scenario file.")
    parser.add_argument("--type", choices=TYPES)
    parser.add_argument("--category", help="an existing category folder under scenarios/")
    parser.add_argument("--new-category", action="store_true", help="allow creating a new category folder")
    parser.add_argument("--sandbox", help="for mysteries: linux, docker, kube, aws, azure, gcp, db, git")
    parser.add_argument("--title")
    parser.add_argument("--steps", type=int, default=None)
    args = parser.parse_args(argv)

    kind = args.type or _choose("What are you adding", TYPES)
    categories = list_categories() if root == SCENARIOS_DIR else sorted(
        p.name for p in root.iterdir() if p.is_dir() and ((p / "tutorials").exists() or (p / "incidents").exists()))
    category = args.category
    if kind != "career_path" and not category:
        category = _choose("Category", categories)
    if category and category not in categories and not args.new_category:
        parser.error(f"unknown category '{category}' (existing: {', '.join(categories)}); "
                     "pass --new-category to create it")
    sandbox = args.sandbox
    if kind == "mystery" and not sandbox:
        import mystery
        sandbox = _choose("Sandbox", sorted(mystery.SANDBOXES))
    title = args.title or read_input("\nTitle: ").strip() or "Untitled"
    steps = args.steps
    if steps is None:
        raw = read_input("How many steps? (Enter for 5): ").strip()
        steps = int(raw) if raw.isdigit() and int(raw) > 0 else 5

    path = write(kind, title, category, steps, sandbox, root)
    for line in next_steps(kind, path, category, new_category=category not in categories):
        print(line)
    return path
