#!/usr/bin/env python3
"""Launch MengerFlock on this experiment."""
import sys
sys.path.insert(0, sys.argv[1])
from mengerflock.config import load_config
from mengerflock.orchestrator import Orchestrator, init_project
from pathlib import Path
config = load_config("config.yaml")
project_dir = Path.cwd()
if not (project_dir / "state").exists():
    init_project(project_dir, config)
orchestrator = Orchestrator(project_dir, config)
print(f"Starting MengerFlock: {config.project.name}")
print(f"  Wildcard: {'yes' if config.agents.wildcard else 'no'}")
orchestrator.run()
