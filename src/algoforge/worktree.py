from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=check,
    )


def create_branch(repo: Path, branch_name: str) -> None:
    result = _git(repo, "branch", "--list", branch_name)
    if branch_name not in result.stdout:
        _git(repo, "branch", branch_name)


def create_worktree(repo: Path, worktree_path: Path, branch: str) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", str(worktree_path), branch)


def remove_worktree(repo: Path, worktree_path: Path) -> None:
    _git(repo, "worktree", "remove", str(worktree_path), "--force", check=False)
    _git(repo, "worktree", "prune")


def list_worktrees(repo: Path) -> list[str]:
    result = _git(repo, "worktree", "list", "--porcelain")
    worktrees = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            worktrees.append(line[len("worktree "):])
    return worktrees
