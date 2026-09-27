"""Tests for lab_formats.py (Dockerfile, HCL, bash parsers) and the
order/absent checks they enable in yaml_lab.validate_manifest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lab_formats
import yaml_lab


class TestDockerfile:
    def test_parses_instructions_into_lines_and_lists(self):
        parsed, problems = lab_formats.parse_dockerfile(
            "FROM node:20-alpine\n# comment\nWORKDIR /app\nCOPY . .\nCMD [\"node\", \"server.js\"]\n"
        )
        assert problems == []
        assert parsed["lines"][0] == "FROM node:20-alpine"
        assert parsed["WORKDIR"] == ["/app"]
        assert parsed["CMD"] == ['["node", "server.js"]']

    def test_joins_line_continuations(self):
        parsed, _ = lab_formats.parse_dockerfile("FROM alpine\nRUN apk add \\\n    curl \\\n    git\n")
        assert parsed["RUN"] == ["apk add curl git"]

    def test_instructions_are_case_insensitive(self):
        parsed, _ = lab_formats.parse_dockerfile("from alpine\nrun echo hi\n")
        assert parsed["lines"] == ["FROM alpine", "RUN echo hi"]

    def test_unknown_instruction_is_reported(self):
        parsed, problems = lab_formats.parse_dockerfile("FORM alpine\n")
        assert parsed is None and "Unknown Dockerfile instruction 'FORM'" in problems[0]

    def test_must_start_with_from(self):
        parsed, problems = lab_formats.parse_dockerfile("RUN echo hi\nFROM alpine\n")
        assert parsed is None and "must start with FROM" in problems[0]

    def test_arg_before_from_is_allowed(self):
        _, problems = lab_formats.parse_dockerfile("ARG VERSION=20\nFROM node:${VERSION}\n")
        assert problems == []


class TestHCL:
    def test_blocks_with_labels_become_nested_keys(self):
        parsed, problems = lab_formats.parse_hcl('resource "aws_s3_bucket" "logs" {\n  bucket = "acme-logs"\n}\n')
        assert problems == []
        assert parsed["resource"]["aws_s3_bucket"]["logs"]["bucket"] == "acme-logs"

    def test_value_types(self):
        parsed, _ = lab_formats.parse_hcl('x {\n  n = 3\n  f = 1.5\n  b = true\n  ref = var.region\n  l = ["a", "b"]\n}\n')
        assert parsed["x"] == {"n": 3, "f": 1.5, "b": True, "ref": "var.region", "l": ["a", "b"]}

    def test_nested_blocks_and_maps(self):
        text = (
            'terraform {\n'
            '  required_providers {\n'
            '    aws = {\n'
            '      source  = "hashicorp/aws"\n'
            '      version = "~> 5.0"\n'
            '    }\n'
            '  }\n'
            '  backend "s3" {\n'
            '    encrypt = true\n'
            '  }\n'
            '}\n'
        )
        parsed, problems = lab_formats.parse_hcl(text)
        assert problems == []
        assert parsed["terraform"]["required_providers"]["aws"]["version"] == "~> 5.0"
        assert parsed["terraform"]["backend"]["s3"]["encrypt"] is True

    def test_interpolation_kept_raw_in_strings(self):
        parsed, _ = lab_formats.parse_hcl('x {\n  name = "logs-${var.env}"\n}\n')
        assert parsed["x"]["name"] == "logs-${var.env}"

    def test_comments_are_ignored(self):
        parsed, problems = lab_formats.parse_hcl('# top\nx {\n  // line\n  a = 1 # trailing\n  /* block */\n}\n')
        assert problems == [] and parsed["x"]["a"] == 1

    def test_function_call_expression_kept_raw(self):
        parsed, _ = lab_formats.parse_hcl('x {\n  tags = merge(var.tags, { Name = "web" })\n}\n')
        assert parsed["x"]["tags"] == 'merge(var.tags, { Name = "web" })'

    def test_repeated_blocks_become_a_list(self):
        parsed, _ = lab_formats.parse_hcl('sg {\n  ingress {\n    port = 22\n  }\n  ingress {\n    port = 443\n  }\n}\n')
        assert [r["port"] for r in parsed["sg"]["ingress"]] == [22, 443]

    def test_unbalanced_brace_is_a_syntax_error(self):
        parsed, problems = lab_formats.parse_hcl('resource "a" "b" {\n  x = 1\n')
        assert parsed is None and "HCL syntax error" in problems[0]

    def test_missing_value_is_a_syntax_error(self):
        parsed, problems = lab_formats.parse_hcl('x {\n  a =\n}\n')
        assert parsed is None and "missing value" in problems[0]


class TestBash:
    def test_extracts_shebang_and_code_lines(self):
        parsed, problems = lab_formats.parse_bash("#!/usr/bin/env bash\n# comment\nset -euo pipefail\necho hi\n")
        assert problems == []
        assert parsed["shebang"] == "#!/usr/bin/env bash"
        assert parsed["lines"] == ["set -euo pipefail", "echo hi"]

    def test_balanced_blocks_pass(self):
        script = "if [ -z \"$1\" ]; then\n  exit 1\nfi\nfor f in *; do\n  echo \"$f\"\ndone\ncase $x in\n  a) echo a ;;\nesac\n"
        _, problems = lab_formats.parse_bash(script)
        assert problems == []

    def test_unclosed_if_is_reported(self):
        parsed, problems = lab_formats.parse_bash("if true; then\n  echo hi\n")
        assert parsed is None and "never closed with 'fi'" in problems[0]

    def test_unclosed_quote_is_reported(self):
        parsed, problems = lab_formats.parse_bash('echo "hello\n')
        assert parsed is None and "unclosed" in problems[0]

    def test_keywords_inside_quotes_and_comments_are_ignored(self):
        _, problems = lab_formats.parse_bash('echo "if you see this"  # then done\necho \'fi\'\n')
        assert problems == []


class TestOrderAndAbsent:
    def test_order_passes_when_sequence_is_correct(self):
        parsed = {"lines": ["COPY package.json ./", "RUN npm ci", "COPY . ."]}
        assert yaml_lab.validate_manifest(parsed, {"order": ["COPY package", "RUN npm ci", "COPY . ."]}) == []

    def test_order_reports_wrong_sequence(self):
        parsed = {"lines": ["COPY . .", "RUN npm ci"]}
        problems = yaml_lab.validate_manifest(parsed, {"order": ["RUN npm ci", "COPY . ."]})
        assert problems == ["'COPY . .' must come after 'RUN npm ci'"]

    def test_order_reports_missing_line(self):
        problems = yaml_lab.validate_manifest({"lines": ["FROM a"]}, {"order": ["USER node"]})
        assert "missing a line containing 'USER node'" in problems[0]

    def test_absent_flags_forbidden_text(self):
        problems = yaml_lab.validate_manifest({"lines": []}, {"absent": ["hunter2"]}, text='password = "hunter2"')
        assert problems == ["file must not contain 'hunter2'"]

    def test_absent_passes_when_text_is_clean(self):
        assert yaml_lab.validate_manifest({"lines": []}, {"absent": ["hunter2"]}, text="ok") == []
