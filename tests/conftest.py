"""Shared pytest fixtures for AlgoForge tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


MINIMAL_CONFIG: dict = {
    "project": {
        "name": "test-project",
        "mode": "evolve",
        "seed_path": "seeds/",
    },
    "modules": {
        "entry_point": "algorithm.py",
    },
    "build": {
        "command": "python build.py",
        "timeout": 60,
    },
    "benchmarks": {
        "command": "python benchmark.py",
        "timeout": 120,
    },
    "evaluation": {
        "metric": "score",
        "direction": "maximize",
    },
    "agents": {
        "strategist": {
            "model": "gpt-4o",
        },
        "researcher": {
            "model": "gpt-4o-mini",
            "count": 2,
        },
    },
    "timeouts": {
        "iteration": 300,
        "total": 3600,
    },
    "stopping_conditions": {
        "max_iterations": 50,
        "target_score": None,
    },
}


@pytest.fixture
def tmp_project(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal project directory with a valid config.yaml and seed dir.

    Returns a (project_dir, config_path) tuple so both orchestrator tests
    and config tests can destructure what they need.
    """
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(MINIMAL_CONFIG))

    return tmp_path, config_path
