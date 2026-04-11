import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mengerflock.config import load_config
from mengerflock.orchestrator import (
    init_project,
    is_seed_url,
    check_stopping_conditions,
)
from mengerflock.state import init_state_dir, append_result


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


# --- is_seed_url tests ---

def test_is_seed_url_https():
    assert is_seed_url("https://github.com/user/repo.git")


def test_is_seed_url_http():
    assert is_seed_url("http://github.com/user/repo.git")


def test_is_seed_url_git():
    assert is_seed_url("git@github.com:user/repo.git")


def test_is_seed_url_local():
    assert not is_seed_url("./seed/")
    assert not is_seed_url("/home/user/seed")


# --- init_project tests ---

def test_init_project_creates_state(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""\
project:
  name: test
  seed_path: ./seed/
  language: python
modules:
  - name: core
    files: [core.py]
    description: Core
build:
  command: "true"
  binary: "python solver.py"
benchmarks:
  small: ["*.txt"]
evaluation:
  metric: bins_used
agents:
  tool: claude
  strategist:
    model_flags: ""
  researchers:
    model_flags: ""
""")
    (tmp_path / "seed").mkdir()
    cfg = load_config(config_path)
    with patch("mengerflock.orchestrator.create_branch"):
        init_project(tmp_path, cfg)
    assert (tmp_path / "state").is_dir()
    assert (tmp_path / "state" / "interrupts").is_dir()


def test_init_project(tmp_project):
    tmp_path, config_path = tmp_project
    _init_git_repo(tmp_path)
    config = load_config(config_path)
    init_project(tmp_path, config)

    assert (tmp_path / "state").is_dir()
    assert (tmp_path / "state" / "results.tsv").exists()
    assert (tmp_path / "state" / "assignments").is_dir()


# --- check_stopping_conditions tests ---

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
