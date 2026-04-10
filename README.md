# AlgoForge

Hierarchical multi-agent system for automated algorithm discovery and evolution.

AlgoForge coordinates multiple coding agent sessions — a strategist and N parallel researchers — to evolve codebases toward better performance on defined benchmarks. It uses existing coding agents (Claude Code, Codex, etc.) as the intelligence layer and provides a thin orchestration layer to coordinate them.

## How It Works

```
                    Orchestrator
           (launches sessions, manages state)
                   /          \
          Strategist          Researchers (N)
     (research PI, web       (each in own git worktree,
      search, compose,        evolving assigned module)
      reassign, report)
```

1. The **strategist** analyzes the target codebase, researches the domain via web search, decomposes the code into modules, and assigns work
2. **Researchers** run in parallel, each evolving their assigned module in a tight loop: hypothesize, implement, build, evaluate, keep or revert
3. The **strategist** periodically composes the best modules, evaluates the combined result, and reassigns researchers based on evidence
4. When done, the strategist produces a report documenting what was tried, what worked, and why

## Key Design Decisions

- **Agents are coding tool sessions** pointed at markdown instruction files — not custom LLM infrastructure
- **Git worktrees** provide filesystem isolation for parallel researchers
- **Filesystem-based communication** via a shared `state/` directory (results.tsv, assignments)
- **Domain-agnostic** — works with any codebase in any language
- **The strategist has web search** to autonomously research unfamiliar domains

## Quick Start

```bash
# Initialize a project with seed code
algoforge init --seed ./path/to/seed --config config.yaml

# Run the experiment
algoforge run config.yaml

# Check progress
algoforge status

# Gracefully stop
algoforge stop

# Generate report
algoforge report
```

## Configuration

```yaml
project:
  name: "my-algorithm"
  mode: "evolve"          # evolve (from seed) or generate (from scratch)
  seed_path: "./seed/"
  language: "c"

modules:
  - name: "core_logic"
    files: ["src/core.c"]
    description: "Main algorithm logic"

build:
  command: "make -j4"
  binary: "./solver"

benchmarks:
  small: ["bench/small1.tsp"]
  medium: ["bench/med1.tsp"]
  large: ["bench/large1.tsp"]

evaluation:
  metric: "gap_to_optimal"
  runs_per_instance: 5
  random_seeds: [42, 123, 456, 789, 1024]

agents:
  tool: "claude"
  strategist:
    model_flags: "--model opus"
  researchers:
    count: 4
    model_flags: "--model sonnet"
    max_iterations_per_assignment: 20

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  stagnation_window: 50
```

## Project Structure

```
algoforge/
├── src/algoforge/
│   ├── cli.py              # CLI entry point
│   ├── config.py           # config loading and validation
│   ├── state.py            # results.tsv, assignments, shutdown
│   ├── worktree.py         # git worktree management
│   ├── orchestrator.py     # session launching and monitoring
│   └── eval.sh             # benchmark evaluation script
├── prompts/
│   ├── strategist.md       # strategist agent instructions
│   └── researcher.md       # researcher agent instructions
├── examples/
│   └── tsp/config.yaml     # TSP test case
└── tests/
```

## Evolution Strategy

**Primary: Decomposed Module Evolution**
- The strategist decomposes the codebase into modules
- Each researcher evolves one module on a dedicated git branch
- The strategist composes the best modules and evaluates the whole

**Fallback: Cross-Pollination**
- Used only when module composition fails due to tight coupling
- Researchers fork the full codebase and evolve holistically

