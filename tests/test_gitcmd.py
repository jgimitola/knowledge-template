"""git subprocesses must obey the path they are given, not the ambient environment.

These tests deliberately set GIT_DIR, which is what git itself exports to every hook it
runs. The autouse fixture in conftest scrubs it for every other test; here it is put back,
because the point is to prove the library does not need a clean environment to be correct.
"""

import subprocess

import pytest

from knowledge import gitcmd


def test_clean_env_drops_the_variables_that_bind_git_to_a_repository():
    polluted = {
        "PATH": "/usr/bin",
        "GIT_DIR": "/somewhere/.git/worktrees/x",
        "GIT_WORK_TREE": "/somewhere",
        "GIT_INDEX_FILE": "/somewhere/.git/index",
        "GIT_AUTHOR_NAME": "someone else",
        "GITHUB_TOKEN": "kept — it is not a GIT_ variable",
    }
    assert gitcmd.clean_env(polluted) == {
        "PATH": "/usr/bin",
        "GITHUB_TOKEN": "kept — it is not a GIT_ variable",
    }


def test_clean_env_keeps_what_describes_the_installation_not_the_repository():
    kept = {"GIT_EXEC_PATH": "/usr/lib/git-core", "GIT_SSH_COMMAND": "ssh -i key"}
    assert gitcmd.clean_env(kept) == kept


def test_init_creates_the_repository_the_path_names_under_an_ambient_git_dir(
    tmp_path, monkeypatch
):
    """`git init <path>` with GIT_DIR set reinitialises GIT_DIR and leaves <path> with no
    repository at all — it does not even fail. This is the first step of the failure: every
    later command in the same fixture then ran against the invoking repository."""
    elsewhere = tmp_path / "elsewhere"
    gitcmd.run(["init", "-q", "-b", "main", str(elsewhere)], check=True, capture_output=True)
    monkeypatch.setenv("GIT_DIR", str(elsewhere / ".git"))

    target = tmp_path / "target"
    target.mkdir()
    gitcmd.run(["init", "-q", "-b", "main", str(target)], check=True, capture_output=True)

    assert (target / ".git").is_dir()


def test_a_commit_lands_in_the_named_repository_under_an_ambient_git_dir(
    tmp_path, monkeypatch
):
    """The end state the pre-push hook actually hit: `git -C <path> add -A` staged the
    named directory's files into the *invoking* repository's index, and the commit ran the
    invoking repository's hooks."""
    elsewhere = tmp_path / "elsewhere"
    gitcmd.run(["init", "-q", "-b", "main", str(elsewhere)], check=True, capture_output=True)
    monkeypatch.setenv("GIT_DIR", str(elsewhere / ".git"))

    target = tmp_path / "target"
    target.mkdir()
    (target / "a.txt").write_text("hello\n")
    gitcmd.run(["init", "-q", "-b", "main", str(target)], check=True, capture_output=True)
    gitcmd.run(["-C", str(target), "config", "user.email", "t@t"], check=True)
    gitcmd.run(["-C", str(target), "config", "user.name", "T"], check=True)
    gitcmd.run(["-C", str(target), "add", "-A"], check=True, capture_output=True)
    gitcmd.run(["-C", str(target), "commit", "-m", "init"], check=True, capture_output=True)

    listed = gitcmd.run(
        ["-C", str(target), "ls-tree", "--name-only", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    assert listed.stdout.split() == ["a.txt"]
    # The repository GIT_DIR pointed at was never touched.
    with pytest.raises(subprocess.CalledProcessError):
        gitcmd.run(
            ["-C", str(elsewhere), "rev-parse", "HEAD"], check=True, capture_output=True
        )
