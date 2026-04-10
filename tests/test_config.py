"""Tests for algoforge.config module."""

import pytest
import yaml
from pathlib import Path
from algoforge.config import load_config, ConfigError


def test_load_valid_config(tmp_project):
    tmp_path, config_path = tmp_project
    config = load_config(config_path)
    assert config.project.name == "test-project"
    assert config.project.mode == "evolve"
    assert config.agents.researchers.count == 2
    assert len(config.modules) == 1


def test_load_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_load_missing_required_field(tmp_path):
    bad_config = {"project": {"name": "test"}}
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(yaml.dump(bad_config))
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_mode_must_be_evolve_or_generate(tmp_project):
    tmp_path, config_path = tmp_project
    raw = yaml.safe_load(config_path.read_text())
    raw["project"]["mode"] = "invalid"
    config_path.write_text(yaml.dump(raw))
    with pytest.raises(ConfigError, match="mode"):
        load_config(config_path)


def test_researcher_count_must_be_positive(tmp_project):
    tmp_path, config_path = tmp_project
    raw = yaml.safe_load(config_path.read_text())
    raw["agents"]["researchers"]["count"] = 0
    config_path.write_text(yaml.dump(raw))
    with pytest.raises(ConfigError, match="count"):
        load_config(config_path)


def test_researcher_count_defaults_to_none(tmp_project):
    tmp_path, config_path = tmp_project
    raw = yaml.safe_load(config_path.read_text())
    del raw["agents"]["researchers"]["count"]
    config_path.write_text(yaml.dump(raw))
    config = load_config(config_path)
    assert config.agents.researchers.count is None


def test_seed_path_optional_in_evolve(tmp_project):
    tmp_path, config_path = tmp_project
    raw = yaml.safe_load(config_path.read_text())
    del raw["project"]["seed_path"]
    config_path.write_text(yaml.dump(raw))
    config = load_config(config_path)
    assert config.project.seed_path is None


def test_generate_mode_requires_problem_spec(tmp_project):
    tmp_path, config_path = tmp_project
    raw = yaml.safe_load(config_path.read_text())
    raw["project"]["mode"] = "generate"
    config_path.write_text(yaml.dump(raw))
    with pytest.raises(ConfigError, match="problem_spec"):
        load_config(config_path)
