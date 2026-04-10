"""Tests for algoforge.config module."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from algoforge.config import AlgoForgeConfig, ConfigError, load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path: Path, data: dict) -> Path:
    """Serialise *data* to config.yaml inside *tmp_path* and return the path."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(data))
    return config_path


def _base_config() -> dict:
    """Return a deep copy of the minimal valid config dict."""
    return {
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
            "strategist": {"model": "gpt-4o"},
            "researcher": {"model": "gpt-4o-mini", "count": 2},
        },
        "timeouts": {
            "iteration": 300,
            "total": 3600,
        },
        "stopping_conditions": {
            "max_iterations": 50,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_valid_config(tmp_project: Path) -> None:
    """A well-formed config.yaml should load without errors."""
    cfg = load_config(tmp_project / "config.yaml")

    assert isinstance(cfg, AlgoForgeConfig)
    assert cfg.project.name == "test-project"
    assert cfg.project.mode == "evolve"
    assert cfg.agents.researcher.count == 2
    assert cfg.stopping_conditions.max_iterations == 50


def test_load_missing_file(tmp_path: Path) -> None:
    """Trying to load a non-existent file must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does_not_exist.yaml")


def test_load_missing_required_field(tmp_path: Path) -> None:
    """A config missing a required top-level section must raise ConfigError."""
    data = _base_config()
    del data["build"]  # Remove a required section

    config_path = _write_config(tmp_path, data)

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_mode_must_be_evolve_or_generate(tmp_path: Path) -> None:
    """An invalid mode value must raise ConfigError mentioning 'mode'."""
    data = _base_config()
    data["project"]["mode"] = "invalid_mode"

    config_path = _write_config(tmp_path, data)

    with pytest.raises(ConfigError, match="mode"):
        load_config(config_path)


def test_researcher_count_must_be_positive(tmp_path: Path) -> None:
    """A researcher count of 0 must raise ConfigError mentioning 'count'."""
    data = _base_config()
    data["agents"]["researcher"]["count"] = 0

    config_path = _write_config(tmp_path, data)

    with pytest.raises(ConfigError, match="count"):
        load_config(config_path)


def test_seed_path_optional_in_evolve(tmp_path: Path) -> None:
    """In 'evolve' mode, seed_path is optional and the config loads fine."""
    data = _base_config()
    data["project"].pop("seed_path", None)  # Remove seed_path

    config_path = _write_config(tmp_path, data)

    cfg = load_config(config_path)
    assert cfg.project.seed_path is None
    assert cfg.project.mode == "evolve"


def test_generate_mode_requires_problem_spec(tmp_path: Path) -> None:
    """'generate' mode without problem_spec must raise ConfigError mentioning 'problem_spec'."""
    data = _base_config()
    data["project"]["mode"] = "generate"
    # Intentionally do NOT set problem_spec

    config_path = _write_config(tmp_path, data)

    with pytest.raises(ConfigError, match="problem_spec"):
        load_config(config_path)
