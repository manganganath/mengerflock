"""Configuration loading and validation for AlgoForge."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when the configuration is invalid or missing required fields."""


def _require(raw: dict[str, Any], key: str, context: str) -> Any:
    """Return raw[key], raising ConfigError if the key is absent."""
    if key not in raw:
        raise ConfigError(f"Missing required field '{key}' in {context}")
    return raw[key]


@dataclasses.dataclass
class ProjectConfig:
    name: str
    mode: str  # "evolve" or "generate"
    seed_path: str | None = None
    problem_spec: str | None = None


@dataclasses.dataclass
class ModuleConfig:
    entry_point: str
    name: str = ""


@dataclasses.dataclass
class BuildConfig:
    command: str
    timeout: int


@dataclasses.dataclass
class BenchmarkConfig:
    command: str
    timeout: int


@dataclasses.dataclass
class EvaluationConfig:
    metric: str
    direction: str  # "maximize" or "minimize"


@dataclasses.dataclass
class StrategistConfig:
    model: str
    model_flags: str = ""


@dataclasses.dataclass
class ResearcherConfig:
    model: str
    count: int
    model_flags: str = ""


@dataclasses.dataclass
class AgentsConfig:
    strategist: StrategistConfig
    researcher: ResearcherConfig
    tool: str = "claude"

    @property
    def researchers(self) -> "ResearcherConfig":
        """Alias for researcher (plural form used by orchestrator)."""
        return self.researcher


@dataclasses.dataclass
class TimeoutsConfig:
    iteration: int
    total: int


@dataclasses.dataclass
class StoppingConditions:
    max_iterations: int
    target_score: float | None = None
    max_hours: float = 24.0
    target_improvement: float = 0.0
    stagnation_window: int = 20

    @property
    def max_total_iterations(self) -> int:
        """Alias for max_iterations (used by orchestrator)."""
        return self.max_iterations


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
    """Load and validate an AlgoForge config YAML file.

    Args:
        path: Path to the config.yaml file.

    Returns:
        A fully validated AlgoForgeConfig dataclass.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ConfigError: If a required field is missing or a value is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    # ── project ──────────────────────────────────────────────────────────────
    raw_project = _require(raw, "project", "root")
    name = _require(raw_project, "name", "project")
    mode = _require(raw_project, "mode", "project")

    if mode not in ("evolve", "generate"):
        raise ConfigError(
            f"project.mode must be 'evolve' or 'generate', got '{mode}'"
        )

    seed_path = raw_project.get("seed_path")
    problem_spec = raw_project.get("problem_spec")

    if mode == "generate" and not problem_spec:
        raise ConfigError(
            "project.problem_spec is required when mode is 'generate'"
        )

    project = ProjectConfig(
        name=name,
        mode=mode,
        seed_path=seed_path,
        problem_spec=problem_spec,
    )

    # ── modules ───────────────────────────────────────────────────────────────
    raw_modules = _require(raw, "modules", "root")
    if isinstance(raw_modules, list):
        # New list-of-modules format: [{name: mod_a, entry_point: ...}, ...]
        modules = [
            ModuleConfig(
                entry_point=_require(m, "entry_point", f"modules[{i}]"),
                name=m.get("name", f"module_{i}"),
            )
            for i, m in enumerate(raw_modules)
        ]
    else:
        # Legacy single-module format: {entry_point: ...}
        entry_point = _require(raw_modules, "entry_point", "modules")
        module_name = raw_modules.get("name", "default")
        modules = [ModuleConfig(entry_point=entry_point, name=module_name)]

    # ── build ─────────────────────────────────────────────────────────────────
    raw_build = _require(raw, "build", "root")
    build = BuildConfig(
        command=_require(raw_build, "command", "build"),
        timeout=_require(raw_build, "timeout", "build"),
    )

    # ── benchmarks ────────────────────────────────────────────────────────────
    raw_bench = _require(raw, "benchmarks", "root")
    benchmarks = BenchmarkConfig(
        command=_require(raw_bench, "command", "benchmarks"),
        timeout=_require(raw_bench, "timeout", "benchmarks"),
    )

    # ── evaluation ────────────────────────────────────────────────────────────
    raw_eval = _require(raw, "evaluation", "root")
    evaluation = EvaluationConfig(
        metric=_require(raw_eval, "metric", "evaluation"),
        direction=_require(raw_eval, "direction", "evaluation"),
    )

    # ── agents ────────────────────────────────────────────────────────────────
    raw_agents = _require(raw, "agents", "root")

    raw_strategist = _require(raw_agents, "strategist", "agents")
    strategist = StrategistConfig(
        model=_require(raw_strategist, "model", "agents.strategist"),
        model_flags=raw_strategist.get("model_flags", ""),
    )

    raw_researcher = _require(raw_agents, "researcher", "agents")
    researcher_count = _require(raw_researcher, "count", "agents.researcher")
    if researcher_count < 1:
        raise ConfigError(
            f"agents.researcher.count must be >= 1, got {researcher_count}"
        )
    researcher = ResearcherConfig(
        model=_require(raw_researcher, "model", "agents.researcher"),
        count=researcher_count,
        model_flags=raw_researcher.get("model_flags", ""),
    )

    agents = AgentsConfig(
        strategist=strategist,
        researcher=researcher,
        tool=raw_agents.get("tool", "claude"),
    )

    # ── timeouts ──────────────────────────────────────────────────────────────
    raw_timeouts = _require(raw, "timeouts", "root")
    timeouts = TimeoutsConfig(
        iteration=_require(raw_timeouts, "iteration", "timeouts"),
        total=_require(raw_timeouts, "total", "timeouts"),
    )

    # ── stopping_conditions ───────────────────────────────────────────────────
    raw_stop = _require(raw, "stopping_conditions", "root")
    stopping_conditions = StoppingConditions(
        max_iterations=_require(raw_stop, "max_iterations", "stopping_conditions"),
        target_score=raw_stop.get("target_score"),
        max_hours=float(raw_stop.get("max_hours", 24.0)),
        target_improvement=float(raw_stop.get("target_improvement", 0.0)),
        stagnation_window=int(raw_stop.get("stagnation_window", 20)),
    )

    return AlgoForgeConfig(
        project=project,
        modules=modules,
        build=build,
        benchmarks=benchmarks,
        evaluation=evaluation,
        agents=agents,
        timeouts=timeouts,
        stopping_conditions=stopping_conditions,
    )
