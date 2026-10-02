"""
Parsers that turn each lab file format into a plain nested dict, so
yaml_lab.validate_manifest can check any format with the same dotted-path
field specs, [*] wildcards, and {"contains": ...} checks.

Every parser returns (parsed_dict_or_None, problems). Non-YAML formats also
expose "lines" (for `order` checks) and "text" (for `absent`/contains).

No external tools or libraries: the HCL and bash checks are deliberately
lightweight — structural, not full language implementations — so labs
behave identically on every machine.
"""

import ast
import re

import yaml

# ---------------------------------------------------------------- YAML


def parse_yaml(content: str):
    try:
        return yaml.safe_load(content), []
    except yaml.YAMLError as e:
        return None, [f"YAML syntax error: {e}"]


# ---------------------------------------------------------- Dockerfile

DOCKERFILE_INSTRUCTIONS = {
    "FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ADD", "COPY", "ENTRYPOINT",
    "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK",
    "SHELL", "MAINTAINER",
}


def parse_dockerfile(content: str):
    """{'lines': ['FROM node:20 AS build', ...], 'FROM': [args, ...], ...}"""
    logical, buffer = [], ""
    for raw in content.splitlines():
        line = raw.strip()
        if not buffer and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            buffer += line[:-1].strip() + " "
            continue
        logical.append((buffer + line).strip())
        buffer = ""
    if buffer.strip():
        logical.append(buffer.strip())

    parsed = {"lines": [], "text": content}
    problems = []
    for n, line in enumerate(logical, start=1):
        parts = line.split(None, 1)
        instruction = parts[0].upper()
        args = parts[1].strip() if len(parts) > 1 else ""
        if instruction not in DOCKERFILE_INSTRUCTIONS:
            problems.append(f"Unknown Dockerfile instruction '{parts[0]}' (instruction {n})")
            continue
        parsed["lines"].append(f"{instruction} {args}".strip())
        parsed.setdefault(instruction, []).append(args)

    if not parsed["lines"]:
        return None, problems or ["Dockerfile is empty."]
    if parsed["lines"][0].split()[0] not in ("FROM", "ARG"):
        problems.append("A Dockerfile must start with FROM (only ARG may come before it).")
    return (None if problems else parsed), problems


# ----------------------------------------------------------------- HCL


class HCLError(Exception):
    pass


