from __future__ import annotations

import shlex
import signal
import subprocess
import time
from pathlib import Path

from mengerflock.config import MengerFlockConfig
from mengerflock.state import (
    init_state_dir,
    read_results,
    write_shutdown_flag,
    is_shutdown_requested,
    is_phase1_complete,
    is_phase2_complete,
    is_phase3_complete,
)
from mengerflock.worktree import create_branch, create_worktree


def is_seed_url(seed_path: str) -> bool:
    return seed_path.startswith(("http://", "https://", "git@"))


def init_project(project_dir: Path, config: MengerFlockConfig) -> None:
    # Clone seed if URL
    if is_seed_url(config.project.seed_path):
        seed_dir = project_dir / "seed"
        if not seed_dir.exists():
            subprocess.run(
                ["git", "clone", config.project.seed_path, str(seed_dir)],
                check=True,
            )
            config.project.seed_path = str(seed_dir)

    state_dir = project_dir / "state"
    init_state_dir(state_dir)

    # Create module branches
    for module in config.modules:
        create_branch(project_dir, f"module/{module.name}")


def check_stopping_conditions(
    state_dir: Path,
    config: MengerFlockConfig,
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
    def __init__(self, project_dir: Path, config: MengerFlockConfig):
        self.project_dir = project_dir.resolve()
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
            "tmux", "new-window", "-t", "mengerflock",
            "-n", "strategist",
            "-c", str(self.project_dir),
            f"{tool} {model_flags} --allowedTools 'Edit,Write,Bash,Read,Glob,Grep,WebSearch,WebFetch'"
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
            "tmux", "send-keys", "-t", "mengerflock:strategist",
            prompt, "Enter"
        ], check=True)

    def launch_researcher(self, researcher_id: str, module_name: str) -> None:
        wt_path = self.project_dir / ".worktrees" / researcher_id
        branch = f"module/{module_name}"

        if not wt_path.exists():
            create_worktree(self.project_dir, wt_path, branch)

        # Create symlinks (use absolute paths)
        state_link = wt_path / "state"
        if not state_link.exists():
            state_link.symlink_to(self.state_dir.resolve())

        for name in ["eval.sh", "datasets", "researcher.md"]:
            link = wt_path / name
            src = self.project_dir / name
            if src.exists() and not link.exists():
                link.symlink_to(src.resolve())

        tool = self.config.agents.tool
        model_flags = self.config.agents.researchers.model_flags

        # Create tmux window
        subprocess.run([
            "tmux", "new-window", "-t", "mengerflock",
            "-n", researcher_id,
            "-c", str(wt_path),
            f"{tool} {model_flags} --allowedTools 'Edit,Write,Bash,Read,Glob,Grep,WebSearch,WebFetch'"
        ], check=True)

        # Wait then send prompt
        time.sleep(3)
        prompt = (
            f"Read researcher.md and follow its instructions. "
            f"Your researcher ID is {researcher_id}. "
            f"State, datasets, and eval.sh are symlinked in your working directory."
        )
        subprocess.run([
            "tmux", "send-keys", "-t", f"mengerflock:{researcher_id}",
            prompt, "Enter"
        ], check=True)

    def monitor_phase2(self, poll_interval: float = 30.0) -> str:
        """Monitor Phase 2. Returns reason for exit: 'stopping', 'phase2_complete', 'shutdown', 'exited'."""
        while not self._shutdown:
            # Check if strategist signaled Phase 2 complete (ready for Phase 3)
            if is_phase2_complete(self.state_dir):
                print("Strategist signaled Phase 2 complete. Entering Phase 3.")
                return "phase2_complete"

            # Check stopping conditions
            triggered, reason = check_stopping_conditions(
                self.state_dir, self.config, self.start_time,
            )
            if triggered:
                print(f"Stopping condition met: {reason}")
                return "stopping"

            if is_shutdown_requested(self.state_dir):
                return "shutdown"

            # Check if tmux session still has windows
            result = subprocess.run(
                ["tmux", "list-windows", "-t", "mengerflock"],
                capture_output=True, check=False
            )
            if result.returncode != 0:
                print("All sessions have exited")
                return "exited"

            time.sleep(poll_interval)
        return "shutdown"

    def wait_for_phase3(self, poll_interval: float = 10.0) -> str:
        """Wait for strategist to complete Phase 3.
        Returns: 'complete', 'reenter_phase2', or 'shutdown'."""
        print("Phase 3: Strategist is evaluating holdout and writing reports...")
        while not self._shutdown:
            if is_phase3_complete(self.state_dir):
                print("Phase 3 complete. Experiment finished.")
                return "complete"

            # Check if strategist requests Phase 2 re-entry
            reentry_path = self.state_dir / "reenter_phase2"
            if reentry_path.exists():
                reentry_path.unlink()  # consume the signal
                print("Strategist requests Phase 2 re-entry.")
                return "reenter_phase2"

            # Check if tmux session still alive
            result = subprocess.run(
                ["tmux", "list-windows", "-t", "mengerflock"],
                capture_output=True, check=False
            )
            if result.returncode != 0:
                return "shutdown"

            time.sleep(poll_interval)
        return "shutdown"

    def stop_researchers(self) -> None:
        """Stop researcher and wildcard windows, keep strategist alive."""
        write_shutdown_flag(self.state_dir)

        result = subprocess.run(
            ["tmux", "list-windows", "-t", "mengerflock", "-F", "#{window_name}"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            for window in result.stdout.strip().split('\n'):
                if window and window != "strategist":
                    subprocess.run([
                        "tmux", "send-keys", "-t", f"mengerflock:{window}",
                        "/exit", "Enter"
                    ], check=False)

    def relaunch_researchers(self) -> None:
        """Relaunch researchers for Phase 2 re-entry. Clean up old worktrees first."""
        # Remove shutdown flag so researchers don't immediately exit
        shutdown_path = self.state_dir / "shutdown"
        if shutdown_path.exists():
            shutdown_path.unlink()

        # Clear phase signals
        for f in ["phase2_complete", "phase3_complete"]:
            p = self.state_dir / f
            if p.exists():
                p.unlink()

        count = self.config.agents.researchers.count
        if count is None:
            count = len(self.config.modules)

        for i in range(count):
            rid = f"r{i + 1}"
            module = self.config.modules[i % len(self.config.modules)]
            # Clean up old worktree
            wt_path = self.project_dir / ".worktrees" / rid
            if wt_path.exists():
                from mengerflock.worktree import remove_worktree
                remove_worktree(self.project_dir, wt_path)
            self.launch_researcher(rid, module.name)

        wildcard = getattr(self.config.agents, 'wildcard', None)
        if wildcard:
            wt_path = self.project_dir / ".worktrees" / "w1"
            if wt_path.exists():
                from mengerflock.worktree import remove_worktree
                remove_worktree(self.project_dir, wt_path)
            self.launch_wildcard()

    def shutdown(self, keep_strategist: bool = False) -> None:
        self._shutdown = True
        write_shutdown_flag(self.state_dir)

        result = subprocess.run(
            ["tmux", "list-windows", "-t", "mengerflock", "-F", "#{window_name}"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            for window in result.stdout.strip().split('\n'):
                if window and (not keep_strategist or window != "strategist"):
                    subprocess.run([
                        "tmux", "send-keys", "-t", f"mengerflock:{window}",
                        "/exit", "Enter"
                    ], check=False)

    def wait_for_phase1(self, poll_interval: float = 10.0) -> bool:
        """Wait for strategist to complete Phase 1 (user approval gate).
        Returns True if Phase 1 completed, False if shutdown was requested."""
        print("Waiting for strategist to complete Phase 1 (user approval)...")
        while not self._shutdown:
            if is_phase1_complete(self.state_dir):
                print("Phase 1 complete. Launching researchers.")
                return True
            if is_shutdown_requested(self.state_dir):
                print("Shutdown requested during Phase 1.")
                return False
            time.sleep(poll_interval)
        return False

    def launch_all_researchers(self) -> None:
        """Launch all researcher and wildcard windows."""
        count = self.config.agents.researchers.count
        if count is None:
            count = len(self.config.modules)

        for i in range(count):
            rid = f"r{i + 1}"
            module = self.config.modules[i % len(self.config.modules)]
            self.launch_researcher(rid, module.name)

        wildcard = getattr(self.config.agents, 'wildcard', None)
        if wildcard:
            self.launch_wildcard()

    def run(self) -> None:
        self.setup_signal_handlers()
        max_reentries = self.config.stopping_conditions.max_reentries
        reentry_count = 0

        # Create tmux session
        subprocess.run(["tmux", "new-session", "-d", "-s", "mengerflock"], check=False)

        # === Phase 1: Strategist researches, presents plan, waits for user approval ===
        print("=== Phase 1: Strategist initialization ===")
        self.launch_strategist()

        if not self.wait_for_phase1():
            return

        # === Phase 2: Researchers evolve the codebase ===
        while True:
            print(f"=== Phase 2: Research loop (attempt {reentry_count + 1}) ===")
            self.launch_all_researchers()

            exit_reason = self.monitor_phase2()

            # Stop researchers, keep strategist alive for Phase 3
            self.stop_researchers()

            if exit_reason == "exited" or exit_reason == "shutdown":
                print("Experiment ended.")
                return

            # === Phase 3: Strategist evaluates holdout and writes reports ===
            print("=== Phase 3: Evaluation and reporting ===")
            phase3_result = self.wait_for_phase3()

            if phase3_result == "complete":
                print("Experiment complete. Shutting down.")
                self.shutdown()
                return

            if phase3_result == "reenter_phase2":
                reentry_count += 1
                if reentry_count >= max_reentries:
                    print(f"Max re-entries reached ({max_reentries}). Finishing.")
                    self.shutdown()
                    return
                print(f"Re-entering Phase 2 (attempt {reentry_count + 1}/{max_reentries + 1})...")
                self.relaunch_researchers()
                continue

            # shutdown or unexpected
            self.shutdown()
            return

    def launch_wildcard(self) -> None:
        wt_path = self.project_dir / ".worktrees" / "w1"
        branch = "wildcard/w1"

        create_branch(self.project_dir, branch, start_point="baseline")
        if not wt_path.exists():
            create_worktree(self.project_dir, wt_path, branch)

        # Restricted state: only results.tsv for writing, no full state/ access
        wt_state = wt_path / "state"
        wt_state.mkdir(exist_ok=True)

        results_link = wt_state / "results.tsv"
        if not results_link.exists():
            results_link.symlink_to((self.state_dir / "results.tsv").resolve())

        # Shutdown detection — symlink the shutdown flag location
        # (wildcard checks if state/shutdown exists)

        objectives_link = wt_path / "objectives.md"
        objectives_src = self.state_dir / "objectives.md"
        if objectives_src.exists() and not objectives_link.exists():
            objectives_link.symlink_to(objectives_src.resolve())

        for name in ["eval.sh", "datasets", "wildcard.md"]:
            link = wt_path / name
            src = self.project_dir / name
            if src.exists() and not link.exists():
                link.symlink_to(src.resolve())

        tool = self.config.agents.tool
        wildcard_cfg = self.config.agents.wildcard
        model_flags = wildcard_cfg.model_flags

        subprocess.run([
            "tmux", "new-window", "-t", "mengerflock",
            "-n", "w1",
            "-c", str(wt_path),
            f"{tool} {model_flags} --allowedTools 'Edit,Write,Bash,Read,Glob,Grep'"
        ], check=True)

        time.sleep(3)
        prompt = (
            "Read wildcard.md and follow its instructions. "
            "Read objectives.md for the experiment's high-level goals. "
            "Your ID is w1. "
            "Datasets and eval.sh are in your working directory."
        )
        subprocess.run([
            "tmux", "send-keys", "-t", "mengerflock:w1",
            prompt, "Enter"
        ], check=True)
