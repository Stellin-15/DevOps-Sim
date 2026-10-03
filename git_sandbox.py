"""
Git sandbox — a real repository and the real git binary. Each state is a
throwaway clone-like repo of a small service (shop-api) under
workspace/git-sandbox/, built in one `git fast-import` with fixed
timestamps so commit hashes are the same every time. One of five problems
is seeded:
  wrong_branch    two commits made on main that belonged on feature/search
  leaked_secret   a key committed in one of three unpushed commits
  merge_conflict  a merge of feature/pricing stopped on a conflict
  lost_commits    'git reset --hard HEAD~2' threw away unpushed work
  bad_commit      a pushed commit broke a setting; undo it without rewriting

The player runs real git commands. Anything that would reach the network,
run arbitrary programs (bisect run, rebase --exec, filter-branch, aliases,
hooks or editors set through config), or leave the repository is refused.
Files are edited in the player's own editor (the repo path is shown) or
with a small built-in `sed -i`.

This is the one sandbox that runs an external tool. It needs git installed,
and its tests are skipped without it.
"""

import json
import os
import random
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sandbox_common import BASE_DIR, SandboxStore, run_loop

WORK_ROOT = BASE_DIR / "workspace" / "git-sandbox"
EDITOR_SCRIPT = BASE_DIR / "tools" / "git_editor.py"
STALE_SECONDS = 6 * 3600
GIT_TIMEOUT = 30

PROBLEMS = ["wrong_branch", "leaked_secret", "merge_conflict", "lost_commits", "bad_commit"]

REPORTS = {
    "wrong_branch": "You made two search commits on main that belonged on feature/search. Nothing is pushed yet.",
    "leaked_secret": "A payment API key went into one of your three unpushed commits. Get it out of the history "
                     "before you push, and keep the other two commits.",
    "merge_conflict": "Merging feature/pricing into main stopped with a conflict. Finish the merge, keeping both features.",
    "lost_commits": "Someone ran 'git reset --hard' on main, and two commits of unpushed retry work vanished.",
    "bad_commit": "Since v1.5, every outbound request times out at once; v1.4 was fine. Find the commit and undo "
                  "it without rewriting history that's already pushed.",
}

SECRET_NEEDLE = "pk-test-0000-not-a-real-key"
TEAM = [("Dana Park", "dana@shop.example"), ("Omar Haddad", "omar@shop.example"),
        ("Priya Mehta", "priya@shop.example")]
PLAYER = ("You", "you@shop.example")
START = int(datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc).timestamp())

HELP_TEXT = """This is a real git repository; type real git commands.
  git status | log [--oneline --graph --all] | diff | show | branch | switch | checkout
  git add | commit -m "..." | reset | revert | cherry-pick | rebase [--onto] | merge | stash
  git reflog | bisect start|good|bad|reset | blame | grep | tag | restore | log -S <text>
Files:
  ls [dir]   cat <file>   pwd   edit <file> (prints the path to open in your own editor)
  sed -i '/pattern/d' <file>   sed -i 's/old/new/[g]' <file>
  check      whether the reported problem is fixed (sandbox only)
Not available: anything that talks to a remote (push, pull, fetch, clone), 'bisect run',
'rebase --exec', filter-branch, and config that runs programs.
  help | exit          (pipes work: git log --oneline | grep search)"""


# ------------------------------------------------------------------ running git

def _env(repo_root: Path, author=PLAYER, when=None) -> dict:
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_"):
            del env[k]
    empty = repo_root / ".gitconfig-empty"
    if not empty.exists():
        empty.write_text("", encoding="utf-8")
    editor = f'"{Path(sys.executable).as_posix()}" "{EDITOR_SCRIPT.as_posix()}"'
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(empty),
        "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat", "PAGER": "cat",
        "GIT_EDITOR": editor, "GIT_SEQUENCE_EDITOR": editor,
        "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1],
        "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1],
        "LC_ALL": "C",
    })
    if when is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{when} +0000"
    return env


BASE_FLAGS = ["-c", "color.ui=never", "-c", "core.quotepath=off", "-c", "core.autocrlf=false",
              "-c", "advice.detachedHead=false"]