class _HCLParser:
    """Minimal HCL: blocks with labels, attributes, strings (with ${}
    interpolation kept raw), numbers, bools, lists, maps, and raw
    expressions. Enough for typical Terraform configs, not a full spec."""

    def __init__(self, text: str):
        self.s = text
        self.i = 0

    def line(self) -> int:
        return self.s.count("\n", 0, self.i) + 1

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def skip(self, newlines=True):
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in " \t\r" or (newlines and c == "\n"):
                self.i += 1
            elif c == "#" or self.s.startswith("//", self.i):
                while self.i < len(self.s) and self.s[self.i] != "\n":
                    self.i += 1
            elif self.s.startswith("/*", self.i):
                end = self.s.find("*/", self.i + 2)
                if end == -1:
                    raise HCLError(f"unterminated /* comment starting on line {self.line()}")
                self.i = end + 2
            else:
                break

    def read_string(self) -> str:
        start_line = self.line()
        self.i += 1
        out, depth = [], 0
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == "\\" and self.i + 1 < len(self.s):
                out.append(self.s[self.i + 1])
                self.i += 2
                continue
            if self.s.startswith("${", self.i):
                depth += 1
                out.append("${")
                self.i += 2
                continue
            if c == "}" and depth:
                depth -= 1
            if c == '"' and not depth:
                self.i += 1
                return "".join(out)
            if c == "\n":
                break
            out.append(c)
            self.i += 1
        raise HCLError(f"unterminated string on line {start_line}")

    def read_ident(self) -> str:
        if self.peek() == '"':
            return self.read_string()
        m = re.match(r"[A-Za-z_][A-Za-z0-9_\-]*", self.s[self.i:])
        if not m:
            raise HCLError(f"unexpected '{self.peek()}' on line {self.line()}")
        self.i += m.end()
        return m.group(0)

    def parse_body(self, closing=None) -> dict:
        body = {}
        while True:
            self.skip()
            if self.i >= len(self.s):
                if closing:
                    raise HCLError("unbalanced braces: a '{' is never closed")
                return body
            if self.peek() == closing:
                self.i += 1
                return body
            if self.peek() == ",":
                self.i += 1
                continue
            if self.peek() == "}":
                raise HCLError(f"unexpected '}}' on line {self.line()}")
            name = self.read_ident()
            self.skip(newlines=False)
            if self.peek() in ("=", ":"):
                self.i += 1
                body[name] = self.parse_value()
                continue
            labels = []
            while self.peek() == '"':
                labels.append(self.read_string())
                self.skip(newlines=False)
            if self.peek() != "{":
                raise HCLError(f"expected '=' or '{{' after '{name}' on line {self.line()}")
            self.i += 1
            inner = self.parse_body("}")
            self._insert(body, [name] + labels, inner)

    @staticmethod
    def _insert(body, keys, inner):
        target = body
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        last = keys[-1]
        if last in target:
            existing = target[last]
            target[last] = existing + [inner] if isinstance(existing, list) else [existing, inner]
        else:
            target[last] = inner

    def parse_value(self):
        self.skip(newlines=False)
        c = self.peek()
        if c == '"':
            return self.read_string()
        if c == "[":
            self.i += 1
            items = []
            while True:
                self.skip()
                if self.peek() == "]":
                    self.i += 1
                    return items
                if not self.peek():
                    raise HCLError("unbalanced brackets: a '[' is never closed")
                items.append(self.parse_value())
                self.skip()
                if self.peek() == ",":
                    self.i += 1
        if c == "{":
            self.i += 1
            return self.parse_body("}")
        return self._convert(self.read_expression())

    def read_expression(self) -> str:
        start, depth = self.i, 0
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == '"':
                self.read_string()
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif (c == "\n" or c == ",") and depth == 0:
                break
            elif depth == 0 and (c == "#" or self.s.startswith("//", self.i)):
                break
            self.i += 1
        expr = self.s[start:self.i].strip()
        if not expr:
            raise HCLError(f"missing value on line {self.line()}")
        return expr

    @staticmethod
    def _convert(expr: str):
        if expr == "true":
            return True
        if expr == "false":
            return False
        if re.fullmatch(r"-?\d+", expr):
            return int(expr)
        if re.fullmatch(r"-?\d+\.\d+", expr):
            return float(expr)
        return expr


def parse_hcl(content: str):
    try:
        parsed = _HCLParser(content).parse_body()
    except HCLError as e:
        return None, [f"HCL syntax error: {e}"]
    if not parsed:
        return None, ["File is empty."]
    parsed["text"] = content
    return parsed, []


# ---------------------------------------------------------------- bash

_OPENERS = {"if": "fi", "case": "esac", "do": "done"}


def _strip_bash_comments_and_strings(line: str) -> str:
    out, quote = [], None
    for idx, c in enumerate(line):
        if quote:
            if c == quote and (quote == "'" or line[idx - 1] != "\\"):
                quote = None
            continue
        if c in ("'", '"'):
            quote = c
            out.append(" ")
            continue
        if c == "#" and (idx == 0 or line[idx - 1] in " \t;"):
            break
        out.append(c)
    return "".join(out)


