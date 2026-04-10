# AlgoForge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build AlgoForge — a thin Python orchestrator that coordinates multiple coding agent sessions (Claude Code, Codex) to autonomously discover and evolve algorithms.

**Architecture:** The orchestrator launches coding agent sessions as subprocesses, each in its own git worktree, pointed at a markdown instruction file. Communication between agents happens via the filesystem (`state/` directory). The orchestrator monitors progress, enforces stopping conditions, and handles graceful shutdown.

**Tech Stack:** Python 3.11+, PyYAML, Click (CLI), pytest. No LLM libraries — the coding agent tool handles all LLM interaction.

**Spec:** `docs/superpowers/specs/2026-04-10-algoforge-design.md`

---

## File Structure

```
algoforge/
├── pyproject.toml              # project metadata, dependencies, CLI entry point
├── src/
│   └── algoforge/
│       ├── __init__.py         # version
│       ├── cli.py              # Click CLI (init, run, status, stop, report)
│       ├── config.py           # load + validate config.yaml
│       ├── state.py            # read/write results.tsv, strategist_log.tsv, assignments
│       ├── worktree.py         # git worktree create/destroy/list
│       ├── orchestrator.py     # launch sessions, monitor, shutdown
│       └── eval.sh             # benchmark runner script template
├── prompts/
│   ├── strategist.md           # strategist agent instructions
│   └── researcher.md           # researcher agent instructions
├── tests/
│   ├── conftest.py             # shared fixtures (tmp git repos, sample configs)
│   ├── test_config.py
│   ├── test_state.py
│   ├── test_worktree.py
│   └── test_orchestrator.py
└── examples/
    └── tsp/
        └── config.yaml         # TSP test case config template
```

---

## Chunk 1: Project Scaffolding and Config

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/algoforge/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "algoforge"
version = "0.1.0"
description = "Hierarchical multi-agent system for automated algorithm discovery"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
algoforge = "algoforge.cli:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create __init__.py**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Install in dev mode and verify**

Run: `cd /Users/nuwan.ganganath.m.a/Projects/nuwan_tsp && pip install -e ".[dev]"`
Expected: installs successfully

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/algoforge/__init__.py
git commit -m "feat: project scaffolding with pyproject.toml"
```

---

### Task 2: Config loading and validation

**Files:**
- Create: `tests/test_config.py`
- Create: `src/algoforge/config.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create conftest.py with shared fixtures**

```python
import os
import tempfile
import pytest
import yaml


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project directory for testing."""
    config = {
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
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    # Create seed directory
    (tmp_path / "seed").mkdir()
    (tmp_path / "seed" / "src").mkdir(parents=True)
    (tmp_path / "seed" / "src" / "a.c").write_text("int main() { return 0; }")

    return tmp_path, config_path
```

- [ ] **Step 2: Write failing tests for config loading**

```python
# tests/test_config.py
import pytest
import yaml
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/nuwan.ganganath.m.a/Projects/nuwan_tsp && pytest tests/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement config.py**

```python
# src/algoforge/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class ConfigError(Exception):
    pass


@dataclass
class ProjectConfig:
    name: str
    mode: str
    language: str
    seed_path: Optional[str] = None
    problem_spec: Optional[str] = None
    reference_materials: Optional[list[str]] = None


@dataclass
class ModuleConfig:
    name: str
    files: list[str]
    description: str


@dataclass
class BuildConfig:
    command: str
    binary: str


@dataclass
class BenchmarkConfig:
    small: list[str]
    medium: list[str] = field(default_factory=list)
    large: list[str] = field(default_factory=list)
    baseline_results: Optional[str] = None


@dataclass
class EvaluationConfig:
    metric: str
    progressive: bool = True
    runs_per_instance: int = 5
    random_seeds: list[int] = field(default_factory=lambda: [42, 123, 456, 789, 1024])


@dataclass
class StrategistConfig:
    model_flags: str = ""


@dataclass
class ResearcherConfig:
    count: int
    model_flags: str = ""
    max_iterations_per_assignment: int = 20


@dataclass
class AgentsConfig:
    tool: str
    strategist: StrategistConfig
    researchers: ResearcherConfig


@dataclass
class TimeoutsConfig:
    build: int = 30
    eval_per_instance: int = 30


@dataclass
class StoppingConditions:
    max_total_iterations: int = 500
    max_hours: float = 24
    target_improvement: float = 0.5
    stagnation_window: int = 50


@dataclass
class AlgoForgeConfig:
    project: ProjectConfig
    modules: list[ModuleConfig]
    build: BuildConfig
    benchmarks: BenchmarkConfig
    evaluation: EvaluationConfig
    agents: AgentsConfig
    timeouts: TimeoutsConfig
    stopping_conditions: StoppingConditions


