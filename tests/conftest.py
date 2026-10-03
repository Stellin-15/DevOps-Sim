"""Shared test setup: the Git sandbox builds real repositories, so tests
put them in a temporary directory instead of workspace/, and skip
everything that needs git when it isn't installed."""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import git_sandbox


@pytest.fixture(autouse=True, scope="session")
def _git_sandbox_in_temp_dir(tmp_path_factory):
    git_sandbox.WORK_ROOT = tmp_path_factory.mktemp("git-sandbox")


def pytest_collection_modifyitems(config, items):
    if shutil.which("git"):
        return
    skip = pytest.mark.skip(reason="git is not installed")
    for item in items:
        if "mystery-git" in item.nodeid or "test_git_sandbox" in item.nodeid:
            item.add_marker(skip)
