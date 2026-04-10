import subprocess
import time
from pathlib import Path
from algoforge.config import load_config
from algoforge.orchestrator import (
    init_project,
    check_stopping_conditions,
    build_session_command,
)
from algoforge.state import init_state_dir, append_result


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def test_init_project(tmp_project):
    tmp_path, config_path = tmp_project
    _init_git_repo(tmp_path)
    config = load_config(config_path)
    init_project(tmp_path, config)

    assert (tmp_path / "state").is_dir()
    assert (tmp_path / "state" / "results.tsv").exists()
    assert (tmp_path / "state" / "assignments").is_dir()


def test_check_stopping_max_iterations(tmp_project):
    tmp_path, config_path = tmp_project
    config = load_config(config_path)
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)

    for i in range(100):
        append_result(state_dir, {
            "researcher": "r1", "module": "mod_a", "commit": f"abc{i:04d}",
            "metric_avg": 0.01, "metric_best": 0.008,
            "status": "discard", "hypothesis": "test", "description": "test",
        })

    triggered, reason = check_stopping_conditions(state_dir, config, start_time=0)
    assert triggered
    assert "iterations" in reason.lower()


def test_check_stopping_not_triggered(tmp_project):
    tmp_path, config_path = tmp_project
    config = load_config(config_path)
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)

    triggered, reason = check_stopping_conditions(state_dir, config, start_time=time.time())
    assert not triggered


def test_build_session_command():
    cmd = build_session_command(
        tool="claude",
        model_flags="--model sonnet",
        prompt_path="/project/prompts/researcher.md",
        working_dir="/project/.worktrees/r1",
        researcher_id="r1",
    )
    assert "claude" in cmd[0]
    assert "--model" in cmd
    assert "sonnet" in cmd
