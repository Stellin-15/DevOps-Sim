"""Tests for sandbox_common.py — pipes, table rendering, persistence."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sandbox_common as sc

SAMPLE = "alpha running\nbeta Exited\ngamma running\ndelta Exited"


class TestSplitPipes:
    def test_splits_on_pipes(self):
        assert sc.split_pipes("ps aux | grep python | head -3") == ["ps aux", "grep python", "head -3"]

    def test_ignores_pipes_inside_quotes(self):
        assert sc.split_pipes("grep 'a|b' file") == ["grep 'a|b' file"]


class TestApplyPipe:
    def test_grep(self):
        assert sc.apply_pipe(SAMPLE, "grep Exited") == "beta Exited\ndelta Exited"

    def test_grep_ignore_case_and_invert(self):
        assert sc.apply_pipe(SAMPLE, "grep -i exited") == "beta Exited\ndelta Exited"
        assert sc.apply_pipe(SAMPLE, "grep -v running") == "beta Exited\ndelta Exited"

    def test_grep_count(self):
        assert sc.apply_pipe(SAMPLE, "grep -c running") == "2"

    def test_grep_quoted_pattern_with_spaces(self):
        assert sc.apply_pipe("out of memory here\nfine", "grep -i 'Out of memory'") == "out of memory here"

    def test_head_and_tail_forms(self):
        assert sc.apply_pipe(SAMPLE, "head -2").splitlines() == ["alpha running", "beta Exited"]
        assert sc.apply_pipe(SAMPLE, "head -n 1") == "alpha running"
        assert sc.apply_pipe(SAMPLE, "tail -1") == "delta Exited"

    def test_wc_and_sort(self):
        assert sc.apply_pipe(SAMPLE, "wc -l") == "4"
        assert sc.apply_pipe(SAMPLE, "sort").splitlines()[0] == "alpha running"

    def test_unsupported_pipe_explains_itself(self):
        assert "isn't supported" in sc.apply_pipe(SAMPLE, "awk '{print $1}'")


class TestRunCommand:
    def test_chains_pipes_after_the_sandbox_command(self):
        out = sc.run_command(lambda state, raw: SAMPLE if raw == "list" else "?", {}, "list | grep Exited | wc -l")
        assert out == "2"

    def test_exit_passes_through_as_none(self):
        assert sc.run_command(lambda state, raw: None, {}, "exit") is None


class TestRenderTable:
    def test_columns_fit_widest_cell(self):
        out = sc.render_table(["NAME", "X"], [["a-very-long-name", "1"], ["b", "2"]])
        header, row1, _ = out.splitlines()
        assert header.index("X") == row1.index("1")


class TestSandboxStore:
    def test_kubernetes_keeps_legacy_location(self):
        assert sc.SandboxStore("kubernetes").root == sc.SANDBOX_ROOT

    def test_other_kinds_get_their_own_folder(self):
        assert sc.SandboxStore("docker").root == sc.SANDBOX_ROOT / "docker"

    def test_save_and_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "SANDBOX_ROOT", tmp_path)
        store = sc.SandboxStore("linux")
        store.save_current({"x": 1})
        assert store.current_file.exists()
        monkeypatch.setattr(sc, "read_input", lambda prompt="": "y")
        store.prompt_keep({"x": 1}, "server")
        assert len(store.list_saved()) == 1

    def test_discard_deletes_current(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "SANDBOX_ROOT", tmp_path)
        store = sc.SandboxStore("linux")
        store.save_current({"x": 1})
        monkeypatch.setattr(sc, "read_input", lambda prompt="": "n")
        store.prompt_keep({"x": 1}, "server")
        assert not store.current_file.exists()
