import subprocess
from pathlib import Path
from algoforge.worktree import (
    create_worktree,
    remove_worktree,
    list_worktrees,
    create_branch,
)


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def test_create_and_list_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    wt_path = tmp_path / "worktrees" / "r1"
    create_branch(repo, "module/mod_a")
    create_worktree(repo, wt_path, "module/mod_a")

    assert wt_path.exists()
    assert (wt_path / "README.md").exists()

    worktrees = list_worktrees(repo)
    assert any("r1" in str(wt) for wt in worktrees)


def test_remove_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    wt_path = tmp_path / "worktrees" / "r1"
    create_branch(repo, "module/mod_a")
    create_worktree(repo, wt_path, "module/mod_a")
    remove_worktree(repo, wt_path)

    assert not wt_path.exists()


def test_create_branch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    create_branch(repo, "module/test_branch")
    result = subprocess.run(
        ["git", "branch", "--list", "module/test_branch"],
        cwd=repo, capture_output=True, text=True,
    )
    assert "module/test_branch" in result.stdout
