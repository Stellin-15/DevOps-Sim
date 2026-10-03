"""Tests for git_sandbox.py, which runs the real git: each problem starts
unfixed, the real fix clears it, the tempting wrong fixes don't, history
rewrites of pushed commits count as collateral, and commands that would
leave the repository or run programs are refused."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import git_sandbox as gs
from sandbox_common import run_command


def fresh(problem):
    return gs.generate_state(seed=1, problems=[problem])


def run(state, cmd):
    return run_command(gs.handle_command, state, cmd.format(**gs.placeholders(state)))


def fixed(state, problem):
    return gs.FIXES[problem](state)


@pytest.mark.parametrize("problem", gs.PROBLEMS)
def test_starts_unfixed_without_collateral(problem):
    state = fresh(problem)
    assert not fixed(state, problem)
    assert gs.collateral_issues(state) == set()


def test_random_state_has_one_known_problem():
    state = gs.generate_state(seed=5)
    assert len(state["problems"]) == 1 and state["problems"][0] in gs.PROBLEMS


def test_states_are_independent_copies():
    a, b = fresh("lost_commits"), fresh("lost_commits")
    assert a["repo"] != b["repo"]
    run(a, "git reset --hard HEAD@{{1}}")
    assert fixed(a, "lost_commits") and not fixed(b, "lost_commits")


def test_hashes_are_the_same_every_time():
    assert fresh("bad_commit")["expected"]["bad_commit"] == fresh("bad_commit")["expected"]["bad_commit"]


# ------------------------------------------------------------------ real fixes

FIXES = {
    "wrong_branch": ["git branch -f feature/search main", "git reset --hard origin/main"],
    "leaked_secret": ["git rebase --onto {leak_commit}^ {leak_commit}"],
    "merge_conflict": ["sed -i '/^<<<<<<<\\|^=======\\|^>>>>>>>/d' app/pricing.py",
                       "git add app/pricing.py", "git commit --no-edit"],
    "lost_commits": ["git reset --hard HEAD@{{1}}"],
    "bad_commit": ["git revert --no-edit {bad_commit}"],
}


@pytest.mark.parametrize("problem", gs.PROBLEMS)
def test_real_fix_works(problem):
    state = fresh(problem)
    for cmd in FIXES[problem]:
        run(state, cmd)
    assert fixed(state, problem)
    assert gs.collateral_issues(state) == set()
    assert "[fixed]" in run(state, "check")


# ----------------------------------------------------------------- wrong fixes

def test_resetting_main_alone_loses_the_commits():
    state = fresh("wrong_branch")
    run(state, "git reset --hard origin/main")
    assert not fixed(state, "wrong_branch")


def test_deleting_the_key_in_a_new_commit_leaves_it_in_history():
    state = fresh("leaked_secret")
    run(state, "sed -i '/PAYMENT_API_KEY/d' config/settings.py")
    run(state, "git commit -am 'remove key'")
    assert "remove key" in run(state, "git log --oneline -1")
    assert not fixed(state, "leaked_secret")


def test_dropping_every_unpushed_commit_is_not_a_fix():
    state = fresh("leaked_secret")
    run(state, "git reset --hard origin/main")
    assert not fixed(state, "leaked_secret")


def test_aborting_or_taking_one_side_is_not_a_merge():
    state = fresh("merge_conflict")
    run(state, "git checkout --ours app/pricing.py")
    run(state, "git add app/pricing.py")
    run(state, "git commit --no-edit")
    assert not fixed(state, "merge_conflict")
    state = fresh("merge_conflict")
    run(state, "git merge --abort")
    assert not fixed(state, "merge_conflict")


def test_committing_the_markers_is_not_a_merge():
    state = fresh("merge_conflict")
    run(state, "git add app/pricing.py")
    run(state, "git commit --no-edit")
    assert not fixed(state, "merge_conflict")


def test_resetting_past_the_bad_commit_rewrites_pushed_history():
    state = fresh("bad_commit")
    run(state, "git reset --hard {bad_commit}^")
    assert not fixed(state, "bad_commit")
    assert any("already pushed" in issue for issue in gs.collateral_issues(state))


def test_deleting_a_tag_or_branch_is_collateral():
    state = fresh("wrong_branch")
    run(state, "git tag -d v1.4")
    run(state, "git branch -D feature/search")
    issues = gs.collateral_issues(state)
    assert "deleted the release tag v1.4" in issues and "deleted the branch feature/search" in issues


# ------------------------------------------------------------------- refusals

@pytest.mark.parametrize("cmd", [
    "git push origin main", "git fetch", "git pull", "git clone https://git.shop.example/x.git",
    "git -C .. status", "git -c core.pager=less log", "git config alias.x '!echo hi'",
    "git config --global user.name x", "git bisect run python -c 1", "git rebase -x 'echo hi' HEAD~1",
    "git log --help", "git help log", "git format-patch -o /tmp HEAD~1", "git worktree add ../w",
])
def test_refused(cmd):
    out = run(fresh("bad_commit"), cmd)
    assert "isn't available" in out or "aren't available" in out or "doesn't allow" in out \
        or "git-scm.com" in out or "executes a program" in out or "runs shell" in out, out


def test_allowed_config_still_works():
    state = fresh("bad_commit")
    run(state, "git config user.name Sam")
    assert run(state, "git config user.name") == "Sam"


def test_files_outside_the_repository_are_unreachable():
    state = fresh("bad_commit")
    assert "No such file" in run(state, "cat ../../conftest.py")
    assert "No such file" in run(state, "ls ../..")


def test_sed_refuses_git_internals():
    state = fresh("bad_commit")
    assert "isn't allowed" in run(state, "sed -i 's/a/b/' .git/config")


def test_commit_without_message_explains_the_skipped_editor():
    state = fresh("bad_commit")
    out = run(state, "git commit --allow-empty")
    assert out.startswith("(no terminal")


# --------------------------------------------------------------------- helpers

def test_basic_regex_conversion():
    assert gs._bre_to_python(r"^<<<\|^===") == "^<<<|^==="
    assert gs._bre_to_python("a+(b)") == r"a\+\(b\)"


def test_sed_substitute_and_print():
    state = fresh("bad_commit")
    assert "TIMEOUT_SECONDS = 99" in run(state, "sed 's/= 0/= 99/' config/settings.py")
    assert "TIMEOUT_SECONDS = 0" in run(state, "cat config/settings.py")  # no -i: file unchanged


def test_meta_commands():
    state = fresh("merge_conflict")
    assert "app/" in run(state, "ls")
    assert run(state, "pwd") == state["repo"]
    assert "own editor" in run(state, "edit app/pricing.py")
    assert "both modified" in run(state, "git status | grep both")


def test_missing_repository_is_rebuilt():

    state = fresh("bad_commit")
    gs._rmtree(Path(state["repo"]).parent)
    assert "rebuilt" in run(state, "git status")
    assert not fixed(state, "bad_commit") and Path(state["repo"]).exists()
