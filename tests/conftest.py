"""Shared pytest fixtures for AlgoForge tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


MINIMAL_CONFIG: dict = {
    "project": {
        "name": "test-project",
        "mode": "evolve",
        "seed_path": "./seed/",
        "language": "c",
    },
    "modules": [
        {
            "name": "module_a",
            "files": ["src/a.c"],
            "description": "Module A",
        }
    ],
    "build": {
        "command": "make",
        "binary": "./test_bin",
    },
    "benchmarks": {
        "small": ["bench/small1.tsp"],
        "medium": [],
        "large": [],
        "baseline_results": "baselines/results.json",
    },
    "evaluation": {
        "metric": "gap_to_optimal",
        "progressive": True,
        "runs_per_instance": 5,
        "random_seeds": [42, 123, 456, 789, 1024],
    },
    "agents": {
        "tool": "claude",
        "strategist": {"model_flags": "--model opus"},
        "researchers": {
            "count": 2,
            "model_flags": "--model sonnet",
            "max_iterations_per_assignment": 20,
        },
    },
    "timeouts": {
        "build": 30,
        "eval_per_instance": 30,
    },
    "stopping_conditions": {
        "max_total_iterations": 100,
        "max_hours": 1,
        "target_improvement": 0.5,
        "stagnation_window": 20,
    },
}


@pytest.fixture
def tmp_project(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal project directory with a valid config.yaml and seed dir."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(MINIMAL_CONFIG))

    (tmp_path / "seed").mkdir()
    (tmp_path / "seed" / "src").mkdir(parents=True)
    (tmp_path / "seed" / "src" / "a.c").write_text("int main() { return 0; }")

    return tmp_path, config_path
