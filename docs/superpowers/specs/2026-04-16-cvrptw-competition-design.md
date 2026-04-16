# CVRPTW Competition Preparation — Design Spec

## Goal

Prepare MengerFlock to compete in the GECCO 2026 ML4VRP competition (CVRPTW track) by: (1) adding two small domain-agnostic improvements to MengerFlock, (2) setting up a CVRPTW experiment template with PyVRP as the seed, and (3) submitting a 2-page GECCO abstract by April 21.

## Scope Boundary

- **Competition-facing docs** (abstract, algorithm description PDF): use VRP/CVRPTW/ML4VRP/GECCO terminology freely.
- **MengerFlock internals** (prompts, README, config field names, code): stay domain-agnostic. No VRP-specific logic in the engine.

## Deadlines

- **April 21, 2026**: 2-page abstract submission
- **June 13, 2026**: Algorithm description + solution files submission
- **July 13-17, 2026**: GECCO conference (results announced)

---

## Part 1: MengerFlock Improvements (iteration-8)

Two domain-agnostic additions. No VRP-specific code.

### 1a. Pre-check Step in Evaluation

**Problem**: If a researcher's change breaks basic checks (syntax errors, constraint violations), eval.sh still runs the full solver before failing. This wastes minutes per hypothesis.

**Solution**: New optional `pre_check` field in config.yaml. If set, the orchestrator (or researcher prompt) runs it before eval.sh. Non-zero exit code = skip eval.sh, log as crash.

```yaml
evaluation:
  metric: "weighted_objective"
  pre_check: "python scripts/verify_solution.py"  # optional, runs before eval.sh
```

**Implementation**: ~10 lines in orchestrator or researcher prompt to check for this field and run the command before eval.sh.

### 1b. Training Data Sourcing Config

**Problem**: The current config has `training.train` and `training.validation` paths but no way to express how data should be sourced if those paths are empty.

**Solution**: Flat fields under `training` to guide the strategist's Phase 1 Q&A:

```yaml
training:
  train: ""
  validation: ""
  data_source: "split"                # "split" | "generate" | "download" | "manual"
  split_source: "datasets/all/"       # only used if data_source: "split"
  split_ratios: [0.6, 0.2, 0.2]      # only used if data_source: "split"
  stratify_by: "instance_type"        # optional, only used if data_source: "split"
```

**Behavior**: Strategist reads `data_source` to know the default approach, confirms with user during Phase 1 Q&A, and ignores irrelevant fields. If `train` and `validation` paths already contain files, the whole sourcing step is skipped.

**Implementation**: Strategist prompt update + config dataclass update. No orchestrator code changes.

---

## Part 2: CVRPTW Template

### Directory Structure

```
projects/cvrptw/
├── original-seed/              # PyVRP source (git clone)
├── datasets/
│   ├── all/                    # Full corpus before splitting
│   ├── train/                  # ~60% (after stratified split)
│   ├── validation/             # ~20%
│   └── holdout/                # ~20%
├── config.yaml
├── eval.sh
├── paper.md
└── scripts/
    └── verify_solution.py      # Pre-check: validates route feasibility
```

### Seed: PyVRP

- Git clone into `original-seed/`.
- Researchers modify only the Python heuristic layer via module config:
  - `pyvrp/search/` — local search and ALNS logic
  - `pyvrp/crossover/` — genetic operators
  - `pyvrp/diversity/` — population penalty coefficients