def _git(repo: Path, *args, input_bytes=None, author=PLAYER, when=None) -> subprocess.CompletedProcess:
    """Internal git call: no restrictions, output captured."""
    return subprocess.run(["git", *BASE_FLAGS, *args], cwd=repo, env=_env(repo.parent.parent, author, when),
                          input=input_bytes, capture_output=True, timeout=GIT_TIMEOUT,
                          stdin=None if input_bytes is not None else subprocess.DEVNULL)


def _out(repo: Path, *args) -> str:
    return _git(repo, *args).stdout.decode("utf-8", "replace").strip()


def _ok(repo: Path, *args) -> bool:
    return _git(repo, *args).returncode == 0


# ------------------------------------------------------------- file contents

def _server(health=False, logging=False, shutdown=False) -> str:
    lines = []
    if logging:
        lines.append("import logging")
    if shutdown:
        lines.append("import signal")
    lines.append("from http.server import BaseHTTPRequestHandler, HTTPServer")
    lines += ["", ""]
    if logging:
        lines += ['log = logging.getLogger("shop-api")', "", ""]
    lines += ["class Handler(BaseHTTPRequestHandler):", "    def do_GET(self):"]
    if logging:
        lines.append('        log.info("GET %s", self.path)')
    if health:
        lines += ['        if self.path == "/healthz":', "            self.send_response(200)",
                  "            self.end_headers()", "            return"]
    lines += ["        self.send_response(404)", "        self.end_headers()", "", "", "def main():",
              '    server = HTTPServer(("", 8080), Handler)']
    if shutdown:
        lines.append("    signal.signal(signal.SIGTERM, lambda *_: server.shutdown())")
    lines += ["    server.serve_forever()", "", "", 'if __name__ == "__main__":', "    main()"]
    return "\n".join(lines) + "\n"


PRICING_1 = '''def subtotal(items):
    return sum(i["price_cents"] * i["qty"] for i in items)
'''
PRICING_2 = PRICING_1 + '''

FREE_SHIPPING_CENTS = 5000
SHIPPING_CENTS = 495


def shipping(subtotal_cents):
    return 0 if subtotal_cents >= FREE_SHIPPING_CENTS else SHIPPING_CENTS
'''
PRICING_ROUND = PRICING_2 + '''

def to_cents(amount):
    return int(round(amount * 100))
'''
PRICING_DISCOUNT = PRICING_2 + '''

def apply_discount(subtotal_cents, percent):
    return subtotal_cents - subtotal_cents * percent // 100
'''
PRICING_TAX = PRICING_2 + '''

def apply_tax(subtotal_cents, rate_percent):
    return subtotal_cents + subtotal_cents * rate_percent // 100
'''

SETTINGS_1 = '''import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/shop")
TIMEOUT_SECONDS = 30
RETRIES = 3
'''
SETTINGS_2 = SETTINGS_1.replace('os.environ.get("DATABASE_URL", "postgresql://localhost/shop")',
                                'os.environ["DATABASE_URL"]')


def _settings_tidy(timeout: int) -> str:
    return f'''import os

# Database
DATABASE_URL = os.environ["DATABASE_URL"]

# Outbound HTTP
TIMEOUT_SECONDS = {timeout}
RETRIES = 3
'''


TESTS_1 = '''from app.pricing import subtotal


def test_subtotal():
    assert subtotal([{"price_cents": 250, "qty": 2}]) == 500
'''
TESTS_2 = TESTS_1.replace("from app.pricing import subtotal", "from app.pricing import shipping, subtotal") + '''

def test_free_shipping_over_threshold():
    assert shipping(5000) == 0
'''
TESTS_3 = TESTS_2.replace("import shipping, subtotal", "import shipping, subtotal, to_cents") + '''

def test_to_cents_rounds():
    assert to_cents(19.999) == 2000
'''
README_1 = "# shop-api\n\nThe shop's HTTP API.\n"
README_2 = README_1 + "\n## Local setup\n\n    pip install -r requirements.txt\n    python -m app.server\n"
CHANGELOG = "# Changelog\n\n## 1.5\n- Free shipping threshold\n- Graceful shutdown\n"
SEARCH_1 = 'def parse_query(text):\n    return [w for w in text.lower().split() if w]\n'
SEARCH_2 = SEARCH_1 + '\n\ndef build_index(products):\n    return {p["id"]: parse_query(p["name"]) for p in products}\n'
RETRY = '''import time


def with_retries(fn, attempts=3, delay=0.5):
    for attempt in range(attempts):
        try:
            return fn()
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay * 2 ** attempt)
'''
RETRY_TESTS = '''from app.retry import with_retries


def test_returns_first_success():
    assert with_retries(lambda: 7) == 7
'''


