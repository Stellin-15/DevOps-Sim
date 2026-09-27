"""Tests for yaml_lab.py — dotted-path resolution, manifest validation,
and the file-based run loop."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml_lab


class TestGetValue:
    def test_simple_key(self):
        found, value = yaml_lab.get_value({"kind": "Pod"}, "kind")
        assert found and value == "Pod"

    def test_nested_key(self):
        obj = {"metadata": {"name": "db"}}
        found, value = yaml_lab.get_value(obj, "metadata.name")
        assert found and value == "db"

    def test_list_index(self):
        obj = {"spec": {"containers": [{"image": "nginx"}]}}
        found, value = yaml_lab.get_value(obj, "spec.containers[0].image")
        assert found and value == "nginx"

    def test_missing_key_returns_false(self):
        found, value = yaml_lab.get_value({"kind": "Pod"}, "metadata.name")
        assert not found

    def test_index_out_of_range_returns_false(self):
        obj = {"spec": {"containers": []}}
        found, value = yaml_lab.get_value(obj, "spec.containers[0].image")
        assert not found

    def test_indexing_into_non_list_returns_false(self):
        obj = {"spec": "not a list"}
        found, value = yaml_lab.get_value(obj, "spec[0]")
        assert not found

    def test_deep_path(self):
        obj = {"spec": {"containers": [{"resources": {"limits": {"memory": "512Mi"}}}]}}
        found, value = yaml_lab.get_value(obj, "spec.containers[0].resources.limits.memory")
        assert found and value == "512Mi"


class TestValidateManifest:
    def test_passes_when_all_fields_match(self):
        parsed = {"kind": "Pod", "metadata": {"name": "db"}}
        problems = yaml_lab.validate_manifest(parsed, {"kind": "Pod", "fields": {"metadata.name": "db"}})
        assert problems == []

    def test_reports_wrong_kind(self):
        parsed = {"kind": "Deployment"}
        problems = yaml_lab.validate_manifest(parsed, {"kind": "Pod", "fields": {}})
        assert any("kind" in p for p in problems)

    def test_reports_missing_kind(self):
        parsed = {"metadata": {"name": "db"}}
        problems = yaml_lab.validate_manifest(parsed, {"kind": "Pod", "fields": {}})
        assert any("kind is missing" in p for p in problems)

    def test_reports_missing_field(self):
        parsed = {"kind": "Pod", "metadata": {}}
        problems = yaml_lab.validate_manifest(parsed, {"kind": "Pod", "fields": {"metadata.name": "db"}})
        assert any("metadata.name" in p and "missing" in p for p in problems)

    def test_reports_wrong_value(self):
        parsed = {"kind": "Pod", "metadata": {"name": "wrong-name"}}
        problems = yaml_lab.validate_manifest(parsed, {"kind": "Pod", "fields": {"metadata.name": "db"}})
        assert any("metadata.name" in p for p in problems)

    def test_any_sentinel_accepts_any_value(self):
        parsed = {"kind": "Pod", "metadata": {"name": "whatever"}}
        problems = yaml_lab.validate_manifest(parsed, {"kind": "Pod", "fields": {"metadata.name": "ANY"}})
        assert problems == []

    def test_none_parsed_is_reported(self):
        problems = yaml_lab.validate_manifest(None, {"kind": "Pod", "fields": {}})
        assert len(problems) == 1

    def test_non_dict_top_level_is_reported(self):
        problems = yaml_lab.validate_manifest(["not", "a", "dict"], {"kind": "Pod", "fields": {}})
        assert len(problems) == 1

    def test_multiple_fields_all_checked(self):
        parsed = {"kind": "Pod", "metadata": {"name": "db"}, "spec": {"containers": [{"image": "wrong"}]}}
        spec = {
            "kind": "Pod",
            "fields": {
                "metadata.name": "db",
                "spec.containers[0].image": "postgres:15",
            },
        }
        problems = yaml_lab.validate_manifest(parsed, spec)
        assert len(problems) == 1
        assert "spec.containers[0].image" in problems[0]


class TestLoadAndParse:
    def test_missing_file(self, tmp_path):
        parsed, problems = yaml_lab.load_and_parse(tmp_path / "does_not_exist.yaml")
        assert parsed is None
        assert "not found" in problems[0].lower()

    def test_valid_yaml(self, tmp_path):
        f = tmp_path / "pod.yaml"
        f.write_text("kind: Pod\nmetadata:\n  name: db\n", encoding="utf-8")
        parsed, problems = yaml_lab.load_and_parse(f)
        assert problems == []
        assert parsed == {"kind": "Pod", "metadata": {"name": "db"}}

    def test_invalid_yaml_syntax(self, tmp_path):
        f = tmp_path / "broken.yaml"
        f.write_text("kind: Pod\n  bad indent: [unterminated\n", encoding="utf-8")
        parsed, problems = yaml_lab.load_and_parse(f)
        assert parsed is None
        assert "syntax error" in problems[0].lower()

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        parsed, problems = yaml_lab.load_and_parse(f)
        assert parsed is None
        assert problems == []  # yaml.safe_load("") is None, not a parse error


class TestRunYamlLab:
    def _lab(self, tmp_path, starter="", solution_field="db"):
        return {
            "title": "Test Lab",
            "intro": "intro text",
            "steps": [
                {
                    "file": "pod.yaml",
                    "starter_content": starter,
                    "prompt": "Write a Pod named 'db'.",
                    "apply_commands": ["kubectl apply -f pod.yaml"],
                    "validate": {"kind": "Pod", "fields": {"metadata.name": solution_field}},
                    "fake_output": "pod/db created",
                }
            ],
        }

    def test_correct_file_completes_lab(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yaml_lab, "WORKSPACE_DIR", tmp_path)
        inputs = iter(["kubectl apply -f pod.yaml"])

        def fake_read_input(prompt=""):
            # By the time this runs, the "player" has already written the correct file.
            (tmp_path / "pod.yaml").write_text("kind: Pod\nmetadata:\n  name: db\n", encoding="utf-8")
            return next(inputs)

        monkeypatch.setattr(yaml_lab, "read_input", fake_read_input)
        assert yaml_lab.run_yaml_lab(self._lab(tmp_path)) is True

    def test_quit_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yaml_lab, "WORKSPACE_DIR", tmp_path)
        monkeypatch.setattr(yaml_lab, "read_input", lambda prompt="": "exit")
        assert yaml_lab.run_yaml_lab(self._lab(tmp_path)) is False

    def test_starter_content_is_written_to_workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(yaml_lab, "WORKSPACE_DIR", tmp_path)
        step = {"file": "deployment.yaml", "starter_content": "kind: Deployment\n"}
        file_path = yaml_lab.prepare_file(step)
        assert file_path.read_text(encoding="utf-8") == "kind: Deployment\n"

    def test_wrong_then_correct_attempt(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(yaml_lab, "WORKSPACE_DIR", tmp_path)
        (tmp_path / "pod.yaml").write_text("kind: Pod\nmetadata:\n  name: wrong\n", encoding="utf-8")
        inputs = iter(["kubectl apply -f pod.yaml", "kubectl apply -f pod.yaml"])

        def fake_read_input(prompt=""):
            value = next(inputs)
            if value == "kubectl apply -f pod.yaml" and "wrong" in (tmp_path / "pod.yaml").read_text():
                # Second call fixes the file before the (second) apply is processed.
                pass
            return value

        call_count = {"n": 0}

        def fake_read_input_fix(prompt=""):
            call_count["n"] += 1
            if call_count["n"] == 2:
                (tmp_path / "pod.yaml").write_text("kind: Pod\nmetadata:\n  name: db\n", encoding="utf-8")
            return next(inputs)

        monkeypatch.setattr(yaml_lab, "read_input", fake_read_input_fix)
        assert yaml_lab.run_yaml_lab(self._lab(tmp_path)) is True
        out = capsys.readouterr().out
        assert "Not quite" in out
