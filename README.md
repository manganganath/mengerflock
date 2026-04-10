# AlgoForge

A hierarchical multi-agent system that evolves algorithms through autonomous experimentation.

Give AlgoForge a codebase, a build step, and a benchmark — it will coordinate a team of AI coding agents to systematically improve the code's performance. The strategist researches the domain, decomposes the problem, and directs parallel researchers who each evolve a piece of the codebase in a tight loop: hypothesize, implement, build, evaluate, keep or revert.

## Architecture

```
                    Orchestrator
           (launches sessions, manages state)
                   /          \
          Strategist          Researchers (N)
     (research PI, web       (each in own git worktree,
      search, compose,        evolving assigned module)
      reassign, report)
```

The orchestrator is a thin Python layer. The real work happens in the coding agents (Claude Code, Codex, etc.) — each pointed at a markdown instruction file, exactly like giving a developer a spec and letting them run.

**Strategist** — the research PI. Analyzes the codebase, researches the domain via web search, decomposes the code into modules, assigns work, periodically composes the best modules into a combined build, reassigns researchers based on evidence, and writes the final report.

**Researchers** — N parallel workers. Each runs autonomously in its own git worktree, evolving its assigned module. The loop: read the code, form a hypothesis, edit, commit, build, benchmark, keep or revert. Indefinitely, until stopped.

## What Can AlgoForge Evolve?

Any codebase where you can compile, run against benchmarks, and get a number back. The requirements are simple: code + build step + measurable metric.

| Domain | Examples |
|---|---|
| **Combinatorial Optimization** | Routing heuristics, vehicle routing, graph coloring, bin packing, scheduling |
| **Search & Solvers** | SAT solvers, constraint satisfaction, branch-and-bound, local search frameworks |
| **Numerical Computing** | Matrix multiplication kernels, sorting algorithms, compression, signal processing |
| **ML Training** | Neural network training loops, optimizer implementations, data augmentation |
| **Compilers** | Optimization passes, code generation heuristics, register allocation |

The domain-agnostic design means AlgoForge doesn't need to be pre-configured for any specific problem type. The strategist researches the domain autonomously via web search.

## Quick Start

```bash
# Initialize a project
algoforge init --seed ./path/to/seed --config config.yaml

# Run the experiment
algoforge run config.yaml

# Monitor progress
algoforge status

# Gracefully stop (finishes current iterations, then reports)
algoforge stop

# Generate report from completed run
algoforge report
```

## Configuration

```yaml
project:
  name: "my-algorithm"
  mode: "evolve"            # evolve (from seed) or generate (from scratch)
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
  small: ["bench/small1.txt"]
  medium: ["bench/med1.txt"]
  large: ["bench/large1.txt"]

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

## Evolution Strategy

**Primary: Decomposed Module Evolution** — the strategist splits the codebase into modules. Each researcher evolves one module on a dedicated git branch. The strategist periodically merges the best version of each module into a combined build and evaluates the whole. This gives natural parallelism without merge conflicts.

**Fallback: Cross-Pollination** — when module composition fails due to tight coupling, researchers fork the full codebase and evolve holistically. This is a last resort, triggered only after the strategist fails to resolve merge conflicts.

## Design Principles

- **Agents are coding tool sessions**, not custom LLM infrastructure. AlgoForge doesn't make API calls — it launches Claude Code / Codex sessions pointed at instruction files.
- **Git is the state manager.** Worktrees for isolation, branches for versioning, tags for milestones.
- **Filesystem for communication.** Agents read/write a shared `state/` directory. No queues, no IPC.
- **The strategist has web search.** It can autonomously research unfamiliar domains, find papers, and discover seed code.

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
├── examples/               # example project configs
└── tests/
```