# ------------------------------------------------------------ history builder

class _History:
    """Builds a git fast-import stream. Commits on a ref continue from that
    ref's last commit unless `parent` (a mark) is given."""

    def __init__(self):
        self.parts, self.mark, self.time = [], 0, START

    @staticmethod
    def _data(text: str) -> bytes:
        raw = text.encode("utf-8")
        return b"data %d\n" % len(raw) + raw + b"\n"

    def commit(self, ref, subject, files, parent=None, author=0) -> int:
        self.mark += 1
        self.time += 3 * 3600 + (self.mark * 977) % 3600
        name, email = TEAM[author % len(TEAM)]
        out = [f"commit {ref}\nmark :{self.mark}\n".encode(),
               f"author {name} <{email}> {self.time} +0000\n".encode(),
               f"committer {name} <{email}> {self.time} +0000\n".encode(),
               self._data(subject + "\n")]
        if parent:
            out.append(f"from :{parent}\n".encode())
        for path, content in files.items():
            if content is None:
                out.append(f"D {path}\n".encode())
            else:
                out.append(f"M 100644 inline {path}\n".encode())
                out.append(self._data(content))
        self.parts.append(b"".join(out) + b"\n")
        return self.mark

    def ref(self, ref, mark):
        self.parts.append(f"reset {ref}\nfrom :{mark}\n\n".encode())

    def stream(self) -> bytes:
        return b"".join(self.parts) + b"done\n"


def _base(h: _History, bad_timeout=False) -> int:
    main = "refs/heads/main"
    h.commit(main, "initial skeleton", {"README.md": README_1, "app/__init__.py": "", "app/server.py": _server(),
                                        "app/pricing.py": PRICING_1, "config/settings.py": SETTINGS_1})
    h.commit(main, "server: health endpoint", {"app/server.py": _server(health=True)}, author=1)
    h.commit(main, "tests: pricing subtotal", {"tests/test_pricing.py": TESTS_1}, author=2)
    h.commit(main, "config: read database url from env", {"config/settings.py": SETTINGS_2})
    v14 = h.commit(main, "server: request logging", {"app/server.py": _server(health=True, logging=True)}, author=1)
    h.ref("refs/tags/v1.4", v14)
    h.commit(main, "docs: local setup", {"README.md": README_2}, author=2)
    h.commit(main, "pricing: free shipping threshold", {"app/pricing.py": PRICING_2})
    h.commit(main, "tests: shipping threshold", {"tests/test_pricing.py": TESTS_2}, author=2)
    h.commit(main, "config: tidy formatting", {"config/settings.py": _settings_tidy(0 if bad_timeout else 30)}, author=1)
    h.commit(main, "server: graceful shutdown",
             {"app/server.py": _server(health=True, logging=True, shutdown=True)})
    tip = h.commit(main, "docs: changelog for 1.5", {"CHANGELOG.md": CHANGELOG}, author=2)
    h.ref("refs/tags/v1.5", tip)
    return tip


# ----------------------------------------------------------------- generation

def _rmtree(path: Path) -> None:
    def make_writable(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=make_writable)


def _prune(root: Path) -> None:
    """Remove repositories left by earlier sessions and mysteries, except
    those a saved sandbox state still points at."""
    if not root.exists():
        return
    keep = set()
    for saved in SandboxStore("git").list_saved():
        try:
            keep.add(Path(json.loads(saved.read_text(encoding="utf-8"))["repo"]).parent.name)
        except (ValueError, KeyError):
            pass
    now = time.time()
    for d in root.iterdir():
        if d.is_dir() and not d.name.startswith(".") and d.name not in keep and now - d.stat().st_mtime > STALE_SECONDS:
            try:
                _rmtree(d)
            except OSError:
                pass