- C++ backend is untouchable (not listed in any module's `files`).

### Datasets

- **Solomon** 100-node instances (56 instances, 6 types: C1, C2, R1, R2, RC1, RC2)
- **Homberger & Gehring** 200 and 400-node instances
- **Split**: Stratified by instance type (C1, C2, R1, R2, RC1, RC2) so each split has balanced representation across types.
- **Ratios**: 60% train, 20% validation, 20% holdout (configurable via `split_ratios`).

### eval.sh

- Signature: `./eval.sh <binary> <instance> <seed> <timeout>`
- Runs PyVRP on the instance
- Verifies route feasibility (capacity, time windows)
- Outputs single number to stdout: `1000 * NV + TD` (number of vehicles * 1000 + total distance)
- Prints NV and TD separately to stderr for researcher visibility
- Returns non-zero exit code + "FAIL" on infeasible or timeout

### verify_solution.py (pre-check)

- Validates that the solver output is a feasible CVRPTW solution
- Checks: all customers visited exactly once, capacity constraints, time window constraints, depot return
- Fast (~1 second), runs before the full eval.sh scoring
- Referenced by `evaluation.pre_check` in config.yaml

### paper.md

Analysis document for the strategist, covering:

- PyVRP architecture (C++ core vs Python heuristic layer)
- Heuristic components: ALNS destroy/repair operators, crossover mechanisms, penalty management
- Known improvement directions from the PyVRP+ paper (evolved parent selection, adaptive stratified diversity)
- Module decomposition recommendation for researcher assignments
- F1 scoring note: robustness across instance families (C, R, RC) matters more than peak performance on any single instance. Being consistently top-8 across all instances beats being 1st on half and 9th on the rest.

### config.yaml

```yaml
project:
  name: "pyvrp"
  seed_path: "./seed/"
  original_seed_path: "./original-seed/"
  language: "python"
  paper: "./paper.md"

modules:
  - name: "search"
    files: ["pyvrp/search/*.py"]
    description: "Local search and ALNS destroy/repair operators"
  - name: "crossover"
    files: ["pyvrp/crossover/*.py"]
    description: "Genetic crossover mechanisms"
  - name: "diversity"
    files: ["pyvrp/diversity/*.py"]
    description: "Population penalty coefficients and diversity management"

build:
  command: "pip install -e . --quiet"
  binary: "python -m pyvrp"

benchmarks:
  small: ["datasets/holdout/solomon_100_*"]
  medium: ["datasets/holdout/homberger_200_*"]
  large: ["datasets/holdout/homberger_400_*"]

training:
  train: "datasets/train/"
  validation: "datasets/validation/"
  data_source: "split"
  split_source: "datasets/all/"
  split_ratios: [0.6, 0.2, 0.2]
  stratify_by: "instance_type"

evaluation:
  metric: "weighted_objective"
  pre_check: "python scripts/verify_solution.py"
  runs_per_instance: 5
  random_seeds: [42, 123, 456, 789, 1024]

agents:
  tool: "claude"
  strategist:
    model_flags: "--model opus"
  researchers:
    model_flags: "--model sonnet"
    max_iterations_per_assignment: 20
  wildcard:
    model_flags: "--model opus"

stopping_conditions:
  max_total_iterations: 500
  max_hours: 24
  stagnation_window: 50
```

---

## Part 3: 2-Page GECCO Abstract

### Format
- ACM `sigconf` 2-page competition entry (verify exact template from GECCO 2026 submission instructions)
- Author: Nuwan Ganganath

### Content
- **Title**: Something like "MengerFlock: Autonomous Multi-Agent Algorithm Evolution for CVRPTW"
- **Abstract**: Multi-agent system that evolves metaheuristic components of PyVRP through autonomous experimentation
- **Section 1 — Introduction**: MengerFlock architecture, the problem it solves (automated algorithm design), why LLM-driven code evolution is novel for VRP
- **Section 2 — Approach**: Three-phase lifecycle (research plan → parallel hypothesis testing → holdout evaluation), key process innovations (regression gate, isolated testing, single-keep composition, F1-aware robustness targeting)
- **Section 3 — Preliminary Results**: Table showing baseline PyVRP vs evolved PyVRP on a subset of Solomon instances from a short (~24h) experiment. Even modest improvement validates the pipeline.
- **Section 4 — Conclusion**: Summary and reference to June submission
- **References**: PyVRP paper, PyVRP+ paper, MengerFlock repo

### Timeline
- Days 1-2: Set up template, download PyVRP + datasets, get eval.sh working
- Day 3: Run 24h experiment on Solomon 100-node training instances
- Day 4: Collect results, write abstract
- Day 5 (April 21): Submit

---

## What This Spec Does NOT Cover

- The actual experiment execution (that's runtime, not implementation)
- Solution file export in CVRPLIB format for June submission (will be added later)
- Conference registration
- The algorithm description PDF for June (written after experiments complete)

---

## Success Criteria

1. `mengerflock new cvrptw-experiment-1` creates a working experiment from the template
2. `mengerflock run` launches the multi-agent system targeting PyVRP's heuristic layer
3. eval.sh correctly scores CVRPTW solutions using `1000*NV + TD`
4. Pre-check catches infeasible routes before full evaluation
5. A 2-page abstract is submitted by April 21
6. By June 13, evolved solutions for all provided instances are packaged in CVRPLIB format
