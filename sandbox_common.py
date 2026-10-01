"""
Shared machinery for every sandbox (Kubernetes, Docker, Linux): table
rendering, shell-style pipes, save/keep/discard persistence, and the
interactive loop. Each sandbox module only supplies generate_state() and
handle_command(state, raw).
"""

import json
import re
from datetime import datetime
from pathlib import Path

from engine import normalize, read_input

BASE_DIR = Path(__file__).parent
SANDBOX_ROOT = BASE_DIR / "sandbox_data"
SANDBOX_TITLES = {"aws": "AWS", "gcp": "Google Cloud", "kube": "Kubernetes (fixable)"}  # kinds whose .title() would read wrong


def render_table(headers: list, rows: list, prefix: str = "") -> str:
    """Renders a table with column widths sized to fit the widest cell in
    each column (plus the header), so long names never collide with the
    next column — unlike a fixed-width format string."""
    col_count = len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i in range(col_count):
            cell = str(row[i])
            if i == 0:
                cell = prefix + cell
            widths[i] = max(widths[i], len(cell))
    widths = [w + 2 for w in widths]

    def render_row(cells, is_first_col_prefixed=False):
        parts = []
        for i, cell in enumerate(cells):
            text = (prefix + str(cell)) if (i == 0 and is_first_col_prefixed) else str(cell)
            parts.append(text.ljust(widths[i]))
        return "".join(parts).rstrip()

    lines = [render_row(headers)]
    for row in rows:
        lines.append(render_row(row, is_first_col_prefixed=True))
    return "\n".join(lines)


# ------------------------------------------------------------------ pipes

def split_pipes(raw: str) -> list:
    """Split on | outside quotes: 'ps aux | grep "a|b"' -> 2 segments."""
    segments, current, quote = [], [], None
    for c in raw:
        if quote:
            if c == quote:
                quote = None
            current.append(c)
        elif c in ("'", '"'):
            quote = c
            current.append(c)
        elif c == "|":
            segments.append("".join(current).strip())
            current = []
        else:
            current.append(c)
    segments.append("".join(current).strip())
    return segments


def _count_arg(tokens: list, default: int = 10) -> int:
    for i, tok in enumerate(tokens[1:], start=1):
        if tok == "-n" and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            return int(tokens[i + 1])
        if re.fullmatch(r"-\d+", tok):
            return int(tok[1:])
        if re.fullmatch(r"-n\d+", tok):
            return int(tok[2:])
    return default


def apply_pipe(output: str, segment: str) -> str:
    """Supports the filters people actually chain onto commands:
    grep [-i] [-v] [-c] PATTERN, head/tail [-n N | -N], wc -l, sort [-r]."""
    tokens = segment.split()
    if not tokens:
        return output
    lines = output.splitlines()
    cmd = tokens[0]

    if cmd == "grep":
        # Context flags (-A/-B/-C N, or -A4) take a number argument.
        after = before = 0
        rest = []
        args = tokens[1:]
        i = 0
        while i < len(args):
            m = re.fullmatch(r"-([ABC])(\d*)", args[i])
            if m:
                n = m.group(2)
                if not n and i + 1 < len(args) and args[i + 1].isdigit():
                    n = args[i + 1]
                    i += 1
                n = int(n or 0)
                if m.group(1) in "AC":
                    after = n
                if m.group(1) in "BC":
                    before = n
            else:
                rest.append(args[i])
            i += 1
        flags = {t for t in rest if t.startswith("-")}
        pattern_tokens = [t for t in rest if not t.startswith("-")]
        if not pattern_tokens:
            return "usage: grep [-i] [-v] [-c] [-A N] [-B N] PATTERN"
        pattern = " ".join(pattern_tokens).strip("'\"")
        ignore_case = any("i" in f for f in flags)
        invert = any("v" in f for f in flags)
        needle = pattern.lower() if ignore_case else pattern
        hits = [i for i, l in enumerate(lines) if (needle in (l.lower() if ignore_case else l)) != invert]
        if any("c" in f for f in flags):
            return str(len(hits))
        keep = sorted({j for i in hits for j in range(max(0, i - before), min(len(lines), i + after + 1))})
        return "\n".join(lines[j] for j in keep)
    if cmd == "head":
        return "\n".join(lines[:_count_arg(tokens)])
    if cmd == "tail":
        return "\n".join(lines[-_count_arg(tokens):])
    if cmd == "wc" and "-l" in tokens:
        return str(len(lines))
    if cmd == "sort":
        return "\n".join(sorted(lines, reverse="-r" in tokens))
    return f"(pipe to '{cmd}' isn't supported in the sandbox — try grep, head, tail, wc -l, or sort)"


