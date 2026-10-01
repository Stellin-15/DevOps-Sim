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


class TestMarkdown:
    DOC = "# Postmortem: Outage\n\n## Summary\nIt broke.\n\n## Impact\n\n## Timeline (UTC)\n- 14:02 deploy\n"

    def test_sections_title_and_empty_count(self):
        parsed, problems = lab_formats.parse("markdown", self.DOC)
        assert problems == []
        assert parsed["title"] == "Postmortem: Outage"
        assert parsed["headings"] == ["summary", "impact", "timeline (utc)"]
        assert parsed["sections"]["summary"] == "It broke."
        assert parsed["empty_section_count"] == 1

    def test_order_check_on_headings(self):
        parsed, _ = lab_formats.parse("markdown", self.DOC)
        assert yaml_lab._check_order(parsed, ["## Summary", "## Impact", "## Timeline"]) == []
        assert yaml_lab._check_order(parsed, ["## Impact", "## Summary"]) != []

    def test_empty_document(self):
        assert lab_formats.parse("markdown", "   \n")[0] is None


class TestAnsible:
    def test_playbook_list_is_wrapped_in_plays(self):
        parsed, problems = lab_formats.parse("ansible", "- name: x\n  hosts: web\n  serial: 2\n  tasks: []\n")
        assert problems == []
        assert yaml_lab.get_values(parsed, "plays[0].hosts") == ["web"]
        assert "serial: 2" in parsed["text"]

    def test_mapping_is_rejected_with_a_helpful_message(self):
        parsed, problems = lab_formats.parse("ansible", "hosts: web\ntasks: []\n")
        assert parsed is None and "list of plays" in problems[0]

    def test_yaml_errors_pass_through(self):
        parsed, problems = lab_formats.parse("ansible", "- name: [unclosed\n")
        assert parsed is None and "YAML syntax error" in problems[0]


class TestNginx:
    CONF = (
        "# reverse proxy\n"
        "upstream backend {\n"
        "    least_conn;\n"
        "    server 10.0.1.11:8080 max_fails=3;  # first\n"
        "    server 10.0.1.12:8080;\n"
        "}\n"
        "\n"
        "server {\n"
        "    listen 443 ssl;\n"
        "    server_name shop.example.com;\n"
        "\n"
        "    location / {\n"
        "        proxy_pass http://backend;\n"
        "        proxy_set_header Host $host;\n"
        "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        "    }\n"
        "    location /static/ {\n"
        "        root /var/www;\n"
        "        add_header Cache-Control \"public, max-age=3600\";\n"
        "    }\n"
        "}\n"
    )

    def test_directives_blocks_and_labels(self):
        parsed, problems = lab_formats.parse("nginx", self.CONF)
        assert problems == []
        assert parsed["server"]["listen"] == "443 ssl"
        assert parsed["upstream"]["backend"]["least_conn"] == ""
        assert yaml_lab.get_values(parsed, "server.location./.proxy_pass") == ["http://backend"]
        assert yaml_lab.get_values(parsed, "server.location./static/.root") == ["/var/www"]

    def test_repeated_directives_become_a_list(self):
        parsed, _ = lab_formats.parse("nginx", self.CONF)
        assert parsed["upstream"]["backend"]["server"] == ["10.0.1.11:8080 max_fails=3", "10.0.1.12:8080"]
        assert yaml_lab.get_values(parsed, "upstream.backend.server[*]") == ["10.0.1.11:8080 max_fails=3", "10.0.1.12:8080"]
        headers = parsed["server"]["location"]["/"]["proxy_set_header"]
        assert headers == ["Host $host", "X-Forwarded-For $proxy_add_x_forwarded_for"]

    def test_repeated_blocks_become_a_list(self):
        parsed, problems = lab_formats.parse("nginx", "server { listen 80; }\nserver { listen 443 ssl; }\n")
        assert problems == []
        assert [s["listen"] for s in parsed["server"]] == ["80", "443 ssl"]

    def test_quoted_values_keep_semicolons_braces_and_hashes(self):
        parsed, problems = lab_formats.parse("nginx", "server {\n  return 200 'a; b { # c }';\n}\n")
        assert problems == []
        assert parsed["server"]["return"] == "200 a; b { # c }"

    def test_comments_are_ignored_but_stay_in_text(self):
        parsed, _ = lab_formats.parse("nginx", self.CONF)
        assert "# reverse proxy" not in parsed["lines"]
        assert "# reverse proxy" in parsed["text"]
        assert "first" not in parsed["upstream"]["backend"]["server"][0]

    def test_variable_braces_stay_in_the_word(self):
        parsed, problems = lab_formats.parse("nginx", "server {\n  return 301 https://${host}${request_uri};\n}\n")
        assert problems == []
        assert parsed["server"]["return"] == "301 https://${host}${request_uri}"

    def test_missing_semicolon_names_the_line(self):
        parsed, problems = lab_formats.parse("nginx", "server {\n  listen 80\n  server_name x;\n}\n")
        assert parsed is None
        assert "missing ';'" in problems[0] and "line 2" in problems[0] and "listen 80" in problems[0]

    def test_missing_semicolon_before_closing_brace(self):
        parsed, problems = lab_formats.parse("nginx", "server {\n  listen 80\n}\n")
        assert parsed is None and "missing ';'" in problems[0]

    def test_unbalanced_braces(self):
        assert "never closed" in lab_formats.parse("nginx", "server {\n  listen 80;\n")[1][0]
        assert "unexpected '}'" in lab_formats.parse("nginx", "server {\n  listen 80;\n}\n}\n")[1][0]

    def test_multiline_log_format_is_allowed(self):
        conf = "http {\n  log_format main '$remote_addr $status'\n                  '$request_time';\n}\n"
        parsed, problems = lab_formats.parse("nginx", conf)
        assert problems == []
        assert parsed["http"]["log_format"] == "main $remote_addr $status $request_time"

    def test_empty_file(self):
        assert lab_formats.parse("nginx", "# nothing here\n") == (None, ["File is empty."])

    def test_validation_with_contains_and_order(self):
        parsed, _ = lab_formats.parse("nginx", self.CONF)
        spec = {
            "fields": {
                "server.location./.proxy_set_header": {"contains": ["Host $host", "X-Forwarded-For"]},
                "upstream.backend.server[*]": {"contains": "10.0.1.12"},
            },
            "order": ["upstream backend", "server {", "location /"],
            "absent": ["proxy_pass http://10."],
        }
        assert yaml_lab.validate_manifest(parsed, spec) == []
