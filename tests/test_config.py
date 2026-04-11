import pytest
from pathlib import Path
from mengerflock.config import load_config, ConfigError

def _write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p

MINIMAL_CONFIG = """\
project:
  name: test-project
  seed_path: ./seed/
  language: python

modules:
  - name: core
    files: [src/core.py]
    description: Core logic

build:
  command: "true"
  binary: "python solver.py"

benchmarks:
  small: ["datasets/holdout/small_*.txt"]

evaluation:
  metric: gap_to_optimal

agents:
  tool: claude
  strategist:
    model_flags: "--model opus"
  researchers:
    model_flags: "--model sonnet"

stopping_conditions:
  max_total_iterations: 100
"""

def test_load_minimal_config(tmp_path):
    cfg = load_config(_write_config(tmp_path, MINIMAL_CONFIG))
    assert cfg.project.name == "test-project"
    assert cfg.project.seed_path == "./seed/"
    assert cfg.project.paper is None

def test_mode_field_ignored(tmp_path):
    with_mode = MINIMAL_CONFIG.replace("  language: python", "  mode: evolve\n  language: python")
    cfg = load_config(_write_config(tmp_path, with_mode))
    assert not hasattr(cfg.project, 'mode')

def test_paper_field_loaded(tmp_path):
    with_paper = MINIMAL_CONFIG.replace(
        "  language: python",
        "  language: python\n  paper: https://example.com/paper.pdf"
    )
    cfg = load_config(_write_config(tmp_path, with_paper))
    assert cfg.project.paper == "https://example.com/paper.pdf"

def test_seed_path_required(tmp_path):
    no_seed = MINIMAL_CONFIG.replace("  seed_path: ./seed/\n", "")
    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, no_seed))

def test_max_reentries_default(tmp_path):
    cfg = load_config(_write_config(tmp_path, MINIMAL_CONFIG))
    assert cfg.stopping_conditions.max_reentries == 2

def test_max_reentries_custom(tmp_path):
    custom = MINIMAL_CONFIG.replace(
        "  max_total_iterations: 100",
        "  max_total_iterations: 100\n  max_reentries: 5"
    )
    cfg = load_config(_write_config(tmp_path, custom))
    assert cfg.stopping_conditions.max_reentries == 5
