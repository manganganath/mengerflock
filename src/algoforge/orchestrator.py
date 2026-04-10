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
from algoforge.worktree import create_branch, create_worktree


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


class Orchestrator:
    def __init__(self, project_dir: Path, config: AlgoForgeConfig):
        self.project_dir = project_dir
        self.config = config
        self.state_dir = project_dir / "state"
        self.start_time = time.time()
        self._shutdown = False

    def _handle_signal(self, signum, frame):
        self._shutdown = True
        write_shutdown_flag(self.state_dir)

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def launch_strategist(self) -> None:
        tool = self.config.agents.tool
        model_flags = self.config.agents.strategist.model_flags

        # Create tmux window with interactive claude
        subprocess.run([
            "tmux", "new-window", "-t", "algoforge",
            "-n", "strategist",
            "-c", str(self.project_dir),
            f"{tool} {model_flags}"
        ], check=True)

        # Wait for claude to start, then send the prompt
        time.sleep(3)
        prompt = (
            "Read strategist.md and follow its instructions. "
            "This is the project root directory. "
            "State files are in state/. Benchmarks in datasets/. "
            "Eval script is eval.sh. "
            "After initialization, enter Phase 2 and monitor continuously."
        )
        subprocess.run([
            "tmux", "send-keys", "-t", "algoforge:strategist",
            prompt, "Enter"
        ], check=True)

    def launch_researcher(self, researcher_id: str, module_name: str) -> None:
        wt_path = self.project_dir / ".worktrees" / researcher_id
        branch = f"module/{module_name}"

        if not wt_path.exists():
            create_worktree(self.project_dir, wt_path, branch)

        # Create symlinks
        state_link = wt_path / "state"
        if not state_link.exists():
            state_link.symlink_to(self.state_dir)

        for name in ["eval.sh", "datasets"]:
            link = wt_path / name
            src = self.project_dir / name
            if src.exists() and not link.exists():
                link.symlink_to(src)

        tool = self.config.agents.tool
        model_flags = self.config.agents.researchers.model_flags

        # Create tmux window
        subprocess.run([
            "tmux", "new-window", "-t", "algoforge",
            "-n", researcher_id,
            "-c", str(wt_path),
            f"{tool} {model_flags}"
        ], check=True)

        # Wait then send prompt
        time.sleep(3)
        prompt = (
            f"Read researcher.md and follow its instructions. "
            f"Your researcher ID is {researcher_id}. "
            f"State, datasets, and eval.sh are symlinked in your working directory."
        )
        subprocess.run([
            "tmux", "send-keys", "-t", f"algoforge:{researcher_id}",
            prompt, "Enter"
        ], check=True)

    def monitor(self, poll_interval: float = 30.0) -> None:
        while not self._shutdown:
            triggered, reason = check_stopping_conditions(
                self.state_dir, self.config, self.start_time,
            )
            if triggered:
                print(f"Stopping: {reason}")
                self.shutdown()
                return

            # Check if tmux session still has windows
            result = subprocess.run(
                ["tmux", "list-windows", "-t", "algoforge"],
                capture_output=True, check=False
            )
            if result.returncode != 0:
                print("All sessions have exited")
                return

            time.sleep(poll_interval)

    def shutdown(self) -> None:
        self._shutdown = True
        write_shutdown_flag(self.state_dir)

        # Send /exit to all windows
        result = subprocess.run(
            ["tmux", "list-windows", "-t", "algoforge", "-F", "#{window_name}"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            for window in result.stdout.strip().split('\n'):
                if window:
                    subprocess.run([
                        "tmux", "send-keys", "-t", f"algoforge:{window}",
                        "/exit", "Enter"
                    ], check=False)

    def run(self) -> None:
        self.setup_signal_handlers()

        # Create tmux session
        subprocess.run(["tmux", "new-session", "-d", "-s", "algoforge"], check=False)

        self.launch_strategist()

        for i in range(self.config.agents.researchers.count):
            rid = f"r{i + 1}"
            module = self.config.modules[i % len(self.config.modules)]
            self.launch_researcher(rid, module.name)

        self.monitor()
