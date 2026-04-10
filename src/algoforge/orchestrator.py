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
            triggered, reason = check_stopping_conditions(
                self.state_dir, self.config, self.start_time,
            )
            if triggered:
                print(f"Stopping: {reason}")
                self.shutdown()
                return

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

        for pid, proc in self.processes.items():
            print(f"Waiting for {pid} to finish...")
            proc.wait(timeout=120)

    def run(self) -> None:
        self.setup_signal_handlers()
        self.launch_strategist()

        for i in range(self.config.agents.researchers.count):
            rid = f"r{i + 1}"
            module = self.config.modules[i % len(self.config.modules)]
            self.launch_researcher(rid, module.name)

        self.monitor()
