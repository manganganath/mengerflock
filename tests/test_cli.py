import os
import pytest
from pathlib import Path
from click.testing import CliRunner
from mengerflock.cli import main
from mengerflock.state import init_state_dir, append_result


@pytest.fixture
def project_dir(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    return tmp_path


def test_status_no_project(tmp_path):
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(main, ["status"])
        assert "No active project" in result.output
    finally:
        os.chdir(old_cwd)


def test_status_with_results(project_dir):
    append_result(project_dir / "state", {
        "researcher": "r1", "module": "core", "commit": "abc",
        "metric_avg": "0.05", "metric_best": "0.03",
        "status": "keep", "hypothesis": "test", "description": "desc",
    })
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = runner.invoke(main, ["status"])
        assert "Keep: 1" in result.output
    finally:
        os.chdir(old_cwd)


def test_stop_creates_shutdown(project_dir):
    old_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        runner = CliRunner()
        result = runner.invoke(main, ["stop"])
        assert "Shutdown signal sent" in result.output
        assert (project_dir / "state" / "shutdown").exists()
    finally:
        os.chdir(old_cwd)


def test_report_generates_file(project_dir):
    append_result(project_dir / "state", {
        "researcher": "r1", "module": "core", "commit": "abc",
        "metric_avg": "0.05", "metric_best": "0.03",
        "status": "keep", "hypothesis": "test hyp", "description": "desc",
    })
    old_cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        runner = CliRunner()
        result = runner.invoke(main, ["report"])
        assert "Experimentation report" in result.output
        report_path = project_dir / "report" / "experimentation-report.md"
        assert report_path.exists()
        content = report_path.read_text()
        assert "MengerFlock" in content
        assert "test hyp" in content
    finally:
        os.chdir(old_cwd)