def parse_flags(tokens: list, aliases: dict | None = None, booleans: set | None = None):
    """Split normalized tokens into (flags, positional).

    Handles --key=value, --key value, short aliases (-g rg -> resource-group),
    bare boolean flags, and quoted values containing spaces
    (--command='curl -s x' arrives as several tokens). normalize() glues a
    boolean flag to a following positional (--tunnel-through-iap=web-1);
    names listed in `booleans` have that value handed back as a positional."""
    aliases, booleans = aliases or {}, booleans or set()
    flags, positional = {}, []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        key = value = None
        if tok.startswith("--"):
            key, _, value = tok[2:].partition("=")
            if "=" not in tok:
                value = None
        elif tok in aliases:
            key = aliases[tok]
        else:
            positional.append(tok.strip("'\""))
            i += 1
            continue

        if key in booleans:
            flags[key] = True
            if value:
                positional.append(value.strip("'\""))
            i += 1
            continue
        if value is None:
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                value = tokens[i + 1]
                i += 1
            else:
                flags[key] = True
                i += 1
                continue
        if value[:1] in ("'", '"') and not (len(value) > 1 and value.endswith(value[0])):
            quote = value[0]
            while i + 1 < len(tokens):
                i += 1
                value += " " + tokens[i]
                if tokens[i].endswith(quote):
                    break
        flags[key] = value.strip("'\"")
        i += 1
    return flags, positional


def run_command(handle_command, state: dict, raw: str):
    """Run the first segment through the sandbox, then apply any pipes.
    Returns None when the player wants to exit."""
    segments = split_pipes(raw)
    output = handle_command(state, segments[0])
    if output is None:
        return None
    for segment in segments[1:]:
        output = apply_pipe(output, segment)
    return output


# ------------------------------------------------------------ persistence

class SandboxStore:
    """Per-kind storage. Kubernetes keeps the original sandbox_data/ root
    so sessions saved before multi-sandbox support still load."""

    def __init__(self, kind: str):
        self.kind = kind
        self.root = SANDBOX_ROOT if kind == "kubernetes" else SANDBOX_ROOT / kind
        self.saved_dir = self.root / "saved"
        self.current_file = self.root / "current_session.json"

    def list_saved(self) -> list:
        if not self.saved_dir.exists():
            return []
        return sorted(self.saved_dir.glob("*.json"))

    def save_current(self, state: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def choose_or_generate(self, generate_state, noun: str) -> dict:
        saved = self.list_saved()
        if saved:
            print(f"\nYou have saved {noun} states:")
            for i, path in enumerate(saved, start=1):
                print(f"  {i}. {path.stem}")
            print(f"  {len(saved) + 1}. Generate a new random {noun}")
            choice = read_input("\nChoose an option: ")
            if choice.isdigit() and 1 <= int(choice) <= len(saved):
                return json.loads(saved[int(choice) - 1].read_text(encoding="utf-8"))
        return generate_state()

    def prompt_keep(self, state: dict, noun: str) -> None:
        choice = read_input(f"\nKeep this {noun} state for future reference? (y/N): ").lower()
        if choice == "y":
            self.saved_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            (self.saved_dir / f"session-{ts}.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
            print(f"Saved. You can pick this {noun} again next time you enter its sandbox.")
        else:
            if self.current_file.exists():
                self.current_file.unlink()
            print(f"Discarded — this {noun} state is gone.")


def run_loop(kind: str, noun: str, generate_state, handle_command, describe_state) -> None:
    """The interactive loop every sandbox shares. describe_state(state)
    returns the intro lines shown once the state is loaded."""
    store = SandboxStore(kind)
    print(f"\n=== {SANDBOX_TITLES.get(kind, kind.title())} Sandbox ===")
    state = store.choose_or_generate(generate_state, noun)
    store.save_current(state)

    for line in describe_state(state):
        print(line)
    print("Type 'help' for supported commands (pipes like '| grep x' work), 'exit' to leave.")

    while True:
        raw = read_input("\n$ ")
        if not raw:
            continue
        # A sandbox with a nested shell (AWS's ssm start-session) sets
        # state["session"]; 'exit' then ends that session, not the sandbox.
        if normalize(raw) in {"exit", "quit", ":q"} and not state.get("session"):
            break
        output = run_command(handle_command, state, raw)
        if output is None:
            break
        print(f"\n{output}")

    store.prompt_keep(state, noun)
