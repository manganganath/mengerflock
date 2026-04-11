import pytest
from pathlib import Path
from mengerflock.state import (
    init_state_dir, append_result, read_results,
    write_shutdown_flag, is_shutdown_requested,
    write_interrupt, read_interrupt, acknowledge_interrupt,
    write_objectives, read_objectives,
    append_baseline_holdout, read_baseline_holdout,
)

def test_init_creates_interrupts_dir(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    assert (state / "interrupts").is_dir()

def test_init_creates_assignments_dir(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    assert (state / "assignments").is_dir()

def test_init_creates_results_tsv(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    assert (state / "results.tsv").exists()
    content = (state / "results.tsv").read_text()
    assert "timestamp" in content

def test_append_and_read_results(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    append_result(state, {
        "researcher": "r1", "module": "core", "commit": "abc123",
        "metric_avg": "0.05", "metric_best": "0.03",
        "status": "keep", "hypothesis": "test", "description": "test desc",
    })
    results = read_results(state)
    assert len(results) == 1
    assert results[0]["researcher"] == "r1"

def test_shutdown_flag(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    assert not is_shutdown_requested(state)
    write_shutdown_flag(state)
    assert is_shutdown_requested(state)

def test_write_and_read_interrupt(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    write_interrupt(state, "r1", "Stop exploring SkipG. Focus on candidate edges.")
    content = read_interrupt(state, "r1")
    assert "SkipG" in content

def test_acknowledge_interrupt(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    write_interrupt(state, "r1", "redirect content")
    acknowledge_interrupt(state, "r1")
    assert not (state / "interrupts" / "r1.md").exists()
    assert (state / "interrupts" / "r1.ack.md").exists()

def test_read_interrupt_returns_none_when_absent(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    assert read_interrupt(state, "r1") is None

def test_write_and_read_objectives(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    write_objectives(state, "Improve solution quality.\nReduce gap to optimal.")
    content = read_objectives(state)
    assert "Improve solution quality" in content

def test_write_and_read_baseline_holdout(tmp_path):
    state = tmp_path / "state"
    init_state_dir(state)
    append_baseline_holdout(state, {
        "researcher": "baseline", "module": "baseline", "commit": "abc123",
        "metric_avg": "0.083", "metric_best": "0.048",
        "status": "baseline", "hypothesis": "original seed", "description": "unmodified LKH-2",
    })
    results = read_baseline_holdout(state)
    assert len(results) == 1
    assert results[0]["researcher"] == "baseline"
    assert results[0]["metric_avg"] == "0.083"
