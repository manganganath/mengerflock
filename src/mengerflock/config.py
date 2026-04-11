"""Configuration loading and validation for AlgoForge."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigError(Exception):
    """Raised when the configuration is invalid or missing required fields."""


def _require(raw: dict[str, Any], key: str, context: str = "") -> Any:
    """Return raw[key], raising ConfigError if the key is absent."""
    if key not in raw:
        ctx = f" in {context}" if context else ""
        raise ConfigError(f"Missing required field '{key}'{ctx}")
    return raw[key]


@dataclasses.dataclass
class ProjectConfig:
    name: str
    mode: str
    language: str
    seed_path: Optional[str] = None
    problem_spec: Optional[str] = None
    reference_materials: Optional[list[str]] = None


@dataclasses.dataclass
class ModuleConfig:
    name: str
    files: list[str]
    description: str


@dataclasses.dataclass
class BuildConfig:
    command: str
    binary: str


@dataclasses.dataclass
class BenchmarkConfig:
    small: list[str]
    medium: list[str] = dataclasses.field(default_factory=list)
    large: list[str] = dataclasses.field(default_factory=list)
    baseline_results: Optional[str] = None


@dataclasses.dataclass
class EvaluationConfig:
    metric: str
    progressive: bool = True
    runs_per_instance: int = 5
    random_seeds: list[int] = dataclasses.field(default_factory=lambda: [42, 123, 456, 789, 1024])


@dataclasses.dataclass
class StrategistConfig:
    model_flags: str = ""


@dataclasses.dataclass
class ResearcherConfig:
    count: Optional[int] = None  # None = strategist decides (default: one per module)
    model_flags: str = ""
    max_iterations_per_assignment: int = 20


@dataclasses.dataclass
class WildcardConfig:
    model_flags: str = ""


@dataclasses.dataclass
class AgentsConfig:
    tool: str
    strategist: StrategistConfig
    researchers: ResearcherConfig
    wildcard: Optional[WildcardConfig] = None


@dataclasses.dataclass
class TimeoutsConfig:
    build: int = 30
    eval_per_instance: int = 30


@dataclasses.dataclass
class StoppingConditions:
    max_total_iterations: int = 500
    max_hours: float = 24
    target_improvement: float = 0.5
    stagnation_window: int = 50


@dataclasses.dataclass
class AlgoForgeConfig:
    project: ProjectConfig
    modules: list[ModuleConfig]
    build: BuildConfig
    benchmarks: BenchmarkConfig
    evaluation: EvaluationConfig
    agents: AgentsConfig
    timeouts: TimeoutsConfig
    stopping_conditions: StoppingConditions


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
        language=proj_raw.get("language", ""),
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
    count = res_raw.get("count")  # None = strategist decides based on modules
    if count is not None and count < 1:
        raise ConfigError("agents.researchers.count must be >= 1")

    # Wildcard (optional)
    wildcard = None
    wildcard_raw = agents_raw.get("wildcard")
    if wildcard_raw:
        wildcard = WildcardConfig(model_flags=wildcard_raw.get("model_flags", ""))

    agents = AgentsConfig(
        tool=_require(agents_raw, "tool", "agents"),
        strategist=StrategistConfig(model_flags=strat_raw.get("model_flags", "")),
        researchers=ResearcherConfig(
            count=count,
            model_flags=res_raw.get("model_flags", ""),
            max_iterations_per_assignment=res_raw.get("max_iterations_per_assignment", 20),
        ),
        wildcard=wildcard,
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