def parse_bash(content: str):
    """{'shebang': ..., 'lines': [...], 'text': ...} plus a structural
    check: balanced if/fi, case/esac, do/done, and closed quotes."""
    lines = content.splitlines()
    parsed = {
        "shebang": lines[0].strip() if lines and lines[0].startswith("#!") else "",
        "lines": [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")],
        "text": content,
    }
    if not parsed["lines"]:
        return None, ["Script is empty."]

    stack, problems = [], []
    in_quote = None
    for n, raw in enumerate(lines, start=1):
        # Track multi-line quote state first.
        for idx, c in enumerate(raw):
            if in_quote:
                if c == in_quote and (in_quote == "'" or raw[idx - 1] != "\\"):
                    in_quote = None
            elif c in ("'", '"'):
                in_quote = c
            elif c == "#" and (idx == 0 or raw[idx - 1] in " \t;"):
                break
        code = _strip_bash_comments_and_strings(raw)
        for word in re.findall(r"[A-Za-z_]+", code):
            if word in _OPENERS:
                stack.append((word, n))
            elif word in _OPENERS.values():
                if not stack or _OPENERS[stack[-1][0]] != word:
                    problems.append(f"'{word}' on line {n} doesn't close a matching block")
                else:
                    stack.pop()
    if in_quote:
        problems.append(f"unclosed {in_quote} quote")
    for opener, n in stack:
        problems.append(f"'{opener}' on line {n} is never closed with '{_OPENERS[opener]}'")
    if problems:
        return None, [f"Script syntax error: {p}" for p in problems]
    return parsed, []


def parse_markdown(content: str):
    """{'title', 'sections': {heading: body}, 'headings', 'lines', 'text',
    'empty_section_count'}. Sections are split on level-2 headings
    ('## '), keyed by the heading text lowercased. Labs usually check
    structure with 'order' on lines (e.g. '## Impact' before '## Timeline')
    and content with 'contains'/'absent' on the text."""
    lines = content.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), "")
    sections, current = {}, None
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    bodies = {k: "\n".join(v).strip() for k, v in sections.items()}
    if not lines or not any(l.strip() for l in lines):
        return None, ["Document is empty."]
    return {
        "title": title,
        "sections": bodies,
        "headings": list(bodies),
        "lines": [l.strip() for l in lines if l.strip()],
        "text": content,
        "empty_section_count": sum(1 for b in bodies.values() if not b),
    }, []