def _require(raw: dict, key: str, context: str = "") -> any:
    if key not in raw:
        ctx = f" in {context}" if context else ""
        raise ConfigError(f"Missing required field '{key}'{ctx}")
    return raw[key]


def load_config(path: str | Path) -> AlgoForgeConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigError("Config must be a YAML mapping")

    # Project
    proj_raw = _require(raw, "project")
    mode = _require(proj_raw, "mode", "project")
    if mode not in ("evolve", "generate"):
        raise ConfigError(f"project.mode must be 'evolve' or 'generate', got '{mode}'")

    project = ProjectConfig(
        name=_require(proj_raw, "name", "project"),
        mode=mode,
        language=_require(proj_raw, "language", "project"),
        seed_path=proj_raw.get("seed_path"),
        problem_spec=proj_raw.get("problem_spec"),
        reference_materials=proj_raw.get("reference_materials"),
    )

    if mode == "generate" and not project.problem_spec:
        raise ConfigError("project.problem_spec is required in generate mode")

    # Modules
    modules_raw = _require(raw, "modules")
    modules = [
        ModuleConfig(
            name=_require(m, "name", "modules[]"),
            files=_require(m, "files", "modules[]"),
            description=_require(m, "description", "modules[]"),
        )
        for m in modules_raw
    ]

    # Build
    build_raw = _require(raw, "build")
    build = BuildConfig(
        command=_require(build_raw, "command", "build"),
        binary=_require(build_raw, "binary", "build"),
    )

    # Benchmarks
    bench_raw = _require(raw, "benchmarks")
    benchmarks = BenchmarkConfig(
        small=_require(bench_raw, "small", "benchmarks"),
        medium=bench_raw.get("medium", []),
        large=bench_raw.get("large", []),
        baseline_results=bench_raw.get("baseline_results"),
    )

    # Evaluation
    eval_raw = _require(raw, "evaluation")
    evaluation = EvaluationConfig(
        metric=_require(eval_raw, "metric", "evaluation"),
        progressive=eval_raw.get("progressive", True),
        runs_per_instance=eval_raw.get("runs_per_instance", 5),
        random_seeds=eval_raw.get("random_seeds", [42, 123, 456, 789, 1024]),
    )

    # Agents
    agents_raw = _require(raw, "agents")
    strat_raw = _require(agents_raw, "strategist", "agents")
    res_raw = _require(agents_raw, "researchers", "agents")
    count = _require(res_raw, "count", "agents.researchers")
    if count < 1:
        raise ConfigError("agents.researchers.count must be >= 1")

    agents = AgentsConfig(
        tool=_require(agents_raw, "tool", "agents"),
        strategist=StrategistConfig(model_flags=strat_raw.get("model_flags", "")),
        researchers=ResearcherConfig(
            count=count,
            model_flags=res_raw.get("model_flags", ""),
            max_iterations_per_assignment=res_raw.get("max_iterations_per_assignment", 20),
        ),
    )

    # Timeouts
    timeouts_raw = raw.get("timeouts", {})
    timeouts = TimeoutsConfig(
        build=timeouts_raw.get("build", 30),
        eval_per_instance=timeouts_raw.get("eval_per_instance", 30),
    )

    # Stopping conditions
    stop_raw = raw.get("stopping_conditions", {})
    stopping = StoppingConditions(
        max_total_iterations=stop_raw.get("max_total_iterations", 500),
        max_hours=stop_raw.get("max_hours", 24),
        target_improvement=stop_raw.get("target_improvement", 0.5),
        stagnation_window=stop_raw.get("stagnation_window", 50),
    )

    return AlgoForgeConfig(
        project=project,
        modules=modules,
        build=build,
        benchmarks=benchmarks,
        evaluation=evaluation,
        agents=agents,
        timeouts=timeouts,
        stopping_conditions=stopping,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: all 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/algoforge/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: config loading and validation"
```

---

## Chunk 2: State Management

### Task 3: State file operations (results.tsv, strategist_log.tsv, assignments)

**Files:**
- Create: `tests/test_state.py`
- Create: `src/algoforge/state.py`

- [ ] **Step 1: Write failing tests for state operations**

```python
# tests/test_state.py
import time
from pathlib import Path
from algoforge.state import (
    init_state_dir,
    append_result,
    read_results,
    append_strategist_log,
    read_strategist_log,
    write_assignment,
    read_assignment,
    write_shutdown_flag,
    is_shutdown_requested,
)


def test_init_state_dir(tmp_path):
    init_state_dir(tmp_path / "state")
    state_dir = tmp_path / "state"
    assert state_dir.exists()
    assert (state_dir / "results.tsv").exists()
    assert (state_dir / "strategist_log.tsv").exists()
    assert (state_dir / "assignments").is_dir()


def test_append_and_read_results(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    append_result(state_dir, {
        "researcher": "r1",
        "module": "mod_a",
        "commit": "abc1234",
        "metric_avg": 0.0012,
        "metric_best": 0.0008,
        "status": "keep",
        "hypothesis": "test hypothesis",
        "description": "test change",
    })
    results = read_results(state_dir)
    assert len(results) == 1
    assert results[0]["researcher"] == "r1"
    assert results[0]["status"] == "keep"
    assert float(results[0]["metric_avg"]) == 0.0012


def test_append_and_read_strategist_log(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    append_strategist_log(state_dir, "init", "Decomposed into 3 modules")
    log = read_strategist_log(state_dir)
    assert len(log) == 1
    assert log[0]["action"] == "init"


def test_write_and_read_assignment(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    assignment = {
        "module_name": "move_operators",
        "files": ["SRC/Best2OptMove.c"],
        "objective": "Improve k-opt move selection",
        "constraints": ["Do not change function signatures"],
        "context": "Previous attempts focused on sorting",
    }
    write_assignment(state_dir, "r1", assignment)
    loaded = read_assignment(state_dir, "r1")
    assert loaded["module_name"] == "move_operators"
    assert loaded["files"] == ["SRC/Best2OptMove.c"]


def test_shutdown_flag(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    assert not is_shutdown_requested(state_dir)
    write_shutdown_flag(state_dir)
    assert is_shutdown_requested(state_dir)


def test_read_results_empty(tmp_path):
    state_dir = tmp_path / "state"
    init_state_dir(state_dir)
    results = read_results(state_dir)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement state.py**

```python
# src/algoforge/state.py
from __future__ import annotations

import csv
import fcntl
from datetime import datetime, timezone
from pathlib import Path

import yaml

RESULTS_HEADER = [
    "timestamp", "researcher", "module", "commit",
    "metric_avg", "metric_best", "status", "hypothesis", "description",
]

STRATEGIST_LOG_HEADER = ["timestamp", "action", "details"]


def init_state_dir(state_dir: str | Path) -> None:
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "assignments").mkdir(exist_ok=True)

    results_path = state_dir / "results.tsv"
    if not results_path.exists():
        results_path.write_text("\t".join(RESULTS_HEADER) + "\n")

    log_path = state_dir / "strategist_log.tsv"
    if not log_path.exists():
        log_path.write_text("\t".join(STRATEGIST_LOG_HEADER) + "\n")


def _append_tsv(path: Path, row: list[str]) -> None:
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write("\t".join(str(v) for v in row) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def append_result(state_dir: str | Path, result: dict) -> None:
    state_dir = Path(state_dir)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    row = [
        ts,
        result["researcher"],
        result["module"],
        result["commit"],
        result["metric_avg"],
        result["metric_best"],
        result["status"],
        result["hypothesis"],
        result["description"],
    ]
    _append_tsv(state_dir / "results.tsv", row)


def read_results(state_dir: str | Path) -> list[dict]:
    return _read_tsv(Path(state_dir) / "results.tsv")


def append_strategist_log(state_dir: str | Path, action: str, details: str) -> None:
    state_dir = Path(state_dir)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    _append_tsv(state_dir / "strategist_log.tsv", [ts, action, details])


def read_strategist_log(state_dir: str | Path) -> list[dict]:
    return _read_tsv(Path(state_dir) / "strategist_log.tsv")


def write_assignment(state_dir: str | Path, researcher_id: str, assignment: dict) -> None:
    path = Path(state_dir) / "assignments" / f"{researcher_id}.yaml"
    path.write_text(yaml.dump(assignment, default_flow_style=False))


def read_assignment(state_dir: str | Path, researcher_id: str) -> dict:
    path = Path(state_dir) / "assignments" / f"{researcher_id}.yaml"
    return yaml.safe_load(path.read_text())


def write_shutdown_flag(state_dir: str | Path) -> None:
    (Path(state_dir) / "shutdown").touch()


def is_shutdown_requested(state_dir: str | Path) -> bool:
    return (Path(state_dir) / "shutdown").exists()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/algoforge/state.py tests/test_state.py
git commit -m "feat: state management for results, logs, assignments, and shutdown"
```

---

## Chunk 3: Git Worktree Management

### Task 4: Git worktree operations

**Files:**
- Create: `tests/test_worktree.py`
- Create: `src/algoforge/worktree.py`

- [ ] **Step 1: Write failing tests for worktree operations**

```python
# tests/test_worktree.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worktree.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement worktree.py**

```python
# src/algoforge/worktree.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_worktree.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/algoforge/worktree.py tests/test_worktree.py
git commit -m "feat: git worktree create, remove, list operations"
```

---

## Chunk 4: Orchestrator

### Task 5: Orchestrator core — session launching, monitoring, and shutdown

**Files:**
- Create: `tests/test_orchestrator.py`
- Create: `src/algoforge/orchestrator.py`

- [ ] **Step 1: Write failing tests for orchestrator**

Note: The orchestrator launches real coding agent sessions as subprocesses. For unit testing, we test the logic around session management (init, monitoring, shutdown) using mock subprocesses. Integration testing with real agents is done manually.

```python
# tests/test_orchestrator.py
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
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

    # Add 100 results (matches max_total_iterations in test config)
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

    import time
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement orchestrator.py**

```python
# src/algoforge/orchestrator.py
from __future__ import annotations

import shlex
import signal
import subprocess
import time
from pathlib import Path

from algoforge.config import AlgoForgeConfig
from algoforge.state import (
    init_state_dir,
    read_results,
    write_shutdown_flag,
    is_shutdown_requested,
)
from algoforge.worktree import create_branch, create_worktree, remove_worktree


def init_project(project_dir: Path, config: AlgoForgeConfig) -> None:
    state_dir = project_dir / "state"
    init_state_dir(state_dir)

    # Create module branches
    for module in config.modules:
        create_branch(project_dir, f"module/{module.name}")


def check_stopping_conditions(
    state_dir: Path,
    config: AlgoForgeConfig,
    start_time: float,
) -> tuple[bool, str]:
    sc = config.stopping_conditions
    results = read_results(state_dir)

    # Max iterations
    if len(results) >= sc.max_total_iterations:
        return True, f"Max iterations reached ({sc.max_total_iterations})"

    # Max hours
    elapsed_hours = (time.time() - start_time) / 3600
    if elapsed_hours >= sc.max_hours:
        return True, f"Max hours reached ({sc.max_hours}h)"

    # Target improvement
    keep_results = [r for r in results if r["status"] == "keep"]
    if keep_results:
        best_avg = min(float(r["metric_avg"]) for r in keep_results)
        if len(results) > 0:
            first_keep = next((r for r in results if r["status"] == "keep"), None)
            if first_keep:
                baseline = float(first_keep["metric_avg"])
                improvement = baseline - best_avg
                if improvement >= sc.target_improvement:
                    return True, f"Target improvement reached ({improvement:.4f} >= {sc.target_improvement})"

    # Stagnation
    if len(results) >= sc.stagnation_window:
        recent = results[-sc.stagnation_window:]
        if not any(r["status"] == "keep" for r in recent):
            return True, f"Stagnation: no improvement in last {sc.stagnation_window} iterations"

    return False, ""


def build_session_command(
    tool: str,
    model_flags: str,
    prompt_path: str,
    working_dir: str,
    researcher_id: str | None = None,
) -> list[str]:
    cmd = [tool]
    if model_flags:
        cmd.extend(shlex.split(model_flags))

    role = "researcher" if researcher_id else "strategist"
    id_part = f" Your researcher ID is {researcher_id}." if researcher_id else ""

    cmd.extend([
        "-p",
        f"Read {prompt_path} and follow its instructions.{id_part}",
        "--allowedTools", "Edit,Read,Write,Bash,Glob,Grep",
    ])

    return cmd


class Orchestrator:
    def __init__(self, project_dir: Path, config: AlgoForgeConfig):
        self.project_dir = project_dir
        self.config = config
        self.state_dir = project_dir / "state"
        self.processes: dict[str, subprocess.Popen] = {}
        self.start_time = time.time()
        self._shutdown = False

    def _handle_signal(self, signum, frame):
        self._shutdown = True
        write_shutdown_flag(self.state_dir)

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def launch_researcher(self, researcher_id: str, module_name: str) -> None:
        wt_path = self.project_dir / ".worktrees" / researcher_id
        branch = f"module/{module_name}"

        # Create worktree if it doesn't exist
        if not wt_path.exists():
            create_worktree(self.project_dir, wt_path, branch)

        prompt_path = str(self.project_dir / "prompts" / "researcher.md")
        cmd = build_session_command(
            tool=self.config.agents.tool,
            model_flags=self.config.agents.researchers.model_flags,
            prompt_path=prompt_path,
            working_dir=str(wt_path),
            researcher_id=researcher_id,
        )

        proc = subprocess.Popen(cmd, cwd=wt_path)
        self.processes[researcher_id] = proc

    def launch_strategist(self) -> None:
        prompt_path = str(self.project_dir / "prompts" / "strategist.md")
        cmd = build_session_command(
            tool=self.config.agents.tool,
            model_flags=self.config.agents.strategist.model_flags,
            prompt_path=prompt_path,
            working_dir=str(self.project_dir),
        )

        proc = subprocess.Popen(cmd, cwd=self.project_dir)
        self.processes["strategist"] = proc

    def monitor(self, poll_interval: float = 30.0) -> None:
        while not self._shutdown:
            # Check stopping conditions
            triggered, reason = check_stopping_conditions(
                self.state_dir, self.config, self.start_time,
            )
            if triggered:
                print(f"Stopping: {reason}")
                self.shutdown()
                return

            # Check if any process died
            for pid, proc in list(self.processes.items()):
                if proc.poll() is not None:
                    print(f"Session {pid} exited with code {proc.returncode}")
                    del self.processes[pid]

            if not self.processes:
                print("All sessions have exited")
                return

            time.sleep(poll_interval)

    def shutdown(self) -> None:
        self._shutdown = True
        write_shutdown_flag(self.state_dir)

        # Wait for processes to finish
        for pid, proc in self.processes.items():
            print(f"Waiting for {pid} to finish...")
            proc.wait(timeout=120)

    def run(self) -> None:
        self.setup_signal_handlers()

        # Launch strategist
        self.launch_strategist()

        # Launch researchers
        for i in range(self.config.agents.researchers.count):
            rid = f"r{i + 1}"
            module = self.config.modules[i % len(self.config.modules)]
            self.launch_researcher(rid, module.name)

        # Monitor
        self.monitor()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_orchestrator.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/algoforge/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator with session launching, monitoring, and shutdown"
```

---

## Chunk 5: CLI and Eval Script

### Task 6: CLI entry point

**Files:**
- Create: `src/algoforge/cli.py`

- [ ] **Step 1: Implement cli.py**

```python
# src/algoforge/cli.py
from __future__ import annotations

from pathlib import Path

import click

from algoforge.config import load_config
from algoforge.orchestrator import Orchestrator, init_project
from algoforge.state import read_results, read_strategist_log, is_shutdown_requested


@click.group()
def main():
    """AlgoForge — automated algorithm discovery through multi-agent evolution."""
    pass


@main.command()
@click.option("--seed", type=click.Path(exists=True), help="Path to seed codebase")
@click.option("--config", "config_path", required=True, type=click.Path(exists=True))
def init(seed: str | None, config_path: str):
    """Initialize a new AlgoForge project."""
    config = load_config(config_path)
    project_dir = Path.cwd()

    if seed:
        config.project.seed_path = seed

    init_project(project_dir, config)
    click.echo(f"Project initialized: {config.project.name}")
    click.echo(f"State directory: {project_dir / 'state'}")


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
def run(config_path: str):
    """Run the AlgoForge experiment."""
    config = load_config(config_path)
    project_dir = Path.cwd()

    # Ensure project is initialized
    if not (project_dir / "state").exists():
        init_project(project_dir, config)

    orchestrator = Orchestrator(project_dir, config)
    click.echo(f"Starting AlgoForge: {config.agents.researchers.count} researchers")
    orchestrator.run()


@main.command()
def status():
    """Show current experiment progress."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project. Run 'algoforge init' first.")
        return

    results = read_results(state_dir)
    keeps = [r for r in results if r["status"] == "keep"]
    discards = [r for r in results if r["status"] == "discard"]
    crashes = [r for r in results if r["status"] == "crash"]

    click.echo(f"Total experiments: {len(results)}")
    click.echo(f"  Keep: {len(keeps)}")
    click.echo(f"  Discard: {len(discards)}")
    click.echo(f"  Crash: {len(crashes)}")

    if keeps:
        best = min(keeps, key=lambda r: float(r["metric_avg"]))
        click.echo(f"Best metric_avg: {best['metric_avg']} ({best['module']}, {best['commit']})")

    if is_shutdown_requested(state_dir):
        click.echo("Status: SHUTTING DOWN")
    else:
        click.echo("Status: RUNNING")


@main.command()
def stop():
    """Gracefully stop the experiment."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project.")
        return

    from algoforge.state import write_shutdown_flag
    write_shutdown_flag(state_dir)
    click.echo("Shutdown signal sent. Sessions will finish current iteration and stop.")


@main.command()
def report():
    """Generate report from experiment results."""
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        click.echo("No active project.")
        return

    results = read_results(state_dir)
    log = read_strategist_log(state_dir)

    click.echo("=" * 60)
    click.echo("AlgoForge Experiment Report")
    click.echo("=" * 60)
    click.echo(f"\nTotal experiments: {len(results)}")
    click.echo(f"Strategist actions: {len(log)}")

    keeps = [r for r in results if r["status"] == "keep"]
    if keeps:
        best = min(keeps, key=lambda r: float(r["metric_avg"]))
        click.echo(f"\nBest result:")
        click.echo(f"  Module: {best['module']}")
        click.echo(f"  Commit: {best['commit']}")
        click.echo(f"  Metric (avg): {best['metric_avg']}")
        click.echo(f"  Hypothesis: {best['hypothesis']}")

    click.echo(f"\nFull results in: state/results.tsv")
    click.echo(f"Strategist log in: state/strategist_log.tsv")
```

- [ ] **Step 2: Verify CLI installs and runs**

Run: `pip install -e ".[dev]" && algoforge --help`
Expected: shows help text with init, run, status, stop, report commands

- [ ] **Step 3: Commit**

```bash
git add src/algoforge/cli.py
git commit -m "feat: CLI with init, run, status, stop, report commands"
```

---

### Task 7: Eval script template

**Files:**
- Create: `src/algoforge/eval.sh`

- [ ] **Step 1: Create eval.sh**

This is a template that gets copied into the project directory. It's deterministic (no LLM) — just runs the binary against benchmark instances and outputs metrics.

```bash
#!/usr/bin/env bash
# AlgoForge benchmark evaluation script
# Usage: ./eval.sh <binary> <instance.tsp> <seed> <timeout>
# Output: tour_length on stdout, or "FAIL" on error

set -euo pipefail

BINARY="$1"
INSTANCE="$2"
SEED="${3:-42}"
TIMEOUT="${4:-30}"

if [ ! -x "$BINARY" ]; then
    echo "FAIL: binary not found or not executable: $BINARY" >&2
    exit 1
fi

if [ ! -f "$INSTANCE" ]; then
    echo "FAIL: instance not found: $INSTANCE" >&2
    exit 1
fi

# Create a temporary parameter file for LKH
PARAM_FILE=$(mktemp /tmp/algoforge_eval_XXXXXX.par)
TOUR_FILE=$(mktemp /tmp/algoforge_eval_XXXXXX.tour)

cat > "$PARAM_FILE" <<EOF
PROBLEM_FILE = $INSTANCE
TOUR_FILE = $TOUR_FILE
SEED = $SEED
RUNS = 1
EOF

# Run with timeout
if timeout "$TIMEOUT" "$BINARY" "$PARAM_FILE" > /dev/null 2>&1; then
    # Extract tour length from tour file
    if [ -f "$TOUR_FILE" ]; then
        # LKH tour format: line with tour length is typically after COMMENT
        TOUR_LENGTH=$(grep -oP '(?<=COMMENT : Length = )\d+' "$TOUR_FILE" || echo "FAIL")
        echo "$TOUR_LENGTH"
    else
        echo "FAIL: no tour file produced" >&2
        exit 1
    fi
else
    echo "FAIL: timeout or crash" >&2
    exit 1
fi

# Cleanup
rm -f "$PARAM_FILE" "$TOUR_FILE"
```

- [ ] **Step 2: Make it executable and commit**

```bash
chmod +x src/algoforge/eval.sh
git add src/algoforge/eval.sh
git commit -m "feat: benchmark evaluation script template"
```

---

## Chunk 6: Agent Prompts

### Task 8: Researcher prompt

**Files:**
- Create: `prompts/researcher.md`

- [ ] **Step 1: Write researcher.md**

This is the equivalent of AutoResearch's `program.md` — the core instruction file that drives researcher behavior.

```markdown
# AlgoForge Researcher Agent

You are an autonomous researcher agent working to improve a specific module of a codebase. Your goal is to make targeted modifications that improve performance on benchmarks.

## Setup

1. Read your assignment file at `state/assignments/<your_id>.yaml`. It contains:
   - `module_name`: the module you're working on
   - `files`: the source files you can modify
   - `objective`: what to improve
   - `constraints`: what NOT to change
   - `context`: notes from the strategist about what's been tried

2. Read the source files listed in your assignment. Understand the code thoroughly.

3. Read `state/results.tsv` to see recent experiment history. Learn from what worked and what didn't.

4. Read `eval.sh` to understand how benchmarks are run.

## The Experiment Loop

LOOP FOREVER:

1. **Hypothesize**: Based on your understanding of the code and past results, form a hypothesis about a specific change that should improve the metric. Write it down as a one-line hypothesis.

2. **Implement**: Edit the source files to implement your hypothesis. Stay within your assigned files. Do NOT change function signatures unless your assignment explicitly allows it.

3. **Commit**: `git add` your changes and `git commit -m "<hypothesis>"`.

4. **Build**: Run the build command from `config.yaml`. Redirect output: `<build_command> > build.log 2>&1`
   - If the build fails, read `build.log`, fix the error, and retry (up to 3 times).
   - If you can't fix it after 3 tries, revert and log as crash.

5. **Evaluate**: Run `eval.sh` against each benchmark instance listed in your assignment. Record the tour lengths.

6. **Compare**:
   - Calculate the geometric mean gap across instances.
   - If **strictly better** than your current best AND no single instance regressed by more than 2x → **keep**.
   - Otherwise → **discard**.

7. **Log**: Append a row to `state/results.tsv`:
   ```
   <timestamp>\t<researcher_id>\t<module>\t<commit_hash>\t<metric_avg>\t<metric_best>\t<keep|discard|crash>\t<hypothesis>\t<description>
   ```
   Use tab separation. Get the timestamp with `date -u +%Y-%m-%dT%H:%M:%S`.

8. **Keep or Revert**:
   - If keep: your branch advances. This is your new baseline.
   - If discard: `git reset --hard HEAD~1`

9. **Check for updates**:
   - Re-read `state/assignments/<your_id>.yaml`. If the module_name changed, the strategist has reassigned you. Start over with the new assignment.
   - Check if `state/shutdown` exists. If so, finish and exit.

10. **Repeat** from step 1.

## Rules

- **NEVER STOP** unless `state/shutdown` exists. You are fully autonomous.
- **NEVER modify files outside your assigned module** unless your constraints explicitly allow it.
- **NEVER ask the human** if you should continue. They may be asleep.
- **If stuck**, re-read the source code for new angles. Try combining ideas from previous near-misses. Try more radical changes. Try simplifications.
- **Build failures count as iterations.** Don't waste all your cycles fighting the compiler.
- **Simpler is better.** If a small improvement adds ugly complexity, it's probably not worth it. If you can delete code and maintain performance, that's a win.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/researcher.md
git commit -m "feat: researcher agent prompt"
```

---

### Task 9: Strategist prompt

**Files:**
- Create: `prompts/strategist.md`

- [ ] **Step 1: Write strategist.md**

```markdown
# AlgoForge Strategist Agent

You are the research PI of an autonomous algorithm discovery system. You coordinate a team of researcher agents who evolve a codebase to improve performance on benchmarks.

## Your Capabilities

You have full access to: file read/edit, bash commands, git, and **web search**. Use web search to research the target domain, find papers, understand algorithms, and discover known weaknesses.

## Setup (Phase 1: Initialization)

1. **Read `config.yaml`** to understand the project: target codebase, modules, benchmarks, evaluation metric.

2. **Research the domain**: Use web search to understand:
   - What is this algorithm/codebase?
   - What are its known strengths and weaknesses?
   - What competing approaches exist?
   - What papers describe improvements?

   Write a summary of your findings to `state/strategist_log.tsv`.

3. **If no seed code** (`seed_path` is empty): Use web search to find the best available open-source implementation. Download it and place it in the project directory.

4. **Analyze the codebase**: Read the source code. Identify:
   - Module boundaries (validate/refine what's in config.yaml)
   - Inter-module dependencies (shared headers, function calls across modules)
   - Key algorithms and data structures
   - Potential improvement areas

5. **Run baseline**: Compile and run benchmarks on the unmodified code. Record results.
   Tag this state: `git tag baseline`

6. **Create initial assignments**: Write `state/assignments/r<id>.yaml` for each researcher with:
   ```yaml
   module_name: <name>
   files: [<list of files>]
   objective: <what to improve and why>
   constraints: [<what not to change>]
   context: <your analysis of this module and what might work>
   ```

## Research Loop (Phase 2)

LOOP FOREVER:

1. **Monitor progress**: Read `state/results.tsv` every 30 seconds. Track:
   - Which researchers are making progress (keep entries)
   - Which are stagnating (many consecutive discards/crashes)
   - Overall improvement trajectory

2. **Compose** when triggered:
   - A researcher reports a new `keep` in results.tsv
   - 10 minutes pass with no composition
   - You're about to reassign a researcher

   To compose:
   - Create a composition branch from main
   - Merge each module's best branch: `git merge module/<name>`
   - If merge conflicts: resolve them yourself. Only if you truly cannot resolve, switch that researcher to cross-pollination mode.
   - Build and evaluate the composed code against ALL benchmark tiers
   - If better than main: `git checkout main && git merge composition/<id> --ff-only` and tag it
   - Log the result to `state/strategist_log.tsv`

3. **Reprioritize**: After each composition, reassess:
   - Which modules have the most improvement potential?
   - Which researchers are stuck? Reassign them.
   - Are there module coupling issues? Adjust boundaries.

   Update `state/assignments/r<id>.yaml` to reassign researchers.

4. **Check for shutdown**: If `state/shutdown` exists, proceed to Report phase.

## Priority Scoring

Rank modules by:
- **Improvement potential**: recent gains = hot area, prioritize
- **Stagnation**: many failures = deprioritize
- **Impact weight**: your domain knowledge about which components matter most
- **Dependency**: if module A improvement unlocks module B, prioritize A

## Cross-Pollination Fallback

Only use when:
- You cannot resolve a merge conflict between modules
- Composed results are worse than individual module improvements (coupling issue)
- All modules are stagnating simultaneously

In cross-pollination mode: the researcher works on `crosspollin/<id>` branch with the full codebase, not a single module.

## Report (Phase 3)

When shutdown is requested:

1. Analyze the full experiment history in `state/results.tsv`
2. Write a comprehensive report to `report/report.md`:
   - Summary of the experiment
   - What domain research revealed
   - What was tried across all modules
   - What worked and why
   - What didn't work and why
   - Final algorithm description
   - Benchmark comparison: baseline vs final
3. Log completion to `state/strategist_log.tsv`

## Rules

- **NEVER STOP** unless `state/shutdown` exists.
- **NEVER ask the human** if you should continue.
- **Shared headers are yours to manage.** If a researcher needs a header change, they note it in results.tsv. You apply it to main and propagate.
- **Function signatures at module boundaries are frozen.** Only you can unfreeze them.
- **Use web search proactively.** When stuck or when a new approach is needed, search for papers and techniques.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/strategist.md
git commit -m "feat: strategist agent prompt"
```

---

## Chunk 7: TSP Test Case and Integration

### Task 10: TSP test case config

**Files:**
- Create: `examples/tsp/config.yaml`

- [ ] **Step 1: Create the TSP example config**

```yaml
project:
  name: "tsp-heuristic"
  mode: "evolve"
  seed_path: "./seeds/lkh2/"
  language: "c"

modules:
  - name: "move_operators"
    files: ["SRC/Best2OptMove.c", "SRC/Best3OptMove.c", "SRC/Best4OptMove.c", "SRC/Best5OptMove.c"]
    description: "k-opt move evaluation and selection — the core improvement operators"
  - name: "candidate_edges"
    files: ["SRC/CreateCandidateSet.c", "SRC/Ascent.c"]
    description: "Alpha-nearness based candidate edge generation using subgradient optimization"
  - name: "perturbation"
    files: ["SRC/LinKernighan.c", "SRC/RecordBestTour.c"]
    description: "Main LK search loop, double-bridge perturbation, and tour recording"

build:
  command: "make -j4"
  binary: "./LKH"

benchmarks:
  small:
    - "benchmarks/tsplib/eil51.tsp"
    - "benchmarks/tsplib/berlin52.tsp"
    - "benchmarks/tsplib/st70.tsp"
    - "benchmarks/tsplib/eil76.tsp"
    - "benchmarks/tsplib/pr76.tsp"
  medium:
    - "benchmarks/tsplib/rat195.tsp"
    - "benchmarks/tsplib/d198.tsp"
    - "benchmarks/tsplib/kroA200.tsp"
    - "benchmarks/tsplib/rat783.tsp"
    - "benchmarks/tsplib/pr1002.tsp"
  large:
    - "benchmarks/tsplib/fl1577.tsp"
    - "benchmarks/tsplib/d2103.tsp"
    - "benchmarks/tsplib/pcb3038.tsp"
  baseline_results: "baselines/lkh2_results.json"

evaluation:
  metric: "gap_to_optimal"
  progressive: true
  runs_per_instance: 5
  random_seeds: [42, 123, 456, 789, 1024]

agents:
  tool: "claude"
  strategist:
    model_flags: "--model opus"
  researchers:
    count: 3
    model_flags: "--model sonnet"
    max_iterations_per_assignment: 20

timeouts:
  build: 30
  eval_per_instance: 60

stopping_conditions:
  max_total_iterations: 500
  max_hours: 12
  target_improvement: 0.5
  stagnation_window: 50
```

- [ ] **Step 2: Commit**

```bash
mkdir -p examples/tsp
git add examples/tsp/config.yaml
git commit -m "feat: TSP test case example config"
```

---

### Task 11: End-to-end dry run test

**Files:**
- None (manual verification)

- [ ] **Step 1: Verify full install and CLI**

```bash
cd /Users/nuwan.ganganath.m.a/Projects/nuwan_tsp
pip install -e ".[dev]"
algoforge --help
algoforge init --help
algoforge run --help
algoforge status --help
algoforge stop --help
algoforge report --help
```

Expected: all commands show help text

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 3: Commit any fixes**

If any fixes were needed, commit them:
```bash
git add -A
git commit -m "fix: address issues found during integration testing"
```

---

## Summary

| Task | What it builds | Files |
|------|---------------|-------|
| 1 | Project scaffolding | `pyproject.toml`, `__init__.py` |
| 2 | Config loading | `config.py`, `test_config.py`, `conftest.py` |
| 3 | State management | `state.py`, `test_state.py` |
| 4 | Git worktrees | `worktree.py`, `test_worktree.py` |
| 5 | Orchestrator | `orchestrator.py`, `test_orchestrator.py` |
| 6 | CLI | `cli.py` |
| 7 | Eval script | `eval.sh` |
| 8 | Researcher prompt | `researcher.md` |
| 9 | Strategist prompt | `strategist.md` |
| 10 | TSP example config | `examples/tsp/config.yaml` |
| 11 | Integration test | manual verification |

Total: ~7 Python files, 2 markdown prompts, 1 shell script, 4 test files. Matches the spec's "thin orchestrator" philosophy.