def generate_state(seed=None, problems=None) -> dict:
    """One random problem by default; mystery incidents pass an explicit list.
    The content is fixed per problem set, so each set is built once into
    root/.templates and copied: a git process costs ~0.2s on Windows."""
    rng = random.Random(seed)
    problems = list(problems) if problems is not None else [rng.choice(PROBLEMS)]
    root = Path(WORK_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    _prune(root)
    template = root / ".templates" / "-".join(sorted(problems))
    marker = template / "expected.json"
    if not marker.exists():
        if template.exists():
            _rmtree(template)
        expected = _build(template / "shop-api", problems)
        marker.write_text(json.dumps(expected), encoding="utf-8")
    repo = root / uuid.uuid4().hex[:12] / "shop-api"
    shutil.copytree(template / "shop-api", repo)
    return {"seed": seed, "problems": problems, "repo": str(repo),
            "expected": json.loads(marker.read_text(encoding="utf-8"))}


def _build(repo: Path, problems: list) -> dict:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")

    h = _History()
    tip = _base(h, bad_timeout="bad_commit" in problems)
    pushed = tip
    if "wrong_branch" in problems:
        h.ref("refs/heads/feature/search", tip)
        h.commit("refs/heads/main", "search: add query parser", {"app/search.py": SEARCH_1})
        h.commit("refs/heads/main", "search: add index builder", {"app/search.py": SEARCH_2})
    if "leaked_secret" in problems:
        h.commit("refs/heads/main", "pricing: round totals to cents", {"app/pricing.py": PRICING_ROUND})
        h.commit("refs/heads/main", "config: payment key for local testing", {
            "config/settings.py": _settings_tidy(30) + f'\n# TODO: move to the environment before pushing\n'
                                                       f'PAYMENT_API_KEY = "{SECRET_NEEDLE}"\n'})
        h.commit("refs/heads/main", "tests: cover rounding", {"tests/test_pricing.py": TESTS_3})
    if "merge_conflict" in problems:
        h.commit("refs/heads/feature/pricing", "pricing: add tax", {"app/pricing.py": PRICING_TAX},
                 parent=tip, author=2)
        pushed = h.commit("refs/heads/main", "pricing: add discounts", {"app/pricing.py": PRICING_DISCOUNT}, author=1)
    h.ref("refs/remotes/origin/main", pushed)

    _git(repo, "fast-import", "--quiet", input_bytes=h.stream())
    with open(repo / ".git" / "config", "a", encoding="utf-8") as f:
        f.write('[remote "origin"]\n\turl = https://git.shop.example/shop-api.git\n'
                '\tfetch = +refs/heads/*:refs/remotes/origin/*\n'
                '[branch "main"]\n\tremote = origin\n\tmerge = refs/heads/main\n')
    _git(repo, "reset", "-q", "--hard", "main")

    expected = {}
    if "merge_conflict" in problems:
        _git(repo, "merge", "feature/pricing", when=h.time + 600)
    if "lost_commits" in problems:
        for i, (path, content, subject) in enumerate([("app/retry.py", RETRY, "add retry logic"),
                                                      ("tests/test_retry.py", RETRY_TESTS, "add retry tests")]):
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_bytes(content.encode("utf-8"))
            _git(repo, "add", path)
            _git(repo, "commit", "-q", "-m", subject, author=TEAM[0], when=h.time + 1800 * (i + 1))
        expected["lost_tip"] = _out(repo, "rev-parse", "HEAD")
        _git(repo, "reset", "-q", "--hard", "HEAD~2")
    if "leaked_secret" in problems:
        expected["leak_commit"] = _out(repo, "log", "main", "--format=%H", "-S", SECRET_NEEDLE)
    if "bad_commit" in problems:
        expected["bad_commit"] = _out(repo, "log", "main", "--format=%H", "-S", "TIMEOUT_SECONDS = 0")
    expected["branches"] = _out(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
    return expected


# ------------------------------------------------------------------- commands

BLOCKED_SUBCOMMANDS = {
    "clone", "fetch", "pull", "push", "ls-remote", "submodule", "daemon", "instaweb", "send-email",
    "request-pull", "credential", "credential-store", "credential-cache", "upload-pack", "receive-pack",
    "upload-archive", "difftool", "mergetool", "gui", "citool", "web--browse", "p4", "svn", "archimport",
    "cvsimport", "cvsserver", "cvsexportcommit", "quiltimport", "filter-branch", "worktree", "help",
    "fsmonitor--daemon", "maintenance", "scalar", "bugreport", "remote-ext", "remote-fd",
}
BLOCKED_CONFIG = ("alias.", "hookspath", "editor", "pager", "sshcommand", "fsmonitor", "textconv", "filter.",
                  "credential", "gpg", "program", "askpass", "include", "core.worktree", "url.", "http.",
                  "proxy", "protocol.", "--global", "--system", "--file", "-f", "--blob")
INTERACTIVE_FLAGS = {"-p", "--patch", "-i", "--interactive", "--edit-todo", "-e", "--edit"}
NO_TERMINAL_NOTE = "(no terminal, so git's editor was skipped and the file was used as git wrote it)\n"


def _refusal(args: list):
    if not args:
        return None
    if args[0].startswith("-") and args[0] not in ("--version", "--no-pager", "-p", "--paginate"):
        return "Global options such as -C, -c, and --git-dir aren't available: the sandbox stays in this repository."
    if "--help" in args:
        return "git's manual opens outside the terminal; read it at https://git-scm.com/docs, or try -h."
    sub = next((a for a in args if not a.startswith("-")), "")
    rest = args[args.index(sub) + 1:] if sub else []
    if sub in BLOCKED_SUBCOMMANDS:
        return (f"'git {sub}' isn't available in the sandbox: it talks to a remote or runs outside the repository. "
                "Everything here is local; origin/main shows what's already been pushed.")
    if sub == "bisect" and rest[:1] == ["run"]:
        return "'git bisect run' executes a program; mark commits yourself with 'git bisect good' or 'git bisect bad'."
    if sub == "rebase" and any(a in ("-x", "--exec") or a.startswith("--exec=") for a in rest):
        return "'rebase --exec' runs shell commands, which the sandbox doesn't allow."
    if sub == "config" and any(b in a.lower() for a in rest for b in BLOCKED_CONFIG):
        return "That configuration could run programs or reach the network, so the sandbox doesn't allow it."
    if any(a in ("-o", "--output", "--output-directory") or a.startswith(("--output=", "--output-directory="))
           for a in rest):
        return "Writing output files isn't available in the sandbox; the output is shown here instead."
    return None


def _needs_terminal(args: list) -> bool:
    sub = next((a for a in args if not a.startswith("-")), "")
    rest = set(args[1:])
    if rest & INTERACTIVE_FLAGS or "--continue" in rest:
        return True
    if sub == "commit":
        return not any(a.startswith(("-m", "--message", "-F", "--file", "-C", "--reuse-message", "--no-edit",
                                     "--fixup")) for a in args[1:])
    if sub == "revert":
        return "--no-edit" not in rest
    if sub == "tag":
        return bool(rest & {"-a", "-s", "--annotate"}) and not any(a.startswith(("-m", "-F")) for a in args[1:])
    return False


def _player_git(state: dict, args: list) -> str:
    refusal = _refusal(args)
    if refusal:
        return refusal
    repo = Path(state["repo"])
    cmd = ["git", *BASE_FLAGS, *args]
    env = _env(repo.parent.parent)
    if _needs_terminal(args) and sys.stdin.isatty():
        code = subprocess.run(cmd, cwd=repo, env=env).returncode
        return f"(git ran interactively; exit code {code})"
    try:
        proc = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, stdin=subprocess.DEVNULL,
                              timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "git took too long and was stopped."
    text = (proc.stdout + proc.stderr).decode("utf-8", "replace").rstrip()
    # progress lines redraw themselves with \r; keep what a terminal would show
    text = "\n".join(line.rstrip("\r").split("\r")[-1] for line in text.split("\n"))
    if _needs_terminal(args):
        text = NO_TERMINAL_NOTE + text
    return text


def _resolve(state: dict, name: str):
    repo = Path(state["repo"]).resolve()
    path = (repo / name).resolve()
    if path != repo and repo not in path.parents:
        return None
    return path


def _ls(state, args) -> str:
    show_all = any(a.startswith("-") and "a" in a for a in args)
    names = [a for a in args if not a.startswith("-")]
    path = _resolve(state, names[0] if names else ".")
    if path is None or not path.exists():
        return f"ls: cannot access '{names[0] if names else '.'}': No such file or directory"
    if path.is_file():
        return path.name
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir()
                     if show_all or not p.name.startswith("."))
    return "  ".join(entries)


def _cat(state, args) -> str:
    out = []
    for name in args:
        path = _resolve(state, name)
        if path is None or not path.is_file():
            out.append(f"cat: {name}: No such file or directory")
        else:
            out.append(path.read_bytes().decode("utf-8", "replace").rstrip("\n"))
    return "\n".join(out) if args else "cat: missing file operand"


def _bre_to_python(pattern: str) -> str:
    """GNU sed basic regex -> Python: \\| \\( \\) \\+ \\? are operators, the
    bare characters are literals."""
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            nxt = pattern[i + 1]
            out.append(nxt if nxt in "|()+?{}" else c + nxt)
            i += 2
            continue
        out.append("\\" + c if c in "|()+?{}" else c)
        i += 1
    return "".join(out)


def _split_unescaped(text: str, sep: str = "/") -> list:
    parts, current, i = [], [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            if text[i + 1] == sep:
                current.append(sep)
            else:
                current.append(text[i:i + 2])
            i += 2
            continue
        if text[i] == sep:
            parts.append("".join(current))
            current = []
        else:
            current.append(text[i])
        i += 1
    parts.append("".join(current))
    return parts


def _sed(state, args) -> str:
    in_place = "-i" in args
    extended = "-E" in args or "-r" in args
    rest = [a for a in args if a not in ("-i", "-E", "-r")]
    if len(rest) != 2:
        return "sed: the sandbox supports: sed [-i] [-E] '/pattern/d' <file>  or  sed [-i] 's/old/new/[g]' <file>"
    script, name = rest
    path = _resolve(state, name)
    if path is None or not path.is_file():
        return f"sed: can't read {name}: No such file or directory"
    if ".git" in path.relative_to(Path(state["repo"]).resolve()).parts:
        return "sed: editing git's own files isn't allowed in the sandbox"
    convert = (lambda p: p) if extended else _bre_to_python
    try:
        if script.startswith("/") and script.endswith("/d"):
            regex = re.compile(convert(script[1:-2]))
            action = lambda line: None if regex.search(line) else line
        elif script.startswith("s/"):
            parts = _split_unescaped(script[2:])
            if len(parts) != 3:
                return f"sed: unterminated `s' command: {script}"
            regex = re.compile(convert(parts[0]))
            repl = parts[1].replace("&", r"\g<0>")
            count = 0 if "g" in parts[2] else 1
            action = lambda line: regex.sub(repl, line, count=count)
        else:
            return "sed: the sandbox supports only '/pattern/d' and 's/old/new/[g]'"
    except re.error as e:
        return f"sed: invalid regex: {e}"
    out_lines = []
    for raw in path.read_bytes().decode("utf-8").splitlines(keepends=True):
        body = raw.rstrip("\r\n")
        ending = raw[len(body):]
        new = action(body)
        if new is not None:
            out_lines.append(new + ending)
    result = "".join(out_lines)
    if not in_place:
        return result.rstrip("\n")
    path.write_bytes(result.encode("utf-8"))
    return ""


def handle_command(state: dict, raw: str) -> str:
    if not (Path(state["repo"]) / ".git").exists():
        state.update(generate_state(state.get("seed"), state.get("problems")))
        return f"The repository was missing (cleaned up since it was saved), so it was rebuilt fresh at {state['repo']}."
    try:
        tokens = shlex.split(raw)
    except ValueError as e:
        return f"parse error: {e}"
    if not tokens:
        return ""
    cmd, args = tokens[0], tokens[1:]
    if cmd in ("help", "?"):
        return HELP_TEXT
    if cmd == "check":
        return _check_report(state)
    if cmd == "git":
        return _player_git(state, args)
    if cmd == "ls":
        return _ls(state, args)
    if cmd == "cat":
        return _cat(state, args)
    if cmd == "pwd":
        return state["repo"]
    if cmd == "sed":
        return _sed(state, args)
    if cmd in ("edit", "code", "vim", "vi", "nano", "notepad"):
        path = _resolve(state, args[0]) if args else None
        if path is None:
            return f"{cmd}: name a file in the repository"
        return f"Open this file in your own editor, save it, then come back:\n  {path}"
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


# ------------------------------------------------------- mystery/sandbox hooks

def _repo(state) -> Path:
    return Path(state["repo"])


def _history_kept(state) -> bool:
    return _ok(_repo(state), "merge-base", "--is-ancestor", "origin/main", "main")


def _clean(state) -> bool:
    return _out(_repo(state), "status", "--porcelain") == ""


def _subjects(state, rev_range) -> list:
    return _out(_repo(state), "log", "--format=%s", rev_range).splitlines()


def _branch_moved(state, goal=None) -> bool:
    repo = _repo(state)
    on_feature = _subjects(state, "origin/main..feature/search")
    return (_out(repo, "rev-parse", "main") == _out(repo, "rev-parse", "origin/main")
            and {"search: add query parser", "search: add index builder"} <= set(on_feature)
            and _ok(repo, "cat-file", "-e", "feature/search:app/search.py"))


def _secret_purged(state, goal=None) -> bool:
    repo = _repo(state)
    return (_out(repo, "log", "main", "--format=%H", "-S", SECRET_NEEDLE) == ""
            and {"pricing: round totals to cents", "tests: cover rounding"} <= set(_subjects(state, "origin/main..main"))
            and _history_kept(state))


def _merge_completed(state, goal=None) -> bool:
    repo = _repo(state)
    if (repo / ".git" / "MERGE_HEAD").exists():
        return False
    parents = _out(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()
    if len(parents) != 3 or parents[2] != _out(repo, "rev-parse", "feature/pricing"):
        return False
    text = _out(repo, "show", "HEAD:app/pricing.py")
    markers = any(line.startswith(("<<<<<<<", "=======", ">>>>>>>")) for line in text.splitlines())
    return "def apply_discount" in text and "def apply_tax" in text and not markers and _clean(state)


def _commits_recovered(state, goal=None) -> bool:
    return {"add retry logic", "add retry tests"} <= set(_subjects(state, "main")) and _clean(state)


def _bad_commit_reverted(state, goal=None) -> bool:
    repo = _repo(state)
    return ("TIMEOUT_SECONDS = 30" in _out(repo, "show", "main:config/settings.py")
            and _ok(repo, "merge-base", "--is-ancestor", state["expected"]["bad_commit"], "main")
            and _history_kept(state) and _clean(state))


FIXES = {
    "wrong_branch": _branch_moved,
    "leaked_secret": _secret_purged,
    "merge_conflict": _merge_completed,
    "lost_commits": _commits_recovered,
    "bad_commit": _bad_commit_reverted,
}

GOAL_CHECKS = {
    "problem_fixed": lambda state, g: FIXES[g["problem"]](state),
    "history_kept": lambda state, g: _history_kept(state),
}


def _check_report(state) -> str:
    return "\n".join(f"[{'fixed' if FIXES[p](state) else 'open '}] {REPORTS[p]}" for p in state["problems"])


def placeholders(state: dict) -> dict:
    return {k: v for k, v in state["expected"].items() if isinstance(v, str)}


def collateral_issues(state: dict) -> set:
    repo = _repo(state)
    if not (repo / ".git").exists():
        return set()
    issues = set()
    if not _history_kept(state):
        issues.add("rewrote history that was already pushed: origin/main is no longer part of main, "
                   "so everyone else's clone now disagrees with yours")
    for tag in ("v1.4", "v1.5"):
        if not _ok(repo, "rev-parse", "--verify", "-q", f"refs/tags/{tag}"):
            issues.add(f"deleted the release tag {tag}")
    for branch in state["expected"].get("branches", []):
        if not _ok(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}"):
            issues.add(f"deleted the branch {branch}")
    return issues


def describe_state(state: dict) -> list:
    return [f"You're in the shop-api repository, a real git repository at:\n  {state['repo']}",
            "Open its files in your own editor whenever you need to. Reported:",
            *[f"  - {REPORTS[p]}" for p in state["problems"]],
            "Use real git. 'check' shows whether it's fixed."]


def run_sandbox() -> None:
    if shutil.which("git") is None:
        print("\nThe Git sandbox runs the real git, which isn't installed (https://git-scm.com/downloads).")
        return
    run_loop("git", "repository", generate_state, handle_command, describe_state)