def parse_ansible(content: str):
    """An Ansible playbook is a YAML *list* of plays; the validator works on
    mappings, so wrap it: {'plays': [...], 'lines', 'text'}."""
    parsed, problems = parse_yaml(content)
    if problems:
        return None, problems
    if not isinstance(parsed, list):
        return None, ["A playbook must be a YAML list of plays (start the first play with '- name:' or '- hosts:')."]
    return {"plays": parsed,
            "lines": [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")],
            "text": content}, []


def parse_yaml_list(content: str):
    """Any other YAML file whose top level is a list (Falco rules, for
    example): {'items': [...], 'lines', 'text'}. Paths then read
    'items[0].rule' or 'items[*].priority'."""
    parsed, problems = parse_yaml(content)
    if problems:
        return None, problems
    if not isinstance(parsed, list):
        return None, ["This file must be a YAML list: each top-level entry starts with '- '."]
    return {"items": parsed,
            "lines": [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")],
            "text": content}, []


# ---------------------------------------------------------------- nginx

class NginxError(Exception):
    pass


# Directives that are legitimately written across several lines. Anything
# else spanning lines is almost always a forgotten ';'.
_NGINX_MULTILINE = {"log_format", "map", "geo", "types"}


def _nginx_tokens(content: str) -> list:
    """[(token, line, quoted)] — words, quoted strings, and the three
    structural characters { } ;. Comments run from an unquoted # to the
    end of the line. ${var} stays inside its word."""
    out, i, line, n = [], 0, 1, len(content)
    while i < n:
        c = content[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif c == "#":
            while i < n and content[i] != "\n":
                i += 1
        elif c in "{};":
            out.append((c, line, False))
            i += 1
        elif c in "'\"":
            start_line, quote, buf = line, c, []
            i += 1
            while i < n and content[i] != quote:
                if content[i] == "\\" and i + 1 < n:
                    buf.append(content[i + 1])
                    i += 2
                    continue
                if content[i] == "\n":
                    line += 1
                buf.append(content[i])
                i += 1
            if i >= n:
                raise NginxError(f"unterminated quote starting on line {start_line}")
            i += 1
            out.append(("".join(buf), start_line, True))
        else:
            start = i
            while i < n and not content[i].isspace() and content[i] not in ";{}":
                if content.startswith("${", i):
                    end = content.find("}", i)
                    i = end if end != -1 else n - 1
                i += 1
            out.append((content[start:i], line, False))
    return out


def _nginx_insert(body: dict, key: str, value):
    """A repeated directive or block becomes a list, like HCL blocks."""
    if key in body:
        existing = body[key]
        body[key] = existing + [value] if isinstance(existing, list) else [existing, value]
    else:
        body[key] = value


def _nginx_block(tokens: list, pos: int, top: bool):
    body = {}
    while True:
        if pos >= len(tokens):
            if not top:
                raise NginxError("unbalanced braces: a '{' is never closed")
            return body, pos
        tok, line, quoted = tokens[pos]
        if tok == "}" and not quoted:
            if top:
                raise NginxError(f"unexpected '}}' on line {line}")
            return body, pos + 1
        if tok in ("{", ";") and not quoted:
            raise NginxError(f"unexpected '{tok}' on line {line}")
        name, first_line, words = tok, line, []
        pos += 1
        while True:
            if pos >= len(tokens):
                raise NginxError(f"missing ';' after '{name}' on line {first_line}")
            tok, line, quoted = tokens[pos]
            if not quoted and tok in (";", "{", "}"):
                break
            if line != first_line and name not in _NGINX_MULTILINE and not quoted:
                shown = " ".join([name] + words)
                raise NginxError(f"missing ';' at the end of line {first_line} ('{shown}')")
            words.append(tok)
            pos += 1
        if tok == "}":
            raise NginxError(f"missing ';' after '{name}' on line {first_line}")
        if tok == ";":
            _nginx_insert(body, name, " ".join(words))
            pos += 1
            continue
        inner, pos = _nginx_block(tokens, pos + 1, top=False)
        if words:
            # 'location /api/ { }' -> {"location": {"/api/": {...}}}
            _nginx_insert(body.setdefault(name, {}), " ".join(words), inner)
        else:
            _nginx_insert(body, name, inner)


def parse_nginx(content: str):
    """nginx configuration -> nested dict. A simple directive maps its name
    to its arguments as one string ('listen': '443 ssl'); a block maps its
    name to a dict, keyed by its arguments when it has any ('upstream':
    {'backend': {...}}, 'location': {'/api/': {...}}). Anything repeated at
    the same level (two 'server' blocks, several 'proxy_set_header' lines)
    becomes a list. Structural only: it catches unbalanced braces and
    missing semicolons, not unknown directives — that's what `nginx -t`
    is for."""
    try:
        parsed, _ = _nginx_block(_nginx_tokens(content), 0, top=True)
    except NginxError as e:
        return None, [f"nginx syntax error: {e}"]
    if not parsed:
        return None, ["File is empty."]
    parsed["lines"] = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    parsed["text"] = content
    return parsed, []


# ---------------------------------------------------------------- python

def parse_python(content: str):
    """Python source -> {'functions', 'imports', 'calls', 'has_main_guard',
    'shebang', 'lines', 'text'}, using the standard library's ast module.
    'calls' holds dotted call names as written ('subprocess.run',
    'parser.add_argument', 'sys.exit'). The file is parsed, never run, so
    this proves it's valid Python with the right structure, not that it
    works."""
    if not content.strip():
        return None, ["File is empty."]
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return None, [f"Python syntax error on line {e.lineno}: {e.msg}"]

    functions, imports, calls = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Call):
            calls.append(ast.unparse(node.func))

    has_main_guard = any(
        isinstance(node, ast.If) and "__name__" in ast.unparse(node.test) and "__main__" in ast.unparse(node.test)
        for node in tree.body
    )
    lines = content.splitlines()
    return {
        "functions": functions,
        "imports": imports,
        "calls": calls,
        "has_main_guard": has_main_guard,
        "shebang": lines[0] if lines and lines[0].startswith("#!") else "",
        "lines": [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")],
        "text": content,
    }, []


PARSERS = {
    "python": parse_python,
    "nginx": parse_nginx,
    "yaml": parse_yaml,
    "dockerfile": parse_dockerfile,
    "hcl": parse_hcl,
    "bash": parse_bash,
    "markdown": parse_markdown,
    "ansible": parse_ansible,
    "yamllist": parse_yaml_list,
}


def parse(fmt: str, content: str):
    return PARSERS[fmt](content)
